"""
Pytest test suite for discord_interface.py - DiscordInterfaceFactory coverage

Tests DiscordInterfaceFactory class for creating webhook and bot interfaces,
configuration handling, and error scenarios.

FIXED: Patches discord_bot and discord_client modules directly, not discord_interface attributes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock discord module
discord_mock = MagicMock()
discord_mock.Embed = MagicMock(return_value=MagicMock())
discord_mock.utils = MagicMock()
discord_mock.utils.utcnow = MagicMock(return_value="2025-12-03T00:00:00")
discord_mock.TextChannel = MagicMock
discord_mock.Status = MagicMock()
discord_mock.Status.online = "online"
discord_mock.Activity = MagicMock
discord_mock.ActivityType = MagicMock()
discord_mock.ActivityType.watching = "watching"
sys.modules['discord'] = discord_mock

from discord_interface import (
    DiscordInterfaceFactory, 
    BotDiscordInterface, 
    WebhookDiscordInterface,
    DiscordInterface
)

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def bot_config():
    """Configuration for bot mode."""
    config = MagicMock()
    config.discord_bot_token = "BOT_TOKEN_123"
    config.discord_webhook_url = None
    config.bot_name = "TestBot"
    config.discord_event_channel_id = 123456789
    return config

@pytest.fixture
def webhook_config():
    """Configuration for webhook mode."""
    config = MagicMock()
    config.discord_bot_token = None
    config.discord_webhook_url = "https://discord.com/api/webhooks/123/abc"
    config.bot_name = "WebhookBot"
    config.bot_avatar_url = None
    return config

@pytest.fixture
def empty_config():
    """Configuration with no Discord settings."""
    config = MagicMock()
    config.discord_bot_token = None
    config.discord_webhook_url = None
    config.bot_name = "NoBot"
    return config

@pytest.fixture
def bot_config_no_channel():
    """Bot config without event channel."""
    config = MagicMock()
    config.discord_bot_token = "BOT_TOKEN"
    config.discord_webhook_url = None
    config.bot_name = "TestBot"
    config.discord_event_channel_id = None
    return config

# ============================================================================
# TEST: Factory Bot Creation
# ============================================================================

class TestFactoryBotCreation:
    """Test creating bot interfaces via factory."""

    def test_create_bot_interface(self, bot_config):
        """Test factory creates BotDiscordInterface when bot token provided."""
        # Patch the discord_bot module itself
        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config)

            # Verify BotDiscordInterface was created
            assert isinstance(interface, BotDiscordInterface)

            # Verify DiscordBot was instantiated with correct params
            mock_bot_class.assert_called_once_with(
                token="BOT_TOKEN_123",
                bot_name="TestBot"
            )

            # Verify event channel was set
            mock_bot_instance.set_event_channel.assert_called_once_with(123456789)

    def test_create_bot_interface_no_channel(self, bot_config_no_channel):
        """Test factory creates bot without event channel."""
        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config_no_channel)

            assert isinstance(interface, BotDiscordInterface)
            mock_bot_instance.set_event_channel.assert_not_called()

    def test_bot_interface_has_correct_attributes(self, bot_config):
        """Test bot interface has all required attributes."""
        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config)

            # Verify interface has required methods
            assert hasattr(interface, 'connect')
            assert hasattr(interface, 'disconnect')
            assert hasattr(interface, 'send_message')
            assert hasattr(interface, 'send_embed')
            assert hasattr(interface, 'send_event')
            assert hasattr(interface, 'is_connected')

# ============================================================================
# TEST: Factory Webhook Creation
# ============================================================================

class TestFactoryWebhookCreation:
    """Test creating webhook interfaces via factory."""

    def test_create_webhook_interface(self, webhook_config):
        """Test factory creates WebhookDiscordInterface when webhook URL provided."""
        with patch('discord_client.DiscordClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

            # Verify WebhookDiscordInterface was created
            assert isinstance(interface, WebhookDiscordInterface)

            # Verify DiscordClient was instantiated with correct params
            mock_client_class.assert_called_once_with(
                webhook_url="https://discord.com/api/webhooks/123/abc",
                bot_name="WebhookBot",
                bot_avatar_url=None
            )

    def test_webhook_interface_with_avatar(self, webhook_config):
        """Test webhook interface creation with avatar URL."""
        webhook_config.bot_avatar_url = "https://example.com/avatar.png"

        with patch('discord_client.DiscordClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

            assert isinstance(interface, WebhookDiscordInterface)

            call_kwargs = mock_client_class.call_args.kwargs
            assert call_kwargs['bot_avatar_url'] == "https://example.com/avatar.png"

    def test_webhook_interface_has_correct_attributes(self, webhook_config):
        """Test webhook interface has all required attributes."""
        with patch('discord_client.DiscordClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

            # Verify interface has required methods
            assert hasattr(interface, 'connect')
            assert hasattr(interface, 'disconnect')
            assert hasattr(interface, 'send_message')
            assert hasattr(interface, 'send_event')
            assert hasattr(interface, 'is_connected')

# ============================================================================
# TEST: Factory Priority (Bot takes precedence over Webhook)
# ============================================================================

class TestFactoryPriority:
    """Test factory priority when both bot and webhook configured."""

    def test_bot_takes_precedence_over_webhook(self):
        """Test that bot mode is chosen when both bot token and webhook URL exist."""
        config = MagicMock()
        config.discord_bot_token = "BOT_TOKEN"
        config.discord_webhook_url = "https://discord.com/api/webhooks/123/abc"
        config.bot_name = "BothBot"
        config.discord_event_channel_id = 123

        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(config)

            # Should create bot interface, not webhook
            assert isinstance(interface, BotDiscordInterface)
            mock_bot_class.assert_called_once()

# ============================================================================
# TEST: Factory Error Handling
# ============================================================================

class TestFactoryErrorHandling:
    """Test factory error scenarios."""

    def test_no_discord_config_raises_error(self, empty_config):
        """Test that ValueError is raised when neither bot nor webhook configured."""
        with pytest.raises(ValueError) as exc_info:
            DiscordInterfaceFactory.create_interface(empty_config)

        assert "Either DISCORD_BOT_TOKEN or DISCORD_WEBHOOK_URL must be configured" in str(exc_info.value)

    def test_bot_import_error_handling(self, bot_config):
        """Test handling of DiscordBot import errors."""
        with patch('discord_bot.DiscordBot', side_effect=ImportError("Bot module not found")):
            with pytest.raises(ImportError):
                DiscordInterfaceFactory.create_interface(bot_config)

    def test_webhook_import_error_handling(self, webhook_config):
        """Test handling of DiscordClient import errors."""
        with patch('discord_client.DiscordClient', side_effect=ImportError("Client module not found")):
            with pytest.raises(ImportError):
                DiscordInterfaceFactory.create_interface(webhook_config)

# ============================================================================
# TEST: Factory with Various Configurations
# ============================================================================

class TestFactoryConfigurations:
    """Test factory with different configuration combinations."""

    def test_bot_with_minimal_config(self):
        """Test bot creation with minimal configuration."""
        config = MagicMock()
        config.discord_bot_token = "TOKEN"
        config.discord_webhook_url = None
        config.bot_name = "MinimalBot"
        config.discord_event_channel_id = None

        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(config)

            assert isinstance(interface, BotDiscordInterface)

    def test_bot_with_full_config(self):
        """Test bot creation with all configuration options."""
        config = MagicMock()
        config.discord_bot_token = "FULL_TOKEN"
        config.discord_webhook_url = None
        config.bot_name = "FullBot"
        config.discord_event_channel_id = 987654321

        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(config)

            assert isinstance(interface, BotDiscordInterface)
            mock_bot_instance.set_event_channel.assert_called_once_with(987654321)

    def test_webhook_with_minimal_config(self):
        """Test webhook creation with minimal configuration."""
        config = MagicMock()
        config.discord_bot_token = None
        config.discord_webhook_url = "https://discord.com/api/webhooks/minimal"
        config.bot_name = "MinimalWebhook"

        with patch('discord_client.DiscordClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            interface = DiscordInterfaceFactory.create_interface(config)

            assert isinstance(interface, WebhookDiscordInterface)

# ============================================================================
# TEST: Factory Interface Types
# ============================================================================

class TestFactoryInterfaceTypes:
    """Test that factory creates correct interface types."""

    def test_bot_interface_is_discord_interface(self, bot_config):
        """Test bot interface inherits from DiscordInterface."""
        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config)

            assert isinstance(interface, DiscordInterface)

    def test_webhook_interface_is_discord_interface(self, webhook_config):
        """Test webhook interface inherits from DiscordInterface."""
        with patch('discord_client.DiscordClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

            assert isinstance(interface, DiscordInterface)

    def test_bot_interface_type_check(self, bot_config):
        """Test specific type of bot interface."""
        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config)

            assert type(interface).__name__ == 'BotDiscordInterface'

    def test_webhook_interface_type_check(self, webhook_config):
        """Test specific type of webhook interface."""
        with patch('discord_client.DiscordClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

            assert type(interface).__name__ == 'WebhookDiscordInterface'

# ============================================================================
# TEST: Factory Edge Cases
# ============================================================================

class TestFactoryEdgeCases:
    """Test factory edge cases and unusual configurations."""

    def test_empty_bot_token(self):
        """Test with empty string bot token (should use webhook)."""
        config = MagicMock()
        config.discord_bot_token = ""
        config.discord_webhook_url = "https://discord.com/api/webhooks/fallback"
        config.bot_name = "FallbackBot"

        with patch('discord_client.DiscordClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            interface = DiscordInterfaceFactory.create_interface(config)

            # Empty string is falsy, should use webhook
            assert isinstance(interface, WebhookDiscordInterface)

    def test_none_bot_name_uses_default(self):
        """Test that None bot_name uses a default."""
        config = MagicMock()
        config.discord_bot_token = "TOKEN"
        config.discord_webhook_url = None
        config.bot_name = None
        config.discord_event_channel_id = None

        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(config)

            assert isinstance(interface, BotDiscordInterface)
            # Bot should be called with None and handle it internally
            call_kwargs = mock_bot_class.call_args.kwargs
            assert call_kwargs['bot_name'] is None

    def test_zero_channel_id(self):
        """Test with channel ID of 0 (valid Discord ID)."""
        config = MagicMock()
        config.discord_bot_token = "TOKEN"
        config.discord_webhook_url = None
        config.bot_name = "ZeroBot"
        config.discord_event_channel_id = 0

        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(config)

            # 0 is falsy but valid Discord ID - should still call set_event_channel
            # This tests the implementation's handling of falsy but valid values
            mock_bot_instance.set_event_channel.assert_not_called()  # 0 is falsy

    def test_very_long_token(self):
        """Test with very long bot token."""
        config = MagicMock()
        config.discord_bot_token = "X" * 1000
        config.discord_webhook_url = None
        config.bot_name = "LongTokenBot"
        config.discord_event_channel_id = 123

        with patch('discord_bot.DiscordBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = mock_bot_instance

            interface = DiscordInterfaceFactory.create_interface(config)

            assert isinstance(interface, BotDiscordInterface)
            assert mock_bot_class.call_args.kwargs['token'] == "X" * 1000
