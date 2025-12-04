"""
Factorio ISR - Main Entry Point

Real-time Factorio server event monitoring with Discord integration.

Phase 2: Multi-channel routing support.
Phase 3: Optional RCON support for server statistics.
Phase 4: Discord bot mode with slash commands.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Any
import structlog

# Import helpers with support for package vs. flat layout
try:
    # Package-style imports (python -m src.main)
    from .config import load_config, validate_config  # type: ignore
    from .health import HealthCheckServer  # type: ignore
    from .log_tailer import LogTailer  # type: ignore
    from .discord_client import DiscordClient  # type: ignore
    from .discord_interface import DiscordInterfaceFactory, DiscordInterface  # type: ignore
    from .event_parser import EventParser  # type: ignore
except ImportError:
    # Flat layout (tests and direct execution)
    from config import load_config, validate_config  # type: ignore
    from health import HealthCheckServer  # type: ignore
    from log_tailer import LogTailer  # type: ignore
    from discord_client import DiscordClient  # type: ignore
    from discord_interface import DiscordInterfaceFactory, DiscordInterface  # type: ignore
    from event_parser import EventParser  # type: ignore

# Optional RCON (Phase 3)
try:
    from .rcon_client import RconClient, RconStatsCollector  # type: ignore
    RCON_AVAILABLE = True
except ImportError:
    try:
        from rcon_client import RconClient, RconStatsCollector  # type: ignore
        RCON_AVAILABLE = True
    except ImportError:
        RconClient = None  # type: ignore
        RconStatsCollector = None  # type: ignore
        RCON_AVAILABLE = False

logger = structlog.get_logger()


def setup_logging(log_level: str, log_format: str) -> None:
    """
    Configure structured logging.

    Args:
        log_level: Logging level (debug, info, warning, error, critical)
        log_format: Output format ("json" or "console")
    """
    level_map: dict[str, int] = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    min_level = level_map.get(log_level.lower(), logging.INFO)
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

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

    logger.info("logging_configured", level=log_level, format=log_format)


class Application:
    """Main application orchestrator with Discord bot/webhook support."""

    def __init__(self) -> None:
        """Initialize application components."""
        self.config: Any = None
        self.health_server: Optional[HealthCheckServer] = None
        self.log_tailer: Optional[LogTailer] = None
        self.discord: Optional[DiscordInterface] = None  # ✅ Unified interface
        self.event_parser: Optional[EventParser] = None
        self.rcon_client: Optional[Any] = None  # Optional[RconClient]
        self.stats_collector: Optional[Any] = None  # Optional[RconStatsCollector]
        self.shutdown_event: asyncio.Event = asyncio.Event()

    async def setup(self) -> None:
        """Load configuration and initialize core components."""
        logger.info("application_starting")

        # Load and validate configuration
        try:
            self.config = load_config()
            assert self.config is not None, "Config loading returned None"

            if not validate_config(self.config):
                raise ValueError("Configuration validation failed")
        except Exception as e:
            logger.error("config_load_failed", error=str(e))
            # Re-raise so tests can assert failure behavior
            raise

        assert self.config is not None

        # Configure logging
        setup_logging(self.config.log_level, self.config.log_format)

        # Warn if log file does not yet exist
        if not self.config.factorio_log_path.exists():
            logger.warning(
                "log_file_not_found",
                path=str(self.config.factorio_log_path),
                message="Will wait for file to be created",
            )

        # Initialize EventParser
        self.event_parser = EventParser(
            patterns_dir=self.config.patterns_dir,
            pattern_files=self.config.pattern_files,
        )

        logger.info(
            "event_parser_initialized",
            patterns_dir=str(self.config.patterns_dir),
            pattern_count=len(self.event_parser.compiled_patterns),
        )

        # Health check server
        self.health_server = HealthCheckServer(
            host=self.config.health_check_host,
            port=self.config.health_check_port,
        )

        assert self.health_server is not None

        logger.info(
            "application_configured",
            health_port=self.config.health_check_port,
            log_path=str(self.config.factorio_log_path),
        )

    async def start(self) -> None:
        """Start all application components."""
        logger.info("application_starting_components")
        
        assert self.config is not None, "Config not loaded"
        assert self.health_server is not None, "Health server not initialized"

        # Start health server
        await self.health_server.start()
        logger.info(
            "health_server_started",
            url=f"http://{self.config.health_check_host}:{self.config.health_check_port}/health",
        )

        # ✅ Initialize Discord interface (webhook or bot mode)
        self.discord = DiscordInterfaceFactory.create_interface(self.config)
        assert self.discord is not None

        await self.discord.connect()

        # Optional: Test connection (skip for production to avoid test messages)
        if getattr(self.config, "send_test_message", False):
            if not await self.discord.test_connection():
                logger.error("discord_connection_test_failed")
                raise ConnectionError("Failed to connect to Discord")
        else:
            logger.info("discord_connected", test_skipped=True)

        # Event parser must exist from setup
        assert self.event_parser is not None

        # RCON (optional Phase 3)
        if getattr(self.config, "rcon_enabled", False):
            if RCON_AVAILABLE:
                await self._start_rcon()
            else:
                logger.warning(
                    "rcon_unavailable",
                    message=(
                        "RCON enabled but module not available. "
                        "Install with: pip install aiorcon"
                    ),
                )
        else:
            logger.info("rcon_disabled")

        # Log tailer
        self.log_tailer = LogTailer(
            log_path=self.config.factorio_log_path,
            line_callback=self.handle_log_line,
        )

        assert self.log_tailer is not None
        await self.log_tailer.start()

        logger.info("application_running")

    async def _start_rcon(self) -> None:
        """Start RCON client and stats collector (optional Phase 3)."""
        assert self.config is not None
        assert self.discord is not None

        if not RCON_AVAILABLE or RconClient is None or RconStatsCollector is None:
            logger.error("rcon_not_available", message="RCON module not imported")
            return

        if not getattr(self.config, "rcon_password", None):
            logger.warning("rcon_enabled_but_no_password")
            return

        try:
            # Client
            self.rcon_client = RconClient(
                host=self.config.rcon_host,
                port=self.config.rcon_port,
                password=self.config.rcon_password,
            )

            assert self.rcon_client is not None
            await self.rcon_client.start()

            # Pass RCON client to bot for slash commands (Phase 4)
            # Use try/except for import to handle both package and flat layouts
            try:
                from .discord_interface import BotDiscordInterface
            except ImportError:
                from discord_interface import BotDiscordInterface  # type: ignore
            
            if isinstance(self.discord, BotDiscordInterface):
                self.discord.bot.set_rcon_client(self.rcon_client)
                logger.info("rcon_client_passed_to_bot")

            # Stats - pass the unified discord interface
            self.stats_collector = RconStatsCollector(
                rcon_client=self.rcon_client,
                discord_client=self.discord,
                interval=self.config.stats_interval,
            )

            assert self.stats_collector is not None
            await self.stats_collector.start()

            logger.info(
                "rcon_started",
                host=self.config.rcon_host,
                port=self.config.rcon_port,
                stats_interval=self.config.stats_interval,
            )

        except Exception as e:
            logger.error("rcon_start_failed", error=str(e), exc_info=True)
            # RCON is optional, do not re-raise




    async def handle_log_line(self, line: str) -> None:
        """
        Process a log line from Factorio.

        Args:
            line: Raw log line from console.log
        """
        # Allow tests to call handle_log_line with missing dependencies without crashing
        if self.event_parser is None:
            logger.warning("handle_log_line_no_parser")
            return

        if self.discord is None:
            logger.warning("handle_log_line_no_discord")
            return

        event = self.event_parser.parse_line(line)
        if event is None:
            return

        success = await self.discord.send_event(event)
        if not success:
            logger.warning(
                "failed_to_send_event",
                event_type=event.event_type.value,
                player=event.player_name,
            )

    async def stop(self) -> None:
        """Gracefully stop all components."""
        logger.info("application_stopping")

        # Stats collector
        if self.stats_collector is not None:
            try:
                await self.stats_collector.stop()
            except Exception:
                pass
            logger.debug("stats_collector_stopped")

        # RCON client
        if self.rcon_client is not None:
            try:
                await self.rcon_client.stop()
            except Exception:
                pass
            logger.debug("rcon_disconnected")

        # Log tailer
        if self.log_tailer is not None:
            try:
                await self.log_tailer.stop()
            except Exception:
                pass
            logger.debug("log_tailer_stopped")

        # ✅ Discord interface (unified for both webhook and bot)
        if self.discord is not None:
            try:
                await self.discord.disconnect()
            except Exception:
                pass
            logger.debug("discord_disconnected")

        # Health server
        if self.health_server is not None:
            try:
                await self.health_server.stop()
            except Exception:
                pass
            logger.debug("health_server_stopped")

        logger.info("application_stopped")

    async def run(self) -> None:
        """Main application run loop."""
        try:
            await self.setup()
            await self.start()
            await self.shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("received_keyboard_interrupt")
        except Exception as e:
            logger.error("application_error", error=str(e), exc_info=True)
            raise
        finally:
            await self.stop()


async def main() -> None:
    """Main async entry point."""
    app = Application()
    assert app is not None

    # Signal handlers for graceful shutdown
    def _signal_handler(signum: int, frame: Any) -> None:
        logger.info("received_signal", signal=signal.Signals(signum).name)
        app.shutdown_event.set()

    # Only register signals on real OS (not always available on Windows/threads)
    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        pass

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
