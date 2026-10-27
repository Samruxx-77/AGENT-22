"""Mission Control state model and persistence (P0, blueprint Feature A).

Stdlib only. No network, no provider calls, no secrets are stored here:
callers must never put API keys, tokens or passwords into a goal, plan or
step command, and step output is truncated before it is persisted.

State machine (blueprint states, all of them):
    queued -> planning -> running -> waiting_for_approval -> running ...
    running -> paused -> running (resume)
    running/paused/queued/planning/waiting_for_approval/retrying -> cancelled
    running -> retrying -> running (bounded, idempotent steps only)
    running -> completed (only after verification passes; see runner.py)
    running -> failed (limit hit, verification failed, non-retryable error)

Persistence is one JSON file per store directory, written atomically
(tmp file in the same directory + os.replace) so a process restart can
reload a mission without a half-written record. This deliberately reuses
no second database: the blueprint only asks for a new DB if demonstrated
necessary, and a JSON store is enough for single-owner P0 missions.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = (
    "queued",
    "planning",
    "running",
    "waiting_for_approval",
    "paused",
    "retrying",
    "completed",
    "failed",
    "cancelled",
)

# Explicit transitions. Anything not listed is rejected, never silently
# coerced, so a failed mission can never drift into "completed".
TRANSITIONS = {
    "queued": {"planning", "running", "waiting_for_approval", "cancelled", "failed"},
    "planning": {"running", "waiting_for_approval", "cancelled", "failed"},
    "running": {
        "waiting_for_approval",
        "paused",
        "retrying",
        "completed",
        "failed",
        "cancelled",
    },
    "waiting_for_approval": {"queued", "running", "cancelled", "failed"},
    "paused": {"running", "cancelled", "failed"},
    "retrying": {"running", "failed", "cancelled"},
    "completed": set(),
    "failed": {"queued"},  # manual re-queue only, via store.requeue(); not auto
    "cancelled": set(),
}

MAX_OUTPUT_CHARS = 4000


class MissionError(Exception):
    """Base error for mission state / store problems."""


class InvalidTransition(MissionError):
    """Raised when a requested state change is not in TRANSITIONS."""


class MissionNotFound(MissionError):
    """Raised when a mission id is unknown to the store."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def backoff_seconds(attempt: int, base_seconds: float = 1.0, cap_seconds: float = 60.0) -> float:
    """Bounded exponential backoff, pure function (no sleeping here).

    attempt is 0-based: 1.0, 2.0, 4.0 ... capped at cap_seconds.
    The runner sleeps via an injectable sleep function so tests never wait.
    """
    if attempt < 0:
        attempt = 0
    return min(float(cap_seconds), float(base_seconds) * (2.0 ** attempt))


@dataclass
class Step:
    """One bounded unit of work inside a mission.

    command must be a list of argv tokens (never a shell string) -- the
    runner refuses shell strings so a step cannot smuggle ``; rm -rf`` in.
    idempotent=False means: once it has run, it is NEVER auto-retried,
    because its side effect may already have happened (blueprint rule).
    verify is a list of checks evaluated by runner.verify_checks(); a
    mission is completed only if every check passes.
    """

    name: str
    command: list[str] = field(default_factory=list)
    idempotent: bool = False
    verify: list[dict[str, Any]] = field(default_factory=list)
    timeout_seconds: int = 120
    max_retries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Step":
        return cls(
            name=str(data.get("name", "")),
            command=list(data.get("command") or []),
            idempotent=bool(data.get("idempotent", False)),
            verify=list(data.get("verify") or []),
            timeout_seconds=int(data.get("timeout_seconds", 120)),
            max_retries=int(data.get("max_retries", 0)),
        )


@dataclass
class Mission:
    mission_id: str
    goal: str
    status: str = "queued"
    plan: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    current_step_index: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    approval_requests: list[dict[str, Any]] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(
        default_factory=lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "calls": 0,
            "estimated_cost_usd": 0.0,
            "is_estimate": True,
        }
    )
    final_result: dict[str, Any] | None = None
    error_summary: str = ""
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    deadline_iso: str | None = None
    max_steps: int = 50
    max_retries: int = 3
    requires_approval: bool = False

    def touch(self) -> None:
        self.updated_at = _utcnow_iso()

    def transition(self, new_status: str) -> None:
        if new_status not in STATUSES:
            raise InvalidTransition(f"unknown status: {new_status!r}")
        if new_status not in TRANSITIONS.get(self.status, set()):
            raise InvalidTransition(f"cannot move mission from {self.status} to {new_status}")
        self.status = new_status
        self.touch()

    def is_terminal(self) -> bool:
        return self.status in {"completed", "failed", "cancelled"}

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [s.to_dict() for s in self.steps]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Mission":
        return cls(
            mission_id=str(data["mission_id"]),
            goal=str(data.get("goal", "")),
            status=str(data.get("status", "queued")),
            plan=list(data.get("plan") or []),
            steps=[Step.from_dict(s) for s in (data.get("steps") or [])],
            current_step_index=int(data.get("current_step_index", 0)),
            results=list(data.get("results") or []),
            approval_requests=list(data.get("approval_requests") or []),
            budget=dict(data.get("budget") or {}),
            usage=dict(
                data.get("usage")
                or {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "calls": 0,
                    "estimated_cost_usd": 0.0,
                    "is_estimate": True,
                }
            ),
            final_result=data.get("final_result"),
            error_summary=str(data.get("error_summary", "")),
            created_at=str(data.get("created_at", _utcnow_iso())),
            updated_at=str(data.get("updated_at", _utcnow_iso())),
            deadline_iso=data.get("deadline_iso"),
            max_steps=int(data.get("max_steps", 50)),
            max_retries=int(data.get("max_retries", 3)),
            requires_approval=bool(data.get("requires_approval", False)),
        )


class MissionStore:
    """JSON-backed mission store. One file, atomic replace on every save."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "missions.json"

    def _load_all(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise MissionError("missions.json is corrupt: top level is not an object")
        return data

    def _save_all(self, data: dict[str, dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def create(
        self,
        goal: str,
        plan: list[str] | None = None,
        steps: list[Step] | None = None,
        budget: dict[str, Any] | None = None,
        max_steps: int = 50,
        max_retries: int = 3,
        deadline_iso: str | None = None,
        requires_approval: bool = False,
    ) -> Mission:
        if not goal or not goal.strip():
            raise MissionError("goal must not be empty")
        steps = list(steps or [])
        if len(steps) > max_steps:
            raise MissionError(f"mission has {len(steps)} steps, over max_steps={max_steps}")
        mission = Mission(
            mission_id=uuid.uuid4().hex[:16],
            goal=goal.strip(),
            plan=list(plan or []),
            steps=steps,
            budget=dict(budget or {}),
            max_steps=max_steps,
            max_retries=max_retries,
            deadline_iso=deadline_iso,
            requires_approval=requires_approval,
        )
        if requires_approval:
            mission.transition("waiting_for_approval")
            mission.approval_requests.append(
                {"reason": "mission requires approval before starting", "at": _utcnow_iso()}
            )
        data = self._load_all()
        data[mission.mission_id] = mission.to_dict()
        self._save_all(data)
        return mission

    def get(self, mission_id: str) -> Mission:
        data = self._load_all()
        if mission_id not in data:
            raise MissionNotFound(f"unknown mission: {mission_id}")
        return Mission.from_dict(data[mission_id])

    def list(self) -> list[Mission]:
        return [Mission.from_dict(d) for d in self._load_all().values()]

    def save(self, mission: Mission) -> Mission:
        mission.touch()
        data = self._load_all()
        if mission.mission_id not in data:
            raise MissionNotFound(f"unknown mission: {mission.mission_id}")
        data[mission.mission_id] = mission.to_dict()
        self._save_all(data)
        return mission

    def append_result(self, mission: Mission, result: dict[str, Any]) -> Mission:
        trimmed = dict(result)
        for key in ("stdout", "stderr"):
            if isinstance(trimmed.get(key), str):
                trimmed[key] = trimmed[key][:MAX_OUTPUT_CHARS]
        mission.results.append(trimmed)
        return self.save(mission)

    # -- control actions: every one re-reads from disk first, so a cancel
    # issued by another process/CLI call is honoured, not lost. --
    def pause(self, mission_id: str) -> Mission:
        mission = self.get(mission_id)
        mission.transition("paused")
        return self.save(mission)

    def resume(self, mission_id: str) -> Mission:
        mission = self.get(mission_id)
        # Paused -> running is the resume path. A queued mission is started
        # by the runner, not by resume().
        mission.transition("running")
        return self.save(mission)

    def cancel(self, mission_id: str) -> Mission:
        mission = self.get(mission_id)
        mission.transition("cancelled")
        return self.save(mission)

    def approve(self, mission_id: str) -> Mission:
        mission = self.get(mission_id)
        if mission.status != "waiting_for_approval":
            raise InvalidTransition(f"mission is {mission.status}, not waiting_for_approval")
        mission.transition("queued")
        return self.save(mission)

    def requeue(self, mission_id: str) -> Mission:
        """Manual re-queue of a failed mission (never automatic)."""
        mission = self.get(mission_id)
        if mission.status != "failed":
            raise InvalidTransition(f"only a failed mission can be re-queued, not {mission.status}")
        mission.transition("queued")
        mission.error_summary = ""
        return self.save(mission)
