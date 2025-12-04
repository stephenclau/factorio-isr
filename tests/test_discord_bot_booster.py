"""
Coverage Booster: Additional tests for discord_bot.py - FINAL CORRECT VERSION
Tests all remaining slash commands to achieve 95%+ coverage
Uses correct cooldown names: QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from discord_bot import DiscordBot


# ============================================================================
# FIXTURES - FINAL CORRECT VERSION
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
    bot.tree = MagicMock()
    bot.tree.add_command = MagicMock()
    return bot


@pytest.fixture
def mock_rcon():
    """Mock RCON client"""
    rcon = MagicMock()
    rcon.is_connected = True
    rcon.execute = AsyncMock(return_value="OK")
    rcon.get_players = AsyncMock(return_value=["Alice", "Bob"])
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
def patch_environment(monkeypatch):
    """Patch cooldowns and embeds - FINAL CORRECT with underscore names"""
    class MockCooldown:
        def is_rate_limited(self, user_id):
            return (False, 0.0)

    mock_cooldown = MockCooldown()

    # FINAL FIX: Use correct names with underscores!
    import discord_bot
    monkeypatch.setattr(discord_bot, 'QUERY_COOLDOWN', mock_cooldown)
    monkeypatch.setattr(discord_bot, 'ADMIN_COOLDOWN', mock_cooldown)
    monkeypatch.setattr(discord_bot, 'DANGER_COOLDOWN', mock_cooldown)

    # Proper embed mocking
    def mock_embed(*args, **kwargs):
        return discord.Embed(title=kwargs.get('title', 'Test'))

    monkeypatch.setattr(discord_bot.EmbedBuilder, 'info_embed', staticmethod(mock_embed))
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'error_embed', staticmethod(mock_embed))
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'admin_action_embed', staticmethod(mock_embed))
    monkeypatch.setattr(discord_bot.EmbedBuilder, 'cooldown_embed', staticmethod(mock_embed))


# ============================================================================
# TEST: INFORMATION COMMANDS
# ============================================================================

@pytest.mark.asyncio
async def test_seed_command(bot, mock_rcon, mock_interaction):
    """Test /factorio seed command"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "Map seed: 1234567890"

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    seed_cmd = next(cmd for cmd in group.commands if cmd.name == "seed")

    await seed_cmd.callback(mock_interaction)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_evolution_command(bot, mock_rcon, mock_interaction):
    """Test /factorio evolution command"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "Evolution factor: 0.42"

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    evo_cmd = next(cmd for cmd in group.commands if cmd.name == "evolution")

    await evo_cmd.callback(mock_interaction)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_admins_command(bot, mock_rcon, mock_interaction):
    """Test /factorio admins command"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "Admin1, Admin2"

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    admins_cmd = next(cmd for cmd in group.commands if cmd.name == "admins")

    await admins_cmd.callback(mock_interaction)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_command_all_online(bot, mock_rcon, mock_interaction):
    """Test /factorio health when all systems online"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.is_connected = True

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    health_cmd = next(cmd for cmd in group.commands if cmd.name == "health")

    await health_cmd.callback(mock_interaction)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_command_rcon_offline(bot, mock_rcon, mock_interaction):
    """Test /factorio health when RCON offline"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.is_connected = False

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    health_cmd = next(cmd for cmd in group.commands if cmd.name == "health")

    await health_cmd.callback(mock_interaction)

    mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# TEST: PLAYER MANAGEMENT COMMANDS
# ============================================================================

@pytest.mark.asyncio
async def test_kick_command_with_reason(bot, mock_rcon, mock_interaction):
    """Test /factorio kick with reason"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "Player kicked"

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    kick_cmd = next(cmd for cmd in group.commands if cmd.name == "kick")

    await kick_cmd.callback(mock_interaction, player="Griefer", reason="Griefing")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_kick_command_without_reason(bot, mock_rcon, mock_interaction):
    """Test /factorio kick without reason"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    kick_cmd = next(cmd for cmd in group.commands if cmd.name == "kick")

    await kick_cmd.callback(mock_interaction, player="BadPlayer", reason=None)

    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_ban_command(bot, mock_rcon, mock_interaction):
    """Test /factorio ban command"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    ban_cmd = next(cmd for cmd in group.commands if cmd.name == "ban")

    await ban_cmd.callback(mock_interaction, player="Cheater")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_unban_command(bot, mock_rcon, mock_interaction):
    """Test /factorio unban command"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    unban_cmd = next(cmd for cmd in group.commands if cmd.name == "unban")

    await unban_cmd.callback(mock_interaction, player="Reformed")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_mute_command(bot, mock_rcon, mock_interaction):
    """Test /factorio mute command"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    mute_cmd = next(cmd for cmd in group.commands if cmd.name == "mute")

    await mute_cmd.callback(mock_interaction, player="Spammer")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_unmute_command(bot, mock_rcon, mock_interaction):
    """Test /factorio unmute command"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    unmute_cmd = next(cmd for cmd in group.commands if cmd.name == "unmute")

    await unmute_cmd.callback(mock_interaction, player="Forgiven")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_promote_command(bot, mock_rcon, mock_interaction):
    """Test /factorio promote command"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    promote_cmd = next(cmd for cmd in group.commands if cmd.name == "promote")

    await promote_cmd.callback(mock_interaction, player="Helper")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_demote_command(bot, mock_rcon, mock_interaction):
    """Test /factorio demote command"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    demote_cmd = next(cmd for cmd in group.commands if cmd.name == "demote")

    await demote_cmd.callback(mock_interaction, player="ExAdmin")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# TEST: SERVER MANAGEMENT COMMANDS
# ============================================================================

@pytest.mark.asyncio
async def test_save_command_with_name(bot, mock_rcon, mock_interaction):
    """Test /factorio save with custom name"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    save_cmd = next(cmd for cmd in group.commands if cmd.name == "save")

    await save_cmd.callback(mock_interaction, name="backup-2025")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_command_auto_name(bot, mock_rcon, mock_interaction):
    """Test /factorio save with auto-generated name"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    save_cmd = next(cmd for cmd in group.commands if cmd.name == "save")

    await save_cmd.callback(mock_interaction, name=None)

    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcast_command(bot, mock_rcon, mock_interaction):
    """Test /factorio broadcast command"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    broadcast_cmd = next(cmd for cmd in group.commands if cmd.name == "broadcast")

    await broadcast_cmd.callback(mock_interaction, message="Server restart in 5 minutes")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_whitelist_list(bot, mock_rcon, mock_interaction):
    """Test /factorio whitelist list action"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "Player1, Player2, Player3"

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    whitelist_cmd = next(cmd for cmd in group.commands if cmd.name == "whitelist")

    await whitelist_cmd.callback(mock_interaction, action="list", player=None)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_whitelist_add(bot, mock_rcon, mock_interaction):
    """Test /factorio whitelist add action"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    whitelist_cmd = next(cmd for cmd in group.commands if cmd.name == "whitelist")

    await whitelist_cmd.callback(mock_interaction, action="add", player="NewPlayer")

    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_whitelist_remove(bot, mock_rcon, mock_interaction):
    """Test /factorio whitelist remove action"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    whitelist_cmd = next(cmd for cmd in group.commands if cmd.name == "whitelist")

    await whitelist_cmd.callback(mock_interaction, action="remove", player="OldPlayer")

    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_whitelist_enable(bot, mock_rcon, mock_interaction):
    """Test /factorio whitelist enable action"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    whitelist_cmd = next(cmd for cmd in group.commands if cmd.name == "whitelist")

    await whitelist_cmd.callback(mock_interaction, action="enable", player=None)

    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_whitelist_disable(bot, mock_rcon, mock_interaction):
    """Test /factorio whitelist disable action"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    whitelist_cmd = next(cmd for cmd in group.commands if cmd.name == "whitelist")

    await whitelist_cmd.callback(mock_interaction, action="disable", player=None)

    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_whitelist_invalid_action(bot, mock_rcon, mock_interaction):
    """Test /factorio whitelist with invalid action"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    whitelist_cmd = next(cmd for cmd in group.commands if cmd.name == "whitelist")

    await whitelist_cmd.callback(mock_interaction, action="invalid", player=None)

    # Should send error
    mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# TEST: GAME CONTROL COMMANDS
# ============================================================================

@pytest.mark.asyncio
async def test_time_command_display(bot, mock_rcon, mock_interaction):
    """Test /factorio time to display current time"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "12345"

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    time_cmd = next(cmd for cmd in group.commands if cmd.name == "time")

    await time_cmd.callback(mock_interaction, value=None)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_time_command_set(bot, mock_rcon, mock_interaction):
    """Test /factorio time to set specific time"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    time_cmd = next(cmd for cmd in group.commands if cmd.name == "time")

    await time_cmd.callback(mock_interaction, value=0.5)

    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_speed_command_valid(bot, mock_rcon, mock_interaction):
    """Test /factorio speed with valid value"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    speed_cmd = next(cmd for cmd in group.commands if cmd.name == "speed")

    await speed_cmd.callback(mock_interaction, speed=2.0)

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_speed_command_too_low(bot, mock_rcon, mock_interaction):
    """Test /factorio speed with too low value"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    speed_cmd = next(cmd for cmd in group.commands if cmd.name == "speed")

    await speed_cmd.callback(mock_interaction, speed=0.01)

    # Should send error about bounds
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_speed_command_too_high(bot, mock_rcon, mock_interaction):
    """Test /factorio speed with too high value"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    speed_cmd = next(cmd for cmd in group.commands if cmd.name == "speed")

    await speed_cmd.callback(mock_interaction, speed=20.0)

    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_research_command(bot, mock_rcon, mock_interaction):
    """Test /factorio research command"""
    bot.set_rcon_client(mock_rcon)

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    research_cmd = next(cmd for cmd in group.commands if cmd.name == "research")

    await research_cmd.callback(mock_interaction, technology="automation")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_rcon_command(bot, mock_rcon, mock_interaction):
    """Test /factorio rcon custom command"""
    bot.set_rcon_client(mock_rcon)
    mock_rcon.execute.return_value = "Command executed"

    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    rcon_cmd = next(cmd for cmd in group.commands if cmd.name == "rcon")

    await rcon_cmd.callback(mock_interaction, command="/time")

    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_help_command(bot, mock_interaction):
    """Test /factorio help command"""
    await bot._register_commands()
    group = bot.tree.add_command.call_args[0][0]
    help_cmd = next(cmd for cmd in group.commands if cmd.name == "help")

    await help_cmd.callback(mock_interaction)

    mock_interaction.response.send_message.assert_awaited_once()
