"""
Comprehensive Edge Case Tests for DiscordBot._register_commands
Targets gaps in command coverage to achieve 95%+ overall coverage.
Focuses on error paths, response parsing, and optional parameters.
"""
from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import discord
from discord import app_commands
import pytest

from discord_bot import DiscordBot
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


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
            return False, 0.0

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


# ============================================================================
# PRIORITY 1: help_command (56% coverage -> 100%)
# ============================================================================

class TestHelpCommandComplete:
    """Complete coverage for help_command - CORRECTED to match implementation."""

    @pytest.mark.asyncio
    async def test_help_command_sends_response(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test help command sends a response."""
        cmd = get_command(bot, "help")
        await cmd.callback(mock_interaction)

        # Help command uses send_message directly (not defer + followup)
        mock_interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_help_command_sends_text_content(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test help command sends text content (not embed)."""
        cmd = get_command(bot, "help")
        await cmd.callback(mock_interaction)

        # Get the call arguments
        call_args = mock_interaction.response.send_message.call_args
        assert call_args is not None

        # Help text should be sent as positional arg or content kwarg
        has_content = (
            (call_args.args and isinstance(call_args.args[0], str) and len(call_args.args[0]) > 50) or
            ("content" in call_args.kwargs and len(str(call_args.kwargs.get("content", ""))) > 50)
        )
        assert has_content, "Help command should send substantial text content"

    @pytest.mark.asyncio
    async def test_help_command_contains_command_info(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test help command includes command information."""
        cmd = get_command(bot, "help")
        await cmd.callback(mock_interaction)

        call_args = mock_interaction.response.send_message.call_args
        # Get the message content
        if call_args.args:
            content = str(call_args.args[0])
        else:
            content = str(call_args.kwargs.get("content", ""))

        # Should be a substantial help message
        assert len(content) > 100, "Help message should be substantial (>100 chars)"

    @pytest.mark.asyncio
    async def test_help_command_rate_limited(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test help command respects rate limiting."""
        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return True, 10.0

        with patch("discord_bot.QUERY_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "help")
            await cmd.callback(mock_interaction)

            # Should still respond (with cooldown message via embed)
            mock_interaction.response.send_message.assert_awaited_once()

            # Cooldown message should be ephemeral
            call_kwargs = mock_interaction.response.send_message.call_args.kwargs
            assert call_kwargs.get("ephemeral") is True


# ============================================================================
# PRIORITY 2: Error Response Parsing (65-84% coverage commands)
# ============================================================================

class TestPlayerManagementErrorPaths:
    """Test error responses from server for player management."""

    @pytest.mark.asyncio
    async def test_ban_player_not_found(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test ban when player doesn't exist."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Error: Player 'NonExistent' not found."

        cmd = get_command(bot, "ban")
        await cmd.callback(mock_interaction, player="NonExistent")

        # Should still send response
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ban_already_banned(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test ban when player already banned."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player is already banned."

        cmd = get_command(bot, "ban")
        await cmd.callback(mock_interaction, player="BannedPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unban_not_in_ban_list(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unban when player not banned."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player is not in the ban list."

        cmd = get_command(bot, "unban")
        await cmd.callback(mock_interaction, player="CleanPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unban_success_response(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unban with successful response."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player unbanned successfully."

        cmd = get_command(bot, "unban")
        await cmd.callback(mock_interaction, player="ForgivenPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mute_success(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test mute command successful execution."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player muted."

        cmd = get_command(bot, "mute")
        await cmd.callback(mock_interaction, player="ChatterBox")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unmute_success(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unmute command successful execution."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player unmuted."

        cmd = get_command(bot, "unmute")
        await cmd.callback(mock_interaction, player="SilentPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unmute_not_muted(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unmute when player not muted."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player is not muted."

        cmd = get_command(bot, "unmute")
        await cmd.callback(mock_interaction, player="LoudPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_promote_already_admin(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test promote when player already admin."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player is already an admin."

        cmd = get_command(bot, "promote")
        await cmd.callback(mock_interaction, player="AdminPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_promote_success(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test promote command successful execution."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player promoted to admin."

        cmd = get_command(bot, "promote")
        await cmd.callback(mock_interaction, player="TrustedPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_demote_not_admin(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test demote when player not admin."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player is not an admin."

        cmd = get_command(bot, "demote")
        await cmd.callback(mock_interaction, player="RegularPlayer")

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_demote_success(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test demote command successful execution."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player demoted from admin."

        cmd = get_command(bot, "demote")
        await cmd.callback(mock_interaction, player="ExAdmin")

        mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# PRIORITY 3: Optional Parameters and Branch Coverage
# ============================================================================

class TestSaveCommandResponseParsing:
    """Test save command with different response formats."""

    @pytest.mark.asyncio
    async def test_save_with_parseable_name(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save parsing name from response."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Saving to '_autosave1' (non-blocking)."

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_without_parseable_name(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save when response doesn't contain save name."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Game saved successfully."

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_with_custom_name(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save with custom save name."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Saving to 'backup-2025' (non-blocking)."

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name="backup-2025")

        # Should execute with custom name
        assert "backup-2025" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_error_handling(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save handles errors gracefully."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Disk full")

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name="test")

        mock_interaction.followup.send.assert_awaited_once()


class TestBroadcastCommandEdgeCases:
    """Test broadcast with different message types."""

    @pytest.mark.asyncio
    async def test_broadcast_simple_message(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test broadcast with simple message."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "broadcast")
        await cmd.callback(mock_interaction, message="Server restart in 5 min")

        mock_rcon.execute.assert_awaited_once()
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_quotes(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test broadcast escapes quotes properly."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "broadcast")
        await cmd.callback(mock_interaction, message='Message with "quotes"')

        # Message should be escaped
        call_args = mock_rcon.execute.await_args[0][0]
        assert "\\" in call_args or "quote" in mock_interaction.followup.send.await_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_broadcast_error_handling(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test broadcast handles RCON errors."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("RCON error")

        cmd = get_command(bot, "broadcast")
        await cmd.callback(mock_interaction, message="Test")

        mock_interaction.followup.send.assert_awaited_once()


class TestWhitelistCommandAllActions:
    """Test all whitelist action branches."""

    @pytest.mark.asyncio
    async def test_whitelist_list_action(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist list action."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player1, Player2, Player3"

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="list", player=None)

        assert "whitelist get" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_whitelist_enable_action(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist enable action."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Whitelist enabled"

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="enable", player=None)

        assert "whitelist enable" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_whitelist_disable_action(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist disable action."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Whitelist disabled"

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="disable", player=None)

        assert "whitelist disable" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_whitelist_add_with_player(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist add with player name."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Added to whitelist"

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="add", player="NewPlayer")

        assert "whitelist add" in mock_rcon.execute.await_args[0][0]
        assert "NewPlayer" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_whitelist_remove_with_player(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist remove with player name."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Removed from whitelist"

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="remove", player="OldPlayer")

        assert "whitelist remove" in mock_rcon.execute.await_args[0][0]
        assert "OldPlayer" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_whitelist_add_without_player(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist add without player name (error case)."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="add", player=None)

        # Should send error
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_whitelist_remove_without_player(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist remove without player name (error case)."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="remove", player=None)

        # Should send error
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True


class TestTimeCommandModes:
    """Test time command in display vs set modes."""

    @pytest.mark.asyncio
    async def test_time_display_current(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test time command displays current time."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "12345"

        cmd = get_command(bot, "time")
        await cmd.callback(mock_interaction, value=None)

        # Should query time
        assert "/time" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_time_set_value(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test time command sets specific time."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "time")
        await cmd.callback(mock_interaction, value=0.5)

        # Should set time to 0.5 (noon)
        call_args = mock_rcon.execute.await_args[0][0]
        assert "0.5" in call_args
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_time_error_handling(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test time command handles RCON errors."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Invalid time")

        cmd = get_command(bot, "time")
        await cmd.callback(mock_interaction, value=0.75)

        mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# PRIORITY 4: RCON Exception Handling and Edge Cases
# ============================================================================

class TestServerInfoCommandsRCONErrors:
    """Test server info commands handle RCON errors."""

    @pytest.mark.asyncio
    async def test_status_rcon_disconnected_during_query(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test status when RCON disconnects during query."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.is_connected = True
        mock_rcon.get_players.side_effect = ConnectionError("Lost connection")

        cmd = get_command(bot, "status")
        await cmd.callback(mock_interaction)

        # Should send error message
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_players_timeout_error(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test players command handles timeout."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.is_connected = True
        mock_rcon.get_players.side_effect = asyncio.TimeoutError()

        cmd = get_command(bot, "players")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_version_command_success(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test version command successful execution."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Factorio 1.1.110"

        cmd = get_command(bot, "version")
        await cmd.callback(mock_interaction)

        assert "version" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_research_command_success(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test research command successful execution."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Research queued"

        cmd = get_command(bot, "research")
        await cmd.callback(mock_interaction, technology="automation")

        assert "automation" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rcon_command_success(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test raw rcon command successful execution."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Command output"

        cmd = get_command(bot, "rcon")
        await cmd.callback(mock_interaction, command="/time")

        assert "/time" in mock_rcon.execute.await_args[0][0]
        mock_interaction.followup.send.assert_awaited_once()


class TestAdminsCommandEdgeCases:
    """Test admins command with different scenarios."""

    @pytest.mark.asyncio
    async def test_admins_command_success(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test admins command with admin list."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Admin1, Admin2, Admin3"

        cmd = get_command(bot, "admins")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_admins_command_no_admins(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test admins command when no admins configured."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "No admins defined."

        cmd = get_command(bot, "admins")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
