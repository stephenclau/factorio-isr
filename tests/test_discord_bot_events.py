"""
Pytest test suite for discord_bot.py - Event Handling Enhancement

Enhances existing event tests with additional coverage for:
- on_ready edge cases
- on_disconnect scenarios
- send_event with various event types
- Event channel configuration
- Event formatting and delivery
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
import discord
from discord import app_commands
import pytest
from discord_bot import DiscordBot
from types import SimpleNamespace
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_text_channel() -> MagicMock:
    """Mock Discord TextChannel for event notifications."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 999888777
    channel.send = AsyncMock()
    return channel

@pytest.fixture
def patch_discord_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch Discord network calls."""
    async def mock_login(self: Any, token: str) -> None:
        pass
    async def mock_connect(self: Any, *args: Any, **kwargs: Any) -> None:
        pass
    async def mock_close(self: Any) -> None:
        pass
    monkeypatch.setattr("discord.Client.login", mock_login)
    monkeypatch.setattr("discord.Client.connect", mock_connect)
    monkeypatch.setattr("discord.Client.close", mock_close)

@pytest.fixture
def patch_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable rate limiting for tests."""
    class NoRateLimit:
        def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
            return (False, 0.0)
    no_limit = NoRateLimit()
    monkeypatch.setattr("discord_bot.QUERY_COOLDOWN", no_limit)
    monkeypatch.setattr("discord_bot.ADMIN_COOLDOWN", no_limit)
    monkeypatch.setattr("discord_bot.DANGER_COOLDOWN", no_limit)

@pytest.fixture
async def bot(patch_discord_network: None, patch_rate_limiting: None) -> DiscordBot:
    """Create a REAL DiscordBot instance."""
    bot_instance = DiscordBot(token="TEST_TOKEN", bot_name="TestBot")
    await bot_instance.setup_hook()
    yield bot_instance
    if not bot_instance.is_closed():
        await bot_instance.close()

# =============================================================================
# TEST: on_ready Event Handler
# =============================================================================

class TestOnReadyEventHandler:
    """Test on_ready event handler enhancements."""

    @pytest.mark.asyncio
    async def test_on_ready_with_no_guilds(self, bot: DiscordBot) -> None:
        """Test on_ready when bot is not in any guilds."""
        mock_user = MagicMock()
        mock_user.name = "TestBot"
        mock_user.id = 12345

        type(bot).user = PropertyMock(return_value=mock_user)
        type(bot).guilds = PropertyMock(return_value=[])  # Empty guilds

        bot.tree.sync = AsyncMock(return_value=[])
        bot._send_connection_notification = AsyncMock()

        await bot.on_ready()

        assert bot.is_connected is True
        assert bot._ready.is_set()

    @pytest.mark.asyncio
    async def test_on_ready_with_multiple_guilds(self, bot: DiscordBot) -> None:
        """Test on_ready when bot is in multiple guilds."""
        mock_user = MagicMock()
        mock_user.name = "TestBot"
        mock_user.id = 12345

        # Multiple guilds
        guilds = [MagicMock() for _ in range(5)]
        type(bot).user = PropertyMock(return_value=mock_user)
        type(bot).guilds = PropertyMock(return_value=guilds)

        bot.tree.sync = AsyncMock(return_value=[])
        bot._send_connection_notification = AsyncMock()

        await bot.on_ready()

        assert bot.is_connected is True

    @pytest.mark.asyncio
    async def test_on_ready_sync_failure(self, bot: DiscordBot) -> None:
        """Test on_ready when command sync fails."""
        mock_user = MagicMock()
        mock_user.name = "TestBot"
        mock_user.id = 12345

        type(bot).user = PropertyMock(return_value=mock_user)
        type(bot).guilds = PropertyMock(return_value=[MagicMock()])

        bot.tree.sync = AsyncMock(side_effect=Exception("Sync failed"))
        bot._send_connection_notification = AsyncMock()

        # Should not raise, should handle gracefully
        await bot.on_ready()

        # Bot should still be marked as connected
        assert bot.is_connected is True

    @pytest.mark.asyncio
    async def test_on_ready_notification_failure(self, bot: DiscordBot) -> None:
        """Test on_ready when connection notification fails."""
        mock_user = MagicMock()
        mock_user.name = "TestBot"
        mock_user.id = 12345

        type(bot).user = PropertyMock(return_value=mock_user)
        type(bot).guilds = PropertyMock(return_value=[MagicMock()])

        bot.tree.sync = AsyncMock(return_value=[])
        bot._send_connection_notification = AsyncMock(side_effect=Exception("Notification failed"))

        # Should not raise
        await bot.on_ready()

        assert bot.is_connected is True

    @pytest.mark.asyncio
    async def test_on_ready_sets_ready_event(self, bot: DiscordBot) -> None:
        """Test that on_ready sets the ready event."""
        mock_user = MagicMock()
        mock_user.name = "TestBot"
        mock_user.id = 12345

        type(bot).user = PropertyMock(return_value=mock_user)
        type(bot).guilds = PropertyMock(return_value=[MagicMock()])

        bot.tree.sync = AsyncMock(return_value=[])
        bot._send_connection_notification = AsyncMock()

        # Ready event should not be set initially
        assert not bot._ready.is_set()

        await bot.on_ready()

        # Should be set after on_ready
        assert bot._ready.is_set()

# =============================================================================
# TEST: on_disconnect Event Handler
# =============================================================================

class TestOnDisconnectEventHandler:
    """Test on_disconnect event handler."""

    @pytest.mark.asyncio
    async def test_on_disconnect_sets_flag(self, bot: DiscordBot) -> None:
        """Test that on_disconnect sets connected flag to False."""
        bot._connected = True

        await bot.on_disconnect()

        assert bot.is_connected is False

    @pytest.mark.asyncio
    async def test_on_disconnect_when_already_disconnected(self, bot: DiscordBot) -> None:
        """Test on_disconnect when already disconnected."""
        bot._connected = False

        # Should not raise
        await bot.on_disconnect()

        assert bot.is_connected is False

    @pytest.mark.asyncio
    async def test_on_disconnect_multiple_times(self, bot: DiscordBot) -> None:
        """Test calling on_disconnect multiple times."""
        bot._connected = True

        await bot.on_disconnect()
        await bot.on_disconnect()
        await bot.on_disconnect()

        assert bot.is_connected is False

# =============================================================================
# TEST: send_event Method
# =============================================================================

class TestSendEventMethod:
    """Test send_event method enhancements."""

    @pytest.mark.asyncio
    async def test_send_event_player_joined(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test send_event with player joined event."""
        bot._connected = True
        bot.set_event_channel(123)

        event = SimpleNamespace(
            event_type=SimpleNamespace(value="player_joined"),
            player_name="TestPlayer"
        )

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="TestPlayer joined the game"):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                result = await bot.send_event(event)

                assert result is True
                mock_text_channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_event_player_left(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test send_event with player left event."""
        bot._connected = True
        bot.set_event_channel(123)

        event = SimpleNamespace(
            event_type=SimpleNamespace(value="player_left"),
            player_name="TestPlayer"
        )

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="TestPlayer left the game"):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                result = await bot.send_event(event)

                assert result is True

    @pytest.mark.asyncio
    async def test_send_event_chat_message(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test send_event with chat message event."""
        bot._connected = True
        bot.set_event_channel(123)

        event = SimpleNamespace(
            event_type=SimpleNamespace(value="chat"),
            player_name="Player1",
            message="Hello world!"
        )

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="<Player1> Hello world!"):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                result = await bot.send_event(event)

                assert result is True

    @pytest.mark.asyncio
    async def test_send_event_no_channel_configured(self, bot: DiscordBot) -> None:
        """Test send_event when no event channel configured."""
        bot._connected = True
        bot.event_channel_id = None

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        result = await bot.send_event(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_channel_not_found(self, bot: DiscordBot) -> None:
        """Test send_event when channel doesn't exist."""
        bot._connected = True
        bot.set_event_channel(999999)

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="Test event"):
            with patch.object(bot, 'get_channel', return_value=None):
                result = await bot.send_event(event)

                assert result is False

    @pytest.mark.asyncio
    async def test_send_event_send_fails(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test send_event when channel.send() fails."""
        bot._connected = True
        bot.set_event_channel(123)

        mock_text_channel.send = AsyncMock(side_effect=Exception("Send failed"))

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="Test event"):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                result = await bot.send_event(event)

                assert result is False

    @pytest.mark.asyncio
    async def test_send_event_formatter_error(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test send_event when formatter raises error."""
        bot._connected = True
        bot.set_event_channel(123)

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   side_effect=Exception("Format error")):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                result = await bot.send_event(event)

                assert result is False

    @pytest.mark.asyncio
    async def test_send_event_wrong_channel_type(self, bot: DiscordBot) -> None:
        """Test send_event when channel is not TextChannel."""
        bot._connected = True
        bot.set_event_channel(123)

        # Mock a VoiceChannel instead of TextChannel
        wrong_channel = MagicMock()
        wrong_channel.__class__.__name__ = "VoiceChannel"

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="Test event"):
            with patch.object(bot, 'get_channel', return_value=wrong_channel):
                result = await bot.send_event(event)

                # Should fail because it's not a TextChannel
                assert result is False

# =============================================================================
# TEST: Event Channel Configuration
# =============================================================================

class TestEventChannelConfiguration:
    """Test event channel configuration."""

    def test_set_event_channel_valid(self, bot: DiscordBot) -> None:
        """Test setting valid event channel ID."""
        bot.set_event_channel(123456789)

        assert bot.event_channel_id == 123456789

    def test_set_event_channel_zero(self, bot: DiscordBot) -> None:
        """Test setting event channel to 0."""
        bot.set_event_channel(0)

        assert bot.event_channel_id == 0

    def test_set_event_channel_negative(self, bot: DiscordBot) -> None:
        """Test setting negative channel ID."""
        bot.set_event_channel(-1)

        # Should accept (validation is Discord's responsibility)
        assert bot.event_channel_id == -1

    def test_set_event_channel_very_large(self, bot: DiscordBot) -> None:
        """Test setting very large channel ID."""
        large_id = 9999999999999999999
        bot.set_event_channel(large_id)

        assert bot.event_channel_id == large_id

    def test_set_event_channel_multiple_times(self, bot: DiscordBot) -> None:
        """Test changing event channel multiple times."""
        bot.set_event_channel(111)
        assert bot.event_channel_id == 111

        bot.set_event_channel(222)
        assert bot.event_channel_id == 222

        bot.set_event_channel(333)
        assert bot.event_channel_id == 333

    def test_set_event_channel_to_none(self, bot: DiscordBot) -> None:
        """Test setting event channel to None."""
        bot.set_event_channel(123)
        bot.event_channel_id = None

        assert bot.event_channel_id is None

# =============================================================================
# TEST: Event Handling Integration
# =============================================================================

class TestEventHandlingIntegration:
    """Test event handling integration scenarios."""

    @pytest.mark.asyncio
    async def test_event_flow_connect_to_send(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test complete flow from connect to sending event."""
        # Setup
        mock_user = MagicMock()
        mock_user.name = "TestBot"
        mock_user.id = 12345

        type(bot).user = PropertyMock(return_value=mock_user)
        type(bot).guilds = PropertyMock(return_value=[MagicMock()])

        bot.tree.sync = AsyncMock(return_value=[])
        bot._send_connection_notification = AsyncMock()
        bot.set_event_channel(123)

        # Connect
        await bot.on_ready()
        assert bot.is_connected is True

        # Send event
        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="Test event"):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                result = await bot.send_event(event)

                assert result is True

    @pytest.mark.asyncio
    async def test_event_send_after_disconnect(
        self, bot: DiscordBot
    ) -> None:
        """Test that events fail to send after disconnect."""
        bot._connected = True
        bot.set_event_channel(123)

        # Disconnect
        await bot.on_disconnect()

        # Try to send event
        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))
        result = await bot.send_event(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_events_rapid_fire(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test sending multiple events rapidly."""
        bot._connected = True
        bot.set_event_channel(123)

        events = [
            SimpleNamespace(event_type=SimpleNamespace(value=f"event_{i}"))
            for i in range(10)
        ]

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="Event message"):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                results = await asyncio.gather(
                    *[bot.send_event(event) for event in events]
                )

                # All should succeed
                assert all(results)
                assert mock_text_channel.send.await_count == 10

    @pytest.mark.asyncio
    async def test_event_send_reconnect_recovery(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test event sending after disconnect and reconnect."""
        mock_user = MagicMock()
        mock_user.name = "TestBot"
        mock_user.id = 12345

        type(bot).user = PropertyMock(return_value=mock_user)
        type(bot).guilds = PropertyMock(return_value=[MagicMock()])

        bot.tree.sync = AsyncMock(return_value=[])
        bot._send_connection_notification = AsyncMock()
        bot.set_event_channel(123)

        # Initial connect
        await bot.on_ready()

        # Disconnect
        await bot.on_disconnect()

        # Reconnect
        await bot.on_ready()

        # Send event
        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="Test event"):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                result = await bot.send_event(event)

                assert result is True
