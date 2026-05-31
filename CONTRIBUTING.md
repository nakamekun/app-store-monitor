# Contributing

Thanks for helping improve `app-store-monitor`.

## Development Setup

```bash
cd app-store-monitor
cp .env.example .env
python -m src.cli init-db
python -m src.cli daily --mock --print
python -m unittest discover -s tests
```

The default `.env.example` uses mock mode. Real App Store Connect credentials are not needed for normal development.

## Before Opening a Pull Request

- Run `python -m unittest discover -s tests`.
- Keep changes scoped to the CLI, documentation, tests, or examples needed for the issue.
- Update README or docs when command behavior changes.
- Prefer deterministic tests using mock data and temporary directories.
- Do not add generated reports, local databases, logs, private keys, `.env` files, or webhook URLs.

## Secret Handling

Never paste or commit:

- App Store Connect issuer IDs, key IDs, vendor numbers, or `.p8` private keys.
- Discord webhook URLs.
- SQLite databases from real accounts.
- Generated reports or logs that may contain app names, IDs, or operational data.

If you accidentally expose a secret, rotate it before continuing and remove it from the branch history before publishing.

## Code Style

The project currently uses the Python standard library only. Keep that property unless a dependency is clearly worth the operational cost for small indie developers.
