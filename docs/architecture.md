# Architecture

See the Mermaid diagram in README.md. Summary:
- Upstream Hermes core: CLI, TUI, gateway, tools, providers, memory, skills.
- AGENT 22 mission-control plugin (`plugins/mission-control/`): mission, budget, router, runner, audit, security, pentest, identity, companion, memory, limits, soul, telegram, platforms, discord, whatsapp, browser, debugloop, dashboard, specialists, briefing, reflection, cli.
- Platform adapters: upstream `plugins/platforms/` (telegram, discord, whatsapp, whatsapp_cloud) reused, not rebranded; AGENT 22 adds a shared `dispatch()` and identity mapping on top.
- State: one shared JSON store per platform dispatch, so a mission started on Telegram can be checked from Discord or WhatsApp by an authorised, mapped user.
- Fork deviation: AGENT 22 identity edits touch upstream core files (`SOUL.md`, `agent/prompt_builder.py`, `hermes_cli/*`). This is documented in CHANGELOG.md; upstream house rules say plugins must not edit core.
