from __future__ import annotations

import json
import urllib.error
import urllib.request


MAX_DISCORD_CONTENT_LENGTH = 2000
DISCORD_WEBHOOK_PREFIX = "https://discord.com" + "/api/webhooks/"


def notify_discord(webhook_url: str, markdown: str) -> str | None:
    validation_error = validate_discord_webhook_url(webhook_url)
    if validation_error:
        return validation_error

    content = _to_discord_content(markdown)
    payload = json.dumps({"content": content}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "zec-app-store-monitor/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                return f"Discord webhook returned HTTP {response.status}."
    except urllib.error.HTTPError as error:
        body = _safe_error_body(error)
        detail = f": {body}" if body else ""
        return f"Discord webhook returned HTTP {error.code}{detail}"
    except urllib.error.URLError as error:
        return str(error)
    return None


def validate_discord_webhook_url(webhook_url: str) -> str | None:
    if not webhook_url:
        return "DISCORD_WEBHOOK_URL is empty."
    if webhook_url != webhook_url.strip():
        return "DISCORD_WEBHOOK_URL has leading or trailing whitespace."
    if webhook_url.startswith(("'", '"')) or webhook_url.endswith(("'", '"')):
        return "DISCORD_WEBHOOK_URL includes quote characters."
    if "\n" in webhook_url or "\r" in webhook_url:
        return "DISCORD_WEBHOOK_URL includes a newline."
    if not webhook_url.startswith(DISCORD_WEBHOOK_PREFIX):
        return "DISCORD_WEBHOOK_URL must start with the Discord webhook API URL prefix."
    return None


def _to_discord_content(markdown: str) -> str:
    lines = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            lines.append(f"**{line[2:]}**")
        elif line.startswith("## "):
            lines.append(f"\n**{line[3:]}**")
        elif line.startswith("|") or line.startswith("Generated:"):
            continue
        elif line.strip():
            lines.append(line)

    content = "\n".join(lines).strip()
    if len(content) > MAX_DISCORD_CONTENT_LENGTH:
        content = content[: MAX_DISCORD_CONTENT_LENGTH - 3] + "..."
    return content


def _safe_error_body(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return ""
    if not body:
        return ""
    if len(body) > 500:
        body = body[:497] + "..."
    return body.replace("\n", " ")
