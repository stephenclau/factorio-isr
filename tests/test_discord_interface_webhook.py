"""
Pytest test suite for discord_interface.py - WebhookDiscordInterface coverage

Tests WebhookDiscordInterface class (Phase 1-3 webhook mode) for:
- Initialization with DiscordClient
- Connection lifecycle
- send_event method
- send_message method
- test_connection method
- is_connected property

This is the FINAL test file completing the 7-file test suite!
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
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
discord_mock.Activity = MagicMock
discord_mock.ActivityType = MagicMock()
discord_mock.ActivityType.watching = "watching"
sys.modules['discord'] = discord_mock

from discord_interface import WebhookDiscordInterface

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_discord_client():
    """Mock DiscordClient for testing WebhookDiscordInterface."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.send_event = AsyncMock(return_value=True)
    client.send_message = AsyncMock(return_value=True)
    client.test_connection = AsyncMock(return_value=True)
    return client

@pytest.fixture
def webhook_interface(mock_discord_client):
    """Create WebhookDiscordInterface instance."""
    return WebhookDiscordInterface(mock_discord_client)

# ============================================================================
# TEST: WebhookDiscordInterface Initialization
# ============================================================================

class TestWebhookDiscordInterfaceInit:
    """Test WebhookDiscordInterface initialization."""

    def test_init_with_client(self, mock_discord_client):
        """Test initialization with DiscordClient."""
        interface = WebhookDiscordInterface(mock_discord_client)

        assert interface.client is mock_discord_client
        assert interface._connected is False

    def test_init_sets_not_connected(self, mock_discord_client):
        """Test that _connected is False on init."""
        interface = WebhookDiscordInterface(mock_discord_client)

        assert interface.is_connected is False

    def test_init_stores_client_reference(self, webhook_interface, mock_discord_client):
        """Test that client reference is stored correctly."""
        assert webhook_interface.client is mock_discord_client

# ============================================================================
# TEST: Connection Lifecycle
# ============================================================================

class TestWebhookInterfaceConnection:
    """Test connection and disconnection."""

    @pytest.mark.asyncio
    async def test_connect(self, webhook_interface, mock_discord_client):
        """Test connecting webhook interface."""
        await webhook_interface.connect()

        # Should call client.connect()
        mock_discord_client.connect.assert_awaited_once()

        # Should set connected flag
        assert webhook_interface.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, webhook_interface, mock_discord_client):
        """Test disconnecting webhook interface."""
        # First connect
        await webhook_interface.connect()
        assert webhook_interface.is_connected is True

        # Then disconnect
        await webhook_interface.disconnect()

        # Should call client.disconnect()
        mock_discord_client.disconnect.assert_awaited_once()

        # Should clear connected flag
        assert webhook_interface.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_when_already_connected(self, webhook_interface, mock_discord_client):
        """Test connect when already connected."""
        await webhook_interface.connect()
        await webhook_interface.connect()

        # Should call connect twice
        assert mock_discord_client.connect.await_count == 2

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, webhook_interface, mock_discord_client):
        """Test disconnect when not connected."""
        assert webhook_interface.is_connected is False

        await webhook_interface.disconnect()

        # Should still call disconnect
        mock_discord_client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_connected_property(self, webhook_interface):
        """Test is_connected property reflects state."""
        assert webhook_interface.is_connected is False

        await webhook_interface.connect()
        assert webhook_interface.is_connected is True

        await webhook_interface.disconnect()
        assert webhook_interface.is_connected is False

# ============================================================================
# TEST: send_event
# ============================================================================

class TestWebhookInterfaceSendEvent:
    """Test send_event functionality."""

    @pytest.mark.asyncio
    async def test_send_event_success(self, webhook_interface, mock_discord_client):
        """Test successful event sending."""
        mock_event = MagicMock()
        mock_discord_client.send_event.return_value = True

        result = await webhook_interface.send_event(mock_event)

        assert result is True
        mock_discord_client.send_event.assert_awaited_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_send_event_failure(self, webhook_interface, mock_discord_client):
        """Test event sending failure."""
        mock_event = MagicMock()
        mock_discord_client.send_event.return_value = False

        result = await webhook_interface.send_event(mock_event)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_event_with_none(self, webhook_interface, mock_discord_client):
        """Test sending None as event."""
        result = await webhook_interface.send_event(None)

        mock_discord_client.send_event.assert_awaited_once_with(None)

    @pytest.mark.asyncio
    async def test_send_event_exception(self, webhook_interface, mock_discord_client):
        """Test send_event when client raises exception."""
        mock_event = MagicMock()
        mock_discord_client.send_event.side_effect = Exception("Send failed")

        # Should propagate exception
        with pytest.raises(Exception, match="Send failed"):
            await webhook_interface.send_event(mock_event)

# ============================================================================
# TEST: send_message
# ============================================================================

class TestWebhookInterfaceSendMessage:
    """Test send_message functionality."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, webhook_interface, mock_discord_client):
        """Test successful message sending."""
        mock_discord_client.send_message.return_value = True

        result = await webhook_interface.send_message("Test message")

        assert result is True
        mock_discord_client.send_message.assert_awaited_once_with(
            "Test message", username=None
        )

    @pytest.mark.asyncio
    async def test_send_message_with_username(self, webhook_interface, mock_discord_client):
        """Test sending message with custom username."""
        mock_discord_client.send_message.return_value = True

        result = await webhook_interface.send_message(
            "Test message", username="CustomBot"
        )

        assert result is True
        mock_discord_client.send_message.assert_awaited_once_with(
            "Test message", username="CustomBot"
        )

    @pytest.mark.asyncio
    async def test_send_message_failure(self, webhook_interface, mock_discord_client):
        """Test message sending failure."""
        mock_discord_client.send_message.return_value = False

        result = await webhook_interface.send_message("Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_empty_string(self, webhook_interface, mock_discord_client):
        """Test sending empty message."""
        mock_discord_client.send_message.return_value = True

        result = await webhook_interface.send_message("")

        assert result is True
        mock_discord_client.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_very_long(self, webhook_interface, mock_discord_client):
        """Test sending very long message."""
        long_message = "A" * 10000
        mock_discord_client.send_message.return_value = True

        result = await webhook_interface.send_message(long_message)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_special_characters(self, webhook_interface, mock_discord_client):
        """Test sending message with special characters."""
        message = 'Message with "quotes" and \backslashes'
        mock_discord_client.send_message.return_value = True

        result = await webhook_interface.send_message(message)

        assert result is True

# ============================================================================
# TEST: test_connection
# ============================================================================

class TestWebhookInterfaceTestConnection:
    """Test test_connection functionality."""

    @pytest.mark.asyncio
    async def test_connection_success(self, webhook_interface, mock_discord_client):
        """Test successful connection test."""
        mock_discord_client.test_connection.return_value = True

        result = await webhook_interface.test_connection()

        assert result is True
        mock_discord_client.test_connection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connection_failure(self, webhook_interface, mock_discord_client):
        """Test failed connection test."""
        mock_discord_client.test_connection.return_value = False

        result = await webhook_interface.test_connection()

        assert result is False

    @pytest.mark.asyncio
    async def test_connection_exception(self, webhook_interface, mock_discord_client):
        """Test connection test with exception."""
        mock_discord_client.test_connection.side_effect = Exception("Connection error")

        # Should propagate exception
        with pytest.raises(Exception, match="Connection error"):
            await webhook_interface.test_connection()

    @pytest.mark.asyncio
    async def test_connection_when_connected(self, webhook_interface, mock_discord_client):
        """Test connection test when already connected."""
        await webhook_interface.connect()

        mock_discord_client.test_connection.return_value = True
        result = await webhook_interface.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_connection_when_disconnected(self, webhook_interface, mock_discord_client):
        """Test connection test when disconnected."""
        assert webhook_interface.is_connected is False

        mock_discord_client.test_connection.return_value = True
        result = await webhook_interface.test_connection()

        assert result is True

# ============================================================================
# TEST: Integration Scenarios
# ============================================================================

class TestWebhookInterfaceIntegration:
    """Test integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, webhook_interface, mock_discord_client):
        """Test complete connect -> send -> disconnect lifecycle."""
        # Connect
        await webhook_interface.connect()
        assert webhook_interface.is_connected

        # Send event
        event = MagicMock()
        result = await webhook_interface.send_event(event)
        assert result is True

        # Send message
        result = await webhook_interface.send_message("Test")
        assert result is True

        # Test connection
        result = await webhook_interface.test_connection()
        assert result is True

        # Disconnect
        await webhook_interface.disconnect()
        assert not webhook_interface.is_connected

    @pytest.mark.asyncio
    async def test_multiple_sends(self, webhook_interface, mock_discord_client):
        """Test sending multiple messages and events."""
        await webhook_interface.connect()

        # Multiple messages
        for i in range(5):
            result = await webhook_interface.send_message(f"Message {i}")
            assert result is True

        # Multiple events
        for i in range(5):
            event = MagicMock()
            result = await webhook_interface.send_event(event)
            assert result is True

        assert mock_discord_client.send_message.await_count == 5
        assert mock_discord_client.send_event.await_count == 5

    @pytest.mark.asyncio
    async def test_send_without_connect(self, webhook_interface, mock_discord_client):
        """Test sending without explicit connect."""
        # Should still work (client handles connection internally)
        result = await webhook_interface.send_message("Test")
        assert result is True

    @pytest.mark.asyncio
    async def test_reconnect_after_disconnect(self, webhook_interface, mock_discord_client):
        """Test reconnecting after disconnect."""
        # First connection
        await webhook_interface.connect()
        await webhook_interface.disconnect()

        # Reconnect
        await webhook_interface.connect()
        assert webhook_interface.is_connected

        # Should work after reconnect
        result = await webhook_interface.send_message("After reconnect")
        assert result is True

    @pytest.mark.asyncio
    async def test_multiple_disconnects(self, webhook_interface, mock_discord_client):
        """Test multiple disconnect calls."""
        await webhook_interface.connect()

        await webhook_interface.disconnect()
        await webhook_interface.disconnect()
        await webhook_interface.disconnect()

        # Should call disconnect 3 times
        assert mock_discord_client.disconnect.await_count == 3

# ============================================================================
# TEST: Error Handling
# ============================================================================

class TestWebhookInterfaceErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_connect_failure(self, webhook_interface, mock_discord_client):
        """Test connect when client.connect() fails."""
        mock_discord_client.connect.side_effect = Exception("Connect failed")

        with pytest.raises(Exception, match="Connect failed"):
            await webhook_interface.connect()

        # Should not set connected flag on failure
        assert webhook_interface.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_failure(self, webhook_interface, mock_discord_client):
        """Test disconnect when client.disconnect() fails."""
        await webhook_interface.connect()

        mock_discord_client.disconnect.side_effect = Exception("Disconnect failed")

        with pytest.raises(Exception, match="Disconnect failed"):
            await webhook_interface.disconnect()

    @pytest.mark.asyncio
    async def test_send_event_client_none(self, mock_discord_client):
        """Test send_event when client is None."""
        interface = WebhookDiscordInterface(None)

        event = MagicMock()

        # Should raise AttributeError
        with pytest.raises(AttributeError):
            await interface.send_event(event)

    @pytest.mark.asyncio
    async def test_send_message_client_none(self, mock_discord_client):
        """Test send_message when client is None."""
        interface = WebhookDiscordInterface(None)

        # Should raise AttributeError
        with pytest.raises(AttributeError):
            await interface.send_message("Test")

# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestWebhookInterfaceEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_init_with_mock_client(self):
        """Test initialization with minimal mock."""
        minimal_client = MagicMock()
        interface = WebhookDiscordInterface(minimal_client)

        assert interface.client is minimal_client

    @pytest.mark.asyncio
    async def test_rapid_connect_disconnect(self, webhook_interface, mock_discord_client):
        """Test rapid connect/disconnect cycles."""
        for _ in range(10):
            await webhook_interface.connect()
            await webhook_interface.disconnect()

        assert mock_discord_client.connect.await_count == 10
        assert mock_discord_client.disconnect.await_count == 10

    @pytest.mark.asyncio
    async def test_send_event_with_complex_object(self, webhook_interface, mock_discord_client):
        """Test sending complex event object."""
        complex_event = {
            "type": "complex",
            "nested": {"data": [1, 2, 3]},
            "list": ["a", "b", "c"]
        }

        result = await webhook_interface.send_event(complex_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, webhook_interface, mock_discord_client):
        """Test concurrent send operations."""
        import asyncio

        await webhook_interface.connect()

        # Concurrent sends
        results = await asyncio.gather(
            webhook_interface.send_message("Msg 1"),
            webhook_interface.send_message("Msg 2"),
            webhook_interface.send_event(MagicMock()),
            webhook_interface.send_event(MagicMock())
        )

        assert all(results)

    @pytest.mark.asyncio
    async def test_is_connected_reflects_state_changes(self, webhook_interface):
        """Test is_connected accurately reflects state changes."""
        states = []

        states.append(webhook_interface.is_connected)  # False
        await webhook_interface.connect()
        states.append(webhook_interface.is_connected)  # True
        await webhook_interface.disconnect()
        states.append(webhook_interface.is_connected)  # False
        await webhook_interface.connect()
        states.append(webhook_interface.is_connected)  # True

        assert states == [False, True, False, True]
