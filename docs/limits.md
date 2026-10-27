# AGENT 22 — Limits Review

SAM asked to "break the limits" and remove them completely. This is the reviewed answer, not a blanket removal. The full, testable table lives in `plugins/mission-control/limits.py`; print it anytime with `hermes mission limits`.

## Loosened (configurable, SAM's choice, his risk)

- **Approval prompts for ordinary tool calls:** `approvals.mode` is `smart` by default. Set it to `off`, use `/yolo` in a session, or launch with `hermes --yolo`. This removes prompts, not hard floors.
- **Private-URL browser access for his own LAN/localhost:** set `browser.allow_private_urls=True`. Cloud-metadata URLs stay blocked regardless.
- **Mission approval gate:** a mission created without `--requires-approval` runs without that gate. Workspace bounds, verification and budget stops still apply.

## Kept (hard floors, NOT removed)

- Destructive system-wide operations (recursive system-dir delete, mkfs/dd, fork bombs, `sudo -S` without a password) — `tools/approval_floors.py`, `tools/approval_detection.py`.
- Credential / protected-file access (.env, SSH keys, auth.json, vault/, /etc/passwd|shadow|sudoers) — `agent/file_safety.py`.
- Cloud-metadata / SSRF (169.254.169.254, metadata endpoints) — `tools/browser_url_policy.py`.
- Unauthorized access / attacks on others' systems — no exploit, auth bypass, brute force or credential attack, even in pentest mode (owned-system diagnostics only).
- Telegram allowlist — gateway authorisation runs before any plugin command.

Why kept, in one line: these protect SAM's own system from a mistaken or injected command, and from a test escaping to somewhere else. Removing them would not make AGENT 22 more capable at SAM's real work; it would make a single bad prompt capable of destroying or leaking his own setup.

## Cannot be removed by editing this file

Muse's own runtime safety rules (for example: no sexual content involving minors, no bioweapons/chemical weapons, no incitement to violence) live in Muse's runtime, not in the Hermes repo. No file in this ZIP changes them, and no claim in AGENT 22's files should pretend otherwise. Once running, AGENT 22 is governed by its own model provider's policy.
