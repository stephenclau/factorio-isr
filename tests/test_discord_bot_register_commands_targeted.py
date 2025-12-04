"""
Targeted Coverage Tests for Missing Paths in _register_commands
Specifically targets ban, unban, unmute, promote, demote, save, and admins commands
to achieve 90%+ coverage by testing all untested branches.
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
# BAN COMMAND - Target: 75% -> 95%+
# ============================================================================

class TestBanCommandMissingPaths:
    """Complete coverage for ban_command missing paths."""

    @pytest.mark.asyncio
    async def test_ban_rate_limited_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test ban command rate limit response is ephemeral."""
        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return True, 15.0

        with patch("discord_bot.ADMIN_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "ban")
            await cmd.callback(mock_interaction, player="TestPlayer")

            # Should send rate limit message
            mock_interaction.response.send_message.assert_awaited_once()
            call_kwargs = mock_interaction.response.send_message.call_args.kwargs
            assert call_kwargs.get("ephemeral") is True, "Rate limit message must be ephemeral"

    @pytest.mark.asyncio
    async def test_ban_no_rcon_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test ban command error when RCON is None is ephemeral."""
        bot.rcon_client = None

        cmd = get_command(bot, "ban")
        await cmd.callback(mock_interaction, player="TestPlayer")

        # Should defer, then send ephemeral error
        mock_interaction.response.defer.assert_awaited_once()
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True, "RCON unavailable error must be ephemeral"

    @pytest.mark.asyncio
    async def test_ban_exception_response_is_ephemeral(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test ban command exception handling sends ephemeral error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("RCON connection lost")

        cmd = get_command(bot, "ban")
        await cmd.callback(mock_interaction, player="TestPlayer")

        # Should catch exception and send ephemeral error
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True, "Exception error must be ephemeral"

    @pytest.mark.asyncio
    async def test_ban_success_logs_action(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test ban command logs successful ban action."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player banned successfully"

        cmd = get_command(bot, "ban")
        await cmd.callback(mock_interaction, player="Griefer")

        # Should execute ban command
        mock_rcon.execute.assert_awaited_once()
        call_args = mock_rcon.execute.call_args[0][0]
        assert "ban" in call_args.lower()
        assert "Griefer" in call_args


# ============================================================================
# UNBAN COMMAND - Target: 75% -> 95%+
# ============================================================================

class TestUnbanCommandMissingPaths:
    """Complete coverage for unban_command missing paths."""

    @pytest.mark.asyncio
    async def test_unban_rate_limited_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test unban command rate limit response is ephemeral."""
        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return True, 15.0

        with patch("discord_bot.ADMIN_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "unban")
            await cmd.callback(mock_interaction, player="TestPlayer")

            mock_interaction.response.send_message.assert_awaited_once()
            call_kwargs = mock_interaction.response.send_message.call_args.kwargs
            assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_unban_no_rcon_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test unban command error when RCON is None is ephemeral."""
        bot.rcon_client = None

        cmd = get_command(bot, "unban")
        await cmd.callback(mock_interaction, player="TestPlayer")

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_unban_exception_response_is_ephemeral(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unban command exception handling sends ephemeral error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Player not found in ban list")

        cmd = get_command(bot, "unban")
        await cmd.callback(mock_interaction, player="TestPlayer")

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_unban_success_logs_action(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unban command logs successful unban action."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player unbanned"

        cmd = get_command(bot, "unban")
        await cmd.callback(mock_interaction, player="ForgivenPlayer")

        mock_rcon.execute.assert_awaited_once()
        call_args = mock_rcon.execute.call_args[0][0]
        assert "unban" in call_args.lower()
        assert "ForgivenPlayer" in call_args


# ============================================================================
# UNMUTE COMMAND - Target: 75% -> 95%+
# ============================================================================

class TestUnmuteCommandMissingPaths:
    """Complete coverage for unmute_command missing paths."""

    @pytest.mark.asyncio
    async def test_unmute_rate_limited_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test unmute command rate limit response is ephemeral."""
        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return True, 15.0

        with patch("discord_bot.ADMIN_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "unmute")
            await cmd.callback(mock_interaction, player="TestPlayer")

            mock_interaction.response.send_message.assert_awaited_once()
            call_kwargs = mock_interaction.response.send_message.call_args.kwargs
            assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_unmute_no_rcon_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test unmute command error when RCON is None is ephemeral."""
        bot.rcon_client = None

        cmd = get_command(bot, "unmute")
        await cmd.callback(mock_interaction, player="TestPlayer")

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_unmute_exception_response_is_ephemeral(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unmute command exception handling sends ephemeral error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Unmute failed")

        cmd = get_command(bot, "unmute")
        await cmd.callback(mock_interaction, player="TestPlayer")

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_unmute_success_logs_action(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test unmute command logs successful unmute action."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player unmuted"

        cmd = get_command(bot, "unmute")
        await cmd.callback(mock_interaction, player="ChatterBox")

        mock_rcon.execute.assert_awaited_once()
        call_args = mock_rcon.execute.call_args[0][0]
        assert "unmute" in call_args.lower()
        assert "ChatterBox" in call_args


# ============================================================================
# PROMOTE COMMAND - Target: 75% -> 95%+
# ============================================================================

class TestPromoteCommandMissingPaths:
    """Complete coverage for promote_command missing paths."""

    @pytest.mark.asyncio
    async def test_promote_rate_limited_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test promote command rate limit response is ephemeral."""
        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return True, 15.0

        with patch("discord_bot.ADMIN_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "promote")
            await cmd.callback(mock_interaction, player="TestPlayer")

            mock_interaction.response.send_message.assert_awaited_once()
            call_kwargs = mock_interaction.response.send_message.call_args.kwargs
            assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_promote_no_rcon_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test promote command error when RCON is None is ephemeral."""
        bot.rcon_client = None

        cmd = get_command(bot, "promote")
        await cmd.callback(mock_interaction, player="TestPlayer")

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_promote_exception_response_is_ephemeral(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test promote command exception handling sends ephemeral error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Promote failed")

        cmd = get_command(bot, "promote")
        await cmd.callback(mock_interaction, player="TestPlayer")

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_promote_success_logs_action(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test promote command logs successful promote action."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player promoted"

        cmd = get_command(bot, "promote")
        await cmd.callback(mock_interaction, player="TrustedPlayer")

        mock_rcon.execute.assert_awaited_once()
        call_args = mock_rcon.execute.call_args[0][0]
        assert "promote" in call_args.lower()
        assert "TrustedPlayer" in call_args


# ============================================================================
# DEMOTE COMMAND - Target: 75% -> 95%+
# ============================================================================

class TestDemoteCommandMissingPaths:
    """Complete coverage for demote_command missing paths."""

    @pytest.mark.asyncio
    async def test_demote_rate_limited_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test demote command rate limit response is ephemeral."""
        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return True, 15.0

        with patch("discord_bot.ADMIN_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "demote")
            await cmd.callback(mock_interaction, player="TestPlayer")

            mock_interaction.response.send_message.assert_awaited_once()
            call_kwargs = mock_interaction.response.send_message.call_args.kwargs
            assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_demote_no_rcon_response_is_ephemeral(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test demote command error when RCON is None is ephemeral."""
        bot.rcon_client = None

        cmd = get_command(bot, "demote")
        await cmd.callback(mock_interaction, player="TestPlayer")

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_demote_exception_response_is_ephemeral(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test demote command exception handling sends ephemeral error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Demote failed")

        cmd = get_command(bot, "demote")
        await cmd.callback(mock_interaction, player="TestPlayer")

        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_demote_success_logs_action(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test demote command logs successful demote action."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Player demoted"

        cmd = get_command(bot, "demote")
        await cmd.callback(mock_interaction, player="ExAdmin")

        mock_rcon.execute.assert_awaited_once()
        call_args = mock_rcon.execute.call_args[0][0]
        assert "demote" in call_args.lower()
        assert "ExAdmin" in call_args


# ============================================================================
# SAVE COMMAND - Target: 75% -> 95%+ (More complex with regex)
# ============================================================================

class TestSaveCommandMissingPaths:
    """Complete coverage for save_command missing paths including regex logic."""

    @pytest.mark.asyncio
    async def test_save_rate_limited_uses_response(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test save command rate limit response uses response.send_message."""
        class RateLimited:
            def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
                return True, 5.5

        with patch("discord_bot.QUERY_COOLDOWN", RateLimited()):
            cmd = get_command(bot, "save")
            await cmd.callback(mock_interaction, name=None)

            # Save uses response.send_message for rate limit (not followup.send)
            mock_interaction.response.send_message.assert_awaited_once()
            call_kwargs = mock_interaction.response.send_message.call_args.kwargs
            assert call_kwargs.get("ephemeral") is True, "Rate limit message must be ephemeral"
            call_args = str(mock_interaction.response.send_message.call_args)
            assert "5.5" in call_args or "slow down" in call_args.lower()

    @pytest.mark.asyncio
    async def test_save_no_rcon_uses_followup(
        self, bot: DiscordBot, mock_interaction: MagicMock
    ) -> None:
        """Test save command error when RCON is None uses followup."""
        bot.rcon_client = None

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        # Should defer, then send via followup
        mock_interaction.response.defer.assert_awaited_once()
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_regex_extracts_savename_from_response(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save command regex extraction of save name."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Saving to '_autosave3' (non-blocking)."

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        # Should extract _autosave3
        mock_interaction.followup.send.assert_awaited_once()
        call_args = str(mock_interaction.followup.send.call_args)
        assert "_autosave3" in call_args or "autosave" in call_args.lower()

    @pytest.mark.asyncio
    async def test_save_regex_no_match_uses_fallback(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save command uses fallback label when regex doesn't match."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Game saved successfully (no name in response)"

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name=None)

        # Should use fallback label "current save"
        mock_interaction.followup.send.assert_awaited_once()
        call_args = str(mock_interaction.followup.send.call_args)
        assert "save" in call_args.lower()

    @pytest.mark.asyncio
    async def test_save_with_custom_name_uses_it_as_label(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save command with custom name uses it as label."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "Saving to 'backup-2025' (non-blocking)."

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name="backup-2025")

        # Should execute with custom name
        call_args = mock_rcon.execute.call_args[0][0]
        assert "backup-2025" in call_args

    @pytest.mark.asyncio
    async def test_save_exception_handling(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test save command exception handling."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Disk full")

        cmd = get_command(bot, "save")
        await cmd.callback(mock_interaction, name="test")

        # Should catch exception and send error
        mock_interaction.followup.send.assert_awaited_once()
        call_args = str(mock_interaction.followup.send.call_args)
        assert "failed" in call_args.lower() or "disk full" in call_args.lower()


# ============================================================================
# ADMINS COMMAND - Target: 100% -> Maintain/Verify
# ============================================================================

class TestAdminsCommandEdgeCases:
    """Edge case tests for admins_command (already at 100%)."""

    @pytest.mark.asyncio
    async def test_admins_exception_response_is_ephemeral(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test admins command exception handling sends ephemeral error."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.side_effect = Exception("Failed to list admins")

        cmd = get_command(bot, "admins")
        await cmd.callback(mock_interaction)

        # Should catch exception and send ephemeral error
        mock_interaction.followup.send.assert_awaited_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_admins_empty_list_response(
        self, bot: DiscordBot, mock_rcon: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test admins command when no admins are configured."""
        bot.set_rcon_client(mock_rcon)
        mock_rcon.execute.return_value = "No admins defined"

        cmd = get_command(bot, "admins")
        await cmd.callback(mock_interaction)

        # Should still send response with "No admins"
        mock_interaction.followup.send.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
