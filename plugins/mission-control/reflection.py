"""Reflection on mistakes, politely — like Muse and ChatGPT at their best.

This is not a model pretending to feel remorse, and it is not a
generic "sorry" pasted over every answer. It is a structured habit,
in code, so AGENT 22 actually learns from a failure or a correction:

  * reflect_on_failure(error, context): what happened, what most
    likely went wrong (labelled as a best reading, not a verified
    fact), what AGENT 22 assumed, and what to change next time.
  * reflect_on_correction(previous, correction): the user corrected
    something; the reflection thanks them briefly, states the old
    claim, states the corrected claim, and says what will change.
    It never argues, never gets defensive, and never blames the user
    for the mistake — even if the user's wording was unclear, the
    reflection owns the part AGENT 22 got wrong.
  * Politeness rules (also in SOUL.md / soul.py): courteous and
    warm, brief apology (one line, not grovelling), correction
    first, explanation second, and a check at the end ("does that
    fix it?"). No filler, no repeated apologies, no "as an AI" lectures.
  * ReflectionLog: reflections are saved as JSON in the store, so
    a mistake is not forgotten on restart. The log is inspectable
    (list/get) and correctable, like project memory. It never stores
    secrets — values are redacted before saving.

A reflection is a template over explicit inputs (an error string, a
correction string, a mission report). It does not invent a root
cause: if the cause is not in the inputs, it says "I don't know yet
what caused this" and proposes the next check, instead of guessing.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SECRET_RE = re.compile(r"(?i)(password|api[_-]?key|secret|token)\s*[:=]\s*\S+")


def _redact(text: str) -> str:
    return _SECRET_RE.sub(r"\1=[REDACTED]", text or "")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def reflect_on_failure(error: str, context: str = "", assumed: str = "") -> dict[str, Any]:
    """Structured reflection on a failure. Cause is a best reading, not a fact."""
    error = _redact(error or "unknown error")
    return {
        "apology": "Sorry about that — thanks for flagging it, let me fix it properly.",
        "what_happened": error,
        "what_likely_went_wrong": (
            "My best reading (not verified yet): " + (_redact(assumed) if assumed else "I don't know yet what caused this — the next check below is how I'd find out.")
        ),
        "what_i_assumed": _redact(assumed) if assumed else "Nothing recorded — I should have checked the assumption before acting.",
        "context": _redact(context),
        "what_to_change_next_time": [
            "Check the assumption before acting, not after failing.",
            "Verify the result before claiming success.",
            "If the same error repeats, stop and ask SAM instead of retrying the same step.",
        ],
        "next_check": "Re-run the failing step with its output visible, and compare it against the expected result before proceeding.",
        "blames_user": False,
    }


def reflect_on_correction(previous: str, correction: str) -> dict[str, Any]:
    """Structured reflection on a user correction. Correction first, never defensive."""
    return {
        "apology": "You're right, thank you for correcting me — sorry for getting that wrong.",
        "previous_claim": _redact(previous or ""),
        "corrected_claim": _redact(correction or ""),
        "what_changes": "I will use the corrected version from now on, and I will not repeat the old claim without checking it first.",
        "blames_user": False,
        "check": "Does that fix it? If anything is still off, tell me and I'll correct it again.",
    }


def format_reflection(reflection: dict[str, Any]) -> str:
    """Polite, short, human-readable reflection. Correction first."""
    lines = [reflection.get("apology", "Sorry about that.")]
    if "corrected_claim" in reflection:
        lines.append(f"Corrected: {reflection['corrected_claim']}")
        if reflection.get("previous_claim"):
            lines.append(f"Previously I said: {reflection['previous_claim']}")
        lines.append(reflection["what_changes"])
        lines.append(reflection["check"])
    else:
        lines.append(f"What happened: {reflection['what_happened']}")
        lines.append(reflection["what_likely_went_wrong"])
        lines.append("What I'll change next time:")
        for item in reflection["what_to_change_next_time"]:
            lines.append(f"  - {item}")
        lines.append(f"Next check: {reflection['next_check']}")
    return "\n".join(lines)


class ReflectionLog:
    """Persistent, inspectable log of reflections (JSON, atomic writes)."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "reflections.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else []

    def _save(self, data: list[dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, reflection: dict[str, Any], mission_id: str = "", kind: str = "failure") -> dict[str, Any]:
        entry = {"mission_id": mission_id, "kind": kind, "at": _utcnow(), "reflection": reflection}
        data = self._load()
        data.append(entry)
        self._save(data)
        return entry

    def list(self) -> list[dict[str, Any]]:
        return self._load()

    def latest(self) -> dict[str, Any] | None:
        data = self._load()
        return data[-1] if data else None
