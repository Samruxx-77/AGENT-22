"""WhatsApp Cloud mission-control layer (Phase 3, official API only).

This is NOT a second WhatsApp client and it does NOT change any
account configuration. The real gateway is the repo's existing
WhatsApp Cloud adapter (plugins/platforms/whatsapp_cloud, official
Meta Cloud API: Graph API outbound, aiohttp webhook with
X-Hub-Signature-256 verification inbound), which is functional and
is reused as-is. The older WhatsApp Web bridge
(plugins/platforms/whatsapp, Node.js Baileys) is NOT used: it is
unofficial, less maintainable, and risks the number being banned.

WhatsApp-specific rules, on top of platforms.dispatch():
  * Identity is the phone number (E.164), exact match, from the
    webhook metadata -- never a display/profile name, which arrives
    in webhook contacts[] and is untrusted.
  * Authorization is the same mapping as every other platform:
    the phone number must be mapped to SAM (owner) or an admin for
    control commands, any mapped role for queries. Unmapped numbers
    get a denial, not a mission answer.
  * Webhook verification: verify_webhook() compares the incoming
    hub.verify_token to the configured token in constant time and
    returns the challenge only on match, else None. verify_signature()
    HMAC-SHA256s the raw body with the app secret and compares in
    constant time. Secrets are read from env by the real adapter;
    this module never prints them and never accepts them as chat
    arguments.
  * 24-hour window: after 24 hours without a user message, Meta only
    allows template messages, not free text. This layer does NOT
    guess the window: the caller passes requires_template (from
    webhook/session state), and the response is flagged accordingly.
    If requires_template is True, the response must be sent as a
    template by the real adapter, not as free text.
  * Health: whatsapp_health() = platforms.health("whatsapp_cloud")
    plus which optional pieces are present (verify token, app
    secret). Missing config = "not_configured", graceful, no crash.

Setup, costs and eligibility -- READ BEFORE CHANGING ANY ACCOUNT
(see AGENT22_PLATFORMS.md for the full checklist):
  * Required Meta account: a Meta developer app + a WhatsApp Business
    Account (WABA) + a phone number registered to that WABA. The
    number must NOT already be registered on WhatsApp (personal app
    or Business app) -- Meta rejects already-registered numbers.
    Do NOT assume SAM's US number (created via Proton VPN, purpose
    not yet stated) is eligible: eligibility is per-number and must
    be checked in the Meta dashboard at setup time, before any
    migration. This build makes NO account change and NO assumption.
  * Credentials (env only, never in chat): WHATSAPP_CLOUD_PHONE_NUMBER_ID,
    WHATSAPP_CLOUD_ACCESS_TOKEN (System User permanent token),
    WHATSAPP_CLOUD_APP_SECRET, WHATSAPP_CLOUD_VERIFY_TOKEN,
    WHATSAPP_CLOUD_WABA_ID. Webhook: public HTTPS URL, path
    /whatsapp/webhook (default), port 8090 (default), GET handshake
    with hub.verify_token, POST with X-Hub-Signature-256.
  * Message restrictions: 24-hour customer-service window for free
    text; outside it, approved templates only. Business-initiated
    messages must use templates. Media, buttons and voice notes are
    supported by the real adapter, but every outbound message still
    goes through the allowlist.
  * Costs: DO NOT assume free. Meta charges per 24-hour conversation,
    by category (utility / marketing / authentication / service)
    and by destination country, and rates change. Test numbers in
    the Meta dashboard are for testing only. Verify the current
    Meta pricing page at setup time and budget for it; no price is
    asserted in this module, because any price asserted here would
    be stale or country-wrong.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Any

try:
    from .platforms import IdentityMapping, dispatch, health
except ImportError:  # loaded as standalone files in tests
    from platforms import IdentityMapping, dispatch, health


def whatsapp_health(env: dict[str, str] | None = None) -> dict[str, Any]:
    """WhatsApp Cloud gateway readiness + optional pieces (presence only)."""
    env = env if env is not None else os.environ
    result = health("whatsapp_cloud", env)
    result.update({
        "verify_token_present": bool(env.get("WHATSAPP_CLOUD_VERIFY_TOKEN")),
        "app_secret_present": bool(env.get("WHATSAPP_CLOUD_APP_SECRET")),
        "waba_id_present": bool(env.get("WHATSAPP_CLOUD_WABA_ID")),
        "webhook_path_default": "/whatsapp/webhook",
        "webhook_port_default": 8090,
        "real_adapter": "plugins/platforms/whatsapp_cloud (official Meta Cloud API) — reused, not replaced",
        "note": "No account change is made by this module. Verify number eligibility and current Meta pricing in the dashboard before setup.",
    })
    return result


def verify_webhook(mode: str, token: str, challenge: str, configured_token: str) -> str | None:
    """Return the challenge only on a constant-time token match."""
    if mode != "subscribe":
        return None
    if not configured_token or not hmac.compare_digest(token, configured_token):
        return None
    return challenge


def verify_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    """Verify X-Hub-Signature-256 (sha256=<hex>) in constant time."""
    if not app_secret or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header[len("sha256="):], expected)


def handle_whatsapp_command(
    phone_number: str,
    command: str,
    store_dir: str | Path,
    requires_template: bool = False,
    mapping: IdentityMapping | None = None,
) -> dict[str, Any]:
    """WhatsApp command: shared dispatch, flagged for template if needed."""
    result = dispatch("whatsapp_cloud", phone_number, command, store_dir, mapping=mapping)
    result["platform"] = "whatsapp_cloud"
    result["requires_template"] = requires_template
    if requires_template and result.get("ok"):
        result["note"] = "24-hour window closed: send this as an approved template via the real adapter, not as free text."
    return result
