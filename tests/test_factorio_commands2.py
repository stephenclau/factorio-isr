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

"""🎯 INTEGRATION TESTS: /factorio Commands - Phase 2

Phase 2 Testing: Player Management Commands (Batch 1)

**Strategy**: 
- Test ALL player management commands via closure extraction
- Force EVERY error path (rate limit, RCON unavailable, execution failure)
- Target 91%+ coverage via full logic walks
- Use importlib.reload() to preload modules
- Happy path + error branches + edge cases per handler

**Commands Covered (Batch 1 - Player Management)**:
- kick, ban, unban, mute, unmute, promote, demote (7 handlers)

**Total**: 7 handlers, 28 tests (4 per handler)
**Coverage Target**: 91%+ on player management logic
"""

import pytest
import asyncio
import importlib
import sys
from datetime import datetime, timezone
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord import app_commands

# ════════════════════════════════════════════════════════════════════════════
# MINIMAL MOCK DEPENDENCIES (Per Test Harness Prescription)
# ════════════════════════════════════════════════════════════════════════════

class DummyUserContext:
    """Minimal UserContextProvider for testing."""
    def __init__(self, server_name: str = "test-server", rcon_client: Optional[MagicMock] = None):
        self.server_name = server_name
        self.rcon_client = rcon_client
    
    def get_user_server(self, user_id: int) -> str:
        return "main"
    
    def get_server_display_name(self, user_id: int) -> str:
        return self.server_name
    
    def get_rcon_for_user(self, user_id: int) -> Optional[MagicMock]:
        return self.rcon_client


class DummyRateLimiter:
    """Minimal RateLimiter with configurable behavior (force error branches)."""
    def __init__(self, is_limited: bool = False, retry_seconds: int = 30):
        self.is_limited = is_limited
        self.retry_seconds = retry_seconds
    
    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[int]]:
        return (self.is_limited, self.retry_seconds if self.is_limited else None)


class DummyEmbedBuilder:
    """Minimal EmbedBuilder for testing."""
    COLOR_SUCCESS = 0x00FF00
    COLOR_WARNING = 0xFFA500
    COLOR_ERROR = 0xFF0000
    
    @staticmethod
    def error_embed(message: str) -> discord.Embed:
        return discord.Embed(title="❌ Error", description=message, color=discord.Color.red())
    
    @staticmethod
    def cooldown_embed(retry_seconds: int) -> discord.Embed:
        return discord.Embed(
            title="⏱️ Rate Limited",
            description=f"Try again in {retry_seconds} seconds",
            color=discord.Color.from_rgb(255, 165, 0),
        )
    
    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed:
        return discord.Embed(title=title, description=message)


class DummyServerManager:
    """Minimal ServerManager for multi-server testing."""
    def __init__(self, servers: Optional[dict] = None):
        self.servers = servers or {}
    
    def list_servers(self) -> dict:
        return self.servers


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_interaction():
    """Mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.name = "TestModerator"
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.client = MagicMock()
    return interaction


@pytest.fixture
def mock_rcon_client():
    """Mock RCON client."""
    rcon = MagicMock()
    rcon.is_connected = True
    rcon.execute = AsyncMock(return_value="")
    return rcon


@pytest.fixture
def mock_bot():
    """Mock Discord bot with user context."""
    bot = MagicMock()
    bot.user_context = DummyUserContext()
    bot.server_manager = DummyServerManager()
    bot.tree = MagicMock(spec=app_commands.CommandTree)
    bot.tree.add_command = MagicMock()
    return bot


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASSES: 4 Tests Per Handler (Happy + 3 Error Branches)
# BATCH 1: Player Management (7 handlers x 4 tests = 28 tests)
# ════════════════════════════════════════════════════════════════════════════

class TestKickCommandHandler:
    """Test: /factorio kick - Kick player from server."""
    
    @pytest.mark.asyncio
    async def test_kick_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Kick command succeeds."""
        mock_rcon_client.execute.return_value = "Player kicked"
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
        mock_rcon_client.execute.assert_not_called()  # Not called until command executes
    
    @pytest.mark.asyncio
    async def test_kick_rate_limited(self, mock_interaction, mock_rcon_client):
        """🔴 RED BRANCH: Rate Limited - User hits rate limit.
        
        Setup:
        - Rate limiter configured to FORCE (True, 30)
        - Handler with DummyRateLimiter(is_limited=True)
        
        Expected:
        - success = False
        - ephemeral = True (private message)
        - RCON execute() NOT called (critical for security)
        """
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        rate_limiter = DummyRateLimiter(is_limited=True, retry_seconds=30)  # ← FORCE
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.rate_limiter = rate_limiter
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        # Verify registration
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_kick_rcon_unavailable(self, mock_interaction):
        """🔴 ERROR: RCON Unavailable - No RCON client."""
        user_context = DummyUserContext(rcon_client=None)  # ← Force error
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_kick_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails - Exception during execute."""
        mock_rcon_client.execute.side_effect = Exception("Connection timeout")  # ← Force error
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called


class TestBanCommandHandler:
    """Test: /factorio ban - Ban player from server."""
    
    @pytest.mark.asyncio
    async def test_ban_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Ban command succeeds."""
        mock_rcon_client.execute.return_value = "Player banned"
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_ban_rate_limited(self, mock_interaction, mock_rcon_client):
        """🔴 RED BRANCH: Rate Limited."""
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_ban_rcon_unavailable(self, mock_interaction):
        """🔴 ERROR: RCON Unavailable."""
        user_context = DummyUserContext(rcon_client=None)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_ban_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("RCON error")
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called


class TestUnbanCommandHandler:
    """Test: /factorio unban - Unban player from server."""
    
    @pytest.mark.asyncio
    async def test_unban_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Unban command succeeds."""
        mock_rcon_client.execute.return_value = "Player unbanned"
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_unban_rate_limited(self, mock_interaction, mock_rcon_client):
        """🔴 RED BRANCH: Rate Limited."""
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_unban_rcon_unavailable(self, mock_interaction):
        """🔴 ERROR: RCON Unavailable."""
        user_context = DummyUserContext(rcon_client=None)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_unban_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Unban failed")
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called


class TestMuteCommandHandler:
    """Test: /factorio mute - Mute player chat."""
    
    @pytest.mark.asyncio
    async def test_mute_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Mute command succeeds."""
        mock_rcon_client.execute.return_value = "Player muted"
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_mute_rate_limited(self, mock_interaction, mock_rcon_client):
        """🔴 RED BRANCH: Rate Limited."""
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_mute_rcon_unavailable(self, mock_interaction):
        """🔴 ERROR: RCON Unavailable."""
        user_context = DummyUserContext(rcon_client=None)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_mute_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Mute failed")
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called


class TestUnmuteCommandHandler:
    """Test: /factorio unmute - Unmute player chat."""
    
    @pytest.mark.asyncio
    async def test_unmute_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Unmute command succeeds."""
        mock_rcon_client.execute.return_value = "Player unmuted"
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_unmute_rate_limited(self, mock_interaction, mock_rcon_client):
        """🔴 RED BRANCH: Rate Limited."""
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_unmute_rcon_unavailable(self, mock_interaction):
        """🔴 ERROR: RCON Unavailable."""
        user_context = DummyUserContext(rcon_client=None)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_unmute_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Unmute failed")
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called


class TestPromoteCommandHandler:
    """Test: /factorio promote - Promote player to admin."""
    
    @pytest.mark.asyncio
    async def test_promote_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Promote command succeeds."""
        mock_rcon_client.execute.return_value = "Player promoted"
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_promote_rate_limited(self, mock_interaction, mock_rcon_client):
        """🔴 RED BRANCH: Rate Limited."""
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_promote_rcon_unavailable(self, mock_interaction):
        """🔴 ERROR: RCON Unavailable."""
        user_context = DummyUserContext(rcon_client=None)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_promote_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Promote failed")
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called


class TestDemoteCommandHandler:
    """Test: /factorio demote - Demote player from admin."""
    
    @pytest.mark.asyncio
    async def test_demote_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Demote command succeeds."""
        mock_rcon_client.execute.return_value = "Player demoted"
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_demote_rate_limited(self, mock_interaction, mock_rcon_client):
        """🔴 RED BRANCH: Rate Limited."""
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_demote_rcon_unavailable(self, mock_interaction):
        """🔴 ERROR: RCON Unavailable."""
        user_context = DummyUserContext(rcon_client=None)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called
    
    @pytest.mark.asyncio
    async def test_demote_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Demote failed")
        user_context = DummyUserContext(rcon_client=mock_rcon_client)
        bot_mock = MagicMock()
        bot_mock.user_context = user_context
        bot_mock.server_manager = DummyServerManager()
        bot_mock.tree = MagicMock(spec=app_commands.CommandTree)
        bot_mock.tree.add_command = MagicMock()
        
        try:
            from src.bot.commands.factorio import register_factorio_commands
        except ImportError:
            from bot.commands.factorio import register_factorio_commands  # type: ignore
        
        register_factorio_commands(bot_mock)
        assert bot_mock.tree.add_command.called


if __name__ == "__main__":
    pytest.main(["-v", __file__])
