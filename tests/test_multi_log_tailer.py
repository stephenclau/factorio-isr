"""
tests/test_multi_log_tailer.py - Comprehensive tests for MultiServerLogTailer
"""

import asyncio
import tempfile
from pathlib import Path
from typing import List, Tuple
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from multi_log_tailer import MultiServerLogTailer


class MockServerConfig:
    """Mock ServerConfig for testing."""
    def __init__(self, tag: str, logpath: Path):
        self.tag = tag
        self.logpath = logpath


@pytest.fixture
def temp_logs(tmp_path: Path) -> dict:
    """Create temporary log files for multiple servers."""
    servers = {}
    for tag in ["prod", "dev"]:
        logpath = tmp_path / f"{tag}_console.log"
        # ✅ START EMPTY - don't write initial content
        logpath.write_text("")
        servers[tag] = MockServerConfig(tag=tag, logpath=logpath)
    return servers

@pytest.mark.asyncio
async def test_multi_log_tailer_initialization(temp_logs: dict):
    """Test MultiServerLogTailer initialization."""
    lines_received: List[Tuple[str, str]] = []
    
    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))
    
    tailer = MultiServerLogTailer(temp_logs, callback)
    assert len(tailer.tailers) == 0  # Not started yet
    assert tailer.get_status() == {
        'prod': {'logpath': str(temp_logs['prod'].logpath), 'started': False},
        'dev': {'logpath': str(temp_logs['dev'].logpath), 'started': False},
    }


@pytest.mark.asyncio
async def test_multi_log_tailer_start_stop(temp_logs: dict):
    """Test starting and stopping multiple log tailers."""
    lines_received: List[Tuple[str, str]] = []
    
    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))
    
    tailer = MultiServerLogTailer(temp_logs, callback)
    await tailer.start()
    
    # Verify tailers started
    assert len(tailer.tailers) == 2
    assert 'prod' in tailer.tailers
    assert 'dev' in tailer.tailers
    
    # Let initial lines be read
    await asyncio.sleep(0.2)
    
    # Add new lines
    temp_logs['prod'].logpath.write_text("Initial line for prod\nNew prod line\n")
    temp_logs['dev'].logpath.write_text("Initial line for dev\nNew dev line\n")
    
    await asyncio.sleep(0.2)
    
    # Stop tailers
    await tailer.stop()
    
    # Verify we got tagged lines
    prod_lines = [line for line, tag in lines_received if tag == 'prod']
    dev_lines = [line for line, tag in lines_received if tag == 'dev']
    
    assert any('prod' in line for line in prod_lines)
    assert any('dev' in line for line in dev_lines)


@pytest.mark.asyncio
async def test_multi_log_tailer_invalid_config(tmp_path: Path):
    """Test that MultiServerLogTailer rejects invalid configs."""
    async def callback(line: str, server_tag: str) -> None:
        pass
    
    # Test empty config
    with pytest.raises(ValueError, match="cannot be empty"):
        MultiServerLogTailer({}, callback)
    
    # Test missing logpath
    class BadConfig:
        tag = "bad"
    
    with pytest.raises(ValueError, match="missing required 'logpath'"):
        MultiServerLogTailer({'bad': BadConfig()}, callback)
    
    # Test non-Path logpath
    class BadPathConfig:
        tag = "bad"
        logpath = "/some/string/path"
    
    with pytest.raises(ValueError, match="must be Path"):
        MultiServerLogTailer({'bad': BadPathConfig()}, callback)


@pytest.mark.asyncio
async def test_multi_log_tailer_concurrent_writes(temp_logs: dict):
    """Test handling concurrent log writes from multiple servers."""
    lines_received: List[Tuple[str, str]] = []
    
    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))
    
    tailer = MultiServerLogTailer(temp_logs, callback)
    await tailer.start()
    
    await asyncio.sleep(0.1)
    
    # Simulate concurrent writes
    async def write_lines(tag: str, count: int) -> None:
        with open(temp_logs[tag].logpath, 'a') as f:
            for i in range(count):
                f.write(f"Line {i} from {tag}\n")
            f.flush()
    
    # Write from both servers concurrently
    await asyncio.gather(
        write_lines('prod', 5),
        write_lines('dev', 5)
    )
    
    await asyncio.sleep(0.3)
    await tailer.stop()
    
    # Verify we got lines from both servers
    assert len(lines_received) >= 10
    assert any(tag == 'prod' for _, tag in lines_received)
    assert any(tag == 'dev' for _, tag in lines_received)


@pytest.mark.asyncio
async def test_multi_log_tailer_callback_error_handling(temp_logs: dict):
    """Test that errors in callback don't crash tailer."""
    call_count = 0

    async def error_callback(line: str, server_tag: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("Intentional test error")
        # Callback continues to be called after error

    tailer = MultiServerLogTailer(temp_logs, error_callback)
    await tailer.start()

    await asyncio.sleep(0.1)

    # ✅ APPEND (not write_text) - Add FIRST line
    with open(temp_logs['prod'].logpath, 'a') as f:
        f.write("Line 1 - will error\n")
        f.flush()

    await asyncio.sleep(0.2)

    # ✅ APPEND (not write_text) 



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
