from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from src.config import ROOT_DIR


SCHEMA_PATH = ROOT_DIR / "sql" / "schema.sql"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _ensure_column(conn, "apps", "primary_locale", "TEXT")
        _ensure_column(conn, "apps", "source", "TEXT NOT NULL DEFAULT 'mock'")
        conn.execute("UPDATE apps SET source = 'mock' WHERE source IS NULL OR source = ''")
        conn.commit()
    finally:
        conn.close()


def upsert_app(conn: sqlite3.Connection, app: dict) -> int:
    conn.execute(
        """
        INSERT INTO apps (app_store_id, bundle_id, sku, name, primary_locale, source, updated_at)
        VALUES (:app_store_id, :bundle_id, :sku, :name, :primary_locale, :source, CURRENT_TIMESTAMP)
        ON CONFLICT(app_store_id) DO UPDATE SET
          bundle_id = excluded.bundle_id,
          sku = excluded.sku,
          name = excluded.name,
          primary_locale = excluded.primary_locale,
          source = excluded.source,
          updated_at = CURRENT_TIMESTAMP
        """,
        {**app, "primary_locale": app.get("primary_locale"), "source": app.get("source", "mock")},
    )
    row = conn.execute(
        "SELECT id FROM apps WHERE app_store_id = ?",
        (app["app_store_id"],),
    ).fetchone()
    return int(row["id"])


def upsert_daily_metrics(conn: sqlite3.Connection, rows: Iterable[dict]) -> int:
    count = 0
    for row in rows:
        conn.execute(
            """
            INSERT INTO daily_metrics (
              metric_date, app_id, source_type, impressions,
              product_page_views, downloads, conversion_rate, updated_at
            )
            VALUES (
              :metric_date, :app_id, :source_type, :impressions,
              :product_page_views, :downloads, :conversion_rate, CURRENT_TIMESTAMP
            )
            ON CONFLICT(metric_date, app_id, source_type) DO UPDATE SET
              impressions = excluded.impressions,
              product_page_views = excluded.product_page_views,
              downloads = excluded.downloads,
              conversion_rate = excluded.conversion_rate,
              updated_at = CURRENT_TIMESTAMP
            """,
            row,
        )
        count += 1
    return count


def upsert_app_usage_metrics(conn: sqlite3.Connection, rows: Iterable[dict]) -> int:
    count = 0
    for row in rows:
        conn.execute(
            """
            INSERT INTO app_usage_metrics (
              metric_date, app_id, source_type, active_devices,
              sessions, total_session_duration, updated_at
            )
            VALUES (
              :metric_date, :app_id, :source_type, :active_devices,
              :sessions, :total_session_duration, CURRENT_TIMESTAMP
            )
            ON CONFLICT(metric_date, app_id, source_type) DO UPDATE SET
              active_devices = excluded.active_devices,
              sessions = excluded.sessions,
              total_session_duration = excluded.total_session_duration,
              updated_at = CURRENT_TIMESTAMP
            """,
            row,
        )
        count += 1
    return count


def upsert_apps(conn: sqlite3.Connection, apps: Iterable[dict]) -> int:
    count = 0
    for app in apps:
        upsert_app(conn, app)
        count += 1
    return count


def list_apps_from_db(conn: sqlite3.Connection, source: str | None = None) -> list[sqlite3.Row]:
    where = "WHERE source = ?" if source else ""
    params = (source,) if source else ()
    return conn.execute(
        """
        SELECT id, app_store_id, bundle_id, sku, name, primary_locale, source, updated_at
        FROM apps
        {where}
        ORDER BY name COLLATE NOCASE
        """.format(where=where),
        params,
    ).fetchall()


def get_app_by_app_store_id(conn: sqlite3.Connection, app_store_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, app_store_id, bundle_id, sku, name, primary_locale, source
        FROM apps
        WHERE app_store_id = ?
        """,
        (app_store_id,),
    ).fetchone()


def first_real_app(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, app_store_id, bundle_id, sku, name, primary_locale, source
        FROM apps
        WHERE source = 'app_store_connect'
        ORDER BY name COLLATE NOCASE
        LIMIT 1
        """
    ).fetchone()


def delete_apps_by_source(conn: sqlite3.Connection, source: str) -> int:
    rows = conn.execute("SELECT id FROM apps WHERE source = ?", (source,)).fetchall()
    app_ids = [int(row["id"]) for row in rows]
    for app_id in app_ids:
        conn.execute("DELETE FROM daily_metrics WHERE app_id = ?", (app_id,))
        conn.execute("DELETE FROM app_usage_metrics WHERE app_id = ?", (app_id,))
    conn.execute("DELETE FROM apps WHERE source = ?", (source,))
    return len(app_ids)


def latest_metric_date(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(metric_date) AS metric_date FROM daily_metrics").fetchone()
    return row["metric_date"] if row and row["metric_date"] else None


def insert_report_run(
    conn: sqlite3.Connection,
    report_date: str,
    report_path: str,
    discord_sent: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO report_runs (report_date, report_path, discord_sent)
        VALUES (?, ?, ?)
        """,
        (report_date, report_path, 1 if discord_sent else 0),
    )


def has_discord_sent_for_date(conn: sqlite3.Connection, report_date: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM report_runs
        WHERE report_date = ? AND discord_sent = 1
        LIMIT 1
        """,
        (report_date,),
    ).fetchone()
    return row is not None


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
