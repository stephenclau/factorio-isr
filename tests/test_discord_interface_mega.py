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

import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add project src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# ----------------------------------------------------------------------
# Global discord module mock (before importing discord_interface)
# ----------------------------------------------------------------------
discord_mock = MagicMock()
discord_mock.Embed = MagicMock(return_value=MagicMock())
discord_mock.utils = MagicMock()
discord_mock.utils.utcnow = MagicMock(return_value="2025-12-03T00:00:00")
# Provide a concrete TextChannel type for isinstance checks
discord_mock.TextChannel = type("TextChannel", (), {})
discord_mock.Status = MagicMock()
discord_mock.Status.online = "online"
discord_mock.Activity = MagicMock(return_value=MagicMock())
discord_mock.ActivityType = MagicMock()
discord_mock.ActivityType.watching = "watching"
discord_mock.errors = MagicMock()
discord_mock.errors.Forbidden = type("Forbidden", (Exception,), {})
discord_mock.errors.HTTPException = type("HTTPException", (Exception,), {})

sys.modules["discord"] = discord_mock

from discord_interface import (  # type: ignore
    WebhookDiscordInterface,
    BotDiscordInterface,
    DiscordInterfaceFactory,
    DiscordInterface,
)

# Ensure module-level flags use our mock
import discord_interface as di_mod  # type: ignore

di_mod.DISCORD_AVAILABLE = True
di_mod.discord = discord_mock


# ======================================================================
# Fixtures – shared
# ======================================================================

@pytest.fixture
def mock_discord_client() -> MagicMock:
    """Mock DiscordClient for webhook interface tests."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.send_event = AsyncMock(return_value=True)
    client.send_message = AsyncMock(return_value=True)
    client.test_connection = AsyncMock(return_value=True)
    return client


@pytest.fixture
def webhook_interface(mock_discord_client: MagicMock) -> WebhookDiscordInterface:
    """Create WebhookDiscordInterface instance."""
    return WebhookDiscordInterface(mock_discord_client)


@pytest.fixture
def mock_discord_bot() -> MagicMock:
    """Mock DiscordBot for BotDiscordInterface tests."""
    bot = MagicMock()
    bot.is_connected = True  # boolean property
    bot.event_channel_id = 123456789
    bot.connect_bot = AsyncMock()
    bot.disconnect_bot = AsyncMock()
    bot.send_event = AsyncMock(return_value=True)

    # Proper TextChannel-like channel for isinstance checks
    channel = MagicMock(spec=discord_mock.TextChannel)
    channel.send = AsyncMock()
    bot.get_channel = MagicMock(return_value=channel)
    return bot


@pytest.fixture
def bot_interface(mock_discord_bot: MagicMock) -> BotDiscordInterface:
    """Create BotDiscordInterface instance."""
    return BotDiscordInterface(mock_discord_bot)


# ======================================================================
# WebhookDiscordInterface tests
# ======================================================================

class TestWebhookDiscordInterfaceInit:
    """Initialization behavior for WebhookDiscordInterface."""

    def test_init_with_client(self, mock_discord_client: MagicMock) -> None:
        interface = WebhookDiscordInterface(mock_discord_client)
        assert interface.client is mock_discord_client
        assert interface._connected is False

    def test_init_sets_not_connected(self, mock_discord_client: MagicMock) -> None:
        interface = WebhookDiscordInterface(mock_discord_client)
        assert interface.is_connected is False

    def test_init_stores_client_reference(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        assert webhook_interface.client is mock_discord_client


class TestWebhookInterfaceConnection:
    """Connection and disconnection for webhook interface."""

    @pytest.mark.asyncio
    async def test_connect(self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock) -> None:
        await webhook_interface.connect()
        mock_discord_client.connect.assert_awaited_once()
        assert webhook_interface.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock) -> None:
        await webhook_interface.connect()
        assert webhook_interface.is_connected is True
        await webhook_interface.disconnect()
        mock_discord_client.disconnect.assert_awaited_once()
        assert webhook_interface.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_when_already_connected(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        await webhook_interface.connect()
        await webhook_interface.connect()
        assert mock_discord_client.connect.await_count == 2

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        assert webhook_interface.is_connected is False
        await webhook_interface.disconnect()
        mock_discord_client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_connected_property(self, webhook_interface: WebhookDiscordInterface) -> None:
        assert webhook_interface.is_connected is False
        await webhook_interface.connect()
        assert webhook_interface.is_connected is True
        await webhook_interface.disconnect()
        assert webhook_interface.is_connected is False


class TestWebhookInterfaceSendEvent:
    """send_event for webhook interface."""

    @pytest.mark.asyncio
    async def test_send_event_success(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        evt = MagicMock()
        mock_discord_client.send_event.return_value = True
        result = await webhook_interface.send_event(evt)
        assert result is True
        mock_discord_client.send_event.assert_awaited_once_with(evt)

    @pytest.mark.asyncio
    async def test_send_event_failure(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        evt = MagicMock()
        mock_discord_client.send_event.return_value = False
        result = await webhook_interface.send_event(evt)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_with_none(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        result = await webhook_interface.send_event(None)
        mock_discord_client.send_event.assert_awaited_once_with(None)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_event_exception(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        evt = MagicMock()
        mock_discord_client.send_event.side_effect = Exception("Send failed")
        with pytest.raises(Exception, match="Send failed"):
            await webhook_interface.send_event(evt)


class TestWebhookInterfaceSendMessageAndTestConnection:
    """send_message and test_connection for webhook interface."""

    @pytest.mark.asyncio
    async def test_send_message_success(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        mock_discord_client.send_message.return_value = True
        result = await webhook_interface.send_message("Hello", username="Bot")
        assert result is True
        mock_discord_client.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_test_connection(
        self, webhook_interface: WebhookDiscordInterface, mock_discord_client: MagicMock
    ) -> None:
        mock_discord_client.test_connection.return_value = True
        result = await webhook_interface.test_connection()
        assert result is True


# ======================================================================
# BotDiscordInterface tests
# ======================================================================

class TestBotInterfaceInit:
    """Initialization of BotDiscordInterface."""

    def test_init_with_bot(self, mock_discord_bot: MagicMock) -> None:
        interface = BotDiscordInterface(mock_discord_bot)
        assert interface.bot is mock_discord_bot
        assert hasattr(interface, "embed_builder")

    def test_init_when_discord_not_available(self, mock_discord_bot: MagicMock) -> None:
        with patch("discord_interface.DISCORD_AVAILABLE", False):
            interface = BotDiscordInterface(mock_discord_bot)
        assert interface.bot is mock_discord_bot
        assert interface.embed_builder is None


class TestBotInterfaceConnection:
    """Connection lifecycle for bot interface."""

    @pytest.mark.asyncio
    async def test_connect_calls_bot_connect(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        await bot_interface.connect()
        mock_discord_bot.connect_bot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_calls_bot_disconnect(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        await bot_interface.disconnect()
        mock_discord_bot.disconnect_bot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_connected_reflects_bot_state(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        mock_discord_bot.is_connected = True
        assert bot_interface.is_connected is True
        mock_discord_bot.is_connected = False
        assert bot_interface.is_connected is False


class TestBotInterfaceTestConnection:
    """test_connection method for bot interface."""

    @pytest.mark.asyncio
    async def test_connection_when_connected(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        mock_discord_bot.is_connected = True
        result = await bot_interface.test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_connection_when_not_connected(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        mock_discord_bot.is_connected = False
        result = await bot_interface.test_connection()
        assert result is False


class TestBotInterfaceSendEvent:
    """send_event delegation."""

    @pytest.mark.asyncio
    async def test_send_event(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        evt = MagicMock()
        mock_discord_bot.send_event.return_value = True
        result = await bot_interface.send_event(evt)
        assert result is True
        mock_discord_bot.send_event.assert_awaited_once_with(evt)


class TestBotInterfaceSendMessage:
    """send_message behavior and error paths."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123456
        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        result = await bot_interface.send_message("Test message")
        assert result is True
        channel.send.assert_awaited_once_with("Test message")

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        mock_discord_bot.is_connected = False
        result = await bot_interface.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_no_channel(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = None
        result = await bot_interface.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_wrong_channel_type(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        wrong_channel = MagicMock()  # no TextChannel spec
        mock_discord_bot.get_channel = MagicMock(return_value=wrong_channel)

        result = await bot_interface.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_forbidden(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock(side_effect=discord_mock.errors.Forbidden("no perms"))
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        result = await bot_interface.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_http_exception(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock(side_effect=discord_mock.errors.HTTPException("http"))
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        result = await bot_interface.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_unexpected_exception(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock(side_effect=Exception("boom"))
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        result = await bot_interface.send_message("Test message")
        assert result is False


class TestBotInterfaceSendEmbed:
    """send_embed behavior and error paths."""

    @pytest.mark.asyncio
    async def test_send_embed_success(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        embed = MagicMock()
        result = await bot_interface.send_embed(embed)
        assert result is True
        channel.send.assert_awaited_once_with(embed=embed)

    @pytest.mark.asyncio
    async def test_send_embed_not_connected(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        mock_discord_bot.is_connected = False
        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_no_channel(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = None
        result = await bot_interface.send_embed(MagicMock())
        assert result is False


# ======================================================================
# DiscordInterfaceFactory tests
# ======================================================================

@pytest.fixture
def bot_config() -> MagicMock:
    cfg = MagicMock()
    cfg.discord_bot_token = "BOT_TOKEN_123"
    cfg.discord_webhook_url = None
    cfg.bot_name = "TestBot"
    cfg.discord_event_channel_id = 123456789
    cfg.rcon_breakdown_mode = "transition"
    cfg.rcon_breakdown_interval = 300
    return cfg


@pytest.fixture
def webhook_config() -> MagicMock:
    cfg = MagicMock()
    cfg.discord_bot_token = None
    cfg.discord_webhook_url = "https://discord.com/api/webhooks/123/abc"
    cfg.bot_name = "WebhookBot"
    cfg.bot_avatar_url = None
    return cfg


@pytest.fixture
def empty_config() -> MagicMock:
    cfg = MagicMock()
    cfg.discord_bot_token = None
    cfg.discord_webhook_url = None
    cfg.bot_name = "NoBot"
    return cfg


@pytest.fixture
def bot_config_no_channel() -> MagicMock:
    cfg = MagicMock()
    cfg.discord_bot_token = "BOT_TOKEN"
    cfg.discord_webhook_url = None
    cfg.bot_name = "TestBot"
    cfg.discord_event_channel_id = None
    cfg.rcon_breakdown_mode = "transition"
    cfg.rcon_breakdown_interval = 300
    return cfg


class TestFactoryBotCreation:
    """Factory creation of bot interfaces."""

    def test_create_bot_interface(self, bot_config: MagicMock) -> None:
        with patch("discord_bot.DiscordBot") as mock_bot_class:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config)

        assert isinstance(interface, BotDiscordInterface)
        mock_bot_class.assert_called_once_with(
            token="BOT_TOKEN_123",
            bot_name="TestBot",
            breakdown_mode=bot_config.rcon_breakdown_mode,
            breakdown_interval=bot_config.rcon_breakdown_interval,
        )
        bot_instance.set_event_channel.assert_called_once_with(123456789)

    def test_create_bot_interface_no_channel(self, bot_config_no_channel: MagicMock) -> None:
        with patch("discord_bot.DiscordBot") as mock_bot_class:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config_no_channel)

        assert isinstance(interface, BotDiscordInterface)
        bot_instance.set_event_channel.assert_not_called()

    def test_bot_interface_has_required_attributes(self, bot_config: MagicMock) -> None:
        with patch("discord_bot.DiscordBot") as mock_bot_class:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config)

        for attr in ("connect", "disconnect", "send_message", "send_embed", "send_event", "is_connected"):
            assert hasattr(interface, attr)


class TestFactoryWebhookCreation:
    """Factory creation of webhook interfaces."""

    def test_create_webhook_interface(self, webhook_config: MagicMock) -> None:
        with patch("discord_client.DiscordClient") as mock_client_class:
            client_instance = MagicMock()
            mock_client_class.return_value = client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

        assert isinstance(interface, WebhookDiscordInterface)
        mock_client_class.assert_called_once_with(
            webhook_url="https://discord.com/api/webhooks/123/abc",
            bot_name="WebhookBot",
            bot_avatar_url=None,
        )

    def test_webhook_interface_with_avatar(self, webhook_config: MagicMock) -> None:
        webhook_config.bot_avatar_url = "https://example.com/avatar.png"
        with patch("discord_client.DiscordClient") as mock_client_class:
            client_instance = MagicMock()
            mock_client_class.return_value = client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

        assert isinstance(interface, WebhookDiscordInterface)
        kwargs = mock_client_class.call_args.kwargs
        assert kwargs["bot_avatar_url"] == "https://example.com/avatar.png"

    def test_webhook_interface_has_required_attributes(self, webhook_config: MagicMock) -> None:
        with patch("discord_client.DiscordClient") as mock_client_class:
            client_instance = MagicMock()
            mock_client_class.return_value = client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

        for attr in ("connect", "disconnect", "send_message", "send_event", "is_connected"):
            assert hasattr(interface, attr)


class TestFactoryInterfaceTypes:
    """Factory return types and inheritance."""

    def test_bot_interface_is_discord_interface(self, bot_config: MagicMock) -> None:
        with patch("discord_bot.DiscordBot") as mock_bot_class:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = bot_instance

            interface = DiscordInterfaceFactory.create_interface(bot_config)

        assert isinstance(interface, DiscordInterface)

    def test_webhook_interface_is_discord_interface(self, webhook_config: MagicMock) -> None:
        with patch("discord_client.DiscordClient") as mock_client_class:
            client_instance = MagicMock()
            mock_client_class.return_value = client_instance

            interface = DiscordInterfaceFactory.create_interface(webhook_config)

        assert isinstance(interface, DiscordInterface)


class TestFactoryEdgeCases:
    """Edge cases for factory configuration."""

    def test_empty_bot_token_uses_webhook(self) -> None:
        cfg = MagicMock()
        cfg.discord_bot_token = ""
        cfg.discord_webhook_url = "https://discord.com/api/webhooks/fallback"
        cfg.bot_name = "FallbackBot"
        cfg.bot_avatar_url = None

        with patch("discord_client.DiscordClient") as mock_client_class:
            client_instance = MagicMock()
            mock_client_class.return_value = client_instance

            interface = DiscordInterfaceFactory.create_interface(cfg)

        assert isinstance(interface, WebhookDiscordInterface)

    def test_none_bot_name(self) -> None:
        cfg = MagicMock()
        cfg.discord_bot_token = "TOKEN"
        cfg.discord_webhook_url = None
        cfg.bot_name = None
        cfg.discord_event_channel_id = None
        cfg.rcon_breakdown_mode = "transition"
        cfg.rcon_breakdown_interval = 300

        with patch("discord_bot.DiscordBot") as mock_bot_class:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = bot_instance

            interface = DiscordInterfaceFactory.create_interface(cfg)

        assert isinstance(interface, BotDiscordInterface)
        kwargs = mock_bot_class.call_args.kwargs
        assert kwargs["bot_name"] is None

    def test_zero_channel_id(self) -> None:
        cfg = MagicMock()
        cfg.discord_bot_token = "TOKEN"
        cfg.discord_webhook_url = None
        cfg.bot_name = "ZeroBot"
        cfg.discord_event_channel_id = 0
        cfg.rcon_breakdown_mode = "transition"
        cfg.rcon_breakdown_interval = 300

        with patch("discord_bot.DiscordBot") as mock_bot_class:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = bot_instance

            interface = DiscordInterfaceFactory.create_interface(cfg)

        assert isinstance(interface, BotDiscordInterface)
        # Implementation treats falsy values as "no channel"
        bot_instance.set_event_channel.assert_not_called()

    def test_very_long_token(self) -> None:
        token = "X" * 1000
        cfg = MagicMock()
        cfg.discord_bot_token = token
        cfg.discord_webhook_url = None
        cfg.bot_name = "LongTokenBot"
        cfg.discord_event_channel_id = 123
        cfg.rcon_breakdown_mode = "transition"
        cfg.rcon_breakdown_interval = 300

        with patch("discord_bot.DiscordBot") as mock_bot_class:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = bot_instance

            interface = DiscordInterfaceFactory.create_interface(cfg)

        assert isinstance(interface, BotDiscordInterface)
        assert mock_bot_class.call_args.kwargs["token"] == token

    def test_missing_both_bot_and_webhook_raises(self, empty_config: MagicMock) -> None:
        with pytest.raises(ValueError, match="Either DISCORD_BOT_TOKEN or DISCORD_WEBHOOK_URL"):
            DiscordInterfaceFactory.create_interface(empty_config)



# ... existing tests above remain unchanged ...

# ======================================================================
# EmbedBuilder tests (Phase 5.1 utilities)
# ======================================================================

class TestEmbedBuilderBase:
    """Tests for EmbedBuilder low-level behavior."""

    def test_create_base_embed_uses_defaults(self) -> None:
        """create_base_embed should use default color and footer."""
        from discord_interface import EmbedBuilder

        embed = EmbedBuilder.create_base_embed("Title", "Description")

        discord_embed_call = discord_mock.Embed.call_args
        kwargs = discord_embed_call.kwargs
        assert kwargs["title"] == "Title"
        assert kwargs["description"] == "Description"
        assert kwargs["color"] == EmbedBuilder.COLOR_INFO

        # Ensure footer text is correct (do not assume only once)
        embed.set_footer.assert_any_call(text="Factorio ISR")


    def test_create_base_embed_custom_color(self) -> None:
        """create_base_embed should accept explicit color overrides."""
        from discord_interface import EmbedBuilder

        custom_color = 0x123456
        EmbedBuilder.create_base_embed("Title", color=custom_color)
        kwargs = discord_mock.Embed.call_args.kwargs
        assert kwargs["color"] == custom_color

    def test_create_base_embed_raises_when_discord_unavailable(self, monkeypatch: Any) -> None:
        """When DISCORD_AVAILABLE is False, create_base_embed should raise."""
        import discord_interface as di_mod

        # Temporarily mark discord as unavailable
        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)

        from discord_interface import EmbedBuilder

        with pytest.raises(RuntimeError, match="discord.py not available"):
            EmbedBuilder.create_base_embed("Title")


class TestEmbedBuilderSpecializedEmbeds:
    """Tests for specialized embed helpers."""

    def test_server_status_embed_enabled_with_uptime(self) -> None:
        from discord_interface import EmbedBuilder

        embed = EmbedBuilder.server_status_embed(
            status="Online",
            players_online=5,
            rcon_enabled=True,
            uptime="1h 23m",
        )

        # Fields added on the returned embed mock
        calls = [c.kwargs for c in embed.add_field.call_args_list]
        names = [c["name"] for c in calls]
        assert "Status" in names
        assert "Players Online" in names
        assert "RCON" in names
        assert "Uptime" in names

    def test_server_status_embed_disabled_without_uptime(self) -> None:
        from discord_interface import EmbedBuilder

        embed = EmbedBuilder.server_status_embed(
            status="Offline",
            players_online=0,
            rcon_enabled=False,
            uptime=None,
        )

        field_calls = [c.kwargs for c in embed.add_field.call_args_list]
        # The last three fields are from this call
        last_fields = field_calls[-3:]
        names = [c["name"] for c in last_fields]

        assert "Status" in names
        assert "Players Online" in names
        assert "RCON" in names
        assert "Uptime" not in names



    def test_players_list_embed_empty(self) -> None:
        from discord_interface import EmbedBuilder

        embed = EmbedBuilder.players_list_embed([])
        # Should call create_base_embed with the "no players" description
        kwargs = discord_mock.Embed.call_args.kwargs
        assert "No players currently online" in (kwargs.get("description") or "")

    def test_players_list_embed_with_players(self) -> None:
        from discord_interface import EmbedBuilder

        embed = EmbedBuilder.players_list_embed(["Alice", "Bob"])
        # Description should contain list of players
        kwargs = discord_mock.Embed.call_args.kwargs
        desc = kwargs.get("description") or ""
        assert "Alice" in desc
        assert "Bob" in desc
        assert "(2)" in kwargs.get("title", "")

    def test_admin_action_embed_truncates_long_response(self) -> None:
        from discord_interface import EmbedBuilder

        long_response = "X" * 2000
        embed = EmbedBuilder.admin_action_embed(
            action="Ban",
            player="Griefer",
            moderator="Admin",
            reason="Griefing",
            response=long_response,
        )

        # Last field should contain a shortened response with backticks
        last_call_kwargs = embed.add_field.call_args_list[-1].kwargs
        value = last_call_kwargs["value"]
        assert value.startswith("```")
        assert value.endswith("```")
        assert "..." in value

    def test_error_cooldown_and_info_embeds(self) -> None:
        from discord_interface import EmbedBuilder

        EmbedBuilder.error_embed("Something went wrong")
        kwargs_err = discord_mock.Embed.call_args.kwargs
        assert kwargs_err["title"] == "❌ Error"

        EmbedBuilder.cooldown_embed(3.5)
        kwargs_cd = discord_mock.Embed.call_args.kwargs
        assert "Slow Down" in kwargs_cd["title"]

        EmbedBuilder.info_embed("Info", "All good")
        kwargs_info = discord_mock.Embed.call_args.kwargs
        assert kwargs_info["title"] == "Info"
        assert kwargs_info["description"] == "All good"


# ======================================================================
# DiscordInterfaceFactory helper tests
# ======================================================================

class TestFactoryImportHelpers:
    """Direct tests for DiscordInterfaceFactory import helpers."""

    def test_import_with_importlib_missing_module_path_raises(self, monkeypatch: Any) -> None:
        """_import_with_importlib should raise ImportError when __file__ is missing."""
        from discord_interface import DiscordInterfaceFactory

        # Fake __file__ missing on current module
        current_module = MagicMock()
        monkeypatch.setitem(sys.modules, "discord_interface", current_module)
        setattr(current_module, "__file__", None)

        with pytest.raises(ImportError):
            DiscordInterfaceFactory._import_with_importlib("some_module", "SomeClass")


# ======================================================================
# COVERAGE-FOCUSED ADDITIONS (append to test_discord_interface_mega.py)
# ======================================================================

class TestEmbedBuilderCoverage:
    """Isolated tests for EmbedBuilder edge cases and error paths."""

    def test_create_base_embed_when_discord_unavailable(self, monkeypatch: Any) -> None:
        """create_base_embed should raise RuntimeError when discord.py unavailable."""
        import discord_interface as di_mod
        
        # Save original state
        original_available = di_mod.DISCORD_AVAILABLE
        original_discord = di_mod.discord
        
        # Temporarily disable discord
        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)
        
        from discord_interface import EmbedBuilder
        
        with pytest.raises(RuntimeError, match="discord.py not available"):
            EmbedBuilder.create_base_embed("Title")
        
        # Restore
        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", original_available)
        monkeypatch.setattr(di_mod, "discord", original_discord)

    def test_server_status_embed_color_when_rcon_enabled(self) -> None:
        """server_status_embed should use SUCCESS color when RCON enabled."""
        from discord_interface import EmbedBuilder
        
        # Reset mock to isolate this test
        discord_mock.Embed.reset_mock()
        
        EmbedBuilder.server_status_embed(
            status="Online",
            players_online=5,
            rcon_enabled=True,
            uptime=None
        )
        
        kwargs = discord_mock.Embed.call_args.kwargs
        assert kwargs["color"] == EmbedBuilder.COLOR_SUCCESS

    def test_server_status_embed_color_when_rcon_disabled(self) -> None:
        """server_status_embed should use WARNING color when RCON disabled."""
        from discord_interface import EmbedBuilder
        
        discord_mock.Embed.reset_mock()
        
        EmbedBuilder.server_status_embed(
            status="Offline",
            players_online=0,
            rcon_enabled=False,
            uptime=None
        )
        
        kwargs = discord_mock.Embed.call_args.kwargs
        assert kwargs["color"] == EmbedBuilder.COLOR_WARNING

    def test_server_status_embed_with_uptime(self) -> None:
        """server_status_embed should add Uptime field when provided."""
        from discord_interface import EmbedBuilder
        
        embed = MagicMock()
        embed.add_field = MagicMock()
        discord_mock.Embed.return_value = embed
        
        EmbedBuilder.server_status_embed(
            status="Online",
            players_online=3,
            rcon_enabled=True,
            uptime="2h 15m"
        )
        
        # Check that add_field was called with Uptime
        field_names = [call.kwargs["name"] for call in embed.add_field.call_args_list]
        assert "Uptime" in field_names

    def test_server_status_embed_without_uptime(self) -> None:
        """server_status_embed should NOT add Uptime field when None."""
        from discord_interface import EmbedBuilder
        
        embed = MagicMock()
        embed.add_field = MagicMock()
        discord_mock.Embed.return_value = embed
        
        EmbedBuilder.server_status_embed(
            status="Online",
            players_online=3,
            rcon_enabled=True,
            uptime=None
        )
        
        # Count add_field calls - should be 3 (Status, Players, RCON) not 4
        assert embed.add_field.call_count == 3

    def test_players_list_embed_empty_list(self) -> None:
        """players_list_embed with empty list should show 'No players' message."""
        from discord_interface import EmbedBuilder
        
        discord_mock.Embed.reset_mock()
        
        EmbedBuilder.players_list_embed([])
        
        kwargs = discord_mock.Embed.call_args.kwargs
        assert "No players currently online" in kwargs["description"]
        assert kwargs["color"] == EmbedBuilder.COLOR_INFO

    def test_players_list_embed_with_players(self) -> None:
        """players_list_embed with players should list them."""
        from discord_interface import EmbedBuilder
        
        discord_mock.Embed.reset_mock()
        
        EmbedBuilder.players_list_embed(["Alice", "Bob", "Charlie"])
        
        kwargs = discord_mock.Embed.call_args.kwargs
        assert "Alice" in kwargs["description"]
        assert "Bob" in kwargs["description"]
        assert "Charlie" in kwargs["description"]
        assert "(3)" in kwargs["title"]
        assert kwargs["color"] == EmbedBuilder.COLOR_SUCCESS

    def test_admin_action_embed_short_response(self) -> None:
        """admin_action_embed with short response should not truncate."""
        from discord_interface import EmbedBuilder
        
        embed = MagicMock()
        embed.add_field = MagicMock()
        discord_mock.Embed.return_value = embed
        
        short_response = "Command executed successfully"
        
        EmbedBuilder.admin_action_embed(
            action="Kick",
            player="Griefer",
            moderator="Admin",
            reason="Test",
            response=short_response
        )
        
        # Find the Server Response field
        response_field = [call for call in embed.add_field.call_args_list 
                         if call.kwargs.get("name") == "Server Response"][0]
        assert "..." not in response_field.kwargs["value"]
        assert short_response in response_field.kwargs["value"]

    def test_admin_action_embed_long_response_truncates(self) -> None:
        """admin_action_embed with >1000 char response should truncate."""
        from discord_interface import EmbedBuilder
        
        embed = MagicMock()
        embed.add_field = MagicMock()
        discord_mock.Embed.return_value = embed
        
        long_response = "X" * 1500
        
        EmbedBuilder.admin_action_embed(
            action="Ban",
            player="Spammer",
            moderator="Admin",
            reason="Spam",
            response=long_response
        )
        
        # Find the Server Response field
        response_field = [call for call in embed.add_field.call_args_list 
                         if call.kwargs.get("name") == "Server Response"][0]
        value = response_field.kwargs["value"]
        assert "..." in value
        assert len(value) < 1500  # Should be truncated

    def test_admin_action_embed_without_reason_or_response(self) -> None:
        """admin_action_embed should handle None reason and response."""
        from discord_interface import EmbedBuilder
        
        embed = MagicMock()
        embed.add_field = MagicMock()
        discord_mock.Embed.return_value = embed
        
        EmbedBuilder.admin_action_embed(
            action="Warn",
            player="Player1",
            moderator="Mod1",
            reason=None,
            response=None
        )
        
        field_names = [call.kwargs["name"] for call in embed.add_field.call_args_list]
        assert "Reason" not in field_names
        assert "Server Response" not in field_names

    def test_error_embed_creates_red_embed(self) -> None:
        """error_embed should create embed with ERROR color."""
        from discord_interface import EmbedBuilder
        
        discord_mock.Embed.reset_mock()
        
        EmbedBuilder.error_embed("Something went wrong")
        
        kwargs = discord_mock.Embed.call_args.kwargs
        assert kwargs["title"] == "❌ Error"
        assert kwargs["description"] == "Something went wrong"
        assert kwargs["color"] == EmbedBuilder.COLOR_ERROR

    def test_cooldown_embed_formats_time(self) -> None:
        """cooldown_embed should format retry_after time."""
        from discord_interface import EmbedBuilder
        
        discord_mock.Embed.reset_mock()
        
        EmbedBuilder.cooldown_embed(5.7)
        
        kwargs = discord_mock.Embed.call_args.kwargs
        assert "5.7" in kwargs["description"]
        assert kwargs["color"] == EmbedBuilder.COLOR_WARNING

    def test_info_embed_uses_info_color(self) -> None:
        """info_embed should use INFO color."""
        from discord_interface import EmbedBuilder
        
        discord_mock.Embed.reset_mock()
        
        EmbedBuilder.info_embed("Info Title", "Info content")
        
        kwargs = discord_mock.Embed.call_args.kwargs
        assert kwargs["title"] == "Info Title"
        assert kwargs["description"] == "Info content"
        assert kwargs["color"] == EmbedBuilder.COLOR_INFO


class TestBotInterfaceRuntimeErrors:
    """Test BotDiscordInterface error paths at runtime (not just init)."""

    @pytest.mark.asyncio
    async def test_send_message_when_discord_becomes_unavailable(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock, monkeypatch: Any
    ) -> None:
        """send_message should fail gracefully if discord module disappears at runtime."""
        import discord_interface as di_mod
        
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        
        # Simulate discord module becoming unavailable
        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)
        
        result = await bot_interface.send_message("Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_when_discord_becomes_unavailable(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock, monkeypatch: Any
    ) -> None:
        """send_embed should fail gracefully if discord module disappears at runtime."""
        import discord_interface as di_mod
        
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        
        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)
        
        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_channel_not_found(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """send_message should handle get_channel returning None."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 999999
        mock_discord_bot.get_channel = MagicMock(return_value=None)
        
        result = await bot_interface.send_message("Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_channel_not_found(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """send_embed should handle get_channel returning None."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 999999
        mock_discord_bot.get_channel = MagicMock(return_value=None)
        
        result = await bot_interface.send_embed(MagicMock())
        assert result is False


class TestFactoryImportFallbacks:
    """Test DiscordInterfaceFactory import fallback logic."""

    # def test_import_discord_bot_fallback_to_importlib(self, monkeypatch: Any) -> None:
    #     """_import_discord_bot should fall back to importlib when direct import fails."""
    #     from discord_interface import DiscordInterfaceFactory
        
    #     # Mock the imports to force fallback
    #     import sys
    #     original_import = __builtins__.__import__
        
    #     def mock_import(name, *args, **kwargs):
    #         if name == "discord_bot":
    #             raise ImportError("Forced failure")
    #         return original_import(name, *args, **kwargs)
        
    #     with patch("builtins.__import__", side_effect=mock_import):
    #         with patch.object(DiscordInterfaceFactory, "_import_with_importlib") as mock_importlib:
    #             mock_importlib.return_value = type("DiscordBot", (), {})
                
    #             result = DiscordInterfaceFactory._import_discord_bot()
                
    #             mock_importlib.assert_called_once_with("discord_bot", "DiscordBot")

    # def test_import_discord_client_fallback_to_importlib(self, monkeypatch: Any) -> None:
    #     """_import_discord_client should fall back to importlib when direct import fails."""
    #     from discord_interface import DiscordInterfaceFactory
        
    #     original_import = __builtins__.__import__
        
    #     def mock_import(name, *args, **kwargs):
    #         if name == "discord_client":
    #             raise ImportError("Forced failure")
    #         return original_import(name, *args, **kwargs)
        
    #     with patch("builtins.__import__", side_effect=mock_import):
    #         with patch.object(DiscordInterfaceFactory, "_import_with_importlib") as mock_importlib:
    #             mock_importlib.return_value = type("DiscordClient", (), {})
                
    #             result = DiscordInterfaceFactory._import_discord_client()
                
    #             mock_importlib.assert_called_once_with("discord_client", "DiscordClient")

    def test_import_with_importlib_no_spec(self, monkeypatch: Any) -> None:
        """_import_with_importlib should raise ImportError when spec is None."""
        from discord_interface import DiscordInterfaceFactory
        import importlib.util
        
        with patch("importlib.util.spec_from_file_location", return_value=None):
            with pytest.raises(ImportError, match="Could not load"):
                DiscordInterfaceFactory._import_with_importlib("test_module", "TestClass")

    def test_import_with_importlib_no_loader(self, monkeypatch: Any) -> None:
        """_import_with_importlib should raise ImportError when loader is None."""
        from discord_interface import DiscordInterfaceFactory
        
        fake_spec = MagicMock()
        fake_spec.loader = None
        
        with patch("importlib.util.spec_from_file_location", return_value=fake_spec):
            with pytest.raises(ImportError, match="Could not load"):
                DiscordInterfaceFactory._import_with_importlib("test_module", "TestClass")

    # def test_import_with_importlib_missing_class_attribute(self, monkeypatch: Any) -> None:
    #     """_import_with_importlib should raise AttributeError when class doesn't exist in module."""
    #     from discord_interface import DiscordInterfaceFactory
    #     import importlib.util
        
    #     # Create a real module without the target class
    #     fake_spec = MagicMock()
    #     fake_spec.loader = MagicMock()
    #     fake_module = MagicMock()
        
    #     with patch("importlib.util.spec_from_file_location", return_value=fake_spec):
    #         with patch("importlib.util.module_from_spec", return_value=fake_module):
    #             # Make getattr raise AttributeError
    #             with patch("builtins.getattr", side_effect=AttributeError("No such class")):
    #                 with pytest.raises(AttributeError):
    #                     DiscordInterfaceFactory._import_with_importlib("test_module", "MissingClass")

    # def test_import_with_importlib_logs_sys_path_addition(self, monkeypatch: Any) -> None:
    #     """_import_with_importlib should log when adding to sys.path."""
    #     from discord_interface import DiscordInterfaceFactory
    #     import sys
        
    #     # This test just ensures the sys.path modification branch is hit
    #     # We can't easily test the logger.debug call, but we can verify the path logic
        
    #     fake_spec = MagicMock()
    #     fake_spec.loader = MagicMock()
    #     fake_module = type("FakeModule", (), {"TestClass": type("TestClass", (), {})})()
        
    #     with patch("importlib.util.spec_from_file_location", return_value=fake_spec):
    #         with patch("importlib.util.module_from_spec", return_value=fake_module):
    #             with patch("builtins.getattr", return_value=type("TestClass", (), {})):
    #                 # Force sys.path manipulation by ensuring src_dir not in sys.path
    #                 original_path = sys.path.copy()
    #                 sys.path = ["/some/other/path"]
                    
    #                 try:
    #                     result = DiscordInterfaceFactory._import_with_importlib("test", "TestClass")
    #                     # Just verify it completes without error
    #                     assert result is not None
    #                 finally:
    #                     sys.path = original_path


class TestFactoryCreateInterfaceErrors:
    """Test error handling in create_interface."""

    def test_create_bot_interface_import_error(self) -> None:
        """create_interface should raise ImportError with helpful message when DiscordBot import fails."""
        cfg = MagicMock()
        cfg.discord_bot_token = "TOKEN"
        cfg.discord_webhook_url = None
        
        from discord_interface import DiscordInterfaceFactory
        
        with patch.object(DiscordInterfaceFactory, "_import_discord_bot", side_effect=ImportError("File not found")):
            with pytest.raises(ImportError, match="Could not import DiscordBot"):
                DiscordInterfaceFactory.create_interface(cfg)

    def test_create_webhook_interface_import_error(self) -> None:
        """create_interface should raise ImportError when DiscordClient import fails."""
        cfg = MagicMock()
        cfg.discord_bot_token = None
        cfg.discord_webhook_url = "https://discord.com/api/webhooks/test"
        cfg.bot_name = "TestBot"
        
        from discord_interface import DiscordInterfaceFactory
        
        with patch.object(DiscordInterfaceFactory, "_import_discord_client", side_effect=ImportError("File not found")):
            with pytest.raises(ImportError, match="Could not import DiscordClient"):
                DiscordInterfaceFactory.create_interface(cfg)

    def test_create_bot_interface_with_none_breakdown_params(self) -> None:
        """create_interface should handle None breakdown_mode and interval."""
        cfg = MagicMock()
        cfg.discord_bot_token = "TOKEN"
        cfg.discord_webhook_url = None
        cfg.bot_name = "TestBot"
        cfg.discord_event_channel_id = 123
        cfg.rcon_breakdown_mode = None
        cfg.rcon_breakdown_interval = None
        
        with patch("discord_bot.DiscordBot") as mock_bot_class:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_class.return_value = bot_instance
            
            from discord_interface import DiscordInterfaceFactory
            interface = DiscordInterfaceFactory.create_interface(cfg)
            
            # Verify None values were passed through
            kwargs = mock_bot_class.call_args.kwargs
            assert kwargs["breakdown_mode"] is None
            assert kwargs["breakdown_interval"] is None

    def test_create_webhook_with_getattr_default(self) -> None:
        """create_interface should use getattr default when bot_avatar_url missing."""
        cfg = MagicMock()
        cfg.discord_bot_token = None
        cfg.discord_webhook_url = "https://discord.com/webhooks/test"
        cfg.bot_name = "TestBot"
        # Simulate missing bot_avatar_url attribute
        del cfg.bot_avatar_url
        
        with patch("discord_client.DiscordClient") as mock_client_class:
            client_instance = MagicMock()
            mock_client_class.return_value = client_instance
            
            from discord_interface import DiscordInterfaceFactory
            interface = DiscordInterfaceFactory.create_interface(cfg)
            
            # Verify getattr default (None) was used
            kwargs = mock_client_class.call_args.kwargs
            assert kwargs["bot_avatar_url"] is None


class TestDiscordInterfaceBase:
    """Coverage for abstract base default behaviors."""

    @pytest.mark.asyncio
    async def test_send_embed_default_returns_false(self) -> None:
        from discord_interface import DiscordInterface

        class Dummy(DiscordInterface):
            async def connect(self) -> None: ...
            async def disconnect(self) -> None: ...
            async def send_event(self, event: Any) -> bool: return True
            async def send_message(self, message: str, username: Optional[str] = None) -> bool: return True
            async def test_connection(self) -> bool: return True
            @property
            def is_connected(self) -> bool: return True

        dummy = Dummy()
        result = await dummy.send_embed(MagicMock())
        assert result is False
        
        
class TestEmbedBuilderEdges:
    """Targeted tests for EmbedBuilder branches."""

    def test_create_base_embed_raises_when_discord_unavailable(self, monkeypatch: Any) -> None:
        import discord_interface as di_mod
        from discord_interface import EmbedBuilder

        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)

        with pytest.raises(RuntimeError, match="discord.py not available"):
            EmbedBuilder.create_base_embed("Title")

    def test_server_status_embed_color_enabled_vs_disabled(self) -> None:
        from discord_interface import EmbedBuilder

        discord_mock.Embed.reset_mock()
        EmbedBuilder.server_status_embed("Running", 3, True, None)
        enabled_color = discord_mock.Embed.call_args.kwargs["color"]

        discord_mock.Embed.reset_mock()
        EmbedBuilder.server_status_embed("Stopped", 0, False, None)
        disabled_color = discord_mock.Embed.call_args.kwargs["color"]

        assert enabled_color == EmbedBuilder.COLOR_SUCCESS
        assert disabled_color == EmbedBuilder.COLOR_WARNING

    def test_server_status_embed_adds_and_omits_uptime(self) -> None:
        from discord_interface import EmbedBuilder

        embed = MagicMock()
        embed.add_field = MagicMock()
        discord_mock.Embed.return_value = embed

        EmbedBuilder.server_status_embed("Online", 5, True, "1h")
        names_with = [c.kwargs["name"] for c in embed.add_field.call_args_list]
        assert "Uptime" in names_with

        embed.add_field.reset_mock()
        EmbedBuilder.server_status_embed("Online", 5, True, None)
        names_without = [c.kwargs["name"] for c in embed.add_field.call_args_list]
        assert "Uptime" not in names_without

    def test_players_list_embed_empty_vs_nonempty(self) -> None:
        from discord_interface import EmbedBuilder

        discord_mock.Embed.reset_mock()
        EmbedBuilder.players_list_embed([])
        kwargs_empty = discord_mock.Embed.call_args.kwargs
        assert "No players currently online" in kwargs_empty["description"]
        assert kwargs_empty["color"] == EmbedBuilder.COLOR_INFO

        discord_mock.Embed.reset_mock()
        EmbedBuilder.players_list_embed(["Alice", "Bob"])
        kwargs_nonempty = discord_mock.Embed.call_args.kwargs
        assert "Alice" in kwargs_nonempty["description"]
        assert "Bob" in kwargs_nonempty["description"]
        assert "(2)" in kwargs_nonempty["title"]
        assert kwargs_nonempty["color"] == EmbedBuilder.COLOR_SUCCESS

    def test_admin_action_embed_reason_and_response_variants(self) -> None:
        from discord_interface import EmbedBuilder

        embed = MagicMock()
        embed.add_field = MagicMock()
        discord_mock.Embed.return_value = embed

        # Reason and short response
        EmbedBuilder.admin_action_embed("Kick", "P1", "Mod", "Test", "OK")
        names = [c.kwargs["name"] for c in embed.add_field.call_args_list]
        assert "Reason" in names
        assert "Server Response" in names

        # No reason or response
        embed.add_field.reset_mock()
        EmbedBuilder.admin_action_embed("Warn", "P1", "Mod", None, None)
        names2 = [c.kwargs["name"] for c in embed.add_field.call_args_list]
        assert "Reason" not in names2
        assert "Server Response" not in names2

        # Long response truncation
        embed.add_field.reset_mock()
        long_response = "X" * 1500
        EmbedBuilder.admin_action_embed("Ban", "P1", "Mod", "Griefing", long_response)
        response_field = [c for c in embed.add_field.call_args_list if c.kwargs["name"] == "Server Response"][0]
        value = response_field.kwargs["value"]
        assert "..." in value
        assert len(value) < len(long_response)

    def test_error_cooldown_and_info_embeds(self) -> None:
        from discord_interface import EmbedBuilder

        discord_mock.Embed.reset_mock()
        EmbedBuilder.error_embed("Bad")
        err_kwargs = discord_mock.Embed.call_args.kwargs
        assert err_kwargs["title"] == "❌ Error"
        assert err_kwargs["color"] == EmbedBuilder.COLOR_ERROR

        discord_mock.Embed.reset_mock()
        EmbedBuilder.cooldown_embed(3.2)
        cd_kwargs = discord_mock.Embed.call_args.kwargs
        assert "3.2" in cd_kwargs["description"]
        assert cd_kwargs["color"] == EmbedBuilder.COLOR_WARNING

        discord_mock.Embed.reset_mock()
        EmbedBuilder.info_embed("Info", "Message")
        info_kwargs = discord_mock.Embed.call_args.kwargs
        assert info_kwargs["title"] == "Info"
        assert info_kwargs["description"] == "Message"
        assert info_kwargs["color"] == EmbedBuilder.COLOR_INFO

class TestBotInterfaceRemainingBranches:
    """Cover BotDiscordInterface branches not in happy-path tests."""

    def test_init_when_discord_unavailable_sets_embed_builder_none(self, monkeypatch: Any, mock_discord_bot: MagicMock) -> None:
        import discord_interface as di_mod
        from discord_interface import BotDiscordInterface

        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "EmbedBuilder", MagicMock())

        iface = BotDiscordInterface(mock_discord_bot)
        assert iface.embed_builder is None

    @pytest.mark.asyncio
    async def test_send_message_channel_none(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        mock_discord_bot.get_channel = MagicMock(return_value=None)

        result = await bot_interface.send_message("Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_channel_none(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        mock_discord_bot.get_channel = MagicMock(return_value=None)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_runtime_discord_unavailable(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock, monkeypatch: Any) -> None:
        import discord_interface as di_mod

        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)

        result = await bot_interface.send_message("Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_runtime_discord_unavailable(self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock, monkeypatch: Any) -> None:
        import discord_interface as di_mod

        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

class TestFactoryErrorBranches:
    """Cover factory import and error handling without heavy import mocking."""

    def test_import_with_importlib_no_spec(self) -> None:
        from discord_interface import DiscordInterfaceFactory

        with patch("importlib.util.spec_from_file_location", return_value=None):
            with pytest.raises(ImportError, match="Could not load"):
                DiscordInterfaceFactory._import_with_importlib("mod", "Cls")

    def test_import_with_importlib_no_loader(self) -> None:
        from discord_interface import DiscordInterfaceFactory

        fake_spec = MagicMock()
        fake_spec.loader = None

        with patch("importlib.util.spec_from_file_location", return_value=fake_spec):
            with pytest.raises(ImportError, match="Could not load"):
                DiscordInterfaceFactory._import_with_importlib("mod", "Cls")

    def test_create_bot_interface_wraps_import_error(self) -> None:
        from discord_interface import DiscordInterfaceFactory

        cfg = MagicMock()
        cfg.discord_bot_token = "TOKEN"
        cfg.discord_webhook_url = None
        cfg.bot_name = "Bot"
        cfg.rcon_breakdown_mode = "transition"
        cfg.rcon_breakdown_interval = 300

        with patch.object(DiscordInterfaceFactory, "_import_discord_bot", side_effect=ImportError("broken")):
            with pytest.raises(ImportError, match="Could not import DiscordBot"):
                DiscordInterfaceFactory.create_interface(cfg)

    def test_create_webhook_interface_wraps_import_error(self) -> None:
        from discord_interface import DiscordInterfaceFactory

        cfg = MagicMock()
        cfg.discord_bot_token = None
        cfg.discord_webhook_url = "https://discord.com/api/webhooks/x/y"
        cfg.bot_name = "Webhook"

        with patch.object(DiscordInterfaceFactory, "_import_discord_client", side_effect=ImportError("broken")):
            with pytest.raises(ImportError, match="Could not import DiscordClient"):
                DiscordInterfaceFactory.create_interface(cfg)

    def test_create_bot_interface_with_none_breakdown_params(self) -> None:
        from discord_interface import DiscordInterfaceFactory

        cfg = MagicMock()
        cfg.discord_bot_token = "TOKEN"
        cfg.discord_webhook_url = None
        cfg.bot_name = "Bot"
        cfg.discord_event_channel_id = 123
        cfg.rcon_breakdown_mode = None
        cfg.rcon_breakdown_interval = None

        with patch("discord_bot.DiscordBot") as mock_bot_cls:
            bot_instance = MagicMock()
            bot_instance.set_event_channel = MagicMock()
            mock_bot_cls.return_value = bot_instance

            interface = DiscordInterfaceFactory.create_interface(cfg)
            kwargs = mock_bot_cls.call_args.kwargs
            assert kwargs["breakdown_mode"] is None
            assert kwargs["breakdown_interval"] is None

    def test_create_webhook_interface_uses_getattr_default_for_avatar(self) -> None:
        from discord_interface import DiscordInterfaceFactory

        cfg = MagicMock()
        cfg.discord_bot_token = None
        cfg.discord_webhook_url = "https://discord.com/api/webhooks/x/y"
        cfg.bot_name = "Webhook"
        # simulate no bot_avatar_url attribute
        if hasattr(cfg, "bot_avatar_url"):
            del cfg.bot_avatar_url

        with patch("discord_client.DiscordClient") as mock_client_cls:
            client_instance = MagicMock()
            mock_client_cls.return_value = client_instance

            interface = DiscordInterfaceFactory.create_interface(cfg)
            kwargs = mock_client_cls.call_args.kwargs
            assert kwargs["bot_avatar_url"] is None


class TestBotInterfaceSendEmbedRemaining:
    @pytest.mark.asyncio
    async def test_send_embed_channel_none(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        mock_discord_bot.get_channel = MagicMock(return_value=None)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_runtime_discord_unavailable(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock, monkeypatch: Any
    ) -> None:
        import discord_interface as di_mod

        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

# class TestFactoryImportBotClientFallback:
    # def test_import_discord_bot_uses_importlib_on_import_error(self) -> None:
    #     from discord_interface import DiscordInterfaceFactory

    #     with patch("discord_interface.DiscordInterfaceFactory._import_with_importlib") as mock_fallback:
    #         mock_fallback.return_value = MagicMock()
    #         with patch("discord_interface.discord_bot", create=True):
    #             # Force ImportError via mocking the direct import inside helper
    #             with patch("discord_interface.DiscordInterfaceFactory._import_discord_bot.__globals__", new={}):
    #                 # Call the helper; we only care that fallback is used
    #                 DiscordInterfaceFactory._import_discord_bot()
    #         mock_fallback.assert_called_once_with("discord_bot", "DiscordBot")

    # def test_import_discord_client_uses_importlib_on_import_error(self) -> None:
    #     from discord_interface import DiscordInterfaceFactory

    #     with patch("discord_interface.DiscordInterfaceFactory._import_with_importlib") as mock_fallback:
    #         mock_fallback.return_value = MagicMock()
    #         with patch("discord_interface.DiscordInterfaceFactory._import_discord_client.__globals__", new={}):
    #             DiscordInterfaceFactory._import_discord_client()
    #         mock_fallback.assert_called_once_with("discord_client", "DiscordClient")

class TestImportWithImportlibBranches:
    def test_import_with_importlib_no_current_path(self, monkeypatch: Any) -> None:
        from discord_interface import DiscordInterfaceFactory
        import sys

        # Fake module with no __file__
        current_module = MagicMock()
        monkeypatch.setitem(sys.modules, "discord_interface", current_module)
        setattr(current_module, "__name__", "discord_interface")
        setattr(current_module, "__file__", None)

        with pytest.raises(ImportError, match="Could not determine module path"):
            DiscordInterfaceFactory._import_with_importlib("mod", "Cls")

    def test_import_with_importlib_success_path(self, monkeypatch: Any) -> None:
        from discord_interface import DiscordInterfaceFactory
        import importlib.util

        fake_spec = MagicMock()
        fake_spec.loader = MagicMock()

        fake_module = type(
            "FakeModule",
            (),
            {"MyClass": type("MyClass", (), {})}
        )()

        with patch("importlib.util.spec_from_file_location", return_value=fake_spec):
            with patch("importlib.util.module_from_spec", return_value=fake_module):
                result = DiscordInterfaceFactory._import_with_importlib("mod", "MyClass")
        assert result is not None

class TestBotInterfaceSendEmbedBranches:
    """Exhaustive branch coverage for BotDiscordInterface.send_embed."""

    @pytest.mark.asyncio
    async def test_send_embed_not_connected(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """Branch: bot is not connected → returns False."""
        mock_discord_bot.is_connected = False

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_no_channel(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """Branch: event_channel_id is None → returns False."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = None

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_discord_unavailable_runtime(
        self,
        bot_interface: BotDiscordInterface,
        mock_discord_bot: MagicMock,
        monkeypatch: Any,
    ) -> None:
        """Branch: DISCORD_AVAILABLE False / discord None at runtime → returns False."""
        import discord_interface as di_mod

        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        monkeypatch.setattr(di_mod, "DISCORD_AVAILABLE", False)
        monkeypatch.setattr(di_mod, "discord", None)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_channel_not_found(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """Branch: get_channel returns None → returns False."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123
        mock_discord_bot.get_channel = MagicMock(return_value=None)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_invalid_channel_type(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """Branch: channel is not a TextChannel → returns False."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        wrong_channel = MagicMock()  # no TextChannel spec
        mock_discord_bot.get_channel = MagicMock(return_value=wrong_channel)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_forbidden_error(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """Branch: channel.send raises Forbidden → returns False."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock(side_effect=discord_mock.errors.Forbidden("no perms"))
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_http_exception(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """Branch: channel.send raises HTTPException → returns False."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock(side_effect=discord_mock.errors.HTTPException("http"))
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_unexpected_exception(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """Branch: channel.send raises generic Exception → returns False."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock(side_effect=Exception("boom"))
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        result = await bot_interface.send_embed(MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_success(
        self, bot_interface: BotDiscordInterface, mock_discord_bot: MagicMock
    ) -> None:
        """Happy path: connected, valid channel, send succeeds → returns True."""
        mock_discord_bot.is_connected = True
        mock_discord_bot.event_channel_id = 123

        channel = MagicMock(spec=discord_mock.TextChannel)
        channel.send = AsyncMock()
        mock_discord_bot.get_channel = MagicMock(return_value=channel)

        embed = MagicMock()
        result = await bot_interface.send_embed(embed)

        assert result is True
        channel.send.assert_awaited_once_with(embed=embed)
