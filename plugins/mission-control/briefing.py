"""Phone briefing: a short daily text briefing from the store.

This is the proactive-briefing generator, not a scheduler and not a
voice synthesizer:
  * generate_briefing() reads missions, budget and identity from the
    store and returns plain text: what is running, completed, failed
    or waiting, estimated spend today, and the next step. It is a
    template over real store data, not an LLM summary, so it cannot
    invent a mission or a cost.
  * Voice: AGENT 22 has no built-in TTS here. The briefing text is
    the input to any external TTS the user already uses (for example
    ElevenLabs, which SAM already uses for voiceovers); the audio
    step is documented in HERMES_ULTIMATE.md, not faked by this
    module. For delivery to a phone, MP3 is the format (per SAM's
    audio rule), not WAV.
  * Scheduling: this module does not create a cron. A daily briefing
    needs a schedule SAM approves (time + destination); the command
    to run is `hermes mission briefing`, and the cron, if SAM wants
    one, is a separate, explicit approval.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

try:
    from .dashboard import dashboard_data
except ImportError:  # loaded as standalone files in tests
    from dashboard import dashboard_data


def generate_briefing(store_dir: str | Path, when: str | None = None) -> str:
    """Generate a short briefing from real store data."""
    data = dashboard_data(store_dir)
    date = when or datetime.now(timezone.utc).date().isoformat()
    lines = [
        f"AGENT 22 briefing — {date}",
        f"Owner: {data['owner']} | Mode: {data['mode']}",
        f"Missions: {data['missions_total']} total",
    ]
    for status, count in sorted(data["missions_by_status"].items()):
        lines.append(f"  {status}: {count}")
    for mission in data["missions"]:
        if mission["status"] in ("failed", "waiting_for_approval", "running"):
            lines.append(f"  Attention: {mission['mission_id']} — {mission['goal']} ({mission['status']})")
    lines.append(f"Estimated spend today: ${data['estimated_spend_today_usd']:.4f} USD (estimate only)")
    lines.append("Next step: check any Attention items above, then run `hermes mission report <id>` for details.")
    return "\n".join(lines)
