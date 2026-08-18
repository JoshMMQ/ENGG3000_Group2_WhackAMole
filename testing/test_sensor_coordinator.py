import json
import socket
import unittest
from typing import Callable, Optional

from software.game.sensor_scan import SensorId
from software.transport.sensor_coordinator import SensorCoordinator
from software.transport.sensor_scan_packet import parse_sensor_scan_packet
from software.transport.sensor_station_protocol import (
    UINT32_MAX,
    decode_measure_command,
    encode_hello,
    encode_measure_result,
)


Endpoint = tuple[str, int]


class FakeClock:
    def __init__(self, now_s: float = 1.0) -> None:
        self.now_s = now_s

    def __call__(self) -> float:
        return self.now_s

    def advance(self, duration_s: float) -> None:
        self.now_s += max(0.0, duration_s)


class FakeSocket:
    def __init__(
        self,
        clock: FakeClock,
        on_send: Optional[Callable[[bytes, Endpoint], None]] = None,
    ) -> None:
        self.clock = clock
        self.on_send = on_send
        self.timeout_s: Optional[float] = None
        self.incoming: list[tuple[bytes, Endpoint]] = []
        self.sent: list[tuple[bytes, Endpoint, float]] = []
        self.closed = False

    def settimeout(self, value: Optional[float]) -> None:
        self.timeout_s = value

    def recvfrom(self, _buffer_size: int) -> tuple[bytes, Endpoint]:
        if self.incoming:
            return self.incoming.pop(0)
        self.clock.advance(self.timeout_s or 0.0)
        raise socket.timeout

    def sendto(self, data: bytes, address: Endpoint) -> int:
        self.sent.append((data, address, self.clock()))
        if self.on_send is not None:
            self.on_send(data, address)
        return len(data)

    def close(self) -> None:
        self.closed = True


class SensorCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.control = FakeSocket(self.clock)
        self.output = FakeSocket(self.clock)
        self.coordinator = SensorCoordinator(
            control_socket=self.control,
            output_socket=self.output,
            clock=self.clock,
            wait=self.clock.advance,
        )
        self.endpoints = {
            1: ("192.168.137.11", 5006),
            2: ("192.168.137.12", 5006),
            3: ("192.168.137.13", 5006),
        }

    def register_all(self) -> None:
        for sensor_index, endpoint in self.endpoints.items():
            self.assertTrue(
                self.coordinator.register_hello(
                    encode_hello(sensor_index), endpoint
                )
            )

    def install_standard_responder(
        self, missing: Optional[set[int]] = None
    ) -> None:
        missing_indices = missing if missing is not None else set()

        def respond(packet: bytes, _endpoint: Endpoint) -> None:
            command = decode_measure_command(packet)
            self.assertIsNotNone(command)
            if command.target_sensor_index in missing_indices:
                return
            self.control.incoming.append(
                (
                    encode_measure_result(
                        command.cycle_id,
                        800.0 + command.target_sensor_index * 100.0,
                        1000,
                        True,
                        command.target_sensor_index,
                    ),
                    self.endpoints[command.target_sensor_index],
                )
            )

        self.control.on_send = respond

    def test_registers_all_sensors_from_hello_datagrams(self) -> None:
        for sensor_index, endpoint in self.endpoints.items():
            self.control.incoming.append((encode_hello(sensor_index), endpoint))

        self.coordinator.wait_for_stations()

        active = self.coordinator.active_registrations()
        self.assertEqual(set(active), {1, 2, 3})
        self.assertEqual(active[2].endpoint, self.endpoints[2])

    def test_new_hello_replaces_endpoint_and_heartbeat(self) -> None:
        self.coordinator.register_hello(
            encode_hello(1), self.endpoints[1], now_s=1.0
        )
        replacement = ("192.168.137.99", 6010)

        self.coordinator.register_hello(
            encode_hello(1), replacement, now_s=2.5
        )

        registration = self.coordinator.active_registrations(now_s=2.5)[1]
        self.assertEqual(registration.endpoint, replacement)
        self.assertEqual(registration.last_hello_s, 2.5)

    def test_stale_registration_is_removed(self) -> None:
        self.coordinator.register_hello(
            encode_hello(1), self.endpoints[1], now_s=1.0
        )

        self.assertIn(1, self.coordinator.active_registrations(now_s=3.999))
        self.assertNotIn(1, self.coordinator.active_registrations(now_s=4.0))

    def test_commands_use_ordered_slots_and_cycle_id_rollover(self) -> None:
        self.coordinator = SensorCoordinator(
            control_socket=self.control,
            output_socket=self.output,
            clock=self.clock,
            wait=self.clock.advance,
            initial_cycle_id=UINT32_MAX,
        )
        self.register_all()
        self.install_standard_responder()

        first_scan = self.coordinator.run_cycle()
        second_scan = self.coordinator.run_cycle()

        commands = [
            decode_measure_command(packet) for packet, _, _ in self.control.sent
        ]
        self.assertEqual(
            [command.target_sensor_index for command in commands],
            [1, 2, 3, 1, 2, 3],
        )
        self.assertEqual(
            [command.cycle_id for command in commands],
            [UINT32_MAX] * 3 + [0] * 3,
        )
        self.assertEqual(first_scan.cycle_id, UINT32_MAX)
        self.assertEqual(second_scan.cycle_id, 0)
        self.assertEqual(
            [round(sent_at_s, 3) for _, _, sent_at_s in self.control.sent[:3]],
            [1.0, 1.035, 1.07],
        )

    def test_wrong_sender_cycle_and_sensor_results_are_ignored(self) -> None:
        self.register_all()

        def respond(packet: bytes, endpoint: Endpoint) -> None:
            command = decode_measure_command(packet)
            self.assertIsNotNone(command)
            index = command.target_sensor_index
            self.control.incoming.extend(
                [
                    (
                        encode_measure_result(
                            command.cycle_id, 300.0, 1, True, index
                        ),
                        ("192.168.137.250", 5006),
                    ),
                    (
                        encode_measure_result(
                            (command.cycle_id + 1) & UINT32_MAX,
                            400.0,
                            1,
                            True,
                            index,
                        ),
                        endpoint,
                    ),
                    (
                        encode_measure_result(
                            command.cycle_id,
                            500.0,
                            1,
                            True,
                            1 if index == 3 else index + 1,
                        ),
                        endpoint,
                    ),
                    (
                        encode_measure_result(
                            command.cycle_id, 900.0 + index, 1, True, index
                        ),
                        endpoint,
                    ),
                ]
            )

        self.control.on_send = respond

        scan = self.coordinator.run_cycle()

        self.assertEqual(
            [scan.reading_for(sensor_id).distance_mm for sensor_id in SensorId],
            [901.0, 902.0, 903.0],
        )

    def test_missing_s2_is_invalid_but_s3_is_still_requested(self) -> None:
        self.register_all()
        self.install_standard_responder(missing={2})

        scan = self.coordinator.run_cycle()

        commands = [
            decode_measure_command(packet) for packet, _, _ in self.control.sent
        ]
        self.assertEqual(
            [command.target_sensor_index for command in commands], [1, 2, 3]
        )
        s2 = scan.reading_for(SensorId.S2)
        self.assertFalse(s2.valid)
        self.assertIsNone(s2.distance_mm)
        self.assertEqual(s2.sample_time_ms, 1035)
        self.assertTrue(scan.reading_for(SensorId.S3).valid)

    def test_forwards_exact_v3_schema_to_default_loopback_destination(self) -> None:
        self.register_all()
        self.install_standard_responder(missing={2})

        scan = self.coordinator.run_cycle()

        self.assertEqual(len(self.output.sent), 1)
        packet, destination, _ = self.output.sent[0]
        self.assertEqual(destination, ("127.0.0.1", 5005))
        self.assertEqual(parse_sensor_scan_packet(packet), scan)
        payload = json.loads(packet)
        self.assertEqual(
            set(payload), {"version", "type", "cycle_id", "readings"}
        )
        self.assertEqual(payload["version"], 3)
        self.assertEqual(payload["type"], "sensor_scan")
        self.assertEqual(
            [reading["sensor_id"] for reading in payload["readings"]],
            ["s1", "s2", "s3"],
        )
        self.assertEqual(
            set(payload["readings"][0]),
            {"sensor_id", "distance_mm", "valid", "sample_time_ms"},
        )

    def test_module_does_not_load_pygame_or_simulated_input(self) -> None:
        import software.transport.sensor_coordinator as coordinator_module

        source_names = set(coordinator_module.__dict__)
        self.assertNotIn("pygame", source_names)
        self.assertNotIn("SimulatedPositionSource", source_names)


if __name__ == "__main__":
    unittest.main()
