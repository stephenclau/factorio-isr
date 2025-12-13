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

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rcon_metrics_engine import RconMetricsEngine, UPSCalculator


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
    client.execute = AsyncMock()
    client.get_players = AsyncMock(return_value=["Alice", "Bob", "Charlie"])
    client.get_player_count = AsyncMock(return_value=3)
    client.get_play_time = AsyncMock(return_value="1h 23m 45s")
    client.server_config = None
    return client


@pytest.fixture
def mock_rcon_client_with_config() -> MagicMock:
    """Mock RconClient with server config."""
    client = MagicMock()
    client.is_connected = True
    client.server_tag = "staging"
    client.server_name = "Staging Server"
    client.execute = AsyncMock()
    client.get_players = AsyncMock(return_value=[])
    client.get_player_count = AsyncMock(return_value=0)
    client.get_play_time = AsyncMock(return_value="0h 0m 0s")
    
    # Mock server config with custom thresholds
    config = MagicMock()
    config.pause_time_threshold = 3.0
    config.ups_ema_alpha = 0.3
    client.server_config = config
    return client


@pytest.fixture
def ups_calculator() -> UPSCalculator:
    """Create a UPSCalculator instance."""
    return UPSCalculator(pause_time_threshold=5.0)


@pytest.fixture
def metrics_engine(mock_rcon_client: MagicMock) -> RconMetricsEngine:
    """Create a RconMetricsEngine instance."""
    return RconMetricsEngine(
        rcon_client=mock_rcon_client,
        enable_ups_stat=True,
        enable_evolution_stat=True,
    )


# ============================================================================
# UPS CALCULATOR TESTS
# ============================================================================


class TestUPSCalculatorInit:
    """Test UPSCalculator initialization."""

    def test_init_with_default_threshold(self) -> None:
        """Initialize calculator with default pause threshold."""
        calc = UPSCalculator()

        assert calc.pause_time_threshold == 5.0
        assert calc.last_tick is None
        assert calc.last_sample_time is None
        assert calc.current_ups is None
        assert calc.is_paused is False
        assert calc.last_known_ups is None

    def test_init_with_custom_threshold(self) -> None:
        """Initialize calculator with custom pause threshold."""
        calc = UPSCalculator(pause_time_threshold=3.0)

        assert calc.pause_time_threshold == 3.0


@pytest.mark.asyncio
class TestUPSCalculatorSampling:
    """Test UPS sampling and calculation."""

    async def test_sample_ups_first_sample_returns_none(self) -> None:
        """First UPS sample returns None (need baseline)."""
        calc = UPSCalculator()
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(return_value="100")

        result = await calc.sample_ups(mock_client)

        assert result is None
        assert calc.last_tick == 100
        assert calc.last_sample_time is not None

    async def test_sample_ups_calculates_from_second_sample(self) -> None:
        """Second UPS sample calculates actual UPS."""
        calc = UPSCalculator()
        mock_client = MagicMock()

        # First sample
        mock_client.execute = AsyncMock(return_value="1000")
        await calc.sample_ups(mock_client)
        first_time = calc.last_sample_time

        # Second sample (2 real seconds later, 120 ticks advanced)
        with patch("time.time", return_value=first_time + 2.0):
            mock_client.execute = AsyncMock(return_value="1120")
            result = await calc.sample_ups(mock_client)

        # 120 ticks / 2 seconds = 60 UPS
        assert result == 60.0
        assert calc.current_ups == 60.0
        assert calc.last_known_ups == 60.0

    async def test_sample_ups_detects_pause_no_tick_advancement(self) -> None:
        """Pause detected when no ticks advanced over threshold time."""
        calc = UPSCalculator(pause_time_threshold=5.0)
        mock_client = MagicMock()
        first_time = time.time()

        # First sample
        with patch("time.time", return_value=first_time):
            mock_client.execute = AsyncMock(return_value="1000")
            await calc.sample_ups(mock_client)

        # Second sample: no tick advancement, 5+ seconds later
        with patch("time.time", return_value=first_time + 6.0):
            mock_client.execute = AsyncMock(return_value="1000")
            result = await calc.sample_ups(mock_client)

        assert result is None
        assert calc.is_paused is True

    async def test_sample_ups_detects_minimal_advancement_as_pause(self) -> None:
        """Minimal tick advancement (< 60 ticks over 5+ seconds) indicates pause."""
        calc = UPSCalculator(pause_time_threshold=5.0)
        mock_client = MagicMock()
        first_time = time.time()

        # First sample
        with patch("time.time", return_value=first_time):
            mock_client.execute = AsyncMock(return_value="1000")
            await calc.sample_ups(mock_client)

        # Second sample: only 30 ticks (< 60), 5+ seconds later
        with patch("time.time", return_value=first_time + 6.0):
            mock_client.execute = AsyncMock(return_value="1030")
            result = await calc.sample_ups(mock_client)

        assert result is None
        assert calc.is_paused is True

    async def test_sample_ups_detects_unpause_with_reasonable_ups(self) -> None:
        """Unpause detected when UPS > 10 after being paused."""
        calc = UPSCalculator(pause_time_threshold=5.0)
        mock_client = MagicMock()
        first_time = time.time()

        # First sample
        with patch("time.time", return_value=first_time):
            mock_client.execute = AsyncMock(return_value="1000")
            await calc.sample_ups(mock_client)

        # Pause: no advancement for 6 seconds
        with patch("time.time", return_value=first_time + 6.0):
            mock_client.execute = AsyncMock(return_value="1000")
            result = await calc.sample_ups(mock_client)
            assert calc.is_paused is True

        # Resume: 60 ticks in 1 second = 60 UPS
        with patch("time.time", return_value=first_time + 7.0):
            mock_client.execute = AsyncMock(return_value="1060")
            result = await calc.sample_ups(mock_client)

        assert result == 60.0
        assert calc.is_paused is False

    async def test_sample_ups_rejects_too_fast_samples(self) -> None:
        """Too-fast samples (< 0.1s) return cached UPS, don't update."""
        calc = UPSCalculator()
        mock_client = MagicMock()
        first_time = time.time()

        # First sample
        with patch("time.time", return_value=first_time):
            mock_client.execute = AsyncMock(return_value="1000")
            await calc.sample_ups(mock_client)

        # Normal second sample
        with patch("time.time", return_value=first_time + 2.0):
            mock_client.execute = AsyncMock(return_value="1120")
            await calc.sample_ups(mock_client)

        cached_ups = calc.current_ups

        # Too-fast third sample (0.05 seconds later)
        with patch("time.time", return_value=first_time + 2.05):
            mock_client.execute = AsyncMock(return_value="1123")
            result = await calc.sample_ups(mock_client)

        assert result == cached_ups  # Returns cached, doesn't update

    async def test_sample_ups_handles_rcon_error(self) -> None:
        """UPS sampling handles RCON errors gracefully."""
        calc = UPSCalculator()
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(side_effect=RuntimeError("RCON failed"))

        result = await calc.sample_ups(mock_client)

        assert result is None

    async def test_sample_ups_handles_invalid_tick_format(self) -> None:
        """UPS sampling handles non-numeric tick response."""
        calc = UPSCalculator()
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(return_value="not_a_number")

        with pytest.raises(ValueError):
            await calc.sample_ups(mock_client)


# ============================================================================
# METRICS ENGINE INITIALIZATION TESTS
# ============================================================================


class TestRconMetricsEngineInit:
    """Test RconMetricsEngine initialization."""

    def test_init_with_all_stats_enabled(self, mock_rcon_client: MagicMock) -> None:
        """Initialize engine with all stats enabled."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=True,
            enable_evolution_stat=True,
        )

        assert engine.rcon_client is mock_rcon_client
        assert engine.enable_ups_stat is True
        assert engine.enable_evolution_stat is True
        assert engine.ups_calculator is not None
        assert engine.ema_alpha == 0.2  # Default
        assert engine.ema_ups is None
        assert engine._ups_samples_for_sma == []

    def test_init_with_ups_disabled(self, mock_rcon_client: MagicMock) -> None:
        """Initialize engine with UPS stats disabled."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=False,
            enable_evolution_stat=True,
        )

        assert engine.enable_ups_stat is False
        assert engine.ups_calculator is None

    def test_init_with_evolution_disabled(self, mock_rcon_client: MagicMock) -> None:
        """Initialize engine with evolution stats disabled."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )

        assert engine.enable_evolution_stat is False

    def test_init_uses_server_config_thresholds(
        self, mock_rcon_client_with_config: MagicMock
    ) -> None:
        """Initialize engine reads pause threshold from server config."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client_with_config,
            enable_ups_stat=True,
        )

        assert engine.ups_calculator.pause_time_threshold == 3.0
        assert engine.ema_alpha == 0.3


# ============================================================================
# SAMPLE UPS TESTS
# ============================================================================


@pytest.mark.asyncio
class TestRconMetricsEngineSampleUPS:
    """Test RconMetricsEngine UPS sampling."""

    async def test_sample_ups_returns_none_when_disabled(self) -> None:
        """sample_ups returns None when UPS stat disabled."""
        mock_client = MagicMock()
        engine = RconMetricsEngine(
            rcon_client=mock_client,
            enable_ups_stat=False,
        )

        result = await engine.sample_ups()

        assert result is None
        mock_client.execute.assert_not_called()

    async def test_sample_ups_delegates_to_calculator(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """sample_ups delegates to internal UPS calculator."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=True,
        )
        mock_rcon_client.execute = AsyncMock(return_value="1000")

        result = await engine.sample_ups()

        # First sample returns None
        assert result is None
        mock_rcon_client.execute.assert_called_once()


# ============================================================================
# EVOLUTION FACTOR TESTS
# ============================================================================


@pytest.mark.asyncio
class TestRconMetricsEngineEvolution:
    """Test evolution factor collection."""

    async def test_get_evolution_returns_empty_when_disabled(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """get_evolution_by_surface returns empty dict when disabled."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_evolution_stat=False,
        )

        result = await engine.get_evolution_by_surface()

        assert result == {}
        mock_rcon_client.execute.assert_not_called()

    async def test_get_evolution_single_surface(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """Parse evolution factor from single surface."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_evolution_stat=True,
        )
        evolution_json = '{"nauvis": 0.42}'
        mock_rcon_client.execute = AsyncMock(return_value=evolution_json)

        result = await engine.get_evolution_by_surface()

        assert result == {"nauvis": 0.42}

    async def test_get_evolution_multi_surface(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """Parse evolution factors from multiple surfaces."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_evolution_stat=True,
        )
        evolution_json = '{"nauvis": 0.42, "gleba": 0.15, "vulcanus": 0.33}'
        mock_rcon_client.execute = AsyncMock(return_value=evolution_json)

        result = await engine.get_evolution_by_surface()

        assert result == {"nauvis": 0.42, "gleba": 0.15, "vulcanus": 0.33}

    async def test_get_evolution_handles_empty_response(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """Empty evolution response returns empty dict."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_evolution_stat=True,
        )
        mock_rcon_client.execute = AsyncMock(return_value="{}")

        result = await engine.get_evolution_by_surface()

        assert result == {}

    async def test_get_evolution_handles_json_decode_error(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """Malformed JSON returns empty dict and logs error."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_evolution_stat=True,
        )
        mock_rcon_client.execute = AsyncMock(return_value="not valid json {")

        result = await engine.get_evolution_by_surface()

        assert result == {}

    async def test_get_evolution_handles_rcon_error(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """RCON error during evolution collection returns empty dict."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_evolution_stat=True,
        )
        mock_rcon_client.execute = AsyncMock(side_effect=RuntimeError("RCON failed"))

        result = await engine.get_evolution_by_surface()

        assert result == {}


# ============================================================================
# PLAYER METRICS TESTS
# ============================================================================


@pytest.mark.asyncio
class TestRconMetricsEnginePlayerMetrics:
    """Test player metric collection."""

    async def test_get_players(
        self, metrics_engine: RconMetricsEngine, mock_rcon_client: MagicMock
    ) -> None:
        """Get player list from RCON."""
        result = await metrics_engine.get_players()

        assert result == ["Alice", "Bob", "Charlie"]
        mock_rcon_client.get_players.assert_called_once()

    async def test_get_player_count(
        self, metrics_engine: RconMetricsEngine, mock_rcon_client: MagicMock
    ) -> None:
        """Get player count from RCON."""
        result = await metrics_engine.get_player_count()

        assert result == 3
        mock_rcon_client.get_player_count.assert_called_once()

    async def test_get_play_time(
        self, metrics_engine: RconMetricsEngine, mock_rcon_client: MagicMock
    ) -> None:
        """Get play time from RCON."""
        result = await metrics_engine.get_play_time()

        assert result == "1h 23m 45s"
        mock_rcon_client.get_play_time.assert_called_once()


# ============================================================================
# GATHER ALL METRICS TESTS (HAPPY PATH)
# ============================================================================


@pytest.mark.asyncio
class TestRconMetricsEngineGatherAllMetricsHappyPath:
    """Test gather_all_metrics happy path."""

    async def test_gather_all_metrics_returns_complete_dict(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """gather_all_metrics returns all expected keys."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=True,
            enable_evolution_stat=True,
        )
        mock_rcon_client.execute = AsyncMock(return_value="3600")

        result = await engine.gather_all_metrics()

        # Check all keys present
        assert "ups" in result
        assert "ups_sma" in result
        assert "ups_ema" in result
        assert "is_paused" in result
        assert "last_known_ups" in result
        assert "tick" in result
        assert "game_time_seconds" in result
        assert "evolution_factor" in result
        assert "evolution_by_surface" in result
        assert "player_count" in result
        assert "players" in result
        assert "play_time" in result

    async def test_gather_all_metrics_collects_tick(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """gather_all_metrics collects game tick."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=False,
            enable_evolution_stat=False,
        )
        mock_rcon_client.execute = AsyncMock(return_value="7200")

        result = await engine.gather_all_metrics()

        assert result["tick"] == 7200
        assert result["game_time_seconds"] == 120.0  # 7200 / 60

    async def test_gather_all_metrics_ema_initialization(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """gather_all_metrics initializes EMA from first sample."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )
        first_time = time.time()
        call_count = 0

        async def mock_execute(cmd):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                with patch("time.time", return_value=first_time):
                    return "1000"
            else:
                with patch("time.time", return_value=first_time + 2.0):
                    return "1120"

        mock_rcon_client.execute = AsyncMock(side_effect=mock_execute)

        # First gather (EMA not initialized)
        result1 = await engine.gather_all_metrics()
        assert result1["ups_ema"] is None

        # Second gather (EMA initialized from UPS sample)
        result2 = await engine.gather_all_metrics()
        assert result2["ups_ema"] is not None

    async def test_gather_all_metrics_ema_updates(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """gather_all_metrics updates EMA correctly."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )
        engine.ema_alpha = 0.5  # Make math easier
        engine.ema_ups = 60.0  # Start with 60

        # Mock UPS sample to return 50
        mock_rcon_client.execute = AsyncMock(return_value="3600")
        with patch.object(engine.ups_calculator, "sample_ups", return_value=50.0):
            result = await engine.gather_all_metrics()

        # EMA = 0.5 * 50 + 0.5 * 60 = 55
        assert result["ups_ema"] == 55.0

    async def test_gather_all_metrics_sma_window(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """gather_all_metrics maintains SMA window of 5 samples."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )

        mock_rcon_client.execute = AsyncMock(return_value="3600")

        # Add 7 samples
        for i in range(7):
            ups_value = 50.0 + i
            with patch.object(engine.ups_calculator, "sample_ups", return_value=ups_value):
                result = await engine.gather_all_metrics()

        # Only last 5 samples should be in SMA
        # [52, 53, 54, 55, 56] -> SMA = 54
        assert len(engine._ups_samples_for_sma) == 5
        assert result["ups_sma"] == 54.0

    async def test_gather_all_metrics_evolution_sets_backward_compat(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """gather_all_metrics sets evolution_factor from first surface."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=False,
            enable_evolution_stat=True,
        )
        evolution_json = '{"nauvis": 0.42, "gleba": 0.15}'
        mock_rcon_client.execute = AsyncMock(return_value=evolution_json)

        result = await engine.gather_all_metrics()

        # evolution_factor should be first surface value
        assert result["evolution_factor"] == 0.42
        assert result["evolution_by_surface"] == {"nauvis": 0.42, "gleba": 0.15}


# ============================================================================
# GATHER ALL METRICS TESTS (ERROR PATHS)
# ============================================================================


@pytest.mark.asyncio
class TestRconMetricsEngineGatherAllMetricsErrorPaths:
    """Test gather_all_metrics error handling."""

    async def test_gather_all_metrics_handles_tick_error(self) -> None:
        """gather_all_metrics handles tick collection error gracefully."""
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(side_effect=RuntimeError("RCON failed"))
        mock_client.get_players = AsyncMock(return_value=[])
        mock_client.get_player_count = AsyncMock(return_value=0)
        mock_client.get_play_time = AsyncMock(return_value="0h 0m 0s")
        mock_client.server_config = None

        engine = RconMetricsEngine(
            rcon_client=mock_client,
            enable_ups_stat=False,
            enable_evolution_stat=False,
        )

        result = await engine.gather_all_metrics()

        # Should return metrics with tick as None
        assert result["tick"] is None
        assert result["game_time_seconds"] is None

    async def test_gather_all_metrics_handles_player_collection_error(self) -> None:
        """gather_all_metrics handles player collection error gracefully."""
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(return_value="3600")
        mock_client.get_players = AsyncMock(side_effect=RuntimeError("Get players failed"))
        mock_client.get_player_count = AsyncMock(
            side_effect=RuntimeError("Get player count failed")
        )
        mock_client.get_play_time = AsyncMock(side_effect=RuntimeError("Get play time failed"))
        mock_client.server_config = None

        engine = RconMetricsEngine(
            rcon_client=mock_client,
            enable_ups_stat=False,
            enable_evolution_stat=False,
        )

        # Should not raise, but log errors
        result = await engine.gather_all_metrics()

        # Player fields should have default values
        assert "players" in result
        assert "player_count" in result
        assert "play_time" in result

    async def test_gather_all_metrics_returns_defaults_with_all_stats_disabled(
        self, mock_rcon_client: MagicMock
    ) -> None:
        """gather_all_metrics returns all defaults when stats disabled."""
        engine = RconMetricsEngine(
            rcon_client=mock_rcon_client,
            enable_ups_stat=False,
            enable_evolution_stat=False,
        )
        mock_rcon_client.execute = AsyncMock(return_value="3600")

        result = await engine.gather_all_metrics()

        assert result["ups"] is None
        assert result["ups_ema"] is None
        assert result["ups_sma"] is None
        assert result["evolution_factor"] is None
        assert result["evolution_by_surface"] == {}


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
class TestRconMetricsEngineIntegration:
    """Integration tests for complete workflows."""

    async def test_full_metrics_collection_cycle(self) -> None:
        """Complete metrics collection: tick, UPS, evolution, players."""
        mock_client = MagicMock()
        mock_client.server_tag = "prod"
        mock_client.server_name = "Production"
        mock_client.server_config = None
        mock_client.execute = AsyncMock(return_value="3600")
        mock_client.get_players = AsyncMock(return_value=["Alice", "Bob"])
        mock_client.get_player_count = AsyncMock(return_value=2)
        mock_client.get_play_time = AsyncMock(return_value="1h 0m 0s")

        engine = RconMetricsEngine(
            rcon_client=mock_client,
            enable_ups_stat=True,
            enable_evolution_stat=True,
        )

        result = await engine.gather_all_metrics()

        # Verify all data collected
        assert result["tick"] == 3600
        assert result["game_time_seconds"] == 60.0
        assert result["player_count"] == 2
        assert result["players"] == ["Alice", "Bob"]
        assert result["play_time"] == "1h 0m 0s"

    async def test_metrics_state_persistence_across_calls(self) -> None:
        """Metrics engine maintains state across multiple gather calls."""
        mock_client = MagicMock()
        mock_client.server_config = None
        mock_client.execute = AsyncMock(return_value="3600")
        mock_client.get_players = AsyncMock(return_value=[])
        mock_client.get_player_count = AsyncMock(return_value=0)
        mock_client.get_play_time = AsyncMock(return_value="0h 0m 0s")

        engine = RconMetricsEngine(
            rcon_client=mock_client,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )

        # First call
        with patch.object(engine.ups_calculator, "sample_ups", return_value=60.0):
            result1 = await engine.gather_all_metrics()
            ema1 = result1["ups_ema"]

        # Second call
        with patch.object(engine.ups_calculator, "sample_ups", return_value=59.0):
            result2 = await engine.gather_all_metrics()
            ema2 = result2["ups_ema"]

        # EMA should change between calls
        assert ema1 != ema2
        assert ema2 == pytest.approx(0.2 * 59.0 + 0.8 * ema1)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
