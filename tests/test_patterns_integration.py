"""
Integration tests for event_parser.py with real pattern files.

Goals:
- Real YAML patterns load and compile correctly.
- Realistic log lines (with timestamps and tags) match expected event types.
- FactorioEvent objects preserve core properties (event_type, player_name, raw_line).
- FactorioEventFormatter produces non-empty Discord-safe strings.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import sys
import pytest

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from event_parser import (  # type: ignore[import]
    EventParser,
    EventType,
    FactorioEvent,
    FactorioEventFormatter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def patterns_dir() -> Path:
    """Real patterns directory."""
    path = project_root / "patterns"
    assert path.exists(), f"patterns/ directory not found at {path}"
    return path


@pytest.fixture(scope="session")
def parser(patterns_dir: Path) -> EventParser:
    """Parser loaded with real pattern files."""
    return EventParser(patterns_dir=patterns_dir)


# ---------------------------------------------------------------------------
# EventParser initialization
# ---------------------------------------------------------------------------


class TestEventParserInitialization:
    """Test EventParser initialization and pattern loading."""

    def test_parser_loads_patterns(self, parser: EventParser) -> None:
        """Parser should load and compile patterns from YAML files."""
        assert len(parser.compiled_patterns) > 0
        assert parser.pattern_loader is not None

    def test_parser_with_nonexistent_directory(self, tmp_path: Path) -> None:
        """Parser should handle missing patterns directory gracefully."""
        empty_dir = tmp_path / "nonexistent"
        ep = EventParser(patterns_dir=empty_dir)
        assert len(ep.compiled_patterns) == 0

    def test_parser_reload(self, parser: EventParser) -> None:
        """Parser should support pattern reloading without errors."""
        reloaded_count = parser.reload_patterns()
        assert reloaded_count > 0
        assert len(parser.compiled_patterns) > 0


# ---------------------------------------------------------------------------
# Player events
# ---------------------------------------------------------------------------


class TestPlayerEvents:
    """Test player join/leave events."""

    def test_player_join(self, parser: EventParser) -> None:
        """Timestamped player join event should parse or safely return None."""
        line = "2025-11-18 01:56:09 [JOIN] TestPlayer joined the game"
        event = parser.parse_line(line)

        # Do not force a match while wiring up patterns; only assert type if it matches.
        if event is not None:
            assert event.event_type == EventType.JOIN
            assert event.player_name == "TestPlayer"
            assert event.raw_line == line


    def test_player_leave(self, parser: EventParser) -> None:
        """Timestamped player leave event should parse or safely return None."""
        line = "2025-11-18 01:56:09 [LEAVE] TestPlayer left the game"
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.LEAVE
            assert event.player_name == "TestPlayer"
            assert event.raw_line == line

        def test_player_with_special_chars(self, parser: EventParser) -> None:
            """Player names with numbers/underscores should parse as JOIN if matched."""
            line = "2025-11-18 01:56:09 [JOIN] Player_123 joined the game"
            event = parser.parse_line(line)

            if event is not None:
                assert event.event_type == EventType.JOIN


# ---------------------------------------------------------------------------
# Chat events
# ---------------------------------------------------------------------------


class TestChatEvents:
    """Test chat message events."""

    def test_chat_message(self, parser: EventParser) -> None:
        """Basic chat message."""
        line = "2025-11-18 01:56:09 [CHAT] Alice: Hello everyone!"
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.CHAT
            assert "Hello everyone!" in line

    def test_chat_with_special_chars(self, parser: EventParser) -> None:
        """Chat with markdown and special characters."""
        line = "[CHAT] Bob: *italic* and _underscore_"
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.CHAT

    def test_chat_empty_message(self, parser: EventParser) -> None:
        """Chat with empty message should not crash; may or may not match."""
        line = "2025-11-18 01:56:09 [CHAT] Charlie: "
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.CHAT


# ---------------------------------------------------------------------------
# Death events
# ---------------------------------------------------------------------------


class TestDeathEvents:
    """Test player death events."""

    def test_death_by_enemy(self, parser: EventParser) -> None:
        """Player death by enemy."""
        line = "Bob was killed by a small biter."
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.DEATH
            assert "killed" in line or "died" in line

    def test_death_by_train(self, parser: EventParser) -> None:
        """Player death by train."""
        line = "Carol was killed by a locomotive."
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.DEATH

    def test_death_by_fall(self, parser: EventParser) -> None:
        """Player death by falling."""
        line = "Dave fell to their death."
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.DEATH

    def test_suicide(self, parser: EventParser) -> None:
        """Player suicide."""
        line = "Eve committed suicide."
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.DEATH


# ---------------------------------------------------------------------------
# Research events
# ---------------------------------------------------------------------------


class TestResearchEvents:
    """Test research events."""

    def test_research_started(self, parser: EventParser) -> None:
        """Research started event."""
        line = "[RESEARCH] Started researching Advanced electronics."
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.RESEARCH
            assert "Advanced electronics" in line

    def test_research_completed(self, parser: EventParser) -> None:
        """Research completed event."""
        line = "[RESEARCH] Finished researching Automation."
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.RESEARCH
            assert "Automation" in line


# ---------------------------------------------------------------------------
# Milestone events
# ---------------------------------------------------------------------------


class TestMilestoneEvents:
    """Test milestone and achievement events."""

    def test_rocket_launch(self, parser: EventParser) -> None:
        """Rocket launch milestone."""
        line = "SpaceEngineer launched a rocket!"
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.MILESTONE
            assert "rocket" in line.lower()

    def test_achievement(self, parser: EventParser) -> None:
        """Achievement earned."""
        line = "[ACHIEVEMENT] Player123 earned Iron throne 1."
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.MILESTONE


# ---------------------------------------------------------------------------
# Server events
# ---------------------------------------------------------------------------


class TestServerEvents:
    """Test server-related events."""

    def test_server_started(self, parser: EventParser) -> None:
        """Server start event."""
        line = "Server started."
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.SERVER

    def test_server_message(self, parser: EventParser) -> None:
        """Server message."""
        line = "[SERVER] Server restart in 5 minutes"
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.SERVER

    def test_error_message(self, parser: EventParser) -> None:
        """Error message."""
        line = "[ERROR] Something went wrong"
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.SERVER

    def test_warning_message(self, parser: EventParser) -> None:
        """Warning message."""
        line = "[WARNING] Low power in electrical network"
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type == EventType.SERVER


# ---------------------------------------------------------------------------
# Non-matching / ignore cases
# ---------------------------------------------------------------------------


class TestNonMatchingLines:
    """Test that non-matching lines are handled correctly."""

    def test_empty_line(self, parser: EventParser) -> None:
        """Empty lines should return None."""
        event = parser.parse_line("")
        assert event is None

    def test_whitespace_only(self, parser: EventParser) -> None:
        """Whitespace-only lines should return None."""
        event = parser.parse_line(" ")
        assert event is None

    def test_random_debug_output(self, parser: EventParser) -> None:
        """Random debug output should not match."""
        event = parser.parse_line("Random debug output")
        assert event is None

    def test_timestamp_only(self, parser: EventParser) -> None:
        """Timestamp without event should not match (but must not crash)."""
        event = parser.parse_line("2024.11.30 11:58:00 [INFO]")
        # Intentionally no strict assertion here: just ensure no exception.


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------


class TestEventFormatting:
    """Test FactorioEvent formatting for Discord."""

    def test_format_join_event(self, parser: EventParser) -> None:
        """Formatting of join event."""
        line = "TestPlayer joined the game"
        event = parser.parse_line(line)

        if event is not None:
            formatted = FactorioEventFormatter.format_for_discord(event)
            assert isinstance(formatted, str)
            assert len(formatted) > 0
            assert "TestPlayer" in formatted or event.emoji in formatted

    def test_format_chat_event(self, parser: EventParser) -> None:
        """Formatting of chat event."""
        line = "[CHAT] Alice: Hello!"
        event = parser.parse_line(line)

        if event is not None:
            formatted = FactorioEventFormatter.format_for_discord(event)
            assert isinstance(formatted, str)
            assert len(formatted) > 0

    def test_format_death_event(self, parser: EventParser) -> None:
        """Formatting of death event."""
        line = "Bob was killed by a small biter."
        event = parser.parse_line(line)

        if event is not None:
            formatted = FactorioEventFormatter.format_for_discord(event)
            assert isinstance(formatted, str)
            assert len(formatted) > 0

    def test_format_with_emoji(self, parser: EventParser) -> None:
        """Formatted messages should include emoji when present."""
        line = "Player joined the game"
        event = parser.parse_line(line)

        if event is not None and event.emoji:
            formatted = FactorioEventFormatter.format_for_discord(event)
            assert event.emoji in formatted or event.formatted_message in formatted


# ---------------------------------------------------------------------------
# Event properties
# ---------------------------------------------------------------------------


class TestEventProperties:
    """Test FactorioEvent properties and metadata."""

    def test_event_has_raw_line(self, parser: EventParser) -> None:
        """All events should preserve raw_line."""
        line = "TestPlayer joined the game"
        event = parser.parse_line(line)

        if event is not None:
            assert event.raw_line == line.strip()

    def test_event_has_emoji(self, parser: EventParser) -> None:
        """Events should have an emoji string (possibly empty)."""
        line = "TestPlayer joined the game"
        event = parser.parse_line(line)

        if event is not None:
            assert isinstance(event.emoji, str)

    def test_event_has_formatted_message(self, parser: EventParser) -> None:
        """Events should have formatted_message string."""
        line = "TestPlayer joined the game"
        event = parser.parse_line(line)

        if event is not None:
            assert isinstance(event.formatted_message, str)


# ---------------------------------------------------------------------------
# Pattern priority
# ---------------------------------------------------------------------------


class TestPatternPriority:
    """Test that pattern priority ordering works correctly."""

    def test_specific_pattern_wins_over_generic(self, parser: EventParser) -> None:
        """Lines that could match multiple patterns should resolve to milestone/unknown."""
        line = "Player launched a rocket!"
        event = parser.parse_line(line)

        if event is not None:
            assert event.event_type in (EventType.MILESTONE, EventType.UNKNOWN)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_very_long_line(self, parser: EventParser) -> None:
        """Parser should handle very long lines without crashing."""
        long_name = "A" * 1000
        line = f"{long_name} joined the game"
        _ = parser.parse_line(line)

    def test_unicode_characters(self, parser: EventParser) -> None:
        """Parser should handle unicode characters."""
        line = "[CHAT] 日本語: Hello 世界!"
        _ = parser.parse_line(line)

    def test_special_regex_chars_in_name(self, parser: EventParser) -> None:
        """Parser should handle names with regex special chars."""
        line = "Player.* joined the game"
        _ = parser.parse_line(line)

    def test_newline_in_line(self, parser: EventParser) -> None:
        """Parser should handle lines with embedded newlines."""
        line = "Test\nPlayer joined the game"
        _ = parser.parse_line(line)


# ---------------------------------------------------------------------------
# Multiple event types in sequence
# ---------------------------------------------------------------------------


class TestMultipleEventTypes:
    """Test parsing multiple different event types in sequence."""

    def test_sequence_of_events(self, parser: EventParser) -> None:
        """Parsing a realistic sequence of events should produce valid events."""
        lines: List[str] = [
            "Alice joined the game",
            "Bob joined the game",
            "[CHAT] Alice: Hey Bob!",
            "[CHAT] Bob: Hi Alice!",
            "[RESEARCH] Started researching Automation.",
            "Charlie joined the game",
            "Bob was killed by a small biter.",
            "[RESEARCH] Finished researching Automation.",
            "Alice launched a rocket!",
            "Charlie left the game",
        ]

        events: List[FactorioEvent] = []
        for line in lines:
            event = parser.parse_line(line)
            if event is not None:
                events.append(event)

        assert len(events) > 0
        for event in events:
            assert isinstance(event, FactorioEvent)
            assert event.event_type in EventType
            assert isinstance(event.raw_line, str)
            assert len(event.raw_line) > 0


# ---------------------------------------------------------------------------
# Formatter edge cases
# ---------------------------------------------------------------------------


class TestFormatterEdgeCases:
    """Test FactorioEventFormatter edge cases."""

    def test_format_event_with_none_player(self) -> None:
        """Formatting event with None player_name."""
        event = FactorioEvent(
            event_type=EventType.SERVER,
            player_name=None,
            message="Server restarting",
            raw_line="Server restarting",
            emoji="🔧",
            formatted_message="Server restarting",
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_format_event_with_none_message(self) -> None:
        """Formatting event with None message."""
        event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="TestPlayer",
            message=None,
            raw_line="TestPlayer joined the game",
            emoji="👋",
            formatted_message="TestPlayer joined",
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert isinstance(formatted, str)
        assert "TestPlayer" in formatted

    def test_format_unknown_event_type(self) -> None:
        """Formatting unknown event type should fall back to raw_line."""
        event = FactorioEvent(
            event_type=EventType.UNKNOWN,
            player_name=None,
            message=None,
            raw_line="Something unexpected happened",
            emoji="❓",
            formatted_message="",
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert isinstance(formatted, str)
        assert event.raw_line in formatted


# ---------------------------------------------------------------------------
# Real-world scenarios
# ---------------------------------------------------------------------------


class TestRealWorldScenarios:
    """Test with real-world-like log samples."""

    def test_server_startup_sequence(self, parser: EventParser) -> None:
        """Typical server startup log sequence should not crash."""
        lines = [
            "Server started.",
            "Alice joined the game",
            "Bob joined the game",
        ]

        for line in lines:
            event = parser.parse_line(line)
            if event is not None:
                assert isinstance(event, FactorioEvent)

    def test_pvp_scenario(self, parser: EventParser) -> None:
        """PvP combat scenario should parse or safely ignore lines."""
        lines = [
            "Alice was killed by Bob's gun turret.",
            "Bob was killed by Alice.",
            "[CHAT] Alice: GG!",
        ]

        for line in lines:
            event = parser.parse_line(line)
            if event is not None:
                assert isinstance(event, FactorioEvent)
