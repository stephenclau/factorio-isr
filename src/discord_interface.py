"""
Unified interface for Discord communication with Phase 5.1 enhancements.

Supports both webhook (Phase 1-3) and bot (Phase 4+) modes.
Uses utils/ for general features, implements Discord-specific features here.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock, patch
import asyncio
import structlog
import pytest
import pytest_asyncio
import sys


# Import general utilities (framework-agnostic)
try:
    from .utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
except ImportError:
    from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN

# Import discord for bot mode
try:
    import discord
    DISCORD_AVAILABLE = True
except ImportError:
    discord = None  # type: ignore
    DISCORD_AVAILABLE = False

# Import for type hints only
if TYPE_CHECKING:
    from event_parser import FactorioEvent
    if DISCORD_AVAILABLE:
        from discord import Embed, Client
else:
    try:
        from .event_parser import FactorioEvent
    except ImportError:
        try:
            from event_parser import FactorioEvent  # type: ignore
        except ImportError:
            FactorioEvent = None  # type: ignore

logger = structlog.get_logger()


# ============================================================================
# PHASE 5.1: DISCORD-SPECIFIC UTILITIES
# ============================================================================

class EmbedBuilder:
    """Helper class for creating rich Discord embeds (Discord-specific)."""

    # Color scheme
    COLOR_SUCCESS = 0x00FF00  # Green
    COLOR_INFO = 0x3498DB     # Blue
    COLOR_WARNING = 0xFFA500  # Orange
    COLOR_ERROR = 0xFF0000    # Red
    COLOR_ADMIN = 0x9B59B6    # Purple
    COLOR_FACTORIO = 0xFF6B00 # Factorio orange

    @staticmethod
    def create_base_embed(
        title: str,
        description: Optional[str] = None,
        color: Optional[int] = None
    ) -> Any:  # Returns discord.Embed
        """Create a base embed with standard styling."""
        if not DISCORD_AVAILABLE or discord is None:
            raise RuntimeError("discord.py not available")

        embed = discord.Embed(
            title=title,
            description=description,
            color=color or EmbedBuilder.COLOR_INFO,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Factorio ISR")
        return embed

    @staticmethod
    def server_status_embed(
        status: str,
        players_online: int,
        rcon_enabled: bool,
        uptime: Optional[str] = None
    ) -> Any:  # Returns discord.Embed
        """Create server status embed."""
        embed = EmbedBuilder.create_base_embed(
            title="🏭 Factorio Server Status",
            color=EmbedBuilder.COLOR_SUCCESS if rcon_enabled else EmbedBuilder.COLOR_WARNING
        )

        embed.add_field(name="Status", value=f"🟢 {status}", inline=True)
        embed.add_field(name="Players Online", value=f"👥 {players_online}", inline=True)
        embed.add_field(name="RCON", value=f"🔧 {'Enabled' if rcon_enabled else 'Disabled'}", inline=True)

        if uptime:
            embed.add_field(name="Uptime", value=f"⏱️ {uptime}", inline=False)

        return embed

    @staticmethod
    def players_list_embed(players: list[str]) -> Any:  # Returns discord.Embed
        """Create players list embed."""
        if not players:
            embed = EmbedBuilder.create_base_embed(
                title="👥 Players Online",
                description="No players currently online",
                color=EmbedBuilder.COLOR_INFO
            )
        else:
            players_text = "\n".join(f"• {player}" for player in players)
            embed = EmbedBuilder.create_base_embed(
                title=f"👥 Players Online ({len(players)})",
                description=players_text,
                color=EmbedBuilder.COLOR_SUCCESS
            )
        return embed

    @staticmethod
    def admin_action_embed(
        action: str,
        player: str,
        moderator: str,
        reason: Optional[str] = None,
        response: Optional[str] = None
    ) -> Any:  # Returns discord.Embed
        """Create admin action embed."""
        embed = EmbedBuilder.create_base_embed(
            title=f"🔨 {action}",
            color=EmbedBuilder.COLOR_ADMIN
        )

        embed.add_field(name="Player", value=player, inline=True)
        embed.add_field(name="Moderator", value=moderator, inline=True)

        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)

        if response:
            response_text = response[:1000] + "..." if len(response) > 1000 else response
            embed.add_field(name="Server Response", value=f"```{response_text}```", inline=False)

        return embed

    @staticmethod
    def error_embed(error_message: str) -> Any:  # Returns discord.Embed
        """Create error embed."""
        return EmbedBuilder.create_base_embed(
            title="❌ Error",
            description=error_message,
            color=EmbedBuilder.COLOR_ERROR
        )

    @staticmethod
    def cooldown_embed(retry_after: float) -> Any:  # Returns discord.Embed
        """Create rate limit embed."""
        return EmbedBuilder.create_base_embed(
            title="⏱️ Slow Down!",
            description=f"You're using commands too quickly.\nTry again in {retry_after:.1f} seconds.",
            color=EmbedBuilder.COLOR_WARNING
        )

    @staticmethod
    def info_embed(title: str, message: str) -> Any:  # Returns discord.Embed
        """Create generic info embed."""
        return EmbedBuilder.create_base_embed(
            title=title,
            description=message,
            color=EmbedBuilder.COLOR_INFO
        )


# ============================================================================
# ABSTRACT INTERFACE (Enhanced for Phase 5.1)
# ============================================================================

class DiscordInterface(ABC):
    """Abstract interface for Discord communication."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to Discord."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from Discord."""
        pass

    @abstractmethod
    async def send_event(self, event: Any) -> bool:  # event is FactorioEvent
        """Send a Factorio event to Discord."""
        pass

    @abstractmethod
    async def send_message(self, message: str, username: Optional[str] = None) -> bool:
        """Send a plain text message to Discord."""
        pass

    async def send_embed(self, embed: Any) -> bool:  # embed is discord.Embed
        """Send a rich embed to Discord."""
        logger.warning("send_embed_not_implemented")
        return False

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the Discord connection."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to Discord."""
        pass


# ============================================================================
# WEBHOOK INTERFACE (Phase 1-3) - Unchanged
# ============================================================================

class WebhookDiscordInterface(DiscordInterface):
    """Discord interface using webhooks (Phase 1-3)."""

    def __init__(self, discord_client: Any) -> None:
        self.client = discord_client
        self._connected = False

    async def connect(self) -> None:
        await self.client.connect()
        self._connected = True
        logger.info("webhook_interface_connected")

    async def disconnect(self) -> None:
        await self.client.disconnect()
        self._connected = False
        logger.info("webhook_interface_disconnected")

    async def send_event(self, event: Any) -> bool:
        return await self.client.send_event(event)

    async def send_message(self, message: str, username: Optional[str] = None) -> bool:
        return await self.client.send_message(message, username=username)

    async def test_connection(self) -> bool:
        return await self.client.test_connection()

    @property
    def is_connected(self) -> bool:
        return self._connected


# ============================================================================
# BOT INTERFACE (Phase 4+ with Phase 5.1 Enhancements)
# ============================================================================

class BotDiscordInterface(DiscordInterface):
    """Discord interface using bot (Phase 4+) with Phase 5.1 enhancements."""

    def __init__(self, discord_bot: Any) -> None:
        self.bot = discord_bot

        # PHASE 5.1: Discord-specific features
        if DISCORD_AVAILABLE:
            self.embed_builder = EmbedBuilder()
           
        else:
            self.embed_builder = None  # type: ignore
            

        # PHASE 5.1: General utilities (from utils package)
        self.query_cooldown = QUERY_COOLDOWN
        self.admin_cooldown = ADMIN_COOLDOWN
        self.danger_cooldown = DANGER_COOLDOWN

    async def connect(self) -> None:
        await self.bot.connect_bot()

        

        logger.info(
            "bot_interface_connected",
            phase="5.1",
            features=["embeds", "cooldowns", "presence"]
        )

    async def disconnect(self) -> None:
        

        await self.bot.disconnect_bot()
        logger.info("bot_interface_disconnected")

    async def send_event(self, event: Any) -> bool:
        return await self.bot.send_event(event)

    async def send_message(self, message: str, username: Optional[str] = None) -> bool:
        if not self.bot.is_connected:
            logger.warning("send_message_not_connected")
            return False

        if self.bot.event_channel_id is None:
            logger.warning("send_message_no_channel")
            return False

        if not DISCORD_AVAILABLE or discord is None:
            logger.error("discord_module_not_available")
            return False

        try:
            channel = self.bot.get_channel(self.bot.event_channel_id)
            if channel is None:
                logger.error("send_message_channel_not_found", channel_id=self.bot.event_channel_id)
                return False

            if not isinstance(channel, discord.TextChannel):
                logger.error("send_message_invalid_channel_type", channel_id=self.bot.event_channel_id)
                return False

            await channel.send(message)
            logger.debug("message_sent", channel_id=self.bot.event_channel_id)
            return True

        except discord.errors.Forbidden:
            logger.error("send_message_forbidden", channel_id=self.bot.event_channel_id)
            return False
        except discord.errors.HTTPException as e:
            logger.error("send_message_http_error", error=str(e))
            return False
        except Exception as e:
            logger.error("send_message_unexpected_error", error=str(e), exc_info=True)
            return False

    async def send_embed(self, embed: Any) -> bool:  # embed is discord.Embed
        if not self.bot.is_connected:
            logger.warning("send_embed_not_connected")
            return False

        if self.bot.event_channel_id is None:
            logger.warning("send_embed_no_channel")
            return False

        if not DISCORD_AVAILABLE or discord is None:
            logger.error("discord_module_not_available")
            return False

        try:
            channel = self.bot.get_channel(self.bot.event_channel_id)
            if channel is None:
                logger.error("send_embed_channel_not_found", channel_id=self.bot.event_channel_id)
                return False

            if not isinstance(channel, discord.TextChannel):
                logger.error("send_embed_invalid_channel_type", channel_id=self.bot.event_channel_id)
                return False

            await channel.send(embed=embed)
            logger.debug("embed_sent", channel_id=self.bot.event_channel_id)
            return True

        except discord.errors.Forbidden:
            logger.error("send_embed_forbidden", channel_id=self.bot.event_channel_id)
            return False
        except discord.errors.HTTPException as e:
            logger.error("send_embed_http_error", error=str(e))
            return False
        except Exception as e:
            logger.error("send_embed_unexpected_error", error=str(e), exc_info=True)
            return False

    async def test_connection(self) -> bool:
        return self.bot.is_connected

    @property
    def is_connected(self) -> bool:
        return self.bot.is_connected

"""
RECOMMENDED SOLUTION: Refactor create_interface() for Testability

The 49% missing coverage is in unreachable error-handling paths.
This refactoring extracts import logic into testable helper methods.
"""

# ============================================================================
# REFACTORED discord_interface.py (Factory section)
# ============================================================================

class DiscordInterfaceFactory:
    """Factory for creating Discord interface instances."""

    @staticmethod
    def _import_discord_bot() -> Any:
        """
        Import DiscordBot with fallback to importlib.util.

        This method is extracted for testability.

        Returns:
            DiscordBot class

        Raises:
            ImportError: If DiscordBot cannot be imported
        """
        try:
            # Try normal import first
            from discord_bot import DiscordBot
            return DiscordBot
        except ImportError:
            # Fallback to importlib
            return DiscordInterfaceFactory._import_with_importlib('discord_bot', 'DiscordBot')

    @staticmethod
    def _import_discord_client() -> Any:
        """
        Import DiscordClient with fallback to importlib.util.

        This method is extracted for testability.

        Returns:
            DiscordClient class

        Raises:
            ImportError: If DiscordClient cannot be imported
        """
        try:
            # Try normal import first
            from discord_client import DiscordClient
            return DiscordClient
        except ImportError:
            # Fallback to importlib
            return DiscordInterfaceFactory._import_with_importlib('discord_client', 'DiscordClient')

    @staticmethod
    def _import_with_importlib(module_name: str, class_name: str) -> Any:
        """
        Import a class using importlib.util as fallback.

        Args:
            module_name: Name of the module (e.g., 'discord_bot')
            class_name: Name of the class (e.g., 'DiscordBot')

        Returns:
            The imported class

        Raises:
            ImportError: If import fails
        """
        import importlib.util
        import sys
        import os

        # Get the current module's path
        current_module = sys.modules[__name__]
        current_path = getattr(current_module, '__file__', None)

        if not current_path:
            raise ImportError(f"Could not determine module path for {module_name}")

        # Get the directory containing discord_interface.py
        src_dir = os.path.dirname(os.path.abspath(current_path))

        # Add src directory to sys.path if not already there
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
            logger.debug("added_to_sys_path", path=src_dir)

        # Build path to the module file
        module_path = os.path.join(src_dir, f'{module_name}.py')

        # Create spec from file location
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load {module_name} module")

        # Load the module
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Get the class from the module
        return getattr(module, class_name)

    @staticmethod
    def create_interface(config: Any) -> DiscordInterface:
        """
        Create appropriate Discord interface based on configuration.

        Args:
            config: Application configuration

        Returns:
            DiscordInterface instance (webhook or bot mode)

        Raises:
            ValueError: If neither webhook nor bot is configured
        """
        if config.discord_bot_token:
            logger.info("creating_bot_interface", phase="5.1")

            try:
                # Import using extracted method (now testable!)
                DiscordBot = DiscordInterfaceFactory._import_discord_bot()
            except Exception as e:
                logger.error("failed_to_import_discord_bot", error=str(e), exc_info=True)
                raise ImportError(
                    f"Could not import DiscordBot. Make sure discord_bot.py is in the same directory. Error: {e}"
                )

            bot = DiscordBot(
                token=config.discord_bot_token,
                bot_name=config.bot_name,
                breakdown_mode=config.rcon_breakdown_mode,
                breakdown_interval=config.rcon_breakdown_interval,
            )

            if config.discord_event_channel_id:
                bot.set_event_channel(config.discord_event_channel_id)
            else:
                logger.warning(
                    "bot_mode_no_channel",
                    message="DISCORD_EVENT_CHANNEL_ID not set. Events won't be sent.",
                )

            return BotDiscordInterface(bot)

        elif config.discord_webhook_url:
            logger.info("creating_webhook_interface")

            try:
                # Import using extracted method (now testable!)
                DiscordClient = DiscordInterfaceFactory._import_discord_client()
            except Exception as e:
                logger.error("failed_to_import_discord_client", error=str(e), exc_info=True)
                raise ImportError(
                    f"Could not import DiscordClient. Error: {e}"
                )

            client = DiscordClient(
                webhook_url=config.discord_webhook_url,
                bot_name=config.bot_name,
                bot_avatar_url=getattr(config, 'bot_avatar_url', None),
            )

            return WebhookDiscordInterface(client)

        else:
            raise ValueError(
                "Either DISCORD_BOT_TOKEN or DISCORD_WEBHOOK_URL must be configured"
            )
