"""CLI for the mission-control plugin: ``hermes mission <verb> ...``.

Wired by plugins/mission-control/__init__.py via
ctx.register_cli_command("mission", setup_fn, handler_fn), following the
plugin pattern in hermes_cli/main.py:_attach_plugin_cli_command: setup_fn
receives the ``mission`` parser and adds subparsers; each subcommand sets
its own func. Handlers take an argparse namespace and return an int exit
code, printing JSON so output is machine-checkable and never claims a
file exists unless it was created and verified (runner.build_report).

Default store location follows the repo rule (never hardcode ~/.hermes
in production code): the CLI resolves it at call time from
HERMES_HOME, falling back to ~/.hermes only when that env var is absent.
Tests pass --store explicitly, so they never touch a real home.
"""

from __future__ import annotations

import argparse
import json
import shlex
import os
import sys
from pathlib import Path
from typing import Any

try:
    from .audit import analyse_text_file, debug_run, extract_strings
    from .budget import BudgetLedger, Usage
    from .companion import companion_prompt, set_tone
    from .identity import IdentityStore, detect_model_from_config, render_banner, render_status
    from .memory import ProjectMemory
    from .mission import MissionStore, Step
    from .runner import build_report, resolve_workspace, run_mission
    from .pentest import pentest_owned_target
    from .briefing import generate_briefing
    from .browser import run_browser_smoke
    from .reflection import ReflectionLog, format_reflection, reflect_on_correction, reflect_on_failure
    from .discord import DiscordConfig, discord_health, handle_discord_command
    from .platforms import IdentityMapping, all_health, dispatch, health
    from .whatsapp import handle_whatsapp_command, whatsapp_health
    from .dashboard import dashboard_data, select_model_live, write_dashboard
    from .debugloop import run_debug_loop
    from .limits import limits_review
    from .specialists import install_skill, propose_skill, review_change, specialist_plan
    from .soul import full_persona, heart_text, soul_text
    from .security import ctf_decode, dependency_audit, network_diagnostics, scoped_security_report, static_malware_profile
except ImportError:  # loaded as standalone files in tests
    from audit import analyse_text_file, debug_run, extract_strings
    from budget import BudgetLedger, Usage
    from companion import companion_prompt, set_tone
    from identity import IdentityStore, detect_model_from_config, render_banner, render_status
    from memory import ProjectMemory
    from mission import MissionStore, Step
    from runner import build_report, resolve_workspace, run_mission
    from pentest import pentest_owned_target
    from briefing import generate_briefing
    from browser import run_browser_smoke
    from reflection import ReflectionLog, format_reflection, reflect_on_correction, reflect_on_failure
    from discord import DiscordConfig, discord_health, handle_discord_command
    from platforms import IdentityMapping, all_health, dispatch, health
    from whatsapp import handle_whatsapp_command, whatsapp_health
    from dashboard import dashboard_data, select_model_live, write_dashboard
    from debugloop import run_debug_loop
    from limits import limits_review
    from specialists import install_skill, propose_skill, review_change, specialist_plan
    from soul import full_persona, heart_text, soul_text
    from security import ctf_decode, dependency_audit, network_diagnostics, scoped_security_report, static_malware_profile


def _default_store() -> Path:
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(home) / "missions"


def _store_from_args(args: Any) -> MissionStore:
    return MissionStore(Path(args.store) if getattr(args, "store", None) else _default_store())


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _cmd_create(args: Any) -> int:
    store = _store_from_args(args)
    steps = []
    for spec in args.step or []:
        # spec: name=cmd1,cmd2,... ; a step with no command is a plan-only step
        if "=" in spec:
            name, cmd = spec.split("=", 1)
            command = shlex.split(cmd)
        else:
            name, command = spec, []
        steps.append(Step(name=name, command=command, idempotent=args.idempotent))
    mission = store.create(
        goal=args.goal,
        plan=args.plan or [],
        steps=steps,
        max_steps=args.max_steps,
        max_retries=args.max_retries,
        requires_approval=args.require_approval,
    )
    _print(mission.to_dict())
    return 0


def _cmd_run(args: Any) -> int:
    store = _store_from_args(args)
    mission = run_mission(store, args.mission_id, args.workspace, sleep_fn=lambda _s: None)
    _print(build_report(mission))
    return 0 if mission.status == "completed" else 1


def _cmd_status(args: Any) -> int:
    store = _store_from_args(args)
    _print(store.get(args.mission_id).to_dict())
    return 0


def _cmd_list(args: Any) -> int:
    store = _store_from_args(args)
    _print([m.to_dict() for m in store.list()])
    return 0


def _cmd_pause(args: Any) -> int:
    _print(_store_from_args(args).pause(args.mission_id).to_dict())
    return 0


def _cmd_resume(args: Any) -> int:
    _print(_store_from_args(args).resume(args.mission_id).to_dict())
    return 0


def _cmd_cancel(args: Any) -> int:
    _print(_store_from_args(args).cancel(args.mission_id).to_dict())
    return 0


def _cmd_approve(args: Any) -> int:
    _print(_store_from_args(args).approve(args.mission_id).to_dict())
    return 0


def _cmd_report(args: Any) -> int:
    _print(build_report(_store_from_args(args).get(args.mission_id)))
    return 0


def _cmd_budget(args: Any) -> int:
    ledger = BudgetLedger(
        Path(args.store) if args.store else _default_store(),
        max_task_cost_usd=args.max_task_cost,
        daily_budget_usd=args.daily_budget,
    )
    usage = Usage(
        input_tokens=args.input_tokens,
        output_tokens=args.output_tokens,
        estimated_cost_usd=args.cost,
    )
    ledger.record(args.task_id, usage)
    _print(
        {
            "task_id": args.task_id,
            "task_total_estimated_usd": ledger.task_total(args.task_id),
            "daily_total_estimated_usd": ledger.daily_total(),
            "is_estimate": True,
        }
    )
    return 0


def _cmd_audit(args: Any) -> int:
    workspace = resolve_workspace(args.workspace)
    if args.mode == "strings":
        result = extract_strings(args.target, workspace, authorised=args.i_own_this)
    elif args.mode == "debug":
        result = debug_run(args.target, workspace, authorised=args.i_own_this, args=args.extra or [])
    else:
        result = analyse_text_file(args.target, workspace, authorised=args.i_own_this)
    _print(result)
    return 0


def _add_common(parser: Any) -> None:
    parser.add_argument("--store", default=None, help="Mission store directory (default: $HERMES_HOME/missions)")


def _add_id(parser: Any) -> None:
    parser.add_argument("mission_id", help="Mission id from `mission create`")



def _identity_store_from_args(args: Any) -> IdentityStore:
    return IdentityStore(Path(args.store) if getattr(args, "store", None) else _default_store())


def _cmd_soul(args: Any) -> int:
    part = getattr(args, "part", "all")
    if part == "soul":
        print(soul_text())
    elif part == "heart":
        print(heart_text())
    else:
        print(full_persona())
    return 0


def _cmd_debug(args: Any) -> int:
    fixer = None
    if getattr(args, "fix_script", None):
        try:
            from .audit import debug_run as _debug_run
        except ImportError:
            from audit import debug_run as _debug_run
        def fixer(attempt, record, _ws=args.workspace, _script=args.fix_script):
            _debug_run(_script, _ws, authorised=True)
    _print(run_debug_loop(args.command, args.workspace, fixer=fixer, max_attempts=args.max_attempts, timeout=args.timeout))
    return 0


def _cmd_dashboard(args: Any) -> int:
    store_dir = Path(args.store) if args.store else _default_store()
    if args.output:
        _print({"dashboard_file": str(write_dashboard(store_dir, args.output))})
    else:
        _print(dashboard_data(store_dir))
    return 0


def _cmd_cost(args: Any) -> int:
    store_dir = Path(args.store) if args.store else _default_store()
    ledger = BudgetLedger(store_dir)
    _print({"estimated_spend_today_usd": ledger.daily_total(), "cost_is_estimate": True, "note": "Estimates only; no live provider billing."})
    return 0


def _cmd_briefing(args: Any) -> int:
    store_dir = Path(args.store) if args.store else _default_store()
    text = generate_briefing(store_dir)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        _print({"briefing_file": args.output})
    else:
        print(text)
    return 0


def _cmd_specialists(args: Any) -> int:
    verb = args.specialist_command
    if verb == "plan":
        _print(specialist_plan(args.goal))
    elif verb == "review":
        _print(review_change(args.file or [], checks_passed=args.checks_passed, secrets_found=args.secrets_found))
    elif verb == "propose":
        _print({"draft": str(propose_skill(args.name, args.description, args.body or "", args.proposals_dir))})
    elif verb == "install":
        _print({"installed": str(install_skill(args.name, args.proposals_dir, args.skills_dir, approved=args.approve))})
    return 0


def _cmd_reflect(args: Any) -> int:
    store_dir = Path(args.store) if getattr(args, "store", None) else _default_store()
    log = ReflectionLog(store_dir)
    if args.correction:
        reflection = reflect_on_correction(args.previous or "", args.correction)
        log.add(reflection, mission_id=args.mission_id or "", kind="correction")
    else:
        reflection = reflect_on_failure(args.error or "no error given", context=args.context or "")
        log.add(reflection, mission_id=args.mission_id or "", kind="failure")
    print(format_reflection(reflection))
    return 0


def _cmd_browser_smoke(args: Any) -> int:
    _print(run_browser_smoke(args.workspace))
    return 0


def _cmd_platforms(args: Any) -> int:
    store_dir = Path(args.store) if getattr(args, "store", None) else _default_store()
    verb = getattr(args, "platform_command", None)
    if verb == "health":
        if args.platform:
            if args.platform == "discord":
                _print(discord_health())
            elif args.platform == "whatsapp_cloud":
                _print(whatsapp_health())
            else:
                _print(health(args.platform))
        else:
            _print(all_health())
    elif verb == "map":
        mapping = IdentityMapping(store_dir)
        _print(mapping.add(args.platform, args.platform_user_id, args.agent_user, args.role))
    elif verb == "dispatch":
        result = dispatch(args.platform, args.platform_user_id, args.command, store_dir)
        _print(result)
    return 0


def _cmd_limits(args: Any) -> int:
    _print(limits_review())
    return 0


def _cmd_identity(args: Any) -> int:
    store = _identity_store_from_args(args)
    identity = store.load()
    detected = detect_model_from_config()
    _print(render_status(identity, detected["model"], detected["provider"]))
    return 0


def _cmd_banner(args: Any) -> int:
    store = _identity_store_from_args(args)
    identity = store.load()
    detected = detect_model_from_config()
    # Connection is "unknown" unless the caller measured it and passed it in.
    print(render_banner(identity, detected["model"], detected["provider"], args.connection_status))
    return 0


def _cmd_mode(args: Any) -> int:
    store = _identity_store_from_args(args)
    identity = store.set_mode(args.mode)
    if getattr(args, "tone", None):
        identity = store.save(set_tone(identity, args.tone))
    _print(identity.to_dict())
    _print({"companion_prompt": companion_prompt(identity)})
    return 0


def _cmd_memory(args: Any) -> int:
    mem = ProjectMemory(Path(args.store) if args.store else _default_store())
    verb = args.memory_command
    if verb == "add":
        _print(mem.add(args.key, args.value, args.source or "").to_dict())
    elif verb == "get":
        fact = mem.get(args.key)
        _print(fact.to_dict() if fact else {"found": False, "key": args.key})
    elif verb == "list":
        _print([f.to_dict() for f in mem.list()])
    elif verb == "correct":
        _print(mem.correct(args.key, args.value, args.source or "").to_dict())
    elif verb == "delete":
        _print({"deleted": mem.delete(args.key), "key": args.key})
    elif verb == "export":
        _print(mem.export())
    return 0


def _cmd_security(args: Any) -> int:
    verb = args.security_command
    if verb == "dependency":
        _print(dependency_audit(args.workspace, authorised=args.i_own_this))
    elif verb == "profile":
        _print(static_malware_profile(args.target, args.workspace, authorised=args.i_own_this))
    elif verb == "diag":
        _print(network_diagnostics(args.host, args.port or [], authorised=args.i_own_this))
    elif verb == "ctf":
        _print({"method": args.method, "decoded": ctf_decode(args.text, args.method)})
    elif verb == "report":
        _print(scoped_security_report(args.target, args.workspace, authorised=args.i_own_this, checks=args.check or ["static"]))
    elif verb == "pentest":
        _print(pentest_owned_target(args.host, ports=args.port or [], authorised=args.i_own_this, attack_type=args.attack_type, workspace=args.workspace, use_https=args.https))
    return 0


def build_mission_parser(parser: Any) -> None:
    """setup_fn for ctx.register_cli_command: parser is the `mission` parser."""
    sub = parser.add_subparsers(dest="mission_command")

    p = sub.add_parser("create", help="Create a mission")
    p.add_argument("goal", help="Mission goal, in plain words")
    p.add_argument("--plan", action="append", default=[], help="Plan line (repeatable)")
    p.add_argument("--step", action="append", default=[], help="Step as name=cmd,arg,... (repeatable)")
    p.add_argument("--idempotent", action="store_true", help="Mark steps idempotent (safe to auto-retry)")
    p.add_argument("--max-steps", type=int, default=50)
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--require-approval", action="store_true", help="Start in waiting_for_approval")
    _add_common(p)
    p.set_defaults(func=_cmd_create)

    p = sub.add_parser("run", help="Run or resume a mission inside a workspace")
    _add_id(p)
    p.add_argument("--workspace", required=True, help="Workspace root; steps and checks stay inside it")
    _add_common(p)
    p.set_defaults(func=_cmd_run)

    for name, func, help_text in [
        ("status", _cmd_status, "Show a mission"),
        ("list", _cmd_list, "List missions"),
        ("pause", _cmd_pause, "Pause a mission"),
        ("resume", _cmd_resume, "Resume a paused mission"),
        ("cancel", _cmd_cancel, "Cancel a mission"),
        ("approve", _cmd_approve, "Approve a waiting_for_approval mission"),
        ("report", _cmd_report, "Final report for a mission"),
    ]:
        p = sub.add_parser(name, help=help_text)
        if name != "list":
            _add_id(p)
        _add_common(p)
        p.set_defaults(func=func)

    p = sub.add_parser("budget", help="Record estimated usage against task/daily limits")
    p.add_argument("task_id")
    p.add_argument("--input-tokens", type=int, default=0)
    p.add_argument("--output-tokens", type=int, default=0)
    p.add_argument("--cost", type=float, required=True, help="Estimated cost in USD")
    p.add_argument("--max-task-cost", type=float, default=None)
    p.add_argument("--daily-budget", type=float, default=None)
    _add_common(p)
    p.set_defaults(func=_cmd_budget)

    p = sub.add_parser(
        "audit",
        help="Audit YOUR OWN file in the workspace (analyse / strings / debug). "
        "Requires --i-own-this; network targets and unauthorised targets are refused.",
    )
    p.add_argument("target", help="File path inside --workspace (no URLs, no outside paths)")
    p.add_argument("--workspace", required=True)
    p.add_argument("--mode", choices=["analyse", "strings", "debug"], default="analyse")
    p.add_argument("--extra", nargs="*", default=[], help="Extra argv for --mode debug")
    p.add_argument(
        "--i-own-this",
        action="store_true",
        help="Confirm you own or are authorised to test this target",
    )
    p.set_defaults(func=_cmd_audit)


    p = sub.add_parser("soul", help="Print AGENT 22's soul and heart")
    p.add_argument("--part", choices=["all", "soul", "heart"], default="all")
    p.set_defaults(func=_cmd_soul)

    p = sub.add_parser("debug", help="Bounded self-debug loop: run, fix, re-run (max attempts)")
    p.add_argument("command", nargs="+", help="argv command to run in the workspace")
    p.add_argument("--workspace", required=True)
    p.add_argument("--fix-script", default=None, help="Own .py in workspace, run on failure to fix (debug_run, authorised)")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--timeout", type=float, default=120.0)
    p.set_defaults(func=_cmd_debug)

    p = sub.add_parser("dashboard", help="Cost/mission dashboard snapshot (static HTML or JSON)")
    p.add_argument("--output", default=None, help="Write static HTML dashboard to this file")
    _add_common(p)
    p.set_defaults(func=_cmd_dashboard)

    p = sub.add_parser("cost", help="Estimated spend today (estimates only)")
    _add_common(p)
    p.set_defaults(func=_cmd_cost)

    p = sub.add_parser("briefing", help="Daily phone briefing text from store data")
    p.add_argument("--output", default=None)
    _add_common(p)
    p.set_defaults(func=_cmd_briefing)

    spec = sub.add_parser("specialists", help="Specialist roles and skill factory (propose = draft only)")
    spec_sub = spec.add_subparsers(dest="specialist_command", required=True)
    sp = spec_sub.add_parser("plan"); sp.add_argument("goal"); sp.set_defaults(func=_cmd_specialists)
    sp = spec_sub.add_parser("review"); sp.add_argument("--file", action="append", default=[]); sp.add_argument("--checks-passed", action="store_true"); sp.add_argument("--secrets-found", action="store_true"); sp.set_defaults(func=_cmd_specialists)
    sp = spec_sub.add_parser("propose"); sp.add_argument("name"); sp.add_argument("description"); sp.add_argument("--body", default=""); sp.add_argument("--proposals-dir", required=True); sp.set_defaults(func=_cmd_specialists)
    sp = spec_sub.add_parser("install"); sp.add_argument("name"); sp.add_argument("--proposals-dir", required=True); sp.add_argument("--skills-dir", required=True); sp.add_argument("--approve", action="store_true"); sp.set_defaults(func=_cmd_specialists)

    plat = sub.add_parser("platforms", help="Multi-platform core: health, identity mapping, dispatch")
    plat_sub = plat.add_subparsers(dest="platform_command", required=True)
    pp = plat_sub.add_parser("health"); pp.add_argument("--platform", choices=["telegram", "discord", "whatsapp_cloud"], default=None); pp.set_defaults(func=_cmd_platforms)
    pp = plat_sub.add_parser("map"); pp.add_argument("--platform", required=True); pp.add_argument("--platform-user-id", required=True); pp.add_argument("--agent-user", default="SAM"); pp.add_argument("--role", choices=["owner", "admin", "user"], required=True); _add_common(pp); pp.set_defaults(func=_cmd_platforms)
    pp = plat_sub.add_parser("dispatch"); pp.add_argument("--platform", required=True); pp.add_argument("--platform-user-id", required=True); pp.add_argument("--command", required=True); _add_common(pp); pp.set_defaults(func=_cmd_platforms)

    p = sub.add_parser("reflect", help="Reflect on a mistake politely: failure or user correction, saved to the reflection log")
    p.add_argument("--error", default=None)
    p.add_argument("--previous", default=None)
    p.add_argument("--correction", default=None)
    p.add_argument("--context", default=None)
    p.add_argument("--mission-id", default=None)
    _add_common(p)
    p.set_defaults(func=_cmd_reflect)

    p = sub.add_parser("browser-smoke", help="Browser smoke test: example.com title + screenshot via browser_exec (owner/admin via Telegram dispatch)")
    p.add_argument("--workspace", required=True)
    p.set_defaults(func=_cmd_browser_smoke)

    p = sub.add_parser("limits", help="Review AGENT 22 limits: configurable vs hard floors kept vs runtime")
    p.set_defaults(func=_cmd_limits)

    p = sub.add_parser("identity", help="Show configured AGENT 22 identity and status (no hardcoded claims)")
    _add_common(p)
    p.set_defaults(func=_cmd_identity)

    p = sub.add_parser("banner", help="Print the clean AGENT 22 startup banner")
    p.add_argument("--connection-status", default="unknown (no live check performed)", help="Measured connection status only; default is unknown")
    _add_common(p)
    p.set_defaults(func=_cmd_banner)

    p = sub.add_parser("mode", help="Set mode: normal (default) or companion (opt-in, tone only)")
    p.add_argument("mode", choices=["normal", "companion"])
    p.add_argument("--tone", choices=["calm", "playful", "energetic", "supportive"], default=None)
    _add_common(p)
    p.set_defaults(func=_cmd_mode)

    mem = sub.add_parser("memory", help="Persistent project memory: add/get/list/correct/delete/export")
    mem_sub = mem.add_subparsers(dest="memory_command", required=True)
    mp = mem_sub.add_parser("add"); mp.add_argument("key"); mp.add_argument("value"); mp.add_argument("--source", default=""); _add_common(mp); mp.set_defaults(func=_cmd_memory)
    mp = mem_sub.add_parser("get"); mp.add_argument("key"); _add_common(mp); mp.set_defaults(func=_cmd_memory)
    mp = mem_sub.add_parser("list"); _add_common(mp); mp.set_defaults(func=_cmd_memory)
    mp = mem_sub.add_parser("correct"); mp.add_argument("key"); mp.add_argument("value"); mp.add_argument("--source", default=""); _add_common(mp); mp.set_defaults(func=_cmd_memory)
    mp = mem_sub.add_parser("delete"); mp.add_argument("key"); _add_common(mp); mp.set_defaults(func=_cmd_memory)
    mp = mem_sub.add_parser("export"); _add_common(mp); mp.set_defaults(func=_cmd_memory)

    sec = sub.add_parser("security", help="Security Research Mode (authorised scope only)")
    sec_sub = sec.add_subparsers(dest="security_command", required=True)
    sp = sec_sub.add_parser("dependency"); sp.add_argument("--workspace", required=True); sp.add_argument("--i-own-this", action="store_true"); sp.set_defaults(func=_cmd_security)
    sp = sec_sub.add_parser("profile"); sp.add_argument("target"); sp.add_argument("--workspace", required=True); sp.add_argument("--i-own-this", action="store_true"); sp.set_defaults(func=_cmd_security)
    sp = sec_sub.add_parser("diag"); sp.add_argument("host"); sp.add_argument("--port", type=int, action="append", default=[]); sp.add_argument("--i-own-this", action="store_true"); sp.set_defaults(func=_cmd_security)
    sp = sec_sub.add_parser("ctf"); sp.add_argument("method", choices=["base64", "hex", "rot13", "reverse"]); sp.add_argument("text"); sp.set_defaults(func=_cmd_security)
    sp = sec_sub.add_parser("report"); sp.add_argument("target"); sp.add_argument("--workspace", required=True); sp.add_argument("--check", action="append", default=[]); sp.add_argument("--i-own-this", action="store_true"); sp.set_defaults(func=_cmd_security)
    sp = sec_sub.add_parser("pentest"); sp.add_argument("host"); sp.add_argument("--port", type=int, action="append", default=[]); sp.add_argument("--workspace", default=None); sp.add_argument("--attack-type", default="diagnostic"); sp.add_argument("--https", action="store_true"); sp.add_argument("--i-own-this", action="store_true"); sp.set_defaults(func=_cmd_security)

    parser.set_defaults(func=lambda args: parser.print_help() or 0)


def main(argv: list[str] | None = None) -> int:
    """Standalone entry for tests and for `python -m` style invocation."""
    parser = argparse.ArgumentParser(prog="mission")
    build_mission_parser(parser)
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
