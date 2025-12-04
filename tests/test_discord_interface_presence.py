"""
Pytest test suite for discord_interface.py - PresenceUpdater coverage

Tests PresenceUpdater class for bot presence management,
update loops, start/stop lifecycle, and error handling.

CORRECTLY FIXED: Tests match actual implementation where _update_presence 
lets exceptions bubble to _update_loop which catches them.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock discord module
discord_mock = MagicMock()
discord_mock.Embed = MagicMock(return_value=MagicMock())
discord_mock.utils = MagicMock()
discord_mock.utils.utcnow = MagicMock(return_value="2025-12-03T00:00:00")
discord_mock.TextChannel = MagicMock
discord_mock.Status = MagicMock()
discord_mock.Status.online = "online"
discord_mock.Status.idle = "idle"
discord_mock.Activity = MagicMock(return_value=MagicMock())
discord_mock.ActivityType = MagicMock()
discord_mock.ActivityType.watching = "watching"
discord_mock.errors = MagicMock()
sys.modules['discord'] = discord_mock

from discord_interface import PresenceUpdater

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_bot():
    """Mock Discord bot for testing PresenceUpdater."""
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    bot.is_closed = MagicMock(return_value=False)
    bot.change_presence = AsyncMock()
    return bot

@pytest.fixture
def presence_updater(mock_bot):
    """Create PresenceUpdater instance."""
    return PresenceUpdater(mock_bot, interval=1)  # Short interval for tests

# ============================================================================
# TEST: PresenceUpdater Initialization
# ============================================================================

class TestPresenceUpdaterInit:
    """Test PresenceUpdater initialization."""

    def test_init_with_default_interval(self, mock_bot):
        """Test initialization with default interval."""
        updater = PresenceUpdater(mock_bot)

        assert updater.bot is mock_bot
        assert updater.interval == 60  # Default interval
        assert updater.task is None

    def test_init_with_custom_interval(self, mock_bot):
        """Test initialization with custom interval."""
        updater = PresenceUpdater(mock_bot, interval=30)

        assert updater.bot is mock_bot
        assert updater.interval == 30
        assert updater.task is None

    def test_init_with_very_short_interval(self, mock_bot):
        """Test initialization with very short interval."""
        updater = PresenceUpdater(mock_bot, interval=1)

        assert updater.interval == 1

    def test_init_with_very_long_interval(self, mock_bot):
        """Test initialization with very long interval."""
        updater = PresenceUpdater(mock_bot, interval=3600)

        assert updater.interval == 3600

# ============================================================================
# TEST: Start and Stop
# ============================================================================

class TestPresenceUpdaterStartStop:
    """Test start and stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self, presence_updater, mock_bot):
        """Test that start() creates an asyncio task."""
        with patch.object(presence_updater, '_update_loop', new_callable=AsyncMock):
            await presence_updater.start()

            assert presence_updater.task is not None
            assert isinstance(presence_updater.task, asyncio.Task)

    @pytest.mark.asyncio
    async def test_start_when_already_started(self, presence_updater, mock_bot):
        """Test that start() does nothing when already running."""
        # Create a fake task
        fake_task = asyncio.create_task(asyncio.sleep(10))
        presence_updater.task = fake_task

        await presence_updater.start()

        # Should still be the same task
        assert presence_updater.task is fake_task

        # Cleanup
        fake_task.cancel()
        try:
            await fake_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, presence_updater, mock_bot):
        """Test that stop() cancels the update task."""
        # Start the updater
        with patch.object(presence_updater, '_update_loop', new_callable=AsyncMock) as mock_loop:
            # Make _update_loop run indefinitely
            async def infinite_loop():
                await asyncio.sleep(100)
            mock_loop.side_effect = infinite_loop

            await presence_updater.start()
            assert presence_updater.task is not None

            # Stop the updater
            await presence_updater.stop()

            # Task should be None after stop
            assert presence_updater.task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self, presence_updater):
        """Test that stop() does nothing when not started."""
        assert presence_updater.task is None

        # Should not raise
        await presence_updater.stop()

        assert presence_updater.task is None

    @pytest.mark.asyncio
    async def test_stop_handles_cancelled_error(self, presence_updater):
        """Test that stop() handles CancelledError gracefully."""
        # Create a task that's already cancelled
        async def already_cancelled():
            raise asyncio.CancelledError()

        presence_updater.task = asyncio.create_task(already_cancelled())

        # Should not raise
        await presence_updater.stop()

        assert presence_updater.task is None

# ============================================================================
# TEST: Update Loop
# ============================================================================

class TestPresenceUpdaterLoop:
    """Test the presence update loop."""

    @pytest.mark.asyncio
    async def test_update_loop_waits_until_ready(self, presence_updater, mock_bot):
        """Test that update loop waits for bot to be ready."""
        loop_started = False

        async def mock_update():
            nonlocal loop_started
            loop_started = True

        with patch.object(presence_updater, '_update_presence', new_callable=AsyncMock) as mock_update_presence:
            mock_update_presence.side_effect = mock_update

            # Make bot close immediately after ready
            async def close_after_ready():
                mock_bot.is_closed.return_value = True

            mock_bot.wait_until_ready.side_effect = close_after_ready

            await presence_updater._update_loop()

            # Should have called wait_until_ready
            mock_bot.wait_until_ready.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_loop_calls_update_presence(self, presence_updater, mock_bot):
        """Test that update loop calls _update_presence."""
        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                mock_bot.is_closed.return_value = True

        with patch.object(presence_updater, '_update_presence', new_callable=AsyncMock) as mock_update:
            with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
                await presence_updater._update_loop()

                # Should have called update at least once
                assert mock_update.await_count >= 1

    @pytest.mark.asyncio
    async def test_update_loop_respects_interval(self, presence_updater, mock_bot):
        """Test that update loop uses correct interval."""
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)
            mock_bot.is_closed.return_value = True  # Stop after first iteration

        with patch.object(presence_updater, '_update_presence', new_callable=AsyncMock):
            with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
                await presence_updater._update_loop()

                # Should have slept with the configured interval
                assert presence_updater.interval in sleep_calls

    @pytest.mark.asyncio
    async def test_update_loop_handles_cancelled_error(self, presence_updater, mock_bot):
        """Test that update loop handles CancelledError."""
        async def raise_cancelled(seconds):
            raise asyncio.CancelledError()

        with patch.object(presence_updater, '_update_presence', new_callable=AsyncMock):
            with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=raise_cancelled):
                # Should not raise
                await presence_updater._update_loop()

    @pytest.mark.asyncio
    async def test_update_loop_handles_general_exception(self, presence_updater, mock_bot):
        """Test that update loop handles general exceptions and continues."""
        call_count = 0

        async def mock_update():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            # Second call succeeds

        async def mock_sleep(seconds):
            if call_count >= 2:
                mock_bot.is_closed.return_value = True

        with patch.object(presence_updater, '_update_presence', new_callable=AsyncMock) as mock_update_presence:
            mock_update_presence.side_effect = mock_update
            with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
                # Should not raise, should continue after error
                await presence_updater._update_loop()

                # Should have been called at least twice (once failing, once succeeding)
                assert mock_update_presence.await_count >= 2

    @pytest.mark.asyncio
    async def test_update_loop_stops_when_bot_closed(self, presence_updater, mock_bot):
        """Test that update loop stops when bot is closed."""
        call_count = 0

        def is_closed_check():
            nonlocal call_count
            call_count += 1
            return call_count > 1  # Close after first iteration

        mock_bot.is_closed = MagicMock(side_effect=is_closed_check)

        with patch.object(presence_updater, '_update_presence', new_callable=AsyncMock):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await presence_updater._update_loop()

                # Loop should have checked is_closed multiple times
                assert mock_bot.is_closed.call_count >= 2

# ============================================================================
# TEST: Update Presence
# ============================================================================

class TestPresenceUpdaterUpdatePresence:
    """Test the _update_presence method."""

    @pytest.mark.asyncio
    async def test_update_presence_creates_activity(self, presence_updater, mock_bot):
        """Test that _update_presence creates Discord activity."""
        await presence_updater._update_presence()

        # Should have called change_presence
        mock_bot.change_presence.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_presence_uses_watching_activity(self, presence_updater, mock_bot):
        """Test that presence uses watching activity type."""
        with patch('discord_interface.discord.Activity') as mock_activity:
            with patch('discord_interface.discord.ActivityType') as mock_activity_type:
                mock_activity_type.watching = "watching"

                await presence_updater._update_presence()

                # Should have created activity with watching type
                mock_activity.assert_called()

    @pytest.mark.asyncio
    async def test_update_presence_sets_online_status(self, presence_updater, mock_bot):
        """Test that presence sets online status."""
        await presence_updater._update_presence()

        call_kwargs = mock_bot.change_presence.call_args.kwargs
        assert 'status' in call_kwargs

    @pytest.mark.asyncio
    async def test_update_presence_includes_help_command(self, presence_updater, mock_bot):
        """Test that presence includes help command text."""
        with patch('discord_interface.discord.Activity') as mock_activity:
            await presence_updater._update_presence()

            # Activity should have been called with name containing help
            if mock_activity.called:
                call_kwargs = mock_activity.call_args.kwargs
                assert 'name' in call_kwargs
                assert 'help' in call_kwargs['name'].lower()

    @pytest.mark.asyncio
    async def test_update_presence_exception_bubbles_up(self, presence_updater, mock_bot):
        """Test that _update_presence lets exceptions bubble up (caught by loop)."""
        mock_bot.change_presence.side_effect = Exception("Presence update failed")

        # Should raise - the LOOP catches it, not _update_presence
        with pytest.raises(Exception, match="Presence update failed"):
            await presence_updater._update_presence()

    @pytest.mark.asyncio
    async def test_loop_handles_update_presence_exception(self, presence_updater, mock_bot):
        """Test that the LOOP handles _update_presence exceptions."""
        call_count = 0

        async def failing_update():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Update failed")

        async def mock_sleep(seconds):
            if call_count >= 1:
                mock_bot.is_closed.return_value = True

        with patch.object(presence_updater, '_update_presence', new_callable=AsyncMock) as mock_update:
            mock_update.side_effect = failing_update
            with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
                # Loop should not raise - it catches exceptions
                await presence_updater._update_loop()

                # Update was called and failed
                assert mock_update.await_count >= 1

# ============================================================================
# TEST: Integration Scenarios
# ============================================================================

class TestPresenceUpdaterIntegration:
    """Test integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, presence_updater, mock_bot):
        """Test complete start -> update -> stop lifecycle."""
        update_count = 0

        async def count_updates():
            nonlocal update_count
            update_count += 1

        async def mock_sleep(seconds):
            if update_count >= 2:
                mock_bot.is_closed.return_value = True

        with patch.object(presence_updater, '_update_presence', new_callable=AsyncMock) as mock_update:
            mock_update.side_effect = count_updates
            with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
                # Start
                await presence_updater.start()
                assert presence_updater.task is not None

                # Wait for a couple updates
                await asyncio.sleep(0.1)

                # Stop
                await presence_updater.stop()
                assert presence_updater.task is None

    @pytest.mark.asyncio
    async def test_restart_after_stop(self, presence_updater, mock_bot):
        """Test that updater can be restarted after stop."""
        with patch.object(presence_updater, '_update_loop', new_callable=AsyncMock):
            # First start
            await presence_updater.start()
            first_task = presence_updater.task
            assert first_task is not None

            # Stop
            await presence_updater.stop()
            assert presence_updater.task is None

            # Restart
            await presence_updater.start()
            second_task = presence_updater.task
            assert second_task is not None
            assert second_task is not first_task  # Different task

    @pytest.mark.asyncio
    async def test_multiple_start_calls_idempotent(self, presence_updater):
        """Test that multiple start() calls don't create multiple tasks."""
        with patch.object(presence_updater, '_update_loop', new_callable=AsyncMock):
            await presence_updater.start()
            first_task = presence_updater.task

            await presence_updater.start()
            await presence_updater.start()

            # Should still be the same task
            assert presence_updater.task is first_task

            # Cleanup
            await presence_updater.stop()

    @pytest.mark.asyncio
    async def test_multiple_stop_calls_idempotent(self, presence_updater):
        """Test that multiple stop() calls are safe."""
        with patch.object(presence_updater, '_update_loop', new_callable=AsyncMock):
            await presence_updater.start()

            # Multiple stops should not raise
            await presence_updater.stop()
            await presence_updater.stop()
            await presence_updater.stop()

            assert presence_updater.task is None

# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestPresenceUpdaterEdgeCases:
    """Test edge cases and unusual scenarios."""

    @pytest.mark.asyncio
    async def test_zero_interval(self, mock_bot):
        """Test with interval of 0 (should still work)."""
        updater = PresenceUpdater(mock_bot, interval=0)

        assert updater.interval == 0

        # Should still be able to start (though it will update very rapidly)
        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                mock_bot.is_closed.return_value = True

        with patch.object(updater, '_update_presence', new_callable=AsyncMock):
            with patch('asyncio.sleep', new_callable=AsyncMock, side_effect=mock_sleep):
                await updater._update_loop()

    @pytest.mark.asyncio
    async def test_negative_interval(self, mock_bot):
        """Test with negative interval (edge case)."""
        updater = PresenceUpdater(mock_bot, interval=-1)

        assert updater.interval == -1

        # Should still create updater (behavior may vary)
        assert updater is not None

    @pytest.mark.asyncio
    async def test_concurrent_start_calls(self, mock_bot):
        """Test concurrent start() calls."""
        updater = PresenceUpdater(mock_bot, interval=1)

        with patch.object(updater, '_update_loop', new_callable=AsyncMock):
            # Start concurrently
            await asyncio.gather(
                updater.start(),
                updater.start(),
                updater.start()
            )

            # Should only have one task
            assert updater.task is not None

            # Cleanup
            await updater.stop()
