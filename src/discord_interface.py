"""
Unified interface for Discord communication.
Supports both webhook (Phase 1-3) and bot (Phase 4+) modes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
import structlog

# Import discord for bot mode
try:
    import discord
except ImportError:
    discord = None  # type: ignore

# Import for type hints
try:
    from .event_parser import FactorioEvent
except ImportError:
    from event_parser import FactorioEvent  # type: ignore

logger = structlog.get_logger()


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
    async def send_event(self, event: FactorioEvent) -> bool:
        """
        Send a Factorio event to Discord.
        
        Args:
            event: Factorio event to send
        
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_message(self, message: str, username: Optional[str] = None) -> bool:
        """
        Send a plain text message to Discord.
        
        Args:
            message: Message text to send
            username: Optional username override
        
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test the Discord connection.
        
        Returns:
            True if connection is valid, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to Discord."""
        pass


class WebhookDiscordInterface(DiscordInterface):
    """Discord interface using webhooks (Phase 1-3)."""
    
    def __init__(self, discord_client) -> None:
        """
        Initialize webhook interface.
        
        Args:
            discord_client: DiscordClient instance
        """
        self.client = discord_client
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to Discord webhook."""
        await self.client.connect()
        self._connected = True
        logger.info("webhook_interface_connected")
    
    async def disconnect(self) -> None:
        """Disconnect from Discord webhook."""
        await self.client.disconnect()
        self._connected = False
        logger.info("webhook_interface_disconnected")
    
    async def send_event(self, event: FactorioEvent) -> bool:
        """Send event via webhook."""
        return await self.client.send_event(event)
    
    async def send_message(self, message: str, username: Optional[str] = None) -> bool:
        """Send plain text message via webhook."""
        return await self.client.send_message(message, username=username)
    
    async def test_connection(self) -> bool:
        """Test webhook connection."""
        return await self.client.test_connection()
    
    @property
    def is_connected(self) -> bool:
        """Check if webhook is connected."""
        return self._connected


class BotDiscordInterface(DiscordInterface):
    """Discord interface using bot (Phase 4+)."""
    
    def __init__(self, discord_bot) -> None:
        """
        Initialize bot interface.
        
        Args:
            discord_bot: DiscordBot instance
        """
        self.bot = discord_bot
    
    async def connect(self) -> None:
        """Connect Discord bot."""
        await self.bot.connect_bot()
        logger.info("bot_interface_connected")
    
    async def disconnect(self) -> None:
        """Disconnect Discord bot."""
        await self.bot.disconnect_bot()
        logger.info("bot_interface_disconnected")
    
    async def send_event(self, event: FactorioEvent) -> bool:
        """Send event via bot."""
        return await self.bot.send_event(event)
    
    async def send_message(self, message: str, username: Optional[str] = None) -> bool:
        """
        Send plain text message via bot.
        
        Args:
            message: Message text to send
            username: Optional username override (ignored for bots)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.bot.is_connected:
            logger.warning("send_message_not_connected")
            return False
        
        if self.bot.event_channel_id is None:
            logger.warning("send_message_no_channel")
            return False
        
        # Type guard - ensure discord module is available
        if discord is None:
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
            
            # Send the message
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

    
    async def test_connection(self) -> bool:
        """Test bot connection."""
        return self.bot.is_connected
    
    @property
    def is_connected(self) -> bool:
        """Check if bot is connected."""
        return self.bot.is_connected


class DiscordInterfaceFactory:
    """Factory for creating Discord interface instances."""
    
    @staticmethod
    def create_interface(config) -> DiscordInterface:
        """
        Create appropriate Discord interface based on configuration.
        
        Args:
            config: Application configuration
        
        Returns:
            DiscordInterface instance (webhook or bot mode)
        
        Raises:
            ValueError: If neither webhook nor bot is configured
        """
        # Prefer bot mode if both are configured
        if config.discord_bot_token:
            logger.info("creating_bot_interface")
            
            # Try package-style import first, then flat
            try:
                from .discord_bot import DiscordBot  # type: ignore
            except ImportError:
                from discord_bot import DiscordBot  # type: ignore
            
            bot = DiscordBot(
                token=config.discord_bot_token,
                bot_name=config.bot_name,
            )
            
            # Set event channel if configured
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
            
            # Try package-style import first, then flat
            try:
                from .discord_client import DiscordClient  # type: ignore
            except ImportError:
                from discord_client import DiscordClient  # type: ignore
            
            client = DiscordClient(
                webhook_url=config.discord_webhook_url,
                bot_name=config.bot_name,
                bot_avatar_url=config.bot_avatar_url,
            )
            
            return WebhookDiscordInterface(client)
        
        else:
            raise ValueError(
                "Either DISCORD_BOT_TOKEN or DISCORD_WEBHOOK_URL must be configured"
            )
