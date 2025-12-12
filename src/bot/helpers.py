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

"""Helper utilities for Discord bot operations.

Includes presence management, uptime formatting, channel utilities, and game state helpers.
"""

from datetime import timedelta
from typing import Any, Optional
import discord
import structlog

logger = structlog.get_logger()


class PresenceManager:
    """Manage Discord bot presence status."""

    def __init__(self, bot: Any) -> None:
        """
        Initialize presence manager.

        Args:
            bot: DiscordBot instance
        """
        self.bot = bot

    async def update(self) -> None:
        """Update bot presence to reflect RCON connection status."""
        if not self.bot._connected or not hasattr(self.bot, "user") or self.bot.user is None:
            return

        try:
            status_text = "🔺 RCON (0/0)"
            status = discord.Status.idle
            activity_type = discord.ActivityType.watching

            if self.bot.server_manager:
                # Multi-server mode: show connected/total count
                status_summary = self.bot.server_manager.get_status_summary()
                total = len(status_summary)
                connected_count = sum(1 for v in status_summary.values() if v)

                if total > 0:
                    if connected_count == total:
                        status_text = f"🔹 RCON ({connected_count}/{total})"
                        status = discord.Status.online
                    elif connected_count > 0:
                        status_text = f"🔸 RCON ({connected_count}/{total})"
                        status = discord.Status.idle
                    else:
                        status_text = f"🔺 RCON (0/{total})"
                        status = discord.Status.idle

            activity = discord.Activity(
                type=activity_type,
                name=f"{status_text} | /factorio help",
            )

            await self.bot.change_presence(status=status, activity=activity)
            logger.debug("presence_updated", status=status_text)
        except Exception as e:
            logger.warning("presence_update_failed", error=str(e))


def format_uptime(uptime_delta: timedelta) -> str:
    """
    Format a timedelta as a human-readable uptime string.

    Args:
        uptime_delta: timedelta object representing uptime

    Returns:
        Formatted uptime string (e.g., "2h 15m", "45m", "3d 12h")
    """
    total_seconds = int(uptime_delta.total_seconds())

    # Calculate components
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    # Build readable string
    parts = []
    if days == 0 and hours == 0 and minutes == 0 and total_seconds < 60:
        return "< 1m"
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or (days == 0 and hours == 0):
        parts.append(f"{minutes}m")

    return " ".join(parts)


async def get_seed(rcon_client: Any) -> str:
    """
    Get Factorio map seed via RCON.

    Queries the server for the seed value using proper Lua syntax.
    This extracts the raw seed number from the game state.

    Args:
        rcon_client: RconClient instance to query

    Returns:
        Seed as string or "Unknown" on error

    Raises:
        Exception: Propagates RCON communication errors for caller handling
    """
    if not rcon_client or not rcon_client.is_connected:
        logger.debug("get_seed_client_unavailable")
        return "Unknown"

    try:
        # Query server seed using proper Lua syntax
        response = await rcon_client.execute('/sc rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)')

        # Log the raw response for debugging
        logger.debug("get_seed_response", response=response, length=len(response))

        # Check if response is empty or invalid
        if not response or not response.strip():
            logger.warning("get_seed_empty_response")
            return "Unknown"

        # The seed should be a numeric value; validate it
        seed_value = response.strip()
        try:
            # Verify it's a valid integer
            int(seed_value)
        except ValueError as e:
            logger.warning(
                "get_seed_parse_failed",
                response=response,
                error=str(e),
            )
            return "Unknown"

        logger.debug("get_seed_retrieved", seed=seed_value)
        return seed_value

    except Exception as e:
        logger.warning("get_seed_query_failed", error=str(e), exc_info=True)
        return "Unknown"


async def get_game_uptime(rcon_client: Any) -> str:
    """
    Get actual Factorio server uptime via RCON.

    Args:
        rcon_client: RconClient instance to query

    Returns:
        Formatted uptime string or "Unknown" on error
    """
    if not rcon_client or not rcon_client.is_connected:
        return "Unknown"

    try:
        # Query server ticks using proper Lua syntax
        response = await rcon_client.execute("/sc rcon.print(game.tick)")

        # Log the raw response for debugging
        logger.debug("game_uptime_response", response=response, length=len(response))

        # Check if response is empty or invalid
        if not response or not response.strip():
            logger.warning("game_uptime_empty_response")
            return "Unknown"

        # Try to parse the tick count
        try:
            ticks = int(response.strip())
        except ValueError as e:
            logger.warning("game_uptime_parse_failed", response=response, error=str(e))
            return "Unknown"

        # Validate tick count is reasonable
        if ticks < 0:
            logger.warning("game_uptime_negative_ticks", ticks=ticks)
            return "Unknown"

        # Convert ticks to seconds (60 ticks = 1 second)
        total_seconds = ticks // 60

        # Use format_uptime helper
        uptime_delta = timedelta(seconds=total_seconds)
        formatted = format_uptime(uptime_delta)
        logger.debug(
            "game_uptime_calculated",
            ticks=ticks,
            seconds=total_seconds,
            formatted=formatted,
        )
        return formatted

    except Exception as e:
        logger.warning("game_uptime_query_failed", error=str(e), exc_info=True)
        return "Unknown"


async def send_to_channel(bot: Any, channel_id: int, embed: discord.Embed) -> None:
    """
    Helper to send embed to a specific channel.

    Args:
        bot: DiscordBot instance
        channel_id: Discord channel ID
        embed: Embed to send
    """
    try:
        channel = bot.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(embed=embed)
    except discord.errors.Forbidden:
        logger.warning("send_to_channel_forbidden", channel_id=channel_id)
    except Exception as e:
        logger.warning("send_to_channel_failed", channel_id=channel_id, error=str(e))
