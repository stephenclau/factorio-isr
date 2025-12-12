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

"""Factorio slash command group registration.

All /factorio subcommands are defined in this single file to respect Discord's
25 subcommand-per-group limit. Currently using 17/25 slots.

Each command is a self-contained closure that:
1. Validates rate limits and RCON connectivity
2. Executes RCON command(s)
3. Parses response inline
4. Formats Discord embed
5. Sends to user

Command Breakdown:
- Multi-Server Commands: 2/25 (servers, connect)
- Server Information: 7/25 (status, players, version, seed, evolution, admins, health)
- Player Management: 7/25 (kick, ban, unban, mute, unmute, promote, demote)
- Server Management: 4/25 (save, broadcast, whisper, whitelist)
- Game Control: 3/25 (time, speed, research)
- Advanced: 2/25 (rcon, help)
"""

from typing import Any, List, Optional
from datetime import datetime, timezone
import discord
from discord import app_commands
import re
import structlog

try:
    # Try flat layout first (when run from src/ directory)
    from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
    from discord_interface import EmbedBuilder
except ImportError:
    try:
        # Fallback to package style (when installed as package)
        from src.utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN  # type: ignore
        from src.discord_interface import EmbedBuilder  # type: ignore
    except ImportError:
        # Last resort: use relative imports from parent
        try:
            from ..utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN  # type: ignore
            from ..discord_interface import EmbedBuilder  # type: ignore
        except ImportError:
            raise ImportError(
                "Could not import rate_limiting or discord_interface from any path"
            )

logger = structlog.get_logger()


def register_factorio_commands(bot: Any) -> None:
    """Register all /factorio subcommands."""
    factorio_group = app_commands.Group(
        name="factorio",
        description="Factorio server status, players, and RCON management",
    )

    @factorio_group.command(name="status", description="Show Factorio server status")
    async def status_command(interaction: discord.Interaction) -> None:
        """Get comprehensive server status with rich embed including metrics."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        server_tag = bot.user_context.get_user_server(interaction.user.id)
        server_name = bot.user_context.get_server_display_name(interaction.user.id)

        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n"
                "Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Get shared metrics engine and gather comprehensive metrics
            metrics_engine = bot.server_manager.get_metrics_engine(server_tag)
            if metrics_engine is None:
                raise RuntimeError(f"Metrics engine not available for {server_tag}")
            
            metrics = await metrics_engine.gather_all_metrics()

            # Get uptime (existing logic)
            uptime_text = "Unknown"
            state = bot.rcon_monitor.rcon_server_states.get(server_tag)
            last_connected = state.get("last_connected") if state else None
            if last_connected is not None:
                uptime_delta = datetime.now(timezone.utc) - last_connected
                days = int(uptime_delta.total_seconds()) // 86400
                hours = (int(uptime_delta.total_seconds()) % 86400) // 3600
                minutes = (int(uptime_delta.total_seconds()) % 3600) // 60
                parts = []
                if days > 0:
                    parts.append(f"{days}d")
                if hours > 0:
                    parts.append(f"{hours}h")
                if minutes > 0 or (days == 0 and hours == 0):
                    parts.append(f"{minutes}m")
                uptime_text = " ".join(parts) if parts else "< 1m"

            # Build rich embed with comprehensive metrics
            embed = EmbedBuilder.create_base_embed(
                title=f"🏭 {server_name} Status",
                color=(
                    EmbedBuilder.COLOR_SUCCESS
                    if rcon_client.is_connected
                    else EmbedBuilder.COLOR_WARNING
                ),
            )

            # Bot and RCON status
            bot_online = bot._connected
            bot_status = "🟢 Online" if bot_online else "🔴 Offline"
            embed.add_field(name="🤖 Bot Status", value=bot_status, inline=True)
            embed.add_field(
                name="🔧 RCON",
                value="🟢 Connected" if rcon_client.is_connected else "🔴 Disconnected",
                inline=True,
            )
            embed.add_field(
                name="⏱️ Monitoring Uptime",
                value=uptime_text,
                inline=True,
            )

            # Performance Metrics (from metrics engine)
            is_paused = metrics.get("is_paused", False)
            ups_value = metrics.get("ups")
            
            if is_paused:
                embed.add_field(
                    name="🖥️ Server State",
                    value="⏸️ Paused",
                    inline=True,
                )
            elif ups_value is not None:
                ups_str = f"{ups_value:.1f}"
                embed.add_field(
                    name="🖥️ Server State",
                    value=f"▶️ Running @ {ups_str}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="🖥️ Server State",
                    value="🔄 Fetching...",
                    inline=True,
                )
            
            if metrics.get("ups_sma") is not None:
                embed.add_field(
                    name="📊 UPS (SMA)",
                    value=f"{metrics['ups_sma']:.1f}",
                    inline=True,
                )
            
            if metrics.get("ups_ema") is not None:
                embed.add_field(
                    name="📈 UPS (EMA)",
                    value=f"{metrics['ups_ema']:.1f}",
                    inline=True,
                )

            # Evolution Factor - Display nauvis and gleba separately if available
            evolution_by_surface = metrics.get("evolution_by_surface", {})
            
            # Display nauvis evolution if available
            if "nauvis" in evolution_by_surface:
                nauvis_evo = evolution_by_surface["nauvis"]
                nauvis_pct = nauvis_evo * 100
                embed.add_field(
                    name="🐛 Nauvis Evolution",
                    value=f"{nauvis_evo:.2f} ({nauvis_pct:.1f}%)",
                    inline=True,
                )
            
            # Display gleba evolution if available
            if "gleba" in evolution_by_surface:
                gleba_evo = evolution_by_surface["gleba"]
                gleba_pct = gleba_evo * 100
                embed.add_field(
                    name="🐛 Gleba Evolution",
                    value=f"{gleba_evo:.2f} ({gleba_pct:.1f}%)",
                    inline=True,
                )
            
            # Fallback to single evolution_factor if multi-surface data unavailable
            if not evolution_by_surface and metrics.get("evolution_factor") is not None:
                evo_pct = metrics["evolution_factor"] * 100
                embed.add_field(
                    name="🐛 Enemy Evolution",
                    value=f"{evo_pct:.1f}%",
                    inline=True,
                )

            # Players (from metrics engine)
            player_count = metrics.get("player_count", 0)
            embed.add_field(
                name="👥 Players Online",
                value=str(player_count),
                inline=True,
            )

            # Online players list (if any)
            players = metrics.get("players", [])
            if players:
                player_list = "\n".join(f"• {name}" for name in players[:10])
                if len(players) > 10:
                    player_list += f"\n... and {len(players) - 10} more"
                embed.add_field(
                    name="👥 Online Players",
                    value=player_list,
                    inline=False,
                )

            embed.set_footer(text="Factorio ISR | Metrics via RconMetricsEngine")
            await interaction.followup.send(embed=embed)
            logger.info(
                "status_command_executed",
                user=interaction.user.name,
                server_tag=server_tag,
                has_metrics=True,
                ups=metrics.get("ups"),
                evolution=metrics.get("evolution_factor"),
                evolution_surfaces=list(metrics.get("evolution_by_surface", {}).keys()),
                is_paused=metrics.get("is_paused"),
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get status: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("status_command_failed", error=str(e), exc_info=True)

    bot.tree.add_command(factorio_group)
    logger.info(
            "slash_commands_registered",
            root=factorio_group.name,
        )
