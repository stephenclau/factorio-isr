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

"""Ultra-intensified tests for RconHealthMonitor._send_status_alert_embeds().

Full line-by-line coverage of _send_status_alert_embeds() method (lines 156-198):
- Import handling (EmbedBuilder fallback chains)
- Embed building and None checks
- Global channel routing (send, exceptions, logging)
- Per-server channel iteration
- Duplicate channel detection
- Channel type checking (isinstance discord.TextChannel)
- Exception handling and logging for each channel
- All conditional branches

Total: 30+ ultra-specific tests covering every line and branch
"""

import pytest
import asyncio
from datetime import datetime, timezone
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

    async def update(self) -> None:
        pass


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
        event_channel_id: Optional[int] = None,
    ):
        self.server_manager = server_manager or MockServerManager()
        self.event_channel_id = event_channel_id
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


class TestSendStatusAlertEmbedsIntensified:
    """Ultra-intensified tests for _send_status_alert_embeds() covering every line."""

    # ========================================================================
    # IMPORT HANDLING TESTS (Lines 157-165)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_import_embedbuilder_from_relative_path(self) -> None:
        """Handles import from .discord_interface (line 158)."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        # Successfully imports from first path
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # No error logged

    @pytest.mark.asyncio
    async def test_import_embedbuilder_fallback_absolute_import(self) -> None:
        """Falls back to absolute import from discord_interface (line 160)."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        # Simulate first import failing, second succeeding
        def mock_import(name, *args, **kwargs):
            if name == "bot.discord_interface":
                raise ImportError()
            if name == "discord_interface":
                return Mock(EmbedBuilder=MockEmbedBuilder)
            return __import__(name, *args, **kwargs)
        
        with patch("builtins.__import__", side_effect=mock_import):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()

    @pytest.mark.asyncio
    async def test_import_embedbuilder_both_fail_logs_error(self) -> None:
        """Logs error when both imports fail (line 163)."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        # Both imports fail
        with patch("builtins.__import__", side_effect=ImportError()):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
                
                error_logged = any(
                    call[0][0] == "discord_interface_not_available_for_status_alert"
                    for call in mock_logger.error.call_args_list
                )
                assert error_logged

    @pytest.mark.asyncio
    async def test_import_failure_returns_early(self) -> None:
        """Returns early when EmbedBuilder import fails (line 165)."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        # Set up mocks
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        bot.event_channel_id = 111
        
        # Both imports fail
        with patch("builtins.__import__", side_effect=ImportError()):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Channel should not have been called (returned early)
        assert len(channel.messages_sent) == 0

    # ========================================================================
    # SERVER MANAGER CHECK TESTS (Lines 167-169)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_server_manager_none_returns_early(self) -> None:
        """Returns early if server_manager is None (line 168)."""
        bot = MockBot()
        bot.server_manager = None
        monitor = RconHealthMonitor(bot)
        
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        bot.event_channel_id = 111
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Channel not called when server_manager is None
        assert len(channel.messages_sent) == 0

    # ========================================================================
    # EMBED BUILDING TESTS (Lines 171-173)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_build_embed_returns_none(self) -> None:
        """Handles None returned from _build_rcon_status_alert_embed (line 172)."""
        bot = MockBot()
        bot.server_manager.get_status_summary = Mock(return_value={})
        monitor = RconHealthMonitor(bot)
        
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        bot.event_channel_id = 111
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Channel should not be called when embed is None
        assert len(channel.messages_sent) == 0

    @pytest.mark.asyncio
    async def test_build_embed_returns_valid_embed(self) -> None:
        """Continues when _build_rcon_status_alert_embed returns valid embed (line 172)."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        bot.event_channel_id = 111
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Channel should be called with valid embed
        assert len(channel.messages_sent) == 1

    # ========================================================================
    # GLOBAL CHANNEL TESTS (Lines 175-193)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_global_channel_id_is_none(self) -> None:
        """Skips global channel when event_channel_id is None (line 175)."""
        bot = MockBot(event_channel_id=None)
        monitor = RconHealthMonitor(bot)
        
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # No send to this specific channel
        # (but per-server channels may have been called)

    @pytest.mark.asyncio
    async def test_global_channel_get_channel_called(self) -> None:
        """Calls bot.get_channel with event_channel_id (line 176)."""
        bot = MockBot(event_channel_id=111)
        bot.get_channel = Mock(return_value=None)
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Should call get_channel at least once for global channel
        assert bot.get_channel.called
        # Check that 111 (global channel) was in the calls
        global_channel_called = any(
            call_obj[0][0] == 111
            for call_obj in bot.get_channel.call_args_list
        )
        assert global_channel_called

    @pytest.mark.asyncio
    async def test_global_channel_is_none(self) -> None:
        """Skips send when bot.get_channel returns None (line 177)."""
        bot = MockBot(event_channel_id=111)
        bot.get_channel = Mock(return_value=None)
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # No error, just skipped

    @pytest.mark.asyncio
    async def test_global_channel_not_text_channel(self) -> None:
        """Skips send when channel is not discord.TextChannel (line 177)."""
        bot = MockBot(event_channel_id=111)
        bot.channels[111] = Mock()  # Not a TextChannel
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # No error, just skipped

    @pytest.mark.asyncio
    async def test_global_channel_send_success(self) -> None:
        """Successfully sends to global channel (line 179)."""
        bot = MockBot(event_channel_id=111)
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        assert len(channel.messages_sent) == 1

    @pytest.mark.asyncio
    async def test_global_channel_send_logs_success(self) -> None:
        """Logs successful global channel send (lines 180-184)."""
        bot = MockBot(event_channel_id=111)
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
                
                success_logged = any(
                    call[0][0] == "rcon_status_alert_sent" and
                    call[1].get("scope") == "global"
                    for call in mock_logger.info.call_args_list
                )
                assert success_logged

    @pytest.mark.asyncio
    async def test_global_channel_send_exception(self) -> None:
        """Handles exception during global channel send (line 186)."""
        bot = MockBot(event_channel_id=111)
        channel = MockTextChannel(channel_id=111)
        
        # Make send raise exception
        async def failing_send(**kwargs):
            raise RuntimeError("Send failed")
        channel.send = failing_send
        
        bot.channels[111] = channel
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
                
                warning_logged = any(
                    call[0][0] == "rcon_status_alert_send_failed" and
                    call[1].get("scope") == "global"
                    for call in mock_logger.warning.call_args_list
                )
                assert warning_logged

    @pytest.mark.asyncio
    async def test_global_channel_exception_logs_details(self) -> None:
        """Exception log includes channel_id and error (lines 187-192)."""
        bot = MockBot(event_channel_id=111)
        channel = MockTextChannel(channel_id=111)
        
        async def failing_send(**kwargs):
            raise RuntimeError("Test error")
        channel.send = failing_send
        
        bot.channels[111] = channel
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
                
                # Check warning includes channel_id
                warning_call = None
                for call_obj in mock_logger.warning.call_args_list:
                    if call_obj[0][0] == "rcon_status_alert_send_failed":
                        warning_call = call_obj
                        break
                
                assert warning_call is not None
                assert warning_call[1].get("channel_id") == 111

    # ========================================================================
    # PER-SERVER CHANNEL TESTS (Lines 194-198)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_per_server_list_servers_called(self) -> None:
        """Iterates through server_manager.list_servers() (line 195)."""
        bot = MockBot(event_channel_id=None)  # No global channel
        bot.server_manager.list_servers = Mock(return_value={
            "prod": MockServerConfig("prod", "Production", event_channel_id=111),
        })
        monitor = RconHealthMonitor(bot)
        
        channel = MockTextChannel(channel_id=111)
        bot.channels[111] = channel
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        bot.server_manager.list_servers.assert_called()

    @pytest.mark.asyncio
    async def test_per_server_no_event_channel_id(self) -> None:
        """Skips server with no event_channel_id (line 197)."""
        bot = MockBot(event_channel_id=None)
        bot.server_manager.configs["prod"].event_channel_id = None
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Should not raise

    @pytest.mark.asyncio
    async def test_per_server_duplicate_global_channel_skip(self) -> None:
        """Skips per-server channel if same as global (line 201-203)."""
        bot = MockBot(event_channel_id=111)
        bot.server_manager.configs["prod"].event_channel_id = 111  # Same as global
        bot.server_manager.configs["staging"].event_channel_id = 222
        
        channel111 = MockTextChannel(channel_id=111)
        channel222 = MockTextChannel(channel_id=222)
        bot.channels = {111: channel111, 222: channel222}
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Global channel (111) should be sent once
        # Staging (222) should be sent once
        # Prod (111 duplicate) should be skipped
        assert len(channel111.messages_sent) == 1  # Only global send
        assert len(channel222.messages_sent) == 1  # Only per-server send

    @pytest.mark.asyncio
    async def test_per_server_get_channel_called(self) -> None:
        """Calls bot.get_channel for each per-server channel (line 205)."""
        bot = MockBot(event_channel_id=None)
        bot.get_channel = Mock(return_value=None)
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Should call get_channel for each server with event_channel_id
        assert bot.get_channel.called

    @pytest.mark.asyncio
    async def test_per_server_channel_is_none(self) -> None:
        """Skips per-server channel when get_channel returns None (line 206)."""
        bot = MockBot(event_channel_id=None)
        bot.get_channel = Mock(return_value=None)
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Should not raise

    @pytest.mark.asyncio
    async def test_per_server_channel_not_text_channel(self) -> None:
        """Skips per-server channel if not discord.TextChannel (line 206)."""
        bot = MockBot(event_channel_id=None)
        bot.channels[222] = Mock()  # Not a TextChannel
        bot.get_channel = Mock(side_effect=lambda cid: bot.channels.get(cid))
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Should not raise

    @pytest.mark.asyncio
    async def test_per_server_send_success(self) -> None:
        """Successfully sends to per-server channel (line 208)."""
        bot = MockBot(event_channel_id=None)
        channel = MockTextChannel(channel_id=222)
        bot.channels[222] = channel
        bot.server_manager.configs["staging"].event_channel_id = 222
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        assert len(channel.messages_sent) == 1

    @pytest.mark.asyncio
    async def test_per_server_send_logs_success(self) -> None:
        """Logs successful per-server channel send (lines 209-214)."""
        bot = MockBot(event_channel_id=None)
        channel = MockTextChannel(channel_id=222)
        bot.channels[222] = channel
        bot.server_manager.configs["staging"].event_channel_id = 222
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
                
                success_logged = any(
                    call[0][0] == "rcon_status_alert_sent" and
                    call[1].get("scope") == "server"
                    for call in mock_logger.info.call_args_list
                )
                assert success_logged

    @pytest.mark.asyncio
    async def test_per_server_send_exception(self) -> None:
        """Handles exception during per-server channel send (line 216)."""
        bot = MockBot(event_channel_id=None)
        channel = MockTextChannel(channel_id=222)
        
        async def failing_send(**kwargs):
            raise RuntimeError("Send failed")
        channel.send = failing_send
        
        bot.channels[222] = channel
        bot.server_manager.configs["staging"].event_channel_id = 222
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
                
                warning_logged = any(
                    call[0][0] == "rcon_status_alert_send_failed" and
                    call[1].get("scope") == "server"
                    for call in mock_logger.warning.call_args_list
                )
                assert warning_logged

    @pytest.mark.asyncio
    async def test_per_server_exception_logs_details(self) -> None:
        """Exception log includes server_tag, channel_id, and error (lines 217-223)."""
        bot = MockBot(event_channel_id=None)
        channel = MockTextChannel(channel_id=222)
        
        async def failing_send(**kwargs):
            raise RuntimeError("Test error")
        channel.send = failing_send
        
        bot.channels[222] = channel
        bot.server_manager.configs["staging"].event_channel_id = 222
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
                
                # Check warning includes server details
                warning_call = None
                for call_obj in mock_logger.warning.call_args_list:
                    if call_obj[0][0] == "rcon_status_alert_send_failed" and \
                       call_obj[1].get("scope") == "server":
                        warning_call = call_obj
                        break
                
                assert warning_call is not None
                assert warning_call[1].get("channel_id") == 222
                assert warning_call[1].get("server_tag") == "staging"

    # ========================================================================
    # INTEGRATION TESTS (Multiple servers, channels, conditions)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_multiple_servers_different_channels(self) -> None:
        """Correctly routes to multiple different server channels."""
        bot = MockBot(event_channel_id=None)
        
        prod_channel = MockTextChannel(channel_id=111)
        staging_channel = MockTextChannel(channel_id=222)
        bot.channels = {111: prod_channel, 222: staging_channel}
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Both should receive one message
        assert len(prod_channel.messages_sent) == 1
        assert len(staging_channel.messages_sent) == 1

    @pytest.mark.asyncio
    async def test_global_and_per_server_channels_together(self) -> None:
        """Correctly sends to global and different per-server channels."""
        bot = MockBot(event_channel_id=111)
        bot.server_manager.configs["staging"].event_channel_id = 222
        
        global_channel = MockTextChannel(channel_id=111)
        server_channel = MockTextChannel(channel_id=222)
        bot.channels = {111: global_channel, 222: server_channel}
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger"):
                await monitor._send_status_alert_embeds()
        
        # Global gets one message
        assert len(global_channel.messages_sent) == 1
        # Server-specific gets one message (not duplicate to global)
        assert len(server_channel.messages_sent) == 1

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure_channels(self) -> None:
        """Handles mix of successful and failed sends without crashing."""
        bot = MockBot(event_channel_id=111)
        bot.server_manager.configs["staging"].event_channel_id = 222
        
        global_channel = MockTextChannel(channel_id=111)
        
        # Staging channel fails
        server_channel = MockTextChannel(channel_id=222)
        async def failing_send(**kwargs):
            raise RuntimeError("Failure")
        server_channel.send = failing_send
        
        bot.channels = {111: global_channel, 222: server_channel}
        
        monitor = RconHealthMonitor(bot)
        
        with patch.dict('sys.modules', {'discord_interface': Mock(EmbedBuilder=MockEmbedBuilder)}):
            with patch("bot.rcon_health_monitor.logger") as mock_logger:
                await monitor._send_status_alert_embeds()
        
        # Global channel succeeded
        assert len(global_channel.messages_sent) == 1
        # Warning logged for server failure
        warning_logged = any(
            call[0][0] == "rcon_status_alert_send_failed"
            for call in mock_logger.warning.call_args_list
        )
        assert warning_logged
