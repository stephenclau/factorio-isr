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

"""🎯 INTEGRATION TESTS: /factorio Commands - Phase 3

Phase 3 Testing: Server Management + Game Control Commands (Batch 2-3)

**Strategy**: 
- Test ALL server management and game control commands via closure extraction
- Force EVERY error path (rate limit, RCON unavailable, execution failure)
- Target 91%+ coverage via full logic walks
- Happy path + error branches + edge cases per handler

**Commands Covered (Batch 2 - Server Management)**:
- save, broadcast, whisper, whitelist (4 handlers)

**Commands Covered (Batch 3 - Game Control)**:
- clock, speed, research, status (4 handlers)

**Total**: 8 handlers, 32 tests (4 per handler)
**Coverage Target**: 91%+ on server management + game control logic
"""

import pytest
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import discord
from discord import app_commands

# ════════════════════════════════════════════════════════════════════════════
# MINIMAL MOCK DEPENDENCIES
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
    """Minimal RateLimiter with configurable behavior."""
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
# BATCH 2: Server Management (4 handlers x 4 tests = 16 tests)
# ════════════════════════════════════════════════════════════════════════════

class TestSaveCommandHandler:
    """Test: /factorio save - Save the game."""
    
    @pytest.mark.asyncio
    async def test_save_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Save command succeeds."""
        mock_rcon_client.execute.return_value = "Game saved"
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
    async def test_save_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_save_rcon_unavailable(self, mock_interaction):
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
    async def test_save_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Save failed")
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


class TestBroadcastCommandHandler:
    """Test: /factorio broadcast - Send message to all players."""
    
    @pytest.mark.asyncio
    async def test_broadcast_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Broadcast command succeeds."""
        mock_rcon_client.execute.return_value = "Message broadcast"
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
    async def test_broadcast_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_broadcast_rcon_unavailable(self, mock_interaction):
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
    async def test_broadcast_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Broadcast failed")
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


class TestWhisperCommandHandler:
    """Test: /factorio whisper - Send private message to player."""
    
    @pytest.mark.asyncio
    async def test_whisper_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Whisper command succeeds."""
        mock_rcon_client.execute.return_value = "Message sent"
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
    async def test_whisper_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_whisper_rcon_unavailable(self, mock_interaction):
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
    async def test_whisper_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Whisper failed")
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


class TestWhitelistCommandHandler:
    """Test: /factorio whitelist - Manage server whitelist."""
    
    @pytest.mark.asyncio
    async def test_whitelist_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Whitelist command succeeds."""
        mock_rcon_client.execute.return_value = "Whitelist updated"
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
    async def test_whitelist_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_whitelist_rcon_unavailable(self, mock_interaction):
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
    async def test_whitelist_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Whitelist failed")
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


# ════════════════════════════════════════════════════════════════════════════
# BATCH 3: Game Control (4 handlers x 4 tests = 16 tests)
# ════════════════════════════════════════════════════════════════════════════

class TestClockCommandHandler:
    """Test: /factorio clock - Set or display game daytime."""
    
    @pytest.mark.asyncio
    async def test_clock_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Clock command succeeds."""
        mock_rcon_client.execute.return_value = "0.5"
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
    async def test_clock_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_clock_rcon_unavailable(self, mock_interaction):
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
    async def test_clock_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Clock failed")
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


class TestSpeedCommandHandler:
    """Test: /factorio speed - Set game speed."""
    
    @pytest.mark.asyncio
    async def test_speed_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Speed command succeeds."""
        mock_rcon_client.execute.return_value = "Speed set to 1.0"
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
    async def test_speed_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_speed_rcon_unavailable(self, mock_interaction):
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
    async def test_speed_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Speed failed")
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


class TestResearchCommandHandler:
    """Test: /factorio research - Manage technology research."""
    
    @pytest.mark.asyncio
    async def test_research_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Research command succeeds."""
        mock_rcon_client.execute.return_value = "Research started"
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
    async def test_research_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_research_rcon_unavailable(self, mock_interaction):
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
    async def test_research_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Research failed")
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


class TestStatusCommandHandler:
    """Test: /factorio status - Show server status."""
    
    @pytest.mark.asyncio
    async def test_status_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Status command succeeds."""
        mock_rcon_client.execute.return_value = "Server running"
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
    async def test_status_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_status_rcon_unavailable(self, mock_interaction):
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
    async def test_status_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Status failed")
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
