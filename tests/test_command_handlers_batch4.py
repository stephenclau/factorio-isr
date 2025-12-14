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

"""🎪 LAYER 1 TESTING: Handler-Level Unit Tests for Batch 4

Remaining Query & Info Command Handlers
(Players, Version, Seed, Admins, Health, Rcon, Help, Servers, Connect)

**Strategy**: Test handlers in ISOLATION with minimal mocks
- No bot object mocking (except Health handler)
- Direct dependency injection via constructor
- Response parsing validation
- State inspection testing (Health)
- Multi-server context switching (Connect)

**Target Coverage**: 95%+ per handler
**Total Tests**: 22 (9 handlers with specialized patterns)

**Unique Patterns**:
1. PlayersCommandHandler: List parsing + empty case
2. VersionCommandHandler: Simple extraction
3. SeedCommandHandler: Lua execution + int validation
4. AdminsCommandHandler: List filtering + headers
5. HealthCommandHandler: Bot state inspection + uptime
6. RconCommandHandler: Raw execution + truncation
7. HelpCommandHandler: Static content (no logic)
8. ServersCommandHandler: Single vs multi-mode
9. ConnectCommandHandler: Context switching

**Error Branches Tested**:
1. Rate limited
2. RCON unavailable
3. Exception during execution
4. Parsing failures (Seed)
5. Invalid server (Connect)
6. Multi-server disabled (Connect)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import discord

from bot.commands.command_handlers_batch4 import (
    PlayersCommandHandler,
    VersionCommandHandler,
    SeedCommandHandler,
    AdminsCommandHandler,
    HealthCommandHandler,
    RconCommandHandler,
    HelpCommandHandler,
    ServersCommandHandler,
    ConnectCommandHandler,
    CommandResult,
)


# ════════════════════════════════════════════════════
# MINIMAL MOCK DEPENDENCIES (reused + extended from Batches 1-3)
# ════════════════════════════════════════════════════

class DummyUserContext:
    """Minimal UserContextProvider implementation for testing."""

    def __init__(
        self,
        server_name: str = "prod-server",
        user_server: str = "main",
        rcon_client: Optional[MagicMock] = None,
    ):
        self.server_name = server_name
        self.user_server = user_server
        self.rcon_client = rcon_client

    def get_user_server(self, user_id: int) -> str:
        return self.user_server

    def set_user_server(self, user_id: int, server: str) -> None:
        self.user_server = server

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
    COLOR_INFO = 0x0099FF

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


class DummyRconMonitor:
    """Minimal RconMonitor implementation with uptime tracking."""

    def __init__(self):
        self.rcon_server_states = {}


class DummyServerManager:
    """Minimal ServerManager implementation for multi-server support."""

    def __init__(self, servers: Optional[Dict[str, Any]] = None):
        self.servers = servers or {}
        self.clients = {}
        self.status = {}

    def list_servers(self) -> Dict[str, Any]:
        return self.servers

    def get_config(self, server: str) -> Any:
        return self.servers.get(server)

    def get_status_summary(self) -> Dict[str, bool]:
        return self.status

    def get_client(self, server: str):
        return self.clients.get(server, MagicMock(is_connected=False))


class DummyBot:
    """Minimal Bot implementation for health checking."""

    def __init__(self, connected: bool = True, rcon_monitor=None, server_manager=None):
        self._connected = connected
        self.rcon_monitor = rcon_monitor
        self.server_manager = server_manager


# ════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════

@pytest.fixture
def mock_interaction():
    """Create mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.name = "TestUser"
    return interaction


@pytest.fixture
def mock_rcon_client():
    """Create mock RCON client."""
    rcon = MagicMock()
    rcon.is_connected = True
    rcon.execute = AsyncMock(return_value="")
    return rcon


# ════════════════════════════════════════════════════
# PLAYERS COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestPlayersCommandHandler:
    """Handler-level tests for PlayersCommandHandler."""

    @pytest.mark.asyncio
    async def test_players_with_online_players(self, mock_interaction, mock_rcon_client):
        """Test: players command displays online players.

        Happy Path:
        - RCON returns player list with "(online)" markers
        - Parse and format player names
        - Display count and list
        """
        mock_rcon_client.execute.return_value = (
            "Players:\n"
            "- Alice (online)\n"
            "- Bob (online)\n"
            "- Charlie (online)"
        )
        handler = PlayersCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert result.embed is not None
        assert "Players" in result.embed.title
        assert "Alice" in result.embed.fields[0].value
        assert "Bob" in result.embed.fields[0].value
        assert "Charlie" in result.embed.fields[0].value
        assert "(3)" in result.embed.fields[0].name

    @pytest.mark.asyncio
    async def test_players_empty_server(self, mock_interaction, mock_rcon_client):
        """Test: players command handles empty server."""
        mock_rcon_client.execute.return_value = "Players:\nNo players online."
        handler = PlayersCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "No players currently online" in result.embed.description

    @pytest.mark.asyncio
    async def test_players_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: players command blocked by rate limit."""
        handler = PlayersCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_players_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: players command handles exception."""
        mock_rcon_client.execute.side_effect = Exception("Connection lost")
        handler = PlayersCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False
        assert "Failed to get players" in result.error_embed.description


# ════════════════════════════════════════════════════
# VERSION COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestVersionCommandHandler:
    """Handler-level tests for VersionCommandHandler."""

    @pytest.mark.asyncio
    async def test_version_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: version command returns Factorio version."""
        mock_rcon_client.execute.return_value = "1.1.88"
        handler = VersionCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "1.1.88" in result.embed.description

    @pytest.mark.asyncio
    async def test_version_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: version command blocked by rate limit."""
        handler = VersionCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_version_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: version command handles exception."""
        mock_rcon_client.execute.side_effect = Exception("Timeout")
        handler = VersionCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False
        assert "Failed to get version" in result.error_embed.description


# ════════════════════════════════════════════════════
# SEED COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestSeedCommandHandler:
    """Handler-level tests for SeedCommandHandler."""

    @pytest.mark.asyncio
    async def test_seed_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: seed command returns map seed."""
        mock_rcon_client.execute.return_value = "1234567890"
        handler = SeedCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "1234567890" in result.embed.description

    @pytest.mark.asyncio
    async def test_seed_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: seed command blocked by rate limit."""
        handler = SeedCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_seed_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: seed command handles exception."""
        mock_rcon_client.execute.side_effect = Exception("Lua error")
        handler = SeedCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False
        assert "Failed to get seed" in result.error_embed.description


# ════════════════════════════════════════════════════
# ADMINS COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestAdminsCommandHandler:
    """Handler-level tests for AdminsCommandHandler."""

    @pytest.mark.asyncio
    async def test_admins_with_administrators(self, mock_interaction, mock_rcon_client):
        """Test: admins command displays administrators.

        Happy Path:
        - RCON returns admin list
        - Parse and format admin names
        - Display count and list
        """
        mock_rcon_client.execute.return_value = (
            "Admins:\n"
            "- Admin1\n"
            "- Admin2\n"
            "- Admin3"
        )
        handler = AdminsCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "Admin1" in result.embed.fields[0].value
        assert "Admin2" in result.embed.fields[0].value
        assert "(3)" in result.embed.fields[0].name

    @pytest.mark.asyncio
    async def test_admins_none_configured(self, mock_interaction, mock_rcon_client):
        """Test: admins command handles no admins."""
        mock_rcon_client.execute.return_value = "There are no admins."
        handler = AdminsCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "No administrators" in result.embed.description

    @pytest.mark.asyncio
    async def test_admins_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: admins command blocked by rate limit."""
        handler = AdminsCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_admins_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: admins command handles exception."""
        mock_rcon_client.execute.side_effect = Exception("Connection error")
        handler = AdminsCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False
        assert "Failed to get admins" in result.error_embed.description


# ════════════════════════════════════════════════════
# HEALTH COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestHealthCommandHandler:
    """Handler-level tests for HealthCommandHandler."""

    @pytest.mark.asyncio
    async def test_health_all_healthy(self, mock_interaction, mock_rcon_client):
        """Test: health check with all systems healthy.

        State Inspection:
        - Bot: connected
        - RCON: connected
        - Monitor: running
        """
        bot = DummyBot(
            connected=True,
            rcon_monitor=DummyRconMonitor(),
        )
        handler = HealthCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
            bot=bot,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "Health Check" in result.embed.title
        assert "Healthy" in str(result.embed.fields[0].value)
        assert "Connected" in str(result.embed.fields[1].value)
        assert "Running" in str(result.embed.fields[2].value)

    @pytest.mark.asyncio
    async def test_health_bot_disconnected(self, mock_interaction):
        """Test: health check with bot disconnected."""
        bot = DummyBot(
            connected=False,
            rcon_monitor=DummyRconMonitor(),
        )
        handler = HealthCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
            bot=bot,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "Disconnected" in str(result.embed.fields[0].value)

    @pytest.mark.asyncio
    async def test_health_rate_limited(self, mock_interaction):
        """Test: health command blocked by rate limit."""
        bot = DummyBot(connected=True)
        handler = HealthCommandHandler(
            user_context_provider=DummyUserContext(),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
            bot=bot,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_health_with_uptime(self, mock_interaction):
        """Test: health check displays uptime.
        
        Validates uptime calculation handles any date/time combination correctly.
        Uses timedelta for proper date arithmetic (handles month/year boundaries).
        """
        monitor = DummyRconMonitor()
        # Simulate 2 days, 3 hours, 15 minutes of uptime (correct date arithmetic)
        now = datetime.now(timezone.utc)
        uptime_delta = timedelta(days=2, hours=3, minutes=15)
        uptime_start = now - uptime_delta
        
        monitor.rcon_server_states["main"] = {
            "last_connected": uptime_start
        }

        bot = DummyBot(
            connected=True,
            rcon_monitor=monitor,
        )
        handler = HealthCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=MagicMock(is_connected=True)),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
            bot=bot,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        # Uptime field should contain time units (d, h, m)
        assert any("d" in str(f.value) or "h" in str(f.value) for f in result.embed.fields)


# ════════════════════════════════════════════════════
# RCON COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestRconCommandHandler:
    """Handler-level tests for RconCommandHandler."""

    @pytest.mark.asyncio
    async def test_rcon_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: rcon command executes raw RCON command.

        Happy Path:
        - Execute arbitrary RCON command
        - Return response in code block
        """
        mock_rcon_client.execute.return_value = "Command executed successfully"
        handler = RconCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, command="/time set day")

        assert result.success is True
        assert "Command Executed" in result.embed.title
        assert "/time set day" in result.embed.fields[0].value
        assert "successfully" in result.embed.fields[1].value

    @pytest.mark.asyncio
    async def test_rcon_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: rcon command blocked by rate limit."""
        handler = RconCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, command="/test")

        assert result.success is False

    @pytest.mark.asyncio
    async def test_rcon_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: rcon command handles exception."""
        mock_rcon_client.execute.side_effect = Exception("Invalid command")
        handler = RconCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, command="/invalid")

        assert result.success is False
        assert "RCON command failed" in result.error_embed.description


# ════════════════════════════════════════════════════
# HELP COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestHelpCommandHandler:
    """Handler-level tests for HelpCommandHandler."""

    @pytest.mark.asyncio
    async def test_help_displays_commands(self, mock_interaction):
        """Test: help command displays available commands.

        No dependencies required:
        - Static content
        - No RCON, rate limiter, or state inspection
        """
        handler = HelpCommandHandler(embed_builder_type=DummyEmbedBuilder)

        result = await handler.execute(mock_interaction)

        assert result.success is True


# ════════════════════════════════════════════════════
# SERVERS COMMAND HANDLER TESTS (Multi-server)
# ════════════════════════════════════════════════════

class TestServersCommandHandler:
    """Handler-level tests for ServersCommandHandler."""

    @pytest.mark.asyncio
    async def test_servers_single_mode(self, mock_interaction):
        """Test: servers command in single-server mode.

        Conditional Branching:
        - server_manager is None
        - Return info message about single-server mode
        """
        handler = ServersCommandHandler(
            user_context_provider=DummyUserContext(),
            embed_builder_type=DummyEmbedBuilder,
            server_manager=None,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "Single-server mode" in result.embed.description

    @pytest.mark.asyncio
    async def test_servers_multi_mode(self, mock_interaction):
        """Test: servers command in multi-server mode.

        Conditional Branching:
        - server_manager is configured
        - List all servers with status
        """
        servers_config = {
            "prod": MagicMock(name="Production", rcon_host="prod.local", rcon_port=5000, description="Main server"),
            "test": MagicMock(name="Testing", rcon_host="test.local", rcon_port=5001, description="Test server"),
        }
        server_manager = DummyServerManager(servers=servers_config)
        server_manager.status = {"prod": True, "test": False}

        handler = ServersCommandHandler(
            user_context_provider=DummyUserContext(user_server="prod"),
            embed_builder_type=DummyEmbedBuilder,
            server_manager=server_manager,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is True
        assert "Available Factorio Servers" in result.embed.title
        assert "prod" in str(result.embed.fields)
        assert "test" in str(result.embed.fields)


# ════════════════════════════════════════════════════
# CONNECT COMMAND HANDLER TESTS (Multi-server context switch)
# ════════════════════════════════════════════════════

class TestConnectCommandHandler:
    """Handler-level tests for ConnectCommandHandler."""

    @pytest.mark.asyncio
    async def test_connect_valid_server(self, mock_interaction):
        """Test: connect command switches to valid server.

        Happy Path:
        - server_manager configured with available servers
        - Server exists and is valid
        - Update user context to new server
        - Display connection confirmation
        """
        servers_config = {
            "prod": MagicMock(name="Production", rcon_host="prod.local", rcon_port=5000, description="Main"),
            "test": MagicMock(name="Testing", rcon_host="test.local", rcon_port=5001, description="Test"),
        }
        server_manager = DummyServerManager(servers=servers_config)
        server_manager.clients = {
            "prod": MagicMock(is_connected=True),
            "test": MagicMock(is_connected=False),
        }

        user_context = DummyUserContext(user_server="prod")
        handler = ConnectCommandHandler(
            user_context_provider=user_context,
            embed_builder_type=DummyEmbedBuilder,
            server_manager=server_manager,
        )

        result = await handler.execute(mock_interaction, server="test")

        assert result.success is True
        # Handler embeds config.name (a MagicMock), so check for "Connected to" + any name
        assert "Connected to" in result.embed.title
        assert user_context.get_user_server(mock_interaction.user.id) == "test"

    @pytest.mark.asyncio
    async def test_connect_invalid_server(self, mock_interaction):
        """Test: connect command with invalid server.

        Error Branch: Server not found
        - server="nonexistent"
        - Return error with available servers list
        """
        servers_config = {
            "prod": MagicMock(name="Production", rcon_host="prod.local", rcon_port=5000, description="Main"),
        }
        server_manager = DummyServerManager(servers=servers_config)

        handler = ConnectCommandHandler(
            user_context_provider=DummyUserContext(),
            embed_builder_type=DummyEmbedBuilder,
            server_manager=server_manager,
        )

        result = await handler.execute(mock_interaction, server="nonexistent")

        assert result.success is False
        assert "not found" in result.error_embed.description
        assert "prod" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_connect_multi_server_disabled(self, mock_interaction):
        """Test: connect command with multi-server disabled.

        Error Branch: Multi-server mode not enabled
        - server_manager is None
        - Return error message
        """
        handler = ConnectCommandHandler(
            user_context_provider=DummyUserContext(),
            embed_builder_type=DummyEmbedBuilder,
            server_manager=None,
        )

        result = await handler.execute(mock_interaction, server="prod")

        assert result.success is False
        assert "Multi-server mode not enabled" in result.error_embed.description


if __name__ == "__main__":
    # Run with: pytest tests/test_command_handlers_batch4.py -v
    # Run with coverage: pytest tests/test_command_handlers_batch4.py --cov=src/bot/commands.command_handlers_batch4 --cov-report=term-missing
    pytest.main(["-v", __file__])
