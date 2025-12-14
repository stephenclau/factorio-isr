# Copyright (c) 2025 Stephen Clau
#
# Factorio ISR - Dual Licensed (AGPL-3.0 OR Commercial)
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""Server Management Command Handlers (Batch 2).

Handlers for server management operations:
- SaveCommandHandler: Save the game
- BroadcastCommandHandler: Send message to all players
- WhisperCommandHandler: Send private message to player
- WhitelistCommandHandler: Manage server whitelist (multi-action dispatch)
"""

from typing import Optional, Protocol
from dataclasses import dataclass
import discord
import re
import structlog

logger = structlog.get_logger()


class UserContextProvider(Protocol):
    def get_server_display_name(self, user_id: int) -> str: ...
    def get_rcon_for_user(self, user_id: int) -> Optional["RconClient"]: ...


class RconClient(Protocol):
    @property
    def is_connected(self) -> bool: ...
    async def execute(self, command: str) -> str: ...


class RateLimiter(Protocol):
    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[int]]: ...


class EmbedBuilderType(Protocol):
    @staticmethod
    def error_embed(message: str) -> discord.Embed: ...
    @staticmethod
    def cooldown_embed(retry_seconds: int) -> discord.Embed: ...
    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed: ...
    COLOR_WARNING: int
    COLOR_SUCCESS: int


@dataclass
class CommandResult:
    success: bool
    embed: Optional[discord.Embed] = None
    error_embed: Optional[discord.Embed] = None
    ephemeral: bool = False


# ============================================================================
# Save Command Handler
# ============================================================================

class SaveCommandHandler:
    """Save the game."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        name: Optional[str] = None,
    ) -> CommandResult:
        """Execute save command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry or 0),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            cmd = f"/save {name}" if name else "/save"
            resp = await rcon_client.execute(cmd)

            # Parse save name from response
            if name:
                label = name
            else:
                match = re.search(r"/([^/]+?)\.zip", resp)
                if match:
                    label = match.group(1)
                else:
                    match = re.search(r"Saving (?:map )?to ([\w-]+)", resp)
                    label = match.group(1) if match else "current save"

            embed = self.embed_builder.info_embed(
                title="💾 Game Saved",
                message=f"Save name: **{label}**\n\nServer response:\n{resp}",
            )
            embed.color = self.embed_builder.COLOR_SUCCESS

            logger.info(
                "game_saved",
                save_name=label,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("save_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Failed to save game: {str(e)}"),
                ephemeral=True,
            )


# ============================================================================
# Broadcast Command Handler
# ============================================================================

class BroadcastCommandHandler:
    """Send message to all players."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> CommandResult:
        """Execute broadcast command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry or 0),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            escaped_msg = message.replace('"', '\\"')
            await rcon_client.execute(f'/sc game.print("[color=pink]{escaped_msg}[/color]")')

            embed = self.embed_builder.info_embed(
                title="📢 Broadcast Sent",
                message=f"Message: _{message}_\n\nAll online players have been notified.",
            )
            embed.color = self.embed_builder.COLOR_SUCCESS

            logger.info(
                "message_broadcast",
                message=message,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("broadcast_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Broadcast failed: {str(e)}"),
                ephemeral=True,
            )


# ============================================================================
# Whisper Command Handler
# ============================================================================

class WhisperCommandHandler:
    """Send private message to player."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        message: str,
    ) -> CommandResult:
        """Execute whisper command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry or 0),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            await rcon_client.execute(f"/whisper {player} {message}")

            embed = discord.Embed(
                title="💬 Private Message Sent",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Message", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "whisper_sent",
                player=player,
                message=message[:50],
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("whisper_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Failed to send message: {str(e)}"),
                ephemeral=True,
            )


# ============================================================================
# Whitelist Command Handler (Multi-action dispatch)
# ============================================================================

class WhitelistCommandHandler:
    """Manage server whitelist (multi-action: add/remove/list/enable/disable)."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        action: str,
        player: Optional[str] = None,
    ) -> CommandResult:
        """Execute whitelist command with multi-action dispatch."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry or 0),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        action_lower = action.lower().strip()

        try:
            if action_lower == "list":
                resp = await rcon_client.execute("/whitelist get")
                embed = self.embed_builder.info_embed(
                    title="📋 Whitelist", message=resp
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif action_lower == "enable":
                resp = await rcon_client.execute("/whitelist enable")
                embed = self.embed_builder.info_embed(
                    title="✅ Whitelist Enabled", message=resp
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif action_lower == "disable":
                resp = await rcon_client.execute("/whitelist disable")
                embed = self.embed_builder.info_embed(
                    title="⚠️ Whitelist Disabled", message=resp
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif action_lower == "add":
                if not player:
                    return CommandResult(
                        success=False,
                        error_embed=self.embed_builder.error_embed(
                            "Player name required for 'add' action"
                        ),
                        ephemeral=True,
                    )
                resp = await rcon_client.execute(f"/whitelist add {player}")
                embed = self.embed_builder.info_embed(
                    title=f"✅ {player} Added to Whitelist", message=resp
                )
                logger.info(
                    "whitelist_add", player=player, moderator=interaction.user.name
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif action_lower == "remove":
                if not player:
                    return CommandResult(
                        success=False,
                        error_embed=self.embed_builder.error_embed(
                            "Player name required for 'remove' action"
                        ),
                        ephemeral=True,
                    )
                resp = await rcon_client.execute(f"/whitelist remove {player}")
                embed = self.embed_builder.info_embed(
                    title=f"🚫 {player} Removed from Whitelist", message=resp
                )
                logger.info(
                    "whitelist_remove", player=player, moderator=interaction.user.name
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            else:
                return CommandResult(
                    success=False,
                    error_embed=self.embed_builder.error_embed(
                        f"Invalid action: {action}\n\nValid actions: add, remove, list, enable, disable"
                    ),
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(
                "whitelist_command_failed",
                error=str(e),
                action=action_lower,
                player=player,
            )
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Whitelist command failed: {str(e)}"
                ),
                ephemeral=True,
            )
