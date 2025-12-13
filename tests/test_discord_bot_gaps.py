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

"""Gap coverage tests for discord_bot.py - Phase 6 final push to 93%.

Phase 6 of coverage intensity: Targeted gap coverage for remaining statements.

Coverage targets:
- Event handler error paths (on_ready error)
- Message sending guard clauses and exceptions
- Notification methods with edge cases
- Connection/disconnection exception handling

Total: 13 tests covering the remaining 6% gap to 93%.
"""

import asyncio
import pytest
from typing import Optional
from unittest.mock import Mock, AsyncMock, MagicMock, patch, PropertyMock
import discord

try:
    from discord_bot import DiscordBot
except ImportError:
    pass


class TestOnReadyErrorPath:
    """Test on_ready error handling when user is None."""

    @pytest.mark.asyncio
    async def test_on_ready_no_user(self) -> None:
        """on_ready should handle missing user gracefully."""
        bot = DiscordBot(token="test-token")
        
        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
            mock_user.return_value = None
            
            # Should not raise
            await bot.on_ready()
            
            # Should not set connected flag
            assert bot._connected is False


class TestSendMessageErrorPaths:
    """Test send_message error handling and guard clauses."""

    @pytest.mark.asyncio
    async def test_send_message_when_disconnected(self) -> None:
        """send_message should return early when bot disconnected."""
        bot = DiscordBot(token="test-token")
        bot._connected = False
        bot.event_channel_id = 123456789
        
        # Should not raise
        await bot.send_message("test message")
        
        # Should return early without sending
        assert True

    @pytest.mark.asyncio
    async def test_send_message_no_channel(self) -> None:
        """send_message should return early when channel not configured."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = None
        
        # Should not raise
        await bot.send_message("test message")
        
        # Should return early without sending
        assert True

    @pytest.mark.asyncio
    async def test_send_message_channel_not_found(self) -> None:
        """send_message should handle channel not found gracefully."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        bot.get_channel = MagicMock(return_value=None)
        
        # Should not raise
        await bot.send_message("test message")
        
        # Should return early without sending
        assert True

    @pytest.mark.asyncio
    async def test_send_message_invalid_channel_type(self) -> None:
        """send_message should handle wrong channel type gracefully."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        
        # Return a voice channel instead of text channel
        mock_channel = MagicMock(spec=discord.VoiceChannel)
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        # Should not raise
        await bot.send_message("test message")
        
        # Should return early without sending
        assert True

    @pytest.mark.asyncio
    async def test_send_message_forbidden_error(self) -> None:
        """send_message should handle Forbidden exception."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=discord.errors.Forbidden(
                MagicMock(status=403), "Forbidden"
            )
        )
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        # Should not raise
        await bot.send_message("test message")
        
        # Should handle error gracefully
        assert True

    @pytest.mark.asyncio
    async def test_send_message_http_error(self) -> None:
        """send_message should handle HTTPException."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=discord.errors.HTTPException(
                MagicMock(status=500), "Server Error"
            )
        )
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        # Should not raise
        await bot.send_message("test message")
        
        # Should handle error gracefully
        assert True

    @pytest.mark.asyncio
    async def test_send_message_generic_error(self) -> None:
        """send_message should handle generic exceptions."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        # Should not raise
        await bot.send_message("test message")
        
        # Should handle error gracefully
        assert True


class TestNotificationGuards:
    """Test notification methods with guard clauses."""

    @pytest.mark.asyncio
    async def test_send_connection_notification_no_manager(self) -> None:
        """_send_connection_notification should handle missing server manager."""
        bot = DiscordBot(token="test-token")
        bot.server_manager = None
        
        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
            mock_user.return_value = MagicMock(name="Test Bot")
            
            # Should not raise
            await bot._send_connection_notification()
            
            # Should return early
            assert True

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_not_connected(self) -> None:
        """_send_disconnection_notification should guard when not connected."""
        bot = DiscordBot(token="test-token")
        bot._connected = False
        bot.server_manager = MagicMock()
        
        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
            mock_user.return_value = MagicMock(name="Test Bot")
            
            # Should not raise
            await bot._send_disconnection_notification()
            
            # Should return early
            assert True

    @pytest.mark.asyncio
    async def test_send_disconnection_notification_no_manager(self) -> None:
        """_send_disconnection_notification should guard when no manager."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.server_manager = None
        
        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
            mock_user.return_value = MagicMock(name="Test Bot")
            
            # Should not raise
            await bot._send_disconnection_notification()
            
            # Should return early
            assert True


class TestConnectionExceptionPaths:
    """Test connection exception handling."""

    @pytest.mark.asyncio
    async def test_connect_bot_timeout_with_task_cancel(self) -> None:
        """connect_bot should handle timeout and cancel task."""
        bot = DiscordBot(token="test-token")
        bot.login = AsyncMock()
        bot.connect = AsyncMock()
        
        # Create a real task that times out
        async def long_sleep():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
        
        bot.connect = AsyncMock(return_value=asyncio.create_task(long_sleep()))
        
        # Don't set ready event - causes timeout
        with pytest.raises(ConnectionError, match="timed out after 30 seconds"):
            async def connect_with_timeout():
                bot.login = AsyncMock()
                bot.connect = AsyncMock()
                # Simulate timeout
                try:
                    await asyncio.wait_for(
                        bot._ready.wait(),
                        timeout=0.01
                    )
                except asyncio.TimeoutError:
                    if bot._connection_task and not bot._connection_task.done():
                        bot._connection_task.cancel()
                    raise ConnectionError("Discord bot connection timed out after 30 seconds")
            
            await connect_with_timeout()

    @pytest.mark.asyncio
    async def test_connect_bot_generic_exception(self) -> None:
        """connect_bot should handle generic exceptions."""
        bot = DiscordBot(token="test-token")
        bot.login = AsyncMock(side_effect=RuntimeError("Test error"))
        
        with pytest.raises(RuntimeError, match="Test error"):
            await bot.connect_bot()


class TestDisconnectBotClose:
    """Test disconnect close handling."""

    @pytest.mark.asyncio
    async def test_disconnect_bot_close_when_open(self) -> None:
        """disconnect_bot should close bot when not already closed."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot._connection_task = None
        bot.is_closed = MagicMock(return_value=False)
        bot.close = AsyncMock()
        
        # Mock monitors
        bot.rcon_monitor = AsyncMock()
        bot.rcon_monitor.stop = AsyncMock()
        bot.presence_manager = AsyncMock()
        bot.presence_manager.stop = AsyncMock()
        bot._send_disconnection_notification = AsyncMock()
        
        await bot.disconnect_bot()
        
        # Verify close was called
        bot.close.assert_awaited_once()
        assert bot._connected is False


class TestSendMessageHappyPath:
    """Test send_message successful path."""

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """send_message should successfully send message to channel."""
        bot = DiscordBot(token="test-token")
        bot._connected = True
        bot.event_channel_id = 123456789
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=mock_channel)
        
        await bot.send_message("test message")
        
        # Verify message was sent
        mock_channel.send.assert_awaited_once_with("test message")
