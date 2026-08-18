import unittest

from software.game.scene import (
    GameplayUi,
    active_mole_position,
    continue_button_rect,
    hole_positions,
    pause_button_rect,
    sensor_overlay_layout,
    start_button_rect,
)


class SceneLayoutTests(unittest.TestCase):
    def test_hole_layout_has_three_by_three_grid(self) -> None:
        holes = hole_positions(900, 900)

        self.assertEqual(len(holes), 9)
        self.assertEqual(len({x for x, _ in holes}), 3)
        self.assertEqual(len({y for _, y in holes}), 3)

    def test_hole_layout_stays_inside_window(self) -> None:
        for x, y in hole_positions(900, 900):
            self.assertGreater(x, 0)
            self.assertLess(x, 900)
            self.assertGreater(y, 0)
            self.assertLess(y, 900)

    def test_active_mole_uses_centre_hole(self) -> None:
        self.assertEqual(active_mole_position(900, 900), (450, 558))

    def test_active_mole_can_use_each_hole_index(self) -> None:
        holes = hole_positions(900, 900)

        self.assertEqual(active_mole_position(900, 900, active_hole_index=0), holes[0])
        self.assertEqual(active_mole_position(900, 900, active_hole_index=8), holes[8])

    def test_active_mole_index_wraps_to_hole_count(self) -> None:
        self.assertEqual(active_mole_position(900, 900, active_hole_index=9), hole_positions(900, 900)[0])

    def test_start_button_stays_inside_window(self) -> None:
        x, y, width, height = start_button_rect(900, 900)

        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + width, 900)
        self.assertLessEqual(y + height, 900)

    def test_continue_button_stays_inside_window(self) -> None:
        x, y, width, height = continue_button_rect(900, 900)

        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + width, 900)
        self.assertLessEqual(y + height, 900)

    def test_pause_button_stays_inside_window(self) -> None:
        x, y, width, height = pause_button_rect(900, 900)

        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + width, 900)
        self.assertLessEqual(y + height, 900)

    def test_gameplay_ui_defaults_match_starting_hud(self) -> None:
        ui = GameplayUi()

        self.assertEqual(ui.score, 0)
        self.assertEqual(ui.lives, 3)
        self.assertEqual(ui.remaining_seconds, 60)
        self.assertIsNone(ui.sensor_overlay)
        self.assertEqual(ui.tracking_debug_lines, ())

    def test_sensor_overlay_layout_stays_inside_common_window_sizes(self) -> None:
        for window_width, window_height in ((320, 240), (640, 480), (900, 900), (1280, 720)):
            with self.subTest(size=(window_width, window_height)):
                layout = sensor_overlay_layout(window_width, window_height)
                for rect in (
                    layout.container,
                    layout.banner,
                    layout.left_panel,
                    layout.right_panel,
                ):
                    x, y, width, height = rect
                    self.assertGreater(width, 0)
                    self.assertGreater(height, 0)
                    self.assertGreaterEqual(x, 0)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + width, window_width)
                    self.assertLessEqual(y + height, window_height)

    def test_sensor_overlay_panels_do_not_overlap(self) -> None:
        layout = sensor_overlay_layout(640, 480)
        left_x, left_y, left_width, left_height = layout.left_panel
        right_x, right_y, _, right_height = layout.right_panel

        self.assertLessEqual(left_x + left_width, right_x)
        self.assertEqual(left_y, right_y)
        self.assertEqual(left_height, right_height)

    def test_sensor_overlay_contents_stay_inside_container(self) -> None:
        for window_width, window_height in ((320, 240), (640, 480), (900, 900), (1280, 720)):
            with self.subTest(size=(window_width, window_height)):
                layout = sensor_overlay_layout(window_width, window_height)
                container_x, container_y, container_width, container_height = layout.container
                for x, y, width, height in (
                    layout.banner,
                    layout.left_panel,
                    layout.right_panel,
                ):
                    self.assertGreaterEqual(x, container_x)
                    self.assertGreaterEqual(y, container_y)
                    self.assertLessEqual(x + width, container_x + container_width)
                    self.assertLessEqual(y + height, container_y + container_height)

    def test_sensor_overlay_layout_rejects_nonpositive_window_dimensions(self) -> None:
        for width, height in ((0, 480), (640, 0), (-1, 480), (640, -1)):
            with self.subTest(size=(width, height)):
                with self.assertRaises(ValueError):
                    sensor_overlay_layout(width, height)


if __name__ == "__main__":
    unittest.main()
