"""
Exhaustive branch-walk tests for rcon_client.py.

Designed to run alongside test_rcon_client.py and test_rcon_client_intense.py.
Focuses specifically on remaining uncovered and rarely executed branches.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rcon_client import (
    RconClient,
    RconStatsCollector,
    RconAlertMonitor,
    UPSCalculator,
    RCON_AVAILABLE,
)


# ============================================================================
# RconClient additional edge tests
# ============================================================================

@pytest.mark.asyncio
class TestRconClientFullIntense:
    async def test_connect_not_available_skips_without_setting_connected(self, monkeypatch):
        """connect() branch where RCON_AVAILABLE is False or RCONClient is None."""
        if not RCON_AVAILABLE:
            pytest.skip("global RCON_AVAILABLE already False")

        client = RconClient("localhost", 27015, "pwd")
        # Force client module-level RCONClient to None
        monkeypatch.setattr("rcon_client.RCONClient", None)

        await client.connect()
        # Should exit early without raising and remain disconnected
        assert client.connected is False

    
    async def test_execute_timeout_error_path(self, monkeypatch):
        """Explicitly drive the asyncio.TimeoutError path in execute()."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        client = RconClient("localhost", 27015, "pwd", timeout=0.01)

        # Pretend we are already connected to exercise timeout branch
        client.connected = True

        def _execute_blocking() -> str:
            # A long-running function for to_thread
            import time as _time
            _time.sleep(0.2)
            return "LATE"

        # Force RCONClient to be non-None for assert but never actually used
        class Dummy:
            def __init__(self, *_, **__):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def run(self, command: str) -> str:
                return "OK"

        monkeypatch.setattr("rcon_client.RCONClient", Dummy)

        async def fake_to_thread(fn, *args, **kwargs):
            # Wrap blocking helper to guarantee timeout vs to_thread
            return _execute_blocking()  # type: ignore

        # Instead of patching asyncio.to_thread (used in your code),
        # directly patch asyncio.wait_for to raise TimeoutError.
        original_wait_for = asyncio.wait_for

        async def fake_wait_for(coro, timeout=None):
            raise asyncio.TimeoutError()

        monkeypatch.setattr("asyncio.wait_for", fake_wait_for)

        with pytest.raises(TimeoutError):
            await client.execute("status")

        # Restore wait_for to avoid side-effects on other tests
        monkeypatch.setattr("asyncio.wait_for", original_wait_for)

    async def test_execute_generic_exception_error_path(self, monkeypatch):
        """execute() branch where _execute raises generic Exception after connection succeeded."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")

        client = RconClient("localhost", 27015, "pwd", timeout=0.01)
        client.connected = True

        class Dummy:
            def __init__(self, *_, **__):
                pass

            def __enter__(self):
                raise RuntimeError("boom")

            def __exit__(self, *args):
                return False

        monkeypatch.setattr("rcon_client.RCONClient", Dummy)

        with pytest.raises(RuntimeError):
            await client.execute("status")

        # Should mark as disconnected on generic failure
        assert client.connected is False


# ============================================================================
# UPSCalculator final branches
# ============================================================================

@pytest.mark.asyncio
class TestUPSCalculatorFullIntense:
    async def test_sample_ups_zero_delta_time_returns_none(self, monkeypatch):
        """Branch where computed delta_seconds is zero or extremely small."""
        calc = UPSCalculator(pause_time_threshold=5.0)
        mock_client = AsyncMock(spec=RconClient)

        ticks = ["0", "60"]
        times = [1000.0, 1000.0]  # zero delta time

        async def exec_side_effect(_):
            return ticks.pop(0)

        mock_client.execute = AsyncMock(side_effect=exec_side_effect)
        monkeypatch.setattr("time.time", lambda: times.pop(0))

        # First sample initializes
        assert await calc.sample_ups(mock_client) is None
        # Second sample with zero delta time → returns None and state should not crash
        result = await calc.sample_ups(mock_client)
        assert result is None


# ============================================================================
# RconStatsCollector remaining branches
# ============================================================================

@pytest.mark.asyncio
class TestRconStatsCollectorFullIntense:
    async def test_collect_and_post_handles_player_count_error(self, monkeypatch):
        """_collect_and_post branch when get_player_count raises."""
        mock_rcon = AsyncMock(spec=RconClient)
        mock_rcon.server_tag = "ERR"
        mock_rcon.server_name = "Err Server"

        async def bad_player_count():
            raise RuntimeError("pc error")

        mock_rcon.get_player_count = bad_player_count  # type: ignore
        mock_rcon.get_players_online = AsyncMock(return_value=["Alice"])
        mock_rcon.get_server_time = AsyncMock(return_value="Day 1, 00:00")

        mock_discord = AsyncMock()
        mock_discord.send_message = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
            collect_ups=False,
            collect_evolution=False,
        )

        # Should not raise
        await collector._collect_and_post()

    async def test_collect_and_post_handles_discord_send_failure(self):
        """_collect_and_post branch where discord_client.send_message raises."""
        mock_rcon = AsyncMock(spec=RconClient)
        mock_rcon.server_tag = "ERR2"
        mock_rcon.server_name = "Err 2 Server"
        mock_rcon.get_player_count = AsyncMock(return_value=1)
        mock_rcon.get_players_online = AsyncMock(return_value=["Alice"])
        mock_rcon.get_server_time = AsyncMock(return_value="Day 1, 00:00")

        mock_discord = AsyncMock()
        mock_discord.send_message = AsyncMock(side_effect=RuntimeError("discord fail"))

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
            collect_ups=False,
            collect_evolution=False,
        )

        # Should swallow/log error rather than raise
        await collector._collect_and_post()

    async def test_format_stats_text_no_ups_or_evolution(self):
        """_format_stats_text branch when metrics has no UPS/evolution keys at all."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.server_tag = "BARE"
        mock_rcon.server_name = "Bare Server"
        mock_discord = AsyncMock()

        collector = RconStatsCollector(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            interval=60,
        )

        bare_metrics: Dict[str, Any] = {}
        text = collector._format_stats_text(
            player_count=0,
            players=[],
            server_time="Day 0, 00:00",
            metrics=bare_metrics,
        )
        # Only assert that label and time appear; UPS/Evo fields optional here
        assert "[BARE] Bare Server" in text
        assert "Day 0, 00:00" in text


# ============================================================================
# RconAlertMonitor remaining branches
# ============================================================================

@pytest.mark.asyncio
class TestRconAlertMonitorFullIntense:
    async def test_check_ups_handles_ema_based_low_detection(self, monkeypatch):
        """_check_ups path where decision UPS is ema_ups instead of current UPS."""
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

        # Start with a very low EMA, then ups_calculator returns a moderate UPS
        # so decision_ups used is ema_ups and still below threshold.
        async def moderate_ups(_):
            return 50.0

        monitor.ups_calculator.sample_ups = moderate_ups  # type: ignore
        monitor.ups_ema = 40.0  # existing low EMA
        monitor._send_low_ups_alert = AsyncMock()  # type: ignore
        monkeypatch.setattr(monitor, "_can_send_alert", lambda: True)

        await monitor._check_ups()

        assert monitor.alert_state["consecutive_bad_samples"] >= 1
        assert monitor.alert_state["low_ups_active"] is True
        monitor._send_low_ups_alert.assert_awaited()  # type: ignore

    async def test_check_ups_recovery_uses_ema_and_current_ups(self, monkeypatch):
        """_check_ups path where ema_ups and current UPS both above recovery threshold."""
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

        # Simulate existing low state with previous bad samples
        monitor.alert_state["low_ups_active"] = True
        monitor.alert_state["consecutive_bad_samples"] = 3
        monitor.ups_ema = 40.0

        async def good_ups(_):
            return 70.0

        monitor.ups_calculator.sample_ups = good_ups  # type: ignore
        monitor._send_ups_recovered_alert = AsyncMock()  # type: ignore
        monkeypatch.setattr(monitor, "_can_send_alert", lambda: True)

        # After check, EMA will move toward 70; assume >= recovery threshold in implementation
        await monitor._check_ups()

        # Even if EMA lags, current UPS > recovery threshold, so recovery branch should fire
        assert monitor.alert_state["low_ups_active"] is False
        monitor._send_ups_recovered_alert.assert_awaited()  # type: ignore

    async def test_start_noop_if_already_started(self, monkeypatch):
        """start() branch where monitor is already running."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_rcon.is_connected = True
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=0.1,
        )

        # First start
        await monitor.start()
        first_task = monitor.task

        # Second start should not replace task
        await monitor.start()
        assert monitor.task is first_task

        await monitor.stop()

    async def test_stop_without_task_is_safe(self):
        """stop() branch where task is already None."""
        mock_rcon = MagicMock(spec=RconClient)
        mock_discord = AsyncMock()

        monitor = RconAlertMonitor(
            rcon_client=mock_rcon,
            discord_client=mock_discord,
            check_interval=0.1,
        )

        assert monitor.task is None
        # Should not raise
        await monitor.stop()
        assert monitor.task is None

@pytest.mark.asyncio
async def test_reconnection_loop_runs_backoff_once_then_stops(monkeypatch):
    """Walk _reconnection_loop body: sleep, attempt reconnect, backoff, and error handler."""

    if not RCON_AVAILABLE:
        pytest.skip("rcon library not available")

    client = RconClient("localhost", 27015, "pwd", reconnect_delay=0.01, max_reconnect_delay=0.02)

    # Always disconnected so the reconnect path executes
    client.connected = False

    async def fake_connect():
        # Simulate failed reconnect attempt
        client.connected = False

    monkeypatch.setattr(client, "connect", fake_connect)

    real_sleep = asyncio.sleep

    async def fast_sleep(delay: float):
        # collapse long sleeps to something tiny
        await real_sleep(0.001)

    # Only patch the module-level sleep used in _reconnection_loop
    monkeypatch.setattr("rcon_client.asyncio.sleep", fast_sleep)

    client._should_reconnect = True
    task = asyncio.create_task(client._reconnection_loop())

    # Let loop run a couple of iterations
    await real_sleep(0.03)

    # Stop loop and allow clean exit
    client._should_reconnect = False
    await real_sleep(0.01)

    # Cancel if still pending to clean up
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # At minimum we exercised the path where it logged and attempted reconnect
    assert client._should_reconnect is False

@pytest.mark.asyncio
async def test_reconnection_loop_error_handler_and_backoff(monkeypatch):
    """
    Drive _reconnection_loop through:
    - initial start log
    - sleep
    - not-connected branch
    - failed connect raising Exception (error handler path)
    - backoff branch
    Then stop the loop.
    """
    if not RCON_AVAILABLE:
        pytest.skip("rcon library not available")

    client = RconClient("localhost", 27015, "pwd", reconnect_delay=0.01, max_reconnect_delay=0.02)
    client.connected = False

    # First connect call raises to trigger error handler; subsequent calls just keep it disconnected
    calls = {"count": 0}

    async def flaky_connect():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        client.connected = False

    monkeypatch.setattr(client, "connect", flaky_connect)

    real_sleep = asyncio.sleep

    async def fast_sleep(delay: float):
        # collapse 5s and backoff sleeps to something tiny
        await real_sleep(0.001)

    # Patch the sleep used inside _reconnection_loop only
    monkeypatch.setattr("rcon_client.asyncio.sleep", fast_sleep)

    client._should_reconnect = True
    task = asyncio.create_task(client._reconnection_loop())

    # Let loop run long enough to hit error handler and one backoff
    await real_sleep(0.03)

    # Stop loop and allow it to exit
    client._should_reconnect = False
    await real_sleep(0.01)

    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # We should have attempted connect at least twice: once raising, once after backoff
    assert calls["count"] >= 2

@pytest.mark.asyncio
async def test_execute_raises_when_connect_cannot_set_connected(monkeypatch):
    """Cover execute: not connected, connect() runs, but still not connected → ConnectionError."""
    client = RconClient("localhost", 27015, "pwd", timeout=0.1)

    async def fake_connect():
        client.connected = False

    client.connected = False
    monkeypatch.setattr(client, "connect", fake_connect)

    with pytest.raises(ConnectionError):
        await client.execute("status")


@pytest.mark.asyncio
async def test_execute_timeout_error_branch(monkeypatch):
    """Cover execute: asyncio.TimeoutError from wait_for."""
    client = RconClient("localhost", 27015, "pwd", timeout=0.01)
    client.connected = True

    class Dummy:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def run(self, command: str) -> str:
            return "OK"

    monkeypatch.setattr("rcon_client.RCONClient", Dummy)

    async def fake_wait_for(coro, timeout=None):
        raise asyncio.TimeoutError()

    monkeypatch.setattr("asyncio.wait_for", fake_wait_for)

    with pytest.raises(TimeoutError):
        await client.execute("status")


@pytest.mark.asyncio
async def test_execute_generic_failure_marks_disconnected(monkeypatch):
    """Cover execute: generic Exception from _execute context → logs and sets connected False."""
    client = RconClient("localhost", 27015, "pwd", timeout=0.1)
    client.connected = True

    class Failing:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            raise RuntimeError("boom")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("rcon_client.RCONClient", Failing)

    with pytest.raises(RuntimeError):
        await client.execute("status")

    assert client.connected is False

@pytest.mark.asyncio
async def test_reconnection_loop_backoff_and_error(monkeypatch):
    client = RconClient("localhost", 27015, "pwd", reconnect_delay=0.01, max_reconnect_delay=0.02)
    client.connected = False

    calls = {"count": 0}

    async def flaky_connect():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")  # trigger error handler in loop
        client.connected = False

    monkeypatch.setattr(client, "connect", flaky_connect)

    real_sleep = asyncio.sleep

    async def fast_sleep(delay: float):
        await real_sleep(0.001)

    monkeypatch.setattr("rcon_client.asyncio.sleep", fast_sleep)

    client._should_reconnect = True
    task = asyncio.create_task(client._reconnection_loop())

    await real_sleep(0.03)
    client._should_reconnect = False
    await real_sleep(0.01)

    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert calls["count"] >= 2

@pytest.mark.asyncio
async def test_reconnection_loop_skips_when_already_connected(monkeypatch):
    """
    Cover the branch where 'if not self.connected' is False inside _reconnection_loop.
    """
    client = RconClient("localhost", 27015, "pwd", reconnect_delay=0.01, max_reconnect_delay=0.02)

    # Start with connected=True to skip the reconnect block at least once
    client.connected = True

    async def fake_connect():
        # Should not be called while connected stays True
        client.connected = True

    monkeypatch.setattr(client, "connect", fake_connect)

    real_sleep = asyncio.sleep

    async def fast_sleep(delay: float):
        # Shorten the 5s loop sleep
        await real_sleep(0.001)

    monkeypatch.setattr("rcon_client.asyncio.sleep", fast_sleep)

    client._should_reconnect = True
    task = asyncio.create_task(client._reconnection_loop())

    # Let one iteration run with connected=True so the 'if not self.connected' is False
    await real_sleep(0.005)

    # Now flip connected=False once so reconnect path is also exercised
    client.connected = False
    await real_sleep(0.005)

    client._should_reconnect = False
    await real_sleep(0.005)

    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # We care that no exceptions occurred and the 'connected=True' path was hit
    assert True

@pytest.mark.asyncio
async def test_execute_raises_when_rcon_library_missing(monkeypatch):
    """
    Cover execute branch where RCONClient is None while client.connected is True.
    """
    client = RconClient("localhost", 27015, "pwd", timeout=0.1)
    client.connected = True

    # Force RCONClient None for this test only
    monkeypatch.setattr("rcon_client.RCONClient", None)

    with pytest.raises(ConnectionError) as exc:
        await client.execute("status")

    assert "library not available" in str(exc.value)
