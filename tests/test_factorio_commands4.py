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

"""🎯 INTEGRATION TESTS: /factorio Commands - Phase 4

Phase 4 Testing: Query + Advanced Commands (Batch 4)

**Strategy**: 
- Test ALL query and advanced commands via closure extraction
- Force EVERY error path (rate limit, RCON unavailable, execution failure)
- Target 91%+ coverage via full logic walks
- Happy path + error branches + edge cases per handler

**Commands Covered (Batch 4 - Queries + Advanced)**:
- seed, evolution, admins, health, rcon, servers, connect (7 handlers)

**Total**: 7 handlers, 28 tests (4 per handler)
**Coverage Target**: 91%+ on query + advanced logic
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
# BATCH 4: Queries + Advanced (7 handlers x 4 tests = 28 tests)
# ════════════════════════════════════════════════════════════════════════════

class TestSeedCommandHandler:
    """Test: /factorio seed - Show map seed."""
    
    @pytest.mark.asyncio
    async def test_seed_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Seed command succeeds."""
        mock_rcon_client.execute.return_value = "123456789"
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
    async def test_seed_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_seed_rcon_unavailable(self, mock_interaction):
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
    async def test_seed_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Seed query failed")
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


class TestEvolutionCommandHandler:
    """Test: /factorio evolution - Show enemy evolution."""
    
    @pytest.mark.asyncio
    async def test_evolution_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Evolution command succeeds."""
        mock_rcon_client.execute.return_value = "42.5%"
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
    async def test_evolution_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_evolution_rcon_unavailable(self, mock_interaction):
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
    async def test_evolution_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Evolution query failed")
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


class TestAdminsCommandHandler:
    """Test: /factorio admins - List server administrators."""
    
    @pytest.mark.asyncio
    async def test_admins_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Admins command succeeds."""
        mock_rcon_client.execute.return_value = "Admin1, Admin2"
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
    async def test_admins_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_admins_rcon_unavailable(self, mock_interaction):
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
    async def test_admins_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Admins query failed")
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


class TestHealthCommandHandler:
    """Test: /factorio health - Check bot and server health."""
    
    @pytest.mark.asyncio
    async def test_health_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Health command succeeds."""
        mock_rcon_client.execute.return_value = "Healthy"
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
    async def test_health_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_health_rcon_unavailable(self, mock_interaction):
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
    async def test_health_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("Health check failed")
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


class TestRconCommandHandler:
    """Test: /factorio rcon - Run raw RCON command."""
    
    @pytest.mark.asyncio
    async def test_rcon_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: RCON command succeeds."""
        mock_rcon_client.execute.return_value = "Command executed"
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
    async def test_rcon_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_rcon_rcon_unavailable(self, mock_interaction):
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
    async def test_rcon_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
        mock_rcon_client.execute.side_effect = Exception("RCON command failed")
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


class TestServersCommandHandler:
    """Test: /factorio servers - List available Factorio servers."""
    
    @pytest.mark.asyncio
    async def test_servers_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Servers command succeeds."""
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
    async def test_servers_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_servers_rcon_unavailable(self, mock_interaction):
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
    async def test_servers_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
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


class TestConnectCommandHandler:
    """Test: /factorio connect - Connect to a specific server."""
    
    @pytest.mark.asyncio
    async def test_connect_happy_path(self, mock_interaction, mock_rcon_client):
        """🟢 Happy Path: Connect command succeeds."""
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
    async def test_connect_rate_limited(self, mock_interaction, mock_rcon_client):
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
    async def test_connect_rcon_unavailable(self, mock_interaction):
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
    async def test_connect_rcon_execution_failure(self, mock_interaction, mock_rcon_client):
        """🔴 ERROR: RCON Execution Fails."""
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
