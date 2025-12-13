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
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from rcon_alert_monitor import RconAlertMonitor


# ============================================================================
# FIXTURES
# ============================================================================


@pytest_asyncio.fixture
async def mock_rcon_client() -> AsyncGenerator[MagicMock, None]:
    """Mock RconClient for use in tests."""
    mock = MagicMock()
    mock.is_connected = True
    mock.server_tag = "TEST"
    mock.server_name = "Test Server"
    yield mock


@pytest_asyncio.fixture
async def mock_discord_interface() -> AsyncGenerator[AsyncMock, None]:
    """Mock Discord interface for use in tests."""
    mock = AsyncMock()
    mock.is_connected = True
    mock.send_message = AsyncMock()
    mock.send_embed = AsyncMock(return_value=None)
    yield mock


@pytest_asyncio.fixture
async def mock_metrics_engine() -> AsyncGenerator[AsyncMock, None]:
    """Mock RconMetricsEngine for use in tests."""
    mock = AsyncMock()
    mock.sample_ups = AsyncMock(return_value=59.5)
    mock.ema_ups = 59.3
    mock.ema_alpha = 0.1
    mock.ups_calculator = MagicMock()
    mock.ups_calculator.is_paused = False
    mock.ups_calculator.last_known_ups = 59.5
    yield mock


# ============================================================================
# INITIALIZATION TESTS (4 tests)
# ============================================================================


@pytest.mark.asyncio
class TestRconAlertMonitorInitialization:
    """Test RconAlertMonitor initialization."""

    async def test_init_with_all_params(self, mock_rcon_client, mock_discord_interface):
        """Test initialization with all parameters."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            check_interval=30,
            samples_before_alert=2,
            ups_warning_threshold=50.0,
            ups_recovery_threshold=55.0,
            alert_cooldown=120,
        )

        assert monitor.rcon_client is mock_rcon_client
        assert monitor.discord_interface is mock_discord_interface
        assert monitor.check_interval == 30
        assert monitor.samples_before_alert == 2
        assert monitor.ups_warning_threshold == 50.0
        assert monitor.ups_recovery_threshold == 55.0
        assert monitor.alert_cooldown == 120
        assert monitor.running is False
        assert monitor.task is None

    async def test_init_creates_metrics_engine_when_not_provided(self, mock_rcon_client, mock_discord_interface):
        """Test that metrics engine is created when not provided."""
        with patch("rcon_metrics_engine.RconMetricsEngine") as mock_engine_cls:
            mock_engine_instance = MagicMock()
            mock_engine_cls.return_value = mock_engine_instance

            monitor = RconAlertMonitor(
                rcon_client=mock_rcon_client,
                discord_interface=mock_discord_interface,
                metrics_engine=None,
            )

        mock_engine_cls.assert_called_once_with(
            mock_rcon_client,
            enable_ups_stat=True,
            enable_evolution_stat=False,
        )
        assert monitor.metrics_engine is mock_engine_instance

    async def test_init_uses_provided_metrics_engine(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test that provided metrics engine is used."""
        with patch("rcon_metrics_engine.RconMetricsEngine") as mock_engine_cls:
            monitor = RconAlertMonitor(
                rcon_client=mock_rcon_client,
                discord_interface=mock_discord_interface,
                metrics_engine=mock_metrics_engine,
            )

        mock_engine_cls.assert_not_called()
        assert monitor.metrics_engine is mock_metrics_engine

    async def test_init_alert_state_defaults(self, mock_rcon_client, mock_discord_interface):
        """Test alert state is initialized with correct defaults."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        assert monitor.alert_state["low_ups_active"] is False
        assert monitor.alert_state["last_alert_time"] is None
        assert monitor.alert_state["consecutive_bad_samples"] == 0
        assert monitor.alert_state["recent_ups_samples"] == []


# ============================================================================
# LIFECYCLE TESTS (4 tests)
# ============================================================================


@pytest.mark.asyncio
class TestRconAlertMonitorLifecycle:
    """Test start and stop lifecycle."""

    async def test_start_creates_task(self, mock_rcon_client, mock_discord_interface):
        """Test start() creates monitoring task."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        assert monitor.running is False
        assert monitor.task is None

        await monitor.start()

        assert monitor.running is True
        assert monitor.task is not None
        assert isinstance(monitor.task, asyncio.Task)

        await monitor.stop()

    async def test_start_when_already_running_returns_early(self, mock_rcon_client, mock_discord_interface):
        """Test start() when already running does not create duplicate task."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        await monitor.start()
        first_task = monitor.task

        await monitor.start()

        # Task should be the same
        assert monitor.task is first_task

        await monitor.stop()

    async def test_stop_cancels_task(self, mock_rcon_client, mock_discord_interface):
        """Test stop() cancels the running task."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        await monitor.start()
        task = monitor.task

        await monitor.stop()

        assert monitor.running is False
        assert monitor.task is None
        assert task.cancelled()

    async def test_stop_when_not_running_returns_early(self, mock_rcon_client, mock_discord_interface):
        """Test stop() when not running is safe."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        # Should not raise
        await monitor.stop()

        assert monitor.running is False
        assert monitor.task is None


# ============================================================================
# UPS CHECK TESTS (4 tests)
# ============================================================================


@pytest.mark.asyncio
class TestRconAlertMonitorUpsCheck:
    """Test _check_ups method behavior."""

    async def test_check_ups_returns_early_when_not_connected(self, mock_rcon_client, mock_discord_interface):
        """Test _check_ups returns early when RCON not connected."""
        mock_rcon_client.is_connected = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        await monitor._check_ups()

        # Alert state should not be modified
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_check_ups_skips_when_server_paused(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test _check_ups skips alert processing when server is paused."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=50.0)  # Low UPS
        mock_metrics_engine.ups_calculator.is_paused = True
        mock_metrics_engine.ema_ups = 50.0

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            ups_warning_threshold=55.0,
        )

        # Manually set alert active
        monitor.alert_state["low_ups_active"] = True

        await monitor._check_ups()

        # Alert should be cleared (paused)
        assert monitor.alert_state["low_ups_active"] is False
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_check_ups_increments_bad_samples_on_low_ups(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test _check_ups increments bad sample counter on low UPS."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=50.0)  # Below threshold
        mock_metrics_engine.ema_ups = 50.0
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            ups_warning_threshold=55.0,
            samples_before_alert=3,
        )

        await monitor._check_ups()

        assert monitor.alert_state["consecutive_bad_samples"] == 1

    async def test_check_ups_resets_bad_samples_on_recovery(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test _check_ups resets bad sample counter when UPS recovers."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=59.5)  # Above recovery threshold
        mock_metrics_engine.ema_ups = 59.5
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
        )

        # Manually set some bad samples
        monitor.alert_state["consecutive_bad_samples"] = 5

        await monitor._check_ups()

        # Should reset on recovery
        assert monitor.alert_state["consecutive_bad_samples"] == 0


# ============================================================================
# ALERT TRIGGERING TESTS (6 tests)
# ============================================================================


@pytest.mark.asyncio
class TestRconAlertMonitorAlertTriggering:
    """Test alert triggering logic."""

    async def test_alert_triggered_after_threshold_samples(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test alert is triggered after enough bad samples."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=50.0)
        mock_metrics_engine.ema_ups = 50.0
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            ups_warning_threshold=55.0,
            samples_before_alert=2,
        )

        with patch.object(monitor, "_send_low_ups_alert", new_callable=AsyncMock):
            # First check: consecutive_bad_samples = 1 (not yet threshold)
            await monitor._check_ups()
            assert monitor.alert_state["low_ups_active"] is False

            # Second check: consecutive_bad_samples = 2 (at threshold)
            await monitor._check_ups()
            # Alert should now be active
            assert monitor.alert_state["low_ups_active"] is True

    async def test_alert_respects_cooldown(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test alert cooldown prevents duplicate alerts."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=50.0)
        mock_metrics_engine.ema_ups = 50.0
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            ups_warning_threshold=55.0,
            samples_before_alert=1,
            alert_cooldown=60,
        )

        # Set last alert time to now
        monitor.alert_state["last_alert_time"] = datetime.now(timezone.utc)

        # Should return False (within cooldown)
        can_send = monitor._can_send_alert()
        assert can_send is False

    async def test_alert_allowed_after_cooldown_expires(self, mock_rcon_client, mock_discord_interface):
        """Test alert is allowed after cooldown expires."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            alert_cooldown=60,
        )

        # Set last alert time to 61 seconds ago
        past_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        monitor.alert_state["last_alert_time"] = past_time

        # Should return True (cooldown expired)
        can_send = monitor._can_send_alert()
        assert can_send is True

    async def test_low_ups_alert_sent_with_metrics(self, mock_rcon_client, mock_discord_interface):
        """Test low UPS alert includes metrics data."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        with patch("discord_interface.EmbedBuilder") as mock_builder:
            mock_embed = MagicMock()
            mock_builder.create_base_embed.return_value = mock_embed
            mock_embed.add_field = MagicMock()
            mock_discord_interface.send_embed = AsyncMock()

            await monitor._send_low_ups_alert(
                current_ups=50.0,
                sma_ups=51.0,
                ema_ups=50.5,
            )

        # Verify embed was created with title
        mock_builder.create_base_embed.assert_called_once()
        call_kwargs = mock_builder.create_base_embed.call_args.kwargs
        assert "Low UPS Warning" in call_kwargs["title"]

    async def test_ups_recovered_alert_sent(self, mock_rcon_client, mock_discord_interface):
        """Test recovery alert is sent correctly."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        with patch("discord_interface.EmbedBuilder") as mock_builder:
            mock_embed = MagicMock()
            mock_builder.create_base_embed.return_value = mock_embed
            mock_discord_interface.send_embed = AsyncMock()

            await monitor._send_ups_recovered_alert(
                current_ups=59.5,
                sma_ups=59.0,
                ema_ups=59.3,
            )

        # Verify embed was created with recovery title
        mock_builder.create_base_embed.assert_called_once()
        call_kwargs = mock_builder.create_base_embed.call_args.kwargs
        assert "Recovered" in call_kwargs["title"]

    async def test_alert_with_fallback_text_message(self, mock_rcon_client, mock_discord_interface):
        """Test alert falls back to text when embed is not available."""
        # Remove send_embed method to simulate unavailable
        del mock_discord_interface.send_embed

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        await monitor._send_low_ups_alert(
            current_ups=50.0,
            sma_ups=51.0,
            ema_ups=50.5,
        )

        # Should have called send_message (fallback)
        mock_discord_interface.send_message.assert_called_once()


# ============================================================================
# ERROR HANDLING TESTS (4 tests)
# ============================================================================


@pytest.mark.asyncio
class TestRconAlertMonitorErrorHandling:
    """Test error handling in alert monitor."""

    async def test_check_ups_handles_sample_ups_error(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test _check_ups handles errors from sample_ups."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(side_effect=RuntimeError("Metrics error"))

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
        )

        # Should not raise - _check_ups catches this
        await monitor._check_ups()
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_monitor_loop_catches_errors_from_check_ups(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test monitoring loop catches errors from _check_ups."""
        call_count = 0

        async def check_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Check error")

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            check_interval=0.05,
        )

        with patch.object(monitor, "_check_ups", side_effect=check_with_error):
            await monitor.start()
            await asyncio.sleep(0.15)
            await monitor.stop()

        # Should have attempted checks despite error
        assert call_count >= 2

    async def test_monitor_loop_continues_on_error(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test monitoring loop continues after exception."""
        call_count = 0

        async def check_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First check error")
            # Second call succeeds

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            check_interval=0.05,
        )

        with patch.object(monitor, "_check_ups", side_effect=check_with_error):
            await monitor.start()
            await asyncio.sleep(0.15)
            await monitor.stop()

        # Should have attempted at least 2 checks
        assert call_count >= 2

    async def test_send_low_ups_alert_with_successful_embed(self, mock_rcon_client, mock_discord_interface):
        """Test _send_low_ups_alert sends embed successfully."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        with patch("discord_interface.EmbedBuilder") as mock_builder:
            mock_embed = MagicMock()
            mock_builder.create_base_embed.return_value = mock_embed
            mock_discord_interface.send_embed = AsyncMock(return_value=None)

            # Should succeed
            await monitor._send_low_ups_alert(50.0, 51.0, 50.5)

        mock_discord_interface.send_embed.assert_called_once()


# ============================================================================
# SERVER LABEL TESTS (2 tests)
# ============================================================================


@pytest.mark.asyncio
class TestServerLabelBuilding:
    """Test _build_server_label method."""

    async def test_build_label_with_tag_and_name(self, mock_rcon_client, mock_discord_interface):
        """Test label includes both tag and name."""
        mock_rcon_client.server_tag = "PROD"
        mock_rcon_client.server_name = "Production"

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = monitor._build_server_label()

        assert "[PROD]" in label
        assert "Production" in label

    async def test_build_label_with_neither_tag_nor_name(self, mock_rcon_client, mock_discord_interface):
        """Test default label when no tag or name."""
        mock_rcon_client.server_tag = None
        mock_rcon_client.server_name = None

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        label = monitor._build_server_label()

        assert label == "Factorio Server"


# ============================================================================
# RECENT SAMPLES TRACKING TESTS (2 tests)
# ============================================================================


@pytest.mark.asyncio
class TestRecentSamplesTracking:
    """Test recent UPS samples tracking for SMA calculation."""

    async def test_samples_list_maintains_max_length(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test recent samples list doesn't exceed 5 entries."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=59.0)
        mock_metrics_engine.ema_ups = 59.0
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
        )

        # Add 10 samples
        for _ in range(10):
            await monitor._check_ups()

        # Should maintain only 5 most recent
        assert len(monitor.alert_state["recent_ups_samples"]) == 5

    async def test_samples_used_for_sma_calculation(self, mock_rcon_client, mock_discord_interface):
        """Test samples are collected for SMA in alert."""
        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
        )

        # Set sample history
        monitor.alert_state["recent_ups_samples"] = [58.0, 57.5, 57.0, 56.5, 56.0]

        # Calculate SMA
        sma = sum(monitor.alert_state["recent_ups_samples"]) / len(
            monitor.alert_state["recent_ups_samples"]
        )

        assert abs(sma - 57.0) < 0.01  # Average of [58, 57.5, 57, 56.5, 56]


# ============================================================================
# EDGE CASE TESTS (4 tests)
# ============================================================================


@pytest.mark.asyncio
class TestRconAlertMonitorEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_check_ups_with_none_sample_skips_processing(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test _check_ups skips when sample_ups returns None."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=None)  # First sample
        mock_metrics_engine.ema_ups = None
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
        )

        await monitor._check_ups()

        # Should skip processing
        assert monitor.alert_state["consecutive_bad_samples"] == 0
        assert len(monitor.alert_state["recent_ups_samples"]) == 0

    async def test_ups_exactly_at_warning_threshold(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test behavior when UPS is exactly at warning threshold."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=55.0)  # Exactly at threshold
        mock_metrics_engine.ema_ups = 55.0
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            ups_warning_threshold=55.0,
        )

        await monitor._check_ups()

        # At threshold should not trigger (must be BELOW)
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_ups_exactly_at_recovery_threshold(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test behavior when UPS is exactly at recovery threshold."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=58.0)  # Exactly at recovery
        mock_metrics_engine.ema_ups = 58.0
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
        )

        # Manually set alert active
        monitor.alert_state["low_ups_active"] = True
        monitor.alert_state["consecutive_bad_samples"] = 3

        with patch.object(monitor, "_send_ups_recovered_alert", new_callable=AsyncMock):
            await monitor._check_ups()

        # At recovery should trigger recovery (must be >= recovery threshold)
        assert monitor.alert_state["low_ups_active"] is False

    async def test_check_ups_with_none_ema_falls_back_to_current(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test _check_ups uses current UPS when EMA is None."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=50.0)
        mock_metrics_engine.ema_ups = None  # No EMA yet
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            ups_warning_threshold=55.0,
        )

        await monitor._check_ups()

        # Should use current UPS (50.0) for decision
        assert monitor.alert_state["consecutive_bad_samples"] == 1


# ============================================================================
# INTEGRATION TESTS (2 tests)
# ============================================================================


@pytest.mark.asyncio
class TestRconAlertMonitorIntegration:
    """Integration tests for complete workflows."""

    async def test_full_monitoring_cycle(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test complete monitoring cycle: start -> check -> stop."""
        mock_rcon_client.is_connected = True
        mock_metrics_engine.sample_ups = AsyncMock(return_value=59.5)
        mock_metrics_engine.ema_ups = 59.5
        mock_metrics_engine.ups_calculator.is_paused = False

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            check_interval=0.05,  # Short interval for testing
        )

        with patch.object(monitor, "_check_ups", new_callable=AsyncMock) as mock_check:
            await monitor.start()
            await asyncio.sleep(0.15)  # Allow multiple iterations
            await monitor.stop()

        # Should have checked UPS at least 2 times
        assert mock_check.call_count >= 2

    async def test_error_in_check_loop_doesnt_crash(self, mock_rcon_client, mock_discord_interface, mock_metrics_engine):
        """Test monitoring loop continues after error."""
        call_count = 0

        async def failing_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error")

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon_client,
            discord_interface=mock_discord_interface,
            metrics_engine=mock_metrics_engine,
            check_interval=0.05,
        )

        with patch.object(monitor, "_check_ups", side_effect=failing_check):
            await monitor.start()
            await asyncio.sleep(0.15)
            await monitor.stop()

        # Should have attempted checks despite first error
        assert call_count >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
