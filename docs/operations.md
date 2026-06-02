# Operations

This guide covers local daily operation for `app-store-monitor`.

## Mock Daily Run

```bash
cd /path/to/app-store-monitor
python -m src.cli daily --mock --print
```

This creates or migrates the local SQLite database, inserts deterministic mock metrics, writes a report to `reports/`, and prints the Markdown report.

## Real Daily Run

Real mode expects a private local `.env` file and an App Store Connect `.p8` key that is not committed.

```bash
python -m src.cli check-config
python -m src.cli check-connection --real
python -m src.cli sync-apps
python -m src.cli create-report-request --all
python -m src.cli fetch --latest --all
python -m src.cli report --latest --print
```

`create-report-request --all` is safe to run daily. Existing active ongoing requests are reported as `existing`.

If `check-config` or `check-connection --real` fails, use [configuration-troubleshooting.md](configuration-troubleshooting.md) before retrying the rest of the real-mode flow.

## Discord Notifications

Set these values only in local `.env`:

```env
DISCORD_ENABLED=true
DISCORD_WEBHOOK_URL=<your-discord-webhook-url>
```

Then run:

```bash
python -m src.cli report --latest --print --notify --notify-once
```

The `--notify-once` flag prevents duplicate sends for the same metric date.

## macOS launchd

The example plist is:

```text
config/launchd/io.github.app-store-monitor.daily.plist.example
```

Edit the placeholder `/absolute/path/to/app-store-monitor` paths before loading it, or use:

```bash
make install-launchd
```

The daily shell runner writes logs to `logs/daily_YYYY-MM-DD.log`.

## Windows Task Scheduler

Register the daily task from the project root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\config\windows\register_task.ps1
```

Default task:

- Name: `App Store Monitor Daily`
- Schedule: daily at 08:30
- Working directory: project root
- Script: `scripts\run_daily.ps1`

Inspect the task:

```powershell
Get-ScheduledTask -TaskName "App Store Monitor Daily"
Get-ScheduledTaskInfo -TaskName "App Store Monitor Daily"
```

Unregister it:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\config\windows\unregister_task.ps1
```

## Local Data Reset

Delete only local runtime data when you want a clean development database:

```bash
rm -f data/app_store_monitor.sqlite3 data/app_store_monitor.sqlite3-*
python -m src.cli init-db
python -m src.cli seed-mock
python -m src.cli report --latest --print
```

Do not commit anything under `data/`, `logs/`, or generated `reports/`.
