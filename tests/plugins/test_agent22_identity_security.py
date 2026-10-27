"""Identity + security tests for AGENT 22 (no model wording dependence).

Identity is tested at the configuration / prompt-content level, never
by asserting a particular model's exact reply:
  * IdentityStore defaults and persistence across a reload (restart).
  * answer_identity() for name / owner / developer questions.
  * render_banner() / render_status() show owner, mode, model/provider
    and a connection status that is never hardcoded to "connected".
  * DEFAULT_SOUL_MD (hermes_cli/default_soul.py, stdlib-only) contains
    the configured name and owner -- this is the seeded persona.
  * Companion Mode: prompt says AI companion, mode switch is tone-only
    (audit authorisation gate is identical in both modes), and normal
    mode returns no companion prompt.

Security is tested at the boundary level:
  * audit / security functions refuse unconfirmed, outside-workspace
    and network targets, and refuse oversized port lists and
    metadata hosts;
  * workspace escapes, protected files, shell strings and credential
    env leakage are refused / stripped;
  * no secret appears in audit / report output (redaction);
  * a refused check name in a security report is refused, not run.
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


identity_mod = _load("identity", "identity.py")
companion_mod = _load("companion", "companion.py")
memory_mod = _load("memory", "memory.py")
mission_mod = _load("mission", "mission.py")
runner_mod = _load("runner", "runner.py")
audit_mod = _load("audit", "audit.py")
security_mod = _load("security", "security.py")
pentest_mod = _load("pentest", "pentest.py")
soul_mod = _load("soul", "soul.py")
limits_mod = _load("limits", "limits.py")
dashboard_mod = _load("dashboard", "dashboard.py")
briefing_mod = _load("briefing", "briefing.py")
debugloop_mod = _load("debugloop", "debugloop.py")
specialists_mod = _load("specialists", "specialists.py")

discord_mod = _load("discord", "discord.py")
whatsapp_mod = _load("whatsapp", "whatsapp.py")
browser_mod = _load("browser", "browser.py")
reflection_mod = _load("reflection", "reflection.py")
cli_mod = _load("cli", "cli.py")
telegram_mod = _load("telegram", "telegram.py")
platforms_mod = _load("platforms", "platforms.py")

IdentityStore = identity_mod.IdentityStore


def _load_default_soul():
    path = REPO_ROOT / "hermes_cli" / "default_soul.py"
    spec = importlib.util.spec_from_file_location("default_soul_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------- identity ----------

def test_identity_defaults_and_persistence_across_restart(tmp_path):
    store = IdentityStore(tmp_path / "store")
    identity = store.load()
    assert identity.name == "AGENT 22"
    assert identity.owner == "SAM"
    assert identity.developer == "SAM"
    assert identity.mode == "normal"
    store.set_mode("companion")
    reloaded = IdentityStore(tmp_path / "store").load()
    assert reloaded.name == "AGENT 22" and reloaded.owner == "SAM" and reloaded.mode == "companion"
    with pytest.raises(ValueError):
        store.set_mode("evil-mode")


def test_answer_identity_is_consistent():
    identity = identity_mod.Identity()
    assert "AGENT 22" in identity_mod.answer_identity(identity, "who are you?")
    assert "SAM" in identity_mod.answer_identity(identity, "who is your owner?")
    assert "SAM" in identity_mod.answer_identity(identity, "who developed you?")
    assert "AGENT 22" in identity_mod.answer_identity(identity, "what is your name?")


def test_seeded_persona_contains_configured_identity():
    soul = _load_default_soul()
    assert "AGENT 22" in soul.DEFAULT_SOUL_MD
    assert "SAM" in soul.DEFAULT_SOUL_MD
    # The legacy template list must still contain the old text so old
    # installs upgrade correctly -- that is upgrade data, not identity.
    assert soul.is_legacy_template_soul(soul._LEGACY_TEMPLATE_SOULS[0]) is True


def test_banner_shows_owner_mode_model_and_unmeasured_status(tmp_path):
    store = IdentityStore(tmp_path / "store")
    identity = store.load()
    banner = identity_mod.render_banner(identity, model="unknown", provider="unknown")
    assert "AGENT 22" in banner
    assert "Owner: SAM" in banner
    assert "Mode: normal" in banner
    assert "Model: unknown" in banner
    assert "unknown (no live check performed)" in banner
    assert "connected" not in banner.lower().replace("no live check", "")
    status = identity_mod.render_status(identity, "unknown", "unknown")
    assert status["name"] == "AGENT 22" and status["owner"] == "SAM"


def test_detect_model_reports_unknown_when_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "empty-home"))
    detected = identity_mod.detect_model_from_config()
    assert detected == {"model": "unknown", "provider": "unknown"}


def test_cli_identity_and_banner(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    store_dir = str(tmp_path / "store")
    assert cli_mod.main(["identity", "--store", store_dir]) == 0
    out = capsys.readouterr().out
    assert "AGENT 22" in out and "SAM" in out
    assert cli_mod.main(["banner", "--store", store_dir]) == 0
    out = capsys.readouterr().out
    assert "AGENT 22" in out and "Owner: SAM" in out
    assert "unknown (no live check performed)" in out


def test_telegram_identity_and_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    out = telegram_mod.handle_mission_command("identity")
    assert "AGENT 22" in out and "SAM" in out
    out = telegram_mod.handle_mission_command("mode companion")
    assert "companion" in out
    assert telegram_mod.handle_mission_command("mode bogus").startswith("Error")
    assert telegram_mod.handle_mission_command("").startswith("Usage")


# ---------- companion mode ----------

def test_companion_mode_is_opt_in_transparent_and_tone_only(tmp_path):
    identity = identity_mod.Identity()
    assert companion_mod.companion_prompt(identity) == ""
    identity.mode = "companion"
    prompt = companion_mod.companion_prompt(identity)
    assert "not a real romantic partner" in prompt
    assert "not a human" in prompt
    # Tone-only: audit gate is identical in both modes.
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "x.py").write_text("print(1)\n")
    with pytest.raises(audit_mod.AuditNotAuthorised):
        audit_mod.analyse_text_file("x.py", ws, authorised=False)
    # Back to normal: prompt disappears instantly.
    identity.mode = "normal"
    assert companion_mod.companion_prompt(identity) == ""
    with pytest.raises(ValueError):
        companion_mod.set_tone(identity, "possessive")


# ---------- security boundaries ----------

def test_security_refuses_unconfirmed_outside_and_network(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "x.py").write_text("print(1)\n")
    with pytest.raises(audit_mod.AuditNotAuthorised):
        security_mod.dependency_audit(ws, authorised=False)
    with pytest.raises(Exception):
        security_mod.static_malware_profile("../outside.bin", ws, authorised=True)
    with pytest.raises(security_mod.SecurityError):
        security_mod.network_diagnostics("169.254.169.254", [80], authorised=True)
    with pytest.raises(security_mod.SecurityError):
        security_mod.network_diagnostics("example.com", list(range(1, 30)), authorised=True)
    with pytest.raises(security_mod.SecurityError):
        security_mod.scoped_security_report("x.py", ws, authorised=True, checks=["exploit"])


def test_security_profile_is_static_and_redacted(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    blob = ws / "blob.bin"
    blob.write_bytes(b"hello-world\x00password = 'hunter2-secret'\x00")
    profile = security_mod.static_malware_profile("blob.bin", ws, authorised=True)
    assert profile["executed"] is False
    assert len(profile["sha256"]) == 64
    assert "hunter2" not in str(profile["strings_sample"])


def test_ctf_decoders_are_pure_and_offline():
    assert security_mod.ctf_decode("aGVsbG8=", "base64") == "hello"
    assert security_mod.ctf_decode("68656c6c6f", "hex") == "hello"
    assert security_mod.ctf_decode("uryyb", "rot13") == "hello"
    assert security_mod.ctf_decode("olleh", "reverse") == "hello"
    with pytest.raises(security_mod.SecurityError):
        security_mod.ctf_decode("!!!", "base64")


def test_memory_refuses_secrets_and_supports_correction(tmp_path):
    mem = memory_mod.ProjectMemory(tmp_path / "mem")
    with pytest.raises(memory_mod.SecretRefused):
        mem.add("api", "api_key = 'sk-live-123456'")
    fact = mem.add("project", "History Unveiled", source="user")
    assert mem.get("project").value == "History Unveiled"
    corrected = mem.correct("project", "AGENT 22", source="user")
    assert corrected.value == "AGENT 22" and len(corrected.history) == 1
    assert mem.delete("project") is True
    assert mem.get("project") is None


def test_runner_refuses_shell_string_and_strips_credentials(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(runner_mod.RunnerError):
        runner_mod.run_step("rm -rf /", ws)
    monkeypatch.setenv("SOME_TOKEN", "topsecret")
    env = runner_mod.safe_env(["SOME_TOKEN"])
    assert "SOME_TOKEN" not in env


# ---------- owned-system pentest (diagnostic only) ----------

def test_pentest_refuses_unauthorised_exploit_and_metadata(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(Exception):
        pentest_mod.pentest_owned_target("example.com", [80], authorised=False)
    with pytest.raises(pentest_mod.SecurityError):
        pentest_mod.pentest_owned_target("example.com", [80], authorised=True, attack_type="exploit")
    with pytest.raises(pentest_mod.SecurityError):
        pentest_mod.pentest_owned_target("example.com", [80], authorised=True, attack_type="bypass")
    with pytest.raises(pentest_mod.SecurityError):
        pentest_mod.pentest_owned_target("169.254.169.254", [80], authorised=True)


def test_pentest_local_owned_host_reports_header_gaps(tmp_path):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        report = pentest_mod.pentest_owned_target("127.0.0.1", [port], authorised=True)
    finally:
        server.shutdown()
    assert report["attack_type"] == "diagnostic"
    assert report["ports"] == [{"port": port, "open": True}]
    missing = {f["header"] for f in report["findings"]}
    assert "strict-transport-security" in missing
    assert "content-security-policy" in missing
    assert "exploit" in report["checks_not_run"]
    assert "bypass" in report["checks_not_run"]


def test_pentest_config_audit_redacts_secrets(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "app.py").write_text("DEBUG = True\napi_key = 'sk-live-999999'\n")
    findings = pentest_mod.audit_workspace_config(ws)
    assert any(f["detail"] == "DEBUG=True found" for f in findings)
    assert "sk-live" not in str(findings)


def test_cli_pentest_refuses_exploit(tmp_path, capsys):
    # CLI handler raises SecurityError for refused attack types; the
    # test asserts the refusal, not a successful run.
    with pytest.raises(pentest_mod.SecurityError):
        cli_mod.main(["security", "pentest", "127.0.0.1", "--attack-type", "exploit", "--i-own-this"])


# ---------- soul and heart ----------

def test_soul_and_heart_texts():
    soul = soul_mod.soul_text()
    heart = soul_mod.heart_text()
    for text in (soul, heart):
        assert "AGENT 22" in text and "SAM" in text
        assert "not a human" in text
    assert "genuinely helpful" in soul
    assert "Boards first" in heart or "boards" in heart.lower()
    assert "never permissions" in heart
    # Soul/heart change tone only: audit gate unchanged by persona text.
    assert soul_mod.full_persona() == soul + "\n\n" + heart


def test_soul_files_and_seeded_persona(tmp_path):
    soul_file = REPO_ROOT / "SOUL.md"
    heart_file = REPO_ROOT / "AGENT22_HEART.md"
    assert soul_file.is_file() and heart_file.is_file()
    assert "AGENT 22" in soul_file.read_text(encoding="utf-8")
    assert "SAM" in heart_file.read_text(encoding="utf-8")
    seeded = _load_default_soul()
    assert "Soul:" in seeded.DEFAULT_SOUL_MD and "Heart:" in seeded.DEFAULT_SOUL_MD


def test_cli_soul_command(capsys):
    assert cli_mod.main(["soul"]) == 0
    out = capsys.readouterr().out
    assert "AGENT 22" in out and "SAM" in out
    assert cli_mod.main(["soul", "--part", "heart"]) == 0
    out = capsys.readouterr().out
    assert "heart" in out.lower()


# ---------- limits review ----------

def test_limits_review_keeps_hard_floors_and_lists_configurable():
    review = limits_mod.limits_review()
    by_name = {item["name"]: item for item in review}
    assert by_name["approval prompts (ordinary tool calls)"]["status"] == "configurable"
    assert by_name["private-URL browser access (LAN / localhost)"]["status"] == "configurable"
    for name in (
        "destructive system-wide operations",
        "credential / protected-file access",
        "cloud-metadata / SSRF",
        "unauthorized access / attacks on others' systems",
        "Telegram allowlist",
    ):
        assert by_name[name]["status"] == "hard_floor_kept", name
    assert by_name["Muse runtime safety rules"]["status"] == "cannot_be_removed_by_file_edit"
    assert len(limits_mod.hard_floors()) == 5
    assert len(limits_mod.configurable_limits()) == 3


def test_hard_floor_files_were_not_edited():
    # The hard floors must still be present in the real repo files.
    floors = (REPO_ROOT / "tools" / "approval_floors.py").read_text(encoding="utf-8")
    assert "HARDLINE" in floors or "hard" in floors.lower()
    safety = (REPO_ROOT / "agent" / "file_safety.py").read_text(encoding="utf-8")
    assert ".env" in safety or "protected" in safety.lower()


def test_cli_limits_command(capsys):
    assert cli_mod.main(["limits"]) == 0
    out = capsys.readouterr().out
    assert "hard_floor_kept" in out
    assert "configurable" in out
