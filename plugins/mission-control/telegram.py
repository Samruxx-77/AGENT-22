"""Telegram /mission handler (plugin slash command, not a new core tool).

Registered by __init__.py via ctx.register_command("mission", handler).
The handler is a plain function ``handler(raw_args: str) -> str`` so it
can be tested without a live Telegram connection, gateway, or bot token.

Allowlist behaviour is NOT re-implemented here: the gateway's own
allowlist / authorisation (TELEGRAM_ALLOWED_USERS, gateway/authz_mixin)
runs before any plugin command is dispatched, so an unauthorised user
never reaches this handler. This handler only operates on missions in
the store directory derived from HERMES_HOME at call time (tests set
HERMES_HOME to a tmp dir), and it never prints secrets -- mission
records contain no secrets by construction (see mission.py).

Supported (all read/control, no new side effects beyond mission control):
  /mission status <id>   /mission list
  /mission pause <id>    /mission resume <id>   /mission cancel <id>
  /mission approve <id>  /mission report <id>
  /mission mode normal|companion
  /mission identity
Anything else returns a usage string, never a crash and never a secret.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from .budget import BudgetLedger
    from .identity import IdentityStore, detect_model_from_config, render_status
    from .mission import MissionStore
    from .runner import build_report, run_mission
except ImportError:  # loaded as standalone files in tests
    from budget import BudgetLedger
    from identity import IdentityStore, detect_model_from_config, render_status
    from mission import MissionStore
    from runner import build_report, run_mission

_USAGE = (
    "Usage: /mission status <id> | list | pause <id> | resume <id> | "
    "cancel <id> | approve <id> | report <id> | cost | mode normal|companion | identity\n"
    "Also: /plan <goal> | /run <id> | /cost | /report <id> | /help"
)


def _store_dir() -> Path:
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(home) / "missions"


def handle_mission_command(raw_args: str) -> str:
    """Dispatch one /mission command. Returns user-facing text, no secrets."""
    parts = (raw_args or "").strip().split()
    if not parts:
        return _USAGE
    verb, rest = parts[0].lower(), parts[1:]
    try:
        store = MissionStore(_store_dir())
        if verb == "list":
            missions = store.list()
            if not missions:
                return "No missions."
            return "\n".join(f"{m.mission_id}: {m.status} — {m.goal}" for m in missions)
        if verb == "identity":
            identity = IdentityStore(_store_dir()).load()
            detected = detect_model_from_config()
            return json.dumps(render_status(identity, detected["model"], detected["provider"]), indent=2)
        if verb == "cost":
            ledger = BudgetLedger(_store_dir())
            return f"Estimated spend today: ${ledger.daily_total():.4f} USD (estimates only, from budget.json; no live provider billing)."
        if verb == "mode":
            if len(rest) != 1:
                return _USAGE
            identity = IdentityStore(_store_dir()).set_mode(rest[0])
            return f"Mode set to {identity.mode}. (Tone only; permissions unchanged.)"
        if verb in {"status", "pause", "resume", "cancel", "approve", "report"}:
            if len(rest) != 1:
                return _USAGE
            mission_id = rest[0]
            if verb == "status":
                mission = store.get(mission_id)
                return json.dumps(mission.to_dict(), indent=2, default=str)
            if verb == "pause":
                mission = store.pause(mission_id)
            elif verb == "resume":
                mission = store.resume(mission_id)
            elif verb == "cancel":
                mission = store.cancel(mission_id)
            elif verb == "approve":
                mission = store.approve(mission_id)
            else:
                return json.dumps(build_report(store.get(mission_id)), indent=2, default=str)
            return f"Mission {mission.mission_id} is now {mission.status}."
        return _USAGE
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception as exc:  # never leak internals or secrets to a chat
        return f"Error: {type(exc).__name__}"


HELP_TEXT = (
    "AGENT 22 commands:\n"
    "/plan <goal> — create a mission (returns its id)\n"
    "/run <id> — run a mission in HERMES_WORKSPACE (or current dir)\n"
    "/mission status|list|pause|resume|cancel|approve|report|cost|mode|identity\n"
    "/cost — estimated spend today\n"
    "/report <id> — verification report for a mission\n"
    "/help — this list\n"
    "Gateway allowlist runs first; no command here bypasses it, and no command prints secrets."
)


def handle_plan_command(raw_args: str) -> str:
    """Create a mission from a goal. Returns its id; steps are added later via the mission API/CLI."""
    goal = (raw_args or "").strip()
    if not goal:
        return "Usage: /plan <goal>"
    try:
        mission = MissionStore(_store_dir()).create(goal=goal)
        return f"Mission created: {mission.mission_id} — {mission.goal}"
    except Exception as exc:
        return f"Error: {type(exc).__name__}"


def handle_run_command(raw_args: str) -> str:
    """Run a mission id in the workspace from HERMES_WORKSPACE (tests) or the current directory."""
    mission_id = (raw_args or "").strip().split()[0] if (raw_args or "").strip() else ""
    if not mission_id:
        return "Usage: /run <id>"
    try:
        store = MissionStore(_store_dir())
        workspace = os.environ.get("HERMES_WORKSPACE") or os.getcwd()
        mission = run_mission(store, mission_id, workspace, sleep_fn=lambda s: None)
        return f"Mission {mission.mission_id} finished: {mission.status}."
    except Exception as exc:
        return f"Error: {type(exc).__name__}"


def handle_cost_command(raw_args: str) -> str:
    ledger = BudgetLedger(_store_dir())
    return f"Estimated spend today: ${ledger.daily_total():.4f} USD (estimates only)."


def handle_report_command(raw_args: str) -> str:
    mission_id = (raw_args or "").strip().split()[0] if (raw_args or "").strip() else ""
    if not mission_id:
        return "Usage: /report <id>"
    try:
        return json.dumps(build_report(MissionStore(_store_dir()).get(mission_id)), indent=2, default=str)
    except Exception as exc:
        return f"Error: {type(exc).__name__}"


def handle_help_command(raw_args: str = "") -> str:
    return HELP_TEXT
