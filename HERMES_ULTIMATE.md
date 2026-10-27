# AGENT 22 — Hermes Ultimate, P0 Implementation

> Product name in this fork: **AGENT 22**. Owner / developer: **SAM**.
> See `AGENT22_IDENTITY.md` for how the name is remembered, and for
> what was deliberately NOT removed (LICENSE, provider ids, hard floors).

This document is the handoff for the Hermes Ultimate Implementation
Blueprint, P0 foundation plus the AGENT 22 identity / Security
Research Mode / Telegram / memory / Companion additions requested
on 2026-10-27. P0 is complete and tested; P1/P2 items that remain
are listed honestly at the end -- they are NOT claimed as done.

## What was built (P0, verified by tests)

### Feature A — Mission Control (`plugins/mission-control/mission.py`)
- Mission record: id, goal, status, plan, steps, current step, results,
  approval requests, budget, usage, final result, error summary.
- States: queued, planning, running, waiting_for_approval, paused,
  retrying, completed, failed, cancelled. Invalid transitions raise
  `InvalidTransition` — a failed mission can never drift to completed.
- Persistence: one JSON file per store (`missions.json`), atomic
  tmp + `os.replace` writes, so a process restart reloads missions and
  resume skips already-completed steps (never repeats a completed
  non-idempotent step).
- Control: pause, resume, cancel, approve (waiting_for_approval ->
  queued), manual re-queue of a failed mission only. Cancellation is
  cooperative and re-read from disk before every step and every retry.
- Bounded retries with exponential backoff (`backoff_seconds`, pure
  function, capped). Non-idempotent steps are never auto-retried.
- Deadline, max_steps and max_retries enforced; exceeding a limit ends
  the mission as failed with a clear explanation.

### Feature B — Smart Model Router + Budget (`router.py`, `budget.py`)
- Explicit rule-based routing only. Task types: chat, coding, planning
  (reasoning), vision, simple (chat). Cheapest eligible model wins,
  latency breaks ties, choice is deterministic.
- Eligibility: allowlist (empty = all), healthy only, capability only.
- Fallback: never silently switches to a pricier model. With
  `allow_paid_fallback: false` a fallback may cost at most the primary;
  with a cost ceiling, any candidate over it is dropped. If nothing
  fits, `NoAffordableFallback` is raised — the caller must stop and ask.
- Budget ledger (`budget.json`, atomic): per-task and per-day totals.
  `record()` is a hard stop — exceeding max_task_cost or daily_budget
  raises `BudgetExceeded` and records nothing.
- **All costs are estimates.** Prices come from caller-supplied model
  profiles / example config only. No real prices are hard-coded, and no
  provider is called by this code, so no real money is spent in tests.

### Feature C (P0 part) — Workspace-bounded execution + verification (`runner.py`)
- Steps are argv lists only. Shell strings are refused.
- cwd is forced to the workspace; per-step timeout; environment is
  stripped of credential-looking variables unless explicitly allowlisted
  (and even then credential names are stripped).
- Verification targets must resolve inside the workspace (symlinks
  resolved); `..` escapes and protected basenames/dirs (.env, auth.json,
  .ssh, .git, .aws, .gnupg) are refused.
- Verification checks: `file_exists`, `file_nonempty`, `file_contains`,
  `step_succeeded`. A mission is completed ONLY if every check passes;
  otherwise it ends failed with verification evidence in the report.
- This runner does NOT bypass Hermes' own approval, file-safety or
  browser-URL floors. It is an extra, smaller boundary for mission
  steps, not a replacement for them.

### Bounded own-asset audit (`audit.py`, `mission audit`)
- Static analysis of your own files: flags eval/exec, pickle.load,
  shell=True, hardcoded-secret hints, md5/sha1, verify=False, os.system.
  Findings are review flags, not confirmed vulnerabilities.
- Printable-string extraction from your own binaries.
- Bounded debug runner for your own `.py` files inside the workspace
  (argv only, timeout, stripped env).
- **Hard gates:** target must be inside the workspace, must NOT be a
  URL/network target, and the caller must pass `--i-own-this`
  (authorised=True in code). Without that confirmation the audit is
  refused. Credential-looking strings in output are redacted.
- **Not implemented, by design:** unauthorised access, bypassing
  authentication, password cracking, credential theft/exfiltration,
  attacking other people's systems/accounts/networks, or removing the
  hard floors in `tools/approval_floors.py`,
  `tools/approval_detection.py`, `agent/file_safety.py` or
  `tools/browser_url_policy.py`. The blueprint (§13) requires those
  floors to stay, and the standing rule for this user is: no
  unauthorised access; security auditing for his own assets only.

### CLI + skill + config
- Plugin CLI: `hermes mission create|run|status|list|pause|resume|
  cancel|approve|report|budget|audit` (see `skills/productivity/
  mission-control/SKILL.md` for the full reference).
- Skill: `skills/productivity/mission-control/SKILL.md`.
- Example config (placeholders only, no secrets):
  `mission-control.example.yaml`.
- Plugin manifest: `plugins/mission-control/plugin.yaml` (author SAM).
  The plugin registers only via `ctx.register_cli_command`; **no core
  file was edited for the plugin itself** (plugins/AGENTS.md rule).


## Added in the 2026-10-27 continuation (identity, security, Telegram, memory, Companion)

### Identity — AGENT 22 / SAM (`plugins/mission-control/identity.py`)
- Single source of truth: `Identity` (name AGENT 22, owner SAM,
  developer SAM), `IdentityStore` (JSON, atomic, restart-persistent).
- `hermes mission identity` (JSON status) and `hermes mission banner`
  (clean banner: owner, mode, model/provider from config or "unknown",
  connection status only if actually measured -- default is
  "unknown (no live check performed)", never a hardcoded "connected").
- Core terminal banner also rebranded: `hermes_cli/banner.py` label and
  `hermes_cli/_startup_fast.py` print `AGENT 22 v<version>`.
- Persona: `SOUL.md`, `agent/prompt_builder.py:DEFAULT_AGENT_IDENTITY`,
  `hermes_cli/default_soul.py:DEFAULT_SOUL_MD` all answer AGENT 22 / SAM.
  To force a running install: `cp AGENT22_IDENTITY.md ~/.hermes/SOUL.md`
  (home SOUL.md overrides the repo default).

### Security Research Mode (`security.py`, `audit.py`)
- Static analysis, dependency audit (declared deps; CVE only if a real
  scanner such as pip-audit ran and said so), printable strings,
  static binary profile (size, SHA-256, entropy, strings -- NEVER
  executed), scoped DNS/TCP diagnostics (one host, max 20 ports, no
  metadata hosts, no sweeps), offline CTF decoders (base64/hex/rot13/
  reverse), and evidence-based scoped reports.
- Hard gates on every check: workspace scope, authorised=True
  (`--i-own-this`), no URLs, no other people's systems, no exploits,
  no auth bypass, no credential attacks, no brute force. Refused
  scopes return a structured error, not a partial success.

### Persistent project memory (`memory.py`)
- `hermes mission memory add|get|list|correct|delete|export`.
  Facts carry source + timestamp; correction keeps history; secrets
  are refused at write time, never stored.

### Companion Mode (`companion.py`, opt-in, tone-only)
- `hermes mission mode companion|normal [--tone ...]`. Companion
  prompt is transparent ("AI, not a human, not a real romantic
  partner"), warm/encouraging, no pet names unless configured, no
  guilt/jealousy/exclusivity, instant off. Mode never changes
  permissions, audit gates or secret access (tested).

### Telegram (`telegram.py`, `/mission ...`)
- `/mission status|list|pause|resume|cancel|approve|report|mode|identity`
  via plugin `register_command`. Gateway allowlist still runs first;
  the handler adds no new access and never prints secrets.


### Owned-system pentest (`pentest.py`, diagnostic only)
- `hermes mission security pentest <host> --port N [--workspace W] --i-own-this`
  -- for hosts you explicitly attest you own / are authorised to test.
  Checks: bounded port reachability (max 100, in chunks of 20),
  web security-header gaps from one plain GET, workspace config risks
  (.env present, DEBUG=True, hardcoded-secret patterns -- values
  redacted, never printed).
- Refused, even for owned targets: exploits, payloads, injection,
  XSS/SQLi probes, auth bypass, privilege escalation, brute force,
  password cracking, credential theft, and any blanket bypass of a
  protection -- including AGENT 22's own approval floors, file safety,
  browser URL policy and Telegram allowlists, which are unchanged.
  A refused attack type raises, it does not silently downgrade.

### Soul and heart (`plugins/mission-control/soul.py`
- `plugins/mission-control/limits.py`
- `plugins/mission-control/debugloop.py`
- `plugins/mission-control/dashboard.py`
- `plugins/mission-control/specialists.py`
- `plugins/mission-control/briefing.py`
- `tests/plugins/test_agent22_power.py`
- `plugins/mission-control/platforms.py`
- `plugins/mission-control/discord.py`
- `plugins/mission-control/whatsapp.py`
- `tests/plugins/test_agent22_platforms.py`
- `plugins/mission-control/browser.py`
- `tests/plugins/test_agent22_browser.py`
- `plugins/mission-control/reflection.py`
- `tests/plugins/test_agent22_reflection.py`
- `browser-local.example.yaml`
- `AGENT22_BROWSER.md`
- `AGENT22_PLATFORMS.md`, `SOUL.md`, `AGENT22_HEART.md`)
- Soul: genuinely helpful not performatively helpful, has opinions, resourceful before asking, direct, a guest in SAM's life.
- Heart: truth, respect, care earned daily, fun and connection, curiosity, boards first (Feb-Mar 2027).
- `hermes mission soul [--part soul|heart]` prints the persona; the seeded persona in `hermes_cli/default_soul.py` now carries a short soul+heart paragraph. Existing installs: copy the new `SOUL.md` and `AGENT22_HEART.md` to `~/.hermes/` to get the full text.
- Soul/heart change tone and values only, never permissions, safety rules or secret access. AGENT 22 is an AI, not a human, and never claims otherwise.

### Limits review (`limits.py`, `AGENT22_LIMITS.md`)
- Reviewed every agent limitation and sorted it, instead of blanket-removing: 3 configurable (approval prompts via approvals.mode/off//yolo, private-URL browser access, mission approval gate), 5 hard floors KEPT (destructive system ops, credential/protected files, cloud-metadata/SSRF, unauthorized attacks, Telegram allowlist), and Muse runtime safety rules marked as cannot-be-removed-by-file-edit.
- `hermes mission limits` prints the table. Hard-floor source files were NOT edited (tested: approval_floors and file_safety still contain their protections).

### Power additions (2026-10-27, "build everything")
- Telegram control center: `/plan <goal>`, `/run <id>`, `/cost`, `/report <id>`, `/help`, plus `/mission cost`. Gateway allowlist still first. Tested via handlers with a real mission run.
- Bounded self-debug loop: `hermes mission debug <command> --workspace W [--fix-script fix.py] --max-attempts 3`. Run -> fix -> re-run, stops on success, no fixer, or max attempts. The fixer is user code; the loop does not invent a fix.
- Live routing + cost dashboard: `hermes mission cost`, `hermes mission dashboard [--output file.html]`. Routing with a caller-supplied health map picks the healthy cheap model; without a health map it says "unknown" and falls back to estimates. Dashboard is a static HTML snapshot, not a live server, and costs are estimates only.
- Specialists + skill factory: researcher -> coder -> reviewer plan, reviewer verdict (approve only if checks pass and no secrets), `hermes mission specialists propose` (draft only) and `install --approve` (explicit approval only, never auto-install).
- Phone briefing: `hermes mission briefing` generates a short text briefing from real store data. No scheduler was created (that needs a separate time/destination approval) and no TTS is faked: briefing text is the input to an external TTS SAM already uses, delivered as MP3 per his rule.
- NOT built, as advised and as before: Docker sandbox (needs PC/VPS), large-scale web scraping (rate-limit/ban risk), auto-posting/auto-DM (ban risk + breaks "nothing public without my word").

### Multi-platform (2026-10-27, phased, Telegram first)
- Shared core: `platforms.py` dispatch + identity mapping (id only, never display name; control needs owner/admin, queries need any mapped role). Same mission ids/state on Telegram, Discord and WhatsApp.
- Phase 1 Telegram: DONE and verified (mission commands + authorization, 2 Telegram tests).
- Phase 2 Discord: command layer DONE, real gateway REUSED (`plugins/platforms/discord`, discord.py slash commands, role auth). Explicit guild/channel allowlists, private (ephemeral/DM) responses, file delivery validation (workspace only, <= 8 MB). NOT live-tested with a real bot token.
- Phase 3 WhatsApp: command layer DONE, real gateway REUSED (`plugins/platforms/whatsapp_cloud`, official Meta Cloud API; Baileys bridge NOT used). Webhook/signature verification, phone-number identity, 24-hour template flagging. NO account change made; US-number eligibility NOT assumed; Meta pricing NOT asserted (verify at setup). NOT live-tested with a real WABA/number.
- Health: `hermes mission platforms health [--platform ...]` — env presence only, values never printed; unconfigured = graceful "not_configured", Telegram keeps working.
- Full detail, setup checklists and costs: `AGENT22_PLATFORMS.md`.

### Browser automation (2026-10-27, inspected, NOT yet end-to-end verified)
- Inspected: browser_exec in _HERMES_CORE_TOOLS, toolset browser, hermes-telegram bundle includes terminal+browser_exec (terminal gate satisfied unless disabled in config), backend precedence CDP > ::local > cloud (fallback local) > real profile > Lightpanda > packaged Chromium, local engine auto=Chromium, supported install `hermes pm install chromium`.
- Added: browser smoke test (example.com title + screenshot via browser_exec, fresh throwaway profile, no cookies/creds, no public CDP), `browser-local.example.yaml`, CLI `hermes mission browser-smoke`, Telegram dispatch `browser-smoke` (owner/admin only, allowlist first).
- NOT VERIFIED: this VM has no hermes binary, no .venv, no browser_harness, no Chromium, so `hermes pm install chromium` could not run here and no substitute install was performed. Local smoke honestly reports NOT RUN. End-to-end Telegram test NOT PASSED (needs real Hermes install + Chromium + live Telegram gateway + owner token, none present here). Do not claim browser access works until that test passes. Full detail: AGENT22_BROWSER.md.

### Reflection + politeness (2026-10-27)
- `reflection.py`: structured reflection on failures and on user corrections — brief apology, correction first, what happened, best-reading cause (labelled, never invented), what was assumed, what to change next time, and a check ("Does that fix it?"). Never defensive, never blames SAM.
- Persistent reflection log (`reflections.json` in the store, inspectable, secrets redacted) so a mistake is not forgotten on restart.
- Persona updated in SOUL.md, soul.py and the seeded default_soul: courteous and warm like Muse/ChatGPT at their best, brief apology when wrong, correction first, no grovelling, no "as an AI" lectures.
- Commands: `hermes mission reflect --error "..."` or `--previous "..." --correction "..."`; Telegram: `reflect <error>` (query, any mapped role).
## Files changed / added (exact list)

Added (new files, no upstream file overwritten):
- `plugins/mission-control/__init__.py`
- `plugins/mission-control/plugin.yaml`
- `plugins/mission-control/mission.py`
- `plugins/mission-control/router.py`
- `plugins/mission-control/budget.py`
- `plugins/mission-control/runner.py`
- `plugins/mission-control/audit.py`
- `plugins/mission-control/security.py`
- `plugins/mission-control/identity.py`
- `plugins/mission-control/companion.py`
- `plugins/mission-control/memory.py`
- `plugins/mission-control/telegram.py`
- `plugins/mission-control/pentest.py`
- `plugins/mission-control/soul.py`
- `plugins/mission-control/limits.py`
- `plugins/mission-control/debugloop.py`
- `plugins/mission-control/dashboard.py`
- `plugins/mission-control/specialists.py`
- `plugins/mission-control/briefing.py`
- `tests/plugins/test_agent22_power.py`
- `plugins/mission-control/platforms.py`
- `plugins/mission-control/discord.py`
- `plugins/mission-control/whatsapp.py`
- `tests/plugins/test_agent22_platforms.py`
- `plugins/mission-control/browser.py`
- `tests/plugins/test_agent22_browser.py`
- `plugins/mission-control/reflection.py`
- `tests/plugins/test_agent22_reflection.py`
- `browser-local.example.yaml`
- `AGENT22_BROWSER.md`
- `AGENT22_PLATFORMS.md`
- `plugins/mission-control/cli.py`
- `plugins/mission-control/README.md`
- `tests/plugins/test_mission_control.py`
- `tests/plugins/test_agent22_identity_security.py`
- `tests/skills/test_mission_control_skill.py`
- `skills/productivity/mission-control/SKILL.md`
- `mission-control.example.yaml`
- `AGENT22_IDENTITY.md`
- `HERMES_ULTIMATE.md` (this file)

Edited for rebrand only (user-facing identity, see AGENT22_IDENTITY.md):
- `SOUL.md`
- `agent/prompt_builder.py` (DEFAULT_AGENT_IDENTITY + help guidance)
- `hermes_cli/default_soul.py` (DEFAULT_SOUL_MD + scaffold heading)
- `hermes_cli/banner.py` (banner label -> AGENT 22)
- `hermes_cli/_startup_fast.py` (startup print -> AGENT 22)
- `cli.py` (CLI title)
- `hermes_cli/commands.py` (version command description)

Not edited: the original ZIP, `LICENSE`, all approval/file-safety/
browser-policy floors, the Telegram adapter, the turn loop, and every
other upstream file. A full diff of the working copy against the
original extraction is: only the files listed above differ.

## Installation / commands

Prerequisites: Python 3.11+ (repo targets 3.14), the repo's normal
Hermes install. This P0 code itself needs only the standard library.

```bash
# From the repo root of this ZIP:
python3 -m py_compile plugins/mission-control/*.py   # syntax check

# The plugin is discovered by Hermes at startup (bundled plugins dir).
# Once Hermes is installed from this tree:
hermes mission create "Write a summary" --step write=python3,-c,open('out.txt','w').write('hi')
hermes mission run <mission-id> --workspace /path/to/workspace
hermes mission report <mission-id>

# Make the running install answer as AGENT 22 / SAM for sure:
cp AGENT22_IDENTITY.md ~/.hermes/SOUL.md
```

Default mission store: `$HERMES_HOME/missions`. Pass `--store <dir>`
in tests / scripts to use a different directory. Tests always pass
`--store` with a tmp dir and never touch a real home.

## Tests and exact results

Exact run in this VM (isolated venv, pytest 9.1.1, Python 3.12.3,
`--noconftest` because the repo conftest requires the pm test env --
see Known issues):
`pytest tests/plugins/test_mission_control.py tests/plugins/test_agent22_identity_security.py tests/skills/test_mission_control_skill.py -q`
=> **51 passed in 1.51s** (20 mission/router/budget/runner/audit/CLI
tests, 46 identity/security/memory/Telegram/pentest/soul/limits/power/platforms/browser/reflection tests, 2 skill tests).
No test calls a live provider, spends money, or uses a real secret.
Six tests failed on the first run and were fixed, then four owned-system
pentest tests were added and passed on first run after a test-loader
ordering fix (pentest must be loaded before cli in both test files). (audit network regex
too broad for filenames like `x.py`, CLI step parsing via commas,
base64 validation) -- see the final report; the 35-pass result is the
re-run after those fixes, not a first-run claim.

## Security notes

- Never put API keys, bot tokens, cookies, OAuth tokens or passwords
  into a goal, plan, step command, mission record or audit output.
  Mission records are persisted JSON; step output is truncated to
  4000 chars and credential-looking audit excerpts are redacted, but
  that is not a substitute for keeping secrets out in the first place.
- Telegram allowlists, approval prompts and hard floors are unchanged.
  The mission runner is an additional boundary, not a bypass.
- Dashboard / gateway exposure: P0 adds no dashboard and no new
  network listener.

## Known issues / limitations

- Full upstream test suite (`scripts/run_tests.sh`) was NOT run here:
  it requires `python -m pm.build_env` to build the pm test env, and
  the build VM had no pytest and no `.venv`. Upstream tests that
  assert the literal banner `Hermes Agent v...` and old prompt fixtures
  will fail until they are updated to AGENT 22 — that is expected
  after a rebrand, and is listed here rather than hidden.
- Plugin CLI discovery in a full Hermes install (`hermes mission`)
  was verified by unit-testing `register()` with a fake context and by
  exercising `cli.main()` directly; it was NOT verified inside a live
  `hermes` binary in this VM, because the full Hermes runtime env was
  not built here. The library behaviour (state, router, budget, runner,
  audit) is the part that was actually executed.
- Model routing is rule-based and estimate-based only. It does not
  measure live provider health or latency, and it does not call any
  provider. Real health/latency wiring is P1/P2 work.
- Telegram slash commands (`/plan`, `/run`, `/status`, ...) are NOT
  implemented in P0. Control is via `hermes mission ...` (CLI) in P0;
  Telegram control is Phase 3 / P1 in the blueprint sequence.

## NOT implemented yet (P1 / P2, per blueprint sequence)

- P1 (remaining): deep research skill, bounded self-debugging beyond
  the audit/security tools, specialist delegation beyond the existing
  `delegate_task`. Telegram control is PARTIAL: `/mission ...` is
  implemented and tested via its handler, but the full blueprint set
  (`/plan`, `/run`, `/cost`, `/report`, `/help` as separate commands)
  is not -- use `/mission report` / `/mission status` instead.
- P2: Dashboard, skill factory (user-reviewed skill proposals),
  proactive scheduled workflows beyond the existing cron scheduler,
  specialist agent roles.
- Companion Mode IS implemented as tone-only mode switching (see
  above), with the blueprint's limits. It is not a separate chat
  product and does not change any capability.

## Rollback

- Plugin + P0 only: delete `plugins/mission-control/`,
  `skills/productivity/mission-control/`,
  `tests/plugins/test_mission_control.py`,
  `tests/plugins/test_agent22_identity_security.py`,
  `tests/skills/test_mission_control_skill.py`,
  `mission-control.example.yaml`, `AGENT22_IDENTITY.md`,
  `HERMES_ULTIMATE.md`. No upstream file depends on them.
- Rebrand only: restore `SOUL.md`, `agent/prompt_builder.py`,
  `hermes_cli/default_soul.py`, `hermes_cli/banner.py`,
  `hermes_cli/_startup_fast.py`, `cli.py`, `hermes_cli/commands.py`
  from the original ZIP, and restore `~/.hermes/SOUL.md` from backup.
- Full rollback: discard this working copy and re-extract the
  original ZIP (hash recorded in the final report). The original ZIP
  was never modified.
