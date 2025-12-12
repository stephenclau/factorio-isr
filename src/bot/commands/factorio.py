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
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: 17/25 (8 slots available for future expansion)
"""

from typing import Any, List, Optional
from datetime import datetime, timezone
import discord
from discord import app_commands
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
    """
    Register all /factorio subcommands.

    This function creates and registers the complete /factorio command tree.
    Discord limit: 25 subcommands per group (we use 17).

    Each command is self-contained: RCON execute → parse → format → send.

    Args:
        bot: DiscordBot instance with user_context, server_manager attributes
    """
    factorio_group = app_commands.Group(
        name="factorio",
        description="Factorio server status, players, and RCON management",
    )

    # ========================================================================
    # MULTI-SERVER COMMANDS (2/25)
    # ========================================================================

    @factorio_group.command(name="servers", description="List available Factorio servers")
    async def servers_command(interaction: discord.Interaction) -> None:
        """List all configured servers with status and current context."""
        if not bot.server_manager:
            embed = EmbedBuilder.info_embed(
                title="📱 Server Information",
                message=(
                    "Single-server mode active.\n\n"
                    "To enable multi-server support, configure a `servers.yml` file "
                    "or set the `SERVERS` environment variable."
                ),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        try:
            current_tag = bot.user_context.get_user_server(interaction.user.id)
            status_summary = bot.server_manager.get_status_summary()

            embed = discord.Embed(
                title="📱 Available Factorio Servers",
                color=EmbedBuilder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )

            if not bot.server_manager.list_tags():
                embed.description = "No servers configured."
            else:
                embed.description = f"**Your Context:** `{current_tag}`\n\n"

            for tag, config in bot.server_manager.list_servers().items():
                is_connected = status_summary.get(tag, False)
                status_icon = "🟢" if is_connected else "🔴"
                context_icon = "👉 " if tag == current_tag else " "

                field_lines = [
                    f"{status_icon} {'Online' if is_connected else 'Offline'}",
                    f"Host: `{config.rcon_host}:{config.rcon_port}`",
                ]

                if config.description:
                    field_lines.insert(0, f"*{config.description}*")

                embed.add_field(
                    name=f"{context_icon}**{config.name}** (`{tag}`)",
                    value="\n".join(field_lines),
                    inline=False,
                )

            embed.set_footer(text="Use /factorio connect to switch servers")
            await interaction.followup.send(embed=embed)
            logger.info(
                "servers_listed",
                user=interaction.user.name,
                server_count=len(bot.server_manager.list_tags()),
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to list servers: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("servers_command_failed", error=str(e))

    async def server_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete server tags with display names."""
        if not hasattr(interaction.client, "server_manager"):
            return []

        server_manager = interaction.client.server_manager  # type: ignore
        if not server_manager:
            return []

        current_lower = current.lower()
        choices = []
        for tag, config in server_manager.list_servers().items():
            if (
                current_lower in tag.lower()
                or current_lower in config.name.lower()
                or (config.description and current_lower in config.description.lower())
            ):
                display = f"{tag} - {config.name}"
                if config.description:
                    display += f" ({config.description})"
                choices.append(
                    app_commands.Choice(
                        name=display[:100],
                        value=tag,
                    )
                )

        return choices[:25]

    @factorio_group.command(
        name="connect", description="Connect to a specific Factorio server"
    )
    @app_commands.describe(server="Server tag (use autocomplete or /factorio servers)")
    @app_commands.autocomplete(server=server_autocomplete)
    async def connect_command(interaction: discord.Interaction, server: str) -> None:
        """Switch user's context to a different server."""
        if not bot.server_manager:
            embed = EmbedBuilder.error_embed(
                "Multi-server mode not enabled.\n\n"
                "This bot is running in single-server mode."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        try:
            server = server.lower().strip()

            if server not in bot.server_manager.clients:
                available_list = []
                for tag, config in bot.server_manager.list_servers().items():
                    available_list.append(f"`{tag}` ({config.name})")
                available = ", ".join(available_list) if available_list else "none"
                embed = EmbedBuilder.error_embed(
                    f"❌ Server `{server}` not found.\n\n"
                    f"**Available servers:** {available}\n\n"
                    f"Use `/factorio servers` to see all servers."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            bot.user_context.set_user_server(interaction.user.id, server)

            config = bot.server_manager.get_config(server)
            client = bot.server_manager.get_client(server)
            is_connected = client.is_connected

            embed = discord.Embed(
                title=f"✅ Connected to {config.name}",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )

            status_icon = "🟢" if is_connected else "🟡"
            status_text = "Connected" if is_connected else "Connecting..."

            embed.add_field(name="Tag", value=f"`{server}`", inline=True)
            embed.add_field(name="Status", value=f"{status_icon} {status_text}", inline=True)
            embed.add_field(
                name="Host",
                value=f"`{config.rcon_host}:{config.rcon_port}`",
                inline=True,
            )

            if config.description:
                embed.add_field(
                    name="Description",
                    value=config.description,
                    inline=False,
                )

            embed.description = "All commands will now target this server."
            embed.set_footer(text="Use /factorio servers to see all servers")

            await interaction.followup.send(embed=embed)
            logger.info(
                "user_connected_to_server",
                user=interaction.user.name,
                user_id=interaction.user.id,
                server_tag=server,
                server_name=config.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to connect: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("connect_command_failed", error=str(e), exc_info=True)

    # ========================================================================
    # SERVER INFORMATION COMMANDS (7/25)
    # ========================================================================

    @factorio_group.command(name="status", description="Show Factorio server status")
    async def status_command(interaction: discord.Interaction) -> None:
        """Get comprehensive server status with rich embed."""
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
            # Get players
            players_response = await rcon_client.execute("/players")
            players = []
            if players_response:
                for line in players_response.split("\n"):
                    line = line.strip()
                    if "(online)" in line.lower():
                        player_name = line.split("(online)")[0].strip()
                        player_name = player_name.lstrip("-").strip()
                        if player_name and not player_name.startswith("Player"):
                            players.append(player_name)
            player_count = len(players)

            # Get uptime
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

            # Build embed
            embed = EmbedBuilder.create_base_embed(
                title=f"🏭 {server_name} Status",
                color=(
                    EmbedBuilder.COLOR_SUCCESS
                    if rcon_client.is_connected
                    else EmbedBuilder.COLOR_WARNING
                ),
            )

            bot_online = bot._connected
            bot_status = "🟢 Online" if bot_online else "🔴 Offline"
            embed.add_field(name="🤖 Bot Status", value=bot_status, inline=True)
            embed.add_field(
                name="🔧 RCON",
                value="🟢 Connected" if rcon_client.is_connected else "🔴 Disconnected",
                inline=True,
            )
            embed.add_field(
                name="👥 Players Online",
                value=str(player_count),
                inline=True,
            )
            embed.add_field(
                name="⏱️ Uptime",
                value=uptime_text,
                inline=True,
            )

            if players:
                player_list = "\n".join(f"• {name}" for name in players[:10])
                if len(players) > 10:
                    player_list += f"\n... and {len(players) - 10} more"
                embed.add_field(
                    name="👥 Online Players",
                    value=player_list,
                    inline=False,
                )

            embed.set_footer(text="Factorio ISR")
            await interaction.followup.send(embed=embed)
            logger.info("status_command_executed", user=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get status: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("status_command_failed", error=str(e))

    @factorio_group.command(name="players", description="List players currently online")
    async def players_command(interaction: discord.Interaction) -> None:
        """List online players with detailed information."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Execute RCON command
            response = await rcon_client.execute("/players")
            
            # Parse response
            players = []
            if response:
                for line in response.split("\n"):
                    line = line.strip()
                    if "(online)" in line.lower():
                        player_name = line.split("(online)")[0].strip()
                        player_name = player_name.lstrip("-").strip()
                        if player_name and not player_name.startswith("Player"):
                            players.append(player_name)
            
            # Format embed
            embed = discord.Embed(
                title=f"👥 Players on {server_name}",
                color=EmbedBuilder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )

            if not players:
                embed.description = "No players currently online."
            else:
                player_list = "\n".join(f"• {name}" for name in sorted(players))
                embed.add_field(
                    name=f"Online Players ({len(players)})",
                    value=player_list,
                    inline=False,
                )

            embed.set_footer(text="Factorio ISR")
            await interaction.followup.send(embed=embed)
            logger.info("players_command_executed", player_count=len(players))
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get players: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("players_command_failed", error=str(e))

    @factorio_group.command(name="version", description="Show Factorio server version")
    async def version_command(interaction: discord.Interaction) -> None:
        """Get Factorio server version."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Execute RCON command
            response = await rcon_client.execute("/version")
            
            # Parse response
            version = response.strip() if response else "Unknown"
            
            # Format embed
            embed = discord.Embed(
                title=f"📦 {server_name} Version",
                description=f"`{version}`",
                color=EmbedBuilder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Factorio ISR")
            await interaction.followup.send(embed=embed)
            logger.info("version_command_executed", version=version)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get version: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("version_command_failed", error=str(e))

    @factorio_group.command(name="seed", description="Show map seed")
    async def seed_command(interaction: discord.Interaction) -> None:
        """Get map seed."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Execute RCON command
            response = await rcon_client.execute(
                '/sc rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)'
            )
            
            # Parse and validate response
            seed = "Unknown"
            if response and response.strip():
                try:
                    int(response.strip())  # Validate it's numeric
                    seed = response.strip()
                except ValueError:
                    logger.warning("seed_parse_failed", response=response)
            
            # Format embed
            embed = discord.Embed(
                title=f"🌍 {server_name} Map Seed",
                description=f"```\n{seed}\n```",
                color=EmbedBuilder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Use this seed to generate the same map")
            await interaction.followup.send(embed=embed)
            logger.info("seed_command_executed")
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get seed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("seed_command_failed", error=str(e))

    @factorio_group.command(name="evolution", description="Show biter evolution factor")
    async def evolution_command(interaction: discord.Interaction) -> None:
        """Get enemy evolution factor."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Execute RCON command
            response = await rcon_client.execute(
                '/sc rcon.print(game.forces["enemy"].evolution_factor)'
            )
            
            # Parse response
            evolution = 0.0
            if response and response.strip():
                try:
                    evolution = float(response.strip())
                except ValueError:
                    logger.warning("evolution_parse_failed", response=response)
            
            percentage = min(100.0, evolution * 100)
            bar_filled = int(percentage / 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)

            # Format embed
            embed = discord.Embed(
                title=f"👾 {server_name} Enemy Evolution",
                color=EmbedBuilder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="Evolution Factor",
                value=f"{percentage:.1f}%",
                inline=True,
            )
            embed.add_field(
                name="Progress",
                value=f"`{bar}`",
                inline=False,
            )
            embed.set_footer(text="Higher evolution = stronger biters")
            await interaction.followup.send(embed=embed)
            logger.info("evolution_command_executed", evolution=evolution)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get evolution: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("evolution_command_failed", error=str(e))

    @factorio_group.command(name="admins", description="List server administrators")
    async def admins_command(interaction: discord.Interaction) -> None:
        """Get list of admins."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Execute RCON command
            response = await rcon_client.execute("/admins")
            
            # Parse response
            admins = []
            if response:
                for line in response.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("There are") and not line.startswith("Admins"):
                        admin_name = line.lstrip("- ").strip()
                        if admin_name:
                            admins.append(admin_name)
            
            # Format embed
            embed = discord.Embed(
                title=f"👑 {server_name} Administrators",
                color=EmbedBuilder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )

            if not admins:
                embed.description = "No administrators configured."
            else:
                admin_list = "\n".join(f"• {name}" for name in sorted(admins))
                embed.add_field(
                    name=f"Admins ({len(admins)})",
                    value=admin_list,
                    inline=False,
                )

            embed.set_footer(text="Factorio ISR")
            await interaction.followup.send(embed=embed)
            logger.info("admins_command_executed", admin_count=len(admins), moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get admins: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("admins_command_failed", error=str(e))

    @factorio_group.command(name="health", description="Check bot and server health")
    async def health_command(interaction: discord.Interaction) -> None:
        """Check overall health status."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)

        embed = discord.Embed(
            title=f"💚 {server_name} Health Check",
            color=EmbedBuilder.COLOR_SUCCESS,
            timestamp=discord.utils.utcnow(),
        )

        try:
            # Bot status
            bot_status = "🟢 Healthy" if bot._connected else "🔴 Disconnected"
            embed.add_field(name="Bot Status", value=bot_status, inline=True)

            # RCON status
            rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)
            rcon_status = (
                "🟢 Connected" if rcon_client and rcon_client.is_connected
                else "🔴 Disconnected"
            )
            embed.add_field(name="RCON Status", value=rcon_status, inline=True)

            # Monitor status
            monitor_status = "🟢 Running" if bot.rcon_monitor else "🔴 Not available"
            embed.add_field(name="Monitor Status", value=monitor_status, inline=True)

            # Uptime
            if bot.rcon_monitor and bot.rcon_monitor.rcon_server_states:
                state = bot.rcon_monitor.rcon_server_states.get(
                    bot.user_context.get_user_server(interaction.user.id)
                )
                if state and state.get("last_connected"):
                    uptime_delta = datetime.now(timezone.utc) - state["last_connected"]
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
                    uptime = " ".join(parts) if parts else "< 1m"
                    embed.add_field(name="Uptime", value=uptime, inline=True)

            embed.set_footer(text="Factorio ISR Health Check")
            await interaction.followup.send(embed=embed)
            logger.info("health_command_executed")
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Health check failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("health_command_failed", error=str(e))

    # ========================================================================
    # PLAYER MANAGEMENT COMMANDS (7/25)
    # ========================================================================

    @factorio_group.command(name="kick", description="Kick a player from the server")
    @app_commands.describe(player="Player name", reason="Reason for kick (optional)")
    async def kick_command(
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        """Kick a player."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            message = reason if reason else "Kicked by moderator"
            await rcon_client.execute(f'/kick {player} {message}')

            embed = discord.Embed(
                title="⚠️ Player Kicked",
                color=EmbedBuilder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Reason", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "player_kicked",
                player=player,
                reason=message,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to kick player: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("kick_command_failed", error=str(e))

    @factorio_group.command(name="ban", description="Ban a player from the server")
    @app_commands.describe(player="Player name", reason="Reason for ban (optional)")
    async def ban_command(
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        """Ban a player."""
        is_limited, retry = DANGER_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            message = reason if reason else "Banned by moderator"
            await rcon_client.execute(f'/ban {player} {message}')

            embed = discord.Embed(
                title="🚫 Player Banned",
                color=EmbedBuilder.COLOR_ADMIN,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Reason", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "player_banned",
                player=player,
                reason=message,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to ban player: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("ban_command_failed", error=str(e))

    @factorio_group.command(name="unban", description="Unban a player")
    @app_commands.describe(player="Player name")
    async def unban_command(
        interaction: discord.Interaction,
        player: str,
    ) -> None:
        """Unban a player."""
        is_limited, retry = DANGER_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/unban {player}')

            embed = discord.Embed(
                title="✅ Player Unbanned",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "player_unbanned",
                player=player,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to unban player: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("unban_command_failed", error=str(e))

    @factorio_group.command(name="mute", description="Mute a player")
    @app_commands.describe(player="Player name")
    async def mute_command(interaction: discord.Interaction, player: str) -> None:
        """Mute a player from chat."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/mute {player}')

            embed = discord.Embed(
                title="🔇 Player Muted",
                color=EmbedBuilder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "player_muted",
                player=player,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to mute player: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("mute_command_failed", error=str(e))

    @factorio_group.command(name="unmute", description="Unmute a player")
    @app_commands.describe(player="Player name")
    async def unmute_command(interaction: discord.Interaction, player: str) -> None:
        """Unmute a player."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/unmute {player}')

            embed = discord.Embed(
                title="🔊 Player Unmuted",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "player_unmuted",
                player=player,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to unmute player: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("unmute_command_failed", error=str(e))

    @factorio_group.command(name="promote", description="Promote player to admin")
    @app_commands.describe(player="Player name")
    async def promote_command(interaction: discord.Interaction, player: str) -> None:
        """Promote a player to admin."""
        is_limited, retry = DANGER_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/promote {player}')

            embed = discord.Embed(
                title="👑 Player Promoted",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Role", value="Administrator", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "player_promoted",
                player=player,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to promote player: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("promote_command_failed", error=str(e))

    @factorio_group.command(name="demote", description="Demote player from admin")
    @app_commands.describe(player="Player name")
    async def demote_command(interaction: discord.Interaction, player: str) -> None:
        """Demote a player from admin."""
        is_limited, retry = DANGER_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/demote {player}')

            embed = discord.Embed(
                title="📉 Player Demoted",
                color=EmbedBuilder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Role", value="Player", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "player_demoted",
                player=player,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to demote player: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("demote_command_failed", error=str(e))

    # ========================================================================
    # SERVER MANAGEMENT COMMANDS (4/25)
    # ========================================================================

    @factorio_group.command(name="save", description="Save the game")
    @app_commands.describe(name="Save name (optional, defaults to auto-save)")
    async def save_command(interaction: discord.Interaction, name: Optional[str] = None) -> None:
        """Save the game."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            save_name = name if name else "auto-save"
            await rcon_client.execute(f'/save {save_name}')

            embed = discord.Embed(
                title="💾 Game Saved",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Save Name", value=save_name, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "game_saved",
                save_name=save_name,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to save game: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("save_command_failed", error=str(e))

    @factorio_group.command(name="broadcast", description="Send message to all players")
    @app_commands.describe(message="Message to broadcast")
    async def broadcast_command(interaction: discord.Interaction, message: str) -> None:
        """Broadcast a message to all players."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/say {message}')

            embed = discord.Embed(
                title="📢 Broadcast Sent",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Message", value=message, inline=False)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "broadcast_sent",
                message=message[:50],
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to send broadcast: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("broadcast_command_failed", error=str(e))

    @factorio_group.command(name="whisper", description="Send private message to a player")
    @app_commands.describe(player="Player name", message="Message to send")
    async def whisper_command(
        interaction: discord.Interaction,
        player: str,
        message: str,
    ) -> None:
        """Send a private message to a player."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/whisper {player} {message}')

            embed = discord.Embed(
                title="💬 Private Message Sent",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Message", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "whisper_sent",
                player=player,
                message=message[:50],
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to send message: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("whisper_command_failed", error=str(e))

    @factorio_group.command(name="whitelist", description="Manage server whitelist")
    @app_commands.describe(
        action="Action: add, remove, list, enable, disable",
        player="Player name (required for add/remove)",
    )
    async def whitelist_command(
        interaction: discord.Interaction,
        action: str,
        player: Optional[str] = None,
    ) -> None:
        """Manage the server whitelist."""
        is_limited, retry = DANGER_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            action_lower = action.lower().strip()
            embed = None

            if action_lower == "add" and player:
                await rcon_client.execute(f'/whitelist add {player}')
                embed = discord.Embed(
                    title="✅ Player Added to Whitelist",
                    color=EmbedBuilder.COLOR_SUCCESS,
                )
                embed.add_field(name="Player", value=player, inline=True)
                embed.add_field(name="Server", value=server_name, inline=True)
            elif action_lower == "remove" and player:
                await rcon_client.execute(f'/whitelist remove {player}')
                embed = discord.Embed(
                    title="❌ Player Removed from Whitelist",
                    color=EmbedBuilder.COLOR_WARNING,
                )
                embed.add_field(name="Player", value=player, inline=True)
                embed.add_field(name="Server", value=server_name, inline=True)
            elif action_lower == "list":
                response = await rcon_client.execute('/whitelist list')
                embed = discord.Embed(
                    title="📋 Server Whitelist",
                    color=EmbedBuilder.COLOR_INFO,
                )
                if response and response.strip():
                    wl_text = response.strip()
                    if len(wl_text) > 1024:
                        wl_text = wl_text[:1021] + "..."
                    embed.add_field(
                        name="Whitelisted Players",
                        value=wl_text,
                        inline=False,
                    )
                else:
                    embed.description = "Whitelist is empty."
            elif action_lower == "enable":
                await rcon_client.execute('/whitelist enable')
                embed = discord.Embed(
                    title="🟢 Whitelist Enabled",
                    color=EmbedBuilder.COLOR_SUCCESS,
                )
                embed.add_field(name="Server", value=server_name, inline=True)
            elif action_lower == "disable":
                await rcon_client.execute('/whitelist disable')
                embed = discord.Embed(
                    title="🔴 Whitelist Disabled",
                    color=EmbedBuilder.COLOR_WARNING,
                )
                embed.add_field(name="Server", value=server_name, inline=True)
            else:
                embed = EmbedBuilder.error_embed(
                    "Invalid action. Valid actions: add, remove, list, enable, disable"
                )

            if embed:
                embed.set_footer(text="Action performed via Discord")
                await interaction.followup.send(embed=embed)

            logger.info(
                "whitelist_command_executed",
                action=action_lower,
                player=player,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Whitelist command failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("whitelist_command_failed", error=str(e))

    # ========================================================================
    # GAME CONTROL COMMANDS (3/25)
    # ========================================================================

    @factorio_group.command(name="time", description="Show or set game time")
    @app_commands.describe(value="Game time value (optional, format: tick number)")
    async def time_command(interaction: discord.Interaction, value: Optional[int] = None) -> None:
        """Get or set game time."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            if value is not None:
                await rcon_client.execute(f'/sc game.tick = {value}')
                embed = discord.Embed(
                    title="⏱️ Game Time Set",
                    color=EmbedBuilder.COLOR_SUCCESS,
                )
                embed.add_field(name="New Time", value=f"{value} ticks", inline=True)
            else:
                response = await rcon_client.execute('/sc rcon.print(game.tick)')
                current_time = 0
                if response and response.strip():
                    try:
                        current_time = int(response.strip())
                    except ValueError:
                        logger.warning("time_parse_failed", response=response)
                
                minutes = current_time / 60
                hours = minutes / 60
                embed = discord.Embed(
                    title="⏱️ Current Game Time",
                    color=EmbedBuilder.COLOR_INFO,
                )
                embed.add_field(name="Ticks", value=str(current_time), inline=True)
                embed.add_field(name="Minutes", value=f"{minutes:.1f}", inline=True)
                embed.add_field(name="Hours", value=f"{hours:.1f}", inline=True)

            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="1 tick = 1/60 second")
            await interaction.followup.send(embed=embed)

            logger.info(
                "time_command_executed",
                action="set" if value else "get",
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get/set time: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("time_command_failed", error=str(e))

    @factorio_group.command(name="speed", description="Set game speed")
    @app_commands.describe(value="Game speed (0.1-10.0, 1.0 = normal)")
    async def speed_command(interaction: discord.Interaction, value: float) -> None:
        """Set game speed."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not 0.1 <= value <= 10.0:
            embed = EmbedBuilder.error_embed("Speed must be between 0.1 and 10.0")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/sc game.speed = {value}')

            embed = discord.Embed(
                title="⚡ Game Speed Set",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="New Speed", value=f"{value}x", inline=True)
            if value < 1.0:
                embed.add_field(name="Effect", value="⬇️ Slower", inline=True)
            elif value > 1.0:
                embed.add_field(name="Effect", value="⬆️ Faster", inline=True)
            else:
                embed.add_field(name="Effect", value="➡️ Normal", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "game_speed_set",
                speed=value,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to set speed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("speed_command_failed", error=str(e))

    @factorio_group.command(name="research", description="Force research a technology")
    @app_commands.describe(technology="Technology name")
    async def research_command(
        interaction: discord.Interaction,
        technology: str,
    ) -> None:
        """Force research a technology."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            await rcon_client.execute(f'/research {technology}')

            embed = discord.Embed(
                title="🔬 Technology Researched",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Technology", value=technology, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")
            await interaction.followup.send(embed=embed)

            logger.info(
                "technology_researched",
                technology=technology,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to research technology: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("research_command_failed", error=str(e))

    # ========================================================================
    # ADVANCED COMMANDS (2/25)
    # ========================================================================

    @factorio_group.command(name="rcon", description="Run raw RCON command")
    @app_commands.describe(command="RCON command to execute")
    async def rcon_command(interaction: discord.Interaction, command: str) -> None:
        """Execute a raw RCON command."""
        is_limited, retry = DANGER_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            result = await rcon_client.execute(command)

            embed = discord.Embed(
                title="⌨️ RCON Command Executed",
                color=EmbedBuilder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Command", value=f"```\n{command}\n```", inline=False)
            if result:
                result_text = result if len(result) < 1024 else result[:1021] + "..."
                embed.add_field(name="Response", value=f"```\n{result_text}\n```", inline=False)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Dangerous operation - use with caution")
            await interaction.followup.send(embed=embed)

            logger.warning(
                "raw_rcon_executed",
                command=command[:50],
                user=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"RCON command failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("rcon_command_failed", error=str(e))

    @factorio_group.command(name="help", description="Show available Factorio commands")
    async def help_command(interaction: discord.Interaction) -> None:
        """Display comprehensive help message."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        help_text = (
            "**🏭 Factorio ISR Bot – Commands**\n\n"
            "**🌐 Multi-Server**\n"
            "`/factorio servers` – List available servers\n"
            "`/factorio connect <server>` – Switch to a server\n\n"
            "**📊 Server Information**\n"
            "`/factorio status` – Show server status and uptime\n"
            "`/factorio players` – List players currently online\n"
            "`/factorio version` – Show Factorio server version\n"
            "`/factorio seed` – Show map seed\n"
            "`/factorio evolution` – Show biter evolution factor\n"
            "`/factorio admins` – List server administrators\n"
            "`/factorio health` – Check bot and server health\n\n"
            "**👥 Player Management**\n"
            "`/factorio kick <player> [reason]` – Kick a player\n"
            "`/factorio ban <player> [reason]` – Ban a player\n"
            "`/factorio unban <player>` – Unban a player\n"
            "`/factorio mute <player>` – Mute a player from chat\n"
            "`/factorio unmute <player>` – Unmute a player\n"
            "`/factorio promote <player>` – Promote player to admin\n"
            "`/factorio demote <player>` – Demote player from admin\n\n"
            "**🔧 Server Management**\n"
            "`/factorio broadcast <message>` – Send message to all players\n"
            "`/factorio whisper <player> <message>` – Send private message\n"
            "`/factorio save [name]` – Save the game\n"
            "`/factorio whitelist <action> [player]` – Manage whitelist\n"
            "  └ Actions: add, remove, list, enable, disable\n\n"
            "**🎮 Game Control**\n"
            "`/factorio time [value]` – Show/set game time\n"
            "`/factorio speed <value>` – Set game speed (0.1-10.0)\n"
            "`/factorio research <technology>` – Force research tech\n\n"
            "**🖛️ Advanced**\n"
            "`/factorio rcon <command>` – Run raw RCON command\n"
            "`/factorio help` – Show this help message\n\n"
            "_Most commands require RCON to be enabled._"
        )

        await interaction.response.send_message(help_text)

    # ========================================================================
    # Register the command group
    # ========================================================================

    bot.tree.add_command(factorio_group)
    logger.info(
        "factorio_commands_registered",
        root=factorio_group.name,
        command_count=len(factorio_group.commands),
        phase="7.0-discrete-enclosures",
    )
