"""
Pytest test suite for discord_interface.py - BotDiscordInterface coverage

Tests BotDiscordInterface class for bot mode operations,
send_message, send_embed, lifecycle management.

UPDATED: Added 8 missing error path tests for complete coverage
- DISCORD_AVAILABLE=False handling
- All exception handlers (Forbidden, HTTPException, General)
- Wrong channel type validation
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock discord module BEFORE importing discord_interface
discord_mock = MagicMock()
discord_mock.Embed = MagicMock(return_value=MagicMock())
discord_mock.utils = MagicMock()
discord_mock.utils.utcnow = MagicMock(return_value="2025-12-03T00:00:00")
discord_mock.TextChannel = type('TextChannel', (), {})  # Create actual type for isinstance checks
discord_mock.Status = MagicMock()
discord_mock.Status.online = "online"
discord_mock.Activity = MagicMock(return_value=MagicMock())
discord_mock.ActivityType = MagicMock()
discord_mock.ActivityType.watching = "watching"
discord_mock.errors = MagicMock()
discord_mock.errors.Forbidden = type('Forbidden', (Exception,), {})
discord_mock.errors.HTTPException = type('HTTPException', (Exception,), {})

sys.modules['discord'] = discord_mock

# Now import and patch discord_interface module
import discord_interface
discord_interface.DISCORD_AVAILABLE = True
discord_interface.discord = discord_mock

from discord_interface import BotDiscordInterface

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_discord_bot():
    """Mock DiscordBot for testing BotDiscordInterface."""
    bot = MagicMock()
    bot.is_connected = True  # Property, not method
    bot.event_channel_id = 123456789
    bot.connect_bot = AsyncMock()
    bot.disconnect_bot = AsyncMock()
    bot.send_event = AsyncMock(return_value=True)

    # Mock get_channel to return a proper TextChannel
    mock_channel = MagicMock(spec=discord_mock.TextChannel)
    mock_channel.__class__ = discord_mock.TextChannel  # For isinstance check
    mock_channel.send = AsyncMock()
    bot.get_channel = MagicMock(return_value=mock_channel)

    return bot


@pytest.fixture
def bot_interface(mock_discord_bot):
    """Create BotDiscordInterface instance."""
    return BotDiscordInterface(mock_discord_bot)


# ============================================================================
# TEST: Initialization
# ============================================================================

class TestBotInterfaceInit:
    """Test BotDiscordInterface initialization."""

    def test_init_with_bot(self, mock_discord_bot):
        """Test initialization with Discord bot."""
        interface = BotDiscordInterface(mock_discord_bot)
        assert interface.bot is mock_discord_bot
        assert hasattr(interface, 'embed_builder')
        assert hasattr(interface, 'presence_updater')

    def test_init_creates_embed_builder(self, bot_interface):
        """Test that EmbedBuilder is created."""
        assert bot_interface.embed_builder is not None

    def test_init_creates_presence_updater(self, bot_interface):
        """Test that PresenceUpdater is created."""
        assert bot_interface.presence_updater is not None

    def test_init_when_discord_not_available(self, mock_discord_bot):
        """Test initialization when discord.py not available."""
        with patch('discord_interface.DISCORD_AVAILABLE', False):
            interface = BotDiscordInterface(mock_discord_bot)
            assert interface.bot is mock_discord_bot
            assert interface.embed_builder is None
            assert interface.presence_updater is None


# ============================================================================
# TEST: Connection
# ============================================================================

class TestBotInterfaceConnection:
    """Test connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_calls_bot_connect(self, bot_interface, mock_discord_bot):
        """Test that connect() calls bot.connect_bot()."""
        await bot_interface.connect()
        mock_discord_bot.connect_bot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_starts_presence_updater(self, bot_interface):
        """Test that connect() starts presence updater."""
        with patch.object(bot_interface.presence_updater, 'start', new_callable=AsyncMock) as mock_start:
            await bot_interface.connect()
            mock_start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_calls_bot_disconnect(self, bot_interface, mock_discord_bot):
        """Test that disconnect() calls bot.disconnect_bot()."""
        await bot_interface.disconnect()
        mock_discord_bot.disconnect_bot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_stops_presence_updater(self, bot_interface):
        """Test that disconnect() stops presence updater."""
        with patch.object(bot_interface.presence_updater, 'stop', new_callable=AsyncMock) as mock_stop:
            await bot_interface.disconnect()
            mock_stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_connected_reflects_bot_state(self, bot_interface, mock_discord_bot):
        """Test that is_connected property reflects bot state."""
        mock_discord_bot.is_connected = True
        assert bot_interface.is_connected is True

        mock_discord_bot.is_connected = False
        assert bot_interface.is_connected is False


# ============================================================================
# TEST: Send Event
# ============================================================================

class TestBotInterfaceSendEvent:
    """Test send_event method."""

    @pytest.mark.asyncio
    async def test_send_event_delegates_to_bot(self, bot_interface, mock_discord_bot):
        """Test that send_event delegates to bot."""
        mock_event = MagicMock()
        mock_discord_bot.send_event.return_value = True

        result = await bot_interface.send_event(mock_event)

        assert result is True
        mock_discord_bot.send_event.assert_awaited_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_send_event_returns_false_on_failure(self, bot_interface, mock_discord_bot):
        """Test send_event returns False when bot fails."""
        mock_event = MagicMock()
        mock_discord_bot.send_event.return_value = False

        result = await bot_interface.send_event(mock_event)

        assert result is False


# ============================================================================
# TEST: Send Message
# ============================================================================

class TestBotInterfaceSendMessage:
    """Test send_message method."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, bot_interface, mock_discord_bot):
        """Test successful message send."""
        # Ensure bot is connected and has channel
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        # Setup mock channel that passes isinstance check
        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_message("Test message")

        assert result is True
        mock_channel.send.assert_awaited_once_with("Test message")

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, bot_interface, mock_discord_bot):
        """Test send_message when bot not connected."""
        mock_discord_bot.is_connected = False

        result = await bot_interface.send_message("Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_no_channel(self, bot_interface, mock_discord_bot):
        """Test send_message when no event channel set."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = None

        result = await bot_interface.send_message("Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_discord_not_available(self, bot_interface, mock_discord_bot):
        """Test send_message when DISCORD_AVAILABLE is False."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        with patch('discord_interface.DISCORD_AVAILABLE', False):
            result = await bot_interface.send_message("Test")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_channel_not_found(self, bot_interface, mock_discord_bot):
        """Test send_message when channel not found."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 999999
        mock_discord_bot.get_channel = MagicMock(return_value=None)

        result = await bot_interface.send_message("Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_wrong_channel_type(self, bot_interface, mock_discord_bot):
        """Test when get_channel returns wrong channel type."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        # Return a non-TextChannel (different __class__)
        mock_channel = MagicMock()
        mock_channel.__class__ = type('VoiceChannel', (), {})  # Wrong type
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_message("Test")

        # Should fail type check
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_forbidden_error(self, bot_interface, mock_discord_bot):
        """Test send_message handles Forbidden error."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789
        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock(side_effect=discord_mock.errors.Forbidden(MagicMock(), "No permission"))
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_message("Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_http_exception(self, bot_interface, mock_discord_bot):
        """Test send_message handles HTTPException."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789
        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock(side_effect=discord_mock.errors.HTTPException(MagicMock(), "Error"))
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_message("Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_general_exception(self, bot_interface, mock_discord_bot):
        """Test send_message handles general exceptions."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789
        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_message("Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_with_username(self, bot_interface, mock_discord_bot):
        """Test send_message with username (ignored for bots)."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_message("Test", username="CustomName")

        # Username should be ignored for bots
        assert result is True
        mock_channel.send.assert_awaited_once_with("Test")


# ============================================================================
# TEST: Send Embed
# ============================================================================

class TestBotInterfaceSendEmbed:
    """Test send_embed method."""

    @pytest.mark.asyncio
    async def test_send_embed_success(self, bot_interface, mock_discord_bot):
        """Test successful embed send."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        mock_embed = MagicMock()
        result = await bot_interface.send_embed(mock_embed)

        assert result is True
        mock_channel.send.assert_awaited_once_with(embed=mock_embed)

    @pytest.mark.asyncio
    async def test_send_embed_not_connected(self, bot_interface, mock_discord_bot):
        """Test send_embed when bot not connected."""
        mock_discord_bot.is_connected = False

        result = await bot_interface.send_embed(MagicMock())

        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_no_channel(self, bot_interface, mock_discord_bot):
        """Test send_embed when no event channel set."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = None

        result = await bot_interface.send_embed(MagicMock())

        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_discord_not_available(self, bot_interface, mock_discord_bot):
        """Test send_embed when DISCORD_AVAILABLE is False."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        with patch('discord_interface.DISCORD_AVAILABLE', False):
            result = await bot_interface.send_embed(MagicMock())
            assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_channel_not_found(self, bot_interface, mock_discord_bot):
        """Test send_embed when channel not found."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 999999
        mock_discord_bot.get_channel = MagicMock(return_value=None)

        result = await bot_interface.send_embed(MagicMock())

        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_wrong_channel_type(self, bot_interface, mock_discord_bot):
        """Test send_embed with wrong channel type."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789
        mock_channel = MagicMock()
        mock_channel.__class__ = type('VoiceChannel', (), {})  # Not a TextChannel
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_embed(MagicMock())

        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_forbidden_error(self, bot_interface, mock_discord_bot):
        """Test send_embed handles Forbidden error."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock(side_effect=discord_mock.errors.Forbidden(MagicMock(), "No permission"))
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_embed(MagicMock())

        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_http_exception(self, bot_interface, mock_discord_bot):
        """Test send_embed handles HTTPException."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock(side_effect=discord_mock.errors.HTTPException(MagicMock(), "Error"))
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_embed(MagicMock())

        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_general_exception(self, bot_interface, mock_discord_bot):
        """Test send_embed handles general exceptions."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789
        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock(side_effect=RuntimeError("Unexpected"))
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_embed(MagicMock())

        assert result is False


# ============================================================================
# TEST: Test Connection
# ============================================================================

class TestBotInterfaceTestConnection:
    """Test test_connection method."""

    @pytest.mark.asyncio
    async def test_connection_when_connected(self, bot_interface, mock_discord_bot):
        """Test test_connection returns True when bot connected."""
        mock_discord_bot.is_connected = True

        result = await bot_interface.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_connection_when_not_connected(self, bot_interface, mock_discord_bot):
        """Test test_connection returns False when bot not connected."""
        mock_discord_bot.is_connected = False

        result = await bot_interface.test_connection()

        assert result is False


# ============================================================================
# TEST: Integration Scenarios
# ============================================================================

class TestBotInterfaceIntegration:
    """Test integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, bot_interface, mock_discord_bot):
        """Test complete connect -> send -> disconnect lifecycle."""
        # Connect
        with patch.object(bot_interface.presence_updater, 'start', new_callable=AsyncMock):
            with patch.object(bot_interface.presence_updater, 'stop', new_callable=AsyncMock):
                await bot_interface.connect()

                # Send message
                mock_discord_bot.is_connected = True
                mock_discord_bot.event_channel_id = 123456789
                mock_channel = MagicMock()
                mock_channel.__class__ = discord_mock.TextChannel
                mock_channel.send = AsyncMock()
                mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

                result = await bot_interface.send_message("Test")
                assert result is True

                # Disconnect
                await bot_interface.disconnect()

    @pytest.mark.asyncio
    async def test_multiple_messages(self, bot_interface, mock_discord_bot):
        """Test sending multiple messages."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result1 = await bot_interface.send_message("Message 1")
        result2 = await bot_interface.send_message("Message 2")
        result3 = await bot_interface.send_message("Message 3")

        assert result1 is True
        assert result2 is True
        assert result3 is True
        assert mock_channel.send.await_count == 3

    @pytest.mark.asyncio
    async def test_recovery_after_error(self, bot_interface, mock_discord_bot):
        """Test recovery after send error."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        # First call fails, second succeeds
        mock_channel.send = AsyncMock(side_effect=[
            Exception("Network error"),
            None
        ])
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        # First send fails
        result1 = await bot_interface.send_message("Message 1")
        assert result1 is False

        # Second send succeeds
        result2 = await bot_interface.send_message("Message 2")
        assert result2 is True


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestBotInterfaceEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_send_empty_message(self, bot_interface, mock_discord_bot):
        """Test sending empty message."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        result = await bot_interface.send_message("")

        # Should still attempt to send
        assert result is True
        mock_channel.send.assert_awaited_once_with("")

    @pytest.mark.asyncio
    async def test_send_very_long_message(self, bot_interface, mock_discord_bot):
        """Test sending very long message."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456789

        mock_channel = MagicMock()
        mock_channel.__class__ = discord_mock.TextChannel
        mock_channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=mock_channel)

        long_message = "A" * 10000
        result = await bot_interface.send_message(long_message)

        assert result is True
