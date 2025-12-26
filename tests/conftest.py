
"""Pattern 11 Ops Excellence pytest configuration for real command harness tests.

This module provides:
- Async test markers with @pytest.mark.asyncio
- Type-safe session-level fixtures with explicit return types
- Comprehensive Type Contract documentation for all fixtures
- Event loop management for async tests
- Clean teardown and fixture isolation
- Real command invocation harness with dependency injection

All fixtures follow Pattern 11 standards:
✅ Explicit return type annotations (-> MagicMock)
✅ Type Contract documentation with method signatures
✅ AsyncMock enforcement for async methods
✅ Complete docstrings with usage examples
✅ Production-ready ops excellence
"""

from unittest.mock import MagicMock, AsyncMock
from typing import Generator, Dict, Any, Callable, Optional
from datetime import datetime
import sys
from pathlib import Path
import asyncio
import pytest
import discord

# Add src/ to Python path for absolute imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

pytest_plugins = ['pytest_asyncio']


def pytest_configure(config) -> None:
    """Configure pytest with async support.
    
    Registers the asyncio marker so tests can use @pytest.mark.asyncio
    to indicate async test functions.
    """
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (deselect with '-m \"not asyncio\"')"
    )


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests.
    
    This session-scoped fixture creates a single event loop for all async
    tests in the session, ensuring async test functions can be properly
    awaited and executed.
    
    Yields:
        asyncio.AbstractEventLoop: Event loop for async tests
        
    Cleanup:
        - Closes event loop after all tests complete
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ════════════════════════════════════════════════════════════════════════════
# MOCK FIXTURES FOR DISCRETE TESTS (Pattern 11 Type-Safe)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_bot() -> MagicMock:
    """Create a type-safe mock Discord bot with all required attributes.
    
    This fixture provides a comprehensive mock of the Discord bot including
    all managers, monitors, and integration points needed for testing.
    
    Returns:
        MagicMock: Mock adhering to DiscordBot contract
        
    Type Contract:
        - _connected: bool = True
        - user_context: MagicMock
          - get_user_server: Callable[[int], str] -> "prod"
          - get_server_display_name: Callable[[str], str] -> "Production"
          - get_rcon_for_user: Callable[[int], RconClient]
          - set_user_server: Callable[[int, str], None]
        - server_manager: MagicMock
          - list_tags: Callable[[], List[str]]
          - list_servers: Callable[[], Dict[str, Any]]
          - get_status_summary: Callable[[], Dict[str, Any]]
          - get_config: Callable[[], Config]
          - get_client: Callable[[], RconClient]
          - get_metrics_engine: Callable[[], MetricsEngine]
          - clients: Dict[str, RconClient]
        - rcon_monitor: MagicMock
          - rcon_server_states: Dict[str, Dict[str, Any]]
        - tree: MagicMock (discord command tree)
          - add_command: Callable[[Command], None]
    
    Coverage:
        - Happy path: all managers initialized
        - User context access patterns
        - Server manager integration points
        - RCON monitor state tracking
    """
    bot: MagicMock = MagicMock()
    
    # Bot state
    bot._connected: bool = True
    
    # User context manager
    bot.user_context: MagicMock = MagicMock()
    bot.user_context.get_user_server: Callable[[int], str] = MagicMock(return_value="prod")
    bot.user_context.get_server_display_name: Callable[[str], str] = MagicMock(return_value="Production")
    bot.user_context.get_rcon_for_user: Callable[[int], MagicMock] = MagicMock()
    bot.user_context.set_user_server: Callable[[int, str], None] = MagicMock()
    
    # Server manager (multi-server mode)
    bot.server_manager: MagicMock = MagicMock()
    bot.server_manager.list_tags: Callable[[], list] = MagicMock(return_value=[])
    bot.server_manager.list_servers: Callable[[], dict] = MagicMock(return_value={})
    bot.server_manager.get_status_summary: Callable[[], dict] = MagicMock(return_value={})
    bot.server_manager.get_config: Callable[[], MagicMock] = MagicMock()
    bot.server_manager.get_client: Callable[[], MagicMock] = MagicMock()
    bot.server_manager.get_metrics_engine: Callable[[], MagicMock] = MagicMock()
    bot.server_manager.clients: Dict[str, MagicMock] = {}
    
    # RCON monitor
    bot.rcon_monitor: MagicMock = MagicMock()
    bot.rcon_monitor.rcon_server_states: Dict[str, Dict[str, Any]] = {}
    
    # Discord tree (command registration)
    bot.tree: MagicMock = MagicMock()
    bot.tree.add_command: Callable[[Any], None] = MagicMock()
    
    return bot


@pytest.fixture
def mock_rcon_client() -> MagicMock:
    """Create a type-safe mock RCON client (connected state).
    
    This fixture provides a mock RCON client with async methods properly
    configured using AsyncMock for async/await support.
    
    Returns:
        MagicMock: Mock adhering to RconClient contract
        
    Type Contract:
        - is_connected: bool = True
        - execute: Callable[..., Awaitable[str]] (AsyncMock)
        - host: str = "localhost" (optional)
        - port: int = 27015 (optional)
        - disconnect: Callable[[], Awaitable[None]] (optional)
        - connect: Callable[[], Awaitable[None]] (optional)
    
    Coverage:
        - Happy path: client connected and responsive
        - Async method execution (execute)
        - Connection state tracking
    """
    client: MagicMock = MagicMock()
    
    # Connection state
    client.is_connected: bool = True
    
    # Async execute method
    client.execute: AsyncMock = AsyncMock(return_value="")
    
    return client


@pytest.fixture
def mock_interaction() -> MagicMock:
    """Create a type-safe mock Discord interaction.
    
    Provides a properly mocked discord.Interaction with all required
    async and sync methods for Discord slash command testing.
    
    Returns:
        MagicMock: Mock adhering to discord.Interaction contract
        
    Type Contract:
        - user: MagicMock
          - id: int = 123456789
          - name: str = "testuser"
        - response: MagicMock
          - send_message: Callable[..., Awaitable[None]] (AsyncMock)
          - defer: Callable[..., Awaitable[None]] (AsyncMock)
        - followup: MagicMock
          - send: Callable[..., Awaitable[None]] (AsyncMock)
        - user_id: int (property, for compatibility)
    
    Coverage:
        - User identification (id, name)
        - Response methods (send_message, defer)
        - Followup interactions
        - Proper async/await semantics
    """
    interaction: MagicMock = MagicMock(spec=discord.Interaction)
    
    # User information
    interaction.user: MagicMock = MagicMock()
    interaction.user.id: int = 123456789
    interaction.user.name: str = "testuser"
    
    # Response methods
    interaction.response: MagicMock = MagicMock()
    interaction.response.send_message: AsyncMock = AsyncMock()
    interaction.response.defer: AsyncMock = AsyncMock()
    
    # Followup methods
    interaction.followup: MagicMock = MagicMock()
    interaction.followup.send: AsyncMock = AsyncMock()
    
    return interaction


# ════════════════════════════════════════════════════════════════════════════
# PATTERN 11 VERIFICATION FIXTURES
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_user_context() -> MagicMock:
    """Create a type-safe user context provider mock.
    
    Returns:
        MagicMock: Mock adhering to UserContextProvider contract
        
    Type Contract:
        - get_user_server: Callable[[int], str]
        - get_server_display_name: Callable[[str], str]
        - get_rcon_for_user: Callable[[int], RconClient]
        - set_user_server: Callable[[int, str], None]
        - get_available_servers: Callable[[int], List[str]]
    
    Coverage:
        - User server lookup
        - Server name resolution
        - RCON client retrieval per user
    """
    context: MagicMock = MagicMock()
    context.get_user_server: Callable[[int], str] = MagicMock(return_value="default")
    context.get_server_display_name: Callable[[str], str] = MagicMock(return_value="Test Server")
    
    mock_rcon: MagicMock = MagicMock()
    mock_rcon.is_connected: bool = True
    context.get_rcon_for_user: Callable[[int], MagicMock] = MagicMock(return_value=mock_rcon)
    context.set_user_server: Callable[[int, str], None] = MagicMock()
    
    return context


@pytest.fixture
def mock_server_manager() -> MagicMock:
    """Create a type-safe server manager mock.
    
    Returns:
        MagicMock: Mock adhering to ServerManager contract
        
    Type Contract:
        - get_metrics_engine: Callable[[], MetricsEngine]
        - list_servers: Callable[[], Dict[str, Server]]
        - get_status_summary: Callable[[], Dict[str, Any]]
        - get_client: Callable[[str], RconClient]
    
    Coverage:
        - Metrics engine access
        - Server listing
        - Status aggregation
    """
    manager: MagicMock = MagicMock()
    
    metrics_engine: MagicMock = MagicMock()
    metrics_engine.gather_all_metrics: AsyncMock = AsyncMock(
        return_value={
            "ups": 60.0,
            "ups_sma": 59.5,
            "ups_ema": 59.8,
            "player_count": 2,
            "players": ["Player1", "Player2"],
            "evolution_by_surface": {"nauvis": 0.45},
            "is_paused": False,
        }
    )
    manager.get_metrics_engine: Callable[[], MagicMock] = MagicMock(return_value=metrics_engine)
    
    return manager


@pytest.fixture
def mock_cooldown() -> MagicMock:
    """Create a type-safe rate limiter mock (not limited).
    
    Returns:
        MagicMock: Mock adhering to RateLimiter contract
        
    Type Contract:
        - is_rate_limited: Callable[[int], Tuple[bool, Optional[float]]]
          Returns: (False, None) when not rate limited
    
    Coverage:
        - Happy path: rate limit check passes
    """
    cooldown: MagicMock = MagicMock()
    cooldown.is_rate_limited: Callable[[int], tuple] = MagicMock(
        return_value=(False, None)
    )
    return cooldown


@pytest.fixture
def mock_embed_builder() -> MagicMock:
    """Create a type-safe embed builder mock.
    
    Returns:
        MagicMock: Mock adhering to EmbedBuilderType contract
        
    Type Contract:
        - COLOR_SUCCESS: int = 0x00FF00 (green)
        - COLOR_WARNING: int = 0xFFAA00 (orange)
        - COLOR_ERROR: int = 0xFF0000 (red)
        - COLOR_INFO: int = 0x0099FF (blue)
        - COLOR_ADMIN: int = 0x9B59B6 (purple)
        - cooldown_embed: Callable[[Optional[float]], discord.Embed]
        - error_embed: Callable[[str], discord.Embed]
        - info_embed: Callable[[str, str], discord.Embed]
        - create_base_embed: Callable[[str, int], discord.Embed]
    
    Coverage:
        - Color constants for embed styling
        - Cooldown/rate limit embeds
        - Error message embeds
        - Info message embeds
        - Base embed creation
    """
    builder: MagicMock = MagicMock()
    
    # Color constants
    builder.COLOR_SUCCESS: int = 0x00FF00
    builder.COLOR_WARNING: int = 0xFFAA00
    builder.COLOR_ERROR: int = 0xFF0000
    builder.COLOR_INFO: int = 0x0099FF
    builder.COLOR_ADMIN: int = 0x9B59B6
    
    # Mock embed methods
    mock_embed = MagicMock(spec=discord.Embed)
    mock_embed.add_field = MagicMock()
    mock_embed.set_footer = MagicMock()
    mock_embed.color = builder.COLOR_INFO
    
    builder.cooldown_embed: Callable[[Optional[float]], MagicMock] = MagicMock(
        return_value=mock_embed
    )
    builder.error_embed: Callable[[str], MagicMock] = MagicMock(
        return_value=mock_embed
    )
    builder.info_embed: Callable[[str, str], MagicMock] = MagicMock(
        return_value=mock_embed
    )
    builder.create_base_embed: Callable[[str, int], MagicMock] = MagicMock(
        return_value=mock_embed
    )
    
    return builder


@pytest.fixture
def mock_rcon_monitor() -> MagicMock:
    """Create a type-safe RCON monitor mock.
    
    Returns:
        MagicMock: Mock adhering to RconMonitor contract
        
    Type Contract:
        - rcon_server_states: Dict[str, Dict[str, Any]]
          Format: {
            "server_name": {
              "last_connected": datetime,
              "connected": bool,
              "uptime": timedelta (optional)
            }
          }
        - get_uptime: Callable[[str], Optional[timedelta]]
        - record_connection: Callable[[str, bool], None]
    
    Coverage:
        - Server state tracking
        - Uptime calculation
        - Connection monitoring
    """
    monitor: MagicMock = MagicMock()
    monitor.rcon_server_states: Dict[str, Dict[str, Any]] = {
        "default": {
            "last_connected": datetime.now(),
            "connected": True,
        }
    }
    return monitor
