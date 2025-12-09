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

"""  # START OF FILE

Discord bot client for Factorio ISR - Phase 6.0 Multi-Server Support.

Provides interactive bot functionality with slash commands, event handling,
Phase 5.1 features (embeds, cooldowns), Phase 5.2 RCON monitoring,
and Phase 6.0 multi-server support.
"""

import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict, List

import discord
from discord import app_commands
import structlog
import yaml  # type: ignore[import]

# Phase 5.1: Rate limiting and embeds
from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
from discord_interface import EmbedBuilder

# Import event parser and formatter
try:
    from event_parser import FactorioEvent, FactorioEventFormatter
except ImportError:
    from event_parser import FactorioEvent, FactorioEventFormatter  # type: ignore

# Phase 6: Multi-server support
try:
    from .config import ServerConfig
    from .server_manager import ServerManager
except ImportError:
    try:
        from config import ServerConfig
        from server_manager import ServerManager  # type: ignore
    except ImportError:
        # ServerManager may not be available in single-server mode
        ServerManager = None  # type: ignore
        ServerConfig = None  # type: ignore

logger = structlog.get_logger()


class DiscordBot(discord.Client):
    """Discord bot client with slash command support, RCON monitoring, and multi-server support."""

    def __init__(
        self,
        token: str,
        bot_name: str = "Factorio ISR",
        *,
        intents: Optional[discord.Intents] = None,
        breakdown_mode: str = "transition",
        breakdown_interval: int = 300,
    ):
        """
        Initialize Discord bot.

        Args:
            token: Discord bot token
            bot_name: Display name for the bot
            intents: Discord intents (auto-configured if None)
        """
        # Configure intents
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True  # Required to read messages
            intents.guilds = True
            intents.members = True  # Optional, for advanced features

        super().__init__(intents=intents)

        self.token = token
        self.bot_name = bot_name
        self.tree = app_commands.CommandTree(self)
        self._ready = asyncio.Event()
        self._connected = False
        self._connection_task: Optional[asyncio.Task] = None

        # Channel for sending Factorio events (set by application)
        self.event_channel_id: Optional[int] = None

        # RCON client for slash commands (set by application - legacy single-server)
        self.rcon_client: Optional[Any] = None

        self.server_manager: Optional[Any] = None  # ServerManager instance set by application later

        # Phase 5.2: RCON status monitoring
        self.rcon_last_connected: Optional[datetime] = None
        self.rcon_status_notified = False
        self.rcon_monitor_task: Optional[asyncio.Task] = None

        # Phase 6: Multi-server support
        self.server_manager: Optional[Any] = None  # ServerManager instance
        self.user_contexts: Dict[int, str] = {}  # {user_id: server_tag}

        # Per-server RCON state for multi-server monitoring
        self.rcon_server_states: Dict[str, Dict[str, Any]] = {}  # {tag: {"previous_status": bool | None, "last_connected": datetime | None}}

        # RCON breakdown scheduling
        self.rcon_breakdown_mode = breakdown_mode.lower()
        self.rcon_breakdown_interval = breakdown_interval
        self._last_rcon_breakdown_sent: Optional[datetime] = None

        # Custom mention config from config/mentions.yml
        self._mention_group_keywords: Dict[str, List[str]] = {}
        self._load_mention_config()

        logger.info(
            "breakdown_config_received",
            breakdown_mode_param=breakdown_mode,
            breakdown_mode_stored=self.rcon_breakdown_mode,
            breakdown_interval=breakdown_interval,
        )

        logger.info("discord_bot_initialized", bot_name=bot_name, phase="6.0-multi-server")

    # ========================================================================
    # Config loading
    # ========================================================================

    def _load_mention_config(self) -> None:
        """
        Load custom mention group keywords from config/mentions.yml.

        Expected format:

        mentions:
          groups:
            operations:
              - "operations"
              - "ops"
        """
        config_path = os.path.join("config", "mentions.yml")
        if not os.path.exists(config_path):
            logger.info("mention_config_not_found", path=config_path)
            self._mention_group_keywords = {}
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("mention_config_load_failed", path=config_path, error=str(e))
            self._mention_group_keywords = {}
            return

        mentions = data.get("mentions") or {}
        groups = mentions.get("roles") or {}

        result: Dict[str, List[str]] = {}
        for group_name, tokens in groups.items():
            if isinstance(tokens, list):
                cleaned = [str(t).strip() for t in tokens if str(t).strip()]
                if cleaned:
                    result[group_name] = cleaned

        self._mention_group_keywords = result
        logger.info(
            "mention_config_loaded",
            path=config_path,
            groups=len(self._mention_group_keywords),
        )

    # ========================================================================
    # PHASE 6: Multi-Server Context Management
    # ========================================================================

    def get_user_server(self, user_id: int) -> str:
        """
        Get user's current server context.

        Args:
            user_id: Discord user ID

        Returns:
            Server tag (defaults to "primary" for single-server mode)
        """
        if user_id in self.user_contexts:
            return self.user_contexts[user_id]

        # Multi-server is required now
        if not self.server_manager:
            raise RuntimeError("ServerManager is not configured (multi-server mode required)")

        tags = self.server_manager.list_tags()
        if not tags:
            raise RuntimeError("No servers configured in ServerManager")

        default_tag = tags[0]
        logger.debug(
            "user_server_context_defaulted",
            user_id=user_id,
            server_tag=default_tag,
        )
        return default_tag

    def set_user_server(self, user_id: int, server_tag: str) -> None:
        """
        Set user's current server context.

        Args:
            user_id: Discord user ID
            server_tag: Server tag to set as context
        """
        self.user_contexts[user_id] = server_tag
        logger.info(
            "user_server_context_changed",
            user_id=user_id,
            server_tag=server_tag,
        )

    def get_rcon_for_user(self, user_id: int) -> Optional[Any]:
        """
        Get RCON client for user's current server context.

        Args:
            user_id: Discord user ID

        Returns:
            RconClient instance or None if not available
        """
        # Multi-server mode
        if not self.server_manager:
            raise RuntimeError("ServerManager is not configured (multi-server mode required)")

        server_tag = self.get_user_server(user_id)
        try:
            return self.server_manager.get_client(server_tag)
        except KeyError:
            logger.warning(
                "user_server_context_invalid",
                user_id=user_id,
                server_tag=server_tag,
            )
            return None

    def get_server_display_name(self, user_id: int) -> str:
        """
        Get display name of user's current server.

        Args:
            user_id: Discord user ID

        Returns:
            Server display name or "Unknown"
        """
        if not self.server_manager:
            return "Unknown"

        server_tag = self.get_user_server(user_id)
        try:
            config = self.server_manager.get_config(server_tag)
            return config.name
        except KeyError:
            return "Unknown"

    # ========================================================================
    # PHASE 6: RCON Connection Status Format Helper
    # ========================================================================

    def _format_uptime(self, uptime_delta) -> str:
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

    # ========================================================================
    # PHASE 6: RCON Server Uptime Query
    # ========================================================================

    async def _get_game_uptime(self, rcon_client: Any) -> str:
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

            # Use existing _format_uptime method
            uptime_delta = timedelta(seconds=total_seconds)
            formatted = self._format_uptime(uptime_delta)
            logger.debug("game_uptime_calculated", ticks=ticks, seconds=total_seconds, formatted=formatted)
            return formatted

        except Exception as e:
            logger.warning("game_uptime_query_failed", error=str(e), exc_info=True)
            return "Unknown"

    # ========================================================================
    # PHASE 5.2: RCON Status Monitoring (Updated for Multi-Server)
    # ========================================================================

    async def update_presence(self) -> None:
        """Update bot presence to reflect RCON connection status."""
        if not self._connected or not hasattr(self, "user") or self.user is None:
            return

        try:
            status_text = "🔺 RCON (0/0)"
            status = discord.Status.idle
            activity_type = discord.ActivityType.watching

            if self.server_manager:
                # Multi-server mode: show connected/total count
                status_summary = self.server_manager.get_status_summary()
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

            await self.change_presence(status=status, activity=activity)
            logger.debug("presence_updated", status=status_text)
        except Exception as e:
            logger.warning("presence_update_failed", error=str(e))

    def _serialize_rcon_state(self) -> Dict[str, Any]:
        """Serialize RCON server state to a JSON-friendly dict."""
        result: Dict[str, Any] = {}
        for tag, state in self.rcon_server_states.items():
            last_connected = state.get("last_connected")
            result[tag] = {
                "previous_status": state.get("previous_status"),
                "last_connected": last_connected.isoformat() if isinstance(last_connected, datetime) else None,
            }
        return result

    def _load_rcon_state_from_json(self, data: Dict[str, Any]) -> None:
        """Load RCON server state from JSON-friendly dict."""
        self.rcon_server_states = {}
        for tag, state in data.items():
            last_connected_raw = state.get("last_connected")
            last_connected: Optional[datetime] = None
            if isinstance(last_connected_raw, str):
                try:
                    last_connected = datetime.fromisoformat(last_connected_raw)
                except ValueError:
                    last_connected = None

            self.rcon_server_states[tag] = {
                "previous_status": state.get("previous_status"),
                "last_connected": last_connected,
            }

    async def _handle_server_status_change(self, server_tag: str, current_status: bool) -> bool:
        """
        Handle status transition for a single server.

        Returns:
            True if this call detected a transition, False otherwise.
        """
        state = self.rcon_server_states.setdefault(
            server_tag,
            {"previous_status": None, "last_connected": None},
        )

        previous = state["previous_status"]
        transition_detected = False

        if previous is not None and current_status != previous:
            transition_detected = True
            if current_status:
                # Reconnected
                await self._notify_rcon_reconnected(server_tag)
                state["last_connected"] = datetime.now(timezone.utc)
            else:
                # Disconnected
                await self._notify_rcon_disconnected(server_tag)
        elif previous is None and current_status:
            # First check and already connected
            state["last_connected"] = datetime.now(timezone.utc)

        state["previous_status"] = current_status
        return transition_detected

    def _build_rcon_breakdown_embed(self) -> Optional[discord.Embed]:
        """Build an embed summarizing RCON connectivity for all servers."""
        if not self.server_manager:
            return None

        status_summary = self.server_manager.get_status_summary()
        if not status_summary:
            return None

        total = len(status_summary)
        connected_count = sum(1 for v in status_summary.values() if v)

        embed = discord.Embed(
            title="📡 RCON Connection Status",
            color=EmbedBuilder.COLOR_INFO,
            timestamp=discord.utils.utcnow(),
        )

        for tag, config in self.server_manager.list_servers().items():
            is_connected = status_summary.get(tag, False)
            status_icon = "🟢" if is_connected else "🔴"

            field_lines = [
                f"{status_icon} {'Online' if is_connected else 'Offline'}",
                f"Host: `{config.rcon_host}:{config.rcon_port}`",
            ]

            if getattr(config, "description", None):
                field_lines.insert(0, f"*{config.description}*")

            embed.add_field(
                name=f"[{tag}] {config.name}",
                value="\n".join(field_lines),
                inline=False,
            )

        embed.set_footer(text=f"RCON ({connected_count}/{total} servers connected)")
        return embed

    async def _monitor_rcon_status(self) -> None:
        """
        Monitor RCON connection status and send notifications on changes.

        Multi-server:
        - Tracks per-server transitions via server_manager.get_status_summary().

        Single-server legacy mode is no longer supported here; ServerManager and at
        least one configured server are required.
        """
        logger.info("rcon_status_monitor_started")

        # For compatibility with presence / health, keep this as "any connected"
        previous_any_status: Optional[bool] = None

        while self._connected:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                transitions_detected = False

                if not self.server_manager:
                    logger.error("rcon_status_monitor_no_server_manager")
                    current_any_status = False
                else:
                    status_summary = self.server_manager.get_status_summary()
                    current_any_status = any(status_summary.values())

                    for tag, status in status_summary.items():
                        if await self._handle_server_status_change(tag, status):
                            transitions_detected = True

                # Maintain rcon_last_connected for "any connected" uptime if needed elsewhere
                if previous_any_status is not None and current_any_status != previous_any_status:
                    if current_any_status:
                        self.rcon_last_connected = datetime.now(timezone.utc)
                    # When going disconnected, rcon_last_connected is left as last connected time
                elif previous_any_status is None and current_any_status:
                    self.rcon_last_connected = datetime.now(timezone.utc)

                # RCON breakdown scheduling: check if we should send
                should_send_breakdown = False

                if self.rcon_breakdown_mode == "transition":
                    # Send on any server transition
                    should_send_breakdown = transitions_detected
                elif self.rcon_breakdown_mode == "interval":
                    # Send periodically based on interval
                    now = datetime.now(timezone.utc)
                    if self._last_rcon_breakdown_sent is None:
                        # First time - send immediately
                        should_send_breakdown = True
                    else:
                        elapsed = (now - self._last_rcon_breakdown_sent).total_seconds()
                        should_send_breakdown = elapsed >= self.rcon_breakdown_interval

                if should_send_breakdown and self.server_manager:
                    embed = self._build_rcon_breakdown_embed()
                    if embed is not None:
                        # Global channel
                        if self.event_channel_id is not None:
                            channel = self.get_channel(self.event_channel_id)
                            if channel and isinstance(channel, discord.TextChannel):
                                try:
                                    await channel.send(embed=embed)
                                    logger.info(
                                        "rcon_breakdown_sent",
                                        scope="global",
                                        channel_id=self.event_channel_id,
                                    )
                                except Exception as e:
                                    logger.warning(
                                        "rcon_breakdown_send_failed",
                                        scope="global",
                                        channel_id=self.event_channel_id,
                                        error=str(e),
                                    )

                        # Per-server channels
                        for tag, config in self.server_manager.list_servers().items():
                            server_channel_id = getattr(config, "event_channel_id", None)
                            if not server_channel_id:
                                continue

                            # Avoid double-send to same channel if it's also global
                            if (
                                self.event_channel_id is not None
                                and server_channel_id == self.event_channel_id
                            ):
                                continue

                            channel = self.get_channel(server_channel_id)
                            if channel and isinstance(channel, discord.TextChannel):
                                try:
                                    await channel.send(embed=embed)
                                    logger.info(
                                        "rcon_breakdown_sent",
                                        scope="server",
                                        server_tag=tag,
                                        channel_id=server_channel_id,
                                    )
                                except Exception as e:
                                    logger.warning(
                                        "rcon_breakdown_send_failed",
                                        scope="server",
                                        server_tag=tag,
                                        channel_id=server_channel_id,
                                        error=str(e),
                                    )

                    self._last_rcon_breakdown_sent = datetime.now(timezone.utc)

                await self.update_presence()
                previous_any_status = current_any_status

            except asyncio.CancelledError:
                logger.info("rcon_status_monitor_cancelled")
                break
            except Exception as e:
                logger.error("rcon_status_monitor_error", error=str(e), exc_info=True)
                await asyncio.sleep(10)

    async def _notify_rcon_disconnected(self, server_tag: str) -> None:
        """Send notification when RCON disconnects."""
        if not self.event_channel_id or self.rcon_status_notified:
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                embed = EmbedBuilder.info_embed(
                    title="⚠️ RCON Connection Lost",
                    message=(
                        "Connection to Factorio server lost.\n"
                        "Bot will automatically reconnect when server is available.\n\n"
                        "Commands requiring RCON will be unavailable until reconnection."
                    ),
                )
                embed.color = EmbedBuilder.COLOR_WARNING
                await channel.send(embed=embed)
                self.rcon_status_notified = True
                logger.info("rcon_disconnection_notified", channel_id=self.event_channel_id, server_tag=server_tag)

                # Update presence to reflect disconnected state
                await self.update_presence()
        except Exception as e:
            logger.warning("rcon_disconnection_notification_failed", error=str(e), server_tag=server_tag)

    async def _notify_rcon_reconnected(self, server_tag: str) -> None:
        """Send notification when RCON reconnects."""
        if not self.event_channel_id:
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                # Calculate downtime if we know when we lost connection
                downtime_msg = ""
                if self.rcon_last_connected:
                    downtime = datetime.now(timezone.utc) - self.rcon_last_connected
                    minutes = int(downtime.total_seconds() / 60)
                    if minutes > 0:
                        downtime_msg = f"\nDowntime: ~{minutes} minute{'s' if minutes != 1 else ''}"

                embed = EmbedBuilder.info_embed(
                    title="✅ RCON Reconnected",
                    message=(
                        f"Successfully reconnected to Factorio server!{downtime_msg}\n\n"
                        "All bot commands are now fully operational."
                    ),
                )
                embed.color = EmbedBuilder.COLOR_SUCCESS
                await channel.send(embed=embed)
                self.rcon_status_notified = False
                logger.info("rcon_reconnection_notified", channel_id=self.event_channel_id, server_tag=server_tag)

                # Update presence to reflect reconnected state
                await self.update_presence()
        except Exception as e:
            logger.warning("rcon_reconnection_notification_failed", error=str(e), server_tag=server_tag)

    # ========================================================================
    # Bot Lifecycle
    # ========================================================================

    async def clear_global_commands(self) -> None:
        """Clear all global commands (one-time cleanup)."""
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            logger.info("global_commands_cleared")
        except Exception as e:
            logger.error("clear_global_commands_failed", error=str(e))

    async def setup_hook(self) -> None:
        """Called when the bot is starting up. Set up commands here."""
        await self._register_commands()
        logger.info("discord_bot_setup_complete")

    async def _register_commands(self) -> None:
        """Register slash commands with a single root and subcommands."""
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
            if not self.server_manager:
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
                current_tag = self.get_user_server(interaction.user.id)
                status_summary = self.server_manager.get_status_summary()

                embed = discord.Embed(
                    title="📡 Available Factorio Servers",
                    color=EmbedBuilder.COLOR_INFO,
                    timestamp=discord.utils.utcnow(),
                )

                if not self.server_manager.list_tags():
                    embed.description = "No servers configured."
                else:
                    embed.description = f"**Your Context:** `{current_tag}`\n\n"

                for tag, config in self.server_manager.list_servers().items():
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
                    server_count=len(self.server_manager.list_tags()),
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
            if not self.server_manager:
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
                if server not in self.server_manager.clients:
                    available_list = []
                    for tag, config in self.server_manager.list_servers().items():
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
                self.set_user_server(interaction.user.id, server)

                # Get server info
                config = self.server_manager.get_config(server)
                client = self.server_manager.get_client(server)
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

            await interaction.response.defer()

            # Per-user server context
            server_tag = self.get_user_server(interaction.user.id)
            server_name = self.get_server_display_name(interaction.user.id)

            # User-specific RCON client
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                embed = EmbedBuilder.error_embed(
                    f"RCON not available for {server_name}.\n"
                    "Use `/factorio servers` to see available servers."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                # Bot + RCON status
                bot_online = self._connected
                bot_status = "🟢 Online" if bot_online else "🔴 Offline"

                # Players
                players = await rcon_client.get_players()
                player_names = players  # get_players() returns list[str]
                player_count = len(player_names)

                # RCON monitor uptime for this server (from rcon_server_states)
                uptime_text = "Unknown"
                state = self.rcon_server_states.get(server_tag)
                last_connected = state.get("last_connected") if state else None
                if isinstance(last_connected, datetime):
                    uptime_delta = datetime.now(timezone.utc) - last_connected
                    uptime_text = self._format_uptime(uptime_delta)

                # Actual in-game uptime from game.tick (best-effort)
                game_uptime = await self._get_game_uptime(rcon_client)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            bot_online = self._connected
            bot_status = "🟢 Online" if bot_online else "🔴 Offline"

            # Per-user server context
            server_tag = self.get_user_server(interaction.user.id)
            server_name = self.get_server_display_name(interaction.user.id)

            # RCON status from monitor state
            server_state = self.rcon_server_states.get(server_tag, {})
            last_connected = server_state.get("last_connected")
            rcon_connected = bool(server_state.get("previous_status"))

            # Fallback to direct RCON client for this user's context
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is not None:
                rcon_connected = bool(rcon_client.is_connected)

            # Monitoring uptime
            monitoring_uptime = "Unknown"
            if isinstance(last_connected, datetime):
                uptime_delta = datetime.now(timezone.utc) - last_connected
                monitoring_uptime = self._format_uptime(uptime_delta)

            # Multi-server overall summary
            multi_summary = None
            if self.server_manager:
                status_summary = self.server_manager.get_status_summary()
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
                embed = EmbedBuilder.error_embed(
                    f"RCON not available for {server_name}.\n\n"
                    f"Use `/factorio servers` to see available servers."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                escaped_msg = message.replace('"', '\\"')
                resp = await rcon_client.execute(f'/sc game.print("{escaped_msg}")')
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
            rcon_client = self.get_rcon_for_user(interaction.user.id)
            if rcon_client is None or not rcon_client.is_connected:
                server_name = self.get_server_display_name(interaction.user.id)
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
        self.tree.add_command(factorio_group)
        logger.info(
            "slash_commands_registered",
            root=factorio_group.name,
            command_count=len(factorio_group.commands),
            phase="6.0-multi-server",
        )

    # ========================================================================
    # Discord Event Handlers
    # ========================================================================

    async def on_ready(self) -> None:
        """Called when bot is ready."""
        if self.user is None:
            logger.error("discord_bot_ready_but_no_user")
            return

        logger.info(
            "discord_bot_ready",
            bot_name=self.user.name,
            bot_id=self.user.id,
            guilds=len(self.guilds),
            phase="6.0-multi-server",
        )

        # Set connected flag and signal ready
        self._connected = True
        self._ready.set()

        try:
            # Sync commands globally
            synced_global = await self.tree.sync()
            logger.info(
                "commands_synced_globally",
                count=len(synced_global),
                commands=[cmd.name for cmd in synced_global],
            )

            # Copy to guilds
            for guild in self.guilds:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                top_level = self.tree.get_commands(guild=guild)
                logger.info(
                    "commands_synced_to_guild",
                    guild_name=guild.name,
                    guild_id=guild.id,
                    command_count=len(top_level),
                )
        except Exception as e:
            logger.error("command_sync_failed", error=str(e), exc_info=True)

    async def on_disconnect(self) -> None:
        """Called when bot disconnects."""
        self._connected = False
        logger.warning("discord_bot_disconnected")

    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Called when an error occurs."""
        logger.error("discord_bot_error", event=event, exc_info=True)

    # ========================================================================
    # Connection Management (Phase 5.2 Enhanced)
    # ========================================================================

    async def connect_bot(self) -> None:
        """Connect the bot to Discord with RCON monitoring."""
        try:
            logger.info("connecting_to_discord", phase="6.0-multi-server")
            await self.login(self.token)
            self._connection_task = asyncio.create_task(self.connect())

            try:
                await asyncio.wait_for(self._ready.wait(), timeout=30.0)
                logger.info("discord_bot_connected")
                self._connected = True

                # Send connection notification
                await self._send_connection_notification()

                # PHASE 5.2: Start RCON status monitoring
                if not self.rcon_monitor_task:
                    self.rcon_monitor_task = asyncio.create_task(
                        self._monitor_rcon_status()
                    )
                    logger.info("rcon_status_monitoring_enabled")

                # Initial presence update
                await self.update_presence()
            except asyncio.TimeoutError:
                logger.error("discord_bot_connection_timeout")
                if self._connection_task is not None:
                    self._connection_task.cancel()
                    try:
                        await self._connection_task
                    except asyncio.CancelledError:
                        pass
                raise ConnectionError("Discord bot connection timed out after 30 seconds")
        except discord.errors.LoginFailure as e:
            logger.error("discord_login_failed", error=str(e))
            raise ConnectionError(f"Discord login failed: {e}")
        except Exception as e:
            logger.error("discord_bot_connection_failed", error=str(e), exc_info=True)
            raise

    async def disconnect_bot(self) -> None:
        """Disconnect the bot from Discord and stop monitoring."""
        if self._connected or self._connection_task is not None:
            logger.info("disconnecting_from_discord", phase="6.0-multi-server")

            # Set flag FIRST - allows loops to exit gracefully
            self._connected = False

            # PHASE 5.2: Stop RCON monitoring
            if self.rcon_monitor_task:
                self.rcon_monitor_task.cancel()
                try:
                    await self.rcon_monitor_task
                except asyncio.CancelledError:
                    pass
                self.rcon_monitor_task = None
                logger.info("rcon_status_monitoring_disabled")

            # Send disconnection notification
            await self._send_disconnection_notification()

            # Cancel connection task if exists
            if self._connection_task is not None:
                if not self._connection_task.done():
                    self._connection_task.cancel()
                    try:
                        await self._connection_task
                    except asyncio.CancelledError:
                        pass
                self._connection_task = None

            # Close the bot if not already closed
            if not self.is_closed():
                await self.close()
            logger.info("discord_bot_disconnected")

    # ========================================================================
    # Notification Methods
    # ========================================================================

    async def _send_connection_notification(self) -> None:
        """Send a notification to Discord when bot connects."""
        if self.event_channel_id is None:
            logger.debug("skip_connection_notification_no_channel")
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel is None or not isinstance(channel, discord.TextChannel):
                logger.warning("connection_notification_invalid_channel")
                return

            bot_name = self.user.name if self.user else "Factorio ISR Bot"
            guild_count = len(self.guilds)

            embed = EmbedBuilder.info_embed(
                title=f"🤖 {bot_name} Connected",
                message=(
                    "✅ Bot connected with Discord\n"
                    f"📡 Connected to {guild_count} server"
                    f"{'s' if guild_count != 1 else ''}\n"
                    "💬 Type `/factorio help` to see available commands"
                ),
            )
            embed.color = EmbedBuilder.COLOR_SUCCESS
            await channel.send(embed=embed)
            logger.info("connection_notification_sent", channel_id=self.event_channel_id)
        except discord.errors.Forbidden:
            logger.warning("connection_notification_forbidden")
        except Exception as e:
            logger.warning("connection_notification_failed", error=str(e))

    async def _send_disconnection_notification(self) -> None:
        """Send a notification to Discord when bot disconnects."""
        if not self._connected:
            logger.debug("skip_disconnection_notification_not_connected")
            return

        if self.event_channel_id is None:
            logger.debug("skip_disconnection_notification_no_channel")
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel is None or not isinstance(channel, discord.TextChannel):
                logger.warning("disconnection_notification_invalid_channel")
                return

            bot_name = self.user.name if self.user else "Factorio ISR Bot"
            embed = EmbedBuilder.info_embed(
                title=f"👋 {bot_name} Disconnecting",
                message=(
                    "⚠️ Bot lost connection with Discord\n"
                    "🔄 Monitoring will resume when bot reconnects"
                ),
            )
            embed.color = EmbedBuilder.COLOR_WARNING
            await channel.send(embed=embed)
            logger.info("disconnection_notification_sent", channel_id=self.event_channel_id)
            await asyncio.sleep(0.5)
        except discord.errors.Forbidden:
            logger.warning("disconnection_notification_forbidden")
        except Exception as e:
            logger.warning("disconnection_notification_failed", error=str(e))

    # ========================================================================
    # Event Sending
    # ========================================================================

    async def send_event(self, event: FactorioEvent) -> bool:
        """
        Send a Factorio event to Discord with @mention support.

        Args:
            event: Factorio event to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._connected:
            logger.warning("send_event_not_connected", event_type=event.event_type.value)
            return False

        if self.event_channel_id is None:
            logger.warning(
                "send_event_no_channel_configured",
                event_type=event.event_type.value,
            )
            return False

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel is None:
                logger.error(
                    "send_event_channel_not_found",
                    channel_id=self.event_channel_id,
                )
                return False

            if not isinstance(channel, discord.TextChannel):
                logger.error(
                    "send_event_invalid_channel_type",
                    channel_id=self.event_channel_id,
                )
                return False

            # Base formatted message
            message = FactorioEventFormatter.format_for_discord(event)

            # Mention handling – use metadata from EventParser
            mentions = event.metadata.get("mentions", [])
            if mentions:
                discord_mentions = await self._resolve_mentions(channel.guild, mentions)
                if discord_mentions:
                    # If the formatted message already contains @tokens, replace them.
                    for token, resolved in zip(mentions, discord_mentions):
                        raw_token = f"@{token}"
                        if raw_token in message:
                            message = message.replace(raw_token, resolved)
                        else:
                            # Fallback: append if not present in text
                            message = f"{message}\n{resolved}"

                    logger.info(
                        "mentions_added_to_message",
                        event_type=event.event_type.value,
                        mention_count=len(discord_mentions),
                    )

            await channel.send(message)
            logger.debug("event_sent", event_type=event.event_type.value)
            return True
        except Exception as e:
            logger.error(
                "send_event_unexpected_error",
                error=str(e),
                exc_info=True,
            )
            return False

    async def _resolve_mentions(
        self,
        guild: discord.Guild,
        mentions: List[str],
    ) -> List[str]:
        """
        Resolve Factorio @mentions to actual Discord mentions.

        - User tokens try to map to members.
        - Group tokens try to map to roles or special @everyone / @here.

        Returns:
            List of mention strings you can append to a message.
        """
        discord_mentions: List[str] = []

        # Built-in groups
        base_group_keywords: Dict[str, List[str]] = {
            "admins": ["admin", "admins", "administrator", "administrators"],
            "mods": ["mod", "mods", "moderator", "moderators"],
            "everyone": ["everyone"],
            "here": ["here"],
            "staff": ["staff"],
        }

        # Merge in custom groups from config/mentions.yml (may override built-ins)
        group_keywords: Dict[str, List[str]] = {**base_group_keywords, **self._mention_group_keywords}

        for token in mentions:
            token_lower = token.lower()
            is_group = False

            for group_key, variants in group_keywords.items():
                if token_lower in [v.lower() for v in variants]:
                    is_group = True

                    if group_key == "everyone":
                        discord_mentions.append("@everyone")
                        logger.debug(
                            "mention_resolved_to_everyone",
                            original=token,
                        )
                        break

                    if group_key == "here":
                        discord_mentions.append("@here")
                        logger.debug(
                            "mention_resolved_to_here",
                            original=token,
                        )
                        break

                    role = self._find_role_by_name(guild, variants)
                    if role:
                        discord_mentions.append(role.mention)
                        logger.debug(
                            "mention_resolved_to_role",
                            original=token,
                            role_name=role.name,
                            role_id=role.id,
                        )
                    else:
                        logger.warning(
                            "mention_role_not_found",
                            original=token,
                            searched_names=variants,
                        )
                    break

            if is_group:
                continue

            # User resolution
            member = await self._find_member_by_name(guild, token)
            if member:
                discord_mentions.append(member.mention)
                logger.debug(
                    "mention_resolved_to_user",
                    original=token,
                    user_name=member.name,
                    user_id=member.id,
                )
            else:
                logger.debug("mention_user_not_found", original=token)

        return discord_mentions

    def _find_role_by_name(
        self,
        guild: discord.Guild,
        role_names: List[str],
    ) -> Optional[discord.Role]:
        """
        Find a role by trying multiple name variants (case-insensitive).
        """
        for role in guild.roles:
            role_name_lower = role.name.lower()
            for candidate in role_names:
                if role_name_lower == candidate.lower():
                    return role
        return None

    async def _find_member_by_name(
        self,
        guild: discord.Guild,
        name: str,
    ) -> Optional[discord.Member]:
        """
        Find a guild member by username or display name (exact, then partial).
        """
        name_lower = name.lower()

        # Exact match
        for member in guild.members:
            if (
                member.name.lower() == name_lower
                or member.display_name.lower() == name_lower
            ):
                return member

        # Partial match
        for member in guild.members:
            if (
                name_lower in member.name.lower()
                or name_lower in member.display_name.lower()
            ):
                return member

        return None

    async def send_message(self, message: str) -> None:
        """
        Send a plain text message to the configured event channel.

        Used for stats and other generic text content that doesn't
        fit the FactorioEvent model.
        """
        if not self.is_connected:
            logger.warning("send_message_not_connected")
            return

        if self.event_channel_id is None:
            logger.warning("send_message_no_channel_configured")
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel is None:
                logger.error(
                    "send_message_channel_not_found",
                    channel_id=self.event_channel_id,
                )
                return

            if not isinstance(channel, discord.TextChannel):
                logger.error(
                    "send_message_invalid_channel_type",
                    channel_id=self.event_channel_id,
                )
                return

            await channel.send(message)
            logger.debug("message_sent", length=len(message))
        except discord.errors.Forbidden as e:
            logger.error("send_message_forbidden", error=str(e))
        except discord.errors.HTTPException as e:
            logger.error("send_message_http_error", error=str(e))
        except Exception as e:
            logger.error("send_message_unexpected_error", error=str(e), exc_info=True)

    # ========================================================================
    # Configuration Methods
    # ========================================================================

    def set_event_channel(self, channel_id: int) -> None:
        """Set the channel where Factorio events will be sent."""
        self.event_channel_id = channel_id
        logger.info("event_channel_set", channel_id=channel_id)

    def set_rcon_client(self, rcon_client: Any) -> None:
        """Set RCON client for server queries (legacy single-server mode)."""
        self.rcon_client = rcon_client
        logger.info("rcon_client_set_for_bot_commands")

    def set_server_manager(self, server_manager: Any) -> None:
        """Set ServerManager for multi-server mode."""
        self.server_manager = server_manager
        logger.info("server_manager_set_for_multi_server_mode")

    @property
    def is_connected(self) -> bool:
        """Check if bot is connected to Discord."""
        return self._connected


class DiscordBotFactory:
    """Factory for creating Discord bot instances."""

    @staticmethod
    def create_bot(token: str, bot_name: str = "Factorio ISR") -> DiscordBot:
        """Create a Discord bot instance."""
        return DiscordBot(token=token, bot_name=bot_name)
