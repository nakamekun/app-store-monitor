# app-store-monitor

A small, dependency-light CLI for independent iOS developers who want a daily App Store Connect KPI report without a dashboard subscription.

`app-store-monitor` collects App Store Connect app metadata and Analytics Reports data, stores normalized daily metrics in SQLite, renders Markdown reports, and can send the report to Discord. It also ships with deterministic mock data so contributors can run the full reporting flow without Apple credentials.

## Features

- App Store Connect API authentication with ES256 JWT signing.
- App inventory sync from `/v1/apps`.
- Analytics Reports support for daily App Store discovery, engagement, downloads, and sessions data.
- SQLite storage for app metadata, daily acquisition metrics, usage metrics, and report runs.
- Markdown daily KPI reports for small app portfolios.
- Discord webhook notifications with a once-per-metric-date guard.
- Mock mode for local development, demos, and tests.
- macOS launchd and Windows Task Scheduler examples.

## Repository Layout

```text
app-store-monitor/
  README.md
  LICENSE
  CONTRIBUTING.md
  AGENTS.md
  .env.example
  config/
    apps.example.json
    launchd/
    windows/
  data/
    .gitkeep
  docs/
  reports/
    .gitkeep
  scripts/
  sql/
  src/
  tests/
```

Runtime files such as `.env`, `.p8` keys, SQLite databases, logs, and generated reports are intentionally ignored.

## Requirements

- Python 3.11 or newer.
- OpenSSL for real App Store Connect JWT signing.
- No third-party Python packages are required for the current CLI and test suite.

On Windows, Git for Windows usually provides `openssl.exe`. You can also set `OPENSSL_PATH` in `.env`.

## Quick Start With Mock Data

```bash
cd app-store-monitor
cp .env.example .env
python -m src.cli init-db
python -m src.cli daily --mock --print
```

Or use Make:

```bash
make daily-mock
```

The mock flow initializes SQLite, inserts deterministic sample metrics, writes a Markdown report under `reports/`, and prints it to stdout.

## Configuration

Copy `.env.example` to `.env` and edit only local values:

```env
APP_STORE_MONITOR_MODE=mock
APP_STORE_MONITOR_DB_PATH=./data/app_store_monitor.sqlite3
APP_STORE_MONITOR_REPORT_DIR=./reports
APP_STORE_MONITOR_TIMEZONE=UTC

ASC_ISSUER_ID=
ASC_KEY_ID=
ASC_PRIVATE_KEY_PATH=./private_keys/app_store_connect_api_key.p8
OPENSSL_PATH=

DISCORD_ENABLED=false
DISCORD_WEBHOOK_URL=
```

Never commit `.env`, `.env.local`, `private_keys/`, `*.p8`, Discord webhook URLs, App Store Connect credentials, logs, generated reports, or real SQLite data.

## Real App Store Connect Setup

1. Create an App Store Connect API key with access to Analytics Reports.
2. Download the `.p8` private key once and store it locally, for example:

```text
private_keys/app_store_connect_api_key.p8
```

3. Set these values in `.env`:

```env
APP_STORE_MONITOR_MODE=real
ASC_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ASC_KEY_ID=<key-id>
ASC_PRIVATE_KEY_PATH=./private_keys/app_store_connect_api_key.p8
```

4. Validate local configuration:

```bash
python -m src.cli check-config
python -m src.cli check-connection --real
```

5. Sync apps and create ongoing Analytics Reports requests:

```bash
python -m src.cli sync-apps
python -m src.cli create-report-request --all
```

Apple usually needs 24-48 hours before newly created ongoing report segments are available.

## Common Commands

```bash
# Create or migrate SQLite schema
python -m src.cli init-db

# Insert deterministic mock metrics
python -m src.cli seed-mock --days 14

# Generate the latest local report
python -m src.cli report --latest --print

# Run the mock daily flow
python -m src.cli daily --mock --print

# List apps from App Store Connect
python -m src.cli list-apps

# Sync App Store Connect apps into SQLite
python -m src.cli sync-apps

# Create ongoing Analytics Reports requests for all synced apps
python -m src.cli create-report-request --all

# Fetch the latest available daily segments for all synced apps
python -m src.cli fetch --latest --all

# Send a report to Discord
python -m src.cli report --latest --notify --notify-once
```

## Daily Automation

macOS:

```bash
make install-launchd
```

Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\config\windows\register_task.ps1
```

Both runners load `.env`, run config checks, sync apps, ensure ongoing report requests, fetch the latest available daily data, generate a report, and optionally notify Discord.

## Testing

```bash
python -m unittest discover -s tests
```

The test suite uses mocks and temporary files. It does not require real Apple credentials, Discord webhooks, or network access.

## Security Model

This project is designed so the public repository contains source code, documentation, examples, and tests only. Local secrets and runtime data stay outside Git:

- `.env`, `.env.local`, and other local env files.
- App Store Connect `.p8` private keys.
- Discord webhook URLs.
- SQLite databases and write-ahead log files.
- Generated Markdown reports.
- Runtime logs.

See [docs/publication-checklist.md](docs/publication-checklist.md) before publishing a split repository.

## License

MIT. See [LICENSE](LICENSE).
