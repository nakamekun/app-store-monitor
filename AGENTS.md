# Agent Instructions

This repository is intended to be publishable as open source.

## Safety Rules

- Do not read, print, summarize, copy, or commit `.env`, `.env.local`, `private_keys/`, `*.p8`, real SQLite databases, logs, generated reports, or Discord webhook URLs.
- Use `.env.example`, `config/*.example.*`, mock data, tests, and temporary directories for examples.
- Keep mock mode working without Apple credentials or network access.
- Before publishing, run a secret-oriented scan for private keys, webhook URLs, local absolute paths, SQLite files, logs, and generated reports.

## Useful Commands

```bash
python -m unittest discover -s tests
python -m src.cli daily --mock --print
python -m src.cli check-config
```

## Project Intent

`app-store-monitor` is a CLI for individual and small-team iOS developers who want daily App Store Connect analytics reports and Discord notifications from their own local environment.
