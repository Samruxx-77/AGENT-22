"""Power additions: Telegram control center, debug loop, dashboard,
specialists + skill factory, and phone briefing.

All tests are offline, stdlib-only, and use tmp stores. No live
provider, no real billing, no auto-install, no scheduler is created.
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
debugloop_mod = _load("debugloop", "debugloop.py")
dashboard_mod = _load("dashboard", "dashboard.py")
specialists_mod = _load("specialists", "specialists.py")
briefing_mod = _load("briefing", "briefing.py")
platforms_mod = _load("platforms", "platforms.py")
discord_mod = _load("discord", "discord.py")
whatsapp_mod = _load("whatsapp", "whatsapp.py")
browser_mod = _load("browser", "browser.py")
reflection_mod = _load("reflection", "reflection.py")
cli_mod = _load("cli", "cli.py")


def test_telegram_plan_run_cost_report_help(tmp_path, monkeypatch):
    home = tmp_path / "home"
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_WORKSPACE", str(ws))
    out = telegram_mod.handle_plan_command("Write a summary")
    assert "Mission created:" in out
    mission_id = out.split(":")[1].strip().split()[0]
    # Add a step via the store, then run it through /run.
    store = mission_mod.MissionStore(home / "missions")
    mission = store.get(mission_id)
    mission.steps = [mission_mod.Step(name="write", command=["python3", "-c", "open('out.txt','w').write('hi')"])]
    store.save(mission)
    out = telegram_mod.handle_run_command(mission_id)
    assert "finished: completed" in out
    assert (ws / "out.txt").read_text() == "hi"
    assert "Estimated spend today" in telegram_mod.handle_cost_command("")
    assert "completed" in telegram_mod.handle_report_command(mission_id)
    assert "/plan" in telegram_mod.handle_help_command()
    assert "Usage" in telegram_mod.handle_plan_command("")


def test_debug_loop_fixes_then_succeeds(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    script = ws / "run.py"
    script.write_text("import pathlib\np = pathlib.Path('fixed.txt')\nassert p.exists(), 'not fixed yet'\n")
    def fixer(attempt, record):
        (ws / "fixed.txt").write_text("fixed")
    result = debugloop_mod.run_debug_loop(["python3", "run.py"], ws, fixer=fixer, max_attempts=3)
    assert result["success"] is True
    assert result["attempts_used"] == 2
    # No fixer: fails after 1 attempt, not forever.
    (ws / "fixed.txt").unlink()
    result = debugloop_mod.run_debug_loop(["python3", "run.py"], ws, fixer=None, max_attempts=3)
    assert result["success"] is False
    assert len(result["attempts"]) == 1


def test_dashboard_and_live_routing_honest_about_health(tmp_path):
    store_dir = tmp_path / "store"
    mission_mod.MissionStore(store_dir).create(goal="dashboard test")
    data = dashboard_mod.dashboard_data(store_dir)
    assert data["missions_total"] == 1
    assert data["cost_is_estimate"] is True
    assert "unknown" in data["health_status"]
    html_path = dashboard_mod.write_dashboard(store_dir, tmp_path / "dash.html")
    assert "AGENT 22" in html_path.read_text()
    profiles = [
        router_mod.ModelProfile(model_id="cheap", provider="test", capabilities=frozenset({"chat"}), price_in_per_1k_usd=0.1, price_out_per_1k_usd=0.2),
        router_mod.ModelProfile(model_id="pricey", provider="test", capabilities=frozenset({"chat"}), price_in_per_1k_usd=1.0, price_out_per_1k_usd=2.0),
    ]
    config = router_mod.RouterConfig()
    live = dashboard_mod.select_model_live("chat", profiles, config, health={"cheap": False, "pricey": True})
    assert live["model_id"] == "pricey"
    assert "live health map" in live["health_status"]
    unknown = dashboard_mod.select_model_live("chat", profiles, config)
    assert unknown["model_id"] == "cheap"
    assert "unknown" in unknown["health_status"]


def test_specialists_and_skill_factory_no_auto_install(tmp_path):
    plan = specialists_mod.specialist_plan("Build a demo")
    assert [p["role"] for p in plan] == ["researcher", "coder", "reviewer"]
    assert specialists_mod.review_change(["a.py"], checks_passed=True)["approved"] is True
    assert specialists_mod.review_change(["a.py"], checks_passed=True, secrets_found=True)["approved"] is False
    draft = specialists_mod.propose_skill("demo-skill", "Do a demo task well.", "Steps here.", tmp_path / "proposals")
    assert draft.is_file()
    assert not (tmp_path / "skills" / "demo-skill").exists()
    with pytest.raises(ValueError):
        specialists_mod.install_skill("demo-skill", tmp_path / "proposals", tmp_path / "skills", approved=False)
    installed = specialists_mod.install_skill("demo-skill", tmp_path / "proposals", tmp_path / "skills", approved=True)
    assert installed.is_file()
    with pytest.raises(ValueError):
        specialists_mod.propose_skill("Bad Name", "Too long description that goes on and on and on and on and on.", "", tmp_path / "proposals")


def test_briefing_from_real_store_data(tmp_path):
    store_dir = tmp_path / "store"
    mission_mod.MissionStore(store_dir).create(goal="Briefing test")
    text = briefing_mod.generate_briefing(store_dir, when="2026-10-27")
    assert "AGENT 22 briefing" in text
    assert "Briefing test" not in text  # only attention missions are listed by goal; queued is not
    assert "Missions: 1 total" in text
    assert "estimate only" in text


def test_cli_dashboard_cost_briefing_debug(tmp_path, capsys):
    store_dir = str(tmp_path / "store")
    assert cli_mod.main(["dashboard", "--store", store_dir]) == 0
    assert "AGENT 22" in capsys.readouterr().out
    assert cli_mod.main(["cost", "--store", store_dir]) == 0
    assert "estimate" in capsys.readouterr().out.lower()
    assert cli_mod.main(["briefing", "--store", store_dir]) == 0
    assert "briefing" in capsys.readouterr().out.lower()
