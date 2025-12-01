"""
Event parser for Factorio log files.

Parses log lines and extracts structured events using YAML-configured patterns
with multi-channel routing support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import re
import structlog

# Try/except for both relative and absolute imports
try:  # pragma: no cover - import wiring
    from .pattern_loader import PatternLoader, EventPattern
except ImportError:  # pragma: no cover - import wiring
    from pattern_loader import PatternLoader, EventPattern  # type: ignore[no-redef]

logger = structlog.get_logger()


class EventType(str, Enum):
    """Types of Factorio events."""
    JOIN = "join"
    LEAVE = "leave"
    CHAT = "chat"
    SERVER = "server"
    MILESTONE = "milestone"
    TASK = "task"
    RESEARCH = "research"
    DEATH = "death"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FactorioEvent:
    """Parsed Factorio event with metadata and channel routing."""
    event_type: EventType
    player_name: Optional[str] = None
    message: Optional[str] = None
    raw_line: str = ""
    emoji: str = ""
    formatted_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)  # ✅ Channel routing info


# Type alias for compiled pattern storage
CompiledPatternMap = Dict[str, Tuple[re.Pattern[str], EventPattern]]


class EventParser:
    """Parse Factorio log events using YAML-configured patterns."""
    
    def __init__(
        self,
        patterns_dir: Path = Path("patterns"),
        pattern_files: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize event parser with pattern loader.
        
        Args:
            patterns_dir: Directory containing YAML pattern files.
            pattern_files: Specific pattern files to load (None = load all).
        """
        if not isinstance(patterns_dir, Path):
            raise AssertionError(f"patterns_dir must be Path, got {type(patterns_dir)}")
        
        self.pattern_loader = PatternLoader(patterns_dir)
        self.compiled_patterns: CompiledPatternMap = {}
        
        count = self.pattern_loader.load_patterns(pattern_files)
        logger.info("event_parser_initialized", patterns_loaded=count)
        
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile all loaded patterns into regex objects."""
        patterns: Iterable[EventPattern] = self.pattern_loader.get_patterns(
            enabled_only=True
        )
        
        compiled: CompiledPatternMap = {}
        for pattern in patterns:
            try:
                regex = re.compile(pattern.pattern, re.IGNORECASE)
            except re.error as exc:
                logger.error(
                    "pattern_compile_failed",
                    name=pattern.name,
                    pattern=pattern.pattern,
                    error=str(exc),
                )
                continue
            
            compiled[pattern.name] = (regex, pattern)
            logger.debug(
                "pattern_compiled",
                name=pattern.name,
                type=pattern.event_type,
                channel=pattern.channel  # ✅ Log channel info
            )
        
        self.compiled_patterns = compiled
        logger.info("patterns_compiled", total=len(self.compiled_patterns))
    
    def parse_line(self, line: str) -> Optional[FactorioEvent]:
        """
        Parse a single log line into a FactorioEvent.
        
        Args:
            line: Raw log line from console.log.
        
        Returns:
            FactorioEvent if line matches a pattern, None otherwise.
        """
        if not isinstance(line, str):
            raise AssertionError(f"line must be str, got {type(line)}")
        
        if not line or not line.strip():
            return None
        
        # Try each pattern in (priority) order as supplied by PatternLoader.
        for _name, (compiled_regex, pattern_config) in self.compiled_patterns.items():
            match = compiled_regex.search(line)
            if match:
                return self._create_event(line, match, pattern_config)
        
        return None
    
    def _create_event(
        self,
        line: str,
        match: re.Match[str],
        pattern: EventPattern,
    ) -> FactorioEvent:
        """
        Create a FactorioEvent from a regex match with channel routing.
        """
        if not isinstance(line, str):
            raise AssertionError("line must be str")
        if not isinstance(match, re.Match):
            raise AssertionError("match must be re.Match")
        if not isinstance(pattern, EventPattern):
            raise AssertionError("pattern must be EventPattern")
        
        player_name: Optional[str] = None
        message: Optional[str] = None
        
        # Group indices are 1-based; lastindex can be None.
        lastindex = match.lastindex or 0
        
        if lastindex >= 1:
            try:
                player_name = match.group(1)
            except (IndexError, AttributeError):
                player_name = None
        
        if lastindex:
            try:
                if lastindex == 1:
                    # With a single group, treat it as message for server events only.
                    if self._map_event_type(pattern.event_type) == EventType.SERVER:
                        message = match.group(1)
                elif lastindex >= 2:
                    message = match.group(2)
            except (IndexError, AttributeError):
                message = None
        
        event_type = self._map_event_type(pattern.event_type)
        formatted_message = self._format_message(
            pattern.message_template,
            player_name,
            message,
        )
        
        # ✅ Build metadata with channel routing information
        metadata: Dict[str, Any] = {}
        if pattern.channel:
            metadata['channel'] = pattern.channel
            logger.debug(
                "event_routed_to_channel",
                channel=pattern.channel,
                event_type=event_type.value
            )
        
        event = FactorioEvent(
            event_type=event_type,
            player_name=player_name,
            message=message,
            raw_line=line.strip(),
            emoji=pattern.emoji,
            formatted_message=formatted_message,
            metadata=metadata,  # ✅ Include routing metadata
        )
        
        logger.debug(
            "event_parsed",
            type=event.event_type.value,
            player=player_name,
            pattern=pattern.name,
            channel=pattern.channel  # ✅ Log channel info
        )
        
        return event
    
    def _map_event_type(self, type_str: str) -> EventType:
        """
        Map string event type to EventType enum.
        """
        if not isinstance(type_str, str):
            raise AssertionError("type_str must be str")
        
        try:
            return EventType(type_str.lower())
        except ValueError:
            logger.warning("unknown_event_type", type=type_str)
            return EventType.UNKNOWN
    
    def _format_message(
        self,
        template: str,
        player_name: Optional[str],
        message: Optional[str],
    ) -> str:
        """
        Format event message using template.
        """
        if not isinstance(template, str):
            raise AssertionError("template must be str")
        
        if not template:
            if player_name and message:
                return f"{player_name}: {message}"
            if player_name:
                return player_name
            if message:
                return message
            return ""
        
        result = template
        if player_name:
            result = result.replace("{player}", player_name)
        if message:
            result = result.replace("{message}", message)
        
        return result
    
    def reload_patterns(self) -> int:
        """
        Reload patterns from disk and recompile.
        
        Returns:
            Number of patterns loaded.
        """
        count = self.pattern_loader.reload()
        self._compile_patterns()
        logger.info("patterns_reloaded", count=count)
        return count


class FactorioEventFormatter:
    """Format Factorio events for Discord display."""
    
    @staticmethod
    def format_for_discord(event: FactorioEvent) -> str:
        """
        Format a FactorioEvent as a Discord message.
        """
        if not isinstance(event, FactorioEvent):
            raise AssertionError(
                f"event must be FactorioEvent, got {type(event)}"
            )
        
        # Preferred: use preformatted message if provided.
        if event.formatted_message:
            if event.emoji:
                return f"{event.emoji} {event.formatted_message}"
            return event.formatted_message
        
        # Fallback formatting based on event type.
        if event.event_type == EventType.JOIN:
            return f"👋 {event.player_name} joined the server"
        
        if event.event_type == EventType.LEAVE:
            return f"👋 {event.player_name} left the server"
        
        if event.event_type == EventType.CHAT:
            safe_message = (
                event.message.replace("*", "\\*").replace("_", "\\_")
                if event.message
                else ""
            )
            return f"💬 {event.player_name}: {safe_message}"
        
        if event.event_type == EventType.SERVER:
            return f"🔧 Server: {event.message}"
        
        if event.event_type == EventType.MILESTONE:
            return f"🏆 {event.player_name} completed: {event.message}"
        
        if event.event_type == EventType.TASK:
            return f"✅ {event.player_name} finished: {event.message}"
        
        if event.event_type == EventType.RESEARCH:
            return f"🔬 Research completed: {event.message}"
        
        if event.event_type == EventType.DEATH:
            return f"💀 {event.player_name} {event.message}"
        
        return event.raw_line
