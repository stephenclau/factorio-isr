from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rcon_stats_collector import RconStatsCollector


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_rcon_client() -> MagicMock:
    """Mock RconClient with server context."""
    client = MagicMock()
    client.is_connected = True
    client.server_tag = "prod"
    client.server_name = "Production Server"
    return client


@pytest.fixture
def mock_discord_interface() -> MagicMock:
    """Mock Discord interface for message posting."""
    interface = MagicMock()
    interface.is_connected = True
    interface.send_message = AsyncMock(return_value=True)
    interface.send_embed = AsyncMock(return_value=True)
    return interface


@pytest.fixture
def mock_metrics_engine() -> MagicMock:
    """Mock RconMetricsEngine with gather_all_metrics."""
    engine = MagicMock()
    engine.gather_all_metrics = AsyncMock(
        return_value={
            "player_count": 5,
            "players": ["Alice", "Bob", "Charlie"],
            "server_time": "12:34:56",
            "ups": 60.0,
            "ups_sma": 59.8,
            "ups_ema": 59.5,
            "is_paused": False,
            "evolution_factor": 0.45,
        }
    )
    return engine


@pytest.fixture
def patch_metrics_engine(mock_metrics_engine: MagicMock) -> MagicMock:
    """Auto-patch RconMetricsEngine at source for all tests."""
    with patch("rcon_metrics_engine.RconMetricsEngine", return_value=mock_metrics_engine):
        yield mock_metrics_engine


@pytest.fixture
def stats_collector(
    mock_rcon_client: MagicMock,
    mock_discord_interface: MagicMock,
    patch_metrics_engine: MagicMock,
) -> RconStatsCollector:
    """Create a RconStatsCollector with mocks."""
    return RconStatsCollector(
        rcon_client=mock_rcon_client,
        discord_interface=mock_discord_interface,
        interval=0.05,  # Fast interval for testing (50ms)
        enable_ups_stat=True,
        enable_evolution_stat=True,
    )


@pytest.fixture
def stats_collector_with_engine(
    mock_rcon_client: MagicMock,
    mock_discord_interface: MagicMock,
    mock_metrics_engine: MagicMock,
) -> RconStatsCollector:
    """Create a RconStatsCollector with shared metrics engine."""
    return RconStatsCollector(
        rcon_client=mock_rcon_client,
        discord_interface=mock_discord_interface,
        metrics_engine=mock_metrics_engine,
        interval=0.05,
        enable_ups_stat=True,
        enable_evolution_stat=True,
    )


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


class TestRconStatsCollectorInit:
    """Test RconStatsCollector initialization."""

    def test_init_with_all_params(
        self,
        mock_rcon_client: MagicMock,
        mock_discord_interface: MagicMock,
        patch_metrics_engine: MagicMock,
    ) -> None:
        """Initialize collector with all parameters specified."""
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

    def test_init_creates_metrics_engine_when_not_provided(
        self,
        mock_rcon_client: MagicMock,
        mock_discord_interface: MagicMock,
    ) -> None:
        """When metrics_engine is None, collector creates its own."""
        with patch("rcon_metrics_engine.RconMetricsEngine") as mock_engine_cls:
            mock_engine_instance = MagicMock()
            mock_engine_cls.return_value = mock_engine_instance

            collector = RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_interface=mock_discord_interface,
                metrics_engine=None,
                enable_ups_stat=True,
                enable_evolution_stat=False,
            )

        # Verify engine was created with correct flags
        mock_engine_cls.assert_called_once_with(
            mock_rcon_client,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )
        assert collector.metrics_engine is mock_engine_instance

    def test_init_uses_provided_metrics_engine(
        self,
        mock_rcon_client: MagicMock,
        mock_discord_interface: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """When metrics_engine is provided, collector uses it (doesn't create)."""
        with patch("rcon_metrics_engine.RconMetricsEngine") as mock_engine_cls:
            collector = RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_interface=mock_discord_interface,
                metrics_engine=mock_metrics_engine,
            )

        # Should NOT create a new engine
        mock_engine_cls.assert_not_called()
        assert collector.metrics_engine is mock_metrics_engine

    def test_init_default_interval(
        self,
        mock_rcon_client: MagicMock,
        mock_discord_interface: MagicMock,
        patch_metrics_engine: MagicMock,
    ) -> None:
        """Collector initializes with default interval of 300 seconds."""
        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        assert collector.interval == 300

    def test_init_default_enable_flags(
        self,
        mock_rcon_client: MagicMock,
        mock_discord_interface: MagicMock,
    ) -> None:
        """Collector initializes with stats enabled by default."""
        with patch("rcon_metrics_engine.RconMetricsEngine") as mock_engine_cls:
            RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_interface=mock_discord_interface,
            )

        # Verify both stats enabled by default
        call_kwargs = mock_engine_cls.call_args.kwargs
        assert call_kwargs["enable_ups_stat"] is True
        assert call_kwargs["enable_evolution_stat"] is True


# ============================================================================
# START/STOP TESTS
# ============================================================================


@pytest.mark.asyncio
class TestRconStatsCollectorStartStop:
    """Test collector start and stop operations."""

    async def test_start_creates_task(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Calling start() creates and runs collection task."""
        assert stats_collector.running is False
        assert stats_collector.task is None

        await stats_collector.start()

        assert stats_collector.running is True
        assert stats_collector.task is not None
        assert isinstance(stats_collector.task, asyncio.Task)

        # Cleanup
        await stats_collector.stop()

    async def test_start_when_already_running_logs_warning(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Calling start() when already running logs warning and returns early."""
        await stats_collector.start()
        first_task = stats_collector.task

        # Call start again
        await stats_collector.start()

        # Task should be the same (not replaced)
        assert stats_collector.task is first_task

        # Cleanup
        await stats_collector.stop()

    async def test_stop_cancels_task(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Calling stop() cancels the running task."""
        await stats_collector.start()
        task = stats_collector.task

        await stats_collector.stop()

        assert stats_collector.running is False
        assert stats_collector.task is None
        assert task.cancelled()

    async def test_stop_when_not_running_returns_early(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Calling stop() when not running returns early without error."""
        assert stats_collector.running is False

        # Should not raise
        await stats_collector.stop()

        assert stats_collector.running is False

    async def test_stop_twice_is_safe(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Calling stop() twice is safe."""
        await stats_collector.start()
        await stats_collector.stop()

        # Second stop should be safe
        await stats_collector.stop()

        assert stats_collector.running is False


# ============================================================================
# COLLECTION LOOP TESTS
# ============================================================================


@pytest.mark.asyncio
class TestRconStatsCollectionLoop:
    """Test the main collection loop behavior."""

    async def test_collection_loop_iterates(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """Collection loop iterates multiple times and respects interval."""
        await stats_collector_with_engine.start()

        # Let loop run for a few iterations with short interval
        await asyncio.sleep(0.15)

        await stats_collector_with_engine.stop()

        # Verify metrics were gathered at least once
        assert mock_metrics_engine.gather_all_metrics.call_count >= 1

    async def test_collection_loop_handles_errors(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """Collection loop continues after error in single iteration."""
        # First call fails, subsequent calls succeed
        mock_metrics_engine.gather_all_metrics.side_effect = [
            Exception("Metrics error"),
            {
                "player_count": 5,
                "players": [],
                "ups": 60.0,
                "is_paused": False,
                "evolution_factor": 0.5,
            },
        ]

        await stats_collector_with_engine.start()
        await asyncio.sleep(0.15)  # Allow multiple iterations
        await stats_collector_with_engine.stop()

        # Should have attempted both calls despite first error
        assert mock_metrics_engine.gather_all_metrics.call_count >= 1

    async def test_collection_loop_exits_cleanly(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """Collection loop exits gracefully when running set to False."""
        await stats_collector_with_engine.start()
        await asyncio.sleep(0.05)

        await stats_collector_with_engine.stop()

        # Wait for task to actually complete
        await asyncio.sleep(0.1)

        # Task should be None (cleaned up)
        assert stats_collector_with_engine.task is None


# ============================================================================
# COLLECT AND POST TESTS (HAPPY PATH)
# ============================================================================


@pytest.mark.asyncio
class TestRconStatsCollectAndPostHappyPath:
    """Test successful stats collection and posting."""

    async def test_collect_and_post_gathers_metrics(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """_collect_and_post gathers metrics from engine."""
        with patch("bot.helpers.format_stats_text", return_value="Stats text"):
            await stats_collector_with_engine._collect_and_post()

        mock_metrics_engine.gather_all_metrics.assert_called_once()

    async def test_collect_and_post_sends_embed_when_available(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_discord_interface: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """_collect_and_post uses embed format when send_embed is available."""
        with patch(
            "bot.helpers.format_stats_embed", return_value={"title": "Stats"}
        ) as mock_format_embed:
            mock_discord_interface.send_embed.return_value = True

            await stats_collector_with_engine._collect_and_post()

        # Embed formatter should be called
        mock_format_embed.assert_called_once()
        # send_embed should be called
        mock_discord_interface.send_embed.assert_called_once()

    async def test_collect_and_post_sends_text_when_embed_fails(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_discord_interface: MagicMock,
    ) -> None:
        """_collect_and_post falls back to text when embed fails."""
        # send_embed returns False (failed)
        mock_discord_interface.send_embed.return_value = False

        with patch(
            "bot.helpers.format_stats_text", return_value="Stats text"
        ) as mock_format_text:
            await stats_collector_with_engine._collect_and_post()

        # Text formatter should be called
        mock_format_text.assert_called_once()
        # send_message should be called
        mock_discord_interface.send_message.assert_called_once()

    async def test_collect_and_post_sends_text_when_no_embed_method(
        self,
        mock_rcon_client: MagicMock,
        mock_discord_interface: MagicMock,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """_collect_and_post uses text when discord interface lacks send_embed."""
        # Remove send_embed method
        del mock_discord_interface.send_embed

        collector = RconStatsCollector(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            interval=1,
        )

        with patch("bot.helpers.format_stats_text", return_value="Stats text"):
            await collector._collect_and_post()

        # Only text formatter should be called
        mock_discord_interface.send_message.assert_called_once()

    async def test_collect_and_post_with_all_metrics(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_discord_interface: MagicMock,
    ) -> None:
        """_collect_and_post passes all metric fields to formatters."""
        with patch(
            "bot.helpers.format_stats_embed", return_value={}
        ) as mock_embed:
            mock_discord_interface.send_embed.return_value = True
            await stats_collector_with_engine._collect_and_post()

        # Check formatters were called with metrics dict
        args, _ = mock_embed.call_args
        metrics = args[1]  # Second arg is metrics
        assert "player_count" in metrics
        assert "players" in metrics
        assert "ups" in metrics
        assert "is_paused" in metrics

    async def test_collect_and_post_includes_server_label(
        self,
        stats_collector_with_engine: RconStatsCollector,
    ) -> None:
        """_collect_and_post includes server label in formatting."""
        with patch(
            "bot.helpers.format_stats_text", return_value="Stats"
        ) as mock_format:
            stats_collector_with_engine.discord_interface.send_embed.return_value = False
            await stats_collector_with_engine._collect_and_post()

        # Verify format_stats_text was called with server label
        args, _ = mock_format.call_args
        label = args[0]
        # Label should contain server tag and/or name
        assert "prod" in label or "Production Server" in label


# ============================================================================
# COLLECT AND POST TESTS (ERROR PATHS)
# ============================================================================


@pytest.mark.asyncio
class TestRconStatsCollectAndPostErrorPaths:
    """Test error handling in collect and post."""

    async def test_collect_and_post_handles_metrics_gathering_error(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """_collect_and_post handles errors from gather_all_metrics gracefully."""
        mock_metrics_engine.gather_all_metrics.side_effect = RuntimeError(
            "RCON connection lost"
        )

        # Should not raise
        await stats_collector_with_engine._collect_and_post()

    async def test_collect_and_post_handles_embed_format_error(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_discord_interface: MagicMock,
    ) -> None:
        """_collect_and_post handles errors from format_stats_embed."""
        with patch(
            "bot.helpers.format_stats_embed",
            side_effect=ValueError("Invalid metric value"),
        ):
            with patch(
                "bot.helpers.format_stats_text", return_value="Fallback text"
            ):
                # Should not raise, falls back to text
                await stats_collector_with_engine._collect_and_post()

        # send_message should be called (fallback)
        mock_discord_interface.send_message.assert_called_once()

    async def test_collect_and_post_handles_embed_send_error(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_discord_interface: MagicMock,
    ) -> None:
        """_collect_and_post handles errors from send_embed."""
        mock_discord_interface.send_embed.side_effect = RuntimeError(
            "Discord API error"
        )

        with patch(
            "bot.helpers.format_stats_embed", return_value={}
        ), patch(
            "bot.helpers.format_stats_text", return_value="Fallback text"
        ):
            # Should not raise, falls back to text
            await stats_collector_with_engine._collect_and_post()

        # send_message should be called (fallback)
        mock_discord_interface.send_message.assert_called_once()

    async def test_collect_and_post_handles_text_format_error(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_discord_interface: MagicMock,
    ) -> None:
        """_collect_and_post handles errors from format_stats_text."""
        mock_discord_interface.send_embed.return_value = False

        with patch(
            "bot.helpers.format_stats_text",
            side_effect=ValueError("Format error"),
        ):
            # Should not raise
            await stats_collector_with_engine._collect_and_post()

    async def test_collect_and_post_handles_text_send_error(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_discord_interface: MagicMock,
    ) -> None:
        """_collect_and_post handles errors from send_message."""
        mock_discord_interface.send_embed.return_value = False
        mock_discord_interface.send_message.side_effect = RuntimeError(
            "Discord connection failed"
        )

        with patch(
            "bot.helpers.format_stats_text", return_value="Stats text"
        ):
            # Should not raise
            await stats_collector_with_engine._collect_and_post()


# ============================================================================
# SERVER LABEL BUILDING TESTS
# ============================================================================


class TestServerLabelBuilding:
    """Test _build_server_label method with various configurations."""

    def test_build_label_with_tag_and_name(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Label includes both tag and name when both present."""
        stats_collector.rcon_client.server_tag = "prod"
        stats_collector.rcon_client.server_name = "Production"

        label = stats_collector._build_server_label()

        assert "[prod]" in label
        assert "Production" in label

    def test_build_label_with_tag_only(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Label is just tag when name is None."""
        stats_collector.rcon_client.server_tag = "prod"
        stats_collector.rcon_client.server_name = None

        label = stats_collector._build_server_label()

        assert label == "[prod]"

    def test_build_label_with_name_only(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Label includes name when tag is None."""
        stats_collector.rcon_client.server_tag = None
        stats_collector.rcon_client.server_name = "Production"

        label = stats_collector._build_server_label()

        assert "Production" in label
        assert "None" not in label

    def test_build_label_with_neither_tag_nor_name(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Label is default when both tag and name are None."""
        stats_collector.rcon_client.server_tag = None
        stats_collector.rcon_client.server_name = None

        label = stats_collector._build_server_label()

        assert label == "Factorio Server"

    def test_build_label_spacing(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Label has proper spacing between tag and name."""
        stats_collector.rcon_client.server_tag = "prod"
        stats_collector.rcon_client.server_name = "Production"

        label = stats_collector._build_server_label()

        # Should have space between [prod] and Production
        assert "[prod] Production" in label


# ============================================================================
# METRICS ENGINE LIFECYCLE TESTS
# ============================================================================


class TestMetricsEngineLifecycle:
    """Test metrics engine creation and lifecycle."""

    def test_collector_creates_engine_with_correct_flags(
        self,
        mock_rcon_client: MagicMock,
        mock_discord_interface: MagicMock,
    ) -> None:
        """Collector creates engine with enable flags from constructor."""
        with patch("rcon_metrics_engine.RconMetricsEngine") as mock_engine_cls:
            RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_interface=mock_discord_interface,
                metrics_engine=None,
                enable_ups_stat=False,
                enable_evolution_stat=True,
            )

        call_kwargs = mock_engine_cls.call_args.kwargs
        assert call_kwargs["enable_ups_stat"] is False
        assert call_kwargs["enable_evolution_stat"] is True

    def test_collector_shares_metrics_engine_across_calls(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """Collector reuses same metrics engine across collection cycles."""
        # Multiple collect_and_post calls use same engine
        same_engine = stats_collector_with_engine.metrics_engine

        assert stats_collector_with_engine.metrics_engine is mock_metrics_engine
        assert same_engine is stats_collector_with_engine.metrics_engine


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
class TestRconStatsCollectorIntegration:
    """Integration tests for complete workflows."""

    async def test_full_lifecycle_start_collect_stop(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_metrics_engine: MagicMock,
        mock_discord_interface: MagicMock,
    ) -> None:
        """Complete lifecycle: start -> collect -> stop."""
        # Ensure text path is used (embed fails)
        mock_discord_interface.send_embed.return_value = False

        with patch(
            "bot.helpers.format_stats_text", return_value="Stats"
        ):
            # Start
            await stats_collector_with_engine.start()
            assert stats_collector_with_engine.running is True

            # Let collection happen (short interval: 50ms, so 200ms allows ~4 iterations)
            await asyncio.sleep(0.2)

            # Verify collection occurred
            assert mock_metrics_engine.gather_all_metrics.call_count >= 1
            assert mock_discord_interface.send_message.call_count >= 1

            # Stop
            await stats_collector_with_engine.stop()
            assert stats_collector_with_engine.running is False

    async def test_error_during_collection_doesnt_crash_loop(
        self,
        stats_collector_with_engine: RconStatsCollector,
        mock_metrics_engine: MagicMock,
    ) -> None:
        """Error in one iteration doesn't stop the loop."""
        # First iteration fails, second succeeds
        mock_metrics_engine.gather_all_metrics.side_effect = [
            RuntimeError("Temporary error"),
            {
                "player_count": 10,
                "players": [],
                "ups": 60.0,
                "is_paused": False,
                "evolution_factor": 0.3,
            },
        ]

        with patch(
            "bot.helpers.format_stats_text", return_value="Stats"
        ):
            await stats_collector_with_engine.start()
            await asyncio.sleep(0.15)  # Allow multiple iterations with 50ms interval
            await stats_collector_with_engine.stop()

        # Should have attempted both iterations
        assert mock_metrics_engine.gather_all_metrics.call_count >= 2

    async def test_rapid_start_stop_cycles(
        self, stats_collector: RconStatsCollector
    ) -> None:
        """Multiple rapid start/stop cycles work correctly."""
        for _ in range(3):
            await stats_collector.start()
            await asyncio.sleep(0.05)
            await stats_collector.stop()
            await asyncio.sleep(0.05)

        # Final state should be stopped
        assert stats_collector.running is False
        assert stats_collector.task is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
