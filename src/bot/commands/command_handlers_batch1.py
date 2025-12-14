# Copyright (c) 2025 Stephen Clau
#
# This file is part of Factorio ISR.
#
# Factorio ISR is dual-licensed:
#
# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
#    See LICENSE file for full terms
#
# 2. Commercial License
#    For proprietary use without AGPL requirements
#    Contact: licensing@laudiversified.com
#
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""Player Management Command Handlers (Batch 1).

Handlers for player management operations:
- KickCommandHandler: Kick a player from the server
- BanCommandHandler: Ban a player from the server
- UnbanCommandHandler: Unban a player
- MuteCommandHandler: Mute a player from chat
- UnmuteCommandHandler: Unmute a player
"""

from typing import Optional, Protocol
from dataclasses import dataclass
import discord
import structlog

logger = structlog.get_logger()


# ============================================================================
# Protocols (Type-safe dependency contracts)
# ============================================================================

class UserContextProvider(Protocol):
    """Protocol for user context provider."""

    def get_user_server(self, user_id: int) -> str:
        """Get user's current server context."""
        ...

    def get_server_display_name(self, user_id: int) -> str:
        """Get display name of user's current server."""
        ...

    def get_rcon_for_user(self, user_id: int) -> Optional["RconClient"]:
        """Get RCON client for user's current server."""
        ...


class RconClient(Protocol):
    """Protocol for RCON client."""

    @property
    def is_connected(self) -> bool:
        """Whether RCON is connected."""
        ...

    async def execute(self, command: str) -> str:
        """Execute RCON command."""
        ...


class RateLimiter(Protocol):
    """Protocol for rate limiter."""

    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[int]]:
        """Check if user is rate limited. Returns (is_limited, retry_seconds)."""
        ...


class EmbedBuilderType(Protocol):
    """Protocol for embed builder."""

    @staticmethod
    def error_embed(message: str) -> discord.Embed:
        """Create error embed."""
        ...

    @staticmethod
    def cooldown_embed(retry_seconds: int) -> discord.Embed:
        """Create cooldown embed."""
        ...

    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed:
        """Create info embed."""
        ...

    COLOR_WARNING: int
    COLOR_SUCCESS: int


# ============================================================================
# Result Type
# ============================================================================

@dataclass
class CommandResult:
    """Standard result type for command handlers."""

    success: bool
    embed: Optional[discord.Embed] = None
    error_embed: Optional[discord.Embed] = None
    ephemeral: bool = False


# ============================================================================
# Kick Command Handler
# ============================================================================

class KickCommandHandler:
    """Kick a player from the server.

    Dependencies:
    - user_context_provider: Access to user's current server and RCON
    - rate_limiter: Rate limiting for admin operations
    - embed_builder_type: Discord embed formatting
    """

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        """Initialize handler with dependencies."""
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> CommandResult:
        """Execute kick command.

        Args:
            interaction: Discord interaction context
            player: Player name to kick
            reason: Optional reason for kick

        Returns:
            CommandResult with success status and embed
        """
        # Check rate limit
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
                ephemeral=True,
            )

        # Get RCON client
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
            # Execute RCON command
            message = reason if reason else "Kicked by moderator"
            await rcon_client.execute(f"/kick {player} {message}")

            # Build result embed
            embed = discord.Embed(
                title="⚠️ Player Kicked",
                color=self.embed_builder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Reason", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_kicked",
                player=player,
                reason=message,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("kick_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to kick player: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Ban Command Handler
# ============================================================================

class BanCommandHandler:
    """Ban a player from the server."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        """Initialize handler with dependencies."""
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> CommandResult:
        """Execute ban command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
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
            message = reason if reason else "Banned by moderator"
            await rcon_client.execute(f"/ban {player} {message}")

            embed = discord.Embed(
                title="🚫 Player Banned",
                color=discord.Color.from_rgb(220, 20, 60),  # Crimson
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Reason", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_banned",
                player=player,
                reason=message,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("ban_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to ban player: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Unban Command Handler
# ============================================================================

class UnbanCommandHandler:
    """Unban a player."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        """Initialize handler with dependencies."""
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute unban command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
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
            await rcon_client.execute(f"/unban {player}")

            embed = discord.Embed(
                title="✅ Player Unbanned",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_unbanned",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("unban_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to unban player: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Mute Command Handler
# ============================================================================

class MuteCommandHandler:
    """Mute a player from chat."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        """Initialize handler with dependencies."""
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute mute command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
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
            await rcon_client.execute(f"/mute {player}")

            embed = discord.Embed(
                title="🔇 Player Muted",
                color=self.embed_builder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_muted",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("mute_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to mute player: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Unmute Command Handler
# ============================================================================

class UnmuteCommandHandler:
    """Unmute a player."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        """Initialize handler with dependencies."""
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute unmute command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
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
            await rcon_client.execute(f"/unmute {player}")

            embed = discord.Embed(
                title="🔊 Player Unmuted",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_unmuted",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("unmute_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to unmute player: {str(e)}"
                ),
                ephemeral=True,
            )
