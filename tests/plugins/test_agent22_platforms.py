"""Multi-platform tests: shared state, identity by id (never name),
Discord scope/private/file rules, WhatsApp Cloud webhook/signature/
template rules, health graceful failure, and no secrets in output.

No real Discord/WhatsApp gateway, token, or Meta account is used.
Gateway readiness is tested by env presence only, with dummy values
that must never appear in output.
"""

import hashlib
import hmac
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


def _mapping(tmp_path):
    mapping = platforms_mod.IdentityMapping(tmp_path / "store")
    mapping.add("telegram", "111", "SAM", "owner")
    mapping.add("discord", "222", "SAM", "owner")
    mapping.add("discord", "333", "SAM", "user")
    mapping.add("whatsapp_cloud", "+15550001111", "SAM", "owner")
    return mapping


def test_shared_mission_state_across_platforms(tmp_path, monkeypatch):
    home = tmp_path / "home"
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("HERMES_WORKSPACE", str(ws))
    mapping = _mapping(tmp_path)
    # Start on Telegram.
    result = platforms_mod.dispatch("telegram", "111", "plan Shared mission", home / "missions", mapping=mapping)
    assert result["ok"] is True
    mission_id = result["response"].split(":")[1].strip().split()[0]
    # Check from Discord (same id, same store) and WhatsApp (same id).
    result = platforms_mod.dispatch("discord", "222", f"mission status {mission_id}", home / "missions", mapping=mapping)
    assert result["ok"] is True and mission_id in result["response"]
    result = platforms_mod.dispatch("whatsapp_cloud", "+15550001111", f"mission status {mission_id}", home / "missions", mapping=mapping)
    assert result["ok"] is True and mission_id in result["response"]


def test_display_name_never_authorizes_and_roles_enforced(tmp_path):
    mapping = _mapping(tmp_path)
    # A spoofed display name is not an argument to authorize(); only the id counts.
    with pytest.raises(platforms_mod.NotAuthorized):
        mapping.authorize("telegram", "999", "mission status x")
    # A mapped 'user' may query but not control.
    mapping.authorize("discord", "333", "mission status x")
    with pytest.raises(platforms_mod.NotAuthorized):
        mapping.authorize("discord", "333", "plan Do a thing")
    # Owner may control.
    mapping.authorize("discord", "222", "plan Do a thing")


def test_discord_scope_private_and_file_delivery(tmp_path):
    config = discord_mod.DiscordConfig(allowed_guild_ids=["10"], allowed_channel_ids=["20"], dm_allowed=False)
    mapping = _mapping(tmp_path)
    store_dir = tmp_path / "store" / "missions"
    # Wrong guild denied, even for owner.
    result = discord_mod.handle_discord_command("222", "99", "20", False, "mission list", store_dir, config=config, mapping=mapping)
    assert result["ok"] is False
    # Right guild/channel allowed, and response is private.
    result = discord_mod.handle_discord_command("222", "10", "20", False, "mission list", store_dir, config=config, mapping=mapping)
    assert result["ok"] is True and result["private"] is True
    # DM denied when dm_allowed=False.
    result = discord_mod.handle_discord_command("222", None, None, True, "mission list", store_dir, config=config, mapping=mapping)
    assert result["ok"] is False
    # File delivery: inside workspace ok, outside refused, oversize refused.
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "report.txt").write_text("hello")
    delivered = discord_mod.deliver_file("report.txt", ws)
    assert delivered["private"] is True and delivered["size_bytes"] == 5
    with pytest.raises(Exception):
        discord_mod.deliver_file("../outside.txt", ws)


def test_whatsapp_webhook_signature_and_template_flag(tmp_path):
    secret = "test-app-secret-not-real"
    body = b'{"object":"whatsapp_business_account"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert whatsapp_mod.verify_signature(body, sig, secret) is True
    assert whatsapp_mod.verify_signature(body, "sha256=wrong", secret) is False
    assert whatsapp_mod.verify_webhook("subscribe", "tok123", "chal456", "tok123") == "chal456"
    assert whatsapp_mod.verify_webhook("subscribe", "wrong", "chal456", "tok123") is None
    mapping = _mapping(tmp_path)
    result = whatsapp_mod.handle_whatsapp_command("+15550001111", "mission list", tmp_path / "store" / "missions", requires_template=True, mapping=mapping)
    assert result["ok"] is True and result["requires_template"] is True
    result = whatsapp_mod.handle_whatsapp_command("+19999999999", "mission list", tmp_path / "store" / "missions", mapping=mapping)
    assert result["ok"] is False


def test_health_graceful_failure_and_no_secrets_in_output(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_CLOUD_PHONE_NUMBER_ID", raising=False)
    monkeypatch.delenv("WHATSAPP_CLOUD_ACCESS_TOKEN", raising=False)
    for platform in ("telegram", "discord", "whatsapp_cloud"):
        result = platforms_mod.health(platform)
        assert result["status"] == "not_configured" and result["missing"]
    # With dummy tokens present, health is ready but values never appear.
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "dummy-discord-token-12345")
    monkeypatch.setenv("WHATSAPP_CLOUD_PHONE_NUMBER_ID", "dummy-phone-id-67890")
    monkeypatch.setenv("WHATSAPP_CLOUD_ACCESS_TOKEN", "dummy-wa-token-abcde")
    result = discord_mod.discord_health()
    assert result["status"] == "ready"
    assert "dummy-discord-token-12345" not in str(result)
    result = whatsapp_mod.whatsapp_health()
    assert result["status"] == "ready"
    assert "dummy-wa-token-abcde" not in str(result) and "dummy-phone-id-67890" not in str(result)
    assert cli_mod.main(["platforms", "health"]) == 0
    out = capsys.readouterr().out
    assert "dummy-discord-token-12345" not in out and "dummy-wa-token-abcde" not in out
