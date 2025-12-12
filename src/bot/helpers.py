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
from typing import Any, Optional, List, Dict
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

# ========================================================================
# HELPER METHODS FOR MODULAR COMMAND ARCHITECTURE
# ========================================================================
class FactorioCommandHelpers:

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

    async def get_version(self) -> str:
        """Get Factorio server version."""
        try:
            response = await self.execute("/version")
            return response.strip() if response else "Unknown"
        except Exception as e:
            logger.warning("get_version_failed", error=str(e))
            raise


    async def get_admins(self) -> List[str]:
        """Get list of server administrators."""
        try:
            response = await self.execute("/admins")
            if not response:
                return []
            admins: List[str] = []
            lines = response.split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("Admins"):
                    admins.append(line.lstrip("-").strip())
            return admins
        except Exception as e:
            logger.warning("get_admins_failed", error=str(e))
            raise

    async def get_time(self) -> int:
        """Get current game time (ticks)."""
        try:
            response = await self.execute("/sc rcon.print(game.tick)")
            return int(response.strip()) if response and response.strip() else 0
        except Exception as e:
            logger.warning("get_time_failed", error=str(e))
            raise

    async def set_time(self, ticks: int) -> None:
        """Set game time (ticks)."""
        try:
            lua = f"/c game.tick = {ticks}"
            await self.execute(lua)
        except Exception as e:
            logger.warning("set_time_failed", error=str(e), ticks=ticks)
            raise

    async def set_game_speed(self, speed: float) -> None:
        """Set game speed multiplier."""
        try:
            lua = f"/c game.speed = {speed}"
            await self.execute(lua)
        except Exception as e:
            logger.warning("set_game_speed_failed", error=str(e), speed=speed)
            raise

    async def kick_player(self, player: str, reason: str = "") -> None:
        """Kick a player from the server."""
        try:
            cmd = f"/kick {player}"
            if reason:
                cmd += f" {reason}"
            await self.execute(cmd)
        except Exception as e:
            logger.warning("kick_player_failed", error=str(e), player=player)
            raise

    async def ban_player(self, player: str, reason: str = "") -> None:
        """Ban a player from the server."""
        try:
            cmd = f"/ban {player}"
            if reason:
                cmd += f" {reason}"
            await self.execute(cmd)
        except Exception as e:
            logger.warning("ban_player_failed", error=str(e), player=player)
            raise

    async def unban_player(self, player: str) -> None:
        """Unban a player from the server."""
        try:
            await self.execute(f"/unban {player}")
        except Exception as e:
            logger.warning("unban_player_failed", error=str(e), player=player)
            raise

    async def mute_player(self, player: str) -> None:
        """Mute a player from chat."""
        try:
            await self.execute(f"/mute {player}")
        except Exception as e:
            logger.warning("mute_player_failed", error=str(e), player=player)
            raise

    async def unmute_player(self, player: str) -> None:
        """Unmute a player in chat."""
        try:
            await self.execute(f"/unmute {player}")
        except Exception as e:
            logger.warning("unmute_player_failed", error=str(e), player=player)
            raise

    async def promote_player(self, player: str) -> None:
        """Promote a player to admin."""
        try:
            await self.execute(f"/promote {player}")
        except Exception as e:
            logger.warning("promote_player_failed", error=str(e), player=player)
            raise

    async def demote_player(self, player: str) -> None:
        """Demote a player from admin."""
        try:
            await self.execute(f"/demote {player}")
        except Exception as e:
            logger.warning("demote_player_failed", error=str(e), player=player)
            raise

    async def save(self, name: str = "auto-save") -> None:
        """Save the game."""
        try:
            cmd = f"/save {name}" if name and name != "auto-save" else "/save"
            await self.execute(cmd)
        except Exception as e:
            logger.warning("save_failed", error=str(e), name=name)
            raise

    async def send_message_to_players(self, message: str) -> None:
        """Broadcast a message to all players."""
        try:
            escaped_msg = message.replace('"', '\\"')
            lua = f'/sc game.print("[color=pink]{escaped_msg}[/color]")'
            await self.execute(lua)
        except Exception as e:
            logger.warning("send_message_to_players_failed", error=str(e))
            raise

    async def send_message_to_player(self, player: str, message: str) -> None:
        """Send a private message to a specific player."""
        try:
            await self.execute(f"/whisper {player} {message}")
        except Exception as e:
            logger.warning("send_message_to_player_failed", error=str(e), player=player)
            raise

    async def whitelist_add(self, player: str) -> None:
        """Add player to whitelist."""
        try:
            await self.execute(f"/whitelist add {player}")
        except Exception as e:
            logger.warning("whitelist_add_failed", error=str(e), player=player)
            raise

    async def whitelist_remove(self, player: str) -> None:
        """Remove player from whitelist."""
        try:
            await self.execute(f"/whitelist remove {player}")
        except Exception as e:
            logger.warning("whitelist_remove_failed", error=str(e), player=player)
            raise

    async def whitelist_list(self) -> List[str]:
        """Get whitelist."""
        try:
            response = await self.execute("/whitelist get")
            if not response:
                return []
            players: List[str] = []
            lines = response.split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("Whitelist") and not line.startswith("---"):
                    players.append(line)
            return players
        except Exception as e:
            logger.warning("whitelist_list_failed", error=str(e))
            raise

    async def whitelist_enable(self) -> None:
        """Enable whitelist."""
        try:
            await self.execute("/whitelist enable")
        except Exception as e:
            logger.warning("whitelist_enable_failed", error=str(e))
            raise

    async def whitelist_disable(self) -> None:
        """Disable whitelist."""
        try:
            await self.execute("/whitelist disable")
        except Exception as e:
            logger.warning("whitelist_disable_failed", error=str(e))
            raise

    async def research_technology(self, technology: str) -> None:
        """Force research a technology."""
        try:
            lua = f'/c game.forces["player"].technologies["{technology}"].researched=true'
            await self.execute(lua)
        except Exception as e:
            logger.warning("research_technology_failed", error=str(e), technology=technology)
            raise

    async def send_command(self, command: str) -> str:
        """Execute raw RCON command."""
        return await self.execute(command)