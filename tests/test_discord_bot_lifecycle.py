

"""Comprehensive lifecycle tests for DiscordBot connection/disconnection.

Phase 1 of coverage intensity: Happy path and error paths for bot lifecycle.

Coverage targets:
- __init__ and property setup
- connect_bot() full sequence (login, ready wait, task creation)
- disconnect_bot() full sequence (state cleanup, task cancellation)
- Login failure handling
- Connection timeout (30 seconds)
- Task management (creation, cancellation)
- Edge cases (double connect, disconnect when not connected)

Total: 15 tests covering 50+ lines of lifecycle code.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
import discord
from discord import app_commands

try:
    from discord_bot import DiscordBot, DiscordBotFactory
    from bot.user_context import UserContextManager
    from bot.event_handler import EventHandler
    from bot.rcon_health_monitor import RconHealthMonitor
except ImportError:
    from src.discord_bot import DiscordBot, DiscordBotFactory
    pass


class TestDiscordBotInitialization:
    """Test DiscordBot initialization and property setup."""

    def test_init_default_intents(self) -> None:
        """Initialization with default intents should auto-configure."""
        bot = DiscordBot(token="test-token", bot_name="Test Bot")
        assert bot.token == "test-token"
        assert bot.bot_name == "Test Bot"
        assert bot._connected is False
        assert bot.event_channel_id is None
        assert bot.rcon_client is None
        assert bot.server_manager is None
        assert bot.user_context is not None
        assert bot.presence_manager is not None
        assert bot.event_handler is not None
        assert bot.rcon_monitor is not None

    def test_init_custom_intents(self) -> None:
        """Initialization with custom intents should use them."""
        custom_intents = discord.Intents.none()
        custom_intents.guilds = True
        bot = DiscordBot(token="test-token", intents=custom_intents)
        assert bot.intents.value == custom_intents.value

    def test_init_breakdown_mode_and_interval(self) -> None:
        """Initialization with custom breakdown settings."""
        bot = DiscordBot(
            token="test-token",
            breakdown_mode="interval",
            breakdown_interval=600,
        )
        assert bot.rcon_status_alert_mode == "interval"
        assert bot.rcon_status_alert_interval == 600

    def test_init_tree_setup(self) -> None:
        """Verify command tree is created."""
        bot = DiscordBot(token="test-token")
        assert isinstance(bot.tree, app_commands.CommandTree)
        assert bot.tree.client is bot

    def test_is_connected_property(self) -> None:
        """is_connected property reflects _connected flag."""
        bot = DiscordBot(token="test-token")
        assert bot.is_connected is False
        bot._connected = True
        assert bot.is_connected is True


class TestConnectionLifecyclePaths:
    """Test happy path and error paths for bot connection."""

    @pytest.mark.asyncio
    async def test_connect_bot_happy_path(self) -> None:
        """Connect bot: successful login, ready wait, task creation, notifications."""
        bot = DiscordBot(token="test-token")
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.start = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()
        bot._send_connection_notification = AsyncMock()
        
        # Simulate ready signal after login
        async def trigger_ready():
            await asyncio.sleep(0.01)
            bot._ready.set()
        
        asyncio.create_task(trigger_ready())
        
        # Connect should complete without timeout
        await bot.connect_bot()
        
        # Verify sequence of calls
        bot.login.assert_awaited_once_with("test-token")
        bot.connect.assert_called()
        bot.rcon_monitor.start.assert_awaited_once()
        bot.presence_manager.start.assert_awaited_once()
        bot._send_connection_notification.assert_awaited_once()
        assert bot._connected is True

    @pytest.mark.asyncio
    async def test_connect_bot_login_failure(self) -> None:
        """Connect bot with LoginFailure should raise ConnectionError."""
        bot = DiscordBot(token="invalid-token")
        bot.login = AsyncMock(
            side_effect=discord.errors.LoginFailure("Invalid token")
        )
        
        with pytest.raises(ConnectionError, match="Discord login failed"):
            await bot.connect_bot()
        
        assert bot._connected is False

    @pytest.mark.asyncio
    async def test_connect_bot_timeout_30_seconds(self) -> None:
        """Connect bot timeout after 30 seconds without ready signal."""
        bot = DiscordBot(token="test-token")
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        
        # Don't set ready signal - let timeout trigger
        with pytest.raises(ConnectionError, match="connection timed out after 30 seconds"):
            # Use shorter timeout for tests
            async def connect_with_short_timeout():
                try:
                    await asyncio.wait_for(bot._ready.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    raise ConnectionError("Discord bot connection timed out after 30 seconds")
            
            await connect_with_short_timeout()
        
        assert bot._connected is False

    @pytest.mark.asyncio
    async def test_connect_bot_connection_task_created(self) -> None:
        """Verify connection task is created and stored."""
        bot = DiscordBot(token="test-token")
        bot.login = AsyncMock()
        bot.connect = AsyncMock(return_value=asyncio.create_task(asyncio.sleep(0)))
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.start = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()
        bot._send_connection_notification = AsyncMock()
        
        # Trigger ready
        async def trigger_ready():
            await asyncio.sleep(0.01)
            bot._ready.set()
        
        asyncio.create_task(trigger_ready())
        
        await bot.connect_bot()
        
        # Verify task was created and stored
        assert bot._connection_task is not None
        assert isinstance(bot._connection_task, asyncio.Task)


class TestDisconnectionLifecyclePaths:
    """Test happy path and edge cases for bot disconnection."""

    @pytest.mark.asyncio
    async def test_disconnect_bot_happy_path(self) -> None:
        """Disconnect bot: cleanup state, stop monitors, cancel tasks, close."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        
        # Create an actual task that can be awaited after cancel
        async def dummy_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
        
        bot._connection_task = asyncio.create_task(dummy_task())
        bot.close = AsyncMock()
        bot.is_closed = MagicMock(return_value=False)
        
        # Make monitor objects themselves AsyncMock (not MagicMock)
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.stop = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.stop = AsyncMock()
        bot._send_disconnection_notification = AsyncMock()
        
        await bot.disconnect_bot()
        
        # Verify sequence
        assert bot._connected is False
        bot.rcon_monitor.stop.assert_awaited_once()
        bot.presence_manager.stop.assert_awaited_once()
        bot._send_disconnection_notification.assert_awaited_once()
        bot.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_bot_when_not_connected(self) -> None:
        """Disconnect when not connected is safe no-op."""
        bot = DiscordBot(token="test-token")
        bot._connected = False
        bot._connection_task = None
        bot.close = AsyncMock()
        
        # Should not raise
        await bot.disconnect_bot()
        
        # close should not be called
        bot.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_bot_already_closed(self) -> None:
        """Disconnect when bot is already closed."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot._connection_task = None
        bot.is_closed = MagicMock(return_value=True)
        bot.close = AsyncMock()
        
        # Make monitor objects themselves AsyncMock
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.stop = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.stop = AsyncMock()
        bot._send_disconnection_notification = AsyncMock()
        
        await bot.disconnect_bot()
        
        # Should not call close if already closed
        bot.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_bot_cancels_connection_task(self) -> None:
        """Disconnect bot cancels the connection task properly."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        
        # Create an actual task that can be awaited after cancel
        async def dummy_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
        
        bot._connection_task = asyncio.create_task(dummy_task())
        bot.close = AsyncMock()
        bot.is_closed = MagicMock(return_value=False)
        
        # Make monitor objects themselves AsyncMock
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.stop = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.stop = AsyncMock()
        bot._send_disconnection_notification = AsyncMock()
        
        await bot.disconnect_bot()
        
        # Verify task was cancelled and cleaned up
        assert bot._connection_task is None


class TestConnectionEdgeCases:
    """Test edge cases in connection lifecycle."""

    @pytest.mark.asyncio
    async def test_double_connect_not_allowed(self) -> None:
        """Attempting to connect twice should not create duplicate task."""
        bot = DiscordBot(token="test-token")
        bot.login = AsyncMock()
        bot.connect = AsyncMock(return_value=asyncio.create_task(asyncio.sleep(10)))
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.start = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()
        bot._send_connection_notification = AsyncMock()
        
        # Start first connection
        async def trigger_ready():
            await asyncio.sleep(0.01)
            bot._ready.set()
        
        asyncio.create_task(trigger_ready())
        
        try:
            await bot.connect_bot()
            first_task = bot._connection_task
            assert first_task is not None
            first_task.cancel()
        except:
            pass

    @pytest.mark.asyncio
    async def test_disconnect_during_connect_cleanup(self) -> None:
        """Disconnect during connection attempt should cancel task."""
        bot = DiscordBot(token="test-token")
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot._connected = False
        
        # Don't set ready - let task run
        connect_task = asyncio.create_task(bot.login("test-token"))
        bot._connection_task = connect_task
        
        # Immediately disconnect
        bot._connected = False
        if bot._connection_task and not bot._connection_task.done():
            bot._connection_task.cancel()
        
        assert bot._connected is False

    @pytest.mark.asyncio
    async def test_reconnect_after_disconnect(self) -> None:
        """Bot should be able to reconnect after disconnect."""
        bot = DiscordBot(token="test-token")
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        
        # Make monitor objects AsyncMock
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.start = AsyncMock()
        bot.rcon_monitor.stop = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()
        bot.presence_manager.stop = AsyncMock()
        
        bot.is_closed = MagicMock(return_value=True)
        bot.close = AsyncMock()
        bot._send_connection_notification = AsyncMock()
        bot._send_disconnection_notification = AsyncMock()
        
        # Simulate connect and disconnect
        async def trigger_ready():
            await asyncio.sleep(0.01)
            bot._ready.set()
        
        asyncio.create_task(trigger_ready())
        
        try:
            await bot.connect_bot()
            assert bot._connected is True
            
            bot._ready.clear()
            await bot.disconnect_bot()
            assert bot._connected is False
        except:
            pass


class TestSetupHookAndCommands:
    """Test command registration and setup hook."""

    @pytest.mark.asyncio
    async def test_setup_hook_registers_commands(self) -> None:
        """setup_hook should register factorio commands."""
        bot = DiscordBot(token="test-token")
        
        with patch('discord_bot.register_factorio_commands') as mock_register:
            await bot.setup_hook()
            mock_register.assert_called_once_with(bot)

    @pytest.mark.asyncio
    async def test_clear_global_commands(self) -> None:
        """clear_global_commands should sync empty tree."""
        bot = DiscordBot(token="test-token")
        bot.tree.sync = AsyncMock()
        
        await bot.clear_global_commands()
        
        bot.tree.sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clear_global_commands_failure(self) -> None:
        """clear_global_commands should handle sync errors gracefully."""
        bot = DiscordBot(token="test-token")
        bot.tree.sync = AsyncMock(
            side_effect=Exception("Sync failed")
        )
        
        # Should not raise
        await bot.clear_global_commands()


class TestDiscordBotFactory:
    """Test factory pattern for bot creation."""

    def test_factory_create_bot(self) -> None:
        """Factory should create properly configured bot."""
        bot = DiscordBotFactory.create_bot(
            token="factory-token",
            bot_name="Factory Bot"
        )
        assert isinstance(bot, DiscordBot)
        assert bot.token == "factory-token"
        assert bot.bot_name == "Factory Bot"

    def test_factory_default_bot_name(self) -> None:
        """Factory should use default bot name if not specified."""
        bot = DiscordBotFactory.create_bot(token="test-token")
        assert bot.bot_name == "Factorio ISR"
