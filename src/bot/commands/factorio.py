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
25 subcommand-per-group limit. Currently using 25/25 slots.

Command Breakdown:
- Multi-Server Commands: 2/25 (servers, connect)
- Server Information: 8/25 (status, players, version, seed, evolution, admins, health, help)
- Player Management: 7/25 (kick, ban, unban, mute, unmute, promote, demote)
- Server Management: 4/25 (save, broadcast, whisper, whitelist)
- Game Control: 3/25 (time, speed, research)
- Advanced: 1/25 (rcon)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: 25/25 (no slots available)
"""

from typing import Any, List, Optional
from datetime import datetime, timezone
import discord
from discord import app_commands
import structlog

try:
    # Try package-style imports first
    from event_parser import FactorioEvent
    from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
    from discord_interface import EmbedBuilder
except ImportError:
    try:
        # Fallback to src. prefix
        from src.event_parser import FactorioEvent  # type: ignore
        from src.utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN  # type: ignore
        from src.discord_interface import EmbedBuilder  # type: ignore
    except ImportError:
        raise ImportError("Could not import event_parser, rate_limiting, or discord_interface")

logger = structlog.get_logger()


def register_factorio_commands(bot: Any) -> None:
    """
    Register all /factorio subcommands.

    This function creates and registers the complete /factorio command tree.
    Discord limit: 25 subcommands per group (we use all 25).

    Args:
        bot: DiscordBot instance with user_context, server_manager attributes
    """
    factorio_group = app_commands.Group(
        name="factorio",
        description="Factorio server status, players, and RCON management",
    )

        # ====================================================================
        # PHASE 6: Multi-Server Commands
        # ====================================================================

    @factorio_group.command(name="servers", description="List available Factorio servers")
    async def servers_command(interaction: discord.Interaction) -> None:
        """List all configured servers with status and current context."""
        # Check if multi-server is configured
        if not bot.server_manager:
            embed = EmbedBuilder.info_embed(
                title="📡 Server Information",
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
            current_tag = bot.get_user_server(interaction.user.id)
            status_summary = bot.server_manager.get_status_summary()

            embed = discord.Embed(
                title="📡 Available Factorio Servers",
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

    @factorio_group.command(name="connect", description="Connect to a specific Factorio server")
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
            bot.set_user_server(interaction.user.id, server)

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

    # ====================================================================
    # Server Information Commands
    # ====================================================================

    @factorio_group.command(name="status", description="Show Factorio server status")
    async def status_command(interaction: discord.Interaction) -> None:
        """Get comprehensive server status with rich embed."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        logger.debug("status_deferring")  # ADD THIS
        await interaction.response.defer()

        # Per-user server context
        server_tag = bot.get_user_server(interaction.user.id)
        server_name = bot.get_server_display_name(interaction.user.id)
        logger.debug("status_server_context", server_tag=server_tag, server_name=server_name) 
        
        # User-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        logger.debug("status_rcon_client", has_client=rcon_client is not None)
        
        if rcon_client is None or not rcon_client.is_connected:
            logger.warning("status_rcon_unavailable")
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n"
                "Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            logger.debug("status_fetching_data")
            # Bot + RCON status
            bot_online = bot._connected
            bot_status = "🟢 Online" if bot_online else "🔴 Offline"

            # Players
            players = await rcon_client.get_players()
            player_names = players  # get_players() returns list[str]
            player_count = len(player_names)

            # RCON monitor uptime for this server (from rcon_server_states)
            uptime_text = "Unknown"
            state = bot.rcon_server_states.get(server_tag)
            last_connected = state.get("last_connected") if state else None
            if isinstance(last_connected, datetime):
                uptime_delta = datetime.now(timezone.utc) - last_connected
                uptime_text = bot._format_uptime(uptime_delta)

            # Actual in-game uptime from game.tick (best-effort)
            game_uptime = await bot._get_game_uptime(rcon_client)
            if game_uptime != "Unknown":
                uptime_text = game_uptime

            # Build embed using existing style
            embed = EmbedBuilder.create_base_embed(
                title=f"🏭 {server_name} Status",
                color=EmbedBuilder.COLOR_SUCCESS if rcon_client.is_connected else EmbedBuilder.COLOR_WARNING,
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

    @factorio_group.command(name="players", description="List players currently online")
    async def players_command(interaction: discord.Interaction) -> None:
        """List online players with rich embed."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            players = await rcon_client.get_players()
            embed = EmbedBuilder.players_list_embed(players)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get players: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("players_command_failed", error=str(e))

    @factorio_group.command(name="version", description="Show Factorio server version")
    async def version_command(interaction: discord.Interaction) -> None:
        """Display the Factorio server version."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute("/version")
            embed = EmbedBuilder.info_embed(
                title="🎮 Factorio Version",
                message=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("version_requested", moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get version: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("version_command_failed", error=str(e))

    @factorio_group.command(name="seed", description="Show the map seed")
    async def seed_command(interaction: discord.Interaction) -> None:
        """Display the current map seed."""
        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute('/sc rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)')
            embed = EmbedBuilder.info_embed(
                title="🌱 Map Seed",
                message=f"Seed: `{resp.strip()}`\n\nUse this seed to generate an identical map.",
            )
            await interaction.followup.send(embed=embed)
            logger.info("seed_requested", moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get map seed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("seed_command_failed", error=str(e))

    @factorio_group.command(
        name="evolution",
        description="Show evolution for a surface or all non-platform surfaces",
    )
    @app_commands.describe(
        target='Surface/planet name (e.g. "nauvis") or the keyword "all"',
    )
    async def evolution_command(
        interaction: discord.Interaction,
        target: str,
    ) -> None:
        """
        /factorio evolution all -> aggregate evolution across all non-platform surfaces
        /factorio evolution nauvis -> evolution for surface 'nauvis' only
        """
        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                "Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        raw = target.strip()
        lower = raw.lower()

        try:
            if lower == "all":
                # Aggregate + detailed per-surface evolution, skipping platform surfaces
                lua = (
                    "/c "
                    "local f = game.forces['enemy']; "
                    "local total = 0; local count = 0; "
                    "local lines = {}; "
                    "for _, s in pairs(game.surfaces) do "
                    " if not string.find(string.lower(s.name), 'platform') then "
                    " local evo = f.get_evolution_factor(s); "
                    " total = total + evo; count = count + 1; "
                    " table.insert(lines, s.name .. ':' .. string.format('%.2f%%', evo * 100)); "
                    " end "
                    "end; "
                    "if count > 0 then "
                    " local avg = total / count; "
                    " rcon.print('AGG:' .. string.format('%.2f%%', avg * 100)); "
                    "else "
                    " rcon.print('AGG:0.00%%'); "
                    "end; "
                    "for _, line in ipairs(lines) do "
                    " rcon.print(line); "
                    "end"
                )
                resp = await rcon_client.execute(lua)
                lines = [ln.strip() for ln in resp.splitlines() if ln.strip()]
                agg_line = next((ln for ln in lines if ln.startswith("AGG:")), None)
                per_surface = [ln for ln in lines if not ln.startswith("AGG:")]

                agg_value = "0.00%"
                if agg_line:
                    agg_value = agg_line.replace("AGG:", "", 1).strip()

                if not per_surface:
                    title = "🐛 Evolution – All Surfaces"
                    message = (
                        f"Aggregate enemy evolution across non-platform surfaces: **{agg_value}**\n\n"
                        "No individual non-platform surfaces returned evolution data."
                    )
                else:
                    formatted = "\n".join(f"• `{ln}`" for ln in per_surface)
                    title = "🐛 Evolution – All Non-platform Surfaces"
                    message = (
                        f"Aggregate enemy evolution across non-platform surfaces: **{agg_value}**\n\n"
                        "Per-surface evolution:\n\n"
                        f"{formatted}"
                    )

                embed = EmbedBuilder.info_embed(title=title, message=message)
                await interaction.followup.send(embed=embed)
                logger.info(
                    "evolution_requested",
                    moderator=interaction.user.name,
                    target="all",
                )
                return

            # Single-surface mode
            surface = raw
            lua = (
                "/c "
                f"local s = game.get_surface('{surface}'); "
                "if not s then "
                " rcon.print('SURFACE_NOT_FOUND'); "
                " return "
                "end; "
                "if string.find(string.lower(s.name), 'platform') then "
                " rcon.print('SURFACE_PLATFORM_IGNORED'); "
                " return "
                "end; "
                "local evo = game.forces['enemy'].get_evolution_factor(s); "
                "rcon.print(string.format('%.2f%%', evo * 100))"
            )
            resp = await rcon_client.execute(lua)
            resp_str = resp.strip()

            if resp_str == "SURFACE_NOT_FOUND":
                embed = EmbedBuilder.error_embed(
                    f"Surface `{surface}` was not found.\n\n"
                    "Use map tools or an admin command to list available surfaces."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if resp_str == "SURFACE_PLATFORM_IGNORED":
                embed = EmbedBuilder.error_embed(
                    f"Surface `{surface}` is a platform surface and is ignored for evolution queries."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            title = f"🐛 Evolution – Surface `{surface}`"
            message = (
                f"Enemy evolution on `{surface}`: **{resp_str}**\n\n"
                "Higher evolution means stronger biters!"
            )
            embed = EmbedBuilder.info_embed(title=title, message=message)
            await interaction.followup.send(embed=embed)
            logger.info(
                "evolution_requested",
                moderator=interaction.user.name,
                target=surface,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get evolution: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error(
                "evolution_command_failed",
                error=str(e),
                target=target,
            )

    @factorio_group.command(name="admins", description="List server admins")
    async def admins_command(interaction: discord.Interaction) -> None:
        """List all server administrators."""
        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute("/admins")
            embed = EmbedBuilder.info_embed(
                title="👑 Server Administrators",
                message=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("admins_listed", moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to list admins: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("admins_command_failed", error=str(e))

    # ====================================================================
    # Health Check Command
    # ====================================================================

    @factorio_group.command(name="health", description="Check bot and server health status")
    async def health_command(interaction: discord.Interaction) -> None:
        """Display comprehensive health status of bot and connections."""
        await interaction.response.defer()

        # Global bot health
        bot_online = bot._connected
        bot_status = "🟢 Online" if bot_online else "🔴 Offline"

        # Per-user server context
        server_tag = bot.get_user_server(interaction.user.id)
        server_name = bot.get_server_display_name(interaction.user.id)

        # RCON status from monitor state
        server_state = bot.rcon_server_states.get(server_tag, {})
        last_connected = server_state.get("last_connected")
        rcon_connected = bool(server_state.get("previous_status"))

        # Fallback to direct RCON client for this user's context
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is not None:
            rcon_connected = bool(rcon_client.is_connected)

        # Monitoring uptime
        monitoring_uptime = "Unknown"
        if isinstance(last_connected, datetime):
            uptime_delta = datetime.now(timezone.utc) - last_connected
            monitoring_uptime = bot._format_uptime(uptime_delta)

        # Multi-server overall summary
        multi_summary = None
        if bot.server_manager:
            status_summary = bot.server_manager.get_status_summary()
            total = len(status_summary)
            connected_count = sum(1 for v in status_summary.values() if v)
            multi_summary = f"📡 RCON {connected_count}/{total} servers connected"

        # Build health embed
        embed = EmbedBuilder.create_base_embed(
            title="🩺 Bot & Server Health",
            color=EmbedBuilder.COLOR_INFO,
        )

        embed.add_field(name="🤖 Bot Status", value=bot_status, inline=True)
        embed.add_field(
            name="🔧 RCON Status",
            value="🟢 Connected" if rcon_connected else "🔴 Disconnected",
            inline=True,
        )
        embed.add_field(
            name="🏭 Current Server",
            value=f"[{server_tag}] {server_name}",
            inline=False,
        )
        embed.add_field(
            name="⏱️ Monitoring Since",
            value=monitoring_uptime,
            inline=True,
        )

        if multi_summary:
            embed.add_field(
                name="🌐 Multi-Server RCON",
                value=multi_summary,
                inline=False,
            )

        embed.set_footer(text="Factorio ISR")
        await interaction.followup.send(embed=embed)

    # ====================================================================
    # Player Management Commands
    # ====================================================================

    @factorio_group.command(name="kick", description="Kick a player from the server")
    @app_commands.describe(
        player="Player name to kick",
        reason="Optional reason shown to the player",
    )
    async def kick_command(
        interaction: discord.Interaction,
        player: str,
        reason: str | None = None,
    ) -> None:
        """Kick a player with admin cooldown."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            reason_part = f" {reason}" if reason else ""
            cmd = f"/kick {player}{reason_part}"
            resp = await rcon_client.execute(cmd)
            embed = EmbedBuilder.admin_action_embed(
                action="Player Kicked",
                player=player,
                moderator=interaction.user.name,
                reason=reason,
                response=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("player_kicked", player=player, reason=reason, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Kick failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("kick_command_failed", error=str(e), player=player)

    @factorio_group.command(name="ban", description="Ban a player from the server")
    @app_commands.describe(player="Player name to ban")
    async def ban_command(interaction: discord.Interaction, player: str) -> None:
        """Ban a player with admin cooldown."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        # In ban_command, after defer() and get_rcon_for_user:
        if not player or not player.strip():
            embed = EmbedBuilder.error_embed("Player name is required for ban command")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute(f"/ban {player}")
            embed = EmbedBuilder.admin_action_embed(
                action="Player Banned",
                player=player,
                moderator=interaction.user.name,
                reason=None,
                response=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("player_banned", player=player, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Ban failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("ban_command_failed", error=str(e), player=player)

    @factorio_group.command(name="unban", description="Unban a player from the server")
    @app_commands.describe(player="Player name to unban")
    async def unban_command(interaction: discord.Interaction, player: str) -> None:
        """Unban a player."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute(f"/unban {player}")
            embed = EmbedBuilder.admin_action_embed(
                action="Player Unbanned",
                player=player,
                moderator=interaction.user.name,
                reason=None,
                response=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("player_unbanned", player=player, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Unban failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("unban_command_failed", error=str(e), player=player)

    @factorio_group.command(name="mute", description="Mute a player (prevent chat)")
    @app_commands.describe(player="Player name to mute")
    async def mute_command(interaction: discord.Interaction, player: str) -> None:
        """Mute a player to prevent them from chatting."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute(f"/mute {player}")
            embed = EmbedBuilder.admin_action_embed(
                action="Player Muted",
                player=player,
                moderator=interaction.user.name,
                reason=None,
                response=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("player_muted", player=player, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Mute failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("mute_command_failed", error=str(e), player=player)

    @factorio_group.command(name="unmute", description="Unmute a player")
    @app_commands.describe(player="Player name to unmute")
    async def unmute_command(interaction: discord.Interaction, player: str) -> None:
        """Unmute a player to allow them to chat again."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute(f"/unmute {player}")
            embed = EmbedBuilder.admin_action_embed(
                action="Player Unmuted",
                player=player,
                moderator=interaction.user.name,
                reason=None,
                response=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("player_unmuted", player=player, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Unmute failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("unmute_command_failed", error=str(e), player=player)

    @factorio_group.command(name="promote", description="Promote a player to admin")
    @app_commands.describe(player="Player name to promote")
    async def promote_command(interaction: discord.Interaction, player: str) -> None:
        """Promote a player to admin status."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute(f"/promote {player}")
            embed = EmbedBuilder.admin_action_embed(
                action="Player Promoted",
                player=player,
                moderator=interaction.user.name,
                reason="Promoted to admin",
                response=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("player_promoted", player=player, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Promote failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("promote_command_failed", error=str(e), player=player)

    @factorio_group.command(name="demote", description="Demote a player from admin")
    @app_commands.describe(player="Player name to demote")
    async def demote_command(interaction: discord.Interaction, player: str) -> None:
        """Demote a player from admin status."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute(f"/demote {player}")
            embed = EmbedBuilder.admin_action_embed(
                action="Player Demoted",
                player=player,
                moderator=interaction.user.name,
                reason="Demoted from admin",
                response=resp,
            )
            await interaction.followup.send(embed=embed)
            logger.info("player_demoted", player=player, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Demote failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("demote_command_failed", error=str(e), player=player)

    # ====================================================================
    # Server Management Commands
    # ====================================================================

    @factorio_group.command(name="save", description="Save the Factorio game")
    @app_commands.describe(name="Optional save name")
    async def save_command(interaction: discord.Interaction, name: str | None = None) -> None:
        """Save the game with optional custom save name."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            cmd = f"/save {name}" if name else "/save"
            resp = await rcon_client.execute(cmd)

            # Determine the display label
            if name:
                # Custom save name provided
                label = name
            else:
                # Parse save name from response
                import re

                # Try full path format first: "Saving map to /path/to/LosHermanos.zip"
                match = re.search(r"/([^/]+?)\.zip", resp)
                if match:
                    label = match.group(1)
                else:
                    # Fallback to simpler format: "Saving to _autosave1 (non-blocking)"
                    match = re.search(r"Saving (?:map )?to ([\w-]+)", resp)
                    label = match.group(1) if match else "current save"

            embed = EmbedBuilder.info_embed(
                title="💾 Game Saved",
                message=(
                    f"Save name: **{label}**\n\n"
                    f"Server response:\n{resp}"
                ),
            )
            embed.color = EmbedBuilder.COLOR_SUCCESS
            await interaction.followup.send(embed=embed)
            logger.info("game_saved", name=label, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to save game: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("save_command_failed", error=str(e), name=name)

    @factorio_group.command(name="broadcast", description="Send a message to all players")
    @app_commands.describe(message="Message to broadcast to all players")
    async def broadcast_command(interaction: discord.Interaction, message: str) -> None:
        """Broadcast a message to all players on the server."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            escaped_msg = message.replace('"', '\\"')
            resp = await rcon_client.execute(f'/sc game.print("[color=pink]{escaped_msg}[/color]")')
            embed = EmbedBuilder.info_embed(
                title="📢 Broadcast Sent",
                message=f"Message: _{message}_\n\nAll online players have been notified.",
            )
            embed.color = EmbedBuilder.COLOR_SUCCESS
            await interaction.followup.send(embed=embed)
            logger.info("message_broadcast", message=message, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Broadcast failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("broadcast_command_failed", error=str(e), message=message)

    @factorio_group.command(name="whisper", description="Send a private message to a player")
    @app_commands.describe(
        player="Player name to whisper to",
        message="Private message to send",
    )
    async def whisper_command(
        interaction: discord.Interaction,
        player: str,
        message: str,
    ) -> None:
        """Send a private whisper message to a specific player."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Execute whisper command
            resp = await rcon_client.execute(f"/whisper {player} {message}")
            embed = EmbedBuilder.info_embed(
                title="💬 Whisper Sent",
                message=(
                    f"**To:** {player}\n"
                    f"**Message:** _{message}_\n\n"
                    f"Private message delivered to player."
                ),
            )
            embed.color = EmbedBuilder.COLOR_SUCCESS
            await interaction.followup.send(embed=embed)
            logger.info(
                "whisper_sent",
                player=player,
                message=message,
                moderator=interaction.user.name,
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Whisper failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("whisper_command_failed", error=str(e), player=player)

    @factorio_group.command(name="whitelist", description="Manage server whitelist")
    @app_commands.describe(
        action="Action to perform (add/remove/list/enable/disable)",
        player="Player name (required for add/remove)",
    )
    async def whitelist_command(
        interaction: discord.Interaction,
        action: str,
        player: str | None = None,
    ) -> None:
        """Manage the server whitelist."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        action = action.lower()

        try:
            if action == "list":
                resp = await rcon_client.execute("/whitelist get")
                title = "📋 Whitelist"
            elif action == "enable":
                resp = await rcon_client.execute("/whitelist enable")
                title = "✅ Whitelist Enabled"
            elif action == "disable":
                resp = await rcon_client.execute("/whitelist disable")
                title = "⚠️ Whitelist Disabled"
            elif action == "add":
                if not player:
                    embed = EmbedBuilder.error_embed("Player name required for 'add' action")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                resp = await rcon_client.execute(f"/whitelist add {player}")
                title = f"✅ {player} Added to Whitelist"
                logger.info("whitelist_add", player=player, moderator=interaction.user.name)
            elif action == "remove":
                if not player:
                    embed = EmbedBuilder.error_embed("Player name required for 'remove' action")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                resp = await rcon_client.execute(f"/whitelist remove {player}")
                title = f"🚫 {player} Removed from Whitelist"
                logger.info("whitelist_remove", player=player, moderator=interaction.user.name)
            else:
                embed = EmbedBuilder.error_embed(
                    f"Invalid action: {action}\nValid actions: add, remove, list, enable, disable"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = EmbedBuilder.info_embed(title=title, message=resp)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Whitelist command failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("whitelist_command_failed", error=str(e), action=action, player=player)

    # ====================================================================
    # Game Control Commands
    # ====================================================================

    @factorio_group.command(name="time", description="Set or display game time")
    @app_commands.describe(value="Time value (e.g., 0.5 for noon, 0 for midnight) or leave empty to view")
    async def time_command(interaction: discord.Interaction, value: float | None = None) -> None:
        """Set or display the game time."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            if value is None:
                # Display current time
                resp = await rcon_client.execute("/time")
                embed = EmbedBuilder.info_embed(
                    title="🕐 Current Game Time",
                    message=resp,
                )
            else:
                # Set time
                resp = await rcon_client.execute(f'/sc game.surfaces["nauvis"].daytime = {value}')
                time_desc = "noon" if abs(value - 0.5) < 0.1 else "midnight" if value < 0.1 else f"{value}"
                embed = EmbedBuilder.info_embed(
                    title="🕐 Time Changed",
                    message=f"Game time set to: **{time_desc}**\n\nServer response:\n{resp}",
                )
                logger.info("time_changed", value=value, moderator=interaction.user.name)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Time command failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("time_command_failed", error=str(e), value=value)

    @factorio_group.command(name="speed", description="Set game speed (admin only)")
    @app_commands.describe(speed="Game speed multiplier (0.1 to 10.0, default 1.0)")
    async def speed_command(interaction: discord.Interaction, speed: float) -> None:
        """Set the game speed multiplier."""
        is_limited, retry = DANGER_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if speed < 0.1 or speed > 10.0:
            embed = EmbedBuilder.error_embed("Speed must be between 0.1 and 10.0")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute(f"/sc game.speed = {speed}")
            embed = EmbedBuilder.info_embed(
                title="⚡ Game Speed Changed",
                message=f"Speed multiplier: **{speed}x**\n\n⚠️ This affects all players!\n\nServer response:\n{resp}",
            )
            embed.color = EmbedBuilder.COLOR_WARNING
            await interaction.followup.send(embed=embed)
            logger.info("speed_changed", speed=speed, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Speed change failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("speed_command_failed", error=str(e), speed=speed)

    @factorio_group.command(name="research", description="Force research a technology")
    @app_commands.describe(technology="Technology name to research")
    async def research_command(interaction: discord.Interaction, technology: str) -> None:
        """Force research a technology."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            cmd = f'/sc game.forces["player"].technologies["{technology}"].researched = true'
            resp = await rcon_client.execute(cmd)
            embed = EmbedBuilder.info_embed(
                title="🔬 Technology Researched",
                message=(
                    f"Technology: **{technology}**\n\n"
                    "The technology has been forcefully researched.\n\n"
                    f"Server response:\n{resp}"
                ),
            )
            embed.color = EmbedBuilder.COLOR_SUCCESS
            await interaction.followup.send(embed=embed)
            logger.info("tech_researched", technology=technology, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                f"Research failed: {str(e)}\n\n"
                "Make sure the technology name is correct (e.g., 'automation', 'logistics')"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("research_command_failed", error=str(e), technology=technology)

    # ====================================================================
    # Advanced Commands
    # ====================================================================

    @factorio_group.command(name="rcon", description="Run a raw RCON command")
    @app_commands.describe(command="Raw RCON command, e.g. /time or /ban Alice")
    async def rcon_command(interaction: discord.Interaction, command: str) -> None:
        """Execute raw RCON command."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get user-specific RCON client
        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute(command)
            embed = EmbedBuilder.info_embed(
                title="🖥️ RCON Executed",
                message=f"Command: `{command}`\n\nServer response:\n{resp}",
            )
            await interaction.followup.send(embed=embed)
            logger.info("raw_rcon_executed", command=command, moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"RCON command failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("rcon_command_failed", error=str(e), command=command)

    @factorio_group.command(name="help", description="Show available Factorio commands")
    async def help_command(interaction: discord.Interaction) -> None:
        """Display comprehensive help message."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # discord max subcommands for any command group is 25.
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
            "**🛠️ Advanced**\n"
            "`/factorio rcon ` – Run raw RCON command\n"
            "`/factorio help` – Show this help message\n\n"
            "_Most commands require RCON to be enabled._"
        )

        await interaction.response.send_message(help_text)

# Register the group
    bot.tree.add_command(factorio_group)
    logger.info(
    "slash_commands_registered",
    root=factorio_group.name,
    command_count=len(factorio_group.commands),
    phase="6.0-multi-server",
    )        