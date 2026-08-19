import struct
import unittest

from software.transport.sensor_station_protocol import (
    COMMAND_MAGIC,
    HELLO_MAGIC,
    PROTOCOL_VERSION,
    RESULT_MAGIC,
    UINT32_MAX,
    MeasureCommand,
    MeasureResult,
    StationHello,
    decode_hello,
    decode_measure_command,
    decode_measure_result,
    encode_hello,
    encode_measure_command,
    encode_measure_result,
)


class SensorStationProtocolTests(unittest.TestCase):
    def test_exact_little_endian_packet_layouts(self) -> None:
        self.assertEqual(
            encode_hello(2),
            struct.pack("<IBB", HELLO_MAGIC, PROTOCOL_VERSION, 2),
        )
        self.assertEqual(
            encode_measure_command(0x12345678, 3),
            struct.pack("<IIB", COMMAND_MAGIC, 0x12345678, 3),
        )
        self.assertEqual(
            encode_measure_result(7, 1234.5, 8765, True, 1),
            struct.pack("<IIfIBB", RESULT_MAGIC, 7, 1234.5, 8765, 1, 1),
        )

    def test_valid_packets_decode_to_named_values(self) -> None:
        self.assertEqual(decode_hello(encode_hello(3)), StationHello(3))
        self.assertEqual(
            decode_measure_command(encode_measure_command(42, 2)),
            MeasureCommand(42, 2),
        )
        self.assertEqual(
            decode_measure_result(
                encode_measure_result(42, 900.0, 1500, False, 2)
            ),
            MeasureResult(42, 900.0, 1500, False, 2),
        )

    def test_rejects_incorrect_lengths_magic_version_and_sensor_indices(
        self,
    ) -> None:
        malformed = (
            b"",
            encode_hello(1) + b"\x00",
            struct.pack("<IBB", 0, PROTOCOL_VERSION, 1),
            struct.pack("<IBB", HELLO_MAGIC, PROTOCOL_VERSION + 1, 1),
            struct.pack("<IBB", HELLO_MAGIC, PROTOCOL_VERSION, 4),
        )
        for packet in malformed:
            with self.subTest(packet=packet):
                self.assertIsNone(decode_hello(packet))

        self.assertIsNone(
            decode_measure_command(struct.pack("<IIB", 0, 1, 1))
        )
        self.assertIsNone(
            decode_measure_command(struct.pack("<IIB", COMMAND_MAGIC, 1, 0))
        )
        self.assertIsNone(
            decode_measure_result(
                struct.pack("<IIfIBB", 0, 1, 1000.0, 10, 1, 1)
            )
        )
        self.assertIsNone(decode_measure_result(b"\x00" * 17))

    def test_rejects_nonfinite_distance_and_nonbinary_validity(self) -> None:
        for distance_mm in (float("nan"), float("inf"), float("-inf")):
            packet = struct.pack(
                "<IIfIBB", RESULT_MAGIC, 1, distance_mm, 10, 1, 1
            )
            with self.subTest(distance_mm=distance_mm):
                self.assertIsNone(decode_measure_result(packet))

        invalid_validity = struct.pack(
            "<IIfIBB", RESULT_MAGIC, 1, 1000.0, 10, 2, 1
        )
        self.assertIsNone(decode_measure_result(invalid_validity))

    def test_encoders_reject_values_outside_the_contract(self) -> None:
        for cycle_id in (-1, UINT32_MAX + 1, True):
            with self.subTest(cycle_id=cycle_id):
                with self.assertRaises(ValueError):
                    encode_measure_command(cycle_id, 1)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            encode_hello(4)
        with self.assertRaises(TypeError):
            encode_measure_result(1, 1000.0, 10, 1, 1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
