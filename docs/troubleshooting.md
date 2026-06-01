# Configuration Troubleshooting

This guide uses placeholders only. Do not paste real App Store Connect
credentials, private key contents, Discord webhook URLs, SQLite data, logs, or
generated reports into issues, pull requests, screenshots, or documentation.

## Mock Mode Setup

Mock mode is the safest first check because it does not need Apple credentials,
Discord, network access, or a real app portfolio.

Start from a clean checkout:

```bash
cp .env.example .env
python -m src.cli check-config
python -m src.cli daily --mock --print
```

Expected local values:

```env
APP_STORE_MONITOR_MODE=mock
APP_STORE_MONITOR_DB_PATH=./data/app_store_monitor.sqlite3
APP_STORE_MONITOR_REPORT_DIR=./reports
DISCORD_ENABLED=false
DISCORD_WEBHOOK_URL=
```

If `check-config` fails in mock mode, check these items first:

- `APP_STORE_MONITOR_MODE must be 'mock' or 'real'.` means the mode value has a
  typo or extra whitespace. Use `mock` for local development.
- `DISCORD_ENABLED=true requires DISCORD_WEBHOOK_URL.` means notifications were
  enabled without a webhook. Keep `DISCORD_ENABLED=false` unless testing
  Discord locally with a private webhook.
- `ASC_PRIVATE_KEY_EXISTS: False` is acceptable in mock mode. The private key is
  only required for real App Store Connect calls.

Mock mode writes local runtime files under `data/` and `reports/`. They are
ignored by Git and should stay local.

## Real App Store Connect Setup

Real mode requires a private `.env` file and a local `.p8` key downloaded from
App Store Connect. Use placeholders in shared examples:

```env
APP_STORE_MONITOR_MODE=real
ASC_ISSUER_ID=<issuer-id>
ASC_KEY_ID=<key-id>
ASC_PRIVATE_KEY_PATH=./private_keys/<app-store-connect-api-key>.p8
ASC_VENDOR_NUMBER=<vendor-number>
OPENSSL_PATH=
DISCORD_ENABLED=false
DISCORD_WEBHOOK_URL=
```

Validate configuration before calling the API:

```bash
python -m src.cli check-config
python -m src.cli check-connection --real
```

Common real-mode validation errors:

- `Missing App Store Connect env vars: ASC_ISSUER_ID, ASC_KEY_ID,
  ASC_PRIVATE_KEY_PATH` means one or more required values are blank.
- `Private key file not found: ...` means `ASC_PRIVATE_KEY_PATH` points to a file
  that does not exist from the repository root. Use a local path under
  `private_keys/`, and do not commit that directory.
- `ASC_ISSUER_ID is empty.` or `ASC_KEY_ID is empty.` means the App Store
  Connect API identifiers are still blank.
- `Failed to sign JWT with the private key...` usually means the key file is not
  the expected App Store Connect API key, the path points to the wrong file, or
  OpenSSL cannot read it.
- `Unauthorized (401). Check ASC_ISSUER_ID, ASC_KEY_ID, and the .p8 private
  key.` means the key ID, issuer ID, or private key do not match the same App
  Store Connect API key.

After `check-connection --real` succeeds, run the real flow in small steps:

```bash
python -m src.cli sync-apps
python -m src.cli create-report-request --all
python -m src.cli report-status --all
```

Apple can take 24-48 hours before newly created ongoing Analytics Reports have
downloadable daily segments.

## OpenSSL Path Handling

JWT signing uses OpenSSL. The app checks `OPENSSL_PATH`, then `PATH`, then common
install locations.

On Windows, Git for Windows commonly installs OpenSSL at:

```text
C:\Program Files\Git\usr\bin\openssl.exe
```

If Windows cannot find OpenSSL, set an absolute local path in `.env`:

```env
OPENSSL_PATH=<absolute-path-to-openssl.exe>
```

On macOS, OpenSSL is commonly available from Homebrew or the system path:

```text
/opt/homebrew/bin/openssl
/usr/local/bin/openssl
/usr/bin/openssl
```

If `check-connection --real` reports `OPENSSL_PATH is set but openssl was not
found there`, remove stale quotes or point `OPENSSL_PATH` at the actual local
binary.

If it reports `openssl command not found; cannot generate ES256 JWT`, install
OpenSSL or set `OPENSSL_PATH` in `.env`.

## Discord Webhook Validation

Discord is optional. Keep it disabled until the report flow works locally:

```env
DISCORD_ENABLED=false
DISCORD_WEBHOOK_URL=
```

When testing Discord, store the webhook only in local `.env`:

```env
DISCORD_ENABLED=true
DISCORD_WEBHOOK_URL=<discord-webhook-url>
```

Common notification errors:

- `DISCORD_WEBHOOK_URL is empty.` means Discord is enabled but no webhook is set.
- `DISCORD_WEBHOOK_URL has leading or trailing whitespace.` means the value has
  spaces around it.
- `DISCORD_WEBHOOK_URL includes quote characters.` means the value was wrapped in
  quotes. Store the URL without quotes.
- `DISCORD_WEBHOOK_URL must start with the Discord webhook API URL prefix.` means
  the value is not shaped like a Discord webhook.

Never commit or paste a real webhook URL. If a webhook is exposed, rotate it in
Discord before continuing.

## Files That Must Stay Local

Do not commit these files or include their contents in public support requests:

- `.env`, `.env.local`, or other local env files.
- App Store Connect `.p8` private keys and anything under `private_keys/`.
- Discord webhook URLs.
- Real SQLite databases under `data/`.
- Runtime logs under `logs/`.
- Generated Markdown reports under `reports/`.

Use `.env.example`, `config/*.example.*`, mock app names, mock numbers, and
temporary test directories for documentation and bug reports.
