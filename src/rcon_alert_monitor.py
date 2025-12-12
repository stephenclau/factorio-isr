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
High-frequency UPS monitoring with performance alerts.

Provides RconAlertMonitor for frequent UPS checks via RconMetricsEngine
and threshold-based alerting to Discord channels.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class RconAlertMonitor:
    """Lightweight high-frequency UPS monitoring for performance alerts with pause detection."""

    def __init__(
        self,
        rcon_client: Any,
        discord_interface: Any,
        metrics_engine: Optional[Any] = None,
        check_interval: int = 60,
        samples_before_alert: int = 3,
        ups_warning_threshold: float = 55.0,
        ups_recovery_threshold: float = 58.0,
        alert_cooldown: int = 300,
    ) -> None:
        """
        Initialize alert monitor.

        Args:
            rcon_client: RconClient instance for server queries
            discord_interface: Discord interface for alert posting
            metrics_engine: Optional shared RconMetricsEngine (creates new if None)
            check_interval: Seconds between UPS checks (default: 60)
            samples_before_alert: Consecutive bad samples required (default: 3)
            ups_warning_threshold: UPS below this triggers alert (default: 55)
            ups_recovery_threshold: UPS above this clears alert (default: 58)
            alert_cooldown: Seconds between repeated alerts (default: 300)
        """
        self.rcon_client = rcon_client
        self.discord_interface = discord_interface
        self.check_interval = check_interval
        self.samples_before_alert = samples_before_alert
        self.ups_warning_threshold = ups_warning_threshold
        self.ups_recovery_threshold = ups_recovery_threshold
        self.alert_cooldown = alert_cooldown

        # Use shared metrics engine if provided, otherwise create one
        if metrics_engine is None:
            from rcon_metrics_engine import RconMetricsEngine

            self.metrics_engine = RconMetricsEngine(
                rcon_client,
                enable_ups_stat=True,
                enable_evolution_stat=False,
            )
        else:
            self.metrics_engine = metrics_engine

        # Alert state
        self.alert_state: Dict[str, Any] = {
            "low_ups_active": False,
            "last_alert_time": None,
            "consecutive_bad_samples": 0,
            "recent_ups_samples": [],
        }

        self.running = False
        self.task: Optional[asyncio.Task[None]] = None

        logger.info(
            "alert_monitor_initialized",
            check_interval=check_interval,
            samples_required=samples_before_alert,
            threshold=ups_warning_threshold,
            ema_alpha=self.metrics_engine.ema_alpha,
            shared_metrics_engine=metrics_engine is not None,
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
        """Check current UPS using shared metrics engine with pause detection."""
        if not self.rcon_client.is_connected:
            logger.debug("alert_monitor_rcon_not_connected")
            return

        try:
            current_ups = await self.metrics_engine.sample_ups()

            # PAUSE DETECTION: Skip alert processing when server is paused
            if (
                self.metrics_engine.ups_calculator
                and self.metrics_engine.ups_calculator.is_paused
            ):
                logger.debug(
                    "ups_check_skipped_server_paused",
                    last_known_ups=(
                        self.metrics_engine.ups_calculator.last_known_ups
                        if self.metrics_engine.ups_calculator
                        else None
                    ),
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

            # Use EMA from shared engine
            ups_for_decision = (
                self.metrics_engine.ema_ups
                if self.metrics_engine.ema_ups is not None
                else current_ups
            )

            # Low UPS condition (using EMA for threshold)
            if ups_for_decision < self.ups_warning_threshold:
                self.alert_state["consecutive_bad_samples"] += 1
                logger.debug(
                    "low_ups_detected",
                    current_ups=current_ups,
                    ema_ups=self.metrics_engine.ema_ups,
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
                        # Calculate SMA and use EMA from shared engine
                        if self.alert_state["recent_ups_samples"]:
                            sma_ups = sum(self.alert_state["recent_ups_samples"]) / len(
                                self.alert_state["recent_ups_samples"]
                            )
                        else:
                            sma_ups = current_ups

                        ema_ups = (
                            self.metrics_engine.ema_ups
                            if self.metrics_engine.ema_ups is not None
                            else sma_ups
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
                        ema_ups=self.metrics_engine.ema_ups,
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

                    ema_ups = (
                        self.metrics_engine.ema_ups
                        if self.metrics_engine.ema_ups is not None
                        else sma_ups
                    )
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

        if hasattr(self.discord_interface, "send_embed"):
            result = self.discord_interface.send_embed(embed)
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
            result = self.discord_interface.send_message(message)
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

        if hasattr(self.discord_interface, "send_embed"):
            result = self.discord_interface.send_embed(embed)
            await result
        else:
            message = (
                f"✅ **{server_label}: UPS Recovered**\n"
                f"Current: {current_ups:.1f}/60.0 "
                f"(SMA: {sma_ups:.1f}, EMA: {ema_ups:.1f})\n"
                "Performance normal."
            )
            result = self.discord_interface.send_message(message)
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
