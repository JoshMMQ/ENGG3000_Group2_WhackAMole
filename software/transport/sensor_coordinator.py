"""Laptop-owned sequential coordinator for three Wi-Fi UDP sensor stations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import isfinite
import socket
import time
from typing import Callable, Optional, Protocol

from software.game.sensor_scan import SensorId, SensorReading, SensorScan
from .sensor_scan_packet import encode_sensor_scan_packet
from .sensor_station_protocol import (
    SENSOR_INDICES,
    STATION_CONTROL_PORT,
    UINT32_MAX,
    MeasureResult,
    decode_hello,
    decode_measure_result,
    encode_measure_command,
)
from .udp_receiver import DEFAULT_PORT as SENSOR_SCAN_PORT


DEFAULT_CONTROL_HOST = "0.0.0.0"
DEFAULT_OUTPUT_HOST = "127.0.0.1"
DEFAULT_SLOT_DURATION_S = 0.035
DEFAULT_RESULT_TIMEOUT_S = 0.030
DEFAULT_STATION_STALE_TIMEOUT_S = 3.0
DISCOVERY_POLL_INTERVAL_S = 0.25
CONTROL_BUFFER_SIZE = 256

Endpoint = tuple[str, int]
Clock = Callable[[], float]
Wait = Callable[[float], None]

_SENSOR_IDS = {
    1: SensorId.S1,
    2: SensorId.S2,
    3: SensorId.S3,
}


class DatagramSocket(Protocol):
    def settimeout(self, value: Optional[float]) -> None: ...

    def recvfrom(self, buffer_size: int) -> tuple[bytes, Endpoint]: ...

    def sendto(self, data: bytes, address: Endpoint) -> int: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class StationRegistration:
    endpoint: Endpoint
    last_hello_s: float


class SensorCoordinator:
    """Register stations, run ordered cycles, and forward Version 3 scans."""

    def __init__(
        self,
        *,
        control_host: str = DEFAULT_CONTROL_HOST,
        control_port: int = STATION_CONTROL_PORT,
        output_host: str = DEFAULT_OUTPUT_HOST,
        output_port: int = SENSOR_SCAN_PORT,
        slot_duration_s: float = DEFAULT_SLOT_DURATION_S,
        result_timeout_s: float = DEFAULT_RESULT_TIMEOUT_S,
        station_stale_timeout_s: float = DEFAULT_STATION_STALE_TIMEOUT_S,
        initial_cycle_id: int = 0,
        control_socket: Optional[DatagramSocket] = None,
        output_socket: Optional[DatagramSocket] = None,
        clock: Clock = time.monotonic,
        wait: Wait = time.sleep,
    ) -> None:
        _validate_port(control_port, "control_port")
        _validate_port(output_port, "output_port")
        if not isfinite(slot_duration_s) or slot_duration_s <= 0.0:
            raise ValueError("slot_duration_s must be positive")
        if (
            not isfinite(result_timeout_s)
            or result_timeout_s <= 0.0
            or result_timeout_s > slot_duration_s
        ):
            raise ValueError(
                "result_timeout_s must be positive and no longer than one slot"
            )
        if (
            not isfinite(station_stale_timeout_s)
            or station_stale_timeout_s <= 0.0
        ):
            raise ValueError("station_stale_timeout_s must be positive")
        if (
            isinstance(initial_cycle_id, bool)
            or not isinstance(initial_cycle_id, int)
            or initial_cycle_id < 0
            or initial_cycle_id > UINT32_MAX
        ):
            raise ValueError("initial_cycle_id must be an unsigned 32-bit integer")

        self.control_address = (control_host, control_port)
        self.output_address = (output_host, output_port)
        self.slot_duration_s = float(slot_duration_s)
        self.result_timeout_s = float(result_timeout_s)
        self.station_stale_timeout_s = float(station_stale_timeout_s)
        self._clock = clock
        self._wait = wait
        self._next_cycle_id = initial_cycle_id
        self._registrations: dict[int, StationRegistration] = {}

        self._owns_control_socket = control_socket is None
        self._owns_output_socket = output_socket is None
        if control_socket is None:
            created_control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            created_control_socket.bind(self.control_address)
            control_socket = created_control_socket
        if output_socket is None:
            output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._control_socket = control_socket
        self._output_socket = output_socket

    @property
    def next_cycle_id(self) -> int:
        return self._next_cycle_id

    def active_registrations(
        self,
        now_s: Optional[float] = None,
    ) -> dict[int, StationRegistration]:
        """Return a snapshot after removing expired station heartbeats."""

        active_now_s = self._clock() if now_s is None else now_s
        stale_indices = [
            sensor_index
            for sensor_index, registration in self._registrations.items()
            if active_now_s - registration.last_hello_s
            >= self.station_stale_timeout_s
        ]
        for sensor_index in stale_indices:
            del self._registrations[sensor_index]
        return dict(self._registrations)

    def register_hello(
        self,
        packet: object,
        endpoint: Endpoint,
        *,
        now_s: Optional[float] = None,
    ) -> bool:
        """Register or refresh the endpoint named by one valid hello."""

        hello = decode_hello(packet)
        if hello is None or not _valid_endpoint(endpoint):
            return False
        heartbeat_s = self._clock() if now_s is None else now_s
        self._registrations[hello.sensor_index] = StationRegistration(
            endpoint=endpoint,
            last_hello_s=heartbeat_s,
        )
        return True

    def all_stations_registered(self, now_s: Optional[float] = None) -> bool:
        return set(self.active_registrations(now_s)) == set(SENSOR_INDICES)

    def wait_for_stations(self) -> None:
        """Process hello datagrams until all three active IDs are present."""

        while not self.all_stations_registered():
            deadline_s = self._clock() + DISCOVERY_POLL_INTERVAL_S
            received = self._receive_until(deadline_s)
            if received is None:
                continue
            packet, endpoint = received
            self.register_hello(packet, endpoint)

    def run_cycle(self) -> SensorScan:
        """Request S1/S2/S3 in order and forward exactly one complete scan."""

        registrations = self.active_registrations()
        if set(registrations) != set(SENSOR_INDICES):
            raise RuntimeError("S1, S2, and S3 must be registered before a cycle")

        cycle_id = self._next_cycle_id
        self._next_cycle_id = (cycle_id + 1) & UINT32_MAX
        cycle_started_s = self._clock()
        readings: list[SensorReading] = []

        for slot_offset, sensor_index in enumerate(SENSOR_INDICES):
            request_time_s = self._clock()
            endpoint = registrations[sensor_index].endpoint
            command = encode_measure_command(cycle_id, sensor_index)
            self._control_socket.sendto(command, endpoint)

            result = self._wait_for_matching_result(
                cycle_id=cycle_id,
                sensor_index=sensor_index,
                expected_endpoint=endpoint,
                deadline_s=request_time_s + self.result_timeout_s,
            )
            readings.append(
                self._make_reading(
                    sensor_index,
                    result,
                    request_time_s=request_time_s,
                )
            )

            slot_ends_s = cycle_started_s + (
                (slot_offset + 1) * self.slot_duration_s
            )
            remaining_s = slot_ends_s - self._clock()
            if remaining_s > 0.0:
                self._wait(remaining_s)

        scan = SensorScan(cycle_id=cycle_id, readings=tuple(readings))
        self._output_socket.sendto(
            encode_sensor_scan_packet(scan),
            self.output_address,
        )
        return scan

    def serve_forever(self) -> None:
        """Continuously discover stations and coordinate complete scans."""

        while True:
            self.wait_for_stations()
            self.run_cycle()

    def close(self) -> None:
        if self._owns_control_socket:
            self._control_socket.close()
        if self._owns_output_socket:
            self._output_socket.close()

    def _wait_for_matching_result(
        self,
        *,
        cycle_id: int,
        sensor_index: int,
        expected_endpoint: Endpoint,
        deadline_s: float,
    ) -> Optional[MeasureResult]:
        while self._clock() < deadline_s:
            received = self._receive_until(deadline_s)
            if received is None:
                return None
            packet, endpoint = received
            if self.register_hello(packet, endpoint):
                continue

            result = decode_measure_result(packet)
            if result is None:
                continue
            if endpoint != expected_endpoint:
                continue
            if result.cycle_id != cycle_id:
                continue
            if result.sensor_index != sensor_index:
                continue
            if result.valid and result.distance_mm <= 0.0:
                continue
            return result
        return None

    def _receive_until(
        self,
        deadline_s: float,
    ) -> Optional[tuple[bytes, Endpoint]]:
        remaining_s = deadline_s - self._clock()
        if remaining_s <= 0.0:
            return None
        self._control_socket.settimeout(remaining_s)
        try:
            return self._control_socket.recvfrom(CONTROL_BUFFER_SIZE)
        except (BlockingIOError, socket.timeout, TimeoutError):
            return None

    def _make_reading(
        self,
        sensor_index: int,
        result: Optional[MeasureResult],
        *,
        request_time_s: float,
    ) -> SensorReading:
        sensor_id = _SENSOR_IDS[sensor_index]
        if result is None:
            return SensorReading(
                sensor_id=sensor_id,
                distance_mm=None,
                valid=False,
                sample_time_ms=_monotonic_ms(request_time_s),
            )

        accepted_time_ms = _monotonic_ms(self._clock())
        return SensorReading(
            sensor_id=sensor_id,
            distance_mm=result.distance_mm if result.valid else None,
            valid=result.valid,
            sample_time_ms=accepted_time_ms,
        )


def _monotonic_ms(value_s: float) -> int:
    return max(0, int(value_s * 1000.0))


def _valid_endpoint(endpoint: object) -> bool:
    return (
        isinstance(endpoint, tuple)
        and len(endpoint) == 2
        and isinstance(endpoint[0], str)
        and isinstance(endpoint[1], int)
        and not isinstance(endpoint[1], bool)
        and 0 <= endpoint[1] <= 65535
    )


def _validate_port(port: int, field_name: str) -> None:
    if (
        isinstance(port, bool)
        or not isinstance(port, int)
        or port < 0
        or port > 65535
    ):
        raise ValueError(f"{field_name} must be an integer from 0 to 65535")


def _positive_milliseconds(raw_value: str) -> float:
    value_ms = float(raw_value)
    if not isfinite(value_ms) or value_ms <= 0.0:
        raise argparse.ArgumentTypeError("duration must be positive")
    return value_ms / 1000.0


def _positive_seconds(raw_value: str) -> float:
    value_s = float(raw_value)
    if not isfinite(value_s) or value_s <= 0.0:
        raise argparse.ArgumentTypeError("duration must be positive")
    return value_s


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Coordinate S1/S2/S3 UDP stations and emit Version 3 scans."
    )
    parser.add_argument("--bind-host", default=DEFAULT_CONTROL_HOST)
    parser.add_argument("--control-port", default=STATION_CONTROL_PORT, type=int)
    parser.add_argument("--output-host", default=DEFAULT_OUTPUT_HOST)
    parser.add_argument("--output-port", default=SENSOR_SCAN_PORT, type=int)
    parser.add_argument(
        "--slot-duration-ms",
        default=DEFAULT_SLOT_DURATION_S,
        type=_positive_milliseconds,
        metavar="MS",
    )
    parser.add_argument(
        "--result-timeout-ms",
        default=DEFAULT_RESULT_TIMEOUT_S,
        type=_positive_milliseconds,
        metavar="MS",
    )
    parser.add_argument(
        "--station-stale-timeout-s",
        default=DEFAULT_STATION_STALE_TIMEOUT_S,
        type=_positive_seconds,
        metavar="SECONDS",
    )
    args = parser.parse_args(argv)

    try:
        coordinator = SensorCoordinator(
            control_host=args.bind_host,
            control_port=args.control_port,
            output_host=args.output_host,
            output_port=args.output_port,
            slot_duration_s=args.slot_duration_ms,
            result_timeout_s=args.result_timeout_ms,
            station_stale_timeout_s=args.station_stale_timeout_s,
        )
    except ValueError as error:
        parser.error(str(error))

    print(
        f"Sensor coordinator listening on {args.bind_host}:{args.control_port}; "
        f"forwarding scans to {args.output_host}:{args.output_port}",
        flush=True,
    )
    try:
        coordinator.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        coordinator.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
