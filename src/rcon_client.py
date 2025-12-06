"""
RCON client for Factorio server queries with automatic reconnection.

Handles connection, authentication, and command execution using rcon library.
Includes automatic reconnection with exponential backoff and optional
context helpers for server name/tag.

Also provides:
- RconStatsCollector for periodic server stats posting to Discord
- UPSCalculator for accurate UPS measurement with pause detection
- RconAlertMonitor for performance alerts with EMA-based thresholds
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

# Optional RCON support using rcon library
try:
    from rcon.source import Client as RCONClient

    RCON_AVAILABLE = True
except ImportError:
    RCONClient = None  # type: ignore
    RCON_AVAILABLE = False

logger = structlog.get_logger()


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


class RconStatsCollector:
    """Periodically collect and post server statistics with pause detection."""

    def __init__(
        self,
        rcon_client: RconClient,
        discord_client: Any,
        interval: int | float = 300,
        collect_ups: bool = True,
        collect_evolution: bool = True,
    ) -> None:
        """Initialize stats collector."""
        self.rcon_client = rcon_client
        self.discord_client = discord_client
        self.interval = interval

        self.collect_ups = collect_ups
        self.collect_evolution = collect_evolution

        # UPS calculator with pause detection
        pause_threshold = getattr(
            getattr(rcon_client, "server_config", None),
            "pause_time_threshold",
            5.0,
        )
        self._ups_calculator: Optional[UPSCalculator] = (
            UPSCalculator(pause_time_threshold=pause_threshold) if collect_ups else None
        )

        # Local UPS history for SMA in stats
        self._ups_samples_for_sma: List[float] = []

        # EMA state for stats view
        self.ema_alpha: float = getattr(
            getattr(self.rcon_client, "server_config", None),
            "ups_ema_alpha",
            0.2,
        )
        self.ema_ups: Optional[float] = None

        self.running = False
        self.task: Optional[asyncio.Task[None]] = None

        logger.info(
            "stats_collector_initialized",
            interval=interval,
            rcon_connected=rcon_client.is_connected,
            discord_connected=getattr(discord_client, "is_connected", None),
            collect_ups=collect_ups,
            collect_evolution=collect_evolution,
            ema_alpha=self.ema_alpha,
            pause_threshold=pause_threshold,
        )

    async def start(self) -> None:
        """Start periodic stats collection."""
        if self.running:
            logger.warning("stats_collector_already_running")
            return

        self.running = True
        self.task = asyncio.create_task(self._collection_loop())
        logger.info(
            "stats_collector_started",
            interval=self.interval,
            rcon_connected=self.rcon_client.is_connected,
            discord_connected=getattr(self.discord_client, "is_connected", None),
        )

    async def stop(self) -> None:
        """Stop stats collection."""
        if not self.running:
            logger.debug("stats_collector_stop_called_but_not_running")
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.debug("stats_collector_task_cancelled")
            self.task = None

        logger.info("stats_collector_stopped")

    async def _collection_loop(self) -> None:
        """Main collection loop."""
        logger.info("stats_collection_loop_started")
        iteration = 0

        while self.running:
            iteration += 1
            try:
                logger.debug(
                    "stats_collection_iteration_starting",
                    iteration=iteration,
                    interval=self.interval,
                )
                await self._collect_and_post()
                logger.debug(
                    "stats_collection_iteration_complete",
                    iteration=iteration,
                    next_collection_in=self.interval,
                )
            except Exception as e:
                logger.error(
                    "stats_collection_error",
                    iteration=iteration,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

            if self.running:
                logger.debug(
                    "stats_collector_sleeping",
                    duration=self.interval,
                    next_iteration=iteration + 1,
                )
                await asyncio.sleep(self.interval)

        logger.info("stats_collection_loop_exited", total_iterations=iteration)

    async def _gather_extended_metrics(self) -> Dict[str, Any]:
        """Gather extended game metrics via RCON with pause detection."""
        metrics: Dict[str, Any] = {
            "ups": None,
            "ups_sma": None,
            "ups_ema": None,
            "is_paused": False,
            "last_known_ups": None,
            "tick": None,
            "game_time_seconds": None,
            "evolution_factor": None,
            "evolution_by_surface": {},  # Dict[surface_name, {factor, index}]
        }

        try:
            # Get tick and game time
            try:
                response = await self.rcon_client.execute("/sc rcon.print(game.tick)")
                metrics["tick"] = int(response.strip())
                metrics["game_time_seconds"] = metrics["tick"] / 60.0
            except Exception as e:
                logger.warning("tick_collection_failed", error=str(e))

            # UPS calculation with pause detection
            if self.collect_ups and self._ups_calculator:
                ups = await self._ups_calculator.sample_ups(self.rcon_client)

                # Capture pause state
                metrics["is_paused"] = self._ups_calculator.is_paused
                metrics["last_known_ups"] = self._ups_calculator.last_known_ups

                if ups is not None:
                    metrics["ups"] = ups
                    logger.debug("ups_collected", ups=ups, is_paused=False)

                    # Update SMA window (last 5 samples)
                    self._ups_samples_for_sma.append(ups)
                    if len(self._ups_samples_for_sma) > 5:
                        self._ups_samples_for_sma.pop(0)
                    if self._ups_samples_for_sma:
                        metrics["ups_sma"] = sum(self._ups_samples_for_sma) / len(
                            self._ups_samples_for_sma
                        )

                    # Update EMA for stats view
                    if self.ema_ups is None:
                        self.ema_ups = ups
                    else:
                        self.ema_ups = (
                            self.ema_alpha * ups
                            + (1.0 - self.ema_alpha) * self.ema_ups
                        )
                    metrics["ups_ema"] = self.ema_ups
                    logger.debug(
                        "stats_ups_ema_updated",
                        ups=ups,
                        ema_ups=self.ema_ups,
                        alpha=self.ema_alpha,
                    )
                elif self._ups_calculator.is_paused:
                    logger.debug(
                        "ups_not_collected_server_paused",
                        last_known_ups=self._ups_calculator.last_known_ups,
                    )

            # Evolution factor per surface (multi-surface support)
            if self.collect_evolution:
                response: Optional[str] = None
                try:
                    # Print as: name:index:factor per line
                    response = await self.rcon_client.execute(
                        "/sc "
                        "for _, surface in pairs(game.surfaces) do "
                        "  local evo = game.forces[\"enemy\"].get_evolution_factor(surface); "
                        "  rcon.print(surface.name .. \":\" .. surface.index .. \":\" .. evo); "
                        "end"
                    )

                    if not response:
                        logger.warning("evolution_collection_failed_empty_response")
                    else:
                        evolution_by_surface: Dict[str, Dict[str, float]] = {}
                        for line in response.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            # Expect "name:index:factor"
                            parts = line.split(":")
                            if len(parts) != 3:
                                logger.debug(
                                    "evolution_line_unexpected_format",
                                    line=line,
                                )
                                continue
                            name, index_str, factor_str = parts

                            # Skip platform surfaces by name
                            if "platform" in name.lower():
                                logger.debug(
                                    "evolution_surface_skipped_platform",
                                    surface=name,
                                )
                                continue

                            try:
                                index = int(index_str)
                                factor = float(factor_str)
                            except ValueError:
                                logger.debug(
                                    "evolution_line_parse_failed",
                                    line=line,
                                )
                                continue

                            evolution_by_surface[name] = {
                                "factor": factor,
                                "index": index,
                            }

                        metrics["evolution_by_surface"] = evolution_by_surface

                        # For backwards compatibility, store the first/main surface evolution
                        if evolution_by_surface:
                            first_surface = next(iter(evolution_by_surface.values()))
                            metrics["evolution_factor"] = first_surface["factor"]

                        logger.debug(
                            "evolution_collected_multi_surface",
                            surfaces=list(evolution_by_surface.keys()),
                            evolution_data=evolution_by_surface,
                        )
                        
                        
                except Exception as e:
                    logger.warning(
                        "evolution_collection_failed",
                        error=str(e),
                        response=(response[:200] if isinstance(response, str) else "")
                    )

        except Exception as e:
            logger.warning("extended_metrics_partial_failure", error=str(e))

        return metrics

    async def _collect_and_post(self) -> None:
        """Collect stats and post to Discord."""
        try:
            player_count = await self.rcon_client.get_player_count()
            players = await self.rcon_client.get_players_online()
            server_time = await self.rcon_client.get_server_time()

            metrics = await self._gather_extended_metrics()

            logger.debug(
                "stats_gathered",
                player_count=player_count,
                player_list_count=len(players),
                server_time=server_time,
                ups=metrics.get("ups"),
                ups_sma=metrics.get("ups_sma"),
                ups_ema=metrics.get("ups_ema"),
                is_paused=metrics.get("is_paused"),
                evolution=metrics.get("evolution_factor"),
            )

            embed_sent = False
            if hasattr(self.discord_client, "send_embed"):
                try:
                    embed = self._format_stats_embed(
                        player_count,
                        players,
                        server_time,
                        metrics,
                    )
                    logger.debug("stats_formatted_as_embed")
                    result = self.discord_client.send_embed(embed)
                    embed_sent = await result
                    logger.debug("stats_embed_send_result", success=embed_sent)
                except Exception as e:
                    logger.warning(
                        "embed_format_or_send_failed",
                        error=str(e),
                        exc_info=True,
                    )
                    embed_sent = False

            if not embed_sent:
                message = self._format_stats_text(
                    player_count,
                    players,
                    server_time,
                    metrics,
                )
                logger.debug(
                    "stats_formatted_as_text",
                    message_preview=(
                        message[:100] if len(message) > 100 else message
                    ),
                )
                result = self.discord_client.send_message(message)
                await result

            logger.info(
                "stats_posted",
                player_count=player_count,
                players=len(players),
                used_embed=embed_sent,
                ups=metrics.get("ups"),
                ups_sma=metrics.get("ups_sma"),
                ups_ema=metrics.get("ups_ema"),
                is_paused=metrics.get("is_paused"),
            )
        except Exception as e:
            logger.error("failed_to_post_stats", error=str(e), exc_info=True)

    def _build_server_label(self) -> str:
        """Build a server label from server_name and server_tag safely."""
        parts: List[str] = []
        if self.rcon_client.server_tag is not None:
            parts.append(f"[{self.rcon_client.server_tag}]")
        if self.rcon_client.server_name is not None:
            parts.append(self.rcon_client.server_name)
        return " ".join(parts) if parts else "Factorio Server"

        # ... all existing imports, classes, and code above unchanged ...

    def _format_stats_text(
        self,
        player_count: int,
        players: List[str],
        server_time: str,
        metrics: Dict[str, Any] | None = None,
    ) -> str:
        """Format stats as a plain text Discord message with pause detection."""
        lines: List[str] = []
        server_label = self._build_server_label()
        lines.append(f"📊 **{server_label} Stats**")

        # Check if paused
        if metrics and metrics.get("is_paused"):
            last_ups = metrics.get("last_known_ups")
            if last_ups and last_ups > 0:
                lines.append(f"⏸️ Status: Paused (last: {last_ups:.1f} UPS)")
            else:
                lines.append("⏸️ Status: Paused")
        elif metrics and metrics.get("ups") is not None:
            ups = float(metrics["ups"])
            sma = metrics.get("ups_sma")
            ema = metrics.get("ups_ema")
            ups_emoji = "✅" if ups >= 59.0 else "⚠️"

            parts = [f"Raw: {ups:.1f}/60.0"]
            if sma is not None:
                parts.append(f"SMA: {float(sma):.1f}")
            if ema is not None:
                parts.append(f"EMA: {float(ema):.1f}")

            lines.append(f"{ups_emoji} UPS: " + " | ".join(parts))

        lines.append(f"👥 Players Online: {player_count}")
        if players:
            lines.append("📝 " + ", ".join(players))
        lines.append(f"⏰ Game Time: {server_time}")

        # Evolution per surface
        if metrics and metrics.get("evolution_by_surface"):
            evolution_by_surface = metrics["evolution_by_surface"]
            if len(evolution_by_surface) == 1:
                # Single surface - compact format
                surface_name = next(iter(evolution_by_surface.keys()))
                evo_pct = evolution_by_surface[surface_name]["factor"] * 100.0
                evo_str = f"{evo_pct:.2f}" if evo_pct >= 0.1 else f"{evo_pct:.4f}"
                lines.append(f"🐛 Evolution: {evo_str}%")
            else:
                # Multiple surfaces - list format
                lines.append("🐛 Evolution:")
                for surface_name, data in sorted(
                    evolution_by_surface.items(),
                    key=lambda x: x[1]["index"],
                ):
                    evo_pct = data["factor"] * 100.0
                    evo_str = f"{evo_pct:.2f}" if evo_pct >= 0.1 else f"{evo_pct:.4f}"
                    lines.append(f" • {surface_name}: {evo_str}%")
        elif metrics and metrics.get("evolution_factor") is not None:
            # Fallback for old single-surface format
            evolution_pct = float(metrics["evolution_factor"]) * 100.0
            evo_str = (
                f"{evolution_pct:.2f}"
                if evolution_pct >= 0.1
                else f"{evolution_pct:.4f}"
            )
            lines.append(f"🐛 Evolution: {evo_str}%")

        return "\n".join(lines)

    def _format_stats_embed(
        self,
        player_count: int,
        players: List[str],
        server_time: str,
        metrics: Dict[str, Any] | None = None,
    ) -> Any:
        """Format stats as Discord embed with pause detection."""
        from discord_interface import EmbedBuilder  # type: ignore[import]

        server_label = self._build_server_label()
        title = f"📊 {server_label} Status"
        embed = EmbedBuilder.create_base_embed(
            title=title,
            color=EmbedBuilder.COLOR_INFO,
        )

        # UPS or Pause status
        if metrics and metrics.get("is_paused"):
            last_ups = metrics.get("last_known_ups")
            if last_ups and last_ups > 0:
                value = f"⏸️ Paused\n(last: {last_ups:.1f} UPS)"
            else:
                value = "⏸️ Paused"
            embed.add_field(
                name="Status",
                value=value,
                inline=True,
            )
        elif metrics and metrics.get("ups") is not None:
            ups = float(metrics["ups"])
            sma = metrics.get("ups_sma")
            ema = metrics.get("ups_ema")
            ups_emoji = "✅" if ups >= 59.0 else "⚠️"

            lines: List[str] = [f"Raw: {ups:.1f}/60.0"]
            if sma is not None:
                lines.append(f"SMA: {float(sma):.1f}")
            if ema is not None:
                lines.append(f"EMA: {float(ema):.1f}")

            embed.add_field(
                name=f"{ups_emoji} UPS",
                value="\n".join(lines),
                inline=True,
            )

        embed.add_field(
            name="👥 Players Online",
            value=f"{player_count}",
            inline=True,
        )

        embed.add_field(
            name="⏰ Game Time",
            value=server_time,
            inline=True,
        )

        if players:
            players_text = "\n".join(f"• {p}" for p in players)
            embed.add_field(
                name="📝 Players",
                value=(
                    players_text
                    if len(players_text) <= 1024
                    else f"{players_text[:1020]}..."
                ),
                inline=False,
            )

        # Evolution per surface
        if metrics and metrics.get("evolution_by_surface"):
            evolution_by_surface = metrics["evolution_by_surface"]

            if len(evolution_by_surface) == 1:
                # Single surface - inline field
                surface_name = next(iter(evolution_by_surface.keys()))
                evo_pct = evolution_by_surface[surface_name]["factor"] * 100.0
                evo_str = f"{evo_pct:.2f}" if evo_pct >= 0.1 else f"{evo_pct:.4f}"
                embed.add_field(
                    name="🐛 Evolution",
                    value=f"{evo_str}%",
                    inline=True,
                )
            else:
                # Multiple surfaces - full-width field with list
                evo_lines = []
                for surface_name, data in sorted(
                    evolution_by_surface.items(),
                    key=lambda x: x[1]["index"],
                ):
                    evo_pct = data["factor"] * 100.0
                    evo_str = (
                        f"{evo_pct:.2f}" if evo_pct >= 0.1 else f"{evo_pct:.4f}"
                    )
                    evo_lines.append(f"**{surface_name}**: {evo_str}%")

                embed.add_field(
                    name="🐛 Evolution by Surface",
                    value="\n".join(evo_lines),
                    inline=False,
                )
        elif metrics and metrics.get("evolution_factor") is not None:
            # Fallback for old single-surface format
            evolution_pct = float(metrics["evolution_factor"]) * 100.0
            evo_str = (
                f"{evolution_pct:.2f}"
                if evolution_pct >= 0.1
                else f"{evolution_pct:.4f}"
            )
            embed.add_field(
                name="🐛 Evolution",
                value=f"{evo_str}%",
                inline=True,
            )

        return embed

# ... remainder of RconAlertMonitor and other code stays unchanged ...



class RconAlertMonitor:
    """Lightweight high-frequency UPS monitoring for performance alerts with pause detection."""

    def __init__(
        self,
        rcon_client: RconClient,
        discord_client: Any,
        check_interval: int = 60,
        samples_before_alert: int = 3,
        ups_warning_threshold: float = 55.0,
        ups_recovery_threshold: float = 58.0,
        alert_cooldown: int = 300,
    ) -> None:
        """Initialize alert monitor."""
        self.rcon_client = rcon_client
        self.discord_client = discord_client
        self.check_interval = check_interval
        self.samples_before_alert = samples_before_alert
        self.ups_warning_threshold = ups_warning_threshold
        self.ups_recovery_threshold = ups_recovery_threshold
        self.alert_cooldown = alert_cooldown

        # UPS calculator with pause detection
        pause_threshold = getattr(
            getattr(rcon_client, "server_config", None),
            "pause_time_threshold",
            5.0,
        )
        self.ups_calculator = UPSCalculator(pause_time_threshold=pause_threshold)

        # Alert state
        self.alert_state: Dict[str, Any] = {
            "low_ups_active": False,
            "last_alert_time": None,
            "consecutive_bad_samples": 0,
            "recent_ups_samples": [],
        }

        self.running = False
        self.task: Optional[asyncio.Task[None]] = None

        # EMA for alert decisions
        self.ema_alpha: float = getattr(
            getattr(self.rcon_client, "server_config", None),
            "ups_ema_alpha",
            0.2,
        )
        self.ema_ups: Optional[float] = None

        logger.info(
            "alert_monitor_initialized",
            check_interval=check_interval,
            samples_required=samples_before_alert,
            threshold=ups_warning_threshold,
            ema_alpha=self.ema_alpha,
            pause_threshold=pause_threshold,
        )

    async def start(self) -> None:
        """Start alert monitoring loop."""
        if self.running:
            logger.warning("alert_monitor_already_running")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("alert_monitor_started", interval=self.check_interval)

    async def stop(self) -> None:
        """Stop alert monitoring."""
        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

        logger.info("alert_monitor_stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop - checks UPS only."""
        while self.running:
            try:
                await self._check_ups()
            except Exception as e:
                logger.error(
                    "alert_monitor_check_failed",
                    error=str(e),
                    exc_info=True,
                )

            if self.running:
                await asyncio.sleep(self.check_interval)

    async def _check_ups(self) -> None:
        """Check current UPS using tick delta method with pause detection."""
        if not self.rcon_client.is_connected:
            logger.debug("alert_monitor_rcon_not_connected")
            return

        try:
            current_ups = await self.ups_calculator.sample_ups(self.rcon_client)

            # PAUSE DETECTION: Skip alert processing when server is paused
            if self.ups_calculator.is_paused:
                logger.debug(
                    "ups_check_skipped_server_paused",
                    last_known_ups=self.ups_calculator.last_known_ups,
                )

                # Clear low UPS alert state if paused (expected behavior)
                if self.alert_state["low_ups_active"]:
                    logger.info(
                        "low_ups_cleared_server_paused",
                        server_tag=self.rcon_client.server_tag,
                    )
                    self.alert_state["low_ups_active"] = False
                    self.alert_state["consecutive_bad_samples"] = 0

                # Don't process alerts when paused
                return

            # Skip if first sample (None but not paused)
            if current_ups is None:
                logger.debug("ups_first_sample_skipped")
                return

            # Track recent samples (keep last 5 for SMA)
            self.alert_state["recent_ups_samples"].append(current_ups)
            if len(self.alert_state["recent_ups_samples"]) > 5:
                self.alert_state["recent_ups_samples"].pop(0)

            logger.debug(
                "ups_sample_collected",
                ups=current_ups,
                samples=len(self.alert_state["recent_ups_samples"]),
            )

            # Update EMA
            if self.ema_ups is None:
                self.ema_ups = current_ups
            else:
                self.ema_ups = (
                    self.ema_alpha * current_ups
                    + (1.0 - self.ema_alpha) * self.ema_ups
                )

            logger.debug(
                "ups_ema_updated",
                current_ups=current_ups,
                ema_ups=self.ema_ups,
                alpha=self.ema_alpha,
            )

            ups_for_decision = self.ema_ups if self.ema_ups is not None else current_ups

            # Low UPS condition (using EMA for threshold)
            if ups_for_decision < self.ups_warning_threshold:
                self.alert_state["consecutive_bad_samples"] += 1
                logger.debug(
                    "low_ups_detected",
                    current_ups=current_ups,
                    ema_ups=self.ema_ups,
                    decision_ups=ups_for_decision,
                    threshold=self.ups_warning_threshold,
                    consecutive_count=self.alert_state["consecutive_bad_samples"],
                )

                if (
                    not self.alert_state["low_ups_active"]
                    and self.alert_state["consecutive_bad_samples"]
                    >= self.samples_before_alert
                ):
                    if self._can_send_alert():
                        # Calculate SMA and EMA for alert
                        if self.alert_state["recent_ups_samples"]:
                            sma_ups = sum(self.alert_state["recent_ups_samples"]) / len(
                                self.alert_state["recent_ups_samples"]
                            )
                        else:
                            sma_ups = current_ups

                        ema_ups = (
                            self.ema_ups if self.ema_ups is not None else sma_ups
                        )
                        await self._send_low_ups_alert(current_ups, sma_ups, ema_ups)
                        self.alert_state["low_ups_active"] = True
                        self.alert_state["last_alert_time"] = datetime.now(
                            timezone.utc
                        )

            # Recovery condition (using EMA for threshold)
            elif ups_for_decision >= self.ups_recovery_threshold:
                if self.alert_state["consecutive_bad_samples"] > 0:
                    logger.debug(
                        "ups_recovery_detected",
                        current_ups=current_ups,
                        ema_ups=self.ema_ups,
                        decision_ups=ups_for_decision,
                        threshold=self.ups_recovery_threshold,
                    )
                self.alert_state["consecutive_bad_samples"] = 0

                if self.alert_state["low_ups_active"]:
                    if self.alert_state["recent_ups_samples"]:
                        sma_ups = sum(self.alert_state["recent_ups_samples"]) / len(
                            self.alert_state["recent_ups_samples"]
                        )
                    else:
                        sma_ups = current_ups

                    ema_ups = self.ema_ups if self.ema_ups is not None else sma_ups
                    await self._send_ups_recovered_alert(
                        current_ups,
                        sma_ups,
                        ema_ups,
                    )
                    self.alert_state["low_ups_active"] = False

        except Exception as e:
            logger.warning("ups_check_failed", error=str(e), exc_info=True)

    def _can_send_alert(self) -> bool:
        """Check if enough time has passed since last alert (cooldown)."""
        last_alert = self.alert_state.get("last_alert_time")
        if last_alert is None:
            return True

        elapsed = (datetime.now(timezone.utc) - last_alert).total_seconds()
        can_send = elapsed >= self.alert_cooldown
        if not can_send:
            logger.debug(
                "alert_suppressed_cooldown",
                elapsed=elapsed,
                cooldown=self.alert_cooldown,
            )
        return can_send

    async def _send_low_ups_alert(
        self,
        current_ups: float,
        sma_ups: float,
        ema_ups: float,
    ) -> None:
        """Send low UPS warning with SMA and EMA."""
        from discord_interface import EmbedBuilder  # type: ignore[import]

        server_label = self._build_server_label()
        embed = EmbedBuilder.create_base_embed(
            title=f"⚠️ {server_label}: Low UPS Warning",
            color=EmbedBuilder.COLOR_WARNING,
        )

        embed.add_field(
            name="Current UPS (raw)",
            value=f"{current_ups:.1f}/60.0",
            inline=True,
        )
        embed.add_field(
            name="UPS SMA (last 5)",
            value=f"{sma_ups:.1f}/60.0",
            inline=True,
        )
        embed.add_field(
            name="UPS EMA",
            value=f"{ema_ups:.1f}/60.0",
            inline=True,
        )
        embed.add_field(
            name="Threshold",
            value=f"< {self.ups_warning_threshold}",
            inline=True,
        )
        embed.add_field(
            name="Duration",
            value=(
                f"{self.alert_state['consecutive_bad_samples']} "
                f"consecutive checks "
                f"(~{self.alert_state['consecutive_bad_samples'] * self.check_interval // 60} min)"
            ),
            inline=False,
        )
        embed.add_field(
            name="Impact",
            value="Game is running slower than real-time. Performance degraded.",
            inline=False,
        )

        if hasattr(self.discord_client, "send_embed"):
            result = self.discord_client.send_embed(embed)
            await result
        else:
            message = (
                f"⚠️ **{server_label}: Low UPS Warning**\n"
                f"Current: {current_ups:.1f}/60.0 "
                f"(SMA: {sma_ups:.1f}, EMA: {ema_ups:.1f})\n"
                f"Threshold: < {self.ups_warning_threshold}\n"
                f"Duration: {self.alert_state['consecutive_bad_samples']} checks\n"
                "Performance degraded."
            )
            result = self.discord_client.send_message(message)
            await result

        logger.warning(
            "low_ups_alert_sent",
            server_tag=self.rcon_client.server_tag,
            current_ups=current_ups,
            sma_ups=sma_ups,
            ema_ups=ema_ups,
            consecutive_bad=self.alert_state["consecutive_bad_samples"],
        )

    async def _send_ups_recovered_alert(
        self,
        current_ups: float,
        sma_ups: float,
        ema_ups: float,
    ) -> None:
        """Send UPS recovery notification with SMA and EMA."""
        from discord_interface import EmbedBuilder  # type: ignore[import]

        server_label = self._build_server_label()
        embed = EmbedBuilder.create_base_embed(
            title=f"✅ {server_label}: UPS Recovered",
            color=EmbedBuilder.COLOR_SUCCESS,
        )

        embed.add_field(
            name="Current UPS (raw)",
            value=f"{current_ups:.1f}/60.0",
            inline=True,
        )
        embed.add_field(
            name="UPS SMA (last 5)",
            value=f"{sma_ups:.1f}/60.0",
            inline=True,
        )
        embed.add_field(
            name="UPS EMA",
            value=f"{ema_ups:.1f}/60.0",
            inline=True,
        )
        embed.add_field(
            name="Status",
            value="Performance has returned to normal.",
            inline=False,
        )

        if hasattr(self.discord_client, "send_embed"):
            result = self.discord_client.send_embed(embed)
            await result
        else:
            message = (
                f"✅ **{server_label}: UPS Recovered**\n"
                f"Current: {current_ups:.1f}/60.0 "
                f"(SMA: {sma_ups:.1f}, EMA: {ema_ups:.1f})\n"
                "Performance normal."
            )
            result = self.discord_client.send_message(message)
            await result

        logger.info(
            "ups_recovered_alert_sent",
            server_tag=self.rcon_client.server_tag,
            current_ups=current_ups,
            sma_ups=sma_ups,
            ema_ups=ema_ups,
        )

    def _build_server_label(self) -> str:
        """Build server label from context."""
        parts: List[str] = []
        if self.rcon_client.server_tag:
            parts.append(f"[{self.rcon_client.server_tag}]")
        if self.rcon_client.server_name:
            parts.append(self.rcon_client.server_name)
        return " ".join(parts) if parts else "Factorio Server"
