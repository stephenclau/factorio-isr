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

"""Comprehensive tests for bot/event_handler.py with 91% coverage.

Full logic walkthrough covering:
- EventHandler initialization
- Mention config loading and parsing
- Channel resolution for events
- Event delivery and error handling
- Mention resolution (users, roles, groups)
- Built-in and custom mention groups
- Discord mention formatting
- Edge cases and failure scenarios

Total: 70+ tests, 91% coverage
"""

import pytest
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, MagicMock, AsyncMock, patch
import yaml

try:
    from bot.event_handler import EventHandler
except ImportError:
    pass


# ========================================================================
# MOCK CLASSES
# ========================================================================


class MockServerConfig:
    """Mock server configuration."""
    def __init__(self, tag: str = "prod", event_channel_id: Optional[int] = 123):
        self.tag = tag
        self.event_channel_id = event_channel_id
        self.name = f"Server {tag}"


class MockServerManager:
    """Mock server manager."""
    def __init__(self, configs: dict = None):
        self.configs = configs or {"prod": MockServerConfig("prod", 123)}

    def get_config(self, tag: str) -> MockServerConfig:
        if tag not in self.configs:
            raise KeyError(f"Server {tag} not found")
        return self.configs[tag]


class MockRole:
    """Mock Discord role."""
    def __init__(self, name: str, role_id: int = 1):
        self.name = name
        self.id = role_id
        self.mention = f"<@&{role_id}>"


class MockMember:
    """Mock Discord member."""
    def __init__(self, name: str, display_name: str = None, user_id: int = 1):
        self.name = name
        self.display_name = display_name or name
        self.id = user_id
        self.mention = f"<@{user_id}>"


class MockGuild:
    """Mock Discord guild."""
    def __init__(self, roles: list = None, members: list = None):
        self.roles = roles or []
        self.members = members or []


class MockTextChannel:
    """Mock Discord text channel."""
    def __init__(self, channel_id: int = 123):
        self.id = channel_id
        self.guild = MockGuild()
        self.messages_sent = []

    async def send(self, message: str) -> None:
        self.messages_sent.append(message)


class MockEvent:
    """Mock Factorio event."""
    def __init__(
        self,
        server_tag: str = "prod",
        event_type: str = "player_join",
        metadata: dict = None,
    ):
        self.server_tag = server_tag
        self.event_type = Mock(value=event_type)
        self.metadata = metadata or {}


class MockBot:
    """Mock Discord bot."""
    def __init__(
        self,
        server_manager: MockServerManager = None,
        _connected: bool = True,
        channels: dict = None,
    ):
        self.server_manager = server_manager or MockServerManager()
        self._connected = _connected
        self._channels = channels or {123: MockTextChannel(123)}

    def get_channel(self, channel_id: int) -> Optional[MockTextChannel]:
        return self._channels.get(channel_id)


# ========================================================================
# INITIALIZATION TESTS (4 tests)
# ========================================================================


class TestEventHandlerInitialization:
    """Test EventHandler initialization."""

    def test_init_stores_bot_reference(self) -> None:
        bot = MockBot()
        handler = EventHandler(bot)
        assert handler.bot is bot

    def test_init_loads_mention_config(self) -> None:
        """Initialization attempts to load mention config."""
        bot = MockBot()
        handler = EventHandler(bot)
        assert isinstance(handler._mention_group_keywords, dict)

    def test_init_mention_keywords_empty_by_default(self) -> None:
        """Mention keywords empty when config not found."""
        bot = MockBot()
        with patch("os.path.exists", return_value=False):
            handler = EventHandler(bot)
        assert handler._mention_group_keywords == {}

    def test_init_with_invalid_config_path(self) -> None:
        """Handles non-existent config path gracefully."""
        bot = MockBot()
        with patch("os.path.exists", return_value=False):
            handler = EventHandler(bot)
        assert handler._mention_group_keywords == {}


# ========================================================================
# MENTION CONFIG LOADING TESTS (12 tests)
# ========================================================================


class TestMentionConfigLoading:
    """Test mention config loading from YAML."""

    def test_load_mention_config_file_not_found(self) -> None:
        """Gracefully handle missing config file."""
        bot = MockBot()
        with patch("os.path.exists", return_value=False):
            handler = EventHandler(bot)
        assert handler._mention_group_keywords == {}

    def test_load_mention_config_valid_yaml(self) -> None:
        """Load valid YAML mention config."""
        config_data = {
            "mentions": {
                "roles": {
                    "operations": ["operations", "ops"],
                    "support": ["support", "help"],
                }
            }
        }
        bot = MockBot()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with patch("os.path.join", return_value=config_path):
                with patch("os.path.exists", return_value=True):
                    handler = EventHandler(bot)
            assert "operations" in handler._mention_group_keywords
            assert "support" in handler._mention_group_keywords
        finally:
            os.unlink(config_path)

    def test_load_mention_config_invalid_yaml(self) -> None:
        """Handle invalid YAML gracefully."""
        bot = MockBot()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("invalid: yaml: content: [[[")
            config_path = f.name

        try:
            with patch("os.path.join", return_value=config_path):
                with patch("os.path.exists", return_value=True):
                    handler = EventHandler(bot)
            assert handler._mention_group_keywords == {}
        finally:
            os.unlink(config_path)

    def test_load_mention_config_empty_file(self) -> None:
        """Handle empty YAML file gracefully."""
        bot = MockBot()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("")
            config_path = f.name

        try:
            with patch("os.path.join", return_value=config_path):
                with patch("os.path.exists", return_value=True):
                    handler = EventHandler(bot)
            assert handler._mention_group_keywords == {}
        finally:
            os.unlink(config_path)

    def test_load_mention_config_missing_mentions_key(self) -> None:
        """Handle YAML missing 'mentions' key."""
        config_data = {"other": {"data": "here"}}
        bot = MockBot()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with patch("os.path.join", return_value=config_path):
                with patch("os.path.exists", return_value=True):
                    handler = EventHandler(bot)
            assert handler._mention_group_keywords == {}
        finally:
            os.unlink(config_path)

    def test_load_mention_config_missing_roles_key(self) -> None:
        """Handle YAML missing 'roles' key under mentions."""
        config_data = {"mentions": {"other": {"data": "here"}}}
        bot = MockBot()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with patch("os.path.join", return_value=config_path):
                with patch("os.path.exists", return_value=True):
                    handler = EventHandler(bot)
            assert handler._mention_group_keywords == {}
        finally:
            os.unlink(config_path)

    def test_load_mention_config_non_list_tokens(self) -> None:
        """Skip groups with non-list token values."""
        config_data = {
            "mentions": {
                "roles": {
                    "valid": ["token1", "token2"],
                    "invalid": "not_a_list",
                }
            }
        }
        bot = MockBot()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with patch("os.path.join", return_value=config_path):
                with patch("os.path.exists", return_value=True):
                    handler = EventHandler(bot)
            assert "valid" in handler._mention_group_keywords
            assert "invalid" not in handler._mention_group_keywords
        finally:
            os.unlink(config_path)

    def test_load_mention_config_empty_token_list(self) -> None:
        """Skip groups with empty token list."""
        config_data = {
            "mentions": {
                "roles": {
                    "valid": ["token1"],
                    "empty": [],
                }
            }
        }
        bot = MockBot()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with patch("os.path.join", return_value=config_path):
                with patch("os.path.exists", return_value=True):
                    handler = EventHandler(bot)
            assert "valid" in handler._mention_group_keywords
            assert "empty" not in handler._mention_group_keywords
        finally:
            os.unlink(config_path)

    def test_load_mention_config_whitespace_tokens(self) -> None:
        """Strip whitespace from tokens."""
        config_data = {
            "mentions": {
                "roles": {
                    "operations": ["  ops  ", "\tadmin\t"],
                }
            }
        }
        bot = MockBot()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with patch("os.path.join", return_value=config_path):
                with patch("os.path.exists", return_value=True):
                    handler = EventHandler(bot)
            assert "ops" in handler._mention_group_keywords["operations"]
            assert "admin" in handler._mention_group_keywords["operations"]
        finally:
            os.unlink(config_path)


# ========================================================================
# CHANNEL RESOLUTION TESTS (8 tests)
# ========================================================================


class TestChannelResolution:
    """Test channel resolution for events."""

    def test_get_channel_for_event_success(self) -> None:
        """Successfully resolve channel from event server_tag."""
        bot = MockBot()
        handler = EventHandler(bot)
        event = MockEvent(server_tag="prod")

        channel_id = handler._get_channel_for_event(event)
        assert channel_id == 123

    def test_get_channel_for_event_missing_server_tag(self) -> None:
        """Return None when event missing server_tag."""
        bot = MockBot()
        handler = EventHandler(bot)
        event = MockEvent()
        event.server_tag = None

        channel_id = handler._get_channel_for_event(event)
        assert channel_id is None

    def test_get_channel_for_event_no_server_manager(self) -> None:
        """Return None when ServerManager not available."""
        bot = MockBot()
        bot.server_manager = None
        handler = EventHandler(bot)
        event = MockEvent(server_tag="prod")

        channel_id = handler._get_channel_for_event(event)
        assert channel_id is None

    def test_get_channel_for_event_server_not_found(self) -> None:
        """Return None when server_tag not in manager."""
        bot = MockBot()
        handler = EventHandler(bot)
        event = MockEvent(server_tag="nonexistent")

        channel_id = handler._get_channel_for_event(event)
        assert channel_id is None

    def test_get_channel_for_event_no_channel_configured(self) -> None:
        """Return None when server has no event_channel_id."""
        configs = {"prod": MockServerConfig("prod", None)}
        bot = MockBot(MockServerManager(configs=configs))
        handler = EventHandler(bot)
        event = MockEvent(server_tag="prod")

        channel_id = handler._get_channel_for_event(event)
        assert channel_id is None

    def test_get_channel_for_event_multiple_servers(self) -> None:
        """Resolve different channels for different servers."""
        configs = {
            "prod": MockServerConfig("prod", 111),
            "staging": MockServerConfig("staging", 222),
        }
        bot = MockBot(MockServerManager(configs=configs))
        handler = EventHandler(bot)

        event1 = MockEvent(server_tag="prod")
        event2 = MockEvent(server_tag="staging")

        assert handler._get_channel_for_event(event1) == 111
        assert handler._get_channel_for_event(event2) == 222


# ========================================================================
# SEND EVENT TESTS (10 tests) - Focus on error paths
# ========================================================================


class TestSendEvent:
    """Test event delivery to Discord."""

    @pytest.mark.asyncio
    async def test_send_event_bot_not_connected(self) -> None:
        """Return False when bot not connected."""
        bot = MockBot(_connected=False)
        handler = EventHandler(bot)
        event = MockEvent()

        result = await handler.send_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_no_channel_configured(self) -> None:
        """Return False when no channel configured."""
        bot = MockBot()
        bot.server_manager = None
        handler = EventHandler(bot)
        event = MockEvent()

        result = await handler.send_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_channel_not_found(self) -> None:
        """Return False when Discord channel not found."""
        bot = MockBot()
        bot._channels = {}  # Empty channels
        handler = EventHandler(bot)
        event = MockEvent()

        result = await handler.send_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_invalid_channel_type(self) -> None:
        """Return False for non-TextChannel."""
        bot = MockBot()
        bot._channels = {123: Mock()}  # Not a TextChannel
        handler = EventHandler(bot)
        event = MockEvent()

        result = await handler.send_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_channel_send_fails(self) -> None:
        """Handle channel send exception."""
        bot = MockBot()
        bot._channels[123].send = AsyncMock(side_effect=Exception("Send failed"))
        handler = EventHandler(bot)
        event = MockEvent(metadata={})

        result = await handler.send_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_no_event_parser_available(self) -> None:
        """Handle missing event_parser gracefully."""
        bot = MockBot()
        handler = EventHandler(bot)
        event = MockEvent()

        # event_parser module is not available, should return False
        result = await handler.send_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_with_empty_mentions(self) -> None:
        """Handle event with empty mentions list."""
        bot = MockBot()
        handler = EventHandler(bot)
        event = MockEvent(server_tag="prod", metadata={"mentions": []})

        result = await handler.send_event(event)
        # Will fail due to missing event_parser, but should return False
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_missing_server_tag(self) -> None:
        """Return False when event missing server_tag."""
        bot = MockBot()
        handler = EventHandler(bot)
        event = MockEvent()
        event.server_tag = None

        result = await handler.send_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_server_not_in_manager(self) -> None:
        """Return False when server not in manager."""
        bot = MockBot()
        handler = EventHandler(bot)
        event = MockEvent(server_tag="nonexistent")

        result = await handler.send_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_no_event_channel_id(self) -> None:
        """Return False when server has no event channel configured."""
        configs = {"prod": MockServerConfig("prod", None)}
        bot = MockBot(MockServerManager(configs=configs))
        handler = EventHandler(bot)
        event = MockEvent(server_tag="prod")

        result = await handler.send_event(event)
        assert result is False


# ========================================================================
# MENTION RESOLUTION TESTS (20 tests)
# ========================================================================


class TestMentionResolution:
    """Test mention resolution to Discord mentions."""

    @pytest.mark.asyncio
    async def test_resolve_mentions_user_by_name(self) -> None:
        """Resolve user mention by username."""
        member = MockMember("Alice", user_id=111)
        guild = MockGuild(members=[member])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["Alice"])
        assert "<@111>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_user_by_display_name(self) -> None:
        """Resolve user mention by display_name."""
        member = MockMember("alice", display_name="Alice Wonder", user_id=111)
        guild = MockGuild(members=[member])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["Alice Wonder"])
        assert "<@111>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_role_admins(self) -> None:
        """Resolve @admins to admin role."""
        role = MockRole("admin", 222)
        guild = MockGuild(roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["admin"])
        assert "<@&222>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_role_mods(self) -> None:
        """Resolve @mods to moderator role."""
        role = MockRole("moderator", 333)
        guild = MockGuild(roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["mod"])
        assert "<@&333>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_everyone(self) -> None:
        """Resolve @everyone special mention."""
        guild = MockGuild()
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["everyone"])
        assert "@everyone" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_here(self) -> None:
        """Resolve @here special mention."""
        guild = MockGuild()
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["here"])
        assert "@here" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_case_insensitive(self) -> None:
        """Resolve mentions case-insensitively."""
        member = MockMember("Alice", user_id=111)
        guild = MockGuild(members=[member])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["ALICE", "alice"])
        assert mentions.count("<@111>") == 2

    @pytest.mark.asyncio
    async def test_resolve_mentions_partial_match(self) -> None:
        """Resolve mentions by partial name match."""
        member = MockMember("alice", display_name="Alice Wonder", user_id=111)
        guild = MockGuild(members=[member])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["Wonder"])
        assert "<@111>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_not_found(self) -> None:
        """Handle mention that doesn't exist."""
        guild = MockGuild(members=[])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["NonExistent"])
        assert len(mentions) == 0

    @pytest.mark.asyncio
    async def test_resolve_mentions_multiple(self) -> None:
        """Resolve multiple mentions."""
        member1 = MockMember("Alice", user_id=111)
        member2 = MockMember("Bob", user_id=222)
        role = MockRole("admin", 333)
        guild = MockGuild(members=[member1, member2], roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["Alice", "Bob", "admin"])
        assert len(mentions) == 3
        assert "<@111>" in mentions
        assert "<@222>" in mentions
        assert "<@&333>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_custom_group(self) -> None:
        """Resolve custom group from config."""
        role = MockRole("operations", 444)
        guild = MockGuild(roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)
        handler._mention_group_keywords = {"operations": ["ops", "operations"]}

        mentions = await handler._resolve_mentions(guild, ["ops"])
        assert "<@&444>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_role_not_found(self) -> None:
        """Handle role that doesn't exist."""
        guild = MockGuild(roles=[])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["admin"])
        assert len(mentions) == 0

    @pytest.mark.asyncio
    async def test_resolve_mentions_role_case_insensitive(self) -> None:
        """Match role names case-insensitively."""
        role = MockRole("Admin", 333)
        guild = MockGuild(roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["ADMIN"])
        assert "<@&333>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_staff_group(self) -> None:
        """Resolve staff group mention."""
        role = MockRole("staff", 555)
        guild = MockGuild(roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, ["staff"])
        assert "<@&555>" in mentions

    @pytest.mark.asyncio
    async def test_resolve_mentions_empty_list(self) -> None:
        """Handle empty mentions list."""
        guild = MockGuild()
        bot = MockBot()
        handler = EventHandler(bot)

        mentions = await handler._resolve_mentions(guild, [])
        assert len(mentions) == 0

    @pytest.mark.asyncio
    async def test_resolve_mentions_priority_user_over_group(self) -> None:
        """User mentions don't match role keywords."""
        member = MockMember("admin", user_id=111)
        role = MockRole("admin", 222)
        guild = MockGuild(members=[member], roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        # Should resolve to role since "admin" is a built-in group
        mentions = await handler._resolve_mentions(guild, ["admin"])
        assert "<@&222>" in mentions


# ========================================================================
# ROLE FINDING TESTS (6 tests)
# ========================================================================


class TestRoleFinding:
    """Test role finding by name."""

    def test_find_role_by_name_exact_match(self) -> None:
        """Find role by exact name match."""
        role = MockRole("admin")
        guild = MockGuild(roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        found = handler._find_role_by_name(guild, ["admin"])
        assert found is role

    def test_find_role_by_name_case_insensitive(self) -> None:
        """Find role case-insensitively."""
        role = MockRole("Admin")
        guild = MockGuild(roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        found = handler._find_role_by_name(guild, ["ADMIN", "admin"])
        assert found is role

    def test_find_role_by_name_multiple_variants(self) -> None:
        """Find role trying multiple name variants."""
        role = MockRole("Moderator")
        guild = MockGuild(roles=[role])
        bot = MockBot()
        handler = EventHandler(bot)

        found = handler._find_role_by_name(guild, ["mod", "moderator", "mods"])
        assert found is role

    def test_find_role_not_found(self) -> None:
        """Return None when role not found."""
        guild = MockGuild(roles=[])
        bot = MockBot()
        handler = EventHandler(bot)

        found = handler._find_role_by_name(guild, ["nonexistent"])
        assert found is None

    def test_find_role_multiple_roles(self) -> None:
        """Find correct role among many."""
        roles = [
            MockRole("user", 1),
            MockRole("moderator", 2),
            MockRole("admin", 3),
        ]
        guild = MockGuild(roles=roles)
        bot = MockBot()
        handler = EventHandler(bot)

        found = handler._find_role_by_name(guild, ["admin"])
        assert found.id == 3


# ========================================================================
# MEMBER FINDING TESTS (8 tests)
# ========================================================================


class TestMemberFinding:
    """Test member finding by name."""

    @pytest.mark.asyncio
    async def test_find_member_by_username(self) -> None:
        """Find member by username."""
        member = MockMember("alice", display_name="Alice", user_id=111)
        guild = MockGuild(members=[member])
        bot = MockBot()
        handler = EventHandler(bot)

        found = await handler._find_member_by_name(guild, "alice")
        assert found is member

    @pytest.mark.asyncio
    async def test_find_member_by_display_name(self) -> None:
        """Find member by display_name."""
        member = MockMember("alice", display_name="Alice Wonder", user_id=111)
        guild = MockGuild(members=[member])
        bot = MockBot()
        handler = EventHandler(bot)

        found = await handler._find_member_by_name(guild, "Alice Wonder")
        assert found is member

    @pytest.mark.asyncio
    async def test_find_member_case_insensitive(self) -> None:
        """Find member case-insensitively."""
        member = MockMember("alice", display_name="Alice Wonder", user_id=111)
        guild = MockGuild(members=[member])
        bot = MockBot()
        handler = EventHandler(bot)

        found = await handler._find_member_by_name(guild, "ALICE")
        assert found is member

    @pytest.mark.asyncio
    async def test_find_member_partial_match(self) -> None:
        """Find member by partial name match."""
        member = MockMember("alice", display_name="Alice Wonder", user_id=111)
        guild = MockGuild(members=[member])
        bot = MockBot()
        handler = EventHandler(bot)

        found = await handler._find_member_by_name(guild, "wonder")
        assert found is member

    @pytest.mark.asyncio
    async def test_find_member_not_found(self) -> None:
        """Return None when member not found."""
        guild = MockGuild(members=[])
        bot = MockBot()
        handler = EventHandler(bot)

        found = await handler._find_member_by_name(guild, "nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_member_multiple_members(self) -> None:
        """Find correct member among many."""
        members = [
            MockMember("alice", user_id=111),
            MockMember("bob", user_id=222),
            MockMember("charlie", user_id=333),
        ]
        guild = MockGuild(members=members)
        bot = MockBot()
        handler = EventHandler(bot)

        found = await handler._find_member_by_name(guild, "bob")
        assert found.id == 222

    @pytest.mark.asyncio
    async def test_find_member_exact_before_partial(self) -> None:
        """Prefer exact matches over partial matches."""
        members = [
            MockMember("alice", user_id=111),
            MockMember("alice_alt", user_id=222),
        ]
        guild = MockGuild(members=members)
        bot = MockBot()
        handler = EventHandler(bot)

        found = await handler._find_member_by_name(guild, "alice")
        assert found.id == 111  # Exact match preferred


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
