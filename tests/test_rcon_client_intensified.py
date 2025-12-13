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

"""Intensified tests for RconClient critical methods.

Focused on 100% line coverage for:
- RconClient.execute() (lines 235-279)
- RconClient._reconnection_loop() (lines 197-233)
- RconClient.connect() (lines 160-185)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call

try:
    from rcon_client import RconClient, RCON_AVAILABLE
except ImportError:
    from src.rcon_client import RconClient, RCON_AVAILABLE


class TestExecuteMethodIntensified:
    """Intensified tests for RconClient.execute() method."""

    @pytest.mark.asyncio
    async def test_execute_not_connected_calls_connect(self) -> None:
        """execute() should call connect() when not connected (line 245)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = False
        client.connect = AsyncMock()
        
        with pytest.raises(ConnectionError):
            await client.execute("status")
        
        client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_connection_check_after_reconnect(self) -> None:
        """execute() should check connected status after reconnect (line 246)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = False
        client.connect = AsyncMock()  # Doesn't set connected=True
        
        # Should raise because reconnect failed
        with pytest.raises(ConnectionError, match="connection failed"):
            await client.execute("status")

    @pytest.mark.asyncio
    async def test_execute_rcon_client_none_raises(self) -> None:
        """execute() should raise when RCONClient is None (line 249-250)."""
        with patch('rcon_client.RCONClient', None):
            client = RconClient.__new__(RconClient)
            client.connected = True
            client.host = "localhost"
            client.port = 27015
            client.password = "password"
            client.timeout = 10.0
            
            with pytest.raises(ConnectionError, match="RCON library not available"):
                await client.execute("status")

    @pytest.mark.asyncio
    async def test_execute_to_thread_called_with_execute_function(self) -> None:
        """execute() should call asyncio.to_thread with _execute function (line 256-270)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        call_count = 0
        async def mock_to_thread(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return "success"
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            result = await client.execute("status")
            assert result == "success"
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_execute_wait_for_timeout_applied(self) -> None:
        """execute() should apply timeout + 5.0 seconds (line 256-258)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password", timeout=3.0)
        client.connected = True
        
        timeout_values = []
        original_wait_for = asyncio.wait_for
        
        async def mock_wait_for(coro, timeout=None):
            timeout_values.append(timeout)
            return "success"
        
        with patch("rcon_client.asyncio.wait_for", side_effect=mock_wait_for):
            result = await client.execute("status")
            assert result == "success"
            assert timeout_values[0] == 8.0  # 3.0 + 5.0

    @pytest.mark.asyncio
    async def test_execute_returns_empty_string_on_none_response(self) -> None:
        """execute() should return empty string when response is None (line 265)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        async def mock_to_thread(fn, *args, **kwargs):
            return None
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            result = await client.execute("status")
            assert result == ""

    @pytest.mark.asyncio
    async def test_execute_logs_command_executed(self) -> None:
        """execute() should log command execution (line 267-271)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        async def mock_to_thread(fn, *args, **kwargs):
            return "result"
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            with patch("rcon_client.logger") as mock_logger:
                await client.execute("status")
                mock_logger.debug.assert_called()
                call_args = mock_logger.debug.call_args
                assert call_args[0][0] == "rcon_command_executed"

    @pytest.mark.asyncio
    async def test_execute_timeout_error_handling(self) -> None:
        """execute() should handle asyncio.TimeoutError (line 272-275)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password", timeout=1.0)
        client.connected = True
        
        with patch('rcon_client.asyncio.wait_for') as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(TimeoutError, match="timed out"):
                await client.execute("status")

    @pytest.mark.asyncio
    async def test_execute_timeout_error_logs(self) -> None:
        """execute() should log timeout error (line 273-274)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password", timeout=1.0)
        client.connected = True
        
        with patch('rcon_client.asyncio.wait_for') as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError()
            
            with patch("rcon_client.logger") as mock_logger:
                with pytest.raises(TimeoutError):
                    await client.execute("status")
                
                mock_logger.error.assert_called()
                call_args = mock_logger.error.call_args
                assert call_args[0][0] == "rcon_command_timeout"

    @pytest.mark.asyncio
    async def test_execute_generic_exception_sets_disconnected(self) -> None:
        """execute() should set connected=False on exception (line 278)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        async def mock_to_thread(fn, *args, **kwargs):
            raise RuntimeError("Test error")
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(RuntimeError):
                await client.execute("status")
            
            assert client.connected is False

    @pytest.mark.asyncio
    async def test_execute_exception_logs_error(self) -> None:
        """execute() should log exception (line 279-282)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        async def mock_to_thread(fn, *args, **kwargs):
            raise RuntimeError("Connection lost")
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            with patch("rcon_client.logger") as mock_logger:
                with pytest.raises(RuntimeError):
                    await client.execute("status")
                
                mock_logger.error.assert_called()
                call_args = mock_logger.error.call_args
                assert call_args[0][0] == "rcon_command_failed"


class TestConnectMethodIntensified:
    """Intensified tests for RconClient.connect() method."""

    @pytest.mark.asyncio
    async def test_connect_checks_rcon_available(self) -> None:
        """connect() should check RCON_AVAILABLE flag (line 161-163)."""
        with patch('rcon_client.RCON_AVAILABLE', False):
            client = RconClient.__new__(RconClient)
            client.host = "localhost"
            client.port = 27015
            client.password = "password"
            client.timeout = 10.0
            client.connected = False
            
            with patch("rcon_client.logger") as mock_logger:
                await client.connect()
                mock_logger.error.assert_called_with("rcon_library_not_available")
            
            assert client.connected is False

    @pytest.mark.asyncio
    async def test_connect_checks_rconclient_is_none(self) -> None:
        """connect() should check if RCONClient is None (line 161-163)."""
        with patch('rcon_client.RCONClient', None):
            client = RconClient.__new__(RconClient)
            client.host = "localhost"
            client.port = 27015
            client.password = "password"
            client.timeout = 10.0
            client.connected = False
            
            with patch("rcon_client.logger") as mock_logger:
                await client.connect()
                mock_logger.error.assert_called_with("rcon_library_not_available")

    @pytest.mark.asyncio
    async def test_connect_calls_to_thread_with_test_connect(self) -> None:
        """connect() should call asyncio.to_thread with _test_connect (line 172-177)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = False
        
        to_thread_called = False
        async def mock_to_thread(fn, *args, **kwargs):
            nonlocal to_thread_called
            to_thread_called = True
            return True
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            await client.connect()
            assert to_thread_called
            assert client.connected is True

    @pytest.mark.asyncio
    async def test_connect_success_sets_connected_true(self) -> None:
        """connect() should set connected=True on success (line 175)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = False
        
        async def mock_to_thread(fn, *args, **kwargs):
            return True
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            await client.connect()
            assert client.connected is True

    @pytest.mark.asyncio
    async def test_connect_success_resets_delay(self) -> None:
        """connect() should reset reconnect_delay on success (line 176)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            "localhost", 27015, "password",
            reconnect_delay=2.0
        )
        client.connected = False
        client.current_reconnect_delay = 16.0  # Was backed off
        
        async def mock_to_thread(fn, *args, **kwargs):
            return True
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            await client.connect()
            assert client.current_reconnect_delay == 2.0

    @pytest.mark.asyncio
    async def test_connect_success_logs_connected(self) -> None:
        """connect() should log connection success (line 177-181)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = False
        
        async def mock_to_thread(fn, *args, **kwargs):
            return True
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            with patch("rcon_client.logger") as mock_logger:
                await client.connect()
                mock_logger.info.assert_called()
                call_args = mock_logger.info.call_args
                assert call_args[0][0] == "rcon_connected"

    @pytest.mark.asyncio
    async def test_connect_exception_sets_disconnected(self) -> None:
        """connect() should set connected=False on exception (line 183)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.connected = True
        
        async def mock_to_thread(fn, *args, **kwargs):
            raise RuntimeError("Connection failed")
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            await client.connect()
            assert client.connected is False

    @pytest.mark.asyncio
    async def test_connect_exception_logs_error(self) -> None:
        """connect() should log connection error (line 184-189)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        
        async def mock_to_thread(fn, *args, **kwargs):
            raise RuntimeError("Connection failed")
        
        with patch("rcon_client.asyncio.to_thread", side_effect=mock_to_thread):
            with patch("rcon_client.logger") as mock_logger:
                await client.connect()
                mock_logger.error.assert_called()
                call_args = mock_logger.error.call_args
                assert call_args[0][0] == "rcon_connection_failed"


class TestReconnectionLoopIntensified:
    """Intensified tests for RconClient._reconnection_loop() method."""

    @pytest.mark.asyncio
    async def test_reconnection_loop_logs_startup(self) -> None:
        """_reconnection_loop() should log startup (line 205)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = True
        
        async def mock_sleep(delay):
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            with patch("rcon_client.logger") as mock_logger:
                await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
                
                # Check that startup was logged
                startup_logged = any(
                    call[0][0] == "rcon_reconnection_loop_started"
                    for call in mock_logger.info.call_args_list
                )
                assert startup_logged

    @pytest.mark.asyncio
    async def test_reconnection_loop_while_condition_respected(self) -> None:
        """_reconnection_loop() should respect while condition (line 206)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = False  # False from start
        
        # Should exit immediately without any sleeps
        await asyncio.wait_for(client._reconnection_loop(), timeout=0.5)
        
        assert client._should_reconnect is False

    @pytest.mark.asyncio
    async def test_reconnection_loop_initial_sleep_exact_duration(self) -> None:
        """_reconnection_loop() should sleep exactly 5.0 seconds initially (line 208)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = True
        
        sleep_calls = []
        async def mock_sleep(delay):
            sleep_calls.append(delay)
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
        
        assert sleep_calls[0] == 5.0

    @pytest.mark.asyncio
    async def test_reconnection_loop_connects_when_disconnected(self) -> None:
        """_reconnection_loop() should call connect when not connected (line 214)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = False
        client.connect = AsyncMock()
        
        async def mock_sleep(delay):
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
        
        client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnection_loop_backoff_sleep_exact_delay(self) -> None:
        """_reconnection_loop() should sleep exact backoff delay (line 216)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            "localhost", 27015, "password",
            reconnect_delay=1.5,
            reconnect_backoff=2.0
        )
        client._should_reconnect = True
        client.connected = False
        client.current_reconnect_delay = 1.5
        client.connect = AsyncMock()  # Fails
        
        sleep_calls = []
        async def mock_sleep(delay):
            sleep_calls.append(delay)
            if len(sleep_calls) >= 2:
                client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
        
        # Should have initial 5.0 + backoff delay
        assert 5.0 in sleep_calls
        assert 1.5 in sleep_calls  # Current delay before backoff

    @pytest.mark.asyncio
    async def test_reconnection_loop_applies_backoff_calculation(self) -> None:
        """_reconnection_loop() should apply backoff calculation (line 217-220)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            "localhost", 27015, "password",
            reconnect_delay=1.0,
            reconnect_backoff=2.0,
            max_reconnect_delay=60.0
        )
        client._should_reconnect = True
        client.connected = False
        client.connect = AsyncMock()  # Fails
        
        initial_delay = client.current_reconnect_delay
        
        async def mock_sleep(delay):
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
        
        # Backoff should have been applied
        assert client.current_reconnect_delay > initial_delay

    @pytest.mark.asyncio
    async def test_reconnection_loop_respects_max_delay_during_backoff(self) -> None:
        """_reconnection_loop() backoff should respect max (line 217-220)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient(
            "localhost", 27015, "password",
            reconnect_delay=1.0,
            reconnect_backoff=100.0,  # Very aggressive
            max_reconnect_delay=10.0
        )
        client._should_reconnect = True
        client.connected = False
        client.connect = AsyncMock()  # Fails
        
        async def mock_sleep(delay):
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
        
        # Should not exceed max
        assert client.current_reconnect_delay <= 10.0

    @pytest.mark.asyncio
    async def test_reconnection_loop_logs_backoff(self) -> None:
        """_reconnection_loop() should log backoff (line 221-224)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = False
        client.connect = AsyncMock()  # Fails
        
        async def mock_sleep(delay):
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            with patch("rcon_client.logger") as mock_logger:
                await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
                
                # Check backoff was logged
                backoff_logged = any(
                    call[0][0] == "rcon_reconnect_backoff"
                    for call in mock_logger.debug.call_args_list
                )
                assert backoff_logged

    @pytest.mark.asyncio
    async def test_reconnection_loop_exception_caught_and_logged(self) -> None:
        """_reconnection_loop() should catch Exception (line 228-233)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connect = AsyncMock(side_effect=RuntimeError("Test"))
        
        sleep_count = 0
        async def mock_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 2:
                client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
        
        # Should have continued after exception
        assert sleep_count >= 2

    @pytest.mark.asyncio
    async def test_reconnection_loop_exception_logs_error(self) -> None:
        """_reconnection_loop() should log exception (line 229-232)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connect = AsyncMock(side_effect=RuntimeError("Test error"))
        
        async def mock_sleep(delay):
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            with patch("rcon_client.logger") as mock_logger:
                await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
                
                mock_logger.error.assert_called()
                call_args = mock_logger.error.call_args
                assert call_args[0][0] == "rcon_reconnection_loop_error"

    @pytest.mark.asyncio
    async def test_reconnection_loop_exception_recovery_sleep(self) -> None:
        """_reconnection_loop() should sleep after exception (line 233)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connect = AsyncMock(side_effect=RuntimeError("Test"))
        
        sleep_calls = []
        async def mock_sleep(delay):
            sleep_calls.append(delay)
            if len(sleep_calls) >= 2:
                client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
        
        # Should have 5.0 (initial) + 5.0 (recovery)
        assert len(sleep_calls) >= 2
        assert all(d == 5.0 for d in sleep_calls)

    @pytest.mark.asyncio
    async def test_reconnection_loop_skip_connect_when_connected(self) -> None:
        """_reconnection_loop() should skip connect when already connected (line 209)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = True
        client.connect = AsyncMock()
        
        async def mock_sleep(delay):
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
        
        # connect should NOT be called when already connected
        client.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconnection_loop_logs_reconnect_attempt(self) -> None:
        """_reconnection_loop() should log reconnect attempt (line 210-213)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client._should_reconnect = True
        client.connected = False
        client.connect = AsyncMock()
        
        async def mock_sleep(delay):
            client._should_reconnect = False
        
        with patch("rcon_client.asyncio.sleep", side_effect=mock_sleep):
            with patch("rcon_client.logger") as mock_logger:
                await asyncio.wait_for(client._reconnection_loop(), timeout=1.0)
                
                # Check reconnect attempt was logged
                reconnect_logged = any(
                    call[0][0] == "rcon_attempting_reconnect"
                    for call in mock_logger.info.call_args_list
                )
                assert reconnect_logged

    @pytest.mark.asyncio
    async def test_reconnection_loop_handles_cancelled_via_stop(self) -> None:
        """_reconnection_loop() should handle cancellation via stop() call (line 225-227)."""
        if not RCON_AVAILABLE:
            pytest.skip("rcon library not available")
        
        client = RconClient("localhost", 27015, "password")
        client.disconnect = AsyncMock()
        
        await client.start()
        await asyncio.sleep(0.1)  # Let loop run
        
        # Now stop it
        await client.stop()
        
        # Verify stopped state
        assert client._should_reconnect is False
        assert client.reconnect_task is None
        client.disconnect.assert_called_once()
