from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_env(path: Path | None = None) -> None:
    env_path = path or ROOT_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return ROOT_DIR / path


@dataclass(frozen=True)
class Settings:
    mode: str
    db_path: Path
    report_dir: Path
    discord_webhook_url: str
    discord_enabled: bool
    timezone: ZoneInfo
    app_store_issuer_id: str
    app_store_key_id: str
    app_store_private_key_path: Path
    app_store_vendor_number: str


def load_settings() -> Settings:
    load_env()
    private_key_path = resolve_path(
        _env_first("ASC_PRIVATE_KEY_PATH", "APP_STORE_CONNECT_PRIVATE_KEY_PATH"),
        ROOT_DIR / "private_keys" / "app_store_connect_api_key.p8",
    )
    return Settings(
        mode=_load_mode(os.getenv("APP_STORE_MONITOR_MODE", "mock")),
        db_path=resolve_path(
            os.getenv("APP_STORE_MONITOR_DB_PATH"),
            ROOT_DIR / "data" / "app_store_monitor.sqlite3",
        ),
        report_dir=resolve_path(
            os.getenv("APP_STORE_MONITOR_REPORT_DIR"),
            ROOT_DIR / "reports",
        ),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
        discord_enabled=os.getenv("DISCORD_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
        timezone=_load_timezone(os.getenv("APP_STORE_MONITOR_TIMEZONE", "Asia/Tokyo")),
        app_store_issuer_id=_env_first("ASC_ISSUER_ID", "APP_STORE_CONNECT_ISSUER_ID").strip(),
        app_store_key_id=_env_first("ASC_KEY_ID", "APP_STORE_CONNECT_KEY_ID").strip(),
        app_store_private_key_path=private_key_path,
        app_store_vendor_number=_env_first("ASC_VENDOR_NUMBER", "APP_STORE_CONNECT_VENDOR_NUMBER").strip(),
    )


def validate_settings(settings: Settings, require_real_api: bool = False) -> list[str]:
    errors = []
    if settings.mode not in {"mock", "real"}:
        errors.append("APP_STORE_MONITOR_MODE must be `mock` or `real`.")
    if settings.discord_enabled and not settings.discord_webhook_url:
        errors.append("DISCORD_ENABLED=true requires DISCORD_WEBHOOK_URL.")

    if require_real_api or settings.mode == "real":
        missing = []
        if not settings.app_store_issuer_id:
            missing.append("ASC_ISSUER_ID")
        if not settings.app_store_key_id:
            missing.append("ASC_KEY_ID")
        if not str(settings.app_store_private_key_path):
            missing.append("ASC_PRIVATE_KEY_PATH")
        if missing:
            errors.append("Missing App Store Connect env vars: " + ", ".join(missing))
        if settings.app_store_private_key_path and not settings.app_store_private_key_path.exists():
            errors.append(f"Private key file not found: {settings.app_store_private_key_path}")

    return errors


def _load_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Tokyo")


def _load_mode(value: str) -> str:
    mode = value.strip().lower()
    return mode or "mock"


def _env_first(primary: str, fallback: str) -> str:
    return os.getenv(primary) or os.getenv(fallback) or ""
