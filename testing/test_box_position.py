import unittest

from software.game.box_position import (
    BoxPositionSource,
    SingleBoxPositionSource,
    WallTriangulationMapper,
    parse_box_reading,
)


class FakeSocket:
    def __init__(self, packets: list[bytes]) -> None:
        self._packets = packets
        self.closed = False

    def recvfrom(self, buffer_size: int) -> tuple[bytes, tuple[str, int]]:
        if not self._packets:
            raise BlockingIOError
        return self._packets.pop(0), ("127.0.0.1", 12345)

    def close(self) -> None:
        self.closed = True


class ParseBoxReadingTests(unittest.TestCase):
    def test_parses_valid_reading(self) -> None:
        self.assertEqual(parse_box_reading(b"box1,123.4"), ("box1", 123.4))

    def test_rejects_malformed_payload(self) -> None:
        self.assertIsNone(parse_box_reading(b"not-a-reading"))

    def test_rejects_negative_distance(self) -> None:
        self.assertIsNone(parse_box_reading(b"box1,-5.0"))


class WallTriangulationMapperTests(unittest.TestCase):
    def test_solves_equilateral_triangle(self) -> None:
        mapper = WallTriangulationMapper(baseline_m=1.0, depth_m=1.0)

        position = mapper.position_for_ranges(1.0, 1.0)

        self.assertIsNotNone(position)
        x, y = position
        self.assertAlmostEqual(x, 0.5)
        self.assertAlmostEqual(y, 0.8660254, places=5)

    def test_returns_none_when_ranges_cannot_intersect(self) -> None:
        mapper = WallTriangulationMapper(baseline_m=1.0, depth_m=1.0)

        self.assertIsNone(mapper.position_for_ranges(0.1, 0.1))

    def test_clamps_depth_to_play_area(self) -> None:
        mapper = WallTriangulationMapper(baseline_m=1.0, depth_m=0.5)

        x, y = mapper.position_for_ranges(1.0, 1.0)

        self.assertAlmostEqual(x, 0.5)
        self.assertEqual(y, 0.5)

    def test_rejects_invalid_range(self) -> None:
        with self.assertRaises(ValueError):
            WallTriangulationMapper(baseline_m=0.0)


class BoxPositionSourceTests(unittest.TestCase):
    def test_starts_at_centre_until_both_boxes_report(self) -> None:
        source = BoxPositionSource(
            mapper=WallTriangulationMapper(baseline_m=1.0, depth_m=1.0),
            sock=FakeSocket([b"box1,100.0"]),
        )

        self.assertEqual(source.poll_position(), (0.5, 0.5))

    def test_updates_position_once_both_boxes_report(self) -> None:
        source = BoxPositionSource(
            mapper=WallTriangulationMapper(baseline_m=1.0, depth_m=1.0),
            sock=FakeSocket([b"box1,100.0", b"box2,100.0"]),
        )

        x, y = source.poll_position()

        self.assertAlmostEqual(x, 0.5)
        self.assertAlmostEqual(y, 0.8660254, places=5)

    def test_ignores_malformed_packet(self) -> None:
        source = BoxPositionSource(
            mapper=WallTriangulationMapper(baseline_m=1.0, depth_m=1.0),
            sock=FakeSocket([b"garbage"]),
        )

        self.assertEqual(source.poll_position(), (0.5, 0.5))

    def test_close_leaves_caller_provided_socket_open(self) -> None:
        sock = FakeSocket([])
        source = BoxPositionSource(sock=sock)

        source.close()

        self.assertFalse(sock.closed)


class SingleBoxPositionSourceTests(unittest.TestCase):
    def test_starts_at_centre_depth_until_a_reading_arrives(self) -> None:
        source = SingleBoxPositionSource(
            centre_x_m=0.75,
            max_depth_m=2.0,
            sock=FakeSocket([]),
        )

        self.assertEqual(source.poll_position(), (0.75, 1.0))

    def test_updates_depth_from_matching_box_id(self) -> None:
        source = SingleBoxPositionSource(
            centre_x_m=0.75,
            max_depth_m=2.0,
            sock=FakeSocket([b"box1,80.0"]),
        )

        self.assertEqual(source.poll_position(), (0.75, 0.8))

    def test_ignores_readings_from_a_different_box_id(self) -> None:
        source = SingleBoxPositionSource(
            centre_x_m=0.75,
            max_depth_m=2.0,
            box_id="box1",
            sock=FakeSocket([b"box2,80.0"]),
        )

        self.assertEqual(source.poll_position(), (0.75, 1.0))

    def test_clamps_distance_to_max_depth(self) -> None:
        source = SingleBoxPositionSource(
            centre_x_m=0.75,
            max_depth_m=2.0,
            sock=FakeSocket([b"box1,500.0"]),
        )

        self.assertEqual(source.poll_position(), (0.75, 2.0))

    def test_rejects_invalid_max_depth(self) -> None:
        sock = FakeSocket([])

        with self.assertRaises(ValueError):
            SingleBoxPositionSource(max_depth_m=0.0, sock=sock)


if __name__ == "__main__":
    unittest.main()
