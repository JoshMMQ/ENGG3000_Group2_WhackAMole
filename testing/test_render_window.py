import unittest

from software.game.main import (
    active_hole_index_at,
    create_mapper,
    gameplay_elapsed_seconds,
    is_cursor_over_mole,
    mapped_cursor_position,
    randomized_hole_index,
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

    def test_active_hole_index_changes_randomly_on_interval(self) -> None:
        self.assertEqual(active_hole_index_at(0.0, interval_s=1.75), 3)
        self.assertEqual(active_hole_index_at(1.74, interval_s=1.75), 3)
        self.assertEqual(active_hole_index_at(1.75, interval_s=1.75), 8)

    def test_active_hole_index_stays_inside_hole_range(self) -> None:
        for slot in range(30):
            index = active_hole_index_at(slot * 1.75, interval_s=1.75)
            self.assertGreaterEqual(index, 0)
            self.assertLess(index, 9)

    def test_active_hole_index_rejects_invalid_interval(self) -> None:
        with self.assertRaises(ValueError):
            active_hole_index_at(0.0, interval_s=0.0)

    def test_randomized_hole_index_is_repeatable(self) -> None:
        self.assertEqual([randomized_hole_index(slot) for slot in range(6)], [3, 8, 5, 1, 7, 3])

    def test_randomized_hole_index_avoids_adjacent_repeats(self) -> None:
        sequence = [randomized_hole_index(slot) for slot in range(12)]

        self.assertTrue(all(left != right for left, right in zip(sequence, sequence[1:])))

    def test_randomized_hole_index_rejects_invalid_hole_count(self) -> None:
        with self.assertRaises(ValueError):
            randomized_hole_index(0, hole_count=0)

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

    def test_gameplay_elapsed_seconds_excludes_paused_time(self) -> None:
        self.assertEqual(gameplay_elapsed_seconds(10_000, 1_000, 4_000), 5.0)

    def test_gameplay_elapsed_seconds_does_not_go_negative(self) -> None:
        self.assertEqual(gameplay_elapsed_seconds(1_000, 10_000, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
