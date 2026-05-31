from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ReportResult:
    report_date: str
    markdown: str
    output_path: Path | None = None


def generate_daily_report(conn: sqlite3.Connection, report_date: str, app_source: str | None = None) -> ReportResult:
    current = fetch_aggregate(conn, report_date, app_source=app_source)
    if not current:
        markdown = f"# App Store Daily Report - {report_date}\n\nNo metrics found for this date.\n"
        return ReportResult(report_date=report_date, markdown=markdown)

    previous_date = _previous_metric_date(conn, report_date)
    previous = fetch_aggregate(conn, previous_date, app_source=app_source) if previous_date else {}
    source_rows = fetch_source_breakdown(conn, report_date, app_source=app_source)
    usage_rows = fetch_usage_breakdown(conn, report_date, app_source=app_source)
    top_cvr = _top_cvr(current)
    improvement_candidates = _improvement_candidates(current)

    lines = [
        f"# App Store Daily Report - {report_date}",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        _summary_highlights(current, source_rows),
        "",
        _low_volume_note(current, top_cvr, improvement_candidates),
        "",
        _summary_table(current, previous),
        "",
        "## Search Winners",
        "",
        _search_winners(source_rows, current),
        "",
        "## Emerging Apps",
        "",
        _emerging_apps(current, previous),
        "",
        "## Search Exposure, No Downloads",
        "",
        _search_exposure_no_downloads(source_rows, current),
        "",
        "## Low Volume Summary",
        "",
        _low_volume_summary(current, source_rows),
        "",
        "## App Usage Top",
        "",
        _usage_top_tables(usage_rows),
        "",
        "## CVR Top",
        "",
        _ranking_table(top_cvr),
        "",
        "## CVR Drop",
        "",
        _change_table(_cvr_drop(current, previous), "cvr_delta_pct"),
        "",
        "## Download Growth",
        "",
        _change_table(_download_growth(current, previous), "downloads_delta"),
        "",
        "## Improvement Candidates",
        "",
        _improvement_table(improvement_candidates),
        "",
        "## Source Type Breakdown",
        "",
        _source_table(source_rows),
        "",
    ]
    return ReportResult(report_date=report_date, markdown="\n".join(lines))


def write_report(result: ReportResult, report_dir: Path) -> ReportResult:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"daily_{result.report_date}.md"
    path.write_text(result.markdown, encoding="utf-8")
    return ReportResult(report_date=result.report_date, markdown=result.markdown, output_path=path)


def calculate_page_cvr(downloads: int, product_page_views: int) -> float:
    if product_page_views <= 0:
        return 0.0
    return downloads / product_page_views


def find_improvement_candidates(current: dict, limit: int = 5) -> list[dict]:
    rows = []
    for item in current.values():
        if item["product_page_views"] < 40:
            continue
        score = item["product_page_views"] * max(0.0, 0.10 - item["conversion_rate"])
        if score <= 0:
            continue
        rows.append({**item, "improvement_score": score})
    return sorted(rows, key=lambda row: row["improvement_score"], reverse=True)[:limit]


def fetch_aggregate(conn: sqlite3.Connection, metric_date: str | None, app_source: str | None = None) -> dict[str, dict]:
    if not metric_date:
        return {}
    source_filter = "AND a.source = ?" if app_source else ""
    params = (metric_date, app_source) if app_source else (metric_date,)
    rows = conn.execute(
        f"""
        SELECT
          a.name,
          a.sku,
          a.bundle_id,
          a.source,
          SUM(m.impressions) AS impressions,
          SUM(m.product_page_views) AS product_page_views,
          SUM(m.downloads) AS downloads
        FROM daily_metrics m
        JOIN apps a ON a.id = m.app_id
        WHERE m.metric_date = ?
        {source_filter}
        GROUP BY a.id
        ORDER BY downloads DESC, product_page_views DESC
        """,
        params,
    ).fetchall()
    result = {}
    for row in rows:
        views = int(row["product_page_views"] or 0)
        downloads = int(row["downloads"] or 0)
        cvr = calculate_page_cvr(downloads, views)
        result[row["sku"]] = {
            "name": row["name"],
            "sku": row["sku"],
            "bundle_id": row["bundle_id"],
            "source": row["source"],
            "impressions": int(row["impressions"] or 0),
            "product_page_views": views,
            "downloads": downloads,
            "conversion_rate": cvr,
        }
    return result


def fetch_source_breakdown(conn: sqlite3.Connection, metric_date: str, app_source: str | None = None) -> list[sqlite3.Row]:
    source_filter = "AND a.source = ?" if app_source else ""
    params = (metric_date, app_source) if app_source else (metric_date,)
    return conn.execute(
        f"""
        SELECT
          a.name,
          a.sku,
          a.source,
          m.source_type,
          m.impressions,
          m.product_page_views,
          m.downloads,
          m.conversion_rate
        FROM daily_metrics m
        JOIN apps a ON a.id = m.app_id
        WHERE m.metric_date = ?
        {source_filter}
        ORDER BY a.name, m.downloads DESC
        """,
        params,
    ).fetchall()


def fetch_usage_breakdown(conn: sqlite3.Connection, metric_date: str, app_source: str | None = None) -> list[sqlite3.Row]:
    source_filter = "AND a.source = ?" if app_source else ""
    params = (metric_date, app_source) if app_source else (metric_date,)
    return conn.execute(
        f"""
        SELECT
          a.name,
          a.sku,
          a.source,
          u.source_type,
          u.active_devices,
          u.sessions,
          u.total_session_duration
        FROM app_usage_metrics u
        JOIN apps a ON a.id = u.app_id
        WHERE u.metric_date = ?
        {source_filter}
        ORDER BY a.name, u.sessions DESC
        """,
        params,
    ).fetchall()


def _previous_metric_date(conn: sqlite3.Connection, report_date: str) -> str | None:
    row = conn.execute(
        "SELECT MAX(metric_date) AS metric_date FROM daily_metrics WHERE metric_date < ?",
        (report_date,),
    ).fetchone()
    return row["metric_date"] if row and row["metric_date"] else None


def _summary_table(current: dict, previous: dict) -> str:
    headers = "| App | Impressions | Product Page Views | Downloads | CVR | DL vs prev | CVR vs prev |"
    sep = "|---|---:|---:|---:|---:|---:|---:|"
    lines = [headers, sep]
    for item in sorted(current.values(), key=lambda row: row["downloads"], reverse=True):
        prev = previous.get(item["sku"], {})
        dl_delta = item["downloads"] - int(prev.get("downloads", 0)) if prev else 0
        cvr_delta = item["conversion_rate"] - float(prev.get("conversion_rate", 0.0)) if prev else 0.0
        lines.append(
            f"| {item['name']} | {item['impressions']:,} | {item['product_page_views']:,} | "
            f"{item['downloads']:,} | {_pct(item['conversion_rate'])} | {dl_delta:+,} | {_pct_delta(cvr_delta)} |"
        )
    return "\n".join(lines)


def _summary_highlights(current: dict, source_rows: list[sqlite3.Row]) -> str:
    app_count = len(current)
    apps_with_downloads = sum(1 for row in current.values() if int(row["downloads"]) > 0)
    total_downloads = sum(int(row["downloads"]) for row in current.values())
    best_ctr = _best_ctr_app(current)
    highest_impressions = _highest_impressions_app(current)
    lines = [
        f"- Apps with downloads: {apps_with_downloads} / {app_count}",
        f"- Total downloads: {total_downloads:,}",
        f"- Best CTR app: {_summary_app_metric(best_ctr, 'conversion_rate')}",
        f"- Highest impressions app: {_summary_app_metric(highest_impressions, 'impressions')}",
    ]
    search_totals = _search_totals(source_rows)
    if search_totals["impressions"] > 0:
        lines.append(
            f"- Search CTR total: {_ctr(search_totals['page_views'], search_totals['impressions'])} "
            f"({search_totals['page_views']:,} / {search_totals['impressions']:,})"
        )
    return "\n".join(lines)


def _best_ctr_app(current: dict) -> dict | None:
    rows = [row for row in current.values() if int(row["product_page_views"]) > 0]
    if not rows:
        return None
    return sorted(rows, key=lambda row: (float(row["conversion_rate"]), int(row["downloads"])), reverse=True)[0]


def _highest_impressions_app(current: dict) -> dict | None:
    rows = [row for row in current.values() if int(row["impressions"]) > 0]
    if not rows:
        return None
    return sorted(rows, key=lambda row: int(row["impressions"]), reverse=True)[0]


def _summary_app_metric(row: dict | None, metric_key: str) -> str:
    if not row:
        return "None"
    if metric_key == "conversion_rate":
        return f"{row['name']} ({_pct(row['conversion_rate'])})"
    return f"{row['name']} ({int(row[metric_key]):,})"


def _search_totals(source_rows: list[sqlite3.Row]) -> dict[str, int]:
    rows = [row for row in source_rows if str(row["source_type"]).lower() == "app store search"]
    return {
        "impressions": sum(int(row["impressions"] or 0) for row in rows),
        "page_views": sum(int(row["product_page_views"] or 0) for row in rows),
    }


def _low_volume_note(current: dict, top_cvr: list[dict], improvement_candidates: list[dict]) -> str:
    max_views = max((int(row["product_page_views"]) for row in current.values()), default=0)
    if top_cvr or improvement_candidates:
        return "Low volume note: CVR and improvement rankings use minimum page-view thresholds to avoid over-reading small samples."
    return (
        "Low volume note: CVR Top requires at least 20 page views and Improvement Candidates requires at least "
        f"40 page views. Current max page views is {max_views}, so No candidates means insufficient sample size, "
        "not necessarily missing or failed parsing."
    )


def _low_volume_summary(current: dict, source_rows: list[sqlite3.Row]) -> str:
    app_count = len(current)
    zero_download_count = sum(1 for row in current.values() if int(row["downloads"]) == 0)
    lines = [
        f"- Apps with zero downloads: {zero_download_count} / {app_count}",
        "",
        "### Impressions Top",
        "",
        _metric_top_table(current.values(), "impressions", "Impressions", "No apps with impressions yet."),
        "",
        "### Page Views Top",
        "",
        _metric_top_table(current.values(), "product_page_views", "Page Views", "No page views yet."),
        "",
        "### Search Impressions Top",
        "",
        _search_impressions_table(source_rows),
        "",
        "### Search CTR",
        "",
        _search_ctr_table(source_rows),
    ]
    return "\n".join(lines)


def _metric_top_table(rows, metric_key: str, metric_label: str, empty_message: str, limit: int = 3) -> str:
    ranked = sorted(
        (row for row in rows if int(row[metric_key]) > 0),
        key=lambda row: int(row[metric_key]),
        reverse=True,
    )[:limit]
    if not ranked:
        return empty_message
    lines = [f"| Rank | App | {metric_label} |", "|---:|---|---:|"]
    for index, row in enumerate(ranked, start=1):
        lines.append(f"| {index} | {row['name']} | {int(row[metric_key]):,} |")
    return "\n".join(lines)


def _search_impressions_table(source_rows: list[sqlite3.Row], limit: int = 3) -> str:
    rows = [
        row for row in source_rows
        if str(row["source_type"]).lower() == "app store search" and int(row["impressions"] or 0) > 0
    ]
    rows = sorted(rows, key=lambda row: int(row["impressions"] or 0), reverse=True)[:limit]
    if not rows:
        return "No apps with impressions yet."
    lines = ["| Rank | App | Search Impressions | Page Views | Downloads |", "|---:|---|---:|---:|---:|"]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"| {index} | {row['name']} | {int(row['impressions'] or 0):,} | "
            f"{int(row['product_page_views'] or 0):,} | {int(row['downloads'] or 0):,} |"
        )
    return "\n".join(lines)


def _search_ctr_table(source_rows: list[sqlite3.Row], limit: int = 5) -> str:
    rows = [
        row for row in source_rows
        if str(row["source_type"]).lower() == "app store search" and int(row["impressions"] or 0) > 0
    ]
    rows = sorted(rows, key=lambda row: int(row["impressions"] or 0), reverse=True)[:limit]
    if not rows:
        return "No apps with search impressions yet."

    total_impressions = sum(
        int(row["impressions"] or 0)
        for row in source_rows
        if str(row["source_type"]).lower() == "app store search"
    )
    total_page_views = sum(
        int(row["product_page_views"] or 0)
        for row in source_rows
        if str(row["source_type"]).lower() == "app store search"
    )
    lines = ["| App | Search Impressions | Search Page Views | Search CTR |", "|---|---:|---:|---:|"]
    lines.append(f"| Total | {total_impressions:,} | {total_page_views:,} | {_ctr(total_page_views, total_impressions)} |")
    for row in rows:
        impressions = int(row["impressions"] or 0)
        page_views = int(row["product_page_views"] or 0)
        lines.append(f"| {row['name']} | {impressions:,} | {page_views:,} | {_ctr(page_views, impressions)} |")
    return "\n".join(lines)


def _search_winners(source_rows: list[sqlite3.Row], current: dict, limit: int = 5) -> str:
    rows = [
        row for row in _search_app_metrics(source_rows, current)
        if row["impressions"] > 0 and row["downloads"] > 0
    ]
    rows = sorted(rows, key=lambda row: (row["downloads"], row["ctr"], row["impressions"]), reverse=True)[:limit]
    if not rows:
        return "No search winners yet."
    lines = []
    for row in rows:
        lines.append(
            f"- {row['name']} - impressions: {row['impressions']:,}, "
            f"page views: {row['page_views']:,}, CTR: {_ctr(row['page_views'], row['impressions'])}, "
            f"downloads: {row['downloads']:,}"
        )
    return "\n".join(lines)


def _search_app_metrics(source_rows: list[sqlite3.Row], current: dict) -> list[dict]:
    app_rows: dict[str, dict] = {}
    for row in source_rows:
        if str(row["source_type"]).lower() != "app store search":
            continue
        item = app_rows.setdefault(row["sku"], {
            "sku": row["sku"],
            "name": row["name"],
            "impressions": 0,
            "page_views": 0,
            "downloads": int((current.get(row["sku"]) or {}).get("downloads", 0)),
        })
        item["impressions"] += int(row["impressions"] or 0)
        item["page_views"] += int(row["product_page_views"] or 0)
    for item in app_rows.values():
        item["ctr"] = item["page_views"] / item["impressions"] if item["impressions"] > 0 else 0.0
    return list(app_rows.values())


def _emerging_apps(current: dict, previous: dict, limit: int = 5) -> str:
    rows = []
    for sku, item in current.items():
        prev = previous.get(sku, {})
        impressions_delta = int(item["impressions"]) - int(prev.get("impressions", 0))
        page_views_delta = int(item["product_page_views"]) - int(prev.get("product_page_views", 0))
        downloads_delta = int(item["downloads"]) - int(prev.get("downloads", 0))
        if impressions_delta <= 0 and page_views_delta <= 0 and downloads_delta <= 0 and int(item["downloads"]) <= 0:
            continue
        rows.append({
            **item,
            "impressions_delta": impressions_delta,
            "page_views_delta": page_views_delta,
            "downloads_delta": downloads_delta,
        })
    rows = sorted(
        rows,
        key=lambda row: (
            int(row["downloads"]),
            int(row["downloads_delta"]),
            int(row["impressions_delta"]),
            int(row["page_views_delta"]),
        ),
        reverse=True,
    )[:limit]
    if not rows:
        return "No emerging apps."
    lines = ["| App | Impressions Delta | Page Views Delta | Downloads | DL Delta |", "|---|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(
            f"| {row['name']} | {int(row['impressions_delta']):+,} | "
            f"{int(row['page_views_delta']):+,} | {int(row['downloads']):,} | "
            f"{int(row['downloads_delta']):+,} |"
        )
    return "\n".join(lines)


def _search_exposure_no_downloads(source_rows: list[sqlite3.Row], current: dict, limit: int = 5) -> str:
    rows = [
        row for row in source_rows
        if (
            str(row["source_type"]).lower() == "app store search"
            and int(row["impressions"] or 0) > 0
            and int((current.get(row["sku"]) or {}).get("downloads", 0)) == 0
        )
    ]
    rows = sorted(rows, key=lambda row: int(row["impressions"] or 0), reverse=True)[:limit]
    if not rows:
        return "No candidates."
    return "\n".join(_format_search_no_download_row(row, current) for row in rows)


def _format_search_no_download_row(row: sqlite3.Row, current: dict) -> str:
    impressions = int(row["impressions"] or 0)
    page_views = int(row["product_page_views"] or 0)
    return (
        f"- {row['name']} - search impressions: {impressions:,}, "
        f"page views: {page_views:,}, CTR: {_ctr(page_views, impressions)}, "
        f"app downloads: {int((current.get(row['sku']) or {}).get('downloads', 0)):,}"
    )


def _top_cvr(current: dict) -> list[dict]:
    rows = [row for row in current.values() if row["product_page_views"] >= 20]
    return sorted(rows, key=lambda row: (row["conversion_rate"], row["downloads"]), reverse=True)[:5]


def _cvr_drop(current: dict, previous: dict) -> list[dict]:
    rows = []
    for sku, item in current.items():
        prev = previous.get(sku)
        if not prev:
            continue
        cvr_delta = item["conversion_rate"] - prev["conversion_rate"]
        rows.append({**item, "cvr_delta_pct": cvr_delta * 100})
    return sorted(rows, key=lambda row: row["cvr_delta_pct"])[:5]


def _download_growth(current: dict, previous: dict) -> list[dict]:
    rows = []
    for sku, item in current.items():
        prev = previous.get(sku)
        if not prev:
            continue
        rows.append({**item, "downloads_delta": item["downloads"] - prev["downloads"]})
    return sorted(rows, key=lambda row: row["downloads_delta"], reverse=True)[:5]


def _improvement_candidates(current: dict) -> list[dict]:
    return find_improvement_candidates(current)


def _usage_top_tables(rows: list[sqlite3.Row], limit: int = 5) -> str:
    if not rows:
        return "No app usage data."
    app_totals = {}
    for row in rows:
        item = app_totals.setdefault(row["sku"], {
            "name": row["name"],
            "active_devices": 0,
            "sessions": 0,
            "total_session_duration": 0,
        })
        item["active_devices"] += int(row["active_devices"] or 0)
        item["sessions"] += int(row["sessions"] or 0)
        item["total_session_duration"] += int(row["total_session_duration"] or 0)

    active_rows = sorted(app_totals.values(), key=lambda row: row["active_devices"], reverse=True)[:limit]
    session_rows = sorted(app_totals.values(), key=lambda row: row["sessions"], reverse=True)[:limit]
    lines = [
        "### Active Devices Top",
        "",
        _usage_metric_table(active_rows, "active_devices", "Active Devices"),
        "",
        "### Sessions Top",
        "",
        _usage_metric_table(session_rows, "sessions", "Sessions"),
    ]
    return "\n".join(lines)


def _usage_metric_table(rows: list[dict], metric_key: str, metric_label: str) -> str:
    ranked = [row for row in rows if int(row[metric_key]) > 0]
    if not ranked:
        return "No app usage data."
    if metric_key == "sessions":
        lines = [f"| Rank | App | {metric_label} | Active Devices |", "|---:|---|---:|---:|"]
        for index, row in enumerate(ranked, start=1):
            lines.append(
                f"| {index} | {row['name']} | {int(row['sessions']):,} | "
                f"{int(row['active_devices']):,} |"
            )
        return "\n".join(lines)

    lines = [f"| Rank | App | {metric_label} | Sessions |", "|---:|---|---:|---:|"]
    for index, row in enumerate(ranked, start=1):
        lines.append(
            f"| {index} | {row['name']} | {int(row[metric_key]):,} | "
            f"{int(row['sessions']):,} |"
        )
    return "\n".join(lines)


def _ranking_table(rows: list[dict]) -> str:
    if not rows:
        return "No candidates."
    lines = ["| Rank | App | Downloads | Product Page Views | CVR |", "|---:|---|---:|---:|---:|"]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"| {index} | {row['name']} | {row['downloads']:,} | "
            f"{row['product_page_views']:,} | {_pct(row['conversion_rate'])} |"
        )
    return "\n".join(lines)


def _change_table(rows: list[dict], delta_key: str) -> str:
    if not rows:
        return "No comparison data."
    delta_label = "CVR Delta" if delta_key == "cvr_delta_pct" else "DL Delta"
    lines = [f"| App | Downloads | CVR | {delta_label} |", "|---|---:|---:|---:|"]
    for row in rows:
        delta = f"{row[delta_key]:+.2f}pt" if delta_key == "cvr_delta_pct" else f"{row[delta_key]:+,}"
        lines.append(f"| {row['name']} | {row['downloads']:,} | {_pct(row['conversion_rate'])} | {delta} |")
    return "\n".join(lines)


def _improvement_table(rows: list[dict]) -> str:
    if not rows:
        return "No candidates."
    lines = ["| App | Issue | Views | Downloads | CVR |", "|---|---|---:|---:|---:|"]
    for row in rows:
        issue = "Traffic exists, conversion is below 10%"
        lines.append(
            f"| {row['name']} | {issue} | {row['product_page_views']:,} | "
            f"{row['downloads']:,} | {_pct(row['conversion_rate'])} |"
        )
    return "\n".join(lines)


def _source_table(rows: list[sqlite3.Row]) -> str:
    if not rows:
        return "No source data."
    lines = ["| App | Source Type | Impressions | Views | Downloads | CVR |", "|---|---|---:|---:|---:|---:|"]
    search_impressions = sum(
        int(row["impressions"] or 0)
        for row in rows
        if str(row["source_type"]).lower() == "app store search"
    )
    browse_impressions = sum(
        int(row["impressions"] or 0)
        for row in rows
        if str(row["source_type"]).lower() == "app store browse"
    )
    total_page_views = sum(int(row["product_page_views"] or 0) for row in rows)
    lines.extend([
        f"| Search impressions total | Total | {search_impressions:,} |  |  |  |",
        f"| Browse impressions total | Total | {browse_impressions:,} |  |  |  |",
        f"| Total page views | Total |  | {total_page_views:,} |  |  |",
    ])
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['source_type']} | {row['impressions']:,} | "
            f"{row['product_page_views']:,} | {row['downloads']:,} | {_pct(row['conversion_rate'])} |"
        )
    return "\n".join(lines)


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _pct_delta(value: float) -> str:
    return f"{value * 100:+.2f}pt"


def _ctr(page_views: int, impressions: int) -> str:
    if impressions <= 0:
        return "0.0%"
    return f"{(page_views / impressions) * 100:.1f}%"
