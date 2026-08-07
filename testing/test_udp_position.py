import json
import unittest

from software.game.udp_position import DistanceAxisMapper, UdpPositionSource
from testing.test_packet import valid_payload


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


class DistanceAxisMapperTests(unittest.TestCase):
    def test_maps_distance_range_to_x_axis(self) -> None:
        mapper = DistanceAxisMapper()

        self.assertEqual(mapper.position_for_distance(500), (0.0, 1.5))
        self.assertEqual(mapper.position_for_distance(1500), (1.5, 1.5))
        self.assertEqual(mapper.position_for_distance(2500), (3.0, 1.5))

    def test_preserves_out_of_range_distance_for_safety_detection(self) -> None:
        mapper = DistanceAxisMapper()

        self.assertLess(mapper.position_for_distance(0)[0], 0.0)
        self.assertGreater(mapper.position_for_distance(3000)[0], 3.0)

    def test_rejects_invalid_range(self) -> None:
        with self.assertRaises(ValueError):
            DistanceAxisMapper(min_distance_mm=2500, max_distance_mm=500)


class UdpPositionSourceTests(unittest.TestCase):
    def test_starts_at_centre_until_packet_arrives(self) -> None:
        source = UdpPositionSource(sock=FakeSocket([]))

        self.assertEqual(source.latest_position, (1.5, 1.5))
        self.assertEqual(source.poll_position(), (1.5, 1.5))

    def test_valid_packet_updates_latest_position(self) -> None:
        payload = valid_payload()
        payload["readings"][0]["distance_mm"] = 2500
        source = UdpPositionSource(sock=FakeSocket([json.dumps(payload).encode("utf-8")]))

        self.assertEqual(source.poll_position(), (3.0, 1.5))
        self.assertEqual(source.latest_position, (3.0, 1.5))

    def test_invalid_packet_keeps_last_position(self) -> None:
        source = UdpPositionSource(sock=FakeSocket([b"{bad json"]))

        self.assertEqual(source.poll_position(), (1.5, 1.5))

    def test_invalid_reading_keeps_last_position(self) -> None:
        payload = valid_payload()
        payload["readings"][0]["valid"] = False
        payload["readings"][0]["distance_mm"] = None
        source = UdpPositionSource(sock=FakeSocket([json.dumps(payload).encode("utf-8")]))

        self.assertEqual(source.poll_position(), (1.5, 1.5))


if __name__ == "__main__":
    unittest.main()
