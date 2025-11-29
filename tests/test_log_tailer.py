"""Test the log tailer functionality."""
import asyncio
import tempfile
from pathlib import Path
import sys

import pytest  # Add this import

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from log_tailer import LogTailer


@pytest.mark.asyncio  # Add this decorator
async def test_basic_tailing():
    """Test basic log tailing functionality."""
    lines_received = []
    
    async def callback(line: str):
        print(f"Received: {line}")
        lines_received.append(line)
    
    # Create a temporary log file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        log_path = Path(f.name)
        f.write("Initial line\n")
        f.flush()
    
    try:
        # Start tailer
        tailer = LogTailer(log_path, callback, poll_interval=0.05)
        await tailer.start()
        
        # Give it time to open the file
        await asyncio.sleep(0.2)
        
        # Append new lines
        with open(log_path, 'a') as f:
            f.write("Test line 1\n")
            f.flush()
        
        await asyncio.sleep(0.2)
        
        with open(log_path, 'a') as f:
            f.write("Test line 2\n")
            f.write("Test line 3\n")
            f.flush()
        
        await asyncio.sleep(0.2)
        
        # Stop tailer
        await tailer.stop()
        
        # Verify
        print(f"\nLines received: {lines_received}")
        assert "Test line 1" in lines_received
        assert "Test line 2" in lines_received
        assert "Test line 3" in lines_received
        assert "Initial line" not in lines_received
        
        print("✓ Basic tailing test passed!")
        
    finally:
        log_path.unlink()


# Keep this for direct execution
if __name__ == "__main__":
    asyncio.run(test_basic_tailing())
