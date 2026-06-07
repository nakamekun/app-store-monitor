# Sample Daily Report

This is a mock-mode sample. It does not contain real App Store Connect data, real app identifiers, private credentials, or production KPI history.

## How to read the report

- **Summary** gives a quick daily health check: total downloads, the highest-impression mock app, and the strongest search click-through rate.
- **Search Winners** highlights mock apps that attracted search impressions and turned some of that attention into downloads.
- **Emerging Apps** calls out mock apps with improving impressions, page views, or downloads compared with the previous mock day.
- **Search Exposure, No Downloads** is a watch list for mock apps that received search visibility but did not convert it into downloads.
- **Improvement Candidates** points to mock apps with enough page views to review, but lower conversion than the sample threshold.
- **Source Type Breakdown** separates mock App Store Search, Browse, and total page-view activity so readers can see where traffic came from.

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
