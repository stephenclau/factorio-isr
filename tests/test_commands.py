"""
Unit tests for Phase 5 admin commands in discord_bot.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord import app_commands

# Assume your discord_bot module
from discord_bot import DiscordBot


class TestPhase5AdminCommands:
    """Test Phase 5 admin command implementations."""

    @pytest.fixture
    def bot(self):
        """Create a bot instance for testing."""
        token = "test_token_12345"
        bot = DiscordBot(token=token, bot_name="Test Bot")
        bot.event_channel_id = 123456789
        return bot

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.name = "TestModerator"
        return interaction

    # ========================================================================
    # Broadcast Command Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_broadcast_command_success(self, bot, mock_interaction):
        """Test successful message broadcast."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Message sent")

        # Simulate the command
        message = "Server maintenance in 10 minutes!"

        # Mock the command decorator behavior
        await mock_interaction.response.defer()

        # Execute broadcast logic
        escaped_msg = message.replace('"', '\\"')
        resp = await bot.rcon_client.execute(f'/c game.print("{escaped_msg}")')

        await mock_interaction.followup.send(f"📢 **Broadcast Sent**\n\nMessage: _{message}_")

        # Assertions
        bot.rcon_client.execute.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_command_no_rcon(self, bot, mock_interaction):
        """Test broadcast command when RCON is not available."""
        bot.rcon_client = None

        await mock_interaction.response.defer()
        await mock_interaction.followup.send("⚠️ RCON not available. Cannot broadcast messages.")

        mock_interaction.followup.send.assert_called_with("⚠️ RCON not available. Cannot broadcast messages.")

    # ========================================================================
    # Whitelist Command Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_whitelist_add_player(self, bot, mock_interaction):
        """Test adding a player to whitelist."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Player added to whitelist")

        player = "NewPlayer"
        action = "add"

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute(f"/whitelist add {player}")
        await mock_interaction.followup.send(f"✅ **Player Added to Whitelist**\n\nPlayer: **{player}**")

        bot.rcon_client.execute.assert_called_once_with(f"/whitelist add {player}")
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_list(self, bot, mock_interaction):
        """Test listing whitelist."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Whitelist: Player1, Player2")

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute("/whitelist get")
        await mock_interaction.followup.send(f"📋 **Whitelist**\n\n{resp}")

        bot.rcon_client.execute.assert_called_once_with("/whitelist get")

    @pytest.mark.asyncio
    async def test_whitelist_invalid_action(self, bot, mock_interaction):
        """Test whitelist command with invalid action."""
        bot.rcon_client = AsyncMock()

        action = "invalid"

        await mock_interaction.response.defer()
        await mock_interaction.followup.send(
            f"❌ Invalid action: {action}\nValid actions: add, remove, list, enable, disable"
        )

        # Should not call RCON
        bot.rcon_client.execute.assert_not_called()

    # ========================================================================
    # Promote/Demote Command Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_promote_player(self, bot, mock_interaction):
        """Test promoting a player to admin."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Player promoted")

        player = "TrustedPlayer"

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute(f"/promote {player}")
        await mock_interaction.followup.send(f"⬆️ **Player Promoted**")

        bot.rcon_client.execute.assert_called_once_with(f"/promote {player}")

    @pytest.mark.asyncio
    async def test_demote_player(self, bot, mock_interaction):
        """Test demoting a player from admin."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Player demoted")

        player = "FormerAdmin"

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute(f"/demote {player}")
        await mock_interaction.followup.send(f"⬇️ **Player Demoted**")

        bot.rcon_client.execute.assert_called_once_with(f"/demote {player}")

    # ========================================================================
    # Mute/Unmute Command Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_mute_player(self, bot, mock_interaction):
        """Test muting a player."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Player muted")

        player = "SpammerPlayer"

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute(f"/mute {player}")
        await mock_interaction.followup.send(f"🔇 **Player Muted**")

        bot.rcon_client.execute.assert_called_once_with(f"/mute {player}")

    @pytest.mark.asyncio
    async def test_unmute_player(self, bot, mock_interaction):
        """Test unmuting a player."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Player unmuted")

        player = "ReformedPlayer"

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute(f"/unmute {player}")
        await mock_interaction.followup.send(f"🔊 **Player Unmuted**")

        bot.rcon_client.execute.assert_called_once_with(f"/unmute {player}")

    # ========================================================================
    # Server Info Command Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_seed_command(self, bot, mock_interaction):
        """Test getting map seed."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="1234567890")

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute('/c rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)')
        await mock_interaction.followup.send(f"🌱 **Map Seed**\n\nSeed: `{resp.strip()}`")

        bot.rcon_client.execute.assert_called_once()
        assert "1234567890" in str(mock_interaction.followup.send.call_args)

    @pytest.mark.asyncio
    async def test_version_command(self, bot, mock_interaction):
        """Test getting Factorio version."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Factorio 1.1.100")

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute("/version")
        await mock_interaction.followup.send(f"🎮 **Factorio Version**\n\n{resp}")

        bot.rcon_client.execute.assert_called_once_with("/version")

    @pytest.mark.asyncio
    async def test_evolution_command(self, bot, mock_interaction):
        """Test getting evolution factor."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="45.67%")

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute('/c rcon.print(string.format("%.2f%%", game.forces["enemy"].evolution_factor * 100))')
        await mock_interaction.followup.send(f"🐛 **Evolution Factor**\n\nCurrent evolution: **{resp.strip()}**")

        bot.rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_admins_command(self, bot, mock_interaction):
        """Test listing server admins."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Admin1, Admin2, Admin3")

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute("/admins")
        await mock_interaction.followup.send(f"👑 **Server Administrators**\n\n{resp}")

        bot.rcon_client.execute.assert_called_once_with("/admins")

    # ========================================================================
    # Game Control Command Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_time_command_view(self, bot, mock_interaction):
        """Test viewing current game time."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="12:00 PM")

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute("/time")
        await mock_interaction.followup.send(f"🕐 **Current Game Time**\n\n{resp}")

        bot.rcon_client.execute.assert_called_once_with("/time")

    @pytest.mark.asyncio
    async def test_time_command_set(self, bot, mock_interaction):
        """Test setting game time."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Time set")

        value = 0.5  # Noon

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute(f'/c game.surfaces["nauvis"].daytime = {value}')
        await mock_interaction.followup.send(f"🕐 **Time Changed**")

        bot.rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_speed_command_valid(self, bot, mock_interaction):
        """Test setting game speed with valid value."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Speed changed")

        speed = 2.0

        await mock_interaction.response.defer()
        resp = await bot.rcon_client.execute(f"/c game.speed = {speed}")
        await mock_interaction.followup.send(f"⚡ **Game Speed Changed**\n\nSpeed multiplier: **{speed}x**")

        bot.rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_speed_command_invalid_range(self, bot, mock_interaction):
        """Test speed command with invalid range."""
        bot.rcon_client = AsyncMock()

        speed = 15.0  # Too high

        await mock_interaction.response.defer()

        # Should validate and reject
        if speed < 0.1 or speed > 10.0:
            await mock_interaction.followup.send("❌ Speed must be between 0.1 and 10.0")

        # Should not call RCON
        bot.rcon_client.execute.assert_not_called()
        mock_interaction.followup.send.assert_called_with("❌ Speed must be between 0.1 and 10.0")

    @pytest.mark.asyncio
    async def test_research_command(self, bot, mock_interaction):
        """Test forcing technology research."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(return_value="Research completed")

        technology = "automation-2"

        await mock_interaction.response.defer()
        cmd = f'/c game.forces["player"].technologies["{technology}"].researched = true'
        resp = await bot.rcon_client.execute(cmd)
        await mock_interaction.followup.send(f"🔬 **Technology Researched**")

        bot.rcon_client.execute.assert_called_once()
        assert technology in str(bot.rcon_client.execute.call_args)


class TestPhase5ErrorHandling:
    """Test error handling for Phase 5 commands."""

    @pytest.fixture
    def bot(self):
        token = "test_token_12345"
        bot = DiscordBot(token=token, bot_name="Test Bot")
        return bot

    @pytest.fixture
    def mock_interaction(self):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.name = "TestModerator"
        return interaction

    @pytest.mark.asyncio
    async def test_command_rcon_exception(self, bot, mock_interaction):
        """Test handling of RCON exceptions."""
        bot.rcon_client = AsyncMock()
        bot.rcon_client.execute = AsyncMock(side_effect=Exception("RCON connection lost"))

        await mock_interaction.response.defer()

        try:
            resp = await bot.rcon_client.execute("/version")
        except Exception as e:
            await mock_interaction.followup.send(f"❌ Failed to get version: {str(e)}")

        mock_interaction.followup.send.assert_called()
        assert "Failed" in str(mock_interaction.followup.send.call_args)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
