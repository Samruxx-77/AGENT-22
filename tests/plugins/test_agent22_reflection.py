"""Reflection + politeness tests: structured reflection, no blame,
no invented root cause, persistent log, CLI and Telegram dispatch.
"""

import importlib.util
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins" / "mission-control"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name, filename):
    path = PLUGIN_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mission_mod = _load("mission", "mission.py")
budget_mod = _load("budget", "budget.py")
router_mod = _load("router", "router.py")
runner_mod = _load("runner", "runner.py")
audit_mod = _load("audit", "audit.py")
identity_mod = _load("identity", "identity.py")
companion_mod = _load("companion", "companion.py")
memory_mod = _load("memory", "memory.py")
security_mod = _load("security", "security.py")
pentest_mod = _load("pentest", "pentest.py")
soul_mod = _load("soul", "soul.py")
limits_mod = _load("limits", "limits.py")
telegram_mod = _load("telegram", "telegram.py")
dashboard_mod = _load("dashboard", "dashboard.py")
briefing_mod = _load("briefing", "briefing.py")
debugloop_mod = _load("debugloop", "debugloop.py")
specialists_mod = _load("specialists", "specialists.py")
platforms_mod = _load("platforms", "platforms.py")
discord_mod = _load("discord", "discord.py")
whatsapp_mod = _load("whatsapp", "whatsapp.py")
browser_mod = _load("browser", "browser.py")
reflection_mod = _load("reflection", "reflection.py")
cli_mod = _load("cli", "cli.py")


def test_failure_reflection_is_polite_no_blame_no_invented_cause():
    reflection = reflection_mod.reflect_on_failure("step failed with exit 1")
    assert reflection["blames_user"] is False
    assert "Sorry" in reflection["apology"]
    assert "don't know yet" in reflection["what_likely_went_wrong"]
    assert reflection["what_to_change_next_time"]
    text = reflection_mod.format_reflection(reflection)
    assert "Sorry" in text and "What I'll change" in text


def test_correction_reflection_puts_correction_first():
    reflection = reflection_mod.reflect_on_correction("old claim", "new correct claim")
    assert reflection["blames_user"] is False
    assert "thank" in reflection["apology"].lower()
    text = reflection_mod.format_reflection(reflection)
    assert text.index("Corrected: new correct claim") < text.index("Previously I said: old claim")


def test_reflection_log_persists_and_redacts(tmp_path):
    log = reflection_mod.ReflectionLog(tmp_path / "store")
    reflection = reflection_mod.reflect_on_failure("api_key = 'sk-live-123456' leaked in log")
    log.add(reflection, mission_id="abc123", kind="failure")
    reloaded = reflection_mod.ReflectionLog(tmp_path / "store")
    assert len(reloaded.list()) == 1
    assert reloaded.latest()["mission_id"] == "abc123"
    assert "sk-live" not in str(reloaded.list())


def test_soul_and_persona_are_polite():
    assert "polite" in soul_mod.soul_text().lower()
    assert "never blame" in soul_mod.soul_text().lower()
    soul_file = (REPO_ROOT / "SOUL.md").read_text(encoding="utf-8")
    assert "Politeness and reflection" in soul_file
    assert "Does that fix it?" in soul_file


def test_cli_reflect_and_telegram_reflect(tmp_path, capsys, monkeypatch):
    store_dir = str(tmp_path / "store")
    assert cli_mod.main(["reflect", "--error", "test failed", "--store", store_dir]) == 0
    out = capsys.readouterr().out
    assert "Sorry" in out and "What I'll change" in out
    assert cli_mod.main(["reflect", "--previous", "old", "--correction", "new", "--store", store_dir]) == 0
    out = capsys.readouterr().out
    assert "Corrected: new" in out
    # Telegram dispatch: reflect is a query, any mapped role may use it.
    home = tmp_path / "home"
    monkeypatch.setenv("HERMES_WORKSPACE", str(tmp_path / "ws"))
    mapping = platforms_mod.IdentityMapping(tmp_path / "store2")
    mapping.add("telegram", "111", "SAM", "owner")
    mapping.add("telegram", "222", "SAM", "user")
    result = platforms_mod.dispatch("telegram", "222", "reflect something went wrong", home / "missions", mapping=mapping)
    assert result["ok"] is True and "Sorry" in result["response"]
