"""Workspace-bounded mission execution + verification (P0).

Security posture, deliberately narrow (blueprint §13):
  * Steps run with NO shell (argv list only), cwd forced to the workspace,
    a per-step timeout, and an environment stripped of credential-looking
    variables unless the caller explicitly allowlists them. This runner
    does NOT bypass Hermes' own approval / file-safety / browser-URL
    floors -- it is an extra, smaller boundary for mission steps, and
    the terminal tool's own guards still apply when the agent uses it.
  * Every output path a verification check touches must resolve inside
    the workspace (symlinks resolved). ``..`` escapes are refused.
  * Protected basenames inside the workspace (.env files, auth.json,
    .ssh) are refused as verification targets, matching the spirit of
    agent/file_safety.py without duplicating its full denylist.
  * Cancellation is cooperative and checked before every step and
    before recording a side-effecting result, by re-reading the store.
  * A step that already ran is never auto-retried unless it is marked
    idempotent. A failed step on a non-idempotent step ends the mission
    as failed, with the error recorded -- never silently re-run.
  * A mission is marked completed ONLY if every verification check
    passes. Verification failure => failed, with evidence in the report.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from .mission import Mission, MissionStore, backoff_seconds
except ImportError:  # loaded as a standalone file in tests
    from mission import Mission, MissionStore, backoff_seconds

PROTECTED_BASENAMES = {".env", ".env.local", ".env.production", "auth.json"}
PROTECTED_DIRS = {".ssh", ".git", ".aws", ".gnupg"}

_CREDENTIAL_ENV_HINTS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "CREDENTIAL")


class RunnerError(Exception):
    """Base runner error."""


class WorkspaceViolation(RunnerError):
    """A path or command would escape the workspace or touch protected data."""


def resolve_workspace(path: str | Path) -> Path:
    workspace = Path(path).expanduser().resolve()
    if not workspace.is_dir():
        raise WorkspaceViolation(f"workspace is not an existing directory: {path}")
    return workspace


def assert_inside(workspace: Path, target: str | Path) -> Path:
    """Resolve target against the workspace and refuse escapes / protected paths."""
    raw = Path(target)
    resolved = (workspace / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError:
        raise WorkspaceViolation(f"path escapes workspace: {target}")
    if resolved.name in PROTECTED_BASENAMES:
        raise WorkspaceViolation(f"protected file refused as a target: {target}")
    if any(part in PROTECTED_DIRS for part in resolved.relative_to(workspace).parts):
        raise WorkspaceViolation(f"protected directory refused as a target: {target}")
    return resolved


def safe_env(allow_env: list[str] | None = None) -> dict[str, str]:
    """Minimal environment: PATH/LANG/HOME only, plus explicit allowlist.

    Credential-looking variables (TOKEN/KEY/SECRET/PASSWORD/CREDENTIAL)
    are stripped even if allowlisted by accident -- an explicit allowlist
    entry must name a non-credential variable to take effect.
    """
    import os

    env: dict[str, str] = {}
    for key in ("PATH", "LANG", "LC_ALL", "HOME"):
        if key in os.environ:
            env[key] = os.environ[key]
    for key in allow_env or []:
        upper = key.upper()
        if any(hint in upper for hint in _CREDENTIAL_ENV_HINTS):
            continue
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _is_transient(exit_code: int | None, stderr: str) -> bool:
    """Tiny, explicit transient classifier. Unknown errors are NOT transient."""
    if exit_code == 124:  # timeout, from our own timeout handling below
        return True
    lowered = (stderr or "").lower()
    return any(
        token in lowered
        for token in ("timed out", "timeout", "connection reset", "temporarily unavailable", "rate limit")
    )


def verify_checks(checks: list[dict[str, Any]], workspace: Path) -> list[dict[str, Any]]:
    """Evaluate verification checks. Returns one evidence dict per check."""
    evidence: list[dict[str, Any]] = []
    for check in checks:
        kind = check.get("type")
        try:
            if kind == "file_exists":
                path = assert_inside(workspace, check["path"])
                passed = path.is_file()
                detail = f"file_exists {path.name}: {passed}"
            elif kind == "file_nonempty":
                path = assert_inside(workspace, check["path"])
                passed = path.is_file() and path.stat().st_size > 0
                detail = f"file_nonempty {path.name}: {passed}"
            elif kind == "file_contains":
                path = assert_inside(workspace, check["path"])
                text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
                passed = check.get("text", "") in text
                detail = f"file_contains {path.name}: {passed}"
            elif kind == "step_succeeded":
                passed = bool(check.get("passed", False))
                detail = f"step_succeeded: {passed}"
            else:
                passed = False
                detail = f"unknown check type: {kind!r}"
        except (WorkspaceViolation, KeyError, OSError) as exc:
            passed = False
            detail = f"check error: {exc}"
        evidence.append({"check": check, "passed": passed, "detail": detail})
    return evidence


def run_step(
    command: list[str],
    workspace: Path,
    timeout_seconds: int = 120,
    allow_env: list[str] | None = None,
) -> dict[str, Any]:
    """Run one argv-list step. Shell strings are refused outright."""
    if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
        raise RunnerError("step command must be a non-empty list of strings (no shell string)")
    try:
        proc = subprocess.run(
            command,
            cwd=str(workspace),
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            env=safe_env(allow_env),
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "stdout": exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            "stderr": exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            "timed_out": True,
        }
    except OSError as exc:
        return {"exit_code": 127, "stdout": "", "stderr": str(exc), "timed_out": False}


def build_report(mission: Mission) -> dict[str, Any]:
    """Final report: summary, deliverables, verification, cost (labelled)."""
    verification = []
    for result in mission.results:
        verification.extend(result.get("verification", []))
    all_verified = all(v.get("passed") for v in verification) if verification else False
    return {
        "mission_id": mission.mission_id,
        "goal": mission.goal,
        "status": mission.status,
        "steps_completed": sum(1 for r in mission.results if r.get("exit_code") == 0),
        "steps_total": len(mission.steps),
        "verification": verification,
        "verification_passed": all_verified,
        "deliverable_paths": [r.get("step") for r in mission.results],
        "remaining_issues": mission.error_summary,
        "estimated_cost_usd": mission.usage.get("estimated_cost_usd"),
        "cost_is_estimate": mission.usage.get("is_estimate", True),
        "completed_at": mission.updated_at,
    }


def run_mission(
    store: MissionStore,
    mission_id: str,
    workspace: str | Path,
    sleep_fn: Callable[[float], None] = time.sleep,
    allow_env: list[str] | None = None,
) -> Mission:
    """Run (or resume) a mission to a terminal state, cooperatively.

    Resume rule: steps already recorded as successful are NOT re-run --
    that is what makes restart safe for non-idempotent steps. A paused or
    cancelled mission stops before starting any new step.
    """
    workspace = resolve_workspace(workspace)
    mission = store.get(mission_id)
    if mission.is_terminal():
        return mission
    if len(mission.steps) > mission.max_steps:
        mission.transition("failed")
        mission.error_summary = f"step limit exceeded: {len(mission.steps)} > {mission.max_steps}"
        return store.save(mission)
    if mission.deadline_iso:
        try:
            deadline = datetime.fromisoformat(mission.deadline_iso)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > deadline:
                mission.transition("failed")
                mission.error_summary = "deadline exceeded before completion"
                return store.save(mission)
        except ValueError:
            mission.transition("failed")
            mission.error_summary = "deadline_iso is not a valid ISO timestamp"
            return store.save(mission)

    # queued/planning/paused -> running (resume of a paused mission lands here too)
    if mission.status in {"queued", "planning", "paused"}:
        mission.transition("running")
        mission = store.save(mission)
    elif mission.status == "waiting_for_approval":
        mission.error_summary = "mission is waiting for approval; run `mission approve` first"
        return mission

    completed_step_names = {r.get("step") for r in mission.results if r.get("exit_code") == 0}
    for index, step in enumerate(mission.steps):
        # Cooperative cancellation / pause: re-read from disk every step.
        fresh = store.get(mission_id)
        if fresh.status == "cancelled":
            return fresh
        if fresh.status == "paused":
            return fresh
        mission = fresh
        mission.current_step_index = index
        if step.name in completed_step_names:
            continue  # resume: never repeat a completed step

        attempts = 0
        last_result: dict[str, Any] | None = None
        while True:
            # Check cancellation again before each attempt / side effect.
            if store.get(mission_id).status == "cancelled":
                return store.get(mission_id)
            last_result = run_step(step.command, workspace, step.timeout_seconds, allow_env)
            transient = _is_transient(last_result["exit_code"], last_result["stderr"])
            if last_result["exit_code"] == 0 or not transient:
                break
            if not step.idempotent:
                break  # never auto-retry a step whose side effect may have happened
            attempts += 1
            if attempts > max(step.max_retries, mission.max_retries if step.max_retries == 0 else step.max_retries):
                break
            if attempts > 0:
                mission.transition("retrying")
                mission = store.save(mission)
                mission.transition("running")
                mission = store.save(mission)
            sleep_fn(backoff_seconds(attempts - 1))

        assert last_result is not None
        verification = verify_checks(
            step.verify + ([{"type": "step_succeeded", "passed": last_result["exit_code"] == 0}] if not step.verify else step.verify),
            workspace,
        )
        # When a step declares its own checks, those checks decide; the
        # synthetic step_succeeded check above is only added when none
        # were declared, so a declared check cannot be masked.
        result = {
            "step": step.name,
            "exit_code": last_result["exit_code"],
            "stdout": last_result["stdout"],
            "stderr": last_result["stderr"],
            "timed_out": last_result["timed_out"],
            "verification": verification,
        }
        mission = store.append_result(mission, result)
        if last_result["exit_code"] != 0:
            mission.transition("failed")
            mission.error_summary = (
                f"step {step.name!r} failed with exit {last_result['exit_code']}: "
                f"{(last_result['stderr'] or last_result['stdout'])[:300]}"
            )
            return store.save(mission)

    # All steps succeeded: completion requires verification to pass.
    mission = store.get(mission_id)
    all_checks = [v for r in mission.results for v in r.get("verification", [])]
    if all_checks and not all(v.get("passed") for v in all_checks):
        mission.transition("failed")
        mission.error_summary = "verification failed: not all checks passed; mission not marked completed"
        return store.save(mission)
    mission.transition("completed")
    mission.final_result = build_report(mission)
    return store.save(mission)
