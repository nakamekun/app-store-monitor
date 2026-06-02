# Configuration Troubleshooting

Use this guide when local setup works in mock mode but fails in real App Store Connect mode.

## Start With Mock Mode

Mock mode is the safest way to verify the CLI, SQLite setup, and report generation before adding Apple credentials.

```env
APP_STORE_MONITOR_MODE=mock
DISCORD_ENABLED=false
```

Then run:

```bash
python -m src.cli init-db
python -m src.cli daily --mock --print
```

If mock mode succeeds, your local Python environment and project checkout are generally fine. The remaining work is usually real-mode credentials, OpenSSL, or Discord configuration.

## Real Mode Checklist

Switch to real mode only after mock mode is working.

```env
APP_STORE_MONITOR_MODE=real
ASC_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ASC_KEY_ID=ABC123DEFG
ASC_PRIVATE_KEY_PATH=./private_keys/app_store_connect_api_key.p8
OPENSSL_PATH=
DISCORD_ENABLED=false
DISCORD_WEBHOOK_URL=
```

Run these commands in order:

```bash
python -m src.cli check-config
python -m src.cli check-connection --real
```

`check-config` validates local settings and file paths. `check-connection --real` confirms the `.p8` key can be used to generate an ES256 JWT.

## Common `check-config` Failures

### `APP_STORE_MONITOR_MODE must be \`mock\` or \`real\`.`

Cause:
The mode value in `.env` is empty or misspelled.

Fix:
Set `APP_STORE_MONITOR_MODE=mock` for local testing or `APP_STORE_MONITOR_MODE=real` for App Store Connect access.

### `Missing App Store Connect env vars: ...`

Cause:
Real mode requires `ASC_ISSUER_ID`, `ASC_KEY_ID`, and `ASC_PRIVATE_KEY_PATH`.

Fix:
Add all three values to `.env`. Use placeholders while editing docs or screenshots, never real credentials.

### `Private key file not found: ...`

Cause:
`ASC_PRIVATE_KEY_PATH` does not point to a readable local `.p8` file.

Fix:
- Confirm the file exists on disk.
- Check relative paths from the repository root.
- Avoid surrounding the path with quotes unless your shell or editor requires them.

Example:

```env
ASC_PRIVATE_KEY_PATH=./private_keys/app_store_connect_api_key.p8
```

## Common `check-connection --real` Failures

### `ASC_ISSUER_ID is empty.` or `ASC_KEY_ID is empty.`

Cause:
Required App Store Connect values are still blank in `.env`.

Fix:
Copy the values from App Store Connect into `.env` and rerun `python -m src.cli check-config`.

### `openssl command not found; cannot generate ES256 JWT.`

Cause:
The CLI could not find `openssl` in `PATH`, and no fallback Windows path was available.

Fix on Windows:
- Install Git for Windows or OpenSSL.
- If `openssl.exe` is not already in `PATH`, set `OPENSSL_PATH` in `.env`.

Example:

```env
OPENSSL_PATH=C:\Program Files\Git\usr\bin\openssl.exe
```

Fix on macOS:
- Confirm `openssl` is available in your shell `PATH`.
- If you use a custom install location, point `OPENSSL_PATH` to that executable.

### `OPENSSL_PATH is set but openssl was not found there: ...`

Cause:
The configured path is wrong, or the file does not exist on this machine.

Fix:
- Correct the path in `.env`.
- Prefer an absolute path on Windows.
- On macOS, you can use either a valid absolute path or a shell-resolvable executable name if it is in `PATH`.

### `Unauthorized (401). Check ASC_ISSUER_ID, ASC_KEY_ID, and the .p8 private key.`

Cause:
The JWT was created, but App Store Connect rejected the credentials.

Fix:
- Re-check `ASC_ISSUER_ID` and `ASC_KEY_ID` for copy/paste mistakes.
- Confirm the `.p8` file matches the key ID.
- Make sure the key has not been revoked and belongs to the correct App Store Connect account.

### `Forbidden (403). Check App Store Connect API key roles and app access.`

Cause:
The key is valid, but it does not have permission to perform the requested API operation.

Fix:
- Review the App Store Connect API key roles.
- Confirm the key can access the target apps and analytics data.
- If the account was recently updated, retry after permissions have propagated.

## Discord Webhook Validation

If you enable Discord notifications, keep this separate from App Store Connect troubleshooting.

Common webhook validation failures:

- `DISCORD_ENABLED=true requires DISCORD_WEBHOOK_URL.`
- `DISCORD_WEBHOOK_URL is empty.`
- `DISCORD_WEBHOOK_URL has leading or trailing whitespace.`
- `DISCORD_WEBHOOK_URL includes quote characters.`
- `DISCORD_WEBHOOK_URL must start with the Discord webhook API URL prefix.`

Fix:
- Set `DISCORD_ENABLED=false` until the webhook is ready.
- Paste the full Discord webhook URL without quotes or extra spaces.
- Keep the real URL in local `.env` only.

## Safe Files To Keep Local Only

Never commit any of the following:

- `.env` or `.env.local`
- `private_keys/`
- `*.p8`
- real SQLite database files
- logs
- generated reports
- Discord webhook URLs

Use `.env.example`, `config/*.example.*`, mock data, and placeholder values in documentation instead.
