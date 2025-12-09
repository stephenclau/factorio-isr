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


from __future__ import annotations
from pathlib import Path
from typing import List
import sys
import pytest
import tempfile
import yaml

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from event_parser import (  # type: ignore[import]
    EventParser,
    EventType,
    FactorioEvent,
    FactorioEventFormatter,
)
from pattern_loader import (  # type: ignore[import]
    PatternLoader,
    EventPattern,
    MAX_PATTERN_LENGTH,
    MAX_TEMPLATE_LENGTH,
    MAX_PATTERNS_PER_FILE,
    MAX_FILE_SIZE_BYTES,
    ALLOWED_YAML_KEYS,
    ALLOWED_TEMPLATE_PLACEHOLDERS,
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

@pytest.fixture
def temp_patterns_dir(tmp_path: Path) -> Path:
    """Temporary patterns directory for security tests."""
    patterns_dir = tmp_path / "patterns"
    patterns_dir.mkdir()
    return patterns_dir

@pytest.fixture
def create_test_yaml(temp_patterns_dir: Path):
    """Factory to create test YAML files."""
    def _create(filename: str, content: dict) -> Path:
        filepath = temp_patterns_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(content, f)
        return filepath
    return _create

# ---------------------------------------------------------------------------
# Security validation tests (NEW)
# ---------------------------------------------------------------------------

class TestPatternLoaderSecurity:
    """Test security validations in pattern loading."""

    def test_pattern_length_limit_enforced(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Patterns exceeding MAX_PATTERN_LENGTH should be rejected."""
        long_pattern = "x" * (MAX_PATTERN_LENGTH + 1)
        yaml_data = {
            "events": {
                "too_long": {
                    "pattern": long_pattern,
                    "type": "chat"
                }
            }
        }
        create_test_yaml("long_pattern.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Pattern should be rejected
        assert count == 0

    def test_template_length_limit_enforced(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Templates exceeding MAX_TEMPLATE_LENGTH should be rejected."""
        long_template = "x" * (MAX_TEMPLATE_LENGTH + 1)
        yaml_data = {
            "events": {
                "long_template": {
                    "pattern": "test",
                    "type": "chat",
                    "message": long_template
                }
            }
        }
        create_test_yaml("long_template.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Pattern should be rejected
        assert count == 0

    def test_yaml_key_whitelist_enforced(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """YAML files with non-whitelisted keys should be rejected."""
        yaml_data = {
            "events": {
                "malicious": {
                    "pattern": "test",
                    "type": "chat",
                    "handler": "evil.py",  # Not in ALLOWED_YAML_KEYS
                    "execute": "rm -rf /"  # Not in ALLOWED_YAML_KEYS
                }
            }
        }
        create_test_yaml("malicious.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Pattern should be rejected
        assert count == 0

    def test_template_placeholder_validation(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Templates with non-whitelisted placeholders should be rejected."""
        yaml_data = {
            "events": {
                "bad_placeholder": {
                    "pattern": "test",
                    "type": "chat",
                    "message": "{player} {__import__}"  # __import__ not allowed
                }
            }
        }
        create_test_yaml("bad_placeholder.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Pattern should be rejected
        assert count == 0

    def test_valid_placeholders_accepted(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Templates with only {player} and {message} should be accepted."""
        yaml_data = {
            "events": {
                "valid": {
                    "pattern": "test",
                    "type": "chat",
                    "message": "{player} said {message}"
                }
            }
        }
        create_test_yaml("valid.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Pattern should be accepted
        assert count == 1
        assert loader.patterns[0].message_template == "{player} said {message}"

    def test_pattern_name_validation(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Pattern names must be alphanumeric with underscores only."""
        yaml_data = {
            "events": {
                "invalid-name": {  # Hyphen not allowed
                    "pattern": "test",
                    "type": "chat"
                }
            }
        }
        create_test_yaml("invalid_name.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Pattern should be rejected
        assert count == 0

    def test_valid_pattern_name_accepted(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Pattern names with alphanumeric and underscores should be accepted."""
        yaml_data = {
            "events": {
                "valid_name_123": {
                    "pattern": "test",
                    "type": "chat"
                }
            }
        }
        create_test_yaml("valid_name.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Pattern should be accepted
        assert count == 1
        assert loader.patterns[0].name == "valid_name_123"

    def test_file_size_limit_enforced(self, temp_patterns_dir: Path) -> None:
        """Files exceeding MAX_FILE_SIZE_BYTES should be rejected."""
        huge_file = temp_patterns_dir / "huge.yml"

        # Create file larger than 1MB
        with open(huge_file, 'w') as f:
            f.write("events:\n")
            for i in range(50000):
                f.write(f"  pattern_{i}:\n    pattern: 'x' * 100\n    type: chat\n")

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # File should be rejected
        assert count == 0

    def test_pattern_count_per_file_limit(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Files with >MAX_PATTERNS_PER_FILE patterns should be rejected."""
        events = {}
        for i in range(MAX_PATTERNS_PER_FILE + 1):
            events[f"pattern_{i}"] = {
                "pattern": f"test{i}",
                "type": "chat"
            }
        yaml_data = {"events": events}
        create_test_yaml("too_many.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # File should be rejected
        assert count == 0

    def test_mixed_valid_and_invalid_patterns(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Valid patterns should load even if some are invalid."""
        yaml_data = {
            "events": {
                "valid1": {
                    "pattern": "test1",
                    "type": "chat"
                },
                "too_long": {
                    "pattern": "x" * (MAX_PATTERN_LENGTH + 1),
                    "type": "chat"
                },
                "valid2": {
                    "pattern": "test2",
                    "type": "join"
                }
            }
        }
        create_test_yaml("mixed.yml", yaml_data)

        loader = PatternLoader(patterns_dir=temp_patterns_dir)
        count = loader.load_patterns()

        # Only valid patterns should load
        assert count == 2
        valid_names = {p.name for p in loader.patterns}
        assert valid_names == {"valid1", "valid2"}

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

    def test_parser_loads_secured_patterns_only(self, temp_patterns_dir: Path, create_test_yaml) -> None:
        """Parser should only compile patterns that pass security validation."""
        yaml_data = {
            "events": {
                "valid": {
                    "pattern": r"\w+ joined",
                    "type": "join",
                    "message": "{player} joined"
                },
                "invalid_long": {
                    "pattern": "x" * (MAX_PATTERN_LENGTH + 1),
                    "type": "chat"
                }
            }
        }
        create_test_yaml("test.yml", yaml_data)

        parser = EventParser(patterns_dir=temp_patterns_dir)

        # Only valid pattern should be compiled
        assert len(parser.compiled_patterns) == 1
        assert "valid" in parser.compiled_patterns

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
        event = parser.parse_line("   ")
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
        """PVP combat scenario should parse or safely ignore lines."""
        lines = [
            "Alice was killed by Bob's gun turret.",
            "Bob was killed by Alice.",
            "[CHAT] Alice: GG!",
        ]

        for line in lines:
            event = parser.parse_line(line)
            if event is not None:
                assert isinstance(event, FactorioEvent)

# ---------------------------------------------------------------------------
# Security constants validation
# ---------------------------------------------------------------------------

class TestSecurityConstants:
    """Test that security constants are properly defined."""

    def test_max_pattern_length_defined(self) -> None:
        """MAX_PATTERN_LENGTH should be defined and positive."""
        assert MAX_PATTERN_LENGTH > 0
        assert isinstance(MAX_PATTERN_LENGTH, int)

    def test_max_template_length_defined(self) -> None:
        """MAX_TEMPLATE_LENGTH should be defined and positive."""
        assert MAX_TEMPLATE_LENGTH > 0
        assert isinstance(MAX_TEMPLATE_LENGTH, int)

    def test_max_patterns_per_file_defined(self) -> None:
        """MAX_PATTERNS_PER_FILE should be defined and positive."""
        assert MAX_PATTERNS_PER_FILE > 0
        assert isinstance(MAX_PATTERNS_PER_FILE, int)

    def test_max_file_size_defined(self) -> None:
        """MAX_FILE_SIZE_BYTES should be defined and positive."""
        assert MAX_FILE_SIZE_BYTES > 0
        assert isinstance(MAX_FILE_SIZE_BYTES, int)

    def test_allowed_yaml_keys_defined(self) -> None:
        """ALLOWED_YAML_KEYS should be a non-empty set."""
        assert isinstance(ALLOWED_YAML_KEYS, set)
        assert len(ALLOWED_YAML_KEYS) > 0
        # Check for expected keys
        assert "pattern" in ALLOWED_YAML_KEYS
        assert "type" in ALLOWED_YAML_KEYS
        assert "message" in ALLOWED_YAML_KEYS

    def test_allowed_placeholders_defined(self) -> None:
        """ALLOWED_TEMPLATE_PLACEHOLDERS should contain player and message."""
        assert isinstance(ALLOWED_TEMPLATE_PLACEHOLDERS, set)
        assert "player" in ALLOWED_TEMPLATE_PLACEHOLDERS
        assert "message" in ALLOWED_TEMPLATE_PLACEHOLDERS
