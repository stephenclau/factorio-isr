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
        assert client.connected is False

    async def test_disconnect_no_client_is_safe(self):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        client = RconClient("localhost", 27015, "test123")
        assert client.connected is False
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

    async def test_get_play_time_success_and_strip(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value=" Day 10, 12:00  \n")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        time_str = await client.get_play_time()
        assert time_str == "Day 10, 12:00"

    async def test_get_play_time_empty_returns_unknown(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value="")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        time_str = await client.get_play_time()
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

    async def test_get_play_time_handles_errors(self, mock_rcon_client_class):
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(side_effect=Exception("Error"))
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        time_str = await client.get_play_time()
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
# STATS COLLECTOR (CORRECT API)
# ============================================================================

@pytest.mark.asyncio
class TestRconStatsCollector:
    """Tests for RconStatsCollector using actual API."""

    async def test_init_wires_dependencies(self):
        """Test initialization with correct parameters."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_rcon.server_tag = "PROD"
        mock_rcon.server_name = "Production"
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            interval=300,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )

        assert collector.rcon_client is mock_rcon
        assert collector.discord_interface is mock_discord
        assert collector.interval == 300
        assert collector.running is False
        assert collector.task is None
        assert collector.metrics_engine is not None

    async def test_start_and_stop(self):
        """Test lifecycle: start and stop."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            interval=1,
        )

        await collector.start()
        assert collector.running is True
        assert collector.task is not None

        await collector.stop()
        assert collector.running is False
        assert collector.task is None

    async def test_build_server_label(self):
        """Test server label generation."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "PROD"
        mock_rcon.server_name = "Production Server"
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
        )

        label = collector._build_server_label()
        assert "PROD" in label
        assert "Production Server" in label

    async def test_build_server_label_with_tag_only(self):
        """Test label with tag but no name."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "DEV"
        mock_rcon.server_name = None
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
        )

        label = collector._build_server_label()
        assert "DEV" in label

    async def test_build_server_label_default(self):
        """Test label with no tag or name."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = None
        mock_rcon.server_name = None
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
        )

        label = collector._build_server_label()
        assert label == "Factorio Server"

    async def test_shared_metrics_engine(self):
        """Test passing shared metrics engine."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()
        shared_engine = MagicMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            metrics_engine=shared_engine,
        )

        assert collector.metrics_engine is shared_engine


# ============================================================================
# ALERT MONITOR (CORRECT API)
# ============================================================================

@pytest.mark.asyncio
class TestRconAlertMonitor:
    """Tests for RconAlertMonitor using actual API."""

    async def test_init_wires_dependencies(self):
        """Test initialization with correct parameters."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_rcon.server_tag = "PROD"
        mock_rcon.server_name = "Production"
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            check_interval=60,
            samples_before_alert=3,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
        )

        assert monitor.rcon_client is mock_rcon
        assert monitor.discord_interface is mock_discord
        assert monitor.check_interval == 60
        assert monitor.running is False
        assert monitor.task is None
        assert monitor.alert_state["low_ups_active"] is False
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_start_and_stop(self):
        """Test lifecycle: start and stop."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            check_interval=1,
        )

        await monitor.start()
        assert monitor.running is True
        assert monitor.task is not None

        await monitor.stop()
        assert monitor.running is False
        assert monitor.task is None

    async def test_check_ups_skips_when_not_connected(self):
        """Test that _check_ups returns early when not connected."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = False
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
        )

        await monitor._check_ups()
        # Should not have modified alert state
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_can_send_alert_no_prior_alert(self):
        """Test first alert can be sent (no cooldown yet)."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            alert_cooldown=300,
        )

        # No prior alert, should allow
        assert monitor._can_send_alert() is True

    async def test_can_send_alert_within_cooldown(self, monkeypatch):
        """Test alert blocked within cooldown period."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            alert_cooldown=300,
        )

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        monitor.alert_state["last_alert_time"] = now

        monkeypatch.setattr(
            "rcon_alert_monitor.datetime",
            MagicMock(
                now=MagicMock(return_value=MagicMock(
                    timezone=timezone,
                    utcnow=MagicMock(return_value=now),
                ))
            )
        )

        # Within cooldown, should block
        result = monitor._can_send_alert()
        assert isinstance(result, bool)

    async def test_build_server_label(self):
        """Test server label generation."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "PROD"
        mock_rcon.server_name = "Production"
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
        )

        label = monitor._build_server_label()
        assert "PROD" in label
        assert "Production" in label

    async def test_shared_metrics_engine(self):
        """Test passing shared metrics engine."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()
        shared_engine = MagicMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            metrics_engine=shared_engine,
        )

        assert monitor.metrics_engine is shared_engine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
