"""Tests for the mission-control plugin (P0).

Loads the plugin's stdlib-only library modules directly from the repo
path, following the tests/plugins/test_disk_cleanup_plugin.py pattern.
Tests use only tmp_path stores/workspaces, never a real HERMES_HOME,
never a network call, never a real provider, and never a real secret.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins" / "mission-control"


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
dashboard_mod = _load("dashboard", "dashboard.py")
briefing_mod = _load("briefing", "briefing.py")
debugloop_mod = _load("debugloop", "debugloop.py")
specialists_mod = _load("specialists", "specialists.py")
telegram_mod = _load("telegram", "telegram.py")
platforms_mod = _load("platforms", "platforms.py")
discord_mod = _load("discord", "discord.py")
whatsapp_mod = _load("whatsapp", "whatsapp.py")
browser_mod = _load("browser", "browser.py")
reflection_mod = _load("reflection", "reflection.py")
cli_mod = _load("cli", "cli.py")

MissionStore = mission_mod.MissionStore
Step = mission_mod.Step
InvalidTransition = mission_mod.InvalidTransition
BudgetLedger = budget_mod.BudgetLedger
Usage = budget_mod.Usage
BudgetExceeded = budget_mod.BudgetExceeded
ModelProfile = router_mod.ModelProfile
RouterConfig = router_mod.RouterConfig
NoAffordableFallback = router_mod.NoAffordableFallback
NoModelAvailable = router_mod.NoModelAvailable


def _py(code):
    return ["python3", "-c", code]


# ---------- mission state ----------

def test_invalid_transition_is_rejected(tmp_path):
    store = MissionStore(tmp_path / "store")
    mission = store.create("do a thing")
    with pytest.raises(InvalidTransition):
        mission.transition("completed")  # queued -> completed is not allowed
    assert store.get(mission.mission_id).status == "queued"


def test_store_survives_reload_like_process_restart(tmp_path):
    store = MissionStore(tmp_path / "store")
    mission = store.create("persist me", plan=["a", "b"])
    reloaded = MissionStore(tmp_path / "store").get(mission.mission_id)
    assert reloaded.goal == "persist me" and reloaded.plan == ["a", "b"]


def test_pause_resume_cancel_and_approval(tmp_path):
    store = MissionStore(tmp_path / "store")
    mission = store.create("controlled", requires_approval=True)
    assert mission.status == "waiting_for_approval"
    assert store.approve(mission.mission_id).status == "queued"
    # pause requires a running mission, so move it to running first
    m = store.get(mission.mission_id)
    m.transition("running")
    store.save(m)
    assert store.pause(m.mission_id).status == "paused"
    assert store.resume(m.mission_id).status == "running"
    assert store.cancel(m.mission_id).status == "cancelled"
    with pytest.raises(InvalidTransition):
        store.cancel(m.mission_id)


def test_backoff_is_bounded():
    assert mission_mod.backoff_seconds(0) == 1.0
    assert mission_mod.backoff_seconds(1) == 2.0
    assert mission_mod.backoff_seconds(2) == 4.0
    assert mission_mod.backoff_seconds(100, cap_seconds=60.0) == 60.0


# ---------- router ----------

def _profiles():
    return [
        ModelProfile("cheap-chat", "prov-a", frozenset({"chat"}), 0.001, 0.002, "fast", True),
        ModelProfile("coder", "prov-a", frozenset({"chat", "coding"}), 0.005, 0.01, "standard", True),
        ModelProfile("thinker", "prov-b", frozenset({"chat", "reasoning"}), 0.02, 0.04, "slow", True),
        ModelProfile("down-chat", "prov-b", frozenset({"chat"}), 0.0001, 0.0001, "fast", False),
    ]


def test_router_picks_cheapest_capable_and_ignores_down():
    chosen = router_mod.select_model("chat", _profiles(), RouterConfig())
    assert chosen.model_id == "cheap-chat"
    assert router_mod.select_model("coding", _profiles(), RouterConfig()).model_id == "coder"
    assert router_mod.select_model("planning", _profiles(), RouterConfig()).model_id == "thinker"
    with pytest.raises(NoModelAvailable):
        router_mod.select_model("vision", _profiles(), RouterConfig())


def test_router_respects_allowlist():
    cfg = RouterConfig(allowed_models=["coder"])
    assert router_mod.select_model("chat", _profiles(), cfg).model_id == "coder"


def test_fallback_never_silently_goes_pricier():
    primary = _profiles()[0]
    # cheap-chat is cheapest, so no cheaper fallback exists for chat
    with pytest.raises(NoAffordableFallback):
        router_mod.fallback_order(primary, _profiles(), RouterConfig(allow_paid_fallback=False))
    # with paid fallback allowed but a tight ceiling, still refused
    with pytest.raises(NoAffordableFallback):
        router_mod.fallback_order(
            primary, _profiles(), RouterConfig(allow_paid_fallback=True, max_task_cost_usd=0.001)
        )


# ---------- budget ----------

def test_budget_estimate_and_hard_stop(tmp_path):
    assert budget_mod.estimate_cost(1000, 500, 0.01, 0.02) == pytest.approx(0.02)
    ledger = BudgetLedger(tmp_path / "budget", max_task_cost_usd=0.05, daily_budget_usd=0.05)
    ledger.record("t1", Usage(estimated_cost_usd=0.04))
    with pytest.raises(BudgetExceeded):
        ledger.record("t1", Usage(estimated_cost_usd=0.02))
    assert ledger.task_total("t1") == pytest.approx(0.04)  # failed record added nothing


# ---------- workspace / runner ----------

def test_workspace_escape_and_protected_targets_refused(tmp_path):
    ws = runner_mod.resolve_workspace(tmp_path / "ws") if (tmp_path / "ws").exists() else None
    (tmp_path / "ws").mkdir()
    ws = runner_mod.resolve_workspace(tmp_path / "ws")
    with pytest.raises(runner_mod.WorkspaceViolation):
        runner_mod.assert_inside(ws, "../outside.txt")
    with pytest.raises(runner_mod.WorkspaceViolation):
        runner_mod.assert_inside(ws, ".env")
    assert runner_mod.assert_inside(ws, "out/result.txt").name == "result.txt"


def test_safe_env_strips_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_TOKEN", "should-not-leak")
    monkeypatch.setenv("MY_SAFE_FLAG", "yes")
    env = runner_mod.safe_env(["MY_API_TOKEN", "MY_SAFE_FLAG"])
    assert "MY_API_TOKEN" not in env
    assert env.get("MY_SAFE_FLAG") == "yes"


def test_verify_checks(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "hello.txt").write_text("hello world")
    checks = runner_mod.verify_checks(
        [
            {"type": "file_exists", "path": "hello.txt"},
            {"type": "file_contains", "path": "hello.txt", "text": "world"},
            {"type": "file_contains", "path": "hello.txt", "text": "missing"},
            {"type": "bogus"},
        ],
        ws,
    )
    assert [c["passed"] for c in checks] == [True, True, False, False]


def test_run_mission_success_and_verification_gate(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    store = MissionStore(tmp_path / "store")
    good = store.create(
        "write a file",
        steps=[Step("write", _py("open('out.txt','w').write('done')"), verify=[{"type": "file_contains", "path": "out.txt", "text": "done"}])],
    )
    done = runner_mod.run_mission(store, good.mission_id, ws, sleep_fn=lambda _s: None)
    assert done.status == "completed"
    assert (ws / "out.txt").read_text() == "done"

    bad = store.create(
        "claim without proof",
        steps=[Step("write", _py("open('out2.txt','w').write('x')"), verify=[{"type": "file_contains", "path": "out2.txt", "text": "proof"}])],
    )
    failed = runner_mod.run_mission(store, bad.mission_id, ws, sleep_fn=lambda _s: None)
    assert failed.status == "failed"  # verification failed => never completed
    assert "verification" in failed.error_summary


def test_run_mission_resume_does_not_repeat_completed_steps(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    store = MissionStore(tmp_path / "store")
    mission = store.create(
        "append once",
        steps=[
            Step("append", _py("open('log.txt','a').write('x\\n')"), idempotent=True),
            Step("second", _py("open('done.txt','w').write('ok')")),
        ],
    )
    first = runner_mod.run_mission(store, mission.mission_id, ws, sleep_fn=lambda _s: None)
    assert first.status == "completed"
    # Simulate a restart: fresh store instance, run again.
    second = runner_mod.run_mission(MissionStore(tmp_path / "store"), mission.mission_id, ws, sleep_fn=lambda _s: None)
    assert second.status == "completed"
    assert (ws / "log.txt").read_text() == "x\n"  # not "x\nx\n"


def test_cancelled_mission_starts_no_steps(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    store = MissionStore(tmp_path / "store")
    mission = store.create("never run", steps=[Step("write", _py("open('nope.txt','w').write('x')"))])
    store.cancel(mission.mission_id)
    result = runner_mod.run_mission(store, mission.mission_id, ws, sleep_fn=lambda _s: None)
    assert result.status == "cancelled"
    assert not (ws / "nope.txt").exists()


def test_non_idempotent_step_is_not_auto_retried(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    store = MissionStore(tmp_path / "store")
    mission = store.create(
        "transient but not safe to retry",
        steps=[Step("fail", _py("import sys; print('timed out', file=sys.stderr); sys.exit(1)"), idempotent=False, max_retries=5)],
    )
    result = runner_mod.run_mission(store, mission.mission_id, ws, sleep_fn=lambda _s: None)
    assert result.status == "failed"
    assert len(result.results) == 1  # exactly one attempt


def test_idempotent_transient_step_retries_then_succeeds(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    script = ws / "flaky.py"
    script.write_text(
        "from pathlib import Path\n"
        "p = Path('count.txt')\n"
        "n = int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n + 1))\n"
        "import sys\n"
        "sys.exit(0 if n >= 1 else 1)\n"
    )
    # Make the first failure look transient by printing the token to stderr.
    script.write_text(
        "from pathlib import Path\nimport sys\n"
        "p = Path('count.txt')\n"
        "n = int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n + 1))\n"
        "print('timed out', file=sys.stderr)\n"
        "sys.exit(0 if n >= 1 else 1)\n"
    )
    store = MissionStore(tmp_path / "store")
    mission = store.create(
        "flaky but safe",
        steps=[Step("flaky", ["python3", "flaky.py"], idempotent=True, max_retries=3)],
    )
    result = runner_mod.run_mission(store, mission.mission_id, ws, sleep_fn=lambda _s: None)
    assert result.status == "completed"
    assert (ws / "count.txt").read_text() == "2"


# ---------- audit (own assets only) ----------

def test_audit_flags_patterns_and_redacts_secrets(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "bad.py").write_text("x = eval(user_input)\npassword = 'hunter2-secret'\n")
    with pytest.raises(audit_mod.AuditNotAuthorised):
        audit_mod.analyse_text_file("bad.py", ws, authorised=False)
    report = audit_mod.analyse_text_file("bad.py", ws, authorised=True)
    assert any(f["pattern"] == "eval_or_exec" for f in report["findings"])
    assert "hunter2" not in str(report["findings"])
    with pytest.raises(audit_mod.AuditError):
        audit_mod.analyse_text_file("https://example.com/x.py", ws, authorised=True)


def test_audit_strings_and_debug_run(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "blob.bin").write_bytes(b"\x00hello-world\x00\xff")
    assert "hello-world" in audit_mod.extract_strings("blob.bin", ws, authorised=True)["strings"]
    (ws / "ok.py").write_text("print('debug-ok')\n")
    out = audit_mod.debug_run("ok.py", ws, authorised=True)
    assert out["exit_code"] == 0 and "debug-ok" in out["stdout"]


# ---------- CLI ----------

def test_cli_create_run_report(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    store_dir = str(tmp_path / "store")
    rc = cli_mod.main(["create", "cli mission", "--store", store_dir, "--step", "write=python3 -c \"open('cli.txt','w').write('hi')\""])
    assert rc == 0
    store = MissionStore(tmp_path / "store")
    missions = store.list()
    assert len(missions) == 1
    rc = cli_mod.main(["run", missions[0].mission_id, "--workspace", str(ws), "--store", store_dir])
    assert rc == 0
    assert (ws / "cli.txt").read_text() == "hi"


def test_plugin_register_records_mission_command():
    calls = {}

    class FakeCtx:
        def register_cli_command(self, name, help_text, setup_fn, handler_fn, description=""):
            calls["name"] = name
            calls["setup_fn"] = setup_fn

        def register_command(self, name, handler, description="", args_hint=""):
            calls.setdefault("slash_names", []).append(name)
            calls["slash"] = name
            calls["slash_handler"] = handler

    import importlib.util as _ilu

    spec = importlib.util.spec_from_file_location(
        "mission_control_plugin",
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["mission_control_plugin"] = pkg
    spec.loader.exec_module(pkg)
    pkg.register(FakeCtx())
    assert calls["name"] == "mission"
    assert callable(calls["setup_fn"])
    assert "mission" in calls["slash_names"]
    assert "plan" in calls["slash_names"] and "help" in calls["slash_names"]
    assert callable(calls["slash_handler"])
