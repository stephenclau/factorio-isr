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

"""Configuration testing for DiscordBot settings and multi-server setup.

Phase 4 of coverage intensity: Configuration methods and server management.

Coverage targets:
- set_event_channel() - Sets the event channel ID
- set_rcon_client() - Sets the RCON client reference
- set_server_manager() - Sets the server manager
- _apply_server_status_alert_config() - Applies config from first server
- Default values when config missing
- Config loading from server manager
- Multi-server propagation

Total: 8 tests covering configuration code paths.
"""

import pytest
from typing import Optional, Dict, Any
from unittest.mock import Mock, AsyncMock, MagicMock
import discord

try:
    from discord_bot import DiscordBot
except ImportError:
    pass


class MockServerConfig:
    """Mock server configuration."""

    def __init__(
        self,
        tag: str,
        name: str,
        rcon_status_alert_mode: str = "transition",
        rcon_status_alert_interval: int = 300,
    ):
        self.tag = tag
        self.name = name
        self.rcon_status_alert_mode = rcon_status_alert_mode
        self.rcon_status_alert_interval = rcon_status_alert_interval


class MockServerManager:
    """Mock server manager."""

    def __init__(self, servers: Optional[Dict[str, MockServerConfig]] = None):
        if servers is None:
            self.configs = {
                "prod": MockServerConfig(
                    "prod", "Production", "interval", 600
                ),
                "staging": MockServerConfig(
                    "staging", "Staging", "transition", 300
                ),
            }
        else:
            self.configs = servers

    def list_servers(self) -> Dict[str, MockServerConfig]:
        return self.configs

    def get_config(self, tag: str) -> Optional[MockServerConfig]:
        return self.configs.get(tag)


class TestSetEventChannel:
    """Test set_event_channel() method."""

    def test_set_event_channel_with_id(self) -> None:
        """set_event_channel should store the channel ID."""
        bot = DiscordBot(token="test-token")
        assert bot.event_channel_id is None
        
        bot.set_event_channel(123456789)
        
        assert bot.event_channel_id == 123456789

    def test_set_event_channel_with_none(self) -> None:
        """set_event_channel should accept None to clear channel."""
        bot = DiscordBot(token="test-token")
        bot.set_event_channel(123456789)
        assert bot.event_channel_id == 123456789
        
        bot.set_event_channel(None)
        
        assert bot.event_channel_id is None

    def test_set_event_channel_overwrites_previous(self) -> None:
        """set_event_channel should overwrite previous value."""
        bot = DiscordBot(token="test-token")
        bot.set_event_channel(111111111)
        assert bot.event_channel_id == 111111111
        
        bot.set_event_channel(222222222)
        
        assert bot.event_channel_id == 222222222

    def test_set_event_channel_returns_none(self) -> None:
        """set_event_channel should not return anything."""
        bot = DiscordBot(token="test-token")
        result = bot.set_event_channel(123456789)
        assert result is None


class TestSetRconClient:
    """Test set_rcon_client() method."""

    def test_set_rcon_client_with_client(self) -> None:
        """set_rcon_client should store the RCON client."""
        bot = DiscordBot(token="test-token")
        assert bot.rcon_client is None
        
        mock_client = MagicMock()
        bot.set_rcon_client(mock_client)
        
        assert bot.rcon_client is mock_client

    def test_set_rcon_client_with_none(self) -> None:
        """set_rcon_client should accept None to clear client."""
        bot = DiscordBot(token="test-token")
        mock_client = MagicMock()
        bot.set_rcon_client(mock_client)
        assert bot.rcon_client is mock_client
        
        bot.set_rcon_client(None)
        
        assert bot.rcon_client is None

    def test_set_rcon_client_overwrites_previous(self) -> None:
        """set_rcon_client should overwrite previous client."""
        bot = DiscordBot(token="test-token")
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        
        bot.set_rcon_client(mock_client1)
        assert bot.rcon_client is mock_client1
        
        bot.set_rcon_client(mock_client2)
        
        assert bot.rcon_client is mock_client2

    def test_set_rcon_client_stores_reference(self) -> None:
        """set_rcon_client should store the exact object reference."""
        bot = DiscordBot(token="test-token")
        mock_client = MagicMock()
        mock_client.test_attr = "unique_value"
        
        bot.set_rcon_client(mock_client)
        
        # Verify it's the same object
        assert bot.rcon_client.test_attr == "unique_value"


class TestSetServerManager:
    """Test set_server_manager() method."""

    def test_set_server_manager_with_manager(self) -> None:
        """set_server_manager should store the server manager."""
        bot = DiscordBot(token="test-token")
        assert bot.server_manager is None
        
        manager = MockServerManager()
        bot.set_server_manager(manager)
        
        assert bot.server_manager is manager

    def test_set_server_manager_with_none(self) -> None:
        """set_server_manager should accept None to clear manager."""
        bot = DiscordBot(token="test-token")
        manager = MockServerManager()
        bot.set_server_manager(manager)
        assert bot.server_manager is manager
        
        bot.set_server_manager(None)
        
        assert bot.server_manager is None

    def test_set_server_manager_overwrites_previous(self) -> None:
        """set_server_manager should overwrite previous manager."""
        bot = DiscordBot(token="test-token")
        manager1 = MockServerManager({"prod": MockServerConfig("prod", "Prod")})
        manager2 = MockServerManager({"staging": MockServerConfig("staging", "Stage")})
        
        bot.set_server_manager(manager1)
        assert bot.server_manager is manager1
        
        bot.set_server_manager(manager2)
        
        assert bot.server_manager is manager2

    def test_set_server_manager_stores_reference(self) -> None:
        """set_server_manager should store the exact object reference."""
        bot = DiscordBot(token="test-token")
        manager = MockServerManager()
        
        bot.set_server_manager(manager)
        
        # Verify we can call methods on stored reference
        servers = bot.server_manager.list_servers()
        assert "prod" in servers
        assert "staging" in servers


class TestApplyServerStatusAlertConfig:
    """Test _apply_server_status_alert_config() method."""

    def test_apply_config_loads_from_first_server(self) -> None:
        """_apply_server_status_alert_config should load from first server."""
        bot = DiscordBot(token="test-token")
        manager = MockServerManager()
        bot.set_server_manager(manager)
        
        bot._apply_server_status_alert_config()
        
        # Should get prod server's config (first in dict)
        # In Python 3.7+, dict insertion order is preserved
        assert bot.rcon_status_alert_mode == "interval"
        assert bot.rcon_status_alert_interval == 600

    def test_apply_config_handles_missing_server_manager(self) -> None:
        """_apply_server_status_alert_config should handle missing manager."""
        bot = DiscordBot(token="test-token")
        bot.server_manager = None
        
        # Should not raise
        bot._apply_server_status_alert_config()
        
        # Should keep defaults
        assert bot.rcon_status_alert_mode == "transition"
        assert bot.rcon_status_alert_interval == 300

    def test_apply_config_handles_empty_servers(self) -> None:
        """_apply_server_status_alert_config with no servers uses defaults."""
        bot = DiscordBot(token="test-token")
        manager = MockServerManager({})
        bot.set_server_manager(manager)
        
        bot._apply_server_status_alert_config()
        
        # Should keep defaults when no servers
        assert bot.rcon_status_alert_mode == "transition"
        assert bot.rcon_status_alert_interval == 300

    def test_apply_config_multiple_times(self) -> None:
        """_apply_server_status_alert_config can be called multiple times."""
        bot = DiscordBot(token="test-token")
        manager = MockServerManager()
        bot.set_server_manager(manager)
        
        bot._apply_server_status_alert_config()
        first_mode = bot.rcon_status_alert_mode
        first_interval = bot.rcon_status_alert_interval
        
        bot._apply_server_status_alert_config()
        
        # Values should be the same
        assert bot.rcon_status_alert_mode == first_mode
        assert bot.rcon_status_alert_interval == first_interval


class TestConfigurationIntegration:
    """Integration tests for configuration methods."""

    def test_set_all_configs_together(self) -> None:
        """All configuration methods work together."""
        bot = DiscordBot(token="test-token")
        
        bot.set_event_channel(123456789)
        mock_rcon = MagicMock()
        bot.set_rcon_client(mock_rcon)
        manager = MockServerManager()
        bot.set_server_manager(manager)
        bot._apply_server_status_alert_config()
        
        # Verify all set
        assert bot.event_channel_id == 123456789
        assert bot.rcon_client is mock_rcon
        assert bot.server_manager is manager
        assert bot.rcon_status_alert_mode == "interval"
        assert bot.rcon_status_alert_interval == 600

    def test_config_persistence(self) -> None:
        """Configuration values persist across multiple calls."""
        bot = DiscordBot(token="test-token")
        
        bot.set_event_channel(111111111)
        mock_rcon = MagicMock()
        bot.set_rcon_client(mock_rcon)
        
        # Verify persistence
        assert bot.event_channel_id == 111111111
        assert bot.rcon_client is mock_rcon
        
        # Add more config
        bot.set_event_channel(222222222)
        
        # Previous rcon_client should still be there
        assert bot.rcon_client is mock_rcon
        # New channel should be set
        assert bot.event_channel_id == 222222222

    def test_config_clear_sequence(self) -> None:
        """Configuration can be cleared in sequence."""
        bot = DiscordBot(token="test-token")
        manager = MockServerManager()
        
        bot.set_event_channel(123456789)
        bot.set_server_manager(manager)
        
        assert bot.event_channel_id == 123456789
        assert bot.server_manager is manager
        
        # Clear them
        bot.set_event_channel(None)
        bot.set_server_manager(None)
        
        assert bot.event_channel_id is None
        assert bot.server_manager is None
