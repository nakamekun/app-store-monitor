from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.cli import main
from src.cli import _run_report
from src.notifier import DISCORD_WEBHOOK_PREFIX
from src.db import (
    connect,
    init_db,
    list_apps_from_db,
    upsert_app,
    upsert_apps,
    upsert_app_usage_metrics,
    upsert_daily_metrics,
)
from src.mock_data import seed_mock_data
from src.report import generate_daily_report, write_report


FAKE_WEBHOOK_URL = DISCORD_WEBHOOK_PREFIX + "id/token"


class MockDataReportIntegrationTests(unittest.TestCase):
    def test_mock_data_generates_daily_report_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "app_store_monitor.sqlite3"
            report_dir = tmp_path / "reports"

            init_db(db_path)
            seeded = seed_mock_data(db_path, end_date=date(2026, 5, 8), days=8)

            with connect(db_path) as conn:
                result = generate_daily_report(conn, "2026-05-08")
            conn.close()
            result = write_report(result, report_dir)

            self.assertGreater(seeded, 0)
            self.assertTrue(result.output_path and result.output_path.exists())
            self.assertIn("# App Store Daily Report - 2026-05-08", result.markdown)
            self.assertIn("Low volume note:", result.markdown)
            self.assertIn("## Search Winners", result.markdown)
            self.assertIn("## Emerging Apps", result.markdown)
            self.assertIn("## Low Volume Summary", result.markdown)
            self.assertIn("## CVR Top", result.markdown)
            self.assertIn("## Improvement Candidates", result.markdown)
            self.assertIn("## Source Type Breakdown", result.markdown)
            self.assertIn("URL Cleaner", result.markdown)

    def test_upsert_apps_syncs_app_store_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app_store_monitor.sqlite3"
            init_db(db_path)

            with connect(db_path) as conn:
                count = upsert_apps(conn, [{
                    "app_store_id": "1234567890",
                    "bundle_id": "com.example.app",
                    "sku": "example-app",
                    "name": "Example App",
                    "primary_locale": "en-US",
                    "source": "app_store_connect",
                }])
                conn.commit()
                rows = list_apps_from_db(conn)
            conn.close()

            self.assertEqual(count, 1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["app_store_id"], "1234567890")
            self.assertEqual(rows[0]["bundle_id"], "com.example.app")
            self.assertEqual(rows[0]["sku"], "example-app")
            self.assertEqual(rows[0]["name"], "Example App")
            self.assertEqual(rows[0]["primary_locale"], "en-US")
            self.assertEqual(rows[0]["source"], "app_store_connect")

    def test_low_volume_summary_shows_small_positive_top_rows_totals_and_search_ctr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app_store_monitor.sqlite3"
            init_db(db_path)

            with connect(db_path) as conn:
                apps = [
                    {"app_store_id": "1", "bundle_id": "com.example.bigtext", "sku": "bigtext", "name": "BigTextNote", "primary_locale": "en-US", "source": "app_store_connect"},
                    {"app_store_id": "2", "bundle_id": "com.example.water", "sku": "water", "name": "WaterDone", "primary_locale": "en-US", "source": "app_store_connect"},
                    {"app_store_id": "3", "bundle_id": "com.example.zero", "sku": "zero", "name": "ZeroApp", "primary_locale": "en-US", "source": "app_store_connect"},
                    {"app_store_id": "4", "bundle_id": "com.example.third", "sku": "third", "name": "ThirdApp", "primary_locale": "en-US", "source": "app_store_connect"},
                    {"app_store_id": "5", "bundle_id": "com.example.fourth", "sku": "fourth", "name": "FourthApp", "primary_locale": "en-US", "source": "app_store_connect"},
                    {"app_store_id": "6", "bundle_id": "com.example.fifth", "sku": "fifth", "name": "FifthApp", "primary_locale": "en-US", "source": "app_store_connect"},
                    {"app_store_id": "7", "bundle_id": "com.example.sixth", "sku": "sixth", "name": "SixthApp", "primary_locale": "en-US", "source": "app_store_connect"},
                    {"app_store_id": "8", "bundle_id": "com.example.downloaded", "sku": "downloaded", "name": "DownloadedApp", "primary_locale": "en-US", "source": "app_store_connect"},
                    {"app_store_id": "9", "bundle_id": "com.example.seventh", "sku": "seventh", "name": "SeventhApp", "primary_locale": "en-US", "source": "app_store_connect"},
                ]
                app_ids = {app["sku"]: upsert_app(conn, app) for app in apps}
                upsert_daily_metrics(conn, [
                    {"metric_date": "2026-05-16", "app_id": app_ids["bigtext"], "source_type": "App Store Search", "impressions": 12, "product_page_views": 1, "downloads": 0, "conversion_rate": 0.0},
                    {"metric_date": "2026-05-16", "app_id": app_ids["water"], "source_type": "App Store Browse", "impressions": 2, "product_page_views": 4, "downloads": 0, "conversion_rate": 0.0},
                    {"metric_date": "2026-05-16", "app_id": app_ids["zero"], "source_type": "App Store Search", "impressions": 0, "product_page_views": 0, "downloads": 0, "conversion_rate": 0.0},
                    {"metric_date": "2026-05-16", "app_id": app_ids["third"], "source_type": "App Store Search", "impressions": 3, "product_page_views": 2, "downloads": 0, "conversion_rate": 0.0},
                    {"metric_date": "2026-05-16", "app_id": app_ids["fourth"], "source_type": "App Store Search", "impressions": 8, "product_page_views": 2, "downloads": 0, "conversion_rate": 0.0},
                    {"metric_date": "2026-05-16", "app_id": app_ids["fifth"], "source_type": "App Store Search", "impressions": 6, "product_page_views": 2, "downloads": 0, "conversion_rate": 0.0},
                    {"metric_date": "2026-05-16", "app_id": app_ids["sixth"], "source_type": "App Store Search", "impressions": 1, "product_page_views": 1, "downloads": 0, "conversion_rate": 0.0},
                    {"metric_date": "2026-05-16", "app_id": app_ids["downloaded"], "source_type": "App Store Search", "impressions": 20, "product_page_views": 8, "downloads": 1, "conversion_rate": 0.125},
                    {"metric_date": "2026-05-16", "app_id": app_ids["seventh"], "source_type": "App Store Search", "impressions": 2, "product_page_views": 1, "downloads": 0, "conversion_rate": 0.0},
                ])
                upsert_app_usage_metrics(conn, [
                    {"metric_date": "2026-05-16", "app_id": app_ids["bigtext"], "source_type": "App Store Search", "active_devices": 4, "sessions": 9, "total_session_duration": 180},
                    {"metric_date": "2026-05-16", "app_id": app_ids["downloaded"], "source_type": "App Store Search", "active_devices": 8, "sessions": 12, "total_session_duration": 360},
                    {"metric_date": "2026-05-16", "app_id": app_ids["third"], "source_type": "App Store Browse", "active_devices": 2, "sessions": 7, "total_session_duration": 140},
                ])
                conn.commit()
                result = generate_daily_report(conn, "2026-05-16")
            conn.close()

            summary_section = result.markdown.split("## Summary", maxsplit=1)[1].split("## Search Winners", maxsplit=1)[0]
            self.assertIn("- Apps with downloads: 1 / 9", summary_section)
            self.assertIn("- Total downloads: 1", summary_section)
            self.assertIn("- Best CTR app: DownloadedApp (12.50%)", summary_section)
            self.assertIn("- Highest impressions app: DownloadedApp (20)", summary_section)
            winners_section = result.markdown.split("## Search Winners", maxsplit=1)[1].split("## Emerging Apps", maxsplit=1)[0]
            self.assertIn("DownloadedApp - impressions: 20, page views: 8, CTR: 40.0%, downloads: 1", winners_section)
            emerging_section = result.markdown.split("## Emerging Apps", maxsplit=1)[1].split("## Search Exposure, No Downloads", maxsplit=1)[0]
            self.assertIn("| DownloadedApp | +20 | +8 | 1 | +1 |", emerging_section)
            low_volume = result.markdown.split("## Low Volume Summary", maxsplit=1)[1].split("## App Usage Top", maxsplit=1)[0]
            self.assertIn("| 1 | DownloadedApp | 20 |", low_volume)
            self.assertIn("| 2 | BigTextNote | 12 |", low_volume)
            self.assertIn("| 3 | FourthApp | 8 |", low_volume)
            self.assertIn("| 2 | WaterDone | 4 |", low_volume)
            self.assertIn("| 3 | ThirdApp | 2 |", low_volume)
            self.assertNotIn("| ZeroApp | 0 |", low_volume)
            self.assertIn("| Search impressions total | Total | 52 |", result.markdown)
            self.assertIn("| Browse impressions total | Total | 2 |", result.markdown)
            self.assertIn("| Total page views | Total |  | 21 |", result.markdown)
            self.assertIn("### Search CTR", low_volume)
            self.assertIn("| Total | 52 | 17 | 32.7% |", low_volume)
            self.assertIn("| DownloadedApp | 20 | 8 | 40.0% |", low_volume)
            self.assertIn("| BigTextNote | 12 | 1 | 8.3% |", low_volume)
            exposure_section = result.markdown.split("## Search Exposure, No Downloads", maxsplit=1)[1].split("## Low Volume Summary", maxsplit=1)[0]
            self.assertIn("BigTextNote", exposure_section)
            self.assertIn("search impressions: 12, page views: 1, CTR: 8.3%, app downloads: 0", exposure_section)
            self.assertIn("search impressions: 8, page views: 2, CTR: 25.0%, app downloads: 0", exposure_section)
            self.assertIn("search impressions: 6, page views: 2, CTR: 33.3%, app downloads: 0", exposure_section)
            self.assertIn("search impressions: 3, page views: 2, CTR: 66.7%, app downloads: 0", exposure_section)
            self.assertIn("search impressions: 2, page views: 1, CTR: 50.0%, app downloads: 0", exposure_section)
            self.assertNotIn("SixthApp", exposure_section)
            self.assertNotIn("DownloadedApp", exposure_section)
            self.assertNotIn("WaterDone", exposure_section)
            usage_section = result.markdown.split("## App Usage Top", maxsplit=1)[1].split("## CVR Top", maxsplit=1)[0]
            self.assertIn("### Active Devices Top", usage_section)
            self.assertIn("| 1 | DownloadedApp | 8 | 12 |", usage_section)
            self.assertIn("### Sessions Top", usage_section)
            self.assertIn("| 1 | DownloadedApp | 12 | 8 |", usage_section)
            self.assertIn("| 2 | BigTextNote | 9 | 4 |", usage_section)

    def test_search_exposure_no_downloads_uses_app_aggregate_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app_store_monitor.sqlite3"
            init_db(db_path)

            with connect(db_path) as conn:
                app_id = upsert_app(conn, {
                    "app_store_id": "1",
                    "bundle_id": "com.example.crosssource",
                    "sku": "crosssource",
                    "name": "CrossSourceApp",
                    "primary_locale": "en-US",
                    "source": "app_store_connect",
                })
                upsert_daily_metrics(conn, [
                    {
                        "metric_date": "2026-05-20",
                        "app_id": app_id,
                        "source_type": "App Store Search",
                        "impressions": 40,
                        "product_page_views": 2,
                        "downloads": 0,
                        "conversion_rate": 0.0,
                    },
                    {
                        "metric_date": "2026-05-20",
                        "app_id": app_id,
                        "source_type": "App Referrer",
                        "impressions": 0,
                        "product_page_views": 1,
                        "downloads": 1,
                        "conversion_rate": 1.0,
                    },
                ])
                conn.commit()
                result = generate_daily_report(conn, "2026-05-20")
            conn.close()

            exposure_section = result.markdown.split("## Search Exposure, No Downloads", maxsplit=1)[1].split("## Low Volume Summary", maxsplit=1)[0]
            self.assertIn("No candidates.", exposure_section)
            self.assertNotIn("CrossSourceApp", exposure_section)

    def test_low_volume_summary_shows_empty_messages_for_zero_totals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app_store_monitor.sqlite3"
            init_db(db_path)

            with connect(db_path) as conn:
                app_id = upsert_app(conn, {
                    "app_store_id": "1",
                    "bundle_id": "com.example.empty",
                    "sku": "empty",
                    "name": "EmptyApp",
                    "primary_locale": "en-US",
                    "source": "app_store_connect",
                })
                upsert_daily_metrics(conn, [{
                    "metric_date": "2026-05-16",
                    "app_id": app_id,
                    "source_type": "App Store Search",
                    "impressions": 0,
                    "product_page_views": 0,
                    "downloads": 0,
                    "conversion_rate": 0.0,
                }])
                conn.commit()
                result = generate_daily_report(conn, "2026-05-16")
            conn.close()

            self.assertIn("No apps with impressions yet.", result.markdown)
            self.assertIn("No page views yet.", result.markdown)
            self.assertIn("No apps with search impressions yet.", result.markdown)

    def test_notify_once_skips_discord_after_metric_date_was_sent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "app_store_monitor.sqlite3"
            report_dir = tmp_path / "reports"
            init_db(db_path)

            with connect(db_path) as conn:
                app_id = upsert_app(conn, {
                    "app_store_id": "1",
                    "bundle_id": "com.example.once",
                    "sku": "once",
                    "name": "OnceApp",
                    "primary_locale": "en-US",
                    "source": "app_store_connect",
                })
                upsert_daily_metrics(conn, [{
                    "metric_date": "2026-05-16",
                    "app_id": app_id,
                    "source_type": "App Store Search",
                    "impressions": 10,
                    "product_page_views": 2,
                    "downloads": 0,
                    "conversion_rate": 0.0,
                }])
                conn.commit()
            conn.close()

            with patch("src.cli.notify_discord", return_value=None) as notify:
                _run_report(
                    db_path=db_path,
                    report_date="2026-05-16",
                    output_dir=report_dir,
                    notify=True,
                    notify_once=True,
                    print_markdown=False,
                    webhook_url=FAKE_WEBHOOK_URL,
                )
                _run_report(
                    db_path=db_path,
                    report_date="2026-05-16",
                    output_dir=report_dir,
                    notify=True,
                    notify_once=True,
                    print_markdown=False,
                    webhook_url=FAKE_WEBHOOK_URL,
                )

            self.assertEqual(notify.call_count, 1)

    def test_manual_notify_can_send_after_notify_once_sent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "app_store_monitor.sqlite3"
            report_dir = tmp_path / "reports"
            init_db(db_path)

            with connect(db_path) as conn:
                app_id = upsert_app(conn, {
                    "app_store_id": "1",
                    "bundle_id": "com.example.manual",
                    "sku": "manual",
                    "name": "ManualApp",
                    "primary_locale": "en-US",
                    "source": "app_store_connect",
                })
                upsert_daily_metrics(conn, [{
                    "metric_date": "2026-05-16",
                    "app_id": app_id,
                    "source_type": "App Store Search",
                    "impressions": 10,
                    "product_page_views": 2,
                    "downloads": 0,
                    "conversion_rate": 0.0,
                }])
                conn.commit()
            conn.close()

            with patch("src.cli.notify_discord", return_value=None) as notify:
                _run_report(
                    db_path=db_path,
                    report_date="2026-05-16",
                    output_dir=report_dir,
                    notify=True,
                    notify_once=True,
                    print_markdown=False,
                    webhook_url=FAKE_WEBHOOK_URL,
                )
                _run_report(
                    db_path=db_path,
                    report_date="2026-05-16",
                    output_dir=report_dir,
                    notify=True,
                    notify_once=False,
                    print_markdown=False,
                    webhook_url=FAKE_WEBHOOK_URL,
                )

            self.assertEqual(notify.call_count, 2)

    def test_daily_mock_does_not_use_env_discord_unless_notify_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "app_store_monitor.sqlite3"
            report_dir = tmp_path / "reports"
            env = {
                "APP_STORE_MONITOR_DB_PATH": str(db_path),
                "APP_STORE_MONITOR_REPORT_DIR": str(report_dir),
                "APP_STORE_MONITOR_MODE": "mock",
                "APP_STORE_MONITOR_TIMEZONE": "UTC",
                "DISCORD_ENABLED": "true",
                "DISCORD_WEBHOOK_URL": FAKE_WEBHOOK_URL,
            }

            with patch.dict("os.environ", env, clear=False), \
                    patch("sys.argv", ["cli", "--db", str(db_path), "daily", "--mock", "--date", "2026-05-16"]), \
                    patch("src.cli.notify_discord", return_value=None) as notify:
                main()

            self.assertEqual(notify.call_count, 0)


if __name__ == "__main__":
    unittest.main()
