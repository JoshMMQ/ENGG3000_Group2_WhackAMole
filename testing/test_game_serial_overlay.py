import io
import unittest
from unittest.mock import Mock, patch

from software.game.main import main, run
from software.game.sensor_overlay import SensorOverlaySnapshot, SensorOverlayValue


class _FakeScreen:
    def get_size(self):
        return 900, 900


class _FakeClock:
    def tick(self, frame_rate):
        _ = frame_rate


class _FakeDisplay:
    def __init__(self):
        self.screen = _FakeScreen()

    def set_mode(self, size, flags=0):
        _ = size, flags
        return self.screen

    def set_caption(self, caption):
        _ = caption


class _FakeTime:
    def Clock(self):
        return _FakeClock()

    def get_ticks(self):
        return 0


class _FakePygame:
    RESIZABLE = 1

    def __init__(self):
        self.display = _FakeDisplay()
        self.time = _FakeTime()
        self.quit_count = 0

    def init(self):
        return None

    def quit(self):
        self.quit_count += 1


class _FakeOverlay:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.poll_count = 0
        self.close_count = 0

    def poll(self):
        self.poll_count += 1
        return self.snapshot

    def close(self):
        self.close_count += 1


def overlay_snapshot():
    return SensorOverlaySnapshot(
        left=SensorOverlayValue("LEFT SENSOR", "/dev/ttyUSB0", "LIVE", 173.7),
        right=SensorOverlayValue("RIGHT SENSOR", "/dev/ttyUSB1", "LIVE", 170.5),
    )


class GameSerialOverlayCliTests(unittest.TestCase):
    @patch("software.game.main.run", return_value=0)
    @patch("software.game.main.SerialSensorOverlay")
    def test_cli_opens_and_forwards_serial_overlay(self, overlay_class, run_game):
        overlay = overlay_class.return_value

        result = main(
            [
                "--serial-overlay",
                "--left-port",
                "/dev/ttyUSB0",
                "--right-port",
                "/dev/ttyUSB1",
                "--baud",
                "115200",
                "--stale-after",
                "1.5",
            ]
        )

        self.assertEqual(result, 0)
        overlay_class.assert_called_once_with(
            "/dev/ttyUSB0",
            "/dev/ttyUSB1",
            baud_rate=115200,
            stale_after_s=1.5,
        )
        run_game.assert_called_once_with(
            smoke_test=False,
            input_source="simulated",
            sensor_overlay=overlay,
            safety_enabled=False,
        )

    @patch("software.game.main.run", return_value=0)
    def test_cli_can_explicitly_restore_safety_gates(self, run_game):
        result = main(["--enable-safety"])

        self.assertEqual(result, 0)
        self.assertTrue(run_game.call_args.kwargs["safety_enabled"])

    def test_cli_requires_two_distinct_ports(self):
        invalid_arguments = (
            ["--serial-overlay"],
            [
                "--serial-overlay",
                "--left-port",
                "/dev/ttyUSB0",
                "--right-port",
                "/dev/ttyUSB0",
            ],
            ["--left-port", "/dev/ttyUSB0"],
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(SystemExit), patch("sys.stderr", new=io.StringIO()):
                    main(arguments)

    def test_cli_rejects_invalid_serial_timing_values(self):
        common = [
            "--serial-overlay",
            "--left-port",
            "/dev/ttyUSB0",
            "--right-port",
            "/dev/ttyUSB1",
        ]
        for extra in (("--baud", "0"), ("--stale-after", "0"), ("--stale-after", "nan")):
            with self.subTest(extra=extra):
                with self.assertRaises(SystemExit), patch("sys.stderr", new=io.StringIO()):
                    main(common + list(extra))

    @patch("software.game.main.run")
    @patch("software.game.main.SerialSensorOverlay", side_effect=OSError("port busy"))
    def test_cli_reports_port_open_failure_without_starting_game(self, overlay_class, run_game):
        with patch("sys.stderr", new=io.StringIO()) as error_output:
            result = main(
                [
                    "--serial-overlay",
                    "--left-port",
                    "/dev/ttyUSB0",
                    "--right-port",
                    "/dev/ttyUSB1",
                ]
            )

        self.assertEqual(result, 2)
        self.assertIn("Unable to open serial overlay: port busy", error_output.getvalue())
        run_game.assert_not_called()
        overlay_class.assert_called_once()


class GameSerialOverlayRuntimeTests(unittest.TestCase):
    def test_smoke_run_polls_renders_and_closes_overlay_without_moving_cursor(self):
        snapshot = overlay_snapshot()
        overlay = _FakeOverlay(snapshot)
        fake_pygame = _FakePygame()

        with (
            patch("software.game.main.pygame", new=fake_pygame),
            patch("software.game.main.draw_loading_screen") as draw_loading,
            patch("software.game.main.draw_title_screen") as draw_title,
            patch("software.game.main.draw_game_over_screen") as draw_game_over,
            patch("software.game.main.draw_frame") as draw_frame,
        ):
            result = run(smoke_test=True, sensor_overlay=overlay)

        self.assertEqual(result, 0)
        self.assertEqual(overlay.poll_count, 1)
        self.assertEqual(overlay.close_count, 1)
        self.assertEqual(fake_pygame.quit_count, 1)
        draw_loading.assert_called_once_with(fake_pygame.display.screen, 1.0, snapshot)
        draw_title.assert_called_once_with(fake_pygame.display.screen, snapshot)
        draw_game_over.assert_called_once_with(fake_pygame.display.screen, 0, snapshot)
        self.assertEqual(draw_frame.call_count, 4)
        for call in draw_frame.call_args_list:
            self.assertEqual(call.args[1], (450, 584))
            self.assertIs(call.args[2].sensor_overlay, snapshot)


if __name__ == "__main__":
    unittest.main()
