import json
import socket
import unittest

from software.game.coordinates import CoordinateMapper
from software.game.udp_position import TrackingStatus, UdpPositionSource, parse_range_pair_packet
from software.transport.mock_range_pair_sender import (
    build_range_pair_payload,
    encode_payload,
    ranges_for_position,
    send_mock_packets,
    simulated_position,
)


class MockRangePairSenderTests(unittest.TestCase):
    def test_payload_round_trips_through_game_parser(self) -> None:
        payload = build_range_pair_payload(7, 0.30, 1.00)

        packet = parse_range_pair_packet(encode_payload(payload))

        self.assertIsNotNone(packet)
        self.assertEqual(packet.cycle_id, 7)
        self.assertTrue(packet.left_valid)
        self.assertEqual(json.loads(encode_payload(payload))["version"], 2)

    def test_ranges_match_known_centre_position(self) -> None:
        left_mm, right_mm = ranges_for_position(0.75, 1.30)

        self.assertAlmostEqual(left_mm, right_mm)
        self.assertAlmostEqual(left_mm, 1415.097, places=3)

    def test_simulated_positions_stay_in_playable_area(self) -> None:
        for cycle_id in range(240):
            x_m, y_m = simulated_position(cycle_id)
            self.assertGreaterEqual(x_m, 0.0)
            self.assertLessEqual(x_m, 1.50)
            self.assertGreaterEqual(y_m, 0.60)
            self.assertLessEqual(y_m, 2.00)

    def test_sender_drives_real_udp_source_to_world_position(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.setblocking(False)
            _, port = receiver.getsockname()
            source = UdpPositionSource(sock=receiver, filter_alpha=1.0)

            send_mock_packets(
                target_port=port,
                count=1,
                interval_s=0.0,
                fixed_position=(1.20, 1.00),
            )
            snapshot = source.poll(now_s=1.0)

        self.assertEqual(snapshot.status, TrackingStatus.PLAYABLE)
        self.assertAlmostEqual(snapshot.world_position[0], 1.20, places=5)
        self.assertAlmostEqual(snapshot.world_position[1], 1.00, places=5)
        self.assertEqual(CoordinateMapper().physical_to_screen(*snapshot.world_position), (719, 257))


if __name__ == "__main__":
    unittest.main()
