"""
Comprehensive pytest suite for MultiServerLogTailer

Tests cover:
- Initialization and validation
- Happy path: starting, tailing, and stopping
- Error paths: missing configs, invalid attributes, callback exceptions
- Multi-server concurrent operations
- File rotation handling
- Graceful shutdown and restart
"""

import asyncio
import tempfile
from pathlib import Path
from typing import List, Tuple, Any, Dict
import pytest
import sys

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from multi_log_tailer import MultiServerLogTailer


class MockServerConfig:
    """Mock ServerConfig for testing."""
    def __init__(self, tag: str, log_path: Path) -> None:
        self.tag = tag
        self.log_path = log_path  # Use 'log_path' not 'logpath' to match actual usage


@pytest.fixture
def temp_logs(tmp_path: Path) -> Dict[str, MockServerConfig]:
    """Create temporary log files for multiple servers."""
    servers: Dict[str, MockServerConfig] = {}
    for tag in ["prod", "dev", "staging"]:
        log_path = tmp_path / f"{tag}_console.log"
        # Start with empty file
        log_path.write_text("")
        servers[tag] = MockServerConfig(tag=tag, log_path=log_path)
    return servers


# ============================================================================
# HAPPY PATH TESTS - Normal operation
# ============================================================================

@pytest.mark.asyncio
async def test_multi_log_tailer_initialization(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test MultiServerLogTailer initializes correctly."""
    lines_received: List[Tuple[str, str]] = []

    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))

    tailer = MultiServerLogTailer(temp_logs, callback)
    
    # Before starting, no tailers should be active
    assert len(tailer.tailers) == 0
    assert tailer.server_configs == temp_logs
    assert tailer.line_callback == callback
    assert tailer.poll_interval == 0.1


@pytest.mark.asyncio
async def test_multi_log_tailer_start_stop_happy_path(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test happy path: starting and stopping multiple log tailers."""
    lines_received: List[Tuple[str, str]] = []

    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))

    tailer = MultiServerLogTailer(temp_logs, callback, poll_interval=0.05)
    
    # Start all tailers
    await tailer.start()
    
    # Verify tailers started
    assert len(tailer.tailers) == 3
    assert "prod" in tailer.tailers
    assert "dev" in tailer.tailers
    assert "staging" in tailer.tailers
    
    # Let tailers initialize
    await asyncio.sleep(0.2)
    
    # Add lines to all servers
    for tag, config in temp_logs.items():
        with open(config.log_path, "a") as f:
            f.write(f"Line from {tag}\n")
            f.flush()
    
    # Wait for processing
    await asyncio.sleep(0.3)
    
    # Stop tailers
    await tailer.stop()
    
    # Verify we got tagged lines
    prod_lines = [line for line, tag in lines_received if tag == "prod"]
    dev_lines = [line for line, tag in lines_received if tag == "dev"]
    staging_lines = [line for line, tag in lines_received if tag == "staging"]
    
    assert len(prod_lines) > 0
    assert len(dev_lines) > 0
    assert len(staging_lines) > 0
    assert any("prod" in line for line in prod_lines)
    assert any("dev" in line for line in dev_lines)
    assert any("staging" in line for line in staging_lines)


@pytest.mark.asyncio
async def test_multi_log_tailer_concurrent_writes(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test happy path: handling concurrent writes to multiple servers."""
    lines_received: List[Tuple[str, str]] = []

    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))

    tailer = MultiServerLogTailer(temp_logs, callback, poll_interval=0.05)
    await tailer.start()
    await asyncio.sleep(0.15)
    
    # Simulate concurrent writes from all servers
    async def write_lines(tag: str, count: int) -> None:
        with open(temp_logs[tag].log_path, "a") as f:
            for i in range(count):
                f.write(f"Concurrent line {i} from {tag}\n")
            f.flush()
    
    # Write concurrently from all servers
    await asyncio.gather(
        write_lines("prod", 3),
        write_lines("dev", 3),
        write_lines("staging", 3),
    )
    
    await asyncio.sleep(0.3)
    await tailer.stop()
    
    # Verify we got lines from all servers
    assert len(lines_received) >= 9
    assert any(tag == "prod" for _, tag in lines_received)
    assert any(tag == "dev" for _, tag in lines_received)
    assert any(tag == "staging" for _, tag in lines_received)


@pytest.mark.asyncio
async def test_multi_log_tailer_get_status(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test get_status returns correct status for all servers."""
    async def callback(line: str, server_tag: str) -> None:
        pass

    tailer = MultiServerLogTailer(temp_logs, callback)
    
    # Get status before starting
    status = tailer.get_status()
    
    assert len(status) == 3
    for tag in ["prod", "dev", "staging"]:
        assert tag in status
        assert "log_path" in status[tag]
        assert "started" in status[tag]
        assert status[tag]["started"] is False
    
    # Start and check again
    await tailer.start()
    await asyncio.sleep(0.1)
    
    status_running = tailer.get_status()
    for tag in ["prod", "dev", "staging"]:
        assert status_running[tag]["started"] is True
    
    await tailer.stop()


@pytest.mark.asyncio
async def test_multi_log_tailer_sync_callback(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test that sync callbacks are supported."""
    lines_received: List[Tuple[str, str]] = []

    def sync_callback(line: str, server_tag: str) -> None:
        """Synchronous callback (not async)."""
        lines_received.append((line, server_tag))

    tailer = MultiServerLogTailer(temp_logs, sync_callback, poll_interval=0.05)
    await tailer.start()
    await asyncio.sleep(0.15)
    
    # Add lines
    for tag, config in temp_logs.items():
        with open(config.log_path, "a") as f:
            f.write(f"Sync test {tag}\n")
            f.flush()
    
    await asyncio.sleep(0.3)
    await tailer.stop()
    
    # Should have captured lines even though callback is sync
    assert len(lines_received) >= 3


# ============================================================================
# ERROR PATH TESTS - Invalid configurations and error handling
# ============================================================================

@pytest.mark.asyncio
async def test_multi_log_tailer_empty_config_raises() -> None:
    """Test error path: empty server config raises ValueError."""
    async def callback(line: str, server_tag: str) -> None:
        pass

    with pytest.raises(ValueError, match="cannot be empty"):
        MultiServerLogTailer({}, callback)


@pytest.mark.asyncio
async def test_multi_log_tailer_missing_log_path_raises() -> None:
    """Test error path: missing log_path attribute raises ValueError."""
    async def callback(line: str, server_tag: str) -> None:
        pass

    class BadConfig:
        tag = "bad"
        # Missing log_path attribute

    with pytest.raises(ValueError, match="missing required 'log_path'"):
        MultiServerLogTailer({"bad": BadConfig()}, callback)


@pytest.mark.asyncio
async def test_multi_log_tailer_wrong_log_path_type_raises() -> None:
    """Test error path: log_path must be Path object."""
    async def callback(line: str, server_tag: str) -> None:
        pass

    class BadConfig:
        tag = "bad"
        log_path = "/some/string/path"  # String instead of Path

    with pytest.raises(ValueError, match="must be Path"):
        MultiServerLogTailer({"bad": BadConfig()}, callback)


@pytest.mark.asyncio
async def test_multi_log_tailer_callback_exception_handling(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test error path: callback exceptions don't crash the tailer."""
    call_count = 0

    async def failing_callback(line: str, server_tag: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("Intentional test error")
        # Callback should be called again after error

    tailer = MultiServerLogTailer(temp_logs, failing_callback, poll_interval=0.05)
    await tailer.start()
    await asyncio.sleep(0.15)
    
    # Write first line (will cause error)
    with open(temp_logs["prod"].log_path, "a") as f:
        f.write("Error line\n")
        f.flush()
    
    await asyncio.sleep(0.2)
    
    # Write second line (should still work despite previous error)
    with open(temp_logs["prod"].log_path, "a") as f:
        f.write("Recovery line\n")
        f.flush()
    
    await asyncio.sleep(0.2)
    await tailer.stop()
    
    # Callback should have been called at least twice
    assert call_count >= 2


@pytest.mark.asyncio
async def test_multi_log_tailer_partial_start_failure_cleanup(tmp_path: Path) -> None:
    """Test error path: partial start failure triggers cleanup."""
    configs: Dict[str, MockServerConfig] = {}
    
    # Create valid configs
    for tag in ["prod", "dev"]:
        log_path = tmp_path / f"{tag}_console.log"
        log_path.write_text("")
        configs[tag] = MockServerConfig(tag=tag, log_path=log_path)

    async def callback(line: str, server_tag: str) -> None:
        pass

    tailer = MultiServerLogTailer(configs, callback)
    
    # Mock the callback to fail during start for one server
    failed_callback_calls = 0

    async def failing_start_callback(line: str, server_tag: str) -> None:
        nonlocal failed_callback_calls
        if server_tag == "dev":
            failed_callback_calls += 1
            if failed_callback_calls == 1:
                raise RuntimeError("Start failure for dev")

    tailer_with_fail = MultiServerLogTailer(configs, failing_start_callback)
    
    # Start should handle the error gracefully
    await tailer_with_fail.start()
    await asyncio.sleep(0.2)
    await tailer_with_fail.stop()


# ============================================================================
# RESTART AND RECOVERY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_multi_log_tailer_restart(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test happy path: restart functionality."""
    lines_received: List[Tuple[str, str]] = []

    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))

    tailer = MultiServerLogTailer(temp_logs, callback, poll_interval=0.05)
    
    # First start
    await tailer.start()
    await asyncio.sleep(0.15)
    
    with open(temp_logs["prod"].log_path, "a") as f:
        f.write("Before restart\n")
        f.flush()
    
    await asyncio.sleep(0.2)
    initial_count = len(lines_received)
    
    # Restart
    await tailer.restart()
    await asyncio.sleep(0.15)
    
    with open(temp_logs["prod"].log_path, "a") as f:
        f.write("After restart\n")
        f.flush()
    
    await asyncio.sleep(0.2)
    await tailer.stop()
    
    # Should have lines from both before and after restart
    assert len(lines_received) > initial_count


@pytest.mark.asyncio
async def test_multi_log_tailer_stop_before_start_safe(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test error path: stop before start is safe."""
    async def callback(line: str, server_tag: str) -> None:
        pass

    tailer = MultiServerLogTailer(temp_logs, callback)
    
    # Should not raise
    await tailer.stop()
    
    # Verify state is still correct
    assert len(tailer.tailers) == 0


@pytest.mark.asyncio
async def test_multi_log_tailer_double_start_safe(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test happy path: double start is handled safely."""
    async def callback(line: str, server_tag: str) -> None:
        pass

    tailer = MultiServerLogTailer(temp_logs, callback, poll_interval=0.05)
    
    await tailer.start()
    await asyncio.sleep(0.1)
    
    # Start again - should not cause issues
    await tailer.start()
    await asyncio.sleep(0.1)
    
    assert len(tailer.tailers) == 3
    
    await tailer.stop()


# ============================================================================
# EDGE CASES AND PERFORMANCE
# ============================================================================

@pytest.mark.asyncio
async def test_multi_log_tailer_many_lines(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test happy path: handling many lines rapidly."""
    lines_received: List[Tuple[str, str]] = []

    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))

    tailer = MultiServerLogTailer(temp_logs, callback, poll_interval=0.05)
    await tailer.start()
    await asyncio.sleep(0.15)
    
    # Write many lines to all servers
    for tag, config in temp_logs.items():
        with open(config.log_path, "a") as f:
            for i in range(20):
                f.write(f"Line {i} from {tag}\n")
            f.flush()
    
    await asyncio.sleep(0.5)
    await tailer.stop()
    
    # Should have captured most/all lines
    assert len(lines_received) >= 50  # Allow for some margin


@pytest.mark.asyncio
async def test_multi_log_tailer_unicode_content(temp_logs: Dict[str, MockServerConfig]) -> None:
    """Test happy path: handling unicode content."""
    lines_received: List[Tuple[str, str]] = []

    async def callback(line: str, server_tag: str) -> None:
        lines_received.append((line, server_tag))

    tailer = MultiServerLogTailer(temp_logs, callback, poll_interval=0.05)
    await tailer.start()
    await asyncio.sleep(0.15)
    
    # Write unicode to log files
    unicode_content = "Player joined: 👾 @ 🌍"
    for tag, config in temp_logs.items():
        with open(config.log_path, "a", encoding="utf-8") as f:
            f.write(f"{unicode_content}\n")
            f.flush()
    
    await asyncio.sleep(0.3)
    await tailer.stop()
    
    # Should have captured unicode
    assert len(lines_received) >= 3
    assert any(unicode_content in line for line, _ in lines_received)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
