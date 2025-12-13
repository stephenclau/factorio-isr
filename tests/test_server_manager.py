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

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# conftest.py handles sys.path - just import directly
from server_manager import ServerManager
from config import ServerConfig
from discord_interface import DiscordInterface


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_discord_interface() -> MagicMock:
    """Mock DiscordInterface for ServerManager tests."""
    interface = MagicMock(spec=DiscordInterface)
    interface.is_connected = True
    interface.send_message = AsyncMock(return_value=True)
    interface.send_embed = AsyncMock(return_value=True)
    interface.use_channel = MagicMock(return_value=MagicMock())
    return interface


@pytest.fixture
def sample_server_config() -> ServerConfig:
    """Provide a valid ServerConfig for testing."""
    return ServerConfig(
        tag="test",
        name="Test Server",
        rcon_host="localhost",
        rcon_port=27015,
        rcon_password="test123",
        description="Test server description",
        event_channel_id=123456789,
        stats_interval=300,
        collect_ups=True,
        collect_evolution=True,
        enable_alerts=True,
        alert_check_interval=60,
        alert_samples_required=3,
        ups_warning_threshold=55.0,
        ups_recovery_threshold=58.0,
        alert_cooldown=300,
        enable_stats_collector=True,
        enable_ups_stat=True,
        enable_evolution_stat=True,
    )


@pytest.fixture
def minimal_server_config() -> ServerConfig:
    """Provide a minimal ServerConfig (no alerts, no stats)."""
    return ServerConfig(
        tag="minimal",
        name="Minimal Server",
        rcon_host="localhost",
        rcon_port=27016,
        rcon_password="minimal123",
        event_channel_id=None,  # No stats collector
        enable_alerts=False,  # No alert monitor
    )


@pytest.fixture
def server_manager(mock_discord_interface: MagicMock) -> ServerManager:
    """Create a ServerManager instance with mocked Discord interface."""
    return ServerManager(discord_interface=mock_discord_interface)


@pytest.fixture
def mock_rcon_client() -> MagicMock:
    """
    Mock RconClient with method chaining support.

    Supports: RconClient(...).use_context(...) pattern
    """
    client_instance = MagicMock()
    client_instance.is_connected = False  # Starts disconnected
    client_instance.server_name = "Test Server"
    client_instance.server_tag = "test"
    client_instance.start = AsyncMock()
    client_instance.stop = AsyncMock()

    # Mock use_context to return self (for chaining)
    client_instance.use_context = MagicMock(return_value=client_instance)

    # When start() is awaited, set is_connected = True
    async def mock_start() -> None:
        client_instance.is_connected = True

    client_instance.start.side_effect = mock_start
    return client_instance


@pytest.fixture
def mock_stats_collector() -> MagicMock:
    """Mock RconStatsCollector."""
    collector = MagicMock()
    collector.start = AsyncMock()
    collector.stop = AsyncMock()
    return collector


@pytest.fixture
def mock_alert_monitor() -> MagicMock:
    """Mock RconAlertMonitor."""
    monitor = MagicMock()
    monitor.start = AsyncMock()
    monitor.stop = AsyncMock()
    monitor.alert_state = {"low_ups_active": False, "consecutive_bad_samples": 0}
    return monitor


@pytest.fixture
def mock_metrics_engine() -> MagicMock:
    """Mock RconMetricsEngine."""
    engine = MagicMock()
    return engine


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


class TestServerManagerInit:
    """Test ServerManager initialization."""

    def test_init_with_discord_interface(
        self, mock_discord_interface: MagicMock
    ) -> None:
        manager = ServerManager(discord_interface=mock_discord_interface)
        assert manager.discord_interface is mock_discord_interface
        assert manager.servers == {}
        assert manager.clients == {}
        assert manager.stats_collectors == {}
        assert manager.alert_monitors == {}
        assert manager.metrics_engines == {}

    def test_init_empty_state(self, server_manager: ServerManager) -> None:
        """Verify all registries start empty."""
        assert len(server_manager.servers) == 0
        assert len(server_manager.clients) == 0
        assert len(server_manager.stats_collectors) == 0
        assert len(server_manager.alert_monitors) == 0
        assert len(server_manager.metrics_engines) == 0


# ============================================================================
# ADD SERVER TESTS (without defer_stats)
# ============================================================================


@pytest.mark.asyncio
class TestServerManagerAddServer:
    """Test add_server() method."""

    async def test_add_server_success_full_config(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """Add server with full configuration (client + collector + monitor)."""
        # Patch where classes are USED (server_manager module), not where defined
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor), patch(
            "server_manager.RconMetricsEngine", return_value=mock_metrics_engine
        ):
            await server_manager.add_server(sample_server_config)

        # Verify use_context was called with correct params
        mock_rcon_client.use_context.assert_called_once_with(
            server_name=sample_server_config.name,
            server_tag=sample_server_config.tag,
        )

        # Verify client.start() was awaited
        mock_rcon_client.start.assert_awaited_once()

        # Verify stats collector was created and started
        mock_stats_collector.start.assert_awaited_once()

        # Verify alert monitor was created and started
        mock_alert_monitor.start.assert_awaited_once()

        # Verify all components are registered
        assert sample_server_config.tag in server_manager.servers
        assert sample_server_config.tag in server_manager.clients
        assert sample_server_config.tag in server_manager.stats_collectors
        assert sample_server_config.tag in server_manager.alert_monitors

        # Verify client is connected
        assert server_manager.clients[sample_server_config.tag].is_connected

    async def test_add_server_minimal_config(
        self,
        server_manager: ServerManager,
        minimal_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """Add server with minimal config (no stats, no alerts)."""
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            await server_manager.add_server(minimal_server_config)

        # Client should be created and started
        assert minimal_server_config.tag in server_manager.clients
        mock_rcon_client.start.assert_awaited_once()

        # No stats collector (event_channel_id is None)
        assert minimal_server_config.tag not in server_manager.stats_collectors

        # No alert monitor (enable_alerts is False)
        assert minimal_server_config.tag not in server_manager.alert_monitors

    async def test_add_server_duplicate_tag_raises_value_error(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """Adding server with duplicate tag raises ValueError."""
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            await server_manager.add_server(sample_server_config)

        # Try to add again - should raise before creating new client
        with pytest.raises(ValueError, match="already exists"):
            await server_manager.add_server(sample_server_config)

    async def test_add_server_connection_failure_cleanup(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
    ) -> None:
        """When RCON connection fails, all components are cleaned up."""
        # Create mock that fails on start()
        failing_client = MagicMock()
        failing_client.use_context = MagicMock(return_value=failing_client)
        failing_client.start = AsyncMock(side_effect=ConnectionError("Connection failed"))
        failing_client.stop = AsyncMock()

        with patch("server_manager.RconClient", return_value=failing_client):
            with pytest.raises(ConnectionError, match="Connection failed"):
                await server_manager.add_server(sample_server_config)

        # When client.start() fails BEFORE adding to self.clients,
        # the cleanup code never calls stop() because:
        # if config.tag in self.clients: <- This is False
        # await self.clients[config.tag].stop()
        #
        # So stop() should NOT be called in this scenario
        failing_client.stop.assert_not_awaited()

        # Verify nothing was registered after cleanup
        assert sample_server_config.tag not in server_manager.servers
        assert sample_server_config.tag not in server_manager.clients
        assert sample_server_config.tag not in server_manager.stats_collectors
        assert sample_server_config.tag not in server_manager.alert_monitors

    async def test_add_server_stats_collector_failure_cleanup(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """When stats collector fails, RCON client is cleaned up."""
        # Mock collector that fails on start
        failing_collector = MagicMock()
        failing_collector.start = AsyncMock(side_effect=Exception("Collector failed"))
        failing_collector.stop = AsyncMock()

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=failing_collector
        ):
            with pytest.raises(Exception, match="Collector failed"):
                await server_manager.add_server(sample_server_config)

        # Verify cleanup: client.stop() was called
        mock_rcon_client.stop.assert_awaited()

        # Verify nothing remains registered
        assert sample_server_config.tag not in server_manager.clients
        assert sample_server_config.tag not in server_manager.stats_collectors

    async def test_add_server_alert_monitor_failure_cleanup(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
    ) -> None:
        """When alert monitor fails, client and collector are cleaned up."""
        # Mock monitor that fails on start
        failing_monitor = MagicMock()
        failing_monitor.start = AsyncMock(side_effect=Exception("Monitor failed"))
        failing_monitor.stop = AsyncMock()

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=failing_monitor):
            with pytest.raises(Exception, match="Monitor failed"):
                await server_manager.add_server(sample_server_config)

        # Verify all components were cleaned up
        mock_stats_collector.stop.assert_awaited()
        mock_rcon_client.stop.assert_awaited()
        assert sample_server_config.tag not in server_manager.clients
        assert sample_server_config.tag not in server_manager.stats_collectors
        assert sample_server_config.tag not in server_manager.alert_monitors

    async def test_add_server_use_context_wrapper_chain(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
    ) -> None:
        """
        use_context may return a wrapped client; ensure the wrapped instance is stored.

        This reflects the project's use_context chain patterns for richer context objects.
        """
        base_client = MagicMock()
        wrapped_client = MagicMock()
        wrapped_client.is_connected = False
        wrapped_client.start = AsyncMock()
        wrapped_client.stop = AsyncMock()

        # Simulate RconClient(...).use_context(...) returning a different instance
        base_client.use_context = MagicMock(return_value=wrapped_client)

        async def wrapped_start() -> None:
            wrapped_client.is_connected = True

        wrapped_client.start.side_effect = wrapped_start

        with patch("server_manager.RconClient", return_value=base_client):
            await server_manager.add_server(sample_server_config)

        # use_context should have been invoked on the base client
        base_client.use_context.assert_called_once_with(
            server_name=sample_server_config.name,
            server_tag=sample_server_config.tag,
        )

        # The stored client should be the wrapped instance
        stored_client = server_manager.clients[sample_server_config.tag]
        assert stored_client is wrapped_client
        assert stored_client.is_connected

    async def test_add_server_stats_flags_respected(
        self,
        server_manager: ServerManager,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
    ) -> None:
        """
        When event_channel_id is set but collect_ups/evolution are False,
        ensure the flags are propagated to RconStatsCollector.
        """
        config = ServerConfig(
            tag="nostats",
            name="No Stats Metrics",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="nostats",
            event_channel_id=111,
            stats_interval=120,
            collect_ups=False,
            collect_evolution=False,
            enable_alerts=False,
            enable_stats_collector=True,
            enable_ups_stat=False,
            enable_evolution_stat=False,
        )

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ) as collector_cls:
            await server_manager.add_server(config)

        # Collector is created despite metrics disabled, but flags must match config
        collector_cls.assert_called_once()
        kwargs = collector_cls.call_args.kwargs
        assert kwargs["enable_ups_stat"] is False
        assert kwargs["enable_evolution_stat"] is False

    async def test_add_server_alert_defaults_used_when_missing(
        self,
        server_manager: ServerManager,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
    ) -> None:
        """
        When alert fields are omitted, getattr default values in add_server are used.
        """
        # Deliberately omit alert_* fields; enable_alerts=True triggers default getattr
        config = ServerConfig(
            tag="defaults",
            name="Default Alerts Server",
            rcon_host="localhost",
            rcon_port=27017,
            rcon_password="defaults",
            event_channel_id=222,
            stats_interval=60,
            enable_alerts=True,
        )

        mock_monitor = MagicMock()
        mock_monitor.start = AsyncMock()
        mock_monitor.alert_state = {}

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_monitor) as mon_cls:
            await server_manager.add_server(config)

        # Check that getattr defaults from implementation are honored
        call_kwargs = mon_cls.call_args.kwargs
        assert call_kwargs["check_interval"] == 60
        assert call_kwargs["samples_before_alert"] == 3
        assert call_kwargs["ups_warning_threshold"] == 55.0
        assert call_kwargs["ups_recovery_threshold"] == 58.0
        assert call_kwargs["alert_cooldown"] == 300

    async def test_add_server_with_defer_stats_true(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
    ) -> None:
        """
        With defer_stats=True, client is added but stats_collector not started.

        User must call start_stats_for_server() later.
        """
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ):
            await server_manager.add_server(sample_server_config, defer_stats=True)

        # Client should be registered and started
        assert sample_server_config.tag in server_manager.clients
        mock_rcon_client.start.assert_awaited_once()

        # Stats collector should NOT be started
        assert sample_server_config.tag not in server_manager.stats_collectors
        mock_stats_collector.start.assert_not_awaited()

    async def test_add_server_with_defer_stats_no_cleanup_on_client_start_fail(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
    ) -> None:
        """
        With defer_stats=True, if client.start() fails during add_server,
        cleanup still occurs but stats collectors are never created.
        """
        failing_client = MagicMock()
        failing_client.use_context = MagicMock(return_value=failing_client)
        failing_client.start = AsyncMock(side_effect=ConnectionError("Connection failed"))
        failing_client.stop = AsyncMock()

        with patch("server_manager.RconClient", return_value=failing_client):
            with pytest.raises(ConnectionError, match="Connection failed"):
                await server_manager.add_server(sample_server_config, defer_stats=True)

        # Cleanup should occur
        failing_client.stop.assert_not_awaited()
        assert sample_server_config.tag not in server_manager.clients


# ============================================================================
# START STATS FOR SERVER TESTS
# ============================================================================


@pytest.mark.asyncio
class TestServerManagerStartStatsForServer:
    """Test start_stats_for_server() method - new feature for deferred stats."""

    async def test_start_stats_for_server_success(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """
        After add_server with defer_stats=True, start_stats_for_server() starts
        stats and alert monitoring.
        """
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor), patch(
            "server_manager.RconMetricsEngine", return_value=mock_metrics_engine
        ):
            # Add server with defer_stats=True
            await server_manager.add_server(sample_server_config, defer_stats=True)

            # Now start stats
            await server_manager.start_stats_for_server(sample_server_config.tag)

        # Verify metrics engine was created (lazy-loaded)
        assert sample_server_config.tag in server_manager.metrics_engines

        # Verify stats collector was started
        mock_stats_collector.start.assert_awaited_once()

        # Verify alert monitor was started
        mock_alert_monitor.start.assert_awaited_once()

        # Verify both are registered
        assert sample_server_config.tag in server_manager.stats_collectors
        assert sample_server_config.tag in server_manager.alert_monitors

    async def test_start_stats_for_server_nonexistent_tag_raises_key_error(
        self, server_manager: ServerManager
    ) -> None:
        """start_stats_for_server() on non-existent tag raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await server_manager.start_stats_for_server("nonexistent")

    async def test_start_stats_for_server_already_started_raises_runtime_error(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
    ) -> None:
        """
        Calling start_stats_for_server() twice raises RuntimeError.

        This prevents double-starting.
        """
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            # Add with defer_stats=True
            await server_manager.add_server(sample_server_config, defer_stats=True)

            # Start stats once
            await server_manager.start_stats_for_server(sample_server_config.tag)

            # Try to start again - should raise
            with pytest.raises(RuntimeError, match="already started"):
                await server_manager.start_stats_for_server(sample_server_config.tag)

    async def test_start_stats_for_server_respects_enable_stats_collector_flag(
        self,
        server_manager: ServerManager,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
    ) -> None:
        """
        When enable_stats_collector=False, no collector is created even if
        event_channel_id is set.
        """
        config = ServerConfig(
            tag="no-collector",
            name="No Collector",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="nocollector",
            event_channel_id=999,
            enable_stats_collector=False,  # Explicitly disabled
            enable_alerts=True,
        )

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            await server_manager.add_server(config, defer_stats=True)
            await server_manager.start_stats_for_server(config.tag)

        # Collector should NOT be created or started
        mock_stats_collector.start.assert_not_awaited()
        assert config.tag not in server_manager.stats_collectors

        # Alert monitor should still be created
        mock_alert_monitor.start.assert_awaited_once()
        assert config.tag in server_manager.alert_monitors

    async def test_start_stats_for_server_uses_shared_metrics_engine(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """
        start_stats_for_server() gets or creates metrics engine and passes
        it to stats collector.
        """
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ) as collector_cls, patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor), patch(
            "server_manager.RconMetricsEngine", return_value=mock_metrics_engine
        ):
            await server_manager.add_server(sample_server_config, defer_stats=True)
            await server_manager.start_stats_for_server(sample_server_config.tag)

        # Verify metrics engine was passed to stats collector
        collector_cls.assert_called_once()
        collector_kwargs = collector_cls.call_args.kwargs
        assert collector_kwargs["metrics_engine"] is mock_metrics_engine

    async def test_start_stats_for_server_uses_per_server_channel(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
        mock_discord_interface: MagicMock,
    ) -> None:
        """
        When event_channel_id is set, use_channel() is called to bind
        stats collector to that channel.
        """
        mock_per_channel_interface = MagicMock()
        mock_discord_interface.use_channel.return_value = mock_per_channel_interface

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ) as collector_cls, patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            await server_manager.add_server(sample_server_config, defer_stats=True)
            await server_manager.start_stats_for_server(sample_server_config.tag)

        # Verify use_channel was called with the correct channel_id
        mock_discord_interface.use_channel.assert_called_once_with(
            sample_server_config.event_channel_id
        )

        # Verify collector received the per-channel interface
        collector_kwargs = collector_cls.call_args.kwargs
        assert collector_kwargs["discord_interface"] is mock_per_channel_interface

    async def test_start_stats_for_server_alert_with_per_channel_interface(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
        mock_discord_interface: MagicMock,
    ) -> None:
        """
        When event_channel_id is set and alerts enabled, alert monitor
        also gets the per-channel interface.
        """
        mock_per_channel_interface = MagicMock()
        mock_discord_interface.use_channel.return_value = mock_per_channel_interface

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch(
            "server_manager.RconAlertMonitor", return_value=mock_alert_monitor
        ) as alert_cls:
            await server_manager.add_server(sample_server_config, defer_stats=True)
            await server_manager.start_stats_for_server(sample_server_config.tag)

        # Verify alert monitor received the per-channel interface
        alert_kwargs = alert_cls.call_args.kwargs
        assert alert_kwargs["discord_interface"] is mock_per_channel_interface

    async def test_start_stats_for_server_alert_without_channel_uses_global(
        self,
        server_manager: ServerManager,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
        mock_discord_interface: MagicMock,
    ) -> None:
        """
        When event_channel_id is None but alerts enabled, alert monitor
        uses the global discord_interface.
        """
        config = ServerConfig(
            tag="no-channel",
            name="No Channel",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="nochannel",
            event_channel_id=None,  # No channel
            enable_alerts=True,
        )

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch(
            "server_manager.RconAlertMonitor", return_value=mock_alert_monitor
        ) as alert_cls:
            await server_manager.add_server(config, defer_stats=True)
            await server_manager.start_stats_for_server(config.tag)

        # Verify alert monitor received the global interface
        alert_kwargs = alert_cls.call_args.kwargs
        assert alert_kwargs["discord_interface"] is mock_discord_interface


# ============================================================================
# GET METRICS ENGINE TESTS
# ============================================================================


@pytest.mark.asyncio
class TestServerManagerGetMetricsEngine:
    """Test get_metrics_engine() - lazy-loaded singleton per server."""

    async def test_get_metrics_engine_creates_on_first_call(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """
        First call to get_metrics_engine() creates a new engine
        and caches it.
        """
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconMetricsEngine", return_value=mock_metrics_engine
        ) as engine_cls:
            await server_manager.add_server(sample_server_config, defer_stats=True)

            # First call - should create
            engine1 = server_manager.get_metrics_engine(sample_server_config.tag)

        # Verify constructor was called
        engine_cls.assert_called_once()
        engine_call_kwargs = engine_cls.call_args.kwargs
        assert engine_call_kwargs["enable_ups_stat"] == sample_server_config.enable_ups_stat
        assert engine_call_kwargs["enable_evolution_stat"] == sample_server_config.enable_evolution_stat

        assert engine1 is mock_metrics_engine

    async def test_get_metrics_engine_returns_cached_instance(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """
        Subsequent calls to get_metrics_engine() return cached instance
        without creating a new one.
        """
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconMetricsEngine", return_value=mock_metrics_engine
        ) as engine_cls:
            await server_manager.add_server(sample_server_config, defer_stats=True)

            # First call
            engine1 = server_manager.get_metrics_engine(sample_server_config.tag)

            # Reset mock to verify no new call
            engine_cls.reset_mock()

            # Second call
            engine2 = server_manager.get_metrics_engine(sample_server_config.tag)

        # Should not call constructor again
        engine_cls.assert_not_called()

        # Should return the same instance
        assert engine1 is engine2

    async def test_get_metrics_engine_nonexistent_server_returns_none(
        self, server_manager: ServerManager
    ) -> None:
        """get_metrics_engine() returns None for non-existent server."""
        result = server_manager.get_metrics_engine("nonexistent")
        assert result is None

    async def test_get_metrics_engine_respects_config_flags(
        self,
        server_manager: ServerManager,
        mock_rcon_client: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """
        Metrics engine is created with enable flags from ServerConfig.
        """
        config = ServerConfig(
            tag="custom-flags",
            name="Custom Flags",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="custom",
            enable_ups_stat=False,
            enable_evolution_stat=True,
        )

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconMetricsEngine", return_value=mock_metrics_engine
        ) as engine_cls:
            await server_manager.add_server(config, defer_stats=True)

            server_manager.get_metrics_engine(config.tag)

        # Verify flags were passed
        engine_kwargs = engine_cls.call_args.kwargs
        assert engine_kwargs["enable_ups_stat"] is False
        assert engine_kwargs["enable_evolution_stat"] is True


# ============================================================================
# REMOVE SERVER TESTS
# ============================================================================


@pytest.mark.asyncio
class TestServerManagerRemoveServer:
    """Test remove_server() method."""

    async def test_remove_server_success(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
    ) -> None:
        """Successfully remove a server with all components."""
        # Add server first
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            await server_manager.add_server(sample_server_config)

        # Now remove it
        await server_manager.remove_server(sample_server_config.tag)

        # Verify stop was called in correct order: monitor -> collector -> client
        mock_alert_monitor.stop.assert_awaited_once()
        mock_stats_collector.stop.assert_awaited_once()
        mock_rcon_client.stop.assert_awaited()

        # Verify all components were unregistered
        assert sample_server_config.tag not in server_manager.servers
        assert sample_server_config.tag not in server_manager.clients
        assert sample_server_config.tag not in server_manager.stats_collectors
        assert sample_server_config.tag not in server_manager.alert_monitors

    async def test_remove_server_nonexistent_tag_raises_key_error(
        self, server_manager: ServerManager
    ) -> None:
        """Removing non-existent server raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await server_manager.remove_server("nonexistent")

    async def test_remove_server_minimal_config(
        self,
        server_manager: ServerManager,
        minimal_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """Remove server with minimal config (no stats, no alerts)."""
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            await server_manager.add_server(minimal_server_config)

        await server_manager.remove_server(minimal_server_config.tag)

        # Client stop should be called
        assert mock_rcon_client.stop.await_count >= 1
        assert minimal_server_config.tag not in server_manager.clients

    async def test_remove_server_with_failing_monitor_stop(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
    ) -> None:
        """Removal continues even if alert monitor stop fails."""
        # Make monitor.stop() fail
        mock_alert_monitor.stop = AsyncMock(side_effect=Exception("Stop failed"))

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            await server_manager.add_server(sample_server_config)

        # Remove should not raise, despite monitor.stop() failing
        await server_manager.remove_server(sample_server_config.tag)

        # Verify cleanup continued despite monitor failure
        mock_stats_collector.stop.assert_awaited_once()
        assert mock_rcon_client.stop.await_count >= 1
        assert sample_server_config.tag not in server_manager.servers

    async def test_remove_server_with_all_stops_failing(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
    ) -> None:
        """Removal completes even if all component stops fail."""
        # Create mocks that all fail on stop
        failing_client = MagicMock()
        failing_client.use_context = MagicMock(return_value=failing_client)
        failing_client.start = AsyncMock()
        failing_client.stop = AsyncMock(side_effect=Exception("Client stop failed"))

        failing_collector = MagicMock()
        failing_collector.start = AsyncMock()
        failing_collector.stop = AsyncMock(
            side_effect=Exception("Collector stop failed")
        )

        failing_monitor = MagicMock()
        failing_monitor.start = AsyncMock()
        failing_monitor.stop = AsyncMock(side_effect=Exception("Monitor stop failed"))
        failing_monitor.alert_state = {}

        # Client needs is_connected to work
        async def set_connected() -> None:
            failing_client.is_connected = True

        failing_client.is_connected = False
        failing_client.start.side_effect = set_connected

        with patch("server_manager.RconClient", return_value=failing_client), patch(
            "server_manager.RconStatsCollector", return_value=failing_collector
        ), patch("server_manager.RconAlertMonitor", return_value=failing_monitor):
            await server_manager.add_server(sample_server_config)

            # Remove should not raise
            await server_manager.remove_server(sample_server_config.tag)

        # Verify all components were unregistered despite failures
        assert sample_server_config.tag not in server_manager.servers
        assert sample_server_config.tag not in server_manager.clients
        assert sample_server_config.tag not in server_manager.stats_collectors
        assert sample_server_config.tag not in server_manager.alert_monitors

    async def test_remove_server_cleans_up_metrics_engine(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """Removing a server also cleans up its cached metrics engine."""
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconMetricsEngine", return_value=mock_metrics_engine
        ):
            await server_manager.add_server(sample_server_config, defer_stats=True)

            # Pre-load metrics engine
            server_manager.get_metrics_engine(sample_server_config.tag)
            assert sample_server_config.tag in server_manager.metrics_engines

        # Remove server
        await server_manager.remove_server(sample_server_config.tag)

        # Metrics engine should be cleaned up
        assert sample_server_config.tag not in server_manager.metrics_engines


# ============================================================================
# GETTER METHOD TESTS
# ============================================================================


@pytest.mark.asyncio
class TestServerManagerGetters:
    """Test getter methods (get_client, get_config, get_collector, get_alert_monitor)."""

    async def test_get_client_success(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            await server_manager.add_server(sample_server_config)

        client = server_manager.get_client(sample_server_config.tag)
        # Client should be the mock instance (not the class)
        assert client is mock_rcon_client

    async def test_get_client_nonexistent_tag_raises_key_error(
        self, server_manager: ServerManager
    ) -> None:
        with pytest.raises(KeyError, match="not found"):
            server_manager.get_client("nonexistent")

    async def test_get_client_error_message_includes_available_tags(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """KeyError message includes list of available tags."""
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            await server_manager.add_server(sample_server_config)

        with pytest.raises(KeyError, match=f"Available.*{sample_server_config.tag}"):
            server_manager.get_client("wrong")

    async def test_get_config_success(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            await server_manager.add_server(sample_server_config)

        config = server_manager.get_config(sample_server_config.tag)
        assert config is sample_server_config
        assert config.name == "Test Server"

    async def test_get_config_nonexistent_tag(
        self, server_manager: ServerManager
    ) -> None:
        with pytest.raises(KeyError, match="not found"):
            server_manager.get_config("nonexistent")

    async def test_get_collector_success(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
    ) -> None:
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ):
            await server_manager.add_server(sample_server_config)

        collector = server_manager.get_collector(sample_server_config.tag)
        assert collector is mock_stats_collector

    async def test_get_collector_nonexistent_raises_key_error(
        self, server_manager: ServerManager
    ) -> None:
        with pytest.raises(KeyError, match="not found"):
            server_manager.get_collector("nonexistent")

    async def test_get_alert_monitor_success(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
    ) -> None:
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            await server_manager.add_server(sample_server_config)

        monitor = server_manager.get_alert_monitor(sample_server_config.tag)
        assert monitor is mock_alert_monitor

    async def test_get_alert_monitor_nonexistent(
        self, server_manager: ServerManager
    ) -> None:
        with pytest.raises(KeyError, match="not found"):
            server_manager.get_alert_monitor("nonexistent")


# ============================================================================
# LIST/SUMMARY METHOD TESTS
# ============================================================================


@pytest.mark.asyncio
class TestServerManagerListMethods:
    """Test list_tags, list_servers, get_status_summary, get_alert_states."""

    async def test_list_tags_empty(self, server_manager: ServerManager) -> None:
        tags = server_manager.list_tags()
        assert tags == []

    async def test_list_tags_multiple_servers(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        config2 = ServerConfig(
            tag="prod",
            name="Production",
            rcon_host="prod.example.com",
            rcon_port=27015,
            rcon_password="prod123",
        )

        # Create second mock client
        mock_client2 = MagicMock()
        mock_client2.use_context = MagicMock(return_value=mock_client2)
        mock_client2.start = AsyncMock()
        mock_client2.stop = AsyncMock()
        mock_client2.is_connected = False

        async def set_conn2() -> None:
            mock_client2.is_connected = True

        mock_client2.start.side_effect = set_conn2

        with patch(
            "server_manager.RconClient", side_effect=[mock_rcon_client, mock_client2]
        ):
            await server_manager.add_server(sample_server_config)
            await server_manager.add_server(config2)

        tags = server_manager.list_tags()
        assert set(tags) == {"test", "prod"}

    async def test_list_servers_returns_copy(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """list_servers() returns a copy, not the internal dict."""
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            await server_manager.add_server(sample_server_config)

        servers = server_manager.list_servers()
        assert sample_server_config.tag in servers

        # Modify the returned dict
        servers["fake"] = MagicMock()

        # Original should be unchanged
        assert "fake" not in server_manager.servers

    async def test_get_status_summary_all_connected(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            await server_manager.add_server(sample_server_config)

        status = server_manager.get_status_summary()
        # Mock client gets is_connected = True after start()
        assert status == {sample_server_config.tag: True}

    async def test_get_status_summary_mixed_states(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
    ) -> None:
        """Test status summary with mixed connection states."""
        # First client - connected
        mock_client1 = MagicMock()
        mock_client1.use_context = MagicMock(return_value=mock_client1)
        mock_client1.is_connected = False

        async def connect1() -> None:
            mock_client1.is_connected = True

        mock_client1.start = AsyncMock(side_effect=connect1)

        # Second client - not connected
        mock_client2 = MagicMock()
        mock_client2.use_context = MagicMock(return_value=mock_client2)
        mock_client2.is_connected = False

        async def stay_disconnected() -> None:
            mock_client2.is_connected = False  # Stays False

        mock_client2.start = AsyncMock(side_effect=stay_disconnected)

        config2 = ServerConfig(
            tag="staging",
            name="Staging",
            rcon_host="staging.example.com",
            rcon_port=27015,
            rcon_password="staging123",
        )

        with patch(
            "server_manager.RconClient", side_effect=[mock_client1, mock_client2]
        ):
            await server_manager.add_server(sample_server_config)
            await server_manager.add_server(config2)

        status = server_manager.get_status_summary()
        assert status["test"] is True
        assert status["staging"] is False

    async def test_get_alert_states_returns_all_states(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
    ) -> None:
        # Set alert state before adding server
        mock_alert_monitor.alert_state = {
            "low_ups_active": True,
            "consecutive_bad_samples": 5,
        }

        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            await server_manager.add_server(sample_server_config)

        states = server_manager.get_alert_states()
        assert sample_server_config.tag in states
        # Should return the mock's alert_state
        assert states[sample_server_config.tag]["low_ups_active"] is True
        assert states[sample_server_config.tag]["consecutive_bad_samples"] == 5


# ============================================================================
# STOP ALL TESTS
# ============================================================================


@pytest.mark.asyncio
class TestServerManagerStopAll:
    """Test stop_all() method."""

    async def test_stop_all_empty(self, server_manager: ServerManager) -> None:
        """stop_all() on empty manager completes without error."""
        await server_manager.stop_all()
        assert len(server_manager.clients) == 0
        assert len(server_manager.metrics_engines) == 0

        # Second call should also be a no-op and not raise
        await server_manager.stop_all()
        assert len(server_manager.clients) == 0

    async def test_stop_all_single_server(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
    ) -> None:
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            await server_manager.add_server(sample_server_config)

        await server_manager.stop_all()

        # Verify all components were stopped
        mock_alert_monitor.stop.assert_awaited_once()
        mock_stats_collector.stop.assert_awaited_once()
        # Client.stop may be called multiple times (cleanup + remove)
        assert mock_rcon_client.stop.await_count >= 1

        # Verify all registries are empty
        assert len(server_manager.servers) == 0
        assert len(server_manager.clients) == 0
        assert len(server_manager.stats_collectors) == 0
        assert len(server_manager.alert_monitors) == 0
        assert len(server_manager.metrics_engines) == 0

    async def test_stop_all_multiple_servers(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """stop_all() removes all servers."""
        config2 = ServerConfig(
            tag="prod",
            name="Production",
            rcon_host="prod.example.com",
            rcon_port=27015,
            rcon_password="prod123",
        )

        mock_client2 = MagicMock()
        mock_client2.use_context = MagicMock(return_value=mock_client2)
        mock_client2.start = AsyncMock()
        mock_client2.stop = AsyncMock()
        mock_client2.is_connected = False

        async def connect2() -> None:
            mock_client2.is_connected = True

        mock_client2.start.side_effect = connect2

        with patch(
            "server_manager.RconClient", side_effect=[mock_rcon_client, mock_client2]
        ):
            await server_manager.add_server(sample_server_config)
            await server_manager.add_server(config2)

        await server_manager.stop_all()

        # Both clients should be stopped
        assert mock_rcon_client.stop.await_count >= 1
        assert mock_client2.stop.await_count >= 1

        # All registries should be empty
        assert len(server_manager.servers) == 0
        assert len(server_manager.clients) == 0

    async def test_stop_all_with_failures_continues(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """stop_all() continues even if individual server removals fail."""
        config2 = ServerConfig(
            tag="failing",
            name="Failing Server",
            rcon_host="fail.example.com",
            rcon_port=27015,
            rcon_password="fail123",
        )

        # Second client will fail on stop
        mock_client2 = MagicMock()
        mock_client2.use_context = MagicMock(return_value=mock_client2)
        mock_client2.start = AsyncMock()
        mock_client2.stop = AsyncMock(side_effect=Exception("Stop failed"))
        mock_client2.is_connected = False

        async def connect_fail() -> None:
            mock_client2.is_connected = True

        mock_client2.start.side_effect = connect_fail

        with patch(
            "server_manager.RconClient", side_effect=[mock_rcon_client, mock_client2]
        ):
            await server_manager.add_server(sample_server_config)
            await server_manager.add_server(config2)

        # stop_all should not raise, despite failure
        await server_manager.stop_all()

        # Both should be attempted
        assert mock_rcon_client.stop.await_count >= 1
        assert mock_client2.stop.await_count >= 1

        # All servers should be removed despite failures
        assert len(server_manager.servers) == 0
        assert len(server_manager.clients) == 0


# ============================================================================
# EDGE CASES AND INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
class TestServerManagerEdgeCases:
    """Test edge cases and integration scenarios."""

    async def test_defer_stats_flow_add_then_start(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
        mock_stats_collector: MagicMock,
        mock_alert_monitor: MagicMock,
    ) -> None:
        """
        Integration test: defer_stats=True -> add_server() -> start_stats_for_server()

        Simulates lazy initialization workflow.
        """
        with patch("server_manager.RconClient", return_value=mock_rcon_client), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch("server_manager.RconAlertMonitor", return_value=mock_alert_monitor):
            # Phase 1: Add server without starting stats
            await server_manager.add_server(sample_server_config, defer_stats=True)

            assert sample_server_config.tag in server_manager.clients
            assert sample_server_config.tag not in server_manager.stats_collectors
            mock_stats_collector.start.assert_not_awaited()

            # Phase 2: Start stats later
            await server_manager.start_stats_for_server(sample_server_config.tag)

            assert sample_server_config.tag in server_manager.stats_collectors
            mock_stats_collector.start.assert_awaited_once()

    async def test_multiple_servers_different_states(
        self,
        server_manager: ServerManager,
        mock_rcon_client: MagicMock,
    ) -> None:
        """Multiple servers can be in different states simultaneously."""
        config_full = ServerConfig(
            tag="full",
            name="Full Config",
            rcon_host="full.example.com",
            rcon_port=27015,
            rcon_password="full123",
            event_channel_id=999,
            enable_stats_collector=True,
            enable_alerts=True,
        )

        config_client_only = ServerConfig(
            tag="client-only",
            name="Client Only",
            rcon_host="client.example.com",
            rcon_port=27015,
            rcon_password="client123",
            event_channel_id=None,
        )

        mock_client2 = MagicMock()
        mock_client2.use_context = MagicMock(return_value=mock_client2)
        mock_client2.start = AsyncMock()
        mock_client2.is_connected = False

        async def connect2() -> None:
            mock_client2.is_connected = True

        mock_client2.start.side_effect = connect2

        mock_stats_collector = MagicMock()
        mock_stats_collector.start = AsyncMock()

        mock_alert_monitor = MagicMock()
        mock_alert_monitor.start = AsyncMock()

        with patch(
            "server_manager.RconClient", side_effect=[mock_rcon_client, mock_client2]
        ), patch(
            "server_manager.RconStatsCollector", return_value=mock_stats_collector
        ), patch(
            "server_manager.RconAlertMonitor", return_value=mock_alert_monitor
        ):
            # Add full config server
            await server_manager.add_server(config_full)
            assert "full" in server_manager.stats_collectors

            # Add minimal config server
            await server_manager.add_server(config_client_only)
            assert "client-only" not in server_manager.stats_collectors

        # Both clients should be present
        assert "full" in server_manager.clients
        assert "client-only" in server_manager.clients

    async def test_add_remove_add_same_server(
        self,
        server_manager: ServerManager,
        sample_server_config: ServerConfig,
        mock_rcon_client: MagicMock,
    ) -> None:
        """Server can be removed and re-added."""
        with patch("server_manager.RconClient", return_value=mock_rcon_client):
            # Add
            await server_manager.add_server(sample_server_config)
            assert sample_server_config.tag in server_manager.clients

            # Remove
            await server_manager.remove_server(sample_server_config.tag)
            assert sample_server_config.tag not in server_manager.clients

            # Re-add (need to reset mock state)
            mock_rcon_client.is_connected = False

            async def reconnect() -> None:
                mock_rcon_client.is_connected = True

            mock_rcon_client.start.side_effect = reconnect

            await server_manager.add_server(sample_server_config)
            assert sample_server_config.tag in server_manager.clients


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
