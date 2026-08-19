"""Non-blocking input for the temporary HC-SR04 USB bench sketches.

This module intentionally remains separate from the wireless gameplay packet
contract.  The flat JSON lines are useful for a two-board diagnostic monitor,
but independent USB readings are not a time-matched pair for triangulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError, loads
from math import isfinite
from typing import Optional, Protocol


DEFAULT_BAUD_RATE = 115200
MAX_READ_BYTES = 16_384
MAX_BUFFER_BYTES = 65_536


class SerialByteStream(Protocol):
    """Small pySerial-compatible boundary used by the polling source."""

    @property
    def in_waiting(self) -> int:
        ...

    def read(self, size: int = 1) -> bytes:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class BenchSensorReading:
    """One validated JSON line emitted by a sensor bench sketch."""

    node_id: str
    sensor_id: str
    distance_mm: Optional[float]
    valid: bool
    sample_us: int


@dataclass(frozen=True)
class SerialPortDescription:
    """A serial device name and the description reported by the OS."""

    device: str
    description: str


def parse_bench_reading(raw_line: object) -> Optional[BenchSensorReading]:
    """Parse one flat bench-sketch JSON line, dropping malformed input."""

    if isinstance(raw_line, bytes):
        try:
            text = raw_line.decode("utf-8")
        except UnicodeDecodeError:
            return None
    elif isinstance(raw_line, str):
        text = raw_line
    else:
        return None

    try:
        payload = loads(text.strip())
    except (JSONDecodeError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None

    node_id = _nonempty_text(payload.get("node_id"))
    sensor_id = _nonempty_text(payload.get("sensor_id"))
    valid = payload.get("valid")
    sample_us = _nonnegative_integer(payload.get("sample_us"))

    if node_id is None or sensor_id is None or not isinstance(valid, bool):
        return None
    if sample_us is None:
        return None

    distance_value = payload.get("distance_mm")
    if valid:
        distance_mm = _nonnegative_number(distance_value)
        if distance_mm is None:
            return None
    else:
        if distance_value is not None:
            return None
        distance_mm = None

    return BenchSensorReading(
        node_id=node_id,
        sensor_id=sensor_id,
        distance_mm=distance_mm,
        valid=valid,
        sample_us=sample_us,
    )


class SerialSensorSource:
    """Drain complete JSON lines from one serial device without blocking."""

    def __init__(
        self,
        port: str,
        baud_rate: int = DEFAULT_BAUD_RATE,
        stream: Optional[SerialByteStream] = None,
    ) -> None:
        if not port.strip():
            raise ValueError("port must not be empty")
        if baud_rate <= 0:
            raise ValueError("baud_rate must be positive")

        self.port = port
        self._stream = stream or _open_serial_stream(port, baud_rate)
        self._buffer = bytearray()

    def poll_readings(self) -> tuple[BenchSensorReading, ...]:
        """Return every complete valid reading currently waiting on the port."""

        waiting = max(0, int(self._stream.in_waiting))
        if waiting <= 0:
            return ()

        incoming = self._stream.read(min(waiting, MAX_READ_BYTES))
        if not incoming:
            return ()
        if not isinstance(incoming, bytes):
            raise TypeError("serial stream read() must return bytes")

        self._buffer.extend(incoming)
        if len(self._buffer) > MAX_BUFFER_BYTES and b"\n" not in self._buffer:
            self._buffer.clear()
            return ()

        lines = self._buffer.split(b"\n")
        self._buffer = bytearray(lines.pop())

        readings = []
        for line in lines:
            reading = parse_bench_reading(bytes(line).rstrip(b"\r"))
            if reading is not None:
                readings.append(reading)
        return tuple(readings)

    def close(self) -> None:
        self._stream.close()


def available_serial_ports() -> tuple[SerialPortDescription, ...]:
    """List ports without importing pySerial until the function is called."""

    try:
        from serial.tools import list_ports
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyserial is required; install it with "
            "'.venv/bin/python -m pip install -r requirements.txt'"
        ) from exc

    ports = (
        SerialPortDescription(device=port.device, description=port.description)
        for port in list_ports.comports()
    )
    return tuple(sorted(ports, key=lambda port: port.device))


def _open_serial_stream(port: str, baud_rate: int) -> SerialByteStream:
    try:
        import serial
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyserial is required; install it with "
            "'.venv/bin/python -m pip install -r requirements.txt'"
        ) from exc

    return serial.Serial(port=port, baudrate=baud_rate, timeout=0)


def _nonempty_text(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _nonnegative_integer(value: object) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not isfinite(number) or number < 0 or number != int(number):
        return None
    return int(number)


def _nonnegative_number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not isfinite(number) or number < 0:
        return None
    return number
