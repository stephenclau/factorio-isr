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
Multi-server RCON management for Factorio ISR.

Manages multiple RconClient instances, their stats collectors, and alert monitors.
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, TYPE_CHECKING, Any

import structlog

try:
    from .config import ServerConfig
    from .rcon_client import RconClient, RconStatsCollector, RconAlertMonitor
except ImportError:
    from config import ServerConfig
    from rcon_client import RconClient, RconStatsCollector, RconAlertMonitor

if TYPE_CHECKING:
    from discord_interface import DiscordInterface  # Use interface, not bot

logger = structlog.get_logger()


class ServerManager:
    """Manages multiple Factorio server RCON connections with stats and alerts."""

    def __init__(self, discord_interface: "DiscordInterface"):
        """
        Initialize server manager.

        Args:
            discord_interface: Discord interface (bot or webhook) for stats posting
        """
        self.discord_interface = discord_interface
        self.servers: Dict[str, ServerConfig] = {}  # {tag: ServerConfig}
        self.clients: Dict[str, RconClient] = {}  # {tag: RconClient}
        self.stats_collectors: Dict[str, RconStatsCollector] = {}  # {tag: Collector}
        self.alert_monitors: Dict[str, RconAlertMonitor] = {}  # {tag: AlertMonitor}

        logger.info("server_manager_initialized")

    async def add_server(self, config: ServerConfig, defer_stats: bool = False) -> None:
        """
        Add and connect a new server.

        Args:
            config: Server configuration
            defer_stats: If True, don't start stats collectors yet (call start_stats_for_server later)

        Raises:
            ValueError: If tag already exists
            ConnectionError: If RCON connection fails
        """
        if config.tag in self.clients:
            raise ValueError(f"Server '{config.tag}' already exists")

        logger.info(
            "adding_server",
            tag=config.tag,
            name=config.name,
            host=config.rcon_host,
            port=config.rcon_port,
            defer_stats=defer_stats
        )

        try:
            # Create and start RCON client with context from config/servers.yml
            client = RconClient(
                host=config.rcon_host,
                port=config.rcon_port,
                password=config.rcon_password,
            ).use_context(
                server_name=config.name,
                server_tag=config.tag,
            )

            await client.start()

            # Store server config and client
            self.servers[config.tag] = config
            self.clients[config.tag] = client

            # Start stats collectors immediately unless deferred
            if not defer_stats:
                await self.start_stats_for_server(config.tag)

            logger.info(
                "server_added",
                tag=config.tag,
                name=config.name,
                connected=client.is_connected,
                stats_started=not defer_stats
            )

        except Exception as e:
            logger.error(
                "failed_to_add_server",
                tag=config.tag,
                name=config.name,
                error=str(e),
                exc_info=True
            )

            # Cleanup on failure
            if config.tag in self.alert_monitors:
                try:
                    await self.alert_monitors[config.tag].stop()
                except Exception:
                    pass
                del self.alert_monitors[config.tag]

            if config.tag in self.stats_collectors:
                try:
                    await self.stats_collectors[config.tag].stop()
                except Exception:
                    pass
                del self.stats_collectors[config.tag]

            if config.tag in self.clients:
                try:
                    await self.clients[config.tag].stop()
                except Exception:
                    pass
                del self.clients[config.tag]

            if config.tag in self.servers:
                del self.servers[config.tag]

            raise

    async def start_stats_for_server(self, tag: str) -> None:
        """
        Start stats collector and alert monitor for a server.
        
        Used when server was added with defer_stats=True.
        Respects the enable_stats_gather flag for conditional collector startup.

        Args:
            tag: Server tag

        Raises:
            KeyError: If server doesn't exist
            RuntimeError: If stats already started
        """
        if tag not in self.clients:
            raise KeyError(f"Server '{tag}' not found")

        if tag in self.stats_collectors or tag in self.alert_monitors:
            raise RuntimeError(f"Stats/alerts for '{tag}' already started")

        config = self.servers[tag]
        client = self.clients[tag]

        # Create stats collector if enabled and channel configured
        if config.enable_stats_gather and config.event_channel_id:
            # Create a per-server interface bound to this server's channel
            server_interface = self.discord_interface.use_channel(config.event_channel_id)
            
            collector = RconStatsCollector(
                rcon_client=client,
                discord_interface=server_interface,
                interval=config.stats_interval,
                collect_ups=getattr(config, 'collect_ups', True),
                collect_evolution=getattr(config, 'collect_evolution', True),
            )

            await collector.start()
            self.stats_collectors[config.tag] = collector

            logger.info(
                "stats_collector_started",
                tag=config.tag,
                channel_id=config.event_channel_id,
                interval=config.stats_interval,
                ups_enabled=getattr(config, 'collect_ups', True),
                evolution_enabled=getattr(config, 'collect_evolution', True),
            )
        elif not config.enable_stats_gather:
            logger.info(
                "stats_gathering_disabled",
                tag=config.tag,
                server_name=config.name,
                reason="enable_stats_gather=false in servers.yml",
            )

        # Create alert monitor if enabled
        if getattr(config, 'enable_alerts', True):
            # Create a per-server interface bound to this server's channel
            if config.event_channel_id:
                alert_interface = self.discord_interface.use_channel(config.event_channel_id)
            else:
                alert_interface = self.discord_interface
            
            alert_monitor = RconAlertMonitor(
                rcon_client=client,
                discord_interface=alert_interface,
                check_interval=getattr(config, 'alert_check_interval', 60),
                samples_before_alert=getattr(config, 'alert_samples_required', 3),
                ups_warning_threshold=getattr(config, 'ups_warning_threshold', 55.0),
                ups_recovery_threshold=getattr(config, 'ups_recovery_threshold', 58.0),
                alert_cooldown=getattr(config, 'alert_cooldown', 300),
            )

            await alert_monitor.start()
            self.alert_monitors[config.tag] = alert_monitor

            logger.info(
                "alert_monitor_started",
                tag=config.tag,
                channel_id=config.event_channel_id if config.event_channel_id else "global",
                check_interval=getattr(config, 'alert_check_interval', 60),
                threshold=getattr(config, 'ups_warning_threshold', 55.0),
            )

    async def remove_server(self, tag: str) -> None:
        """
        Stop and remove a server.

        Args:
            tag: Server tag to remove

        Raises:
            KeyError: If tag doesn't exist
        """
        if tag not in self.clients:
            raise KeyError(f"Server '{tag}' not found")

        logger.info("removing_server", tag=tag)

        # Stop alert monitor
        if tag in self.alert_monitors:
            try:
                await self.alert_monitors[tag].stop()
                logger.debug("alert_monitor_stopped", tag=tag)
            except Exception as e:
                logger.warning("failed_to_stop_alert_monitor", tag=tag, error=str(e))
            del self.alert_monitors[tag]

        # Stop stats collector
        if tag in self.stats_collectors:
            try:
                await self.stats_collectors[tag].stop()
                logger.debug("stats_collector_stopped", tag=tag)
            except Exception as e:
                logger.warning("failed_to_stop_stats_collector", tag=tag, error=str(e))
            del self.stats_collectors[tag]

        # Stop RCON client
        try:
            await self.clients[tag].stop()
            logger.debug("rcon_client_stopped", tag=tag)
        except Exception as e:
            logger.warning("failed_to_stop_rcon_client", tag=tag, error=str(e))

        # Remove from registry
        del self.clients[tag]
        del self.servers[tag]

        logger.info("server_removed", tag=tag)

    def get_client(self, tag: str) -> RconClient:
        """
        Get RCON client for a specific server.

        Args:
            tag: Server tag

        Returns:
            RconClient instance

        Raises:
            KeyError: If tag doesn't exist
        """
        if tag not in self.clients:
            available = ", ".join(f"'{t}'" for t in self.list_tags())
            raise KeyError(
                f"Server '{tag}' not found. Available: {available or 'none'}"
            )

        return self.clients[tag]

    def get_config(self, tag: str) -> ServerConfig:
        """
        Get server configuration.

        Args:
            tag: Server tag

        Returns:
            ServerConfig instance

        Raises:
            KeyError: If tag doesn't exist
        """
        if tag not in self.servers:
            raise KeyError(f"Server '{tag}' not found")

        return self.servers[tag]

    def get_collector(self, tag: str) -> RconStatsCollector:
        """
        Get stats collector for a specific server.

        Args:
            tag: Server tag

        Returns:
            RconStatsCollector instance

        Raises:
            KeyError: If tag doesn't exist or no collector configured
        """
        if tag not in self.stats_collectors:
            available = ", ".join(f"'{t}'" for t in self.stats_collectors.keys())
            raise KeyError(
                f"Stats collector for '{tag}' not found. "
                f"Available: {available or 'none'}"
            )

        return self.stats_collectors[tag]

    def get_alert_monitor(self, tag: str) -> RconAlertMonitor:
        """
        Get alert monitor for a specific server.

        Args:
            tag: Server tag

        Returns:
            RconAlertMonitor instance

        Raises:
            KeyError: If tag doesn't exist or no monitor configured
        """
        if tag not in self.alert_monitors:
            available = ", ".join(f"'{t}'" for t in self.alert_monitors.keys())
            raise KeyError(
                f"Alert monitor for '{tag}' not found. "
                f"Available: {available or 'none'}"
            )

        return self.alert_monitors[tag]

    def list_tags(self) -> List[str]:
        """
        Get all server tags.

        Returns:
            List of server tags
        """
        return list(self.servers.keys())

    def list_servers(self) -> Dict[str, ServerConfig]:
        """
        Get all servers with their configs.

        Returns:
            Dictionary of {tag: ServerConfig}
        """
        return self.servers.copy()

    def get_status_summary(self) -> Dict[str, bool]:
        """
        Get connection status for all servers.

        Returns:
            Dictionary of {tag: is_connected}
        """
        return {
            tag: client.is_connected
            for tag, client in self.clients.items()
        }

    def get_alert_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Get alert states for all servers.

        Returns:
            Dictionary of {tag: alert_state}
        """
        return {
            tag: monitor.alert_state
            for tag, monitor in self.alert_monitors.items()
        }

    async def stop_all(self) -> None:
        """Stop all servers, collectors, and monitors."""
        logger.info("stopping_all_servers", count=len(self.clients))

        for tag in list(self.clients.keys()):
            try:
                await self.remove_server(tag)
            except Exception as e:
                logger.error("failed_to_remove_server", tag=tag, error=str(e))

        logger.info("all_servers_stopped")
