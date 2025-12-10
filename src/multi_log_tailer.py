"""Multi-server log tailer managing multiple per-server LogTailer instances.

Coordinates log tailing across multiple Factorio servers, routing each log line
with server context to a unified callback. Simplifies Application orchestration.
"""

import asyncio
from typing import Callable, Dict, Optional, Any
from pathlib import Path
import structlog

try:
    from log_tailer import LogTailer
except ImportError:
    from .log_tailer import LogTailer

logger = structlog.get_logger()


class MultiServerLogTailer:
    """Manage LogTailer instances for multiple Factorio servers.
    
    Internally creates one LogTailer per server. Routes each log line
    with server metadata (server_tag) to a unified callback.
    
    Example:
        servers_config = {
            'prod': ServerConfig(name='Production', log_path=Path('/logs/prod/console.log'), ...),
            'dev': ServerConfig(name='Development', log_path=Path('/logs/dev/console.log'), ...),
        }
        
        async def on_line(line: str, server_tag: str) -> None:
            print(f"[{server_tag}] {line}")
        
        multi_tailer = MultiServerLogTailer(servers_config, on_line)
        await multi_tailer.start()
        await multi_tailer.stop()
    """

    def __init__(
        self,
        server_configs: Dict[str, Any],
        line_callback: Callable[[str, str], Any],
        poll_interval: float = 0.1,
    ) -> None:
        """Initialize multi-server log tailer.
        
        Args:
            server_configs: Dictionary mapping server tag to ServerConfig instance.
                          ServerConfig must have .log_path attribute (Path).
            line_callback: Async or sync callable invoked as callback(line, server_tag).
            poll_interval: Polling interval for log tailing (default 0.1s).
        
        Raises:
            ValueError: If server_configs is empty or log_path missing from any config.
        """
        if not server_configs:
            raise ValueError("server_configs cannot be empty")

        self.server_configs = server_configs
        self.line_callback = line_callback
        self.poll_interval = poll_interval
        self.tailers: Dict[str, LogTailer] = {}

        # Validate all servers have log_path
        for tag, config in server_configs.items():
            if not hasattr(config, "log_path"):
                raise ValueError(
                    f"Server '{tag}' config missing required 'log_path' attribute"
                )
            if not isinstance(config.log_path, Path):
                raise ValueError(
                    f"Server '{tag}' log_path must be Path, got {type(config.log_path)}"
                )

        logger.info(
            "multi_server_log_tailer_initialized",
            server_count=len(server_configs),
            servers=list(server_configs.keys()),
        )

    async def start(self) -> None:
        """Start all per-server LogTailers concurrently.
        
        Creates one LogTailer per server with a bound callback that includes
        the server tag. Raises on first failure.
        """
        logger.info("starting_multi_server_log_tailers", count=len(self.server_configs))

        create_tasks = []
        for tag, config in self.server_configs.items():
            log_path = config.log_path

            # Create bound callback with server tag captured via default argument
            async def bound_callback(line: str, t: str = tag) -> None:
                try:
                    # Support both async and sync callbacks
                    result = self.line_callback(line, t)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(
                        "callback_error",
                        server_tag=t,
                        line=line[:100],
                        error=str(e),
                        exc_info=True,
                    )

            tailer = LogTailer(log_path, bound_callback, poll_interval=self.poll_interval)
            self.tailers[tag] = tailer
            create_tasks.append(tailer.start())

        # Start all tailers concurrently
        try:
            await asyncio.gather(*create_tasks)
            logger.info("all_multi_server_log_tailers_started")
        except Exception as e:
            logger.error(
                "failed_to_start_log_tailers",
                error=str(e),
                exc_info=True,
            )
            # Clean up any partially started tailers
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop all per-server LogTailers concurrently.
        
        Calls stop() on all tailers in parallel. Logs errors but does not raise.
        """
        logger.info("stopping_multi_server_log_tailers", count=len(self.tailers))

        stop_tasks = [tailer.stop() for tailer in self.tailers.values()]
        results = await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Log any errors
        for (tag, tailer), result in zip(self.tailers.items(), results):
            if isinstance(result, Exception):
                logger.error(
                    "error_stopping_tailer",
                    server_tag=tag,
                    error=str(result),
                    exc_info=True,
                )

        logger.info("all_multi_server_log_tailers_stopped")

    async def restart(self) -> None:
        """Restart all log tailers (stop and start).
        
        Useful for recovery after connection loss or log rotation issues.
        """
        logger.info("restarting_multi_server_log_tailers")
        await self.stop()
        await asyncio.sleep(0.5)  # Brief pause before restart
        await self.start()

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all tailers.
        
        Returns:
            Dictionary mapping server_tag to status dict.
        """
        return {
            tag: {
                "log_path": str(self.server_configs[tag].log_path),
                "started": tag in self.tailers,
            }
            for tag in self.server_configs.keys()
        }
