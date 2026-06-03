# Sample Daily Report

This is a mock-mode sample. It does not contain real App Store Connect data, real app identifiers, private credentials, or production KPI history.

## How to read this report

The generated daily report is meant to answer one question quickly: "Which apps need attention today?"

### Summary

The `Summary` block is the executive snapshot. It tells you how many apps actually produced downloads, how many total downloads landed that day, which app had the strongest search click-through rate, which app had the broadest top-of-funnel reach, and how search traffic performed across the portfolio as a whole.

The table under `Summary` then moves from portfolio-wide totals to app-by-app context:

- `Impressions`: how often the app was shown in App Store surfaces
- `Product Page Views`: how often users opened the product page
- `Downloads`: installs attributed to the reporting window
- `CVR`: conversion rate from page views to downloads
- `DL vs prev`: day-over-day download change
- `CVR vs prev`: day-over-day conversion-rate change

The low-volume note matters because very small page-view counts can make conversion swings look more dramatic than they really are.

### Search Winners

`Search Winners` highlights the apps currently converting App Store Search traffic best. This is useful when you want quick examples of titles or listings that are already pulling strong qualified traffic.

### Emerging Apps

`Emerging Apps` is the momentum view. It surfaces apps whose impressions and page views are growing so you can spot rising visibility before it fully shows up in download totals.

### Search Exposure, No Downloads

`Search Exposure, No Downloads` calls out apps that are being shown in search results but still are not converting into installs. If this section contains rows, those apps are likely candidates for metadata, screenshots, pricing, or positioning work.

### Improvement Candidates

`Improvement Candidates` is the "something is off" section. It looks for apps that have enough traffic to judge but are still converting below the current threshold. This helps you prioritize where product-page improvements may have the highest near-term payoff.

### Source Type Breakdown

`Source Type Breakdown` explains where visibility and downloads came from. The aggregate rows show total search, browse, and page-view volume; the per-app rows then break out individual source types so you can tell whether an app is relying more on search discovery or browse discovery.

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
