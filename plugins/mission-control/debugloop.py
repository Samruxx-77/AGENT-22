"""Bounded self-debug loop: run -> fix -> re-run, with a hard stop.

This is the primitive that turns "audit found a bug" into "fixed and
verified", without a runaway loop and without pretending an AI fixed
something it did not:

  * Each attempt runs ONE argv command inside the workspace, via the
    same safe runner as missions (argv only, no shell strings, safe
    env, timeout, workspace bounds).
  * On failure, an optional fixer is called. The fixer is user code
    (a callable in tests, or a --fix-script .py in the workspace via
    the CLI, run with audit.debug_run). It may edit workspace files;
    it may not escape the workspace, and it gets the redacted failure.
  * The loop stops on first success, when there is no fixer, or after
    max_attempts (default 3). It never retries forever, never runs a
    different command than the one given, and never claims success
    unless the final run exited 0 AND all verification checks passed.
  * The report redacts secret-looking values from stderr/stdout, and
    records every attempt (exit code, truncated output) so a fix is
    auditable, not magical.

In real use the "fixer" is the agent/model editing code between runs;
this module is the harness that bounds and verifies that loop.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

try:
    from .runner import WorkspaceViolation, resolve_workspace, run_step, verify_checks
except ImportError:  # loaded as standalone files in tests
    from runner import WorkspaceViolation, resolve_workspace, run_step, verify_checks

_SECRET_RE = re.compile(r"(?i)(password|api[_-]?key|secret|token)\s*[:=]\s*\S+")


def _redact(text: str) -> str:
    return _SECRET_RE.sub(r"\1=[REDACTED]", text or "")


class DebugLoopError(Exception):
    """Base debug-loop error."""


def run_debug_loop(
    command: list[str],
    workspace: str | Path,
    fixer: Callable[[int, dict[str, Any]], Any] | None = None,
    max_attempts: int = 3,
    timeout: float = 120.0,
    verify: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run command, fixing between attempts, up to max_attempts."""
    if not command or not isinstance(command, list):
        raise DebugLoopError("command must be a non-empty argv list")
    if max_attempts < 1:
        raise DebugLoopError("max_attempts must be >= 1")
    ws = resolve_workspace(workspace)
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        result = run_step(command, ws, timeout_seconds=int(timeout))
        checks = verify_checks(verify or [], ws)
        verified = all(c.get("passed") for c in checks) if checks else result.get("exit_code") == 0
        record = {
            "attempt": attempt,
            "exit_code": result.get("exit_code"),
            "stdout": _redact(str(result.get("stdout", ""))[:2000]),
            "stderr": _redact(str(result.get("stderr", ""))[:2000]),
            "verified": verified,
        }
        attempts.append(record)
        if verified:
            return {"success": True, "attempts": attempts, "attempts_used": attempt, "fixed_by_loop": attempt > 1}
        if fixer is None or attempt == max_attempts:
            break
        try:
            fixer(attempt, record)
        except Exception as exc:
            attempts.append({"attempt": attempt, "fixer_error": f"{type(exc).__name__}: {_redact(str(exc))[:500]}"})
            break
    return {"success": False, "attempts": attempts, "attempts_used": len([a for a in attempts if "attempt" in a and isinstance(a.get("attempt"), int)]), "fixed_by_loop": False}
