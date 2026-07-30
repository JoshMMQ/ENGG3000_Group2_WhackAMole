import unittest

from software.game.main import mapped_cursor_position, static_cursor_position


class RenderWindowTests(unittest.TestCase):
    def test_static_cursor_uses_mapped_play_area_centre(self) -> None:
        self.assertEqual(static_cursor_position(), (450, 450))

    def test_mapped_cursor_position_uses_physical_coordinates(self) -> None:
        self.assertEqual(mapped_cursor_position((3.0, 0.0)), (899, 0))


if __name__ == "__main__":
    unittest.main()
