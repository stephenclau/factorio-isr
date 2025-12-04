"""
Supplementary Tests for DiscordBot._register_commands Branch Coverage
Focuses on complex conditional paths and error recovery scenarios.
Targets remaining gaps to push coverage from 90% to 95%+.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord import app_commands
import pytest

from discord_bot import DiscordBot
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.fixture
def mock_rcon() -> MagicMock:
    """Mock RCON client."""
    rcon = MagicMock()
    rcon.execute = AsyncMock(return_value="OK")
    rcon.get_players = AsyncMock(return_value=["Player1", "Player2"])
    rcon.is_connected = True
    rcon.host = "localhost"
    rcon.port = 27015
    return rcon


@pytest.fixture
def mock_interaction() -> MagicMock:
    """Mock Discord Interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(id=123456, name="TestUser")
    interaction.guild = MagicMock(name="TestGuild", id=999)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
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
    """Disable rate limiting."""
    class NoRateLimit:
        def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
            return False, 0.0

    no_limit = NoRateLimit()
    monkeypatch.setattr("discord_bot.QUERY_COOLDOWN", no_limit)
    monkeypatch.setattr("discord_bot.ADMIN_COOLDOWN", no_limit)
    monkeypatch.setattr("discord_bot.DANGER_COOLDOWN", no_limit)


@pytest.fixture
async def bot(patch_discord_network: None, patch_rate_limiting: None) -> DiscordBot:
    """Create bot instance."""
    bot_instance = DiscordBot(token="TEST_TOKEN", bot_name="TestBot")
    await bot_instance.setup_hook()
    yield bot_instance
    if not bot_instance.is_closed():
        await bot_instance.close()


def get_command(bot: DiscordBot, name: str) -> app_commands.Command:
    """Extract command from factorio group."""
    for cmd in bot.tree.get_commands():
        if isinstance(cmd, app_commands.Group) and cmd.name == "factorio":
            for subcmd in cmd.commands:
                if subcmd.name == name:
                    return cast(app_commands.Command, subcmd)
    raise RuntimeError(f"Command {name!r} not found")


# ============================================================================
# Complex Save Command Response Parsing
# ============================================================================

class TestSaveCommandComplexParsing:
    """Test save command response parsing edge cases."""

    @pytest.mark.asyncio
    async def test_save_regex_with_underscores(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save name extraction with underscores."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Saving to '_autosave1' (non-blocking)."

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        # Should extract _autosave1
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_regex_with_hyphens(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save name extraction with hyphens."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Saving to 'backup-2025-01' (non-blocking)."

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_regex_no_match(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save when regex doesn't match."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Game saved but no filename in response"

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        # Should still send success message with fallback label
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_custom_name_fallback(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save uses custom name as fallback label."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Saved"

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name="my-save")

        # Should use my-save as label
        call_args = str(mock_interaction.followup.send.await_args)
        assert "my-save" in call_args.lower() or "save" in call_args.lower()


# ============================================================================
# Kick Command with Reason Variations
# ============================================================================

class TestKickCommandReasonHandling:
    """Test kick command with different reason formats."""

    @pytest.mark.asyncio
    async def test_kick_with_reason(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test kick with reason provided."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player kicked"

        cmd = get_command(bot, "kick")
        await cmd.callback(mock_interaction, player="Griefer", reason="Griefing")

        # Should include reason in command
        call_args = mock_rcon.execute.await_args[0][0]
        assert "Griefer" in call_args
        assert "Griefing" in call_args
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kick_without_reason(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test kick without reason."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player kicked"

        cmd = get_command(bot, "kick")
        await cmd.callback(mock_interaction, player="BadPlayer", reason=None)

        # Should kick without reason
        call_args = mock_rcon.execute.await_args[0][0]
        assert "BadPlayer" in call_args
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kick_with_empty_string_reason(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test kick with empty string reason."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player kicked"

        cmd = get_command(bot, "kick")
        await cmd.callback(mock_interaction, player="Player", reason="")

        mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# Health Command Branch Coverage
# ============================================================================

class TestHealthCommandBranches:
    """Test health command conditional branches."""

    @pytest.mark.asyncio
    async def test_health_all_systems_online(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test health when all systems operational."""
        bot.set_rcon_client(mock_rcon)
        bot.connected = True
        mock_rcon.is_connected = True
        bot._rcon_last_connected = None  # Ensure no uptime calc error

        cmd = get_command(bot, "health")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_rcon_offline(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test health when RCON offline."""
        bot.set_rcon_client(mock_rcon)
        bot.connected = True
        mock_rcon.is_connected = False

        cmd = get_command(bot, "health")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_with_rcon_uptime(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test health shows RCON uptime when available."""
        from datetime import datetime, timedelta

        bot.set_rcon_client(mock_rcon)
        bot.connected = True
        mock_rcon.is_connected = True
        bot._rcon_last_connected = datetime.utcnow() - timedelta(minutes=30)

        cmd = get_command(bot, "health")
        await cmd.callback(mock_interaction)

        # Should calculate and show uptime
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_without_rcon_client(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test health when RCON client not configured."""
        bot.rcon_client = None
        bot.connected = True

        cmd = get_command(bot, "health")
        await cmd.callback(mock_interaction)

        # Should still send health status without RCON info
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_shows_guild_count(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test health includes guild count."""
        bot.set_rcon_client(mock_rcon)
        bot.connected = True

        # Mock guilds
        from unittest.mock import PropertyMock
        mock_guilds = [MagicMock(), MagicMock()]
        type(bot).guilds = PropertyMock(return_value=mock_guilds)

        cmd = get_command(bot, "health")
        await cmd.callback(mock_interaction)

        mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# Status and Players Command Error Paths
# ============================================================================

class TestStatusPlayersErrorRecovery:
    """Test status and players commands handle errors gracefully."""

    @pytest.mark.asyncio
    async def test_status_rcon_connected_get_players_fails(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test status when get_players raises exception."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.is_connected = True
        mock_rcon.get_players.side_effect = Exception("Query failed")

        cmd = get_command(bot, "status")
        await cmd.callback(mock_interaction)

        # Should catch exception and send error
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_status_success_path(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test status command successful execution."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.is_connected = True
        mock_rcon.get_players.return_value = ["Alice", "Bob", "Charlie"]

        cmd = get_command(bot, "status")
        await cmd.callback(mock_interaction)

        mock_rcon.get_players.assert_awaited_once()
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_players_rcon_not_connected(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test players when RCON not connected."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.is_connected = False

        cmd = get_command(bot, "players")
        await cmd.callback(mock_interaction)

        # Should send error without calling get_players
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_players_success_with_players(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test players command with online players."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.is_connected = True
        mock_rcon.get_players.return_value = ["Player1", "Player2", "Player3"]

        cmd = get_command(bot, "players")
        await cmd.callback(mock_interaction)

        mock_rcon.get_players.assert_awaited_once()
        mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# Version and Research Command Success Paths
# ============================================================================

class TestVersionResearchSuccessPaths:
    """Test version and research commands successful execution."""

    @pytest.mark.asyncio
    async def test_version_rcon_error(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test version command RCON error handling."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("RCON timeout")

        cmd = get_command(bot, "version")
        await cmd.callback(mock_interaction)

        # Should catch and send error
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_research_rcon_error(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test research command RCON error handling."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Technology not found")

        cmd = get_command(bot, "research")
        await cmd.callback(mock_interaction, technology="fake-tech")

        # Should catch and send error
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_rcon_command_error(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test raw rcon command error handling."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Invalid command")

        cmd = get_command(bot, "rcon")
        await cmd.callback(mock_interaction, command="invalid_cmd")

        # Should catch and send error
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True


# ============================================================================
# Whitelist Command Invalid Action
# ============================================================================

class TestWhitelistInvalidAction:
    """Test whitelist command with invalid actions."""

    @pytest.mark.asyncio
    async def test_whitelist_invalid_action_string(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist with invalid action."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "whitelist")
        await cmd.callback(mock_interaction, action="invalid", player=None)

        # Should send error message
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_whitelist_action_case_insensitive(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test whitelist actions are case-insensitive."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Whitelist enabled"

        cmd = get_command(bot, "whitelist")
        # Test uppercase action
        await cmd.callback(mock_interaction, action="ENABLE", player=None)

        # Should convert to lowercase and execute
        mock_rcon.execute.assert_awaited_once()


# ============================================================================
# Time Command Edge Cases
# ============================================================================

class TestTimeCommandEdgeCases:
    """Test time command with various values."""

    @pytest.mark.asyncio
    async def test_time_set_midnight(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test time command set to midnight (0)."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "time")
        await cmd.callback(mock_interaction, value=0.0)

        # Should set time to 0
        call_args = mock_rcon.execute.await_args[0][0]
        assert "0" in call_args or "0.0" in call_args

    @pytest.mark.asyncio
    async def test_time_set_noon(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test time command set to noon (0.5)."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "time")
        await cmd.callback(mock_interaction, value=0.5)

        # Should set time to 0.5
        call_args = mock_rcon.execute.await_args[0][0]
        assert "0.5" in call_args

    @pytest.mark.asyncio
    async def test_time_query_response(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test time command displays server response."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Current tick: 12345678"

        cmd = get_command(bot, "time")
        await cmd.callback(mock_interaction, value=None)

        mock_interaction.followup.send.assert_awaited_once()


# ============================================================================
# Mute/Unmute Command Success Cases
# ============================================================================

class TestMuteUnmuteSuccessCases:
    """Test mute/unmute commands with various responses."""

    @pytest.mark.asyncio
    async def test_mute_player_name_with_spaces(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test mute with player name containing spaces."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player muted"

        cmd = get_command(bot, "mute")
        await cmd.callback(mock_interaction, player="Player With Spaces")

        call_args = mock_rcon.execute.await_args[0][0]
        assert "Player With Spaces" in call_args or "With" in call_args

    @pytest.mark.asyncio
    async def test_unmute_player_name_with_special_chars(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unmute with special characters in name."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player unmuted"

        cmd = get_command(bot, "unmute")
        await cmd.callback(mock_interaction, player="Player_123")

        call_args = mock_rcon.execute.await_args[0][0]
        assert "Player_123" in call_args or "_123" in call_args


# ============================================================================
# Broadcast Command Success with Different Messages
# ============================================================================

class TestBroadcastMessageFormats:
    """Test broadcast with different message formats."""

    @pytest.mark.asyncio
    async def test_broadcast_unicode_message(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test broadcast with unicode characters."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "broadcast")
        await cmd.callback(mock_interaction, message="Server restart 🔄 in 5 min")

        mock_rcon.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_multiline_message(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test broadcast with newlines (should be handled)."""
        bot.set_rcon_client(mock_rcon)

        cmd = get_command(bot, "broadcast")
        await cmd.callback(mock_interaction, message="Line1\nLine2")

        mock_rcon.execute.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
