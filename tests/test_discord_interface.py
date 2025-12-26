

"""Comprehensive test suite for discord_interface.py

Coverage targets:
- EmbedBuilder: All 12 embed creation methods
- BotDiscordInterface: Connection, messaging, embed sending (24 paths)
- DiscordInterfaceFactory: Bot import and interface creation (7 paths)
- DiscordInterface: Abstract base (2 paths)

Total: 60+ tests covering 79% -> 93%+ coverage.
"""

import pytest
import sys
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import discord

try:
    from discord_interface import (
        EmbedBuilder, BotDiscordInterface, DiscordInterfaceFactory,
        DiscordInterface, DISCORD_AVAILABLE
    )
except ImportError:
    from src.discord_interface import (
        EmbedBuilder, BotDiscordInterface, DiscordInterfaceFactory,
        DiscordInterface, DISCORD_AVAILABLE
    )


class TestEmbedBuilder:
    """Test EmbedBuilder - All embed creation methods."""

    def test_create_base_embed_success(self) -> None:
        """create_base_embed should create embed with title and color."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.create_base_embed(
            title="Test Title",
            description="Test Description",
            color=0xFF0000
        )
        
        assert embed.title == "Test Title"
        assert embed.description == "Test Description"
        assert embed.color.value == 0xFF0000
        assert embed.footer.text == "Factorio ISR"

    def test_create_base_embed_default_color(self) -> None:
        """create_base_embed should use COLOR_INFO as default."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.create_base_embed(title="Test")
        
        assert embed.color.value == EmbedBuilder.COLOR_INFO

    def test_create_base_embed_discord_unavailable(self) -> None:
        """create_base_embed should raise when discord unavailable."""
        with patch('discord_interface.DISCORD_AVAILABLE', False):
            with patch('discord_interface.discord', None):
                with pytest.raises(RuntimeError, match="discord.py not available"):
                    EmbedBuilder.create_base_embed("Test")

    def test_server_status_embed_rcon_enabled(self) -> None:
        """server_status_embed should use success color when RCON enabled."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.server_status_embed(
            status="Running",
            players_online=5,
            rcon_enabled=True
        )
        
        assert embed.color.value == EmbedBuilder.COLOR_SUCCESS
        field_values = [f.value for f in embed.fields]
        assert any("Running" in str(v) for v in field_values)
        assert any("5" in str(v) for v in field_values)

    def test_server_status_embed_rcon_disabled(self) -> None:
        """server_status_embed should use warning color when RCON disabled."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.server_status_embed(
            status="Offline",
            players_online=0,
            rcon_enabled=False
        )
        
        assert embed.color.value == EmbedBuilder.COLOR_WARNING

    def test_server_status_embed_with_uptime(self) -> None:
        """server_status_embed should include uptime field when provided."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.server_status_embed(
            status="Running",
            players_online=3,
            rcon_enabled=True,
            uptime="5 days 12 hours"
        )
        
        field_names = [f.name for f in embed.fields]
        assert "Uptime" in field_names
        uptime_field = next(f for f in embed.fields if f.name == "Uptime")
        assert "5 days 12 hours" in uptime_field.value

    def test_server_status_embed_no_uptime(self) -> None:
        """server_status_embed should work without uptime."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.server_status_embed(
            status="Running",
            players_online=2,
            rcon_enabled=True,
            uptime=None
        )
        
        assert embed.title == "🏭 Factorio Server Status"

    def test_players_list_embed_empty(self) -> None:
        """players_list_embed should handle empty player list."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.players_list_embed([])
        
        assert "No players currently online" in embed.description
        assert embed.color.value == EmbedBuilder.COLOR_INFO

    def test_players_list_embed_with_players(self) -> None:
        """players_list_embed should format player list correctly."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        players = ["Alice", "Bob", "Charlie"]
        embed = EmbedBuilder.players_list_embed(players)
        
        assert "Alice" in embed.description
        assert "Bob" in embed.description
        assert "Charlie" in embed.description
        assert "3" in embed.title
        assert embed.color.value == EmbedBuilder.COLOR_SUCCESS

    def test_admin_action_embed_minimal(self) -> None:
        """admin_action_embed should work with just action and player."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.admin_action_embed(
            action="Ban",
            player="Griefer123",
            moderator="Admin"
        )
        
        assert "Ban" in embed.title
        assert embed.color.value == EmbedBuilder.COLOR_ADMIN
        field_names = [f.name for f in embed.fields]
        assert "Player" in field_names
        assert "Moderator" in field_names

    def test_admin_action_embed_with_reason(self) -> None:
        """admin_action_embed should include reason when provided."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.admin_action_embed(
            action="Kick",
            player="BadBehavior",
            moderator="Mod",
            reason="Excessive spam"
        )
        
        field_names = [f.name for f in embed.fields]
        assert "Reason" in field_names
        reason_field = next(f for f in embed.fields if f.name == "Reason")
        assert "Excessive spam" in reason_field.value

    def test_admin_action_embed_with_response(self) -> None:
        """admin_action_embed should truncate long responses."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        long_response = "x" * 2000
        embed = EmbedBuilder.admin_action_embed(
            action="Ban",
            player="Test",
            moderator="Admin",
            response=long_response
        )
        
        field_names = [f.name for f in embed.fields]
        assert "Server Response" in field_names
        response_field = next(f for f in embed.fields if f.name == "Server Response")
        # Response should be truncated (with code block wrapping)
        assert "..." in response_field.value

    def test_admin_action_embed_response_exactly_1000(self) -> None:
        """admin_action_embed should not truncate response of exactly 1000 chars."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        resp = "x" * 1000
        embed = EmbedBuilder.admin_action_embed("Ban", "p", "m", response=resp)
        field = next(f for f in embed.fields if f.name == "Server Response")
        # Count x's in the value (account for code block wrapping)
        x_count = field.value.count("x")
        assert x_count == 1000
        # Should not have ellipsis for exactly 1000 chars
        assert "..." not in field.value

    def test_admin_action_embed_response_1001(self) -> None:
        """admin_action_embed should truncate response of 1001 chars."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        resp = "x" * 1001
        embed = EmbedBuilder.admin_action_embed("Ban", "p", "m", response=resp)
        field = next(f for f in embed.fields if f.name == "Server Response")
        # Should contain truncation ellipsis
        assert "..." in field.value
        # Count x's (should be 1000, not 1001)
        x_count = field.value.count("x")
        assert x_count == 1000

    def test_error_embed(self) -> None:
        """error_embed should create error embed with red color."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.error_embed("Something went wrong")
        
        assert "Error" in embed.title
        assert "Something went wrong" in embed.description
        assert embed.color.value == EmbedBuilder.COLOR_ERROR

    def test_cooldown_embed(self) -> None:
        """cooldown_embed should show retry time."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.cooldown_embed(5.5)
        
        assert "5.5" in embed.description
        assert "Slow Down" in embed.title
        assert embed.color.value == EmbedBuilder.COLOR_WARNING

    def test_cooldown_embed_small_time(self) -> None:
        """cooldown_embed should format small time values correctly."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.cooldown_embed(0.1)
        
        assert "0.1" in embed.description

    def test_cooldown_embed_large_time(self) -> None:
        """cooldown_embed should format large time values correctly."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.cooldown_embed(3600.5)
        
        assert "3600.5" in embed.description

    def test_info_embed(self) -> None:
        """info_embed should create generic info embed."""
        if not DISCORD_AVAILABLE:
            pytest.skip("discord.py not available")
        
        embed = EmbedBuilder.info_embed("Status", "All systems operational")
        
        assert embed.title == "Status"
        assert embed.description == "All systems operational"
        assert embed.color.value == EmbedBuilder.COLOR_INFO

    def test_embed_color_constants_defined(self) -> None:
        """All embed color constants should be defined."""
        assert hasattr(EmbedBuilder, 'COLOR_SUCCESS')
        assert hasattr(EmbedBuilder, 'COLOR_INFO')
        assert hasattr(EmbedBuilder, 'COLOR_WARNING')
        assert hasattr(EmbedBuilder, 'COLOR_ERROR')
        assert hasattr(EmbedBuilder, 'COLOR_ADMIN')
        assert isinstance(EmbedBuilder.COLOR_SUCCESS, int)
        assert isinstance(EmbedBuilder.COLOR_INFO, int)
        assert isinstance(EmbedBuilder.COLOR_WARNING, int)
        assert isinstance(EmbedBuilder.COLOR_ERROR, int)
        assert isinstance(EmbedBuilder.COLOR_ADMIN, int)


class TestBotDiscordInterface:
    """Test BotDiscordInterface - Bot interface implementation."""

    def test_init_with_discord_available(self) -> None:
        """__init__ should set embed_builder when discord available."""
        mock_bot = MagicMock()
        
        with patch('discord_interface.DISCORD_AVAILABLE', True):
            interface = BotDiscordInterface(mock_bot)
            
            assert interface.bot is mock_bot
            assert interface.channel_id is None
            assert interface.embed_builder is not None

    def test_init_without_discord(self) -> None:
        """__init__ should handle missing discord module."""
        mock_bot = MagicMock()
        
        with patch('discord_interface.DISCORD_AVAILABLE', False):
            interface = BotDiscordInterface(mock_bot)
            
            assert interface.bot is mock_bot
            assert interface.embed_builder is None

    def test_use_channel_binding(self) -> None:
        """use_channel should create bound instance."""
        mock_bot = MagicMock()
        interface = BotDiscordInterface(mock_bot)
        
        bound = interface.use_channel(123456789)
        
        assert bound.channel_id == 123456789
        assert bound.bot is mock_bot
        assert bound is not interface

    @pytest.mark.asyncio
    async def test_connect(self) -> None:
        """connect should call bot.connect_bot()."""
        mock_bot = AsyncMock()
        interface = BotDiscordInterface(mock_bot)
        
        await interface.connect()
        
        mock_bot.connect_bot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        """disconnect should call bot.disconnect_bot()."""
        mock_bot = AsyncMock()
        interface = BotDiscordInterface(mock_bot)
        
        await interface.disconnect()
        
        mock_bot.disconnect_bot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_event(self) -> None:
        """send_event should delegate to bot.send_event()."""
        mock_bot = AsyncMock()
        mock_bot.send_event = AsyncMock(return_value=True)
        interface = BotDiscordInterface(mock_bot)
        
        mock_event = MagicMock()
        result = await interface.send_event(mock_event)
        
        mock_bot.send_event.assert_awaited_once_with(mock_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_when_disconnected(self) -> None:
        """send_message should return False when not connected."""
        mock_bot = MagicMock()
        mock_bot.is_connected = False
        interface = BotDiscordInterface(mock_bot)
        
        result = await interface.send_message("test")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_no_channel(self) -> None:
        """send_message should return False when no channel configured."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = None
        interface = BotDiscordInterface(mock_bot)
        
        result = await interface.send_message("test")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """send_message should send to text channel successfully."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        result = await interface.send_message("test message")
        
        mock_channel.send.assert_awaited_once_with("test message")
        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_channel_not_found(self) -> None:
        """send_message should return False if channel not found."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 999999999
        mock_bot.get_channel = MagicMock(return_value=None)
        
        interface = BotDiscordInterface(mock_bot)
        result = await interface.send_message("test")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_invalid_channel_type(self) -> None:
        """send_message should return False for non-text channel."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = MagicMock(spec=discord.VoiceChannel)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        result = await interface.send_message("test")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_forbidden_error(self) -> None:
        """send_message should handle Forbidden exception."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=discord.errors.Forbidden(MagicMock(status=403), "Forbidden")
        )
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        result = await interface.send_message("test")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_http_error(self) -> None:
        """send_message should handle HTTPException."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=discord.errors.HTTPException(MagicMock(status=500), "Error")
        )
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        result = await interface.send_message("test")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_generic_error(self) -> None:
        """send_message should handle generic exceptions."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(side_effect=RuntimeError("Error"))
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        result = await interface.send_message("test")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_discord_unavailable(self) -> None:
        """send_message should return False when discord unavailable."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123
        
        with patch('discord_interface.DISCORD_AVAILABLE', False):
            with patch('discord_interface.discord', None):
                interface = BotDiscordInterface(mock_bot)
                result = await interface.send_message("test")
                assert result is False

    @pytest.mark.asyncio
    async def test_send_message_uses_global_channel_when_unbound(self) -> None:
        """send_message should use global channel when not bound."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 111
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)  # channel_id is None
        await interface.send_message("test")
        mock_bot.get_channel.assert_called_with(111)

    @pytest.mark.asyncio
    async def test_send_message_bound_channel_takes_priority(self) -> None:
        """send_message should use bound channel over global."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 111
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        bound = interface.use_channel(222)
        await bound.send_message("test")
        mock_bot.get_channel.assert_called_with(222)

    @pytest.mark.asyncio
    async def test_send_embed_when_disconnected(self) -> None:
        """send_embed should return False when not connected."""
        mock_bot = MagicMock()
        mock_bot.is_connected = False
        interface = BotDiscordInterface(mock_bot)
        
        mock_embed = MagicMock(spec=discord.Embed)
        result = await interface.send_embed(mock_embed)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_no_channel(self) -> None:
        """send_embed should return False when no channel configured."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = None
        interface = BotDiscordInterface(mock_bot)
        
        mock_embed = MagicMock(spec=discord.Embed)
        result = await interface.send_embed(mock_embed)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_success(self) -> None:
        """send_embed should send embed to text channel successfully."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        mock_embed = MagicMock(spec=discord.Embed)
        result = await interface.send_embed(mock_embed)
        
        mock_channel.send.assert_awaited_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_send_embed_channel_not_found(self) -> None:
        """send_embed should return False if channel not found."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 999999999
        mock_bot.get_channel = MagicMock(return_value=None)
        
        interface = BotDiscordInterface(mock_bot)
        mock_embed = MagicMock(spec=discord.Embed)
        result = await interface.send_embed(mock_embed)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_invalid_channel_type(self) -> None:
        """send_embed should return False for non-text channel."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = MagicMock(spec=discord.VoiceChannel)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        mock_embed = MagicMock(spec=discord.Embed)
        result = await interface.send_embed(mock_embed)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_forbidden_error(self) -> None:
        """send_embed should handle Forbidden exception."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=discord.errors.Forbidden(MagicMock(status=403), "Forbidden")
        )
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        mock_embed = MagicMock(spec=discord.Embed)
        result = await interface.send_embed(mock_embed)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_http_error(self) -> None:
        """send_embed should handle HTTPException."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=discord.errors.HTTPException(MagicMock(status=500), "Error")
        )
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        mock_embed = MagicMock(spec=discord.Embed)
        result = await interface.send_embed(mock_embed)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_generic_error(self) -> None:
        """send_embed should handle generic exceptions."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(side_effect=RuntimeError("Error"))
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        mock_embed = MagicMock(spec=discord.Embed)
        result = await interface.send_embed(mock_embed)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_discord_unavailable(self) -> None:
        """send_embed should return False when discord unavailable."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 123
        
        with patch('discord_interface.DISCORD_AVAILABLE', False):
            with patch('discord_interface.discord', None):
                interface = BotDiscordInterface(mock_bot)
                result = await interface.send_embed(MagicMock(spec=discord.Embed))
                assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_uses_global_channel_when_unbound(self) -> None:
        """send_embed should use global channel when not bound."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 111
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)  # channel_id is None
        await interface.send_embed(MagicMock(spec=discord.Embed))
        mock_bot.get_channel.assert_called_with(111)

    @pytest.mark.asyncio
    async def test_send_embed_bound_channel_takes_priority(self) -> None:
        """send_embed should use bound channel over global."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.event_channel_id = 111
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        
        interface = BotDiscordInterface(mock_bot)
        bound = interface.use_channel(222)
        await bound.send_embed(MagicMock(spec=discord.Embed))
        mock_bot.get_channel.assert_called_with(222)

    @pytest.mark.asyncio
    async def test_test_connection(self) -> None:
        """test_connection should return bot connection status."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        interface = BotDiscordInterface(mock_bot)
        
        result = await interface.test_connection()
        
        assert result is True

    def test_is_connected_property(self) -> None:
        """is_connected property should return bot status."""
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        interface = BotDiscordInterface(mock_bot)
        
        assert interface.is_connected is True


class TestDiscordInterfaceFactory:
    """Test DiscordInterfaceFactory - Interface creation."""

    def test_create_interface_no_token(self) -> None:
        """create_interface should raise ValueError if no token."""
        mock_config = MagicMock()
        mock_config.discord_bot_token = None
        
        with pytest.raises(ValueError, match="discord_bot_token is REQUIRED"):
            DiscordInterfaceFactory.create_interface(mock_config)

    def test_create_interface_success(self) -> None:
        """create_interface should create BotDiscordInterface."""
        mock_config = MagicMock()
        mock_config.discord_bot_token = "test-token"
        
        with patch.object(
            DiscordInterfaceFactory,
            '_import_discord_bot',
            return_value=MagicMock()
        ):
            interface = DiscordInterfaceFactory.create_interface(mock_config)
            
            assert isinstance(interface, BotDiscordInterface)

    def test_create_interface_import_failure(self) -> None:
        """create_interface should raise ImportError if bot import fails."""
        mock_config = MagicMock()
        mock_config.discord_bot_token = "test-token"
        
        with patch.object(
            DiscordInterfaceFactory,
            '_import_discord_bot',
            side_effect=ImportError("Failed to import")
        ):
            with pytest.raises(ImportError, match="Could not import DiscordBot"):
                DiscordInterfaceFactory.create_interface(mock_config)

    def test_import_discord_bot_fallback_to_importlib(self) -> None:
        """_import_discord_bot should fallback to importlib when direct import fails."""
        with patch.dict(sys.modules, {'discord_bot': None}):
            with patch.object(
                DiscordInterfaceFactory,
                '_import_with_importlib',
                return_value=MagicMock()
            ) as mock_importlib:
                result = DiscordInterfaceFactory._import_discord_bot()
                mock_importlib.assert_called()
                assert result is mock_importlib.return_value

    def test_import_with_importlib_no_current_path(self) -> None:
        """_import_with_importlib should raise if __file__ not available."""
        with patch('discord_interface.__file__', None):
            with pytest.raises(ImportError, match="Could not determine module path"):
                DiscordInterfaceFactory._import_with_importlib('test_module', 'TestClass')

    def test_import_with_importlib_no_spec(self) -> None:
        """_import_with_importlib should raise if spec_from_file_location fails."""
        import importlib.util
        with patch('importlib.util.spec_from_file_location', return_value=None):
            with pytest.raises(ImportError, match="Could not load"):
                DiscordInterfaceFactory._import_with_importlib('test_module', 'TestClass')

    def test_import_with_importlib_success(self) -> None:
        """_import_with_importlib should successfully import module."""
        # This test creates a minimal mock module structure
        mock_spec = MagicMock()
        mock_loader = MagicMock()
        mock_spec.loader = mock_loader
        
        mock_module = MagicMock()
        mock_module.TestClass = MagicMock()
        mock_loader.exec_module = MagicMock()
        
        with patch('importlib.util.spec_from_file_location', return_value=mock_spec):
            with patch('importlib.util.module_from_spec', return_value=mock_module):
                result = DiscordInterfaceFactory._import_with_importlib('test_module', 'TestClass')
                assert result is mock_module.TestClass


class TestDiscordInterfaceAbstract:
    """Test DiscordInterface abstract base."""

    def test_send_embed_default_implementation(self) -> None:
        """send_embed should have default implementation that returns False coroutine."""
        class TestInterface(DiscordInterface):
            async def connect(self) -> None:
                pass
            
            async def disconnect(self) -> None:
                pass
            
            async def send_event(self, event: Any) -> bool:
                return False
            
            async def send_message(self, message: str, username: Optional[str] = None) -> bool:
                return False
            
            async def test_connection(self) -> bool:
                return False
            
            @property
            def is_connected(self) -> bool:
                return False
        
        interface = TestInterface()
        result_sync = interface.send_embed(MagicMock())
        
        assert hasattr(result_sync, '__await__')
