

"""RCON connection status monitoring and notifications."""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Any, Dict
import discord
import structlog

logger = structlog.get_logger()


class RconHealthMonitor:
    """Monitor RCON connection health and send notifications."""

    def __init__(self, bot: Any) -> None:
        """
        Initialize RCON health monitor.

        Args:
            bot: DiscordBot instance with server_manager and event_channel_id
        """
        self.bot = bot
        self.rcon_server_states: Dict[str, Dict[str, Any]] = {}  # {tag: {"previous_status": bool | None, "last_connected": datetime | None}}
        self.rcon_monitor_task: Optional[asyncio.Task] = None
        self._last_rcon_status_alert_sent: Optional[datetime] = None

    async def start(self) -> None:
        """Start RCON health monitoring."""
        if not self.rcon_monitor_task:
            self.rcon_monitor_task = asyncio.create_task(self._monitor_rcon_status())
            logger.info("rcon_status_monitoring_started")

    async def stop(self) -> None:
        """Stop RCON health monitoring."""
        if self.rcon_monitor_task:
            self.rcon_monitor_task.cancel()
            try:
                await self.rcon_monitor_task
            except asyncio.CancelledError:
                pass
            self.rcon_monitor_task = None
            logger.info("rcon_status_monitoring_stopped")

    async def _monitor_rcon_status(self) -> None:
        """
        Monitor RCON connection status and send notifications.

        Multi-server:
        - Tracks per-server transitions via server_manager.get_status_summary().
        """
        logger.info("rcon_status_monitor_started")

        # For compatibility with presence / health, keep this as "any connected"
        previous_any_status: Optional[bool] = None

        while self.bot._connected:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                transitions_detected = False

                if not self.bot.server_manager:
                    logger.error("rcon_status_monitor_no_server_manager")
                    current_any_status = False
                else:
                    status_summary = self.bot.server_manager.get_status_summary()
                    current_any_status = any(status_summary.values())

                    for tag, status in status_summary.items():
                        if await self._handle_server_status_change(tag, status):
                            transitions_detected = True

                # Maintain rcon_last_connected for "any connected" uptime if needed elsewhere
                if previous_any_status is not None and current_any_status != previous_any_status:
                    if current_any_status:
                        self.bot.rcon_last_connected = datetime.now(timezone.utc)
                    # When going disconnected, rcon_last_connected is left as last connected time
                elif previous_any_status is None and current_any_status:
                    self.bot.rcon_last_connected = datetime.now(timezone.utc)

                # RCON status alert scheduling: check if we should send
                should_send_status_alert = False

                if self.bot.rcon_status_alert_mode == "transition":
                    # Send on any server transition
                    should_send_status_alert = transitions_detected
                elif self.bot.rcon_status_alert_mode == "interval":
                    # Send periodically based on interval
                    now = datetime.now(timezone.utc)
                    if self._last_rcon_status_alert_sent is None:
                        # First time - send immediately
                        should_send_status_alert = True
                    else:
                        elapsed = (now - self._last_rcon_status_alert_sent).total_seconds()
                        should_send_status_alert = elapsed >= self.bot.rcon_status_alert_interval

                if should_send_status_alert and self.bot.server_manager:
                    await self._send_status_alert_embeds()
                    self._last_rcon_status_alert_sent = datetime.now(timezone.utc)

                await self.bot.presence_manager.update()
                previous_any_status = current_any_status

            except asyncio.CancelledError:
                logger.info("rcon_status_monitor_cancelled")
                break
            except Exception as e:
                logger.error("rcon_status_monitor_error", error=str(e), exc_info=True)
                await asyncio.sleep(10)

    async def _handle_server_status_change(self, server_tag: str, current_status: bool) -> bool:
        """
        Handle status transition for a single server.

        Returns:
            True if this call detected a transition, False otherwise.
        """
        state = self.rcon_server_states.setdefault(
            server_tag,
            {"previous_status": None, "last_connected": None},
        )

        previous = state["previous_status"]
        transition_detected = False

        if previous is not None and current_status != previous:
            transition_detected = True
            if current_status:
                # Reconnected
                await self._notify_rcon_reconnected(server_tag)
                state["last_connected"] = datetime.now(timezone.utc)
            else:
                # Disconnected
                await self._notify_rcon_disconnected(server_tag)
        elif previous is None and current_status:
            # First check and already connected
            state["last_connected"] = datetime.now(timezone.utc)

        state["previous_status"] = current_status
        return transition_detected

    async def _send_status_alert_embeds(self) -> None:
        """
        Send RCON status alert embeds to configured channels.
        """
        try:
            from .discord_interface import EmbedBuilder  # type: ignore
        except ImportError:
            try:
                from discord_interface import EmbedBuilder  # type: ignore
            except ImportError:
                logger.error("discord_interface_not_available_for_status_alert")
                return

        if not self.bot.server_manager:
            return

        embed = self._build_rcon_status_alert_embed(EmbedBuilder)
        if embed is None:
            return

        # Global channel
        if self.bot.event_channel_id is not None:
            channel = self.bot.get_channel(self.bot.event_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(embed=embed)
                    logger.info(
                        "rcon_status_alert_sent",
                        scope="global",
                        channel_id=self.bot.event_channel_id,
                    )
                except Exception as e:
                    logger.warning(
                        "rcon_status_alert_send_failed",
                        scope="global",
                        channel_id=self.bot.event_channel_id,
                        error=str(e),
                    )

        # Per-server channels
        for tag, config in self.bot.server_manager.list_servers().items():
            server_channel_id = getattr(config, "event_channel_id", None)
            if not server_channel_id:
                continue

            # Avoid double-send to same channel if it's also global
            if (
                self.bot.event_channel_id is not None
                and server_channel_id == self.bot.event_channel_id
            ):
                continue

            channel = self.bot.get_channel(server_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(embed=embed)
                    logger.info(
                        "rcon_status_alert_sent",
                        scope="server",
                        server_tag=tag,
                        channel_id=server_channel_id,
                    )
                except Exception as e:
                    logger.warning(
                        "rcon_status_alert_send_failed",
                        scope="server",
                        server_tag=tag,
                        channel_id=server_channel_id,
                        error=str(e),
                    )

    def _build_rcon_status_alert_embed(self, EmbedBuilder: Any) -> Optional[discord.Embed]:
        """Build an embed summarizing RCON connectivity for all servers."""
        if not self.bot.server_manager:
            return None

        status_summary = self.bot.server_manager.get_status_summary()
        if not status_summary:
            return None

        total = len(status_summary)
        connected_count = sum(1 for v in status_summary.values() if v)

        embed = discord.Embed(
            title="📱 RCON Status Alert",
            color=EmbedBuilder.COLOR_INFO,
            timestamp=discord.utils.utcnow(),
        )

        for tag, config in self.bot.server_manager.list_servers().items():
            is_connected = status_summary.get(tag, False)
            status_icon = "🟢" if is_connected else "🔴"

            field_lines = [
                f"{status_icon} {'Online' if is_connected else 'Offline'}",
                f"Host: `{config.rcon_host}:{config.rcon_port}`",
            ]

            if getattr(config, "description", None):
                field_lines.insert(0, f"*{config.description}*")

            embed.add_field(
                name=f"[{tag}] {config.name}",
                value="\n".join(field_lines),
                inline=False,
            )

        embed.set_footer(text=f"RCON ({connected_count}/{total} servers connected)")
        return embed

    async def _notify_rcon_disconnected(self, server_tag: str) -> None:
        """Send notification when RCON disconnects for a specific server."""
        try:
            from .discord_interface import EmbedBuilder  # type: ignore
        except ImportError:
            try:
                from discord_interface import EmbedBuilder  # type: ignore
            except ImportError:
                logger.error("discord_interface_not_available")
                return

        if not self.bot.server_manager:
            return

        try:
            from .bot.helpers import send_to_channel  # type: ignore
        except ImportError:
            try:
                from helpers import send_to_channel  # type: ignore
            except ImportError:
                send_to_channel = None

        try:
            config = self.bot.server_manager.get_config(server_tag)
            channel_id = config.event_channel_id

            if not channel_id:
                logger.debug(
                    "skip_rcon_disconnect_notification_no_channel", server_tag=server_tag
                )
                return

            embed = EmbedBuilder.info_embed(
                title=f"⚠️ RCON Connection Lost - {config.name}",
                message=(
                    "Connection to Factorio server lost.\n"
                    "Bot will automatically reconnect when server is available.\n\n"
                    "Commands requiring RCON will be unavailable until reconnection."
                ),
            )
            embed.color = EmbedBuilder.COLOR_WARNING

            if send_to_channel:
                await send_to_channel(self.bot, channel_id, embed)
            else:
                # Fallback
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    await channel.send(embed=embed)

            logger.info(
                "rcon_disconnection_notified",
                server_tag=server_tag,
                channel_id=channel_id,
            )
        except Exception as e:
            logger.warning(
                "rcon_disconnection_notification_failed",
                server_tag=server_tag,
                error=str(e),
            )

    async def _notify_rcon_reconnected(self, server_tag: str) -> None:
        """Send notification when RCON reconnects for a specific server."""
        try:
            from .discord_interface import EmbedBuilder  # type: ignore
        except ImportError:
            try:
                from discord_interface import EmbedBuilder  # type: ignore
            except ImportError:
                logger.error("discord_interface_not_available")
                return

        if not self.bot.server_manager:
            return

        try:
            from .bot.helpers import send_to_channel  # type: ignore
        except ImportError:
            try:
                from helpers import send_to_channel  # type: ignore
            except ImportError:
                send_to_channel = None

        try:
            config = self.bot.server_manager.get_config(server_tag)
            channel_id = config.event_channel_id

            if not channel_id:
                logger.debug(
                    "skip_rcon_reconnect_notification_no_channel", server_tag=server_tag
                )
                return

            state = self.rcon_server_states.get(server_tag, {})
            last_connected = state.get("last_connected")

            downtime_msg = ""
            if isinstance(last_connected, datetime):
                downtime = datetime.now(timezone.utc) - last_connected
                minutes = int(downtime.total_seconds() / 60)
                if minutes > 0:
                    downtime_msg = (
                        f"\nDowntime: ~{minutes} minute{'s' if minutes != 1 else ''}"
                    )

            embed = EmbedBuilder.info_embed(
                title=f"✅ RCON Reconnected - {config.name}",
                message=(
                    f"Successfully reconnected to Factorio server!{downtime_msg}\n\n"
                    "All bot commands are now fully operational."
                ),
            )
            embed.color = EmbedBuilder.COLOR_SUCCESS

            if send_to_channel:
                await send_to_channel(self.bot, channel_id, embed)
            else:
                # Fallback
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    await channel.send(embed=embed)

            logger.info(
                "rcon_reconnection_notified",
                server_tag=server_tag,
                channel_id=channel_id,
            )
        except Exception as e:
            logger.warning(
                "rcon_reconnection_notification_failed",
                server_tag=server_tag,
                error=str(e),
            )

    def _serialize_rcon_state(self) -> Dict[str, Any]:
        """Serialize RCON server state to a JSON-friendly dict."""
        result: Dict[str, Any] = {}
        for tag, state in self.rcon_server_states.items():
            last_connected = state.get("last_connected")
            result[tag] = {
                "previous_status": state.get("previous_status"),
                "last_connected": (
                    last_connected.isoformat()
                    if isinstance(last_connected, datetime)
                    else None
                ),
            }
        return result

    def _load_rcon_state_from_json(self, data: Dict[str, Any]) -> None:
        """Load RCON server state from JSON-friendly dict."""
        self.rcon_server_states = {}
        for tag, state in data.items():
            last_connected_raw = state.get("last_connected")
            last_connected: Optional[datetime] = None
            if isinstance(last_connected_raw, str):
                try:
                    last_connected = datetime.fromisoformat(last_connected_raw)
                except ValueError:
                    last_connected = None

            self.rcon_server_states[tag] = {
                "previous_status": state.get("previous_status"),
                "last_connected": last_connected,
            }
