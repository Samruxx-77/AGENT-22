"""AGENT 22 identity: single source of truth, persisted across restarts.

Name / owner / developer are configured data, not a model's improvisation:
  * DEFAULT_NAME = "AGENT 22", DEFAULT_OWNER = DEFAULT_DEVELOPER = "SAM".
  * IdentityStore persists the configured identity as JSON (atomic write)
    in the store directory, so a process restart reloads the same values.
  * answer_identity() is the canned, testable answer to "who are you?"
    / "who made you?" -- tests assert on this configuration and on the
    prompt content in agent/prompt_builder.py / hermes_cli/default_soul.py,
    never on a particular model's exact wording.
  * render_banner() shows owner, mode, model/provider and connection
    status, but connection status is NEVER hardcoded: the caller must
    supply a status it actually measured ("connected", "failed: ...",
    or "unknown"). The default, when nothing was measured, is "unknown
    (no live check performed)". Model/provider are likewise taken from
    the caller's config (see detect_model_from_config) or reported as
    "unknown" -- never invented.

Modes: "normal" (default) and "companion" (opt-in, tone only -- see
companion.py). Switching mode changes tone, never permissions, tool
access or secret access.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_NAME = "AGENT 22"
DEFAULT_OWNER = "SAM"
DEFAULT_DEVELOPER = "SAM"
VALID_MODES = ("normal", "companion")


@dataclass
class Identity:
    name: str = DEFAULT_NAME
    owner: str = DEFAULT_OWNER
    developer: str = DEFAULT_DEVELOPER
    mode: str = "normal"
    companion_tone: str = "supportive"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Identity":
        mode = str(data.get("mode", "normal"))
        if mode not in VALID_MODES:
            mode = "normal"
        return cls(
            name=str(data.get("name", DEFAULT_NAME) or DEFAULT_NAME),
            owner=str(data.get("owner", DEFAULT_OWNER) or DEFAULT_OWNER),
            developer=str(data.get("developer", DEFAULT_DEVELOPER) or DEFAULT_DEVELOPER),
            mode=mode,
            companion_tone=str(data.get("companion_tone", "supportive")),
        )


class IdentityStore:
    """JSON identity store, atomic writes, restart-persistent."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "identity.json"

    def load(self) -> Identity:
        if not self.path.exists():
            return Identity()
        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            return Identity()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return Identity()
        return Identity.from_dict(data)

    def save(self, identity: Identity) -> Identity:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(identity.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)
        return identity

    def set_mode(self, mode: str) -> Identity:
        if mode not in VALID_MODES:
            raise ValueError(f"unknown mode: {mode!r} (valid: {', '.join(VALID_MODES)})")
        identity = self.load()
        identity.mode = mode
        return self.save(identity)


def answer_identity(identity: Identity, question: str = "") -> str:
    """Consistent, configured answer to identity questions."""
    q = (question or "").lower()
    if "who" in q and ("develop" in q or "creat" in q or "made" in q or "built" in q):
        return f"I was developed by {identity.developer}."
    if "owner" in q:
        return f"My owner is {identity.owner}."
    return f"I am {identity.name}, an AI assistant developed by {identity.developer} for {identity.owner}."


def detect_model_from_config(home: str | Path | None = None) -> dict[str, str]:
    """Best-effort model/provider detection from ~/.hermes/config.yaml.

    This is a plain-text scan (no YAML dependency) for the lines the
    repo's own example uses: ``model:`` followed by ``default: <id>``,
    and a ``provider:`` line. If nothing is found, both fields are
    "unknown" -- the caller must not upgrade that to "connected" or to
    a guessed model name.
    """
    home_path = Path(home) if home else Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    config = home_path / "config.yaml"
    model, provider = "unknown", "unknown"
    if config.is_file():
        text = config.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^\s*default\s*:\s*([^\s#]+)", text, re.MULTILINE)
        if m:
            model = m.group(1)
        p = re.search(r"^\s*provider\s*:\s*([^\s#]+)", text, re.MULTILINE)
        if p:
            provider = p.group(1)
        # model ids are often "provider/model"; split only for display.
        if provider == "unknown" and "/" in model:
            provider = model.split("/", 1)[0]
    return {"model": model, "provider": provider}


def render_banner(
    identity: Identity,
    model: str = "unknown",
    provider: str = "unknown",
    connection_status: str = "unknown (no live check performed)",
) -> str:
    """Clean startup banner. No status is claimed unless measured."""
    lines = [
        "==============================",
        f"{identity.name}",
        f"Owner: {identity.owner}  |  Developed by: {identity.developer}",
        f"Mode: {identity.mode}",
        f"Model: {model}  |  Provider: {provider}",
        f"Connection: {connection_status}",
        "==============================",
    ]
    return "\n".join(lines)


def render_status(identity: Identity, model: str = "unknown", provider: str = "unknown", connection_status: str = "unknown (no live check performed)") -> dict[str, Any]:
    """Machine-readable CLI status: same fields as the banner, no claims."""
    return {
        "name": identity.name,
        "owner": identity.owner,
        "developer": identity.developer,
        "mode": identity.mode,
        "companion_tone": identity.companion_tone,
        "model": model,
        "provider": provider,
        "connection_status": connection_status,
    }
