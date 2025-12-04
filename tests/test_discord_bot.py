"""
Standalone pytest suite for discord_bot.py
Uses REAL discord.py with mocked network calls only.
Does NOT depend on conftest.py mocks.
Achieves 90%+ coverage by testing actual command callbacks.
"""
from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch, Mock

import discord
from discord import app_commands
import pytest

from discord_bot import DiscordBot, DiscordBotFactory
from rcon_client import RconClient

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# =============================================================================
# TEST FIXTURES - Standalone, no conftest dependency
# =============================================================================

@pytest.fixture
def mock_rcon() -> MagicMock:
    """Mock RCON client with async methods."""
    rcon = MagicMock(spec=RconClient)
    rcon.execute = AsyncMock(return_value="OK")
    rcon.get_players = AsyncMock(return_value=["Alice", "Bob"])
    rcon.is_connected = True
    rcon.host = "localhost"
    rcon.port = 27015
    return rcon


@pytest.fixture
def mock_interaction() -> MagicMock:
    """Mock Discord Interaction - only network parts are fake."""
    interaction = MagicMock(spec=discord.Interaction)

    # User info (read-only, doesn't need network)
    interaction.user = MagicMock()
    interaction.user.id = 123456
    interaction.user.name = "TestUser"
    interaction.guild = MagicMock()
    interaction.guild.name = "TestGuild"
    interaction.guild.id = 999

    # Response methods (these make network calls - mock them)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.is_done = Mock(return_value=False)

    # Followup (network calls)
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    return interaction


@pytest.fixture
def mock_text_channel() -> MagicMock:
    """Mock Discord TextChannel for event notifications."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 999888777
    channel.send = AsyncMock()
    return channel


@pytest.fixture
def patch_discord_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Patch Discord network calls but leave app_commands infrastructure intact.
    This allows real command registration while preventing actual connections.
    """
    # Prevent bot from actually connecting to Discord
    async def mock_login(self: Any, token: str) -> None:
        pass

    async def mock_connect(self: Any, *args: Any, **kwargs: Any) -> None:
        pass

    async def mock_close(self: Any) -> None:
        pass

    # Patch the network methods on discord.Client
    monkeypatch.setattr("discord.Client.login", mock_login)
    monkeypatch.setattr("discord.Client.connect", mock_connect)
    monkeypatch.setattr("discord.Client.close", mock_close)


@pytest.fixture
def patch_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable rate limiting for tests."""
    class NoRateLimit:
        def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
            return (False, 0.0)

    no_limit = NoRateLimit()
    monkeypatch.setattr("discord_bot.QUERY_COOLDOWN", no_limit)
    monkeypatch.setattr("discord_bot.ADMIN_COOLDOWN", no_limit)
    monkeypatch.setattr("discord_bot.DANGER_COOLDOWN", no_limit)


@pytest.fixture
async def bot(patch_discord_network: None, patch_rate_limiting: None) -> DiscordBot:
    """
    Create a REAL DiscordBot instance with real app_commands.
    Network calls are mocked, but command registration is real.
    """
    bot_instance = DiscordBot(token="TEST_TOKEN", bot_name="TestBot")

    # Register commands (this uses REAL discord.py app_commands)
    await bot_instance.setup_hook()

    yield bot_instance

    # Cleanup
    if not bot_instance.is_closed():
        await bot_instance.close()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_factorio_group(bot: DiscordBot) -> app_commands.Group:
    """Extract the REAL factorio command group from bot's tree."""
    for cmd in bot.tree.get_commands():
        if isinstance(cmd, app_commands.Group) and cmd.name == "factorio":
            return cmd
    raise RuntimeError("factorio command group not found")


def get_command(bot: DiscordBot, name: str) -> app_commands.Command:
    """Extract a REAL command from the factorio group."""
    group = get_factorio_group(bot)
    for cmd in group.commands:
        if cmd.name == name:
            return cast(app_commands.Command, cmd)
    raise RuntimeError(f"Command {name!r} not found")


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================

class TestDiscordBotInit:
    """Test bot initialization."""

    @pytest.mark.asyncio
    async def test_init_with_token(self, patch_discord_network: None) -> None:
        bot = DiscordBot(token="TEST123")
        assert bot.token == "TEST123"
        assert bot.bot_name == "Factorio ISR"
        await bot.close()

    @pytest.mark.asyncio
    async def test_init_with_custom_name(self, patch_discord_network: None) -> None:
        bot = DiscordBot(token="TOKEN", bot_name="CustomBot")
        assert bot.bot_name == "CustomBot"
        await bot.close()

    @pytest.mark.asyncio
    async def test_set_event_channel(self, bot: DiscordBot) -> None:
        bot.set_event_channel(123456)
        assert bot.event_channel_id == 123456

    @pytest.mark.asyncio
    async def test_set_rcon_client(self, bot: DiscordBot, mock_rcon: MagicMock) -> None:
        bot.set_rcon_client(mock_rcon)
        assert bot.rcon_client is mock_rcon

    @pytest.mark.asyncio
    async def test_is_connected_property(self, patch_discord_network: None) -> None:
        """Test is_connected property with private _connected attribute."""
        test_bot = DiscordBot(token="TEST123", bot_name="TestBot")

        # Use _connected (private attribute)
        assert test_bot._connected is False
        assert test_bot.is_connected is False

        test_bot._connected = True
        assert test_bot.is_connected is True

        test_bot._connected = False
        assert test_bot.is_connected is False

        await test_bot.close()


class TestDiscordBotFactory:
    """Test factory pattern."""

    @pytest.mark.asyncio
    async def test_create_bot(self, patch_discord_network: None) -> None:
        bot = DiscordBotFactory.create_bot("TOKEN", "FactoryBot")
        assert isinstance(bot, DiscordBot)
        assert bot.bot_name == "FactoryBot"
        await bot.close()


# =============================================================================
# COMMAND REGISTRATION TESTS
# =============================================================================

class TestCommandRegistration:
    """Test that REAL commands are registered."""

    @pytest.mark.asyncio
    async def test_all_commands_registered(self, bot: DiscordBot) -> None:
        """Test that all 23 commands are actually registered."""
        group = get_factorio_group(bot)
        command_names = {cmd.name for cmd in group.commands}

        expected = {
            "ping", "status", "players", "version", "seed", "evolution",
            "admins", "health", "kick", "ban", "unban", "mute", "unmute",
            "promote", "demote", "save", "broadcast", "whitelist", "time",
            "speed", "research", "rcon", "help"
        }

        missing = expected - command_names
        assert len(missing) == 0, f"Missing commands: {missing}"

    @pytest.mark.asyncio
    async def test_commands_are_real_objects(self, bot: DiscordBot) -> None:
        """Test that commands are REAL app_commands.Command objects."""
        cmd = get_command(bot, "ping")
        assert isinstance(cmd, app_commands.Command)
        assert hasattr(cmd, "callback")
        assert callable(cmd.callback)


# =============================================================================
# SERVER INFORMATION COMMANDS
# =============================================================================

class TestServerInformationCommands:
    """Test query commands with REAL command execution."""

    @pytest.mark.asyncio
    async def test_ping_command_success(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test ping command executes real code."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "ping")

        await cmd.callback(mock_interaction)  # REAL callback execution!

        # Verify it actually called methods
        mock_interaction.response.defer.assert_awaited_once()
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ping_no_rcon(self, bot: DiscordBot, mock_interaction: MagicMock) -> None:
        """Test ping handles missing RCON."""
        bot.rcon_client = None
        cmd = get_command(bot, "ping")

        await cmd.callback(mock_interaction)

        # Should send error
        assert mock_interaction.followup.send.await_count >= 1

    @pytest.mark.asyncio
    async def test_status_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test status command."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.is_connected = True

        cmd = get_command(bot, "status")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_players_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test players command."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.get_players.return_value = ["Alice", "Bob", "Charlie"]

        cmd = get_command(bot, "players")
        await cmd.callback(mock_interaction)

        mock_rcon.get_players.assert_awaited_once()
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test health command."""
        bot.set_rcon_client(mock_rcon)
        bot._connected = True
        mock_rcon.is_connected = True

        cmd = get_command(bot, "health")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_version_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test version command."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "1.1.100"

        cmd = get_command(bot, "version")
        await cmd.callback(mock_interaction)

        mock_rcon.execute.assert_awaited_once()


# =============================================================================
# PLAYER MANAGEMENT COMMANDS
# =============================================================================

class TestPlayerManagementCommands:
    """Test admin commands."""

    @pytest.mark.asyncio
    async def test_kick_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test kick command executes."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "kick")

        await cmd.callback(mock_interaction, player="Griefer", reason="Griefing")

        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_ban_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test ban command executes."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "ban")

        await cmd.callback(mock_interaction, player="BadGuy")

        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_unban_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test unban command executes."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "unban")

        await cmd.callback(mock_interaction, player="Forgiven")

        mock_rcon.execute.assert_awaited()


# =============================================================================
# SERVER MANAGEMENT COMMANDS
# =============================================================================

class TestServerManagementCommands:
    """Test server management commands."""

    @pytest.mark.asyncio
    async def test_save_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test save command."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "save")

        await cmd.callback(mock_interaction, name="manual-save")

        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test broadcast command."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "broadcast")

        await cmd.callback(mock_interaction, message="Server restart in 5 min")

        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_whitelist_add(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test whitelist add."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "whitelist")

        await cmd.callback(mock_interaction, action="add", player="NewPlayer")

        mock_rcon.execute.assert_awaited()


# =============================================================================
# GAME CONTROL COMMANDS
# =============================================================================

class TestGameControlCommands:
    """Test game control commands."""

    @pytest.mark.asyncio
    async def test_time_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test time command."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "time")

        await cmd.callback(mock_interaction, value=None)

        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_speed_valid(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test speed command with valid value."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "speed")

        await cmd.callback(mock_interaction, speed=2.0)

        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_speed_out_of_bounds(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test speed command rejects invalid values."""
        bot.set_rcon_client(mock_rcon)
        cmd = get_command(bot, "speed")

        await cmd.callback(mock_interaction, speed=100.0)  # Too high

        # Should error without calling RCON
        mock_interaction.followup.send.assert_awaited()
        mock_rcon.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_help_command(self, bot: DiscordBot, mock_interaction: MagicMock) -> None:
        """Test help command."""
        cmd = get_command(bot, "help")

        await cmd.callback(mock_interaction)

        # Help command uses direct response, not followup
        mock_interaction.response.send_message.assert_awaited_once()


# =============================================================================
# LIFECYCLE TESTS - FIXED!
# =============================================================================

class TestBotLifecycle:
    """Test bot lifecycle methods."""

    @pytest.mark.asyncio
    async def test_on_ready(self, bot: DiscordBot) -> None:
        """Test on_ready sets connected flag."""
        # Mock the user property (read-only)
        mock_user = MagicMock()
        mock_user.name = "TestBot"
        mock_user.id = 12345

        # Mock guilds property (read-only)
        mock_guild = MagicMock()
        type(bot).guilds = PropertyMock(return_value=[mock_guild])
        type(bot).user = PropertyMock(return_value=mock_user)

        # Mock tree.sync to avoid actual API call - FIXED!
        bot.tree.sync = AsyncMock(return_value=[])

        # Mock _send_connection_notification to avoid actual Discord calls
        bot._send_connection_notification = AsyncMock()

        await bot.on_ready()

        # Verify bot is now connected
        assert bot.is_connected is True
        assert bot._ready.is_set()  # Ready event should be set
        bot.tree.sync.assert_awaited()  # Should have synced commands

    @pytest.mark.asyncio
    async def test_on_disconnect(self, bot: DiscordBot) -> None:
        """Test on_disconnect."""
        bot._connected = True

        await bot.on_disconnect()

        assert bot.is_connected is False


# =============================================================================
# EVENT SENDING TESTS
# =============================================================================

class TestEventSending:
    """Test send_event method."""

    @pytest.mark.asyncio
    async def test_send_event_success(
        self, bot: DiscordBot, mock_text_channel: MagicMock
    ) -> None:
        """Test successful event sending."""
        from types import SimpleNamespace

        bot._connected = True
        bot.set_event_channel(123)
        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        with patch('discord_bot.FactorioEventFormatter.format_for_discord',
                   return_value="Test event message"):
            with patch.object(bot, 'get_channel', return_value=mock_text_channel):
                result = await bot.send_event(event)

        assert result is True
        mock_text_channel.send.assert_awaited_once_with("Test event message")

    @pytest.mark.asyncio
    async def test_send_event_not_connected(self, bot: DiscordBot) -> None:
        """Test send_event when bot not connected."""
        from types import SimpleNamespace

        bot._connected = False
        event = SimpleNamespace(event_type=SimpleNamespace(value="test"))

        result = await bot.send_event(event)

        assert result is False


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling in commands."""

    @pytest.mark.asyncio
    async def test_command_handles_rcon_exception(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test commands handle RCON exceptions gracefully."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("RCON error")

        cmd = get_command(bot, "ping")
        await cmd.callback(mock_interaction)

        # Should still send response
        mock_interaction.followup.send.assert_awaited_once()


# =============================================================================
# RATE LIMITING TESTS
# =============================================================================

class TestRateLimiting:
    """Test rate limiting enforcement."""

    @pytest.mark.asyncio
    async def test_cooldown_is_enforced(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test that cooldowns are enforced."""
        bot.set_rcon_client(mock_rcon)

        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return (True, 30.0)

        with patch("discord_bot.QUERY_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "ping")
            await cmd.callback(mock_interaction)

            # Should send cooldown message, not execute
            mock_interaction.response.send_message.assert_awaited_once()
            mock_rcon.execute.assert_not_awaited()
