import unittest

from software.game.simulated_position import SimulatedPositionSource


class SimulatedPositionSourceTests(unittest.TestCase):
    def test_starts_at_play_area_centre(self) -> None:
        source = SimulatedPositionSource()

        self.assertEqual(source.position_at(0.0), (1.5, 1.5))

    def test_positions_stay_inside_play_area(self) -> None:
        source = SimulatedPositionSource()

        for step in range(0, 121):
            x_m, y_m = source.position_at(step / 10.0)
            self.assertGreaterEqual(x_m, 0.0)
            self.assertLessEqual(x_m, 3.0)
            self.assertGreaterEqual(y_m, 0.0)
            self.assertLessEqual(y_m, 3.0)

    def test_positions_change_over_time(self) -> None:
        source = SimulatedPositionSource()

        self.assertNotEqual(source.position_at(0.0), source.position_at(1.0))

    def test_rejects_invalid_periods(self) -> None:
        with self.assertRaises(ValueError):
            SimulatedPositionSource(x_period_s=0.0)

        with self.assertRaises(ValueError):
            SimulatedPositionSource(y_period_s=-1.0)


if __name__ == "__main__":
    unittest.main()
