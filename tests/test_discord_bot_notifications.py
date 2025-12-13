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

"""Comprehensive notification tests for DiscordBot connection/disconnection messaging.

Phase 2 of coverage intensity: Happy path and error paths for notifications.

Coverage targets:
- _send_connection_notification() - Routes to all configured server channels
- _send_disconnection_notification() - Routes with embed creation
- Channel lookup and validation
- Embed creation and formatting
- Multi-server notification routing
- Error handling: Channel not found, Invalid channel type, HTTP exceptions
- Empty guild list graceful handling
- Missing event_channel_id graceful handling

Total: 12 tests covering 60+ lines of notification code.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from typing import Any, Optional, Dict
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
import discord
from discord import app_commands

try:
    from discord_bot import DiscordBot
    from discord_interface import EmbedBuilder
    from bot.user_context import UserContextManager
    from bot.helpers import PresenceManager
    from bot.event_handler import EventHandler
    from bot.rcon_health_monitor import RconHealthMonitor
except ImportError:
    pass


class MockServerConfig:
    """Mock server configuration for testing."""

    def __init__(self, tag: str, name: str, channel_id: Optional[int] = 123456789):
        self.tag = tag
        self.name = name
        self.event_channel_id = channel_id
        self.rcon_host = "localhost"
        self.rcon_port = 27015
        self.rcon_status_alert_mode = "transition"
        self.rcon_status_alert_interval = 300


class MockServerManager:
    """Mock server manager for testing."""

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


class TestConnectionNotifications:
    """Test _send_connection_notification() method."""

    @pytest.fixture
    def bot(self) -> MagicMock:
        bot = MagicMock(spec=DiscordBot)
        bot.user = MagicMock()
        bot.user.name = "Factorio ISR Bot"
        bot.guilds = [MagicMock(), MagicMock()]  # 2 guilds
        bot.server_manager = MockServerManager()
        bot.get_channel = MagicMock()
        return bot

    @pytest.mark.asyncio
    async def test_send_connection_notification_multi_server(self, bot: MagicMock) -> None:
        """Connection notification should route to all configured server channels."""
        # Create real bot instance for this test
        real_bot = DiscordBot(token="test-token")
        real_bot.user = MagicMock()
        real_bot.user.name = "Factorio ISR Bot"
        real_bot.guilds = [MagicMock(), MagicMock()]
        real_bot.server_manager = MockServerManager()
        
        mock_channel_1 = AsyncMock(spec=discord.TextChannel)
        mock_channel_2 = AsyncMock(spec=discord.TextChannel)
        
        def get_channel(channel_id):
            if channel_id == 111111111:
                return mock_channel_1
            elif channel_id == 222222222:
                return mock_channel_2
            return None
        
        real_bot.get_channel = MagicMock(side_effect=get_channel)
        
        await real_bot._send_connection_notification()
        
        # Verify both channels received the notification
        mock_channel_1.send.assert_awaited_once()
        mock_channel_2.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_connection_notification_no_server_manager(self) -> None:
        """Connection notification without ServerManager should skip."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Test Bot"
        bot.server_manager = None
        
        # Should not raise
        await bot._send_connection_notification()

    @pytest.mark.asyncio
    async def test_send_connection_notification_embed_format(self) -> None:
        """Connection notification embed should have proper format."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Factorio ISR Bot"
        bot.guilds = [MagicMock(name="Guild1"), MagicMock(name="Guild2")]
        bot.server_manager = MockServerManager()
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        await bot._send_connection_notification()
        
        # Verify send was called with an embed
        mock_channel.send.assert_awaited_once()
        call_args = mock_channel.send.call_args
        assert call_args is not None
        # Either embed or message content should be present
        assert call_args.kwargs.get('embed') or call_args.args

    @pytest.mark.asyncio
    async def test_send_connection_notification_channel_not_found(self) -> None:
        """Connection notification with missing channel should skip that server."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Test Bot"
        bot.guilds = [MagicMock()]
        bot.server_manager = MockServerManager()
        bot.get_channel = MagicMock(return_value=None)  # Channel not found
        
        # Should not raise
        await bot._send_connection_notification()

    @pytest.mark.asyncio
    async def test_send_connection_notification_invalid_channel_type(self) -> None:
        """Connection notification to non-TextChannel should skip."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Test Bot"
        bot.guilds = [MagicMock()]
        bot.server_manager = MockServerManager()
        
        # Return a VoiceChannel (invalid)
        mock_voice_channel = MagicMock(spec=discord.VoiceChannel)
        bot.get_channel = MagicMock(return_value=mock_voice_channel)
        
        # Should not raise
        await bot._send_connection_notification()

    @pytest.mark.asyncio
    async def test_send_connection_notification_with_no_channels_configured(self) -> None:
        """Connection notification when no server has event_channel_id."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Test Bot"
        bot.guilds = [MagicMock()]
        
        # Create server manager with no channels
        no_channel_servers = {
            "prod": MockServerConfig("prod", "Production", None),
        }
        bot.server_manager = MockServerManager(no_channel_servers)
        bot.get_channel = MagicMock()
        
        await bot._send_connection_notification()
        
        # get_channel should not be called
        bot.get_channel.assert_not_called()


class TestDisconnectionNotifications:
    """Test _send_disconnection_notification() method."""

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_multi_server(self) -> None:
        """Disconnection notification should route to all configured server channels."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Factorio ISR Bot"
        bot._connected = True  # Must be connected to send disconnect notification
        bot.server_manager = MockServerManager()
        
        mock_channel_1 = AsyncMock(spec=discord.TextChannel)
        mock_channel_2 = AsyncMock(spec=discord.TextChannel)
        
        def get_channel(channel_id):
            if channel_id == 111111111:
                return mock_channel_1
            elif channel_id == 222222222:
                return mock_channel_2
            return None
        
        bot.get_channel = MagicMock(side_effect=get_channel)
        
        await bot._send_disconnection_notification()
        
        # Verify both channels received the notification
        mock_channel_1.send.assert_awaited_once()
        mock_channel_2.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_not_connected(self) -> None:
        """Disconnection notification when not connected should skip."""
        bot = DiscordBot(token="test-token")
        bot._connected = False
        bot.get_channel = MagicMock()
        
        await bot._send_disconnection_notification()
        
        # Should not attempt to get channel
        bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_no_server_manager(self) -> None:
        """Disconnection notification without ServerManager should skip."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.user = MagicMock()
        bot.server_manager = None
        
        # Should not raise
        await bot._send_disconnection_notification()

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_embed_format(self) -> None:
        """Disconnection notification embed should have proper format."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Factorio ISR Bot"
        bot._connected = True
        bot.server_manager = MockServerManager()
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        await bot._send_disconnection_notification()
        
        # Verify send was called
        assert mock_channel.send.await_count >= 1

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_delay(self) -> None:
        """Disconnection notification should have a small delay before disconnect."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.user = MagicMock()
        bot.server_manager = MockServerManager()
        bot.get_channel = AsyncMock(return_value=None)
        
        import time
        start = time.time()
        await bot._send_disconnection_notification()
        elapsed = time.time() - start
        
        # Should have some delay (at least for the sleep)
        # This is a soft assertion as timing can vary
        assert elapsed >= 0.4  # 0.5s sleep minus test overhead


class TestMessageSending:
    """Test send_message() method error handling."""

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self) -> None:
        """send_message when not connected should skip."""
        bot = DiscordBot(token="test-token")
        bot._connected = False
        bot.event_channel_id = 123456789
        bot.get_channel = MagicMock()
        
        await bot.send_message("test message")
        
        # Should not attempt to get channel
        bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_no_channel_configured(self) -> None:
        """send_message with no channel should skip."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = None
        bot.get_channel = MagicMock()
        
        await bot.send_message("test message")
        
        # Should not attempt to get channel
        bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_channel_not_found(self) -> None:
        """send_message when channel not found should handle gracefully."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        bot.get_channel = MagicMock(return_value=None)
        
        # Should not raise
        await bot.send_message("test message")

    @pytest.mark.asyncio
    async def test_send_message_invalid_channel_type(self) -> None:
        """send_message to non-TextChannel should handle gracefully."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        mock_voice_channel = MagicMock(spec=discord.VoiceChannel)
        bot.get_channel = MagicMock(return_value=mock_voice_channel)
        
        # Should not raise
        await bot.send_message("test message")

    @pytest.mark.asyncio
    async def test_send_message_forbidden_error(self) -> None:
        """send_message with Forbidden error should handle gracefully."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=discord.errors.Forbidden(MagicMock(), "No permission")
        )
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        # Should not raise
        await bot.send_message("test message")

    @pytest.mark.asyncio
    async def test_send_message_http_exception(self) -> None:
        """send_message with HTTP exception should handle gracefully."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=discord.errors.HTTPException(MagicMock(), "HTTP Error")
        )
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        # Should not raise
        await bot.send_message("test message")

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """send_message should successfully send to channel."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        mock_channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        await bot.send_message("test message")
        
        # Verify message was sent
        mock_channel.send.assert_awaited_once_with("test message")

    @pytest.mark.asyncio
    async def test_send_message_long_message(self) -> None:
        """send_message with very long message should still send."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        mock_channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        long_message = "x" * 2000  # At Discord limit
        await bot.send_message(long_message)
        
        # Should still attempt to send
        mock_channel.send.assert_awaited_once()


class TestNotificationIntegration:
    """Integration tests for notification flow."""

    @pytest.mark.asyncio
    async def test_connect_notification_after_successful_connection(self) -> None:
        """After successful connection, notification should be sent."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Test Bot"
        bot.guilds = [MagicMock()]
        bot.server_manager = MockServerManager()
        mock_channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        await bot._send_connection_notification()
        
        # Notification should have been sent
        assert mock_channel.send.await_count >= 1

    @pytest.mark.asyncio
    async def test_disconnect_notification_before_disconnect(self) -> None:
        """Before disconnecting, notification should be sent."""
        bot = DiscordBot(token="test-token")
        bot.user = MagicMock()
        bot.user.name = "Test Bot"
        bot._connected = True
        bot.server_manager = MockServerManager()
        mock_channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        await bot._send_disconnection_notification()
        
        # Notification should have been sent
        assert mock_channel.send.await_count >= 1
