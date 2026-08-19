import io
import unittest
from unittest.mock import patch

from software.game.main import main


class GameCliTests(unittest.TestCase):
    @patch("software.game.main.run", return_value=0)
    def test_cli_can_explicitly_restore_safety_gates(self, run_game):
        result = main(["--enable-safety"])

        self.assertEqual(result, 0)
        self.assertTrue(run_game.call_args.kwargs["safety_enabled"])

    @patch("software.game.main.run", return_value=0)
    def test_cli_selects_version_three_sensor_scan_input(self, run_game):
        result = main(["--input", "sensor-scan"])

        self.assertEqual(result, 0)
        self.assertEqual(run_game.call_args.kwargs["input_source"], "sensor-scan")
        self.assertFalse(run_game.call_args.kwargs["safety_enabled"])

    def test_cli_rejects_safety_gates_for_sensor_scan_input(self):
        with self.assertRaises(SystemExit), patch("sys.stderr", new=io.StringIO()):
            main(["--input", "sensor-scan", "--enable-safety"])

    def test_cli_rejects_removed_legacy_input_and_overlay_options(self):
        for arguments in (
            ["--input", "udp"],
            ["--serial-overlay"],
            ["--left-port", "/dev/ttyUSB0"],
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(SystemExit), patch(
                    "sys.stderr", new=io.StringIO()
                ):
                    main(arguments)


if __name__ == "__main__":
    unittest.main()
