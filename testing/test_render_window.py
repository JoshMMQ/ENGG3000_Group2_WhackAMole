import unittest

from software.game.main import create_mapper, mapped_cursor_position, static_cursor_position


class RenderWindowTests(unittest.TestCase):
    def test_static_cursor_uses_mapped_play_area_centre(self) -> None:
        self.assertEqual(static_cursor_position(), (450, 450))

    def test_mapped_cursor_position_uses_physical_coordinates(self) -> None:
        self.assertEqual(mapped_cursor_position((3.0, 0.0)), (899, 0))

    def test_create_mapper_uses_active_window_size(self) -> None:
        mapper = create_mapper((1920, 1080))

        self.assertEqual(mapper.physical_to_screen(3.0, 3.0), (1919, 1079))


if __name__ == "__main__":
    unittest.main()
