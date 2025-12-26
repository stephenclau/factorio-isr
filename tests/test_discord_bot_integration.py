

"""Integration testing for DiscordBot end-to-end workflows.

Phase 5 of coverage intensity: End-to-end integration flows and final coverage push.

Coverage targets:
- Full bot lifecycle from init through connect/disconnect
- Configuration integration with lifecycle
- Multi-server notification routing
- Event handler integration
- Presence manager integration
- RCON monitor integration
- Complete workflow happy paths

Total: 6 tests covering integration flows.
"""

import asyncio
import pytest
from typing import Optional, Dict
from unittest.mock import Mock, AsyncMock, MagicMock, patch, PropertyMock
import discord

try:
    from discord_bot import DiscordBot, DiscordBotFactory
except ImportError:
    pass


class MockServerConfig:
    """Mock server configuration."""

    def __init__(
        self,
        tag: str,
        name: str,
        event_channel_id: Optional[int] = None,
    ):
        self.tag = tag
        self.name = name
        self.event_channel_id = event_channel_id
        self.rcon_status_alert_mode = "interval"
        self.rcon_status_alert_interval = 600


class MockServerManager:
    """Mock server manager."""

    def __init__(self, servers: Optional[Dict[str, MockServerConfig]] = None):
        if servers is None:
            self.configs = {
                "prod": MockServerConfig("prod", "Production", 111111111),
                "staging": MockServerConfig("staging", "Staging", 222222222),
            }
        else:
            self.configs = servers

    def list_servers(self) -> Dict[str, MockServerConfig]:
        return self.configs

    def get_config(self, tag: str) -> Optional[MockServerConfig]:
        return self.configs.get(tag)


class TestFullBotLifecycle:
    """Test complete bot lifecycle from init through disconnect."""

    @pytest.mark.asyncio
    async def test_full_bot_lifecycle_init_to_disconnect(self) -> None:
        """Complete bot lifecycle: init, config, connect, disconnect."""
        # Initialize
        bot = DiscordBot(token="test-token", bot_name="Test Bot")
        assert bot.token == "test-token"
        assert bot.bot_name == "Test Bot"
        assert bot._connected is False

        # Configure
        manager = MockServerManager()
        bot.set_event_channel(123456789)
        bot.set_server_manager(manager)
        bot._apply_server_status_alert_config()
        
        assert bot.event_channel_id == 123456789
        assert bot.server_manager is manager
        assert bot.rcon_status_alert_mode == "interval"

        # Mock connection components
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.start = AsyncMock()
        bot.rcon_monitor.stop = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()
        bot.presence_manager.stop = AsyncMock()
        bot._send_connection_notification = AsyncMock()
        bot._send_disconnection_notification = AsyncMock()
        bot.close = AsyncMock()
        bot.is_closed = MagicMock(return_value=False)

        # Trigger ready signal
        async def trigger_ready():
            await asyncio.sleep(0.01)
            bot._ready.set()

        asyncio.create_task(trigger_ready())

        # Connect
        await bot.connect_bot()
        assert bot._connected is True
        bot.login.assert_awaited_once()
        bot.rcon_monitor.start.assert_awaited_once()
        bot.presence_manager.start.assert_awaited_once()

        # Create real task for disconnect test
        async def dummy_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
        bot._connection_task = asyncio.create_task(dummy_task())

        # Disconnect
        await bot.disconnect_bot()
        assert bot._connected is False
        bot.rcon_monitor.stop.assert_awaited_once()
        bot.presence_manager.stop.assert_awaited_once()
        bot.close.assert_awaited_once()


class TestMultiServerNotificationRouting:
    """Test notification routing across multiple servers."""

    @pytest.mark.asyncio
    async def test_notifications_route_to_all_servers(self) -> None:
        """Notifications should route to all configured server channels."""
        bot = DiscordBot(token="test-token")

        # Setup multi-server config
        manager = MockServerManager()
        bot.set_server_manager(manager)

        # Mock channels
        mock_channel_1 = AsyncMock(spec=discord.TextChannel)
        mock_channel_2 = AsyncMock(spec=discord.TextChannel)

        def get_channel(channel_id):
            if channel_id == 111111111:
                return mock_channel_1
            elif channel_id == 222222222:
                return mock_channel_2
            return None

        bot.get_channel = MagicMock(side_effect=get_channel)

        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
            mock_user.return_value = MagicMock(name="Test Bot", id=999888777)

            # Send connection notification
            await bot._send_connection_notification()

            # Both channels should receive notifications
            mock_channel_1.send.assert_awaited()
            mock_channel_2.send.assert_awaited()


class TestConfigurationIntegrationWithLifecycle:
    """Test configuration methods integrated with lifecycle."""

    @pytest.mark.asyncio
    async def test_config_applies_before_connect(self) -> None:
        """Configuration should be applied before connecting."""
        bot = DiscordBot(token="test-token")

        # Setup configuration
        manager = MockServerManager()
        bot.set_event_channel(123456789)
        bot.set_server_manager(manager)
        bot._apply_server_status_alert_config()

        # Verify config is set
        assert bot.event_channel_id == 123456789
        assert bot.rcon_status_alert_mode == "interval"
        assert bot.rcon_status_alert_interval == 600

        # Mock connection
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.start = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()
        bot._send_connection_notification = AsyncMock()

        async def trigger_ready():
            await asyncio.sleep(0.01)
            bot._ready.set()

        asyncio.create_task(trigger_ready())

        # Connect with config in place
        await bot.connect_bot()

        # Verify connection succeeded with config
        assert bot._connected is True
        assert bot.event_channel_id == 123456789
        assert bot.server_manager is manager


class TestEventHandlerIntegration:
    """Test event handlers integrated with bot state."""

    @pytest.mark.asyncio
    async def test_on_ready_with_configured_bot(self) -> None:
        """on_ready should work with fully configured bot."""
        bot = DiscordBot(token="test-token")

        # Configure bot
        bot.set_event_channel(123456789)
        bot.set_server_manager(MockServerManager())
        bot._apply_server_status_alert_config()

        # Setup mocks
        bot.tree.sync = AsyncMock(return_value=[])
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()

        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user, \
             patch.object(type(bot), 'guilds', new_callable=PropertyMock) as mock_guilds:
            mock_user.return_value = MagicMock(name="Test Bot", id=999888777)
            mock_guilds.return_value = []

            # Trigger ready
            await bot.on_ready()

            # Verify state
            assert bot._connected is True
            assert bot._ready.is_set()
            bot.presence_manager.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_disconnect_cleanup(self) -> None:
        """on_disconnect should properly clean up state."""
        bot = DiscordBot(token="test-token")
        bot._connected = True

        # Trigger disconnect
        await bot.on_disconnect()

        # Verify cleanup
        assert bot._connected is False


class TestHappyPathWorkflows:
    """Test complete happy path workflows."""

    @pytest.mark.asyncio
    async def test_end_to_end_command_registration_and_ready(self) -> None:
        """Complete flow: setup_hook -> on_ready -> ready event."""
        bot = DiscordBot(token="test-token")

        # Setup hook
        with patch('discord_bot.register_factorio_commands') as mock_register:
            await bot.setup_hook()
            mock_register.assert_called_once_with(bot)

        # Configure for ready
        bot.tree.sync = AsyncMock(return_value=[])
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()

        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user, \
             patch.object(type(bot), 'guilds', new_callable=PropertyMock) as mock_guilds:
            mock_user.return_value = MagicMock(name="Test Bot", id=999888777)
            mock_guilds.return_value = []

            # Trigger ready
            await bot.on_ready()

            # Verify complete flow
            assert bot._connected is True
            assert bot._ready.is_set()
            bot.tree.sync.assert_awaited()
            bot.presence_manager.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rcon_client_integration_with_lifecycle(self) -> None:
        """RCON client should integrate with bot lifecycle."""
        bot = DiscordBot(token="test-token")
        assert bot.rcon_client is None

        # Set RCON client
        mock_rcon = MagicMock()
        mock_rcon.send_command = MagicMock(return_value="response")
        bot.set_rcon_client(mock_rcon)

        # Verify client is available during lifecycle
        assert bot.rcon_client is mock_rcon
        assert bot.rcon_client.send_command("status") == "response"

        # Clear RCON client
        bot.set_rcon_client(None)
        assert bot.rcon_client is None


class TestFactoryIntegration:
    """Test factory pattern integrated with lifecycle."""

    @pytest.mark.asyncio
    async def test_factory_created_bot_complete_setup(self) -> None:
        """Factory-created bot should support complete setup and lifecycle."""
        # Create bot via factory
        bot = DiscordBotFactory.create_bot(
            token="factory-token",
            bot_name="Factory Bot"
        )

        assert isinstance(bot, DiscordBot)
        assert bot.token == "factory-token"
        assert bot.bot_name == "Factory Bot"
        assert bot._connected is False

        # Configure factory bot
        bot.set_event_channel(123456789)
        manager = MockServerManager()
        bot.set_server_manager(manager)

        # Verify configuration
        assert bot.event_channel_id == 123456789
        assert bot.server_manager is manager

        # Verify it supports lifecycle mocks
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.start = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.start = AsyncMock()
        bot._send_connection_notification = AsyncMock()

        async def trigger_ready():
            await asyncio.sleep(0.01)
            bot._ready.set()

        asyncio.create_task(trigger_ready())

        # Can connect
        await bot.connect_bot()
        assert bot._connected is True
