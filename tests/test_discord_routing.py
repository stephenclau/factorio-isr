"""Tests for multi-channel Discord routing."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from discord_client import DiscordClient
from event_parser import FactorioEvent, EventType


class TestMultiChannelRouting:
    """Test multi-channel routing functionality."""
    
    def test_get_webhook_url_with_channel(self):
        """Test getting webhook URL for configured channel."""
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token",
            "admin": "https://discord.com/api/webhooks/456/admin_token"
        }
        
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/999/default",
            webhook_channels=webhooks
        )
        
        assert client.get_webhook_url("chat") == webhooks["chat"]
        assert client.get_webhook_url("admin") == webhooks["admin"]
    
    def test_get_webhook_url_fallback(self):
        """Test fallback to default when channel not configured."""
        default_url = "https://discord.com/api/webhooks/999/default"
        client = DiscordClient(webhook_url=default_url, webhook_channels={})
        
        # Non-existent channel should fall back to default
        assert client.get_webhook_url("nonexistent") == default_url
        assert client.get_webhook_url(None) == default_url
    
    def test_get_webhook_url_no_channel(self):
        """Test getting default webhook when no channel specified."""
        default_url = "https://discord.com/api/webhooks/999/default"
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token"
        }
        
        client = DiscordClient(
            webhook_url=default_url,
            webhook_channels=webhooks
        )
        
        # No channel specified should return default
        assert client.get_webhook_url() == default_url
        assert client.get_webhook_url(None) == default_url
    
    def test_webhook_channels_defaults_to_empty_dict(self):
        """Test that webhook_channels defaults to empty dict when None."""
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/999/default",
            webhook_channels=None
        )
        
        assert isinstance(client.webhook_channels, dict)
        assert len(client.webhook_channels) == 0
    
    @pytest.mark.asyncio
    async def test_send_event_with_channel_in_metadata(self):
        """Test sending event with channel from metadata."""
        webhooks = {
            "milestone": "https://discord.com/api/webhooks/123/milestone_token"
        }
        
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/999/default",
            webhook_channels=webhooks
        )
        
        # Mock session
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        # Create event with channel metadata
        event = FactorioEvent(
            event_type=EventType.MILESTONE,
            player_name="TestPlayer",
            message="Rocket launched",
            raw_line="test",
            emoji="🚀",
            formatted_message="TestPlayer: Rocket launched",
            metadata={"channel": "milestone"}
        )
        
        result = await client.send_event(event)
        
        assert result is True
        # Verify correct webhook was used
        call_args = mock_session.post.call_args
        assert call_args[0][0] == webhooks["milestone"]
    
    @pytest.mark.asyncio
    async def test_send_event_with_explicit_channel_override(self):
        """Test sending event with explicit channel parameter."""
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token",
            "admin": "https://discord.com/api/webhooks/456/admin_token"
        }
        
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/999/default",
            webhook_channels=webhooks
        )
        
        # Mock session
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        # Create event with different channel in metadata
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello",
            raw_line="test",
            emoji="💬",
            formatted_message="TestPlayer: Hello",
            metadata={"channel": "chat"}
        )
        
        # Override with explicit channel parameter
        result = await client.send_event(event, channel="admin")
        
        assert result is True
        # Verify explicit channel was used (not metadata channel)
        call_args = mock_session.post.call_args
        assert call_args[0][0] == webhooks["admin"]
    
    @pytest.mark.asyncio
    async def test_send_event_fallback_to_default(self):
        """Test event falls back to default when channel not configured."""
        default_url = "https://discord.com/api/webhooks/999/default"
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token"
        }
        
        client = DiscordClient(
            webhook_url=default_url,
            webhook_channels=webhooks
        )
        
        # Mock session
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        # Create event with unconfigured channel
        event = FactorioEvent(
            event_type=EventType.MILESTONE,
            player_name="TestPlayer",
            message="Achievement",
            raw_line="test",
            emoji="🏆",
            formatted_message="TestPlayer: Achievement",
            metadata={"channel": "unconfigured"}
        )
        
        result = await client.send_event(event)
        
        assert result is True
        # Verify default webhook was used
        call_args = mock_session.post.call_args
        assert call_args[0][0] == default_url
    
    @pytest.mark.asyncio
    async def test_send_event_no_metadata(self):
        """Test sending event with no metadata uses default webhook."""
        default_url = "https://discord.com/api/webhooks/999/default"
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token"
        }
        
        client = DiscordClient(
            webhook_url=default_url,
            webhook_channels=webhooks
        )
        
        # Mock session
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        # Create event with no metadata
        event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="TestPlayer",
            raw_line="test",
            emoji="✅",
            formatted_message="TestPlayer joined",
            metadata={}  # Empty metadata
        )
        
        result = await client.send_event(event)
        
        assert result is True
        # Verify default webhook was used
        call_args = mock_session.post.call_args
        assert call_args[0][0] == default_url
    
    @pytest.mark.asyncio
    async def test_send_message_with_specific_webhook(self):
        """Test send_message with explicit webhook URL."""
        default_url = "https://discord.com/api/webhooks/999/default"
        custom_url = "https://discord.com/api/webhooks/888/custom"
        
        client = DiscordClient(webhook_url=default_url)
        
        # Mock session
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session
        
        # Send with explicit webhook
        result = await client.send_message("Test message", webhook_url=custom_url)
        
        assert result is True
        # Verify custom webhook was used
        call_args = mock_session.post.call_args
        assert call_args[0][0] == custom_url
