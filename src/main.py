"""
Factorio ISR - Main Entry Point

Near Real-time Factorio server event monitoring with Discord integration.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
import structlog

# Use try/except to support both relative and absolute imports
try:
    # Relative imports (when run as module: python -m src.main)
    from .config import load_config, validate_config
    from .health import HealthCheckServer
    from .log_tailer import LogTailer
    from .discord_client import DiscordClient
    from .event_parser import EventParser
except ImportError:
    # Absolute imports (when run directly or from tests)
    from config import load_config, validate_config
    from health import HealthCheckServer
    from log_tailer import LogTailer
    from discord_client import DiscordClient
    from event_parser import EventParser

logger = structlog.get_logger()


def setup_logging(log_level: str, log_format: str) -> None:
    """
    Configure structured logging.
    
    Args:
        log_level: Logging level (debug, info, warning, error, critical)
        log_format: Output format (json or console)
    """
    # Map string level to standard logging level
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    
    # Get log level with guaranteed fallback
    min_level = level_map.get(log_level.lower(), logging.INFO)
    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    # Choose renderer based on format
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logger.info(
        "logging_configured",
        level=log_level,
        format=log_format
    )


class Application:
    """Main application orchestrator."""
    
    def __init__(self):
        """Initialize application components."""
        self.config = None
        self.health_server = None
        self.log_tailer = None
        self.discord_client = None
        self.event_parser = None
        self.shutdown_event = asyncio.Event()
    
    async def setup(self) -> None:
        """Load configuration and initialize components."""
        logger.info("application_starting")
        
        # Load and validate configuration
        try:
            self.config = load_config()
            assert self.config is not None, "Config loading returned None"
            
            if not validate_config(self.config):
                raise ValueError("Configuration validation failed")
        except Exception as e:
            logger.error("config_load_failed", error=str(e))
            raise
        
        # Assert config is loaded
        assert self.config is not None
        
        # Set up logging with loaded config
        setup_logging(self.config.log_level, self.config.log_format)
        
        # Verify log file exists
        if not self.config.factorio_log_path.exists():
            logger.warning(
                "log_file_not_found",
                path=str(self.config.factorio_log_path),
                message="Will wait for file to be created"
            )
        
        # Initialize health check server
        self.health_server = HealthCheckServer(
            host=self.config.health_check_host,
            port=self.config.health_check_port
        )
        
        # Assert health server was created
        assert self.health_server is not None
        
        logger.info(
            "application_configured",
            health_port=self.config.health_check_port,
            log_path=str(self.config.factorio_log_path)
        )
    
    async def start(self) -> None:
        """Start all application components."""
        logger.info("application_starting_components")
        
        # Assert components are initialized after setup()
        assert self.health_server is not None, "Health server not initialized"
        assert self.config is not None, "Config not loaded"
        
        # Start health check server
        await self.health_server.start()
        logger.info(
            "health_server_started",
            url=f"http://{self.config.health_check_host}:{self.config.health_check_port}/health"
        )
        
        # Initialize Discord client
        self.discord_client = DiscordClient(
            webhook_url=self.config.discord_webhook_url,
            bot_name=self.config.bot_name,
            bot_avatar_url=self.config.bot_avatar_url,
        )
        
        # Assert Discord client was created
        assert self.discord_client is not None
        
        await self.discord_client.connect()
        
        # Test Discord connection
        if not await self.discord_client.test_connection():
            logger.error("discord_connection_failed")
            raise ConnectionError("Failed to connect to Discord webhook")
        
        # Initialize event parser
        self.event_parser = EventParser()
        
        # Assert event parser was created
        assert self.event_parser is not None
        
        # Start log tailer
        self.log_tailer = LogTailer(
            log_path=self.config.factorio_log_path,
            line_callback=self.handle_log_line,
        )
        
        # Assert log tailer was created
        assert self.log_tailer is not None
        
        await self.log_tailer.start()
        
        logger.info("application_running")
    
    async def handle_log_line(self, line: str) -> None:
        """
        Process a log line from Factorio.
        
        Args:
            line: Raw log line from console.log
        """
        # Assert parser and client are initialized
        assert self.event_parser is not None, "Event parser not initialized"
        assert self.discord_client is not None, "Discord client not initialized"
        
        # Parse the line
        event = self.event_parser.parse(line)
        
        # If we got an event, send it to Discord
        if event is not None:
            success = await self.discord_client.send_event(event)
            if not success:
                logger.warning(
                    "failed_to_send_event",
                    event_type=event.event_type.value,
                    player=event.player_name
                )
    
    async def stop(self) -> None:
        """Gracefully stop all components."""
        logger.info("application_stopping")
        
        # Stop log tailer
        if self.log_tailer is not None:
            await self.log_tailer.stop()
            logger.debug("log_tailer_stopped")
        
        # Disconnect Discord client
        if self.discord_client is not None:
            await self.discord_client.disconnect()
            logger.debug("discord_client_disconnected")
        
        # Stop health server
        if self.health_server is not None:
            await self.health_server.stop()
            logger.debug("health_server_stopped")
        
        logger.info("application_stopped")
    
    async def run(self) -> None:
        """Main application run loop."""
        try:
            await self.setup()
            await self.start()
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except KeyboardInterrupt:
            logger.info("received_keyboard_interrupt")
        except Exception as e:
            logger.error("application_error", error=str(e), exc_info=True)
            raise
        finally:
            await self.stop()


async def main() -> None:
    """Application entry point."""
    app = Application()
    
    # Assert app was created
    assert app is not None
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("received_signal", signal=signal.Signals(signum).name)
        app.shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await app.run()
    except Exception as e:
        logger.error("fatal_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
        sys.exit(0)
