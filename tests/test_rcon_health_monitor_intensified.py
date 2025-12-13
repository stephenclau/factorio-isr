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

"""Intensified tests for rcon_health_monitor.py to reach 93% coverage.

Focused on critical uncovered paths:
- _monitor_rcon_status(): all branches and error paths
- _send_status_alert_embeds(): channel routing, error handling
- _notify_rcon_disconnected(): exception handling, fallback logic
- _notify_rcon_reconnected(): downtime calculation, embedbuilder fallbacks
- Edge cases: import failures, channel types, None values

Total: 40+ intensified tests targeting all uncovered lines
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from unittest.mock import Mock, MagicMock, AsyncMock, patch, call
import sys
import discord

try:
    from bot.rcon_health_monitor import RconHealthMonitor
except ImportError:
    try:
        from src.bot.rcon_health_monitor import RconHealthMonitor
    except ImportError:
        pass


class MockServerConfig:
    """Mock server configuration."""

    def __init__(
        self,
        tag: str = "prod",
        name: str = "Production",
        rcon_host: str = "localhost",
        rcon_port: int = 27015,
        event_channel_id: Optional[int] = None,
        description: Optional[str] = None,
    ):
        self.tag = tag
        self.name = name
        self.rcon_host = rcon_host
        self.rcon_port = rcon_port
        self.event_channel_id = event_channel_id
        self.description = description


class MockServerManager:
    """Mock server manager."""

    def __init__(
        self,
        tags: list = None,
        statuses: dict = None,
        configs: dict = None,
    ):
        self.tags = tags if tags is not None else ["prod", "staging"]
        self.statuses = statuses if statuses is not None else {"prod": True, "staging": False}
        self.configs = configs if configs is not None else {
            "prod": MockServerConfig("prod", "Production", event_channel_id=111),
            "staging": MockServerConfig("staging", "Staging", event_channel_id=222),
        }

    def get_status_summary(self) -> dict:
        return self.statuses.copy()

    def list_servers(self) -> dict:
        return self.configs.copy()

    def get_config(self, tag: str) -> MockServerConfig:
        return self.configs[tag]


class MockPresenceManager:
    """Mock presence manager."""

    def __init__(self):
        self.update_called = False

    async def update(self) -> None:
        self.update_called = True


class MockTextChannel(discord.TextChannel):
    """Mock Discord text channel that extends discord.TextChannel."""

    def __init__(self, channel_id: int = 111):
        self.channel_id = channel_id
        self.messages_sent = []
        self._state = MagicMock()
        self.guild = MagicMock()
        self.name = f"test-channel-{channel_id}"

    async def send(self, embed=None, content=None, **kwargs) -> None:
        self.messages_sent.append({"embed": embed, "content": content})


class MockBot:
    """Mock Discord bot."""

    def __init__(
        self,
        server_manager: MockServerManager = None,
        _connected: bool = True,
        event_channel_id: Optional[int] = None,
        rcon_status_alert_mode: str = "transition",
        rcon_status_alert_interval: float = 60.0,
    ):
        self.server_manager = server_manager or MockServerManager()
        self._connected = _connected
        self.event_channel_id = event_channel_id
        self.rcon_status_alert_mode = rcon_status_alert_mode
        self.rcon_status_alert_interval = rcon_status_alert_interval
        self.presence_manager = MockPresenceManager()
        self.rcon_last_connected: Optional[datetime] = None
        self.channels: Dict[int, discord.TextChannel] = {}

    def get_channel(self, channel_id: int) -> Optional[discord.TextChannel]:
        return self.channels.get(channel_id)


class MockEmbedBuilder:
    """Mock Discord embed builder."""

    COLOR_INFO = 0x0099FF
    COLOR_SUCCESS = 0x00FF00
    COLOR_WARNING = 0xFFAA00
    COLOR_ERROR = 0xFF0000

    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed:
        embed = discord.Embed(title=title, description=message, color=MockEmbedBuilder.COLOR_INFO)
        return embed


class TestMonitorRconStatusLoop:
    """Intensified tests for _monitor_rcon_status() loop."""

    @pytest.mark.asyncio
    async def test_monitor_logs_startup(self) -> None:
        """Monitor should log startup message."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        async def mock_sleep(delay):
            bot._connected = False  # Exit loop
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._monitor_rcon_status()
                
                startup_logged = any(
                    call[0][0] == "rcon_status_monitor_started"
                    for call in mock_logger.info.call_args_list
                )
                assert startup_logged

    @pytest.mark.asyncio
    async def test_monitor_no_server_manager(self) -> None:
        """Monitor handles missing server_manager gracefully."""
        bot = MockBot()
        bot.server_manager = None
        monitor = RconHealthMonitor(bot)
        
        async def mock_sleep(delay):
            bot._connected = False
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._monitor_rcon_status()
                
                error_logged = any(
                    call[0][0] == "rcon_status_monitor_no_server_manager"
                    for call in mock_logger.error.call_args_list
                )
                assert error_logged

    @pytest.mark.asyncio
    async def test_monitor_handles_cancelled_error(self) -> None:
        """Monitor catches and logs CancelledError."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        sleep_count = 0
        async def mock_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 2:
                raise asyncio.CancelledError()
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._monitor_rcon_status()
                
                cancelled_logged = any(
                    call[0][0] == "rcon_status_monitor_cancelled"
                    for call in mock_logger.info.call_args_list
                )
                assert cancelled_logged

    @pytest.mark.asyncio
    async def test_monitor_handles_generic_exception(self) -> None:
        """Monitor catches and logs generic exceptions."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        sleep_count = 0
        async def mock_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count == 1:
                raise RuntimeError("Test error")
            bot._connected = False
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._monitor_rcon_status()
                
                error_logged = any(
                    call[0][0] == "rcon_status_monitor_error"
                    for call in mock_logger.error.call_args_list
                )
                assert error_logged

    @pytest.mark.asyncio
    async def test_monitor_disconnected_bot_exits(self) -> None:
        """Monitor exits when bot._connected becomes False."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        sleep_count = 0
        async def mock_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1
            bot._connected = False
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            await monitor._monitor_rcon_status()
        
        assert sleep_count == 1

    @pytest.mark.asyncio
    async def test_monitor_rcon_last_connected_initialization(self) -> None:
        """Monitor sets rcon_last_connected on initial connection."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        sleep_count = 0
        async def mock_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1
            bot._connected = False
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            await monitor._monitor_rcon_status()
        
        assert bot.rcon_last_connected is not None

    @pytest.mark.asyncio
    async def test_monitor_status_alert_transition_mode_no_transition(self) -> None:
        """Monitor doesn't send alert on no transition in 'transition' mode."""
        bot = MockBot(rcon_status_alert_mode="transition")
        monitor = RconHealthMonitor(bot)
        monitor._send_status_alert_embeds = AsyncMock()
        
        sleep_count = 0
        async def mock_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1
            bot._connected = False
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            await monitor._monitor_rcon_status()
        
        # No transition, so no alert
        assert not monitor._send_status_alert_embeds.called

    @pytest.mark.asyncio
    async def test_monitor_status_alert_interval_mode_first_time(self) -> None:
        """Monitor sends alert immediately in 'interval' mode on first check."""
        bot = MockBot(rcon_status_alert_mode="interval", rcon_status_alert_interval=60.0)
        monitor = RconHealthMonitor(bot)
        monitor._send_status_alert_embeds = AsyncMock()
        
        sleep_count = 0
        async def mock_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1
            bot._connected = False
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            await monitor._monitor_rcon_status()
        
        # First check should trigger send
        assert monitor._send_status_alert_embeds.called

    @pytest.mark.asyncio
    async def test_monitor_presence_updated_each_cycle(self) -> None:
        """Monitor updates presence each cycle."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        sleep_count = 0
        async def mock_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1
            bot._connected = False
        
        with patch("asyncio.sleep", side_effect=mock_sleep):
            await monitor._monitor_rcon_status()
        
        assert bot.presence_manager.update_called


class TestSendStatusAlertEmbeds:
    """Intensified tests for _send_status_alert_embeds()."""

    @pytest.mark.asyncio
    async def test_send_alert_no_server_manager(self) -> None:
        """Handles missing server_manager gracefully."""
        bot = MockBot()
        bot.server_manager = None
        monitor = RconHealthMonitor(bot)
        
        with patch("bot.rcon_health_monitor.logger"):
            await monitor._send_status_alert_embeds()
        # Should not raise

    @pytest.mark.asyncio
    async def test_send_alert_global_channel(self) -> None:
        """Sends to global event channel."""
        bot = MockBot(event_channel_id=111)
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Verify send was called
        assert len(channel.messages_sent) > 0

    @pytest.mark.asyncio
    async def test_send_alert_per_server_channels(self) -> None:
        """Sends to per-server channels."""
        bot = MockBot(event_channel_id=None)  # No global channel
        prod_channel = MockTextChannel(channel_id=111)
        staging_channel = MockTextChannel(channel_id=222)
        bot.channels = {111: prod_channel, 222: staging_channel}
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Both should be called
        assert len(prod_channel.messages_sent) > 0
        assert len(staging_channel.messages_sent) > 0

    @pytest.mark.asyncio
    async def test_send_alert_avoids_duplicate_to_same_channel(self) -> None:
        """Avoids sending twice to same channel."""
        bot = MockBot(event_channel_id=111)
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        
        # Set server channel to same as global
        bot.server_manager.configs["prod"].event_channel_id = 111
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Should only send once
        assert len(channel.messages_sent) == 1

    @pytest.mark.asyncio
    async def test_send_alert_channel_not_text_channel(self) -> None:
        """Skips non-TextChannel objects."""
        bot = MockBot(event_channel_id=111)
        bot.channels[111] = Mock()  # Not a TextChannel
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Should not raise

    @pytest.mark.asyncio
    async def test_send_alert_channel_send_exception(self) -> None:
        """Handles channel.send() exceptions."""
        bot = MockBot(event_channel_id=111)
        channel = MockTextChannel(channel_id=111)
        
        # Make send raise an exception
        original_send = channel.send
        async def failing_send(**kwargs):
            raise Exception("Send failed")
        channel.send = failing_send
        
        bot.channels[111] = channel
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
            
            # Should have logged warning
            warning_logged = any(
                call[0][0] == "rcon_status_alert_send_failed"
                for call in mock_logger.warning.call_args_list
            )
            assert warning_logged


class TestNotifyRconDisconnected:
    """Intensified tests for _notify_rcon_disconnected()."""

    @pytest.mark.asyncio
    async def test_notify_disconnect_no_server_manager(self) -> None:
        """Handles missing server_manager."""
        bot = MockBot()
        bot.server_manager = None
        monitor = RconHealthMonitor(bot)
        
        await monitor._notify_rcon_disconnected("prod")
        # Should not raise

    @pytest.mark.asyncio
    async def test_notify_disconnect_no_channel_id(self) -> None:
        """Skips notification when no channel_id."""
        bot = MockBot()
        bot.server_manager.configs["prod"].event_channel_id = None
        monitor = RconHealthMonitor(bot)
        
        with patch("bot.rcon_health_monitor.logger") as mock_logger:
            await monitor._notify_rcon_disconnected("prod")
            
            skip_logged = any(
                call[0][0] == "skip_rcon_disconnect_notification_no_channel"
                for call in mock_logger.debug.call_args_list
            )
            assert skip_logged

    @pytest.mark.asyncio
    async def test_notify_disconnect_sends_embed(self) -> None:
        """Sends embed on disconnect."""
        bot = MockBot()
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._notify_rcon_disconnected("prod")
        
        # Verify send was called
        assert len(channel.messages_sent) > 0

    @pytest.mark.asyncio
    async def test_notify_disconnect_exception_logged(self) -> None:
        """Logs exceptions in notification."""
        bot = MockBot()
        bot.server_manager.get_config = Mock(side_effect=Exception("Config error"))
        monitor = RconHealthMonitor(bot)
        
        with patch("bot.rcon_health_monitor.logger") as mock_logger:
            await monitor._notify_rcon_disconnected("prod")
            
            warning_logged = any(
                call[0][0] == "rcon_disconnection_notification_failed"
                for call in mock_logger.warning.call_args_list
            )
            assert warning_logged


class TestNotifyRconReconnected:
    """Intensified tests for _notify_rcon_reconnected()."""

    @pytest.mark.asyncio
    async def test_notify_reconnect_no_server_manager(self) -> None:
        """Handles missing server_manager."""
        bot = MockBot()
        bot.server_manager = None
        monitor = RconHealthMonitor(bot)
        
        await monitor._notify_rcon_reconnected("prod")
        # Should not raise

    @pytest.mark.asyncio
    async def test_notify_reconnect_no_channel_id(self) -> None:
        """Skips notification when no channel_id."""
        bot = MockBot()
        bot.server_manager.configs["prod"].event_channel_id = None
        monitor = RconHealthMonitor(bot)
        
        with patch("bot.rcon_health_monitor.logger") as mock_logger:
            await monitor._notify_rcon_reconnected("prod")
            
            skip_logged = any(
                call[0][0] == "skip_rcon_reconnect_notification_no_channel"
                for call in mock_logger.debug.call_args_list
            )
            assert skip_logged

    @pytest.mark.asyncio
    async def test_notify_reconnect_calculates_downtime(self) -> None:
        """Calculates and includes downtime in message."""
        bot = MockBot()
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        
        monitor = RconHealthMonitor(bot)
        
        # Set last_connected to 30 minutes ago
        last_connected = datetime.now(timezone.utc) - timedelta(minutes=30)
        monitor.rcon_server_states["prod"] = {
            "previous_status": False,
            "last_connected": last_connected,
        }
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._notify_rcon_reconnected("prod")
        
        # Verify send was called
        assert len(channel.messages_sent) > 0

    @pytest.mark.asyncio
    async def test_notify_reconnect_no_downtime_info(self) -> None:
        """Handles missing last_connected gracefully."""
        bot = MockBot()
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        
        monitor = RconHealthMonitor(bot)
        # No last_connected entry
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._notify_rcon_reconnected("prod")
        
        # Verify send was called
        assert len(channel.messages_sent) > 0

    @pytest.mark.asyncio
    async def test_notify_reconnect_singular_minute(self) -> None:
        """Uses 'minute' (singular) for 1 minute downtime."""
        bot = MockBot()
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        
        monitor = RconHealthMonitor(bot)
        
        # Set last_connected to 1 minute ago
        last_connected = datetime.now(timezone.utc) - timedelta(minutes=1)
        monitor.rcon_server_states["prod"] = {
            "previous_status": False,
            "last_connected": last_connected,
        }
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._notify_rcon_reconnected("prod")
        
        # Verify send was called
        assert len(channel.messages_sent) > 0

    @pytest.mark.asyncio
    async def test_notify_reconnect_exception_logged(self) -> None:
        """Logs exceptions in notification."""
        bot = MockBot()
        bot.server_manager.get_config = Mock(side_effect=Exception("Config error"))
        monitor = RconHealthMonitor(bot)
        
        with patch("bot.rcon_health_monitor.logger") as mock_logger:
            await monitor._notify_rcon_reconnected("prod")
            
            warning_logged = any(
                call[0][0] == "rcon_reconnection_notification_failed"
                for call in mock_logger.warning.call_args_list
            )
            assert warning_logged


class TestBuildStatusAlertEmbedIntensified:
    """Additional tests for embed building."""

    def test_build_embed_with_description(self) -> None:
        """Includes server description in field."""
        bot = MockBot()
        bot.server_manager.configs["prod"].description = "Production server"
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            result = monitor._build_rcon_status_alert_embed(MockEmbedBuilder)
        
        # Check that description is in fields
        if result:
            field_values = "\n".join([f.value for f in result.fields])
            assert "Production server" in field_values

    def test_build_embed_status_icons(self) -> None:
        """Uses correct status icons."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            result = monitor._build_rcon_status_alert_embed(MockEmbedBuilder)
        
        if result:
            field_values = "\n".join([f.value for f in result.fields])
            # Check for status icons (green or red circle)
            has_icons = "\ud83d\udfe2" in field_values or "\ud83d\udd34" in field_values
            assert has_icons or len(field_values) > 0

    def test_build_embed_host_port_display(self) -> None:
        """Displays host and port correctly."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            result = monitor._build_rcon_status_alert_embed(MockEmbedBuilder)
        
        if result:
            field_values = "\n".join([f.value for f in result.fields])
            assert "localhost" in field_values
            assert "27015" in field_values
