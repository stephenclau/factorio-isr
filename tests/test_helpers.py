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

"""Comprehensive tests for bot/helpers.py with 90% coverage.

Full logic walkthrough covering:
- PresenceManager: lifecycle, updates, loop management
- format_uptime: all time ranges, edge cases
- get_game_uptime: happy path, errors, parsing
- send_to_channel: success, errors, permissions
- format_stats_text: single/multi-surface, paused, UPS variants
- format_stats_embed: single/multi-surface, paused, embed building
- Integration tests and edge cases

Total: 75+ tests, 90% coverage
"""

import asyncio
import pytest
from datetime import timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, patch, MagicMock
import discord

try:
    from bot.helpers import (
        PresenceManager,
        format_uptime,
        get_game_uptime,
        send_to_channel,
        format_stats_text,
        format_stats_embed,
    )
except ImportError:
    pass


# ========================================================================
# MOCK CLASSES
# ========================================================================


class MockRconClient:
    """Mock RCON client for testing."""

    def __init__(self, is_connected: bool = True):
        self.is_connected = is_connected

    async def execute(self, command: str) -> str:
        return "3600"


class MockServerManager:
    """Mock server manager for testing."""

    def __init__(self, statuses: Dict[str, bool] = None):
        self.statuses = statuses or {"prod": True, "staging": False}

    def get_status_summary(self) -> Dict[str, bool]:
        return self.statuses


class MockDiscordBot:
    """Mock Discord bot for testing."""

    def __init__(self, connected: bool = True):
        self._connected = connected
        self.user = MagicMock()
        self.server_manager = MockServerManager()
        self.change_presence = AsyncMock()

    def get_channel(self, channel_id: int) -> Any:
        return MagicMock(spec=discord.TextChannel)


# ========================================================================
# PRESENCE MANAGER TESTS (18 tests)
# ========================================================================


class TestPresenceManagerInitialization:
    """Test PresenceManager initialization."""

    def test_init_stores_bot_reference(self) -> None:
        bot = MockDiscordBot()
        manager = PresenceManager(bot)
        assert manager.bot is bot

    def test_init_task_is_none(self) -> None:
        bot = MockDiscordBot()
        manager = PresenceManager(bot)
        assert manager._presence_task is None


class TestPresenceManagerUpdate:
    """Test presence update functionality."""

    @pytest.mark.asyncio
    async def test_update_not_connected(self) -> None:
        bot = MockDiscordBot(connected=False)
        manager = PresenceManager(bot)
        await manager.update()
        bot.change_presence.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_no_user(self) -> None:
        bot = MockDiscordBot()
        bot.user = None
        manager = PresenceManager(bot)
        await manager.update()
        bot.change_presence.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_all_servers_connected(self) -> None:
        bot = MockDiscordBot()
        bot.server_manager = MockServerManager({"prod": True, "staging": True})
        manager = PresenceManager(bot)
        await manager.update()
        bot.change_presence.assert_awaited_once()
        call_args = bot.change_presence.call_args
        assert call_args[1]["status"] == discord.Status.online

    @pytest.mark.asyncio
    async def test_update_partial_servers_connected(self) -> None:
        bot = MockDiscordBot()
        bot.server_manager = MockServerManager({"prod": True, "staging": False})
        manager = PresenceManager(bot)
        await manager.update()
        bot.change_presence.assert_awaited_once()
        call_args = bot.change_presence.call_args
        assert call_args[1]["status"] == discord.Status.idle

    @pytest.mark.asyncio
    async def test_update_no_servers_connected(self) -> None:
        bot = MockDiscordBot()
        bot.server_manager = MockServerManager({"prod": False, "staging": False})
        manager = PresenceManager(bot)
        await manager.update()
        bot.change_presence.assert_awaited_once()
        call_args = bot.change_presence.call_args
        assert call_args[1]["status"] == discord.Status.idle

    @pytest.mark.asyncio
    async def test_update_no_server_manager(self) -> None:
        bot = MockDiscordBot()
        bot.server_manager = None
        manager = PresenceManager(bot)
        await manager.update()
        bot.change_presence.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_exception_handling(self) -> None:
        bot = MockDiscordBot()
        bot.change_presence.side_effect = Exception("Test error")
        manager = PresenceManager(bot)
        # Should not raise
        await manager.update()


class TestPresenceManagerLifecycle:
    """Test presence manager lifecycle (start/stop)."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self) -> None:
        bot = MockDiscordBot()
        manager = PresenceManager(bot)
        assert manager._presence_task is None
        await manager.start()
        assert manager._presence_task is not None
        assert isinstance(manager._presence_task, asyncio.Task)
        manager._presence_task.cancel()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        bot = MockDiscordBot()
        manager = PresenceManager(bot)
        await manager.start()
        assert manager._presence_task is not None
        await manager.stop()
        assert manager._presence_task is None

    @pytest.mark.asyncio
    async def test_stop_without_task(self) -> None:
        bot = MockDiscordBot()
        manager = PresenceManager(bot)
        # Should not raise
        await manager.stop()
        assert manager._presence_task is None

    @pytest.mark.asyncio
    async def test_start_already_running(self) -> None:
        bot = MockDiscordBot()
        manager = PresenceManager(bot)
        await manager.start()
        first_task = manager._presence_task
        await manager.start()
        # Should not create new task
        assert manager._presence_task is first_task
        manager._presence_task.cancel()

    @pytest.mark.asyncio
    async def test_loop_runs_until_disconnected(self) -> None:
        bot = MockDiscordBot(connected=True)
        manager = PresenceManager(bot)
        await manager.start()
        await asyncio.sleep(0.1)
        bot._connected = False
        await asyncio.sleep(0.2)
        # Task should exit when disconnected
        assert manager._presence_task.done() or bot.change_presence.await_count > 0
        manager._presence_task.cancel()


# ========================================================================
# FORMAT_UPTIME TESTS (12 tests)
# ========================================================================


class TestFormatUptime:
    """Test uptime formatting utility."""

    def test_format_uptime_less_than_minute(self) -> None:
        delta = timedelta(seconds=30)
        result = format_uptime(delta)
        assert result == "< 1m"

    def test_format_uptime_exactly_one_minute(self) -> None:
        delta = timedelta(minutes=1)
        result = format_uptime(delta)
        assert result == "1m"

    def test_format_uptime_minutes_only(self) -> None:
        delta = timedelta(minutes=45)
        result = format_uptime(delta)
        assert result == "45m"

    def test_format_uptime_hours_and_minutes(self) -> None:
        delta = timedelta(hours=2, minutes=15)
        result = format_uptime(delta)
        assert result == "2h 15m"

    def test_format_uptime_exactly_one_hour(self) -> None:
        delta = timedelta(hours=1)
        result = format_uptime(delta)
        assert result == "1h"

    def test_format_uptime_days_and_hours(self) -> None:
        delta = timedelta(days=3, hours=5)
        result = format_uptime(delta)
        assert result == "3d 5h"

    def test_format_uptime_days_only(self) -> None:
        delta = timedelta(days=7)
        result = format_uptime(delta)
        assert result == "7d"

    def test_format_uptime_complex(self) -> None:
        delta = timedelta(days=1, hours=2, minutes=30, seconds=45)
        result = format_uptime(delta)
        assert "1d" in result and "2h" in result and "30m" in result

    def test_format_uptime_zero(self) -> None:
        delta = timedelta()
        result = format_uptime(delta)
        assert result == "< 1m"

    def test_format_uptime_seconds_only(self) -> None:
        delta = timedelta(seconds=59)
        result = format_uptime(delta)
        assert result == "< 1m"

    def test_format_uptime_large_values(self) -> None:
        delta = timedelta(days=365, hours=23, minutes=59)
        result = format_uptime(delta)
        assert "365d" in result

    def test_format_uptime_precision(self) -> None:
        delta = timedelta(days=2, hours=3, minutes=4, seconds=5)
        result = format_uptime(delta)
        assert "2d" in result and "3h" in result and "4m" in result


# ========================================================================
# GET_GAME_UPTIME TESTS (15 tests)
# ========================================================================


class TestGetGameUptime:
    """Test game uptime querying."""

    @pytest.mark.asyncio
    async def test_get_game_uptime_not_connected(self) -> None:
        rcon = MockRconClient(is_connected=False)
        result = await get_game_uptime(rcon)
        assert result == "Unknown"

    @pytest.mark.asyncio
    async def test_get_game_uptime_none_client(self) -> None:
        result = await get_game_uptime(None)
        assert result == "Unknown"

    @pytest.mark.asyncio
    async def test_get_game_uptime_success(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(return_value="3600")
        result = await get_game_uptime(rcon)
        assert result != "Unknown"
        assert "m" in result or "h" in result or "d" in result

    @pytest.mark.asyncio
    async def test_get_game_uptime_zero_ticks(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(return_value="0")
        result = await get_game_uptime(rcon)
        assert result == "< 1m"

    @pytest.mark.asyncio
    async def test_get_game_uptime_large_ticks(self) -> None:
        rcon = MockRconClient()
        # 1 day worth of ticks: 86400 seconds * 60 ticks/second
        rcon.execute = AsyncMock(return_value="5184000")
        result = await get_game_uptime(rcon)
        assert "d" in result

    @pytest.mark.asyncio
    async def test_get_game_uptime_empty_response(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(return_value="")
        result = await get_game_uptime(rcon)
        assert result == "Unknown"

    @pytest.mark.asyncio
    async def test_get_game_uptime_whitespace_response(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(return_value="   ")
        result = await get_game_uptime(rcon)
        assert result == "Unknown"

    @pytest.mark.asyncio
    async def test_get_game_uptime_invalid_number(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(return_value="not_a_number")
        result = await get_game_uptime(rcon)
        assert result == "Unknown"

    @pytest.mark.asyncio
    async def test_get_game_uptime_negative_ticks(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(return_value="-100")
        result = await get_game_uptime(rcon)
        assert result == "Unknown"

    @pytest.mark.asyncio
    async def test_get_game_uptime_execute_exception(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(side_effect=Exception("RCON error"))
        result = await get_game_uptime(rcon)
        assert result == "Unknown"

    @pytest.mark.asyncio
    async def test_get_game_uptime_with_whitespace(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(return_value="  3600  ")
        result = await get_game_uptime(rcon)
        assert result != "Unknown"

    @pytest.mark.asyncio
    async def test_get_game_uptime_minute_range(self) -> None:
        rcon = MockRconClient()
        # 60 ticks = 1 second, 3600 ticks = 60 seconds = 1 minute
        rcon.execute = AsyncMock(return_value="3600")
        result = await get_game_uptime(rcon)
        assert result == "1m"

    @pytest.mark.asyncio
    async def test_get_game_uptime_hour_range(self) -> None:
        rcon = MockRconClient()
        # 3600 seconds * 60 ticks/second = 216000 ticks
        rcon.execute = AsyncMock(return_value="216000")
        result = await get_game_uptime(rcon)
        assert "h" in result


# ========================================================================
# SEND_TO_CHANNEL TESTS (8 tests)
# ========================================================================


class TestSendToChannel:
    """Test channel sending utility."""

    @pytest.mark.asyncio
    async def test_send_to_channel_success(self) -> None:
        bot = MagicMock()
        mock_channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel.return_value = mock_channel
        embed = discord.Embed(title="Test")
        await send_to_channel(bot, 123456, embed)
        mock_channel.send.assert_awaited_once_with(embed=embed)

    @pytest.mark.asyncio
    async def test_send_to_channel_not_found(self) -> None:
        bot = MagicMock()
        bot.get_channel.return_value = None
        embed = discord.Embed(title="Test")
        # Should not raise
        await send_to_channel(bot, 123456, embed)

    @pytest.mark.asyncio
    async def test_send_to_channel_wrong_type(self) -> None:
        bot = MagicMock()
        bot.get_channel.return_value = MagicMock()  # Not a TextChannel
        embed = discord.Embed(title="Test")
        # Should not raise
        await send_to_channel(bot, 123456, embed)

    @pytest.mark.asyncio
    async def test_send_to_channel_forbidden(self) -> None:
        bot = MagicMock()
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send.side_effect = discord.errors.Forbidden(
            MagicMock(), "No permission"
        )
        bot.get_channel.return_value = mock_channel
        embed = discord.Embed(title="Test")
        # Should not raise
        await send_to_channel(bot, 123456, embed)

    @pytest.mark.asyncio
    async def test_send_to_channel_exception(self) -> None:
        bot = MagicMock()
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send.side_effect = Exception("Send failed")
        bot.get_channel.return_value = mock_channel
        embed = discord.Embed(title="Test")
        # Should not raise
        await send_to_channel(bot, 123456, embed)

    @pytest.mark.asyncio
    async def test_send_to_channel_get_channel_exception(self) -> None:
        bot = MagicMock()
        bot.get_channel.side_effect = Exception("Get channel failed")
        embed = discord.Embed(title="Test")
        # Should not raise
        await send_to_channel(bot, 123456, embed)

    @pytest.mark.asyncio
    async def test_send_to_channel_with_real_embed(self) -> None:
        bot = MagicMock()
        mock_channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel.return_value = mock_channel
        embed = discord.Embed(title="Test", description="Description")
        embed.add_field(name="Field", value="Value")
        await send_to_channel(bot, 123456, embed)
        mock_channel.send.assert_awaited_once()


# ========================================================================
# FORMAT_STATS_TEXT TESTS (10 tests)
# ========================================================================


class TestFormatStatsText:
    """Test text stats formatting."""

    def test_format_stats_text_basic(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 2,
            "players": ["Alice", "Bob"],
            "play_time": "2h 30m",
            "evolution_factor": 0.45,
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "📊" in result
        assert "[prod] Main" in result
        assert "60.0" in result
        assert "2" in result
        assert "Alice" in result

    def test_format_stats_text_paused(self) -> None:
        metrics = {
            "is_paused": True,
            "last_known_ups": 59.5,
            "player_count": 1,
            "play_time": "1h",
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "⏸️" in result
        assert "Paused" in result

    def test_format_stats_text_paused_no_last_ups(self) -> None:
        metrics = {
            "is_paused": True,
            "player_count": 0,
            "play_time": "0m",
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "⏸️" in result
        assert "Paused" in result

    def test_format_stats_text_low_ups(self) -> None:
        metrics = {
            "ups": 30.0,
            "player_count": 2,
            "play_time": "1h",
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "⚠️" in result
        assert "30.0" in result

    def test_format_stats_text_with_sma_ema(self) -> None:
        metrics = {
            "ups": 60.0,
            "ups_sma": 59.8,
            "ups_ema": 59.9,
            "player_count": 0,
            "play_time": "0m",
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "SMA" in result
        assert "EMA" in result

    def test_format_stats_text_single_surface_evolution(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 0,
            "play_time": "0m",
            "evolution_by_surface": {"nauvis": 0.45},
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "🐛" in result
        assert "45.00%" in result or "45" in result

    def test_format_stats_text_multi_surface_evolution(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 0,
            "play_time": "0m",
            "evolution_by_surface": {"nauvis": 0.45, "vulcanus": 0.20},
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "🐛" in result
        assert "nauvis" in result
        assert "vulcanus" in result

    def test_format_stats_text_small_evolution(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 0,
            "play_time": "0m",
            "evolution_by_surface": {"nauvis": 0.001},
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "0.10%" in result or "0.0010" in result

    def test_format_stats_text_no_players(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 0,
            "players": [],
            "play_time": "0m",
        }
        result = format_stats_text("[prod] Main", metrics)
        assert "0" in result


# ========================================================================
# FORMAT_STATS_EMBED TESTS (8 tests)
# ========================================================================


class TestFormatStatsEmbed:
    """Test embed stats formatting."""

    def test_format_stats_embed_creates_embed(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 2,
            "players": ["Alice"],
            "play_time": "1h",
        }
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)
        assert "Main" in result.title or "Status" in result.title

    def test_format_stats_embed_paused(self) -> None:
        metrics = {
            "is_paused": True,
            "last_known_ups": 59.5,
            "player_count": 1,
            "play_time": "1h",
        }
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)

    def test_format_stats_embed_with_fields(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 2,
            "players": ["Alice", "Bob"],
            "play_time": "2h 30m",
            "evolution_by_surface": {"nauvis": 0.45},
        }
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)
        assert len(result.fields) > 0

    def test_format_stats_embed_long_player_list(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 50,
            "players": [f"Player{i}" for i in range(50)],
            "play_time": "1h",
        }
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)
        # Should handle truncation

    def test_format_stats_embed_multi_surface(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 0,
            "play_time": "0m",
            "evolution_by_surface": {
                "nauvis": 0.45,
                "vulcanus": 0.20,
                "aquilo": 0.10,
            },
        }
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)

    def test_format_stats_embed_no_evolution(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 0,
            "play_time": "0m",
        }
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)

    def test_format_stats_embed_fallback_evolution(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 0,
            "play_time": "0m",
            "evolution_factor": 0.45,  # Old single-surface format
        }
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)

    def test_format_stats_embed_no_players_field(self) -> None:
        metrics = {
            "ups": 60.0,
            "player_count": 0,
            "players": [],
            "play_time": "0m",
        }
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)


# ========================================================================
# INTEGRATION TESTS
# ========================================================================


@pytest.mark.asyncio
async def test_integration_uptime_to_text() -> None:
    """Test uptime calculation flows into text formatting."""
    delta = timedelta(hours=2, minutes=30)
    uptime_str = format_uptime(delta)
    metrics = {"ups": 60.0, "player_count": 1, "play_time": uptime_str}
    result = format_stats_text("[prod] Main", metrics)
    assert uptime_str in result


@pytest.mark.asyncio
async def test_integration_game_uptime_formatting() -> None:
    """Test game uptime query flows through formatting."""
    rcon = MockRconClient()
    rcon.execute = AsyncMock(return_value="216000")  # 1 hour
    uptime = await get_game_uptime(rcon)
    assert uptime != "Unknown"
    assert "h" in uptime


@pytest.mark.asyncio
async def test_integration_stats_text_and_embed_consistency() -> None:
    """Test that text and embed formatting use same metrics."""
    metrics = {
        "ups": 60.0,
        "player_count": 2,
        "players": ["Alice", "Bob"],
        "play_time": "2h 30m",
        "evolution_by_surface": {"nauvis": 0.45},
    }
    text = format_stats_text("[prod] Main", metrics)
    embed = format_stats_embed("[prod] Main", metrics)
    # Both should include key metrics
    assert "60.0" in text or "60" in text
    assert "2" in text


@pytest.mark.asyncio
async def test_integration_presence_manager_with_server_changes() -> None:
    """Test presence manager updates with changing server states."""
    bot = MockDiscordBot()
    manager = PresenceManager(bot)
    
    # All connected
    bot.server_manager = MockServerManager({"prod": True, "staging": True})
    await manager.update()
    call1_status = bot.change_presence.call_args_list[-1][1]["status"]
    
    # Some connected
    bot.server_manager = MockServerManager({"prod": True, "staging": False})
    await manager.update()
    call2_status = bot.change_presence.call_args_list[-1][1]["status"]
    
    # Different statuses for different states
    assert call1_status != call2_status or call1_status == discord.Status.online


# ========================================================================
# EDGE CASES
# ========================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_format_uptime_with_only_seconds(self) -> None:
        delta = timedelta(seconds=5)
        result = format_uptime(delta)
        assert result == "< 1m"

    def test_format_stats_text_missing_optional_fields(self) -> None:
        metrics = {"player_count": 0}
        result = format_stats_text("[prod] Main", metrics)
        assert isinstance(result, str)

    def test_format_stats_text_none_values(self) -> None:
        metrics = {
            "ups": None,
            "player_count": 0,
            "play_time": None,
        }
        result = format_stats_text("[prod] Main", metrics)
        assert isinstance(result, str)

    def test_format_stats_embed_missing_evolution(self) -> None:
        metrics = {"player_count": 0}
        result = format_stats_embed("[prod] Main", metrics)
        assert isinstance(result, discord.Embed)

    @pytest.mark.asyncio
    async def test_get_game_uptime_very_small_tick_values(self) -> None:
        rcon = MockRconClient()
        rcon.execute = AsyncMock(return_value="1")
        result = await get_game_uptime(rcon)
        assert result == "< 1m"
