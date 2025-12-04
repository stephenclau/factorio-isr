"""
Pytest test suite for discord_bot.py - Complete Coverage
Tests connect_bot(), disconnect_bot(), send_event(), and more.

Coverage Target: +5-7%
"""

from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock, create_autospec
import pytest
import asyncio
import discord
from types import SimpleNamespace
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from discord_bot import DiscordBot


@pytest.fixture
def real_intents():
    """Return real Discord intents."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    return intents


@pytest.fixture
def bot(real_intents):
    """Create a DiscordBot instance."""
    bot = DiscordBot(token="TEST_TOKEN", bot_name="TestBot", intents=real_intents)

    # Mock user
    mock_user = MagicMock(id=12345, name="TestBot")
    type(bot).user = PropertyMock(return_value=mock_user)
    type(bot).guilds = PropertyMock(return_value=[MagicMock()])

    return bot


# ============================================================================
# CONNECT_BOT TESTS
# ============================================================================

@pytest.mark.asyncio
class TestConnectBot:
    """Test connect_bot() connection lifecycle."""

    async def test_connect_bot_success(self, bot):
        """Test successful bot connection."""
        # Mock all the connection steps
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot._ready = asyncio.Event()
        bot._send_connection_notification = AsyncMock()
        bot.update_presence = AsyncMock()
        bot._monitor_rcon_status = AsyncMock()

        # Simulate ready event being set after connection
        async def mock_connect():
            await asyncio.sleep(0.01)
            bot._ready.set()

        bot.connect = mock_connect

        # Call connect_bot
        await bot.connect_bot()

        # Verify all steps were called
        bot.login.assert_awaited_once_with("TEST_TOKEN")
        bot._send_connection_notification.assert_awaited_once()
        bot.update_presence.assert_awaited_once()
        assert bot._ready.is_set()

    async def test_connect_bot_timeout(self, bot):
        """Test connect_bot() raises ConnectionError on timeout."""
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot._ready = asyncio.Event()

        # Don't set ready - simulate timeout
        async def mock_connect_never_ready():
            await asyncio.sleep(100)  # Will timeout before this

        bot.connect = mock_connect_never_ready

        # Should raise ConnectionError after 30 seconds
        with pytest.raises(ConnectionError, match="Discord bot connection timed out after 30 seconds"):
            await bot.connect_bot()

    async def test_connect_bot_login_failure(self, bot):
        """Test connect_bot() raises ConnectionError on login failure."""
        # Mock login to raise LoginFailure
        bot.login = AsyncMock(side_effect=discord.errors.LoginFailure("Invalid token"))

        # Should raise ConnectionError with descriptive message
        with pytest.raises(ConnectionError, match="Discord login failed"):
            await bot.connect_bot()

    async def test_connect_bot_generic_exception(self, bot):
        """Test connect_bot() re-raises generic exceptions."""
        # Mock login to raise generic exception
        bot.login = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        # Should re-raise the exception
        with pytest.raises(RuntimeError, match="Unexpected error"):
            await bot.connect_bot()

    async def test_connect_bot_starts_rcon_monitoring(self, bot):
        """Test connect_bot() starts RCON monitoring task."""
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot._ready = asyncio.Event()
        bot._send_connection_notification = AsyncMock()
        bot.update_presence = AsyncMock()
        bot._monitor_rcon_status = AsyncMock()
        bot.rcon_monitor_task = None

        # Set ready immediately
        async def mock_connect():
            bot._ready.set()

        bot.connect = mock_connect

        await bot.connect_bot()

        # Verify RCON monitoring was started
        assert bot.rcon_monitor_task is not None

    async def test_connect_bot_skips_rcon_monitoring_if_already_running(self, bot):
        """Test connect_bot() doesn't start RCON monitoring if already running."""
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot._ready = asyncio.Event()
        bot._send_connection_notification = AsyncMock()
        bot.update_presence = AsyncMock()

        # Already have a running task
        async def dummy():
            await asyncio.sleep(10)
        bot.rcon_monitor_task = asyncio.create_task(dummy())
        existing_task = bot.rcon_monitor_task

        # Set ready immediately
        async def mock_connect():
            bot._ready.set()

        bot.connect = mock_connect

        await bot.connect_bot()

        # Should not have created a new task
        assert bot.rcon_monitor_task is existing_task

        # Clean up
        bot.rcon_monitor_task.cancel()
        try:
            await bot.rcon_monitor_task
        except asyncio.CancelledError:
            pass

    async def test_connect_bot_sends_notification(self, bot):
        """Test connect_bot() sends connection notification."""
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot._ready = asyncio.Event()
        bot._send_connection_notification = AsyncMock()
        bot.update_presence = AsyncMock()
        bot._monitor_rcon_status = AsyncMock()

        async def mock_connect():
            bot._ready.set()

        bot.connect = mock_connect

        await bot.connect_bot()

        # Verify notification was sent
        bot._send_connection_notification.assert_awaited_once()

    async def test_connect_bot_updates_presence(self, bot):
        """Test connect_bot() updates bot presence."""
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot._ready = asyncio.Event()
        bot._send_connection_notification = AsyncMock()
        bot.update_presence = AsyncMock()
        bot._monitor_rcon_status = AsyncMock()

        async def mock_connect():
            bot._ready.set()

        bot.connect = mock_connect

        await bot.connect_bot()

        # Verify presence was updated
        bot.update_presence.assert_awaited_once()


# ============================================================================
# SEND_EVENT ERROR PATHS
# ============================================================================

@pytest.mark.asyncio
class TestSendEventErrorPaths:
    """Test send_event() error handling."""

    async def test_send_event_when_not_connected(self, bot):
        """Test send_event() returns False when bot not connected."""
        bot._connected = False
        bot.event_channel_id = 123456

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))
        result = await bot.send_event(event)

        assert result is False

    async def test_send_event_no_channel_configured(self, bot):
        """Test send_event() returns False when no channel configured."""
        bot._connected = True
        bot.event_channel_id = None

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))
        result = await bot.send_event(event)

        assert result is False

    async def test_send_event_channel_not_found(self, bot):
        """Test send_event() returns False when channel doesn't exist."""
        bot._connected = True
        bot.event_channel_id = 999888777

        bot.get_channel = MagicMock(return_value=None)

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))
        result = await bot.send_event(event)

        assert result is False

    async def test_send_event_invalid_channel_type(self, bot):
        """Test send_event() returns False for non-TextChannel."""
        bot._connected = True
        bot.event_channel_id = 123456

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        bot.get_channel = MagicMock(return_value=voice_channel)

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))
        result = await bot.send_event(event)

        assert result is False

    async def test_send_event_forbidden_error(self, bot):
        """Test send_event() handles Forbidden error."""
        bot._connected = True
        bot.event_channel_id = 123456

        # Create REAL discord.TextChannel mock
        channel = create_autospec(discord.TextChannel, instance=True)
        channel.send = AsyncMock(side_effect=discord.errors.Forbidden(MagicMock(), "No perms"))
        bot.get_channel = MagicMock(return_value=channel)

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch("discord_bot.FactorioEventFormatter.format_for_discord", return_value="Test"):
            result = await bot.send_event(event)

        assert result is False

    async def test_send_event_http_exception(self, bot):
        """Test send_event() handles HTTPException."""
        bot._connected = True
        bot.event_channel_id = 123456

        channel = create_autospec(discord.TextChannel, instance=True)
        channel.send = AsyncMock(side_effect=discord.errors.HTTPException(MagicMock(), "Rate limit"))
        bot.get_channel = MagicMock(return_value=channel)

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch("discord_bot.FactorioEventFormatter.format_for_discord", return_value="Test"):
            result = await bot.send_event(event)

        assert result is False

    async def test_send_event_generic_exception(self, bot):
        """Test send_event() handles unexpected errors."""
        bot._connected = True
        bot.event_channel_id = 123456

        channel = create_autospec(discord.TextChannel, instance=True)
        channel.send = AsyncMock(side_effect=RuntimeError("Unexpected"))
        bot.get_channel = MagicMock(return_value=channel)

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch("discord_bot.FactorioEventFormatter.format_for_discord", return_value="Test"):
            result = await bot.send_event(event)

        assert result is False

    async def test_send_event_success(self, bot):
        """Test send_event() returns True on success."""
        bot._connected = True
        bot.event_channel_id = 123456

        # Use create_autospec for proper isinstance() check
        channel = create_autospec(discord.TextChannel, instance=True)
        channel.send = AsyncMock(return_value=MagicMock())
        bot.get_channel = MagicMock(return_value=channel)

        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch("discord_bot.FactorioEventFormatter.format_for_discord", return_value="Test msg"):
            result = await bot.send_event(event)

        assert result is True
        channel.send.assert_awaited_once_with("Test msg")


# ============================================================================
# DISCONNECT_BOT LIFECYCLE
# ============================================================================

@pytest.mark.asyncio
class TestDisconnectBot:
    """Test disconnect_bot() cleanup."""

    async def test_disconnect_bot_when_connected(self, bot):
        """Test disconnect_bot() cleanup when bot is connected."""
        bot._connected = True

        # Create proper async task mock
        async def dummy_task():
            await asyncio.sleep(0)

        task = asyncio.create_task(dummy_task())
        bot._connection_task = task

        bot._send_disconnection_notification = AsyncMock()
        bot.close = AsyncMock()
        bot.is_closed = MagicMock(return_value=False)

        await bot.disconnect_bot()

        # Verify bot was closed
        bot.close.assert_awaited_once()
        assert bot._connected is False

    async def test_disconnect_bot_cancels_rcon_monitor(self, bot):
        """Test disconnect_bot() cancels RCON monitoring task."""
        bot._connected = True
        bot._connection_task = None

        # Create real asyncio task
        async def monitor():
            await asyncio.sleep(10)

        bot.rcon_monitor_task = asyncio.create_task(monitor())

        bot._send_disconnection_notification = AsyncMock()
        bot.close = AsyncMock()
        bot.is_closed = MagicMock(return_value=False)

        await bot.disconnect_bot()

        # Verify RCON task was cancelled
        assert bot.rcon_monitor_task is None

    async def test_disconnect_bot_when_already_closed(self, bot):
        """Test disconnect_bot() when bot already closed."""
        bot._connected = True
        bot._connection_task = None
        bot.rcon_monitor_task = None

        bot.is_closed = MagicMock(return_value=True)
        bot.close = AsyncMock()
        bot._send_disconnection_notification = AsyncMock()

        await bot.disconnect_bot()

        # Should not call close again
        bot.close.assert_not_awaited()

    async def test_disconnect_bot_skips_when_no_connection(self, bot):
        """Test disconnect_bot() does nothing when not connected and no task."""
        bot._connected = False
        bot._connection_task = None

        # Should not raise, just return early
        await bot.disconnect_bot()


# ============================================================================
# CLEAR GLOBAL COMMANDS
# ============================================================================

@pytest.mark.asyncio
class TestClearGlobalCommands:
    """Test clear_global_commands() method."""

    async def test_clear_global_commands_success(self, bot):
        """Test successful command clearing."""
        bot.tree.clear_commands = MagicMock()
        bot.tree.sync = AsyncMock()

        await bot.clear_global_commands()

        bot.tree.clear_commands.assert_called_once_with(guild=None)
        bot.tree.sync.assert_awaited_once()

    async def test_clear_global_commands_http_error(self, bot):
        """Test error handling in clear_global_commands()."""
        bot.tree.clear_commands = MagicMock()
        bot.tree.sync = AsyncMock(side_effect=discord.errors.HTTPException(MagicMock(), "Fail"))

        # Should not raise
        await bot.clear_global_commands()

    async def test_clear_global_commands_generic_error(self, bot):
        """Test generic error handling in clear_global_commands()."""
        bot.tree.clear_commands = MagicMock(side_effect=RuntimeError("Failed"))

        # Should not raise
        await bot.clear_global_commands()


# ============================================================================
# PROPERTY TESTS
# ============================================================================

class TestBotProperties:
    """Test bot properties and setters."""

    def test_is_connected_false(self, bot):
        """Test is_connected property when False."""
        bot._connected = False
        assert bot.is_connected is False

    def test_is_connected_true(self, bot):
        """Test is_connected property when True."""
        bot._connected = True
        assert bot.is_connected is True

    def test_set_event_channel(self, bot):
        """Test set_event_channel()."""
        bot.set_event_channel(987654321)
        # NOTE: Uses PUBLIC attribute event_channel_id (no underscore!)
        assert bot.event_channel_id == 987654321

    def test_set_rcon_client(self, bot):
        """Test set_rcon_client()."""
        mock_rcon = MagicMock()
        bot.set_rcon_client(mock_rcon)
        assert bot.rcon_client is mock_rcon


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
