# Copyright (c) 2025 Stephen Clau

# This file is part of Factorio ISR.

# Factorio ISR is dual-licensed:

# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for full terms

# 2. Commercial License
# For proprietary use without AGPL requirements
# Contact: licensing@laudiversified.com

# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""
Factorio ISR - Main Entry Point

Real-time Factorio server event monitoring with Discord integration.

Phase 6: Multi-server architecture with ServerManager (REQUIRED).
- servers.yml configuration is MANDATORY
- All servers managed via ServerManager
- Per-server RCON clients with context
- Unified Discord interface for all servers
- MultiServerLogTailer for concurrent log monitoring
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Any, Union

try:
    from multi_log_tailer import MultiServerLogTailer
except ImportError:
    from .multi_log_tailer import MultiServerLogTailer

import structlog

# Import helpers with support for package vs. flat layout
try:
    # Package-style imports (python -m src.main)
    from .config import load_config, validate_config  # type: ignore
    from .health import HealthCheckServer  # type: ignore
    from .discord_interface import DiscordInterfaceFactory, DiscordInterface  # type: ignore
    from .event_parser import EventParser  # type: ignore
except ImportError:
    # Flat layout (tests and direct execution)
    from config import load_config, validate_config  # type: ignore
    from health import HealthCheckServer  # type: ignore
    from discord_interface import DiscordInterfaceFactory, DiscordInterface  # type: ignore
    from event_parser import EventParser  # type: ignore

# Phase 6: ServerManager (REQUIRED for multi-server support)
try:
    from .server_manager import ServerManager  # type: ignore
    from .config import ServerConfig  # type: ignore
    SERVER_MANAGER_AVAILABLE = True
except ImportError:
    try:
        from server_manager import ServerManager  # type: ignore
        from config import ServerConfig  # type: ignore
        SERVER_MANAGER_AVAILABLE = True
    except ImportError:
        ServerManager = None  # type: ignore
        ServerConfig = None  # type: ignore
        SERVER_MANAGER_AVAILABLE = False

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
    """Main application orchestrator with multi-server support via ServerManager."""

    def __init__(self) -> None:
        """Initialize application components."""
        self.config: Any = None
        self.health_server: Optional[HealthCheckServer] = None
        self.logtailer: Optional[Union[MultiServerLogTailer, Any]] = None
        self.discord: Optional[DiscordInterface] = None
        self.event_parser: Optional[EventParser] = None
        self.server_manager: Optional[Any] = None
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
            raise

        assert self.config is not None

        # Configure logging
        setup_logging(self.config.log_level, self.config.log_format)

        # Warn if log files do not exist yet
        if self.config.servers:
            for tag, server_config in self.config.servers.items():
                if not server_config.log_path.exists():
                    logger.warning(
                        "server_log_file_not_found",
                        server_tag=tag,
                        path=str(server_config.log_path),
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
            servers_count=len(self.config.servers) if self.config.servers else 0,
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
            url=f"http://{self.config.health_check_host}:"
            f"{self.config.health_check_port}/health",
        )

        # Initialize Discord interface (bot mode only)
        self.discord = DiscordInterfaceFactory.create_interface(self.config)
        assert self.discord is not None

        await self.discord.connect()

        # Optional: Test connection (skip for production to avoid test messages)
        if getattr(self.config, "send_test_message", False):
            if not await self.discord.test_connection():
                logger.error("discord_connection_test_failed")
                raise ConnectionError("Failed to connect to Discord")
            else:
                logger.info("discord_connected", test_passed=True)
        else:
            logger.info("discord_connected", test_skipped=True)

        # Event parser must exist from setup
        assert self.event_parser is not None

        # Servers config is REQUIRED (no legacy fallback)
        if not self.config.servers:
            logger.error(
                "servers_configuration_required",
                message=(
                    "config/servers.yml configuration is REQUIRED. "
                    "Multi-server mode is the only supported architecture. "
                    "Create a config/servers.yml file with at least one server."
                ),
            )
            raise ValueError(
                "servers.yml configuration required - multi-server mode is mandatory"
            )

        # Start multi-server mode (wires Discord bot + per-server RCON + stats)
        await self._start_multi_server_mode()

        # Start multi-server log tailer
        self.logtailer = MultiServerLogTailer(
            server_configs=self.config.servers,
            line_callback=self.handle_log_line,
            poll_interval=0.1,
        )

        logger.info(
            "starting_multi_server_log_tailer",
            count=len(self.config.servers),
            servers=list(self.config.servers.keys()),
        )

        await self.logtailer.start()

        logger.info("application_running")

    async def _start_multi_server_mode(self) -> None:
        """Initialize ServerManager and add all configured servers."""
        assert self.config is not None
        assert self.discord is not None

        if not SERVER_MANAGER_AVAILABLE or ServerManager is None:
            logger.error(
                "server_manager_unavailable",
                message="ServerManager module not available. Check imports.",
            )
            raise ImportError("ServerManager not available")

        # Validate bot mode (ServerManager requires bot for commands)
        if not getattr(self.config, "discord_bot_token", None):
            logger.error(
                "bot_mode_required_for_multi_server",
                message="Multi-server mode requires Discord bot mode (DISCORD_BOT_TOKEN)",
            )
            raise ValueError("Bot mode required for multi-server support")

        # Get the bot instance from the interface
        try:
            from .discord_interface import BotDiscordInterface
        except ImportError:
            from discord_interface import BotDiscordInterface  # type: ignore

        if not isinstance(self.discord, BotDiscordInterface):
            logger.error(
                "bot_interface_required",
                message="Multi-server mode requires BotDiscordInterface",
            )
            raise TypeError("Bot interface required")

        bot = self.discord.bot

        # Create ServerManager
        self.server_manager = ServerManager(discord_interface=self.discord)

        logger.info("server_manager_created")

        # Add all servers from config
        if not self.config.servers:
            logger.error(
                "no_servers_configured",
                message="config/servers.yml has no servers defined",
            )
            raise ValueError("No servers configured in config/servers.yml")

        added_servers: list[str] = []
        failed_servers: list[str] = []

        for tag, server_config in self.config.servers.items():
            try:
                await self.server_manager.add_server(server_config)
                added_servers.append(f"{tag} ({server_config.name})")

                logger.info(
                    "server_added_to_manager",
                    tag=tag,
                    name=server_config.name,
                    host=server_config.rcon_host,
                    port=server_config.rcon_port,
                )

            except Exception as e:
                failed_servers.append(f"{tag}: {str(e)}")
                logger.error(
                    "failed_to_add_server_to_manager",
                    tag=tag,
                    name=server_config.name,
                    error=str(e),
                    exc_info=True,
                )

        # Wire ServerManager to bot so commands and presence can reach it
        bot.set_server_manager(self.server_manager)

        logger.info("server_manager_wired_to_bot")

        # Apply per-server breakdown configuration to the bot
        bot._apply_server_breakdown_config()

        logger.info("server_breakdown_config_applied_to_bot")

        # Report summary
        logger.info(
            "multi_server_mode_initialized",
            total_configured=len(self.config.servers),
            added=len(added_servers),
            failed=len(failed_servers),
            added_servers=added_servers,
            failed_servers=failed_servers if failed_servers else None,
        )

        if not added_servers:
            raise ConnectionError("Failed to add any servers to ServerManager")

    async def handle_log_line(self, line: str, server_tag: str) -> None:
        """
        Process a log line from Factorio.

        Args:
            line: Raw log line from console.log
            server_tag: Which server this line came from (always present, never synthetic)
        """
        if self.event_parser is None:
            logger.warning("handle_log_line_no_parser")
            return

        if self.discord is None:
            logger.warning("handle_log_line_no_discord")
            return

        logger.debug(
            "processing_log_line", line=line[:100], server_tag=server_tag
        )

        assert self.event_parser is not None, "Event parser not initialized"
        assert self.discord is not None, "Discord client not initialized"

        # Parse the line using EventParser with server_tag parameter
        event = self.event_parser.parse_line(line, server_tag=server_tag)

        if event is not None:
            # Send event to Discord
            success = await self.discord.send_event(event)

            if not success:
                logger.warning(
                    "failed_to_send_event",
                    server_tag=server_tag,
                    event_type=event.event_type.value,
                    player=event.player_name,
                )

    async def stop(self) -> None:
        """Gracefully stop all components."""
        logger.info("application_stopping")

        # ServerManager (stops all RCON clients and stats collectors)
        if self.server_manager is not None:
            try:
                await self.server_manager.stop_all()
            except Exception as e:
                logger.error("server_manager_stop_failed", error=str(e))

            logger.debug("server_manager_stopped")

        # Log tailer
        if self.logtailer is not None:
            try:
                await self.logtailer.stop()
            except Exception:
                pass

            logger.debug("log_tailer_stopped")

        # Discord interface
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

    async def main(self) -> None:  # type: ignore[override]
        """Unused; kept for backward compatibility."""
        await self.run()


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
