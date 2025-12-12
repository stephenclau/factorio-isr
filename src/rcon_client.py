# Copyright (c) 2025 Stephen Clau
#
# This file is part of Factorio ISR.
#
# Factorio ISR is dual-licensed:
#
# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
#    See LICENSE file for full terms
#
# 2. Commercial License
#    For proprietary use without AGPL requirements
#    Contact: licensing@laudiversified.com
#
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial


"""
RCON client for Factorio server queries with automatic reconnection.

Handles connection, authentication, and command execution using rcon library.
Includes automatic reconnection with exponential backoff and optional
context helpers for server name/tag.

For metrics collection, stats posting, and alerting, see:
- rcon_metrics_engine.py: RconMetricsEngine
- rcon_stats_collector.py: RconStatsCollector
- rcon_alert_monitor.py: RconAlertMonitor
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, List, Optional

import structlog

# Optional RCON support using rcon library
try:
    from rcon.source import Client as RCONClient

    RCON_AVAILABLE = True
except ImportError:
    RCONClient = None  # type: ignore
    RCON_AVAILABLE = False

logger = structlog.get_logger()


# Backward compatibility: Re-export classes from new modules
try:
    from rcon_metrics_engine import RconMetricsEngine
    from rcon_stats_collector import RconStatsCollector
    from rcon_alert_monitor import RconAlertMonitor
except ImportError:
    try:
        from src.rcon_metrics_engine import RconMetricsEngine  # type: ignore
        from src.rcon_stats_collector import RconStatsCollector  # type: ignore
        from src.rcon_alert_monitor import RconAlertMonitor  # type: ignore
    except ImportError:
        # Graceful degradation if modules not found
        RconMetricsEngine = None  # type: ignore
        RconStatsCollector = None  # type: ignore
        RconAlertMonitor = None  # type: ignore


class UPSCalculator:
    """Helper class to calculate actual UPS from game.tick deltas with pause detection."""

    def __init__(self, pause_time_threshold: float = 5.0) -> None:
        """
        Initialize UPS calculator.

        Args:
            pause_time_threshold: Seconds of 0 tick advancement to confirm pause.
        """
        self.last_tick: Optional[int] = None
        self.last_sample_time: Optional[float] = None
        self.current_ups: Optional[float] = None

        # Pause detection
        self.is_paused: bool = False
        self.last_known_ups: Optional[float] = None
        self.pause_time_threshold = pause_time_threshold

    async def sample_ups(self, rcon_client: "RconClient") -> Optional[float]:
        """
        Calculate UPS by comparing tick delta to real-time delta.

        Detects when server is paused (no tick advancement).

        Returns:
            UPS value, or None if first sample or paused.
        """
        try:
            # Get current tick (silent command)
            response = await rcon_client.execute("/sc rcon.print(game.tick)")
            current_tick = int(response.strip())
            current_time = time.time()

            # Need at least 2 samples to calculate
            if self.last_tick is None or self.last_sample_time is None:
                self.last_tick = current_tick
                self.last_sample_time = current_time
                logger.debug("ups_first_sample_initialized", tick=current_tick)
                return None

            # Calculate deltas
            delta_ticks = current_tick - self.last_tick
            delta_seconds = current_time - self.last_sample_time

            # PAUSE DETECTION: No ticks advanced over significant time
            if delta_ticks == 0 and delta_seconds >= self.pause_time_threshold:
                if not self.is_paused:
                    logger.info(
                        "server_paused_detected",
                        last_tick=current_tick,
                        delta_seconds=delta_seconds,
                    )
                self.is_paused = True
                # Update time even when paused
                self.last_sample_time = current_time
                return None

            # Minimal tick advancement (< 1 second game time over 5+ real seconds)
            # Likely still paused or just recovering
            if delta_ticks < 60 and delta_seconds >= self.pause_time_threshold:
                logger.debug(
                    "minimal_tick_advancement",
                    delta_ticks=delta_ticks,
                    delta_seconds=delta_seconds,
                    likely_paused=True,
                )
                self.is_paused = True
                self.last_tick = current_tick
                self.last_sample_time = current_time
                return None

            # Avoid division by zero or extremely small intervals
            if delta_seconds < 0.1:
                logger.warning("ups_sample_too_fast", delta_seconds=delta_seconds)
                return self.current_ups

            # Normal UPS calculation
            ups = delta_ticks / delta_seconds

            # UNPAUSE DETECTION: Reasonable UPS resumed
            if self.is_paused and ups > 10.0:
                logger.info(
                    "server_unpaused_detected",
                    ups=ups,
                    delta_ticks=delta_ticks,
                    delta_seconds=delta_seconds,
                )
                self.is_paused = False

            # Update state
            self.last_tick = current_tick
            self.last_sample_time = current_time
            self.current_ups = ups
            self.last_known_ups = ups  # Save for display during future pause

            logger.debug(
                "ups_calculated",
                ups=ups,
                delta_ticks=delta_ticks,
                delta_seconds=delta_seconds,
                is_paused=self.is_paused,
            )
            return ups

        except Exception as e:
            logger.warning("ups_calculation_failed", error=str(e))
            return None


class RconClient:
    """Async wrapper for synchronous RCON client with auto-reconnection."""

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        timeout: float = 10.0,
        reconnect_delay: float = 5.0,
        max_reconnect_delay: float = 60.0,
        reconnect_backoff: float = 2.0,
        server_name: str | None = None,
        server_tag: str | None = None,
        server_config: Any | None = None,
    ) -> None:
        """Initialize RCON client with reconnection support."""
        if not RCON_AVAILABLE:
            raise ImportError(
                "rcon package not installed. Install with: pip install rcon"
            )

        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout

        # Context helpers for multi-server labeling
        self.server_name = server_name
        self.server_tag = server_tag

        # Optional config for this server (holds ups_ema_alpha, etc.)
        self.server_config = server_config

        # Reconnection settings
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.reconnect_backoff = reconnect_backoff
        self.current_reconnect_delay = reconnect_delay

        # State
        self.client: Optional[Any] = None
        self.connected = False
        self.reconnect_task: Optional[asyncio.Task[None]] = None
        self._should_reconnect = True

    def use_context(
        self,
        server_name: str | None = None,
        server_tag: str | None = None,
    ) -> "RconClient":
        """Update RCON client context (e.g., for multi-server use)."""
        if server_name is not None:
            self.server_name = server_name
        if server_tag is not None:
            self.server_tag = server_tag

        logger.debug(
            "rcon_context_updated",
            server_name=self.server_name,
            server_tag=self.server_tag,
        )
        return self

    async def start(self) -> None:
        """Start RCON client with automatic reconnection."""
        self._should_reconnect = True
        await self.connect()

        if self.reconnect_task is None:
            self.reconnect_task = asyncio.create_task(self._reconnection_loop())
            logger.info(
                "rcon_reconnection_enabled",
                initial_delay=self.reconnect_delay,
                max_delay=self.max_reconnect_delay,
                backoff=self.reconnect_backoff,
            )

    async def stop(self) -> None:
        """Stop RCON client and cancel reconnection."""
        self._should_reconnect = False

        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass
            self.reconnect_task = None

        logger.info("rcon_reconnection_disabled")
        await self.disconnect()

    async def connect(self) -> None:
        """Establish RCON connection and authenticate."""
        if not RCON_AVAILABLE or RCONClient is None:
            logger.error("rcon_library_not_available")
            return

        try:

            def _test_connect() -> bool:
                assert RCONClient is not None
                with RCONClient(
                    self.host,
                    self.port,
                    passwd=self.password,
                    timeout=self.timeout,
                ):
                    return True

            result = await asyncio.to_thread(_test_connect)
            if result:
                self.connected = True
                self.current_reconnect_delay = self.reconnect_delay
                logger.info(
                    "rcon_connected",
                    host=self.host,
                    port=self.port,
                )
        except Exception as e:
            self.connected = False
            logger.error(
                "rcon_connection_failed",
                host=self.host,
                port=self.port,
                error=str(e),
                exc_info=True,
            )

    async def _reconnection_loop(self) -> None:
        """Background task that monitors connection and reconnects if needed."""
        logger.info("rcon_reconnection_loop_started")
        while self._should_reconnect:
            try:
                await asyncio.sleep(5.0)
                if not self.connected:
                    logger.info(
                        "rcon_attempting_reconnect",
                        next_retry_delay=self.current_reconnect_delay,
                    )
                    await self.connect()
                    if not self.connected:
                        await asyncio.sleep(self.current_reconnect_delay)
                        self.current_reconnect_delay = min(
                            self.current_reconnect_delay * self.reconnect_backoff,
                            self.max_reconnect_delay,
                        )
                        logger.debug(
                            "rcon_reconnect_backoff",
                            next_delay=self.current_reconnect_delay,
                        )
            except asyncio.CancelledError:
                logger.info("rcon_reconnection_loop_cancelled")
                break
            except Exception as e:
                logger.error(
                    "rcon_reconnection_loop_error",
                    error=str(e),
                    exc_info=True,
                )
                await asyncio.sleep(5.0)

    async def disconnect(self) -> None:
        """Close RCON connection."""
        self.connected = False
        logger.info("rcon_disconnected")

    async def execute(self, command: str) -> str:
        """Execute RCON command with automatic reconnect attempt."""
        if not self.connected:
            logger.warning("rcon_not_connected_attempting_immediate_reconnect")
            await self.connect()
            if not self.connected:
                raise ConnectionError("RCON not connected - connection failed")

        if RCONClient is None:
            raise ConnectionError("RCON library not available")

        try:

            def _execute() -> str:
                assert RCONClient is not None
                with RCONClient(
                    self.host,
                    self.port,
                    passwd=self.password,
                    timeout=self.timeout,
                ) as client:
                    return client.run(command)

            response = await asyncio.wait_for(
                asyncio.to_thread(_execute),
                timeout=self.timeout + 5.0,
            )

            logger.debug(
                "rcon_command_executed",
                command=command[:50],
                response_length=len(response) if response else 0,
            )
            return response if response else ""
        except asyncio.TimeoutError:
            logger.error("rcon_command_timeout", command=command, timeout=self.timeout)
            raise TimeoutError(
                f"RCON command timed out after {self.timeout + 5.0}s: {command}"
            )
        except Exception as e:
            self.connected = False
            logger.error(
                "rcon_command_failed",
                command=command,
                error=str(e),
                exc_info=True,
            )
            raise

    @property
    def is_connected(self) -> bool:
        """Check if RCON is currently connected."""
        return self.connected

    async def get_player_count(self) -> int:
        """Get current online player count."""
        try:
            response = await self.execute("/players")
            logger.debug("player_count_response", response=response)

            if not response:
                return 0

            lines = response.split("\n")
            count = 0
            for line in lines:
                if "(online)" in line.lower():
                    count += 1
            return count
        except Exception as e:
            logger.warning("failed_to_get_player_count", error=str(e))
            return -1

    async def get_players_online(self) -> List[str]:
        """Get list of online player names."""
        try:
            response = await self.execute("/players")
            logger.debug("players_online_response", response=response)

            if not response:
                return []

            players: List[str] = []
            lines = response.split("\n")
            for line in lines:
                line = line.strip()
                if "(online)" in line.lower():
                    player_name = line.split("(online)")[0].strip()
                    player_name = player_name.lstrip("-").strip()
                    if player_name and not player_name.startswith("Player"):
                        players.append(player_name)

            return players
        except Exception as e:
            logger.warning("failed_to_get_players", error=str(e))
            return []

    async def get_players(self) -> List[str]:
        """Alias for get_players_online() for compatibility."""
        return await self.get_players_online()

    async def get_server_time(self) -> str:
        """Get current in-game time."""
        try:
            response = await self.execute("/time")
            logger.debug("server_time_response", response=response)
            if response and response.strip():
                return response.strip()
            return "Unknown"
        except Exception as e:
            logger.warning("failed_to_get_server_time", error=str(e))
            return "Unknown"
