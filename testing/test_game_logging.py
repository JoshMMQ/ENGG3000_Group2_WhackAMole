import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from software.game.logging_config import configure_logging
from software.game.main import main


class GameLoggingTests(unittest.TestCase):
    def test_detailed_messages_are_written_to_rotating_log(self) -> None:
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "game.log"
            configured_path = configure_logging(log_path)

            logging.getLogger("software.game.test").debug("coordinate x=0.30 y=1.00")
            self._flush_managed_handlers()

            self.assertEqual(configured_path, log_path)
            self.assertIn("coordinate x=0.30 y=1.00", log_path.read_text(encoding="utf-8"))

    @patch("software.game.main.run", side_effect=RuntimeError("render exploded"))
    def test_unhandled_game_exception_writes_traceback(self, run_game) -> None:
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "crash.log"

            with self.assertRaisesRegex(RuntimeError, "render exploded"):
                main(["--log-file", str(log_path)])
            self._flush_managed_handlers()

            contents = log_path.read_text(encoding="utf-8")
            self.assertIn("Unhandled game crash", contents)
            self.assertIn("RuntimeError: render exploded", contents)
            run_game.assert_called_once()

    @staticmethod
    def _flush_managed_handlers() -> None:
        for handler in logging.getLogger().handlers:
            if getattr(handler, "_whackamole_managed_handler", False):
                handler.flush()


if __name__ == "__main__":
    unittest.main()
