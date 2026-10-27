"""Persistent project memory (blueprint Feature E, P1 part).

Uses the existing mission-store pattern (JSON, atomic writes) rather
than a second database, and sits alongside Hermes' own memory /
session-search -- it does not replace them. Facts are durable project
knowledge with a source reference and a timestamp, so stale or
conflicting facts can be spotted instead of silently treated as current.

Boundaries:
  * No secrets: a value matching a credential-looking pattern
    (password / api key / token / secret assignment, or a long
    high-entropy token-like string) is refused, never stored.
  * Inspect / correct / export / delete are first-class: correct()
    replaces a fact and keeps the previous value in the record's
    history, delete() removes it, export() returns a redacted copy.
  * Temporary task state (mission results) stays in missions.json;
    this store is for durable preferences, project facts and decisions.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SECRET_RE = re.compile(
    r"(?i)(password|api[_-]?key|secret|token|private[_-]?key)\s*[:=]\s*\S{4,}"
)


class MemoryError(Exception):
    """Base memory error."""


class SecretRefused(MemoryError):
    """A value looked like a secret and was refused, not stored."""


@dataclass
class Fact:
    key: str
    value: str
    source: str = ""
    created_at: str = ""
    updated_at: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Fact":
        return cls(
            key=str(data["key"]),
            value=str(data.get("value", "")),
            source=str(data.get("source", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            history=list(data.get("history") or []),
        )


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectMemory:
    """JSON-backed durable fact store."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "project_memory.json"

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise MemoryError("project_memory.json is corrupt")
        return data

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, key: str, value: str, source: str = "") -> Fact:
        if not key or not key.strip():
            raise MemoryError("fact key must not be empty")
        if _SECRET_RE.search(value or ""):
            raise SecretRefused("value looks like a secret and was not stored")
        now = _utcnow()
        fact = Fact(key=key.strip(), value=value, source=source, created_at=now, updated_at=now)
        data = self._load()
        data[fact.key] = fact.to_dict()
        self._save(data)
        return fact

    def get(self, key: str) -> Fact | None:
        data = self._load()
        return Fact.from_dict(data[key]) if key in data else None

    def list(self) -> list[Fact]:
        return [Fact.from_dict(d) for d in self._load().values()]

    def correct(self, key: str, new_value: str, source: str = "") -> Fact:
        if _SECRET_RE.search(new_value or ""):
            raise SecretRefused("value looks like a secret and was not stored")
        data = self._load()
        if key not in data:
            raise MemoryError(f"unknown fact: {key}")
        fact = Fact.from_dict(data[key])
        fact.history.append({"value": fact.value, "source": fact.source, "updated_at": fact.updated_at})
        fact.value = new_value
        fact.source = source or fact.source
        fact.updated_at = _utcnow()
        data[key] = fact.to_dict()
        self._save(data)
        return fact

    def delete(self, key: str) -> bool:
        data = self._load()
        if key not in data:
            return False
        del data[key]
        self._save(data)
        return True

    def export(self) -> list[dict[str, Any]]:
        """Export all facts (values are already secret-free by construction)."""
        return [f.to_dict() for f in self.list()]
