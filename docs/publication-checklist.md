# Publication Checklist

Use this checklist before splitting `products/app-store-monitor` into a standalone public repository.

## Safe to Publish

- Source code under `src/`.
- Tests under `tests/`.
- SQL schema under `sql/`.
- Example configuration files such as `.env.example`, `config/apps.example.json`, scheduler examples, and `.gitkeep` placeholders.
- Documentation under `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/`, and `LICENSE`.
- Scripts under `scripts/` that do not embed local credentials or personal paths.

## Exclude From the Public Repository

- `.env`, `.env.local`, and any `.env.*` files other than `.env.example`.
- `private_keys/` and every `*.p8` file.
- Discord webhook URLs.
- App Store Connect issuer IDs, key IDs, vendor numbers, and private key material.
- `data/*.sqlite*`, `*.db`, and any other real SQLite data.
- Generated reports under `reports/`.
- Runtime logs under `logs/`.
- Personal absolute paths such as a local home directory.

## Pre-Publish Commands

```bash
git status --short
git ls-files
rg -n "DiscordWebhookDomain|BEGIN[[:space:]]+PRIVATE[[:space:]]+KEY|IssuerIdWithValue|KeyIdWithValue|UnixHomePath|WindowsUsersPath" . --glob '!data/**' --glob '!logs/**' --glob '!reports/**' --glob '!private_keys/**' --glob '!.env*'
python -m unittest discover -s tests
python -m src.cli daily --mock --print
```

Review any matches manually. Placeholder values in `.env.example`, tests, and documentation are acceptable only when they are clearly fake.
