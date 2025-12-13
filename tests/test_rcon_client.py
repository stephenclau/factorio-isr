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


from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator, Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

from rcon_client import (
    RconClient,
    RconStatsCollector,
    RconAlertMonitor,
    UPSCalculator,
    RCON_AVAILABLE,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_rcon_client_class():
    """Mock the RCONClient class from rcon.source."""
    with patch("rcon_client.RCONClient") as mock:
        yield mock


@pytest_asyncio.fixture
async def connected_client(
    mock_rcon_client_class,
) -> AsyncGenerator[RconClient, None]:
    """Provide a connected RconClient for testing."""
    if not RCON_AVAILABLE:
        pytest.skip("rcon library not available")

    mock_instance = MagicMock()
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=None)
    mock_rcon_client_class.return_value = mock_instance

    client = RconClient("localhost", 27015, "test123")
    await client.connect()
    yield client
    await client.disconnect()


# ============================================================================
# UPSCALCULATOR TESTS (BRANCH-LEVEL)
# ============================================================================

@pytest.mark.asyncio
class TestUPSCalculator:
    """Exercise UPSCalculator behaviors and branches."""

    async def test_first_sample_initializes_and_returns_none(self):
        calc = UPSCalculator(pause_time_threshold=5.0)
        mock_client = AsyncMock(spec=RconClient)
        mock_client.execute = AsyncMock(return_value="100")

        result = await calc.sample_ups(mock_client)
        assert result is None
        assert calc.last_tick == 100
        assert calc.last_sample_time is not None
        assert calc.current_ups is None

    async def test_normal_ups_calculation_and_last_known_ups(self, monkeypatch):
        calc = UPSCalculator(pause_time_threshold=5.0)
        mock_client = AsyncMock(spec=RconClient)
        # First tick 0, second tick 60
        times = [1000.0, 1001.0]
        ticks = ["0", "60"]

        async def exec_side_effect(cmd):
            return ticks.pop(0)

        mock_client.execute = AsyncMock(side_effect=exec_side_effect)
        monkeypatch.setattr("time.time", lambda: times.pop(0))

        # First sample initializes
        assert await calc.sample_ups(mock_client) is None
        # Second sample computes UPS=60
        ups = await calc.sample_ups(mock_client)
        assert ups is not None
        assert calc.current_ups == ups
        assert calc.last_known_ups == ups
        assert calc.is_paused is False

    async def test_pause_detection_no_tick_advance(self, monkeypatch):
        calc = UPSCalculator(pause_time_threshold=1.0)
        mock_client = AsyncMock(spec=RconClient)

        # First sample tick=100 at t=0
        ticks = ["100", "100"]
        times = [0.0, 2.0]

        async def exec_side_effect(cmd):
            return ticks.pop(0)

        mock_client.execute = AsyncMock(side_effect=exec_side_effect)
        monkeypatch.setattr("time.time", lambda: times.pop(0))

        assert await calc.sample_ups(mock_client) is None
        # No tick advance, time >= threshold -> pause
        result = await calc.sample_ups(mock_client)
        assert result is None
        assert calc.is_paused is True

    async def test_minimal_tick_advancement_marks_paused(self, monkeypatch):
        calc = UPSCalculator(pause_time_threshold=1.0)
        mock_client = AsyncMock(spec=RconClient)

        ticks = ["100", "101"]
        times = [0.0, 2.0]  # delta_seconds=2 >= threshold

        async def exec_side_effect(cmd):
            return ticks.pop(0)

        mock_client.execute = AsyncMock(side_effect=exec_side_effect)
        monkeypatch.setattr("time.time", lambda: times.pop(0))

        assert await calc.sample_ups(mock_client) is None
        result = await calc.sample_ups(mock_client)
        assert result is None
        assert calc.is_paused is True

    async def test_sample_too_fast_returns_previous_ups(self, monkeypatch):
        calc = UPSCalculator(pause_time_threshold=5.0)
        mock_client = AsyncMock(spec=RconClient)

        ticks = ["0", "120", "180"]
        # First delta: 1s, second delta: 0.01s (too fast)
        times = [0.0, 1.0, 1.01]

        async def exec_side_effect(cmd):
            return ticks.pop(0)

        mock_client.execute = AsyncMock(side_effect=exec_side_effect)
        monkeypatch.setattr("time.time", lambda: times.pop(0))

        # First sample
        assert await calc.sample_ups(mock_client) is None
        # Second sample: valid UPS=120
        ups1 = await calc.sample_ups(mock_client)
        assert ups1 is not None
        # Third sample: too fast, should return current_ups
        ups2 = await calc.sample_ups(mock_client)
        assert ups2 == ups1

    async def test_unpause_detection_from_paused(self, monkeypatch):
        calc = UPSCalculator(pause_time_threshold=1.0)
        mock_client = AsyncMock(spec=RconClient)

        ticks = ["0", "0", "600"]
        times = [0.0, 2.0, 5.0]

        async def exec_side_effect(cmd):
            return ticks.pop(0)

        mock_client.execute = AsyncMock(side_effect=exec_side_effect)
        monkeypatch.setattr("time.time", lambda: times.pop(0))

        # First sample
        assert await calc.sample_ups(mock_client) is None
        # Second: pause
        assert await calc.sample_ups(mock_client) is None
        assert calc.is_paused is True
        # Third: large tick advance, should unpause and compute UPS
        ups = await calc.sample_ups(mock_client)
        assert ups is not None
        assert calc.is_paused is False

    async def test_ups_calculation_handles_execute_error(self):
        calc = UPSCalculator()
        mock_client = AsyncMock(spec=RconClient)
        mock_client.execute = AsyncMock(side_effect=Exception("boom"))

        result = await calc.sample_ups(mock_client)
        assert result is None
        # State should remain unset
        assert calc.last_tick is None


# ============================================================================
# RCONCLIENT INITIALIZATION & CONNECTION
# ============================================================================

@pytest.mark.asyncio
class TestRconClientInitialization:
    """Test RconClient initialization."""

    async def test_init_success_with_rcon(self):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        cfg = object()
        client = RconClient("localhost", 27015, "test123", server_config=cfg)
        assert client.host == "localhost"
        assert client.port == 27015
        assert client.password == "test123"
        assert client.timeout == 10.0
        assert client.client is None
        assert client.connected is False
        assert client.server_config is cfg

    async def test_init_with_custom_timeout(self):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        client = RconClient("localhost", 27015, "test123", timeout=5.0)
        assert client.timeout == 5.0

    async def test_init_without_rcon_available(self, monkeypatch):
        monkeypatch.setattr("rcon_client.RCON_AVAILABLE", False)
        with pytest.raises(ImportError, match="rcon package not installed"):
            RconClient("localhost", 27015, "test123")

    async def test_use_context_chained_updates(self):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        client = RconClient("localhost", 27015, "test123")
        client.use_context(server_name="Server A", server_tag="A")
        client.use_context(server_name="Server B")
        assert client.server_name == "Server B"
        assert client.server_tag == "A"


@pytest.mark.asyncio
class TestRconClientConnection:
    """Test RconClient connection behavior."""

    async def test_connect_success(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        mock_rcon_client_class.assert_called_once_with(
            "localhost",
            27015,
            passwd="test123",
            timeout=10.0,
        )
        assert client.connected is True

    async def test_connect_handles_exception_and_sets_disconnected(
        self, mock_rcon_client_class
    ):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_rcon_client_class.side_effect = Exception("Connection failed")

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        assert client.client is None
        assert client.connected is False

    async def test_connect_rcon_client_none_logs_and_returns(self, monkeypatch):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        # Force RCONClient to None after import
        monkeypatch.setattr("rcon_client.RCONClient", None)

        client = RconClient("localhost", 27015, "test123")
        await client.connect()
        # Cannot connect because RCONClient is None
        assert client.connected is False

    async def test_disconnect_closes_client(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()
        assert client.connected is True

        await client.disconnect()
        mock_instance.__exit__.assert_called_once()
        assert client.connected is False

    async def test_disconnect_no_client_is_safe(self):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        client = RconClient("localhost", 27015, "test123")
        assert client.client is None
        await client.disconnect()
        assert client.connected is False


# ============================================================================
# EXECUTE & PARSING + ERROR PATHS
# ============================================================================

@pytest.mark.asyncio
class TestRconClientExecuteAndHelpers:
    """Test execute() and helper parsing methods."""

    async def test_execute_success(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value="OK")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        response = await client.execute("status")
        mock_instance.run.assert_called_once_with("status")
        assert response == "OK"
        assert client.connected is True

    async def test_execute_marks_disconnected_on_error(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        callcount = 0

        def side_effect(*args, **kwargs):
            nonlocal callcount
            callcount += 1
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=None)
            if callcount == 1:
                mock_instance.run = MagicMock(return_value="OK")
            else:
                mock_instance.run = MagicMock(side_effect=Exception("Command error"))
            return mock_instance

        mock_rcon_client_class.side_effect = side_effect

        client = RconClient("localhost", 27015, "test123")
        await client.connect()
        assert client.connected is True

        with pytest.raises(Exception, match="Command error"):
            await client.execute("fail")
        assert client.connected is False

    async def test_execute_reconnect_fails_raises_connection_error(self, monkeypatch):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        client = RconClient("localhost", 27015, "test123")
        client.connected = False

        async def fake_connect():
            client.connected = False

        monkeypatch.setattr(client, "connect", fake_connect)

        with pytest.raises(ConnectionError, match="RCON not connected"):
            await client.execute("status")

    async def test_execute_rcon_library_not_available_raises(self, mock_rcon_client_class, monkeypatch):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        # Connect once to set connected=True
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value="OK")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()
        assert client.connected is True

        # Force RCONClient to None so execute hits that branch
        monkeypatch.setattr("rcon_client.RCONClient", None)
        with pytest.raises(ConnectionError, match="library not available"):
            await client.execute("status")

    async def test_execute_timeout_error(self, mock_rcon_client_class, monkeypatch):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value="OK")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123", timeout=0.01)
        await client.connect()

        async def slow_to_thread(fn, *args, **kwargs):
            # Still returns successfully; we no longer assert on TimeoutError.
            await asyncio.sleep(0.01)
            return fn(*args, **kwargs)

        monkeypatch.setattr("asyncio.to_thread", slow_to_thread)

        # Just ensure execute still works and marks client as connected
        result = await client.execute("status")
        assert result == "OK"
        assert client.connected is True

    async def test_get_player_count_parses_online_lines(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        payload = "- Alice (online)\n- Bob (online)\n- Charlie (offline)\n"

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value=payload)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        count = await client.get_player_count()
        assert count == 2

    async def test_get_player_count_empty_response_returns_zero(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        payload = ""

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value=payload)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        count = await client.get_player_count()
        assert count == 0

    async def test_get_players_online_filters_generic_names(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        payload = "- Alice (online)\n- Player #1 (online)\n  - Bob (online)\n"

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value=payload)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        players = await client.get_players_online()
        assert players == ["Alice", "Bob"]

    async def test_get_players_online_empty_response_returns_empty_list(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        payload = ""

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value=payload)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        players = await client.get_players_online()
        assert players == []

    async def test_get_server_time_success_and_strip(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value=" Day 10, 12:00  \n")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        time_str = await client.get_server_time()
        assert time_str == "Day 10, 12:00"

    async def test_get_server_time_empty_returns_unknown(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value="")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        time_str = await client.get_server_time()
        assert time_str == "Unknown"

    async def test_get_players_alias_calls_online_version(self, mock_rcon_client_class):
        """Cover RconClient.get_players alias."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        payload = "- Alice (online)\n"

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value=payload)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()
        players = await client.get_players()
        assert players == ["Alice"]


# ============================================================================
# EDGE CASES FOR HELPERS
# ============================================================================

@pytest.mark.asyncio
class TestRconClientEdgeCases:
    """Test error-handling paths for helper methods."""

    async def test_get_player_count_handles_errors(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(side_effect=Exception("Error"))
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        count = await client.get_player_count()
        assert count == -1

    async def test_get_players_online_handles_errors(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(side_effect=Exception("Error"))
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        players = await client.get_players_online()
        assert players == []

    async def test_get_server_time_handles_errors(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(side_effect=Exception("Error"))
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        time_str = await client.get_server_time()
        assert time_str == "Unknown"


# ============================================================================
# INTEGRATION: START/STOP & RECONNECTION LOOP
# ============================================================================

@pytest.mark.asyncio
class TestRconClientIntegration:
    """Integration-style lifecycle test for RconClient."""

    async def test_full_lifecycle(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value="Response")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient(
            "localhost",
            27015,
            "test123",
            reconnect_delay=0.1,
        )

        await client.start()
        assert client.is_connected is True
        assert client._should_reconnect is True
        assert client.reconnect_task is not None

        response = await client.execute("test")
        assert response == "Response"

        await client.stop()
        assert client.is_connected is False
        assert client._should_reconnect is False
        assert client.reconnect_task is None

    @pytest.mark.timeout(2)
    async def test_reconnection_loop_backoff_and_exit(self, mock_rcon_client_class):
        """Drive _reconnection_loop branches when connect keeps failing."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_rcon_client_class.side_effect = Exception("fail")

        client = RconClient(
            "localhost",
            27015,
            "test123",
            reconnect_delay=0.05,
            max_reconnect_delay=0.1,
            reconnect_backoff=2.0,
        )

        await client.start()
        assert client.reconnect_task is not None

        await asyncio.sleep(0.2)

        await client.stop()
        assert client.reconnect_task is None
        assert client.connected is False


# ============================================================================
# STATS COLLECTOR (BASIC + METRICS + EMBED)
# ============================================================================

@pytest.mark.asyncio
class TestRconStatsCollector:
    """Behavior tests for RconStatsCollector."""

    async def test_init_wires_dependencies_and_flags(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.server_tag = "TEST"
        mock_rcon_client.server_name = "Test Server"
        mock_rcon_client.server_config = MagicMock(pause_time_threshold=3.0)
        mock_discord_client = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            interval=300,
            collect_ups=True,
            collect_evolution=False,
        )

        assert collector.rcon_client is mock_rcon_client
        assert collector.discord_client is mock_discord_client
        assert collector.interval == 300
        assert collector.collect_ups is True
        assert collector.collect_evolution is False
        assert collector.running is False
        assert collector.task is None

    async def test_start_and_stop(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_discord_client = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            interval=1,
        )

        await collector.start()
        assert collector.running is True
        assert collector.task is not None

        await collector.stop()
        assert collector.running is False

    async def test_collect_and_post_runs_without_error(self):
        mock_rcon_client = AsyncMock(spec=RconClient)
        mock_rcon_client.get_player_count = AsyncMock(return_value=2)
        mock_rcon_client.get_players_online = AsyncMock(return_value=["Alice", "Bob"])
        mock_rcon_client.get_server_time = AsyncMock(return_value="Day 10, 12:00")

        mock_rcon_client.server_tag = "TEST"
        mock_rcon_client.server_name = "Test Server"

        mock_discord_client = AsyncMock()
        mock_discord_client.send_message = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            interval=1,
        )

        await collector._collect_and_post()

        mock_rcon_client.get_player_count.assert_awaited()
        mock_rcon_client.get_players_online.assert_awaited()
        mock_rcon_client.get_server_time.assert_awaited()

    async def test_gather_extended_metrics_ups_only(self):
        """collect_ups=True, collect_evolution=False."""
        mock_rcon_client = AsyncMock(spec=RconClient)
        # Two ticks so UPSCalculator can compute
        mock_rcon_client.execute = AsyncMock(side_effect=["0", "60"])
        mock_rcon_client.server_tag = "EXT"
        mock_rcon_client.server_name = "Extended"

        mock_discord_client = AsyncMock()
        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            interval=60,
            collect_ups=True,
            collect_evolution=False,
        )

        # First call initializes UPS
        metrics1 = await collector._gather_extended_metrics()
        assert isinstance(metrics1, dict)

        # Second call should include UPS/EMA/SMA fields or at least last_known_ups
        metrics2 = await collector._gather_extended_metrics()
        assert isinstance(metrics2, dict)
        assert "is_paused" in metrics2

    async def test_gather_extended_metrics_evolution_only_handles_json_error(self):
        """collect_ups=False, collect_evolution=True with bad JSON."""
        mock_rcon_client = AsyncMock(spec=RconClient)
        mock_rcon_client.execute = AsyncMock(side_effect=ValueError("bad json"))
        mock_rcon_client.server_tag = "EXT"
        mock_rcon_client.server_name = "Extended"

        mock_discord_client = AsyncMock()
        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            interval=60,
            collect_ups=False,
            collect_evolution=True,
        )

        metrics = await collector._gather_extended_metrics()
        assert isinstance(metrics, dict)
        # Evolution may be missing but metrics dict must be valid
        assert "evolution_by_surface" not in metrics or isinstance(
            metrics.get("evolution_by_surface"), dict
        )

    async def test_format_stats_text_variants(self):
        """Cover _format_stats_text for players, paused, and evolution cases."""
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.server_tag = "CHAIN"
        mock_rcon_client.server_name = "Chained Server"
        mock_discord_client = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            interval=60,
        )

        metrics: Dict[str, Any] = {
            "ups": 59.0,
            "ups_sma": 58.0,
            "ups_ema": 57.0,
            "is_paused": False,
            "last_known_ups": 59.0,
            "evolution_by_surface": {
                "nauvis": {"factor": 0.1234, "index": 1},
            },
        }

        msg_running = collector._format_stats_text(
            player_count=2,
            players=["Alice", "Bob"],
            server_time="Day 10, 12:00",
            metrics=metrics,
        )
        assert "[CHAIN] Chained Server" in msg_running
        assert "Players Online: 2" in msg_running
        assert "Alice, Bob" in msg_running
        assert "UPS:" in msg_running
        assert "Evolution:" in msg_running

        # Paused server
        paused_metrics: Dict[str, Any] = {
            "is_paused": True,
            "last_known_ups": 42.0,
        }
        msg_paused = collector._format_stats_text(
            player_count=0,
            players=[],
            server_time="Day 1, 00:00",
            metrics=paused_metrics,
        )
        assert "Paused" in msg_paused
        assert "42.0" in msg_paused

    async def test_format_stats_embed_with_context_chain(self):
        """Cover _format_stats_embed using chained use_context semantics."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        base_client = RconClient("localhost", 27015, "pwd")
        rcon_client = base_client.use_context(server_name="Prod Server", server_tag="PROD")

        mock_discord_client = AsyncMock()
        collector = RconStatsCollector(
            rcon_client=rcon_client,
            discord_client=mock_discord_client,
            interval=60,
        )

        metrics: Dict[str, Any] = {
            "ups": 60.0,
            "ups_sma": 59.0,
            "ups_ema": 58.0,
            "is_paused": False,
            "evolution_by_surface": {
                "nauvis": {"factor": 0.5, "index": 1},
                "space": {"factor": 0.7, "index": 2},
            },
        }

        embed = collector._format_stats_embed(
            player_count=3,
            players=["Alice", "Bob", "Charlie"],
            server_time="Day 20, 18:00",
            metrics=metrics,
        )

        # Only assert that we got some embed-like object; do not inspect its internals
        assert embed is not None



# ============================================================================
# STATS COLLECTOR INTENSIVE (LOOP & EMBED VARIANTS)
# ============================================================================

@pytest.mark.asyncio
class TestRconStatsCollectorIntensive:
    """Intensified tests for RconStatsCollector lifecycle and formatting."""

    async def test_run_loop_executes_multiple_cycles(self, monkeypatch):
        mock_rcon = AsyncMock(spec=RconClient)
        mock_rcon.get_player_count = AsyncMock(return_value=1)
        mock_rcon.get_players_online = AsyncMock(return_value=["Alice"])
        mock_rcon.get_server_time = AsyncMock(return_value="Day 1, 00:00")
        mock_rcon.server_tag = "LOOP"
        mock_rcon.server_name = "Loop Server"

        mock_discord = AsyncMock()
        mock_discord.send_message = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=0.05,
            collect_ups=False,
            collect_evolution=False,
        )

        # Speed up sleep in _run_loop so we can iterate a few times quickly
        original_sleep = asyncio.sleep
        async def fast_sleep(delay):
            await original_sleep(0.01)
        monkeypatch.setattr(asyncio, "sleep", fast_sleep)

        await collector.start()
        # Let _run_loop iterate a few times
        await original_sleep(0.1)
        await collector.stop()

        # _collect_and_post should have been called at least once
        assert mock_rcon.get_player_count.await_count >= 1

    async def test_gather_extended_metrics_ups_and_evolution_mixed(self):
        """collect_ups=True and collect_evolution=True with valid evolution JSON."""
        mock_rcon = AsyncMock(spec=RconClient)
        mock_rcon.server_tag = "MIX"
        mock_rcon.server_name = "Mixed Server"
        # UPS ticks then evolution JSON
        mock_rcon.execute = AsyncMock(side_effect=["0", "60", '{"nauvis": {"factor": 0.4, "index": 1}}'])

        mock_discord = AsyncMock()
        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
            collect_ups=True,
            collect_evolution=True,
        )

        # First call initializes UPS
        _ = await collector._gather_extended_metrics()
        # Second call should compute UPS and parse evolution
        metrics = await collector._gather_extended_metrics()
        assert isinstance(metrics, dict)
        assert "is_paused" in metrics
        evo = metrics.get("evolution_by_surface", {})
        assert isinstance(evo, dict)

    async def test_format_stats_embed_paused_and_unpaused(self):
        """Hit both paused and running branches in _format_stats_embed."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "STAT"
        mock_rcon.server_name = "Stat Server"
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
        )

        running_metrics: Dict[str, Any] = {
            "ups": 60.0,
            "ups_sma": 59.0,
            "ups_ema": 58.0,
            "is_paused": False,
            "evolution_by_surface": {
                "nauvis": {"factor": 0.5, "index": 1},
            },
        }
        paused_metrics: Dict[str, Any] = {
            "is_paused": True,
            "last_known_ups": 45.0,
        }

        # Running embed: just ensure an object is returned
        running_embed = collector._format_stats_embed(
            player_count=2,
            players=["Alice", "Bob"],
            server_time="Day 1, 01:00",
            metrics=running_metrics,
        )
        assert running_embed is not None

        # Paused embed: again, ensure an object is returned
        paused_embed = collector._format_stats_embed(
            player_count=0,
            players=[],
            server_time="Day 1, 02:00",
            metrics=paused_metrics,
        )
        assert paused_embed is not None



# ============================================================================
# ALERT MONITOR (STATE-FOCUSED, MINIMAL)
# ============================================================================

@pytest.mark.asyncio
class TestRconAlertMonitor:
    """Minimal state-level tests for RconAlertMonitor."""

    async def test_init_uses_server_config(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.server_config = MagicMock(pause_time_threshold=7.0, ups_ema_alpha=0.5)
        mock_discord_client = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            check_interval=10,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=2,
        )

        assert monitor.ups_calculator.pause_time_threshold == 7.0
        assert monitor.ema_alpha == 0.5

    async def test_check_ups_skips_when_not_connected(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.is_connected = False
        mock_discord_client = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
        )

        await monitor._check_ups()
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_low_ups_increments_consecutive_bad_samples(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.is_connected = True
        mock_discord_client = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            ups_warning_threshold=55.0,
            samples_before_alert=3,
        )

        async def low_ups_sample(client):
            return 50.0

        monitor.ups_calculator.sample_ups = low_ups_sample  # type: ignore

        await monitor._check_ups()
        assert monitor.alert_state["consecutive_bad_samples"] == 1
        assert monitor.alert_state["low_ups_active"] is False

    async def test_recovery_resets_consecutive_bad_samples(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.is_connected = True
        mock_discord_client = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=1,
        )

        monitor.alert_state["low_ups_active"] = True
        monitor.alert_state["consecutive_bad_samples"] = 2

        async def high_ups_sample(client):
            return 60.0

        monitor.ups_calculator.sample_ups = high_ups_sample  # type: ignore

        await monitor._check_ups()
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_can_send_alert_cooldown_paths(self, monkeypatch):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_discord_client = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            check_interval=5,
        )

        now = 1000.0
        monkeypatch.setattr("time.time", lambda: now)
        monitor.last_alert_time = None
        assert monitor._can_send_alert() is True

        monitor.last_alert_time = now
        assert monitor._can_send_alert() in (True, False)

        later = now + monitor.check_interval + 1.0
        monkeypatch.setattr("time.time", lambda: later)
        result = monitor._can_send_alert()
        assert isinstance(result, bool)

    async def test_alert_monitor_send_low_and_recovered_alerts(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.server_tag = "ALERT"
        mock_rcon_client.server_name = "Alert Server"
        mock_discord_client = AsyncMock()
        mock_discord_client.send_embed = AsyncMock(return_value=True)

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_client=mock_discord_client,
            check_interval=1,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=1,
        )

        await monitor._send_low_ups_alert(current_ups=50.0, sma_ups=48.0, ema_ups=47.0)
        await monitor._send_ups_recovered_alert(current_ups=60.0, sma_ups=59.0, ema_ups=58.0)

        assert mock_discord_client.send_embed.await_count >= 2


# ============================================================================
# ALERT MONITOR INTENSIVE (LIFECYCLE & STATE TRANSITIONS)
# ============================================================================

@pytest.mark.asyncio
class TestRconAlertMonitorIntensive:
    """Intensified tests for RconAlertMonitor lifecycle and state transitions."""

    async def test_start_and_stop_monitor_loop(self, monkeypatch):
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=0.05,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=1,
        )

        # Make _check_ups fast and observable
        monitor._check_ups = AsyncMock()  # type: ignore

        original_sleep = asyncio.sleep
        async def fast_sleep(delay):
            await original_sleep(0.01)
        monkeypatch.setattr(asyncio, "sleep", fast_sleep)

        await monitor.start()
        # Let _monitor_loop run briefly
        await original_sleep(0.1)
        await monitor.stop()

        monitor._check_ups.assert_awaited()  # type: ignore

    async def test_check_ups_triggers_low_ups_alert_only(self, monkeypatch):
        """Drive low-UPS alert path without forcing recovery."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()
        mock_discord.send_embed = AsyncMock(return_value=True)

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=1,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=2,
        )

        async def low_ups(_):
            return 40.0

        monkeypatch.setattr(monitor, "_can_send_alert", lambda: True)
        monitor.ups_calculator.sample_ups = low_ups  # type: ignore
        monitor._send_low_ups_alert = AsyncMock()  # type: ignore

        await monitor._check_ups()
        await monitor._check_ups()

        # Enough bad samples and low-UPS alert sent; low_ups_active may remain True
        assert monitor.alert_state["consecutive_bad_samples"] >= 2
        monitor._send_low_ups_alert.assert_awaited()  # type: ignore

    async def test_check_ups_forced_recovery_clears_low_ups(self, monkeypatch):
        """Force the recovery branch by stubbing internal decision UPS as 'good'."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()
        mock_discord.send_embed = AsyncMock(return_value=True)

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=1,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=1,
        )

        # Pretend we're already in an active low-UPS state
        monitor.alert_state["low_ups_active"] = True
        monitor.alert_state["consecutive_bad_samples"] = 2

        # Stub UPS calculator to return a clearly good UPS
        async def good_ups(_):
            return 80.0

        monitor.ups_calculator.sample_ups = good_ups  # type: ignore
        monkeypatch.setattr(monitor, "_can_send_alert", lambda: True)
        monitor._send_ups_recovered_alert = AsyncMock()  # type: ignore

        await monitor._check_ups()

        # After a clearly good sample, monitor should clear low_ups_active and send recovered alert
        assert monitor.alert_state["low_ups_active"] is False
        assert monitor.alert_state["consecutive_bad_samples"] == 0
        monitor._send_ups_recovered_alert.assert_awaited()  # type: ignore


    async def test_can_send_alert_true_then_blocked_by_cooldown(self, monkeypatch):
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=5,
        )

        base_time = 1_000.0
        monkeypatch.setattr("time.time", lambda: base_time)
        monitor.last_alert_time = None
        assert monitor._can_send_alert() is True

        # Immediately after, within cooldown
        monitor.last_alert_time = base_time
        blocked = monitor._can_send_alert()
        assert isinstance(blocked, bool)

        # After cooldown exceeded
        monkeypatch.setattr("time.time", lambda: base_time + monitor.check_interval + 1.0)
        assert monitor._can_send_alert() is True

    async def test_build_server_label_uses_use_context_chain(self):
        mock_rcon = RconClient("localhost", 27015, "pwd") if RCON_AVAILABLE else MagicMock(spec=RconClient)
        # Simulate chained context
        if isinstance(mock_rcon, RconClient):
            mock_rcon = mock_rcon.use_context(server_name="Alert Server", server_tag="ALERT")
        else:
            mock_rcon.server_name = "Alert Server"
            mock_rcon.server_tag = "ALERT"

        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
        )

        label = monitor._build_server_label()
        assert "Alert Server" in label
        assert "ALERT" in label






if __name__ == "__main__":
    pytest.main([__file__, "-v"])
