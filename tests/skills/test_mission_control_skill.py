"""Authoring-standard checks for the mission-control skill.

This mirrors the repo's own skill authoring standards (skills/AGENTS.md):
frontmatter description must be one sentence, at most 60 characters,
and end with a period. It checks the skill's declared metadata, not
the prose of an implementation.
"""

from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills" / "productivity" / "mission-control" / "SKILL.md"


def _frontmatter():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    _, front, _ = text.split("---", 2)
    data = {}
    for line in front.strip().splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
    return data


def test_skill_exists_and_description_meets_standard():
    assert SKILL.is_file()
    data = _frontmatter()
    assert data["name"] == "mission-control"
    description = data["description"]
    assert len(description) <= 60, description
    assert description.endswith(".")
    assert description.count(".") == 1


def test_skill_mentions_bounded_scope():
    text = SKILL.read_text(encoding="utf-8")
    assert "hermes mission" in text
    assert "i-own-this" in text
