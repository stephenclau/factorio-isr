"""
Log file tailer for real-time monitoring.

Watches Factorio console.log and emits new lines as they appear.
"""
import asyncio
from pathlib import Path
from typing import Callable, Optional, Awaitable

import structlog

logger = structlog.get_logger()


class LogTailer:
    """
    Asynchronous file tailer that monitors a log file for new content.
    
    Handles file rotation, creation delays, and graceful shutdown.
    """
    
    def __init__(
        self,
        log_path: Path,
        line_callback: Callable[[str], Awaitable[None]],
        poll_interval: float = 0.1
    ):
        """
        Initialize log tailer.
        
        Args:
            log_path: Path to the log file to monitor
            line_callback: Async function to call with each new line
            poll_interval: How often to check for new content (seconds)
        """
        self.log_path = log_path
        self.line_callback = line_callback
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._file = None
        self._inode: Optional[int] = None
    
    async def start(self) -> None:
        """Start tailing the log file."""
        if self._running:
            logger.warning("log_tailer_already_running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._tail_loop())
        logger.info("log_tailer_started", path=str(self.log_path))
    
    async def stop(self) -> None:
        """Stop tailing the log file."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._file is not None:
            self._file.close()
            self._file = None
        
        logger.info("log_tailer_stopped")
    
    async def _wait_for_file(self) -> None:
        """Wait for log file to exist."""
        while self._running and not self.log_path.exists():
            logger.debug(
                "waiting_for_log_file",
                path=str(self.log_path),
                check_interval=self.poll_interval
            )
            await asyncio.sleep(self.poll_interval)
    
    def _open_file(self) -> None:
        """Open the log file and seek to end."""
        if self._file is not None:
            self._file.close()
        
        self._file = open(self.log_path, 'r', encoding='utf-8', errors='replace')
        
        # Assert file was opened successfully
        assert self._file is not None
        
        # Get file inode for rotation detection
        stat = self.log_path.stat()
        self._inode = stat.st_ino
        
        # Seek to end (only tail new content)
        self._file.seek(0, 2)
        
        logger.info(
            "log_file_opened",
            path=str(self.log_path),
            inode=self._inode,
            size=stat.st_size
        )
    
    def _check_rotation(self) -> bool:
        """
        Check if file has been rotated.
        
        Returns:
            True if rotation detected, False otherwise
        """
        if not self.log_path.exists():
            return True
        
        try:
            current_inode = self.log_path.stat().st_ino
            
            # Assert inode was set during _open_file
            assert self._inode is not None
            
            if current_inode != self._inode:
                logger.info(
                    "log_rotation_detected",
                    old_inode=self._inode,
                    new_inode=current_inode
                )
                return True
        except OSError as e:
            logger.warning("stat_failed", path=str(self.log_path), error=str(e))
            return True
        
        return False
    
    async def _tail_loop(self) -> None:
        """Main tailing loop."""
        try:
            # Wait for file to exist
            await self._wait_for_file()
            
            if not self._running:
                return
            
            # Open file
            self._open_file()
            
            # Assert file was opened
            assert self._file is not None
            
            logger.info("log_tailing_active", path=str(self.log_path))
            
            while self._running:
                # Check for file rotation
                if self._check_rotation():
                    logger.info("reopening_log_file")
                    await self._wait_for_file()
                    if self._running:
                        self._open_file()
                
                # Assert file is still valid
                assert self._file is not None
                
                # Read new lines
                line = self._file.readline()
                
                if line:
                    # Got a new line - process it
                    line = line.rstrip('\n\r')
                    if line:  # Skip empty lines
                        try:
                            await self.line_callback(line)
                        except Exception as e:
                            logger.error(
                                "line_callback_failed",
                                line=line[:100],
                                error=str(e),
                                exc_info=True
                            )
                else:
                    # No new content - wait before checking again
                    await asyncio.sleep(self.poll_interval)
        
        except asyncio.CancelledError:
            logger.debug("tail_loop_cancelled")
            raise
        except Exception as e:
            logger.error(
                "tail_loop_error",
                error=str(e),
                exc_info=True
            )
            raise
        finally:
            if self._file is not None:
                self._file.close()
                self._file = None


class LogTailerFactory:
    """Factory for creating log tailers with common configurations."""
    
    @staticmethod
    def create_factorio_tailer(
        log_path: Path,
        line_callback: Callable[[str], Awaitable[None]]
    ) -> LogTailer:
        """
        Create a log tailer configured for Factorio logs.
        
        Args:
            log_path: Path to Factorio console.log
            line_callback: Async function to call with each new line
        
        Returns:
            Configured LogTailer instance
        """
        return LogTailer(
            log_path=log_path,
            line_callback=line_callback,
            poll_interval=0.1  # Check every 100ms
        )
