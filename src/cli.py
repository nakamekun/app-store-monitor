from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from src.appstore_client import (
    AppStoreConnectClient,
    AppStoreConnectAnalyticsUnavailable,
    AppStoreConnectConflictError,
    AppStoreConnectError,
    AppStoreConnectHTTPError,
    DOWNLOADS_DEFINITION,
    credentials_from_settings,
    find_active_ongoing_report_request,
    _download_count_from_row,
    _find_downloads_report,
    _get_field,
    _normalize_source_type,
    _report_instance_date,
    _report_instance_granularity,
    _segment_download_url,
)
from src.config import load_settings, validate_settings
from src.db import (
    connect,
    delete_apps_by_source,
    first_real_app,
    get_app_by_app_store_id,
    has_discord_sent_for_date,
    init_db,
    insert_report_run,
    latest_metric_date,
    list_apps_from_db,
    upsert_apps,
    upsert_app_usage_metrics,
    upsert_daily_metrics,
)
from src.mock_data import seed_mock_data
from src.notifier import notify_discord
from src.report import generate_daily_report, write_report


def main() -> None:
    _configure_output_encoding()
    parser = argparse.ArgumentParser(description="App Store Connect analytics monitoring CLI")
    parser.add_argument("--db", type=Path, help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create or migrate the SQLite schema")
    subparsers.add_parser("check-config", help="Validate .env and local API key settings")
    list_apps_parser = subparsers.add_parser("list-apps", help="List apps from App Store Connect API")
    list_apps_parser.add_argument("--limit", type=int, default=200, help="API page size, max 200")

    sync_apps_parser = subparsers.add_parser("sync-apps", help="Sync App Store Connect apps into SQLite")
    sync_apps_parser.add_argument("--limit", type=int, default=200, help="API page size, max 200")

    list_db_parser = subparsers.add_parser("list-db-apps", help="List apps currently stored in SQLite")
    list_db_parser.add_argument("--source", choices=["mock", "app_store_connect"], help="Filter by app source")

    subparsers.add_parser("clear-mock", help="Delete mock apps and their metrics from SQLite")
    subparsers.add_parser("clear-asc-apps", help="Delete App Store Connect apps from SQLite")

    fetch_parser = subparsers.add_parser("fetch", help="Fetch one day of App Store Connect analytics metrics")
    fetch_parser.add_argument("--date", help="YYYY-MM-DD. Defaults to yesterday.")
    fetch_parser.add_argument("--latest", action="store_true", help="Fetch the latest available daily report segment")
    fetch_parser.add_argument("--app-store-id", help="App Store Connect app resource ID. Defaults to first real app in DB.")
    fetch_parser.add_argument("--all", action="store_true", help="Fetch analytics for every app_store_connect app in DB")

    report_status_parser = subparsers.add_parser(
        "report-status",
        help="Diagnose Analytics Reports generation status",
    )
    report_status_group = report_status_parser.add_mutually_exclusive_group(required=True)
    report_status_group.add_argument("--app-store-id", help="App Store Connect app resource ID")
    report_status_group.add_argument("--all", action="store_true", help="Diagnose every app_store_connect app in DB")
    report_status_parser.add_argument("--days", type=int, default=7, help="Recent days to probe for daily instances")

    create_report_parser = subparsers.add_parser(
        "create-report-request",
        help="Create an ONGOING Analytics Reports request for one app",
    )
    create_report_group = create_report_parser.add_mutually_exclusive_group(required=True)
    create_report_group.add_argument("--app-store-id", help="App Store Connect app resource ID")
    create_report_group.add_argument("--all", action="store_true", help="Create requests for every app_store_connect app in DB")

    connect_parser = subparsers.add_parser("check-connection", help="Check local API key readiness")
    connect_parser.add_argument("--real", action="store_true", help="Require real API env vars")

    seed_parser = subparsers.add_parser("seed-mock", help="Insert deterministic mock metrics")
    seed_parser.add_argument("--days", type=int, default=14)
    seed_parser.add_argument("--end-date", help="YYYY-MM-DD. Defaults to yesterday.")

    report_parser = subparsers.add_parser("report", help="Generate a Markdown daily report")
    report_parser.add_argument("--date", help="YYYY-MM-DD. Defaults to latest metric date.")
    report_parser.add_argument("--latest", action="store_true", help="Use the latest metric date in SQLite")
    report_parser.add_argument("--output-dir", type=Path)
    report_parser.add_argument("--notify", action="store_true", help="Send the report to Discord")
    report_parser.add_argument(
        "--notify-once",
        action="store_true",
        help="Skip Discord if this metric date was already sent",
    )
    report_parser.add_argument("--print", action="store_true", help="Print Markdown to stdout")

    debug_metrics_parser = subparsers.add_parser("debug-metrics", help="Print raw daily_metrics rows for diagnosis")
    debug_metrics_group = debug_metrics_parser.add_mutually_exclusive_group()
    debug_metrics_group.add_argument("--date", help="YYYY-MM-DD. Defaults to latest metric date.")
    debug_metrics_group.add_argument("--latest", action="store_true", help="Use the latest metric date in SQLite")
    debug_metrics_parser.add_argument("--source", choices=["mock", "app_store_connect"], help="Filter by app source")

    debug_downloads_parser = subparsers.add_parser(
        "debug-downloads",
        help="Print raw App Downloads report columns and mapped downloads",
    )
    debug_downloads_group = debug_downloads_parser.add_mutually_exclusive_group()
    debug_downloads_group.add_argument("--latest", action="store_true", help="Use the latest App Downloads segment")
    debug_downloads_group.add_argument("--date", help="YYYY-MM-DD")
    debug_downloads_parser.add_argument("--app-store-id", help="App Store Connect app resource ID. Defaults to all real apps in DB.")

    daily_parser = subparsers.add_parser("daily", help="Run the daily monitoring flow")
    daily_parser.add_argument("--date", help="YYYY-MM-DD. Defaults to latest metric date.")
    daily_parser.add_argument("--mock", action="store_true", help="Seed mock data before reporting")
    daily_parser.add_argument("--days", type=int, default=14)
    daily_parser.add_argument("--notify", action="store_true", help="Send the report to Discord")
    daily_parser.add_argument("--print", action="store_true", help="Print Markdown to stdout")

    args = parser.parse_args()
    settings = load_settings()
    db_path = args.db or settings.db_path

    if args.command == "init-db":
        init_db(db_path)
        print(f"Initialized DB: {db_path}")
        return

    if args.command == "check-config":
        _check_config(settings)
        return

    if args.command == "check-connection":
        _check_connection(settings, require_real=args.real)
        return

    if args.command == "list-apps":
        _list_apps(settings, limit=args.limit)
        return

    if args.command == "sync-apps":
        init_db(db_path)
        _sync_apps(settings, db_path=db_path, limit=args.limit)
        return

    if args.command == "list-db-apps":
        init_db(db_path)
        _list_db_apps(db_path, source=args.source)
        return

    if args.command == "clear-mock":
        init_db(db_path)
        _clear_apps_by_source(db_path, source="mock", label="mock")
        return

    if args.command == "clear-asc-apps":
        init_db(db_path)
        _clear_apps_by_source(db_path, source="app_store_connect", label="App Store Connect")
        return

    if args.command == "fetch":
        init_db(db_path)
        if args.latest and args.date:
            raise SystemExit("Use either --latest or --date, not both.")
        target_date = None if args.latest else (args.date or _yesterday(settings).isoformat())
        if args.all and args.app_store_id:
            raise SystemExit("Use either --all or --app-store-id, not both.")
        _fetch_metrics(
            settings,
            db_path=db_path,
            report_date=target_date,
            app_store_id=args.app_store_id,
            all_apps=args.all,
            latest=args.latest,
        )
        return

    if args.command == "report-status":
        init_db(db_path)
        _report_status(settings, db_path=db_path, app_store_id=args.app_store_id, all_apps=args.all, days=args.days)
        return

    if args.command == "create-report-request":
        init_db(db_path)
        _create_report_request(settings, db_path=db_path, app_store_id=args.app_store_id, all_apps=args.all)
        return

    if args.command == "seed-mock":
        init_db(db_path)
        end_date = _parse_date(args.end_date) if args.end_date else _yesterday(settings)
        count = seed_mock_data(db_path, end_date=end_date, days=args.days)
        print(f"Seeded mock metrics: {count} rows through {end_date.isoformat()}")
        return

    if args.command == "report":
        init_db(db_path)
        if args.latest and args.date:
            raise SystemExit("Use either --latest or --date, not both.")
        _run_report(
            db_path=db_path,
            report_date=None if args.latest else args.date,
            output_dir=args.output_dir or settings.report_dir,
            notify=args.notify,
            notify_once=args.notify_once,
            print_markdown=args.print,
            webhook_url=settings.discord_webhook_url,
        )
        return

    if args.command == "debug-metrics":
        init_db(db_path)
        _debug_metrics(db_path=db_path, metric_date=None if args.latest else args.date, app_source=args.source)
        return

    if args.command == "debug-downloads":
        init_db(db_path)
        if not args.latest and not args.date:
            raise SystemExit("Use --latest or --date.")
        _debug_downloads(settings, db_path=db_path, latest=args.latest, report_date=args.date, app_store_id=args.app_store_id)
        return

    if args.command == "daily":
        init_db(db_path)
        if args.mock:
            end_date = _parse_date(args.date) if args.date else _yesterday(settings)
            count = seed_mock_data(db_path, end_date=end_date, days=args.days)
            print(f"Seeded mock metrics: {count} rows through {end_date.isoformat()}")
        notify = args.notify or (settings.discord_enabled and not args.mock)
        _run_report(
            db_path=db_path,
            report_date=args.date,
            output_dir=settings.report_dir,
            notify=notify,
            notify_once=True,
            print_markdown=args.print,
            webhook_url=settings.discord_webhook_url,
        )
        return


def _run_report(
    db_path: Path,
    report_date: str | None,
    output_dir: Path,
    notify: bool,
    notify_once: bool,
    print_markdown: bool,
    webhook_url: str,
) -> None:
    conn = connect(db_path)
    try:
        resolved_date = report_date or latest_metric_date(conn)
        if not resolved_date:
            raise SystemExit("No metrics found. Run `python -m src.cli seed-mock` first.")

        result = generate_daily_report(conn, resolved_date)
        result = write_report(result, output_dir)
        discord_sent = False

        if print_markdown:
            print(result.markdown)

        if notify and notify_once and has_discord_sent_for_date(conn, resolved_date):
            print(f"Discord notification skipped: already sent for {resolved_date}.")
        elif notify:
            error = notify_discord(webhook_url, result.markdown)
            if error:
                print(f"Discord notification skipped/failed: {error}")
            else:
                discord_sent = True
                print("Discord notification sent.")

        insert_report_run(conn, resolved_date, str(result.output_path), discord_sent)
        conn.commit()
        print(f"Report written: {result.output_path}")
    finally:
        conn.close()


def _debug_metrics(db_path: Path, metric_date: str | None, app_source: str | None = None) -> None:
    with connect(db_path) as conn:
        resolved_date = metric_date or latest_metric_date(conn)
        if not resolved_date:
            raise SystemExit("No metrics found in daily_metrics.")

        table_summary = conn.execute(
            """
            SELECT
              COUNT(*) AS row_count,
              COUNT(DISTINCT metric_date) AS date_count,
              MIN(metric_date) AS first_metric_date,
              MAX(metric_date) AS latest_metric_date
            FROM daily_metrics
            """
        ).fetchone()
        date_rows = conn.execute(
            """
            SELECT metric_date, COUNT(*) AS row_count
            FROM daily_metrics
            GROUP BY metric_date
            ORDER BY metric_date DESC
            LIMIT 10
            """
        ).fetchall()

        source_filter = "AND a.source = ?" if app_source else ""
        params = (resolved_date, app_source) if app_source else (resolved_date,)
        rows = conn.execute(
            f"""
            SELECT
              a.name AS app,
              m.metric_date,
              m.impressions,
              m.product_page_views,
              m.downloads,
              m.source_type
            FROM daily_metrics m
            JOIN apps a ON a.id = m.app_id
            WHERE m.metric_date = ?
            {source_filter}
            ORDER BY a.name COLLATE NOCASE, m.source_type COLLATE NOCASE
            """,
            params,
        ).fetchall()

        totals = conn.execute(
            f"""
            SELECT
              COUNT(*) AS row_count,
              COUNT(DISTINCT m.app_id) AS app_count,
              SUM(m.impressions) AS impressions,
              SUM(m.product_page_views) AS product_page_views,
              SUM(m.downloads) AS downloads,
              SUM(CASE WHEN m.impressions IS NULL THEN 1 ELSE 0 END) AS null_impressions,
              SUM(CASE WHEN m.product_page_views IS NULL THEN 1 ELSE 0 END) AS null_page_views,
              SUM(CASE WHEN m.downloads IS NULL THEN 1 ELSE 0 END) AS null_downloads,
              SUM(CASE WHEN m.impressions = 0 THEN 1 ELSE 0 END) AS zero_impressions,
              SUM(CASE WHEN m.product_page_views = 0 THEN 1 ELSE 0 END) AS zero_page_views,
              SUM(CASE WHEN m.downloads = 0 THEN 1 ELSE 0 END) AS zero_downloads
            FROM daily_metrics m
            JOIN apps a ON a.id = m.app_id
            WHERE m.metric_date = ?
            {source_filter}
            """,
            params,
        ).fetchone()

        source_rows = conn.execute(
            f"""
            SELECT
              m.source_type,
              COUNT(*) AS row_count,
              SUM(m.impressions) AS impressions,
              SUM(m.product_page_views) AS product_page_views,
              SUM(m.downloads) AS downloads
            FROM daily_metrics m
            JOIN apps a ON a.id = m.app_id
            WHERE m.metric_date = ?
            {source_filter}
            GROUP BY m.source_type
            ORDER BY row_count DESC, m.source_type COLLATE NOCASE
            """,
            params,
        ).fetchall()

    label = app_source or "all"
    print(
        "daily_metrics: "
        f"rows={int(table_summary['row_count'] or 0)} "
        f"dates={int(table_summary['date_count'] or 0)} "
        f"first_date={table_summary['first_metric_date'] or '-'} "
        f"latest_date={table_summary['latest_metric_date'] or '-'}"
    )
    print("date_counts:")
    for row in date_rows:
        print(f"- {row['metric_date']}: {row['row_count']}")
    print("")
    print(f"metric_date: {resolved_date}")
    print(f"source: {label}")
    print(
        "summary: "
        f"rows={int(totals['row_count'] or 0)} "
        f"apps={int(totals['app_count'] or 0)} "
        f"impressions={int(totals['impressions'] or 0)} "
        f"page_views={int(totals['product_page_views'] or 0)} "
        f"downloads={int(totals['downloads'] or 0)}"
    )
    print(
        "null_counts: "
        f"impressions={int(totals['null_impressions'] or 0)} "
        f"page_views={int(totals['null_page_views'] or 0)} "
        f"downloads={int(totals['null_downloads'] or 0)}"
    )
    print(
        "zero_counts: "
        f"impressions={int(totals['zero_impressions'] or 0)} "
        f"page_views={int(totals['zero_page_views'] or 0)} "
        f"downloads={int(totals['zero_downloads'] or 0)}"
    )
    print("")
    print("| Source Type | Rows | Impressions | Page Views | Downloads |")
    print("|---|---:|---:|---:|---:|")
    for row in source_rows:
        print(
            f"| {row['source_type']} | {row['row_count']} | {int(row['impressions'] or 0)} | "
            f"{int(row['product_page_views'] or 0)} | {int(row['downloads'] or 0)} |"
        )
    print("")
    print("| App | Date | Impressions | Page Views | Downloads | Source Type |")
    print("|---|---|---:|---:|---:|---|")
    for row in rows:
        print(
            f"| {row['app']} | {row['metric_date']} | {row['impressions']} | "
            f"{row['product_page_views']} | {row['downloads']} | {row['source_type']} |"
        )


def _debug_downloads(settings, db_path: Path, latest: bool, report_date: str | None, app_store_id: str | None) -> None:
    errors = validate_settings(settings, require_real_api=True)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    with connect(db_path) as conn:
        if app_store_id:
            app = get_app_by_app_store_id(conn, app_store_id)
            apps = [app] if app else []
        else:
            apps = list_apps_from_db(conn, source="app_store_connect")
        if not apps:
            raise SystemExit("No App Store Connect app found in DB. Run `python -m src.cli sync-apps` first.")

    client = AppStoreConnectClient(credentials_from_settings(settings))
    print(f"downloads_definition: {DOWNLOADS_DEFINITION}")
    print("")
    results = []
    for app in apps:
        result = _debug_downloads_for_app(client, app, latest=latest, report_date=report_date)
        results.append(result)
        _print_debug_downloads_result(result)
    _print_debug_downloads_summary(results)


def _debug_downloads_for_app(
    client: AppStoreConnectClient,
    app,
    latest: bool,
    report_date: str | None,
) -> dict:
    try:
        if latest:
            resolved_date, rows = client.fetch_latest_download_debug_data(app["app_store_id"])
        else:
            if not report_date:
                raise AppStoreConnectAnalyticsUnavailable("No report date specified.")
            request = client.find_ongoing_report_request(app["app_store_id"])
            reports = client.list_reports_for_request(request["id"])
            downloads_report = _find_downloads_report(reports)
            if not downloads_report:
                raise AppStoreConnectAnalyticsUnavailable("No App Downloads report found for this app.")
            resolved_date = report_date
            rows = client.download_report_rows(downloads_report["id"], report_date)
        return {
            "status": "ok",
            "app": app["name"],
            "app_store_id": app["app_store_id"],
            "report_date": resolved_date,
            "raw_columns": _raw_columns(rows),
            "raw_counts_total": _raw_counts_total(rows),
            "merged_app_total": _merged_app_total(rows),
            "territories": _unique_values(rows, "Territory"),
            "source_types": _unique_source_types(rows),
            "source_type_totals": _download_totals_by_field(rows, "Source Type"),
            "territory_totals": _download_totals_by_field(rows, "Territory"),
            "download_type_totals": _download_totals_by_field(rows, "Download Type"),
            "rows": [_download_debug_row(row) for row in rows],
        }
    except AppStoreConnectAnalyticsUnavailable as error:
        return {
            "status": "skipped",
            "app": app["name"],
            "app_store_id": app["app_store_id"],
            "reason": str(error),
        }
    except AppStoreConnectHTTPError as error:
        status = "skipped" if error.status_code == 404 else "error"
        reason = "404 not found or unsupported app state" if error.status_code == 404 else str(error)
        return {
            "status": status,
            "app": app["name"],
            "app_store_id": app["app_store_id"],
            "reason": reason,
        }
    except AppStoreConnectError as error:
        return {
            "status": "error",
            "app": app["name"],
            "app_store_id": app["app_store_id"],
            "reason": str(error),
        }


def _download_debug_row(row: dict) -> dict:
    mapped_downloads, mapped_field = _download_count_from_row(row)
    return {
        "date": _get_field(row, "Date") or "-",
        "source_type": _normalize_source_type(_get_field(row, "Source Type")),
        "download_type": _get_field(row, "Download Type") or "-",
        "mapped_downloads": mapped_downloads,
        "mapped_field": mapped_field,
    }


def _raw_columns(rows: list[dict]) -> list[str]:
    columns = []
    seen = set()
    for row in rows:
        for column in row:
            if column not in seen:
                seen.add(column)
                columns.append(column)
    return columns


def _raw_counts_total(rows: list[dict]) -> int:
    total = 0
    for row in rows:
        raw = _get_field(row, "Counts") or _get_field(row, "Downloads") or _get_field(row, "Total Downloads")
        if raw:
            try:
                total += int(float(raw.replace(",", "")))
            except ValueError:
                pass
    return total


def _merged_app_total(rows: list[dict]) -> int:
    return sum(_download_count_from_row(row)[0] for row in rows)


def _unique_values(rows: list[dict], field_name: str) -> list[str]:
    values = sorted({
        _get_field(row, field_name)
        for row in rows
        if _get_field(row, field_name)
    })
    return values


def _unique_source_types(rows: list[dict]) -> list[str]:
    return sorted({
        _normalize_source_type(_get_field(row, "Source Type"))
        for row in rows
        if _get_field(row, "Source Type")
    })


def _download_totals_by_field(rows: list[dict], field_name: str) -> list[tuple[str, int, int]]:
    totals: dict[str, list[int]] = {}
    for row in rows:
        label = _normalize_source_type(_get_field(row, field_name)) if field_name == "Source Type" else (_get_field(row, field_name) or "-")
        raw_count = _raw_counts_total([row])
        mapped_count = _download_count_from_row(row)[0]
        bucket = totals.setdefault(label, [0, 0])
        bucket[0] += raw_count
        bucket[1] += mapped_count
    return sorted(
        ((label, counts[0], counts[1]) for label, counts in totals.items()),
        key=lambda item: (-item[2], -item[1], item[0]),
    )


def _format_values(values: list[str]) -> str:
    return ", ".join(values) if values else "-"


def _format_download_totals(rows: list[tuple[str, int, int]]) -> str:
    if not rows:
        return "-"
    return ", ".join(f"{label}: raw={raw} mapped={mapped}" for label, raw, mapped in rows)


def _print_debug_downloads_result(result: dict) -> None:
    reason = f" | {result['reason']}" if result.get("reason") else ""
    print(f"[{result['status']}] {result['app']} ({result['app_store_id']}){reason}")
    if result["status"] != "ok":
        print("")
        return
    print(f"  report_date: {result['report_date']}")
    print(f"  raw columns: {', '.join(result['raw_columns']) if result['raw_columns'] else '-'}")
    print(f"  raw counts total: {result['raw_counts_total']}")
    print(f"  merged app total: {result['merged_app_total']}")
    source_type_merged_total = sum(mapped for _label, _raw, mapped in result["source_type_totals"])
    print(f"  source type merged total: {source_type_merged_total}")
    print(f"  territories: {_format_values(result['territories'])}")
    print(f"  source types: {_format_values(result['source_types'])}")
    print(f"  by download type: {_format_download_totals(result['download_type_totals'])}")
    print(f"  by source type: {_format_download_totals(result['source_type_totals'])}")
    print(f"  by territory: {_format_download_totals(result['territory_totals'])}")
    if not result["rows"]:
        print("  rows: 0")
        print("")
        return
    print("  | Date | Source Type | Download Type | Mapped Downloads | Mapped Field |")
    print("  |---|---|---|---:|---|")
    for row in result["rows"]:
        print(
            f"  | {row['date']} | {row['source_type']} | {row['download_type']} | "
            f"{row['mapped_downloads']} | {row['mapped_field']} |"
        )
    print("")


def _print_debug_downloads_summary(results: list[dict]) -> None:
    ok_results = [result for result in results if result["status"] == "ok"]
    raw_total = sum(int(result.get("raw_counts_total") or 0) for result in ok_results)
    merged_total = sum(int(result.get("merged_app_total") or 0) for result in ok_results)
    apps_with_mapped_downloads = sum(1 for result in ok_results if int(result.get("merged_app_total") or 0) > 0)
    print("Summary:")
    print(f"- apps_ok={len(ok_results)} apps_with_mapped_downloads={apps_with_mapped_downloads}")
    print(f"- raw_counts_total={raw_total}")
    print(f"- merged_app_total={merged_total}")


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}. Expected YYYY-MM-DD.") from error


def _yesterday(settings) -> date:
    return datetime.now(settings.timezone).date() - timedelta(days=1)


def _check_config(settings) -> None:
    errors = validate_settings(settings)
    print(f"mode: {settings.mode}")
    print(f"db_path: {settings.db_path}")
    print(f"report_dir: {settings.report_dir}")
    print(f"timezone: {settings.timezone.key}")
    print(f"discord_enabled: {settings.discord_enabled}")
    print(f"discord_webhook_url: {'set' if settings.discord_webhook_url else 'not set'}")
    print(f"ASC_ISSUER_ID: {'set' if settings.app_store_issuer_id else 'not set'}")
    print(f"ASC_KEY_ID: {'set' if settings.app_store_key_id else 'not set'}")
    print(f"ASC_PRIVATE_KEY_PATH: {'set' if str(settings.app_store_private_key_path) else 'not set'}")
    print(f"ASC_PRIVATE_KEY_EXISTS: {settings.app_store_private_key_path.exists()}")
    if errors:
        print("\nConfig errors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("\nConfig OK.")


def _check_connection(settings, require_real: bool) -> None:
    errors = validate_settings(settings, require_real_api=require_real)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    client = AppStoreConnectClient(credentials_from_settings(settings))
    ok, message = client.check_connection()
    print(message)
    if not ok:
        raise SystemExit(1)


def _list_apps(settings, limit: int) -> None:
    errors = validate_settings(settings, require_real_api=True)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    client = AppStoreConnectClient(credentials_from_settings(settings))
    try:
        apps = client.list_apps(limit=limit)
    except AppStoreConnectError as error:
        print(f"Failed to list apps: {error}")
        raise SystemExit(1) from error

    if not apps:
        print("No apps returned from App Store Connect API.")
        return

    print(f"Apps returned from App Store Connect API: {len(apps)}")
    for app in apps:
        attributes = app.get("attributes", {})
        name = attributes.get("name") or "(unnamed)"
        bundle_id = attributes.get("bundleId") or "-"
        sku = attributes.get("sku") or "-"
        app_id = app.get("id") or "-"
        print(f"- {name} | bundle_id={bundle_id} | sku={sku} | app_store_id={app_id}")


def _sync_apps(settings, db_path: Path, limit: int) -> None:
    errors = validate_settings(settings, require_real_api=True)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    client = AppStoreConnectClient(credentials_from_settings(settings))
    try:
        app_records = client.list_app_records(limit=limit)
    except AppStoreConnectError as error:
        print(f"Failed to sync apps: {error}")
        raise SystemExit(1) from error

    with connect(db_path) as conn:
        count = upsert_apps(conn, app_records)
        conn.commit()
        rows = list_apps_from_db(conn)

    print(f"Synced apps into SQLite: {count}")
    print(f"Apps in DB: {len(rows)}")
    for row in rows:
        print(
            f"- {row['name']} | bundle_id={row['bundle_id']} | "
            f"sku={row['sku'] or '-'} | locale={row['primary_locale'] or '-'} | "
            f"source={row['source']} | "
            f"app_store_id={row['app_store_id']}"
        )


def _list_db_apps(db_path: Path, source: str | None) -> None:
    with connect(db_path) as conn:
        rows = list_apps_from_db(conn, source=source)

    label = source or "all"
    print(f"Apps in DB ({label}): {len(rows)}")
    for row in rows:
        print(
            f"- {row['name']} | bundle_id={row['bundle_id']} | "
            f"sku={row['sku'] or '-'} | locale={row['primary_locale'] or '-'} | "
            f"source={row['source']} | app_store_id={row['app_store_id']}"
        )


def _clear_apps_by_source(db_path: Path, source: str, label: str) -> None:
    with connect(db_path) as conn:
        count = delete_apps_by_source(conn, source)
        conn.commit()
    print(f"Deleted {label} apps from SQLite: {count}")


def _fetch_metrics(
    settings,
    db_path: Path,
    report_date: str | None,
    app_store_id: str | None,
    all_apps: bool,
    latest: bool = False,
) -> None:
    errors = validate_settings(settings, require_real_api=True)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    with connect(db_path) as conn:
        if all_apps:
            apps = list_apps_from_db(conn, source="app_store_connect")
        else:
            app = get_app_by_app_store_id(conn, app_store_id) if app_store_id else first_real_app(conn)
            apps = [app] if app else []
        if not apps:
            raise SystemExit("No App Store Connect app found in DB. Run `python -m src.cli sync-apps` first.")

    client = AppStoreConnectClient(credentials_from_settings(settings))
    results = []
    for app in apps:
        result = _fetch_metrics_for_app(client, db_path, app, report_date, latest=latest)
        results.append(result)
        reason = f" | {result['reason']}" if result.get("reason") else ""
        date_text = f" date={result['report_date']}" if result.get("report_date") else ""
        print(
            f"[{result['status']}] {result['name']} ({result['app_store_id']}) "
            f"rows={result['rows_upserted']}{date_text}{reason}"
        )
        if not all_apps and result["status"] == "error":
            raise SystemExit(1)

    _print_fetch_summary(results)


def _fetch_metrics_for_app(
    client: AppStoreConnectClient,
    db_path: Path,
    app,
    report_date: str | None,
    latest: bool = False,
) -> dict:
    base = {
        "name": app["name"],
        "app_store_id": app["app_store_id"],
        "report_date": report_date,
        "rows_upserted": 0,
    }
    try:
        if latest:
            resolved_date, report_data = client.fetch_latest_daily_report_data(app["app_store_id"])
            base["report_date"] = resolved_date
        else:
            if not report_date:
                raise AppStoreConnectAnalyticsUnavailable("No report date specified.")
            report_data = client.fetch_daily_report_data(app["app_store_id"], report_date)
    except AppStoreConnectAnalyticsUnavailable as error:
        return {**base, "status": "skipped", "reason": str(error)}
    except AppStoreConnectHTTPError as error:
        if error.status_code == 403:
            return {**base, "status": "error", "reason": f"403 permission denied: {error}"}
        if error.status_code == 404:
            return {**base, "status": "skipped", "reason": "404 not found or unsupported app state"}
        return {**base, "status": "error", "reason": str(error)}
    except AppStoreConnectError as error:
        return {**base, "status": "error", "reason": str(error)}

    metric_rows = report_data["daily_metrics"]
    usage_rows = report_data["app_usage_metrics"]
    if not metric_rows and not usage_rows:
        return {
            **base,
            "status": "skipped",
            "reason": "no daily analytics segment rows found for this processing date",
        }

    rows_for_db = [{**row, "app_id": int(app["id"])} for row in metric_rows]
    usage_rows_for_db = [{**row, "app_id": int(app["id"])} for row in usage_rows]
    with connect(db_path) as conn:
        count = upsert_daily_metrics(conn, rows_for_db)
        count += upsert_app_usage_metrics(conn, usage_rows_for_db)
        conn.commit()
    return {**base, "status": "success", "rows_upserted": count}


def _print_fetch_summary(results: list[dict]) -> None:
    counts = {"success": 0, "skipped": 0, "error": 0}
    rows_upserted = 0
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        rows_upserted += int(result.get("rows_upserted", 0))
    print(
        "Summary: "
        f"success={counts['success']} "
        f"skipped={counts['skipped']} "
        f"error={counts['error']} "
        f"rows_upserted={rows_upserted}"
    )


def _report_status(settings, db_path: Path, app_store_id: str | None, all_apps: bool, days: int) -> None:
    errors = validate_settings(settings, require_real_api=True)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    if days < 1:
        raise SystemExit("--days must be 1 or greater.")

    with connect(db_path) as conn:
        if all_apps:
            apps = list_apps_from_db(conn, source="app_store_connect")
        else:
            app = get_app_by_app_store_id(conn, app_store_id or "")
            apps = [app] if app else []
        if not apps:
            raise SystemExit("App not found in DB. Run `python -m src.cli sync-apps` first.")

    client = AppStoreConnectClient(credentials_from_settings(settings))
    probe_dates = _recent_dates(settings, days)
    results = []
    for app in apps:
        result = _report_status_for_app(client, app, probe_dates)
        results.append(result)
        _print_report_status(result)

    counts = {"ok": 0, "skipped": 0, "error": 0}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    print(f"Summary: ok={counts['ok']} skipped={counts['skipped']} error={counts['error']}")


def _report_status_for_app(client: AppStoreConnectClient, app, probe_dates: list[str]) -> dict:
    base = {
        "status": "ok",
        "name": app["name"],
        "app_store_id": app["app_store_id"],
        "requests": [],
        "reports": [],
        "probe_dates": probe_dates,
        "latest_fetchable_date": None,
    }
    try:
        requests = client.list_analytics_report_requests(app["app_store_id"])
        active_request = find_active_ongoing_report_request(requests)
        base["requests"] = requests
        if not active_request:
            return {**base, "status": "skipped", "reason": "no active ONGOING request"}

        reports = client.list_reports_for_request(active_request["id"])
        report_statuses = []
        for report in reports:
            report_statuses.append(_report_detail(client, report, probe_dates))
        return {
            **base,
            "reports": report_statuses,
            "active_request_id": active_request.get("id"),
            "latest_fetchable_date": _latest_fetchable_date_from_report_statuses(report_statuses),
        }
    except AppStoreConnectHTTPError as error:
        status = "error" if error.status_code != 404 else "skipped"
        reason = "404 not found or unsupported app state" if error.status_code == 404 else str(error)
        return {**base, "status": status, "reason": reason}
    except AppStoreConnectError as error:
        return {**base, "status": "error", "reason": str(error)}


def _report_detail(client: AppStoreConnectClient, report: dict, probe_dates: list[str]) -> dict:
    report_id = report.get("id") or ""
    instances = []
    supported_fetch_report = _is_supported_fetch_report(report)
    if supported_fetch_report:
        for processing_date in probe_dates:
            for instance in client.list_report_instances(report_id, processing_date=processing_date):
                instance_id = instance.get("id") or ""
                segments = client.list_report_segments(instance_id) if instance_id else []
                instances.append({
                    "id": instance_id,
                    "date": _report_instance_date(instance) or processing_date,
                    "granularity": _report_instance_granularity(instance) or "-",
                    "category": _analytics_category(instance) or _analytics_category(report) or "-",
                    "segment_count": len(segments),
                    "has_downloadable_segment": any(_segment_download_url(segment) for segment in segments),
                })
    return {
        "id": report_id,
        "name": _analytics_name(report),
        "category": _analytics_category(report) or "-",
        "supported_fetch_report": supported_fetch_report,
        "instances": instances,
    }


def _print_report_status(result: dict) -> None:
    reason = f" | {result['reason']}" if result.get("reason") else ""
    print(f"[{result['status']}] {result['name']} ({result['app_store_id']}){reason}")
    active_request = result.get("active_request_id") or "-"
    print(f"  active_ongoing_request: {active_request}")
    print(f"  ongoing_requests: {len(result.get('requests') or [])}")
    print(f"  probed_dates: {', '.join(result.get('probe_dates') or [])}")
    print(f"  reports: {len(result.get('reports') or [])}")
    for report in result.get("reports") or []:
        print(f"  - report: {report['name']} | id={report['id']} | category={report['category']}")
        if not report["supported_fetch_report"]:
            print("    instances: not probed (not used by fetch parser)")
            continue
        if not report["instances"]:
            print("    instances: 0")
            continue
        print(f"    instances: {len(report['instances'])}")
        for instance in report["instances"]:
            segment_state = "yes" if instance["segment_count"] else "no"
            downloadable_state = "yes" if instance["has_downloadable_segment"] else "no"
            print(
                f"    - date={instance['date'] or '-'} "
                f"granularity={instance['granularity']} "
                f"category={instance['category']} "
                f"segments={segment_state} "
                f"downloadable={downloadable_state}"
            )
    print(f"  latest_fetchable_daily_date: {result.get('latest_fetchable_date') or '-'}")


def _analytics_name(item: dict) -> str:
    attributes = item.get("attributes") or {}
    return str(attributes.get("name") or item.get("id") or "-")


def _analytics_category(item: dict) -> str:
    attributes = item.get("attributes") or {}
    return str(attributes.get("category") or attributes.get("reportCategory") or "")


def _recent_dates(settings, days: int) -> list[str]:
    end_date = _yesterday(settings)
    return [
        (end_date - timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]


def _is_supported_fetch_report(report: dict) -> bool:
    name = _analytics_name(report).lower()
    return (
        "app store discovery and engagement" in name
        or "app store downloads" in name
        or "app downloads" in name
        or "app sessions" in name
    )


def _latest_fetchable_date_from_report_statuses(reports: list[dict]) -> str | None:
    latest_date = None
    for report in reports:
        if not report.get("supported_fetch_report"):
            continue
        for instance in report.get("instances") or []:
            instance_date = instance.get("date")
            if (
                instance_date
                and instance.get("granularity") == "DAILY"
                and instance.get("has_downloadable_segment")
                and (latest_date is None or instance_date > latest_date)
            ):
                latest_date = instance_date
    return latest_date


def _create_report_request(settings, db_path: Path, app_store_id: str | None, all_apps: bool) -> None:
    errors = validate_settings(settings, require_real_api=True)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    with connect(db_path) as conn:
        if all_apps:
            apps = list_apps_from_db(conn, source="app_store_connect")
        else:
            app = get_app_by_app_store_id(conn, app_store_id or "")
            apps = [app] if app else []
        if not apps:
            raise SystemExit("App not found in DB. Run `python -m src.cli sync-apps` first.")

    client = AppStoreConnectClient(credentials_from_settings(settings))

    results = []
    for app in apps:
        result = _ensure_report_request_for_app(client, app)
        results.append(result)
        status = result["status"]
        request_id = result.get("request_id") or "-"
        reason = f" | {result['reason']}" if result.get("reason") else ""
        print(f"[{status}] {result['name']} ({result['app_store_id']}) request_id={request_id}{reason}")

    _print_report_request_summary(results)
    print("Analytics report segments are usually available after 24-48 hours. Run fetch after Apple generates the daily segments.")


def _ensure_report_request_for_app(client: AppStoreConnectClient, app) -> dict:
    app_store_id = app["app_store_id"]
    try:
        request, created = client.ensure_ongoing_report_request(app_store_id)
        return {
            "status": "created" if created else "existing",
            "name": app["name"],
            "app_store_id": app_store_id,
            "request_id": request.get("id"),
        }
    except AppStoreConnectConflictError:
        try:
            request = client.find_ongoing_report_request(app_store_id)
            return {
                "status": "existing",
                "name": app["name"],
                "app_store_id": app_store_id,
                "request_id": request.get("id"),
                "reason": "409 conflict resolved as existing request",
            }
        except AppStoreConnectError as error:
            return {
                "status": "error",
                "name": app["name"],
                "app_store_id": app_store_id,
                "reason": f"409 conflict, but existing request could not be read: {error}",
            }
    except AppStoreConnectHTTPError as error:
        if error.status_code == 403:
            return {
                "status": "error",
                "name": app["name"],
                "app_store_id": app_store_id,
                "reason": f"403 permission denied: {error}",
            }
        if error.status_code == 404:
            return {
                "status": "skipped",
                "name": app["name"],
                "app_store_id": app_store_id,
                "reason": "404 not found or unsupported app state",
            }
        return {
            "status": "error",
            "name": app["name"],
            "app_store_id": app_store_id,
            "reason": str(error),
        }
    except AppStoreConnectError as error:
        return {
            "status": "error",
            "name": app["name"],
            "app_store_id": app_store_id,
            "reason": str(error),
        }


def _print_report_request_summary(results: list[dict]) -> None:
    counts = {"created": 0, "existing": 0, "skipped": 0, "error": 0}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    print(
        "Summary: "
        f"created={counts['created']} "
        f"existing={counts['existing']} "
        f"skipped={counts['skipped']} "
        f"error={counts['error']}"
    )


def _configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")


if __name__ == "__main__":
    main()
