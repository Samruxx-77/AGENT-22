# AGENT 22

**A customisable Hermes-based AI agent with shared mission management, messaging-platform integrations and extensible automation.**

AGENT 22 is a fork/customisation of [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research (MIT, Copyright 2025 Nous Research — see `LICENSE` and `docs/upstream/`). It is **not** entirely original code, and it does not claim ownership of upstream Hermes code. Upstream is the foundation; AGENT 22 adds a mission-control plugin, an AGENT 22 / SAM identity layer, multi-platform dispatch, and bounded automation tools on top of it.

Status labels in this README are honest, not marketing:
✅ **Implemented and tested** — code exists and its tests pass here.
🟡 **Implemented but not live-tested** — code and handler tests pass, but no live gateway, bot token, or real account verified it.
🧪 **Experimental / partially implemented** — works in a bounded form, with limits stated.
📋 **Planned / not implemented** — not in this release; do not treat it as operational.

## Features at a glance

| Feature | Status | What it actually does |
|---|---|---|
| Shared mission system | ✅ Implemented and tested | Create, inspect, pause, resume, cancel, approve and report missions. Invalid-transition guards, atomic JSON persistence, resume skips completed steps, bounded retries, deadline/max-steps limits, verification before completion. |
| Telegram control | ✅ Implemented and tested (handler level) | `/mission status\|list\|pause\|resume\|cancel\|approve\|report\|cost\|mode\|identity`, plus `/plan`, `/run`, `/cost`, `/report`, `/help`, `/reflect`, `/browser-smoke`. Allowlist first, then platform-id mapping. Live Telegram gateway with a real bot token is **not** tested in this build environment. |
| Cross-platform architecture | 🟡 Implemented but not live-tested | One shared store and one `dispatch()` for Telegram, Discord and WhatsApp Cloud. Same mission id/state on every platform. Discord and WhatsApp live gateways are not tested here. |
| Identity & permissions | ✅ Implemented and tested | Platform-id identity only (Telegram id, Discord id, WhatsApp phone number). Display names are never trusted. Roles owner > admin > user; control needs owner/admin. |
| Budget & cost tracking | 🧪 Experimental / partially implemented | Per-task and per-day ledger with hard stops. **All figures are estimates**, from caller-supplied model profiles — no live provider billing, no provider API calls in this code. |
| Bounded debugging | ✅ Implemented and tested | Run → fix → re-run loop, max 3 attempts by default, workspace only, argv only, user-supplied fix script. It does not invent a fix. |
| Specialist roles & skills | 🧪 Experimental / partially implemented | Researcher → Coder → Reviewer plan and reviewer verdict. Skill factory proposes drafts only; install requires explicit `--approve`. Specialists are role prompts/checks, not autonomous LLM agents by themselves. |
| Companion Mode | ✅ Implemented and tested (tone only) | Opt-in, transparent AI companion tone. Never claims to be human or a romantic partner. Never changes permissions. Instant off. |
| Browser automation | 🟡 Implemented but not live-tested | Upstream `browser_exec` + AGENT 22 smoke test (example.com title + screenshot). Requires `hermes pm install chromium` and local Chromium config. **End-to-end Telegram browser test has not passed in this build environment** — see `docs/browser.md`. |
| Soul & reflection | ✅ Implemented and tested | Persona (soul/heart) + structured reflection on failures/corrections, persistent reflection log, polite correction-first tone. |
| Limits review | ✅ Implemented and tested | `hermes mission limits`: 3 configurable limits, 5 hard floors kept, Muse runtime rules marked as not removable by file edit. |

## Architecture

```mermaid
flowchart TD
    User[User on Telegram / Discord / WhatsApp] --> Gateway[Platform gateway adapters<br/>upstream: telegram, discord, whatsapp_cloud]
    Gateway --> Auth[Platform identity mapping<br/>id only, never display name<br/>owner > admin > user]
    Auth --> Dispatch[Shared dispatch<br/>plugins/mission-control/platforms.py]
    Dispatch --> Core[Shared AGENT 22 core<br/>MissionStore, BudgetLedger, Identity<br/>Companion, Security, Runner]
    Core --> Tools[Mission tools<br/>audit, pentest (diagnostic), debug loop<br/>dashboard, briefing, specialists, soul, reflection]
    Core --> Browser[Browser automation<br/>upstream browser_exec + local Chromium<br/>smoke test only, no real profile]
    Core --> Store[Shared JSON store<br/>missions.json, budget.json<br/>platform_identities.json, reflections.json]
```

The core is a narrow waist: platforms are adapters, capability lives in the mission-control plugin. Upstream Hermes core tools are unchanged except for the documented AGENT 22 identity edits in `CHANGELOG.md` — a deliberate fork deviation from upstream's "plugins must not edit core" rule, made at the owner's direction and documented, not hidden.

## Quick start

Requirements: Python >= 3.11, < 3.15 (upstream's full pm environment targets 3.14; the mission-control plugin itself is stdlib-only and its tests run on Python 3.12), Git, and a model provider account for the full Hermes agent. The mission-control plugin tests need only Python + pytest.

```bash
# 1. Clone (after publication; replace with the real URL from the release)
git clone https://github.com/Samruxx-77/AGENT-22.git
cd AGENT-22

# 2. Upstream Hermes install (full agent, model, gateway)
# Linux/macOS/WSL2: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
# Termux/Android: use the upstream Termux guide, NOT the desktop/server installer.
# See docs/installation.md for Termux limitations.

# 3. Mission-control plugin tests (stdlib-only, no provider, no secrets)
python3 -m venv /tmp/agent22-test-venv
/tmp/agent22-test-venv/bin/pip install -q pytest
/tmp/agent22-test-venv/bin/pytest tests/plugins/test_mission_control.py \
  tests/plugins/test_agent22_identity_security.py \
  tests/plugins/test_agent22_power.py \
  tests/plugins/test_agent22_platforms.py \
  tests/plugins/test_agent22_browser.py \
  tests/plugins/test_agent22_reflection.py \
  tests/skills/test_mission_control_skill.py \
  -q -p no:cacheprovider --noconftest
# Verified in the release build: 68 passed (see Test results below).
# Note: upstream's own runner is scripts/run_tests.sh and needs the pm test
# environment; --noconftest is used here only because the repo conftest
# requires that pm environment, which was not available in the build VM.
```

Try the mission CLI (inside a Hermes install, where the plugin is registered):

```bash
hermes mission identity
hermes mission banner
hermes mission create "Write a summary" --step "write=python3 -c \"open('out.txt','w').write('hi')\""
hermes mission run <mission-id> --workspace /path/to/your/project
hermes mission report <mission-id>
hermes mission platforms health
hermes mission soul
hermes mission reflect --error "test failed"
```

To force the AGENT 22 persona on a running install, copy `AGENT22_IDENTITY.md` to `~/.hermes/SOUL.md` (home SOUL overrides the repo default). New installs also get the identity from `hermes_cli/default_soul.py` and `agent/prompt_builder.py`.

## Requirements and supported environments

- **Supported (upstream Hermes):** Linux, macOS, WSL2, Windows (native PowerShell installer), Docker, and Termux/Android (aarch64, via the upstream Termux APT guide — see `docs/installation.md`).
- **Termux/Android limitations:** the desktop/server installer script must not be used on Termux; the pm Chromium build is not available on Termux (browser_launcher skips pm install there), so local Chromium browser automation is limited on Termux. Mission-control plugin tests themselves are stdlib-only and do not need Chromium.
- **Not supported / not claimed:** running the full Hermes gateway on a phone with no server/VPS, live Discord/WhatsApp gateways without their respective bot/app setup, and any platform without its required token/account.

## Model provider configuration

Upstream Hermes: use `hermes model` / `hermes setup` to choose a provider (Nous Portal, OpenRouter, OpenAI, your own endpoint, and others in upstream docs). Default model is in `~/.hermes/config.yaml` (`model.default`). AGENT 22's router (`plugins/mission-control/router.py`) is **rule/estimate-based only**: it picks the cheapest eligible model from caller-supplied profiles, never calls a provider, and never hard-codes real prices. Live health is only applied when the caller supplies a health map (`dashboard.py:select_model_live`); without one, health is reported as "unknown". See `docs/configuration.md`.

## Platform setup

Full checklists, including costs and eligibility warnings, are in `docs/platforms.md`. Summary:

- **Telegram:** create a bot via @BotFather, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USERS` (user ids only), map your Telegram id with `hermes mission platforms map --platform telegram --platform-user-id <id> --role owner`. Status: command layer implemented and handler-tested; live gateway not tested in this build environment.
- **Discord:** create a Discord application/bot, invite it to your server, set `DISCORD_BOT_TOKEN` and `DISCORD_ALLOWED_USERS`, set explicit guild/channel allowlists (`DiscordConfig`), and send responses ephemerally/DM only. Reuses upstream `plugins/platforms/discord` (discord.py, slash commands, role auth). Status: implemented but not live-tested. Discord bot API use is free for this use; hosting the agent itself may cost, depending on where you host it.
- **WhatsApp Cloud API:** Meta developer app + WhatsApp Business Account + a phone number registered to it that is **not** already registered on WhatsApp. Env: `WHATSAPP_CLOUD_PHONE_NUMBER_ID`, `WHATSAPP_CLOUD_ACCESS_TOKEN`, `WHATSAPP_CLOUD_APP_SECRET`, `WHATSAPP_CLOUD_VERIFY_TOKEN`, `WHATSAPP_CLOUD_WABA_ID`. Webhook: public HTTPS, `/whatsapp/webhook`, port 8090 by default. 24-hour window: free text only inside it, approved templates outside it. **Do not assume any number is eligible and do not assume free:** Meta charges per 24-hour conversation by category and destination country, rates change, test numbers are for testing only — verify Meta's current pricing at setup. The older Baileys/WhatsApp Web bridge is deliberately not used. Status: implemented but not live-tested, and no account change is made by this code.

## Browser automation setup

See `docs/browser.md` for the full inspection. In short:

```bash
hermes pm install chromium
# then: hermes tools -> Browser Automation -> Browser Use
# copy browser-local.example.yaml's browser: block into ~/.hermes/config.yaml
# restart the gateway
hermes mission browser-smoke --workspace /tmp/agent22-browser-test
# Telegram (owner only, allowlisted): send "browser-smoke"
```

Local Chromium (`browser.engine: auto`, `use_real_profile: false`, `cdp_url: ""`) needs no paid browser API. Lightpanda engine has no screenshots. Never set `browser.cdp_url` to a public address or 0.0.0.0, and never turn on real-profile browsing for smoke tests. **End-to-end Telegram browser test has not passed in this build environment** (no hermes binary, no browser_harness, no Chromium there), so do not treat browser access as verified until the commands above return a real title and screenshot on your install.

## Environment variable reference

Placeholders only — see `.env.example` (upstream) and `mission-control.example.yaml` (AGENT 22 plugin example, placeholders only, no real prices or secrets).

| Variable | Purpose | Required for |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather | Telegram gateway |
| `TELEGRAM_ALLOWED_USERS` | Comma-separated Telegram user ids | Telegram allowlist |
| `DISCORD_BOT_TOKEN` | Discord bot token | Discord gateway |
| `DISCORD_ALLOWED_USERS` | Comma-separated Discord user ids | Discord allowlist |
| `WHATSAPP_CLOUD_PHONE_NUMBER_ID` | WhatsApp Cloud phone number id | WhatsApp Cloud gateway |
| `WHATSAPP_CLOUD_ACCESS_TOKEN` | System User permanent token | WhatsApp Cloud gateway |
| `WHATSAPP_CLOUD_APP_SECRET` | HMAC key for webhook signature verification | WhatsApp Cloud gateway |
| `WHATSAPP_CLOUD_VERIFY_TOKEN` | Webhook handshake token | WhatsApp Cloud gateway |
| `WHATSAPP_CLOUD_WABA_ID` | WhatsApp Business Account id | WhatsApp Cloud gateway |
| `HERMES_HOME` | Hermes home dir (default `~/.hermes`) | All (never hardcode in code) |
| `HERMES_WORKSPACE` | Workspace for mission runs (tests/CLI) | Mission runs |

Never put real values in chat, issues, or commits. Health checks report env **presence only**, never values.

## Permissions and security model

- **Platform identity:** by platform id only, never display name. Roles owner > admin > user; control needs owner/admin.
- **Mission bounds:** workspace only, argv commands only (no shell strings), timeout, stripped credential env, protected files/dirs refused (`.env`, `auth.json`, `.ssh`, `.git`, `.aws`, `.gnupg`), verification before completion, budget hard stops.
- **Hard floors kept (not removed):** destructive system-wide operations, credential/protected-file access, cloud-metadata/SSRF, unauthorized attacks, Telegram allowlist — see `AGENT22_LIMITS.md` and `docs/limits.md`. AGENT 22's configurable limits (approvals off/yolo, private URLs, mission gate) do not remove these floors.
- **Security Research Mode:** authorised own-asset audit/diagnostics only (static analysis, strings, dependency audit, static binary profile never executed, scoped network diagnostics, offline CTF decoders, owned-system diagnostic pentest). No exploits, auth bypass, brute force, password cracking, or credential theft, even for owned targets.
- **Safe deployment:** never expose a privileged agent to unauthorised users — keep allowlists on, keep tokens in env/secure storage, keep `use_real_profile` off unless you deliberately consent, and never publish a `.env`, session database, browser profile, chat log, or personal memory file. See `SECURITY.md`.

## Test instructions and verified results

```bash
# Mission-control plugin tests (see Quick start above)
# Verified in the release build (Python 3.12.3, pytest 9.1.1, isolated venv):
#   68 passed in 2.03s
# Breakdown: mission/router/budget/runner/audit/CLI, identity/security,
# power (Telegram control, debug loop, dashboard, specialists, briefing),
# platforms (shared state, id-only auth, Discord, WhatsApp), browser,
# reflection, and skill authoring.
# Upstream full suite: NOT run here — it needs the pm test environment
# (scripts/run_tests.sh). Do not claim the full upstream suite passes
# from this release alone.
python3 -m py_compile plugins/mission-control/*.py
```

## Troubleshooting and FAQs

- **browser_exec not visible in Telegram?** Check `agent.disabled_toolsets` does not contain `browser` or `terminal` — hermes-telegram includes both, and browser_exec is gated on terminal.
- **Browser smoke says NOT RUN?** That is honest, not a bug: browser_harness/Chromium is not installed. Run `hermes pm install chromium` on a real Hermes install, then retry.
- **Discord/WhatsApp commands denied?** Check the identity mapping (`platforms map`) and, for Discord, guild/channel allowlists; for WhatsApp, the phone number exact match. Display names never authorize.
- **Mission stuck in waiting_for_approval?** Run `hermes mission approve <id>` as owner/admin, or create without `--requires-approval`.
- **Costs look wrong?** They are estimates, not bills. See Budget section above.
- **Is AGENT 22 a human?** No. It is an AI agent, and Companion Mode says so explicitly.

See `docs/troubleshooting.md` for more.

## Roadmap

- 📋 Live-test Discord gateway with a real bot and guild (needs bot token + server setup).
- 📋 Live-test WhatsApp Cloud gateway with a real WABA/number (needs Meta setup + eligibility check + pricing verification).
- 📋 Live-test browser automation end-to-end via Telegram (needs real Hermes install + Chromium).
- 📋 Full upstream test suite via `scripts/run_tests.sh` on a pm environment.
- 📋 Dashboard as a live (not static) view, and scheduled briefings (needs explicit schedule approval).
- 📋 More specialist roles and user-reviewed skill proposals.
- Not planned: Docker sandbox (needs PC/VPS), large-scale web scraping, auto-posting/auto-DM, unrestricted attacks, blanket bypasses.

## Contributing

See `CONTRIBUTING.md`. In short: keep changes in the mission-control plugin where possible (do not edit upstream core without a documented fork reason), add tests that mirror the source layout, never write to `~/.hermes/` in tests, never commit secrets or runtime data, and label every new feature with its honest status (implemented/tested, not live-tested, experimental, planned).

## Hermes upstream attribution, license and acknowledgements

- **Upstream:** Hermes Agent by Nous Research, MIT License, Copyright (c) 2025 Nous Research. Upstream repository: https://github.com/NousResearch/hermes-agent. Upstream README, CONTRIBUTING and SECURITY are preserved in `docs/upstream/`.
- **This fork:** AGENT 22 identity, mission-control plugin, platform dispatch layers, soul/heart, limits review, reflection, browser smoke test, and this documentation are AGENT 22 additions, built by/for SAM (owner/developer of the AGENT 22 customisation). They do not transfer ownership of upstream code to SAM, and upstream code remains under its MIT license.
- **Version/commit note:** the upstream source used here came from a ZIP without a `.git` directory (22,624 zip entries, 273 MB unpacked, 10,283 Python files, `pyproject.toml` version `0.0.0`), received 2026-10-26/27. No upstream commit SHA can be honestly stated from that source, and none is claimed here. If you need an exact upstream commit, compare against the upstream repository's history at release time.
- **Third-party notices:** see upstream `LICENSE`, `NOTICE` files if present in-tree, and dependency licenses in `pyproject.toml`/`uv.lock`. Do not remove attribution notices.
