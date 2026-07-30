import json
import socket
import unittest

from software.transport.udp_receiver import format_packet, receive_packet
from testing.test_packet import valid_payload


class UdpReceiverTests(unittest.TestCase):
    def test_receive_packet_returns_none_when_non_blocking_socket_has_no_data(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.setblocking(False)

            packet, sender_address = receive_packet(receiver)

        self.assertIsNone(packet)
        self.assertIsNone(sender_address)

    def test_receive_packet_returns_valid_telemetry(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            address = receiver.getsockname()

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.sendto(json.dumps(valid_payload()).encode("utf-8"), address)

            packet, sender_address = receive_packet(receiver)

        self.assertIsNotNone(packet)
        self.assertEqual(packet.node_id, "esp32_01")
        self.assertEqual(packet.readings[0].distance_mm, 1500)
        self.assertEqual(sender_address[0], "127.0.0.1")

    def test_receive_packet_drops_invalid_telemetry(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            address = receiver.getsockname()

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.sendto(b"{bad json", address)

            packet, _ = receive_packet(receiver)

        self.assertIsNone(packet)

    def test_format_packet_includes_receiver_diagnostics(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            address = receiver.getsockname()

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.sendto(json.dumps(valid_payload()).encode("utf-8"), address)

            packet, sender_address = receive_packet(receiver)

        line = format_packet(packet, sender_address)

        self.assertIn("node=esp32_01", line)
        self.assertIn("seq=7", line)
        self.assertIn("simulated=1500mm", line)


if __name__ == "__main__":
    unittest.main()
