"""
Pytest test suite for discord_client.py

Integration tests for Discord webhook functionality.
These tests require a real webhook URL in .env
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from discord_client import DiscordClient
from event_parser import FactorioEvent, EventType

# Skip all tests in this file if DISCORD_WEBHOOK_URL is not set
pytestmark = pytest.mark.skipif(
    not os.getenv('DISCORD_WEBHOOK_URL'),
    reason="DISCORD_WEBHOOK_URL not set - skipping integration tests"
)


def get_webhook_url() -> str:
    """Get webhook URL from environment with type safety."""
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    assert webhook_url is not None, "DISCORD_WEBHOOK_URL must be set"
    return webhook_url


@pytest.mark.asyncio
@pytest.mark.integration  # Mark as integration test
class TestDiscordClient:
    """Tests for Discord client (requires real webhook)."""
    
    async def test_connection(self):
        """Test Discord webhook connection."""
        webhook_url = get_webhook_url()
        client = DiscordClient(
            webhook_url=webhook_url,
            bot_name="Test Bot",
            bot_avatar_url=None,
        )
        
        try:
            await client.connect()
            result = await client.test_connection()
            assert result is True, "Webhook connection test failed"
        finally:
            await client.disconnect()
    
    async def test_send_join_event(self):
        """Test sending JOIN event."""
        webhook_url = get_webhook_url()
        client = DiscordClient(
            webhook_url=webhook_url,
            bot_name="Test Bot",
            bot_avatar_url=None,
        )
        
        try:
            await client.connect()
            event = FactorioEvent(event_type=EventType.JOIN, player_name="TestPlayer")
            result = await client.send_event(event)
            assert result is True, "Failed to send JOIN event"
            await asyncio.sleep(0.5)
        finally:
            await client.disconnect()
    
    async def test_send_leave_event(self):
        """Test sending LEAVE event."""
        webhook_url = get_webhook_url()
        client = DiscordClient(
            webhook_url=webhook_url,
            bot_name="Test Bot",
            bot_avatar_url=None,
        )
        
        try:
            await client.connect()
            event = FactorioEvent(event_type=EventType.LEAVE, player_name="TestPlayer")
            result = await client.send_event(event)
            assert result is True, "Failed to send LEAVE event"
            await asyncio.sleep(0.5)
        finally:
            await client.disconnect()
    
    async def test_send_chat_event(self):
        """Test sending CHAT event."""
        webhook_url = get_webhook_url()
        client = DiscordClient(
            webhook_url=webhook_url,
            bot_name="Test Bot",
            bot_avatar_url=None,
        )
        
        try:
            await client.connect()
            event = FactorioEvent(
                event_type=EventType.CHAT,
                player_name="TestPlayer",
                message="Hello from pytest!"
            )
            result = await client.send_event(event)
            assert result is True, "Failed to send CHAT event"
            await asyncio.sleep(0.5)
        finally:
            await client.disconnect()
    
    async def test_send_milestone_event(self):
        """Test sending MILESTONE event."""
        webhook_url = get_webhook_url()
        client = DiscordClient(
            webhook_url=webhook_url,
            bot_name="Test Bot",
            bot_avatar_url=None,
        )
        
        try:
            await client.connect()
            event = FactorioEvent(
                event_type=EventType.MILESTONE,
                player_name="TestPlayer",
                message="First automation"
            )
            result = await client.send_event(event)
            assert result is True, "Failed to send MILESTONE event"
            await asyncio.sleep(0.5)
        finally:
            await client.disconnect()
    
    async def test_send_research_event(self):
        """Test sending RESEARCH event."""
        webhook_url = get_webhook_url()
        client = DiscordClient(
            webhook_url=webhook_url,
            bot_name="Test Bot",
            bot_avatar_url=None,
        )
        
        try:
            await client.connect()
            event = FactorioEvent(
                event_type=EventType.RESEARCH,
                message="Automation technology"
            )
            result = await client.send_event(event)
            assert result is True, "Failed to send RESEARCH event"
            await asyncio.sleep(0.5)
        finally:
            await client.disconnect()
    
    async def test_send_death_event(self):
        """Test sending DEATH event."""
        webhook_url = get_webhook_url()
        client = DiscordClient(
            webhook_url=webhook_url,
            bot_name="Test Bot",
            bot_avatar_url=None,
        )
        
        try:
            await client.connect()
            event = FactorioEvent(
                event_type=EventType.DEATH,
                player_name="TestPlayer",
                metadata={"cause": "a biter"}
            )
            result = await client.send_event(event)
            assert result is True, "Failed to send DEATH event"
            await asyncio.sleep(0.5)
        finally:
            await client.disconnect()
    
    async def test_rate_limiting(self):
        """Test that rate limiting works."""
        import time
        
        webhook_url = get_webhook_url()
        client = DiscordClient(
            webhook_url=webhook_url,
            bot_name="Test Bot",
            bot_avatar_url=None,
        )
        
        try:
            await client.connect()
            event = FactorioEvent(event_type=EventType.JOIN, player_name="RateLimitTest")
            
            start = time.time()
            await client.send_event(event)
            await client.send_event(event)
            elapsed = time.time() - start
            
            # Should take at least rate_limit_delay (0.5s)
            assert elapsed >= 0.5, "Rate limiting not working"
        finally:
            await client.disconnect()


@pytest.mark.asyncio
class TestDiscordClientUnit:
    """Unit tests for Discord client (no network calls)."""
    
    async def test_get_emoji(self):
        """Test emoji mapping."""
        assert DiscordClient._get_emoji(EventType.JOIN) == "✅"
        assert DiscordClient._get_emoji(EventType.LEAVE) == "❌"
        assert DiscordClient._get_emoji(EventType.CHAT) == "💬"
        assert DiscordClient._get_emoji(EventType.SERVER) == "🖥️"
        assert DiscordClient._get_emoji(EventType.MILESTONE) == "🏆"
        assert DiscordClient._get_emoji(EventType.TASK) == "✔️"
        assert DiscordClient._get_emoji(EventType.RESEARCH) == "🔬"
        assert DiscordClient._get_emoji(EventType.DEATH) == "💀"
    
    async def test_client_initialization(self):
        """Test client initializes with correct defaults."""
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/test/token"
        )
        
        assert client.webhook_url == "https://discord.com/api/webhooks/test/token"
        assert client.bot_name == "Factorio Bridge"
        assert client.bot_avatar_url is None
        assert client.rate_limit_delay == 0.5
        assert client.max_retries == 3
        assert client.session is None
    
    async def test_client_custom_config(self):
        """Test client accepts custom configuration."""
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/test/token",
            bot_name="Custom Bot",
            bot_avatar_url="https://example.com/avatar.png",
            rate_limit_delay=1.0,
            max_retries=5
        )
        
        assert client.bot_name == "Custom Bot"
        assert client.bot_avatar_url == "https://example.com/avatar.png"
        assert client.rate_limit_delay == 1.0
        assert client.max_retries == 5
    
    async def test_format_event_message(self):
        """Test event formatting."""
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/test/token"
        )
        
        # Test JOIN event
        join_event = FactorioEvent(event_type=EventType.JOIN, player_name="TestPlayer")
        formatted = client.formatter.format_for_discord(join_event)
        assert "TestPlayer" in formatted
        assert "joined" in formatted.lower()
        
        # Test CHAT event
        chat_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello world"
        )
        formatted = client.formatter.format_for_discord(chat_event)
        assert "TestPlayer" in formatted
        assert "Hello world" in formatted
