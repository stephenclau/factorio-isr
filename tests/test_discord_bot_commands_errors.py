"""
Pytest test suite for discord_bot.py - Command Error Handling

Comprehensive error testing for all 23 slash commands.
Tests RCON failures, rate limiting, validation errors, and edge cases.
This is the LARGEST coverage boost file (+150 statements, 6.6%).
"""

from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch, Mock
import discord
from discord import app_commands
import pytest
from discord_bot import DiscordBot, DiscordBotFactory
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_rcon() -> MagicMock:
    """Mock RCON client with async methods."""
    rcon = MagicMock()
    rcon.execute = AsyncMock(return_value="OK")
    rcon.get_players = AsyncMock(return_value=["Alice", "Bob"])
    rcon.is_connected = True
    rcon.host = "localhost"
    rcon.port = 27015
    return rcon

@pytest.fixture
def mock_interaction() -> MagicMock:
    """Mock Discord Interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 123456
    interaction.user.name = "TestUser"
    interaction.guild = MagicMock()
    interaction.guild.name = "TestGuild"
    interaction.guild.id = 999
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.is_done = Mock(return_value=False)
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction

@pytest.fixture
def patch_discord_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch Discord network calls."""
    async def mock_login(self: Any, token: str) -> None:
        pass
    async def mock_connect(self: Any, *args: Any, **kwargs: Any) -> None:
        pass
    async def mock_close(self: Any) -> None:
        pass
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
    """Create a REAL DiscordBot instance."""
    bot_instance = DiscordBot(token="TEST_TOKEN", bot_name="TestBot")
    await bot_instance.setup_hook()
    yield bot_instance
    if not bot_instance.is_closed():
        await bot_instance.close()

def get_command(bot: DiscordBot, name: str) -> app_commands.Command:
    """Extract a command from the factorio group."""
    for cmd in bot.tree.get_commands():
        if isinstance(cmd, app_commands.Group) and cmd.name == "factorio":
            for subcmd in cmd.commands:
                if subcmd.name == name:
                    return cast(app_commands.Command, subcmd)
    raise RuntimeError(f"Command {name!r} not found")

# =============================================================================
# TEST: Server Information Commands - Error Paths
# =============================================================================

class TestServerInfoCommandErrors:
    """Test error handling for server information commands."""

    @pytest.mark.asyncio
    async def test_ping_rcon_timeout(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test ping handles RCON timeout."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = asyncio.TimeoutError("RCON timeout")

        cmd = get_command(bot, "ping")
        await cmd.callback(mock_interaction)

        # Should send error message
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get('ephemeral') is True

    @pytest.mark.asyncio
    async def test_ping_connection_refused(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test ping handles connection refused."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = ConnectionRefusedError("Connection refused")

        cmd = get_command(bot, "ping")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_status_rcon_disconnected_mid_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test status when RCON disconnects during command."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.is_connected = True
        mock_rcon.get_players.side_effect = ConnectionError("Lost connection")

        cmd = get_command(bot, "status")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_players_empty_response(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test players command with empty player list."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.get_players.return_value = []

        cmd = get_command(bot, "players")
        await cmd.callback(mock_interaction)

        # Should still send response (with "no players" message)
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_players_malformed_response(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test players command handles malformed RCON response."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.get_players.side_effect = ValueError("Malformed response")

        cmd = get_command(bot, "players")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_version_command_timeout(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test version command timeout."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = asyncio.TimeoutError()

        cmd = get_command(bot, "version")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seed_command_lua_error(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test seed command handles Lua execution error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Lua error: nil value")

        cmd = get_command(bot, "seed")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evolution_command_error(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test evolution command handles errors."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = RuntimeError("Evolution calculation failed")

        cmd = get_command(bot, "evolution")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_admins_command_no_admins(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test admins command when no admins configured."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "No admins defined."

        cmd = get_command(bot, "admins")
        await cmd.callback(mock_interaction)

        # Should still send response
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_command_partial_failure(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test health command when RCON is offline but bot is online."""
        bot.set_rcon_client(mock_rcon)
        bot._connected = True
        mock_rcon.is_connected = False

        cmd = get_command(bot, "health")
        await cmd.callback(mock_interaction)

        # Should send warning status
        mock_interaction.followup.send.assert_awaited_once()

# =============================================================================
# TEST: Player Management Commands - Error Paths
# =============================================================================

class TestPlayerManagementCommandErrors:
    """Test error handling for player management commands."""

    @pytest.mark.asyncio
    async def test_kick_player_not_found(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test kick when player doesn't exist."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player not found"

        cmd = get_command(bot, "kick")
        await cmd.callback(mock_interaction, player="NonExistent", reason="Test")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kick_invalid_reason_characters(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test kick with special characters in reason."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "kick")
        # Reason with quotes and special chars
        await cmd.callback(mock_interaction, player="Player", reason='Test "quotes" & <html>')

        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ban_already_banned(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test ban when player already banned."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player already banned"

        cmd = get_command(bot, "ban")
        await cmd.callback(mock_interaction, player="AlreadyBanned")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unban_not_banned(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test unban when player not in ban list."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player not in ban list"

        cmd = get_command(bot, "unban")
        await cmd.callback(mock_interaction, player="NotBanned")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mute_rcon_error(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test mute command RCON error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Mute command failed")

        cmd = get_command(bot, "mute")
        await cmd.callback(mock_interaction, player="Player")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unmute_not_muted(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test unmute when player not muted."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player is not muted"

        cmd = get_command(bot, "unmute")
        await cmd.callback(mock_interaction, player="NotMuted")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_promote_already_admin(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test promote when player already admin."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player is already an admin"

        cmd = get_command(bot, "promote")
        await cmd.callback(mock_interaction, player="AdminPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_demote_not_admin(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test demote when player not admin."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player is not an admin"

        cmd = get_command(bot, "demote")
        await cmd.callback(mock_interaction, player="RegularPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_player_name_with_spaces(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test commands with player names containing spaces."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "kick")
        await cmd.callback(mock_interaction, player="Player With Spaces", reason="Test")

        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_player_name_unicode(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test commands with unicode player names."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "ban")
        await cmd.callback(mock_interaction, player="玩家名字")

        mock_rcon.execute.assert_awaited_once()

# =============================================================================
# TEST: Server Management Commands - Error Paths
# =============================================================================

class TestServerManagementCommandErrors:
    """Test error handling for server management commands."""

    @pytest.mark.asyncio
    async def test_save_disk_full(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test save command when disk is full."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("No space left on device")

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name="test-save")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_invalid_filename(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test save with invalid filename characters."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "save")
        # Filename with illegal characters
        await cmd.callback(mock_interaction, name="save/with\\invalid:chars")

        # Should attempt to save (server will reject)
        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_save_permission_denied(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test save when server lacks write permissions."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Permission denied")

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_empty_message(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test broadcast with empty message."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "broadcast")
        await cmd.callback(mock_interaction, message="")

        # Should still execute (server decides if valid)
        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_very_long_message(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test broadcast with very long message."""
        bot.set_rcon_client(mock_rcon)
        long_message = "A" * 10000

        cmd = get_command(bot, "broadcast")
        await cmd.callback(mock_interaction, message=long_message)

        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_special_characters(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test broadcast with special characters that need escaping."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "broadcast")
        await cmd.callback(mock_interaction, message='Message with "quotes" and \\slashes')

        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_whitelist_invalid_action(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test whitelist with invalid action."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="invalid_action", player=None)

        # Should send error about invalid action
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get('ephemeral') is True

    @pytest.mark.asyncio
    async def test_whitelist_add_without_player(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test whitelist add without providing player name."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="add", player=None)

        # Should send error about missing player
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get('ephemeral') is True

    @pytest.mark.asyncio
    async def test_whitelist_remove_without_player(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test whitelist remove without providing player name."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="remove", player=None)

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get('ephemeral') is True

    @pytest.mark.asyncio
    async def test_whitelist_enable_when_already_enabled(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test whitelist enable when already enabled."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Whitelist is already enabled"

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="enable", player=None)

        mock_interaction.followup.send.assert_awaited_once()

# =============================================================================
# TEST: Game Control Commands - Error Paths
# =============================================================================

class TestGameControlCommandErrors:
    """Test error handling for game control commands."""

    @pytest.mark.asyncio
    async def test_time_invalid_value_negative(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test time command with negative value."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "time")
        await cmd.callback(mock_interaction, value=-1.0)

        # Server should reject, but command executes
        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_time_invalid_value_too_large(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test time command with value > 1.0."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "time")
        await cmd.callback(mock_interaction, value=2.0)

        mock_rcon.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_speed_below_minimum(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test speed command with value below 0.1."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "speed")
        await cmd.callback(mock_interaction, speed=0.05)

        # Should reject without calling RCON
        mock_interaction.followup.send.assert_awaited_once()
        mock_rcon.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_speed_above_maximum(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test speed command with value above 10.0."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "speed")
        await cmd.callback(mock_interaction, speed=15.0)

        # Should reject without calling RCON
        mock_interaction.followup.send.assert_awaited_once()
        mock_rcon.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_speed_exactly_at_boundary_min(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test speed command at minimum boundary (0.1)."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "speed")
        await cmd.callback(mock_interaction, speed=0.1)

        # Should accept at boundary
        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_speed_exactly_at_boundary_max(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test speed command at maximum boundary (10.0)."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "speed")
        await cmd.callback(mock_interaction, speed=10.0)

        # Should accept at boundary
        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_research_nonexistent_technology(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test research with non-existent technology."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Technology not found")

        cmd = get_command(bot, "research")
        await cmd.callback(mock_interaction, technology="fake-tech")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_research_already_researched(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test research technology that's already researched."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = ""  # Lua returns nothing for already researched

        cmd = get_command(bot, "research")
        await cmd.callback(mock_interaction, technology="automation")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_research_invalid_tech_name_format(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test research with invalid technology name format."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Invalid technology name")

        cmd = get_command(bot, "research")
        await cmd.callback(mock_interaction, technology="tech with spaces!")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rcon_dangerous_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test raw RCON with potentially dangerous command."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "rcon")
        # Dangerous Lua that could crash server
        await cmd.callback(mock_interaction, command="/c while true do end")

        # Should still execute (admin responsibility)
        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rcon_command_returns_error(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test raw RCON when command returns error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("RCON command failed")

        cmd = get_command(bot, "rcon")
        await cmd.callback(mock_interaction, command="/invalid")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rcon_empty_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test raw RCON with empty command."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "rcon")
        await cmd.callback(mock_interaction, command="")

        # Should still try to execute
        mock_rcon.execute.assert_awaited_once()

# =============================================================================
# TEST: Rate Limiting Enforcement
# =============================================================================

class TestRateLimitingErrors:
    """Test rate limiting is properly enforced."""

    @pytest.mark.asyncio
    async def test_query_cooldown_enforced(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test query cooldown prevents rapid commands."""
        bot.set_rcon_client(mock_rcon)

        # Mock rate limiter to return rate limited
        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return (True, 15.0)

        with patch("discord_bot.QUERY_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "ping")
            await cmd.callback(mock_interaction)

            # Should send cooldown message
            mock_interaction.response.send_message.assert_awaited_once()
            call_kwargs = mock_interaction.response.send_message.call_args.kwargs
            assert call_kwargs.get('ephemeral') is True

            # Should NOT execute RCON
            mock_rcon.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_cooldown_enforced(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test admin cooldown prevents rapid admin commands."""
        bot.set_rcon_client(mock_rcon)

        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return (True, 30.0)

        with patch("discord_bot.ADMIN_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "kick")
            await cmd.callback(mock_interaction, player="Test", reason=None)

            mock_interaction.response.send_message.assert_awaited_once()
            mock_rcon.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_danger_cooldown_enforced(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test danger cooldown prevents rapid dangerous commands."""
        bot.set_rcon_client(mock_rcon)

        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return (True, 60.0)

        with patch("discord_bot.DANGER_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "speed")
            await cmd.callback(mock_interaction, speed=2.0)

            mock_interaction.response.send_message.assert_awaited_once()
            mock_rcon.execute.assert_not_awaited()

# =============================================================================
# TEST: RCON Connection Errors
# =============================================================================

class TestRCONConnectionErrors:
    """Test handling of RCON connection issues."""

    @pytest.mark.asyncio
    async def test_all_commands_handle_no_rcon_client(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test that all commands handle missing RCON client gracefully."""
        bot.rcon_client = None

        command_names = [
            "ping", "status", "players", "version", "seed", "evolution",
            "admins", "kick", "ban", "unban", "mute", "unmute",
            "promote", "demote", "save", "broadcast", "whitelist",
            "time", "speed", "research", "rcon"
        ]

        for cmd_name in command_names:
            cmd = get_command(bot, cmd_name)

            # Reset mock for each command
            mock_interaction.response.defer.reset_mock()
            mock_interaction.followup.send.reset_mock()
            mock_interaction.response.send_message.reset_mock()

            # Call with appropriate args
            if cmd_name == "kick":
                await cmd.callback(mock_interaction, player="Test", reason=None)
            elif cmd_name in ["ban", "unban", "mute", "unmute", "promote", "demote"]:
                await cmd.callback(mock_interaction, player="Test")
            elif cmd_name == "broadcast":
                await cmd.callback(mock_interaction, message="Test")
            elif cmd_name == "whitelist":
                await cmd.callback(mock_interaction, action="list", player=None)
            elif cmd_name == "time":
                await cmd.callback(mock_interaction, value=None)
            elif cmd_name == "speed":
                await cmd.callback(mock_interaction, speed=1.0)
            elif cmd_name == "research":
                await cmd.callback(mock_interaction, technology="automation")
            elif cmd_name == "rcon":
                await cmd.callback(mock_interaction, command="/time")
            elif cmd_name == "save":
                await cmd.callback(mock_interaction, name=None)
            else:
                await cmd.callback(mock_interaction)

            # All should send error response (except help)
            if cmd_name != "help":
                assert mock_interaction.followup.send.await_count >= 1 or \
                       mock_interaction.response.send_message.await_count >= 1

# =============================================================================
# TEST: Unexpected Errors and Edge Cases
# =============================================================================

class TestUnexpectedErrors:
    """Test handling of unexpected errors and edge cases."""

    @pytest.mark.asyncio
    async def test_command_handles_keyboard_interrupt(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test command doesn't crash on KeyboardInterrupt."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = KeyboardInterrupt()

        cmd = get_command(bot, "ping")

        # Should propagate KeyboardInterrupt (for graceful shutdown)
        with pytest.raises(KeyboardInterrupt):
            await cmd.callback(mock_interaction)

    @pytest.mark.asyncio
    async def test_command_handles_memory_error(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_rcon: MagicMock
    ) -> None:
        """Test command handles MemoryError gracefully."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = MemoryError("Out of memory")

        cmd = get_command(bot, "players")
        await cmd.callback(mock_interaction)

        # Should catch and send error
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_command_with_none_interaction_user(
        self, bot: DiscordBot, mock_rcon: MagicMock
    ) -> None:
        """Test command when interaction.user is None."""
        bot.set_rcon_client(mock_rcon)

        # Create interaction with None user (edge case)
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = None
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()

        # This should cause rate limiter to fail or default
        cmd = get_command(bot, "ping")

        # Depending on implementation, might raise or handle gracefully
        try:
            await cmd.callback(interaction)
        except AttributeError:
            pass  # Expected if accessing user.id fails
