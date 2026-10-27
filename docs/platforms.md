# AGENT 22 — Multi-Platform Roadmap

One shared core, thin adapters. Core = MissionStore, BudgetLedger, Identity, Companion, Security, mission runner. Adapters = Telegram, Discord, WhatsApp Cloud. A mission started on one platform has the same mission_id and state on every other platform, because all adapters call `plugins/mission-control/platforms.py:dispatch()` on the same store.

## Phase 1 — Telegram: DONE and verified

- Status: FUNCTIONAL (mission-control command layer, tested via handlers).
- Commands: `/mission status|list|pause|resume|cancel|approve|report|cost|mode|identity`, plus `/plan`, `/run`, `/cost`, `/report`, `/help`.
- Authorization: repo Telegram adapter allowlist (`TELEGRAM_ALLOWED_USERS`) runs first in the real gateway; mission-control dispatch then checks the platform identity mapping (Telegram user id -> SAM role). Display names are never trusted.
- Real gateway: `plugins/platforms/telegram` (python-telegram-bot, slash commands, allowlists) — reused, not replaced. Required env: `TELEGRAM_BOT_TOKEN` (presence only in health checks; value never printed).
- Tests: `test_telegram_identity_and_mode`, `test_telegram_plan_run_cost_report_help` — passed in the full suite.

## Phase 2 — Discord: COMMAND LAYER DONE, real gateway REUSED (not yet live-tested with a real bot token)

- Inspected and found functional in-repo: `plugins/platforms/discord` — discord.py adapter, native slash commands (global cap 100/app, plugin commands registered after native ones), role-based DM auth (`adapter_authorization.py`, `adapter_slash_auth.py`), threads, reactions. This build does NOT replace it.
- Added in this build: `plugins/mission-control/discord.py` — slash-equivalent controls (`/mission`, `/plan`, `/run`, `/cost`, `/report`, `/help` via the same dispatch verbs as Telegram), mission status updates, private responses (every response marked private=True; the real adapter must send ephemerally or as DM, never as a public channel message), file delivery validation (inside workspace only, <= 8 MB safe default), and explicit server/channel permissions.
- Authorization: Discord user id (never display name) mapped to SAM role; control commands need owner/admin, queries need any mapped role. On top of that, explicit allowlists: `DiscordConfig(allowed_guild_ids=[...], allowed_channel_ids=[...], dm_allowed=False)` — empty allowlists fail closed, wrong guild/channel denied even for owner, DMs denied unless explicitly allowed.
- Setup to go live (not done by this build, no account change made): create a Discord application at discord.com/developers, create a bot, invite it to your server with the permissions it needs, set `DISCORD_BOT_TOKEN` and `DISCORD_ALLOWED_USERS` (user ids), set the guild/channel allowlists in the mission-control config, and register slash commands via the real adapter. Then run `hermes mission platforms health --platform discord`.
- Costs: Discord bot hosting and API use are free for this use; the only recurring cost is wherever you host the agent (your own machine/VPS, if any). No per-message Discord charge is asserted here — verify Discord's current developer terms at setup if you add a paid feature.
- Tests: Discord scope/private/file/health tests in `tests/plugins/test_agent22_platforms.py` — passed. Live Discord testing (real bot, real guild) is NOT done and is not claimed.

## Phase 3 — WhatsApp: COMMAND LAYER DONE, real gateway REUSED, NO account change made

- Inspected: two in-repo options. `plugins/platforms/whatsapp` = Node.js WhatsApp Web bridge (Baileys, unofficial) — NOT used. `plugins/platforms/whatsapp_cloud` = official Meta Cloud API (Graph API outbound, aiohttp webhook with X-Hub-Signature-256 inbound, text/media/buttons/voice, DM allowlists) — USED, because it is the maintainable, official route.
- Added in this build: `plugins/mission-control/whatsapp.py` — same dispatch as Telegram/Discord, phone-number identity (E.164 exact match, never profile/display name), webhook verification (`verify_webhook`, constant-time token compare) and signature verification (`verify_signature`, HMAC-SHA256 constant-time), and 24-hour-window flagging (requires_template passed by the caller; if True, the real adapter must send an approved template, not free text).
- Setup to go live (not done by this build, verify before any change):
  1. Meta developer app + WhatsApp Business Account (WABA) + a phone number registered to that WABA.
  2. The number must NOT already be registered on WhatsApp (personal app or Business app) — Meta rejects already-registered numbers. Do NOT assume SAM's US number (created via Proton VPN, purpose not yet stated) is eligible: check eligibility in the Meta dashboard per-number, before any migration, and do not deregister a personal number you still use without understanding the loss.
  3. Credentials, env only, never in chat: `WHATSAPP_CLOUD_PHONE_NUMBER_ID`, `WHATSAPP_CLOUD_ACCESS_TOKEN` (System User permanent token), `WHATSAPP_CLOUD_APP_SECRET`, `WHATSAPP_CLOUD_VERIFY_TOKEN`, `WHATSAPP_CLOUD_WABA_ID`.
  4. Webhook: public HTTPS URL, path `/whatsapp/webhook` (default), port 8090 (default), GET handshake with `hub.verify_token`, POST with `X-Hub-Signature-256` verification.
  5. Message restrictions: 24-hour customer-service window for free text; outside it, approved templates only; business-initiated messages must use templates.
- Costs: DO NOT assume free. Meta charges per 24-hour conversation, by category (utility / marketing / authentication / service) and by destination country, and rates change. Test numbers in the Meta dashboard are for testing only. Verify the current Meta pricing page at setup time and budget for it; no price is asserted here, because any price here would be stale or country-wrong. Hosting the webhook (public HTTPS) may also cost, depending on where you host it.
- Tests: webhook/signature/template/phone-identity/health tests in `tests/plugins/test_agent22_platforms.py` — passed. Live WhatsApp testing (real WABA, real number) is NOT done and is not claimed.

## Shared rules for every platform

- Same mission ids, same store, same dispatch. Start on Telegram, check on Discord, control on WhatsApp — same state.
- Identity by platform id only (Telegram id, Discord id, WhatsApp phone number). Display names, usernames and profile names are untrusted display data.
- Roles: owner > admin > user. Control needs owner/admin, queries need any mapped role, unmapped users are denied.
- Health checks: `hermes mission platforms health [--platform telegram|discord|whatsapp_cloud]` — env presence only, values never printed. Unconfigured platform = "not_configured", graceful, no crash, Telegram keeps working.
- Identity mapping: `hermes mission platforms map --platform <p> --platform-user-id <id> --role owner|admin|user` (agent-user defaults to SAM).
- Dispatch (core, for testing): `hermes mission platforms dispatch --platform <p> --platform-user-id <id> --command "mission status <id>"`.
- Licensing: repo LICENSE (MIT, Copyright 2025 Nous Research) kept intact; platform adapters in `plugins/platforms/*` are upstream code, reused, not rebranded as SAM's work. AGENT 22 branding is user-facing identity only (see AGENT22_IDENTITY.md).
