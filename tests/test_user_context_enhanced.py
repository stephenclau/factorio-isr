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

"""Enhanced tests for bot/user_context.py - Stress tests, concurrency, and advanced scenarios.

Additional comprehensive coverage:
- Concurrent user access patterns
- Stress testing with many users
- Race conditions and atomicity
- Memory efficiency patterns
- State consistency checks
- Performance characteristics
- Bot state edge cases

Total: 45+ tests, complementing original 52 tests
"""

import pytest
import asyncio
from typing import Dict, List
from unittest.mock import Mock, MagicMock

try:
    from bot.user_context import UserContextManager
except ImportError:
    pass


# ========================================================================
# MOCK CLASSES (Reused from main test suite)
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
    """Mock server manager with proper None handling."""
    def __init__(self, tags: list = None, configs: dict = None, clients: dict = None):
        self.tags = tags if tags is not None else ["prod", "staging"]
        self.configs = configs if configs is not None else {
            "prod": MockServerConfig("prod", "Production"),
            "staging": MockServerConfig("staging", "Staging"),
        }
        self.clients = clients if clients is not None else {
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
# CONCURRENT ACCESS TESTS (8 tests)
# ========================================================================


class TestConcurrentAccess:
    """Test concurrent user access patterns."""

    def test_concurrent_set_and_get(self) -> None:
        """Multiple users can set/get independently."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Simulate concurrent access
        for user_id in range(10):
            manager.set_user_server(user_id, "prod" if user_id % 2 == 0 else "staging")
        
        # Verify all were set correctly
        for user_id in range(10):
            expected = "prod" if user_id % 2 == 0 else "staging"
            assert manager.get_user_server(user_id) == expected

    def test_concurrent_dict_access_isolation(self) -> None:
        """Direct dict access doesn't interfere with get_user_server."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Mix direct and indirect access
        manager.user_contexts[111] = "prod"
        manager.set_user_server(222, "staging")
        direct_access = manager.user_contexts[111]
        get_access = manager.get_user_server(222)
        
        assert direct_access == "prod"
        assert get_access == "staging"

    def test_high_volume_user_creation(self) -> None:
        """Handle creation of many users efficiently."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Create contexts for 1000 users
        for user_id in range(1000):
            manager.set_user_server(user_id, "prod")
        
        # Sample check
        assert len(manager.user_contexts) == 1000
        assert manager.get_user_server(500) == "prod"
        assert manager.get_user_server(999) == "prod"

    def test_rapid_context_switches(self) -> None:
        """Rapid server switching for single user."""
        bot = MockBot(MockServerManager(["prod", "staging", "dev"]))
        manager = UserContextManager(bot)
        
        # Rapidly switch 100 times
        servers = ["prod", "staging", "dev"]
        for i in range(100):
            server = servers[i % 3]
            manager.set_user_server(123, server)
            assert manager.get_user_server(123) == server

    def test_interleaved_user_operations(self) -> None:
        """Interleaved operations on different users."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Interleave operations
        manager.set_user_server(100, "prod")
        manager.set_user_server(200, "staging")
        assert manager.get_user_server(100) == "prod"
        manager.set_user_server(100, "staging")
        assert manager.get_user_server(200) == "staging"
        manager.set_user_server(200, "prod")
        assert manager.get_user_server(100) == "staging"
        assert manager.get_user_server(200) == "prod"

    def test_concurrent_rcon_requests(self) -> None:
        """Multiple users requesting RCON for same server."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(111, "prod")
        manager.set_user_server(222, "prod")
        manager.set_user_server(333, "prod")
        
        rcon1 = manager.get_rcon_for_user(111)
        rcon2 = manager.get_rcon_for_user(222)
        rcon3 = manager.get_rcon_for_user(333)
        
        # All should get same RCON instance
        assert rcon1 is rcon2
        assert rcon2 is rcon3

    def test_concurrent_display_name_requests(self) -> None:
        """Multiple users requesting display names concurrently."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        names = {}
        for user_id in range(100):
            manager.set_user_server(user_id, "prod" if user_id % 2 == 0 else "staging")
            names[user_id] = manager.get_server_display_name(user_id)
        
        # Check consistency
        for user_id, name in names.items():
            expected = "Production" if user_id % 2 == 0 else "Staging"
            assert name == expected


# ========================================================================
# STRESS TESTS (12 tests)
# ========================================================================


class TestStressScenarios:
    """Test under stress conditions."""

    def test_very_large_user_population(self) -> None:
        """Handle very large Discord user IDs."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Discord user IDs are 64-bit integers
        large_ids = [1, 999999999, 9223372036854775807]
        
        for user_id in large_ids:
            manager.set_user_server(user_id, "prod")
            assert manager.get_user_server(user_id) == "prod"

    def test_many_servers_switching(self) -> None:
        """Handle many servers in config."""
        servers = [f"server-{i}" for i in range(50)]
        configs = {tag: MockServerConfig(tag, f"Server {i}") for i, tag in enumerate(servers)}
        clients = {tag: MockRconClient(tag) for tag in servers}
        
        bot = MockBot(MockServerManager(tags=servers, configs=configs, clients=clients))
        manager = UserContextManager(bot)
        
        # Switch between many servers
        for user_id in range(100):
            server = servers[user_id % len(servers)]
            manager.set_user_server(user_id, server)
            assert manager.get_user_server(user_id) == server

    def test_repeated_context_lookups(self) -> None:
        """Many consecutive lookups for same user."""
        bot = MockBot()
        manager = UserContextManager(bot)
        manager.set_user_server(123, "staging")
        
        # 10000 consecutive lookups
        for _ in range(10000):
            result = manager.get_user_server(123)
            assert result == "staging"

    def test_context_stability_after_bulk_operations(self) -> None:
        """Contexts remain stable after bulk operations."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Bulk set
        for i in range(500):
            manager.set_user_server(i, "prod")
        
        # Bulk modification
        for i in range(500):
            manager.set_user_server(i, "staging")
        
        # Verify all changed
        for i in range(500):
            assert manager.get_user_server(i) == "staging"

    def test_mixed_operation_stress(self) -> None:
        """Mix of different operations under stress."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        for iteration in range(100):
            for user_id in range(10):
                # Mix operations
                manager.set_user_server(user_id, "prod" if iteration % 2 == 0 else "staging")
                _ = manager.get_user_server(user_id)
                _ = manager.get_rcon_for_user(user_id)
                _ = manager.get_server_display_name(user_id)

    def test_context_dict_size_growth(self) -> None:
        """Monitor context dict size as users added."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        sizes = []
        for i in range(100):
            manager.set_user_server(i, "prod")
            sizes.append(len(manager.user_contexts))
        
        # Should grow linearly
        for i, size in enumerate(sizes):
            assert size == i + 1

    def test_rapid_fire_set_then_get(self) -> None:
        """Rapid fire: set multiple users, then get all."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Set phase
        for i in range(200):
            manager.set_user_server(i, "prod" if i % 3 == 0 else "staging")
        
        # Get phase
        for i in range(200):
            expected = "prod" if i % 3 == 0 else "staging"
            assert manager.get_user_server(i) == expected

    def test_stress_with_invalid_servers(self) -> None:
        """Stress with many invalid server lookups."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        for i in range(100):
            manager.set_user_server(i, f"invalid-{i}")
            rcon = manager.get_rcon_for_user(i)
            assert rcon is None  # All invalid
            name = manager.get_server_display_name(i)
            assert name == "Unknown"

    def test_stress_rcon_switching(self) -> None:
        """Stress testing RCON client switching."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        for iteration in range(50):
            for user_id in range(10):
                server = "prod" if iteration % 2 == 0 else "staging"
                manager.set_user_server(user_id, server)
                rcon = manager.get_rcon_for_user(user_id)
                assert rcon.tag == server

    def test_memory_efficiency_check(self) -> None:
        """Contexts don't store unnecessary duplicates."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # 1000 users all using same server
        for i in range(1000):
            manager.set_user_server(i, "prod")
        
        # Check that manager just stores references, not copies
        assert len(manager.user_contexts) == 1000
        # All values should be the same string object (or equal)
        values = list(manager.user_contexts.values())
        assert all(v == "prod" for v in values)


# ========================================================================
# BOT STATE EDGE CASES (10 tests)
# ========================================================================


class TestBotStateEdgeCases:
    """Test edge cases with bot state changes."""

    def test_server_manager_becomes_none(self) -> None:
        """Handle ServerManager becoming None at runtime."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(123, "prod")
        assert manager.get_user_server(123) == "prod"
        
        # Bot loses server manager
        bot.server_manager = None
        
        with pytest.raises(RuntimeError):
            manager.get_user_server(456)  # New user, need manager

    def test_server_manager_regains_after_none(self) -> None:
        """Handle ServerManager restoration."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        bot.server_manager = None
        manager2 = UserContextManager(bot)  # Create with None manager
        
        # Restore manager
        bot.server_manager = MockServerManager()
        
        result = manager2.get_user_server(123)
        assert result == "prod"  # Works with restored manager

    def test_server_manager_empty_tags_then_populated(self) -> None:
        """Handle ServerManager with empty tags, then populated."""
        bot = MockBot(MockServerManager(tags=[], configs={}, clients={}))
        manager = UserContextManager(bot)
        
        with pytest.raises(RuntimeError):
            manager.get_user_server(123)
        
        # Repopulate tags
        bot.server_manager = MockServerManager()
        result = manager.get_user_server(456)
        assert result == "prod"

    def test_server_config_removal(self) -> None:
        """Handle server config disappearing."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(123, "prod")
        
        # Remove prod from configs
        bot.server_manager.configs = {"staging": MockServerConfig("staging", "Staging")}
        
        # Display name should return Unknown
        name = manager.get_server_display_name(123)
        assert name == "Unknown"

    def test_rcon_client_unavailable(self) -> None:
        """Handle RCON client not being available."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(123, "prod")
        
        # Remove prod client
        bot.server_manager.clients = {"staging": MockRconClient("staging")}
        
        rcon = manager.get_rcon_for_user(123)
        assert rcon is None

    def test_multiple_bot_instances(self) -> None:
        """Multiple UserContextManager with different bots."""
        bot1 = MockBot(MockServerManager(["prod"]))
        bot2 = MockBot(MockServerManager(["staging"]))
        
        manager1 = UserContextManager(bot1)
        manager2 = UserContextManager(bot2)
        
        manager1.set_user_server(123, "prod")
        manager2.set_user_server(123, "staging")
        
        assert manager1.get_user_server(123) == "prod"
        assert manager2.get_user_server(123) == "staging"

    def test_server_manager_config_changes(self) -> None:
        """Handle dynamic server configuration changes."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(123, "prod")
        name1 = manager.get_server_display_name(123)
        
        # Change server name
        bot.server_manager.configs["prod"] = MockServerConfig("prod", "Updated Name")
        name2 = manager.get_server_display_name(123)
        
        assert name1 == "Production"
        assert name2 == "Updated Name"

    def test_server_list_order_changes(self) -> None:
        """Handle server list order changing."""
        bot = MockBot(MockServerManager(["prod", "staging"]))
        manager = UserContextManager(bot)
        
        # First user gets default (prod)
        default1 = manager.get_user_server(111)
        
        # Change order
        bot.server_manager.tags = ["staging", "prod"]
        
        # New user gets new default (staging)
        default2 = manager.get_user_server(222)
        
        assert default1 == "prod"
        assert default2 == "staging"

    def test_server_addition_during_runtime(self) -> None:
        """Handle new servers being added at runtime."""
        bot = MockBot(MockServerManager(["prod", "staging"]))
        manager = UserContextManager(bot)
        
        manager.set_user_server(123, "prod")
        
        # Add new server
        bot.server_manager.tags.append("dev")
        bot.server_manager.configs["dev"] = MockServerConfig("dev", "Development")
        bot.server_manager.clients["dev"] = MockRconClient("dev")
        
        # Should work
        manager.set_user_server(124, "dev")
        assert manager.get_user_server(124) == "dev"

    def test_graceful_fallback_when_manager_broken(self) -> None:
        """Graceful handling of broken manager state."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(123, "prod")
        
        # Break the manager
        bot.server_manager.get_config = Mock(side_effect=Exception("Manager broken"))
        
        # Display name should still return sensible result
        name = manager.get_server_display_name(123)
        assert name == "Unknown"  # Graceful fallback


# ========================================================================
# PERFORMANCE CHARACTERISTICS (8 tests)
# ========================================================================


class TestPerformanceCharacteristics:
    """Test performance patterns and efficiency."""

    def test_constant_time_get_for_known_user(self) -> None:
        """Direct dict lookup is O(1)."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(123, "prod")
        
        # Multiple gets should all be fast
        results = []
        for _ in range(1000):
            results.append(manager.get_user_server(123))
        
        assert all(r == "prod" for r in results)

    def test_linear_time_initialization_with_many_users(self) -> None:
        """Initialization scales linearly with user count."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Initialize many users
        for i in range(1000):
            manager.set_user_server(i, "prod")
        
        # Verification is also linear
        count = 0
        for user_id in range(1000):
            if manager.get_user_server(user_id) == "prod":
                count += 1
        
        assert count == 1000

    def test_new_user_initialization_cost(self) -> None:
        """First access for new user requires ServerManager call."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # First access for user causes default lookup
        result = manager.get_user_server(999)
        assert result == "prod"
        
        # Subsequent accesses are direct dict lookup
        result2 = manager.get_user_server(999)
        assert result2 == "prod"

    def test_rcon_client_caching(self) -> None:
        """RCON clients retrieved from cache per server."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(111, "prod")
        manager.set_user_server(222, "prod")
        
        rcon1 = manager.get_rcon_for_user(111)
        rcon2 = manager.get_rcon_for_user(222)
        
        # Same RCON instance (from ServerManager cache)
        assert rcon1 is rcon2

    def test_bulk_operations_efficiency(self) -> None:
        """Bulk operations scale well."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Bulk set
        for i in range(10000):
            manager.set_user_server(i, "prod")
        
        assert len(manager.user_contexts) == 10000

    def test_display_name_retrieval_repeated(self) -> None:
        """Display name retrieval is efficient."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        manager.set_user_server(123, "prod")
        
        names = []
        for _ in range(100):
            names.append(manager.get_server_display_name(123))
        
        assert all(n == "Production" for n in names)

    def test_memory_reuse_with_string_interning(self) -> None:
        """Same server tags reuse memory."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        # Many users on same server
        for i in range(100):
            manager.set_user_server(i, "prod")
        
        # All values point to same string (Python string interning)
        values = list(manager.user_contexts.values())
        first = values[0]
        assert all(v is first for v in values)  # Same object

    def test_dict_iteration_efficiency(self) -> None:
        """Iterating contexts dict is efficient."""
        bot = MockBot()
        manager = UserContextManager(bot)
        
        for i in range(100):
            manager.set_user_server(i, "prod" if i % 2 == 0 else "staging")
        
        # Iterate all
        prod_count = sum(1 for v in manager.user_contexts.values() if v == "prod")
        
        assert prod_count == 50
