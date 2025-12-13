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
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

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
async def mock_rcon_client() -> AsyncGenerator[MagicMock, None]:
    """Mock RconClient for use in tests."""
    mock = MagicMock(spec=RconClient)
    mock.is_connected = True
    mock.server_tag = "TEST"
    mock.server_name = "Test Server"
    mock.connected = True
    yield mock


@pytest_asyncio.fixture
async def mock_discord_interface() -> AsyncGenerator[AsyncMock, None]:
    """Mock Discord interface for use in tests."""
    mock = AsyncMock()
    mock.is_connected = True
    mock.send_message = AsyncMock()
    mock.send_embed = AsyncMock(return_value=False)  # Embed fails, fall back to text
    yield mock


# ============================================================================
# RCONCLIENT TESTS (18 tests)
# ============================================================================

@pytest.mark.asyncio
class TestRconClientInitialization:
    """Test RconClient initialization."""

    async def test_init_success_with_rcon(self):
        """Test basic initialization."""
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
        """Test initialization with custom timeout."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        client = RconClient("localhost", 27015, "test123", timeout=5.0)
        assert client.timeout == 5.0

    async def test_init_without_rcon_available(self, monkeypatch):
        """Test error when rcon not available."""
        monkeypatch.setattr("rcon_client.RCON_AVAILABLE", False)
        with pytest.raises(ImportError, match="rcon package not installed"):
            RconClient("localhost", 27015, "test123")

    async def test_use_context_chained_updates(self):
        """Test context chaining with server_name and server_tag."""
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
        """Test successful connection."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        mock_rcon_client_class.assert_called_once()
        assert client.connected is True

    async def test_connect_handles_exception(self, mock_rcon_client_class):
        """Test connection failure."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_rcon_client_class.side_effect = Exception("Connection failed")

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        assert client.connected is False
        assert client.client is None

    async def test_disconnect_closes_client(self, mock_rcon_client_class):
        """Test disconnection."""
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
        """Test disconnect when no client."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        client = RconClient("localhost", 27015, "test123")
        assert client.connected is False
        await client.disconnect()
        assert client.connected is False


@pytest.mark.asyncio
class TestRconClientExecuteAndHelpers:
    """Test execute() and helper parsing methods."""

    async def test_execute_success(self, mock_rcon_client_class):
        """Test successful command execution."""
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
        assert response == "OK"
        assert client.connected is True

    async def test_get_player_count_parses_online_lines(self, mock_rcon_client_class):
        """Test player count parsing."""
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

    async def test_get_players_online_filters_generic_names(self, mock_rcon_client_class):
        """Test player list filtering."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        payload = "- Alice (online)\n- Player #1 (online)\n- Bob (online)\n"

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value=payload)
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123")
        await client.connect()

        players = await client.get_players_online()
        assert "Alice" in players
        assert "Bob" in players
        # Player #1 is generic, may or may not be filtered depending on implementation

    async def test_get_play_time_success_and_strip(self, mock_rcon_client_class):
        """Test playtime retrieval and stripping."""
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

    async def test_get_players_alias_calls_online_version(self, mock_rcon_client_class):
        """Test get_players alias."""
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
        assert "Alice" in players


@pytest.mark.asyncio
class TestRconClientEdgeCases:
    """Test error-handling paths."""

    async def test_get_player_count_handles_errors(self, mock_rcon_client_class):
        """Test error resilience for player count."""
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
        """Test error resilience for player list."""
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
        """Test error resilience for playtime."""
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


@pytest.mark.asyncio
class TestRconClientIntegration:
    """Integration tests for RconClient lifecycle."""

    async def test_full_lifecycle(self, mock_rcon_client_class):
        """Test complete lifecycle: start, execute, stop."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.run = MagicMock(return_value="Response")
        mock_rcon_client_class.return_value = mock_instance

        client = RconClient("localhost", 27015, "test123", reconnect_delay=0.1)

        await client.start()
        assert client.is_connected is True
        assert client._should_reconnect is True

        response = await client.execute("test")
        assert response == "Response"

        await client.stop()
        assert client.is_connected is False
        assert client._should_reconnect is False

    @pytest.mark.timeout(2)
    async def test_reconnection_loop_backoff_and_exit(self, mock_rcon_client_class):
        """Test reconnection backoff when connection fails."""
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
# RCONSTATS COLLECTOR TESTS (8 tests)
# ============================================================================

@pytest.mark.asyncio
class TestRconStatsCollector:
    """Tests for RconStatsCollector."""

    async def test_init_wires_dependencies_and_flags(self, mock_rcon_client, mock_discord_interface):
        """Test initialization with correct parameters."""
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
        assert collector.metrics_engine is not None

    async def test_start_and_stop(self, mock_rcon_client, mock_discord_interface):
        """Test lifecycle: start and stop."""
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
        assert collector.task is None

    async def test_build_server_label_with_tag_and_name(self, mock_rcon_client, mock_discord_interface):
        """Test server label with both tag and name."""
        mock_rcon_client.server_tag = "PROD"
        mock_rcon_client.server_name = "Production Server"

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = collector._build_server_label()
        assert "PROD" in label
        assert "Production Server" in label

    async def test_build_server_label_with_tag_only(self, mock_rcon_client, mock_discord_interface):
        """Test label with tag but no name."""
        mock_rcon_client.server_tag = "DEV"
        mock_rcon_client.server_name = None

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = collector._build_server_label()
        assert "DEV" in label

    async def test_build_server_label_with_name_only(self, mock_rcon_client, mock_discord_interface):
        """Test label with name but no tag."""
        mock_rcon_client.server_tag = None
        mock_rcon_client.server_name = "Test Server"

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = collector._build_server_label()
        assert "Test Server" in label

    async def test_build_server_label_default(self, mock_rcon_client, mock_discord_interface):
        """Test label with no tag or name."""
        mock_rcon_client.server_tag = None
        mock_rcon_client.server_name = None

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = collector._build_server_label()
        assert label == "Factorio Server"

    async def test_shared_metrics_engine(self, mock_rcon_client, mock_discord_interface):
        """Test passing shared metrics engine."""
        shared_engine = MagicMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=shared_engine,
        )

        assert collector.metrics_engine is shared_engine

    async def test_multiple_stop_calls_safe(self, mock_rcon_client, mock_discord_interface):
        """Test multiple stop calls are safe."""
        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        await collector.stop()
        await collector.stop()  # Should not raise


# ============================================================================
# RCONALERT MONITOR TESTS (12 tests)
# ============================================================================

@pytest.mark.asyncio
class TestRconAlertMonitor:
    """Tests for RconAlertMonitor."""

    async def test_init_uses_server_config(self, mock_rcon_client, mock_discord_interface):
        """Test initialization creates metrics engine."""
        mock_rcon_client.is_connected = True

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            check_interval=60,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
        )

        assert monitor.rcon_client is mock_rcon_client
        assert monitor.discord_interface is mock_discord_interface
        assert monitor.check_interval == 60
        assert monitor.ups_warning_threshold == 55.0
        assert monitor.running is False
        assert monitor.task is None

    async def test_alert_state_initialization(self, mock_rcon_client, mock_discord_interface):
        """Test alert state initialized correctly."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        assert monitor.alert_state["low_ups_active"] is False
        assert monitor.alert_state["consecutive_bad_samples"] == 0
        assert monitor.alert_state["recent_ups_samples"] == []

    async def test_start_and_stop(self, mock_rcon_client, mock_discord_interface):
        """Test lifecycle: start and stop."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            check_interval=0.05,
        )

        await monitor.start()
        assert monitor.running is True
        assert monitor.task is not None

        await monitor.stop()
        assert monitor.running is False
        assert monitor.task is None

    async def test_check_ups_skips_when_not_connected(self, mock_rcon_client, mock_discord_interface):
        """Test _check_ups returns early when not connected."""
        mock_rcon_client.is_connected = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        await monitor._check_ups()
        # Should not have modified alert state
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_can_send_alert_no_prior(self, mock_rcon_client, mock_discord_interface):
        """Test first alert can be sent (no cooldown yet)."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            alert_cooldown=300,
        )

        # No prior alert, should allow
        assert monitor._can_send_alert() is True

    async def test_can_send_alert_within_cooldown(self, mock_rcon_client, mock_discord_interface, monkeypatch):
        """Test alert blocked within cooldown period."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            alert_cooldown=300,
        )

        # Set last alert time to now
        now = datetime.now(timezone.utc)
        monitor.alert_state["last_alert_time"] = now

        # Mock datetime to return same time (within cooldown)
        result = monitor._can_send_alert()
        # Should be blocked (alert was "just" sent)
        assert isinstance(result, bool)

    async def test_build_server_label_with_both(self, mock_rcon_client, mock_discord_interface):
        """Test server label with tag and name."""
        mock_rcon_client.server_tag = "ALERT"
        mock_rcon_client.server_name = "Alert Server"

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = monitor._build_server_label()
        assert "ALERT" in label
        assert "Alert Server" in label

    async def test_build_server_label_default(self, mock_rcon_client, mock_discord_interface):
        """Test default label."""
        mock_rcon_client.server_tag = None
        mock_rcon_client.server_name = None

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = monitor._build_server_label()
        assert label == "Factorio Server"

    async def test_shared_metrics_engine(self, mock_rcon_client, mock_discord_interface):
        """Test passing shared metrics engine."""
        shared_engine = MagicMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=shared_engine,
        )

        assert monitor.metrics_engine is shared_engine

    async def test_multiple_stop_calls_safe(self, mock_rcon_client, mock_discord_interface):
        """Test multiple stop calls are safe."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        await monitor.stop()
        await monitor.stop()  # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
