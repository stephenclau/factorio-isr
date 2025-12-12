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

"""Discord bot client - REFACTORED for modularity.

Phase 6.0: Multi-Server Support with Modular Architecture

Refactored to delegate concerns to specialized modules:
- bot.user_context: Per-user server context management
- bot.helpers: Utilities (presence, uptime formatting)
- bot.event_handler: Event sending with mention resolution
- bot.rcon_health_monitor: RCON status monitoring and notifications
- bot.commands.factorio: All /factorio slash commands

This refactored version preserves the public API (DiscordBot class)
while dramatically simplifying the implementation.
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional, Any, Dict

import discord
from discord import app_commands
import structlog
import yaml  # type: ignore[import]

# Phase 5.1: Rate limiting and embeds
try:
    from .event_parser import FactorioEvent
    from .utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
    from .discord_interface import EmbedBuilder
except ImportError:
    from event_parser import FactorioEvent  # type: ignore
    from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN  # type: ignore
    from discord_interface import EmbedBuilder  # type: ignore

# Phase 6: Multi-server support
try:
    from .config import ServerConfig
    from .server_manager import ServerManager
except ImportError:
    try:
        from config import ServerConfig  # type: ignore
        from server_manager import ServerManager  # type: ignore
    except ImportError:
        ServerManager = None  # type: ignore
        ServerConfig = None  # type: ignore

# NEW: Import modular components
try:
    from bot import UserContextManager, RconHealthMonitor, EventHandler, PresenceManager
    from bot.commands import register_factorio_commands
except ImportError:
    try:
        from src.bot import UserContextManager, RconHealthMonitor, EventHandler, PresenceManager  # type: ignore
        from src.bot.commands import register_factorio_commands  # type: ignore
    except ImportError:
        raise ImportError("Could not import bot modules from bot/ or src/bot/")

logger = structlog.get_logger()


class DiscordBot(discord.Client):
    """Discord bot client with slash command support, RCON monitoring, and multi-server support.

    PUBLIC API: This class maintains backward compatibility with the original implementation.
    Internal refactoring delegates to specialized modules.
    """

    def __init__(
        self,
        token: str,
        bot_name: str = "Factorio ISR",
        *,
        breakdown_mode: str = "transition",
        breakdown_interval: int = 300,
        intents: Optional[discord.Intents] = None,
    ):
        """
        Initialize Discord bot.

        Args:
            token: Discord bot token
            bot_name: Display name for the bot
            breakdown_mode: RCON status alert mode ('transition' or 'interval')
            breakdown_interval: Interval in seconds between RCON status alerts
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

        # Phase 6: Multi-server support
        self.server_manager: Optional[Any] = None  # ServerManager instance

        # Phase 5.2: RCON status monitoring
        self.rcon_last_connected: Optional[datetime] = None

        # RCON status alert scheduling (initialized from parameters)
        self.rcon_status_alert_mode = breakdown_mode.lower()
        self.rcon_status_alert_interval = breakdown_interval

        # ====================================================================
        # NEW: Modular Components (replacing inline code)
        # ====================================================================

        # User context management
        self.user_context = UserContextManager(bot=self)

        # Presence management
        self.presence_manager = PresenceManager(bot=self)

        # Event handling
        self.event_handler = EventHandler(bot=self)

        # RCON health monitoring
        self.rcon_monitor = RconHealthMonitor(bot=self)

        logger.info(
            "discord_bot_initialized",
            bot_name=bot_name,
            phase="6.0-multi-server-refactored",
            status_alert_mode=self.rcon_status_alert_mode,
            status_alert_interval=self.rcon_status_alert_interval,
        )

    def _apply_server_status_alert_config(self) -> None:
        """
        Apply per-server status alert configuration to the bot.

        Reads RCON status alert settings from the first configured server
        in ServerManager and applies them globally. This is called after
        set_server_manager() to load per-server settings from ServerConfig.

        Per-server defaults are applied from config.py:
        - rcon_status_alert_mode: "transition" or "interval" (default: "transition")
        - rcon_status_alert_interval: int seconds (default: 300s / 5 minutes)
        """
        if not self.server_manager:
            logger.warning(
                "_apply_server_status_alert_config called without server_manager"
            )
            return

        servers = self.server_manager.list_servers()
        if not servers:
            logger.warning(
                "_apply_server_status_alert_config called with no servers"
            )
            return

        # Get first server's config
        first_server = next(iter(servers.values()))

        # Apply its status alert settings
        self.rcon_status_alert_mode = first_server.rcon_status_alert_mode.lower()
        self.rcon_status_alert_interval = first_server.rcon_status_alert_interval

        logger.info(
            "server_status_alert_config_applied",
            server_name=first_server.name,
            server_tag=first_server.tag,
            mode=self.rcon_status_alert_mode,
            interval=self.rcon_status_alert_interval,
        )

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
        # Register all /factorio commands
        register_factorio_commands(self)
        logger.info("commands_registered") 
        logger.info("discord_bot_setup_complete")

    # ========================================================================
    # Discord Event Handlers
    # ========================================================================

    async def on_ready(self) -> None:
        """Called when bot is ready (fires on initial connect AND reconnects)."""
        if self.user is None:
            logger.error("discord_bot_ready_but_no_user")
            return

        logger.info(
            "discord_bot_ready",
            bot_name=self.user.name,
            bot_id=self.user.id,
            guilds=len(self.guilds),
            phase="7.0-discrete-enclosures",
        )

        # Set connected flag and signal ready
        self._connected = True
        self._ready.set()

        # ✅ RESTART presence updater if not running (handles reconnects)
        await self.presence_manager.start()

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
            logger.info("connecting_to_discord", phase="7.0-discrete-enclosures")
            await self.login(self.token)
            self._connection_task = asyncio.create_task(self.connect())

            try:
                await asyncio.wait_for(self._ready.wait(), timeout=30.0)
                logger.info("discord_bot_connected")
                self._connected = True

                # Send connection notification
                await self._send_connection_notification()

                # PHASE 5.2: Start RCON health monitoring
                await self.rcon_monitor.start()

                # ✅ Start presence updater
                await self.presence_manager.start()

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
            logger.info("disconnecting_from_discord", phase="7.0-discrete-enclosures")

            # Set flag FIRST - allows loops to exit gracefully
            self._connected = False

            # ✅ Stop presence updater
            await self.presence_manager.stop()

            # Send disconnection notification
            await self._send_disconnection_notification()

            # PHASE 5.2: Stop RCON health monitoring
            await self.rcon_monitor.stop()

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
        """Send connection notification to all configured server channels."""
        if not self.server_manager:
            logger.debug("skip_connection_notification_no_server_manager")
            return

        bot_name = self.user.name if self.user else "Factorio ISR Bot"
        guild_count = len(self.guilds)

        embed = EmbedBuilder.info_embed(
            title=f"🤖 {bot_name} Connected",
            message=(
                "✅ Bot connected with Discord\n"
                f"📱 Connected to {guild_count} server{'s' if guild_count != 1 else ''}\n"
                "💬 Type `/factorio help` to see available commands"
            ),
        )
        embed.color = EmbedBuilder.COLOR_SUCCESS

        # Send to each server's channel
        for tag, config in self.server_manager.list_servers().items():
            channel_id = config.event_channel_id
            if channel_id:
                try:
                    from bot.helpers import send_to_channel  # type: ignore
                except ImportError:
                    from src.bot.helpers import send_to_channel  # type: ignore
                await send_to_channel(self, channel_id, embed)
                logger.info(
                    "connection_notification_sent",
                    server_tag=tag,
                    channel_id=channel_id,
                )

    async def _send_disconnection_notification(self) -> None:
        """Send disconnection notification to all configured server channels."""
        if not self._connected or not self.server_manager:
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

        # Send to each server's channel
        for tag, config in self.server_manager.list_servers().items():
            channel_id = config.event_channel_id
            if channel_id:
                try:
                    from bot.helpers import send_to_channel  # type: ignore
                except ImportError:
                    from src.bot.helpers import send_to_channel  # type: ignore
                await send_to_channel(self, channel_id, embed)
                logger.info(
                    "disconnection_notification_sent",
                    server_tag=tag,
                    channel_id=channel_id,
                )

        # Small delay to allow messages to send before disconnect
        await asyncio.sleep(0.5)

    # ========================================================================
    # Event Sending (Delegates to EventHandler)
    # ========================================================================

    async def send_event(self, event: FactorioEvent) -> bool:
        """Send a Factorio event to Discord.

        Args:
            event: Factorio event to send

        Returns:
            True if sent successfully, False otherwise
        """
        return await self.event_handler.send_event(event)

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
