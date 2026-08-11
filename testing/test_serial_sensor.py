import unittest

from software.transport.serial_sensor import (
    BenchSensorReading,
    SerialSensorSource,
    parse_bench_reading,
)


class FakeSerialStream:
    def __init__(self, data: bytes = b"") -> None:
        self.data = bytearray(data)
        self.closed = False

    @property
    def in_waiting(self) -> int:
        return len(self.data)

    def read(self, size: int = 1) -> bytes:
        chunk = bytes(self.data[:size])
        del self.data[:size]
        return chunk

    def close(self) -> None:
        self.closed = True


class BenchReadingParserTests(unittest.TestCase):
    def test_parses_valid_decimal_distance(self) -> None:
        reading = parse_bench_reading(
            b'{"node_id":"box1","sensor_id":"left","distance_mm":173.7,'
            b'"valid":true,"sample_us":13200116}'
        )

        self.assertEqual(
            reading,
            BenchSensorReading("box1", "left", 173.7, True, 13200116),
        )

    def test_parses_no_echo_reading(self) -> None:
        reading = parse_bench_reading(
            '{"node_id":"box2","sensor_id":"right","distance_mm":null,'
            '"valid":false,"sample_us":13273116}'
        )

        self.assertEqual(
            reading,
            BenchSensorReading("box2", "right", None, False, 13273116),
        )

    def test_rejects_banner_malformed_and_inconsistent_lines(self) -> None:
        self.assertIsNone(parse_bench_reading("Left HC-SR04 ready"))
        self.assertIsNone(parse_bench_reading("{bad json"))
        self.assertIsNone(
            parse_bench_reading(
                '{"node_id":"box1","sensor_id":"left","distance_mm":null,'
                '"valid":true,"sample_us":1}'
            )
        )


class SerialSensorSourceTests(unittest.TestCase):
    def test_buffers_fragmented_line_until_newline_arrives(self) -> None:
        stream = FakeSerialStream(
            b'{"node_id":"box1","sensor_id":"left","distance_mm":87.1'
        )
        source = SerialSensorSource("fake-left", stream=stream)

        self.assertEqual(source.poll_readings(), ())

        stream.data.extend(b',"valid":true,"sample_us":1}\r\n')
        self.assertEqual(
            source.poll_readings(),
            (BenchSensorReading("box1", "left", 87.1, True, 1),),
        )

    def test_returns_multiple_readings_and_ignores_banner(self) -> None:
        stream = FakeSerialStream(
            b"Right HC-SR04 ready\n"
            b'{"node_id":"box2","sensor_id":"right","distance_mm":200.0,'
            b'"valid":true,"sample_us":10}\n'
            b'{"node_id":"box2","sensor_id":"right","distance_mm":null,'
            b'"valid":false,"sample_us":20}\n'
        )
        source = SerialSensorSource("fake-right", stream=stream)

        self.assertEqual(
            source.poll_readings(),
            (
                BenchSensorReading("box2", "right", 200.0, True, 10),
                BenchSensorReading("box2", "right", None, False, 20),
            ),
        )

    def test_close_closes_underlying_stream(self) -> None:
        stream = FakeSerialStream()
        source = SerialSensorSource("fake", stream=stream)

        source.close()

        self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
