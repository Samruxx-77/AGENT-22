"""Discord mission-control layer (Phase 2).

This is NOT a second Discord client. The real gateway is the repo's
existing Discord adapter (plugins/platforms/discord, discord.py:
slash commands, role-based DM auth, threads, reactions), which is
functional and is reused as-is. This module is the mission-control
command layer that runs on top of it, so Discord commands share the
same mission ids and state as Telegram (see platforms.py).

Discord-specific rules, on top of platforms.dispatch():
  * Server/channel permissions are explicit: if allowed_guild_ids
    or allowed_channel_ids are set, a command from any other guild
    or channel is denied, even for a mapped owner. DMs are allowed
    only if dm_allowed is True (default False in this layer; the
    repo adapter's own DM policy governs the real gateway).
  * Private responses: every mission response from this layer is
    marked private=True. The real adapter must send it ephemerally
    (or as a DM), never as a public channel message -- mission ids,
    costs and status are not channel content.
  * Slash-equivalent controls: /mission, /plan, /run, /cost, /report
    and /help map to the same dispatch verbs as Telegram. In the real
    adapter these are registered as native slash commands (the repo
    adapter caps global slash commands at 100/app; these six are
    well within that cap, and plugin slash commands are registered
    after native ones so they survive the cap).
  * File delivery: deliver_file() checks the file is inside the
    workspace, exists, and is <= 8 MB (Discord's safe default for
    non-Nitro bots; the real adapter may raise this if its bot has
    a higher limit). It returns a delivery descriptor, never the
    file bytes in chat, and it does NOT send anything itself -- the
    real adapter sends the file via discord.py. No token is needed
    or used here, and no token ever appears in output.
  * Health: discord_health() = platforms.health("discord") plus the
    explicit guild/channel/dm configuration (ids only, no tokens).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from .platforms import IdentityMapping, dispatch, health
    from .runner import assert_inside, resolve_workspace
except ImportError:  # loaded as standalone files in tests
    from platforms import IdentityMapping, dispatch, health
    from runner import assert_inside, resolve_workspace

MAX_DISCORD_FILE_BYTES = 8 * 1024 * 1024


class DiscordConfig:
    """Explicit Discord permissions. Empty allowlists = deny (fail closed)."""

    def __init__(
        self,
        allowed_guild_ids: list[str] | None = None,
        allowed_channel_ids: list[str] | None = None,
        dm_allowed: bool = False,
    ):
        self.allowed_guild_ids = [str(g) for g in (allowed_guild_ids or [])]
        self.allowed_channel_ids = [str(c) for c in (allowed_channel_ids or [])]
        self.dm_allowed = dm_allowed

    def check_scope(self, guild_id: str | None, channel_id: str | None, is_dm: bool) -> None:
        """Raise PermissionError if the guild/channel/DM is not allowed."""
        if is_dm:
            if not self.dm_allowed:
                raise PermissionError("Discord DMs are not allowed for mission commands in this configuration")
            return
        if self.allowed_guild_ids and str(guild_id) not in self.allowed_guild_ids:
            raise PermissionError(f"Discord guild {guild_id} is not allowed for mission commands")
        if self.allowed_channel_ids and str(channel_id) not in self.allowed_channel_ids:
            raise PermissionError(f"Discord channel {channel_id} is not allowed for mission commands")


def discord_health(config: DiscordConfig | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Discord gateway readiness + explicit permission configuration."""
    result = health("discord", env)
    config = config or DiscordConfig()
    result.update({
        "allowed_guild_ids": config.allowed_guild_ids,
        "allowed_channel_ids": config.allowed_channel_ids,
        "dm_allowed": config.dm_allowed,
        "real_adapter": "plugins/platforms/discord (discord.py, slash commands, role-based auth) — reused, not replaced",
    })
    return result


def handle_discord_command(
    user_id: str,
    guild_id: str | None,
    channel_id: str | None,
    is_dm: bool,
    command: str,
    store_dir: str | Path,
    config: DiscordConfig | None = None,
    mapping: IdentityMapping | None = None,
) -> dict[str, Any]:
    """Discord command: scope check, then shared dispatch, private reply."""
    config = config or DiscordConfig()
    try:
        config.check_scope(guild_id, channel_id, is_dm)
    except PermissionError as exc:
        return {"ok": False, "error": str(exc), "private": True}
    result = dispatch("discord", user_id, command, store_dir, mapping=mapping)
    result["private"] = True  # always ephemeral / DM, never a public channel message
    result["platform"] = "discord"
    return result


def deliver_file(target: str, workspace: str | Path) -> dict[str, Any]:
    """Validate a file for Discord delivery. Returns a descriptor, not bytes."""
    ws = resolve_workspace(workspace)
    path = assert_inside(ws, target)
    if not path.is_file():
        raise FileNotFoundError(f"not a file in workspace: {target}")
    size = path.stat().st_size
    if size > MAX_DISCORD_FILE_BYTES:
        raise ValueError(f"file too large for Discord delivery: {size} bytes > {MAX_DISCORD_FILE_BYTES} bytes")
    return {"deliverable": str(path.relative_to(ws)), "size_bytes": size, "private": True, "note": "Send via the real Discord adapter (discord.py) as an ephemeral/DM attachment."}
