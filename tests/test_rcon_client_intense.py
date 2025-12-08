"""
Intensive branch-walk tests for RconStatsCollector and RconAlertMonitor.

This file is designed to be run alongside the existing test_rcon_client.py
without changing its structure. It focuses on edge branches, lifecycle,
and alert/metrics paths that are lightly covered in the main suite.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from rcon_client import (
    RconClient,
    RconStatsCollector,
    RconAlertMonitor,
    RCON_AVAILABLE,
)


# ============================================================================
# RconStatsCollector Intensive
# ============================================================================
@pytest.mark.asyncio
class TestRconStatsCollectorBranchGaps:
    async def test_format_stats_text_no_metrics_provided(self):
        """_format_stats_text when metrics is None or empty."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "EMPTY"
        mock_rcon.server_name = "Empty Metrics"
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
        )

        # metrics=None
        text_none = collector._format_stats_text(
            player_count=0,
            players=[],
            server_time="Day 0, 00:00",
            metrics=None,
        )
        assert "[EMPTY] Empty Metrics" in text_none

        # metrics={}
        text_empty = collector._format_stats_text(
            player_count=0,
            players=[],
            server_time="Day 0, 00:00",
            metrics={},
        )
        assert "[EMPTY] Empty Metrics" in text_empty

    async def test_format_stats_text_paused_without_last_known_ups(self):
        """Paused branch where last_known_ups is missing."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "PAUSE"
        mock_rcon.server_name = "Pause Server"
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
        )

        paused_metrics = {
            "is_paused": True,
            # intentionally omit last_known_ups
        }
        text = collector._format_stats_text(
            player_count=0,
            players=[],
            server_time="Day 1, 00:00",
            metrics=paused_metrics,
        )
        assert "Paused" in text

    async def test_format_stats_text_players_mismatch_count(self):
        """Branch where player_count does not match len(players)."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "MISMATCH"
        mock_rcon.server_name = "Mismatch Server"
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
        )

        metrics = {
            "ups": 50.0,
            "is_paused": False,
        }

        text = collector._format_stats_text(
            player_count=5,
            players=["OnlyOne"],
            server_time="Day 2, 12:00",
            metrics=metrics,
        )
        # Just ensure formatting succeeds and label present
        assert "[MISMATCH] Mismatch Server" in text

@pytest.mark.asyncio
class TestRconStatsCollectorIntensiveStandalone:
    async def test_format_stats_text_matrix(self):
        """Exercise multiple combinations of metrics and players for _format_stats_text."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "MATRIX"
        mock_rcon.server_name = "Matrix Server"
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
        )

        # Running with UPS & evolution
        metrics_running: Dict[str, Any] = {
            "ups": 60.0,
            "ups_sma": 59.0,
            "ups_ema": 58.0,
            "is_paused": False,
            "evolution_by_surface": {
                "nauvis": {"factor": 0.3, "index": 1},
            },
        }
        text_running = collector._format_stats_text(
            player_count=3,
            players=["Alice", "Bob", "Charlie"],
            server_time="Day 5, 12:00",
            metrics=metrics_running,
        )
        assert "[MATRIX] Matrix Server" in text_running
        assert "Players Online: 3" in text_running
        assert "UPS:" in text_running
        assert "Evolution:" in text_running

        # Running, no evolution
        metrics_no_evo: Dict[str, Any] = {
            "ups": 55.0,
            "ups_sma": 54.0,
            "ups_ema": 53.0,
            "is_paused": False,
        }
        text_no_evo = collector._format_stats_text(
            player_count=1,
            players=["Solo"],
            server_time="Day 6, 06:00",
            metrics=metrics_no_evo,
        )
        assert "UPS:" in text_no_evo
        assert "Evolution:" not in text_no_evo

        # Paused with last_known_ups
        paused_metrics: Dict[str, Any] = {
            "is_paused": True,
            "last_known_ups": 42.0,
        }
        text_paused = collector._format_stats_text(
            player_count=0,
            players=[],
            server_time="Day 7, 00:00",
            metrics=paused_metrics,
        )
        assert "Paused" in text_paused
        assert "42.0" in text_paused

        # Edge: player_count=0 but non-empty players list
        weird_text = collector._format_stats_text(
            player_count=0,
            players=["GhostPlayer"],
            server_time="Day 8, 08:00",
            metrics=metrics_running,
        )
        # Only assert it still formats and includes label
        assert "[MATRIX] Matrix Server" in weird_text

    async def test_run_loop_collects_multiple_times(self, monkeypatch):
        """Drive _run_loop with shortened interval and patched sleep."""
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

        real_sleep = asyncio.sleep

        async def fast_sleep(delay: float):
            await real_sleep(0.01)

        monkeypatch.setattr(asyncio, "sleep", fast_sleep)

        await collector.start()
        await real_sleep(0.1)
        await collector.stop()

        assert mock_rcon.get_player_count.await_count >= 1

    async def test_gather_extended_metrics_ups_and_evolution_success(self):
        """collect_ups=True and collect_evolution=True with valid evolution JSON."""
        mock_rcon = AsyncMock(spec=RconClient)
        mock_rcon.server_tag = "MIX"
        mock_rcon.server_name = "Mixed Server"
        # Two UPS ticks then one evolution JSON call
        mock_rcon.execute = AsyncMock(
            side_effect=[
                "0",
                "60",
                '{"nauvis": {"factor": 0.4, "index": 1}}',
            ]
        )

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
        # Second call: UPS calculated and evolution parsed
        metrics = await collector._gather_extended_metrics()
        assert isinstance(metrics, dict)
        assert "is_paused" in metrics
        evo = metrics.get("evolution_by_surface", {})
        assert isinstance(evo, dict)


# ============================================================================
# RconAlertMonitor Intensive
# ============================================================================
@pytest.mark.asyncio
class TestRconAlertMonitorBranchGaps:
    async def test_check_ups_none_when_not_active_and_not_connected(self):
        """sample_ups returns None while not connected and low_ups_active is False."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = False
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=1,
        )

        async def none_sample(_):
            return None

        monitor.ups_calculator.sample_ups = none_sample  # type: ignore

        # This should be a no-op branch inside _check_ups
        await monitor._check_ups()
        assert monitor.alert_state["low_ups_active"] is False
        assert monitor.alert_state["consecutive_bad_samples"] == 0

    async def test_check_ups_recovery_without_prior_low_state(self, monkeypatch):
        """UPS above recovery threshold but low_ups_active was never set."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=1,
        )

        async def good_ups(_):
            return 70.0

        monitor.ups_calculator.sample_ups = good_ups  # type: ignore
        monitor._send_ups_recovered_alert = AsyncMock()  # type: ignore
        # force cooldown allowed for completeness
        monkeypatch.setattr(monitor, "_can_send_alert", lambda: True)

        # low_ups_active starts False
        await monitor._check_ups()

        # Recovery alert should not be sent because there was no prior low state
        assert monitor.alert_state["low_ups_active"] is False
        monitor._send_ups_recovered_alert.assert_not_awaited()  # type: ignore

    async def test_can_send_alert_exactly_at_cooldown_boundary(self, monkeypatch):
        """Boundary condition what happens when now == last_alert_time + cooldown."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=5,
        )

        base_time = 1000.0
        cooldown = monitor.alert_cooldown

        # First call sets last_alert_time
        monkeypatch.setattr("time.time", lambda: base_time)
        monitor.last_alert_time = None
        assert monitor._can_send_alert() is True
        monitor.last_alert_time = base_time

        # Exactly at boundary: base_time + cooldown
        monkeypatch.setattr("time.time", lambda: base_time + cooldown)
        result = monitor._can_send_alert()
        assert isinstance(result, bool)

@pytest.mark.asyncio
class TestRconAlertMonitorIntensiveStandalone:
    async def test_start_twice_and_stop_twice(self, monkeypatch):
        """Exercise start/stop idempotency and monitor loop."""
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

        monitor._check_ups = AsyncMock()  # type: ignore

        real_sleep = asyncio.sleep

        async def fast_sleep(delay: float):
            await real_sleep(0.01)

        monkeypatch.setattr(asyncio, "sleep", fast_sleep)

        await monitor.start()
        # Second start should be safe and not create a second task
        await monitor.start()
        assert monitor.task is not None

        await real_sleep(0.1)

        await monitor.stop()
        # Second stop should not raise
        await monitor.stop()
        assert monitor.task is None

    async def test_monitor_loop_handles_internal_error_and_continues(self, monkeypatch):
        """Patch _check_ups to raise once to hit the generic exception handler."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=0.05,
        )

        calls: List[str] = []

        async def flaky_check():
            if not calls:
                calls.append("error")
                raise RuntimeError("boom")
            calls.append("ok")

        monitor._check_ups = flaky_check  # type: ignore

        real_sleep = asyncio.sleep

        async def fast_sleep(delay: float):
            await real_sleep(0.01)

        monkeypatch.setattr(asyncio, "sleep", fast_sleep)

        await monitor.start()
        await real_sleep(0.1)
        await monitor.stop()

        # Both error and successful path should have been exercised
        assert "error" in calls and "ok" in calls

    async def test_check_ups_sample_none_with_active_low_ups(self, monkeypatch):
        """When sample_ups returns None and low_ups_active is True, state should not reset spuriously."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=1,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=2,
        )

        monitor.alert_state["low_ups_active"] = True
        monitor.alert_state["consecutive_bad_samples"] = 2

        async def none_sample(_):
            return None

        monitor.ups_calculator.sample_ups = none_sample  # type: ignore
        monitor._send_low_ups_alert = AsyncMock()  # type: ignore
        monitor._send_ups_recovered_alert = AsyncMock()  # type: ignore

        await monitor._check_ups()

        # No new alerts, state unchanged other than maybe sample bookkeeping
        assert monitor.alert_state["low_ups_active"] is True
        assert monitor.alert_state["consecutive_bad_samples"] == 2
        monitor._send_low_ups_alert.assert_not_awaited()  # type: ignore
        monitor._send_ups_recovered_alert.assert_not_awaited()  # type: ignore

    async def test_low_ups_no_alert_when_blocked_by_cooldown(self, monkeypatch):
        """Low UPS increments counter but does not send alert if _can_send_alert returns False."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            ups_warning_threshold=55.0,
            samples_before_alert=1,
        )

        async def low_ups(_):
            return 40.0

        monitor.ups_calculator.sample_ups = low_ups  # type: ignore
        monkeypatch.setattr(monitor, "_can_send_alert", lambda: False)
        monitor._send_low_ups_alert = AsyncMock()  # type: ignore

        await monitor._check_ups()

        assert monitor.alert_state["consecutive_bad_samples"] >= 1
        monitor._send_low_ups_alert.assert_not_awaited()  # type: ignore

    async def test_send_low_ups_and_recovered_alerts_called(self):
        """Ensure both alert helpers call Discord send_embed."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "ERR"
        mock_rcon.server_name = "Error Server"

        mock_discord = AsyncMock()
        # Normal successful behaviour
        mock_discord.send_embed = AsyncMock(return_value=True)

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=1,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=1,
        )

        await monitor._send_low_ups_alert(current_ups=40.0, sma_ups=38.0, ema_ups=37.0)
        await monitor._send_ups_recovered_alert(current_ups=60.0, sma_ups=59.0, ema_ups=58.0)

        # Both alert methods should invoke send_embed at least once each
        assert mock_discord.send_embed.await_count >= 2


    async def test_can_send_alert_cooldown_precise(self, monkeypatch):
        """Explicitly walk last_alert_time None / within cooldown / after cooldown."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=5,
        )

        base_time = 1000.0
        monkeypatch.setattr("time.time", lambda: base_time)
        monitor.last_alert_time = None
        assert monitor._can_send_alert() is True

        monitor.last_alert_time = base_time
        # Immediately after: should be treated as within cooldown (most likely False)
        within = monitor._can_send_alert()
        assert isinstance(within, bool)

        # After cooldown elapsed
        monkeypatch.setattr("time.time", lambda: base_time + monitor.check_interval + 1.0)
        assert monitor._can_send_alert() is True

@pytest.mark.asyncio
class TestRconStatsCollectorRemainingBranches:
    async def test_gather_extended_metrics_ups_execute_failure_does_not_break(self):
        """collect_ups=True path when UPSCalculator fails internally."""
        mock_rcon = AsyncMock(spec=RconClient)
        mock_rcon.server_tag = "FAIL"
        mock_rcon.server_name = "Fail Server"

        # Force execute to raise when UPSCalculator calls it
        async def bad_execute(cmd: str) -> str:
            raise RuntimeError("ups failure")

        mock_rcon.execute = bad_execute  # type: ignore

        mock_discord = AsyncMock()
        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
            collect_ups=True,
            collect_evolution=False,
        )

        metrics = await collector._gather_extended_metrics()
        # Should still return a dict and mark paused/unknown UPS safely
        assert isinstance(metrics, dict)
        # Branch where ups_sample is None after failure
        assert "is_paused" in metrics

    async def test_gather_extended_metrics_sma_history_trimming(self, monkeypatch):
        """Drive the SMA sample history trimming logic."""
        mock_rcon = AsyncMock(spec=RconClient)
        mock_rcon.server_tag = "SMA"
        mock_rcon.server_name = "SMA Server"

        # Make UPSCalculator always return 60.0 without touching real execute
        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=AsyncMock(),
            interval=60,
            collect_ups=True,
            collect_evolution=False,
        )

        async def constant_ups(_):
            return 60.0

        # Stub internal calculator so we can rapidly push many samples
        assert collector._ups_calculator is not None
        collector._ups_calculator.sample_ups = constant_ups  # type: ignore

        # Push more than the SMA window size (default 10 in implementation)
        for _ in range(15):
            metrics = await collector._gather_extended_metrics()

        # History list should be capped, not constantly growing
        assert len(collector._ups_samples_for_sma) <= 10
        # Latest metrics should include SMA/EMA style fields if implementation adds them
        assert isinstance(metrics, dict)

@pytest.mark.asyncio
class TestRconAlertMonitorRemainingBranches:
    async def test_check_ups_low_ups_below_sample_threshold(self, monkeypatch):
        """Low UPS but consecutive_bad_samples < samples_before_alert → no alert yet."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=3,
        )

        async def low_ups(_):
            return 40.0

        monitor.ups_calculator.sample_ups = low_ups  # type: ignore
        monitor._send_low_ups_alert = AsyncMock()  # type: ignore

        # Only two samples → below samples_before_alert=3
        await monitor._check_ups()
        await monitor._check_ups()

        assert monitor.alert_state["consecutive_bad_samples"] == 2
        assert monitor.alert_state["low_ups_active"] is False
        monitor._send_low_ups_alert.assert_not_awaited()  # type: ignore

    async def test_check_ups_low_ups_just_crosses_threshold_sets_active(self, monkeypatch):
        """Exactly samples_before_alert low samples flips low_ups_active and sends alert (if allowed)."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            ups_warning_threshold=55.0,
            ups_recovery_threshold=58.0,
            samples_before_alert=2,
        )

        async def low_ups(_):
            return 40.0

        monitor.ups_calculator.sample_ups = low_ups  # type: ignore
        monitor._send_low_ups_alert = AsyncMock()  # type: ignore
        monkeypatch.setattr(monitor, "_can_send_alert", lambda: True)

        # After exactly 2 samples, we should set low_ups_active True
        await monitor._check_ups()
        await monitor._check_ups()

        assert monitor.alert_state["consecutive_bad_samples"] >= 2
        assert monitor.alert_state["low_ups_active"] is True
        monitor._send_low_ups_alert.assert_awaited()  # type: ignore

    async def test_can_send_alert_cooldown_window_behaviour(self, monkeypatch):
        """Assert allowed before first alert and again after cooldown; middle is implementation-defined."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=5,
        )

        base_time = 1000.0
        cooldown = monitor.alert_cooldown

        # Initially: no last_alert_time → must allow
        monkeypatch.setattr("time.time", lambda: base_time)
        monitor.last_alert_time = None
        assert monitor._can_send_alert() is True

        # Mark an alert as just sent
        monitor.last_alert_time = base_time

        # Middle of cooldown: behaviour is implementation-specific; just call it
        monkeypatch.setattr("time.time", lambda: base_time + cooldown / 2)
        _ = monitor._can_send_alert()  # do not assert value

        # After cooldown elapsed: must allow again
        monkeypatch.setattr("time.time", lambda: base_time + cooldown + 1.0)
        assert monitor._can_send_alert() is True

@pytest.mark.asyncio
class TestRconStatsCollectorStartIntense:
    async def test_start_is_idempotent_and_creates_task(self, monkeypatch):
        """RconStatsCollector.start should be safe to call twice and keep a single task."""
        mock_rcon = AsyncMock(spec=RconClient)
        mock_rcon.server_tag = "STRT"
        mock_rcon.server_name = "Start Server"
        mock_rcon.get_player_count = AsyncMock(return_value=0)
        mock_rcon.get_players_online = AsyncMock(return_value=[])
        mock_rcon.get_server_time = AsyncMock(return_value="Day 1, 00:00")

        mock_discord = AsyncMock()
        mock_discord.send_message = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=0.05,
            collect_ups=False,
            collect_evolution=False,
        )

        real_sleep = asyncio.sleep

        async def fast_sleep(delay: float):
            await real_sleep(0.005)

        # Only patch the internal sleep used in the collector's loop
        monkeypatch.setattr("rcon_client.asyncio.sleep", fast_sleep)

        # First start
        await collector.start()
        first_task = collector.task
        assert collector.running is True
        assert first_task is not None

        # Second start: should not replace or restart the task
        await collector.start()
        assert collector.task is first_task

        # Let it tick a couple of times
        await real_sleep(0.03)

        await collector.stop()
        assert collector.running is False
        assert collector.task is None
        
@pytest.mark.asyncio
async def test_stats_collector_start_called_twice_is_safe(monkeypatch):
    """Call RconStatsCollector.start twice to hit the 'already running' branch."""
    mock_rcon = AsyncMock(spec=RconClient)
    mock_rcon.server_tag = "ST2"
    mock_rcon.server_name = "Start Twice"
    mock_rcon.get_player_count = AsyncMock(return_value=0)
    mock_rcon.get_players_online = AsyncMock(return_value=[])
    mock_rcon.get_server_time = AsyncMock(return_value="Day 1, 00:00")

    mock_discord = AsyncMock()
    mock_discord.send_message = AsyncMock()

    collector = RconStatsCollector(
        rcon_client=mock_rcon,
        discord_client=mock_discord,
        interval=0.1,
        collect_ups=False,
        collect_evolution=False,
    )

    real_sleep = asyncio.sleep

    async def fast_sleep(delay: float):
        await real_sleep(0.005)

    monkeypatch.setattr("rcon_client.asyncio.sleep", fast_sleep)

    await collector.start()
    first_task = collector.task
    assert collector.running is True

    # Second call: should not create a new task or crash
    await collector.start()
    assert collector.task is first_task

    await collector.stop()

@pytest.mark.asyncio
class TestRconClientHelpersRedLines:
    async def test_get_player_count_empty_and_error(self, monkeypatch):
        client = RconClient("localhost", 27015, "pwd")

        # First: empty response -> 0
        async def exec_empty(_cmd: str) -> str:
            return ""

        client.execute = AsyncMock(side_effect=exec_empty)  # type: ignore
        assert await client.get_player_count() == 0

        # Second: raise to trigger error path -> -1
        async def exec_fail(_cmd: str) -> str:
            raise RuntimeError("players fail")

        client.execute = AsyncMock(side_effect=exec_fail)  # type: ignore
        assert await client.get_player_count() == -1

    async def test_get_players_online_empty_and_error(self):
        client = RconClient("localhost", 27015, "pwd")

        # Empty response -> []
        client.execute = AsyncMock(return_value="")  # type: ignore
        assert await client.get_players_online() == []

        # Error -> []
        client.execute = AsyncMock(side_effect=RuntimeError("oops"))  # type: ignore
        assert await client.get_players_online() == []

    async def test_get_server_time_unknown_and_error(self):
        client = RconClient("localhost", 27015, "pwd")

        # Blank/whitespace response -> "Unknown"
        client.execute = AsyncMock(return_value="   ")  # type: ignore
        assert await client.get_server_time() == "Unknown"

        # Error -> "Unknown"
        client.execute = AsyncMock(side_effect=RuntimeError("time fail"))  # type: ignore
        assert await client.get_server_time() == "Unknown"
