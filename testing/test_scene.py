import unittest

from software.game.scene import hole_positions


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


if __name__ == "__main__":
    unittest.main()
