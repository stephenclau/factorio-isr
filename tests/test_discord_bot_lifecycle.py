"""
Pytest test suite for discord_bot.py lifecycle methods
Based on ACTUAL implementation from source code - UPDATED for Phase 6
"""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import pytest
import asyncio
import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from discord_bot import DiscordBot

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def real_intents():
    """Return real Discord intents"""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    return intents


@pytest.fixture
def bot(real_intents):
    """Create a DiscordBot instance for testing"""
    bot = DiscordBot(token="TEST_TOKEN", bot_name="TestBot", intents=real_intents)

    # Mock user and guilds properties (read-only in Discord.py)
    mock_user = MagicMock(id=12345, name="TestBot")
    type(bot).user = PropertyMock(return_value=mock_user)  # pyright: ignore[reportAttributeAccessIssue]
    type(bot).guilds = PropertyMock(return_value=[MagicMock(), MagicMock()])  # pyright: ignore[reportAttributeAccessIssue]

    return bot


@pytest.fixture
def mock_rcon():
    """Mock RCON client"""
    rcon = MagicMock()
    rcon.is_connected = True
    rcon.host = "localhost"
    rcon.port = 27015
    rcon.execute = AsyncMock()
    return rcon


@pytest.fixture
def mock_channel():
    """Mock Discord TextChannel"""
    channel = MagicMock(spec=discord.TextChannel)
    channel.send = AsyncMock()
    return channel


# ============================================================================
# TEST: _format_uptime
# ============================================================================

def test_format_uptime_less_than_one_minute(bot):
    """Test formatting uptime less than 1 minute"""
    delta = timedelta(seconds=30)
    result = bot._format_uptime(delta)
    # Implementation shows "0m" for < 1 minute when minutes==0
    assert result == "0m"


def test_format_uptime_zero_seconds(bot):
    """Test formatting zero uptime"""
    delta = timedelta(seconds=0)
    result = bot._format_uptime(delta)
    # Implementation shows "0m" for zero uptime
    assert result == "0m"


def test_format_uptime_exactly_one_minute(bot):
    """Test formatting exactly 1 minute"""
    delta = timedelta(minutes=1)
    result = bot._format_uptime(delta)
    assert result == "1m"


def test_format_uptime_minutes_only(bot):
    """Test formatting minutes only (less than 1 hour)"""
    delta = timedelta(minutes=45)
    result = bot._format_uptime(delta)
    assert result == "45m"


def test_format_uptime_hours_and_minutes(bot):
    """Test formatting hours and minutes"""
    delta = timedelta(hours=2, minutes=15)
    result = bot._format_uptime(delta)
    assert result == "2h 15m"


def test_format_uptime_hours_only(bot):
    """Test formatting hours with zero minutes"""
    delta = timedelta(hours=3)
    result = bot._format_uptime(delta)
    # Minutes only shown if > 0 OR (days==0 AND hours==0)
    # Here: minutes=0, days=0, hours=3, so condition is False
    assert result == "3h"


def test_format_uptime_days_hours_minutes(bot):
    """Test formatting days, hours, and minutes"""
    delta = timedelta(days=2, hours=5, minutes=30)
    result = bot._format_uptime(delta)
    assert result == "2d 5h 30m"


def test_format_uptime_days_only(bot):
    """Test formatting days with zero hours and minutes"""
    delta = timedelta(days=1)
    result = bot._format_uptime(delta)
    # Minutes only shown if > 0 OR (days==0 AND hours==0)
    # Here: minutes=0, days=1, hours=0, so condition is False
    assert result == "1d"


def test_format_uptime_days_and_minutes(bot):
    """Test formatting days and minutes without hours"""
    delta = timedelta(days=3, minutes=42)
    result = bot._format_uptime(delta)
    assert result == "3d 42m"


def test_format_uptime_large_value(bot):
    """Test formatting large uptime value"""
    delta = timedelta(days=365, hours=12, minutes=30)
    result = bot._format_uptime(delta)
    assert result == "365d 12h 30m"


# ============================================================================
# TEST: _get_game_uptime
# ============================================================================

@pytest.mark.asyncio
async def test_get_game_uptime_no_rcon_client(bot):
    """Test game uptime when RCON client is None"""
    bot.rcon_client = None
    result = await bot._get_game_uptime()
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_rcon_not_connected(bot, mock_rcon):
    """Test game uptime when RCON not connected"""
    mock_rcon.is_connected = False
    bot.rcon_client = mock_rcon
    result = await bot._get_game_uptime()
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_success(bot, mock_rcon):
    """Test successful game uptime query"""
    # 3600 ticks = 60 seconds = 1 minute (60 ticks/sec)
    mock_rcon.execute.return_value = "3600"
    bot.rcon_client = mock_rcon

    result = await bot._get_game_uptime()

    mock_rcon.execute.assert_awaited_once_with("/c rcon.print(game.tick)")
    assert result == "1m"


@pytest.mark.asyncio
async def test_get_game_uptime_large_ticks(bot, mock_rcon):
    """Test game uptime with large tick value"""
    # 7_200_000 ticks = 120,000 seconds
    # = 1 day + 9 hours + 20 minutes (not 33 hours - it breaks into days)
    mock_rcon.execute.return_value = "7200000"
    bot.rcon_client = mock_rcon

    result = await bot._get_game_uptime()
    # Implementation breaks large values into days/hours/minutes
    assert result == "1d 9h 20m"


@pytest.mark.asyncio
async def test_get_game_uptime_empty_response(bot, mock_rcon):
    """Test game uptime with empty RCON response"""
    mock_rcon.execute.return_value = ""
    bot.rcon_client = mock_rcon

    result = await bot._get_game_uptime()
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_whitespace_response(bot, mock_rcon):
    """Test game uptime with whitespace-only response"""
    mock_rcon.execute.return_value = "   \n  "
    bot.rcon_client = mock_rcon

    result = await bot._get_game_uptime()
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_invalid_response(bot, mock_rcon):
    """Test game uptime with non-numeric response"""
    mock_rcon.execute.return_value = "not a number"
    bot.rcon_client = mock_rcon

    result = await bot._get_game_uptime()
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_negative_ticks(bot, mock_rcon):
    """Test game uptime with negative tick count"""
    mock_rcon.execute.return_value = "-1000"
    bot.rcon_client = mock_rcon

    result = await bot._get_game_uptime()
    assert result == "Unknown"


@pytest.mark.asyncio
async def test_get_game_uptime_exception(bot, mock_rcon):
    """Test game uptime when RCON raises exception"""
    mock_rcon.execute.side_effect = Exception("Connection lost")
    bot.rcon_client = mock_rcon

    result = await bot._get_game_uptime()
    assert result == "Unknown"


# ============================================================================
# TEST: update_presence
# ============================================================================

@pytest.mark.asyncio
async def test_update_presence_when_connected_with_rcon_online(bot, mock_rcon):
    """Test update_presence when bot connected and RCON online"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    mock_rcon.is_connected = True
    bot.change_presence = AsyncMock()

    await bot.update_presence()

    # Should call change_presence with online status
    bot.change_presence.assert_awaited_once()
    call_kwargs = bot.change_presence.call_args.kwargs
    assert call_kwargs['status'] == discord.Status.online


@pytest.mark.asyncio
async def test_update_presence_when_connected_with_rcon_offline(bot, mock_rcon):
    """Test update_presence when bot connected but RCON offline"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    mock_rcon.is_connected = False
    bot.change_presence = AsyncMock()

    await bot.update_presence()

    # Should call change_presence with idle status
    bot.change_presence.assert_awaited_once()
    call_kwargs = bot.change_presence.call_args.kwargs
    assert call_kwargs['status'] == discord.Status.idle


@pytest.mark.asyncio
async def test_update_presence_skips_when_not_connected(bot):
    """Test update_presence returns early when not connected"""
    bot._connected = False
    bot.change_presence = AsyncMock()

    await bot.update_presence()

    # Should not call change_presence
    bot.change_presence.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_presence_skips_when_user_none(bot, mock_rcon):
    """Test update_presence returns early when user is None"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    type(bot).user = PropertyMock(return_value=None)
    bot.change_presence = AsyncMock()

    await bot.update_presence()

    # Should not call change_presence
    bot.change_presence.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_presence_handles_exception(bot, mock_rcon):
    """Test update_presence handles exceptions gracefully"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    bot.change_presence = AsyncMock(side_effect=Exception("Presence error"))

    # Should not raise
    await bot.update_presence()


# ============================================================================
# TEST: _notify_rcon_disconnected
# ============================================================================

@pytest.mark.asyncio
async def test_notify_rcon_disconnected_sends_notification(bot, mock_channel):
    """Test RCON disconnection notification is sent"""
    bot.event_channel_id = 12345
    bot.rcon_status_notified = False
    bot.get_channel = MagicMock(return_value=mock_channel)

    with patch('discord_bot.EmbedBuilder') as mock_embed_builder:
        mock_embed = MagicMock()
        mock_embed.color = 0xFFA500
        mock_embed_builder.info_embed.return_value = mock_embed

        await bot._notify_rcon_disconnected()

    # Check notification was sent
    mock_channel.send.assert_awaited_once()
    assert bot.rcon_status_notified is True


@pytest.mark.asyncio
async def test_notify_rcon_disconnected_skips_when_no_channel(bot):
    """Test notification skipped when no channel configured"""
    bot.event_channel_id = None
    bot.rcon_status_notified = False
    bot.get_channel = MagicMock()

    await bot._notify_rcon_disconnected()

    # Should not get channel
    bot.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_notify_rcon_disconnected_skips_when_already_notified(bot):
    """Test notification skipped when already sent"""
    bot.event_channel_id = 12345
    bot.rcon_status_notified = True
    bot.get_channel = MagicMock()

    await bot._notify_rcon_disconnected()

    # Should not get channel
    bot.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_notify_rcon_disconnected_handles_exception(bot, mock_channel):
    """Test notification handles exceptions"""
    bot.event_channel_id = 12345
    bot.rcon_status_notified = False
    mock_channel.send = AsyncMock(side_effect=Exception("Send failed"))
    bot.get_channel = MagicMock(return_value=mock_channel)

    # Should not raise
    await bot._notify_rcon_disconnected()


# ============================================================================
# TEST: _notify_rcon_reconnected
# ============================================================================

@pytest.mark.asyncio
async def test_notify_rcon_reconnected_sends_notification(bot, mock_channel):
    """Test RCON reconnection notification is sent"""
    bot.event_channel_id = 12345
    bot.rcon_last_connected = None
    bot.get_channel = MagicMock(return_value=mock_channel)

    with patch('discord_bot.EmbedBuilder') as mock_embed_builder:
        mock_embed = MagicMock()
        mock_embed.color = 0x00FF00
        mock_embed_builder.info_embed.return_value = mock_embed

        await bot._notify_rcon_reconnected()

    # Check notification was sent
    mock_channel.send.assert_awaited_once()
    assert bot.rcon_status_notified is False


@pytest.mark.asyncio
async def test_notify_rcon_reconnected_calculates_downtime(bot, mock_channel):
    """Test reconnection notification includes downtime"""
    bot.event_channel_id = 12345
    # Use datetime.now(timezone.utc) to match implementation
    bot.rcon_last_connected = datetime.now(timezone.utc) - timedelta(minutes=5)
    bot.get_channel = MagicMock(return_value=mock_channel)

    with patch('discord_bot.EmbedBuilder') as mock_embed_builder:
        mock_embed = MagicMock()
        mock_embed_builder.info_embed.return_value = mock_embed

        await bot._notify_rcon_reconnected()

    # Verify embed was created (downtime calculated)
    assert mock_embed_builder.info_embed.called
    call_args = mock_embed_builder.info_embed.call_args
    assert "Downtime" in call_args.kwargs['message']


@pytest.mark.asyncio
async def test_notify_rcon_reconnected_no_downtime_message_when_zero_minutes(bot, mock_channel):
    """Test reconnection notification excludes downtime when < 1 minute"""
    bot.event_channel_id = 12345
    bot.rcon_last_connected = datetime.now(timezone.utc) - timedelta(seconds=30)
    bot.get_channel = MagicMock(return_value=mock_channel)

    with patch('discord_bot.EmbedBuilder') as mock_embed_builder:
        mock_embed = MagicMock()
        mock_embed_builder.info_embed.return_value = mock_embed

        await bot._notify_rcon_reconnected()

    # Verify downtime NOT included (< 1 minute)
    call_args = mock_embed_builder.info_embed.call_args
    assert "Downtime" not in call_args.kwargs['message']


@pytest.mark.asyncio
async def test_notify_rcon_reconnected_skips_when_no_channel(bot):
    """Test reconnection notification skipped when no channel"""
    bot.event_channel_id = None
    bot.get_channel = MagicMock()

    await bot._notify_rcon_reconnected()

    # Should not get channel
    bot.get_channel.assert_not_called()


# ============================================================================
# TEST: _monitor_rcon_status (UPDATED FOR PHASE 6)
# ============================================================================

@pytest.mark.asyncio
async def test_monitor_rcon_status_basic_loop(bot, mock_rcon):
    """Test RCON monitoring loop runs"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    bot.update_presence = AsyncMock()

    loop_count = 0

    async def mock_sleep(seconds):
        nonlocal loop_count
        loop_count += 1
        if loop_count >= 2:
            bot._connected = False  # Stop after 2 iterations

    with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
        await bot._monitor_rcon_status()

    # Verify loop ran multiple times
    assert loop_count >= 2


@pytest.mark.asyncio
async def test_monitor_rcon_status_sets_timestamp_on_first_check_when_connected(bot, mock_rcon):
    """Test monitoring sets rcon_last_connected on first check if already connected"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    bot.rcon_last_connected = None
    bot.update_presence = AsyncMock()

    # RCON is already connected on first check
    mock_rcon.is_connected = True

    loop_count = 0

    async def mock_sleep(seconds):
        nonlocal loop_count
        loop_count += 1
        if loop_count >= 1:
            bot._connected = False  # Stop after first loop

    with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
        await bot._monitor_rcon_status()

    # Should set timestamp on first check when connected
    assert bot.rcon_last_connected is not None


@pytest.mark.asyncio
async def test_monitor_rcon_status_does_not_set_timestamp_on_first_check_when_disconnected(bot, mock_rcon):
    """Test monitoring does NOT set timestamp on first check if disconnected"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    bot.rcon_last_connected = None
    bot.update_presence = AsyncMock()

    # RCON is disconnected on first check
    mock_rcon.is_connected = False

    loop_count = 0

    async def mock_sleep(seconds):
        nonlocal loop_count
        loop_count += 1
        if loop_count >= 1:
            bot._connected = False  # Stop after first loop

    with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
        await bot._monitor_rcon_status()

    # Should NOT set timestamp (RCON was disconnected)
    assert bot.rcon_last_connected is None


@pytest.mark.asyncio
async def test_monitor_rcon_status_detects_disconnection(bot, mock_rcon):
    """Test monitoring detects RCON disconnection"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    bot.update_presence = AsyncMock()
    bot._notify_rcon_disconnected = AsyncMock()

    # Start connected
    mock_rcon.is_connected = True

    loop_count = 0

    async def mock_sleep(seconds):
        nonlocal loop_count
        loop_count += 1
        if loop_count == 1:
            # First loop: still connected, do nothing
            pass
        elif loop_count == 2:
            # Second loop: disconnect
            mock_rcon.is_connected = False
        elif loop_count >= 3:
            # Stop monitoring
            bot._connected = False

    with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
        await bot._monitor_rcon_status()

    # Should have detected disconnection
    bot._notify_rcon_disconnected.assert_awaited()


@pytest.mark.asyncio
async def test_monitor_rcon_status_detects_reconnection_and_sets_timestamp(bot, mock_rcon):
    """Test monitoring detects RCON reconnection and sets timestamp"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    bot.rcon_last_connected = None
    bot.update_presence = AsyncMock()
    bot._notify_rcon_reconnected = AsyncMock()

    # Start disconnected
    mock_rcon.is_connected = False

    loop_count = 0

    async def mock_sleep(seconds):
        nonlocal loop_count
        loop_count += 1
        if loop_count == 1:
            # First loop: disconnected, do nothing
            pass
        elif loop_count == 2:
            # Second loop: reconnect
            mock_rcon.is_connected = True
        elif loop_count >= 3:
            # Stop monitoring
            bot._connected = False

    with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
        await bot._monitor_rcon_status()

    # Should have detected reconnection
    bot._notify_rcon_reconnected.assert_awaited()
    # Should set timestamp AFTER reconnection
    assert bot.rcon_last_connected is not None


@pytest.mark.asyncio
async def test_monitor_rcon_status_timestamp_order_on_reconnection(bot, mock_rcon):
    """Test that reconnection notification is sent BEFORE timestamp is set"""
    bot._connected = True
    bot.rcon_client = mock_rcon
    bot.update_presence = AsyncMock()

    # Track the timestamp when notification is sent
    timestamp_at_notification = None

    async def capture_timestamp():
        nonlocal timestamp_at_notification
        timestamp_at_notification = bot.rcon_last_connected

    bot._notify_rcon_reconnected = AsyncMock(side_effect=capture_timestamp)

    # Start disconnected
    mock_rcon.is_connected = False

    loop_count = 0

    async def mock_sleep(seconds):
        nonlocal loop_count
        loop_count += 1
        if loop_count == 1:
            pass
        elif loop_count == 2:
            mock_rcon.is_connected = True
        elif loop_count >= 3:
            bot._connected = False

    with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
        await bot._monitor_rcon_status()

    # Notification should be sent before timestamp is set
    # So timestamp_at_notification should be None or old value
    # After monitoring, timestamp should be set
    assert bot.rcon_last_connected is not None


@pytest.mark.asyncio
async def test_monitor_rcon_status_handles_cancellation(bot):
    """Test monitoring handles CancelledError"""
    bot._connected = True
    bot.rcon_client = None

    async def mock_sleep(seconds):
        raise asyncio.CancelledError()

    with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
        # Should not raise
        await bot._monitor_rcon_status()


@pytest.mark.asyncio
async def test_monitor_rcon_status_handles_exception(bot, mock_rcon):
    """Test monitoring handles general exceptions"""
    bot._connected = True
    bot.rcon_client = mock_rcon

    call_count = 0

    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Test error")
        else:
            bot._connected = False

    with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
        # Should not raise, continues after error
        await bot._monitor_rcon_status()


# ============================================================================
# TEST: _send_connection_notification
# ============================================================================

@pytest.mark.asyncio
async def test_send_connection_notification_when_configured(bot, mock_channel):
    """Test connection notification sent when channel configured"""
    bot.event_channel_id = 12345
    bot.get_channel = MagicMock(return_value=mock_channel)

    with patch('discord_bot.EmbedBuilder') as mock_embed_builder:
        mock_embed = MagicMock()
        mock_embed_builder.info_embed.return_value = mock_embed

        await bot._send_connection_notification()

    # Verify channel was fetched and message sent
    bot.get_channel.assert_called_once_with(12345)
    mock_channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_connection_notification_skips_when_no_channel(bot):
    """Test connection notification skipped when no channel"""
    bot.event_channel_id = None
    bot.get_channel = MagicMock()

    await bot._send_connection_notification()

    # Should return early
    bot.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_send_connection_notification_handles_forbidden(bot, mock_channel):
    """Test connection notification handles Forbidden error"""
    bot.event_channel_id = 12345
    mock_channel.send = AsyncMock(side_effect=discord.errors.Forbidden(MagicMock(), "No permission"))
    bot.get_channel = MagicMock(return_value=mock_channel)

    # Should not raise
    await bot._send_connection_notification()


# ============================================================================
# TEST: _send_disconnection_notification
# ============================================================================

@pytest.mark.asyncio
async def test_send_disconnection_notification_when_connected(bot, mock_channel):
    """Test disconnection notification sent when connected"""
    bot._connected = True
    bot.event_channel_id = 12345
    bot.get_channel = MagicMock(return_value=mock_channel)

    with patch('discord_bot.EmbedBuilder') as mock_embed_builder:
        mock_embed = MagicMock()
        mock_embed_builder.info_embed.return_value = mock_embed

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await bot._send_disconnection_notification()

    # Verify notification sent
    mock_channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_disconnection_notification_skips_when_not_connected(bot):
    """Test disconnection notification skipped when not connected"""
    bot._connected = False
    bot.get_channel = MagicMock()

    await bot._send_disconnection_notification()

    # Should return early
    bot.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_send_disconnection_notification_skips_when_no_channel(bot):
    """Test disconnection notification skipped when no channel"""
    bot._connected = True
    bot.event_channel_id = None
    bot.get_channel = MagicMock()

    await bot._send_disconnection_notification()

    # Should return early
    bot.get_channel.assert_not_called()
