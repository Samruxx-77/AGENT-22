"""Browser smoke tests: URL safety, handler logic with a fake runner,
Telegram dispatch authorization, config example, and the honest
unavailable case. No real browser, token, cookie or credential is used.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

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


def test_smoke_url_safety():
    browser_mod.validate_smoke_url("https://example.com")
    for bad in ("http://example.com", "https://169.254.169.254/", "https://localhost:8080/", "https://user:pass@example.com/"):
        with pytest.raises(ValueError):
            browser_mod.validate_smoke_url(bad)


def test_smoke_with_fake_runner_returns_title_and_no_cookies(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    shot = ws / "shot.png"
    shot.write_bytes(b"fake-png")
    def fake_runner(code, session):
        assert "example.com" in code and "capture_screenshot" in code and "cookie" not in code.lower()
        return {"available": True, "result": {"stdout": "TITLE:Example Domain\n", "screenshot_path": str(shot)}}
    result = browser_mod.run_browser_smoke(ws, runner=fake_runner)
    assert result["success"] is True
    assert result["title"] == "Example Domain"
    assert result["screenshot"]["size_bytes"] == 8
    assert result["cookies_copied"] is False
    assert result["credentials_printed"] is False


def test_smoke_unavailable_is_not_fake_success(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    result = browser_mod.run_browser_smoke(ws, runner=lambda code, session: {"available": False, "reason": "browser_harness not importable"})
    assert result["success"] is False
    assert result["title"] is None
    assert "NOT RUN" in result["note"]


def test_default_runner_reports_unavailable_in_this_vm(tmp_path):
    # This VM has no browser_harness / Chromium (see final report).
    ws = tmp_path / "ws"
    ws.mkdir()
    result = browser_mod.run_browser_smoke(ws)
    assert result["available"] is False
    assert result["success"] is False


def test_browser_smoke_via_telegram_dispatch_requires_owner(tmp_path, monkeypatch):
    home = tmp_path / "home"
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("HERMES_WORKSPACE", str(ws))
    mapping = platforms_mod.IdentityMapping(tmp_path / "store")
    mapping.add("telegram", "111", "SAM", "owner")
    mapping.add("telegram", "222", "SAM", "user")
    # User role cannot run a control command (browser-smoke).
    result = platforms_mod.dispatch("telegram", "222", "browser-smoke", home / "missions", mapping=mapping)
    assert result["ok"] is False
    # Owner can: in this VM it honestly reports unavailable, not success.
    result = platforms_mod.dispatch("telegram", "111", "browser-smoke", home / "missions", mapping=mapping)
    assert result["ok"] is True
    assert "NOT RUN" in result["response"] or "available" in result["response"]


def test_local_chromium_config_example_and_protections_intact():
    config = (REPO_ROOT / "browser-local.example.yaml").read_text(encoding="utf-8")
    assert "engine: auto" in config
    assert "use_real_profile: false" in config
    assert 'cdp_url: ""' in config
    assert "0.0.0.0" not in config.split("Do NOT")[0]  # 0.0.0.0 appears only in the warning, not as a value
    # Telegram allowlist + browser URL policy + file safety still present in repo.
    telegram_env = (REPO_ROOT / "plugins" / "platforms" / "telegram" / "gateway_env.py").read_text(encoding="utf-8")
    assert "TELEGRAM_ALLOWED_USERS" in telegram_env
    policy = (REPO_ROOT / "tools" / "browser_url_policy.py").read_text(encoding="utf-8")
    assert "metadata" in policy.lower()
    assert "browser_exec" in (REPO_ROOT / "toolsets.py").read_text(encoding="utf-8")
    assert "hermes-telegram" in (REPO_ROOT / "toolsets.py").read_text(encoding="utf-8")


def test_cli_browser_smoke(tmp_path, capsys):
    ws = tmp_path / "ws"
    ws.mkdir()
    assert cli_mod.main(["browser-smoke", "--workspace", str(ws)]) == 0
    out = capsys.readouterr().out
    assert "example.com" in out
    assert "NOT RUN" in out
