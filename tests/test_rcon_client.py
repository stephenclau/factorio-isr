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
        """Test get_play_time (renamed from get_server_time)."""
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
# STATS COLLECTOR (BASIC + METRICS + EMBED)
# ============================================================================

@pytest.mark.asyncio
class TestRconStatsCollector:
    """Behavior tests for RconStatsCollector."""

    async def test_init_wires_dependencies_and_flags(self):
        """Test initialization with correct discord_interface parameter."""
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.server_tag = "TEST"
        mock_rcon_client.server_name = "Test Server"
        mock_rcon_client.is_connected = True
        mock_discord_interface = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            interval=300,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )

        assert collector.rcon_client is mock_rcon_client
        assert collector.discord_interface is mock_discord_interface
        assert collector.interval == 300
        assert collector.running is False
        assert collector.task is None

    async def test_start_and_stop(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.is_connected = True
        mock_discord_interface = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            interval=1,
        )

        await collector.start()
        assert collector.running is True
        assert collector.task is not None

        await collector.stop()
        assert collector.running is False

    async def test_build_server_label(self):
        """Test _build_server_label() method."""
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.server_tag = "PROD"
        mock_rcon_client.server_name = "Production Server"
        mock_discord_interface = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = collector._build_server_label()
        assert "PROD" in label
        assert "Production Server" in label


# ============================================================================
# ALERT MONITOR (STATE-FOCUSED, MINIMAL)
# ============================================================================

@pytest.mark.asyncio
class TestRconAlertMonitor:
    """Minimal state-level tests for RconAlertMonitor."""

    async def test_init_creates_metrics_engine(self):
        """Test initialization with correct discord_interface parameter."""
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.server_config = MagicMock(pause_time_threshold=7.0)
        mock_rcon_client.is_connected = True
        mock_discord_interface = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            check_interval=10,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=2,
        )

        assert monitor.rcon_client is mock_rcon_client
        assert monitor.discord_interface is mock_discord_interface
        assert monitor.check_interval == 10
        assert monitor.ups_warning_threshold == 55.0
        assert monitor.running is False

    async def test_check_ups_skips_when_not_connected(self):
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.is_connected = False
        mock_discord_interface = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        # Just ensure it doesn't crash when not connected
        await monitor._check_ups()
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_alert_state_initialization(self):
        """Test that alert_state is properly initialized."""
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.is_connected = True
        mock_discord_interface = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        assert monitor.alert_state["low_ups_active"] is False
        assert monitor.alert_state["consecutive_bad_samples"] == 0
        assert monitor.alert_state["recent_ups_samples"] == []

    async def test_can_send_alert_cooldown_logic(self, monkeypatch):
        """Test _can_send_alert() cooldown logic."""
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_discord_interface = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            check_interval=5,
            alert_cooldown=10,
        )

        # First alert should always be sendable
        assert monitor._can_send_alert() is True

    async def test_build_server_label(self):
        """Test _build_server_label() method."""
        mock_rcon_client = MagicMock(spec=RconClient)
        mock_rcon_client.server_tag = "ALERT"
        mock_rcon_client.server_name = "Alert Server"
        mock_discord_interface = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = monitor._build_server_label()
        assert "ALERT" in label
        assert "Alert Server" in label


@pytest.mark.asyncio
class TestRconAlertMonitorLifecycle:
    """Test RconAlertMonitor start/stop lifecycle."""

    async def test_start_and_stop(self):
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
            check_interval=0.05,
        )

        await monitor.start()
        assert monitor.running is True
        assert monitor.task is not None

        await monitor.stop()
        assert monitor.running is False
        assert monitor.task is None

    async def test_multiple_stop_calls_safe(self):
        """Multiple stop() calls should be safe."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_interface=mock_discord,
        )

        await monitor.start()
        await monitor.stop()
        # Second stop should not raise
        await monitor.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
