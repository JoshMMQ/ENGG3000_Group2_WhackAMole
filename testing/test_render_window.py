import unittest

from software.game.udp_position import TrackingSnapshot, TrackingStatus

from software.game.main import (
    active_hole_index_at,
    create_mapper,
    gameplay_elapsed_seconds,
    is_inside_play_area,
    is_inside_screen_warning_zone,
    is_inside_tracked_footprint,
    is_cursor_over_mole,
    mapped_cursor_position,
    randomized_hole_index,
    scaled_hit_radius,
    should_clear_screen_warning,
    static_cursor_position,
    tracking_only_position,
)


class RenderWindowTests(unittest.TestCase):
    def test_tracking_only_mode_uses_dead_zone_world_position(self) -> None:
        snapshot = TrackingSnapshot(
            status=TrackingStatus.DEAD_ZONE,
            world_position=(0.40, 0.30),
            cursor_position=(0.80, 1.20),
            cycle_id=4,
        )

        self.assertEqual(tracking_only_position(snapshot), (0.40, 0.30))

    def test_tracking_only_mode_retains_cursor_when_tracking_is_lost(self) -> None:
        snapshot = TrackingSnapshot(
            status=TrackingStatus.TRACKING_LOST,
            world_position=None,
            cursor_position=(0.80, 1.20),
            cycle_id=5,
        )

        self.assertEqual(tracking_only_position(snapshot), (0.80, 1.20))

    def test_static_cursor_uses_mapped_play_area_centre(self) -> None:
        self.assertEqual(static_cursor_position(), (450, 450))

    def test_mapped_cursor_position_uses_physical_coordinates(self) -> None:
        self.assertEqual(mapped_cursor_position((1.50, 0.60)), (899, 0))

    def test_inside_play_area_accepts_boundary_positions(self) -> None:
        self.assertTrue(is_inside_play_area((0.0, 0.60)))
        self.assertTrue(is_inside_play_area((1.50, 2.00)))
        self.assertTrue(is_inside_play_area((0.75, 1.30)))

    def test_inside_play_area_rejects_outside_positions(self) -> None:
        self.assertFalse(is_inside_play_area((-0.01, 1.30)))
        self.assertFalse(is_inside_play_area((1.51, 1.30)))
        self.assertFalse(is_inside_play_area((0.75, 0.59)))
        self.assertFalse(is_inside_play_area((0.75, 2.01)))

    def test_inside_play_area_rejects_invalid_positions(self) -> None:
        self.assertFalse(is_inside_play_area(("bad", 1.5)))
        self.assertFalse(is_inside_play_area((float("nan"), 1.5)))

    def test_inside_play_area_rejects_invalid_dimensions(self) -> None:
        with self.assertRaises(ValueError):
            is_inside_play_area((1.5, 1.5), width_m=0.0)

    def test_screen_warning_is_the_v2_dead_zone_below_sixty_centimetres(self) -> None:
        self.assertTrue(is_inside_screen_warning_zone((0.75, 0.59)))
        self.assertFalse(is_inside_screen_warning_zone((0.75, 0.60)))

    def test_screen_warning_uses_hysteresis_to_clear(self) -> None:
        self.assertFalse(should_clear_screen_warning((0.75, 0.69)))
        self.assertTrue(should_clear_screen_warning((0.75, 0.70)))

    def test_tracked_footprint_includes_dead_zone_but_not_outside_field(self) -> None:
        self.assertTrue(is_inside_tracked_footprint((0.75, 0.30)))
        self.assertTrue(is_inside_tracked_footprint((1.50, 2.00)))
        self.assertFalse(is_inside_tracked_footprint((1.51, 1.00)))
        self.assertFalse(is_inside_tracked_footprint((0.75, -0.01)))

    def test_screen_warning_rejects_invalid_positions(self) -> None:
        self.assertFalse(is_inside_screen_warning_zone((1.5, "bad")))
        self.assertFalse(is_inside_screen_warning_zone((1.5, float("nan"))))
        self.assertFalse(should_clear_screen_warning((1.5, "bad")))

    def test_screen_warning_rejects_invalid_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            is_inside_screen_warning_zone((1.5, 0.5), warning_distance_m=-0.1)
        with self.assertRaises(ValueError):
            should_clear_screen_warning((1.5, 0.7), clear_distance_m=-0.1)

    def test_create_mapper_uses_active_window_size(self) -> None:
        mapper = create_mapper((1920, 1080))

        self.assertEqual(mapper.physical_to_screen(1.50, 2.00), (1919, 1079))

    def test_tracking_only_mapper_exposes_the_full_dead_zone_depth(self) -> None:
        mapper = create_mapper((900, 900), tracking_only=True)

        self.assertEqual(mapper.physical_to_screen(0.75, 0.00), (450, 0))
        self.assertEqual(mapper.physical_to_screen(0.75, 0.30), (450, 135))
        self.assertEqual(mapper.physical_to_screen(0.75, 2.00), (450, 899))

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
