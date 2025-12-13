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
from unittest.mock import MagicMock, AsyncMock, Mock, patch, PropertyMock
import pytest
import sys
import discord

from discord_interface import (
    EmbedBuilder,
    DiscordInterface,
    BotDiscordInterface,
    DiscordInterfaceFactory,
    QUERY_COOLDOWN,
    ADMIN_COOLDOWN,
    DANGER_COOLDOWN,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_discord_bot():
    """Create a mock Discord bot."""
    bot = MagicMock()
    bot.is_connected = True
    bot.event_channel_id = 123456789
    bot.connect_bot = AsyncMock()
    bot.disconnect_bot = AsyncMock()
    bot.send_event = AsyncMock(return_value=True)
    bot.get_channel = MagicMock()
    return bot


@pytest.fixture
def mock_discord_text_channel():
    """Create a mock Discord TextChannel."""
    channel = AsyncMock()
    channel.send = AsyncMock()
    return channel


@pytest.fixture
def bot_interface(mock_discord_bot):
    """Create BotDiscordInterface with mocked bot."""
    with patch('discord_interface.DISCORD_AVAILABLE', True):
        with patch('discord_interface.discord') as mock_discord:
            interface = BotDiscordInterface(mock_discord_bot)
    return interface


# ============================================================================
# EmbedBuilder Tests (10 tests)
# ============================================================================

class TestEmbedBuilder:
    """Test EmbedBuilder utility class."""

    def test_embed_builder_color_constants(self):
        """Test that all color constants are defined."""
        assert EmbedBuilder.COLOR_SUCCESS == 0x00FF00
        assert EmbedBuilder.COLOR_INFO == 0x3498DB
        assert EmbedBuilder.COLOR_WARNING == 0xFFA500
        assert EmbedBuilder.COLOR_ERROR == 0xFF0000
        assert EmbedBuilder.COLOR_ADMIN == 0xFFC0CB
        assert EmbedBuilder.COLOR_FACTORIO == 0xFF6B00

    def test_create_base_embed_with_defaults(self):
        """Test create_base_embed with default parameters."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                embed = EmbedBuilder.create_base_embed(
                    title="Test Title",
                    description="Test Description"
                )

                mock_discord.Embed.assert_called_once()
                mock_embed.set_footer.assert_called_once_with(text="Factorio ISR")
                assert embed == mock_embed

    def test_create_base_embed_with_color(self):
        """Test create_base_embed with custom color."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                embed = EmbedBuilder.create_base_embed(
                    title="Test",
                    color=EmbedBuilder.COLOR_SUCCESS
                )

                call_kwargs = mock_discord.Embed.call_args.kwargs
                assert call_kwargs['color'] == EmbedBuilder.COLOR_SUCCESS

    def test_create_base_embed_no_discord_raises_error(self):
        """Test create_base_embed raises error when discord unavailable."""
        with patch('discord_interface.DISCORD_AVAILABLE', False):
            with patch('discord_interface.discord', None):
                with pytest.raises(RuntimeError, match="discord.py not available"):
                    EmbedBuilder.create_base_embed("Test")

    def test_server_status_embed(self):
        """Test server_status_embed creation."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                embed = EmbedBuilder.server_status_embed(
                    status="Running",
                    players_online=5,
                    rcon_enabled=True,
                    uptime="2 days"
                )

                mock_embed.add_field.assert_called()
                assert mock_embed.add_field.call_count == 4

    def test_players_list_embed_empty(self):
        """Test players_list_embed with no players."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                embed = EmbedBuilder.players_list_embed([])

                call_kwargs = mock_discord.Embed.call_args.kwargs
                assert "No players" in call_kwargs['description']

    def test_players_list_embed_with_players(self):
        """Test players_list_embed with multiple players."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                players = ["Alice", "Bob", "Charlie"]
                embed = EmbedBuilder.players_list_embed(players)

                call_kwargs = mock_discord.Embed.call_args.kwargs
                assert "3" in call_kwargs['title']
                assert "Alice" in call_kwargs['description']

    def test_admin_action_embed(self):
        """Test admin_action_embed creation."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                embed = EmbedBuilder.admin_action_embed(
                    action="Ban",
                    player="Hacker",
                    moderator="Admin",
                    reason="Cheating",
                    response="Player banned"
                )

                assert mock_embed.add_field.call_count == 4

    def test_error_embed(self):
        """Test error_embed creation."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                embed = EmbedBuilder.error_embed("Connection failed")

                call_kwargs = mock_discord.Embed.call_args.kwargs
                assert call_kwargs['color'] == EmbedBuilder.COLOR_ERROR
                assert "Connection failed" in call_kwargs['description']

    def test_cooldown_embed(self):
        """Test cooldown_embed creation."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                embed = EmbedBuilder.cooldown_embed(5.5)

                call_kwargs = mock_discord.Embed.call_args.kwargs
                assert call_kwargs['color'] == EmbedBuilder.COLOR_WARNING
                assert "5.5" in call_kwargs['description']

    def test_info_embed(self):
        """Test info_embed creation."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_embed = MagicMock()
                mock_discord.Embed.return_value = mock_embed
                mock_discord.utils.utcnow.return_value = "2024-01-01T00:00:00"

                embed = EmbedBuilder.info_embed("Info Title", "Info message")

                call_kwargs = mock_discord.Embed.call_args.kwargs
                assert call_kwargs['color'] == EmbedBuilder.COLOR_INFO
                assert "Info Title" in call_kwargs['title']


# ============================================================================
# DiscordInterface (Abstract) Tests (2 tests)
# ============================================================================

class TestDiscordInterface:
    """Test abstract DiscordInterface contract."""

    def test_interface_is_abstract(self):
        """Test that DiscordInterface cannot be instantiated."""
        with pytest.raises(TypeError):
            DiscordInterface()  # type: ignore

    @pytest.mark.asyncio
    async def test_send_embed_default_returns_false(self):
        """Test default send_embed implementation returns False."""
        class ConcreteDiscordInterface(DiscordInterface):
            async def connect(self):
                pass

            async def disconnect(self):
                pass

            async def send_event(self, event):
                return True

            async def send_message(self, message, username=None):
                return True

            async def test_connection(self):
                return True

            @property
            def is_connected(self):
                return True

        interface = ConcreteDiscordInterface()
        result = await interface.send_embed(MagicMock())
        assert result is False


# ============================================================================
# BotDiscordInterface Tests (14 tests)
# ============================================================================

class TestBotDiscordInterface:
    """Test BotDiscordInterface implementation."""

    def test_init_creates_interface(self, mock_discord_bot):
        """Test initialization with bot."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface = BotDiscordInterface(mock_discord_bot)
            assert interface.bot is mock_discord_bot
            assert interface.channel_id is None
            assert interface.embed_builder is not None

    def test_init_wires_cooldown_constants(self, mock_discord_bot):
        """Test initialization wires cooldown constants."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface = BotDiscordInterface(mock_discord_bot)
            assert interface.query_cooldown == QUERY_COOLDOWN
            assert interface.admin_cooldown == ADMIN_COOLDOWN
            assert interface.danger_cooldown == DANGER_COOLDOWN

    def test_init_without_discord_available(self, mock_discord_bot):
        """Test initialization when discord not available."""
        with patch('discord_interface.DISCORD_AVAILABLE', False):
            interface = BotDiscordInterface(mock_discord_bot)
            assert interface.bot is mock_discord_bot
            assert interface.embed_builder is None

    def test_use_channel_creates_bound_instance(self, mock_discord_bot):
        """Test use_channel creates new instance bound to channel."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface1 = BotDiscordInterface(mock_discord_bot)
            interface2 = interface1.use_channel(987654321)
            assert interface1.channel_id is None
            assert interface2.channel_id == 987654321
            assert interface2.bot is mock_discord_bot

    @pytest.mark.asyncio
    async def test_connect(self, mock_discord_bot):
        """Test connect calls bot.connect_bot()."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface = BotDiscordInterface(mock_discord_bot)
            await interface.connect()
            mock_discord_bot.connect_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_discord_bot):
        """Test disconnect calls bot.disconnect_bot()."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface = BotDiscordInterface(mock_discord_bot)
            await interface.disconnect()
            mock_discord_bot.disconnect_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_event(self, mock_discord_bot):
        """Test send_event delegates to bot."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface = BotDiscordInterface(mock_discord_bot)
            event = MagicMock()
            result = await interface.send_event(event)
            mock_discord_bot.send_event.assert_called_once_with(event)
            assert result is True

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_discord_bot, mock_discord_text_channel):
        """Test send_message succeeds when connected."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_discord.TextChannel = type('TextChannel', (), {})
                mock_discord_bot.get_channel.return_value = mock_discord_text_channel
                mock_discord_text_channel.__class__ = mock_discord.TextChannel
                interface = BotDiscordInterface(mock_discord_bot)
                result = await interface.send_message("Test message")
                assert result is True
                mock_discord_text_channel.send.assert_called_once_with("Test message")

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, mock_discord_bot):
        """Test send_message returns False when not connected."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            mock_discord_bot.is_connected = False
            interface = BotDiscordInterface(mock_discord_bot)
            result = await interface.send_message("Test message")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_no_channel(self, mock_discord_bot):
        """Test send_message returns False when no channel configured."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            mock_discord_bot.event_channel_id = None
            interface = BotDiscordInterface(mock_discord_bot)
            result = await interface.send_message("Test message")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_channel_not_found(self, mock_discord_bot):
        """Test send_message handles channel not found."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord'):
                mock_discord_bot.get_channel.return_value = None
                interface = BotDiscordInterface(mock_discord_bot)
                result = await interface.send_message("Test")
                assert result is False

    @pytest.mark.asyncio
    async def test_send_message_invalid_channel_type(self, mock_discord_bot):
        """Test send_message with invalid channel type."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                wrong_channel = MagicMock()
                wrong_channel.__class__.__name__ = 'VoiceChannel'
                mock_discord.TextChannel = type('TextChannel', (), {})
                mock_discord_bot.get_channel.return_value = wrong_channel
                interface = BotDiscordInterface(mock_discord_bot)
                result = await interface.send_message("Test")
                assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_success(self, mock_discord_bot, mock_discord_text_channel):
        """Test send_embed succeeds when connected."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_discord.TextChannel = type('TextChannel', (), {})
                mock_discord_bot.get_channel.return_value = mock_discord_text_channel
                mock_discord_text_channel.__class__ = mock_discord.TextChannel
                interface = BotDiscordInterface(mock_discord_bot)
                embed = MagicMock()
                result = await interface.send_embed(embed)
                assert result is True
                mock_discord_text_channel.send.assert_called_once_with(embed=embed)

    @pytest.mark.asyncio
    async def test_send_embed_not_connected(self, mock_discord_bot):
        """Test send_embed returns False when not connected."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            mock_discord_bot.is_connected = False
            interface = BotDiscordInterface(mock_discord_bot)
            result = await interface.send_embed(MagicMock())
            assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_with_bound_channel(self, mock_discord_bot, mock_discord_text_channel):
        """Test send_embed uses bound channel when set."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_discord.TextChannel = type('TextChannel', (), {})
                mock_discord_bot.get_channel.return_value = mock_discord_text_channel
                mock_discord_text_channel.__class__ = mock_discord.TextChannel
                interface = BotDiscordInterface(mock_discord_bot).use_channel(999999999)
                embed = MagicMock()
                result = await interface.send_embed(embed)
                mock_discord_bot.get_channel.assert_called_with(999999999)
                assert result is True

    @pytest.mark.asyncio
    async def test_test_connection(self, mock_discord_bot):
        """Test test_connection returns bot connection status."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface = BotDiscordInterface(mock_discord_bot)
            mock_discord_bot.is_connected = True
            result = await interface.test_connection()
            assert result is True
            mock_discord_bot.is_connected = False
            result = await interface.test_connection()
            assert result is False

    def test_is_connected_property(self, mock_discord_bot):
        """Test is_connected property returns bot status."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface = BotDiscordInterface(mock_discord_bot)
            mock_discord_bot.is_connected = True
            assert interface.is_connected is True
            mock_discord_bot.is_connected = False
            assert interface.is_connected is False


# ============================================================================
# DiscordInterfaceFactory Tests (5 tests)
# ============================================================================

class TestDiscordInterfaceFactory:
    """Test DiscordInterfaceFactory."""

    def test_import_discord_bot_raises_or_succeeds(self):
        """Test _import_discord_bot handles missing module gracefully."""
        try:
            result = DiscordInterfaceFactory._import_discord_bot()
            assert result is not None
        except ImportError:
            pass

    def test_create_interface_no_token_raises_error(self):
        """Test create_interface raises ValueError without token."""
        config = MagicMock()
        config.discord_bot_token = None
        with pytest.raises(ValueError, match="discord_bot_token is REQUIRED"):
            DiscordInterfaceFactory.create_interface(config)

    def test_create_interface_with_empty_token_raises_error(self):
        """Test create_interface raises ValueError with empty string token."""
        config = MagicMock()
        config.discord_bot_token = ""
        with pytest.raises(ValueError, match="discord_bot_token is REQUIRED"):
            DiscordInterfaceFactory.create_interface(config)

    def test_create_interface_import_error_handling(self):
        """Test create_interface handles import errors gracefully."""
        config = MagicMock()
        config.discord_bot_token = "test_token"
        with patch.object(
            DiscordInterfaceFactory,
            '_import_discord_bot',
            side_effect=ImportError("Test import error")
        ):
            with pytest.raises(ImportError, match="Could not import DiscordBot"):
                DiscordInterfaceFactory.create_interface(config)

    def test_create_interface_success(self):
        """Test create_interface successfully creates interface."""
        config = MagicMock()
        config.discord_bot_token = "test_token"
        with patch.object(
            DiscordInterfaceFactory,
            '_import_discord_bot'
        ) as mock_import:
            mock_discord_bot_class = MagicMock()
            mock_bot_instance = MagicMock()
            mock_discord_bot_class.return_value = mock_bot_instance
            mock_import.return_value = mock_discord_bot_class
            with patch('discord_interface.DISCORD_AVAILABLE', True):
                interface = DiscordInterfaceFactory.create_interface(config)
                assert isinstance(interface, BotDiscordInterface)
                mock_discord_bot_class.assert_called_once_with(token="test_token")


# ============================================================================
# Integration Tests (5 tests)
# ============================================================================

class TestDiscordInterfaceIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_connect_send_disconnect_workflow(self, mock_discord_bot, mock_discord_text_channel):
        """Test complete connect -> send -> disconnect workflow."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_discord.TextChannel = type('TextChannel', (), {})
                mock_discord_bot.get_channel.return_value = mock_discord_text_channel
                mock_discord_text_channel.__class__ = mock_discord.TextChannel
                interface = BotDiscordInterface(mock_discord_bot)
                await interface.connect()
                mock_discord_bot.connect_bot.assert_called_once()
                result = await interface.send_message("Hello")
                assert result is True
                await interface.disconnect()
                mock_discord_bot.disconnect_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_cascade(self, mock_discord_bot):
        """Test error handling in send operations."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord'):
                mock_discord_bot.get_channel.return_value = None
                interface = BotDiscordInterface(mock_discord_bot)
                result = await interface.send_message("Test")
                assert result is False

    @pytest.mark.asyncio
    async def test_multi_channel_routing(self, mock_discord_bot, mock_discord_text_channel):
        """Test routing to different channels via use_channel."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_discord.TextChannel = type('TextChannel', (), {})
                mock_discord_bot.get_channel.return_value = mock_discord_text_channel
                mock_discord_text_channel.__class__ = mock_discord.TextChannel
                interface = BotDiscordInterface(mock_discord_bot).use_channel(555555555)
                result = await interface.send_message("Routed message")
                assert result is True
                mock_discord_bot.get_channel.assert_called_with(555555555)

    @pytest.mark.asyncio
    async def test_send_embed_and_message_workflow(self, mock_discord_bot, mock_discord_text_channel):
        """Test sending both embeds and messages."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            with patch('discord_interface.discord') as mock_discord:
                mock_discord.TextChannel = type('TextChannel', (), {})
                mock_discord_bot.get_channel.return_value = mock_discord_text_channel
                mock_discord_text_channel.__class__ = mock_discord.TextChannel
                interface = BotDiscordInterface(mock_discord_bot)
                result1 = await interface.send_message("Hello")
                assert result1 is True
                embed = MagicMock()
                result2 = await interface.send_embed(embed)
                assert result2 is True
                assert mock_discord_text_channel.send.call_count == 2

    def test_embed_builder_integration(self):
        """Test EmbedBuilder integration with BotDiscordInterface."""
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            mock_bot = MagicMock()
            interface = BotDiscordInterface(mock_bot)
            assert interface.embed_builder is not None
            assert hasattr(interface.embed_builder, 'create_base_embed')
            assert hasattr(interface.embed_builder, 'server_status_embed')
            assert hasattr(interface.embed_builder, 'players_list_embed')
            assert hasattr(interface.embed_builder, 'cooldown_embed')
            assert hasattr(interface.embed_builder, 'info_embed')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
