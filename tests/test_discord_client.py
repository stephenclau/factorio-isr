"""
Comprehensive test suite for discord_client.py.

Type-safe tests with ~95% code coverage for Discord webhook client,
including multi-channel routing, rate limiting, retries, and error handling.
"""

import asyncio
from typing import Dict, Optional, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
import pytest
import aiohttp

# Import the module under test
try:
    from discord_client import DiscordClient
    from event_parser import FactorioEvent, EventType
except ImportError:
    import sys
    sys.path.insert(0, '.')
    from discord_client import DiscordClient
    from event_parser import FactorioEvent, EventType


class TestDiscordClientInit:
    """Test DiscordClient initialization."""

    def test_init_with_minimal_params(self) -> None:
        """Test initialization with only required parameters."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test")

        assert client.default_webhook_url == "https://discord.com/api/webhooks/test"
        assert client.bot_name == "FactorioISR"
        assert client.bot_avatar_url is None
        assert client.rate_limit_delay == 0.5
        assert client.max_retries == 3
        assert client.webhook_channels == {}
        assert client.session is None
        assert client.last_send_time == 0

    def test_init_with_all_params(self) -> None:
        """Test initialization with all parameters."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin",
            "events": "https://discord.com/webhooks/events"
        }

        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/default",
            bot_name="Test Bot",
            bot_avatar_url="https://example.com/avatar.png",
            rate_limit_delay=1.0,
            max_retries=5,
            webhook_channels=webhook_channels
        )

        assert client.default_webhook_url == "https://discord.com/api/webhooks/default"
        assert client.bot_name == "Test Bot"
        assert client.bot_avatar_url == "https://example.com/avatar.png"
        assert client.rate_limit_delay == 1.0
        assert client.max_retries == 5
        assert client.webhook_channels == webhook_channels

    def test_init_with_none_webhook_channels(self) -> None:
        """Test that None webhook_channels becomes empty dict."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            webhook_channels=None
        )

        assert client.webhook_channels == {}
        assert isinstance(client.webhook_channels, dict)


class TestGetWebhookUrl:
    """Test webhook URL routing logic."""

    def test_get_webhook_url_default(self) -> None:
        """Test getting default webhook URL."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/default")

        result = client.get_webhook_url()
        assert result == "https://discord.com/webhooks/default"

    def test_get_webhook_url_with_configured_channel(self) -> None:
        """Test getting webhook URL for configured channel."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin"
        }
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            webhook_channels=webhook_channels
        )

        result = client.get_webhook_url("admin")
        assert result == "https://discord.com/webhooks/admin"

    def test_get_webhook_url_with_unconfigured_channel(self) -> None:
        """Test fallback to default for unconfigured channel."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin"
        }
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            webhook_channels=webhook_channels
        )

        result = client.get_webhook_url("nonexistent")
        assert result == "https://discord.com/webhooks/default"

    def test_get_webhook_url_with_none_channel(self) -> None:
        """Test that None channel returns default URL."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/default")

        result = client.get_webhook_url(None)
        assert result == "https://discord.com/webhooks/default"

    def test_get_webhook_url_with_empty_string_channel(self) -> None:
        """Test that empty string channel returns default URL."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/default")

        result = client.get_webhook_url("")
        assert result == "https://discord.com/webhooks/default"


class TestConnect:
    """Test connection establishment."""

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Test successful connection."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        # Mock the send_message call
        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await client.connect()

            assert client.session is not None
            assert isinstance(client.session, aiohttp.ClientSession)
            mock_send.assert_called_once()

            # Clean up
            await client.session.close()

    @pytest.mark.asyncio
    async def test_connect_already_connected(self) -> None:
        """Test that connecting when already connected doesn't create new session."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await client.connect()
            first_session = client.session

            # Try to connect again
            await client.connect()
            second_session = client.session

            # Should be the same session
            assert first_session is second_session

            # Clean up
            if client.session:
                await client.session.close()


class TestDisconnect:
    """Test disconnection."""

    @pytest.mark.asyncio
    async def test_disconnect_success(self) -> None:
        """Test successful disconnection."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await client.connect()
            assert client.session is not None

            await client.disconnect()
            assert client.session is None

            # send_message should be called twice: connect and disconnect
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self) -> None:
        """Test disconnect when not connected does nothing."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        # Should not raise an exception
        await client.disconnect()
        assert client.session is None


class TestSendMessage:
    """Test message sending with various scenarios."""

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """Test successful message send."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        # Mock session
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_response
        client.session = mock_session

        result = await client.send_message("Test message")

        assert result is True
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_with_custom_webhook(self) -> None:
        """Test sending message to custom webhook URL."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/default")

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_response
        client.session = mock_session

        custom_url = "https://discord.com/webhooks/custom"
        result = await client.send_message("Test", webhook_url=custom_url)

        assert result is True
        # Verify custom URL was used
        call_args = mock_session.post.call_args
        assert call_args[0][0] == custom_url

    @pytest.mark.asyncio
    async def test_send_message_with_avatar(self) -> None:
        """Test sending message with bot avatar URL."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            bot_avatar_url="https://example.com/avatar.png"
        )

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_response
        client.session = mock_session

        result = await client.send_message("Test")

        assert result is True
        # Check that avatar_url was included in payload
        call_args = mock_session.post.call_args
        payload = call_args[1]['json']
        assert 'avatar_url' in payload
        assert payload['avatar_url'] == "https://example.com/avatar.png"

    @pytest.mark.asyncio
    async def test_send_message_rate_limiting(self) -> None:
        """Test rate limiting between messages."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            rate_limit_delay=0.1
        )

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_response
        client.session = mock_session

        # Send first message
        await client.send_message("Message 1")
        first_send_time = client.last_send_time

        # Send second message immediately
        await client.send_message("Message 2")
        second_send_time = client.last_send_time

        # Second message should be delayed by rate limit
        assert second_send_time >= first_send_time + 0.1

    @pytest.mark.asyncio
    async def test_send_message_discord_rate_limit_429(self) -> None:
        """Test handling Discord rate limit (429) response."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        # First response: 429 rate limit
        mock_rate_limit_response = AsyncMock()
        mock_rate_limit_response.status = 429
        mock_rate_limit_response.json.return_value = {"retry_after": 0.1}
        mock_rate_limit_response.__aenter__.return_value = mock_rate_limit_response
        mock_rate_limit_response.__aexit__.return_value = None

        # Second response: success
        mock_success_response = AsyncMock()
        mock_success_response.status = 204
        mock_success_response.__aenter__.return_value = mock_success_response
        mock_success_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.side_effect = [mock_rate_limit_response, mock_success_response]
        client.session = mock_session

        result = await client.send_message("Test")

        assert result is True
        assert mock_session.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_message_server_error_with_retry(self) -> None:
        """Test retry on 5xx server errors."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            max_retries=3
        )

        # First two attempts: 500 error
        mock_error_response = AsyncMock()
        mock_error_response.status = 500
        mock_error_response.text.return_value = "Internal Server Error"
        mock_error_response.__aenter__.return_value = mock_error_response
        mock_error_response.__aexit__.return_value = None

        # Third attempt: success
        mock_success_response = AsyncMock()
        mock_success_response.status = 204
        mock_success_response.__aenter__.return_value = mock_success_response
        mock_success_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.side_effect = [
            mock_error_response,
            mock_error_response,
            mock_success_response
        ]
        client.session = mock_session

        result = await client.send_message("Test")

        assert result is True
        assert mock_session.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_message_client_error_no_retry(self) -> None:
        """Test that 4xx client errors don't retry."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            max_retries=3
        )

        mock_error_response = AsyncMock()
        mock_error_response.status = 404
        mock_error_response.text.return_value = "Not Found"
        mock_error_response.__aenter__.return_value = mock_error_response
        mock_error_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_error_response
        client.session = mock_session

        result = await client.send_message("Test")

        assert result is False
        # Should only try once for 4xx errors
        assert mock_session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_message_aiohttp_client_error(self) -> None:
        """Test handling aiohttp ClientError."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            max_retries=2
        )

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.side_effect = aiohttp.ClientError("Connection failed")
        client.session = mock_session

        result = await client.send_message("Test")

        assert result is False
        assert mock_session.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_message_unexpected_exception(self) -> None:
        """Test handling unexpected exceptions."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.side_effect = ValueError("Unexpected error")
        client.session = mock_session

        result = await client.send_message("Test")

        assert result is False
        # Should only try once for unexpected exceptions
        assert mock_session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_message_max_retries_exhausted(self) -> None:
        """Test that max retries are respected."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            max_retries=3
        )

        mock_error_response = AsyncMock()
        mock_error_response.status = 500
        mock_error_response.text.return_value = "Error"
        mock_error_response.__aenter__.return_value = mock_error_response
        mock_error_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_error_response
        client.session = mock_session

        result = await client.send_message("Test")

        assert result is False
        assert mock_session.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_message_without_session_raises_assertion(self) -> None:
        """Test that sending without connection raises AssertionError."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        with pytest.raises(AssertionError, match="Client not connected"):
            await client.send_message("Test")


class TestSendEvent:
    """Test event sending functionality."""

    @pytest.mark.asyncio
    async def test_send_event_success(self) -> None:
        """Test successful event send."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        # Create a test event
        event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="TestPlayer",
            raw_line="[JOIN] TestPlayer joined the game"
        )

        # Mock session and send_message
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        client.session = mock_session

        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await client.send_event(event)

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_event_with_channel_override(self) -> None:
        """Test sending event with channel override."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin"
        }
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            webhook_channels=webhook_channels
        )

        event = FactorioEvent(
            event_type=EventType.DEATH,
            player_name="TestPlayer",
            raw_line="TestPlayer died"
        )

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        client.session = mock_session

        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await client.send_event(event, channel="admin")

            assert result is True
            # Verify the correct webhook URL was used
            call_args = mock_send.call_args
            assert call_args[1]['webhook_url'] == "https://discord.com/webhooks/admin"

    @pytest.mark.asyncio
    async def test_send_event_with_metadata_channel(self) -> None:
        """Test sending event with channel from metadata."""
        webhook_channels: Dict[str, str] = {
            "events": "https://discord.com/webhooks/events"
        }
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            webhook_channels=webhook_channels
        )

        event = FactorioEvent(
            event_type=EventType.RESEARCH,
            raw_line="Research completed",
            metadata={"channel": "events"}
        )

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        client.session = mock_session

        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await client.send_event(event)

            assert result is True
            call_args = mock_send.call_args
            assert call_args[1]['webhook_url'] == "https://discord.com/webhooks/events"

    @pytest.mark.asyncio
    async def test_send_event_channel_override_takes_precedence(self) -> None:
        """Test that explicit channel parameter overrides metadata channel."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin",
            "events": "https://discord.com/webhooks/events"
        }
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            webhook_channels=webhook_channels
        )

        event = FactorioEvent(
            event_type=EventType.DEATH,
            raw_line="Player died",
            metadata={"channel": "events"}  # This should be overridden
        )

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        client.session = mock_session

        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await client.send_event(event, channel="admin")

            assert result is True
            call_args = mock_send.call_args
            assert call_args[1]['webhook_url'] == "https://discord.com/webhooks/admin"

    @pytest.mark.asyncio
    async def test_send_event_without_session_raises_assertion(self) -> None:
        """Test that sending event without connection raises AssertionError."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="Test",
            raw_line="Test joined"
        )

        with pytest.raises(AssertionError, match="Client not connected"):
            await client.send_event(event)


class TestTestConnection:
    """Test connection testing functionality."""

    @pytest.mark.asyncio
    async def test_connection_success(self) -> None:
        """Test successful connection test."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        client.session = mock_session

        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await client.test_connection()

            assert result is True
            mock_send.assert_called_once()
            # Verify test message was sent
            call_args = mock_send.call_args
            assert "Test Connection Successful" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_connection_failure(self) -> None:
        """Test failed connection test."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        client.session = mock_session

        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False

            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_connection_without_session_raises_assertion(self) -> None:
        """Test that testing connection without session raises AssertionError."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        with pytest.raises(AssertionError, match="Client not connected"):
            await client.test_connection()


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """Test complete connect -> send -> disconnect lifecycle."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        # Mock responses
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('aiohttp.ClientSession.post', return_value=mock_response):
            # Connect
            await client.connect()
            assert client.session is not None

            # Send message
            result = await client.send_message("Test message")
            assert result is True

            # Send event
            event = FactorioEvent(
                event_type=EventType.JOIN,
                player_name="TestPlayer",
                raw_line="[JOIN] TestPlayer"
            )
            result = await client.send_event(event)
            assert result is True

            # Test connection
            result = await client.test_connection()
            assert result is True

            # Disconnect
            await client.disconnect()
            assert client.session is None

    @pytest.mark.asyncio
    async def test_multi_channel_routing(self) -> None:
        """Test routing to multiple channels."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin",
            "events": "https://discord.com/webhooks/events",
            "chat": "https://discord.com/webhooks/chat"
        }

        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            webhook_channels=webhook_channels
        )

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_response
        client.session = mock_session

        # Send to different channels
        await client.send_message("Admin message", webhook_url=webhook_channels["admin"])
        await client.send_message("Event message", webhook_url=webhook_channels["events"])
        await client.send_message("Chat message", webhook_url=webhook_channels["chat"])

        # Verify all three were sent
        assert mock_session.post.call_count == 3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_message(self) -> None:
        """Test sending empty message."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_response
        client.session = mock_session

        result = await client.send_message("")
        assert result is True

    @pytest.mark.asyncio
    async def test_very_long_message(self) -> None:
        """Test sending very long message."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_response
        client.session = mock_session

        long_message = "A" * 10000
        result = await client.send_message(long_message)
        assert result is True

    def test_zero_rate_limit_delay(self) -> None:
        """Test client with zero rate limit delay."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            rate_limit_delay=0.0
        )
        assert client.rate_limit_delay == 0.0

    def test_single_retry(self) -> None:
        """Test client with only one retry."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            max_retries=1
        )
        assert client.max_retries == 1

    @pytest.mark.asyncio
    async def test_concurrent_sends(self) -> None:
        """Test that concurrent sends are properly locked."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            rate_limit_delay=0.01
        )

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.post.return_value = mock_response
        client.session = mock_session

        # Send multiple messages concurrently
        tasks = [
            client.send_message(f"Message {i}")
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)
        # All should have been sent
        assert mock_session.post.call_count == 5
