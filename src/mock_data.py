from __future__ import annotations

import math
from datetime import date, timedelta

from src.db import connect, upsert_app, upsert_daily_metrics


MOCK_APPS = [
    {"app_store_id": "6740000001", "bundle_id": "com.example.pinlog", "sku": "pinlog-ios", "name": "PinLog", "primary_locale": "en-US", "source": "mock"},
    {"app_store_id": "6740000002", "bundle_id": "com.example.waterdone", "sku": "waterdone-ios", "name": "WaterDone", "primary_locale": "en-US", "source": "mock"},
    {"app_store_id": "6740000003", "bundle_id": "com.example.bigtextnote", "sku": "big-text-note-ios", "name": "Big Text Note", "primary_locale": "en-US", "source": "mock"},
    {"app_store_id": "6740000004", "bundle_id": "com.example.urlcleaner", "sku": "url-cleaner-ios", "name": "URL Cleaner", "primary_locale": "en-US", "source": "mock"},
    {"app_store_id": "6740000005", "bundle_id": "com.example.wakeproof", "sku": "wake-proof-ios", "name": "WakeProof", "primary_locale": "en-US", "source": "mock"},
]

SOURCE_TYPES = ["App Store Search", "App Store Browse", "Web Referrer", "App Referrer"]


def seed_mock_data(db_path, end_date: date, days: int = 14) -> int:
    with connect(db_path) as conn:
        app_ids = {app["sku"]: upsert_app(conn, app) for app in MOCK_APPS}
        rows = []
        for day_index in range(days):
            metric_date = end_date - timedelta(days=days - day_index - 1)
            for app_index, app in enumerate(MOCK_APPS):
                for source_index, source_type in enumerate(SOURCE_TYPES):
                    base = 260 + app_index * 70 + source_index * 35
                    trend = day_index * (8 + app_index * 2)
                    wave = int(math.sin((day_index + app_index + source_index) / 2.0) * 24)
                    impressions = max(40, base + trend + wave)
                    product_page_views = max(8, int(impressions * (0.18 + app_index * 0.015 + source_index * 0.01)))

                    cvr_seed = 0.065 + app_index * 0.008 - source_index * 0.006
                    if app["sku"] == "waterdone-ios" and day_index >= days - 4:
                        cvr_seed -= 0.028
                    if app["sku"] == "url-cleaner-ios" and day_index >= days - 3:
                        cvr_seed += 0.035
                    if app["sku"] == "wake-proof-ios" and source_type == "App Store Search":
                        cvr_seed += 0.025
                    conversion_rate = max(0.005, min(0.22, cvr_seed + math.sin(day_index / 3.0) * 0.009))
                    downloads = max(0, int(product_page_views * conversion_rate))

                    rows.append({
                        "metric_date": metric_date.isoformat(),
                        "app_id": app_ids[app["sku"]],
                        "source_type": source_type,
                        "impressions": impressions,
                        "product_page_views": product_page_views,
                        "downloads": downloads,
                        "conversion_rate": round(conversion_rate, 4),
                    })
        count = upsert_daily_metrics(conn, rows)
        conn.commit()
        return count
