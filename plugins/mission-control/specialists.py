"""Specialist agents + skill factory (proposals, never auto-install).

Specialists are roles with prompts and checks, not autonomous LLM
agents by themselves: a model executes the role, this module defines
what each role must do and what counts as done. That distinction is
deliberate -- a role definition cannot hallucinate a review.

Roles:
  * researcher: gather facts, cite sources, separate pakka from andaz.
  * coder: implement the smallest change that satisfies the checks.
  * reviewer: check the change against the checks, flag secret or
    scope violations, and approve or reject with reasons.

Skill factory:
  * propose_skill() writes a SKILL.md DRAFT to a proposals directory
    only. It validates the authoring standard (description <=60
    chars, one sentence, ends with a period, slug name).
  * install_skill() copies a proposal into a skills directory ONLY
    when approved=True is passed explicitly by the user. Without
    approval it raises, and the proposal stays a draft. Nothing here
    auto-installs a skill, and nothing here runs a skill's code.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ROLES: dict[str, dict[str, Any]] = {
    "researcher": {
        "prompt": "You are the Researcher specialist for AGENT 22. Gather facts, cite sources, separate pakka (verified) from andaz (estimate), and return only what you verified.",
        "checks": ["sources cited", "pakka vs andaz labelled", "no invented claims"],
    },
    "coder": {
        "prompt": "You are the Coder specialist for AGENT 22. Implement the smallest change that satisfies the given checks, inside the workspace only, with tests.",
        "checks": ["workspace only", "tests pass", "no secrets in output"],
    },
    "reviewer": {
        "prompt": "You are the Reviewer specialist for AGENT 22. Check the change against its checks, flag secret or scope violations, and approve or reject with reasons. Never approve your own work.",
        "checks": ["checks satisfied", "no scope escape", "no secrets", "reasons given"],
    },
}


def specialist_plan(goal: str) -> list[dict[str, Any]]:
    """Split a goal into researcher -> coder -> reviewer phases."""
    if not goal or not goal.strip():
        raise ValueError("goal must not be empty")
    return [
        {"phase": 1, "role": "researcher", "task": f"Research: {goal.strip()}", "prompt": ROLES["researcher"]["prompt"]},
        {"phase": 2, "role": "coder", "task": f"Implement: {goal.strip()}", "prompt": ROLES["coder"]["prompt"]},
        {"phase": 3, "role": "reviewer", "task": f"Review: {goal.strip()}", "prompt": ROLES["reviewer"]["prompt"]},
    ]


def review_change(files_changed: list[str], checks_passed: bool, secrets_found: bool = False) -> dict[str, Any]:
    """Reviewer verdict: approve only if checks pass and no secrets."""
    reasons = []
    if not checks_passed:
        reasons.append("checks did not pass")
    if secrets_found:
        reasons.append("secrets found in change")
    if files_changed and any(f.startswith("/") and "workspace" not in f for f in files_changed):
        reasons.append("absolute path outside workspace (review manually)")
    approved = not reasons
    return {"approved": approved, "reasons": reasons, "files_changed": files_changed}


def _validate_skill(name: str, description: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name or ""):
        raise ValueError("skill name must be a lowercase slug (letters, digits, hyphens)")
    if len(description) > 60 or not description.endswith(".") or description.count(".") != 1:
        raise ValueError("skill description must be one sentence, <=60 chars, ending with a period")


def propose_skill(name: str, description: str, body: str, proposals_dir: str | Path) -> Path:
    """Write a skill DRAFT to proposals_dir. Does not install anything."""
    _validate_skill(name, description)
    proposals = Path(proposals_dir)
    proposals.mkdir(parents=True, exist_ok=True)
    draft = proposals / f"{name}.md"
    draft.write_text(f"---\nname: {name}\ndescription: \"{description}\"\n---\n\n{body}\n", encoding="utf-8")
    return draft


def install_skill(name: str, proposals_dir: str | Path, skills_dir: str | Path, approved: bool = False) -> Path:
    """Install a proposed skill ONLY with explicit user approval."""
    if not approved:
        raise ValueError("skill install requires approved=True (user approval, not auto-install)")
    draft = Path(proposals_dir) / f"{name}.md"
    if not draft.is_file():
        raise ValueError(f"no proposal found for skill: {name}")
    target_dir = Path(skills_dir) / name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "SKILL.md"
    target.write_text(draft.read_text(encoding="utf-8"), encoding="utf-8")
    return target
