import unittest

from software.game.main import (
    active_hole_index_at,
    create_mapper,
    is_cursor_over_mole,
    mapped_cursor_position,
    scaled_hit_radius,
    static_cursor_position,
)


class RenderWindowTests(unittest.TestCase):
    def test_static_cursor_uses_mapped_play_area_centre(self) -> None:
        self.assertEqual(static_cursor_position(), (450, 450))

    def test_mapped_cursor_position_uses_physical_coordinates(self) -> None:
        self.assertEqual(mapped_cursor_position((3.0, 0.0)), (899, 0))

    def test_create_mapper_uses_active_window_size(self) -> None:
        mapper = create_mapper((1920, 1080))

        self.assertEqual(mapper.physical_to_screen(3.0, 3.0), (1919, 1079))

    def test_active_hole_index_changes_on_interval(self) -> None:
        self.assertEqual(active_hole_index_at(0.0, interval_s=1.75), 0)
        self.assertEqual(active_hole_index_at(1.74, interval_s=1.75), 0)
        self.assertEqual(active_hole_index_at(1.75, interval_s=1.75), 1)

    def test_active_hole_index_wraps_after_nine_holes(self) -> None:
        self.assertEqual(active_hole_index_at(15.75, interval_s=1.75), 0)

    def test_active_hole_index_rejects_invalid_interval(self) -> None:
        with self.assertRaises(ValueError):
            active_hole_index_at(0.0, interval_s=0.0)

    def test_scaled_hit_radius_uses_window_size(self) -> None:
        self.assertEqual(scaled_hit_radius((900, 900), base_radius_px=70), 70)
        self.assertEqual(scaled_hit_radius((1800, 900), base_radius_px=70), 70)
        self.assertEqual(scaled_hit_radius((450, 450), base_radius_px=70), 35)

    def test_scaled_hit_radius_has_minimum_size(self) -> None:
        self.assertEqual(scaled_hit_radius((90, 90), base_radius_px=70), 20)

    def test_cursor_over_mole_uses_circular_radius(self) -> None:
        self.assertTrue(is_cursor_over_mole((100, 100), (130, 140), 50))
        self.assertFalse(is_cursor_over_mole((100, 100), (151, 100), 50))

    def test_cursor_over_mole_rejects_negative_radius(self) -> None:
        with self.assertRaises(ValueError):
            is_cursor_over_mole((100, 100), (100, 100), -1)


if __name__ == "__main__":
    unittest.main()
