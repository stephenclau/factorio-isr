"""
Pytest test suite for discord_client.py

Integration tests for Discord webhook functionality.
These tests require a real webhook URL in .env
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from discord_client import DiscordClient
from event_parser import FactorioEvent, EventType
from config import load_config


@pytest.mark.asyncio
class TestDiscordClient:
    """Tests for Discord client (requires real webhook)."""
    
    @pytest.fixture
    async def client(self):
        """Create and connect Discord client."""
        config = load_config()
        client = DiscordClient(
            webhook_url=config.discord_webhook_url,
            bot_name=config.bot_name,
            bot_avatar_url=config.bot_avatar_url,
        )
        await client.connect()
        yield client
        await client.disconnect()
    
    async def test_connection(self, client):
        """Test Discord webhook connection."""
        result = await client.test_connection()
        assert result is True, "Webhook connection test failed"
    
    async def test_send_join_event(self, client):
        """Test sending JOIN event."""
        event = FactorioEvent(event_type=EventType.JOIN, player_name="TestPlayer")
        result = await client.send_event(event)
        assert result is True, "Failed to send JOIN event"
        await asyncio.sleep(0.5)
    
    async def test_send_leave_event(self, client):
        """Test sending LEAVE event."""
        event = FactorioEvent(event_type=EventType.LEAVE, player_name="TestPlayer")
        result = await client.send_event(event)
        assert result is True, "Failed to send LEAVE event"
        await asyncio.sleep(0.5)
    
    async def test_send_chat_event(self, client):
        """Test sending CHAT event."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello from pytest!"
        )
        result = await client.send_event(event)
        assert result is True, "Failed to send CHAT event"
        await asyncio.sleep(0.5)
    
    async def test_send_milestone_event(self, client):
        """Test sending MILESTONE event."""
        event = FactorioEvent(
            event_type=EventType.MILESTONE,
            player_name="TestPlayer",
            message="First automation"
        )
        result = await client.send_event(event)
        assert result is True, "Failed to send MILESTONE event"
        await asyncio.sleep(0.5)
    
    async def test_send_research_event(self, client):
        """Test sending RESEARCH event."""
        event = FactorioEvent(
            event_type=EventType.RESEARCH,
            message="Automation technology"
        )
        result = await client.send_event(event)
        assert result is True, "Failed to send RESEARCH event"
        await asyncio.sleep(0.5)
    
    async def test_send_death_event(self, client):
        """Test sending DEATH event."""
        event = FactorioEvent(
            event_type=EventType.DEATH,
            player_name="TestPlayer",
            metadata={"cause": "a biter"}
        )
        result = await client.send_event(event)
        assert result is True, "Failed to send DEATH event"
        await asyncio.sleep(0.5)
    
    async def test_rate_limiting(self, client):
        """Test that rate limiting works."""
        import time
        
        event = FactorioEvent(event_type=EventType.JOIN, player_name="RateLimitTest")
        
        start = time.time()
        await client.send_event(event)
        await client.send_event(event)
        elapsed = time.time() - start
        
        # Should take at least rate_limit_delay (0.5s)
        assert elapsed >= 0.5, "Rate limiting not working"


# Keep the manual test function for direct execution
async def manual_test():
    """Manual test that can be run directly."""
    print("Loading config...")
    config = load_config()
    
    print(f"Creating Discord client...")
    client = DiscordClient(
        webhook_url=config.discord_webhook_url,
        bot_name=config.bot_name,
        bot_avatar_url=config.bot_avatar_url,
    )
    
    try:
        print("Connecting...")
        await client.connect()
        
        print("Testing webhook...")
        success = await client.test_connection()
        
        if success:
            print("✓ Webhook test successful!")
            print("\n📤 Sending test events...")
            
            events = [
                (FactorioEvent(event_type=EventType.JOIN, player_name="TestPlayer"), "JOIN"),
                (FactorioEvent(event_type=EventType.CHAT, player_name="TestPlayer", message="Hello!"), "CHAT"),
                (FactorioEvent(event_type=EventType.MILESTONE, player_name="TestPlayer", message="First automation"), "MILESTONE"),
                (FactorioEvent(event_type=EventType.RESEARCH, message="Automation"), "RESEARCH"),
                (FactorioEvent(event_type=EventType.DEATH, player_name="TestPlayer", metadata={"cause": "a biter"}), "DEATH"),
                (FactorioEvent(event_type=EventType.LEAVE, player_name="TestPlayer"), "LEAVE"),
            ]
            
            for event, name in events:
                await client.send_event(event)
                print(f"  ✓ Sent {name} event")
                await asyncio.sleep(1)
            
            print("\n✅ All Discord tests passed!")
            print("📱 Check your Discord channel for the messages.")
        else:
            print("❌ Webhook test failed")
            print("⚠️  Check your DISCORD_WEBHOOK_URL in .env")
    
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(manual_test())
