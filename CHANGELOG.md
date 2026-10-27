# Changelog — AGENT 22

All notable changes to this fork. Upstream Hermes changes are tracked in the upstream repository; this file tracks AGENT 22 additions only.

## [Unreleased] — Initial public release (2026-10-27)

### Added
- Mission-control plugin (`plugins/mission-control/`): mission store, router, budget ledger, workspace runner, verification, CLI (`hermes mission ...`).
- Security Research Mode (authorised own-asset audit only): static audit, dependency audit, static binary profile (never executed), scoped network diagnostics, offline CTF decoders, owned-system diagnostic pentest.
- Identity (AGENT 22 / SAM), persistent project memory, Companion Mode (opt-in, tone-only), soul/heart persona, reflection + politeness.
- Limits review (`AGENT22_LIMITS.md`): 3 configurable limits documented, 5 hard floors kept, Muse runtime rules marked not removable by file edit.
- Telegram control commands (`/plan`, `/run`, `/cost`, `/report`, `/help`, `/reflect`, `/browser-smoke`), bounded self-debug loop, static cost dashboard, specialists + skill factory (draft-only, approved install), phone briefing (text only, no scheduler, no faked TTS).
- Multi-platform dispatch (`platforms.py`, `discord.py`, `whatsapp.py`): shared mission state across Telegram, Discord and WhatsApp Cloud.
- Browser smoke test (`browser.py`, `browser-local.example.yaml`).
- Public-ready documentation: README with honest status labels, `docs/` (installation, configuration, architecture, platforms, browser, troubleshooting), `CODE_OF_CONDUCT.md`, AGENT 22 `CONTRIBUTING.md` and `SECURITY.md`, `.github/workflows/agent22-mission-control.yml`.

### Changed (fork deviation, documented)
- User-facing identity only: `SOUL.md`, `agent/prompt_builder.py`, `hermes_cli/default_soul.py`, `hermes_cli/banner.py`, `hermes_cli/_startup_fast.py`, `cli.py`, `hermes_cli/commands.py` now say AGENT 22, owner/developer SAM. Upstream's "plugins must not edit core" rule is deliberately deviated from here, at the owner's direction.
- Root `README.md`, `CONTRIBUTING.md`, `SECURITY.md` are now AGENT 22 versions; upstream versions are preserved in `docs/upstream/`.

### Deliberately NOT changed / NOT implemented
- `LICENSE` MIT notice (Copyright 2025 Nous Research) — kept.
- Hard floors in `tools/approval_floors.py`, `tools/approval_detection.py`, `agent/file_safety.py`, `tools/browser_url_policy.py` — never edited.
- Unrestricted attacks, exploits, auth bypass, brute force, password cracking, credential theft — not implemented, by design.
- Docker sandbox, large-scale scraping, auto-post/DM — not implemented.
- Live Discord, live WhatsApp Cloud, live Telegram browser test — not live-tested in the build environment (see README status table).

### Known limitations
- Full upstream test suite (`scripts/run_tests.sh`) not run here; it needs the pm test environment. Mission-control tests: 68 passed (see README).
- Upstream commit SHA cannot be stated from the ZIP source (no `.git`).
- No fake badges, stars, usage statistics, or CI status are claimed.
