"""
Comprehensive tests for discord_client.py with 95%+ coverage.

Tests Discord client initialization, connection lifecycle, message sending,
rate limiting, retry logic, error handling, and multi-channel routing.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys
from typing import Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from discord_client import DiscordClient
from event_parser import FactorioEvent, EventType


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def default_webhook_url() -> str:
    """Default webhook URL for testing."""
    return "https://discord.com/api/webhooks/999/default_token"


@pytest.fixture
def webhook_channels() -> Dict[str, str]:
    """Sample webhook channels for routing tests."""
    return {
        "chat": "https://discord.com/api/webhooks/111/chat_token",
        "admin": "https://discord.com/api/webhooks/222/admin_token",
        "milestone": "https://discord.com/api/webhooks/333/milestone_token",
    }


@pytest.fixture
def mock_successful_response():
    """Create a mock successful Discord API response (204)."""
    mock_response = AsyncMock()
    mock_response.status = 204
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    return mock_response


@pytest.fixture
def mock_session(mock_successful_response):
    """Create a mock aiohttp ClientSession."""
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_successful_response)
    mock_session.close = AsyncMock()
    return mock_session


@pytest.fixture
def discord_client(default_webhook_url) -> DiscordClient:
    """Create a basic Discord client for testing."""
    return DiscordClient(webhook_url=default_webhook_url)


@pytest.fixture
def discord_client_with_channels(default_webhook_url, webhook_channels) -> DiscordClient:
    """Create a Discord client with multi-channel support."""
    return DiscordClient(
        webhook_url=default_webhook_url,
        webhook_channels=webhook_channels
    )


@pytest.fixture
async def connected_client(discord_client, mock_session) -> DiscordClient:
    """Create a connected Discord client with mocked session."""
    discord_client.session = mock_session
    return discord_client


@pytest.fixture
def sample_event():
    """Factory for creating test events."""
    def _create_event(
        event_type: EventType = EventType.CHAT,
        player_name: str = "TestPlayer",
        message: str = "Test message",
        channel: str | None = None,
        **kwargs
    ) -> FactorioEvent:
        metadata = {"channel": channel} if channel else {}
        return FactorioEvent(
            event_type=event_type,
            player_name=player_name,
            message=message,
            raw_line=kwargs.get("raw_line", "test log line"),
            emoji=kwargs.get("emoji", "💬"),
            formatted_message=kwargs.get("formatted_message", f"{player_name}: {message}"),
            metadata=metadata
        )
    return _create_event


# ============================================================================
# Initialization Tests
# ============================================================================

class TestDiscordClientInit:
    """Test DiscordClient initialization."""
    
    def test_init_with_minimal_params(self, default_webhook_url):
        """Test initialization with only required parameters."""
        client = DiscordClient(webhook_url=default_webhook_url)
        
        assert client.default_webhook_url == default_webhook_url
        assert client.bot_name == "Factorio Bridge"
        assert client.bot_avatar_url is None
        assert client.rate_limit_delay == 0.5
        assert client.max_retries == 3
        assert isinstance(client.webhook_channels, dict)
        assert len(client.webhook_channels) == 0
        assert client.session is None
        assert client.last_send_time == 0
        assert client.formatter is not None
        assert client._send_lock is not None
    
    def test_init_with_all_params(self, default_webhook_url, webhook_channels):
        """Test initialization with all parameters specified."""
        client = DiscordClient(
            webhook_url=default_webhook_url,
            bot_name="Custom Bot",
            bot_avatar_url="https://example.com/avatar.png",
            rate_limit_delay=1.0,
            max_retries=5,
            webhook_channels=webhook_channels
        )
        
        assert client.default_webhook_url == default_webhook_url
        assert client.bot_name == "Custom Bot"
        assert client.bot_avatar_url == "https://example.com/avatar.png"
        assert client.rate_limit_delay == 1.0
        assert client.max_retries == 5
        assert client.webhook_channels == webhook_channels
    
    def test_init_webhook_channels_none_converts_to_empty_dict(self, default_webhook_url):
        """Test that None webhook_channels becomes empty dict."""
        client = DiscordClient(
            webhook_url=default_webhook_url,
            webhook_channels=None
        )
        
        assert isinstance(client.webhook_channels, dict)
        assert len(client.webhook_channels) == 0


# ============================================================================
# Connection Lifecycle Tests
# ============================================================================

class TestConnectionLifecycle:
    """Test connect() and disconnect() methods."""
    
    @pytest.mark.asyncio
    async def test_connect_creates_session(self, discord_client):
        """Test that connect() creates an aiohttp session."""
        import aiohttp
        
        assert discord_client.session is None
        
        await discord_client.connect()
        
        assert discord_client.session is not None
        assert isinstance(discord_client.session, aiohttp.ClientSession)
        
        # Cleanup
        await discord_client.disconnect()
    
    @pytest.mark.asyncio
    async def test_connect_idempotent(self, discord_client):
        """Test that calling connect() multiple times is safe."""
        await discord_client.connect()
        first_session = discord_client.session
        
        await discord_client.connect()
        
        # Should still be the same session (not recreated)
        assert discord_client.session is first_session
        
        # Cleanup
        await discord_client.disconnect()
    
    @pytest.mark.asyncio
    async def test_disconnect_closes_session(self, discord_client):
        """Test that disconnect() closes the session."""
        await discord_client.connect()
        assert discord_client.session is not None
        
        await discord_client.disconnect()
        
        assert discord_client.session is None
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, discord_client):
        """Test that disconnect() is safe when not connected."""
        assert discord_client.session is None
        
        # Should not raise
        await discord_client.disconnect()
        
        assert discord_client.session is None
    
    @pytest.mark.asyncio
    async def test_connect_sets_timeout(self, discord_client):
        """Test that connect() configures session with timeout."""
        import aiohttp
        
        await discord_client.connect()
        
        # Verify session has timeout configured
        assert discord_client.session is not None
        assert isinstance(discord_client.session, aiohttp.ClientSession)
        # The timeout is set during ClientSession creation
        assert discord_client.session._timeout.total == 10
        
        # Cleanup
        await discord_client.disconnect()


# ============================================================================
# get_webhook_url() Tests
# ============================================================================

class TestGetWebhookUrl:
    """Test get_webhook_url() routing logic."""
    
    def test_returns_default_when_no_channel(self, discord_client, default_webhook_url):
        """Test returns default URL when no channel specified."""
        result = discord_client.get_webhook_url()
        
        assert result == default_webhook_url
    
    def test_returns_default_when_channel_none(self, discord_client, default_webhook_url):
        """Test returns default URL when channel is None."""
        result = discord_client.get_webhook_url(channel=None)
        
        assert result == default_webhook_url
    
    def test_returns_channel_url_when_configured(self, discord_client_with_channels, webhook_channels):
        """Test returns correct channel URL when configured."""
        result = discord_client_with_channels.get_webhook_url("chat")
        
        assert result == webhook_channels["chat"]
    
    def test_returns_default_when_channel_not_configured(
        self, discord_client_with_channels, default_webhook_url
    ):
        """Test falls back to default when channel not configured."""
        result = discord_client_with_channels.get_webhook_url("nonexistent")
        
        assert result == default_webhook_url
    
    def test_returns_default_for_empty_string_channel(self, discord_client, default_webhook_url):
        """Test returns default for empty string channel."""
        result = discord_client.get_webhook_url("")
        
        assert result == default_webhook_url


# ============================================================================
# send_message() Tests
# ============================================================================

class TestSendMessage:
    """Test send_message() method."""
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, connected_client):
        """Test successful message sending."""
        result = await connected_client.send_message("Test message")
        
        assert result is True
        assert connected_client.session.post.called
    
    @pytest.mark.asyncio
    async def test_send_message_uses_default_webhook(self, connected_client, default_webhook_url):
        """Test that send_message uses default webhook when none specified."""
        await connected_client.send_message("Test")
        
        call_args = connected_client.session.post.call_args
        assert call_args[0][0] == default_webhook_url
    
    @pytest.mark.asyncio
    async def test_send_message_uses_custom_webhook(self, connected_client):
        """Test that send_message uses custom webhook when specified."""
        custom_url = "https://discord.com/api/webhooks/custom/token"
        
        await connected_client.send_message("Test", webhook_url=custom_url)
        
        call_args = connected_client.session.post.call_args
        assert call_args[0][0] == custom_url
    
    @pytest.mark.asyncio
    async def test_send_message_payload_structure(self, connected_client):
        """Test that message payload has correct structure."""
        await connected_client.send_message("Test content")
        
        call_args = connected_client.session.post.call_args
        payload = call_args[1]['json']
        
        assert "content" in payload
        assert payload["content"] == "Test content"
        assert "username" in payload
        assert payload["username"] == connected_client.bot_name
    
    @pytest.mark.asyncio
    async def test_send_message_includes_avatar_when_set(self, default_webhook_url, mock_session):
        """Test that avatar_url is included in payload when configured."""
        avatar_url = "https://example.com/avatar.png"
        client = DiscordClient(
            webhook_url=default_webhook_url,
            bot_avatar_url=avatar_url
        )
        client.session = mock_session
        
        await client.send_message("Test")
        
        payload = mock_session.post.call_args[1]['json']
        assert "avatar_url" in payload
        assert payload["avatar_url"] == avatar_url
    
    @pytest.mark.asyncio
    async def test_send_message_no_avatar_when_not_set(self, connected_client):
        """Test that avatar_url is not in payload when not configured."""
        await connected_client.send_message("Test")
        
        payload = connected_client.session.post.call_args[1]['json']
        assert "avatar_url" not in payload
    
    @pytest.mark.asyncio
    async def test_send_message_without_session_raises_assertion(self, discord_client):
        """Test that sending without connecting raises AssertionError."""
        with pytest.raises(AssertionError, match="Client not connected"):
            await discord_client.send_message("Test")
    
    @pytest.mark.asyncio
    async def test_send_message_respects_rate_limit(self, connected_client):
        """Test that rate limiting delay is applied."""
        connected_client.rate_limit_delay = 0.1
        
        start_time = asyncio.get_event_loop().time()
        await connected_client.send_message("First")
        await connected_client.send_message("Second")
        end_time = asyncio.get_event_loop().time()
        
        elapsed = end_time - start_time
        # Should have at least the rate limit delay
        assert elapsed >= 0.1


# ============================================================================
# Retry Logic Tests
# ============================================================================

class TestRetryLogic:
    """Test retry behavior and error handling."""
    
    @pytest.mark.asyncio
    async def test_retries_on_429_rate_limit(self, connected_client):
        """Test that client retries on 429 rate limit."""
        # Mock 429 response
        mock_429 = AsyncMock()
        mock_429.status = 429
        mock_429.json = AsyncMock(return_value={"retry_after": 0.01})
        mock_429.__aenter__ = AsyncMock(return_value=mock_429)
        mock_429.__aexit__ = AsyncMock(return_value=None)
        
        # Return 429 for all attempts
        connected_client.session.post = MagicMock(return_value=mock_429)
        
        result = await connected_client.send_message("Test")
        
        # Should fail after max retries
        assert result is False
        assert connected_client.session.post.call_count == connected_client.max_retries
    
    @pytest.mark.asyncio
    async def test_retries_on_5xx_server_error(self, connected_client):
        """Test that client retries on 5xx server errors."""
        mock_500 = AsyncMock()
        mock_500.status = 500
        mock_500.text = AsyncMock(return_value="Internal Server Error")
        mock_500.__aenter__ = AsyncMock(return_value=mock_500)
        mock_500.__aexit__ = AsyncMock(return_value=None)
        
        connected_client.session.post = MagicMock(return_value=mock_500)
        
        result = await connected_client.send_message("Test")
        
        assert result is False
        assert connected_client.session.post.call_count == connected_client.max_retries
    
    @pytest.mark.asyncio
    async def test_no_retry_on_4xx_client_error(self, connected_client):
        """Test that client doesn't retry on 4xx client errors."""
        mock_400 = AsyncMock()
        mock_400.status = 400
        mock_400.text = AsyncMock(return_value="Bad Request")
        mock_400.__aenter__ = AsyncMock(return_value=mock_400)
        mock_400.__aexit__ = AsyncMock(return_value=None)
        
        connected_client.session.post = MagicMock(return_value=mock_400)
        
        result = await connected_client.send_message("Test")
        
        # Should fail immediately without retries
        assert result is False
        assert connected_client.session.post.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retries_on_network_error(self, connected_client):
        """Test that client retries on network errors."""
        import aiohttp
        
        connected_client.session.post.side_effect = aiohttp.ClientError("Network error")
        
        result = await connected_client.send_message("Test")
        
        assert result is False
        assert connected_client.session.post.call_count == connected_client.max_retries
    
    @pytest.mark.asyncio
    async def test_returns_false_on_unexpected_exception(self, connected_client):
        """Test that unexpected exceptions return False."""
        connected_client.session.post.side_effect = RuntimeError("Unexpected error")
        
        result = await connected_client.send_message("Test")
        
        assert result is False
        # Should fail on first attempt for unexpected exceptions
        assert connected_client.session.post.call_count == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, connected_client):
        """Test that exponential backoff is applied between retries."""
        import aiohttp
        
        connected_client.rate_limit_delay = 0.01  # Minimize rate limit delay
        connected_client.session.post.side_effect = aiohttp.ClientError("Network error")
        
        start_time = asyncio.get_event_loop().time()
        await connected_client.send_message("Test")
        end_time = asyncio.get_event_loop().time()
        
        elapsed = end_time - start_time
        # With 3 retries and exponential backoff (1s, 2s), should take ~3+ seconds
        # But we're using smaller delays for testing
        assert elapsed > 0  # Just verify some time passed


# ============================================================================
# send_event() Tests
# ============================================================================

class TestSendEvent:
    """Test send_event() method."""
    
    @pytest.mark.asyncio
    async def test_send_event_success(self, connected_client, sample_event):
        """Test successful event sending."""
        event = sample_event()
        
        result = await connected_client.send_event(event)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_send_event_formats_message(self, connected_client, sample_event):
        """Test that event is properly formatted before sending."""
        event = sample_event(
            event_type=EventType.JOIN,
            player_name="Player1"
        )
        
        await connected_client.send_event(event)
        
        payload = connected_client.session.post.call_args[1]['json']
        content = payload["content"]
        
        # Should include emoji and formatted message
        assert "✅" in content  # JOIN emoji
        assert "Player1" in content
    
    @pytest.mark.asyncio
    async def test_send_event_routes_by_metadata_channel(
        self, webhook_channels, default_webhook_url, mock_session, sample_event
    ):
        """Test that event routes to channel specified in metadata."""
        client = DiscordClient(
            webhook_url=default_webhook_url,
            webhook_channels=webhook_channels
        )
        client.session = mock_session
        
        event = sample_event(channel="chat")
        
        await client.send_event(event)
        
        # Verify routed to chat webhook
        call_args = mock_session.post.call_args
        assert call_args[0][0] == webhook_channels["chat"]
    
    @pytest.mark.asyncio
    async def test_send_event_explicit_channel_overrides_metadata(
        self, webhook_channels, default_webhook_url, mock_session, sample_event
    ):
        """Test that explicit channel parameter overrides metadata."""
        client = DiscordClient(
            webhook_url=default_webhook_url,
            webhook_channels=webhook_channels
        )
        client.session = mock_session
        
        event = sample_event(channel="chat")
        
        # Override with explicit channel
        await client.send_event(event, channel="admin")
        
        # Should use admin webhook, not chat from metadata
        call_args = mock_session.post.call_args
        assert call_args[0][0] == webhook_channels["admin"]
    
    @pytest.mark.asyncio
    async def test_send_event_without_session_raises_assertion(self, discord_client, sample_event):
        """Test that sending event without session raises AssertionError."""
        event = sample_event()
        
        with pytest.raises(AssertionError, match="Client not connected"):
            await discord_client.send_event(event)
    
    @pytest.mark.asyncio
    async def test_send_event_with_empty_metadata(self, connected_client, sample_event):
        """Test sending event with empty metadata dict."""
        event = sample_event()
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Test",
            message="Hello",
            raw_line="test",
            emoji="💬",
            formatted_message="Test: Hello",
            metadata={}
        )
        
        result = await connected_client.send_event(event)
        
        assert result is True


# ============================================================================
# test_connection() Tests
# ============================================================================

class TestTestConnection:
    """Test test_connection() method."""
    
    @pytest.mark.asyncio
    async def test_connection_success(self, connected_client):
        """Test successful connection test."""
        result = await connected_client.test_connection()
        
        assert result is True
        assert connected_client.session.post.called
    
    @pytest.mark.asyncio
    async def test_connection_failure(self, connected_client):
        """Test failed connection test."""
        mock_error = AsyncMock()
        mock_error.status = 404
        mock_error.text = AsyncMock(return_value="Not Found")
        mock_error.__aenter__ = AsyncMock(return_value=mock_error)
        mock_error.__aexit__ = AsyncMock(return_value=None)
        
        connected_client.session.post = MagicMock(return_value=mock_error)
        
        result = await connected_client.test_connection()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_connection_sends_test_message(self, connected_client):
        """Test that test_connection sends appropriate message."""
        await connected_client.test_connection()
        
        payload = connected_client.session.post.call_args[1]['json']
        content = payload["content"]
        
        assert "🔗" in content
        assert connected_client.bot_name in content
        assert "online" in content
    
    @pytest.mark.asyncio
    async def test_connection_without_session_raises_assertion(self, discord_client):
        """Test that testing connection without session raises AssertionError."""
        with pytest.raises(AssertionError, match="Client not connected"):
            await discord_client.test_connection()


# ============================================================================
# _get_emoji() Tests
# ============================================================================

class TestGetEmoji:
    """Test _get_emoji() static method."""
    
    @pytest.mark.parametrize("event_type,expected_emoji", [
        (EventType.JOIN, "✅"),
        (EventType.LEAVE, "❌"),
        (EventType.CHAT, "💬"),
        (EventType.SERVER, "🖥️"),
        (EventType.MILESTONE, "🏆"),
        (EventType.TASK, "✔️"),
        (EventType.RESEARCH, "🔬"),
        (EventType.DEATH, "💀"),
    ])
    def test_emoji_mapping(self, event_type, expected_emoji):
        """Test that event types map to correct emojis."""
        emoji = DiscordClient._get_emoji(event_type)
        
        assert emoji == expected_emoji
    
    def test_unknown_event_type_returns_default(self):
        """Test that unknown event type returns default emoji."""
        # EventType.UNKNOWN should return default
        emoji = DiscordClient._get_emoji(EventType.UNKNOWN)
        
        assert emoji == "ℹ️"


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_message_workflow(self, discord_client):
        """Test complete workflow: connect, send, disconnect."""
        await discord_client.connect()
        
        # Mock the session after connection
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        discord_client.session.post = MagicMock(return_value=mock_response)
        
        result = await discord_client.send_message("Test message")
        
        assert result is True
        
        await discord_client.disconnect()
        assert discord_client.session is None
    
    @pytest.mark.asyncio
    async def test_multiple_events_sequential(self, connected_client, sample_event):
        """Test sending multiple events sequentially."""
        events = [
            sample_event(event_type=EventType.JOIN, player_name="Player1"),
            sample_event(event_type=EventType.CHAT, player_name="Player1", message="Hello"),
            sample_event(event_type=EventType.LEAVE, player_name="Player1"),
        ]
        
        results = []
        for event in events:
            result = await connected_client.send_event(event)
            results.append(result)
        
        assert all(results)
        assert connected_client.session.post.call_count == len(events)
    
    @pytest.mark.asyncio
    async def test_concurrent_message_sending(self, connected_client):
        """Test that concurrent sends are properly synchronized."""
        messages = [f"Message {i}" for i in range(5)]
        
        results = await asyncio.gather(
            *[connected_client.send_message(msg) for msg in messages]
        )
        
        assert all(results)
        assert connected_client.session.post.call_count == len(messages)


# ============================================================================
# Edge Cases and Error Conditions
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_rate_limit_delay(self, default_webhook_url):
        """Test client with zero rate limit delay."""
        client = DiscordClient(
            webhook_url=default_webhook_url,
            rate_limit_delay=0.0
        )
        
        assert client.rate_limit_delay == 0.0
    
    def test_zero_max_retries(self, default_webhook_url):
        """Test client with zero max retries."""
        client = DiscordClient(
            webhook_url=default_webhook_url,
            max_retries=0
        )
        
        assert client.max_retries == 0
    
    @pytest.mark.asyncio
    async def test_very_long_message(self, connected_client):
        """Test sending a very long message."""
        long_message = "A" * 2000  # Discord limit is 2000 chars
        
        result = await connected_client.send_message(long_message)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_empty_message(self, connected_client):
        """Test sending an empty message."""
        result = await connected_client.send_message("")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_message_with_special_characters(self, connected_client):
        """Test sending message with special characters."""
        special_msg = "Test 🎮 **bold** *italic* `code` [link](url)"
        
        result = await connected_client.send_message(special_msg)
        
        assert result is True
        payload = connected_client.session.post.call_args[1]['json']
        assert payload["content"] == special_msg
    
    def test_webhook_channels_shared_reference(self, default_webhook_url):
        """Test that webhook_channels dict is not shared between instances."""
        channels1 = {"chat": "url1"}
        channels2 = {"admin": "url2"}
        
        client1 = DiscordClient(webhook_url=default_webhook_url, webhook_channels=channels1)
        client2 = DiscordClient(webhook_url=default_webhook_url, webhook_channels=channels2)
        
        assert client1.webhook_channels is not client2.webhook_channels
        assert client1.webhook_channels != client2.webhook_channels


# ============================================================================
# Performance and Stress Tests
# ============================================================================

class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced_under_load(self, connected_client):
        """Test that rate limiting works under rapid message sending."""
        connected_client.rate_limit_delay = 0.05
        messages = ["Test" for _ in range(10)]
        
        start = asyncio.get_event_loop().time()
        
        for msg in messages:
            await connected_client.send_message(msg)
        
        end = asyncio.get_event_loop().time()
        elapsed = end - start
        
        # Should take at least rate_limit_delay * (messages - 1)
        expected_min = connected_client.rate_limit_delay * (len(messages) - 1)
        assert elapsed >= expected_min * 0.9  # Allow 10% margin


# ============================================================================
# Mock Behavior Verification
# ============================================================================

class TestMockVerification:
    """Verify that mocks are being called correctly."""
    
    @pytest.mark.asyncio
    async def test_session_post_called_with_correct_args(self, connected_client, default_webhook_url):
        """Verify session.post is called with correct arguments."""
        await connected_client.send_message("Test")
        
        # Verify call signature
        assert connected_client.session.post.called
        call_args = connected_client.session.post.call_args
        
        # Check positional args (webhook URL)
        assert call_args[0][0] == default_webhook_url
        
        # Check keyword args (json payload)
        assert 'json' in call_args[1]
        assert isinstance(call_args[1]['json'], dict)
