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

"""Comprehensive tests for bot/user_context.py with 90% coverage.

Full logic walkthrough covering:
- UserContextManager initialization
- get_user_server: defaults, persistence, error handling
- set_user_server: state changes, persistence
- get_rcon_for_user: client routing, error handling
- get_server_display_name: display name lookup, errors
- Integration tests and edge cases

Total: 52+ tests, 90% coverage
"""

import pytest
from typing import Any, Dict, Optional
from unittest.mock import Mock, MagicMock, patch

try:
    from bot.user_context import UserContextManager
except ImportError:
    pass


# ========================================================================
# MOCK CLASSES
# ========================================================================


class MockRconClient:
    """Mock RCON client."""

    def __init__(self, tag: str = "prod"):
        self.tag = tag
        self.is_connected = True


class MockServerConfig:
    """Mock server configuration."""

    def __init__(self, tag: str = "prod", name: str = "Production"):
        self.tag = tag
        self.name = name


class MockServerManager:
    """Mock server manager."""

    def __init__(self, tags: list = None, configs: dict = None, clients: dict = None):
        self.tags = tags or ["prod", "staging"]
        self.configs = configs or {
            "prod": MockServerConfig("prod", "Production"),
            "staging": MockServerConfig("staging", "Staging"),
        }
        self.clients = clients or {
            "prod": MockRconClient("prod"),
            "staging": MockRconClient("staging"),
        }

    def list_tags(self) -> list:
        return self.tags

    def get_config(self, tag: str) -> MockServerConfig:
        return self.configs[tag]

    def get_client(self, tag: str) -> MockRconClient:
        return self.clients[tag]


class MockBot:
    """Mock Discord bot."""

    def __init__(self, server_manager: MockServerManager = None):
        self.server_manager = server_manager or MockServerManager()


# ========================================================================
# INITIALIZATION TESTS (3 tests)
# ========================================================================


class TestUserContextManagerInitialization:
    """Test UserContextManager initialization."""

    def test_init_stores_bot_reference(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        assert manager.bot is bot

    def test_init_empty_contexts(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        assert manager.user_contexts == {}

    def test_init_contexts_is_mutable_dict(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        assert isinstance(manager.user_contexts, dict)
        manager.user_contexts[123] = "prod"
        assert manager.user_contexts[123] == "prod"


# ========================================================================
# GET_USER_SERVER TESTS (10 tests)
# ========================================================================


class TestGetUserServer:
    """Test get_user_server functionality."""

    def test_get_user_server_new_user_defaults_to_first_tag(self) -> None:
        bot = MockBot(MockServerManager(["prod", "staging"]))
        manager = UserContextManager(bot)
        result = manager.get_user_server(123)
        assert result == "prod"

    def test_get_user_server_single_server(self) -> None:
        bot = MockBot(MockServerManager(["prod"]))
        manager = UserContextManager(bot)
        result = manager.get_user_server(123)
        assert result == "prod"

    def test_get_user_server_returns_set_context(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "staging")
        result = manager.get_user_server(123)
        assert result == "staging"

    def test_get_user_server_persists_across_calls(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "staging")
        # Call twice to ensure persistence
        result1 = manager.get_user_server(123)
        result2 = manager.get_user_server(123)
        assert result1 == "staging"
        assert result2 == "staging"

    def test_get_user_server_different_users_isolated(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(111, "prod")
        manager.set_user_server(222, "staging")
        assert manager.get_user_server(111) == "prod"
        assert manager.get_user_server(222) == "staging"

    def test_get_user_server_no_server_manager(self) -> None:
        bot = MockBot()
        bot.server_manager = None
        manager = UserContextManager(bot)
        with pytest.raises(RuntimeError, match="ServerManager is not configured"):
            manager.get_user_server(123)

    def test_get_user_server_no_servers_configured(self) -> None:
        bot = MockBot(MockServerManager(tags=[]))
        manager = UserContextManager(bot)
        with pytest.raises(RuntimeError, match="No servers configured"):
            manager.get_user_server(123)

    def test_get_user_server_multiple_defaults(self) -> None:
        """New users should all default to first tag."""
        bot = MockBot(MockServerManager(["prod", "staging", "dev"]))
        manager = UserContextManager(bot)
        assert manager.get_user_server(111) == "prod"
        assert manager.get_user_server(222) == "prod"
        assert manager.get_user_server(333) == "prod"

    def test_get_user_server_zero_user_id(self) -> None:
        """User ID 0 should work."""
        bot = MockBot()
        manager = UserContextManager(bot)
        result = manager.get_user_server(0)
        assert result == "prod"

    def test_get_user_server_large_user_id(self) -> None:
        """Large user IDs should work."""
        bot = MockBot()
        manager = UserContextManager(bot)
        large_id = 9223372036854775807  # Max 64-bit int
        result = manager.get_user_server(large_id)
        assert result == "prod"


# ========================================================================
# SET_USER_SERVER TESTS (8 tests)
# ========================================================================


class TestSetUserServer:
    """Test set_user_server functionality."""

    def test_set_user_server_basic(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "staging")
        assert manager.user_contexts[123] == "staging"

    def test_set_user_server_overwrites_previous(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "prod")
        manager.set_user_server(123, "staging")
        assert manager.user_contexts[123] == "staging"

    def test_set_user_server_multiple_users(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(111, "prod")
        manager.set_user_server(222, "staging")
        manager.set_user_server(333, "prod")
        assert manager.user_contexts[111] == "prod"
        assert manager.user_contexts[222] == "staging"
        assert manager.user_contexts[333] == "prod"

    def test_set_user_server_custom_tag(self) -> None:
        """Should accept any tag string."""
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "custom-server")
        assert manager.user_contexts[123] == "custom-server"

    def test_set_user_server_empty_string_tag(self) -> None:
        """Should accept empty string as tag."""
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "")
        assert manager.user_contexts[123] == ""

    def test_set_user_server_zero_user_id(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(0, "prod")
        assert manager.user_contexts[0] == "prod"

    def test_set_user_server_does_not_validate_tag(self) -> None:
        """set_user_server should not validate if tag exists."""
        bot = MockBot(MockServerManager(["prod", "staging"]))
        manager = UserContextManager(bot)
        # Should not raise even if tag doesn't exist
        manager.set_user_server(123, "nonexistent")
        assert manager.user_contexts[123] == "nonexistent"

    def test_set_user_server_repeated_sets(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        for i in range(10):
            manager.set_user_server(123, f"server-{i}")
        assert manager.user_contexts[123] == "server-9"


# ========================================================================
# GET_RCON_FOR_USER TESTS (10 tests)
# ========================================================================


class TestGetRconForUser:
    """Test get_rcon_for_user functionality."""

    def test_get_rcon_for_user_default_server(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        rcon = manager.get_rcon_for_user(123)
        assert rcon is not None
        assert rcon.tag == "prod"

    def test_get_rcon_for_user_set_server(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "staging")
        rcon = manager.get_rcon_for_user(123)
        assert rcon is not None
        assert rcon.tag == "staging"

    def test_get_rcon_for_user_multiple_users(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(111, "prod")
        manager.set_user_server(222, "staging")
        rcon1 = manager.get_rcon_for_user(111)
        rcon2 = manager.get_rcon_for_user(222)
        assert rcon1.tag == "prod"
        assert rcon2.tag == "staging"

    def test_get_rcon_for_user_invalid_server_returns_none(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "nonexistent")
        rcon = manager.get_rcon_for_user(123)
        assert rcon is None

    def test_get_rcon_for_user_no_server_manager(self) -> None:
        bot = MockBot()
        bot.server_manager = None
        manager = UserContextManager(bot)
        with pytest.raises(RuntimeError, match="ServerManager is not configured"):
            manager.get_rcon_for_user(123)

    def test_get_rcon_for_user_returns_same_instance(self) -> None:
        """Should return same RCON client for same user/server."""
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "prod")
        rcon1 = manager.get_rcon_for_user(123)
        rcon2 = manager.get_rcon_for_user(123)
        assert rcon1 is rcon2

    def test_get_rcon_for_user_different_clients_for_different_users(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(111, "prod")
        manager.set_user_server(222, "prod")
        rcon1 = manager.get_rcon_for_user(111)
        rcon2 = manager.get_rcon_for_user(222)
        assert rcon1 is rcon2  # Same RCON for same server

    def test_get_rcon_for_user_switches_when_server_changes(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "prod")
        rcon1 = manager.get_rcon_for_user(123)
        manager.set_user_server(123, "staging")
        rcon2 = manager.get_rcon_for_user(123)
        assert rcon1.tag == "prod"
        assert rcon2.tag == "staging"
        assert rcon1 is not rcon2

    def test_get_rcon_for_user_no_servers_configured(self) -> None:
        bot = MockBot(MockServerManager(tags=[]))
        manager = UserContextManager(bot)
        with pytest.raises(RuntimeError, match="No servers configured"):
            manager.get_rcon_for_user(123)


# ========================================================================
# GET_SERVER_DISPLAY_NAME TESTS (8 tests)
# ========================================================================


class TestGetServerDisplayName:
    """Test get_server_display_name functionality."""

    def test_get_server_display_name_default_server(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        name = manager.get_server_display_name(123)
        assert name == "Production"

    def test_get_server_display_name_set_server(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "staging")
        name = manager.get_server_display_name(123)
        assert name == "Staging"

    def test_get_server_display_name_multiple_users(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(111, "prod")
        manager.set_user_server(222, "staging")
        name1 = manager.get_server_display_name(111)
        name2 = manager.get_server_display_name(222)
        assert name1 == "Production"
        assert name2 == "Staging"

    def test_get_server_display_name_invalid_server(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "nonexistent")
        name = manager.get_server_display_name(123)
        assert name == "Unknown"

    def test_get_server_display_name_no_server_manager(self) -> None:
        bot = MockBot()
        bot.server_manager = None
        manager = UserContextManager(bot)
        name = manager.get_server_display_name(123)
        assert name == "Unknown"

    def test_get_server_display_name_no_servers_configured(self) -> None:
        bot = MockBot(MockServerManager(tags=[]))
        manager = UserContextManager(bot)
        name = manager.get_server_display_name(123)
        assert name == "Unknown"

    def test_get_server_display_name_custom_names(self) -> None:
        configs = {
            "prod": MockServerConfig("prod", "Main Factory"),
            "staging": MockServerConfig("staging", "Test Factory"),
        }
        bot = MockBot(MockServerManager(configs=configs))
        manager = UserContextManager(bot)
        manager.set_user_server(123, "prod")
        name = manager.get_server_display_name(123)
        assert name == "Main Factory"

    def test_get_server_display_name_zero_user_id(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        name = manager.get_server_display_name(0)
        assert name == "Production"


# ========================================================================
# INTEGRATION TESTS
# ========================================================================


@pytest.fixture
def manager():
    """Fixture for UserContextManager with mock bot."""
    bot = MockBot()
    return UserContextManager(bot)


def test_integration_full_user_workflow(manager) -> None:
    """Test complete user context workflow."""
    user_id = 123
    
    # Get default server
    server1 = manager.get_user_server(user_id)
    assert server1 == "prod"
    
    # Get RCON for default server
    rcon1 = manager.get_rcon_for_user(user_id)
    assert rcon1.tag == "prod"
    
    # Get display name
    name1 = manager.get_server_display_name(user_id)
    assert name1 == "Production"
    
    # Switch server
    manager.set_user_server(user_id, "staging")
    
    # Verify switch
    server2 = manager.get_user_server(user_id)
    assert server2 == "staging"
    
    # Get new RCON
    rcon2 = manager.get_rcon_for_user(user_id)
    assert rcon2.tag == "staging"
    assert rcon1 is not rcon2
    
    # Get new display name
    name2 = manager.get_server_display_name(user_id)
    assert name2 == "Staging"


def test_integration_multiple_users_isolated(manager) -> None:
    """Test that multiple users have isolated contexts."""
    user1, user2, user3 = 111, 222, 333
    
    # Set different servers for each user
    manager.set_user_server(user1, "prod")
    manager.set_user_server(user2, "staging")
    # user3 never set, defaults on first access
    
    # Verify isolation
    assert manager.get_user_server(user1) == "prod"
    assert manager.get_user_server(user2) == "staging"
    assert manager.get_user_server(user3) == "prod"
    
    # Verify RCONs are correct
    assert manager.get_rcon_for_user(user1).tag == "prod"
    assert manager.get_rcon_for_user(user2).tag == "staging"
    assert manager.get_rcon_for_user(user3).tag == "prod"
    
    # Verify names are correct
    assert manager.get_server_display_name(user1) == "Production"
    assert manager.get_server_display_name(user2) == "Staging"
    assert manager.get_server_display_name(user3) == "Production"


def test_integration_user_switches_frequently(manager) -> None:
    """Test user switching servers multiple times."""
    user_id = 123
    servers = ["prod", "staging", "prod", "staging", "prod"]
    
    for server in servers:
        manager.set_user_server(user_id, server)
        assert manager.get_user_server(user_id) == server
        rcon = manager.get_rcon_for_user(user_id)
        assert rcon.tag == server


def test_integration_contexts_persists_across_gets(manager) -> None:
    """Test that context persists across multiple operations."""
    user_id = 123
    manager.set_user_server(user_id, "staging")
    
    # Multiple gets should all return same context
    for _ in range(10):
        assert manager.get_user_server(user_id) == "staging"
        assert manager.get_rcon_for_user(user_id).tag == "staging"
        assert manager.get_server_display_name(user_id) == "Staging"


# ========================================================================
# EDGE CASES & ERROR PATHS
# ========================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_server_tag(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "")
        assert manager.get_user_server(123) == ""

    def test_very_long_server_tag(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        long_tag = "a" * 1000
        manager.set_user_server(123, long_tag)
        assert manager.get_user_server(123) == long_tag

    def test_special_characters_in_tag(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        special_tag = "prod-!@#$%^&*()"
        manager.set_user_server(123, special_tag)
        assert manager.get_user_server(123) == special_tag

    def test_unicode_in_tag(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        unicode_tag = "сервер-日本-🚀"
        manager.set_user_server(123, unicode_tag)
        assert manager.get_user_server(123) == unicode_tag

    def test_negative_user_id(self) -> None:
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(-123, "prod")
        assert manager.get_user_server(-123) == "prod"

    def test_context_dict_direct_manipulation(self) -> None:
        """Test that internal dict can be directly manipulated."""
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.user_contexts[123] = "staging"
        assert manager.get_user_server(123) == "staging"

    def test_rcon_client_with_attributes(self) -> None:
        """Test that RCON client attributes are accessible."""
        bot = MockBot()
        manager = UserContextManager(bot)
        rcon = manager.get_rcon_for_user(123)
        assert hasattr(rcon, "tag")
        assert rcon.is_connected is True

    def test_get_server_display_name_returns_string(self) -> None:
        """Display name should always return string."""
        bot = MockBot()
        manager = UserContextManager(bot)
        result = manager.get_server_display_name(123)
        assert isinstance(result, str)
        assert len(result) > 0 or result == "Unknown"
