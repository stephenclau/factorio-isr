"""
Event parser for Factorio console logs.

Parses JOIN, LEAVE, and CHAT events from console output.
"""
import re
from dataclasses import dataclass, field
from typing import Optional, Dict
from enum import Enum

import structlog

logger = structlog.get_logger()


class EventType(Enum):
    """Types of events we can parse from Factorio logs."""
    SERVER = "server"
    JOIN = "join"
    LEAVE = "leave"
    CHAT = "chat"
    MILESTONE = "milestone"
    TASK = "task"
    RESEARCH = "research"
    DEATH = "death"
    UNKNOWN = "unknown"


@dataclass
class FactorioEvent:
    """Parsed Factorio event."""
    event_type: EventType  # Required
    player_name: Optional[str] = None
    message: Optional[str] = None
    raw_line: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None



class EventParser:
    """
    Parser for Factorio console log events.
    
    Recognizes JOIN, LEAVE, and CHAT events from log lines.
    """
    
    def __init__(self):
        """Initialize event parser with regex patterns."""
        # Common Factorio log patterns
        # Examples:
        # 2024-11-28 15:30:45 [JOIN] PlayerName joined the game
        # 2024-11-28 15:30:45 [LEAVE] PlayerName left the game
        # PlayerName: Hello everyone!
        # [CHAT] PlayerName: Hello everyone!
        
        # JOIN pattern - match player name before "joined"
        self.join_pattern = re.compile(
            r'(?:\[JOIN\]\s*)?(\w+)\s+joined(?:\s+the\s+game)?',
            re.IGNORECASE
        )
        
          # Fixed LEAVE pattern - match player name before "left/leaving"
        self.leave_pattern = re.compile(
            r'(?:\[LEAVE\]\s*)?(\w+)\s+(?:left|leaving)(?:\s+the\s+game)?',
            re.IGNORECASE
        )
        
        

        # Chat patterns - match "PlayerName: message" or "[CHAT] PlayerName: message"
        self.chat_pattern = re.compile(
            r'(?:\[CHAT\]\s*)?(\w+):\s+(.+)',
            re.IGNORECASE
        )
        # Server message pattern - match [CHAT] <server>: message OR just <server>: message
        self.server_pattern = re.compile(
            r'(?:\[CHAT\]\s*)?<server>:\s*(.+)',
            re.IGNORECASE
        )

        # Milestone mod patterns
        # Examples:
        # [Milestones] PlayerName completed milestone: First Steps
        # [MILESTONE] PlayerName: Research automation
        self.milestone_pattern = re.compile(
            r'\[MILESTONE[S]?\]\s*(\w+)(?::\s+|\s+completed\s+milestone:\s+)(.+)',
            re.IGNORECASE
        )

        # Task/Todo mod patterns
        # Examples:
        # [Task] PlayerName completed: Build 100 red circuits
        # [TODO] PlayerName finished task: Set up oil processing
        self.task_pattern = re.compile(
            r'\[(?:TASK|TODO)\]\s*(\w+)\s+(?:completed|finished)(?:\s+task)?:\s+(.+)',
            re.IGNORECASE
        )

         # Research completion
        # Examples:
        # [RESEARCH] Automation technology has been researched
        # Research completed: Advanced electronics
        self.research_pattern = re.compile(
            r'(?:\[RESEARCH\]\s*)?(?:Research\s+completed:\s*)?(.+?)\s+(?:technology\s+)?(?:has\s+been\s+)?researched',
            re.IGNORECASE
        )

        # Death events
        # Examples:
        # PlayerName was killed by a biter
        # [DEATH] PlayerName died
        self.death_pattern = re.compile(
            r'(?:\[DEATH\]\s*)?(\w+)\s+(?:was\s+killed|died)(?:\s+by\s+(.+))?',
            re.IGNORECASE
        )

    def parse(self, line: str) -> Optional[FactorioEvent]:
        """
        Parse a log line into a FactorioEvent.
        
        Args:
            line: Raw log line from console.log
        
        Returns:
            FactorioEvent if recognized, None otherwise
        """
        # Strip timestamp if present (format: YYYY-MM-DD HH:MM:SS)
        cleaned_line = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s*', '', line)
        
        # Try to match MILESTONE (check mod patterns first)
        match = self.milestone_pattern.search(cleaned_line)
        if match:
            player_name = match.group(1)
            milestone = match.group(2).strip()
            logger.debug("parsed_milestone_event", player=player_name, milestone=milestone)
            return FactorioEvent(
                event_type=EventType.MILESTONE,
                player_name=player_name,
                message=milestone,
                raw_line=line,
                metadata={"milestone": milestone}
            )
        
        # Try to match TASK
        match = self.task_pattern.search(cleaned_line)
        if match:
            player_name = match.group(1)
            task = match.group(2).strip()
            logger.debug("parsed_task_event", player=player_name, task=task)
            return FactorioEvent(
                event_type=EventType.TASK,
                player_name=player_name,
                message=task,
                raw_line=line,
                metadata={"task": task}
            )
        
        # Try to match RESEARCH
        match = self.research_pattern.search(cleaned_line)
        if match:
            technology = match.group(1).strip()
            logger.debug("parsed_research_event", technology=technology)
            return FactorioEvent(
                event_type=EventType.RESEARCH,
                message=technology,
                raw_line=line,
                metadata={"technology": technology}
            )
        
        # Try to match DEATH
        match = self.death_pattern.search(cleaned_line)
        if match:
            player_name = match.group(1)
            cause = match.group(2).strip() if match.group(2) else "unknown"
            logger.debug("parsed_death_event", player=player_name, cause=cause)
            return FactorioEvent(
                event_type=EventType.DEATH,
                player_name=player_name,
                message=cause,
                raw_line=line,
                metadata={"cause": cause}
            )


        # Try to match JOIN
        match = self.join_pattern.search(cleaned_line)
        if match:
            player_name = match.group(1)
            logger.debug("parsed_join_event", player=player_name, line=line[:100])
            return FactorioEvent(
                event_type=EventType.JOIN,
                player_name=player_name,
                raw_line=line
            )
        
        # Try to match LEAVE
        match = self.leave_pattern.search(cleaned_line)
        if match:
            player_name = match.group(1)
            logger.debug("parsed_leave_event", player=player_name, line=line[:100])
            return FactorioEvent(
                event_type=EventType.LEAVE,
                player_name=player_name,
                raw_line=line
            )
        # Try to match SERVER messages (check before general CHAT pattern)
        match = self.server_pattern.search(cleaned_line)
        if match:
            message = match.group(1)
            logger.debug("parsed_server_event", message=message[:150])
            return FactorioEvent(
                event_type=EventType.SERVER,
                player_name="server",
                message=message,
                raw_line=line
            )
        
        # Try to match CHAT
        match = self.chat_pattern.search(cleaned_line)
        if match:
            player_name = match.group(1)
            message = match.group(2)
            
            # Filter out system messages (usually contain brackets or special chars)
            if not self._is_system_message(player_name, message):
                logger.debug(
                    "parsed_chat_event",
                    player=player_name,
                    message=message[:255]
                )
                return FactorioEvent(
                    event_type=EventType.CHAT,
                    player_name=player_name,
                    message=message,
                    raw_line=line
                )
        


        # No match
        logger.debug("unparsed_line", line=line[:100])
        return None
    
    def _is_system_message(self, player_name: str, message: str) -> bool:
        """
        Check if a chat message is actually a system message.
        
        Args:
            player_name: Extracted player name
            message: Extracted message
        
        Returns:
            True if this looks like a system message, False if player chat
        """
        # Common system message indicators
        system_indicators = [
            'server',
            'console',
            'script',
            'mod',
        ]
        
        player_lower = player_name.lower()
        message_lower = message.lower()
        
        # Check if player name looks like a system identifier
        for indicator in system_indicators:
            if indicator in player_lower:
                return True
        
        # Check for common system message patterns
        #if message.startswith('[') or message.startswith('<'):
        if message.startswith('['):
            return True
        
        return False


class FactorioEventFormatter:
    """
    Formatter for Factorio events to Discord messages.
    
    Converts parsed FactorioEvent objects into Discord-formatted strings
    with appropriate emoji and markdown formatting.
    """
    
    @staticmethod
    def format_for_discord(event: FactorioEvent) -> str:
        """
        Format a FactorioEvent as a Discord message.
        
        Args:
            event: Parsed event to format
            
        Returns:
            Formatted string for Discord with emoji and markdown
        """
        # Assert event_type is not None
        assert event.event_type is not None, "Event type cannot be None"
        
        # Handle each event type explicitly
        event_type = event.event_type
        
        if event_type == EventType.JOIN:
            player = event.player_name or "Unknown"
            return f"**{player}** joined the server"
        
        if event_type == EventType.LEAVE:
            player = event.player_name or "Unknown"
            return f"**{player}** left the server"
        
        if event_type == EventType.SERVER:
            # Special formatting for server messages
            safe_message = event.message.replace('*', '\\*').replace('_', '\\_') if event.message else ""
            return f"**[SERVER]**: {safe_message}"
        
        if event_type == EventType.CHAT:
            # Escape Discord markdown in player messages
            player = event.player_name or "Unknown"
            safe_message = event.message.replace('*', '\\*').replace('_', '\\_') if event.message else ""
            return f"**{player}**: {safe_message}"
        
        if event_type == EventType.MILESTONE:
            player = event.player_name or "Unknown"
            milestone = event.message or "unknown milestone"
            return f"**{player}** completed milestone: *{milestone}*"
        
        if event_type == EventType.TASK:
            player = event.player_name or "Unknown"
            task = event.message or "unknown task"
            return f"**{player}** completed task: *{task}*"
        
        if event_type == EventType.RESEARCH:
            tech = event.message or "unknown technology"
            return f"Research completed: **{tech}**"
        
        if event_type == EventType.DEATH:
            player = event.player_name or "Unknown"
            if event.metadata and event.metadata.get("cause") != "unknown":
                cause = event.metadata["cause"]
                return f"**{player}** was killed by {cause}"
            else:
                return f"**{player}** died"
        
        # Fallback for UNKNOWN or any other event type - this MUST execute if none above match
        raw = event.raw_line or "Unknown event"
        return f"{raw}"
