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
Unified metrics computation layer for Factorio RCON.

Provides UPSCalculator for pause-aware UPS sampling and RconMetricsEngine
for consolidated metrics gathering (UPS, evolution, players). Designed for
shared use across stats collectors and alert monitors.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class UPSCalculator:
    """Calculate actual UPS from game.tick deltas with pause detection."""

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

    async def sample_ups(self, rcon_client: Any) -> Optional[float]:
        """
        Calculate UPS by comparing tick delta to real-time delta.

        Detects when server is paused (no tick advancement).

        Args:
            rcon_client: RconClient instance to query game.tick

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


class RconMetricsEngine:
    """
    Unified metrics computation layer.

    Consolidates UPS calculation, EMA/SMA tracking, and evolution factor parsing.
    Designed for shared use by RconStatsCollector and RconAlertMonitor to eliminate
    duplicate state and ensure consistent smoothing across stats and alerts.

    **Constraint:** Preserves per-server 1:1 RconClient binding and parallel
    instantiation model. Each server gets its own metrics engine instance.
    """

    def __init__(
        self,
        rcon_client: Any,
        enable_ups_stat: bool = True,
        enable_evolution_stat: bool = True,
    ) -> None:
        """
        Initialize metrics engine.

        Args:
            rcon_client: RconClient instance for server queries
            enable_ups_stat: Enable UPS collection and smoothing
            enable_evolution_stat: Enable evolution factor collection
        """
        self.rcon_client = rcon_client
        self.enable_ups_stat = enable_ups_stat
        self.enable_evolution_stat = enable_evolution_stat

        # Single UPS calculator instance (shared state)
        pause_threshold = getattr(
            getattr(rcon_client, "server_config", None),
            "pause_time_threshold",
            5.0,
        )
        self.ups_calculator: Optional[UPSCalculator] = (
            UPSCalculator(pause_time_threshold=pause_threshold) if enable_ups_stat else None
        )

        # Unified EMA/SMA state (single source of truth)
        self.ema_alpha: float = getattr(
            getattr(self.rcon_client, "server_config", None),
            "ups_ema_alpha",
            0.2,
        )
        self.ema_ups: Optional[float] = None
        self._ups_samples_for_sma: List[float] = []

        logger.info(
            "metrics_engine_initialized",
            server_tag=rcon_client.server_tag,
            server_name=rcon_client.server_name,
            enable_ups_stat=enable_ups_stat,
            enable_evolution_stat=enable_evolution_stat,
            ema_alpha=self.ema_alpha,
            pause_threshold=pause_threshold,
        )

    async def sample_ups(self) -> Optional[float]:
        """
        Sample current UPS with pause detection.

        Returns:
            UPS value, or None if first sample or server paused.
        """
        if not self.enable_ups_stat or not self.ups_calculator:
            return None

        return await self.ups_calculator.sample_ups(self.rcon_client)

    async def get_evolution_by_surface(self) -> Dict[str, float]:
        """
        Fetch evolution factor per surface (multi-surface support).

        Uses /sc (script command) to access game.forces API and query enemy
        evolution factor for each non-platform surface.
        
        **FIX (2025-12-12):** Replaced non-existent game.table_to_json() with
        manual JSON string construction. Factorio's Lua API doesn't provide
        table_to_json; instead we build JSON manually using string concatenation.

        Returns:
            Dict mapping surface names to evolution factors (0.0-1.0).
        """
        if not self.enable_evolution_stat:
            return {}

        try:
            # FIX: Manual JSON construction instead of game.table_to_json()
            # Build JSON like: {"nauvis": 0.42, "gleba": 0.15}
            lua = (
                "/sc "
                "local f = game.forces['enemy']; "
                "local json_parts = {}; "
                "for _, s in pairs(game.surfaces) do "
                "  if not string.find(string.lower(s.name), 'platform') then "
                "    local evo = f.get_evolution_factor(s); "
                "    table.insert(json_parts, '\"' .. s.name .. '\":' .. tostring(evo)); "
                "  end "
                "end; "
                "if #json_parts > 0 then "
                "  rcon.print('{' .. table.concat(json_parts, ',') .. '}'); "
                "else "
                "  rcon.print('{}'); "
                "end"
            )
            response = await self.rcon_client.execute(lua)

            if not response or not response.strip():
                logger.warning("evolution_collection_failed_empty_response")
                return {}

            # Log raw response for debugging
            logger.debug(
                "evolution_raw_response",
                response_sample=response[:500] if len(response) > 500 else response,
            )

            evolution_by_surface: Dict[str, float] = json.loads(response.strip())
            logger.debug(
                "evolution_collected_multi_surface",
                surfaces=list(evolution_by_surface.keys()),
                evolution_data=evolution_by_surface,
            )
            return evolution_by_surface
        except json.JSONDecodeError as e:
            logger.warning(
                "evolution_json_parse_failed",
                error=str(e),
                response=response[:200] if isinstance(response, str) else "",
            )
            return {}
        except Exception as e:
            logger.warning(
                "evolution_collection_failed",
                error=str(e),
                exc_info=True,
            )
            return {}

    async def get_players(self) -> List[str]:
        """Get list of online player names."""
        return await self.rcon_client.get_players()

    async def get_player_count(self) -> int:
        """Get count of online players."""
        return await self.rcon_client.get_player_count()

    async def get_play_time(self) -> str:
        """Get current in-game time."""
        return await self.rcon_client.get_play_time()

    async def gather_all_metrics(self) -> Dict[str, Any]:
        """
        Gather all metrics in one pass (UPS, evolution, players, time).

        Updates internal EMA/SMA state and returns complete metrics dict.
        Ready for direct use by formatters (no further processing needed).

        Returns:
            Dict with keys: ups, ups_sma, ups_ema, is_paused, last_known_ups,
                tick, game_time_seconds, evolution_factor, evolution_by_surface,
                player_count, players, play_time.
        """
        metrics: Dict[str, Any] = {
            "ups": None,
            "ups_sma": None,
            "ups_ema": None,
            "is_paused": False,
            "last_known_ups": None,
            "tick": None,
            "game_time_seconds": None,
            "evolution_factor": None,
            "evolution_by_surface": {},
            "player_count": 0,
            "players": [],
            "play_time": "Unknown",
        }

        try:
            # Get tick and game time
            try:
                response = await self.rcon_client.execute("/sc rcon.print(game.tick)")
                metrics["tick"] = int(response.strip())
                metrics["game_time_seconds"] = metrics["tick"] / 60.0
            except Exception as e:
                logger.warning("tick_collection_failed", error=str(e))

            # UPS with pause detection and smoothing
            if self.enable_ups_stat and self.ups_calculator:
                ups = await self.ups_calculator.sample_ups(self.rcon_client)

                metrics["is_paused"] = self.ups_calculator.is_paused
                metrics["last_known_ups"] = self.ups_calculator.last_known_ups

                if ups is not None:
                    metrics["ups"] = ups

                    # Update SMA window (last 5 samples)
                    self._ups_samples_for_sma.append(ups)
                    if len(self._ups_samples_for_sma) > 5:
                        self._ups_samples_for_sma.pop(0)
                    if self._ups_samples_for_sma:
                        metrics["ups_sma"] = sum(self._ups_samples_for_sma) / len(
                            self._ups_samples_for_sma
                        )

                    # Update EMA (exponential moving average)
                    if self.ema_ups is None:
                        self.ema_ups = ups
                    else:
                        self.ema_ups = (
                            self.ema_alpha * ups
                            + (1.0 - self.ema_alpha) * self.ema_ups
                        )
                    metrics["ups_ema"] = self.ema_ups
                    logger.debug(
                        "metrics_engine_ups_updated",
                        ups=ups,
                        ema_ups=self.ema_ups,
                        sma_ups=metrics.get("ups_sma"),
                        alpha=self.ema_alpha,
                    )

            # Evolution per surface
            if self.enable_evolution_stat:
                evolution_by_surface = await self.get_evolution_by_surface()
                if evolution_by_surface:
                    metrics["evolution_by_surface"] = evolution_by_surface
                    # Backward compat: store first surface as single value
                    metrics["evolution_factor"] = next(
                        iter(evolution_by_surface.values())
                    )

            # Players and time
            metrics["player_count"] = await self.get_player_count()
            metrics["players"] = await self.get_players()
            metrics["play_time"] = await self.get_play_time()

            logger.debug(
                "metrics_engine_gather_complete",
                ups=metrics.get("ups"),
                ups_ema=metrics.get("ups_ema"),
                player_count=metrics["player_count"],
                is_paused=metrics.get("is_paused"),
                evolution_surfaces=list(metrics.get("evolution_by_surface", {}).keys()),
            )
        except Exception as e:
            logger.warning("metrics_engine_partial_failure", error=str(e), exc_info=True)

        return metrics
