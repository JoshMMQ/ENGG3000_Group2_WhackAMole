import unittest

from software.game.main import static_cursor_position


class RenderWindowTests(unittest.TestCase):
    def test_static_cursor_uses_mapped_play_area_centre(self) -> None:
        self.assertEqual(static_cursor_position(), (450, 450))


if __name__ == "__main__":
    unittest.main()
