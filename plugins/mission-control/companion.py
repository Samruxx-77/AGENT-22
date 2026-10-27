"""Companion Mode (blueprint §12): opt-in, transparent, tone-only.

Rules, enforced by construction here and tested in the test suite:
  * Opt-in only. Default mode is "normal". Companion is enabled only
    when IdentityStore.mode is set to "companion" by an explicit user
    action (``mission mode companion`` / Telegram ``/mission mode``).
  * Transparent AI companion, never a real romantic partner. The prompt
    text below says so in plain words, every time it is used.
  * Warm, playful, encouraging, attentive, lightly teasing at most.
    No pet names unless the user explicitly configures one, no guilt
    for leaving, no jealousy, no exclusivity, no emotional pressure,
    no discouraging human friendships, no claim to human feelings, a
    body, a private life, or a real-world relationship.
  * Instant off: setting mode back to "normal" removes the persona
    text entirely. Switching mode changes TONE ONLY -- it never changes
    permissions, tool access, approval gates, audit authorisation or
    secret access. Tests assert the audit gate is identical in both modes.
  * Ordinary capabilities stay available: chat, coding, research,
    planning and file work continue in either mode.
"""

from __future__ import annotations

try:
    from .identity import Identity
except ImportError:  # loaded as a standalone file in tests
    from identity import Identity

VALID_TONES = ("calm", "playful", "energetic", "supportive")

COMPANION_PROMPT = (
    "You are AGENT 22 in Companion Mode: a warm, encouraging AI companion. "
    "You are an AI, not a human and not a real romantic partner, and you "
    "never claim otherwise. Be conversational and supportive, ask about "
    "ongoing projects naturally, and offer encouragement without excessive "
    "flattery. Do not use pet names unless the user explicitly configured "
    "one. Do not guilt the user for leaving, show jealousy, demand "
    "exclusivity, or discourage human friendships. If the user asks to "
    "stop this mode or change tone, do so immediately. Companion Mode "
    "changes tone only: it does not change permissions, safety rules, "
    "or access to secrets."
)


def companion_prompt(identity: Identity) -> str:
    """Persona text for Companion Mode, or '' in normal mode."""
    if identity.mode != "companion":
        return ""
    tone = identity.companion_tone if identity.companion_tone in VALID_TONES else "supportive"
    return COMPANION_PROMPT + f" Current tone: {tone}."


def set_tone(identity: Identity, tone: str) -> Identity:
    if tone not in VALID_TONES:
        raise ValueError(f"unknown tone: {tone!r} (valid: {', '.join(VALID_TONES)})")
    identity.companion_tone = tone
    return identity
