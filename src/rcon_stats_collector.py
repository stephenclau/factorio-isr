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
Periodic server statistics collection and Discord posting.

Provides RconStatsCollector for scheduled stats gathering via RconMetricsEngine
and formatted posting to Discord channels.
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

import structlog

logger = structlog.get_logger()


class RconStatsCollector:
    """Periodically collect and post server statistics with pause detection."""

    def __init__(
        self,
        rcon_client: Any,
        discord_interface: Any,
        metrics_engine: Optional[Any] = None,
        interval: int | float = 300,
        collect_ups: bool = True,
        collect_evolution: bool = True,
    ) -> None:
        """
        Initialize stats collector.

        Args:
            rcon_client: RconClient instance for server queries
            discord_interface: Discord interface for message posting
            metrics_engine: Optional shared RconMetricsEngine (creates new if None)
            interval: Seconds between stats collection cycles (default: 300)
            collect_ups: Enable UPS collection
            collect_evolution: Enable evolution factor collection
        """
        self.rcon_client = rcon_client
        self.discord_interface = discord_interface
        self.interval = interval

        # Use shared metrics engine if provided, otherwise create one
        if metrics_engine is None:
            from rcon_metrics_engine import RconMetricsEngine

            self.metrics_engine = RconMetricsEngine(
                rcon_client,
                collect_ups=collect_ups,
                collect_evolution=collect_evolution,
            )
        else:
            self.metrics_engine = metrics_engine

        self.running = False
        self.task: Optional[asyncio.Task[None]] = None

        logger.info(
            "stats_collector_initialized",
            interval=interval,
            rcon_connected=rcon_client.is_connected,
            discord_connected=getattr(discord_interface, "is_connected", None),
            shared_metrics_engine=metrics_engine is not None,
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
            discord_connected=getattr(self.discord_interface, "is_connected", None),
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

    async def _collect_and_post(self) -> None:
        """Collect stats via engine and post to Discord using formatters."""
        try:
            # Import formatters from bot helpers
            from bot.helpers import format_stats_embed, format_stats_text  # type: ignore[import]

            # Gather all metrics via shared engine
            metrics = await self.metrics_engine.gather_all_metrics()

            logger.debug(
                "stats_gathered",
                player_count=metrics.get("player_count"),
                player_list_count=len(metrics.get("players", [])),
                server_time=metrics.get("server_time"),
                ups=metrics.get("ups"),
                ups_sma=metrics.get("ups_sma"),
                ups_ema=metrics.get("ups_ema"),
                is_paused=metrics.get("is_paused"),
                evolution=metrics.get("evolution_factor"),
            )

            # Build server label for formatting
            server_label = self._build_server_label()

            # Format and send
            embed_sent = False
            if hasattr(self.discord_interface, "send_embed"):
                try:
                    embed = format_stats_embed(server_label, metrics)
                    logger.debug("stats_formatted_as_embed")
                    result = self.discord_interface.send_embed(embed)
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
                message = format_stats_text(server_label, metrics)
                logger.debug(
                    "stats_formatted_as_text",
                    message_preview=(message[:100] if len(message) > 100 else message),
                )
                result = self.discord_interface.send_message(message)
                await result

            logger.info(
                "stats_posted",
                player_count=metrics.get("player_count"),
                players=len(metrics.get("players", [])),
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
