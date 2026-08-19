import math
import unittest

from software.game.coordinates import CoordinateMapper


class CoordinateMapperTests(unittest.TestCase):
    def test_maps_play_area_corners_to_screen_edges(self) -> None:
        mapper = CoordinateMapper()

        self.assertEqual(mapper.physical_to_screen(0.0, 0.60), (0, 0))
        self.assertEqual(mapper.physical_to_screen(1.50, 2.00), (899, 899))

    def test_maps_centre_of_play_area_to_centre_of_screen(self) -> None:
        mapper = CoordinateMapper()

        self.assertEqual(mapper.physical_to_screen(0.75, 1.30), (450, 450))

    def test_clamps_positions_to_window_boundaries(self) -> None:
        mapper = CoordinateMapper()

        self.assertEqual(mapper.physical_to_screen(-1.0, 4.0), (0, 899))
        self.assertEqual(mapper.physical_to_screen(4.0, 0.0), (899, 0))

    def test_maps_off_centre_v2_coordinate(self) -> None:
        mapper = CoordinateMapper()

        self.assertEqual(mapper.physical_to_screen(0.30, 1.00), (180, 257))

    def test_invalid_positions_return_none(self) -> None:
        mapper = CoordinateMapper()

        self.assertIsNone(mapper.physical_to_screen(None, 1.0))
        self.assertIsNone(mapper.physical_to_screen("bad", 1.0))
        self.assertIsNone(mapper.physical_to_screen(math.nan, 1.0))
        self.assertIsNone(mapper.physical_to_screen(1.0, math.inf))
        self.assertIsNone(mapper.physical_to_screen(True, 1.0))

    def test_rejects_invalid_mapper_dimensions(self) -> None:
        with self.assertRaises(ValueError):
            CoordinateMapper(play_area_width_m=0.0)

        with self.assertRaises(ValueError):
            CoordinateMapper(screen_height_px=0)


if __name__ == "__main__":
    unittest.main()
