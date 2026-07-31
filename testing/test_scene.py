import unittest

from software.game.scene import (
    GameplayUi,
    active_mole_position,
    continue_button_rect,
    hole_positions,
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

    def test_gameplay_ui_defaults_match_starting_hud(self) -> None:
        ui = GameplayUi()

        self.assertEqual(ui.score, 0)
        self.assertEqual(ui.lives, 3)
        self.assertEqual(ui.remaining_seconds, 60)


if __name__ == "__main__":
    unittest.main()
