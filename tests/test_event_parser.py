"""
Pytest test suite for event_parser.py

Tests for Factorio event parsing and formatting functionality.
"""

import pytest
import sys
from pathlib import Path

# Add the src directory to the Python path
# This assumes tests/ and src/ are siblings in factorio-isr/
project_root = Path(__file__).parent.parent
src_path = project_root / 'src'
sys.path.insert(0, str(src_path))

from event_parser import (
    EventType,
    FactorioEvent,
    EventParser,
    FactorioEventFormatter
)


class TestEventType:
    """Tests for EventType enum."""
    
    def test_event_type_values(self):
        """Verify all event type enum values are correct."""
        assert EventType.SERVER.value == "server"
        assert EventType.JOIN.value == "join"
        assert EventType.LEAVE.value == "leave"
        assert EventType.CHAT.value == "chat"
        assert EventType.MILESTONE.value == "milestone"
        assert EventType.TASK.value == "task"
        assert EventType.RESEARCH.value == "research"
        assert EventType.DEATH.value == "death"
        assert EventType.UNKNOWN.value == "unknown"


class TestFactorioEvent:
    """Tests for FactorioEvent dataclass."""
    
    def test_create_basic_event(self):
        """Test creating a basic event with required fields."""
        event = FactorioEvent(event_type=EventType.JOIN)
        assert event.event_type == EventType.JOIN
        assert event.player_name is None
        assert event.message is None
        assert event.raw_line is None
        assert event.metadata is None
    
    def test_create_full_event(self):
        """Test creating an event with all fields populated."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello world",
            raw_line="TestPlayer: Hello world",
            metadata={"test": "value"}
        )
        
        assert event.event_type == EventType.CHAT
        assert event.player_name == "TestPlayer"
        assert event.message == "Hello world"
        assert event.raw_line == "TestPlayer: Hello world"
        assert event.metadata == {"test": "value"}


class TestEventParserJoin:
    """Tests for parsing JOIN events."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_join_simple(self, parser):
        """Test parsing simple join message."""
        event = parser.parse("PlayerOne joined")
        assert event is not None
        assert event.event_type == EventType.JOIN
        assert event.player_name == "PlayerOne"
    
    def test_parse_join_with_game(self, parser):
        """Test parsing join message with 'the game'."""
        event = parser.parse("PlayerTwo joined the game")
        assert event is not None
        assert event.event_type == EventType.JOIN
        assert event.player_name == "PlayerTwo"
    
    def test_parse_join_with_tag(self, parser):
        """Test parsing join message with [JOIN] tag."""
        event = parser.parse("[JOIN] PlayerThree joined the game")
        assert event is not None
        assert event.event_type == EventType.JOIN
        assert event.player_name == "PlayerThree"
    
    def test_parse_join_with_timestamp(self, parser):
        """Test parsing join message with timestamp."""
        event = parser.parse("2024-11-28 15:30:45 PlayerFour joined the game")
        assert event is not None
        assert event.event_type == EventType.JOIN
        assert event.player_name == "PlayerFour"
    
    def test_parse_join_case_insensitive(self, parser):
        """Test that join parsing is case insensitive."""
        event = parser.parse("PlayerFive JOINED the game")
        assert event is not None
        assert event.event_type == EventType.JOIN
        assert event.player_name == "PlayerFive"


class TestEventParserLeave:
    """Tests for parsing LEAVE events."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_leave_simple(self, parser):
        """Test parsing simple leave message with 'left'."""
        event = parser.parse("PlayerOne left")
        assert event is not None
        assert event.event_type == EventType.LEAVE
        assert event.player_name == "PlayerOne"
    
    def test_parse_leave_with_game(self, parser):
        """Test parsing leave message with 'the game'."""
        event = parser.parse("PlayerTwo left the game")
        assert event is not None
        assert event.event_type == EventType.LEAVE
        assert event.player_name == "PlayerTwo"
    
    def test_parse_leave_with_leaving(self, parser):
        """Test parsing leave message with 'leaving'."""
        event = parser.parse("PlayerThree leaving the game")
        assert event is not None
        assert event.event_type == EventType.LEAVE
        assert event.player_name == "PlayerThree"
    
    def test_parse_leave_with_tag(self, parser):
        """Test parsing leave message with [LEAVE] tag."""
        event = parser.parse("[LEAVE] PlayerFour left the game")
        assert event is not None
        assert event.event_type == EventType.LEAVE
        assert event.player_name == "PlayerFour"
    
    def test_parse_leave_with_timestamp(self, parser):
        """Test parsing leave message with timestamp."""
        event = parser.parse("2024-11-28 16:45:30 PlayerFive left the game")
        assert event is not None
        assert event.event_type == EventType.LEAVE
        assert event.player_name == "PlayerFive"


class TestEventParserChat:
    """Tests for parsing CHAT events."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_chat_simple(self, parser):
        """Test parsing simple chat message."""
        event = parser.parse("PlayerOne: Hello everyone!")
        assert event is not None
        assert event.event_type == EventType.CHAT
        assert event.player_name == "PlayerOne"
        assert event.message == "Hello everyone!"
    
    def test_parse_chat_with_tag(self, parser):
        """Test parsing chat message with [CHAT] tag."""
        event = parser.parse("[CHAT] PlayerTwo: How's it going?")
        assert event is not None
        assert event.event_type == EventType.CHAT
        assert event.player_name == "PlayerTwo"
        assert event.message == "How's it going?"
    
    def test_parse_chat_with_special_chars(self, parser):
        """Test parsing chat with special characters."""
        event = parser.parse("PlayerThree: Check this out! @#$%")
        assert event is not None
        assert event.event_type == EventType.CHAT
        assert event.player_name == "PlayerThree"
        assert event.message == "Check this out! @#$%"
    
    def test_parse_chat_multiword(self, parser):
        """Test parsing long chat message."""
        event = parser.parse("PlayerFour: This is a much longer message with many words")
        assert event is not None
        assert event.event_type == EventType.CHAT
        assert event.player_name == "PlayerFour"
        assert event.message == "This is a much longer message with many words"


class TestEventParserMilestone:
    """Tests for parsing MILESTONE events."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_milestone_completed(self, parser):
        """Test parsing milestone with 'completed milestone:' format."""
        event = parser.parse("[Milestones] PlayerOne completed milestone: First Steps")
        assert event is not None
        assert event.event_type == EventType.MILESTONE
        assert event.player_name == "PlayerOne"
        assert event.message == "First Steps"
        assert event.metadata == {"milestone": "First Steps"}
    
    def test_parse_milestone_colon_format(self, parser):
        """Test parsing milestone with colon format."""
        event = parser.parse("[MILESTONE] PlayerTwo: Research automation")
        assert event is not None
        assert event.event_type == EventType.MILESTONE
        assert event.player_name == "PlayerTwo"
        assert event.message == "Research automation"
        assert event.metadata == {"milestone": "Research automation"}
    
    def test_parse_milestone_singular(self, parser):
        """Test parsing with [MILESTONE] tag (singular)."""
        event = parser.parse("[MILESTONE] PlayerThree completed milestone: Iron Production")
        assert event is not None
        assert event.event_type == EventType.MILESTONE
        assert event.player_name == "PlayerThree"
        assert "Iron Production" in event.message


class TestEventParserTask:
    """Tests for parsing TASK events."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_task_completed(self, parser):
        """Test parsing task with 'completed' keyword."""
        event = parser.parse("[Task] PlayerOne completed: Build 100 red circuits")
        assert event is not None
        assert event.event_type == EventType.TASK
        assert event.player_name == "PlayerOne"
        assert event.message == "Build 100 red circuits"
        assert event.metadata == {"task": "Build 100 red circuits"}
    
    def test_parse_task_finished(self, parser):
        """Test parsing task with 'finished' keyword."""
        event = parser.parse("[TODO] PlayerTwo finished task: Set up oil processing")
        assert event is not None
        assert event.event_type == EventType.TASK
        assert event.player_name == "PlayerTwo"
        assert event.message == "Set up oil processing"
    
    def test_parse_task_todo_tag(self, parser):
        """Test parsing with [TODO] tag."""
        event = parser.parse("[TODO] PlayerThree completed: Expand base")
        assert event is not None
        assert event.event_type == EventType.TASK
        assert event.player_name == "PlayerThree"


class TestEventParserResearch:
    """Tests for parsing RESEARCH events."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_research_with_tag(self, parser):
        """Test parsing research with [RESEARCH] tag."""
        event = parser.parse("[RESEARCH] Automation technology has been researched")
        assert event is not None
        assert event.event_type == EventType.RESEARCH
        assert event.message == "Automation"
        assert event.metadata == {"technology": "Automation"}
    
    def test_parse_research_completed_format(self, parser):
        """Test parsing research with 'Research completed:' format."""
        event = parser.parse("Research completed: Advanced electronics researched")
        assert event is not None
        assert event.event_type == EventType.RESEARCH
        assert "Advanced electronics" in event.message
    
    def test_parse_research_simple(self, parser):
        """Test parsing simple research format."""
        event = parser.parse("Logistics researched")
        assert event is not None
        assert event.event_type == EventType.RESEARCH
        assert "Logistics" in event.message


class TestEventParserDeath:
    """Tests for parsing DEATH events."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_death_with_cause(self, parser):
        """Test parsing death event with cause."""
        event = parser.parse("PlayerOne was killed by a biter")
        assert event is not None
        assert event.event_type == EventType.DEATH
        assert event.player_name == "PlayerOne"
        assert event.message == "a biter"
        assert event.metadata == {"cause": "a biter"}
    
    def test_parse_death_simple(self, parser):
        """Test parsing death event without cause."""
        event = parser.parse("PlayerTwo died")
        assert event is not None
        assert event.event_type == EventType.DEATH
        assert event.player_name == "PlayerTwo"
        assert event.message == "unknown"
        assert event.metadata == {"cause": "unknown"}
    
    def test_parse_death_with_tag(self, parser):
        """Test parsing death with [DEATH] tag."""
        event = parser.parse("[DEATH] PlayerThree was killed by a spitter")
        assert event is not None
        assert event.event_type == EventType.DEATH
        assert event.player_name == "PlayerThree"
        assert event.message == "a spitter"


class TestEventParserServer:
    """Tests for parsing SERVER events."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_server_message(self, parser):
        """Test parsing server message with <server>: prefix."""
        event = parser.parse("<server>: Server is restarting in 5 minutes")
        assert event is not None
        assert event.event_type == EventType.SERVER
        assert event.player_name == "server"
        assert event.message == "Server is restarting in 5 minutes"


class TestEventParserSystemMessages:
    """Tests for system message filtering."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_is_system_message_server(self, parser):
        """Test that server player name is filtered."""
        assert parser._is_system_message("server", "some message") is True
    
    def test_is_system_message_console(self, parser):
        """Test that console player name is filtered."""
        assert parser._is_system_message("console", "some message") is True
    
    def test_is_system_message_script(self, parser):
        """Test that script player name is filtered."""
        assert parser._is_system_message("script", "some message") is True
    
    def test_is_system_message_bracket_start(self, parser):
        """Test that messages starting with [ are filtered."""
        assert parser._is_system_message("PlayerOne", "[System] message") is True
    
    def test_is_not_system_message(self, parser):
        """Test that normal player messages are not filtered."""
        assert parser._is_system_message("PlayerOne", "Hello everyone!") is False


class TestEventParserEdgeCases:
    """Tests for edge cases and error handling."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_empty_string(self, parser):
        """Test parsing empty string returns None."""
        event = parser.parse("")
        assert event is None
    
    def test_parse_whitespace_only(self, parser):
        """Test parsing whitespace-only string returns None."""
        event = parser.parse("   \n\t  ")
        assert event is None
    
    def test_parse_random_text(self, parser):
        """Test parsing random text returns None."""
        event = parser.parse("This is just random text that doesn't match anything")
        assert event is None
    
    def test_parse_preserves_raw_line(self, parser):
        """Test that raw_line field is preserved."""
        raw = "2024-11-28 15:30:45 [JOIN] TestPlayer joined the game"
        event = parser.parse(raw)
        assert event is not None
        assert event.raw_line == raw


class TestFactorioEventFormatter:
    """Tests for FactorioEventFormatter.format_for_discord() method."""
    
    def test_format_join(self):
        """Test formatting JOIN event."""
        event = FactorioEvent(event_type=EventType.JOIN, player_name="TestPlayer")
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "joined the server" in formatted
    
    def test_format_leave(self):
        """Test formatting LEAVE event."""
        event = FactorioEvent(event_type=EventType.LEAVE, player_name="TestPlayer")
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "left the server" in formatted
    
    def test_format_chat(self):
        """Test formatting CHAT event."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello world"
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "Hello world" in formatted
    
    def test_format_chat_escapes_markdown(self):
        """Test that chat formatting escapes Discord markdown."""
        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="This has *asterisks* and _underscores_"
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "\\*asterisks\\*" in formatted
        assert "\\_underscores\\_" in formatted
    
    def test_format_server(self):
        """Test formatting SERVER event."""
        event = FactorioEvent(
            event_type=EventType.SERVER,
            message="Server restarting"
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "[SERVER]" in formatted
        assert "Server restarting" in formatted
    
    def test_format_server_escapes_markdown(self):
        """Test that server formatting escapes Discord markdown."""
        event = FactorioEvent(
            event_type=EventType.SERVER,
            message="Message with *markdown* _chars_"
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "\\*markdown\\*" in formatted
        assert "\\_chars\\_" in formatted
    
    def test_format_milestone(self):
        """Test formatting MILESTONE event."""
        event = FactorioEvent(
            event_type=EventType.MILESTONE,
            player_name="TestPlayer",
            message="First Steps"
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "milestone" in formatted
        assert "First Steps" in formatted
    
    def test_format_task(self):
        """Test formatting TASK event."""
        event = FactorioEvent(
            event_type=EventType.TASK,
            player_name="TestPlayer",
            message="Build 100 circuits"
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "task" in formatted
        assert "Build 100 circuits" in formatted
    
    def test_format_research(self):
        """Test formatting RESEARCH event."""
        event = FactorioEvent(
            event_type=EventType.RESEARCH,
            message="Automation"
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "Research completed" in formatted
        assert "Automation" in formatted
    
    def test_format_death_with_cause(self):
        """Test formatting DEATH event with cause."""
        event = FactorioEvent(
            event_type=EventType.DEATH,
            player_name="TestPlayer",
            metadata={"cause": "a biter"}
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "killed by a biter" in formatted
    
    def test_format_death_without_cause(self):
        """Test formatting DEATH event without cause."""
        event = FactorioEvent(
            event_type=EventType.DEATH,
            player_name="TestPlayer",
            metadata={"cause": "unknown"}
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "died" in formatted
    
    def test_format_unknown_event(self):
        """Test formatting unknown event type."""
        event = FactorioEvent(
            event_type=EventType.UNKNOWN,
            raw_line="Unknown event happened"
        )
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "Unknown event happened" in formatted


class TestIntegration:
    """Integration tests for complete parsing and formatting workflows."""
    
    @pytest.fixture
    def parser(self):
        """Create an EventParser instance for testing."""
        return EventParser()
    
    def test_parse_and_format_join(self, parser):
        """Test complete workflow: parse JOIN and format for Discord."""
        line = "2024-11-28 15:30:45 TestPlayer joined the game"
        event = parser.parse(line)
        assert event is not None
        
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "joined" in formatted
    
    def test_parse_and_format_chat(self, parser):
        """Test complete workflow: parse CHAT and format for Discord."""
        line = "TestPlayer: Hello everyone!"
        event = parser.parse(line)
        assert event is not None
        
        formatted = FactorioEventFormatter.format_for_discord(event)
        assert "TestPlayer" in formatted
        assert "Hello everyone!" in formatted
    
    def test_batch_parsing(self, parser):
        """Test parsing multiple lines in sequence."""
        lines = [
            "PlayerOne joined the game",
            "PlayerTwo joined the game",
            "PlayerOne: Hello!",
            "PlayerTwo: Hi there!",
            "PlayerOne left the game"
        ]
        
        events = [parser.parse(line) for line in lines]
        
        assert all(e is not None for e in events)
        assert events[0].event_type == EventType.JOIN
        assert events[1].event_type == EventType.JOIN
        assert events[2].event_type == EventType.CHAT
        assert events[3].event_type == EventType.CHAT
        assert events[4].event_type == EventType.LEAVE
