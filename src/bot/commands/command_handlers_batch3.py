# Copyright (c) 2025 Stephen Clau
#
# Factorio ISR - Dual Licensed (AGPL-3.0 OR Commercial)
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""Game Control Command Handlers (Batch 3).

Handlers for game control operations:
- ClockCommandHandler: Set or display game daytime
- SpeedCommandHandler: Set game speed
- PromoteCommandHandler: Promote player to admin
- DemoteCommandHandler: Demote player from admin
"""

from typing import Optional, Protocol
from dataclasses import dataclass
import discord
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
# Clock Command Handler
# ============================================================================

class ClockCommandHandler:
    """Set or display game daytime."""

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
        value: Optional[str] = None,
    ) -> CommandResult:
        """Execute clock command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry or 0),
                ephemeral=True,
            )

        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)
        server_name = self.user_context.get_server_display_name(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            if value is None:
                # Display current daytime
                resp = await rcon_client.execute(
                    '/sc local daytime = game.surfaces["nauvis"].daytime; '
                    'local hours = math.floor(daytime * 24); '
                    'local minutes = math.floor((daytime * 24 - hours) * 60); '
                    'rcon.print(string.format("Current daytime: %.2f (🕐 %02d:%02d)", daytime, hours, minutes))'
                )
                embed = self.embed_builder.info_embed(
                    title="🕐 Current Game Clock", message=resp
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            value_lower = value.lower().strip()

            if value_lower in ["day", "eternal-day"]:
                resp = await rcon_client.execute(
                    '/sc game.surfaces["nauvis"].daytime = 0.5; '
                    'game.surfaces["nauvis"].freeze_daytime = 0.5; '
                    'rcon.print("☀️ Set to eternal day (12:00)")'
                )
                embed = self.embed_builder.info_embed(
                    title="☀️ Eternal Day Set",
                    message="Game time is now permanently frozen at noon (12:00)\n\nServer response:\n"
                    + resp,
                )
                logger.info("eternal_day_set", moderator=interaction.user.name)
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif value_lower in ["night", "eternal-night"]:
                resp = await rcon_client.execute(
                    '/sc game.surfaces["nauvis"].daytime = 0.0; '
                    'game.surfaces["nauvis"].freeze_daytime = 0.0; '
                    'rcon.print("🌙 Set to eternal night (00:00)")'
                )
                embed = self.embed_builder.info_embed(
                    title="🌙 Eternal Night Set",
                    message="Game time is now permanently frozen at midnight (00:00)\n\nServer response:\n"
                    + resp,
                )
                logger.info("eternal_night_set", moderator=interaction.user.name)
                return CommandResult(success=True, embed=embed, ephemeral=False)

            else:
                try:
                    daytime_value = float(value_lower)
                    if not 0.0 <= daytime_value <= 1.0:
                        raise ValueError("Value must be between 0.0 and 1.0")

                    resp = await rcon_client.execute(
                        f'/sc game.surfaces["nauvis"].daytime = {daytime_value}; '
                        f'game.surfaces["nauvis"].freeze_daytime = nil; '
                        f'local hours = math.floor({daytime_value} * 24); '
                        f'local minutes = math.floor(({daytime_value} * 24 - hours) * 60); '
                        f'rcon.print(string.format("Set daytime to %.2f (🕐 %02d:%02d)", {daytime_value}, hours, minutes))'
                    )
                    time_desc = (
                        "noon"
                        if abs(daytime_value - 0.5) < 0.05
                        else ("midnight" if daytime_value < 0.05 else f"{daytime_value:.2f}")
                    )
                    embed = self.embed_builder.info_embed(
                        title="🕐 Game Clock Updated",
                        message=f"Game time set to: **{time_desc}**\n\nServer response:\n{resp}",
                    )
                    logger.info(
                        "daytime_set", value=daytime_value, moderator=interaction.user.name
                    )
                    return CommandResult(success=True, embed=embed, ephemeral=False)

                except ValueError:
                    return CommandResult(
                        success=False,
                        error_embed=self.embed_builder.error_embed(
                            f"Invalid time value: {value}\n\nValid formats:\n"
                            f"- 'day' or 'eternal-day' → Eternal noon\n"
                            f"- 'night' or 'eternal-night' → Eternal midnight\n"
                            f"- 0.0-1.0 → Custom time (0=midnight, 0.5=noon)"
                        ),
                        ephemeral=True,
                    )

        except Exception as e:
            logger.error("clock_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Clock command failed: {str(e)}"),
                ephemeral=True,
            )


# ============================================================================
# Speed Command Handler
# ============================================================================

class SpeedCommandHandler:
    """Set game speed."""

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
        value: float,
    ) -> CommandResult:
        """Execute speed command."""
        # Validate range
        if not 0.1 <= value <= 10.0:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    "Speed must be between 0.1 and 10.0"
                ),
                ephemeral=True,
            )

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
            await rcon_client.execute(f"/sc game.speed = {value}")

            embed = discord.Embed(
                title="⚡ Game Speed Set",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="New Speed", value=f"{value}x", inline=True)
            if value < 1.0:
                embed.add_field(name="Effect", value="⬋ Slower", inline=True)
            elif value > 1.0:
                embed.add_field(name="Effect", value="⬊ Faster", inline=True)
            else:
                embed.add_field(name="Effect", value="➡️ Normal", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "game_speed_set",
                speed=value,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("speed_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Failed to set speed: {str(e)}"),
                ephemeral=True,
            )


# ============================================================================
# Promote Command Handler
# ============================================================================

class PromoteCommandHandler:
    """Promote player to admin."""

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
    ) -> CommandResult:
        """Execute promote command."""
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
            await rcon_client.execute(f"/promote {player}")

            embed = discord.Embed(
                title="👑 Player Promoted",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Role", value="Administrator", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_promoted",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("promote_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to promote player: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Demote Command Handler
# ============================================================================

class DemoteCommandHandler:
    """Demote player from admin."""

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
    ) -> CommandResult:
        """Execute demote command."""
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
            await rcon_client.execute(f"/demote {player}")

            embed = discord.Embed(
                title="📙 Player Demoted",
                color=self.embed_builder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Role", value="Player", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_demoted",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("demote_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to demote player: {str(e)}"
                ),
                ephemeral=True,
            )
