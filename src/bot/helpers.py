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

Includes presence management, uptime formatting, channel utilities, game state helpers,
and RCON stats formatting for embeds and text messages.
"""

import asyncio
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
        self._presence_task: Optional[asyncio.Task] = None

    async def update(self) -> None:
        """Update bot presence to reflect RCON connection status (one-shot)."""
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

    async def _update_presence_loop(self) -> None:
        """Background loop to update presence every 5 seconds.
        
        This loop runs continuously while the bot is connected and automatically
        stops when the bot disconnects. It will be restarted by on_ready() on
        reconnection.
        """
        logger.info("presence_update_loop_started")
        try:
            while self.bot._connected:
                await self.update()
                await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            logger.info("presence_update_loop_cancelled")
            raise
        except Exception as e:
            logger.error("presence_update_loop_error", error=str(e), exc_info=True)
        finally:
            logger.info("presence_update_loop_stopped")

    async def start(self) -> None:
        """Start the presence update loop if not already running."""
        if self._presence_task is None or self._presence_task.done():
            self._presence_task = asyncio.create_task(self._update_presence_loop())
            logger.info("presence_updater_started")
        else:
            logger.debug("presence_updater_already_running")

    async def stop(self) -> None:
        """Stop the presence update loop."""
        if self._presence_task:
            self._presence_task.cancel()
            try:
                await self._presence_task
            except asyncio.CancelledError:
                pass
            self._presence_task = None
            logger.info("presence_updater_stopped")


# ========================================================================
# MODULE-LEVEL HELPER FUNCTIONS
# ========================================================================

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


# ========================================================================
# RCON STATS FORMATTERS (Pure formatting functions - Phase 2)
# ========================================================================

def format_stats_text(
    server_label: str,
    metrics: Dict[str, Any],
) -> str:
    """
    Format RCON server stats as plain text for Discord message.

    Pure formatting function with no state or RCON dependencies.
    Ready for reuse in slash commands or other Discord outputs.

    Args:
        server_label: Server name/tag string (e.g., "[prod] Factorio ISR")
        metrics: Dict from RconMetricsEngine.gather_all_metrics() with keys:
                 ups, ups_sma, ups_ema, is_paused, last_known_ups,
                 player_count, players, server_time, evolution_factor,
                 evolution_by_surface

    Returns:
        Formatted text message ready for Discord
    """
    lines: List[str] = []
    lines.append(f"📊 **{server_label} Stats**")

    # Check if paused
    if metrics.get("is_paused"):
        last_ups = metrics.get("last_known_ups")
        if last_ups and last_ups > 0:
            lines.append(f"⏸️ Status: Paused (last: {last_ups:.1f} UPS)")
        else:
            lines.append("⏸️ Status: Paused")
    elif metrics.get("ups") is not None:
        ups = float(metrics["ups"])
        sma = metrics.get("ups_sma")
        ema = metrics.get("ups_ema")
        ups_emoji = "✅" if ups >= 59.0 else "⚠️"

        parts = [f"Raw: {ups:.1f}/60.0"]
        if sma is not None:
            parts.append(f"SMA: {float(sma):.1f}")
        if ema is not None:
            parts.append(f"EMA: {float(ema):.1f}")

        lines.append(f"{ups_emoji} UPS: " + " | ".join(parts))

    lines.append(f"👥 Players Online: {metrics.get('player_count')}")
    if metrics.get("players"):
        lines.append("📝 " + ", ".join(metrics["players"]))
    lines.append(f"⏰ Game Time: {metrics.get('server_time')}")

    # Evolution per surface
    evolution_by_surface = metrics.get("evolution_by_surface", {})
    if evolution_by_surface:
        if len(evolution_by_surface) == 1:
            # Single surface - compact format
            surface_name = next(iter(evolution_by_surface.keys()))
            evo_pct = evolution_by_surface[surface_name] * 100.0
            evo_str = f"{evo_pct:.2f}" if evo_pct >= 0.1 else f"{evo_pct:.4f}"
            lines.append(f"🐛 Evolution: {evo_str}%")
        else:
            # Multiple surfaces - list format
            lines.append("🐛 Evolution:")
            for surface_name, factor in sorted(evolution_by_surface.items()):
                evo_pct = factor * 100.0
                evo_str = f"{evo_pct:.2f}" if evo_pct >= 0.1 else f"{evo_pct:.4f}"
                lines.append(f" • {surface_name}: {evo_str}%")
    elif metrics.get("evolution_factor") is not None:
        # Fallback for old single-surface format
        evolution_pct = float(metrics["evolution_factor"]) * 100.0
        evo_str = (
            f"{evolution_pct:.2f}"
            if evolution_pct >= 0.1
            else f"{evolution_pct:.4f}"
        )
        lines.append(f"🐛 Evolution: {evo_str}%")

    return "\n".join(lines)


def format_stats_embed(
    server_label: str,
    metrics: Dict[str, Any],
) -> discord.Embed:
    """
    Format RCON server stats as Discord embed.

    Pure formatting function with no state or RCON dependencies.
    Ready for reuse in slash commands or other Discord outputs.

    Args:
        server_label: Server name/tag string (e.g., "[prod] Factorio ISR")
        metrics: Dict from RconMetricsEngine.gather_all_metrics() with keys:
                 ups, ups_sma, ups_ema, is_paused, last_known_ups,
                 player_count, players, server_time, evolution_factor,
                 evolution_by_surface

    Returns:
        Formatted discord.Embed ready for sending
    """
    from discord_interface import EmbedBuilder  # type: ignore[import]

    title = f"📊 {server_label} Status"
    embed = EmbedBuilder.create_base_embed(
        title=title,
        color=EmbedBuilder.COLOR_INFO,
    )

    # UPS or Pause status
    if metrics.get("is_paused"):
        last_ups = metrics.get("last_known_ups")
        if last_ups and last_ups > 0:
            value = f"⏸️ Paused\n(last: {last_ups:.1f} UPS)"
        else:
            value = "⏸️ Paused"
        embed.add_field(
            name="Status",
            value=value,
            inline=True,
        )
    elif metrics.get("ups") is not None:
        ups = float(metrics["ups"])
        sma = metrics.get("ups_sma")
        ema = metrics.get("ups_ema")
        ups_emoji = "✅" if ups >= 59.0 else "⚠️"

        field_lines: List[str] = [f"Raw: {ups:.1f}/60.0"]
        if sma is not None:
            field_lines.append(f"SMA: {float(sma):.1f}")
        if ema is not None:
            field_lines.append(f"EMA: {float(ema):.1f}")

        embed.add_field(
            name=f"{ups_emoji} UPS",
            value="\n".join(field_lines),
            inline=True,
        )

    embed.add_field(
        name="👥 Players Online",
        value=f"{metrics.get('player_count')}",
        inline=True,
    )

    embed.add_field(
        name="⏰ Game Time",
        value=metrics.get("server_time"),
        inline=True,
    )

    if metrics.get("players"):
        players_text = "\n".join(f"• {p}" for p in metrics["players"])
        embed.add_field(
            name="📝 Players",
            value=(
                players_text
                if len(players_text) <= 1024
                else f"{players_text[:1020]}..."
            ),
            inline=False,
        )

    # Evolution per surface
    evolution_by_surface = metrics.get("evolution_by_surface", {})
    if evolution_by_surface:
        if len(evolution_by_surface) == 1:
            # Single surface - inline field
            surface_name = next(iter(evolution_by_surface.keys()))
            evo_pct = evolution_by_surface[surface_name] * 100.0
            evo_str = f"{evo_pct:.2f}" if evo_pct >= 0.1 else f"{evo_pct:.4f}"
            embed.add_field(
                name="🐛 Evolution",
                value=f"{evo_str}%",
                inline=True,
            )
        else:
            # Multiple surfaces - full-width field with list
            evo_lines = []
            for surface_name, factor in sorted(evolution_by_surface.items()):
                evo_pct = factor * 100.0
                evo_str = (
                    f"{evo_pct:.2f}" if evo_pct >= 0.1 else f"{evo_pct:.4f}"
                )
                evo_lines.append(f"**{surface_name}**: {evo_str}%")

            embed.add_field(
                name="🐛 Evolution by Surface",
                value="\n".join(evo_lines),
                inline=False,
            )
    elif metrics.get("evolution_factor") is not None:
        # Fallback for old single-surface format
        evolution_pct = float(metrics["evolution_factor"]) * 100.0
        evo_str = (
            f"{evolution_pct:.2f}"
            if evolution_pct >= 0.1
            else f"{evolution_pct:.4f}"
        )
        embed.add_field(
            name="🐛 Evolution",
            value=f"{evo_str}%",
            inline=True,
        )

    return embed
