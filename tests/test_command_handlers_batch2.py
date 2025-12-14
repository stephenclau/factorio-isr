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

"""🔨 LAYER 1 TESTING: Handler-Level Unit Tests for Batch 2

Server Management Command Handlers (Save, Broadcast, Whisper, Whitelist)

**Strategy**: Test handlers in ISOLATION with minimal mocks
- No bot object mocking
- Direct dependency injection via constructor
- Error branch forcing via dependency attributes
- Multi-action dispatch testing for Whitelist handler

**Target Coverage**: 95%+ per handler
**Total Tests**: 16 (4 handlers with specialized patterns)

**Unique Patterns**:
1. SaveCommandHandler: Regex parsing of save names
2. BroadcastCommandHandler: Message escaping for Lua
3. WhisperCommandHandler: Field-based embed construction
4. WhitelistCommandHandler: Multi-action dispatch (5 actions)

**Error Branches Tested**:
1. Rate limited
2. RCON unavailable
3. Exception during execution
4. Action-specific validation (Whitelist)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Optional
import discord

from bot.commands.command_handlers import (
    SaveCommandHandler,
    BroadcastCommandHandler,
    WhisperCommandHandler,
    WhitelistCommandHandler,
    CommandResult,
)


# ════════════════════════════════════════════════════
# MINIMAL MOCK DEPENDENCIES (reused from Batch 1)
# ════════════════════════════════════════════════════

class DummyUserContext:
    """Minimal UserContextProvider implementation for testing."""

    def __init__(
        self,
        server_name: str = "prod-server",
        rcon_client: Optional[MagicMock] = None,
    ):
        self.server_name = server_name
        self.rcon_client = rcon_client

    def get_user_server(self, user_id: int) -> str:
        return "main"

    def get_server_display_name(self, user_id: int) -> str:
        return self.server_name

    def get_rcon_for_user(self, user_id: int) -> Optional[MagicMock]:
        return self.rcon_client


class DummyRateLimiter:
    """Minimal RateLimiter implementation with configurable behavior."""

    def __init__(self, is_limited: bool = False, retry_seconds: int = 30):
        self.is_limited = is_limited
        self.retry_seconds = retry_seconds

    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[int]]:
        return (self.is_limited, self.retry_seconds if self.is_limited else None)


class DummyEmbedBuilder:
    """Minimal EmbedBuilder implementation."""

    COLOR_WARNING = 0xFFA500
    COLOR_SUCCESS = 0x00FF00

    @staticmethod
    def error_embed(message: str) -> discord.Embed:
        """Create error embed."""
        return discord.Embed(
            title="❌ Error",
            description=message,
            color=discord.Color.red(),
        )

    @staticmethod
    def cooldown_embed(retry_seconds: int) -> discord.Embed:
        """Create cooldown embed."""
        return discord.Embed(
            title="⏱️ Rate Limited",
            description=f"Try again in {retry_seconds} seconds",
            color=discord.Color.from_rgb(255, 165, 0),
        )

    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed:
        """Create info embed."""
        return discord.Embed(title=title, description=message)


# ════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════

@pytest.fixture
def mock_interaction():
    """Create mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.name = "TestAdmin"
    return interaction


@pytest.fixture
def mock_rcon_client():
    """Create mock RCON client."""
    rcon = MagicMock()
    rcon.is_connected = True
    rcon.execute = AsyncMock(return_value="")
    return rcon


# ════════════════════════════════════════════════════
# SAVE COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestSaveCommandHandler:
    """Handler-level tests for SaveCommandHandler."""

    @pytest.mark.asyncio
    async def test_save_happy_path_with_name(self, mock_interaction, mock_rcon_client):
        """Test: save command with explicit name succeeds.

        Happy Path:
        - User not rate limited
        - RCON available and connected
        - Named save (e.g., /save MyGame)

        Expected:
        - result.success = True
        - Embed shows save name
        - RCON execute() called with save name
        """
        handler = SaveCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, name="MyGame")

        assert result.success is True
        assert result.embed is not None
        assert "MyGame" in result.embed.description
        mock_rcon_client.execute.assert_called_once()
        assert "MyGame" in mock_rcon_client.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_save_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: save command blocked by rate limit."""
        handler = SaveCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, name="MyGame")

        assert result.success is False
        assert result.error_embed is not None
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_rcon_unavailable(self, mock_interaction):
        """Test: save command fails when RCON unavailable."""
        handler = SaveCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, name="MyGame")

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_save_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: save command handles exception during RCON execution."""
        mock_rcon_client.execute.side_effect = Exception("Disk full")
        handler = SaveCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, name="MyGame")

        assert result.success is False
        assert "Failed to save" in result.error_embed.description
        assert "Disk full" in result.error_embed.description


# ════════════════════════════════════════════════════
# BROADCAST COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestBroadcastCommandHandler:
    """Handler-level tests for BroadcastCommandHandler."""

    @pytest.mark.asyncio
    async def test_broadcast_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: broadcast command succeeds with message.

        Happy Path:
        - User not rate limited
        - RCON available and connected
        - Message with optional special characters

        Expected:
        - result.success = True
        - Embed shows message
        - RCON execute() called with escaped message
        """
        handler = BroadcastCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, message="Server maintenance in 5 minutes")

        assert result.success is True
        assert result.embed is not None
        assert "Server maintenance" in result.embed.description
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: broadcast command blocked by rate limit."""
        handler = BroadcastCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, message="Maintenance")

        assert result.success is False
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_rcon_unavailable(self, mock_interaction):
        """Test: broadcast command fails when RCON unavailable."""
        handler = BroadcastCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, message="Maintenance")

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_broadcast_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: broadcast command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Connection reset")
        handler = BroadcastCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, message="Maintenance")

        assert result.success is False
        assert "Broadcast failed" in result.error_embed.description


# ════════════════════════════════════════════════════
# WHISPER COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestWhisperCommandHandler:
    """Handler-level tests for WhisperCommandHandler."""

    @pytest.mark.asyncio
    async def test_whisper_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: whisper command succeeds with player and message.

        Happy Path:
        - User not rate limited
        - RCON available and connected
        - Valid player name and message

        Expected:
        - result.success = True
        - Embed with player, server, and message fields
        - RCON execute() called
        """
        handler = WhisperCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="PlayerName",
            message="Hello from Discord",
        )

        assert result.success is True
        assert result.embed is not None
        assert "PlayerName" in result.embed.fields[0].value
        assert "Hello from Discord" in result.embed.fields[2].value
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whisper_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: whisper command blocked by rate limit."""
        handler = WhisperCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="PlayerName",
            message="Hello",
        )

        assert result.success is False
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_whisper_rcon_unavailable(self, mock_interaction):
        """Test: whisper command fails when RCON unavailable."""
        handler = WhisperCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="PlayerName",
            message="Hello",
        )

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_whisper_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: whisper command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Player not found")
        handler = WhisperCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="NonexistentPlayer",
            message="Hello",
        )

        assert result.success is False
        assert "Failed to send message" in result.error_embed.description


# ════════════════════════════════════════════════════
# WHITELIST COMMAND HANDLER TESTS (Multi-action dispatch)
# ════════════════════════════════════════════════════

class TestWhitelistCommandHandler:
    """Handler-level tests for WhitelistCommandHandler (multi-action).

    This handler routes to different RCON commands based on action:
    - list: Returns current whitelist
    - enable: Enables whitelist enforcement
    - disable: Disables whitelist enforcement
    - add <player>: Adds player to whitelist
    - remove <player>: Removes player from whitelist
    """

    @pytest.mark.asyncio
    async def test_whitelist_list_action(self, mock_interaction, mock_rcon_client):
        """Test: whitelist list action returns current whitelist."""
        mock_rcon_client.execute.return_value = "Player1\nPlayer2\nPlayer3"
        handler = WhitelistCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, action="list", player=None)

        assert result.success is True
        assert result.embed is not None
        assert "Player1" in result.embed.description
        mock_rcon_client.execute.assert_called_with("/whitelist get")

    @pytest.mark.asyncio
    async def test_whitelist_add_action(self, mock_interaction, mock_rcon_client):
        """Test: whitelist add action adds player to whitelist."""
        mock_rcon_client.execute.return_value = "Player added"
        handler = WhitelistCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, action="add", player="NewPlayer")

        assert result.success is True
        assert result.embed is not None
        assert "NewPlayer" in result.embed.title
        mock_rcon_client.execute.assert_called_with("/whitelist add NewPlayer")

    @pytest.mark.asyncio
    async def test_whitelist_remove_action(self, mock_interaction, mock_rcon_client):
        """Test: whitelist remove action removes player from whitelist."""
        mock_rcon_client.execute.return_value = "Player removed"
        handler = WhitelistCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, action="remove", player="BadPlayer")

        assert result.success is True
        assert result.embed is not None
        assert "BadPlayer" in result.embed.title
        mock_rcon_client.execute.assert_called_with("/whitelist remove BadPlayer")

    @pytest.mark.asyncio
    async def test_whitelist_invalid_action(self, mock_interaction, mock_rcon_client):
        """Test: whitelist with invalid action returns error.

        Error Branch: Invalid action
        - action="invalid"
        - Should return error_embed with valid actions list
        - RCON not called
        """
        handler = WhitelistCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, action="invalid", player=None)

        assert result.success is False
        assert result.error_embed is not None
        assert "Invalid action" in result.error_embed.description
        assert "add, remove, list, enable, disable" in result.error_embed.description
        mock_rcon_client.execute.assert_not_called()


if __name__ == "__main__":
    # Run with: pytest tests/test_command_handlers_batch2.py -v
    # Run with coverage: pytest tests/test_command_handlers_batch2.py --cov=src/bot/commands.command_handlers_batch2 --cov-report=term-missing
    pytest.main(["-v", __file__])
