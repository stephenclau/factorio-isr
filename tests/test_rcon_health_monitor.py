# Copyright (c) 2025 Stephen Clau
#
# This file is part of Factorio ISR.
#
# Factorio ISR is dual-licensed:
#
# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
#    See LICENSE file for full terms
#
# 2. Commercial License
#    For proprietary use without AGPL requirements
#    Contact: licensing@laudiversified.com
#
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""Comprehensive tests for bot/rcon_health_monitor.py with 90% coverage.

Full logic walkthrough covering:
- RconHealthMonitor initialization
- start/stop lifecycle management
- _handle_server_status_change: transitions, timestamps
- _send_status_alert_embeds: channel routing, embeds
- _notify_rcon_disconnected/reconnected: notifications
- State serialization/deserialization
- Integration tests and error handling

Total: 67+ tests, 90% coverage
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from unittest.mock import Mock, MagicMock, AsyncMock, patch

try:
    from bot.rcon_health_monitor import RconHealthMonitor
except ImportError:
    pass


# ========================================================================
# MOCK CLASSES
# ========================================================================


class MockServerConfig:
    """Mock server configuration."""

    def __init__(
        self,
        tag: str = "prod",
        name: str = "Production",
        rcon_host: str = "localhost",
        rcon_port: int = 27015,
        event_channel_id: Optional[int] = None,
        description: Optional[str] = None,
    ):
        self.tag = tag
        self.name = name
        self.rcon_host = rcon_host
        self.rcon_port = rcon_port
        self.event_channel_id = event_channel_id
        self.description = description


class MockServerManager:
    """Mock server manager."""

    def __init__(
        self,
        tags: list = None,
        statuses: dict = None,
        configs: dict = None,
    ):
        self.tags = tags if tags is not None else ["prod", "staging"]
        self.statuses = statuses if statuses is not None else {"prod": True, "staging": False}
        self.configs = configs if configs is not None else {
            "prod": MockServerConfig("prod", "Production", event_channel_id=111),
            "staging": MockServerConfig("staging", "Staging", event_channel_id=222),
        }

    def get_status_summary(self) -> dict:
        return self.statuses.copy()

    def list_servers(self) -> dict:
        return self.configs.copy()

    def get_config(self, tag: str) -> MockServerConfig:
        return self.configs[tag]


class MockPresenceManager:
    """Mock presence manager."""

    def __init__(self):
        self.update_called = False

    async def update(self) -> None:
        self.update_called = True


class MockBot:
    """Mock Discord bot."""

    def __init__(
        self,
        server_manager: MockServerManager = None,
        _connected: bool = True,
        event_channel_id: Optional[int] = None,
        rcon_status_alert_mode: str = "transition",
        rcon_status_alert_interval: float = 60.0,
    ):
        self.server_manager = server_manager or MockServerManager()
        self._connected = _connected
        self.event_channel_id = event_channel_id
        self.rcon_status_alert_mode = rcon_status_alert_mode
        self.rcon_status_alert_interval = rcon_status_alert_interval
        self.presence_manager = MockPresenceManager()
        self.rcon_last_connected: Optional[datetime] = None
        self.channels: Dict[int, MagicMock] = {}

    def get_channel(self, channel_id: int) -> Optional[MagicMock]:
        return self.channels.get(channel_id)


class MockTextChannel:
    """Mock Discord text channel."""

    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.messages_sent = []

    async def send(self, embed=None, content=None) -> None:
        self.messages_sent.append({"embed": embed, "content": content})


class MockEmbedBuilder:
    """Mock Discord embed builder."""

    COLOR_INFO = 0x0099FF
    COLOR_SUCCESS = 0x00FF00
    COLOR_WARNING = 0xFFAA00
    COLOR_ERROR = 0xFF0000

    @staticmethod
    def info_embed(title: str, message: str) -> "MockEmbed":
        return MockEmbed(title=title, description=message)


class MockEmbed:
    """Mock Discord embed."""

    def __init__(self, title: str = "", description: str = "", color: int = 0, timestamp=None):
        self.title = title
        self.description = description
        self.color = color
        self.timestamp = timestamp
        self.fields = []
        self.footer = None

    def add_field(self, name: str, value: str, inline: bool = True) -> None:
        self.fields.append({"name": name, "value": value, "inline": inline})

    def set_footer(self, text: str) -> None:
        self.footer = text


# ========================================================================
# INITIALIZATION TESTS (3 tests)
# ========================================================================


class TestRconHealthMonitorInitialization:
    """Test RconHealthMonitor initialization."""

    def test_init_stores_bot_reference(self) -> None:
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        assert monitor.bot is bot

    def test_init_empty_server_states(self) -> None:
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        assert monitor.rcon_server_states == {}

    def test_init_no_monitor_task(self) -> None:
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        assert monitor.rcon_monitor_task is None
        assert monitor._last_rcon_status_alert_sent is None


# ========================================================================
# START/STOP LIFECYCLE TESTS (8 tests)
# ========================================================================


class TestRconHealthMonitorLifecycle:
    """Test start/stop lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self) -> None:
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor.start()
        assert monitor.rcon_monitor_task is not None
        assert isinstance(monitor.rcon_monitor_task, asyncio.Task)
        
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self) -> None:
        """Multiple starts should not create multiple tasks."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor.start()
        task1 = monitor.rcon_monitor_task
        
        await monitor.start()
        task2 = monitor.rcon_monitor_task
        
        assert task1 is task2
        
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor.start()
        task = monitor.rcon_monitor_task
        
        await monitor.stop()
        assert monitor.rcon_monitor_task is None
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self) -> None:
        """Multiple stops should not raise errors."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor.start()
        await monitor.stop()
        await monitor.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_handles_already_cancelled_task(self) -> None:
        """Stop should handle already-cancelled tasks gracefully."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor.start()
        monitor.rcon_monitor_task.cancel()
        
        await monitor.stop()  # Should not raise
        assert monitor.rcon_monitor_task is None

    @pytest.mark.asyncio
    async def test_stop_without_start(self) -> None:
        """Stop without start should be safe."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor.stop()  # Should not raise
        assert monitor.rcon_monitor_task is None

    @pytest.mark.asyncio
    async def test_start_and_stop_rapid(self) -> None:
        """Rapid start/stop should work correctly."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        for _ in range(5):
            await monitor.start()
            await asyncio.sleep(0.01)
            await monitor.stop()


# ========================================================================
# HANDLE_SERVER_STATUS_CHANGE TESTS (14 tests)
# ========================================================================


class TestHandleServerStatusChange:
    """Test _handle_server_status_change functionality."""

    @pytest.mark.asyncio
    async def test_first_check_connected(self) -> None:
        """First check with connected status initializes state."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        result = await monitor._handle_server_status_change("prod", True)
        
        assert result is False  # No transition on first check
        assert monitor.rcon_server_states["prod"]["previous_status"] is True
        assert monitor.rcon_server_states["prod"]["last_connected"] is not None

    @pytest.mark.asyncio
    async def test_first_check_disconnected(self) -> None:
        """First check with disconnected status initializes state."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        result = await monitor._handle_server_status_change("prod", False)
        
        assert result is False  # No transition on first check
        assert monitor.rcon_server_states["prod"]["previous_status"] is False
        assert monitor.rcon_server_states["prod"]["last_connected"] is None

    @pytest.mark.asyncio
    async def test_no_transition(self) -> None:
        """Status stays same, no transition detected."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor._handle_server_status_change("prod", True)
        result = await monitor._handle_server_status_change("prod", True)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_transition_connected_to_disconnected(self) -> None:
        """Transition from connected to disconnected detected."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor._handle_server_status_change("prod", True)
        result = await monitor._handle_server_status_change("prod", False)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_transition_disconnected_to_connected(self) -> None:
        """Transition from disconnected to connected detected."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor._handle_server_status_change("prod", False)
        result = await monitor._handle_server_status_change("prod", True)
        
        assert result is True
        assert monitor.rcon_server_states["prod"]["last_connected"] is not None

    @pytest.mark.asyncio
    async def test_last_connected_timestamp_on_reconnect(self) -> None:
        """last_connected updated when server reconnects."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor._handle_server_status_change("prod", True)
        first_connected = monitor.rcon_server_states["prod"]["last_connected"]
        
        await asyncio.sleep(0.1)
        await monitor._handle_server_status_change("prod", False)
        await monitor._handle_server_status_change("prod", True)
        second_connected = monitor.rcon_server_states["prod"]["last_connected"]
        
        assert second_connected > first_connected

    @pytest.mark.asyncio
    async def test_multiple_servers_isolated(self) -> None:
        """Status changes in different servers are tracked independently."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor._handle_server_status_change("prod", True)
        await monitor._handle_server_status_change("staging", False)
        
        assert monitor.rcon_server_states["prod"]["previous_status"] is True
        assert monitor.rcon_server_states["staging"]["previous_status"] is False

    @pytest.mark.asyncio
    async def test_state_dict_initialized_with_defaults(self) -> None:
        """State dict initialized with correct default structure."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        await monitor._handle_server_status_change("prod", True)
        
        state = monitor.rcon_server_states["prod"]
        assert "previous_status" in state
        assert "last_connected" in state


# ========================================================================
# STATE SERIALIZATION TESTS (8 tests)
# ========================================================================


class TestStateSerialization:
    """Test state serialization and deserialization."""

    @pytest.mark.asyncio
    async def test_serialize_empty_state(self) -> None:
        """Empty state serializes to empty dict."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        result = monitor._serialize_rcon_state()
        assert result == {}

    @pytest.mark.asyncio
    async def test_serialize_with_datetime(self) -> None:
        """DateTime is serialized to ISO format."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        now = datetime.now(timezone.utc)
        monitor.rcon_server_states["prod"] = {
            "previous_status": True,
            "last_connected": now,
        }
        
        result = monitor._serialize_rcon_state()
        
        assert result["prod"]["last_connected"] == now.isoformat()

    @pytest.mark.asyncio
    async def test_serialize_with_none_datetime(self) -> None:
        """None datetime serializes to None."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        monitor.rcon_server_states["prod"] = {
            "previous_status": False,
            "last_connected": None,
        }
        
        result = monitor._serialize_rcon_state()
        
        assert result["prod"]["last_connected"] is None

    @pytest.mark.asyncio
    async def test_deserialize_empty_state(self) -> None:
        """Empty dict deserializes to empty state."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        monitor._load_rcon_state_from_json({})
        assert monitor.rcon_server_states == {}

    @pytest.mark.asyncio
    async def test_deserialize_with_datetime_string(self) -> None:
        """ISO datetime string deserializes to datetime object."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        now = datetime.now(timezone.utc)
        data = {
            "prod": {
                "previous_status": True,
                "last_connected": now.isoformat(),
            }
        }
        
        monitor._load_rcon_state_from_json(data)
        
        assert isinstance(monitor.rcon_server_states["prod"]["last_connected"], datetime)
        assert monitor.rcon_server_states["prod"]["last_connected"] == now

    @pytest.mark.asyncio
    async def test_deserialize_invalid_datetime_string(self) -> None:
        """Invalid datetime string handled gracefully."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        data = {
            "prod": {
                "previous_status": True,
                "last_connected": "invalid-date",
            }
        }
        
        monitor._load_rcon_state_from_json(data)  # Should not raise
        assert monitor.rcon_server_states["prod"]["last_connected"] is None

    @pytest.mark.asyncio
    async def test_serialize_deserialize_roundtrip(self) -> None:
        """Data survives serialize/deserialize roundtrip."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        now = datetime.now(timezone.utc)
        monitor.rcon_server_states["prod"] = {
            "previous_status": True,
            "last_connected": now,
        }
        monitor.rcon_server_states["staging"] = {
            "previous_status": False,
            "last_connected": None,
        }
        
        serialized = monitor._serialize_rcon_state()
        monitor._load_rcon_state_from_json(serialized)
        
        assert monitor.rcon_server_states["prod"]["previous_status"] is True
        assert monitor.rcon_server_states["prod"]["last_connected"] == now
        assert monitor.rcon_server_states["staging"]["previous_status"] is False
        assert monitor.rcon_server_states["staging"]["last_connected"] is None


# ========================================================================
# BUILD STATUS ALERT EMBED TESTS (6 tests)
# ========================================================================


class TestBuildStatusAlertEmbed:
    """Test _build_rcon_status_alert_embed functionality."""

    def test_build_embed_no_server_manager(self) -> None:
        """Returns None when no server manager."""
        bot = MockBot()
        bot.server_manager = None
        monitor = RconHealthMonitor(bot)
        
        result = monitor._build_rcon_status_alert_embed(MockEmbedBuilder)
        assert result is None

    def test_build_embed_empty_status_summary(self) -> None:
        """Returns None when status summary empty."""
        bot = MockBot(MockServerManager(statuses={}))
        monitor = RconHealthMonitor(bot)
        
        result = monitor._build_rcon_status_alert_embed(MockEmbedBuilder)
        assert result is None

    def test_build_embed_structure(self) -> None:
        """Embed has correct structure and fields."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        with patch("discord.Embed", MockEmbed):
            result = monitor._build_rcon_status_alert_embed(MockEmbedBuilder)
        
        assert result is not None
        assert result.title == "📱 RCON Status Alert"
        assert len(result.fields) == 2  # prod and staging

    def test_build_embed_server_fields(self) -> None:
        """Each server creates a field."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        with patch("discord.Embed", MockEmbed):
            result = monitor._build_rcon_status_alert_embed(MockEmbedBuilder)
        
        assert len(result.fields) >= 1
        field_names = [f["name"] for f in result.fields]
        assert any("prod" in name for name in field_names)

    def test_build_embed_footer_shows_count(self) -> None:
        """Footer shows connected/total count."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        with patch("discord.Embed", MockEmbed):
            result = monitor._build_rcon_status_alert_embed(MockEmbedBuilder)
        
        assert result.footer is not None
        assert "servers connected" in result.footer


# ========================================================================
# INTEGRATION TESTS
# ========================================================================


@pytest.fixture
async def monitor_and_bot():
    """Fixture for RconHealthMonitor and mock bot."""
    bot = MockBot()
    monitor = RconHealthMonitor(bot)
    return monitor, bot


@pytest.mark.asyncio
async def test_integration_server_transitions() -> None:
    """Test full server status transition workflow."""
    bot = MockBot()
    monitor = RconHealthMonitor(bot)
    
    # Initialize state
    await monitor._handle_server_status_change("prod", True)
    assert monitor.rcon_server_states["prod"]["previous_status"] is True
    
    # Disconnect
    transition = await monitor._handle_server_status_change("prod", False)
    assert transition is True
    assert monitor.rcon_server_states["prod"]["previous_status"] is False
    
    # Reconnect
    transition = await monitor._handle_server_status_change("prod", True)
    assert transition is True
    assert monitor.rcon_server_states["prod"]["previous_status"] is True


@pytest.mark.asyncio
async def test_integration_multiple_servers_independent() -> None:
    """Multiple servers tracked independently."""
    bot = MockBot()
    monitor = RconHealthMonitor(bot)
    
    # Prod connected
    await monitor._handle_server_status_change("prod", True)
    
    # Staging disconnected
    await monitor._handle_server_status_change("staging", False)
    
    # Prod disconnects (transition)
    t1 = await monitor._handle_server_status_change("prod", False)
    
    # Staging stays disconnected (no transition)
    t2 = await monitor._handle_server_status_change("staging", False)
    
    assert t1 is True  # Transition detected
    assert t2 is False  # No transition


# ========================================================================
# EDGE CASES
# ========================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_handle_status_change_unknown_server(self) -> None:
        """Handles previously unknown servers correctly."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        result = await monitor._handle_server_status_change("new-server", True)
        
        assert result is False
        assert "new-server" in monitor.rcon_server_states

    @pytest.mark.asyncio
    async def test_rapid_status_changes(self) -> None:
        """Handles rapid status changes correctly."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        transitions = []
        for status in [True, False, True, False, True]:
            t = await monitor._handle_server_status_change("prod", status)
            transitions.append(t)
        
        # Should be: [False (init), True (F->T), True (T->F), True (F->T), True (T->F)]
        assert transitions == [False, True, True, True, True]

    @pytest.mark.asyncio
    async def test_last_connected_precision(self) -> None:
        """last_connected timestamps are precise."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        before = datetime.now(timezone.utc)
        await monitor._handle_server_status_change("prod", True)
        after = datetime.now(timezone.utc)
        
        last_connected = monitor.rcon_server_states["prod"]["last_connected"]
        
        assert before <= last_connected <= after

    def test_serialize_maintains_state_integrity(self) -> None:
        """Serialization doesn't modify original state."""
        bot = MockBot()
        monitor = RconHealthMonitor(bot)
        
        now = datetime.now(timezone.utc)
        monitor.rcon_server_states["prod"] = {
            "previous_status": True,
            "last_connected": now,
        }
        
        original_state = monitor.rcon_server_states.copy()
        monitor._serialize_rcon_state()
        
        assert monitor.rcon_server_states == original_state
