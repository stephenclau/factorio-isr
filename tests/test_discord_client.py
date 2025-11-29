"""
Unit tests for discord_client.py with mocked HTTP calls.
No webhook required - all network calls are mocked.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path
import aiohttp

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from discord_client import DiscordClient
from event_parser import FactorioEvent, EventType


@pytest.mark.asyncio
class TestDiscordClientInitialization:
    """Test client initialization and configuration."""
    
    async def test_default_initialization(self):
        """Test client initializes with default values."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        assert client.webhook_url == "https://discord.com/api/webhooks/test/token"
        assert client.bot_name == "Factorio Bridge"
        assert client.bot_avatar_url is None
        assert client.rate_limit_delay == 0.5
        assert client.max_retries == 3
        assert client.session is None
    
    async def test_custom_initialization(self):
        """Test client with custom configuration."""
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/custom/token",
            bot_name="Custom Bot",
            bot_avatar_url="https://example.com/avatar.png",
            rate_limit_delay=1.0,
            max_retries=5
        )
        
        assert client.bot_name == "Custom Bot"
        assert client.bot_avatar_url == "https://example.com/avatar.png"
        assert client.rate_limit_delay == 1.0
        assert client.max_retries == 5


@pytest.mark.asyncio
class TestDiscordClientConnection:
    """Test connection lifecycle."""
    
    async def test_connect_creates_session(self):
        """Test that connect creates aiohttp session."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        await client.connect()
        
        assert client.session is not None
        assert isinstance(client.session, aiohttp.ClientSession)
        
        await client.disconnect()
    
    async def test_disconnect_closes_session(self):
        """Test that disconnect closes session."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        await client.connect()
        
        # Save reference and assert it exists
        assert client.session is not None
        session = client.session
        
        await client.disconnect()
        
        assert client.session is None
        assert session.closed
        
@pytest.mark.asyncio
class TestDiscordClientSendMessage:
    """Test send_message with various scenarios."""
    
    async def test_send_message_success(self):
        """Test successful message send."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        # Mock response with proper async context manager
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = AsyncMock()
        
        # Mock session.post to return the response
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        result = await client.send_message("Test message")
        
        assert result is True
        mock_session.post.assert_called_once()
        
        # Check payload
        call_args = mock_session.post.call_args
        assert call_args[0][0] == client.webhook_url
        payload = call_args[1]['json']
        assert payload['content'] == "Test message"
        assert payload['username'] == "Factorio Bridge"
    
    async def test_send_message_with_avatar(self):
        """Test message send includes avatar URL."""
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/test/token",
            bot_avatar_url="https://example.com/avatar.png"
        )
        
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = AsyncMock()
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        await client.send_message("Test")
        
        payload = mock_session.post.call_args[1]['json']
        assert payload['avatar_url'] == "https://example.com/avatar.png"
    
    async def test_send_message_rate_limited_retry(self):
        """Test rate limit handling with retry."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        # First response: rate limited
        mock_response_429 = AsyncMock()
        mock_response_429.status = 429
        mock_response_429.json = AsyncMock(return_value={"retry_after": 0.01})
        mock_response_429.__aenter__.return_value = mock_response_429
        mock_response_429.__aexit__.return_value = AsyncMock()
        
        # Second response: success
        mock_response_204 = AsyncMock()
        mock_response_204.status = 204
        mock_response_204.__aenter__.return_value = mock_response_204
        mock_response_204.__aexit__.return_value = AsyncMock()
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=[mock_response_429, mock_response_204])
        client.session = mock_session
        
        result = await client.send_message("Test")
        
        assert result is True
        assert mock_session.post.call_count == 2
    
    async def test_send_message_client_error_no_retry(self):
        """Test 4xx errors don't retry."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not found")
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = AsyncMock()
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        result = await client.send_message("Test")
        
        assert result is False
        assert mock_session.post.call_count == 1  # No retry
    
    async def test_send_message_server_error_retries(self):
        """Test 5xx errors trigger retries."""
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/test/token",
            max_retries=3
        )
        
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server error")
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = AsyncMock()
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        result = await client.send_message("Test")
        
        assert result is False
        # Should retry 3 times
        assert mock_session.post.call_count == 3
    
    async def test_send_message_network_error(self):
        """Test network error handling."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))
        client.session = mock_session
        
        result = await client.send_message("Test")
        
        assert result is False
    
    async def test_send_message_requires_connection(self):
        """Test send_message asserts session exists."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        with pytest.raises(AssertionError, match="Client not connected"):
            await client.send_message("Test")


@pytest.mark.asyncio
class TestDiscordClientSendEvent:
    """Test send_event functionality."""
    
    async def test_send_join_event(self):
        """Test sending JOIN event."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = AsyncMock()
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        event = FactorioEvent(event_type=EventType.JOIN, player_name="TestPlayer")
        result = await client.send_event(event)
        
        assert result is True
        
        # Check formatted message
        payload = mock_session.post.call_args[1]['json']
        assert "TestPlayer" in payload['content']
        assert "joined" in payload['content']
        assert "✅" in payload['content']  # JOIN emoji
    
    async def test_send_chat_event(self):
        """Test sending CHAT event."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = AsyncMock()
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello world"
        )
        result = await client.send_event(event)
        
        assert result is True
        
        payload = mock_session.post.call_args[1]['json']
        assert "TestPlayer" in payload['content']
        assert "Hello world" in payload['content']
        assert "💬" in payload['content']  # CHAT emoji
    
    async def test_send_event_requires_connection(self):
        """Test send_event asserts session exists."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test/token")
        
        event = FactorioEvent(event_type=EventType.JOIN, player_name="Test")
        
        with pytest.raises(AssertionError, match="Client not connected"):
            await client.send_event(event)
            
@pytest.mark.asyncio
class TestDiscordClientEmoji:
    """Test emoji mapping.""" 
    async def test_get_emoji_all_types(self):
        """Test emoji for all event types."""
        assert DiscordClient._get_emoji(EventType.JOIN) == "✅"
        assert DiscordClient._get_emoji(EventType.LEAVE) == "❌"
        assert DiscordClient._get_emoji(EventType.CHAT) == "💬"
        assert DiscordClient._get_emoji(EventType.SERVER) == "🖥️"
        assert DiscordClient._get_emoji(EventType.MILESTONE) == "🏆"
        assert DiscordClient._get_emoji(EventType.TASK) == "✔️"
        assert DiscordClient._get_emoji(EventType.RESEARCH) == "🔬"
        assert DiscordClient._get_emoji(EventType.DEATH) == "💀"
        assert DiscordClient._get_emoji(EventType.UNKNOWN) == "ℹ️"
        
@pytest.mark.asyncio  
class TestDiscordClientRateLimiting:
    """Test rate limiting behavior."""
 
    async def test_rate_limit_delay(self):
        """Test that messages are delayed by rate limit."""
        import time
        
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/test/token",
            rate_limit_delay=0.1  # Shorter delay for test
        )
        
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = AsyncMock()
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        start = time.time()
        await client.send_message("Message 1")
        await client.send_message("Message 2")
        elapsed = time.time() - start
        
        # Should take at least rate_limit_delay
        assert elapsed >= 0.09  # Allow small margin
        assert mock_session.post.call_count == 2
