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

"""👇 LAYER 1 TESTING: Handler-Level Unit Tests for Batch 1

Player Management Command Handlers (Kick, Ban, Unban, Mute, Unmute)

**Strategy**: Test handlers in ISOLATION with minimal mocks
- No bot object mocking
- Direct dependency injection via constructor
- Error branch forcing via dependency attributes
- 4 tests per handler: 1 happy path + 3 error branches

**Target Coverage**: 95%+ per handler
**Total Tests**: 20 (5 handlers × 4 tests each)

**Error Branches Tested**:
1. Rate limited (cooldown_embed)
2. RCON unavailable (error_embed: "RCON not available")
3. Exception during execution (error_embed: "Failed to...")
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Optional
import discord

from bot.commands.command_handlers_batch1 import (
    KickCommandHandler,
    BanCommandHandler,
    UnbanCommandHandler,
    MuteCommandHandler,
    UnmuteCommandHandler,
    CommandResult,
)


# ════════════════════════════════════════════════════════════════════════════
# MINIMAL MOCK DEPENDENCIES (Layer 1 Protocol Implementation)
# ════════════════════════════════════════════════════════════════════════════

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
            color=discord.Color.from_rgb(255, 165, 0),  # Orange
        )

    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed:
        """Create info embed."""
        return discord.Embed(title=title, description=message)


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_interaction():
    """Create mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.name = "TestModerator"
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def mock_rcon_client():
    """Create mock RCON client."""
    rcon = MagicMock()
    rcon.is_connected = True
    rcon.execute = AsyncMock(return_value="")
    return rcon


# ════════════════════════════════════════════════════════════════════════════
# KICK COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestKickCommandHandler:
    """Handler-level tests for KickCommandHandler."""

    @pytest.mark.asyncio
    async def test_kick_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: kick command succeeds with valid player and reason.

        Happy Path:
        - User not rate limited
        - RCON available and connected
        - execute() completes successfully

        Expected:
        - result.success = True
        - embed created with player name and server
        - RCON execute() called with correct command
        """
        # Setup
        handler = KickCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        # Execute
        result = await handler.execute(
            mock_interaction,
            player="Spammer",
            reason="Excessive spam",
        )

        # Assert
        assert result.success is True
        assert result.embed is not None
        assert result.error_embed is None
        assert "Spammer" in result.embed.fields[0].value
        assert "prod-server" in result.embed.fields[1].value
        assert "Excessive spam" in result.embed.fields[2].value
        mock_rcon_client.execute.assert_called_once()
        assert "Spammer" in mock_rcon_client.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_kick_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: kick command blocked by rate limit.

        Error Branch 1: Rate Limited
        - is_rate_limited() returns (True, 30)

        Expected:
        - result.success = False
        - error_embed created with cooldown message
        - RCON execute() NOT called
        - ephemeral = True (hidden from others)
        """
        # Setup
        handler = KickCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        # Execute
        result = await handler.execute(
            mock_interaction,
            player="Spammer",
            reason="Excessive spam",
        )

        # Assert
        assert result.success is False
        assert result.error_embed is not None
        assert result.embed is None
        assert result.ephemeral is True
        assert "30" in result.error_embed.description  # Cooldown time
        mock_rcon_client.execute.assert_not_called()  # RCON not called

    @pytest.mark.asyncio
    async def test_kick_rcon_unavailable(self, mock_interaction):
        """Test: kick command fails when RCON unavailable.

        Error Branch 2: RCON Unavailable
        - get_rcon_for_user() returns None

        Expected:
        - result.success = False
        - error_embed created with RCON error message
        - ephemeral = True
        """
        # Setup
        handler = KickCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        # Execute
        result = await handler.execute(
            mock_interaction,
            player="Spammer",
            reason="Excessive spam",
        )

        # Assert
        assert result.success is False
        assert result.error_embed is not None
        assert "RCON not available" in result.error_embed.description
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_kick_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: kick command handles exception during RCON execution.

        Error Branch 3: Exception During Execution
        - rcon.execute() raises exception (timeout, network, etc.)

        Expected:
        - result.success = False
        - error_embed created with failure message
        - Exception caught and logged
        - ephemeral = True
        """
        # Setup
        mock_rcon_client.execute.side_effect = Exception("Connection timeout")
        handler = KickCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        # Execute
        result = await handler.execute(
            mock_interaction,
            player="Spammer",
            reason="Excessive spam",
        )

        # Assert
        assert result.success is False
        assert result.error_embed is not None
        assert "Failed to kick" in result.error_embed.description
        assert "Connection timeout" in result.error_embed.description
        assert result.ephemeral is True


# ════════════════════════════════════════════════════════════════════════════
# BAN COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestBanCommandHandler:
    """Handler-level tests for BanCommandHandler."""

    @pytest.mark.asyncio
    async def test_ban_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: ban command succeeds with valid player and reason."""
        handler = BanCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="Griefer",
            reason="Griefing base",
        )

        assert result.success is True
        assert result.embed is not None
        assert "Griefer" in result.embed.fields[0].value
        assert "Griefing base" in result.embed.fields[2].value
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_ban_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: ban command blocked by rate limit."""
        handler = BanCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="Griefer",
        )

        assert result.success is False
        assert result.error_embed is not None
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_ban_rcon_unavailable(self, mock_interaction):
        """Test: ban command fails when RCON unavailable."""
        handler = BanCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="Griefer",
        )

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_ban_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: ban command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Command failed")
        handler = BanCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="Griefer",
        )

        assert result.success is False
        assert "Failed to ban" in result.error_embed.description
        assert "Command failed" in result.error_embed.description


# ════════════════════════════════════════════════════════════════════════════
# UNBAN COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestUnbanCommandHandler:
    """Handler-level tests for UnbanCommandHandler."""

    @pytest.mark.asyncio
    async def test_unban_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: unban command succeeds for valid player."""
        handler = UnbanCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="ReformedPlayer",
        )

        assert result.success is True
        assert result.embed is not None
        assert "ReformedPlayer" in result.embed.fields[0].value
        assert "✅" in result.embed.title  # Success emoji
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_unban_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: unban command blocked by rate limit."""
        handler = UnbanCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="ReformedPlayer",
        )

        assert result.success is False
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unban_rcon_unavailable(self, mock_interaction):
        """Test: unban command fails when RCON unavailable."""
        handler = UnbanCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="ReformedPlayer",
        )

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_unban_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: unban command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Server error")
        handler = UnbanCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="ReformedPlayer",
        )

        assert result.success is False
        assert "Failed to unban" in result.error_embed.description
        assert "Server error" in result.error_embed.description


# ════════════════════════════════════════════════════════════════════════════
# MUTE COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestMuteCommandHandler:
    """Handler-level tests for MuteCommandHandler."""

    @pytest.mark.asyncio
    async def test_mute_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: mute command succeeds for valid player."""
        handler = MuteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="Chatterer",
        )

        assert result.success is True
        assert result.embed is not None
        assert "Chatterer" in result.embed.fields[0].value
        assert "🔇" in result.embed.title  # Mute emoji
        mock_rcon_client.execute.assert_called_once()
        assert "/mute" in mock_rcon_client.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_mute_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: mute command blocked by rate limit."""
        handler = MuteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="Chatterer",
        )

        assert result.success is False
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_mute_rcon_unavailable(self, mock_interaction):
        """Test: mute command fails when RCON unavailable."""
        handler = MuteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="Chatterer",
        )

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_mute_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: mute command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Mute failed")
        handler = MuteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="Chatterer",
        )

        assert result.success is False
        assert "Failed to mute" in result.error_embed.description
        assert "Mute failed" in result.error_embed.description


# ════════════════════════════════════════════════════════════════════════════
# UNMUTE COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestUnmuteCommandHandler:
    """Handler-level tests for UnmuteCommandHandler."""

    @pytest.mark.asyncio
    async def test_unmute_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: unmute command succeeds for valid player."""
        handler = UnmuteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="FormerMutedPlayer",
        )

        assert result.success is True
        assert result.embed is not None
        assert "FormerMutedPlayer" in result.embed.fields[0].value
        assert "🔊" in result.embed.title  # Unmute emoji
        mock_rcon_client.execute.assert_called_once()
        assert "/unmute" in mock_rcon_client.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_unmute_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: unmute command blocked by rate limit."""
        handler = UnmuteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="FormerMutedPlayer",
        )

        assert result.success is False
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unmute_rcon_unavailable(self, mock_interaction):
        """Test: unmute command fails when RCON unavailable."""
        handler = UnmuteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="FormerMutedPlayer",
        )

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_unmute_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: unmute command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Unmute unavailable")
        handler = UnmuteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(
            mock_interaction,
            player="FormerMutedPlayer",
        )

        assert result.success is False
        assert "Failed to unmute" in result.error_embed.description
        assert "Unmute unavailable" in result.error_embed.description


if __name__ == "__main__":
    # Run with: pytest tests/test_command_handlers_batch1.py -v
    # Run with coverage: pytest tests/test_command_handlers_batch1.py --cov=src/bot/commands.command_handlers_batch1 --cov-report=term-missing
    pytest.main(["-v", __file__])
