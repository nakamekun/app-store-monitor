from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.appstore_client import (
    AppStoreConnectClient,
    AppStoreConnectCredentials,
    AppStoreConnectConfigError,
    OPENSSL_CANDIDATE_PATHS,
    _download_count_from_row,
    _find_downloads_report,
    _merge_download_row,
    _merge_engagement_row,
    _merge_session_row,
    _report_instance_date,
    _report_instance_granularity,
    _resolve_openssl_path,
    app_record_from_api,
    find_active_ongoing_report_request,
)


class AppStoreConnectClientTests(unittest.TestCase):
    def test_build_jwt_creates_three_segment_es256_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "test_private_key.p8"
            key_path.write_text("fake private key", encoding="utf-8")
            client = AppStoreConnectClient(AppStoreConnectCredentials(
                issuer_id="issuer",
                key_id="key",
                private_key_path=key_path,
            ))
            completed = Mock(stdout=bytes.fromhex("3006020101020102"))

            with patch("src.appstore_client.time.time", return_value=1_700_000_000), \
                    patch("src.appstore_client._resolve_openssl_path", return_value="openssl"), \
                    patch("src.appstore_client.subprocess.run", return_value=completed):
                token = client.build_jwt()

        header_b64, payload_b64, signature_b64 = token.split(".")
        header = _decode_segment(header_b64)
        payload = _decode_segment(payload_b64)
        signature = _decode_bytes(signature_b64)

        self.assertEqual(header["alg"], "ES256")
        self.assertEqual(header["kid"], "key")
        self.assertEqual(payload["iss"], "issuer")
        self.assertEqual(payload["aud"], "appstoreconnect-v1")
        self.assertEqual(payload["exp"] - payload["iat"], 20 * 60)
        self.assertEqual(len(signature), 64)
        self.assertEqual(signature[-1], 2)

    def test_list_apps_returns_data_from_api_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "test_private_key.p8"
            key_path.write_text("fake private key", encoding="utf-8")
            client = AppStoreConnectClient(AppStoreConnectCredentials(
                issuer_id="issuer",
                key_id="key",
                private_key_path=key_path,
            ))
            response = _FakeResponse(json.dumps({
                "data": [
                    {
                        "id": "1234567890",
                        "attributes": {
                            "name": "Example App",
                            "bundleId": "com.example.app",
                            "sku": "example-app",
                        },
                    }
                ]
            }).encode("utf-8"))

            with patch.object(client, "build_jwt", return_value="token"), \
                    patch("src.appstore_client.urllib.request.urlopen", return_value=response) as urlopen:
                apps = client.list_apps(limit=1)

        self.assertEqual(apps[0]["attributes"]["name"], "Example App")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer token")

    def test_app_record_from_api_maps_app_store_fields(self) -> None:
        record = app_record_from_api({
            "id": "1234567890",
            "attributes": {
                "name": "Example App",
                "bundleId": "com.example.app",
                "sku": "example-app",
                "primaryLocale": "en-US",
            },
        })

        self.assertEqual(record, {
            "app_store_id": "1234567890",
            "bundle_id": "com.example.app",
            "sku": "example-app",
            "name": "Example App",
            "primary_locale": "en-US",
            "source": "app_store_connect",
        })

    def test_report_rows_merge_into_daily_metrics_by_source_type(self) -> None:
        aggregate = {}

        _merge_engagement_row(aggregate, {
            "Date": "2026-05-08",
            "Event": "Impression",
            "Source Type": "App Store search",
            "Counts": "120",
        }, fallback_date="2026-05-08")
        _merge_engagement_row(aggregate, {
            "Date": "2026-05-08",
            "Event": "Page view",
            "Source Type": "App Store search",
            "Counts": "30",
        }, fallback_date="2026-05-08")
        _merge_download_row(aggregate, {
            "Date": "2026-05-08",
            "Source Type": "App Store search",
            "Counts": "6",
        }, fallback_date="2026-05-08")

        metrics = aggregate[("2026-05-08", "App Store Search")]
        self.assertEqual(metrics["impressions"], 120)
        self.assertEqual(metrics["product_page_views"], 30)
        self.assertEqual(metrics["downloads"], 6)

    def test_download_rows_prefer_first_time_download_columns(self) -> None:
        count, field_name = _download_count_from_row({
            "Date": "2026-05-18",
            "Source Type": "App Store Search",
            "First-Time Downloads": "2",
            "Total Downloads": "9",
        })

        self.assertEqual(count, 2)
        self.assertEqual(field_name, "First-Time Downloads")

    def test_download_rows_use_download_type_to_exclude_redownloads(self) -> None:
        aggregate = {}

        _merge_download_row(aggregate, {
            "Date": "2026-05-18",
            "Source Type": "App Store Search",
            "Download Type": "First-Time Download",
            "Counts": "3",
        }, fallback_date="2026-05-18")
        _merge_download_row(aggregate, {
            "Date": "2026-05-18",
            "Source Type": "App Store Search",
            "Download Type": "Redownload",
            "Counts": "5",
        }, fallback_date="2026-05-18")

        metrics = aggregate[("2026-05-18", "App Store Search")]
        self.assertEqual(metrics["downloads"], 3)

    def test_download_rows_keep_zero_first_time_column_instead_of_total_fallback(self) -> None:
        count, field_name = _download_count_from_row({
            "Date": "2026-05-18",
            "Source Type": "App Store Search",
            "First Time Downloads": "0",
            "Total Downloads": "4",
        })

        self.assertEqual(count, 0)
        self.assertEqual(field_name, "First Time Downloads")

    def test_download_type_counts_column_is_authoritative_even_when_zero(self) -> None:
        count, field_name = _download_count_from_row({
            "Date": "2026-05-18",
            "Source Type": "App Store Search",
            "Download Type": "First-time download",
            "Counts": "0",
            "Downloads": "4",
        })

        self.assertEqual(count, 0)
        self.assertEqual(field_name, "Counts where Download Type=First-time download")

    def test_session_rows_merge_into_usage_metrics_by_source_type(self) -> None:
        aggregate = {}

        _merge_session_row(aggregate, {
            "Date": "2026-05-08",
            "Source Type": "App Store search",
            "Sessions": "14",
            "Unique Devices": "5",
            "Total Session Duration": "280",
        }, fallback_date="2026-05-08")
        _merge_session_row(aggregate, {
            "Date": "2026-05-08",
            "Source Type": "App Store search",
            "Sessions": "2",
            "Unique Devices": "1",
            "Total Session Duration": "40",
        }, fallback_date="2026-05-08")

        metrics = aggregate[("2026-05-08", "App Store Search")]
        self.assertEqual(metrics["sessions"], 16)
        self.assertEqual(metrics["active_devices"], 6)
        self.assertEqual(metrics["total_session_duration"], 320)

    def test_find_active_ongoing_report_request_skips_inactive_requests(self) -> None:
        requests = [
            {
                "id": "stopped",
                "attributes": {
                    "accessType": "ONGOING",
                    "stoppedDueToInactivity": True,
                },
            },
            {
                "id": "snapshot",
                "attributes": {
                    "accessType": "ONE_TIME_SNAPSHOT",
                    "stoppedDueToInactivity": False,
                },
            },
            {
                "id": "active",
                "attributes": {
                    "accessType": "ONGOING",
                    "stoppedDueToInactivity": False,
                },
            },
        ]

        self.assertEqual(find_active_ongoing_report_request(requests)["id"], "active")

    def test_report_instance_helpers_read_date_and_granularity(self) -> None:
        instance = {
            "attributes": {
                "processingDate": "2026-05-10",
                "granularity": "DAILY",
            }
        }

        self.assertEqual(_report_instance_date(instance), "2026-05-10")
        self.assertEqual(_report_instance_granularity(instance), "DAILY")

    def test_latest_fetchable_daily_date_uses_newest_daily_instance_with_segment(self) -> None:
        client = _FakeAnalyticsClient()

        latest = client.latest_fetchable_daily_date([
            {"id": "report-1", "attributes": {"name": "App Store Downloads"}},
        ])

        self.assertEqual(latest, "2026-05-10")

    def test_find_downloads_report_accepts_app_downloads_name(self) -> None:
        report = _find_downloads_report([
            {"id": "engagement", "attributes": {"name": "App Store Discovery and Engagement"}},
            {"id": "downloads", "attributes": {"name": "App Downloads"}},
        ])

        self.assertIsNotNone(report)
        self.assertEqual(report["id"], "downloads")

    def test_create_ongoing_report_request_posts_expected_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "test_private_key.p8"
            key_path.write_text("fake private key", encoding="utf-8")
            client = AppStoreConnectClient(AppStoreConnectCredentials(
                issuer_id="issuer",
                key_id="key",
                private_key_path=key_path,
            ))
            response = _FakeResponse(json.dumps({
                "data": {
                    "type": "analyticsReportRequests",
                    "id": "request-id",
                    "attributes": {
                        "accessType": "ONGOING",
                        "stoppedDueToInactivity": False,
                    },
                }
            }).encode("utf-8"))

            with patch.object(client, "build_jwt", return_value="token"), \
                    patch("src.appstore_client.urllib.request.urlopen", return_value=response) as urlopen:
                request = client.create_ongoing_report_request("1234567890")

        self.assertEqual(request["id"], "request-id")
        http_request = urlopen.call_args.args[0]
        self.assertEqual(http_request.get_method(), "POST")
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(payload["data"]["attributes"]["accessType"], "ONGOING")
        self.assertEqual(payload["data"]["relationships"]["app"]["data"]["id"], "1234567890")

    def test_resolve_openssl_uses_env_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            openssl_path = Path(tmp) / "openssl.exe"
            openssl_path.write_text("", encoding="utf-8")

            with patch.dict("src.appstore_client.os.environ", {"OPENSSL_PATH": str(openssl_path)}), \
                    patch("src.appstore_client.shutil.which", return_value=None):
                self.assertEqual(_resolve_openssl_path(), str(openssl_path))

    def test_resolve_openssl_checks_git_for_windows_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            openssl_path = Path(tmp) / "openssl.exe"
            openssl_path.write_text("", encoding="utf-8")

            with patch.dict("src.appstore_client.os.environ", {}, clear=True), \
                    patch("src.appstore_client.shutil.which", return_value=None), \
                    patch("src.appstore_client.OPENSSL_CANDIDATE_PATHS", [openssl_path, *OPENSSL_CANDIDATE_PATHS]):
                self.assertEqual(_resolve_openssl_path(), str(openssl_path))

    def test_resolve_openssl_error_explains_windows_fix(self) -> None:
        with patch.dict("src.appstore_client.os.environ", {}, clear=True), \
                patch("src.appstore_client.shutil.which", return_value=None), \
                patch.object(Path, "exists", return_value=False):
            with self.assertRaises(AppStoreConnectConfigError) as context:
                _resolve_openssl_path()

        message = str(context.exception)
        self.assertIn("OPENSSL_PATH", message)
        self.assertIn("Git", message)
        self.assertIn("openssl.exe", message)


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class _FakeAnalyticsClient(AppStoreConnectClient):
    def __init__(self) -> None:
        pass

    def list_report_instances(self, report_id: str, processing_date: str | None = None) -> list[dict]:
        self.assert_no_processing_date(processing_date)
        return [
            {
                "id": "old-with-segment",
                "attributes": {
                    "processingDate": "2026-05-09",
                    "granularity": "DAILY",
                },
            },
            {
                "id": "new-without-segment",
                "attributes": {
                    "processingDate": "2026-05-11",
                    "granularity": "DAILY",
                },
            },
            {
                "id": "newest-with-segment",
                "attributes": {
                    "processingDate": "2026-05-10",
                    "granularity": "DAILY",
                },
            },
            {
                "id": "weekly-with-segment",
                "attributes": {
                    "processingDate": "2026-05-12",
                    "granularity": "WEEKLY",
                },
            },
        ]

    def list_report_segments(self, instance_id: str) -> list[dict]:
        if instance_id in {"old-with-segment", "newest-with-segment", "weekly-with-segment"}:
            return [{"attributes": {"url": f"https://example.com/{instance_id}.txt.gz"}}]
        return []

    def assert_no_processing_date(self, processing_date: str | None) -> None:
        if processing_date is not None:
            raise AssertionError("latest lookup should not filter by processingDate")


def _decode_segment(segment: str) -> dict:
    return json.loads(_decode_bytes(segment).decode("utf-8"))


def _decode_bytes(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


if __name__ == "__main__":
    unittest.main()
