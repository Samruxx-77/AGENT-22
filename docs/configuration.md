# Configuration

- `~/.hermes/config.yaml`: upstream settings, including `model.default`, `browser:` block (see `browser-local.example.yaml`), and `agent.disabled_toolsets` (must NOT contain `browser` or `terminal` for browser automation).
- `~/.hermes/.env`: secrets only (upstream `.env.example` is placeholders only; copy it to `.env` and fill in your own keys).
- `mission-control.example.yaml`: AGENT 22 plugin example, placeholders only, no real prices or secrets. Router/budget figures are estimates.
- Platform env vars: see README "Environment variable reference".
- Runtime store (never commit): `missions.json`, `budget.json`, `platform_identities.json`, `reflections.json` under the store dir (default `$HERMES_HOME/missions`, overridable with `--store`).
