"""AGENT 22 limits review: what can be loosened, what stays, and why.

The user asked to "break the limits" and "completely remove" them.
This module is the honest, reviewed answer, not a blanket removal:

Configurable limits (SAM may loosen these for his own agent, at his
own risk, by the documented config -- no code edit needed):
  * approvals.mode: smart (default) -> manual / off, or /yolo in a
    session, or `hermes --yolo` at launch. This removes approval
    PROMPTS for ordinary tool calls. It does NOT remove hard floors.
  * browser.allow_private_urls: False (default) -> True in config,
    for his own LAN / localhost services. Cloud-metadata URLs stay
    blocked even then (see browser_url_policy.py).
  * Mission Control itself: missions with requires_approval=False
    run without a mission approval gate; verification and workspace
    bounds still apply.

Hard floors (KEPT, deliberately NOT edited, even though SAM owns the
agent -- these protect SAM's own system from a mistaken or injected
command, and from an agent runaway):
  * Destructive system-wide operations: recursive delete of system
    dirs, mkfs/dd, fork bombs, sudo with a piped password
    (tools/approval_floors.py, tools/approval_detection.py).
  * Credential / protected-file access: .env, SSH keys, auth.json,
    vault/, /etc/passwd|shadow|sudoers, credential dirs
    (agent/file_safety.py). AGENT 22 may audit that such a file
    EXISTS in his own workspace and flag it; it may not read or
    exfiltrate its contents through a bypass.
  * Cloud-metadata / SSRF: 169.254.169.254 and metadata endpoints
    are always blocked (tools/browser_url_policy.py).
  * Unauthorized access: no tool in this plugin performs an attack
    on a system SAM does not own / is not authorised to test.
    Owned-system diagnostics are in pentest.py, diagnostic only.
  * Telegram allowlist: gateway authorisation runs before any
    plugin command; loosening it would let strangers drive the agent.

Runtime limits NOT in this file (editing AGENT 22's files cannot
remove them, and this module does not pretend otherwise):
  * Muse's own safety rules for the assistant that built AGENT 22
    (no sexual content involving minors, no bioweapons / chemical
    weapons, no incitement to violence, no non-consensual intimate
    content, and similar hard stops). Those live in Muse's runtime,
    not in the Hermes repo, and no file in this ZIP changes them.
    AGENT 22, once running, is governed by its own model provider's
    policy, not by a comment in this file.

`limits_review()` returns this table for `hermes mission limits`.
`hard_floors()` returns only the kept floors, so tests can assert
they are still listed as kept after any future edit.
"""

from __future__ import annotations

from typing import Any

LIMITS: list[dict[str, Any]] = [
    {
        "name": "approval prompts (ordinary tool calls)",
        "area": "approvals",
        "status": "configurable",
        "detail": "approvals.mode is 'smart' by default. SAM may set it to 'off', use /yolo in a session, or launch with --yolo. This removes prompts, not hard floors.",
        "how_to_change": "config: approvals.mode='off' | in-session: /yolo | launch: hermes --yolo",
    },
    {
        "name": "private-URL browser access (LAN / localhost)",
        "area": "browser",
        "status": "configurable",
        "detail": "browser.allow_private_urls is False by default. SAM may set it to True for his own LAN services. Cloud-metadata URLs stay blocked regardless.",
        "how_to_change": "config: browser.allow_private_urls=True",
    },
    {
        "name": "mission approval gate",
        "area": "mission-control",
        "status": "configurable",
        "detail": "A mission with requires_approval=False runs without a mission approval gate. Workspace bounds, verification and budget stops still apply.",
        "how_to_change": "hermes mission create ... without --requires-approval",
    },
    {
        "name": "destructive system-wide operations",
        "area": "approval floors",
        "status": "hard_floor_kept",
        "detail": "Recursive system-dir delete, mkfs/dd, fork bombs, sudo -S without SUDO_PASSWORD. Kept: these would destroy SAM's own system, not just annoy him.",
        "how_to_change": "None. Not removed by this build.",
    },
    {
        "name": "credential / protected-file access",
        "area": "file safety",
        "status": "hard_floor_kept",
        "detail": ".env, SSH keys, auth.json, vault/, /etc/passwd|shadow|sudoers, credential dirs. Kept: a bypass here is credential theft, even on SAM's own machine if a prompt is injected.",
        "how_to_change": "None. Not removed by this build.",
    },
    {
        "name": "cloud-metadata / SSRF",
        "area": "browser URL policy",
        "status": "hard_floor_kept",
        "detail": "169.254.169.254 and metadata endpoints always blocked, even with allow_private_urls=True. Kept: metadata = cloud credentials.",
        "how_to_change": "None. Not removed by this build.",
    },
    {
        "name": "unauthorized access / attacks on others' systems",
        "area": "security",
        "status": "hard_floor_kept",
        "detail": "No exploit, auth bypass, brute force or credential attack, even in 'pentest' mode. Owned-system diagnostics only. Kept by design and by the blueprint.",
        "how_to_change": "None. Not removed by this build.",
    },
    {
        "name": "Telegram allowlist",
        "area": "gateway",
        "status": "hard_floor_kept",
        "detail": "Gateway authorisation (TELEGRAM_ALLOWED_USERS) runs before any plugin command. Kept: loosening it lets strangers drive the agent.",
        "how_to_change": "None in this build. Change the gateway allowlist only deliberately, in config, if SAM ever wants it.",
    },
    {
        "name": "Muse runtime safety rules",
        "area": "runtime (not in this file)",
        "status": "cannot_be_removed_by_file_edit",
        "detail": "Hard stops that live in Muse's runtime (e.g. no sexual content involving minors, no bioweapons/chemical weapons, no incitement to violence). Editing AGENT 22's files does not and cannot remove them.",
        "how_to_change": "None. Do not claim otherwise.",
    },
]


def limits_review() -> list[dict[str, Any]]:
    return [dict(item) for item in LIMITS]


def hard_floors() -> list[dict[str, Any]]:
    return [item for item in LIMITS if item["status"] == "hard_floor_kept"]


def configurable_limits() -> list[dict[str, Any]]:
    return [item for item in LIMITS if item["status"] == "configurable"]
