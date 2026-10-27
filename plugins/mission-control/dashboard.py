"""Live routing (health-injected) + cost dashboard (static HTML).

Honest boundaries, stated in the output itself:
  * Routing: select_model_live() takes a health map supplied by the
    caller (model_id -> healthy bool) from a real provider check the
    caller performed. If no health map is given, health is "unknown"
    and selection falls back to the static router -- it never claims
    a provider is up when nothing checked it.
  * Costs: all figures are estimates from BudgetLedger (budget.json),
    labelled as estimates. There is no live provider billing here;
    a real billing figure would need provider credentials and an
    API call, which this module deliberately does not make.
  * Dashboard: a static HTML file generated from the store (missions,
    budget, identity). It is a snapshot, not a live web server, and
    it says so in the page. No secrets are written into it: mission
    records and budget totals contain no secrets by construction.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

try:
    from .budget import BudgetLedger
    from .identity import IdentityStore
    from .mission import MissionStore
    from .router import ModelProfile, RouterConfig, select_model
except ImportError:  # loaded as standalone files in tests
    from budget import BudgetLedger
    from identity import IdentityStore
    from mission import MissionStore
    from router import ModelProfile, RouterConfig, select_model


def select_model_live(
    task_type: str,
    profiles: list[ModelProfile],
    config: RouterConfig,
    health: dict[str, bool] | None = None,
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> dict[str, Any]:
    """Select a model, applying a caller-supplied health map if given."""
    if health is None:
        chosen = select_model(task_type, profiles, config, input_tokens, output_tokens)
        return {"model_id": chosen.model_id, "provider": chosen.provider, "health_status": "unknown (no live provider check performed)", "estimated_cost_usd": config.estimate_for(chosen, input_tokens, output_tokens)}
    adjusted = [
        ModelProfile(
            model_id=p.model_id,
            provider=p.provider,
            capabilities=p.capabilities,
            price_in_per_1k_usd=p.price_in_per_1k_usd,
            price_out_per_1k_usd=p.price_out_per_1k_usd,
            latency_tier=p.latency_tier,
            healthy=bool(health.get(p.model_id, p.healthy)),
        )
        for p in profiles
    ]
    chosen = select_model(task_type, adjusted, config, input_tokens, output_tokens)
    return {"model_id": chosen.model_id, "provider": chosen.provider, "health_status": "live health map applied by caller", "estimated_cost_usd": config.estimate_for(chosen, input_tokens, output_tokens)}


def dashboard_data(store_dir: str | Path) -> dict[str, Any]:
    """Snapshot data for the dashboard (missions, budget, identity)."""
    store_dir = Path(store_dir)
    missions = MissionStore(store_dir).list()
    ledger = BudgetLedger(store_dir)
    identity = IdentityStore(store_dir).load()
    by_status: dict[str, int] = {}
    for mission in missions:
        by_status[mission.status] = by_status.get(mission.status, 0) + 1
    return {
        "name": identity.name,
        "owner": identity.owner,
        "mode": identity.mode,
        "missions_total": len(missions),
        "missions_by_status": by_status,
        "missions": [{"mission_id": m.mission_id, "goal": m.goal, "status": m.status} for m in missions],
        "estimated_spend_today_usd": ledger.daily_total(),
        "cost_is_estimate": True,
        "health_status": "unknown (no live provider check performed)",
    }


def render_dashboard_html(data: dict[str, Any]) -> str:
    """Static HTML snapshot. Escaped, no secrets, labelled as a snapshot."""
    rows = "".join(
        f"<tr><td>{html.escape(m['mission_id'])}</td><td>{html.escape(m['goal'])}</td><td>{html.escape(m['status'])}</td></tr>"
        for m in data["missions"]
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(data['name'])} Dashboard</title></head>
<body><h1>{html.escape(data['name'])} — Dashboard (snapshot, not live)</h1>
<p>Owner: {html.escape(data['owner'])} | Mode: {html.escape(data['mode'])}</p>
<p>Missions: {data['missions_total']} | Estimated spend today: ${data['estimated_spend_today_usd']:.4f} USD (estimate only)</p>
<p>Provider health: {html.escape(data['health_status'])}</p>
<table><tr><th>ID</th><th>Goal</th><th>Status</th></tr>{rows}</table>
</body></html>"""


def write_dashboard(store_dir: str | Path, output_path: str | Path) -> Path:
    """Generate the dashboard HTML file and return its path."""
    output = Path(output_path)
    output.write_text(render_dashboard_html(dashboard_data(store_dir)), encoding="utf-8")
    return output
