"""Mission Control plugin (P0 + identity + security research, bounded).

Registers:
  * one CLI command, ``hermes mission ...``, via
    ctx.register_cli_command (no core file edited for the plugin);
  * one in-session slash command, ``/mission ...``, via
    ctx.register_command (gateway allowlist still runs first -- see
    telegram.py; unauthorised users never reach the handler).

The library modules (mission, router, budget, runner, audit, security,
identity, companion, memory) are stdlib-only, so they can be tested
without the full Hermes test environment.

Identity: this plugin does not set the agent's name by itself. The
agent's name and owner live in the identity layer (see
AGENT22_IDENTITY.md at the repo root, hermes_cli/default_soul.py and
agent/prompt_builder.py), and identity.py is the persisted, testable
copy of that configured identity.
"""

from __future__ import annotations

from .cli import build_mission_parser
from .telegram import handle_cost_command, handle_help_command, handle_mission_command, handle_plan_command, handle_report_command, handle_run_command


def register(ctx) -> None:
    """Plugin entry point, called by PluginManager with a PluginContext."""
    ctx.register_cli_command(
        "mission",
        "Mission Control: resumable missions, budgets, verification (P0)",
        build_mission_parser,
        None,
        description=(
            "Create, run, pause, resume, cancel and report bounded missions. "
            "Steps run inside a workspace only, with verification before "
            "completion and hard budget stops. See HERMES_ULTIMATE.md."
        ),
    )
    ctx.register_command(
        "mission",
        handle_mission_command,
        description="Mission Control: status, list, pause, resume, cancel, approve, report, cost, mode, identity",
        args_hint="<status|list|pause|resume|cancel|approve|report|cost|mode|identity> [id]",
    )
    for name, handler, desc, hint in (
        ("plan", handle_plan_command, "Create a mission from a goal", "<goal>"),
        ("run", handle_run_command, "Run a mission by id", "<id>"),
        ("cost", handle_cost_command, "Estimated spend today", ""),
        ("report", handle_report_command, "Verification report for a mission", "<id>"),
        ("help", handle_help_command, "AGENT 22 command list", ""),
    ):
        ctx.register_command(name, handler, description=desc, args_hint=hint)
