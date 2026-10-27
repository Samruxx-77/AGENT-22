# AGENT 22 — Real Browser Automation

## Inspection findings (from the actual repo, not assumed)

- Browser toolset: `toolsets.py` — `browser_exec` is in `_HERMES_CORE_TOOLS`, toolset `browser` = all `browser_*` tools (browser_exec, browser_cdp, browser_dialog, browser_vault). The browser plugins are `plugins/browser/` (browser_use, browserbase, firecrawl) plus `tools/browser_*.py` (browser_use_cli, browser_session, browser_launcher, browser_url_policy, etc.).
- Telegram gateway: `hermes-telegram` bundle = full core tools, so it includes `terminal` AND `browser_exec`. browser_exec is additionally gated at tool-definition time: sessions whose toolsets lack `terminal` never see it. So the terminal-toolset dependency IS satisfied by the hermes-telegram bundle definition, provided the user has not added `browser` or `terminal` to `agent.disabled_toolsets` in config. Check that before debugging a missing browser_exec.
- Browser engine: `tools/browser_use_cli.py` — browser_exec drives a real browser through the Browser Use CLI engine (browser-harness, a core dependency of Hermes's own venv). Helpers: new_tab(url), goto_url(url), wait_for_load(), page_info(), js(expr), capture_screenshot(), fill_input, click_at_xy, cdp(...).
- Backend precedence (`tools/browser_session.py`): CDP override > hybrid ::local sidecar > cloud provider (fallback to LOCAL on failure) > local real profile (consented only) > Lightpanda (browser.engine=lightpanda, NO screenshots) > packaged Chromium via `tools/browser_launcher.py`.
- Local Chromium, no paid API: supported. Config `browser.engine: auto` (= Chromium), `browser.executable_path: ""` (= pm's chromium via `hermes pm install chromium`, else Docker build, else system chromium), `browser.headed: false`, `browser.use_real_profile: false` (fresh throwaway profile). Cloud provider is only used if configured; with none configured, the local backend is used. No Browser Use / Browserbase API key is required for local Chromium.
- Chromium auto-install: `tools/browser_launcher.py:_maybe_autoinstall_chromium()` does a one-shot `pm.ensure("chromium")` (~170 MB download) unless in Docker/Termux or an explicit executable is pinned. The supported install commands are: `hermes pm install chromium` and `hermes tools` -> Browser Automation -> Browser Use.

## What this build adds

- `plugins/mission-control/browser.py` — smoke test: open https://example.com (public, no login), read title via js('document.title'), screenshot via capture_screenshot(). URL allowlist: https only, private/localhost/metadata/credential URLs refused before any browser call. Fresh throwaway profile only; no real-profile cookies, no cookies copied into chat, no credentials printed, no CDP on a public interface (example config has cdp_url: "").
- `browser-local.example.yaml` — copy the browser: block into ~/.hermes/config.yaml and restart the gateway.
- Telegram: `browser-smoke` is a control command in platforms dispatch (owner/admin only, mapped by Telegram user id, allowlist still first). In Telegram: send `browser-smoke` (via the mission dispatch; the real gateway's slash registration is via the repo Telegram adapter, not by this plugin alone).
- CLI: `hermes mission browser-smoke --workspace <dir>`.

## Status in THIS build VM — read this before claiming anything

- `which hermes`: not found. No ~/.hermes. No .venv in the working copy. `python3 -c "import browser_harness"`: ModuleNotFoundError. `which chromium/chromium-browser/google-chrome`: no binary found.
- Therefore the project's supported install (`hermes pm install chromium`) could NOT be run here, because it requires a Hermes install / pm environment that is not present in this VM. No substitute install (apt, manual download) was performed, because the user specified the project's supported method only.
- Local smoke test in this VM: honestly reports available=False, success=False, "NOT RUN" (tested). Fake-runner tests pass for handler logic, but they are NOT a real browser test.
- End-to-end Telegram test: NOT PASSED. It requires (a) a real Hermes install with `hermes pm install chromium` completed, (b) the browser: block from browser-local.example.yaml in config, (c) a live Telegram gateway with TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USERS set, and (d) an owner-mapped Telegram user sending `browser-smoke`. None of those exist in this VM, and no token was provided or used. Do NOT claim browser access works until that test returns a title and a screenshot on a real install.

## Exact commands to test (on a real Hermes install)

1. `hermes pm install chromium`
2. `hermes tools` -> Browser Automation -> Browser Use (confirm enabled; confirm `browser` and `terminal` are NOT in agent.disabled_toolsets)
3. Copy `browser-local.example.yaml`'s browser: block into ~/.hermes/config.yaml, restart the gateway.
4. CLI smoke (no Telegram needed first): `hermes mission browser-smoke --workspace /tmp/agent22-browser-test`
   Expected on success: {"available": true, "url": "https://example.com", "title": "Example Domain", "screenshot": {"path": "...", "size_bytes": ...}, "success": true}
5. Telegram smoke (owner only, allowlisted): send `browser-smoke` to the bot. Expected: same title + screenshot attachment via the real Telegram adapter.
6. Health: `hermes mission platforms health --platform telegram` (token presence only, value never printed).

## Limitations that remain

- Lightpanda engine: no screenshots. If browser.engine is lightpanda, the smoke test reports title-only.
- Headed Chromium needs a display; display-less hosts stay headless (browser.headed=false is the default here).
- Real-profile browsing (use_real_profile=true) is deliberately OFF for smoke tests; turning it on copies real logins/cookies into a snapshot and must be a separate, consented decision, never a smoke-test default.
- Remote debugging: never set browser.cdp_url to a public address or 0.0.0.0. CDP is local-only in this configuration.
- Cloud browser providers (Browser Use / Browserbase / Nous Portal) are NOT configured here and would need a paid subscription / API key if ever chosen; local Chromium avoids that.
- Telegram allowlist and security protections remain enabled and unedited: TELEGRAM_ALLOWED_USERS, browser_url_policy (metadata/private SSRF guards), file_safety, approval floors. See AGENT22_LIMITS.md and AGENT22_PLATFORMS.md.
