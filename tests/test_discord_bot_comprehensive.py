"""
Comprehensive pytest test suite for discord_bot.py - SIMPLIFIED CORRECT VERSION
Only tests public API and actual bot behavior without making assumptions about internals
Correct parameter: bot_name (with underscore)
Correct cooldowns: QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN (with underscores)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord
from discord import app_commands

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from discord_bot import DiscordBot, DiscordBotFactory


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def real_intents():
    """Return real Discord intents"""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    return intents


@pytest.fixture
def bot(real_intents):
    """Create a DiscordBot instance for testing"""
    bot = DiscordBot(token="TEST_TOKEN", bot_name="TestBot", intents=real_intents)
    bot.tree = MagicMock(spec=app_commands.CommandTree)
    bot.tree.get_commands = MagicMock(return_value=[])
    return bot


@pytest.fixture
def mock_rcon():
    """Mock RCON client"""
    rcon = MagicMock()
    rcon.is_connected = True
    rcon.host = "localhost"
    rcon.port = 27015
    rcon.execute = AsyncMock(return_value="OK")
    rcon.get_players = AsyncMock(return_value=["Alice", "Bob", "Charlie"])
    return rcon


@pytest.fixture
def mock_interaction():
    """Mock Discord interaction"""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(id=123456, name="TestUser")
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture(autouse=True)
def patch_cooldowns(monkeypatch):
    """Patch cooldowns"""
    class MockCooldown:
        def is_rate_limited(self, user_id: int):
            return (False, 0.0)

    mock_cooldown = MockCooldown()

    import discord_bot
    monkeypatch.setattr(discord_bot, 'QUERY_COOLDOWN', mock_cooldown)
    monkeypatch.setattr(discord_bot, 'ADMIN_COOLDOWN', mock_cooldown)
    monkeypatch.setattr(discord_bot, 'DANGER_COOLDOWN', mock_cooldown)


@pytest.fixture(autouse=True)
def patch_embedbuilder(monkeypatch):
    """Patch EmbedBuilder"""
    def mock_embed(*args, **kwargs):
        return discord.Embed(title=kwargs.get('title', 'Test'))

    import discord_bot
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'info_embed', staticmethod(mock_embed))
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'error_embed', staticmethod(mock_embed))
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'cooldown_embed', staticmethod(mock_embed))
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'server_status_embed', staticmethod(mock_embed))
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'players_list_embed', staticmethod(mock_embed))
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'admin_action_embed', staticmethod(mock_embed))


# ============================================================================
# TEST: INITIALIZATION
# ============================================================================

def test_init_default(real_intents):
    """Test DiscordBot initialization with defaults"""
    bot = DiscordBot(token="TOKEN123", intents=real_intents)
    assert bot.token == "TOKEN123"
    assert bot.bot_name == "Factorio ISR"
    assert bot.event_channel_id is None
    assert bot.rcon_client is None


def test_init_custom_bot_name(real_intents):
    """Test DiscordBot initialization with custom bot_name"""
    bot = DiscordBot(token="TOKEN", bot_name="CustomBot", intents=real_intents)
    assert bot.bot_name == "CustomBot"


def test_set_event_channel(bot):
    """Test setting event channel"""
    bot.set_event_channel(123456789)
    assert bot.event_channel_id == 123456789


def test_set_rcon_client(bot, mock_rcon):
    """Test setting RCON client"""
    bot.set_rcon_client(mock_rcon)
    assert bot.rcon_client is mock_rcon


def test_factory_create_bot(real_intents):
    """Test DiscordBotFactory.create_bot"""
    bot = DiscordBotFactory.create_bot(token="FACTORY_TOKEN", bot_name="FactoryBot")
    assert isinstance(bot, DiscordBot)
    assert bot.token == "FACTORY_TOKEN"
    assert bot.bot_name == "FactoryBot"


# ============================================================================
# TEST: COMMAND REGISTRATION
# ============================================================================

@pytest.mark.asyncio
async def test_register_commands(bot):
    """Test command registration creates factorio group"""
    await bot._register_commands()

    bot.tree.add_command.assert_called_once()

    call_args = bot.tree.add_command.call_args
    group = call_args[0][0]

    assert group.name == "factorio"
    assert len(group.commands) >= 4


@pytest.mark.asyncio
async def test_setup_hook(bot):
    """Test setup_hook calls _register_commands"""
    with patch.object(bot, '_register_commands', new_callable=AsyncMock) as mock_register:
        await bot.setup_hook()
        mock_register.assert_awaited_once()


# ============================================================================
# TEST: SLASH COMMANDS - PING
# ============================================================================

@pytest.mark.asyncio
async def test_ping_command_success(bot, mock_rcon, mock_interaction):
    """Test /factorio ping with successful RCON connection"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "Server time: 12345"

    await bot._register_commands()

    group = bot.tree.add_command.call_args[0][0]
    ping_cmd = next(cmd for cmd in group.commands if cmd.name == "ping")

    await ping_cmd.callback(mock_interaction)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()
    mock_rcon.execute.assert_awaited()


@pytest.mark.asyncio
async def test_ping_command_no_rcon(bot, mock_interaction):
    """Test /factorio ping when RCON is not configured"""
    bot.rcon_client = None

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    ping_cmd = next(cmd for cmd in group.commands if cmd.name == "ping")

    await ping_cmd.callback(mock_interaction)

    mock_interaction.followup.send.assert_awaited_once()
    call_kwargs = mock_interaction.followup.send.call_args.kwargs
    assert call_kwargs.get('ephemeral') is True


@pytest.mark.asyncio
async def test_ping_command_rcon_error(bot, mock_rcon, mock_interaction):
    """Test /factorio ping when RCON raises exception"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.side_effect = Exception("Connection failed")

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    ping_cmd = next(cmd for cmd in group.commands if cmd.name == "ping")

    await ping_cmd.callback(mock_interaction)

    mock_interaction.followup.send.assert_awaited_once()
    call_kwargs = mock_interaction.followup.send.call_args.kwargs
    assert call_kwargs.get('ephemeral') is True


# ============================================================================
# TEST: SLASH COMMANDS - STATUS
# ============================================================================

@pytest.mark.asyncio
async def test_status_command_rcon_connected(bot, mock_rcon, mock_interaction):
    """Test /factorio status with RCON connected"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.is_connected = True
    mock_rcon.get_players.return_value = ["Player1", "Player2"]

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    status_cmd = next(cmd for cmd in group.commands if cmd.name == "status")

    await status_cmd.callback(mock_interaction)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_status_command_rcon_disconnected(bot, mock_rcon, mock_interaction):
    """Test /factorio status with RCON disconnected"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.is_connected = False

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    status_cmd = next(cmd for cmd in group.commands if cmd.name == "status")

    await status_cmd.callback(mock_interaction)

    mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# TEST: SLASH COMMANDS - PLAYERS
# ============================================================================

@pytest.mark.asyncio
async def test_players_command_success(bot, mock_rcon, mock_interaction):
    """Test /factorio players with players online"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.is_connected = True
    mock_rcon.get_players.return_value = ["Alice", "Bob"]

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    players_cmd = next(cmd for cmd in group.commands if cmd.name == "players")

    await players_cmd.callback(mock_interaction)

    mock_interaction.response.defer.assert_awaited_once()
    mock_rcon.get_players.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_players_command_rcon_not_connected(bot, mock_rcon, mock_interaction):
    """Test /factorio players when RCON not connected"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.is_connected = False

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    players_cmd = next(cmd for cmd in group.commands if cmd.name == "players")

    await players_cmd.callback(mock_interaction)

    mock_interaction.followup.send.assert_awaited_once()
    call_kwargs = mock_interaction.followup.send.call_args.kwargs
    assert call_kwargs.get('ephemeral') is True


# ============================================================================
# TEST: SLASH COMMANDS - VERSION
# ============================================================================

@pytest.mark.asyncio
async def test_version_command(bot, mock_rcon, mock_interaction):
    """Test /factorio version command"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "Factorio 1.1.104"

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    version_cmd = next(cmd for cmd in group.commands if cmd.name == "version")

    await version_cmd.callback(mock_interaction)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# TEST: ADDITIONAL SLASH COMMANDS
# ============================================================================

@pytest.mark.asyncio
async def test_all_commands_registered(bot):
    """Test that all expected commands are registered"""
    await bot._register_commands()

    group = bot.tree.add_command.call_args[0][0]
    command_names = {cmd.name for cmd in group.commands}

    expected_commands = {
        'ping', 'status', 'players', 'version', 'seed', 'evolution',
        'admins', 'health', 'kick', 'ban', 'unban', 'mute', 'unmute',
        'promote', 'demote', 'save', 'broadcast', 'whitelist',
        'time', 'speed', 'research', 'rcon', 'help'
    }

    assert expected_commands.issubset(command_names)


@pytest.mark.asyncio
async def test_clear_global_commands(bot):
    """Test clear_global_commands clears and syncs"""
    bot.tree.clear_commands = MagicMock()
    bot.tree.sync = AsyncMock()

    await bot.clear_global_commands()

    bot.tree.clear_commands.assert_called_once_with(guild=None)
    bot.tree.sync.assert_awaited_once()
