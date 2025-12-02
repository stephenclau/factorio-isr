"""
Type-safe pytest tests for discord_bot.py.
Tests Discord bot initialization, connection, and event sending.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import sys

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from discord_bot import DiscordBot, DiscordBotFactory  # type: ignore
from event_parser import FactorioEvent, EventType  # type: ignore


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_token() -> str:
    """Provide a mock Discord bot token."""
    return "MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.GhwY8K.mock_token_for_testing_purposes_only"


@pytest.fixture
def bot_token_from_secrets() -> Optional[str]:
    """
    Load bot token from .secrets directory in project root.
    Returns None if not found (for CI/CD environments).
    """
    secrets_path = project_root / ".secrets" / "DISCORD_BOT_TOKEN.txt"
    if secrets_path.exists():
        try:
            token = secrets_path.read_text().strip()
            if token and len(token) > 50:
                return token
        except Exception:
            pass
    return None


@pytest.fixture
def event_channel_id() -> int:
    """Provide a mock channel ID."""
    return 1234567890123456789


# ============================================================================
# Initialization Tests
# ============================================================================

class TestDiscordBotInit:
    """Tests for DiscordBot initialization."""
    
    def test_init_with_token(self, mock_token: str) -> None:
        """Test bot initialization with token."""
        bot = DiscordBot(token=mock_token, bot_name="Test Bot")
        
        assert bot.token == mock_token
        assert bot.bot_name == "Test Bot"
        assert bot.event_channel_id is None
        assert not bot.is_connected
    
    def test_init_default_intents(self, mock_token: str) -> None:
        """Test bot creates default intents if none provided."""
        bot = DiscordBot(token=mock_token)
        
        # Intents should be configured
        assert bot.intents is not None
        assert bot.intents.message_content is True
        assert bot.intents.guilds is True
    
    def test_init_custom_intents(self, mock_token: str) -> None:
        """Test bot accepts custom intents."""
        import discord
        
        custom_intents = discord.Intents.default()
        custom_intents.message_content = False
        
        bot = DiscordBot(token=mock_token, intents=custom_intents)
        
        assert bot.intents.message_content is False


class TestDiscordBotFactory:
    """Tests for DiscordBotFactory."""
    
    def test_create_bot(self, mock_token: str) -> None:
        """Test factory creates bot instance."""
        bot = DiscordBotFactory.create_bot(token=mock_token, bot_name="Factory Bot")
        
        assert isinstance(bot, DiscordBot)
        assert bot.token == mock_token
        assert bot.bot_name == "Factory Bot"


# ============================================================================
# Configuration Tests
# ============================================================================

class TestDiscordBotConfiguration:
    """Tests for bot configuration methods."""
    
    def test_set_event_channel(self, mock_token: str, event_channel_id: int) -> None:
        """Test setting event channel ID."""
        bot = DiscordBot(token=mock_token)
        
        bot.set_event_channel(event_channel_id)
        
        assert bot.event_channel_id == event_channel_id
    
    def test_is_connected_initially_false(self, mock_token: str) -> None:
        """Test is_connected is False before connection."""
        bot = DiscordBot(token=mock_token)
        
        assert bot.is_connected is False


# ============================================================================
# Event Sending Tests
# ============================================================================

class TestDiscordBotSendEvent:
    """Tests for send_event method."""
    
    @pytest.mark.asyncio
    async def test_send_event_not_connected(self, mock_token: str) -> None:
        """Test send_event returns False when not connected."""
        bot = DiscordBot(token=mock_token)
        
        event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="TestPlayer",
            raw_line="TestPlayer joined the game",
            emoji="👋",
            formatted_message="TestPlayer joined the server",
        )
        
        result = await bot.send_event(event)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_event_no_channel_configured(self, mock_token: str) -> None:
        """Test send_event returns False when channel not configured."""
        bot = DiscordBot(token=mock_token)
        bot._connected = True  # Simulate connected state
        
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello world",
            raw_line="CHAT TestPlayer: Hello world",
            emoji="💬",
            formatted_message="TestPlayer: Hello world",
        )
        
        result = await bot.send_event(event)
        
        assert result is False
        assert bot.event_channel_id is None
    
    @pytest.mark.asyncio
    async def test_send_event_channel_not_found(
        self, mock_token: str, event_channel_id: int
    ) -> None:
        """Test send_event returns False when channel not found."""
        bot = DiscordBot(token=mock_token)
        bot._connected = True
        bot.set_event_channel(event_channel_id)
        
        # Mock get_channel to return None
        bot.get_channel = MagicMock(return_value=None)  # type: ignore
        
        event = FactorioEvent(
            event_type=EventType.LEAVE,
            player_name="TestPlayer",
            raw_line="TestPlayer left the game",
            emoji="👋",
            formatted_message="TestPlayer left the server",
        )
        
        result = await bot.send_event(event)
        
        assert result is False


# ============================================================================
# Connection Tests (Mocked)
# ============================================================================

class TestDiscordBotConnection:
    """Tests for bot connection with mocked Discord API."""
    
    @pytest.mark.asyncio
    async def test_connect_bot_timeout(self, mock_token: str) -> None:
        """Test connect_bot raises error on timeout."""
        bot = DiscordBot(token=mock_token)
        
        # Mock start to do nothing (simulate timeout)
        async def mock_start(token: str) -> None:
            await asyncio.sleep(100)  # Never completes
        
        with patch.object(bot, 'start', new=mock_start):
            with pytest.raises(ConnectionError, match="connection timed out"):
                await bot.connect_bot()
    
    @pytest.mark.asyncio
    async def test_disconnect_bot_when_not_connected(self, mock_token: str) -> None:
        """Test disconnect_bot handles not connected state gracefully."""
        bot = DiscordBot(token=mock_token)
        
        # Should not raise
        await bot.disconnect_bot()
        
        assert not bot.is_connected


# ============================================================================
# Integration Tests (Optional - Only Run if Token Available)
# ============================================================================

@pytest.mark.integration
@pytest.mark.skipif(
    not (project_root / ".secrets" / "DISCORD_BOT_TOKEN.txt").exists(),
    reason="No bot token found in .secrets/DISCORD_BOT_TOKEN.txt",
)
class TestDiscordBotIntegration:
    """
    Integration tests that connect to real Discord API.
    Only run when bot token is available in .secrets directory.
    """   
    @pytest.mark.asyncio 
    async def test_real_bot_connection(self, bot_token_from_secrets: Optional[str]) -> None:
        """Test connecting to Discord with real token."""
        if bot_token_from_secrets is None:
            pytest.skip("No valid bot token available")
        
        print(f"\n🔍 Token length: {len(bot_token_from_secrets)}")
        print(f"🔍 Token starts with: {bot_token_from_secrets[:15]}...")
        
        bot = DiscordBot(token=bot_token_from_secrets, bot_name="Test Bot")
        
        try:
            print("🤖 Starting bot connection...")
            await bot.connect_bot()
            
            print(f"✅ connect_bot() completed")
            print(f"   - is_connected: {bot.is_connected}")
            print(f"   - _connected: {bot._connected}")
            print(f"   - _ready.is_set(): {bot._ready.is_set()}")
            print(f"   - user: {bot.user}")
            
            # Give it a moment to fully initialize
            await asyncio.sleep(1)
            
            print(f"After 1s:")
            print(f"   - is_connected: {bot.is_connected}")
            print(f"   - user: {bot.user}")
            
            assert bot._ready.is_set(), "Ready event should be set"
            assert bot.user is not None, "Bot user should be set"
            
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")
            print(f"   - _connected: {bot._connected}")
            print(f"   - _ready.is_set(): {bot._ready.is_set()}")
            raise
        finally:
            print("🔌 Disconnecting bot...")
            await bot.disconnect_bot()


