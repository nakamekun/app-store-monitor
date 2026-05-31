from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


APP_STORE_CONNECT_API_BASE_URL = "https://api.appstoreconnect.apple.com/v1"
ROOT_DIR = Path(__file__).resolve().parents[1]
OPENSSL_ENV_VAR = "OPENSSL_PATH"
OPENSSL_CANDIDATE_PATHS = [
    Path(r"C:\Program Files\Git\usr\bin\openssl.exe"),
    Path(r"C:\Program Files (x86)\Git\usr\bin\openssl.exe"),
    Path("/opt/homebrew/bin/openssl"),
    Path("/usr/local/bin/openssl"),
    Path("/usr/bin/openssl"),
]
DOWNLOADS_DEFINITION = (
    "downloads uses first-time downloads when available: First-Time Downloads / "
    "First Time Downloads / App Units, or Counts where Download Type is first-time. "
    "It falls back to Counts/Downloads only when the TSV does not expose a distinct "
    "first-time download field or Download Type."
)
FIRST_TIME_DOWNLOAD_FIELDS = (
    "First-Time Downloads",
    "First Time Downloads",
    "First-Time Download",
    "First Time Download",
    "App Units",
)
TOTAL_DOWNLOAD_FIELDS = (
    "Total Downloads",
    "Downloads",
    "Counts",
)
FIRST_TIME_DOWNLOAD_TYPES = {
    "firsttimedownload",
    "firsttimedownloads",
    "firsttime",
    "appunit",
    "appunits",
}


@dataclass(frozen=True)
class AppStoreConnectCredentials:
    issuer_id: str
    key_id: str
    private_key_path: Path
    vendor_number: str | None = None


class AppStoreConnectError(RuntimeError):
    pass


class AppStoreConnectConfigError(AppStoreConnectError):
    pass


class AppStoreConnectHTTPError(AppStoreConnectError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AppStoreConnectConflictError(AppStoreConnectHTTPError):
    pass


class AppStoreConnectAnalyticsUnavailable(AppStoreConnectError):
    pass


class AppStoreConnectClient:
    """Small App Store Connect API client for connection checks and app listing."""

    def __init__(self, credentials: AppStoreConnectCredentials) -> None:
        self.credentials = credentials

    def check_api_key_files(self) -> list[str]:
        errors = []
        if not self.credentials.issuer_id:
            errors.append("ASC_ISSUER_ID is empty.")
        if not self.credentials.key_id:
            errors.append("ASC_KEY_ID is empty.")
        if not self.credentials.private_key_path.exists():
            errors.append(f"Private key file not found: {self.credentials.private_key_path}")
        return errors

    def build_jwt(self) -> str:
        errors = self.check_api_key_files()
        if errors:
            raise AppStoreConnectConfigError(" ".join(errors))

        now = int(time.time())
        header = {
            "alg": "ES256",
            "kid": self.credentials.key_id,
            "typ": "JWT",
        }
        payload = {
            "iss": self.credentials.issuer_id,
            "iat": now,
            "exp": now + 20 * 60,
            "aud": "appstoreconnect-v1",
        }
        signing_input = ".".join([
            _base64url_json(header),
            _base64url_json(payload),
        ])
        signature = _sign_es256_with_openssl(
            signing_input.encode("ascii"),
            self.credentials.private_key_path,
        )
        return f"{signing_input}.{_base64url(signature)}"

    def check_connection(self) -> tuple[bool, str]:
        errors = self.check_api_key_files()
        if errors:
            return False, " ".join(errors)
        try:
            self.build_jwt()
        except AppStoreConnectError as error:
            return False, str(error)
        return True, "API key files look ready and JWT generation succeeded."

    def list_apps(self, limit: int = 200) -> list[dict]:
        token = self.build_jwt()
        payload = self._get_json("/apps", {"limit": str(limit)}, token)
        return list(payload.get("data", []))

    def list_app_records(self, limit: int = 200) -> list[dict]:
        return [app_record_from_api(item) for item in self.list_apps(limit=limit)]

    def fetch_daily_metrics(self, app_store_id: str, report_date: str) -> list[dict]:
        data = self.fetch_daily_report_data(app_store_id, report_date)
        return data["daily_metrics"]

    def fetch_daily_report_data(self, app_store_id: str, report_date: str) -> dict[str, list[dict]]:
        request = self.find_ongoing_report_request(app_store_id)
        reports = self.list_reports_for_request(request["id"])
        engagement_report = _find_report(reports, "App Store Discovery and Engagement")
        downloads_report = _find_downloads_report(reports)
        sessions_report = _find_report(reports, "App Sessions")
        if not engagement_report and not downloads_report and not sessions_report:
            raise AppStoreConnectAnalyticsUnavailable(
                "No supported analytics reports found. Expected App Store Discovery and Engagement "
                "and/or App Downloads and/or App Sessions reports. If analytics reports were just requested, Apple "
                "may need 24-48 hours before segments are available."
            )

        return self.fetch_daily_data_for_reports(
            report_date,
            engagement_report=engagement_report,
            downloads_report=downloads_report,
            sessions_report=sessions_report,
        )

    def fetch_latest_daily_metrics(self, app_store_id: str) -> tuple[str, list[dict]]:
        report_date, data = self.fetch_latest_daily_report_data(app_store_id)
        return report_date, data["daily_metrics"]

    def fetch_latest_daily_report_data(self, app_store_id: str) -> tuple[str, dict[str, list[dict]]]:
        request = self.find_ongoing_report_request(app_store_id)
        reports = self.list_reports_for_request(request["id"])
        engagement_report = _find_report(reports, "App Store Discovery and Engagement")
        downloads_report = _find_downloads_report(reports)
        sessions_report = _find_report(reports, "App Sessions")
        latest_date = self.latest_fetchable_daily_date(
            [report for report in [engagement_report, downloads_report, sessions_report] if report]
        )
        if not latest_date:
            raise AppStoreConnectAnalyticsUnavailable(
                "No fetchable daily analytics report segment found. The ONGOING request may still be generating, "
                "or App Store Connect returned no DAILY instances with downloadable segments."
            )
        return latest_date, self.fetch_daily_data_for_reports(
            latest_date,
            engagement_report=engagement_report,
            downloads_report=downloads_report,
            sessions_report=sessions_report,
        )

    def fetch_latest_download_debug_data(self, app_store_id: str) -> tuple[str, list[dict]]:
        request = self.find_ongoing_report_request(app_store_id)
        reports = self.list_reports_for_request(request["id"])
        downloads_report = _find_downloads_report(reports)
        if not downloads_report:
            raise AppStoreConnectAnalyticsUnavailable("No App Downloads report found for this app.")
        latest_date = self.latest_fetchable_daily_date([downloads_report])
        if not latest_date:
            raise AppStoreConnectAnalyticsUnavailable(
                "No fetchable daily App Downloads segment found for this app."
            )
        return latest_date, self.download_report_rows(downloads_report["id"], latest_date)

    def fetch_daily_metrics_for_reports(
        self,
        report_date: str,
        engagement_report: dict | None,
        downloads_report: dict | None,
    ) -> list[dict]:
        return self.fetch_daily_data_for_reports(
            report_date,
            engagement_report=engagement_report,
            downloads_report=downloads_report,
            sessions_report=None,
        )["daily_metrics"]

    def fetch_daily_data_for_reports(
        self,
        report_date: str,
        engagement_report: dict | None,
        downloads_report: dict | None,
        sessions_report: dict | None,
    ) -> dict[str, list[dict]]:
        aggregate: dict[tuple[str, str], dict] = {}
        usage_aggregate: dict[tuple[str, str], dict] = {}
        if engagement_report:
            for row in self.download_report_rows(engagement_report["id"], report_date):
                _merge_engagement_row(aggregate, row, fallback_date=report_date)

        if downloads_report:
            for row in self.download_report_rows(downloads_report["id"], report_date):
                _merge_download_row(aggregate, row, fallback_date=report_date)

        if sessions_report:
            for row in self.download_report_rows(sessions_report["id"], report_date):
                _merge_session_row(usage_aggregate, row, fallback_date=report_date)

        rows = []
        for (metric_date, source_type), metrics in sorted(aggregate.items()):
            views = metrics["product_page_views"]
            downloads = metrics["downloads"]
            rows.append({
                "metric_date": metric_date,
                "source_type": source_type,
                "impressions": metrics["impressions"],
                "product_page_views": views,
                "downloads": downloads,
                "conversion_rate": round(downloads / views, 4) if views else 0.0,
            })
        usage_rows = []
        for (metric_date, source_type), metrics in sorted(usage_aggregate.items()):
            usage_rows.append({
                "metric_date": metric_date,
                "source_type": source_type,
                "active_devices": metrics["active_devices"],
                "sessions": metrics["sessions"],
                "total_session_duration": metrics["total_session_duration"],
            })
        return {"daily_metrics": rows, "app_usage_metrics": usage_rows}

    def latest_fetchable_daily_date(self, reports: list[dict]) -> str | None:
        latest_date = None
        for report in reports:
            report_id = report.get("id")
            if not report_id:
                continue
            for instance in self.list_report_instances(report_id):
                instance_id = instance.get("id")
                if not instance_id:
                    continue
                instance_date = _report_instance_date(instance)
                if not instance_date or _report_instance_granularity(instance) != "DAILY":
                    continue
                has_downloadable_segment = any(
                    _segment_download_url(segment)
                    for segment in self.list_report_segments(instance_id)
                )
                if has_downloadable_segment and (latest_date is None or instance_date > latest_date):
                    latest_date = instance_date
        return latest_date

    def find_ongoing_report_request(self, app_store_id: str) -> dict:
        requests = self.list_analytics_report_requests(app_store_id)
        request = find_active_ongoing_report_request(requests)
        if request:
            return request
        raise AppStoreConnectAnalyticsUnavailable(
            f"No active ONGOING analytics report request found for app {app_store_id}. "
            "Create an ONGOING Analytics Reports request in App Store Connect API first; "
            "Apple usually generates the first report after 24-48 hours."
        )

    def ensure_ongoing_report_request(self, app_store_id: str) -> tuple[dict, bool]:
        requests = self.list_analytics_report_requests(app_store_id)
        existing = find_active_ongoing_report_request(requests)
        if existing:
            return existing, False
        return self.create_ongoing_report_request(app_store_id), True

    def create_ongoing_report_request(self, app_store_id: str) -> dict:
        token = self.build_jwt()
        payload = {
            "data": {
                "type": "analyticsReportRequests",
                "attributes": {
                    "accessType": "ONGOING",
                },
                "relationships": {
                    "app": {
                        "data": {
                            "type": "apps",
                            "id": app_store_id,
                        },
                    },
                },
            },
        }
        response = self._post_json("/analyticsReportRequests", payload, token)
        return response["data"]

    def list_analytics_report_requests(self, app_store_id: str) -> list[dict]:
        token = self.build_jwt()
        payload = self._get_json(
            f"/apps/{app_store_id}/analyticsReportRequests",
            {
                "filter[accessType]": "ONGOING",
                "limit": "200",
            },
            token,
        )
        return list(payload.get("data", []))

    def list_reports_for_request(self, request_id: str) -> list[dict]:
        token = self.build_jwt()
        payload = self._get_json(
            f"/analyticsReportRequests/{request_id}/reports",
            {"limit": "200"},
            token,
        )
        return list(payload.get("data", []))

    def list_report_instances(self, report_id: str, processing_date: str | None = None) -> list[dict]:
        token = self.build_jwt()
        params = {
            "filter[granularity]": "DAILY",
            "limit": "200",
        }
        if processing_date:
            params["filter[processingDate]"] = processing_date
        payload = self._get_json(
            f"/analyticsReports/{report_id}/instances",
            params,
            token,
        )
        return list(payload.get("data", []))

    def list_report_segments(self, instance_id: str) -> list[dict]:
        token = self.build_jwt()
        payload = self._get_json(
            f"/analyticsReportInstances/{instance_id}/segments",
            {"limit": "200"},
            token,
        )
        return list(payload.get("data", []))

    def download_report_rows(self, report_id: str, processing_date: str) -> list[dict]:
        instances = self.list_report_instances(report_id, processing_date)
        if not instances:
            return []

        rows = []
        for instance in instances:
            instance_id = instance.get("id")
            if not instance_id:
                continue
            for segment in self.list_report_segments(instance_id):
                download_url = _segment_download_url(segment)
                if not download_url:
                    continue
                rows.extend(_parse_tsv_gz(self._download_url(download_url)))
        return rows

    def _post_json(self, path: str, payload: dict, token: str) -> dict:
        url = f"{APP_STORE_CONNECT_API_BASE_URL}{path}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            message = _format_http_error(error)
            if error.code == 409:
                raise AppStoreConnectConflictError(message, status_code=error.code) from error
            raise AppStoreConnectHTTPError(message, status_code=error.code) from error
        except urllib.error.URLError as error:
            raise AppStoreConnectHTTPError(f"Network error while calling App Store Connect API: {error.reason}") from error

        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise AppStoreConnectHTTPError("App Store Connect API returned invalid JSON.") from error

    def _get_json(self, path: str, params: dict[str, str], token: str) -> dict:
        query = urllib.parse.urlencode(params)
        url = f"{APP_STORE_CONNECT_API_BASE_URL}{path}"
        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            message = _format_http_error(error)
            raise AppStoreConnectHTTPError(message, status_code=error.code) from error
        except urllib.error.URLError as error:
            raise AppStoreConnectHTTPError(f"Network error while calling App Store Connect API: {error.reason}") from error

        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise AppStoreConnectHTTPError("App Store Connect API returned invalid JSON.") from error

    def _download_url(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            message = _format_http_error(error)
            raise AppStoreConnectHTTPError(message, status_code=error.code) from error
        except urllib.error.URLError as error:
            raise AppStoreConnectHTTPError(f"Network error while downloading analytics report: {error.reason}") from error


def find_active_ongoing_report_request(requests: list[dict]) -> dict | None:
    for item in requests:
        attributes = item.get("attributes") or {}
        if attributes.get("accessType") == "ONGOING" and not attributes.get("stoppedDueToInactivity", False):
            return item
    return None


def credentials_from_settings(settings) -> AppStoreConnectCredentials:
    return AppStoreConnectCredentials(
        issuer_id=settings.app_store_issuer_id,
        key_id=settings.app_store_key_id,
        private_key_path=settings.app_store_private_key_path,
        vendor_number=settings.app_store_vendor_number or None,
    )


def app_record_from_api(item: dict) -> dict:
    attributes = item.get("attributes") or {}
    return {
        "app_store_id": str(item.get("id") or ""),
        "bundle_id": attributes.get("bundleId") or "",
        "sku": attributes.get("sku") or None,
        "name": attributes.get("name") or "(unnamed)",
        "primary_locale": attributes.get("primaryLocale") or None,
        "source": "app_store_connect",
    }


def _find_report(reports: list[dict], name_fragment: str) -> dict | None:
    candidates = []
    for report in reports:
        attributes = report.get("attributes") or {}
        name = attributes.get("name") or ""
        if name_fragment.lower() in name.lower():
            candidates.append(report)
    if not candidates:
        return None
    candidates.sort(key=lambda item: ("detailed" in ((item.get("attributes") or {}).get("name") or "").lower(),))
    return candidates[0]


def _find_downloads_report(reports: list[dict]) -> dict | None:
    return _find_report(reports, "App Store Downloads") or _find_report(reports, "App Downloads")


def _segment_download_url(segment: dict) -> str | None:
    attributes = segment.get("attributes") or {}
    return (
        attributes.get("url")
        or attributes.get("downloadUrl")
        or attributes.get("downloadURL")
    )


def _report_instance_date(instance: dict) -> str:
    attributes = instance.get("attributes") or {}
    return str(
        attributes.get("processingDate")
        or attributes.get("date")
        or attributes.get("reportDate")
        or ""
    )


def _report_instance_granularity(instance: dict) -> str:
    attributes = instance.get("attributes") or {}
    return str(attributes.get("granularity") or "").upper()


def _parse_tsv_gz(content: bytes) -> list[dict]:
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    return [dict(row) for row in reader]


def _merge_engagement_row(aggregate: dict[tuple[str, str], dict], row: dict, fallback_date: str) -> None:
    event = _get_field(row, "Event").strip().lower()
    count = _int_field(row, "Counts")
    if not count:
        return
    metric_date = _get_field(row, "Date") or fallback_date
    source_type = _normalize_source_type(_get_field(row, "Source Type"))
    metrics = _metric_bucket(aggregate, metric_date, source_type)
    if event == "impression":
        metrics["impressions"] += count
    elif event == "page view":
        metrics["product_page_views"] += count


def _merge_download_row(aggregate: dict[tuple[str, str], dict], row: dict, fallback_date: str) -> None:
    count, _field_name = _download_count_from_row(row)
    if not count:
        return
    metric_date = _get_field(row, "Date") or fallback_date
    source_type = _normalize_source_type(_get_field(row, "Source Type"))
    metrics = _metric_bucket(aggregate, metric_date, source_type)
    metrics["downloads"] += count


def _download_count_from_row(row: dict) -> tuple[int, str]:
    for field_name in FIRST_TIME_DOWNLOAD_FIELDS:
        matched_field = _matching_field_name(row, field_name)
        if matched_field:
            return _int_field(row, field_name), matched_field

    download_type = _get_field(row, "Download Type")
    if download_type:
        if _normalize_header(download_type) in FIRST_TIME_DOWNLOAD_TYPES:
            if _has_field(row, "Counts"):
                return _int_field(row, "Counts"), f"Counts where Download Type={download_type}"
            count = _int_field(row, "Downloads")
            field_name = "Downloads"
            return count, f"{field_name} where Download Type={download_type}"
        return 0, f"ignored Download Type={download_type}"

    for field_name in TOTAL_DOWNLOAD_FIELDS:
        matched_field = _matching_field_name(row, field_name)
        if matched_field:
            return _int_field(row, field_name), matched_field

    return 0, "none"


def _merge_session_row(aggregate: dict[tuple[str, str], dict], row: dict, fallback_date: str) -> None:
    sessions = _int_field(row, "Sessions")
    active_devices = _int_field(row, "Unique Devices")
    total_session_duration = _int_field(row, "Total Session Duration")
    if not sessions and not active_devices and not total_session_duration:
        return
    metric_date = _get_field(row, "Date") or fallback_date
    source_type = _normalize_source_type(_get_field(row, "Source Type"))
    metrics = _usage_bucket(aggregate, metric_date, source_type)
    metrics["sessions"] += sessions
    metrics["active_devices"] += active_devices
    metrics["total_session_duration"] += total_session_duration


def _metric_bucket(aggregate: dict[tuple[str, str], dict], metric_date: str, source_type: str) -> dict:
    return aggregate.setdefault((metric_date, source_type), {
        "impressions": 0,
        "product_page_views": 0,
        "downloads": 0,
    })


def _usage_bucket(aggregate: dict[tuple[str, str], dict], metric_date: str, source_type: str) -> dict:
    return aggregate.setdefault((metric_date, source_type), {
        "active_devices": 0,
        "sessions": 0,
        "total_session_duration": 0,
    })


def _get_field(row: dict, name: str) -> str:
    for key, value in row.items():
        if _normalize_header(key) == _normalize_header(name):
            return str(value or "").strip()
    return ""


def _has_field(row: dict, name: str) -> bool:
    return _matching_field_name(row, name) is not None


def _matching_field_name(row: dict, name: str) -> str | None:
    normalized_name = _normalize_header(name)
    for key in row:
        if _normalize_header(key) == normalized_name:
            return str(key)
    return None


def _int_field(row: dict, name: str) -> int:
    raw = _get_field(row, name).replace(",", "")
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _normalize_header(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _normalize_source_type(value: str) -> str:
    value = (value or "Unavailable").strip()
    mapping = {
        "app store search": "App Store Search",
        "app store browse": "App Store Browse",
        "app referrer": "App Referrer",
        "web referrer": "Web Referrer",
        "app clip": "App Clip",
        "notification": "Notification",
        "unavailable": "Unavailable",
        "institutional purchase": "Institutional Purchase",
    }
    return mapping.get(value.lower(), value)


def _base64url_json(value: dict) -> str:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _base64url(encoded)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _sign_es256_with_openssl(signing_input: bytes, private_key_path: Path) -> bytes:
    openssl_path = _resolve_openssl_path()
    input_file = tempfile.NamedTemporaryFile(delete=False)
    input_path = Path(input_file.name)
    try:
        input_file.write(signing_input)
        input_file.close()
        try:
            completed = subprocess.run(
                [
                    openssl_path,
                    "dgst",
                    "-sha256",
                    "-sign",
                    str(private_key_path),
                    str(input_path),
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as error:
            stderr = error.stderr.decode("utf-8", errors="replace").strip()
            detail = f": {stderr}" if stderr else ""
            raise AppStoreConnectConfigError(f"Failed to sign JWT with the private key{detail}") from error
    finally:
        input_file.close()
        try:
            input_path.unlink()
        except FileNotFoundError:
            pass
    return _der_ecdsa_signature_to_raw(completed.stdout)


def _resolve_openssl_path() -> str:
    configured = os.getenv(OPENSSL_ENV_VAR, "").strip().strip('"').strip("'")
    if configured:
        resolved = _resolve_configured_openssl_path(configured)
        if resolved:
            return resolved
        raise AppStoreConnectConfigError(
            f"{OPENSSL_ENV_VAR} is set but openssl was not found there: {configured}. "
            "Set OPENSSL_PATH to a valid openssl.exe path, for example "
            r"C:\Program Files\Git\usr\bin\openssl.exe."
        )

    discovered = shutil.which("openssl")
    if discovered:
        return discovered

    for candidate in OPENSSL_CANDIDATE_PATHS:
        if candidate.exists():
            return str(candidate)

    candidates = ", ".join(str(path) for path in OPENSSL_CANDIDATE_PATHS)
    raise AppStoreConnectConfigError(
        "openssl command not found; cannot generate ES256 JWT. "
        "Install Git for Windows or OpenSSL, or set OPENSSL_PATH in .env. "
        rf"Common Windows path: C:\Program Files\Git\usr\bin\openssl.exe. "
        f"Checked PATH and candidates: {candidates}"
    )


def _resolve_configured_openssl_path(value: str) -> str | None:
    configured_path = Path(value).expanduser()
    paths = []
    if configured_path.is_absolute():
        paths.append(configured_path)
    else:
        paths.append(ROOT_DIR / configured_path)
        paths.append(Path.cwd() / configured_path)

    for path in paths:
        if path.exists():
            return str(path)

    if not configured_path.is_absolute() and not any(separator in value for separator in ("/", "\\")):
        discovered = shutil.which(value)
        if discovered:
            return discovered

    return None


def _der_ecdsa_signature_to_raw(der_signature: bytes) -> bytes:
    try:
        offset = 0
        if der_signature[offset] != 0x30:
            raise ValueError("expected SEQUENCE")
        offset += 1
        sequence_length, offset = _read_der_length(der_signature, offset)
        sequence_end = offset + sequence_length
        r, offset = _read_der_integer(der_signature, offset)
        s, offset = _read_der_integer(der_signature, offset)
        if offset != sequence_end:
            raise ValueError("unexpected trailing data")
    except (IndexError, ValueError) as error:
        raise AppStoreConnectConfigError("Failed to parse ES256 signature from openssl.") from error

    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def _read_der_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    byte_count = first & 0x7F
    if byte_count == 0 or byte_count > 2:
        raise ValueError("unsupported DER length")
    length = int.from_bytes(data[offset:offset + byte_count], "big")
    return length, offset + byte_count


def _read_der_integer(data: bytes, offset: int) -> tuple[int, int]:
    if data[offset] != 0x02:
        raise ValueError("expected INTEGER")
    offset += 1
    length, offset = _read_der_length(data, offset)
    value = int.from_bytes(data[offset:offset + length], "big")
    return value, offset + length


def _format_http_error(error: urllib.error.HTTPError) -> str:
    body = error.read().decode("utf-8", errors="replace")
    reason = ""
    try:
        payload = json.loads(body)
        errors = payload.get("errors") or []
        if errors:
            first = errors[0]
            title = first.get("title", "")
            detail = first.get("detail", "")
            reason = " ".join(part for part in [title, detail] if part)
    except json.JSONDecodeError:
        reason = body.strip()

    if error.code == 401:
        prefix = "Unauthorized (401). Check ASC_ISSUER_ID, ASC_KEY_ID, and the .p8 private key."
    elif error.code == 403:
        prefix = "Forbidden (403). Check App Store Connect API key roles and app access."
    else:
        prefix = f"App Store Connect API returned HTTP {error.code}."
    return f"{prefix} {reason}".strip()
