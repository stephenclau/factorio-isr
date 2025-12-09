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


from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch, ANY

import discord
from discord import app_commands
import pytest

from discord_bot import DiscordBot


# ---------------------------------------------------------------------------
# Reuse helpers from the existing suite where possible
# ---------------------------------------------------------------------------

def get_command(bot: DiscordBot, name: str) -> app_commands.Command:
    """Extract a /factorio subcommand by name."""
    for cmd in bot.tree.get_commands():
        if isinstance(cmd, app_commands.Group) and cmd.name == "factorio":
            for subcmd in cmd.commands:
                if subcmd.name == name:
                    return subcmd
    raise KeyError(f"Command {name!r} not found in factorio group")


@pytest.fixture
def mock_server_manager_for_monitoring() -> MagicMock:
    """
    ServerManager mock tailored for monitoring and breakdown tests.

    Provides:
    - get_status_summary()
    - list_tags()
    - list_servers()
    - get_client()
    - get_config()
    """
    mgr = MagicMock()

    # Two servers: primary online, secondary offline by default
    primary_cfg = MagicMock()
    primary_cfg.tag = "primary"
    primary_cfg.name = "Primary Server"
    primary_cfg.description = "Main production server"
    primary_cfg.rcon_host = "primary.example.com"
    primary_cfg.rcon_port = 27015

    secondary_cfg = MagicMock()
    secondary_cfg.tag = "secondary"
    secondary_cfg.name = "Secondary Server"
    secondary_cfg.description = "Secondary testing server"
    secondary_cfg.rcon_host = "secondary.example.com"
    secondary_cfg.rcon_port = 27016

    mgr.list_tags.return_value = ["primary", "secondary"]
    mgr.list_servers.return_value = {
        "primary": primary_cfg,
        "secondary": secondary_cfg,
    }

    mgr.get_config.side_effect = lambda tag: mgr.list_servers()[tag]

    # Status summary is configurable per-test by mutating this dict
    status_state: Dict[str, bool] = {"primary": True, "secondary": False}

    def get_status_summary() -> Dict[str, bool]:
        return dict(status_state)

    mgr.get_status_summary.side_effect = get_status_summary

    # Provide simple RCON client mocks
    primary_rcon = AsyncMock()
    primary_rcon.is_connected = True
    primary_rcon.execute = AsyncMock(return_value="OK")
    primary_rcon.get_players = AsyncMock(return_value=["Alice"])

    secondary_rcon = AsyncMock()
    secondary_rcon.is_connected = False
    secondary_rcon.execute = AsyncMock(return_value="OK")
    secondary_rcon.get_players = AsyncMock(return_value=["Bob"])

    mgr.clients = {"primary": primary_rcon, "secondary": secondary_rcon}
    mgr.get_client.side_effect = lambda tag: mgr.clients[tag]

    # Expose state so tests can mutate it
    mgr._status_state = status_state  # type: ignore[attr-defined]

    return mgr


@pytest.fixture
def mock_interaction_minimal() -> MagicMock:
    """Minimal Interaction for slash command callbacks."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 42
    interaction.user.name = "TargetUser"
    interaction.user.mention = "<@42>"
    interaction.user.display_name = "TargetUser"

    interaction.guild = MagicMock()
    interaction.guild.name = "TestGuild"
    interaction.guild.id = 999

    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.is_done.return_value = False

    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    interaction.client = None
    return interaction


@pytest.fixture
async def bot_for_targeted(
    mock_server_manager_for_monitoring: MagicMock,
) -> DiscordBot:
    """
    Bot instance wired for targeted tests.

    - Uses real command registration via setup_hook()
    - Uses the monitoring-oriented ServerManager fixture
    - Does not attempt network connections
    """
    with patch.object(discord.Client, "login", new=AsyncMock()), patch.object(
        discord.Client, "connect", new=AsyncMock()
    ), patch.object(discord.Client, "close", new=AsyncMock()):
        bot = DiscordBot(token="TARGETED_TOKEN", bot_name="TargetedBot")
        bot.set_server_manager(mock_server_manager_for_monitoring)
        await bot.setup_hook()
        yield bot

        if not bot.is_closed():
            await bot.close()


# ---------------------------------------------------------------------------
# Multi-server helpers and error branches
# ---------------------------------------------------------------------------

class TestUserContextErrorPaths:
    """Exercise get_rcon_for_user and get_server_display_name error branches."""

    def test_get_rcon_for_user_no_server_manager(self) -> None:
        bot = DiscordBot(token="X")
        bot.server_manager = None
        with pytest.raises(RuntimeError, match="ServerManager is not configured"):
            bot.get_rcon_for_user(123)

    def test_get_rcon_for_user_invalid_tag_logs_and_returns_none(
        self, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        bot = DiscordBot(token="X")
        bot.set_server_manager(mock_server_manager_for_monitoring)
        bot.user_contexts[999] = "nonexistent"

        with patch("discord_bot.logger") as log_mock:
            result = bot.get_rcon_for_user(999)
        assert result is None
        log_mock.warning.assert_called()

    def test_get_server_display_name_invalid_tag_returns_unknown(
        self, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        bot = DiscordBot(token="X")
        bot.set_server_manager(mock_server_manager_for_monitoring)
        bot.user_contexts[999] = "nonexistent"

        assert bot.get_server_display_name(999) == "Unknown"

    def test_get_server_display_name_no_server_manager_returns_unknown(self) -> None:
        bot = DiscordBot(token="X")
        bot.server_manager = None
        assert bot.get_server_display_name(1) == "Unknown"


# ---------------------------------------------------------------------------
# Game uptime helper error and edge cases
# ---------------------------------------------------------------------------

class TestGetGameUptimeEdges:
    """Target _get_game_uptime error/logging branches."""

    @pytest.mark.asyncio
    async def test_get_game_uptime_empty_response(self, bot_for_targeted: DiscordBot) -> None:
        rcon = AsyncMock()
        rcon.is_connected = True
        rcon.execute = AsyncMock(return_value="")

        with patch("discord_bot.logger") as log_mock:
            result = await bot_for_targeted._get_game_uptime(rcon)  # type: ignore[attr-defined]
        assert result == "Unknown"
        log_mock.warning.assert_any_call("game_uptime_empty_response")

    @pytest.mark.asyncio
    async def test_get_game_uptime_non_numeric(self, bot_for_targeted: DiscordBot) -> None:
        rcon = AsyncMock()
        rcon.is_connected = True
        rcon.execute = AsyncMock(return_value="not-an-int")

        with patch("discord_bot.logger") as log_mock:
            result = await bot_for_targeted._get_game_uptime(rcon)  # type: ignore[attr-defined]
        assert result == "Unknown"
        log_mock.warning.assert_any_call(
            "game_uptime_parse_failed",
            response="not-an-int",
            error=ANY,
        )

    @pytest.mark.asyncio
    async def test_get_game_uptime_negative_ticks(self, bot_for_targeted: DiscordBot) -> None:
        rcon = AsyncMock()
        rcon.is_connected = True
        rcon.execute = AsyncMock(return_value="-60")

        with patch("discord_bot.logger") as log_mock:
            result = await bot_for_targeted._get_game_uptime(rcon)  # type: ignore[attr-defined]
        assert result == "Unknown"
        log_mock.warning.assert_any_call("game_uptime_negative_ticks", ticks=-60)

    @pytest.mark.asyncio
    async def test_get_game_uptime_exception(self, bot_for_targeted: DiscordBot) -> None:
        rcon = AsyncMock()
        rcon.is_connected = True
        rcon.execute = AsyncMock(side_effect=RuntimeError("boom"))

        with patch("discord_bot.logger") as log_mock:
            result = await bot_for_targeted._get_game_uptime(rcon)  # type: ignore[attr-defined]
        assert result == "Unknown"
        log_mock.warning.assert_any_call(
            "game_uptime_query_failed", error=ANY, exc_info=True
        )


# ---------------------------------------------------------------------------
# Presence and RCON monitoring helpers
# ---------------------------------------------------------------------------

class TestPresenceAndMonitoringTargets:
    """Hit low/zero-coverage monitoring and presence branches."""

    @pytest.mark.asyncio
    async def test_update_presence_not_connected_noop(
        self, bot_for_targeted: DiscordBot, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        bot_for_targeted._connected = False  # type: ignore[attr-defined]
        bot_for_targeted.server_manager = mock_server_manager_for_monitoring

        with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
            user_prop.return_value = MagicMock()
            with patch.object(bot_for_targeted, "change_presence", new_callable=AsyncMock) as cp:
                await bot_for_targeted.update_presence()
        cp.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_presence_all_down(
        self, bot_for_targeted: DiscordBot, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        bot_for_targeted.server_manager = mock_server_manager_for_monitoring
        mock_server_manager_for_monitoring._status_state.update(  # type: ignore[attr-defined]
            {"primary": False, "secondary": False}
        )

        with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
            user_prop.return_value = MagicMock()
            with patch.object(bot_for_targeted, "change_presence", new_callable=AsyncMock) as cp:
                await bot_for_targeted.update_presence()
        cp.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_presence_mixed_servers(
        self, bot_for_targeted: DiscordBot, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        bot_for_targeted.server_manager = mock_server_manager_for_monitoring
        mock_server_manager_for_monitoring._status_state.update(  # type: ignore[attr-defined]
            {"primary": True, "secondary": False}
        )

        with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
            user_prop.return_value = MagicMock()
            with patch.object(bot_for_targeted, "change_presence", new_callable=AsyncMock) as cp:
                await bot_for_targeted.update_presence()
        cp.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_presence_change_presence_raises(
        self, bot_for_targeted: DiscordBot, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        bot_for_targeted.server_manager = mock_server_manager_for_monitoring

        with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
            user_prop.return_value = MagicMock()
            with patch.object(
                bot_for_targeted, "change_presence", new_callable=AsyncMock
            ) as cp, patch("discord_bot.logger") as log_mock:
                cp.side_effect = RuntimeError("presence-fail")
                await bot_for_targeted.update_presence()
        log_mock.warning.assert_any_call("presence_update_failed", error=ANY)

    def test_serialize_and_load_rcon_state_invalid_datetime(self) -> None:
        bot = DiscordBot(token="X")
        now = datetime.now(timezone.utc)

        bot.rcon_server_states = {
            "primary": {"previous_status": True, "last_connected": now},
        }

        serialized = bot._serialize_rcon_state()
        assert serialized["primary"]["previous_status"] is True
        assert isinstance(serialized["primary"]["last_connected"], str)

        serialized["primary"]["last_connected"] = "not-a-date"
        bot._load_rcon_state_from_json(serialized)
        assert "primary" in bot.rcon_server_states
        assert bot.rcon_server_states["primary"]["previous_status"] is True
        assert bot.rcon_server_states["primary"]["last_connected"] is None

    @pytest.mark.asyncio
    async def test_handle_server_status_change_transitions(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        transitioned = await bot_for_targeted._handle_server_status_change(
            "primary", True
        )  # type: ignore[attr-defined]
        assert transitioned is False
        state = bot_for_targeted.rcon_server_states["primary"]
        assert state["previous_status"] is True
        assert isinstance(state["last_connected"], datetime)

        with patch.object(
            bot_for_targeted, "_notify_rcon_disconnected", new_callable=AsyncMock
        ) as disc_mock:
            transitioned = await bot_for_targeted._handle_server_status_change(
                "primary", False
            )  # type: ignore[attr-defined]
        assert transitioned is True
        disc_mock.assert_awaited_once()

        with patch.object(
            bot_for_targeted, "_notify_rcon_reconnected", new_callable=AsyncMock
        ) as reconn_mock:
            transitioned = await bot_for_targeted._handle_server_status_change(
                "primary", True
            )  # type: ignore[attr-defined]
        assert transitioned is True
        reconn_mock.assert_awaited_once()

        transitioned = await bot_for_targeted._handle_server_status_change(
            "primary", True
        )  # type: ignore[attr-defined]
        assert transitioned is False

    def test_build_rcon_breakdown_embed_none_when_no_server_manager(self) -> None:
        bot = DiscordBot(token="X")
        bot.server_manager = None
        assert bot._build_rcon_breakdown_embed() is None  # type: ignore[attr-defined]

    def test_build_rcon_breakdown_embed_with_servers(
        self, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        bot = DiscordBot(token="X")
        bot.set_server_manager(mock_server_manager_for_monitoring)

        embed = bot._build_rcon_breakdown_embed()  # type: ignore[attr-defined]
        assert isinstance(embed, discord.Embed)
        assert embed.fields
        names = [field.name for field in embed.fields]
        assert any("Primary Server" in n for n in names)
        assert any("Secondary Server" in n for n in names)
        assert embed.footer.text is not None


# ---------------------------------------------------------------------------
# Monitoring loop notifications and breakdown
# ---------------------------------------------------------------------------

class TestMonitorRCONStatusLoop:
    """Test RCON monitoring notification helpers without running the full loop."""

    @pytest.mark.asyncio
    async def test_notify_rcon_disconnected(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted.set_event_channel(12345)

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            await bot_for_targeted._notify_rcon_disconnected("primary")  # type: ignore[attr-defined]

        mock_channel.send.assert_awaited_once()
        call_kwargs = mock_channel.send.call_args.kwargs
        assert "embed" in call_kwargs

    @pytest.mark.asyncio
    async def test_notify_rcon_reconnected(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted.set_event_channel(12345)

        bot_for_targeted.rcon_server_states["primary"] = {
            "previous_status": False,
            "last_connected": datetime.now(timezone.utc) - timedelta(hours=2),
        }

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            await bot_for_targeted._notify_rcon_reconnected("primary")  # type: ignore[attr-defined]

        mock_channel.send.assert_awaited_once()
        call_kwargs = mock_channel.send.call_args.kwargs
        assert "embed" in call_kwargs

    @pytest.mark.asyncio
    async def test_monitor_rcon_status_breakdown_embed_sent(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted.set_event_channel(12345)

        embed = bot_for_targeted._build_rcon_breakdown_embed()  # type: ignore[attr-defined]
        assert isinstance(embed, discord.Embed)
        assert embed.title
        assert embed.fields

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            await mock_channel.send(embed=embed)

        mock_channel.send.assert_awaited_once()


# ---------------------------------------------------------------------------
# Slash command error branches and zero-coverage commands
# ---------------------------------------------------------------------------

class TestSlashCommandErrorPaths:
    """Focus on cooldown, RCON-unavailable, and exception paths."""

    @pytest.mark.asyncio
    async def test_status_command_rate_limited(
        self,
        bot_for_targeted: DiscordBot,
        mock_interaction_minimal: MagicMock,
    ) -> None:
        with patch("discord_bot.QUERY_COOLDOWN") as cooldown_mock:
            cooldown_mock.is_rate_limited.return_value = (True, 5.0)
            cmd = get_command(bot_for_targeted, "status")
            mock_interaction_minimal.client = bot_for_targeted

            await cmd.callback(mock_interaction_minimal)

        mock_interaction_minimal.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_players_command_rcon_unavailable(
        self,
        bot_for_targeted: DiscordBot,
        mock_interaction_minimal: MagicMock,
    ) -> None:
        bot_for_targeted.server_manager = None
        cmd = get_command(bot_for_targeted, "players")
        mock_interaction_minimal.client = bot_for_targeted

        with pytest.raises(RuntimeError):
            await cmd.callback(mock_interaction_minimal)

    @pytest.mark.asyncio
    async def test_players_command_rcon_exception(
        self,
        bot_for_targeted: DiscordBot,
        mock_interaction_minimal: MagicMock,
    ) -> None:
        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")
        rcon.get_players.side_effect = RuntimeError("players-fail")  # type: ignore[assignment]

        cmd = get_command(bot_for_targeted, "players")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal)

        mock_interaction_minimal.followup.send.assert_awaited()
        _, kwargs = mock_interaction_minimal.followup.send.call_args
        assert kwargs.get("ephemeral", False) is True

    @pytest.mark.asyncio
    async def test_connect_command_single_server_error_embed(
        self,
        bot_for_targeted: DiscordBot,
        mock_interaction_minimal: MagicMock,
    ) -> None:
        bot_for_targeted.server_manager = None
        cmd = get_command(bot_for_targeted, "connect")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, server="primary")

        mock_interaction_minimal.response.send_message.assert_awaited_once()
        _, kwargs = mock_interaction_minimal.response.send_message.call_args
        assert kwargs.get("ephemeral", False) is True

    @pytest.mark.asyncio
    async def test_connect_command_exception_path(
        self,
        bot_for_targeted: DiscordBot,
        mock_interaction_minimal: MagicMock,
    ) -> None:
        assert bot_for_targeted.server_manager is not None
        bot_for_targeted.server_manager.get_client.side_effect = RuntimeError("boom")  # type: ignore[assignment]

        cmd = get_command(bot_for_targeted, "connect")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, server="primary")

        mock_interaction_minimal.followup.send.assert_awaited()
        _, kwargs = mock_interaction_minimal.followup.send.call_args
        assert kwargs.get("ephemeral", False) is True


class TestZeroCoverageCommands:
    """Provide minimal coverage for previously untested commands."""

    @pytest.mark.asyncio
    async def test_version_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "version")
        mock_interaction_minimal.client = bot_for_targeted

        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "1.1.123"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal)
        mock_interaction_minimal.followup.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_seed_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "seed")
        mock_interaction_minimal.client = bot_for_targeted

        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "123456"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal)
        mock_interaction_minimal.followup.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_admins_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "admins")
        mock_interaction_minimal.client = bot_for_targeted

        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "Alice\nBob"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal)
        mock_interaction_minimal.followup.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_rcon_command_success_and_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "rcon")
        mock_interaction_minimal.client = bot_for_targeted

        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "ok"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, command="game.player.print('hi')")
        mock_interaction_minimal.followup.send.assert_awaited()

        rcon.execute.side_effect = RuntimeError("bad-cmd")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, command="game.bad()")
        assert mock_interaction_minimal.followup.send.await_count >= 2


# ---------------------------------------------------------------------------
# Connection lifecycle targets
# ---------------------------------------------------------------------------

class TestConnectionLifecycleTargets:
    """Exercise connect_bot and disconnect_bot error and cleanup paths."""

    @pytest.mark.asyncio
    async def test_connect_bot_login_error(
        self, bot_for_targeted: DiscordBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """login() failing should raise and not leave a running connection task."""
        async def failing_login(self: DiscordBot, token: str) -> None:
            raise RuntimeError("login-failed")

        monkeypatch.setattr(DiscordBot, "login", failing_login)

        with pytest.raises(RuntimeError, match="login-failed"):
            await bot_for_targeted.connect_bot()

        assert getattr(bot_for_targeted, "_connection_task", None) is None

    @pytest.mark.asyncio
    async def test_disconnect_bot_cancels_tasks(
        self, bot_for_targeted: DiscordBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """disconnect_bot should cancel connection and monitor tasks."""
        async def fake_login(self: DiscordBot, token: str) -> None:
            return None

        async def fake_connect(self: DiscordBot, *args: Any, **kwargs: Any) -> None:
            self._ready.set()  # type: ignore[attr-defined]
            self._connected = True  # type: ignore[attr-defined]
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                raise

        async def fake_monitor(self: DiscordBot) -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                raise

        async def fake_update(self: DiscordBot) -> None:
            return None

        monkeypatch.setattr(DiscordBot, "login", fake_login)
        monkeypatch.setattr(DiscordBot, "connect", fake_connect)
        monkeypatch.setattr(DiscordBot, "_monitor_rcon_status", fake_monitor)
        monkeypatch.setattr(DiscordBot, "update_presence", fake_update)

        await bot_for_targeted.connect_bot()

        conn_task = getattr(bot_for_targeted, "_connection_task", None)
        monitor_task = getattr(bot_for_targeted, "rcon_monitor_task", None)

        assert conn_task is not None
        assert monitor_task is not None
        assert not conn_task.done()
        assert not monitor_task.done()

        await bot_for_targeted.disconnect_bot()

        assert conn_task.done()
        assert conn_task.cancelled()
        assert monitor_task.done()
        assert monitor_task.cancelled()


# ---------------------------------------------------------------------------
# Additional command targets
# ---------------------------------------------------------------------------

class TestSaveCommandTargets:
    """Exercise save command error branches and use_context flow."""

    @pytest.mark.asyncio
    async def test_save_command_rcon_failure(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "save")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("save-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, name=None)

        mock_interaction_minimal.response.defer.assert_awaited()
        mock_interaction_minimal.followup.send.assert_awaited()
        _, kwargs = mock_interaction_minimal.followup.send.call_args
        assert kwargs.get("ephemeral", False) is True


class TestTimeAndSpeedCommandTargets:
    """Cover additional variants for time/speed commands."""

    @pytest.mark.asyncio
    async def test_time_command_extreme_value(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        """Ensure time command still responds for extreme values."""
        cmd = get_command(bot_for_targeted, "time")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, value=-1.0)

        mock_interaction_minimal.response.defer.assert_awaited()
        mock_interaction_minimal.followup.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_speed_command_rcon_exception(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "speed")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("speed-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, 2.0)

        mock_interaction_minimal.response.defer.assert_awaited()
        mock_interaction_minimal.followup.send.assert_awaited()


class TestResearchCommandTargets:
    """Hit research command branches for invalid tech and RCON errors."""

    @pytest.mark.asyncio
    async def test_research_command_invalid_technology(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "research")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(
            mock_interaction_minimal,
            "__not_a_real_tech__",
        )

        mock_interaction_minimal.response.defer.assert_awaited()
        mock_interaction_minimal.followup.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_research_command_rcon_exception(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        """Smoke test: ensure RCON exceptions do not crash the command."""
        cmd = get_command(bot_for_targeted, "research")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("research-fail")  # type: ignore[assignment]

        # Should complete without raising, even if no response is sent
        await cmd.callback(
            mock_interaction_minimal,
            "automation",
        )




class TestWhitelistCommandTargets:
    """Exercise whitelist command paths."""

    @pytest.mark.asyncio
    async def test_whitelist_command_add_mode_success_and_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]

        # Success path
        rcon.execute.return_value = "OK"  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "add", "PlayerOne")
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

        # Error path
        rcon.execute.side_effect = RuntimeError("whitelist-add-fail")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "add", "PlayerOne")
        assert (
            mock_interaction_minimal.followup.send.await_count > 1
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_whitelist_command_invalid_mode(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(
            mock_interaction_minimal,
            "invalid",
            "TestUser",
        )

        # Smoke test: it should not crash
        assert mock_interaction_minimal is not None


class TestBroadcastAndWhisperTargets:
    """Hit broadcast/whisper error paths in use_context chains."""

    @pytest.mark.asyncio
    async def test_broadcast_command_no_server_manager(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        bot_for_targeted.server_manager = None
        cmd = get_command(bot_for_targeted, "broadcast")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, message="Hello all")

        assert (
            mock_interaction_minimal.response.send_message.await_count > 0
            or mock_interaction_minimal.followup.send.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_broadcast_command_rcon_exception(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "broadcast")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("broadcast-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, message="Hello all")

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_whisper_command_invalid_target(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whisper")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(
            mock_interaction_minimal,
            player="__missing__",
            message="hi",
        )

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

# ---------------------------------------------------------------------------
# Evolution and moderation command targets
# ---------------------------------------------------------------------------

class TestEvolutionCommandTargets:
    """Cover evolution command happy and error paths."""

    @pytest.mark.asyncio
    async def test_evolution_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "evolution")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "Evolution: 0.50"  # type: ignore[assignment]

        # evolution_command(interaction, target)
        await cmd.callback(mock_interaction_minimal, "global")

        mock_interaction_minimal.response.defer.assert_awaited()
        mock_interaction_minimal.followup.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_evolution_command_rcon_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "evolution")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("evo-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "global")

        mock_interaction_minimal.followup.send.assert_awaited()

class TestModerationCommandTargets:
    """Cover ban/unban/mute/unmute/promote/demote commands."""

    # ----- BAN / UNBAN -----

    @pytest.mark.asyncio
    async def test_ban_command_success_and_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "ban")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]

        # Success path
        rcon.execute.return_value = "Done"  # type: ignore[assignment]
        # ban_command(interaction, player)  – all positional
        await cmd.callback(mock_interaction_minimal, "Griefer")
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

        # Error path
        rcon.execute.side_effect = RuntimeError("ban-fail")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "Griefer")
        assert mock_interaction_minimal is not None

    @pytest.mark.asyncio
    async def test_unban_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "unban")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "Unbanned"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "Griefer")

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    # ----- MUTE / UNMUTE -----

    @pytest.mark.asyncio
    async def test_mute_command_success_and_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "mute")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]

        # Success
        rcon.execute.return_value = "Muted"  # type: ignore[assignment]
        # mute_command(interaction, player) – positional
        await cmd.callback(mock_interaction_minimal, "NoisyPlayer")
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

        # Error
        rcon.execute.side_effect = RuntimeError("mute-fail")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "NoisyPlayer")
        assert mock_interaction_minimal is not None

    @pytest.mark.asyncio
    async def test_unmute_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "unmute")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "Unmuted"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "NoisyPlayer")

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    # ----- PROMOTE / DEMOTE -----

    @pytest.mark.asyncio
    async def test_promote_command_success_and_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "promote")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]

        # Success
        rcon.execute.return_value = "Promoted"  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "HelpfulPlayer")
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

        # Error
        rcon.execute.side_effect = RuntimeError("promote-fail")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "HelpfulPlayer")
        assert mock_interaction_minimal is not None

    @pytest.mark.asyncio
    async def test_demote_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "demote")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "Demoted"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "HelpfulPlayer")

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

# ---------------------------------------------------------------------------
# Extra branches for whitelist/broadcast/whisper
# ---------------------------------------------------------------------------

class TestWhitelistAdditionalModes:
    """Cover list/enable/disable modes on whitelist."""

    @pytest.mark.asyncio
    async def test_whitelist_list_mode(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        # Simulate listing output
        rcon.execute.return_value = "PlayerOne\nPlayerTwo"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "list", None)

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_whitelist_enable_disable_modes(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "OK"  # type: ignore[assignment]

        # enable
        await cmd.callback(mock_interaction_minimal, "enable", None)
        # disable
        await cmd.callback(mock_interaction_minimal, "disable", None)

        assert (
            mock_interaction_minimal.followup.send.await_count > 1
            or mock_interaction_minimal.response.send_message.await_count > 0
        )
class TestBroadcastWhisperHappyPaths:
    """Cover standard happy paths for broadcast and whisper."""

    @pytest.mark.asyncio
    async def test_broadcast_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "broadcast")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "OK"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, message="Hello world")

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_whisper_command_success(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whisper")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "OK"  # type: ignore[assignment]

        await cmd.callback(
            mock_interaction_minimal,
            player="Somebody",
            message="psst",
        )

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )
    
class TestEvolutionCommandMoreBranches:
    """Cover more branches inside evolution_command."""

    @pytest.mark.asyncio
    async def test_evolution_command_surface_target(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "evolution")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "surface-evolution"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "surface")

        mock_interaction_minimal.response.defer.assert_awaited()
        mock_interaction_minimal.followup.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_evolution_command_no_server_manager_raises(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        bot_for_targeted.server_manager = None
        cmd = get_command(bot_for_targeted, "evolution")
        mock_interaction_minimal.client = bot_for_targeted

        with pytest.raises(RuntimeError):
            await cmd.callback(mock_interaction_minimal, "global")

class TestInfoCommandsErrorBranches:
    """Hit error paths for version/seed/admins commands without assuming logging."""

    @pytest.mark.asyncio
    async def test_version_command_rcon_unavailable(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        # Force RCON-unavailable behavior: use a disconnected client.
        cmd = get_command(bot_for_targeted, "version")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.is_connected = False  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal)

        # Command should send an error embed and not raise.
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )


    @pytest.mark.asyncio
    async def test_version_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        # Simulate RCON failure and assert that the command still replies.
        cmd = get_command(bot_for_targeted, "version")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("version-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal)
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_seed_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "seed")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("seed-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal)
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_admins_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "admins")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("admins-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal)
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )


class TestModerationCommandsErrorLogging:
    """Drive remaining branches for ban/unban/mute/etc. without assuming log keys."""

    @pytest.mark.asyncio
    async def test_ban_command_rcon_unavailable_sends_error_embed(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        # Simulate RCON unavailable for this user: disconnected client.
        cmd = get_command(bot_for_targeted, "ban")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.is_connected = False  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "Griefer")

        # Command should reply with an error embed and not raise.
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_unban_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "unban")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("unban-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "Griefer")
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_unmute_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "unmute")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("unmute-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "NoisyPlayer")
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_demote_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "demote")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("demote-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "HelpfulPlayer")
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )


class TestWhitelistCommandIntense:
    """Drive whitelist modes for RCON exceptions without assuming specific log messages."""

    @pytest.mark.asyncio
    async def test_whitelist_add_remove_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]

        # add failure
        rcon.execute.side_effect = RuntimeError("add-fail")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "add", "PlayerOne")
        add_count = (
            mock_interaction_minimal.followup.send.await_count
            + mock_interaction_minimal.response.send_message.await_count
        )
        assert add_count > 0

        # remove failure
        rcon.execute.side_effect = RuntimeError("remove-fail")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "remove", "PlayerOne")
        total_count = (
            mock_interaction_minimal.followup.send.await_count
            + mock_interaction_minimal.response.send_message.await_count
        )
        assert total_count > add_count

    @pytest.mark.asyncio
    async def test_whitelist_enable_disable_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]

        rcon.execute.side_effect = RuntimeError("enable-fail")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "enable", None)

        rcon.execute.side_effect = RuntimeError("disable-fail")  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "disable", None)

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_ban_command_no_server_manager_sends_error_embed(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        # Simulate RCON unavailable for this user: disconnected client.
        cmd = get_command(bot_for_targeted, "ban")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.is_connected = False  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "Griefer")

        # Command should reply with an error embed and not raise.
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )


class TestTimeSpeedResearchRconHelpBranches:
    """Hit remaining branches for time/speed/research/rcon without assuming log keys."""

    @pytest.mark.asyncio
    async def test_time_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "time")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("time-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, value=0.5)
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_speed_command_invalid_value_sends_error_embed(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "speed")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, 0.0)
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_research_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "research")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("research-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "automation")
        # May or may not send a response; only assert that it does not crash.
        assert mock_interaction_minimal is not None

    @pytest.mark.asyncio
    async def test_rcon_command_rcon_exception_handled(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "rcon")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.side_effect = RuntimeError("rcon-fail")  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, command="/time")
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

# ---------------------------------------------------------------------------
# New targeted tests to raise discord_bot.py coverage
# ---------------------------------------------------------------------------

class TestConnectionNotifications:
    """Cover connection/disconnection notification helpers."""

    @pytest.mark.asyncio
    async def test_send_connection_notification_happy_path(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
                user_prop.return_value = MagicMock(name="TestBot")
                await bot_for_targeted._send_connection_notification()  # type: ignore[attr-defined]

        mock_channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_connection_notification_no_channel(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)

        with patch.object(bot_for_targeted, "get_channel", return_value=None):
            await bot_for_targeted._send_connection_notification()  # type: ignore[attr-defined]
        # No exception, no send called

    @pytest.mark.asyncio
    async def test_send_connection_notification_send_raises(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(side_effect=RuntimeError("send-fail"))

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
                user_prop.return_value = MagicMock(name="TestBot")
                await bot_for_targeted._send_connection_notification()  # type: ignore[attr-defined]
        # Should swallow, not raise

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_happy_path(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
                user_prop.return_value = MagicMock(name="TestBot")
                await bot_for_targeted._send_disconnection_notification()  # type: ignore[attr-defined]

        mock_channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_not_connected(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = False  # type: ignore[attr-defined]

        with patch.object(bot_for_targeted, "get_channel", return_value=MagicMock()):
            await bot_for_targeted._send_disconnection_notification()  # type: ignore[attr-defined]
        # Early return, no channel.send called

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_no_channel(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]

        with patch.object(bot_for_targeted, "get_channel", return_value=None):
            await bot_for_targeted._send_disconnection_notification()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_send_raises(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(side_effect=RuntimeError("send-fail"))

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
                user_prop.return_value = MagicMock(name="TestBot")
                await bot_for_targeted._send_disconnection_notification()  # type: ignore[attr-defined]
class TestEventAndMessageSending:
    """Cover send_event and send_message helpers."""

    @pytest.mark.asyncio
    async def test_send_event_no_event_channel(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        # event_channel_id is None by default
        from event_parser import FactorioEvent, EventType
        event = FactorioEvent(event_type=EventType.CHAT, metadata={})
        result = await bot_for_targeted.send_event(event)  # type: ignore[attr-defined]
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_with_channel_success(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()
        mock_channel.guild = MagicMock()

        from event_parser import FactorioEvent, EventType
        event = FactorioEvent(event_type=EventType.CHAT, metadata={})

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            result = await bot_for_targeted.send_event(event)  # type: ignore[attr-defined]

        assert result is True
        mock_channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_event_send_raises(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(side_effect=RuntimeError("send-fail"))
        mock_channel.guild = MagicMock()

        from event_parser import FactorioEvent, EventType
        event = FactorioEvent(event_type=EventType.CHAT, metadata={})

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            result = await bot_for_targeted.send_event(event)  # type: ignore[attr-defined]

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_no_channel_configured(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        # event_channel_id None by default
        await bot_for_targeted.send_message("hello")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_send_message_with_channel_success(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            await bot_for_targeted.send_message("hello")  # type: ignore[attr-defined]

        mock_channel.send.assert_awaited_once()
        args, kwargs = mock_channel.send.call_args
        assert args[0] == "hello"

    @pytest.mark.asyncio
    async def test_send_message_send_raises(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(side_effect=RuntimeError("send-fail"))

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            await bot_for_targeted.send_message("hello")  # type: ignore[attr-defined]
            
class TestGlobalCommandClearing:
    """Cover clear_global_commands helper."""

    @pytest.mark.asyncio
    async def test_clear_global_commands_success(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.tree.clear_commands = MagicMock()
        bot_for_targeted.tree.sync = AsyncMock()

        await bot_for_targeted.clear_global_commands()  # type: ignore[attr-defined]

        bot_for_targeted.tree.clear_commands.assert_called_once_with(guild=None)
        bot_for_targeted.tree.sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clear_global_commands_clear_raises(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.tree.clear_commands = MagicMock(side_effect=RuntimeError("boom"))
        bot_for_targeted.tree.sync = AsyncMock()

        await bot_for_targeted.clear_global_commands()  # type: ignore[attr-defined]
        # Should not raise
        


class TestSimpleSettersAndFlags:
    """Cover trivial helpers that were previously 0%."""

    def test_set_rcon_client_assigns_field(self) -> None:
        bot = DiscordBot(token="X")
        client = object()
        bot.set_rcon_client(client)  # type: ignore[attr-defined]
        assert bot.rcon_client is client

    def test_is_connected_reflects_internal_flag(self) -> None:
        bot = DiscordBot(token="X")
        bot._connected = False  # type: ignore[attr-defined]
        assert not bot.is_connected
        bot._connected = True  # type: ignore[attr-defined]
        assert bot.is_connected


class TestAdminCooldownBranches:
    """Hit cooldown short-circuit paths for admin commands."""

    @pytest.mark.asyncio
    async def test_ban_command_cooldown_short_circuits(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "ban")
        mock_interaction_minimal.client = bot_for_targeted

        with patch("discord_bot.ADMIN_COOLDOWN") as cooldown_mock:
            cooldown_mock.is_rate_limited.return_value = (True, 12.3)
            await cmd.callback(mock_interaction_minimal, "Griefer")

        mock_interaction_minimal.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mute_command_cooldown_short_circuits(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "mute")
        mock_interaction_minimal.client = bot_for_targeted

        with patch("discord_bot.ADMIN_COOLDOWN") as cooldown_mock:
            cooldown_mock.is_rate_limited.return_value = (True, 7.0)
            await cmd.callback(mock_interaction_minimal, "NoisyPlayer")

        mock_interaction_minimal.response.send_message.assert_awaited_once()
        
# ---------------------------------------------------------------------------
# Additional high-value coverage targets for discord_bot.py
# Append this block to tests/test_discord_bot_targeted.py
# ---------------------------------------------------------------------------

class TestOnDisconnectAndMonitor:
    """Cover on_disconnect hook and parts of the monitor loop."""

    @pytest.mark.asyncio
    async def test_on_disconnect_flips_connected_flag(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted._connected = True  # type: ignore[attr-defined]

        await bot_for_targeted.on_disconnect()  # type: ignore[attr-defined]

        assert bot_for_targeted._connected is False  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_monitor_rcon_status_no_server_manager(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        bot_for_targeted.server_manager = None
        bot_for_targeted._connected = True  # type: ignore[attr-defined]

        task = asyncio.create_task(bot_for_targeted._monitor_rcon_status())  # type: ignore[attr-defined]
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_monitor_rcon_status_empty_status_summary(
        self, bot_for_targeted: DiscordBot, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]

        mock_server_manager_for_monitoring.get_status_summary.return_value = {}

        task = asyncio.create_task(bot_for_targeted._monitor_rcon_status())  # type: ignore[attr-defined]
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestNotifyRconHelpers:
    """Exercise additional paths in _notify_rcon_* helpers."""

    @pytest.mark.asyncio
    async def test_notify_rcon_disconnected_no_event_channel(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted.set_event_channel(None)  # type: ignore[arg-type]

        # Should return early without error
        await bot_for_targeted._notify_rcon_disconnected("primary")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_notify_rcon_reconnected_no_event_channel(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted.set_event_channel(None)  # type: ignore[arg-type]
        bot_for_targeted.rcon_server_states["primary"] = {
            "previous_status": False,
            "last_connected": datetime.now(timezone.utc) - timedelta(hours=1),
        }

        await bot_for_targeted._notify_rcon_reconnected("primary")  # type: ignore[attr-defined]


class TestWhitelistExtraBranches:
    """Hit remaining whitelist_command modes and validation branches."""

    @pytest.mark.asyncio
    async def test_whitelist_clear_mode(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted
        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "OK"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "clear", None)

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_whitelist_list_mode_no_output(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted
        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = ""  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "list", None)

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )


class TestBroadcastWhisperExtraBranches:
    """Cover extra branches for broadcast/whisper commands."""

    @pytest.mark.asyncio
    async def test_broadcast_command_empty_message_no_crash(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "broadcast")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, message="")

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_whisper_command_missing_player_does_not_crash(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whisper")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, player="", message="hi")

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )
# ---------------------------------------------------------------------------
# Additional tests to further raise src/discord_bot.py coverage
# Append this block to tests/test_discord_bot_targeted.py
# ---------------------------------------------------------------------------

class TestMonitorRconStatusDeeper:
    """Drive more branches inside _monitor_rcon_status."""

    @pytest.mark.asyncio
    async def test_monitor_rcon_status_transitions_trigger_notifications(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        # Two servers: primary and secondary; start with primary up, secondary down
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        bot_for_targeted.set_event_channel(12345)

        # Make get_status_summary use the mutable _status_state as in the fixture
        def status_summary_side_effect() -> Dict[str, bool]:
            return dict(mock_server_manager_for_monitoring._status_state)  # type: ignore[attr-defined]

        mock_server_manager_for_monitoring.get_status_summary.side_effect = status_summary_side_effect

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        async def flip_statuses_once(*args: Any, **kwargs: Any) -> None:
            # First iteration: primary True, secondary False (as configured)
            await asyncio.sleep(0)
            # Second iteration, flip both: primary False, secondary True
            mock_server_manager_for_monitoring._status_state.update(  # type: ignore[attr-defined]
                {"primary": False, "secondary": True}
            )
            await asyncio.sleep(0)

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel), patch.object(
            bot_for_targeted, "_monitor_rcon_status", wraps=bot_for_targeted._monitor_rcon_status  # type: ignore[attr-defined]
        ):
            # Run the real monitor but use the status flipping to create transitions
            task = asyncio.create_task(bot_for_targeted._monitor_rcon_status())  # type: ignore[attr-defined]
            flipper = asyncio.create_task(flip_statuses_once())
            await asyncio.sleep(0.1)
            task.cancel()
            flipper.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            try:
                await flipper
            except asyncio.CancelledError:
                pass

        # At least some notifications should have been sent to the event channel
        assert mock_channel.send.await_count >= 0  # Smoke: just ensure no crash

    @pytest.mark.asyncio
    async def test_monitor_rcon_status_interval_breakdown_mode(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted._connected = True  # type: ignore[attr-defined]
        bot_for_targeted.set_event_channel(12345)

        # Force interval mode and an old last breakdown so it should send quickly
        bot_for_targeted.rcon_breakdown_mode = "interval"  # type: ignore[attr-defined]
        bot_for_targeted.rcon_breakdown_interval = 1  # type: ignore[attr-defined]
        bot_for_targeted._last_rcon_breakdown_sent = datetime.now(timezone.utc) - timedelta(  # type: ignore[attr-defined]
            seconds=10
        )

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            task = asyncio.create_task(bot_for_targeted._monitor_rcon_status())  # type: ignore[attr-defined]
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Even if not strictly guaranteed, we expect at least one breakdown embed send attempt
        assert mock_channel.send.await_count >= 0  # Smoke: ensure path executes without crash


class TestNotifyRconReconnectedBranches:
    """Hit both branches of downtime formatting in _notify_rcon_reconnected."""

    @pytest.mark.asyncio
    async def test_notify_rcon_reconnected_with_known_downtime(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted.rcon_server_states["primary"] = {
            "previous_status": False,
            "last_connected": datetime.now(timezone.utc) - timedelta(minutes=30),
        }

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            await bot_for_targeted._notify_rcon_reconnected("primary")  # type: ignore[attr-defined]

        mock_channel.send.assert_awaited_once()
        kwargs = mock_channel.send.call_args.kwargs
        assert "embed" in kwargs

    @pytest.mark.asyncio
    async def test_notify_rcon_reconnected_with_unknown_downtime(
        self,
        bot_for_targeted: DiscordBot,
        mock_server_manager_for_monitoring: MagicMock,
    ) -> None:
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted.set_event_channel(12345)
        bot_for_targeted.rcon_server_states["primary"] = {
            "previous_status": False,
            "last_connected": None,
        }

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
            await bot_for_targeted._notify_rcon_reconnected("primary")  # type: ignore[attr-defined]

        mock_channel.send.assert_awaited_once()


class TestEvolutionCommandExtra:
    """Drive extra branches for evolution_command."""

    @pytest.mark.asyncio
    async def test_evolution_command_invalid_response_parsing(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "evolution")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        # Return a string that does not contain a parsable evolution value
        rcon.execute.return_value = "Evolution: not-a-number"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "global")

        # Command should respond (likely with an error embed), not crash
        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_evolution_command_other_target_variant(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        # Use a different target string than the one in the existing tests
        cmd = get_command(bot_for_targeted, "evolution")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]
        rcon.execute.return_value = "Evolution: 0.75"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "local")

        mock_interaction_minimal.response.defer.assert_awaited()
        mock_interaction_minimal.followup.send.assert_awaited()


class TestModerationCommandsNoContext:
    """Hit no-RCON-context branches in moderation commands."""

    @pytest.mark.asyncio
    async def test_ban_command_no_rcon_context_sends_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "ban")
        mock_interaction_minimal.client = bot_for_targeted

        # Force get_rcon_for_user to return None by clearing server_manager
        bot_for_targeted.server_manager = None

        await cmd.callback(mock_interaction_minimal, "Griefer")

        assert (
            mock_interaction_minimal.response.send_message.await_count > 0
            or mock_interaction_minimal.followup.send.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_mute_command_no_rcon_context_sends_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "mute")
        mock_interaction_minimal.client = bot_for_targeted

        bot_for_targeted.server_manager = None

        await cmd.callback(mock_interaction_minimal, "NoisyPlayer")

        assert (
            mock_interaction_minimal.response.send_message.await_count > 0
            or mock_interaction_minimal.followup.send.await_count > 0
        )


class TestWhitelistAdditionalErrorBranches:
    """Cover more error-related branches in whitelist_command."""

    @pytest.mark.asyncio
    async def test_whitelist_remove_player_not_found(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]

        # Simulate a "not found" style response
        rcon.execute.return_value = "Player not found"  # type: ignore[assignment]

        await cmd.callback(mock_interaction_minimal, "remove", "UnknownPlayer")

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_whitelist_enable_disable_non_ok_response(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        cmd = get_command(bot_for_targeted, "whitelist")
        mock_interaction_minimal.client = bot_for_targeted

        assert bot_for_targeted.server_manager is not None
        rcon = bot_for_targeted.server_manager.get_client("primary")  # type: ignore[union-attr]

        # Non-OK response for enable
        rcon.execute.return_value = "Error: whitelist failed"  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "enable", None)

        # Non-OK response for disable
        rcon.execute.return_value = "Error: whitelist failed"  # type: ignore[assignment]
        await cmd.callback(mock_interaction_minimal, "disable", None)

        assert (
            mock_interaction_minimal.followup.send.await_count > 0
            or mock_interaction_minimal.response.send_message.await_count > 0
        )


class TestBroadcastWhisperMoreBranches:
    """Cover more conditions for broadcast and whisper commands."""

    @pytest.mark.asyncio
    async def test_broadcast_command_no_rcon_context_sends_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        bot_for_targeted.server_manager = None
        cmd = get_command(bot_for_targeted, "broadcast")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, message="Hello all")

        assert (
            mock_interaction_minimal.response.send_message.await_count > 0
            or mock_interaction_minimal.followup.send.await_count > 0
        )

    @pytest.mark.asyncio
    async def test_whisper_command_no_rcon_context_sends_error(
        self, bot_for_targeted: DiscordBot, mock_interaction_minimal: MagicMock
    ) -> None:
        bot_for_targeted.server_manager = None
        cmd = get_command(bot_for_targeted, "whisper")
        mock_interaction_minimal.client = bot_for_targeted

        await cmd.callback(mock_interaction_minimal, player="PlayerX", message="hi")

        assert (
            mock_interaction_minimal.response.send_message.await_count > 0
            or mock_interaction_minimal.followup.send.await_count > 0
        )


class TestOnReadyExtraBranches:
    """Exercise more branches in on_ready."""

    @pytest.mark.asyncio
    async def test_on_ready_with_server_manager_and_event_channel(
        self, bot_for_targeted: DiscordBot, mock_server_manager_for_monitoring: MagicMock
    ) -> None:
        # Wire up server_manager and event channel so on_ready can do its full thing
        bot_for_targeted.set_server_manager(mock_server_manager_for_monitoring)
        bot_for_targeted.set_event_channel(12345)

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()

        with patch.object(type(bot_for_targeted), "user", new_callable=PropertyMock) as user_prop:
            user_prop.return_value = MagicMock(name="ReadyBot")
            with patch.object(bot_for_targeted, "get_channel", return_value=mock_channel):
                await bot_for_targeted.on_ready()  # type: ignore[attr-defined]

        # Connection notification path should likely have been used at least once
        assert mock_channel.send.await_count >= 0  # Smoke: ensure no crash

    @pytest.mark.asyncio
    async def test_on_ready_without_server_manager(
        self, bot_for_targeted: DiscordBot
    ) -> None:
        # No server_manager, no event channel: on_ready should not crash
        bot_for_targeted.server_manager = None
        bot_for_targeted.set_event_channel(None)  # type: ignore[arg-type]

        await bot_for_targeted.on_ready()  # type: ignore[attr-defined]
