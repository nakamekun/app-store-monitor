# Downloads Definition

`daily_metrics.downloads` is an acquisition metric. It tracks first-time downloads when the App Downloads TSV exposes that distinction.

## Mapping Priority

1. Use an explicit first-time column when present: `First-Time Downloads`, `First Time Downloads`, or `App Units`.
2. If the report is row-based with `Download Type`, use `Counts` only for first-time download rows and ignore redownload rows.
3. Fall back to `Total Downloads`, `Downloads`, or `Counts` only when the TSV does not expose a distinct first-time field or `Download Type`.

## Metric Differences

- `App Units`: closest to first-time app acquisition in older Sales/Trends style reporting.
- `First Time Downloads`: the App Store Connect Analytics downloads metric for first-time downloads.
- `Total Downloads`: first-time downloads plus redownloads. This is useful for total store download activity, but it is not the default report `downloads` definition.

For UI comparison, prefer matching the App Store Connect metric selector to `First Time Downloads` when comparing with this report. If the UI is set to `Total Downloads`, expect the UI to be higher because redownloads are included.

Apple's current metric definitions describe First Time Downloads, Redownloads, and Total Downloads under Downloads metrics:
https://developer.apple.com/help/app-store-connect-analytics/reference/metrics-definitions/

## Debug Command

```bash
python -m src.cli debug-downloads --latest
```

The command prints each app, source type, raw TSV columns, mapped downloads, and the field or row rule used for the mapping.
