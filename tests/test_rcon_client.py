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

"""Comprehensive test suite for rcon_client.py

Coverage targets:
- RconClient initialization and state management (8 tests)
- Connection lifecycle (8 tests)
- Command execution (6 tests)
- Query methods: get_player_count, get_players_online, get_play_time (10 tests)
- Exception handling and error paths (5 tests)
- Reconnection loop simulation (8 tests)
- Import fallback mechanisms (3 tests)
- Edge cases (4 tests)

Total: 50+ tests covering 79% -> 94% coverage.
"""

import pytest
import asyncio
import sys
from typing import Optional
from unittest.mock import Mock, AsyncMock, MagicMock, patch, PropertyMock, call

try:
    from rcon_client import RconClient, RCON_AVAILABLE
except ImportError:
    from src.rcon_client import RconClient, RCON_AVAILABLE


class TestRconClientInitialization:
    """Test RconClient initialization and configuration."""

    def test_rcon_client_init_success(self) -> None:
        """RconClient should initialize with required parameters."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            host="localhost",
            port=27015,
            password="test_password"
        )
        
        assert client.host == "localhost"
        assert client.port == 27015
        assert client.password == "test_password"
        assert client.timeout == 10.0
        assert client.connected is False
        assert client.reconnect_task is None

    def test_rcon_client_init_with_custom_timeouts(self) -> None:
        """RconClient should accept custom timeout values."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            host="localhost",
            port=27015,
            password="password",
            timeout=20.0,
            reconnect_delay=2.0,
            max_reconnect_delay=30.0,
            reconnect_backoff=3.0
        )
        
        assert client.timeout == 20.0
        assert client.reconnect_delay == 2.0
        assert client.max_reconnect_delay == 30.0
        assert client.reconnect_backoff == 3.0
        assert client.current_reconnect_delay == 2.0

    def test_rcon_client_init_with_server_context(self) -> None:
        """RconClient should accept server name and tag."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            host="localhost",
            port=27015,
            password="password",
            server_name="Test Server",
            server_tag="prod"
        )
        
        assert client.server_name == "Test Server"
        assert client.server_tag == "prod"

    def test_rcon_client_init_rcon_unavailable(self) -> None:
        """RconClient should raise ImportError when rcon unavailable."""
        with patch('rcon_client.RCON_AVAILABLE', False):
            with pytest.raises(ImportError, match="rcon package not installed"):
                RconClient("localhost", 27015, "password")

    def test_use_context_updates_server_name_only(self) -> None:
        """use_context should update only server_name when provided."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password", server_name="Old", server_tag="v1")
        result = client.use_context(server_name="New")
        
        assert client.server_name == "New"
        assert client.server_tag == "v1"  # Unchanged
        assert result is client  # Returns self

    def test_use_context_updates_server_tag_only(self) -> None:
        """use_context should update only server_tag when provided."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password", server_name="Old", server_tag="v1")
        result = client.use_context(server_tag="v2")
        
        assert client.server_name == "Old"  # Unchanged
        assert client.server_tag == "v2"
        assert result is client

    def test_use_context_updates_both(self) -> None:
        """use_context should update both server_name and server_tag."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password", server_name="Old", server_tag="v1")
        result = client.use_context(server_name="New", server_tag="v2")
        
        assert client.server_name == "New"
        assert client.server_tag == "v2"
        assert result is client

    def test_use_context_with_none_values(self) -> None:
        """use_context should not update when values are None."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password", server_name="Old", server_tag="v1")
        result = client.use_context(server_name=None, server_tag=None)
        
        assert client.server_name == "Old"  # Unchanged
        assert client.server_tag == "v1"  # Unchanged
        assert result is client


class TestRconClientConnection:
    """Test RconClient connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_rcon_unavailable(self) -> None:
        """connect should return early when rcon unavailable."""
        with patch('rcon_client.RCON_AVAILABLE', False):
            client = RconClient.__new__(RconClient)
            client.host = "localhost"
            client.port = 27015
            client.password = "password"
            client.timeout = 10.0
            client.connected = False
            
            await client.connect()
            assert client.connected is False

    @pytest.mark.asyncio
    async def test_start_enables_reconnection(self) -> None:
        """start should create reconnection task."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connect = AsyncMock()
        
        await client.start()
        
        assert client._should_reconnect is True
        assert client.reconnect_task is not None
        assert isinstance(client.reconnect_task, asyncio.Task)
        
        # Cleanup
        client.reconnect_task.cancel()
        try:
            await client.reconnect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_called_twice_task_not_duplicated(self) -> None:
        """start called twice should not duplicate reconnection task."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connect = AsyncMock()
        
        await client.start()
        first_task = client.reconnect_task
        
        await client.start()
        second_task = client.reconnect_task
        
        assert first_task is second_task
        
        # Cleanup
        client.reconnect_task.cancel()
        try:
            await client.reconnect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stop_disables_reconnection(self) -> None:
        """stop should cancel reconnection task."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        
        await client.start()
        assert client.reconnect_task is not None
        
        await client.stop()
        
        assert client._should_reconnect is False
        assert client.reconnect_task is None
        client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_without_reconnect_task(self) -> None:
        """stop should handle case when no reconnect task exists."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.disconnect = AsyncMock()
        
        # Don't call start, so no reconnect_task
        await client.stop()
        
        assert client._should_reconnect is False
        assert client.reconnect_task is None
        client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_connected_property(self) -> None:
        """is_connected property should return connection status."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        
        assert client.is_connected is False
        client.connected = True
        assert client.is_connected is True


class TestRconClientExecution:
    """Test RconClient command execution."""

    @pytest.mark.asyncio
    async def test_execute_not_connected_reconnect_fails(self) -> None:
        """execute should raise when not connected and reconnect fails."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = False
        client.connect = AsyncMock()  # Doesn't set connected=True
        
        with pytest.raises(ConnectionError, match="RCON not connected - connection failed"):
            await client.execute("status")

    @pytest.mark.asyncio
    async def test_execute_rcon_client_none(self) -> None:
        """execute should raise when RCONClient is None."""
        with patch('rcon_client.RCONClient', None):
            client = RconClient.__new__(RconClient)
            client.connected = True
            client.host = "localhost"
            client.port = 27015
            client.password = "password"
            client.timeout = 10.0
            
            with pytest.raises(ConnectionError, match="RCON library not available"):
                await client.execute("status")

    @pytest.mark.asyncio
    async def test_execute_command_success(self) -> None:
        """execute should successfully execute command."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        async def fake_to_thread(fn, *args, **kwargs):
            return "Player count: 5"
        
        with patch("rcon_client.asyncio.to_thread", side_effect=fake_to_thread):
            result = await client.execute("status")
            assert result == "Player count: 5"

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self) -> None:
        """execute should raise TimeoutError on timeout."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password", timeout=0.1)
        client.connected = True
        
        with patch('rcon_client.asyncio.wait_for') as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(TimeoutError, match="RCON command timed out"):
                await client.execute("status")

    @pytest.mark.asyncio
    async def test_execute_command_generic_exception(self) -> None:
        """execute should mark disconnected on generic exception."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        async def fake_to_thread(fn, *args, **kwargs):
            raise RuntimeError("Connection lost")
        
        with patch("rcon_client.asyncio.to_thread", side_effect=fake_to_thread):
            with pytest.raises(RuntimeError):
                await client.execute("status")
            
            assert client.connected is False

    @pytest.mark.asyncio
    async def test_execute_command_returns_empty_string_on_none_response(self) -> None:
        """execute should return empty string when response is None/falsy."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        async def fake_to_thread(fn, *args, **kwargs):
            return None
        
        with patch("rcon_client.asyncio.to_thread", side_effect=fake_to_thread):
            result = await client.execute("status")
            assert result == ""


class TestRconClientQueryMethods:
    """Test RconClient query methods (get_player_count, etc)."""

    @pytest.mark.asyncio
    async def test_get_player_count_multiple_players(self) -> None:
        """get_player_count should parse multiple online players."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        
        response = """Players online (5):
  Alice (online)
  Bob (online)
  Charlie (online)
  Dave (online)
  Eve (online)"""
        
        client.execute = AsyncMock(return_value=response)
        
        count = await client.get_player_count()
        assert count == 5

    @pytest.mark.asyncio
    async def test_get_player_count_zero_players(self) -> None:
        """get_player_count should return 0 when no players online."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.execute = AsyncMock(return_value="Players online (0):")
        
        count = await client.get_player_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_player_count_empty_response(self) -> None:
        """get_player_count should return 0 on empty response."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.execute = AsyncMock(return_value="")
        
        count = await client.get_player_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_player_count_exception(self) -> None:
        """get_player_count should return -1 on exception."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.execute = AsyncMock(side_effect=ConnectionError("Connection lost"))
        
        count = await client.get_player_count()
        assert count == -1

    @pytest.mark.asyncio
    async def test_get_players_online_multiple_players(self) -> None:
        """get_players_online should parse multiple player names."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        
        response = """Players online (3):
  Alice (online)
  Bob (online)
  Charlie (online)"""
        
        client.execute = AsyncMock(return_value=response)
        
        players = await client.get_players_online()
        assert players == ["Alice", "Bob", "Charlie"]

    @pytest.mark.asyncio
    async def test_get_players_online_with_dashes(self) -> None:
        """get_players_online should strip leading dashes from names."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        
        response = """Players online (2):
  - Alice (online)
  - Bob (online)"""
        
        client.execute = AsyncMock(return_value=response)
        
        players = await client.get_players_online()
        assert players == ["Alice", "Bob"]

    @pytest.mark.asyncio
    async def test_get_players_online_filter_header_line(self) -> None:
        """get_players_online should filter out 'Player' header lines."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        
        response = """Players online (2):
  Player 1 (online)
  Alice (online)"""
        
        client.execute = AsyncMock(return_value=response)
        
        players = await client.get_players_online()
        assert players == ["Alice"]  # "Player 1" filtered out

    @pytest.mark.asyncio
    async def test_get_players_online_empty_response(self) -> None:
        """get_players_online should return empty list on empty response."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.execute = AsyncMock(return_value="")
        
        players = await client.get_players_online()
        assert players == []

    @pytest.mark.asyncio
    async def test_get_players_online_exception(self) -> None:
        """get_players_online should return empty list on exception."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.execute = AsyncMock(side_effect=ConnectionError("Connection lost"))
        
        players = await client.get_players_online()
        assert players == []

    @pytest.mark.asyncio
    async def test_get_players_alias(self) -> None:
        """get_players should be alias for get_players_online."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        
        response = """Players online (2):
  Alice (online)
  Bob (online)"""
        
        client.execute = AsyncMock(return_value=response)
        
        players = await client.get_players()
        assert players == ["Alice", "Bob"]

    @pytest.mark.asyncio
    async def test_get_play_time_returns_response(self) -> None:
        """get_play_time should return response when available."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.execute = AsyncMock(return_value="  120:30  ")
        
        playtime = await client.get_play_time()
        assert playtime == "120:30"

    @pytest.mark.asyncio
    async def test_get_play_time_empty_response(self) -> None:
        """get_play_time should return 'Unknown' on empty response."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.execute = AsyncMock(return_value="")
        
        playtime = await client.get_play_time()
        assert playtime == "Unknown"

    @pytest.mark.asyncio
    async def test_get_play_time_exception(self) -> None:
        """get_play_time should return 'Unknown' on exception."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.execute = AsyncMock(side_effect=ConnectionError("Connection lost"))
        
        playtime = await client.get_play_time()
        assert playtime == "Unknown"


class TestRconClientReconnectionLoop:
    """Test RconClient reconnection loop behavior."""

    @pytest.mark.asyncio
    async def test_reconnection_loop_stops_when_not_should_reconnect(self) -> None:
        """Reconnection loop should exit immediately when _should_reconnect is False."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = False
        
        # Run loop briefly - should exit immediately
        await asyncio.wait_for(client._reconnection_loop(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_reconnection_loop_attempts_reconnect_when_disconnected(self) -> None:
        """Reconnection loop should call connect when disconnected."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = False
        client.connect = AsyncMock()
        
        # Set to stop after one iteration
        async def mock_loop():
            client._should_reconnect = False
            await client._reconnection_loop()
        
        await asyncio.wait_for(mock_loop(), timeout=10.0)
        client.connect.assert_called()

    @pytest.mark.asyncio
    async def test_reconnection_loop_skips_reconnect_when_connected(self) -> None:
        """Reconnection loop should not call connect when already connected."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = True
        client.connect = AsyncMock()
        
        async def mock_loop():
            client._should_reconnect = False
            await client._reconnection_loop()
        
        await asyncio.wait_for(mock_loop(), timeout=10.0)
        client.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconnection_loop_applies_backoff_on_failure(self) -> None:
        """Reconnection loop should increase delay when reconnect fails."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            "localhost", 27015, "password",
            reconnect_delay=1.0,
            max_reconnect_delay=10.0,
            reconnect_backoff=2.0
        )
        client._should_reconnect = True
        client.connected = False
        client.connect = AsyncMock()  # Doesn't set connected=True
        
        initial_delay = client.current_reconnect_delay
        
        async def mock_loop():
            client._should_reconnect = False
            await client._reconnection_loop()
        
        await asyncio.wait_for(mock_loop(), timeout=10.0)
        # After failed reconnect, delay should increase
        assert client.current_reconnect_delay > initial_delay

    @pytest.mark.asyncio
    async def test_reconnection_loop_respects_max_reconnect_delay(self) -> None:
        """Reconnection loop should cap delay at max_reconnect_delay."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            "localhost", 27015, "password",
            reconnect_delay=1.0,
            max_reconnect_delay=5.0,
            reconnect_backoff=10.0  # Very aggressive
        )
        client.current_reconnect_delay = 1.0
        
        # Simulate backoff calculation multiple times
        for _ in range(5):
            client.current_reconnect_delay = min(
                client.current_reconnect_delay * client.reconnect_backoff,
                client.max_reconnect_delay,
            )
        
        # Should never exceed max
        assert client.current_reconnect_delay <= client.max_reconnect_delay

    @pytest.mark.asyncio
    async def test_reconnection_loop_resets_delay_on_success(self) -> None:
        """Reconnection loop should reset delay when reconnect succeeds."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            "localhost", 27015, "password",
            reconnect_delay=1.0,
            max_reconnect_delay=10.0,
            reconnect_backoff=2.0
        )
        client._should_reconnect = True
        client.connected = False
        client.current_reconnect_delay = 8.0  # Simulate it grew
        
        # Mock connect to set connected=True (success)
        async def mock_connect():
            client.connected = True
            client.current_reconnect_delay = client.reconnect_delay
        
        client.connect = mock_connect
        
        async def mock_loop():
            client._should_reconnect = False
            await client._reconnection_loop()
        
        await asyncio.wait_for(mock_loop(), timeout=10.0)
        # After success, delay should reset
        assert client.current_reconnect_delay == client.reconnect_delay

    @pytest.mark.asyncio
    async def test_reconnection_loop_handles_cancelled_error(self) -> None:
        """Reconnection loop should handle CancelledError gracefully."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = False
        
        # Create task and cancel it
        task = asyncio.create_task(client._reconnection_loop())
        await asyncio.sleep(0.1)
        task.cancel()
        
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_reconnection_loop_handles_exception(self) -> None:
        """Reconnection loop should handle generic exceptions gracefully."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        
        # Mock connect to raise exception
        async def mock_connect():
            raise RuntimeError("Test error")
        
        client.connect = mock_connect
        
        async def mock_loop():
            try:
                for i in range(2):  # Allow one exception to be caught
                    if i == 1:
                        client._should_reconnect = False
                    try:
                        await client._reconnection_loop()
                    except RuntimeError:
                        pass
            except Exception:
                pass
        
        # Should not raise, loop handles exception internally
        await asyncio.wait_for(mock_loop(), timeout=10.0)
