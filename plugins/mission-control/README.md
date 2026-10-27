# Mission Control plugin

AGENT 22 (owner/developer: SAM) — P0 foundation plus identity,
Security Research Mode, persistent project memory and Companion Mode.

## What it does

- **Missions:** `hermes mission create|run|status|list|pause|resume|cancel|approve|report`
  — resumable, workspace-bounded, verified before completion.
- **Budgets / routing:** `hermes mission budget ...` — hard task/daily
  stops, estimates only, never a silent switch to a pricier model.
- **Identity:** `hermes mission identity` and `hermes mission banner`
  — configured name/owner, mode, model/provider from config (or
  "unknown"), connection status only if actually measured (default:
  "unknown (no live check performed)").
- **Mode:** `hermes mission mode normal|companion [--tone calm|playful|energetic|supportive]`
  — Companion Mode is opt-in and tone-only; it never changes permissions.
- **Memory:** `hermes mission memory add|get|list|correct|delete|export`
  — durable project facts with source + timestamp; secrets refused.
- **Audit / Security Research Mode:** `hermes mission audit ...` and
  `hermes mission security dependency|profile|diag|ctf|report|pentest`
  — `pentest` is diagnostic only for explicitly owned/authorised
  hosts (`--i-own-this`): port reachability, web security-header
  gaps and workspace config risks. Exploits, bypasses, brute force
  and credential attacks are refused, even for owned targets.
  — static analysis, strings, dependency audit, static binary profile
  (never executed), scoped DNS/TCP diagnostics, offline CTF decoders,
  and evidence-based reports for authorised targets only.
- **Reflection:** `mission reflect` + Telegram `reflect` — polite, correction-first, persistent log.
- **Browser:** `mission browser-smoke` + Telegram `browser-smoke` (real browser_exec when available; NOT RUN without Chromium — see AGENT22_BROWSER.md).
- **Platforms:** shared dispatch + identity mapping, Discord and WhatsApp Cloud layers (see AGENT22_PLATFORMS.md).
- **Power:** `mission debug|dashboard|cost|briefing|specialists`, Telegram `/plan|/run|/cost|/report|/help`.
- **Limits:** `hermes mission limits` — configurable vs hard floors kept vs runtime, with the review in AGENT22_LIMITS.md.
- **Soul/heart:** `hermes mission soul [--part soul|heart]` — persona and values, tone-only, never permissions.
- **Telegram:** `/mission status|list|pause|resume|cancel|approve|report|mode|identity`
  — gateway allowlist runs first; this handler adds no new access.

## What it deliberately does NOT do

- Unrestricted attacks against arbitrary third-party systems.
- Blanket bypasses of security protections (approval floors, file
  safety, browser URL policy, Telegram allowlists are unchanged).
- Exploits, credential attacks, auth bypasses, password cracking,
  credential theft/exfiltration, subnet sweeps or brute force.
- Executing untrusted binaries. Static malware profiling never
  executes the file.
- Claiming a connection, a CVE, or a deployment success that was not
  actually measured.

Security Research Mode is for your own systems, authorised targets,
CTF challenges and isolated analysis — with scoped targets, resource
limits, evidence-based reporting and verification.

## Layout

`mission.py` (state/store), `router.py`, `budget.py`, `runner.py`
(workspace execution + verification), `audit.py`, `security.py`,
`identity.py`, `companion.py`, `memory.py`, `cli.py`, `telegram.py`, `pentest.py`, `soul.py`, `limits.py`, `debugloop.py`, `dashboard.py`, `specialists.py`, `briefing.py`, `platforms.py`, `discord.py`, `whatsapp.py`, `browser.py`, `reflection.py`.
All stdlib-only. Tests: `tests/plugins/test_mission_control.py`,
`tests/plugins/test_agent22_identity_security.py`,
`tests/skills/test_mission_control_skill.py`.
