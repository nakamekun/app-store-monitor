# Windows Task Scheduler

This directory contains PowerShell helpers for running `app-store-monitor` every morning on Windows.

## Requirements

- Python available as `python`
- PowerShell 5 or later
- `.env` configured in the project root
- App Store Connect `.p8` key stored under `private_keys/`
- OpenSSL available from Git for Windows or configured with `OPENSSL_PATH`

Never commit `.env`, `.p8`, or `private_keys/`.

## OpenSSL

JWT signing requires `openssl.exe`. The app first honors `OPENSSL_PATH` in `.env`,
then checks `PATH`, then common install locations such as:

```text
C:\Program Files\Git\usr\bin\openssl.exe
```

If `check-connection --real` cannot find OpenSSL, add this to `.env` with the
actual path on the Windows machine:

```text
OPENSSL_PATH=C:\Program Files\Git\usr\bin\openssl.exe
```

## Manual Run

From the project root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_daily.ps1
```

The script writes logs to:

```text
logs\daily_YYYY-MM-DD.log
```

## Register Daily Task

Run PowerShell from the project root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\config\windows\register_task.ps1
```

Default task:

- Name: `App Store Monitor Daily`
- Schedule: daily at 08:30
- Working directory: project root
- Script: `scripts\run_daily.ps1`

## Unregister

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\config\windows\unregister_task.ps1
```

## Inspect Task

```powershell
Get-ScheduledTask -TaskName "App Store Monitor Daily"
Get-ScheduledTaskInfo -TaskName "App Store Monitor Daily"
```
