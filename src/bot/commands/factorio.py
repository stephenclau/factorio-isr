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
import discord
from discord import app_commands
import structlog

try:
    from ..event_parser import FactorioEvent
    from ..utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
    from ..discord_interface import EmbedBuilder
except ImportError:
    from event_parser import FactorioEvent  # type: ignore
    from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN  # type: ignore
    from discord_interface import EmbedBuilder  # type: ignore

logger = structlog.get_logger()


def register_factorio_commands(bot: Any) -> None:
    """
    Register all /factorio subcommands.

    This function creates and registers the complete /factorio command tree.
    Discord limit: 25 subcommands per group (we use 17).

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
    # /factorio servers
    # /factorio connect

    @factorio_group.command(name="servers", description="List available Factorio servers")
    async def servers_command(interaction: discord.Interaction) -> None:
        """List all configured servers with status and current context."""
        # Check if multi-server is configured
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

                # Build field value
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

    # Autocomplete function for server tags
    async def server_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """
        Autocomplete server tags with display names.

        Shows: "prod - Production (Main server)"
        Returns: "prod"
        """
        if not hasattr(interaction.client, "server_manager"):
            return []

        server_manager = interaction.client.server_manager  # type: ignore
        if not server_manager:
            return []

        current_lower = current.lower()
        choices = []
        for tag, config in server_manager.list_servers().items():
            # Match against tag, name, or description
            if (
                current_lower in tag.lower()
                or current_lower in config.name.lower()
                or (config.description and current_lower in config.description.lower())
            ):
                # Format: "tag - Name (description)"
                display = f"{tag} - {config.name}"
                if config.description:
                    display += f" ({config.description})"
                choices.append(
                    app_commands.Choice(
                        name=display[:100],  # Discord limit
                        value=tag,
                    )
                )

        return choices[:25]  # Discord limit

    @factorio_group.command(
        name="connect", description="Connect to a specific Factorio server"
    )
    @app_commands.describe(server="Server tag (use autocomplete or /factorio servers)")
    @app_commands.autocomplete(server=server_autocomplete)
    async def connect_command(interaction: discord.Interaction, server: str) -> None:
        """Switch user's context to a different server."""
        # Check if multi-server is configured
        if not bot.server_manager:
            embed = EmbedBuilder.error_embed(
                "Multi-server mode not enabled.\n\n"
                "This bot is running in single-server mode."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        try:
            # Normalize tag (case-insensitive)
            server = server.lower().strip()

            # Validate server exists
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

            # Set user context
            bot.user_context.set_user_server(interaction.user.id, server)

            # Get server info
            config = bot.server_manager.get_config(server)
            client = bot.server_manager.get_client(server)
            is_connected = client.is_connected

            # Build confirmation embed
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
    # /factorio status
    # /factorio players
    # /factorio version
    # /factorio seed
    # /factorio evolution
    # /factorio admins
    # /factorio health

    @factorio_group.command(name="status", description="Show Factorio server status")
    async def status_command(interaction: discord.Interaction) -> None:
        """Get comprehensive server status with rich embed."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Per-user server context
        server_tag = bot.user_context.get_user_server(interaction.user.id)
        server_name = bot.user_context.get_server_display_name(interaction.user.id)

        # User-specific RCON client
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n"
                "Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Bot + RCON status
            bot_online = bot._connected
            bot_status = "🟢 Online" if bot_online else "🔴 Offline"

            # Players
            players = await rcon_client.get_players()
            player_names = players  # get_players() returns list[str]
            player_count = len(player_names)

            # RCON monitor uptime for this server (from rcon_server_states)
            uptime_text = "Unknown"
            state = bot.rcon_monitor.rcon_server_states.get(server_tag)
            last_connected = state.get("last_connected") if state else None
            if last_connected is not None:
                from ..bot.helpers import format_uptime  # type: ignore
                from datetime import datetime, timezone
                uptime_delta = datetime.now(timezone.utc) - last_connected
                uptime_text = format_uptime(uptime_delta)

            # Actual in-game uptime from game.tick (best-effort)
            from ..bot.helpers import get_game_uptime  # type: ignore
            game_uptime = await get_game_uptime(rcon_client)
            if game_uptime != "Unknown":
                uptime_text = game_uptime

            # Build embed using existing style
            embed = EmbedBuilder.create_base_embed(
                title=f"🏭 {server_name} Status",
                color=(
                    EmbedBuilder.COLOR_SUCCESS
                    if rcon_client.is_connected
                    else EmbedBuilder.COLOR_WARNING
                ),
            )

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

            if player_names:
                embed.add_field(
                    name="👥 Online Players",
                    value="\n".join(f"• {name}" for name in player_names),
                    inline=False,
                )

            embed.set_footer(text="Factorio ISR")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get status: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("status_command_failed", error=str(e))

    # NOTE: Additional command implementations (players, version, seed, evolution, admins, health)
    # will be added in Phase 6 of the refactor. For now, this template demonstrates the
    # structure and pattern. Each command follows the same pattern as status_command above.

    # ========================================================================
    # PLAYER MANAGEMENT COMMANDS (7/25)
    # ========================================================================
    # /factorio kick
    # /factorio ban
    # /factorio unban
    # /factorio mute
    # /factorio unmute
    # /factorio promote
    # /factorio demote

    # NOTE: Player management commands will be added in Phase 6.

    # ========================================================================
    # SERVER MANAGEMENT COMMANDS (4/25)
    # ========================================================================
    # /factorio save
    # /factorio broadcast
    # /factorio whisper
    # /factorio whitelist

    # NOTE: Server management commands will be added in Phase 6.

    # ========================================================================
    # GAME CONTROL COMMANDS (3/25)
    # ========================================================================
    # /factorio time
    # /factorio speed
    # /factorio research

    # NOTE: Game control commands will be added in Phase 6.

    # ========================================================================
    # ADVANCED COMMANDS (2/25)
    # ========================================================================
    # /factorio rcon
    # /factorio help

    @factorio_group.command(name="help", description="Show available Factorio commands")
    async def help_command(interaction: discord.Interaction) -> None:
        """Display comprehensive help message."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Discord max subcommands for any command group is 25.
        help_text = (
            "**🏭 Factorio ISR Bot – Commands**\n\n"
            "**🌐 Multi-Server**\n"
            "`/factorio servers` – List available servers\n"
            "`/factorio connect ` – Switch to a server\n\n"
            "**📊 Server Information**\n"
            "`/factorio status` – Show server status and uptime\n"
            "`/factorio players` – List players currently online\n"
            "`/factorio version` – Show Factorio server version\n"
            "`/factorio seed` – Show map seed\n"
            "`/factorio evolution` – Show biter evolution factor\n"
            "`/factorio admins` – List server administrators\n"
            "`/factorio health` – Check bot and server health\n\n"
            "**👥 Player Management**\n"
            "`/factorio kick [reason]` – Kick a player\n"
            "`/factorio ban ` – Ban a player\n"
            "`/factorio unban ` – Unban a player\n"
            "`/factorio mute ` – Mute a player from chat\n"
            "`/factorio unmute ` – Unmute a player\n"
            "`/factorio promote ` – Promote player to admin\n"
            "`/factorio demote ` – Demote player from admin\n\n"
            "**🔧 Server Management**\n"
            "`/factorio broadcast ` – Send message to all players\n"
            "`/factorio whisper ` – Send private message to a player\n"
            "`/factorio save [name]` – Save the game\n"
            "`/factorio whitelist [player]` – Manage whitelist\n"
            " └ Actions: add, remove, list, enable, disable\n\n"
            "**🎮 Game Control**\n"
            "`/factorio time [value]` – Set/display game time\n"
            "`/factorio speed ` – Set game speed (0.1-10.0)\n"
            "`/factorio research ` – Force research tech\n\n"
            "**🖛️ Advanced**\n"
            "`/factorio rcon ` – Run raw RCON command\n"
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
        phase="6.0-multi-server",
    )
