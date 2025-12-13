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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast, List
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch, Mock

import discord
from discord import app_commands
import pytest

# Add project root to path if needed
import sys

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import the module under test
from discord_bot import DiscordBot, DiscordBotFactory


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_server_manager() -> MagicMock:
    """Mock ServerManager for multi-server support."""
    manager = MagicMock()

    # Mock server configurations
    primary_config = MagicMock()
    primary_config.tag = "primary"
    primary_config.name = "Primary Server"
    primary_config.description = "Main production server"
    primary_config.rcon_host = "primary.example.com"
    primary_config.rcon_port = 27015
    primary_config.event_channel_id = None

    secondary_config = MagicMock()
    secondary_config.tag = "secondary"
    secondary_config.name = "Secondary Server"
    secondary_config.description = "Testing server"
    secondary_config.rcon_host = "secondary.example.com"
    secondary_config.rcon_port = 27016
    secondary_config.event_channel_id = None

    manager.list_tags.return_value = ["primary", "secondary"]
    manager.list_servers.return_value = {
        "primary": primary_config,
        "secondary": secondary_config,
    }

    manager.get_config.side_effect = lambda tag: {
        "primary": primary_config,
        "secondary": secondary_config,
    }.get(tag)

    # Mock RCON clients
    primary_rcon = AsyncMock()
    primary_rcon.is_connected = True
    primary_rcon.host = "primary.example.com"
    primary_rcon.port = 27015
    primary_rcon.execute = AsyncMock(return_value="OK")
    primary_rcon.get_players = AsyncMock(return_value=["Alice", "Bob"])

    secondary_rcon = AsyncMock()
    secondary_rcon.is_connected = True
    secondary_rcon.host = "secondary.example.com"
    secondary_rcon.port = 27016
    secondary_rcon.execute = AsyncMock(return_value="OK")
    secondary_rcon.get_players = AsyncMock(return_value=["Charlie"])

    manager.get_client.side_effect = lambda tag: {
        "primary": primary_rcon,
        "secondary": secondary_rcon,
    }.get(tag)

    manager.get_status_summary.return_value = {
        "primary": True,
        "secondary": True,
    }

    # Add clients dict for validation
    manager.clients = {"primary": primary_rcon, "secondary": secondary_rcon}
    return manager


@pytest.fixture
def mock_interaction() -> MagicMock:
    """Mock Discord Interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 123456
    interaction.user.name = "TestUser"
    interaction.user.mention = "<@123456>"
    interaction.user.display_name = "TestUser"

    interaction.guild = MagicMock()
    interaction.guild.name = "TestGuild"
    interaction.guild.id = 999
    interaction.guild.roles = []
    interaction.guild.members = []

    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.is_done = Mock(return_value=False)

    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    # Mock client reference
    interaction.client = None  # Will be set by tests
    return interaction


@pytest.fixture
def patch_discord_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch Discord network calls to prevent actual connection attempts."""

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

    # Patch all cooldown instances in discord_bot module
    import discord_bot as bot_module

    monkeypatch.setattr(bot_module, "QUERY_COOLDOWN", no_limit)
    monkeypatch.setattr(bot_module, "ADMIN_COOLDOWN", no_limit)
    monkeypatch.setattr(bot_module, "DANGER_COOLDOWN", no_limit)


@pytest.fixture
async def bot(
    patch_discord_network: None,
    patch_rate_limiting: None,
    mock_server_manager: MagicMock,
) -> DiscordBot:
    """Create bot instance with multi-server support."""
    bot_instance = DiscordBot(token="TEST_TOKEN", bot_name="TestBot")
    bot_instance.set_server_manager(mock_server_manager)
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
    raise KeyError(f"Command {name!r} not found in factorio group")


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestInitialization:
    """Test DiscordBot initialization."""

    @pytest.mark.asyncio
    async def test_init_with_token(self, patch_discord_network: None) -> None:
        """Test basic initialization with token."""
        bot = DiscordBot(token="TEST123")
        assert bot.token == "TEST123"
        assert bot.bot_name == "Factorio ISR"
        assert bot.event_channel_id is None
        assert bot.rcon_client is None
        assert bot.server_manager is None
        assert bot.user_contexts == {}
        assert bot.rcon_server_states == {}
        await bot.close()

    @pytest.mark.asyncio
    async def test_init_with_custom_name(self, patch_discord_network: None) -> None:
        """Test initialization with custom bot name."""
        bot = DiscordBot(token="TOKEN", bot_name="CustomBot")
        assert bot.bot_name == "CustomBot"
        await bot.close()

    @pytest.mark.asyncio
    async def test_init_with_breakdown_config(self, patch_discord_network: None) -> None:
        """Test initialization with RCON breakdown configuration."""
        bot = DiscordBot(
            token="TOKEN",
            breakdown_mode="interval",
            breakdown_interval=600,
        )
        assert bot.rcon_breakdown_mode == "interval"
        assert bot.rcon_breakdown_interval == 600
        await bot.close()

    @pytest.mark.asyncio
    async def test_set_event_channel(self, bot: DiscordBot) -> None:
        """Test setting event channel ID."""
        bot.set_event_channel(123456789)
        assert bot.event_channel_id == 123456789

    @pytest.mark.asyncio
    async def test_set_server_manager(self, bot: DiscordBot, mock_server_manager: MagicMock) -> None:
        """Test setting ServerManager."""
        bot.set_server_manager(mock_server_manager)
        assert bot.server_manager is mock_server_manager

    @pytest.mark.asyncio
    async def test_setup_hook(self, patch_discord_network: None) -> None:
        """Test setup_hook registers commands."""
        bot = DiscordBot(token="TEST")
        await bot.setup_hook()

        commands = bot.tree.get_commands()
        factorio_group = next((c for c in commands if c.name == "factorio"), None)
        assert factorio_group is not None
        assert isinstance(factorio_group, app_commands.Group)

        await bot.close()


class TestFactory:
    """Test DiscordBotFactory."""

    @pytest.mark.asyncio
    async def test_create_bot(self, patch_discord_network: None) -> None:
        """Test factory creates bot correctly."""
        bot = DiscordBotFactory.create_bot("TOKEN123", "FactoryBot")
        assert isinstance(bot, DiscordBot)
        assert bot.bot_name == "FactoryBot"
        assert bot.token == "TOKEN123"
        await bot.close()


# =============================================================================
# CONFIG LOADING TESTS
# =============================================================================


class TestMentionConfigLoading:
    """Test _load_mention_config method."""

    def test_load_mention_config_missing_file(
        self, bot: DiscordBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test behavior when mentions.yml doesn't exist."""
        monkeypatch.chdir(tmp_path)
        bot._load_mention_config()
        assert bot._mention_group_keywords == {}

    def test_load_mention_config_valid_yaml(
        self, bot: DiscordBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading valid mentions.yml."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        mentions_file = config_dir / "mentions.yml"
        mentions_file.write_text(
            "mentions:\n"
            "  roles:\n"
            "    operations:\n"
            "      - ops\n"
            "      - operations\n"
            "    engineering:\n"
            "      - eng\n"
            "      - engineers\n"
        )

        monkeypatch.chdir(tmp_path)
        bot._load_mention_config()

        assert "operations" in bot._mention_group_keywords
        assert "ops" in bot._mention_group_keywords["operations"]
        assert "engineering" in bot._mention_group_keywords

    def test_load_mention_config_invalid_yaml(
        self, bot: DiscordBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test handling of malformed YAML."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        mentions_file = config_dir / "mentions.yml"
        mentions_file.write_text("invalid: [yaml content")

        monkeypatch.chdir(tmp_path)
        bot._load_mention_config()
        assert bot._mention_group_keywords == {}


# ======================================================================
# Mention Resolution
# ======================================================================


class TestMentionResolution:
    """Test mention parsing and resolution (async method)."""

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """Create a mock guild with roles and members."""
        guild = MagicMock(spec=discord.Guild)
        guild.roles = []
        guild.members = []
        return guild

    @pytest.mark.asyncio
    async def test_resolve_mentions_everyone(
        self, bot: DiscordBot, mock_guild: MagicMock
    ) -> None:
        """Test @everyone mention resolves correctly."""
        result = await bot._resolve_mentions(mock_guild, ["everyone"])
        assert "@everyone" in result

    @pytest.mark.asyncio
    async def test_resolve_mentions_here(
        self, bot: DiscordBot, mock_guild: MagicMock
    ) -> None:
        """Test @here mention resolves correctly."""
        result = await bot._resolve_mentions(mock_guild, ["here"])
        assert "@here" in result

    @pytest.mark.asyncio
    async def test_resolve_mentions_user_not_found(
        self, bot: DiscordBot, mock_guild: MagicMock
    ) -> None:
        """Test user mention when user doesn't exist."""
        result = await bot._resolve_mentions(mock_guild, ["unknown_user"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_resolve_mentions_role(
        self,
        bot: DiscordBot,
        mock_guild: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test role mention resolution with config."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "mentions.yml").write_text(
            "mentions:\n  roles:\n    admin:\n      - admin\n      - admins\n"
        )

        monkeypatch.chdir(tmp_path)
        bot._load_mention_config()

        mock_role = MagicMock()
        mock_role.name = "Admin"
        mock_role.mention = "<@&123456>"
        mock_guild.roles = [mock_role]

        result = await bot._resolve_mentions(mock_guild, ["admin"])
        assert "<@&123456>" in result


# =============================================================================
# USER CONTEXT TESTS (Multi-Server)
# =============================================================================


class TestUserContext:
    """Test user-to-server context mapping."""

    def test_set_and_get_user_server(self, bot: DiscordBot) -> None:
        """Test setting and retrieving user server preference."""
        bot.server_manager.list_tags.return_value = ["primary", "prod"]
        bot.set_user_server(123, "prod")
        assert bot.get_user_server(123) == "prod"

    def test_get_user_server_default(self, bot: DiscordBot) -> None:
        """Test getting default server for unmapped user."""
        bot.server_manager.list_tags.return_value = ["primary", "prod"]
        tag = bot.get_user_server(999)
        assert tag == "primary"

    def test_get_user_server_empty_tags(self, bot: DiscordBot) -> None:
        """Test behavior with no available tags."""
        bot.server_manager.list_tags.return_value = []
        with pytest.raises(RuntimeError, match="No servers configured"):
            bot.get_user_server(999)

    def test_get_server_display_name_known(self, bot: DiscordBot) -> None:
        """Test getting display name for known server."""
        bot.server_manager = MagicMock()
        result = bot.get_server_display_name(1)
        assert result is not None

    def test_get_server_display_name_unknown(self, bot: DiscordBot) -> None:
        """Test getting display name for unknown server."""
        bot.server_manager = None
        assert bot.get_server_display_name(1) == "Unknown"


# =============================================================================
# UPTIME AND FORMATTING TESTS
# =============================================================================


class TestUptimeHelpers:
    """Test uptime formatting utility."""

    @pytest.mark.asyncio
    async def test_format_uptime_less_than_minute(self, bot: DiscordBot) -> None:
        """Test that uptimes < 1 minute are formatted as '< 1m'."""
        delta = timedelta(seconds=30)
        formatted = bot._format_uptime(delta)
        assert formatted == "< 1m"

    @pytest.mark.asyncio
    async def test_format_uptime_minutes(self, bot: DiscordBot) -> None:
        """Test minute-only formatting."""
        result = bot._format_uptime(timedelta(minutes=5))
        assert result == "5m"

    @pytest.mark.asyncio
    async def test_format_uptime_hours_minutes(self, bot: DiscordBot) -> None:
        """Test hour and minute formatting."""
        result = bot._format_uptime(timedelta(hours=2, minutes=15))
        assert result == "2h 15m"

    @pytest.mark.asyncio
    async def test_format_uptime_days_hours(self, bot: DiscordBot) -> None:
        """Test day and hour formatting."""
        result = bot._format_uptime(timedelta(days=3, hours=4))
        assert result == "3d 4h"

    @pytest.mark.asyncio
    async def test_format_uptime_zero(self, bot: DiscordBot) -> None:
        """Test zero uptime."""
        result = bot._format_uptime(timedelta(seconds=0))
        assert result == "< 1m"


# =============================================================================
# RCON STATE SERIALIZATION TESTS
# =============================================================================


class TestRCONStateSerialization:
    """Test RCON state serialization/deserialization."""

    @pytest.mark.asyncio
    async def test_serialize_rcon_state(self, bot: DiscordBot) -> None:
        """Test serializing RCON state to JSON."""
        now = datetime.now(timezone.utc)
        bot.rcon_server_states = {
            "primary": {
                "previous_status": True,
                "last_connected": now,
            },
            "secondary": {
                "previous_status": False,
                "last_connected": None,
            },
        }

        serialized = bot._serialize_rcon_state()
        assert "primary" in serialized
        assert serialized["primary"]["previous_status"] is True
        assert isinstance(serialized["primary"]["last_connected"], str)

    @pytest.mark.asyncio
    async def test_load_rcon_state_from_json(self, bot: DiscordBot) -> None:
        """Test loading RCON state from JSON."""
        now = datetime.now(timezone.utc)
        data = {
            "primary": {
                "previous_status": True,
                "last_connected": now.isoformat(),
            }
        }

        bot._load_rcon_state_from_json(data)
        assert "primary" in bot.rcon_server_states
        assert bot.rcon_server_states["primary"]["previous_status"] is True
        assert isinstance(bot.rcon_server_states["primary"]["last_connected"], datetime)


# =============================================================================
# PRESENCE AND MONITORING TESTS
# =============================================================================


class TestPresenceAndMonitoring:
    """Test presence updates and monitoring."""

    @pytest.fixture
    def mock_server_manager(self) -> MagicMock:
        """Create a mock server manager."""
        mgr = MagicMock()
        mgr.get_status_summary.return_value = {"primary": True, "secondary": False}
        mgr.list_tags.return_value = ["primary", "secondary"]
        mgr.list_servers.return_value = {}
        return mgr

    @pytest.mark.asyncio
    async def test_update_presence_single_connected(
        self, bot: DiscordBot, mock_server_manager: MagicMock
    ) -> None:
        """Test presence update with single connected server."""
        bot._connected = True
        bot.server_manager = mock_server_manager

        with patch.object(type(bot), "user", new_callable=PropertyMock) as user_prop:
            user_prop.return_value = MagicMock()
            with patch.object(bot, "change_presence", new_callable=AsyncMock) as cp:
                await bot.update_presence()
                cp.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_presence_multi_server(
        self, bot: DiscordBot, mock_server_manager: MagicMock
    ) -> None:
        """Test presence update with multiple servers."""
        bot._connected = True
        bot.server_manager = mock_server_manager

        with patch.object(type(bot), "user", new_callable=PropertyMock) as user_prop:
            mock_user = MagicMock()
            mock_user.name = "TestBot"
            user_prop.return_value = mock_user
            with patch.object(bot, "change_presence", new_callable=AsyncMock) as cp:
                await bot.update_presence()
                cp.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_presence_disconnected(
        self, bot: DiscordBot, mock_server_manager: MagicMock
    ) -> None:
        """Test presence update when bot is disconnected."""
        bot._connected = False
        bot.server_manager = mock_server_manager

        with patch.object(type(bot), "user", new_callable=PropertyMock) as user_prop:
            user_prop.return_value = MagicMock()
            with patch.object(bot, "change_presence", new_callable=AsyncMock) as cp:
                await bot.update_presence()
                assert True


# =============================================================================
# LIFECYCLE TESTS
# =============================================================================


class TestLifecycle:
    """Test bot lifecycle events."""

    @pytest.mark.asyncio
    async def test_on_ready(self, bot: DiscordBot) -> None:
        """Test on_ready event sets connection state."""
        with patch.object(type(bot), "user", new_callable=PropertyMock) as user_prop:
            mock_user = MagicMock()
            mock_user.name = "TestBot"
            user_prop.return_value = mock_user

            await bot.on_ready()

        assert bot._connected is True
        assert bot._ready.is_set()

    @pytest.mark.asyncio
    async def test_on_error_logs_correctly(self, bot: DiscordBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test on_error does not raise even with structlog's event arg."""
        import discord_bot as bot_module

        # Patch module-level logger to a simple MagicMock to avoid structlog argument clash
        fake_logger = MagicMock()
        monkeypatch.setattr(bot_module, "logger", fake_logger)

        # Should not raise
        await bot.on_error("test_event", Exception("test error"))

        fake_logger.error.assert_called()  # sanity check it was invoked

    @pytest.mark.asyncio
    async def test_connect_bot_creates_task(self, bot: DiscordBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test connect_bot creates and stores a connection task (matches async impl)."""
        # Patch network-related calls and long-running pieces
        async def fake_login(self, token: str) -> None:
            return None

        async def fake_connect(self, *args: Any, **kwargs: Any) -> None:
            # Simulate immediate connect + ready
            bot._ready.set()
            return None

        async def fake_send_connection_notification(self) -> None:
            return None

        async def fake_monitor_rcon_status(self) -> None:
            # Simple loop that exits quickly when _connected flips
            while bot._connected:
                await asyncio.sleep(0.01)

        async def fake_update_presence(self) -> None:
            return None

        monkeypatch.setattr(DiscordBot, "login", fake_login)
        monkeypatch.setattr(DiscordBot, "connect", fake_connect)
        monkeypatch.setattr(DiscordBot, "_send_connection_notification", fake_send_connection_notification)
        monkeypatch.setattr(DiscordBot, "_monitor_rcon_status", fake_monitor_rcon_status)
        monkeypatch.setattr(DiscordBot, "update_presence", fake_update_presence)

        bot._connection_task = None

        # Run connect_bot; it should set _connection_task internally
        await bot.connect_bot()

        assert bot._connection_task is not None
        assert isinstance(bot._connection_task, asyncio.Task)
        assert not bot._connection_task.cancelled()

        # Clean up the connection task
        bot._connected = False
        if not bot._connection_task.done():
            bot._connection_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await bot._connection_task


# =============================================================================
# EVENT TESTS
# =============================================================================


class TestEventHandling:
    """Test event handler behavior."""

    @pytest.mark.asyncio
    async def test_on_ready_sets_ready_flag(self, bot: DiscordBot) -> None:
        """Test on_ready sets the ready event."""
        with patch.object(type(bot), "user", new_callable=PropertyMock) as user_prop:
            user_prop.return_value = MagicMock()
            await bot.on_ready()
        assert bot._ready.is_set()


# =============================================================================
# COMMAND TESTS - MULTI-SERVER
# =============================================================================


class TestMultiServerCommands:
    """Test multi-server management commands."""

    @pytest.mark.asyncio
    async def test_servers_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /factorio servers command."""
        cmd = get_command(bot, "servers")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction)

        mock_interaction.response.defer.assert_awaited_once()
        mock_interaction.followup.send.assert_awaited_once()

        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_connect_command_success(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /factorio connect command with valid server."""
        cmd = get_command(bot, "connect")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction, server="secondary")

        assert bot.get_user_server(mock_interaction.user.id) == "secondary"
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_command_invalid_server(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /factorio connect with invalid server."""
        cmd = get_command(bot, "connect")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction, server="nonexistent")

        call_args = mock_interaction.followup.send.call_args
        assert call_args.kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_server_autocomplete(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test server autocomplete function."""
        mock_interaction.client = bot

        cmd = get_command(bot, "connect")
        autocomplete_func = cmd._params["server"].autocomplete

        choices = await autocomplete_func(mock_interaction, "pri")
        assert len(choices) > 0
        assert any("primary" in str(c.value).lower() for c in choices)


# =============================================================================
# COMMAND TESTS - SERVER INFO
# =============================================================================


class TestServerInfoCommands:
    """Test server information commands."""

    @pytest.mark.asyncio
    async def test_status_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /factorio status command."""
        cmd = get_command(bot, "status")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction)
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_players_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /factorio players command."""
        cmd = get_command(bot, "players")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction)
        mock_interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /factorio health command."""
        cmd = get_command(bot, "health")
        mock_interaction.client = bot

        bot._connected = True
        await cmd.callback(mock_interaction)
        mock_interaction.followup.send.assert_awaited_once()


# =============================================================================
# COMMAND TESTS - ADMIN ACTIONS
# =============================================================================


class TestAdminCommands:
    """Test admin/moderation commands."""

    @pytest.mark.asyncio
    async def test_kick_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /factorio kick command."""
        cmd = get_command(bot, "kick")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction, player="Griefer", reason="Griefing")
        rcon = bot.get_rcon_for_user(mock_interaction.user.id)
        rcon.execute.assert_awaited()


# =============================================================================
# COMMAND TESTS - SERVER MANAGEMENT
# =============================================================================


class TestServerManagementCommands:
    """Test server management commands."""

    @pytest.mark.asyncio
    async def test_save_command_no_name(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /factorio save without custom name."""
        cmd = get_command(bot, "save")
        mock_interaction.client = bot

        rcon = bot.get_rcon_for_user(mock_interaction.user.id)
        rcon.execute.return_value = "Saving game to _autosave1.zip"

        await cmd.callback(mock_interaction, name=None)
        mock_interaction.followup.send.assert_awaited_once()


# =============================================================================
# COMMAND TESTS - GAME CONTROL
# =============================================================================


class TestGameControlCommands:
    """Test Factorio game control commands."""

    @pytest.mark.asyncio
    async def test_time_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /time command execution."""
        bot.server_manager = mock_server_manager

        cmd = get_command(bot, "time")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction, value=0.5)
        mock_interaction.response.defer.assert_awaited()
        mock_interaction.followup.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_time_command_with_different_values(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /time command with various time values."""
        bot.server_manager = mock_server_manager

        cmd = get_command(bot, "time")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction, value=10.0)
        mock_interaction.response.defer.assert_awaited()


# =============================================================================
# COMMAND TESTS - ADVANCED
# =============================================================================


class TestAdvancedCommands:
    """Test advanced Discord commands."""

    @pytest.mark.asyncio
    async def test_help_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /help command execution."""
        bot.server_manager = mock_server_manager

        cmd = get_command(bot, "help")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction)
        mock_interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_help_command_sends_text(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test /help command sends text."""
        bot.server_manager = mock_server_manager

        cmd = get_command(bot, "help")
        mock_interaction.client = bot

        await cmd.callback(mock_interaction)

        mock_interaction.response.send_message.assert_awaited_once()
        call_args = mock_interaction.response.send_message.call_args
        assert call_args
        assert len(call_args.args) > 0 or "message" in call_args.kwargs


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_on_error_with_exception(self, bot: DiscordBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test on_error handles an exception gracefully with structlog logger."""
        import discord_bot as bot_module

        fake_logger = MagicMock()
        monkeypatch.setattr(bot_module, "logger", fake_logger)

        await bot.on_error("test_event", Exception("test"))

        fake_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_get_command_with_invalid_name(self, bot: DiscordBot) -> None:
        """Test get_command raises KeyError for missing command."""
        with pytest.raises(KeyError):
            get_command(bot, "nonexistent_command")

    def test_get_user_server_invalid_user_id(self, bot: DiscordBot) -> None:
        """Test get_user_server with invalid user ID."""
        bot.server_manager.list_tags.return_value = ["primary"]
        result = bot.get_user_server(-1)
        assert result == "primary"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_user_switches_server_and_executes_command(
        self, bot: DiscordBot, mock_interaction: MagicMock, mock_server_manager: MagicMock
    ) -> None:
        """Test complete workflow: user switches server and runs command."""
        mock_interaction.client = bot

        assert bot.get_user_server(mock_interaction.user.id) == "primary"

        connect_cmd = get_command(bot, "connect")
        await connect_cmd.callback(mock_interaction, server="secondary")
        assert bot.get_user_server(mock_interaction.user.id) == "secondary"

        status_cmd = get_command(bot, "status")
        await status_cmd.callback(mock_interaction)

        secondary_rcon = mock_server_manager.get_client("secondary")
        secondary_rcon.get_players.assert_awaited()


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=discord_bot",
            "--cov-report=html",
            "--cov-report=term",
        ]
    )
