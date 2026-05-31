from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from src.config import load_env, load_settings, validate_settings


class ConfigTests(unittest.TestCase):
    def test_load_env_reads_values_without_overwriting_existing_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join([
                    "APP_STORE_MONITOR_MODE=real",
                    "DISCORD_ENABLED=true",
                    "DISCORD_WEBHOOK_URL=https://example.com/webhook",
                    "EXISTING_VALUE=from_file",
                    "QUOTED_VALUE=\"hello\"",
                ]),
                encoding="utf-8",
            )
            keys = [
                "APP_STORE_MONITOR_MODE",
                "DISCORD_ENABLED",
                "DISCORD_WEBHOOK_URL",
                "EXISTING_VALUE",
                "QUOTED_VALUE",
            ]
            old_values = {key: os.environ.get(key) for key in keys}
            try:
                os.environ["EXISTING_VALUE"] = "from_env"
                for key in ["APP_STORE_MONITOR_MODE", "DISCORD_ENABLED", "DISCORD_WEBHOOK_URL", "QUOTED_VALUE"]:
                    os.environ.pop(key, None)

                load_env(env_path)

                self.assertEqual(os.environ["APP_STORE_MONITOR_MODE"], "real")
                self.assertEqual(os.environ["DISCORD_ENABLED"], "true")
                self.assertEqual(os.environ["DISCORD_WEBHOOK_URL"], "https://example.com/webhook")
                self.assertEqual(os.environ["EXISTING_VALUE"], "from_env")
                self.assertEqual(os.environ["QUOTED_VALUE"], "hello")
            finally:
                _restore_env(old_values)

    def test_load_settings_and_validate_discord_requirement(self) -> None:
        keys = [
            "APP_STORE_MONITOR_MODE",
            "APP_STORE_MONITOR_DB_PATH",
            "APP_STORE_MONITOR_REPORT_DIR",
            "DISCORD_ENABLED",
            "DISCORD_WEBHOOK_URL",
        ]
        old_values = {key: os.environ.get(key) for key in keys}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["APP_STORE_MONITOR_MODE"] = "mock"
                os.environ["APP_STORE_MONITOR_DB_PATH"] = str(Path(tmp) / "test.sqlite3")
                os.environ["APP_STORE_MONITOR_REPORT_DIR"] = str(Path(tmp) / "reports")
                os.environ["DISCORD_ENABLED"] = "true"
                os.environ["DISCORD_WEBHOOK_URL"] = ""

                settings = load_settings()

                self.assertEqual(settings.mode, "mock")
                self.assertTrue(settings.discord_enabled)
                self.assertIn("DISCORD_ENABLED=true requires DISCORD_WEBHOOK_URL.", validate_settings(settings))
        finally:
            _restore_env(old_values)


def _restore_env(values: dict[str, str | None]) -> None:
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
