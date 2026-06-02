# Sample Daily Report

This is a mock-mode sample. It does not contain real App Store Connect data, real app identifiers, private credentials, or production KPI history.

Use this page to understand the report structure before you connect App Store Connect credentials. Every app name, app identifier, and KPI value below is mock data only.

```text
# App Store Daily Report - 2026-05-31

Generated: 2026-06-01 00:00:00

## Summary

- Apps with downloads: 5 / 5
- Total downloads: 193
- Best CTR app: URL Cleaner (10.33%)
- Highest impressions app: WakeProof (3,216)
- Search CTR total: 21.4% (614 / 2,864)

Low volume note: CVR and improvement rankings use minimum page-view thresholds to avoid over-reading small samples.

| App | Impressions | Product Page Views | Downloads | CVR | DL vs prev | CVR vs prev |
|---|---:|---:|---:|---:|---:|---:|
| URL Cleaner | 2,868 | 687 | 71 | 10.33% | +0 | -0.11pt |
| WakeProof | 3,216 | 820 | 67 | 8.17% | -1 | -0.20pt |
| Big Text Note | 2,507 | 564 | 32 | 5.67% | -2 | -0.45pt |
| PinLog | 1,731 | 338 | 13 | 3.85% | -1 | -0.44pt |
| WaterDone | 2,129 | 446 | 10 | 2.24% | -1 | -0.28pt |

## Search Winners

- URL Cleaner - impressions: 675, page views: 151, CTR: 22.4%, downloads: 71
- WakeProof - impressions: 767, page views: 184, CTR: 24.0%, downloads: 67
- Big Text Note - impressions: 578, page views: 121, CTR: 20.9%, downloads: 32
- PinLog - impressions: 369, page views: 66, CTR: 17.9%, downloads: 13
- WaterDone - impressions: 475, page views: 92, CTR: 19.4%, downloads: 10

## Emerging Apps

| App | Impressions Delta | Page Views Delta | Downloads | DL Delta |
|---|---:|---:|---:|---:|
| URL Cleaner | +33 | +7 | 71 | +0 |
| WakeProof | +28 | +8 | 67 | -1 |
| Big Text Note | +42 | +9 | 32 | -2 |

## Search Exposure, No Downloads

No candidates.

## Improvement Candidates

| App | Issue | Views | Downloads | CVR |
|---|---|---:|---:|---:|
| WaterDone | Traffic exists, conversion is below 10% | 446 | 10 | 2.24% |
| Big Text Note | Traffic exists, conversion is below 10% | 564 | 32 | 5.67% |

## Source Type Breakdown

| App | Source Type | Impressions | Views | Downloads | CVR |
|---|---|---:|---:|---:|---:|
| Search impressions total | Total | 2,864 |  |  |  |
| Browse impressions total | Total | 3,043 |  |  |  |
| Total page views | Total |  | 2,855 |  |  |
| URL Cleaner | App Store Search | 675 | 151 | 17 | 11.56% |
| WakeProof | App Store Browse | 792 | 198 | 16 | 8.26% |
```

To generate a local sample yourself:

```bash
python -m src.cli --db data/sample.sqlite3 daily --mock --print
```

The generated SQLite database and report files are ignored by `.gitignore`.

## How to Read the Sample

### Summary

The summary is the fastest way to scan the day:

- `Apps with downloads` shows how many tracked apps recorded at least one download.
- `Total downloads` gives the portfolio-wide daily download count.
- `Best CTR app` highlights the app with the strongest search click-through rate, which is product page views divided by search impressions.
- `Highest impressions app` shows which app had the most App Store visibility.
- `Search CTR total` rolls up search impressions and search-driven product page views across every mock app.

The low-volume note is a warning label. It reminds you that conversion rates and day-over-day rankings are less reliable when an app has very few product page views.

### App Performance Table

This table is the per-app daily scoreboard:

- `Impressions` means the app appeared in App Store surfaces such as search or browse.
- `Product Page Views` counts visits to the app’s App Store product page.
- `Downloads` is the number of first-time downloads recorded for the day.
- `CVR` means conversion rate, calculated as downloads divided by product page views.
- `DL vs prev` and `CVR vs prev` compare the latest day against the previous stored day so you can spot movement quickly.

### Search Winners

This section isolates search performance. It helps answer which apps turned App Store Search visibility into product page visits and downloads most effectively on the latest day.

### Emerging Apps

This section calls out apps with growing attention. The impression and page-view deltas show which apps are gaining visibility, while `DL Delta` shows whether that extra attention is also becoming downloads.

### Search Exposure, No Downloads

This section is reserved for apps that earned search visibility but did not convert into downloads. In the sample above there are no candidates, which is why the section reports `No candidates.`

### Improvement Candidates

This section highlights apps with enough traffic to review but weaker conversion performance. It is intended as a prioritization list for store listing, screenshots, copy, or onboarding investigations rather than as proof of a product problem by itself.

### Source Type Breakdown

This section separates totals and app rows by traffic source so you can see where visibility and conversion are coming from:

- `Search impressions total` aggregates App Store Search visibility across all apps.
- `Browse impressions total` aggregates non-search App Store discovery such as browsing or featured surfaces.
- Per-app rows break out one source type at a time so you can compare how the same app performs in search versus browse contexts.

## Safe Sharing Notes

- Keep examples and screenshots limited to mock mode output when contributing docs.
- Do not commit `.env` files, `.p8` keys, Discord webhook URLs, SQLite databases, generated local reports, or logs.
- If you need to explain a setup step publicly, use placeholders instead of real app IDs, bundle IDs, or credentials.
