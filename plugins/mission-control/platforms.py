"""Shared multi-platform core for AGENT 22.

Architecture: ONE shared core (MissionStore, BudgetLedger, Identity,
Companion, Security) with thin platform adapters on top. Telegram is
the first interface; Discord and WhatsApp adapters (discord.py,
whatsapp.py in this plugin) call the SAME dispatch() below, so a
mission started on Telegram has the same mission_id and the same
state when checked from Discord or WhatsApp. No platform duplicates
mission logic, and no platform adapter is edited into the core.

Identity and authorization (the part that must never be shortcut):
  * A platform user is identified ONLY by their platform user id:
    Telegram user id, Discord user id, WhatsApp phone number (E.164).
    A display name, username or profile name is untrusted display
    data and is NEVER used to authorize. Tests assert a spoofed
    display name ("SAM") with a different id is denied.
  * IdentityMapping maps (platform, platform_user_id) -> (agent_user,
    role). Roles: owner > admin > user. Query commands (status, list,
    report, cost, help, identity) need any mapped role; control
    commands (plan, run, pause, resume, cancel, approve, mode) need
    owner or admin. Unmapped users get a denial, not a partial answer.
  * Authorization happens in dispatch() BEFORE any mission handler
    runs, for every platform identically. Platform adapters add their
    own extra checks (Discord guild/channel allowlists, WhatsApp
    phone allowlist) on top, never instead.

Health and graceful failure:
  * health(platform) checks only the PRESENCE of required env vars
    (never their values, never prints them). Missing config means
    status "not_configured" and a list of what is missing -- the
    adapter does not crash, and dispatch() (core logic) is unaffected,
    because core and gateway readiness are separate concerns: a
    gateway that is not configured simply cannot receive messages,
    it does not corrupt shared state.
  * No API key or token ever appears in a health report, a dispatch
    response, or a log line from this module. Tests set dummy tokens
    and assert they do not appear in output.

Platforms supported by this core:
  * telegram: first interface, already implemented in telegram.py.
    Required env: TELEGRAM_BOT_TOKEN (presence only).
  * discord: Phase 2, discord.py. Required env: DISCORD_BOT_TOKEN.
    Reuses the repo's existing Discord adapter (plugins/platforms/
    discord, discord.py, slash commands, role-based auth) for the
    real gateway; this plugin's discord.py is the mission-control
    command layer on top of that adapter, not a second Discord client.
  * whatsapp_cloud: Phase 3, whatsapp.py. Required env:
    WHATSAPP_CLOUD_PHONE_NUMBER_ID, WHATSAPP_CLOUD_ACCESS_TOKEN.
    Reuses the repo's existing WhatsApp Cloud adapter
    (plugins/platforms/whatsapp_cloud, official Meta Cloud API) for
    the real gateway; this plugin's whatsapp.py is the mission-control
    command layer + webhook verification helpers, not a second client.
    The older WhatsApp Web bridge (plugins/platforms/whatsapp, Node.js
    Baileys) is NOT used: the Cloud API is the maintainable, official
    route, as specified.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from .telegram import handle_cost_command, handle_help_command, handle_mission_command, handle_plan_command, handle_report_command, handle_run_command
except ImportError:  # loaded as standalone files in tests
    from telegram import handle_cost_command, handle_help_command, handle_mission_command, handle_plan_command, handle_report_command, handle_run_command

ROLE_RANK = {"user": 1, "admin": 2, "owner": 3}
QUERY_COMMANDS = {"status", "list", "report", "cost", "help", "identity", "reflect"}
CONTROL_COMMANDS = {"plan", "run", "pause", "resume", "cancel", "approve", "mode", "browser-smoke"}

PLATFORM_REQUIRED_ENV: dict[str, list[str]] = {
    "telegram": ["TELEGRAM_BOT_TOKEN"],
    "discord": ["DISCORD_BOT_TOKEN"],
    "whatsapp_cloud": ["WHATSAPP_CLOUD_PHONE_NUMBER_ID", "WHATSAPP_CLOUD_ACCESS_TOKEN"],
}


class PlatformError(Exception):
    """Base platform error."""


class NotAuthorized(PlatformError):
    """Platform user is not mapped, or lacks the role for the command."""


class IdentityMapping:
    """JSON mapping (platform, platform_user_id) -> (agent_user, role)."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "platform_identities.json"

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        raw = self.path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, platform: str, platform_user_id: str, agent_user: str, role: str) -> dict[str, Any]:
        if role not in ROLE_RANK:
            raise PlatformError(f"unknown role: {role!r}")
        if not platform_user_id or not str(platform_user_id).strip():
            raise PlatformError("platform_user_id must not be empty (display names are never used)")
        data = self._load()
        key = f"{platform}:{platform_user_id}"
        data[key] = {"platform": platform, "platform_user_id": str(platform_user_id), "agent_user": agent_user, "role": role}
        self._save(data)
        return data[key]

    def get(self, platform: str, platform_user_id: str) -> dict[str, Any] | None:
        return self._load().get(f"{platform}:{platform_user_id}")

    def authorize(self, platform: str, platform_user_id: str, command: str) -> dict[str, Any]:
        """Authorize by id only. Display names are not an argument here."""
        mapping = self.get(platform, platform_user_id)
        if mapping is None:
            raise NotAuthorized(f"unmapped {platform} user: authorization denied")
        verb = command.strip().split()[0].lower() if command.strip() else ""
        if verb in CONTROL_COMMANDS and ROLE_RANK[mapping["role"]] < ROLE_RANK["admin"]:
            raise NotAuthorized(f"role {mapping['role']} cannot run control command {verb!r}")
        if verb not in QUERY_COMMANDS and verb not in CONTROL_COMMANDS and verb != "mission":
            raise NotAuthorized(f"unknown command: {verb!r}")
        return mapping


def health(platform: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Gateway readiness: env presence only, values never printed."""
    env = env if env is not None else os.environ
    required = PLATFORM_REQUIRED_ENV.get(platform)
    if required is None:
        return {"platform": platform, "status": "unknown_platform", "configured": False, "missing": []}
    missing = [name for name in required if not env.get(name)]
    return {
        "platform": platform,
        "status": "ready" if not missing else "not_configured",
        "configured": not missing,
        "missing": missing,
        "note": "Token presence only; values are never printed or logged." if not missing else "Configure the missing env vars; the adapter will not crash while unconfigured.",
    }


def all_health(env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    return [health(platform, env) for platform in PLATFORM_REQUIRED_ENV]


def dispatch(
    platform: str,
    platform_user_id: str,
    command: str,
    store_dir: str | Path,
    mapping: IdentityMapping | None = None,
) -> dict[str, Any]:
    """Shared dispatch: authorize by id, then run the mission command.

    Returns {"ok": True, "response": str} or {"ok": False, "error": str}.
    The response never contains a secret. Store dir is shared across
    platforms, so mission ids are identical on every platform.
    """
    mapping = mapping or IdentityMapping(store_dir)
    try:
        who = mapping.authorize(platform, platform_user_id, command)
    except NotAuthorized as exc:
        return {"ok": False, "error": str(exc)}
    # Handlers resolve the store from HERMES_HOME; temporarily point
    # it at the shared store's parent (the home dir) for this call.
    store_path = Path(store_dir)
    home = store_path.parent if store_path.name == "missions" else store_path
    old_home, old_ws = os.environ.get("HERMES_HOME"), os.environ.get("HERMES_WORKSPACE")
    try:
        os.environ["HERMES_HOME"] = str(home)
        parts = command.strip().split(maxsplit=1)
        verb, rest = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
        if verb == "mission":
            response = handle_mission_command(rest)
        elif verb == "plan":
            response = handle_plan_command(rest)
        elif verb == "run":
            response = handle_run_command(rest)
        elif verb == "cost":
            response = handle_cost_command(rest)
        elif verb == "report":
            response = handle_report_command(rest)
        elif verb == "help":
            response = handle_help_command(rest)
        elif verb == "reflect":
            try:
                from reflection import ReflectionLog, format_reflection, reflect_on_failure
            except ImportError:
                from .reflection import ReflectionLog, format_reflection, reflect_on_failure
            _log = ReflectionLog(store_path)
            _reflection = reflect_on_failure(rest or "no error given")
            _log.add(_reflection, kind="failure")
            response = format_reflection(_reflection)
        elif verb == "browser-smoke":
            try:
                from browser import run_browser_smoke
            except ImportError:
                from .browser import run_browser_smoke
            import json as _json
            _ws = os.environ.get("HERMES_WORKSPACE") or os.getcwd()
            response = _json.dumps(run_browser_smoke(_ws), indent=2, default=str)
        else:
            return {"ok": False, "error": f"unknown command: {verb!r}"}
        return {"ok": True, "response": response, "agent_user": who["agent_user"], "role": who["role"]}
    finally:
        if old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = old_home
        if old_ws is None:
            os.environ.pop("HERMES_WORKSPACE", None)
        else:
            os.environ["HERMES_WORKSPACE"] = old_ws
