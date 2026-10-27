# Security Policy — AGENT 22

AGENT 22 is a fork of Hermes Agent (Nous Research, MIT). Upstream security policy is preserved in `docs/upstream/SECURITY-HERMES.md`. This file covers AGENT 22 additions and deployment of this fork.

## Reporting a vulnerability
Report privately via GitHub Security Advisories on this repository. Do not open public issues, PRs, or comments for vulnerabilities. Include the affected component (file path and line range), environment, reproduction, and which trust boundary is crossed.

## Trust boundaries in AGENT 22
- **Platform identity:** platform id only, never display name. A spoofed display name must never authorize a command.
- **Allowlist first:** Telegram/Discord/WhatsApp gateways must check the allowlist before any dispatch. An unmapped user is denied.
- **Mission bounds:** workspace only, argv commands only, timeout, stripped credential env, protected files/dirs refused, verification before completion, budget hard stops.
- **Hard floors (kept):** destructive system-wide operations, credential/protected-file access, cloud-metadata/SSRF, unauthorized attacks, Telegram allowlist — in `tools/approval_floors.py`, `tools/approval_detection.py`, `agent/file_safety.py`, `tools/browser_url_policy.py`. These are not removable by AGENT 22 config.
- **Browser:** never set `browser.cdp_url` to a public address, never turn on real-profile browsing for smoke tests, never copy cookies into chat.

## Safe deployment checklist
- Keep allowlists on; keep tokens in env/secure storage, never in commits.
- Never expose a privileged agent to unauthorised users.
- Never publish `.env`, session databases, browser profiles, chat logs, or personal memory files.
- Rotate any credential that was ever committed, and clean the history (deleting the file from the latest commit is not enough).

## Out of scope
- Security Research Mode is authorised own-asset audit/diagnostics only. It does not provide exploits, auth bypass, brute force, password cracking, or credential theft, and reports of its absence are not vulnerabilities.
- Limits of in-process heuristics are hardening work, not vulnerabilities, unless they cross a boundary above.
