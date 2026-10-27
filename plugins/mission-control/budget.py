"""Budget-aware usage ledger (P0, blueprint Feature B).

All costs are ESTIMATES unless a provider returns reliable usage data and
the caller records it as such. Nothing here calls a provider, spends
money, or invents a price: prices come only from the caller-supplied
model profile (see router.py) or from the example config, and the
``is_estimate`` flag stays True on every record this module creates.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class BudgetError(Exception):
    """Base budget error."""


class BudgetExceeded(BudgetError):
    """Raised when a task or daily limit would be exceeded (hard stop)."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    estimated_cost_usd: float = 0.0
    is_estimate: bool = True


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    price_in_per_1k_usd: float,
    price_out_per_1k_usd: float,
) -> float:
    """Estimate cost from token counts and per-1k prices. Never negative."""
    if input_tokens < 0 or output_tokens < 0:
        raise BudgetError("token counts must not be negative")
    return (input_tokens / 1000.0) * price_in_per_1k_usd + (
        output_tokens / 1000.0
    ) * price_out_per_1k_usd


class BudgetLedger:
    """Per-task and per-day usage ledger, persisted as JSON (atomic write).

    A ledger entry is keyed by task id and by UTC date. ``record()`` is a
    hard stop: if recording would push the task or the day over its
    configured limit, it raises BudgetExceeded and records nothing, so a
    mission cannot quietly drift past its budget.
    """

    def __init__(
        self,
        directory: str | Path,
        max_task_cost_usd: float | None = None,
        daily_budget_usd: float | None = None,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "budget.json"
        self.max_task_cost_usd = max_task_cost_usd
        self.daily_budget_usd = daily_budget_usd

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"tasks": {}, "days": {}}
        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            return {"tasks": {}, "days": {}}
        data = json.loads(raw)
        data.setdefault("tasks", {})
        data.setdefault("days", {})
        return data

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def task_total(self, task_id: str) -> float:
        return float(self._load()["tasks"].get(task_id, 0.0))

    def daily_total(self, date: str | None = None) -> float:
        return float(self._load()["days"].get(date or self._today(), 0.0))

    def check(self, task_id: str, additional_cost_usd: float) -> None:
        """Raise BudgetExceeded if this extra cost would break a limit."""
        if additional_cost_usd < 0:
            raise BudgetError("cost must not be negative")
        if self.max_task_cost_usd is not None:
            projected = self.task_total(task_id) + additional_cost_usd
            if projected > self.max_task_cost_usd:
                raise BudgetExceeded(
                    f"task budget exceeded: {projected:.4f} > "
                    f"{self.max_task_cost_usd:.4f} USD (estimated)"
                )
        if self.daily_budget_usd is not None:
            projected = self.daily_total() + additional_cost_usd
            if projected > self.daily_budget_usd:
                raise BudgetExceeded(
                    f"daily budget exceeded: {projected:.4f} > "
                    f"{self.daily_budget_usd:.4f} USD (estimated)"
                )

    def record(self, task_id: str, usage: Usage) -> Usage:
        self.check(task_id, usage.estimated_cost_usd)
        data = self._load()
        data["tasks"][task_id] = float(data["tasks"].get(task_id, 0.0)) + usage.estimated_cost_usd
        today = self._today()
        data["days"][today] = float(data["days"].get(today, 0.0)) + usage.estimated_cost_usd
        self._save(data)
        return usage
