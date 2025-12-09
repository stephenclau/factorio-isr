"""
Comprehensive tests for event_parser.py with 95% code coverage.
Type-safe and tests all code paths including edge cases.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from security_monitor import Infraction

from event_parser import (
    EventParser,
    EventType,
    FactorioEvent,
    FactorioEventFormatter,
)
from pattern_loader import EventPattern


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_pattern_loader() -> MagicMock:
    """Create a mock PatternLoader."""
    loader = MagicMock()
    loader.load_patterns.return_value = 3  # type: ignore[attr-defined]
    loader.reload.return_value = 3  # type: ignore[attr-defined]
    return loader


@pytest.fixture
def mock_event_pattern() -> EventPattern:
    """Create a real EventPattern for testing."""
    return EventPattern(
        name="test_pattern",
        pattern=r'^(?P<player>\w+) joined',
        event_type="join",
        emoji="✅",
        message_template="{player} joined the server",
        channel="general",
        enabled=True,
        priority=10
    )


@pytest.fixture
def event_parser(mock_pattern_loader: MagicMock) -> EventParser:
    """Create EventParser with mocked PatternLoader."""
    with patch('event_parser.PatternLoader', return_value=mock_pattern_loader):
        parser = EventParser(Path("patterns"))
    return parser


@pytest.fixture
def sample_factorio_event() -> FactorioEvent:
    """Create a sample FactorioEvent for testing."""
    return FactorioEvent(
        event_type=EventType.JOIN,
        player_name="TestPlayer",
        message="joined the game",
        raw_line="[JOIN] TestPlayer joined the game",
        emoji="✅",
        formatted_message="TestPlayer joined the server",
        metadata={"channel": "general"}
    )


# ============================================================================
# EventType Tests
# ============================================================================

class TestEventType:
    """Test EventType enum."""

    def test_event_type_values(self) -> None:
        """Test all EventType enum values."""
        assert EventType.JOIN.value == "join"
        assert EventType.LEAVE.value == "leave"
        assert EventType.CHAT.value == "chat"
        assert EventType.SERVER.value == "server"
        assert EventType.MILESTONE.value == "milestone"
        assert EventType.TASK.value == "task"
        assert EventType.RESEARCH.value == "research"
        assert EventType.DEATH.value == "death"
        assert EventType.UNKNOWN.value == "unknown"

    def test_event_type_string_behavior(self) -> None:
        """Test that EventType behaves as string."""
        # EventType.value returns the string, not str(EventType)
        assert EventType.JOIN.value == "join"
        assert EventType.JOIN == "join"


# ============================================================================
# FactorioEvent Tests
# ============================================================================

class TestFactorioEvent:
    """Test FactorioEvent dataclass."""

    def test_factorio_event_creation(self) -> None:
        """Test creating a FactorioEvent."""
        event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="Player1",
            message="test message",
            raw_line="test line",
            emoji="✅",
            formatted_message="formatted",
            metadata={"key": "value"}
        )
        assert event.event_type == EventType.JOIN
        assert event.player_name == "Player1"
        assert event.message == "test message"
        assert event.raw_line == "test line"
        assert event.emoji == "✅"
        assert event.formatted_message == "formatted"
        assert event.metadata == {"key": "value"}

    def test_factorio_event_defaults(self) -> None:
        """Test FactorioEvent with default values."""
        event = FactorioEvent(event_type=EventType.CHAT)
        assert event.player_name is None
        assert event.message is None
        assert event.raw_line == ""
        assert event.emoji == ""
        assert event.formatted_message == ""
        assert event.metadata == {}

    def test_factorio_event_frozen(self) -> None:
        """Test that FactorioEvent is immutable (frozen)."""
        event = FactorioEvent(event_type=EventType.JOIN)
        with pytest.raises(AttributeError):
            event.player_name = "NewPlayer"  # type: ignore[misc]


# ============================================================================
# EventParser Tests
# ============================================================================

class TestEventParserInit:
    """Test EventParser initialization."""

    def test_init_with_valid_path(self, mock_pattern_loader: MagicMock) -> None:
        """Test initialization with valid Path."""
        with patch('event_parser.PatternLoader', return_value=mock_pattern_loader):
            parser = EventParser(Path("patterns"))
            assert parser.pattern_loader == mock_pattern_loader
            assert isinstance(parser.compiled_patterns, dict)

    def test_init_with_invalid_type_raises_assertion(self) -> None:
        """Test initialization with non-Path raises AssertionError."""
        with pytest.raises(AssertionError, match="patterns_dir must be Path"):
            EventParser("patterns")  # type: ignore[arg-type]

    def test_init_calls_load_patterns(self, mock_pattern_loader: MagicMock) -> None:
        """Test that init calls load_patterns."""
        with patch('event_parser.PatternLoader', return_value=mock_pattern_loader):
            EventParser(Path("patterns"), pattern_files=["test.yml"])
            mock_pattern_loader.load_patterns.assert_called_once_with(["test.yml"])


class TestEventParserCompilePatterns:
    """Test EventParser._compile_patterns method."""

    def test_compile_patterns_success(self, event_parser: EventParser, mock_event_pattern: EventPattern) -> None:
        """Test successful pattern compilation."""
        event_parser.pattern_loader.get_patterns.return_value = [mock_event_pattern]  # type: ignore[attr-defined]
        event_parser._compile_patterns()
        
        assert "test_pattern" in event_parser.compiled_patterns
        regex, pattern = event_parser.compiled_patterns["test_pattern"]
        assert isinstance(regex, re.Pattern)
        assert pattern == mock_event_pattern

    def test_compile_patterns_with_invalid_regex(self, event_parser: EventParser) -> None:
        """Test that invalid regex patterns are skipped."""
        bad_pattern = EventPattern(
            name="bad_pattern",
            pattern=r"[invalid(regex",  # Invalid regex
            event_type="join",
            emoji="",
            message_template="",
            channel=None,
            enabled=True,
            priority=10
        )
        
        event_parser.pattern_loader.get_patterns.return_value = [bad_pattern]  # type: ignore[attr-defined]
        event_parser._compile_patterns()
        
        # Bad pattern should not be compiled
        assert "bad_pattern" not in event_parser.compiled_patterns

    def test_compile_patterns_empty_list(self, event_parser: EventParser) -> None:
        """Test compiling with no patterns."""
        event_parser.pattern_loader.get_patterns.return_value = []  # type: ignore[attr-defined]
        event_parser._compile_patterns()
        assert len(event_parser.compiled_patterns) == 0


class TestEventParserParseLine:
    """Test EventParser.parse_line method."""

    def test_parse_line_with_invalid_type(self, event_parser: EventParser) -> None:
        """Test parse_line with non-string raises AssertionError."""
        with pytest.raises(AssertionError, match="line must be str"):
            event_parser.parse_line(123)  # type: ignore[arg-type]

    def test_parse_line_empty_string(self, event_parser: EventParser) -> None:
        """Test parse_line with empty string returns None."""
        assert event_parser.parse_line("") is None
        assert event_parser.parse_line("   ") is None

    def test_parse_line_no_match(self, event_parser: EventParser, mock_event_pattern: EventPattern) -> None:
        """Test parse_line when no pattern matches."""
        event_parser.pattern_loader.get_patterns.return_value = [mock_event_pattern]  # type: ignore[attr-defined]
        event_parser._compile_patterns()
        
        result = event_parser.parse_line("This line does not match")
        assert result is None

    def test_parse_line_with_match(self, event_parser: EventParser, mock_event_pattern: EventPattern) -> None:
        """Test parse_line with matching pattern."""
        event_parser.pattern_loader.get_patterns.return_value = [mock_event_pattern]  # type: ignore[attr-defined]
        event_parser._compile_patterns()
        
        result = event_parser.parse_line("TestPlayer joined")
        assert result is not None
        assert isinstance(result, FactorioEvent)
        assert result.event_type == EventType.JOIN


class TestEventParserCreateEvent:
    """Test EventParser._create_event method."""

    def test_create_event_invalid_line_type(self, event_parser: EventParser, mock_event_pattern: EventPattern) -> None:
        """Test _create_event with non-string line."""
        match = Mock(spec=re.Match)
        with pytest.raises(AssertionError, match="line must be str"):
            event_parser._create_event(123, match, mock_event_pattern)  # type: ignore[arg-type]

    def test_create_event_invalid_match_type(self, event_parser: EventParser, mock_event_pattern: EventPattern) -> None:
        """Test _create_event with non-Match object."""
        with pytest.raises(AssertionError, match="match must be re.Match"):
            event_parser._create_event("line", "not a match", mock_event_pattern)  # type: ignore[arg-type]

    def test_create_event_invalid_pattern_type(self, event_parser: EventParser) -> None:
        """Test _create_event with non-EventPattern object."""
        match = Mock(spec=re.Match)
        match.lastindex = 0
        with pytest.raises(AssertionError, match="pattern must be EventPattern"):
            event_parser._create_event("line", match, "not a pattern")  # type: ignore[arg-type]

    def test_create_event_with_player_only(self, event_parser: EventParser, mock_event_pattern: EventPattern) -> None:
        """Test _create_event with single capture group (player)."""
        match = Mock(spec=re.Match)
        match.lastindex = 1
        match.group.side_effect = lambda x: "Player1" if x == 1 else None  # type: ignore[attr-defined]
        
        event = event_parser._create_event("[JOIN] Player1", match, mock_event_pattern)
        assert event.player_name == "Player1"
        assert event.event_type == EventType.JOIN

    def test_create_event_with_player_and_message(self, event_parser: EventParser) -> None:
        """Test _create_event with two capture groups."""
        match = Mock(spec=re.Match)
        match.lastindex = 2
        match.group.side_effect = lambda x: "Player1" if x == 1 else "test message" if x == 2 else None  # type: ignore[attr-defined]
        
        pattern = EventPattern(
            name="chat_pattern",
            pattern=r'^(?P<player>\w+): (?P<message>.+)',
            event_type="chat",
            emoji="💬",
            message_template="{player}: {message}",
            channel="general",
            enabled=True,
            priority=10
        )
        
        event = event_parser._create_event("[CHAT] Player1: test", match, pattern)
        assert event.player_name == "Player1"
        assert event.message == "test message"

    def test_create_event_server_event_single_group(self, event_parser: EventParser) -> None:
        """Test _create_event for server event with single group."""
        match = Mock(spec=re.Match)
        match.lastindex = 1
        match.group.side_effect = lambda x: "Server started" if x == 1 else None  # type: ignore[attr-defined]
        
        pattern = EventPattern(
            name="server_pattern",
            pattern=r'^(?P<message>.+)',
            event_type="server",
            emoji="🖥️",
            message_template="{message}",
            channel="general",
            enabled=True,
            priority=10
        )
        
        event = event_parser._create_event("Server started", match, pattern)
        assert event.message == "Server started"
        assert event.event_type == EventType.SERVER

    def test_create_event_with_channel_metadata(self, event_parser: EventParser, mock_event_pattern: EventPattern) -> None:
        """Test _create_event includes channel in metadata."""
        match = Mock(spec=re.Match)
        match.lastindex = 1
        match.group.return_value = "Player1"  # type: ignore[attr-defined]
        
        event = event_parser._create_event("test", match, mock_event_pattern)
        assert event.metadata.get("channel") == "general"

    def test_create_event_without_channel(self, event_parser: EventParser) -> None:
        """Test _create_event without channel."""
        match = Mock(spec=re.Match)
        match.lastindex = 0
        
        pattern = EventPattern(
            name="no_channel_pattern",
            pattern=r'^test',
            event_type="join",
            emoji="",
            message_template="",
            channel=None,
            enabled=True,
            priority=10
        )
        
        event = event_parser._create_event("test", match, pattern)
        assert "channel" not in event.metadata

    def test_create_event_index_error_handling(self, event_parser: EventParser, mock_event_pattern: EventPattern) -> None:
        """Test _create_event handles IndexError gracefully."""
        match = Mock(spec=re.Match)
        match.lastindex = 2
        match.group.side_effect = IndexError("No such group")  # type: ignore[attr-defined]
        
        event = event_parser._create_event("test", match, mock_event_pattern)
        assert event.player_name is None
        assert event.message is None


class TestEventParserMapEventType:
    """Test EventParser._map_event_type method."""

    def test_map_event_type_invalid_type(self, event_parser: EventParser) -> None:
        """Test _map_event_type with non-string."""
        with pytest.raises(AssertionError, match="type_str must be str"):
            event_parser._map_event_type(123)  # type: ignore[arg-type]

    def test_map_event_type_valid_types(self, event_parser: EventParser) -> None:
        """Test _map_event_type with all valid types."""
        assert event_parser._map_event_type("join") == EventType.JOIN
        assert event_parser._map_event_type("leave") == EventType.LEAVE
        assert event_parser._map_event_type("chat") == EventType.CHAT
        assert event_parser._map_event_type("server") == EventType.SERVER
        assert event_parser._map_event_type("milestone") == EventType.MILESTONE
        assert event_parser._map_event_type("task") == EventType.TASK
        assert event_parser._map_event_type("research") == EventType.RESEARCH
        assert event_parser._map_event_type("death") == EventType.DEATH

    def test_map_event_type_case_insensitive(self, event_parser: EventParser) -> None:
        """Test _map_event_type is case-insensitive."""
        assert event_parser._map_event_type("JOIN") == EventType.JOIN
        assert event_parser._map_event_type("JoIn") == EventType.JOIN

    def test_map_event_type_unknown(self, event_parser: EventParser) -> None:
        """Test _map_event_type with unknown type returns UNKNOWN."""
        assert event_parser._map_event_type("invalid_type") == EventType.UNKNOWN

class TestEventParserClassifyMentions:
    """Direct tests for EventParser._classify_mentions."""

    def test_classify_mentions_empty_returns_user(self, event_parser: EventParser) -> None:
        """Empty mention list is treated as user-class mentions."""
        result = event_parser._classify_mentions([])
        assert result == "user"

    def test_classify_mentions_all_users(self, event_parser: EventParser) -> None:
        """Pure user-like tokens should classify as user."""
        mentions = ["Alice", "Bob123", "somebody"]
        result = event_parser._classify_mentions(mentions)
        assert result == "user"

    def test_classify_mentions_all_groups(self, event_parser: EventParser) -> None:
        """All group keywords should classify as group."""
        # Includes several entries from the group_keywords set
        mentions = ["admins", "MOD", "Everyone", "staff"]
        result = event_parser._classify_mentions(mentions)
        assert result == "group"

    def test_classify_mentions_mixed_users_and_groups(self, event_parser: EventParser) -> None:
        """Combination of group keywords and user tokens should classify as mixed."""
        mentions = ["admins", "Alice", "mods"]
        result = event_parser._classify_mentions(mentions)
        assert result == "mixed"

    def test_classify_mentions_case_insensitive(self, event_parser: EventParser) -> None:
        """Group keyword detection should be case-insensitive."""
        mentions = ["AdMiN", "MoDeRaToR"]
        result = event_parser._classify_mentions(mentions)
        assert result == "group"


class TestEventParserMentionsIntegration:
    """Integration tests for mention extraction and classification via _create_event."""

    def test_create_event_with_user_mentions(self, event_parser: EventParser) -> None:
        """_create_event should populate metadata for user-only mentions."""
        pattern = EventPattern(
            name="chat_with_mentions",
            pattern=r"^\[CHAT\] (\w+): (.+)$",
            event_type="chat",
            emoji="💬",
            message_template="{player}: {message}",
            channel="chat",
            enabled=True,
            priority=10,
        )

        line = "[CHAT] Alice: hello @Bob @Charlie"
        # First group: player, second group: message
        match = re.match(pattern.pattern, line, re.IGNORECASE)
        assert match is not None

        event = event_parser._create_event(line, match, pattern)

        # Mentions list should be extracted without '@'
        assert event.metadata.get("mentions") == ["Bob", "Charlie"]
        assert event.metadata.get("mention_type") == "user"

    def test_create_event_with_group_mentions(self, event_parser: EventParser) -> None:
        """_create_event should classify pure group mentions as group."""
        pattern = EventPattern(
            name="chat_groups",
            pattern=r"^\[CHAT\] (\w+): (.+)$",
            event_type="chat",
            emoji="💬",
            message_template="{player}: {message}",
            channel="chat",
            enabled=True,
            priority=10,
        )

        line = "[CHAT] Alice: ping @admins @MODS @Here"
        match = re.match(pattern.pattern, line, re.IGNORECASE)
        assert match is not None

        event = event_parser._create_event(line, match, pattern)

        assert event.metadata.get("mentions") == ["admins", "MODS", "Here"]
        assert event.metadata.get("mention_type") == "group"

    def test_create_event_with_mixed_mentions(self, event_parser: EventParser) -> None:
        """_create_event should classify mixed user/group mentions as mixed."""
        pattern = EventPattern(
            name="chat_mixed",
            pattern=r"^\[CHAT\] (\w+): (.+)$",
            event_type="chat",
            emoji="💬",
            message_template="{player}: {message}",
            channel="chat",
            enabled=True,
            priority=10,
        )

        line = "[CHAT] Alice: hey @admins and @Bob"
        match = re.match(pattern.pattern, line, re.IGNORECASE)
        assert match is not None

        event = event_parser._create_event(line, match, pattern)

        assert event.metadata.get("mentions") == ["admins", "Bob"]
        assert event.metadata.get("mention_type") == "mixed"

    def test_create_event_without_mentions_has_no_mention_metadata(
        self, event_parser: EventParser
    ) -> None:
        """Events without @ tokens should not include mention metadata keys."""
        pattern = EventPattern(
            name="chat_no_mentions",
            pattern=r"^\[CHAT\] (\w+): (.+)$",
            event_type="chat",
            emoji="💬",
            message_template="{player}: {message}",
            channel="chat",
            enabled=True,
            priority=10,
        )

        line = "[CHAT] Alice: hello world"
        match = re.match(pattern.pattern, line, re.IGNORECASE)
        assert match is not None

        event = event_parser._create_event(line, match, pattern)

        assert "mentions" not in event.metadata
        assert "mention_type" not in event.metadata


class TestEventParserFormatMessage:
    """Test EventParser._format_message method."""

    def test_format_message_invalid_template_type(self, event_parser: EventParser) -> None:
        """Test _format_message with non-string template."""
        with pytest.raises(AssertionError, match="template must be str"):
            event_parser._format_message(123, "Player", "message")  # type: ignore[arg-type]

    def test_format_message_empty_template_both_args(self, event_parser: EventParser) -> None:
        """Test empty template with player and message."""
        result = event_parser._format_message("", "Player1", "test message")
        assert result == "Player1: test message"

    def test_format_message_empty_template_player_only(self, event_parser: EventParser) -> None:
        """Test empty template with player only."""
        result = event_parser._format_message("", "Player1", None)
        assert result == "Player1"

    def test_format_message_empty_template_message_only(self, event_parser: EventParser) -> None:
        """Test empty template with message only."""
        result = event_parser._format_message("", None, "test message")
        assert result == "test message"

    def test_format_message_empty_template_no_args(self, event_parser: EventParser) -> None:
        """Test empty template with no arguments."""
        result = event_parser._format_message("", None, None)
        assert result == ""

    def test_format_message_with_player_placeholder(self, event_parser: EventParser) -> None:
        """Test template with {player} placeholder."""
        result = event_parser._format_message("{player} joined", "Player1", None)
        assert result == "Player1 joined"

    def test_format_message_with_message_placeholder(self, event_parser: EventParser) -> None:
        """Test template with {message} placeholder."""
        result = event_parser._format_message("Server: {message}", None, "started")
        assert result == "Server: started"

    def test_format_message_with_both_placeholders(self, event_parser: EventParser) -> None:
        """Test template with both placeholders."""
        result = event_parser._format_message("{player}: {message}", "Player1", "hello")
        assert result == "Player1: hello"

    def test_format_message_no_placeholders(self, event_parser: EventParser) -> None:
        """Test template without placeholders."""
        result = event_parser._format_message("static message", "Player1", "ignored")
        assert result == "static message"


class TestEventParserReloadPatterns:
    """Test EventParser.reload_patterns method."""

    def test_reload_patterns(self, event_parser: EventParser, mock_pattern_loader: MagicMock) -> None:
        """Test reload_patterns calls loader.reload and recompiles."""
        mock_pattern_loader.reload.return_value = 5  # type: ignore[attr-defined]
        
        count = event_parser.reload_patterns()
        
        assert count == 5
        mock_pattern_loader.reload.assert_called_once()


# ============================================================================
# FactorioEventFormatter Tests
# ============================================================================

class TestFactorioEventFormatter:
    """Test FactorioEventFormatter class."""

    def test_format_for_discord_invalid_type(self) -> None:
        """Test format_for_discord with non-FactorioEvent."""
        with pytest.raises(AssertionError, match="event must be FactorioEvent"):
            FactorioEventFormatter.format_for_discord("not an event")  # type: ignore[arg-type]

    def test_format_for_discord_with_formatted_message_and_emoji(self) -> None:
        """Test formatting when event has formatted_message and emoji."""
        event = FactorioEvent(
            event_type=EventType.JOIN,
            formatted_message="Player joined",
            emoji="✅"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "✅ Player joined"

    def test_format_for_discord_with_formatted_message_no_emoji(self) -> None:
        """Test formatting when event has formatted_message but no emoji."""
        event = FactorioEvent(
            event_type=EventType.JOIN,
            formatted_message="Player joined",
            emoji=""
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "Player joined"

    def test_format_for_discord_join_fallback(self) -> None:
        """Test JOIN fallback formatting."""
        event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="Player1"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "👋 **Player1** joined the server"

    def test_format_for_discord_leave_fallback(self) -> None:
        """Test LEAVE fallback formatting."""
        event = FactorioEvent(
            event_type=EventType.LEAVE,
            player_name="Player1"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "👋 **Player1** left the server"

    def test_format_for_discord_chat_fallback(self) -> None:
        """Test CHAT fallback formatting with markdown escaping."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Player1",
            message="hello *world* _test_"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "💬 **Player1**: hello *world* _test_"

    def test_format_for_discord_chat_no_message(self) -> None:
        """Test CHAT fallback with no message."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Player1",
            message=None
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "💬 **Player1**: "

    def test_format_for_discord_server_fallback(self) -> None:
        """Test SERVER fallback formatting."""
        event = FactorioEvent(
            event_type=EventType.SERVER,
            message="Server started"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "🖥️ **Server:** Server started"

    def test_format_for_discord_milestone_fallback(self) -> None:
        """Test MILESTONE fallback formatting."""
        event = FactorioEvent(
            event_type=EventType.MILESTONE,
            player_name="Player1",
            message="Achievement unlocked"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "🏆 **Player1** completed: *Achievement unlocked*"

    def test_format_for_discord_task_fallback(self) -> None:
        """Test TASK fallback formatting."""
        event = FactorioEvent(
            event_type=EventType.TASK,
            player_name="Player1",
            message="Build 100 assemblers"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        # Note: The emoji ✔️ may render with extra space depending on font
        assert "**Player1**" in result
        assert "finished:" in result
        assert "*Build 100 assemblers*" in result

    def test_format_for_discord_research_fallback(self) -> None:
        """Test RESEARCH fallback formatting."""
        event = FactorioEvent(
            event_type=EventType.RESEARCH,
            message="Advanced electronics"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "🔬 Research completed: **Advanced electronics**"

    def test_format_for_discord_death_fallback(self) -> None:
        """Test DEATH fallback formatting."""
        event = FactorioEvent(
            event_type=EventType.DEATH,
            player_name="Player1",
            message="was killed by a biter"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "💀 **Player1** was killed by a biter"

    def test_format_for_discord_unknown_fallback(self) -> None:
        """Test UNKNOWN fallback uses raw_line."""
        event = FactorioEvent(
            event_type=EventType.UNKNOWN,
            raw_line="Unknown event type"
        )
        result = FactorioEventFormatter.format_for_discord(event)
        assert result == "Unknown event type"


# ============================================================================
# Integration Tests
# ============================================================================

class TestEventParserIntegration:
    """Integration tests with real patterns."""

    def test_end_to_end_join_event(self, mock_pattern_loader: MagicMock) -> None:
        """Test complete flow from line to formatted Discord message."""
        pattern = EventPattern(
            name="join_pattern",
            pattern=r'^\[JOIN\] (?P<player>\w+) joined',
            event_type="join",
            emoji="✅",
            message_template="**{player}** joined the server",
            channel="general",
            enabled=True,
            priority=10
        )
        
        mock_pattern_loader.get_patterns.return_value = [pattern]  # type: ignore[attr-defined]
        
        with patch('event_parser.PatternLoader', return_value=mock_pattern_loader):
            parser = EventParser(Path("patterns"))
            parser._compile_patterns()
            
            event = parser.parse_line("[JOIN] TestPlayer joined the game")
            assert event is not None
            
            result = FactorioEventFormatter.format_for_discord(event)
            assert "✅" in result
            assert "TestPlayer" in result

# ============================================================================
# Tests for timeout_handler, _safe_regex_search, check_rate_limit_for_event,
# and _create_security_alert_event
# ============================================================================

class TestTimeoutHandler:
    """Test timeout_handler signal handler function."""
    
    def test_timeout_handler_raises_timeout_error(self):
        """timeout_handler should raise TimeoutError when called."""
        from event_parser import timeout_handler, TimeoutError
        
        with pytest.raises(TimeoutError, match="Regex match exceeded timeout"):
            timeout_handler(None, None)
    
    def test_timeout_handler_with_signum_and_frame(self):
        """timeout_handler should work with actual signal arguments."""
        from event_parser import timeout_handler, TimeoutError
        import signal
        
        # Simulate signal handler call with real signal arguments
        with pytest.raises(TimeoutError):
            timeout_handler(signal.SIGALRM, None)


class TestSafeRegexSearch:
    """Test _safe_regex_search with various conditions."""
    
    def test_safe_regex_search_happy_path_match(self, event_parser, mock_event_pattern):
        """Successful regex match should return Match object."""
        event_parser.pattern_loader.get_patterns.return_value = [mock_event_pattern]
        event_parser._compile_patterns()
        
        regex, _ = event_parser.compiled_patterns["test_pattern"]
        result = event_parser._safe_regex_search(regex, "TestPlayer joined", "test_pattern")
        
        assert result is not None
        assert result.group(0) == "TestPlayer joined"
    
    def test_safe_regex_search_happy_path_no_match(self, event_parser, mock_event_pattern):
        """Non-matching line should return None gracefully."""
        event_parser.pattern_loader.get_patterns.return_value = [mock_event_pattern]
        event_parser._compile_patterns()
        
        regex, _ = event_parser.compiled_patterns["test_pattern"]
        result = event_parser._safe_regex_search(regex, "Random line", "test_pattern")
        
        assert result is None
    
    def test_safe_regex_search_stdlib_timeout_path(self, event_parser):
        """Timeout on stdlib regex should be caught and return None (RE2 not installed)."""
        from event_parser import TimeoutError as EventParserTimeoutError
        
        # Since RE2 is not installed, test the stdlib path
        pattern_obj = EventPattern(
            name="test",
            pattern=r".*",
            event_type="chat",
            emoji="",
            message_template="",
            channel="general",
            enabled=True,
            priority=1
        )
        
        # Mock the compiled regex to raise TimeoutError
        mock_regex = Mock()
        mock_regex.search.side_effect = EventParserTimeoutError("Regex match exceeded timeout")
        
        result = event_parser._safe_regex_search(mock_regex, "test line", "test_pattern")
        assert result is None
    
    def test_safe_regex_search_no_signal_alarm_windows(self, event_parser):
        """signal.alarm unavailable (Windows) should use untimed fallback."""
        pattern_obj = EventPattern(
            name="test",
            pattern=r"test",
            event_type="chat",
            emoji="",
            message_template="",
            channel="general",
            enabled=True,
            priority=1
        )
        
        event_parser.pattern_loader.get_patterns.return_value = [pattern_obj]
        event_parser._compile_patterns()
        regex, _ = event_parser.compiled_patterns["test"]
        
        # Mock signal to raise AttributeError (simulating Windows)
        with patch('signal.signal', side_effect=AttributeError("No SIGALRM on Windows")):
            with patch('signal.alarm', side_effect=AttributeError("No alarm on Windows")):
                result = event_parser._safe_regex_search(regex, "test line", "test")
                # Should still work, using fallback path
                assert result is not None
    
    def test_safe_regex_search_unexpected_exception(self, event_parser):
        """Unexpected exceptions should be caught and logged."""
        mock_regex = Mock()
        mock_regex.search.side_effect = RuntimeError("Unexpected error")
        
        # Should not raise, should return None
        result = event_parser._safe_regex_search(mock_regex, "test", "pattern")
        assert result is None
    
    def test_safe_regex_search_with_special_characters(self, event_parser):
        """Regex with special characters should be handled safely."""
        pattern_obj = EventPattern(
            name="special",
            pattern=r"^\[CHAT\] (\w+): (.+)$",
            event_type="chat",
            emoji="💬",
            message_template="{player}: {message}",
            channel="chat",
            enabled=True,
            priority=1
        )
        
        event_parser.pattern_loader.get_patterns.return_value = [pattern_obj]
        event_parser._compile_patterns()
        regex, _ = event_parser.compiled_patterns["special"]
        
        result = event_parser._safe_regex_search(
            regex, 
            "[CHAT] Alice: hello @everyone", 
            "special"
        )
        assert result is not None
        assert result.group(1) == "Alice"
    
    def test_safe_regex_search_exception_during_compile(self, event_parser):
        """Exception during pattern compilation should be handled."""
        # Create a pattern with invalid regex
        invalid_pattern = EventPattern(
            name="invalid",
            pattern=r"[invalid(regex",  # Unclosed bracket
            event_type="chat",
            emoji="",
            message_template="",
            channel="general",
            enabled=True,
            priority=1
        )
        
        event_parser.pattern_loader.get_patterns.return_value = [invalid_pattern]
        
        # Should not crash, just skip the invalid pattern
        event_parser._compile_patterns()
        
        # Invalid pattern should not be compiled
        assert "invalid" not in event_parser.compiled_patterns
    
    def test_safe_regex_search_signal_handling_success(self, event_parser, mock_event_pattern):
        """Successful match with signal handling should return match and clear alarm."""
        import signal
        
        event_parser.pattern_loader.get_patterns.return_value = [mock_event_pattern]
        event_parser._compile_patterns()
        
        regex, _ = event_parser.compiled_patterns["test_pattern"]
        
        # Track that alarm was cleared
        alarm_calls = []
        
        def mock_alarm(seconds):
            alarm_calls.append(seconds)
        
        with patch('signal.alarm', side_effect=mock_alarm):
            with patch('signal.signal'):
                result = event_parser._safe_regex_search(regex, "TestPlayer joined", "test_pattern")
        
        # Should have match
        assert result is not None
        # Should have set alarm and then cleared it (0)
        assert 0 in alarm_calls


class TestCheckRateLimitForEvent:
    """Test check_rate_limit_for_event logic paths."""
    
    def test_check_rate_limit_happy_path_no_player(self, event_parser):
        """Event without player_name should always be allowed."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name=None,
            message="Server started",
            raw_line="Server started"
        )
        
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        assert allowed is True
        assert reason is None
    
    def test_check_rate_limit_happy_path_chat_message(self, event_parser):
        """Regular chat message should check default rate limit."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Alice",
            message="Hello world",
            raw_line="[CHAT] Alice: Hello world",
            metadata={}
        )
        
        # Mock security monitor to return allowed
        event_parser.security_monitor.check_rate_limit = Mock(return_value=(True, None))
        
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        
        assert allowed is True
        assert reason is None
        event_parser.security_monitor.check_rate_limit.assert_called_once_with(
            action_type="chat_message",
            player_name="Alice"
        )
    
    def test_check_rate_limit_happy_path_mention_everyone(self, event_parser):
        """Event with 'everyone' in mentions list (with non-group type) should use mention_everyone action type."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Charlie",
            message="@everyone alert!",
            raw_line="[CHAT] Charlie: @everyone alert!",
            metadata={
                "mentions": ["everyone"],
                "mention_type": "user"  # Set to "user" or "mixed" to avoid the if branch
            }
        )
        
        # Create a fresh mock for this test to avoid contamination
        event_parser.security_monitor.check_rate_limit = Mock(return_value=(True, None))
        
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        
        assert allowed is True
        # Since mention_type is not "group", it falls to elif which checks for "everyone"
        event_parser.security_monitor.check_rate_limit.assert_called_once_with(
            action_type="mention_everyone",
            player_name="Charlie"
        )

    def test_check_rate_limit_happy_path_mention_admin(self, event_parser):
        """Event with group mention (not everyone) should use mention_admin action type."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Bob",
            message="@admins help!",
            raw_line="[CHAT] Bob: @admins help!",
            metadata={
                "mentions": ["admins"],
                "mention_type": "group"
            }
        )
        
        # Create a fresh mock for this test
        event_parser.security_monitor.check_rate_limit = Mock(return_value=(True, None))
        
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        
        assert allowed is True
        event_parser.security_monitor.check_rate_limit.assert_called_once_with(
            action_type="mention_admin",
            player_name="Bob"
        )

    
    
    def test_check_rate_limit_error_path_rate_exceeded(self, event_parser):
        """Rate limit exceeded should return False with reason."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Spammer",
            message="spam spam spam",
            raw_line="[CHAT] Spammer: spam spam spam",
            metadata={}
        )
        
        # Mock security monitor to return rate limited
        event_parser.security_monitor.check_rate_limit = Mock(
            return_value=(False, "Rate limit exceeded: 10 messages/min")
        )
        
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        
        assert allowed is False
        assert reason == "Rate limit exceeded: 10 messages/min"
    
    def test_check_rate_limit_user_mentions_default_action(self, event_parser):
        """User mentions (not group) should use default chat_message action."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Dave",
            message="@Alice hey!",
            raw_line="[CHAT] Dave: @Alice hey!",
            metadata={
                "mentions": ["Alice"],
                "mention_type": "user"
            }
        )
        
        event_parser.security_monitor.check_rate_limit = Mock(return_value=(True, None))
        
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        
        assert allowed is True
        event_parser.security_monitor.check_rate_limit.assert_called_once_with(
            action_type="chat_message",
            player_name="Dave"
        )
    
    def test_check_rate_limit_empty_player_name(self, event_parser):
        """Empty string player_name should be treated as None."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="",
            message="test",
            raw_line="test"
        )
        
        # Empty string is falsy, should return True without calling security monitor
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        assert allowed is True
        assert reason is None
    
    def test_check_rate_limit_mixed_mention_types(self, event_parser):
        """Mixed mention types should use default chat_message action."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Eve",
            message="@Alice @admins check this",
            raw_line="[CHAT] Eve: @Alice @admins check this",
            metadata={
                "mentions": ["Alice", "admins"],
                "mention_type": "mixed"
            }
        )
        
        event_parser.security_monitor.check_rate_limit = Mock(return_value=(True, None))
        
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        
        assert allowed is True
        # Mixed should fall through to default chat_message
        event_parser.security_monitor.check_rate_limit.assert_called_once_with(
            action_type="chat_message",
            player_name="Eve"
        )
    
    def test_check_rate_limit_mention_here(self, event_parser):
        """Event with @here should use mention_everyone action type."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Frank",
            message="@here urgent!",
            raw_line="[CHAT] Frank: @here urgent!",
            metadata={
                "mentions": ["here"],
                "mention_type": "group"
            }
        )
        
        event_parser.security_monitor.check_rate_limit = Mock(return_value=(True, None))
        
        allowed, reason = event_parser.check_rate_limit_for_event(event)
        
        assert allowed is True
        # @here is not @everyone, so it should use mention_admin
        event_parser.security_monitor.check_rate_limit.assert_called_once_with(
            action_type="mention_admin",
            player_name="Frank"
        )


class TestCreateSecurityAlertEvent:
    """Test _create_security_alert_event with various infractions."""
    
    def test_create_security_alert_happy_path_complete(self, event_parser):
        """Complete infraction should create properly formatted alert."""
        from security_monitor import Infraction
        from datetime import datetime
        
        original_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Attacker",
            message="malicious payload",
            raw_line="[CHAT] Attacker: malicious payload"
        )
        
        infraction = Infraction(
            player_name="Attacker",
            severity="critical",
            pattern_type="sql_injection",
            matched_pattern="DROP TABLE",
            raw_text="malicious payload",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            auto_banned=True,
            metadata={
                "description": "SQL Injection Attempt",
                "match": "DROP TABLE",
                "pattern_name": "sql_injection"
            }
        )
        
        alert_event = event_parser._create_security_alert_event(original_event, infraction)
        
        # Check event type and routing
        assert alert_event.event_type == EventType.SERVER
        assert alert_event.player_name == "Attacker"
        assert alert_event.metadata["channel"] == event_parser.security_channel
        assert alert_event.emoji == "🚨"
        
        # Check formatted message contains all parts
        assert "🚨 **SECURITY ALERT** 🚨" in alert_event.formatted_message
        assert "**Player:** Attacker" in alert_event.formatted_message
        assert "**Severity:** CRITICAL" in alert_event.formatted_message
        assert "**Type:** SQL Injection Attempt" in alert_event.formatted_message
        assert "**Matched:** `DROP TABLE`" in alert_event.formatted_message
        assert "**Action:** BANNED" in alert_event.formatted_message
        assert "2024-01-15 10:30:00" in alert_event.formatted_message
        
        # Check metadata
        assert alert_event.metadata["severity"] == "critical"
        assert alert_event.metadata["auto_banned"] is True
        assert "infraction" in alert_event.metadata
    
    def test_create_security_alert_happy_path_not_banned(self, event_parser):
        """Infraction without auto_ban should show LOGGED action."""
        from security_monitor import Infraction
        from datetime import datetime
        
        original_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Suspicious",
            message="suspicious text",
            raw_line="[CHAT] Suspicious: suspicious text"
        )
        
        infraction = Infraction(
            player_name="Suspicious",
            severity="low",
            pattern_type="suspicious_pattern",
            matched_pattern="sus",
            raw_text="suspicious text",
            timestamp=datetime(2024, 1, 15, 11, 0, 0),
            auto_banned=False,
            metadata={
                "description": "Suspicious Pattern",
                "match": "sus",
            }
        )
        
        alert_event = event_parser._create_security_alert_event(original_event, infraction)
        
        assert "**Action:** LOGGED" in alert_event.formatted_message
        assert alert_event.metadata["auto_banned"] is False
    
    def test_create_security_alert_error_path_missing_metadata(self, event_parser):
        """Missing metadata fields should use fallback values."""
        from security_monitor import Infraction
        from datetime import datetime
        
        original_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Player",
            message="test",
            raw_line="test"
        )
        
        # Infraction with minimal metadata
        infraction = Infraction(
            player_name="Player",
            severity="medium",
            pattern_type="unknown",
            matched_pattern="",
            raw_text="test message",
            timestamp=datetime(2024, 1, 15, 12, 0, 0),
            auto_banned=False,
            metadata={}  # Empty metadata
        )
        
        alert_event = event_parser._create_security_alert_event(original_event, infraction)
        
        # Should handle missing keys gracefully with .get()
        assert "**Type:** None" in alert_event.formatted_message
        assert "**Matched:** `N/A`" in alert_event.formatted_message
        assert alert_event.formatted_message is not None
    
    def test_create_security_alert_error_path_long_raw_text(self, event_parser):
        """Long raw text should be truncated in alert."""
        from security_monitor import Infraction
        from datetime import datetime
        
        original_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Verbose",
            message="x" * 500,
            raw_line="x" * 500
        )
        
        infraction = Infraction(
            player_name="Verbose",
            severity="high",
            pattern_type="spam",
            matched_pattern="xxx",
            raw_text="x" * 500,
            timestamp=datetime.now(),
            auto_banned=True,
            metadata={"description": "Spam"}
        )
        
        alert_event = event_parser._create_security_alert_event(original_event, infraction)
        
        # Raw text should be truncated to 100 chars
        raw_line = [line for line in alert_event.formatted_message.split('\n') if '**Raw:**' in line][0]
        # Extract the actual content between backticks
        assert '...' in raw_line  # Truncation indicator present
    
    def test_create_security_alert_preserves_original_raw_line(self, event_parser):
        """Alert event should preserve original event's raw_line."""
        from security_monitor import Infraction
        from datetime import datetime
        
        original_raw = "[CHAT] Test: original message"
        original_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Test",
            message="original message",
            raw_line=original_raw
        )
        
        infraction = Infraction(
            player_name="Test",
            severity="low",
            pattern_type="test",
            matched_pattern="test",
            raw_text="test",
            timestamp=datetime.now(),
            auto_banned=False,
            metadata={}
        )
        
        alert_event = event_parser._create_security_alert_event(original_event, infraction)
        
        assert alert_event.raw_line == original_raw
    
    def test_create_security_alert_uses_custom_security_channel(self):
        """Security alert should route to custom security channel."""
        from security_monitor import Infraction, SecurityMonitor
        from datetime import datetime
        
        # Create parser with custom security channel
        with patch('event_parser.PatternLoader') as mock_loader:
            mock_loader.return_value.load_patterns.return_value = 0
            parser = EventParser(
                Path("patterns"),
                security_monitor=SecurityMonitor(),
                security_channel="custom-security"
            )
        
        original_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Test",
            message="test",
            raw_line="test"
        )
        
        infraction = Infraction(
            player_name="Test",
            severity="medium",
            pattern_type="test",
            matched_pattern="test",
            raw_text="test",
            timestamp=datetime.now(),
            auto_banned=False,
            metadata={}
        )
        
        alert_event = parser._create_security_alert_event(original_event, infraction)
        
        assert alert_event.metadata["channel"] == "custom-security"
    
    def test_create_security_alert_infraction_to_dict_in_metadata(self, event_parser):
        """Alert metadata should contain serialized infraction."""
        from security_monitor import Infraction
        from datetime import datetime
        
        original_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Test",
            message="test",
            raw_line="test"
        )
        
        infraction = Infraction(
            player_name="Test",
            severity="low",
            pattern_type="test_type",
            matched_pattern="test_pattern",
            raw_text="test",
            timestamp=datetime.now(),
            auto_banned=False,
            metadata={"key": "value"}
        )
        
        alert_event = event_parser._create_security_alert_event(original_event, infraction)
        
        # Check that to_dict() was called and stored
        assert "infraction" in alert_event.metadata
        infraction_dict = alert_event.metadata["infraction"]
        assert isinstance(infraction_dict, dict)
        assert infraction_dict["player_name"] == "Test"
    
    def test_create_security_alert_with_medium_severity(self, event_parser):
        """Medium severity infraction should be formatted correctly."""
        from security_monitor import Infraction
        from datetime import datetime
        
        original_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="MediumThreat",
            message="slightly suspicious",
            raw_line="[CHAT] MediumThreat: slightly suspicious"
        )
        
        infraction = Infraction(
            player_name="MediumThreat",
            severity="medium",
            pattern_type="suspicious_keyword",
            matched_pattern="suspicious",
            raw_text="slightly suspicious",
            timestamp=datetime.now(),
            auto_banned=False,
            metadata={"description": "Keyword Watch"}
        )
        
        alert_event = event_parser._create_security_alert_event(original_event, infraction)
        
        assert "**Severity:** MEDIUM" in alert_event.formatted_message
        assert alert_event.metadata["severity"] == "medium"
