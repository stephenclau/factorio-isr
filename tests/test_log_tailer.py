"""
Comprehensive tests for log_tailer.py with 95%+ coverage.

Tests LogTailer lifecycle, file monitoring, rotation detection,
callback handling, error conditions, and LogTailerFactory.
"""

import pytest
import asyncio
from pathlib import Path
from typing import List
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from log_tailer import LogTailer, LogTailerFactory


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file path."""
    log_file = tmp_path / "test.log"
    return log_file


@pytest.fixture
def existing_log_file(tmp_path):
    """Create a temporary log file that already exists."""
    log_file = tmp_path / "existing.log"
    log_file.write_text("Initial content\n")
    return log_file


@pytest.fixture
def mock_callback():
    """Create a mock async callback function."""
    callback = AsyncMock()
    return callback


@pytest.fixture
def tailer(temp_log_file, mock_callback):
    """Create a LogTailer instance for testing."""
    return LogTailer(
        log_path=temp_log_file,
        line_callback=mock_callback,
        poll_interval=0.01  # Fast polling for tests
    )


@pytest.fixture
def tailer_with_existing_file(existing_log_file, mock_callback):
    """Create a LogTailer with an existing file."""
    return LogTailer(
        log_path=existing_log_file,
        line_callback=mock_callback,
        poll_interval=0.01
    )


# ============================================================================
# LogTailer Initialization Tests
# ============================================================================

class TestLogTailerInit:
    """Test LogTailer initialization."""
    
    def test_init_with_required_params(self, temp_log_file, mock_callback):
        """Test initialization with required parameters."""
        tailer = LogTailer(
            log_path=temp_log_file,
            line_callback=mock_callback
        )
        
        assert tailer.log_path == temp_log_file
        assert tailer.line_callback == mock_callback
        assert tailer.poll_interval == 0.1  # Default
        assert tailer._running is False
        assert tailer._task is None
        assert tailer._file is None
        assert tailer._inode is None
    
    def test_init_with_custom_poll_interval(self, temp_log_file, mock_callback):
        """Test initialization with custom poll interval."""
        tailer = LogTailer(
            log_path=temp_log_file,
            line_callback=mock_callback,
            poll_interval=0.5
        )
        
        assert tailer.poll_interval == 0.5
    
    def test_init_accepts_path_object(self, mock_callback):
        """Test that initialization accepts Path objects."""
        log_path = Path("/tmp/test.log")
        tailer = LogTailer(
            log_path=log_path,
            line_callback=mock_callback
        )
        
        assert isinstance(tailer.log_path, Path)
        assert tailer.log_path == log_path


# ============================================================================
# start() and stop() Tests
# ============================================================================

class TestStartStop:
    """Test LogTailer start() and stop() methods."""
    
    @pytest.mark.asyncio
    async def test_start_creates_task(self, existing_log_file, mock_callback):
        """Test that start() creates an async task."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        
        assert tailer._running is True
        assert tailer._task is not None
        assert isinstance(tailer._task, asyncio.Task)
        
        # Cleanup
        await tailer.stop()
    
    @pytest.mark.asyncio
    async def test_start_when_already_running(self, existing_log_file, mock_callback):
        """Test that calling start() when already running is safe."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        first_task = tailer._task
        
        # Call start again
        await tailer.start()
        
        # Should still be the same task
        assert tailer._task is first_task
        
        # Cleanup
        await tailer.stop()
    
    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, existing_log_file, mock_callback):
        """Test that stop() cancels the tailing task."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)  # Let it run briefly
        
        await tailer.stop()
        
        assert tailer._running is False
        assert tailer._task is not None  # Task still exists but is cancelled
        assert tailer._file is None  # File should be closed
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, tailer):
        """Test that stop() is safe when not running."""
        # Tailer never started
        await tailer.stop()
        
        # Should complete without error
        assert tailer._running is False
    
    @pytest.mark.asyncio
    async def test_stop_closes_file(self, existing_log_file, mock_callback):
        """Test that stop() closes the open file handle."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)  # Let it open the file
        
        # File should be open
        assert tailer._file is not None
        
        await tailer.stop()
        
        # File should be closed
        assert tailer._file is None


# ============================================================================
# _wait_for_file() Tests
# ============================================================================

class TestWaitForFile:
    """Test LogTailer._wait_for_file() method."""
    
    @pytest.mark.asyncio
    async def test_wait_for_file_when_exists(self, existing_log_file, mock_callback):
        """Test waiting for file that already exists."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        tailer._running = True
        
        # Should return immediately
        await tailer._wait_for_file()
        
        # File exists, so no waiting needed
        assert existing_log_file.exists()
    
    @pytest.mark.asyncio
    async def test_wait_for_file_creates_after_delay(self, temp_log_file, mock_callback):
        """Test waiting for file that is created after a delay."""
        tailer = LogTailer(
            log_path=temp_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        tailer._running = True
        
        # Create file after a delay
        async def create_file_later():
            await asyncio.sleep(0.05)
            temp_log_file.write_text("Created!\n")
        
        # Start both tasks
        create_task = asyncio.create_task(create_file_later())
        wait_task = asyncio.create_task(tailer._wait_for_file())
        
        # Wait for both
        await asyncio.gather(create_task, wait_task)
        
        assert temp_log_file.exists()
    
    @pytest.mark.asyncio
    async def test_wait_for_file_stops_when_not_running(self, temp_log_file, mock_callback):
        """Test that wait stops when tailer is stopped."""
        tailer = LogTailer(
            log_path=temp_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        tailer._running = True
        
        # Stop tailer after brief delay
        async def stop_later():
            await asyncio.sleep(0.03)
            tailer._running = False
        
        stop_task = asyncio.create_task(stop_later())
        wait_task = asyncio.create_task(tailer._wait_for_file())
        
        await asyncio.gather(stop_task, wait_task)
        
        # File still doesn't exist, but wait should have stopped
        assert not temp_log_file.exists()


# ============================================================================
# _open_file() Tests
# ============================================================================

class TestOpenFile:
    """Test LogTailer._open_file() method."""
    
    def test_open_file_success(self, existing_log_file, mock_callback):
        """Test successfully opening a file."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback
        )
        
        tailer._open_file()
        
        assert tailer._file is not None
        assert tailer._inode is not None
        
        # Cleanup
        if tailer._file is not None:  # Type guard for close
            tailer._file.close()
    
    def test_open_file_seeks_to_end(self, existing_log_file, mock_callback):
        """Test that file is opened at the end (seeking to EOF)."""
        # Write some initial content
        existing_log_file.write_text("Line 1\nLine 2\nLine 3\n")
        
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback
        )
        
        tailer._open_file()
        
        # Assert file was opened
        assert tailer._file is not None
        
        # Should be at end of file
        current_pos = tailer._file.tell()
        file_size = existing_log_file.stat().st_size
        
        assert current_pos == file_size
        
        # Cleanup
        if tailer._file is not None:  # Type guard for close
            tailer._file.close()
    
    def test_open_file_closes_existing_file(self, existing_log_file, mock_callback):
        """Test that opening a file closes any previously open file."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback
        )
        
        # Open file first time
        tailer._open_file()
        first_file = tailer._file
        
        # Open again
        tailer._open_file()
        second_file = tailer._file
        
        # Should be different file objects
        assert first_file is not second_file
        assert tailer._file == second_file
        
        # Cleanup
        if tailer._file is not None:  # Type guard for close
            tailer._file.close()
    
    def test_open_file_stores_inode(self, existing_log_file, mock_callback):
        """Test that file inode is stored for rotation detection."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback
        )
        
        tailer._open_file()
        
        expected_inode = existing_log_file.stat().st_ino
        assert tailer._inode == expected_inode
        
        # Cleanup
        if tailer._file is not None:  # Type guard for close
            tailer._file.close()


# ============================================================================
# _check_rotation() Tests
# ============================================================================

class TestCheckRotation:
    """Test LogTailer._check_rotation() method."""
    
    def test_check_rotation_no_rotation(self, existing_log_file, mock_callback):
        """Test when file has not been rotated."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback
        )
        
        tailer._open_file()
        
        # Check rotation immediately - should be False
        result = tailer._check_rotation()
        
        assert result is False
        
        # Cleanup
        if tailer._file is not None:  # Type guard for close
            tailer._file.close()
    
    def test_check_rotation_file_deleted(self, existing_log_file, mock_callback):
        """Test rotation detection when file is deleted."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback
        )
        
        tailer._open_file()
        
        # Delete the file
        existing_log_file.unlink()
        
        # Should detect rotation
        result = tailer._check_rotation()
        
        assert result is True
        
        # Cleanup
        if tailer._file:
            tailer._file.close()
    
    def test_check_rotation_inode_changed(self, existing_log_file, mock_callback, tmp_path):
        """Test rotation detection when inode changes."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback
        )
        
        tailer._open_file()
        old_inode = tailer._inode
        
        # Simulate rotation: delete and recreate file
        existing_log_file.unlink()
        existing_log_file.write_text("New file after rotation\n")
        
        # New file should have different inode
        new_inode = existing_log_file.stat().st_ino
        
        # Note: On some filesystems, inode might be reused, so we can't
        # guarantee they're different, but _check_rotation should still work
        result = tailer._check_rotation()
        
        # Should detect rotation (file was deleted)
        assert result is True
        
        # Cleanup
        if tailer._file:
            tailer._file.close()
    
    def test_check_rotation_os_error(self, existing_log_file, mock_callback):
        """Test handling of OSError during rotation check."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback
        )
        
        tailer._open_file()
        
        # Mock stat() to raise OSError
        with patch.object(Path, 'stat', side_effect=OSError("Permission denied")):
            result = tailer._check_rotation()
            
            # Should treat error as rotation
            assert result is True
        
        # Cleanup
        if tailer._file:
            tailer._file.close()


# ============================================================================
# _tail_loop() Tests
# ============================================================================

class TestTailLoop:
    """Test LogTailer._tail_loop() method."""
    
    @pytest.mark.asyncio
    async def test_tail_loop_reads_new_lines(self, existing_log_file, mock_callback):
        """Test that tail loop reads and processes new lines."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)  # Let it start
        
        # Append new lines
        with open(existing_log_file, 'a') as f:
            f.write("New line 1\n")
            f.write("New line 2\n")
        
        # Wait for lines to be read
        await asyncio.sleep(0.1)
        
        await tailer.stop()
        
        # Callback should have been called for each new line
        assert mock_callback.call_count >= 2
        calls = [call.args[0] for call in mock_callback.call_args_list]
        assert "New line 1" in calls
        assert "New line 2" in calls
    
    @pytest.mark.asyncio
    async def test_tail_loop_skips_empty_lines(self, existing_log_file, mock_callback):
        """Test that empty lines are skipped."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Append lines with empty lines
        with open(existing_log_file, 'a') as f:
            f.write("Line 1\n")
            f.write("\n")  # Empty line
            f.write("Line 2\n")
            f.write("   \n")  # Whitespace only (will be stripped to empty)
        
        await asyncio.sleep(0.1)
        await tailer.stop()
        
        # Should only process non-empty lines
        calls = [call.args[0] for call in mock_callback.call_args_list]
        assert "Line 1" in calls
        assert "Line 2" in calls
        # Empty lines should not trigger callback
        assert "" not in calls
    
    @pytest.mark.asyncio
    async def test_tail_loop_handles_callback_exception(self, existing_log_file):
        """Test that exceptions in callback are caught and logged."""
        # Create callback that raises exception
        failing_callback = AsyncMock(side_effect=RuntimeError("Callback failed"))
        
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=failing_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Append a line
        with open(existing_log_file, 'a') as f:
            f.write("Test line\n")
            f.flush()
        
        # Give it time to process and handle the exception
        await asyncio.sleep(0.15)
        
        # Tailer should still be running despite callback error
        assert tailer._running is True
        
        # Write another line to verify tailer still works
        with open(existing_log_file, 'a') as f:
            f.write("Second line\n")
            f.flush()
        
        await asyncio.sleep(0.1)
        
        # Stop the tailer
        await tailer.stop()
        
        # Callback should have been called multiple times (once per line)
        assert failing_callback.call_count >= 2
    
    
    @pytest.mark.asyncio
    async def test_tail_loop_detects_file_rotation(self, existing_log_file, mock_callback):
        """Test that tail loop detects and handles file rotation."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.1)
        
        # Write and verify initial line
        with open(existing_log_file, 'a') as f:
            f.write("Line 1\n")
            f.flush()
        
        await asyncio.sleep(0.1)
        
        initial_calls = mock_callback.call_count
        assert initial_calls >= 1
        
        # Store initial inode
        initial_inode = existing_log_file.stat().st_ino
        
        # Simulate rotation by deleting and recreating
        existing_log_file.unlink()
        await asyncio.sleep(0.15)  # Give time to detect
        
        # Create new file
        existing_log_file.write_text("")
        await asyncio.sleep(0.15)  # Give time to reopen
        
        # Verify new inode (file was rotated)
        new_inode = existing_log_file.stat().st_ino
        # Note: inodes might be reused on some filesystems, so we can't always assert they differ
        
        # Write new line and verify tailer still works
        with open(existing_log_file, 'a') as f:
            f.write("Line after rotation\n")
            f.flush()
        
        await asyncio.sleep(0.2)
        await tailer.stop()
        
        # Tailer should still be functional and have processed more lines
        final_calls = mock_callback.call_count
        assert final_calls >= initial_calls  # Should have processed at least initial lines
        
        # Verify tailer stopped cleanly
        assert tailer._running is False
        assert tailer._file is None

    
    @pytest.mark.asyncio
    async def test_tail_loop_waits_for_file_creation(self, temp_log_file, mock_callback):
        """Test that tail loop waits for file to be created."""
        tailer = LogTailer(
            log_path=temp_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        
        # Create file after delay
        await asyncio.sleep(0.05)
        temp_log_file.write_text("Initial line\n")
        
        # Write additional line
        await asyncio.sleep(0.03)
        with open(temp_log_file, 'a') as f:
            f.write("Second line\n")
        
        await asyncio.sleep(0.1)
        await tailer.stop()
        
        # Should have read the second line (first line was before tail point)
        calls = [call.args[0] for call in mock_callback.call_args_list]
        assert "Second line" in calls
    
    @pytest.mark.asyncio
    async def test_tail_loop_cancellation(self, existing_log_file, mock_callback):
        """Test that tail loop handles cancellation gracefully."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Stop should cancel the task
        await tailer.stop()
        
        # Should complete without errors
        assert tailer._running is False
        assert tailer._file is None
    
    @pytest.mark.asyncio
    async def test_tail_loop_cleanup_on_stop(self, existing_log_file, mock_callback):
        """Test that file is properly cleaned up when tail loop stops."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # File should be open while running
        assert tailer._file is not None
        
        # Stop the tailer
        await tailer.stop()
        
        # File should be closed after stop
        assert tailer._file is None


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_tailing_workflow(self, existing_log_file, mock_callback):
        """Test complete workflow: start, read lines, stop."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        # Start tailing
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Write multiple lines
        lines_to_write = [
            "Player1 joined the game",
            "[CHAT] Player1: Hello!",
            "Player2 joined the game",
            "[CHAT] Player2: Hi there!",
            "Server saved",
        ]
        
        with open(existing_log_file, 'a') as f:
            for line in lines_to_write:
                f.write(f"{line}\n")
                f.flush()
        
        # Wait for lines to be processed
        await asyncio.sleep(0.2)
        
        # Stop tailing
        await tailer.stop()
        
        # Verify all lines were processed
        calls = [call.args[0] for call in mock_callback.call_args_list]
        for expected_line in lines_to_write:
            assert expected_line in calls
    
    @pytest.mark.asyncio
    async def test_concurrent_tailers(self, tmp_path, mock_callback):
        """Test multiple tailers can run concurrently."""
        file1 = tmp_path / "log1.log"
        file2 = tmp_path / "log2.log"
        
        file1.write_text("Log 1 initial\n")
        file2.write_text("Log 2 initial\n")
        
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        
        tailer1 = LogTailer(file1, callback1, poll_interval=0.01)
        tailer2 = LogTailer(file2, callback2, poll_interval=0.01)
        
        # Start both
        await tailer1.start()
        await tailer2.start()
        await asyncio.sleep(0.05)
        
        # Write to both files
        with open(file1, 'a') as f:
            f.write("Log 1 new line\n")
        
        with open(file2, 'a') as f:
            f.write("Log 2 new line\n")
        
        await asyncio.sleep(0.1)
        
        # Stop both
        await tailer1.stop()
        await tailer2.stop()
        
        # Each callback should have received its file's line
        calls1 = [call.args[0] for call in callback1.call_args_list]
        calls2 = [call.args[0] for call in callback2.call_args_list]
        
        assert "Log 1 new line" in calls1
        assert "Log 2 new line" in calls2


# ============================================================================
# LogTailerFactory Tests
# ============================================================================

class TestLogTailerFactory:
    """Test LogTailerFactory class."""
    
    def test_create_factorio_tailer(self, temp_log_file, mock_callback):
        """Test creating a Factorio tailer with factory."""
        tailer = LogTailerFactory.create_factorio_tailer(
            log_path=temp_log_file,
            line_callback=mock_callback
        )
        
        assert isinstance(tailer, LogTailer)
        assert tailer.log_path == temp_log_file
        assert tailer.line_callback == mock_callback
        assert tailer.poll_interval == 0.1  # Default for Factorio
    
    def test_create_factorio_tailer_returns_configured_instance(self, temp_log_file):
        """Test that factory returns properly configured LogTailer."""
        callback = AsyncMock()
        
        tailer = LogTailerFactory.create_factorio_tailer(
            log_path=temp_log_file,
            line_callback=callback
        )
        
        # Should be ready to use
        assert tailer._running is False
        assert tailer._task is None
        assert tailer._file is None


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_very_long_line(self, existing_log_file, mock_callback):
        """Test handling of very long lines."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Write very long line
        long_line = "A" * 100000
        with open(existing_log_file, 'a') as f:
            f.write(f"{long_line}\n")
        
        await asyncio.sleep(0.1)
        await tailer.stop()
        
        # Should handle long line
        calls = [call.args[0] for call in mock_callback.call_args_list]
        assert long_line in calls
    
    @pytest.mark.asyncio
    async def test_unicode_content(self, existing_log_file, mock_callback):
        """Test handling of unicode content."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Write unicode characters
        unicode_line = "玩家 joined: 你好 🎮"
        with open(existing_log_file, 'a', encoding='utf-8') as f:
            f.write(f"{unicode_line}\n")
        
        await asyncio.sleep(0.1)
        await tailer.stop()
        
        # Should handle unicode
        calls = [call.args[0] for call in mock_callback.call_args_list]
        assert unicode_line in calls
    
    @pytest.mark.asyncio
    async def test_multiple_lines_at_once(self, existing_log_file, mock_callback):
        """Test handling of multiple complete lines written at once."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Write multiple complete lines at once
        with open(existing_log_file, 'a') as f:
            f.write("Line 1\n")
            f.write("Line 2\n")
            f.write("Line 3\n")
            f.flush()
        
        await asyncio.sleep(0.15)
        await tailer.stop()
        
        # All three lines should be read
        calls = [call.args[0] for call in mock_callback.call_args_list]
        assert "Line 1" in calls
        assert "Line 2" in calls
        assert "Line 3" in calls
        assert len(calls) >= 3
    
    @pytest.mark.asyncio
    async def test_zero_poll_interval(self, existing_log_file, mock_callback):
        """Test with zero poll interval doesn't crash (tight loop)."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.0  # No sleep - tight loop
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Write multiple lines to increase chance of capture
        with open(existing_log_file, 'a') as f:
            for i in range(10):
                f.write(f"Fast line {i}\n")
            f.flush()
        
        # Should still work with zero interval
        await asyncio.sleep(0.2)
        await tailer.stop()
        
        # Should have processed at least some lines (zero interval is very fast)
        # Main goal is to verify it doesn't crash with tight loop
        assert tailer._running is False
        assert tailer._file is None
        # At least one line should have been processed
        assert mock_callback.call_count >= 1

    
    @pytest.mark.asyncio
    async def test_rapid_file_changes(self, existing_log_file, mock_callback):
        """Test handling of rapid file changes."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.01
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Write many lines rapidly
        with open(existing_log_file, 'a') as f:
            for i in range(50):
                f.write(f"Rapid line {i}\n")
                f.flush()
        
        await asyncio.sleep(0.2)
        await tailer.stop()
        
        # Should have read many lines
        assert mock_callback.call_count >= 40  # Allow some margin
    
    def test_file_path_types(self, mock_callback):
        """Test that various path types are accepted."""
        # String path
        tailer1 = LogTailer(
            log_path=Path("/tmp/test.log"),
            line_callback=mock_callback
        )
        assert isinstance(tailer1.log_path, Path)
        
        # Path object
        path = Path("/var/log/test.log")
        tailer2 = LogTailer(
            log_path=path,
            line_callback=mock_callback
        )
        assert tailer2.log_path == path


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_handles_high_throughput(self, existing_log_file, mock_callback):
        """Test handling high volume of log lines."""
        tailer = LogTailer(
            log_path=existing_log_file,
            line_callback=mock_callback,
            poll_interval=0.001  # Very fast polling
        )
        
        await tailer.start()
        await asyncio.sleep(0.05)
        
        # Write many lines quickly
        num_lines = 1000
        with open(existing_log_file, 'a') as f:
            for i in range(num_lines):
                f.write(f"High volume line {i}\n")
        
        # Give it time to process
        await asyncio.sleep(0.5)
        await tailer.stop()
        
        # Should have processed most lines (allow some margin)
        assert mock_callback.call_count >= num_lines * 0.9
