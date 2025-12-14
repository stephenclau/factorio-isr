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
- Game Control: 3/25 (clock, speed, research)
- Advanced: 2/25 (rcon, help)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: 17/25 (8 slots available for future expansion)

🔄 Phase 3 Status: Handlers 1-13 refactored to DI + Command Pattern
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

# ════════════════════════════════════════════════════════════════════════════
# 🔄 Phase 3: Command Handlers (DI + Command Pattern)
# ════════════════════════════════════════════════════════════════════════════

try:
    # Batch 1: Player Management
    from bot.commands.command_handlers_batch1 import (
        KickCommandHandler,
        BanCommandHandler,
        UnbanCommandHandler,
        MuteCommandHandler,
        UnmuteCommandHandler,
    )
    # Batch 2: Server Management
    from bot.commands.command_handlers_batch2 import (
        SaveCommandHandler,
        BroadcastCommandHandler,
        WhisperCommandHandler,
        WhitelistCommandHandler,
    )
    # Batch 3: Game Control + Admin
    from bot.commands.command_handlers_batch3 import (
        ClockCommandHandler,
        SpeedCommandHandler,
        PromoteCommandHandler,
        DemoteCommandHandler,
    )
except ImportError:
    try:
        from src.bot.commands.command_handlers_batch1 import (  # type: ignore
            KickCommandHandler,
            BanCommandHandler,
            UnbanCommandHandler,
            MuteCommandHandler,
            UnmuteCommandHandler,
        )
        from src.bot.commands.command_handlers_batch2 import (  # type: ignore
            SaveCommandHandler,
            BroadcastCommandHandler,
            WhisperCommandHandler,
            WhitelistCommandHandler,
        )
        from src.bot.commands.command_handlers_batch3 import (  # type: ignore
            ClockCommandHandler,
            SpeedCommandHandler,
            PromoteCommandHandler,
            DemoteCommandHandler,
        )
    except ImportError:
        from .command_handlers_batch1 import (
            KickCommandHandler,
            BanCommandHandler,
            UnbanCommandHandler,
            MuteCommandHandler,
            UnmuteCommandHandler,
        )
        from .command_handlers_batch2 import (
            SaveCommandHandler,
            BroadcastCommandHandler,
            WhisperCommandHandler,
            WhitelistCommandHandler,
        )
        from .command_handlers_batch3 import (
            ClockCommandHandler,
            SpeedCommandHandler,
            PromoteCommandHandler,
            DemoteCommandHandler,
        )

logger = structlog.get_logger()

# ════════════════════════════════════════════════════════════════════════════
# 🔄 Phase 3: Global Handler Instances
# ════════════════════════════════════════════════════════════════════════════

kick_handler: Optional[KickCommandHandler] = None
ban_handler: Optional[BanCommandHandler] = None
unban_handler: Optional[UnbanCommandHandler] = None
mute_handler: Optional[MuteCommandHandler] = None
unmute_handler: Optional[UnmuteCommandHandler] = None
save_handler: Optional[SaveCommandHandler] = None
broadcast_handler: Optional[BroadcastCommandHandler] = None
whisper_handler: Optional[WhisperCommandHandler] = None
whitelist_handler: Optional[WhitelistCommandHandler] = None
clock_handler: Optional[ClockCommandHandler] = None
speed_handler: Optional[SpeedCommandHandler] = None
promote_handler: Optional[PromoteCommandHandler] = None
demote_handler: Optional[DemoteCommandHandler] = None


# ════════════════════════════════════════════════════════════════════════════
# 🔄 Phase 3: Composition Root
# ════════════════════════════════════════════════════════════════════════════

def _initialize_command_handlers_all(bot: Any) -> None:
    """Initialize all 13 command handlers with DI."""
    global (
        kick_handler, ban_handler, unban_handler, mute_handler, unmute_handler,
        save_handler, broadcast_handler, whisper_handler, whitelist_handler,
        clock_handler, speed_handler, promote_handler, demote_handler,
    )

    logger.info("initializing_phase3_handlers", count=13)

    # 🔴 BATCH 1: Player Management (5 handlers)
    kick_handler = KickCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    ban_handler = BanCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    unban_handler = UnbanCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    mute_handler = MuteCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    unmute_handler = UnmuteCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    logger.info("batch1_initialized", handlers=5)

    # 🟠 BATCH 2: Server Management (4 handlers)
    save_handler = SaveCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    broadcast_handler = BroadcastCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    whisper_handler = WhisperCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    whitelist_handler = WhitelistCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    logger.info("batch2_initialized", handlers=4)

    # 🟡 BATCH 3: Game Control + Admin (4 handlers)
    clock_handler = ClockCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    speed_handler = SpeedCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    promote_handler = PromoteCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    demote_handler = DemoteCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    logger.info("batch3_initialized", handlers=4)
    logger.info("phase3_all_handlers_initialized", total=13)


def register_factorio_commands(bot: Any) -> None:
    """Register all /factorio subcommands.

    This function creates and registers the complete /factorio command tree.
    Discord limit: 25 subcommands per group (we use 17).

    Args:
        bot: DiscordBot instance with user_context, server_manager attributes
    """
    # 🔄 Initialize Phase 3 handlers
    _initialize_command_handlers_all(bot)

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
            # ✨ NEW: Get shared metrics engine and gather comprehensive metrics
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
                if minutes > 0:
                    parts.append(f"{minutes}m")
                uptime_text = " ".join(parts) if parts else "< 1m"

            # ✨ Build rich embed with comprehensive metrics
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

            # ✨ Performance Metrics (from metrics engine)
            # FIX: Prioritize pause state over fetching state. When is_paused=True,
            # display that immediately without showing "Fetching..." text.
            is_paused = metrics.get("is_paused", False)
            ups_value = metrics.get("ups")
            
            if is_paused:
                # Pause state is definitive - show immediately
                embed.add_field(
                    name="📡 Server State",
                    value="⏸️ Paused",
                    inline=True,
                )
            elif ups_value is not None:
                # UPS data available and not paused - show running state
                ups_str = f"{ups_value:.1f}"
                embed.add_field(
                    name="📡 Server State",
                    value=f"▶️ Running @ {ups_str}",
                    inline=True,
                )
            else:
                # UPS data not yet available - show fetching state
                embed.add_field(
                    name="📡 Server State",
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

            # Players (from metrics engine)
            player_count = metrics.get("player_count", 0)
            embed.add_field(
                name="👥 Players Online",
                value=str(player_count),
                inline=True,
            )

            # Game time (from metrics engine)
            if metrics.get("play_time"):
                embed.add_field(
                    name="🎮🕐 Total Play Time",
                    value=metrics["play_time"],
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
            # ✨ Evolution Factor – Display nauvis and gleba separately if available
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
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        raw = target.strip()
        lower = raw.lower()

        try:
            # Aggregate all non-platform surfaces mode
            if lower == "all":
                # Aggregate + detailed per-surface evolution, skipping platform surfaces
                lua = (
                    "/sc "
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
                "/sc "
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
                    if minutes > 0:
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
    # PLAYER MANAGEMENT COMMANDS (7/25) – 🔄 PHASE 3: HANDLER DELEGATIONS
    # ========================================================================

    @factorio_group.command(name="kick", description="Kick a player from the server")
    @app_commands.describe(player="Player name", reason="Reason for kick (optional)")
    async def kick_command(
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        """Kick a player. Delegates to KickCommandHandler."""
        result = await kick_handler.execute(interaction, player=player, reason=reason)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="ban", description="Ban a player from the server")
    @app_commands.describe(player="Player name", reason="Reason for ban (optional)")
    async def ban_command(
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        """Ban a player. Delegates to BanCommandHandler."""
        result = await ban_handler.execute(interaction, player=player, reason=reason)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="unban", description="Unban a player")
    @app_commands.describe(player="Player name")
    async def unban_command(
        interaction: discord.Interaction,
        player: str,
    ) -> None:
        """Unban a player. Delegates to UnbanCommandHandler."""
        result = await unban_handler.execute(interaction, player=player)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="mute", description="Mute a player")
    @app_commands.describe(player="Player name")
    async def mute_command(interaction: discord.Interaction, player: str) -> None:
        """Mute a player from chat. Delegates to MuteCommandHandler."""
        result = await mute_handler.execute(interaction, player=player)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="unmute", description="Unmute a player")
    @app_commands.describe(player="Player name")
    async def unmute_command(interaction: discord.Interaction, player: str) -> None:
        """Unmute a player. Delegates to UnmuteCommandHandler."""
        result = await unmute_handler.execute(interaction, player=player)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="promote", description="Promote player to admin")
    @app_commands.describe(player="Player name")
    async def promote_command(interaction: discord.Interaction, player: str) -> None:
        """Promote a player to admin. Delegates to PromoteCommandHandler."""
        result = await promote_handler.execute(interaction, player=player)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="demote", description="Demote player from admin")
    @app_commands.describe(player="Player name")
    async def demote_command(interaction: discord.Interaction, player: str) -> None:
        """Demote a player from admin. Delegates to DemoteCommandHandler."""
        result = await demote_handler.execute(interaction, player=player)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    # ========================================================================
    # SERVER MANAGEMENT COMMANDS (4/25) – 🔄 PHASE 3: HANDLER DELEGATIONS
    # ========================================================================

    @factorio_group.command(name="save", description="Save the game")
    @app_commands.describe(name="Save name (optional, defaults to auto-save)")
    async def save_command(interaction: discord.Interaction, name: Optional[str] = None) -> None:
        """Save the game. Delegates to SaveCommandHandler."""
        result = await save_handler.execute(interaction, name=name)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="broadcast", description="Send message to all players")
    @app_commands.describe(message="Message to broadcast")
    async def broadcast_command(interaction: discord.Interaction, message: str) -> None:
        """Broadcast a message to all players. Delegates to BroadcastCommandHandler."""
        result = await broadcast_handler.execute(interaction, message=message)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="whisper", description="Send private message to a player")
    @app_commands.describe(player="Player name", message="Message to send")
    async def whisper_command(
        interaction: discord.Interaction,
        player: str,
        message: str,
    ) -> None:
        """Send a private message to a player. Delegates to WhisperCommandHandler."""
        result = await whisper_handler.execute(interaction, player=player, message=message)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="whitelist", description="Manage server whitelist")
    @app_commands.describe(
        action="Action to perform (add/remove/list/enable/disable)",
        player="Player name (required for add/remove)",
    )
    async def whitelist_command(
        interaction: discord.Interaction,
        action: str,
        player: Optional[str] = None,
    ) -> None:
        """Manage the server whitelist. Delegates to WhitelistCommandHandler."""
        result = await whitelist_handler.execute(interaction, action=action, player=player)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    # ========================================================================
    # GAME CONTROL COMMANDS (3/25) – 🔄 PHASE 3: HANDLER DELEGATIONS
    # ========================================================================

    @factorio_group.command(name="clock", description="Set or display game daytime")
    @app_commands.describe(value="'day'/'night' or 0.0-1.0, or leave empty to view")
    async def clock_command(interaction: discord.Interaction, value: Optional[str] = None) -> None:
        """Set or display the game clock. Delegates to ClockCommandHandler."""
        result = await clock_handler.execute(interaction, value=value)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(name="speed", description="Set game speed")
    @app_commands.describe(value="Game speed (0.1-10.0, 1.0 = normal)")
    async def speed_command(interaction: discord.Interaction, value: float) -> None:
        """Set game speed. Delegates to SpeedCommandHandler."""
        result = await speed_handler.execute(interaction, value=value)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )

    @factorio_group.command(
        name="research",
        description="Manage technology research (Coop: player force, PvP: specify force)"
    )
    @app_commands.describe(
        force='Force name (e.g., "player", "enemy"). Defaults to "player".',
        action='Action: "all", tech name, "undo", or empty to display status',
        technology='Technology name (for undo operations with specific tech)',
    )
    async def research_command(
        interaction: discord.Interaction,
        force: Optional[str] = None,
        action: Optional[str] = None,
        technology: Optional[str] = None,
    ) -> None:
        """Manage technology research with multi-force support."""
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # ════════════════════════════════════════════════════════════════
            # PARAMETER RESOLUTION
            # ════════════════════════════════════════════════════════════════
            # Default force to "player" if not provided (Coop mode)
            target_force = (force.lower().strip() if force else None) or "player"

            # ════════════════════════════════════════════════════════════════
            # MODE 1: DISPLAY STATUS (No arguments)
            # ════════════════════════════════════════════════════════════════
            if action is None:
                # Count researched vs total technologies
                resp = await rcon_client.execute(
                    f'/sc '
                    f'local researched = 0; '
                    f'local total = 0; '
                    f'for _, tech in pairs(game.forces["{target_force}"].technologies) do '
                    f' total = total + 1; '
                    f' if tech.researched then researched = researched + 1 end; '
                    f'end; '
                    f'rcon.print(string.format("%d/%d", researched, total))'
                )

                researched_count = "0/0"
                try:
                    parts = resp.strip().split("/")
                    if len(parts) == 2:
                        researched_count = resp.strip()
                except (ValueError, IndexError):
                    logger.warning(
                        "research_status_parse_failed",
                        response=resp,
                        force=target_force,
                    )

                embed = EmbedBuilder.info_embed(
                    title="🔬 Technology Status",
                    message=f"Force: **{target_force}**\n"
                            f"Technologies researched: **{researched_count}**\n\n"
                            f"Use `/factorio research {target_force if target_force != 'player' else ''}all` to research all.\n"
                            f"Or `/factorio research {target_force + ' ' if target_force != 'player' else ''}<tech-name>` for specific tech.",
                )
                await interaction.followup.send(embed=embed)
                logger.info(
                    "research_status_checked",
                    user=interaction.user.name,
                    force=target_force,
                )
                return

            # ════════════════════════════════════════════════════════════════
            # MODE 2: RESEARCH ALL TECHNOLOGIES
            # ════════════════════════════════════════════════════════════════
            action_lower = action.lower().strip()

            if action_lower == "all" and technology is None:
                resp = await rcon_client.execute(
                    f'/sc game.forces["{target_force}"].research_all_technologies(); '
                    f'rcon.print("All technologies researched")'
                )

                embed = EmbedBuilder.info_embed(
                    title="🔬 All Technologies Researched",
                    message=f"Force: **{target_force}**\n\n"
                            f"All technologies have been instantly unlocked!\n\n"
                            f"{target_force.capitalize()} force can now access all previously locked content.",
                )
                embed.color = EmbedBuilder.COLOR_SUCCESS
                await interaction.followup.send(embed=embed)

                logger.info(
                    "all_technologies_researched",
                    moderator=interaction.user.name,
                    force=target_force,
                )
                return

            # ════════════════════════════════════════════════════════════════
            # MODE 3: UNDO OPERATIONS
            # ════════════════════════════════════════════════════════════════
            if action_lower == "undo":
                # MODE 3a: UNDO ALL
                if technology is None or technology.lower().strip() == "all":
                    resp = await rcon_client.execute(
                        f'/sc '
                        f'for _, tech in pairs(game.forces["{target_force}"].technologies) do '
                        f' tech.researched = false; '
                        f'end; '
                        f'rcon.print("All technologies reverted")'
                    )

                    embed = EmbedBuilder.info_embed(
                        title="⏮️ All Technologies Reverted",
                        message=f"Force: **{target_force}**\n\n"
                                f"All technology research has been undone!\n\n"
                                f"{target_force.capitalize()} force must re-research technologies from scratch.",
                    )
                    embed.color = EmbedBuilder.COLOR_WARNING
                    await interaction.followup.send(embed=embed)

                    logger.info(
                        "all_technologies_reverted",
                        moderator=interaction.user.name,
                        force=target_force,
                    )
                    return

                # MODE 3b: UNDO SINGLE TECHNOLOGY
                tech_name = technology.strip()
                try:
                    resp = await rcon_client.execute(
                        f'/sc game.forces["{target_force}"].technologies["{tech_name}"].researched = false; '
                        f'rcon.print("Technology reverted: {tech_name}")'
                    )

                    embed = EmbedBuilder.info_embed(
                        title="⏮️ Technology Reverted",
                        message=f"Force: **{target_force}**\n"
                                f"Technology: **{tech_name}**\n\n"
                                f"Technology has been undone.",
                    )
                    embed.color = EmbedBuilder.COLOR_WARNING
                    await interaction.followup.send(embed=embed)

                    logger.info(
                        "technology_reverted",
                        technology=tech_name,
                        moderator=interaction.user.name,
                        force=target_force,
                    )
                    return

                except Exception as e:
                    embed = EmbedBuilder.error_embed(
                        f"Failed to revert technology: {str(e)}\n\n"
                        f"Force: `{target_force}`\n"
                        f"Technology: `{tech_name}`\n\n"
                        f"Verify the force exists and technology name is correct\n"
                        f"(e.g., automation-2, logistics-3, steel-processing)"
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    logger.error(
                        "research_undo_failed",
                        technology=tech_name,
                        force=target_force,
                        error=str(e),
                    )
                    return

            # ════════════════════════════════════════════════════════════════
            # MODE 4: RESEARCH SINGLE TECHNOLOGY
            # ════════════════════════════════════════════════════════════════
            if technology is None:
                # User provided action but no technology
                # Assume action is the technology name
                tech_name = action_lower
            else:
                tech_name = technology.strip()

            try:
                resp = await rcon_client.execute(
                    f'/sc game.forces["{target_force}"].technologies["{tech_name}"].researched = true; '
                    f'rcon.print("Technology researched: {tech_name}")'
                )

                embed = EmbedBuilder.info_embed(
                    title="🔬 Technology Researched",
                    message=f"Force: **{target_force}**\n"
                            f"Technology: **{tech_name}**\n\n"
                            f"Technology has been researched.",
                )
                embed.color = EmbedBuilder.COLOR_SUCCESS
                await interaction.followup.send(embed=embed)

                logger.info(
                    "technology_researched",
                    technology=tech_name,
                    moderator=interaction.user.name,
                    force=target_force,
                )

            except Exception as e:
                embed = EmbedBuilder.error_embed(
                    f"Failed to research technology: {str(e)}\n\n"
                    f"Force: `{target_force}`\n"
                    f"Technology: `{tech_name}`\n\n"
                    f"Valid examples: automation-2, logistics-3, steel-processing, electric-furnace\n\n"
                    f"Use `/factorio research {target_force if target_force != 'player' else ''}` to see progress."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error(
                    "research_command_failed",
                    technology=tech_name,
                    force=target_force,
                    error=str(e),
                )

        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Research command failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error(
                "research_command_failed",
                error=str(e),
                force=force,
                action=action,
                technology=technology,
            )

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
            "**🌍 Multi-Server**\n"
            "`/factorio servers` – List available servers\n"
            "`/factorio connect <server>` – Switch to a server\n\n"
            "**📊 Server Information**\n"
            "`/factorio status` – Show server status and uptime\n"
            "`/factorio players` – List players currently online\n"
            "`/factorio version` – Show Factorio server version\n"
            "`/factorio seed` – Show map seed\n"
            "`/factorio evolution [target]` – Show enemy evolution\n"
            "  \n Use 'all' for aggregate or specific surface name\n"
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
            "  \n Actions: add, remove, list, enable, disable\n\n"
            "**🎮 Game Control**\n"
            "`/factorio clock [value]` – Show/set game time\n"
            "`/factorio speed <value>` – Set game speed (0.1-10.0)\n"
            "`/factorio research <technology>` – Force research tech\n\n"
            "**🛠️ Advanced**\n"
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
            "slash_commands_registered",
            root=factorio_group.name,
            command_count=len(factorio_group.commands),
            phase="Phase 3: DI handlers integrated (13/17 commands refactored)",
        )
