import math
import unittest

from software.game.cell_tracking import PlayerCell, world_position_to_cell


class WorldPositionToCellTests(unittest.TestCase):
    def test_player_cell_rejects_values_outside_the_three_by_three_grid(self) -> None:
        for column, row in ((0, 1), (4, 1), (1, 0), (1, 4), (True, 1), (1, 1.5)):
            with self.subTest(column=column, row=row):
                with self.assertRaises(ValueError):
                    PlayerCell(column=column, row=row)

    def test_maps_the_centre_of_all_nine_cells(self) -> None:
        column_centres = (0.25, 0.75, 1.25)
        row_centres = (5.0 / 6.0, 1.30, 53.0 / 30.0)

        for row, y_m in enumerate(row_centres, start=1):
            for column, x_m in enumerate(column_centres, start=1):
                with self.subTest(column=column, row=row):
                    self.assertEqual(
                        world_position_to_cell((x_m, y_m)),
                        PlayerCell(column=column, row=row),
                    )

    def test_includes_all_four_outer_playable_boundaries(self) -> None:
        self.assertEqual(world_position_to_cell((0.0, 0.60)), PlayerCell(1, 1))
        self.assertEqual(world_position_to_cell((1.50, 0.60)), PlayerCell(3, 1))
        self.assertEqual(world_position_to_cell((0.0, 2.00)), PlayerCell(1, 3))
        self.assertEqual(world_position_to_cell((1.50, 2.00)), PlayerCell(3, 3))

    def test_internal_boundaries_enter_the_next_column_or_row(self) -> None:
        first_row_boundary_m = 0.60 + 1.40 / 3.0
        second_row_boundary_m = 0.60 + 2.0 * 1.40 / 3.0

        self.assertEqual(world_position_to_cell((0.50, 0.80)), PlayerCell(2, 1))
        self.assertEqual(world_position_to_cell((1.00, 0.80)), PlayerCell(3, 1))
        self.assertEqual(
            world_position_to_cell((0.25, first_row_boundary_m)),
            PlayerCell(1, 2),
        )
        self.assertEqual(
            world_position_to_cell((0.25, second_row_boundary_m)),
            PlayerCell(1, 3),
        )

    def test_rejects_dead_zone_and_out_of_footprint_positions(self) -> None:
        for position in (
            (-0.001, 1.0),
            (1.501, 1.0),
            (0.75, 0.599),
            (0.75, 2.001),
        ):
            with self.subTest(position=position):
                self.assertIsNone(world_position_to_cell(position))

    def test_rejects_malformed_or_non_finite_positions(self) -> None:
        for position in (
            None,
            (),
            (0.75,),
            (0.75, 1.30, 2.0),
            (True, 1.30),
            (0.75, False),
            (math.nan, 1.30),
            (0.75, math.inf),
            ("bad", 1.30),
        ):
            with self.subTest(position=position):
                self.assertIsNone(world_position_to_cell(position))


if __name__ == "__main__":
    unittest.main()
