from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.notifier import DISCORD_WEBHOOK_PREFIX, notify_discord, validate_discord_webhook_url


FAKE_WEBHOOK_URL = DISCORD_WEBHOOK_PREFIX + "id/token"


class NotifierTests(unittest.TestCase):
    def test_notify_discord_returns_error_without_raising(self) -> None:
        with patch("src.notifier.urllib.request.urlopen", side_effect=URLError("network down")):
            error = notify_discord(FAKE_WEBHOOK_URL, "# Report\n\nbody")

        self.assertIn("network down", error)

    def test_notify_discord_requires_webhook_url(self) -> None:
        self.assertEqual(notify_discord("", "# Report"), "DISCORD_WEBHOOK_URL is empty.")

    def test_validate_discord_webhook_url_rejects_bad_shapes(self) -> None:
        self.assertIsNone(validate_discord_webhook_url(FAKE_WEBHOOK_URL))
        self.assertEqual(
            validate_discord_webhook_url(" " + FAKE_WEBHOOK_URL),
            "DISCORD_WEBHOOK_URL has leading or trailing whitespace.",
        )
        self.assertEqual(
            validate_discord_webhook_url(f'"{FAKE_WEBHOOK_URL}"'),
            "DISCORD_WEBHOOK_URL includes quote characters.",
        )
        self.assertEqual(
            validate_discord_webhook_url("https://example.com/webhook"),
            "DISCORD_WEBHOOK_URL must start with the Discord webhook API URL prefix.",
        )

    def test_notify_discord_returns_http_error_body(self) -> None:
        error = HTTPError(
            url=FAKE_WEBHOOK_URL,
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=_Body(b'{"message":"Missing Permissions"}'),
        )
        with patch("src.notifier.urllib.request.urlopen", side_effect=error):
            result = notify_discord(FAKE_WEBHOOK_URL, "# Report")

        self.assertIn("HTTP 403", result)
        self.assertIn("Missing Permissions", result)


class _Body:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
