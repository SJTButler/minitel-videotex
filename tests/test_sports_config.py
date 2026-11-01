import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pages.sports.config import (
    DEFAULT_COMPETITIONS,
    DEFAULT_BASE_URL,
    SportsConfig,
    load_env_file,
)


class EnvFileTests(unittest.TestCase):
    def test_loads_keys_without_overriding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "\n".join([
                    "# comment",
                    "FOOTBALL_API_KEY=from-file",
                    "FOOTBALL_COMPETITIONS=PL,PD",
                    "export FOOTBALL_LIVE_INTERVAL=45",
                ]),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ, {"FOOTBALL_API_KEY": "from-shell"}, clear=True
            ):
                load_env_file([path])
                self.assertEqual(os.environ["FOOTBALL_API_KEY"], "from-shell")
                self.assertEqual(os.environ["FOOTBALL_COMPETITIONS"], "PL,PD")
                self.assertEqual(os.environ["FOOTBALL_LIVE_INTERVAL"], "45")

    def test_quoted_values_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text('FOOTBALL_API_KEY="quoted"\n', encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                load_env_file([Path(directory) / "missing", path])
                self.assertEqual(os.environ["FOOTBALL_API_KEY"], "quoted")


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        config = SportsConfig.from_env(env={}, load_file=False)
        self.assertFalse(config.configured)
        self.assertEqual(config.base_url, DEFAULT_BASE_URL)
        self.assertEqual(config.competitions, DEFAULT_COMPETITIONS)

    def test_parses_and_clamps(self):
        config = SportsConfig.from_env(
            env={
                "FOOTBALL_API_KEY": " token ",
                "FOOTBALL_API_BASE": "https://example.test/v4/",
                "FOOTBALL_COMPETITIONS": "pl, pd",
                "FOOTBALL_LIVE_INTERVAL": "5",
                "FOOTBALL_DAY_INTERVAL": "10",
                "FOOTBALL_IDLE_INTERVAL": "20",
                "FOOTBALL_RETRY_DELAY": "1",
                "FOOTBALL_TIMEOUT": "0.5",
            },
            load_file=False,
        )
        self.assertTrue(config.configured)
        self.assertEqual(config.token, "token")
        self.assertEqual(config.base_url, "https://example.test/v4")
        self.assertEqual(config.competitions, ("PL", "PD"))
        self.assertEqual(config.live_interval, 30.0)
        self.assertEqual(config.day_interval, 60.0)
        self.assertEqual(config.idle_interval, 300.0)
        self.assertEqual(config.retry_delay, 15.0)
        self.assertEqual(config.timeout, 1.0)


if __name__ == "__main__":
    unittest.main()
