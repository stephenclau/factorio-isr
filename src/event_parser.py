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

"""
Event parser for Factorio log files.

Parses log lines and extracts structured events using YAML-configured patterns
with multi-channel routing support and @mention detection.

SECURITY HARDENING (Runtime Defenses):
- ReDoS protection via google-re2 (linear-time regex engine)
- Timeout wrapper for regex matching (fallback if RE2 unavailable)
- Discord markdown escaping to prevent formatting exploits
- Selective @mention sanitization: blocks @everyone/@here, preserves user/role mentions
- Input length limits on log lines
- Safe template substitution (only .replace(), never eval/format)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import signal
import re as stdlib_re  # For selective mention sanitization
import structlog

from security_monitor import SecurityMonitor, Infraction

# SECURITY: Try to use google-re2 for ReDoS immunity
try:
    import google_re2 as re  # type: ignore
    USING_RE2 = True
except ImportError:
    import re
    USING_RE2 = False

# Try/except for both relative and absolute imports
try:  # pragma: no cover - import wiring
    from .pattern_loader import PatternLoader, EventPattern
except ImportError:  # pragma: no cover - import wiring
    from pattern_loader import PatternLoader, EventPattern  # type: ignore[no-redef]

logger = structlog.get_logger()

# Security configuration constants
MAX_LINE_LENGTH = 10000  # chars - reject extremely long log lines
MAX_PLAYER_NAME_LENGTH = 100  # chars
MAX_MESSAGE_LENGTH = 1000  # chars
REGEX_TIMEOUT_SECONDS = 1  # max time per pattern match (if using stdlib re)

# Log RE2 status
if USING_RE2:
    logger.info("event_parser_using_re2", redos_protection=True)
else:
    logger.warning(
        "event_parser_using_stdlib_re",
        redos_protection=False,
        recommendation="Install google-re2 for better security: pip install google-re2"
    )


class TimeoutError(Exception):
    """Raised when regex matching exceeds timeout."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for regex timeout."""
    raise TimeoutError("Regex match exceeded timeout")


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
    MENTION = "mention"  # used when you want to explicitly treat something as a mention


@dataclass(frozen=True, slots=True)
class FactorioEvent:
    """Parsed Factorio event with metadata and channel routing."""
    event_type: EventType
    player_name: Optional[str] = None
    message: Optional[str] = None
    raw_line: str = ""
    emoji: str = ""
    formatted_message: str = ""
    # metadata carries routing info plus mention info:
    # - channel: str
    # - mentions: list[str]
    # - mention_type: "user" | "group" | "mixed"
    metadata: Dict[str, Any] = field(default_factory=dict)


# Type alias for compiled pattern storage
CompiledPatternMap = Dict[str, Tuple[re.Pattern[str], EventPattern]]


class EventParser:
    """Parse Factorio log events using YAML-configured patterns."""

    def __init__(
        self,
        patterns_dir: Path = Path("patterns"),
        pattern_files: Optional[List[str]] = None,
        security_monitor: Optional[SecurityMonitor] = None, 
        security_channel: Optional[str] = None,  
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
        
        self.security_monitor = security_monitor or SecurityMonitor()
        self.security_channel = security_channel or "security-alerts"

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
                channel=pattern.channel,
            )

        self.compiled_patterns = compiled
        logger.info("patterns_compiled", total=len(self.compiled_patterns))

    def _safe_regex_search(
        self,
        compiled_regex: re.Pattern[str],
        line: str,
        pattern_name: str
    ) -> Optional[re.Match[str]]:
        """
        Safely execute regex search with timeout protection.

        Args:
            compiled_regex: Compiled regex pattern
            line: Input line to search
            pattern_name: Pattern name (for logging)

        Returns:
            Match object or None
        """
        if USING_RE2:
            # RE2 is linear-time, no timeout needed
            try:
                return compiled_regex.search(line)
            except Exception as exc:
                logger.warning(
                    "re2_search_failed",
                    pattern=pattern_name,
                    error=str(exc)
                )
                return None

        # SECURITY: Timeout wrapper for stdlib re to prevent ReDoS
        # Note: signal.alarm only works on Unix; for Windows, consider threading
        try:
            # Set timeout alarm
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(REGEX_TIMEOUT_SECONDS)

            try:
                match = compiled_regex.search(line)
                return match
            finally:
                # Always clear the alarm
                signal.alarm(0)

        except TimeoutError:
            logger.warning(
                "regex_timeout",
                pattern=pattern_name,
                line_preview=line[:100],
                timeout_seconds=REGEX_TIMEOUT_SECONDS
            )
            return None
        except AttributeError:
            # signal.alarm not available (Windows)
            logger.debug("signal_alarm_unavailable", using_untimed_regex=True)
            try:
                return compiled_regex.search(line)
            except Exception as exc:
                logger.warning("regex_search_failed", pattern=pattern_name, error=str(exc))
                return None
        except Exception as exc:
            logger.error(
                "unexpected_regex_error",
                pattern=pattern_name,
                error=str(exc),
                error_type=type(exc).__name__
            )
            return None

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

        # SECURITY: Reject extremely long lines to prevent DoS
        if len(line) > MAX_LINE_LENGTH:
            logger.warning(
                "line_too_long",
                length=len(line),
                max=MAX_LINE_LENGTH,
                preview=line[:100]
            )
            return None

        event: Optional[FactorioEvent] = None

        for pattern_name, (compiled_regex, pattern_config) in self.compiled_patterns.items():
            match = self._safe_regex_search(compiled_regex, line, pattern_name)
            if match:
                event = self._create_event(line, match, pattern_config)
                break

        if not event:
            return None

        # Security monitor integration
        if event.player_name:
            if self.security_monitor.is_banned(event.player_name):
                logger.warning(
                    "blocked_event_from_banned_player",
                    player=event.player_name,
                    type=event.event_type.value,
                )
                return None

            if event.message:
                infraction = self.security_monitor.check_malicious_pattern(
                    text=event.message,
                    player_name=event.player_name,
                )
                if infraction:
                    return self._create_security_alert_event(event, infraction)

        return event    
            
        # Try each pattern in (priority) order as supplied by PatternLoader.
        for pattern_name, (compiled_regex, pattern_config) in self.compiled_patterns.items():
            match = self._safe_regex_search(compiled_regex, line, pattern_name)
            if match:
                return self._create_event(line, match, pattern_config)
            
                if event and event.player_name:
                    # Check if player is banned
                    if self.security_monitor.is_banned(event.player_name):
                        logger.warning(
                            "blocked_event_from_banned_player",
                            player=event.player_name,
                            type=event.event_type.value,
                        )
                        return None  # Silently drop events from banned players

                    # Check for malicious patterns in message
                    if event.message:
                        infraction = self.security_monitor.check_malicious_pattern(
                            text=event.message,
                            player_name=event.player_name,
                        )

                        if infraction:
                            # Create security alert event
                            return self._create_security_alert_event(event, infraction)

        return None

    def _create_security_alert_event(
        self,
        original_event: FactorioEvent,
        infraction: Infraction,
    ) -> FactorioEvent:
        """
        Create a security alert event for an infraction.

        Args:
            original_event: The original event that triggered the alert
            infraction: The infraction record

        Returns:
            Modified event for security channel with alert formatting
        """
        # Format security alert message
        alert_parts = [
            f"🚨 **SECURITY ALERT** 🚨",
            f"**Player:** {infraction.player_name}",
            f"**Severity:** {infraction.severity.upper()}",
            f"**Type:** {infraction.metadata.get("description")}",
            f"**Matched:** `{infraction.metadata.get('match', 'N/A')}`",
            f"**Action:** {'BANNED' if infraction.auto_banned else 'LOGGED'}",
            f"**Time:** {infraction.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Raw:** `{infraction.raw_text[:100]}...`",
        ]

        formatted_alert = "\n".join(alert_parts)

        # Create new event for security channel
        return FactorioEvent(
            event_type=EventType.SERVER,  # Or create new EventType.SECURITY
            player_name=infraction.player_name,
            message=formatted_alert,
            raw_line=original_event.raw_line,
            emoji="🚨",
            formatted_message=formatted_alert,
            metadata={
                "channel": self.security_channel,  # Route to security channel
                "infraction": infraction.to_dict(),
                "severity": infraction.severity,
                "auto_banned": infraction.auto_banned,
            },
        )

    def check_rate_limit_for_event(
        self,
        event: FactorioEvent,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if event should be rate-limited.

        Args:
            event: Event to check

        Returns:
            (allowed, reason) - True if allowed, False if rate-limited
        """
        if not event.player_name:
            return True, None

        # Determine action type from event metadata
        action_type = "chat_message"  # Default

        if event.metadata.get("mentions"):
            mention_type = event.metadata.get("mention_type", "user")
            if mention_type == "group":
                action_type = "mention_admin"
            elif "everyone" in event.metadata.get("mentions", []):
                action_type = "mention_everyone"

        return self.security_monitor.check_rate_limit(
            action_type=action_type,
            player_name=event.player_name,
        )



    def _extract_mentions(self, message: Optional[str]) -> List[str]:
        """
        Extract @mentions from message text.

        Returns a list of tokens without the @ prefix, e.g. '@John @admins' -> ['John', 'admins'].
        """
        if not message:
            return []

        mention_pattern = r"@(\w+)"
        return re.findall(mention_pattern, message)

    def _classify_mentions(self, mentions: List[str]) -> str:
        """
        Classify mentions as user, group, or mixed.

        Heuristic only; final mapping is done in DiscordBot.
        """
        if not mentions:
            return "user"

        group_keywords = {
            "admins",
            "admin",
            "mods",
            "mod",
            "moderators",
            "moderator",
            "everyone",
            "here",
            "staff",
        }

        has_users = False
        has_groups = False

        for m in mentions:
            if m.lower() in group_keywords:
                has_groups = True
            else:
                has_users = True

        if has_groups and has_users:
            return "mixed"
        if has_groups:
            return "group"
        return "user"

    def _sanitize_player_name(self, player_name: str) -> str:
        """
        Sanitize player name for safe Discord display.

        - Escape Discord markdown
        - Block @everyone/@here abuse (mass pings)
        - PRESERVE @username mentions for your mention feature
        - Enforce length limit
        """
        if not player_name:
            return ""

        # SECURITY: Length limit
        safe = player_name[:MAX_PLAYER_NAME_LENGTH]

        # SECURITY: Escape Discord markdown characters
        safe = safe.replace("*", "\\*")
        safe = safe.replace("_", "\\_")
        safe = safe.replace("`", "\\`")
        safe = safe.replace("~", "\\~")
        safe = safe.replace("|", "\\|")

        # SECURITY: Selective mention blocking - only dangerous mass pings
        # Block @everyone and @here (case-insensitive)
        # Preserve @username and @role mentions for your feature
        # FIX: Use actual unicode character, not raw string
        zero_width_space = '\u200b'
        safe = stdlib_re.sub(
            r'@(everyone|here)\b',
            f'@{zero_width_space}\\1',
            safe,
            flags=stdlib_re.IGNORECASE
        )

        return safe

    def _sanitize_message(self, message: str) -> str:
        """
        Sanitize message text for safe Discord display.

        - Escape Discord markdown
        - Block @everyone/@here abuse (mass pings)
        - PRESERVE @username and @role mentions for your mention feature
        - Enforce length limit
        """
        if not message:
            return ""

        # SECURITY: Length limit
        safe = message[:MAX_MESSAGE_LENGTH]

        # SECURITY: Escape Discord markdown characters
        safe = safe.replace("*", "\\*")
        safe = safe.replace("_", "\\_")
        safe = safe.replace("`", "\\`")
        safe = safe.replace("~", "\\~")
        safe = safe.replace("|", "\\|")

        # SECURITY: Selective mention blocking - only dangerous mass pings
        # Block @everyone and @here (case-insensitive)
        # Preserve @username and @role mentions for your feature
        # FIX: Use actual unicode character, not raw string
        zero_width_space = '\u200b'
        safe = stdlib_re.sub(
            r'@(everyone|here)\b',
            f'@{zero_width_space}\\1',
            safe,
            flags=stdlib_re.IGNORECASE
        )

        return safe

    def _create_event(
        self,
        line: str,
        match: re.Match[str],
        pattern: EventPattern,
    ) -> FactorioEvent:
        """
        Create a FactorioEvent from a regex match with channel routing and mention detection.
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

        # Build metadata with channel routing information
        metadata: Dict[str, Any] = {}
        if pattern.channel:
            metadata["channel"] = pattern.channel

        # Mention detection for chat/server text
        mentions = self._extract_mentions(message)
        if mentions:
            metadata["mentions"] = mentions
            metadata["mention_type"] = self._classify_mentions(mentions)
            logger.debug(
                "mentions_detected",
                player=player_name,
                mentions=mentions,
                mention_type=metadata["mention_type"],
            )

        logger.debug(
            "event_routed_to_channel",
            channel=pattern.channel,
            event_type=event_type.value,
        )

        event = FactorioEvent(
            event_type=event_type,
            player_name=player_name,
            message=message,
            raw_line=line.strip(),
            emoji=pattern.emoji,
            formatted_message=formatted_message,
            metadata=metadata,
        )

        logger.debug(
            "event_parsed",
            type=event.event_type.value,
            player=player_name,
            pattern=pattern.name,
            channel=pattern.channel,
        )

        return event

    def _map_event_type(self, type_str: str) -> EventType:
        """Map string event type to EventType enum."""
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
        Format event message using template with SAFE substitution.

        SECURITY: Uses only .replace() for substitution, never .format() or eval.
        All extracted values are sanitized before substitution.
        """
        if not isinstance(template, str):
            raise AssertionError("template must be str")

        if not template:
            if player_name and message:
                # SECURITY: Sanitize before concatenation
                return f"{self._sanitize_player_name(player_name)}: {self._sanitize_message(message)}"
            if player_name:
                return self._sanitize_player_name(player_name)
            if message:
                return self._sanitize_message(message)
            return ""

        result = template

        # SECURITY: Sanitize extracted values before substitution
        if player_name:
            safe_player = self._sanitize_player_name(player_name)
            result = result.replace("{player}", safe_player)

        if message:
            safe_message = self._sanitize_message(message)
            result = result.replace("{message}", safe_message)

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

        Note: Input sanitization happens in EventParser._format_message(),
        so event.formatted_message and event.player_name are already safe.
        """
        # Validate input
        assert isinstance(event, FactorioEvent), "event must be FactorioEvent"

        # Preferred: use preformatted message if provided.
        if event.formatted_message:
            if event.emoji:
                return f"{event.emoji} {event.formatted_message}"
            return event.formatted_message

        # Fallback formatting based on event type.
        # Note: event.player_name and event.message are already sanitized
        if event.event_type == EventType.JOIN:
            return f"👋 **{event.player_name}** joined the server"

        if event.event_type == EventType.LEAVE:
            return f"👋 **{event.player_name}** left the server"

        if event.event_type == EventType.CHAT:
            return f"💬 **{event.player_name}**: {event.message or ''}"

        if event.event_type == EventType.MENTION:
            return f"📢 **{event.player_name}**: {event.message or ''}"

        if event.event_type == EventType.SERVER:
            return f"🖥️ **Server:** {event.message}"

        if event.event_type == EventType.MILESTONE:
            return f"🏆 **{event.player_name}** completed: *{event.message}*"

        if event.event_type == EventType.TASK:
            return f"✔️ **{event.player_name}** finished: *{event.message}*"

        if event.event_type == EventType.RESEARCH:
            return f"🔬 Research completed: **{event.message}**"

        if event.event_type == EventType.DEATH:
            return f"💀 **{event.player_name}** {event.message}"

        return event.raw_line
