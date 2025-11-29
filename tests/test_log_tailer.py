"""
Comprehensive tests for log_tailer.py module.
Tests observable behavior of LogTailer class.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import List
import pytest

# Import with proper typing
from log_tailer import LogTailer, LogTailerFactory


@pytest.mark.asyncio
class TestLogTailerBasic:
    """Basic tailing functionality tests."""
    
    async def test_basic_tailing(self) -> None:
        """Test basic log tailing functionality."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_path = Path(f.name)
            f.write("Initial line\n")
            f.flush()
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.2)
            
            # Append new lines
            with open(log_path, 'a') as f:
                f.write("Test line 1\n")
                f.write("Test line 2\n")
                f.write("Test line 3\n")
                f.flush()
            
            await asyncio.sleep(0.3)
            await tailer.stop()
            
            # Verify - should NOT include initial (seeks to end)
            assert "Test line 1" in lines_received
            assert "Test line 2" in lines_received
            assert "Test line 3" in lines_received
            assert "Initial line" not in lines_received
        finally:
            log_path.unlink(missing_ok=True)
    
    async def test_empty_lines_skipped(self) -> None:
        """Test that empty lines are skipped after rstrip."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.2)
            
            with open(log_path, 'a') as f:
                f.write("Line 1\n")
                f.write("\n")
                f.write("Line 2\n")
                f.write("\n")
                f.write("\n")
                f.write("Line 3\n")
                f.flush()
            
            await asyncio.sleep(0.4)
            await tailer.stop()
            
            # Should have 3 non-empty lines
            assert len(lines_received) == 3
            assert "Line 1" in lines_received
            assert "Line 2" in lines_received
            assert "Line 3" in lines_received
        finally:
            log_path.unlink(missing_ok=True)
    
    async def test_multiple_writes(self) -> None:
        """Test handling multiple separate writes."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.15)
            
            with open(log_path, 'a') as f:
                f.write("First batch\n")
                f.flush()
            
            await asyncio.sleep(0.15)
            
            with open(log_path, 'a') as f:
                f.write("Second batch\n")
                f.flush()
            
            await asyncio.sleep(0.15)
            await tailer.stop()
            
            assert "First batch" in lines_received
            assert "Second batch" in lines_received
        finally:
            log_path.unlink(missing_ok=True)


@pytest.mark.asyncio
class TestLogTailerLifecycle:
    """Test start/stop lifecycle."""
    
    async def test_start_and_stop(self) -> None:
        """Test starting and stopping tailer."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.15)
            
            with open(log_path, 'a') as f:
                f.write("Test line\n")
                f.flush()
            
            await asyncio.sleep(0.2)
            await tailer.stop()
            
            assert "Test line" in lines_received
        finally:
            log_path.unlink(missing_ok=True)
    
    async def test_start_when_already_running(self) -> None:
        """Test that starting when already running logs warning."""
        async def callback(line: str) -> None:
            pass
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.1)
            
            # Should log warning and return
            await tailer.start()
            
            await asyncio.sleep(0.1)
            await tailer.stop()
        finally:
            log_path.unlink(missing_ok=True)
    
    async def test_stop_when_not_running(self) -> None:
        """Test that stopping when not running is safe."""
        async def callback(line: str) -> None:
            pass
        
        log_path = Path("/tmp/nonexistent_test.log")
        tailer = LogTailer(log_path, callback)
        
        # Should not raise error
        await tailer.stop()


@pytest.mark.asyncio
class TestLogTailerWaitForFile:
    """Test waiting for file creation."""
    
    async def test_file_exists_at_start(self) -> None:
        """Test that tailer works when file exists at start."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_path = Path(f.name)
            f.write("Initial\n")
            f.flush()
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.2)
            
            with open(log_path, 'a') as f:
                f.write("New line\n")
                f.flush()
            
            await asyncio.sleep(0.3)
            await tailer.stop()
            
            assert "New line" in lines_received
        finally:
            log_path.unlink(missing_ok=True)


@pytest.mark.asyncio
class TestLogTailerRotation:
    """Test file behavior edge cases."""
    
    async def test_continuous_writing(self) -> None:
        """Test tailer handles continuous writes without rotation."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.2)
            
            # Write multiple times
            for i in range(5):
                with open(log_path, 'a') as f:
                    f.write(f"Batch {i}\n")
                    f.flush()
                await asyncio.sleep(0.1)
            
            await asyncio.sleep(0.3)
            await tailer.stop()
            
            # Should have all batches
            assert len(lines_received) >= 5
            assert "Batch 0" in lines_received
            assert "Batch 4" in lines_received
        finally:
            log_path.unlink(missing_ok=True)


@pytest.mark.asyncio
class TestLogTailerErrorHandling:
    """Test error handling."""
    
    async def test_callback_exception_handling(self) -> None:
        """Test that callback exceptions don't crash tailer."""
        call_count = 0
        
        async def failing_callback(line: str) -> None:
            nonlocal call_count
            call_count += 1
            if "error" in line:
                raise ValueError("Test error")
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailer(log_path, failing_callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.15)
            
            with open(log_path, 'a') as f:
                f.write("error line 1\n")
                f.write("ok line 2\n")
                f.write("error line 3\n")
                f.flush()
            
            await asyncio.sleep(0.3)
            await tailer.stop()
            
            assert call_count == 3
        finally:
            log_path.unlink(missing_ok=True)
    
    async def test_unicode_handling(self) -> None:
        """Test unicode character handling."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.15)
            
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write("Player 🎮 joined\n")
                f.write("你好世界\n")
                f.flush()
            
            await asyncio.sleep(0.25)
            await tailer.stop()
            
            assert any("🎮" in line for line in lines_received)
            assert any("你好世界" in line for line in lines_received)
        finally:
            log_path.unlink(missing_ok=True)


@pytest.mark.asyncio
class TestLogTailerPerformance:
    """Test performance with many lines."""
    
    async def test_many_lines(self) -> None:
        """Test handling many lines at once."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailer(log_path, callback, poll_interval=0.05)
            await tailer.start()
            await asyncio.sleep(0.15)
            
            with open(log_path, 'a') as f:
                for i in range(50):
                    f.write(f"Line {i}\n")
                f.flush()
            
            await asyncio.sleep(0.6)
            await tailer.stop()
            
            assert len(lines_received) >= 45
            assert "Line 0" in lines_received
            assert "Line 49" in lines_received
        finally:
            log_path.unlink(missing_ok=True)


@pytest.mark.asyncio
class TestLogTailerFactory:
    """Test LogTailerFactory."""
    
    async def test_create_factorio_tailer(self) -> None:
        """Test factory creates properly configured tailer."""
        lines_received: List[str] = []
        
        async def callback(line: str) -> None:
            lines_received.append(line)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            tailer = LogTailerFactory.create_factorio_tailer(log_path, callback)
            await tailer.start()
            await asyncio.sleep(0.15)
            
            with open(log_path, 'a') as f:
                f.write("Factory test\n")
                f.flush()
            
            await asyncio.sleep(0.2)
            await tailer.stop()
            
            assert "Factory test" in lines_received
        finally:
            log_path.unlink(missing_ok=True)
