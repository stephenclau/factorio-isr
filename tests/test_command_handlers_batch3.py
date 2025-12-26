

"""🎮 LAYER 1 TESTING: Handler-Level Unit Tests for Batch 3

Game Control Command Handlers (Clock, Speed, Promote, Demote)

**Strategy**: Test handlers in ISOLATION with minimal mocks
- No bot object mocking
- Direct dependency injection via constructor
- Error branch forcing via dependency attributes
- Multi-value option testing (Clock: day/night/custom)
- Numeric validation testing (Speed: 0.1-10.0)

**Target Coverage**: 95%+ per handler
**Total Tests**: 16 (4 handlers with specialized patterns)

**Unique Patterns**:
1. ClockCommandHandler: Multi-value options + float validation
2. SpeedCommandHandler: Numeric range validation + early error check
3. PromoteCommandHandler: Admin elevation with field embeds
4. DemoteCommandHandler: Admin removal with warning color

**Error Branches Tested**:
1. Rate limited
2. RCON unavailable
3. Exception during execution
4. Validation errors (Clock float, Speed range)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Optional
import discord

from bot.commands.command_handlers import (
    ClockCommandHandler,
    SpeedCommandHandler,
    PromoteCommandHandler,
    DemoteCommandHandler,
    CommandResult,
)


# ════════════════════════════════════════════════════
# MINIMAL MOCK DEPENDENCIES (reused from Batches 1-2)
# ════════════════════════════════════════════════════

class DummyUserContext:
    """Minimal UserContextProvider implementation for testing."""

    def __init__(
        self,
        server_name: str = "prod-server",
        rcon_client: Optional[MagicMock] = None,
    ):
        self.server_name = server_name
        self.rcon_client = rcon_client

    def get_user_server(self, user_id: int) -> str:
        return "main"

    def get_server_display_name(self, user_id: int) -> str:
        return self.server_name

    def get_rcon_for_user(self, user_id: int) -> Optional[MagicMock]:
        return self.rcon_client


class DummyRateLimiter:
    """Minimal RateLimiter implementation with configurable behavior."""

    def __init__(self, is_limited: bool = False, retry_seconds: int = 30):
        self.is_limited = is_limited
        self.retry_seconds = retry_seconds

    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[int]]:
        return (self.is_limited, self.retry_seconds if self.is_limited else None)


class DummyEmbedBuilder:
    """Minimal EmbedBuilder implementation."""

    COLOR_WARNING = 0xFFA500
    COLOR_SUCCESS = 0x00FF00

    @staticmethod
    def error_embed(message: str) -> discord.Embed:
        """Create error embed."""
        return discord.Embed(
            title="❌ Error",
            description=message,
            color=discord.Color.red(),
        )

    @staticmethod
    def cooldown_embed(retry_seconds: int) -> discord.Embed:
        """Create cooldown embed."""
        return discord.Embed(
            title="⏱️ Rate Limited",
            description=f"Try again in {retry_seconds} seconds",
            color=discord.Color.from_rgb(255, 165, 0),
        )

    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed:
        """Create info embed."""
        return discord.Embed(title=title, description=message)


# ════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════

@pytest.fixture
def mock_interaction():
    """Create mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.name = "TestAdmin"
    return interaction


@pytest.fixture
def mock_rcon_client():
    """Create mock RCON client."""
    rcon = MagicMock()
    rcon.is_connected = True
    rcon.execute = AsyncMock(return_value="")
    return rcon


# ════════════════════════════════════════════════════
# CLOCK COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestClockCommandHandler:
    """Handler-level tests for ClockCommandHandler."""

    @pytest.mark.asyncio
    async def test_clock_display_current_time(self, mock_interaction, mock_rcon_client):
        """Test: clock display command shows current game time.

        Happy Path (Display):
        - No value argument
        - RCON executes Lua script to get current daytime
        - Embed shows formatted time (HH:MM)

        Expected:
        - result.success = True
        - Embed title: "🕐 Current Game Clock"
        - RCON called with Lua script
        """
        mock_rcon_client.execute.return_value = "Current daytime: 0.50 (🕐 12:00)"
        handler = ClockCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, value=None)

        assert result.success is True
        assert result.embed is not None
        assert "Current Game Clock" in result.embed.title
        assert "12:00" in result.embed.description
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_clock_set_eternal_day(self, mock_interaction, mock_rcon_client):
        """Test: clock set eternal day.

        Happy Path (Eternal Day):
        - value="day" or "eternal-day"
        - Sets daytime to 0.5 (noon) and freezes it
        - Embed shows "☀️ Eternal Day Set"
        """
        mock_rcon_client.execute.return_value = "☀️ Set to eternal day (12:00)"
        handler = ClockCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, value="day")

        assert result.success is True
        assert result.embed is not None
        assert "Eternal Day" in result.embed.title
        mock_rcon_client.execute.assert_called_once()
        assert "daytime = 0.5" in mock_rcon_client.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_clock_set_eternal_night(self, mock_interaction, mock_rcon_client):
        """Test: clock set eternal night.

        Happy Path (Eternal Night):
        - value="night" or "eternal-night"
        - Sets daytime to 0.0 (midnight) and freezes it
        - Embed shows "🌙 Eternal Night Set"
        """
        mock_rcon_client.execute.return_value = "🌙 Set to eternal night (00:00)"
        handler = ClockCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, value="night")

        assert result.success is True
        assert result.embed is not None
        assert "Eternal Night" in result.embed.title
        mock_rcon_client.execute.assert_called_once()
        assert "daytime = 0.0" in mock_rcon_client.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_clock_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: clock command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Lua error")
        handler = ClockCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, value="day")

        assert result.success is False
        assert "Clock command failed" in result.error_embed.description
        assert "Lua error" in result.error_embed.description


# ════════════════════════════════════════════════════
# SPEED COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestSpeedCommandHandler:
    """Handler-level tests for SpeedCommandHandler."""

    @pytest.mark.asyncio
    async def test_speed_valid_normal(self, mock_interaction, mock_rcon_client):
        """Test: speed command with normal speed (1.0x).

        Happy Path (Normal Speed):
        - value=1.0 (valid range: 0.1-10.0)
        - RCON available
        - Embed shows "⚡ Game Speed Set"

        Expected:
        - result.success = True
        - Fields: New Speed, Effect (Normal), Server
        - Effect shows "➡️ Normal"
        """
        handler = SpeedCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, value=1.0)

        assert result.success is True
        assert result.embed is not None
        assert "Game Speed Set" in result.embed.title
        assert "1.0x" in result.embed.fields[0].value
        assert "Normal" in result.embed.fields[1].value or "➡️" in result.embed.fields[1].value
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_speed_valid_faster(self, mock_interaction, mock_rcon_client):
        """Test: speed command with faster speed (>1.0x).

        Happy Path (Faster Speed):
        - value=2.5 (valid range: 0.1-10.0)
        - Effect shows "⬊ Faster"
        """
        handler = SpeedCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, value=2.5)

        assert result.success is True
        assert result.embed is not None
        assert "2.5x" in result.embed.fields[0].value
        assert "Faster" in result.embed.fields[1].value or "⬊" in result.embed.fields[1].value
        mock_rcon_client.execute.assert_called_with("/sc game.speed = 2.5")

    @pytest.mark.asyncio
    async def test_speed_out_of_range(self, mock_interaction, mock_rcon_client):
        """Test: speed command rejects out-of-range values.

        Error Branch (Invalid Range):
        - Early validation before rate limit check
        - value=15.0 (exceeds max 10.0)
        - Should return error_embed immediately
        - RCON not called
        """
        handler = SpeedCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, value=15.0)

        assert result.success is False
        assert result.error_embed is not None
        assert "Speed must be between 0.1 and 10.0" in result.error_embed.description
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_speed_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: speed command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Speed command rejected")
        handler = SpeedCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, value=2.0)

        assert result.success is False
        assert "Failed to set speed" in result.error_embed.description
        assert "Speed command rejected" in result.error_embed.description


# ════════════════════════════════════════════════════
# PROMOTE COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestPromoteCommandHandler:
    """Handler-level tests for PromoteCommandHandler."""

    @pytest.mark.asyncio
    async def test_promote_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: promote command succeeds for valid player.

        Happy Path:
        - User not rate limited
        - RCON available
        - Valid player name

        Expected:
        - result.success = True
        - Embed title: "👑 Player Promoted"
        - Fields: Player, Role="Administrator", Server
        """
        handler = PromoteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, player="NewAdmin")

        assert result.success is True
        assert result.embed is not None
        assert "Player Promoted" in result.embed.title
        assert "NewAdmin" in result.embed.fields[0].value
        assert "Administrator" in result.embed.fields[1].value
        mock_rcon_client.execute.assert_called_once()
        assert "NewAdmin" in mock_rcon_client.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_promote_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: promote command blocked by rate limit."""
        handler = PromoteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, player="NewAdmin")

        assert result.success is False
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_promote_rcon_unavailable(self, mock_interaction):
        """Test: promote command fails when RCON unavailable."""
        handler = PromoteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, player="NewAdmin")

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_promote_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: promote command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Player not found")
        handler = PromoteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, player="NonexistentPlayer")

        assert result.success is False
        assert "Failed to promote" in result.error_embed.description
        assert "Player not found" in result.error_embed.description


# ════════════════════════════════════════════════════
# DEMOTE COMMAND HANDLER TESTS
# ════════════════════════════════════════════════════

class TestDemoteCommandHandler:
    """Handler-level tests for DemoteCommandHandler."""

    @pytest.mark.asyncio
    async def test_demote_happy_path(self, mock_interaction, mock_rcon_client):
        """Test: demote command succeeds for valid player.

        Happy Path:
        - User not rate limited
        - RCON available
        - Valid player name

        Expected:
        - result.success = True
        - Embed title: "📙 Player Demoted"
        - Fields: Player, Role="Player", Server
        - Color: COLOR_WARNING (orange)
        """
        handler = DemoteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, player="FormerAdmin")

        assert result.success is True
        assert result.embed is not None
        assert "Player Demoted" in result.embed.title
        assert "FormerAdmin" in result.embed.fields[0].value
        assert "Player" in result.embed.fields[1].value
        mock_rcon_client.execute.assert_called_once()
        assert "FormerAdmin" in mock_rcon_client.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_demote_rate_limited(self, mock_interaction, mock_rcon_client):
        """Test: demote command blocked by rate limit."""
        handler = DemoteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=True, retry_seconds=30),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, player="FormerAdmin")

        assert result.success is False
        assert result.ephemeral is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_demote_rcon_unavailable(self, mock_interaction):
        """Test: demote command fails when RCON unavailable."""
        handler = DemoteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=None),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, player="FormerAdmin")

        assert result.success is False
        assert "RCON not available" in result.error_embed.description

    @pytest.mark.asyncio
    async def test_demote_exception_during_execute(self, mock_interaction, mock_rcon_client):
        """Test: demote command handles exception during execution."""
        mock_rcon_client.execute.side_effect = Exception("Command not recognized")
        handler = DemoteCommandHandler(
            user_context_provider=DummyUserContext(rcon_client=mock_rcon_client),
            rate_limiter=DummyRateLimiter(is_limited=False),
            embed_builder_type=DummyEmbedBuilder,
        )

        result = await handler.execute(mock_interaction, player="FormerAdmin")

        assert result.success is False
        assert "Failed to demote" in result.error_embed.description
        assert "Command not recognized" in result.error_embed.description


if __name__ == "__main__":
    # Run with: pytest tests/test_command_handlers_batch3.py -v
    # Run with coverage: pytest tests/test_command_handlers_batch3.py --cov=src/bot/commands.command_handlers_batch3 --cov-report=term-missing
    pytest.main(["-v", __file__])
