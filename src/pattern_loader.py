



"""
Pattern loader for YAML-based event configurations.

Loads event patterns from YAML files for flexible parsing configuration.

SECURITY HARDENING:
- Pattern length limits (max 500 chars) to prevent ReDoS
- YAML key whitelist to prevent config injection
- Template placeholder validation (only {player} and {message})
- Max patterns per file limit (100)
- Max file size limit (1MB)
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import re
import yaml
import structlog

logger = structlog.get_logger()

# Security configuration constants
MAX_PATTERN_LENGTH = 500  # chars
MAX_TEMPLATE_LENGTH = 200  # chars
MAX_PATTERNS_PER_FILE = 100
MAX_FILE_SIZE_BYTES = 1024 * 1024  # 1MB
ALLOWED_YAML_KEYS: Set[str] = {
    "pattern", "type", "emoji", "message", 
    "enabled", "priority", "channel", "description"
}
ALLOWED_TEMPLATE_PLACEHOLDERS: Set[str] = {"player", "message"}


class EventPattern:
    """Single event pattern configuration."""

    def __init__(
        self,
        name: str,
        pattern: str,
        event_type: str,
        emoji: str = "",
        message_template: str = "",
        enabled: bool = True,
        priority: int = 10,
        channel: Optional[str] = None
    ):
        """
        Initialize event pattern with security validation.

        Args:
            name: Pattern identifier
            pattern: Regex pattern string
            event_type: Event type (join, leave, chat, etc.)
            emoji: Discord emoji for this event
            message_template: Format string for Discord message
            enabled: Whether this pattern is active
            priority: Pattern matching priority (lower = higher priority)
            channel: Optional channel to route the message
        """
        # Type assertions
        assert isinstance(name, str), f"name must be str, got {type(name)}"
        assert isinstance(pattern, str), f"pattern must be str, got {type(pattern)}"
        assert isinstance(event_type, str), f"event_type must be str, got {type(event_type)}"
        assert isinstance(emoji, str), f"emoji must be str, got {type(emoji)}"
        assert isinstance(message_template, str), f"message_template must be str, got {type(message_template)}"
        assert isinstance(enabled, bool), f"enabled must be bool, got {type(enabled)}"
        assert isinstance(priority, int), f"priority must be int, got {type(priority)}"
        assert channel is None or isinstance(channel, str), f"channel must be None or str, got {type(channel)}"

        # Value assertions - basic
        assert len(name) > 0, "name cannot be empty"
        assert len(pattern) > 0, "pattern cannot be empty"
        assert len(event_type) > 0, "event_type cannot be empty"
        assert priority >= 0, f"priority must be non-negative, got {priority}"

        # SECURITY: Pattern length limit
        assert len(pattern) <= MAX_PATTERN_LENGTH, \
            f"pattern too long: {len(pattern)} chars (max {MAX_PATTERN_LENGTH})"

        # SECURITY: Template length limit
        assert len(message_template) <= MAX_TEMPLATE_LENGTH, \
            f"message_template too long: {len(message_template)} chars (max {MAX_TEMPLATE_LENGTH})"

        # SECURITY: Validate template placeholders
        if message_template:
            placeholders = set(re.findall(r'\{(\w+)\}', message_template))
            invalid_placeholders = placeholders - ALLOWED_TEMPLATE_PLACEHOLDERS
            assert not invalid_placeholders, \
                f"message_template contains disallowed placeholders: {invalid_placeholders}. " \
                f"Only {ALLOWED_TEMPLATE_PLACEHOLDERS} are allowed."

        # SECURITY: Name validation (alphanumeric + underscore only)
        assert re.match(r'^[a-zA-Z0-9_]+$', name), \
            f"name must be alphanumeric with underscores only, got: {name}"

        self.name: str = name
        self.pattern: str = pattern
        self.event_type: str = event_type
        self.emoji: str = emoji
        self.message_template: str = message_template
        self.enabled: bool = enabled
        self.priority: int = priority
        self.channel: Optional[str] = channel

    def __repr__(self) -> str:
        """String representation of pattern."""
        return (
            f"EventPattern(name={self.name!r}, type={self.event_type!r}, "
            f"enabled={self.enabled}, priority={self.priority})"
        )


class PatternLoader:
    """Loads and manages event patterns from YAML files."""

    def __init__(self, patterns_dir: Path = Path("patterns")):
        """
        Initialize pattern loader.

        Args:
            patterns_dir: Directory containing YAML pattern files
        """
        assert isinstance(patterns_dir, Path), f"patterns_dir must be Path, got {type(patterns_dir)}"
        self.patterns_dir: Path = patterns_dir
        self.patterns: List[EventPattern] = []
        self._loaded_files: List[str] = []

    def load_patterns(self, pattern_files: Optional[List[str]] = None) -> int:
        """
        Load patterns from YAML files.

        Args:
            pattern_files: List of YAML filenames to load. If None, loads all .yml files.

        Returns:
            Number of patterns loaded (including disabled ones)
        """
        assert pattern_files is None or isinstance(pattern_files, list), \
            f"pattern_files must be None or list, got {type(pattern_files)}"
        if pattern_files is not None:
            assert all(isinstance(f, str) for f in pattern_files), \
                "All pattern_files must be strings"

        if not self.patterns_dir.exists():
            logger.warning("patterns_directory_not_found", path=str(self.patterns_dir))
            return 0

        # Determine which files to load
        yaml_files: List[Path]
        if pattern_files is None:
            yaml_files = list(self.patterns_dir.glob("*.yml")) + list(self.patterns_dir.glob("*.yaml"))
        else:
            yaml_files = [self.patterns_dir / f for f in pattern_files]

        loaded_count: int = 0
        for yaml_file in yaml_files:
            assert isinstance(yaml_file, Path), f"yaml_file must be Path, got {type(yaml_file)}"

            if not yaml_file.exists():
                logger.warning("pattern_file_not_found", file=str(yaml_file))
                continue

            # SECURITY: Check file size before loading
            file_size = yaml_file.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                logger.error(
                    "pattern_file_too_large",
                    file=str(yaml_file),
                    size_bytes=file_size,
                    max_bytes=MAX_FILE_SIZE_BYTES
                )
                continue

            count = self._load_file(yaml_file)
            assert isinstance(count, int), f"_load_file must return int, got {type(count)}"
            assert count >= 0, f"_load_file returned negative count: {count}"
            loaded_count += count
            self._loaded_files.append(yaml_file.name)
            logger.info(
                "patterns_loaded",
                file=yaml_file.name,
                count=count
            )

        # Sort patterns by priority
        self.patterns.sort(key=lambda p: p.priority)

        # Verify all patterns are EventPattern instances
        assert all(isinstance(p, EventPattern) for p in self.patterns), \
            "All patterns must be EventPattern instances"

        logger.info(
            "pattern_loading_complete",
            total_patterns=loaded_count,
            files=self._loaded_files
        )

        return loaded_count

    def _load_file(self, yaml_file: Path) -> int:
        """
        Load patterns from a single YAML file.

        Args:
            yaml_file: Path to YAML file

        Returns:
            Number of patterns loaded from this file (including disabled)
        """
        assert isinstance(yaml_file, Path), f"yaml_file must be Path, got {type(yaml_file)}"
        assert yaml_file.exists(), f"yaml_file does not exist: {yaml_file}"

        with open(yaml_file, 'r', encoding='utf-8') as f:
            # SECURITY: Use safe_load to prevent arbitrary code execution
            data: Any = yaml.safe_load(f)

        # Type check loaded data
        if data is None:
            logger.warning("empty_yaml_file", file=str(yaml_file))
            return 0

        if not isinstance(data, dict):
            logger.warning("yaml_root_not_dict", file=str(yaml_file), type=type(data).__name__)
            return 0

        if 'events' not in data:
            logger.warning("no_events_in_file", file=str(yaml_file), keys=list(data.keys()))
            return 0

        if not isinstance(data['events'], dict):
            logger.warning("events_not_dict", file=str(yaml_file), type=type(data['events']).__name__)
            return 0

        # SECURITY: Limit number of patterns per file
        if len(data['events']) > MAX_PATTERNS_PER_FILE:
            logger.error(
                "too_many_patterns_in_file",
                file=str(yaml_file),
                count=len(data['events']),
                max=MAX_PATTERNS_PER_FILE
            )
            return 0

        count: int = 0
        for event_name, config in data["events"].items():
            # Validate event name type
            if not isinstance(event_name, str):
                logger.warning(
                    "invalid_event_name_type",
                    name=event_name,
                    type=type(event_name).__name__,
                    file=str(yaml_file)
                )
                continue

            # Validate config is dict
            if not isinstance(config, dict):
                logger.warning(
                    "invalid_event_config_type",
                    name=event_name,
                    type=type(config).__name__,
                    file=str(yaml_file)
                )
                continue

            # SECURITY: Whitelist allowed YAML keys
            unexpected_keys = set(config.keys()) - ALLOWED_YAML_KEYS
            if unexpected_keys:
                logger.warning(
                    "unexpected_yaml_keys",
                    name=event_name,
                    keys=list(unexpected_keys),
                    allowed=list(ALLOWED_YAML_KEYS),
                    file=str(yaml_file)
                )
                continue  # Reject entire entry if unknown keys present

            # Validate required 'pattern' field exists
            if "pattern" not in config:
                logger.warning("pattern_missing_regex", name=event_name, file=str(yaml_file))
                continue

            # Extract and validate all config values with defensive type coercion
            try:
                pattern_str = config["pattern"]
                if not isinstance(pattern_str, str):
                    logger.warning(
                        "pattern_not_string",
                        name=event_name,
                        type=type(pattern_str).__name__,
                        file=str(yaml_file)
                    )
                    continue

                # Get other fields with defaults and type coercion
                event_type = config.get("type", event_name)
                if not isinstance(event_type, str):
                    logger.warning(
                        "type_not_string",
                        name=event_name,
                        type_value=type(event_type).__name__,
                        file=str(yaml_file)
                    )
                    continue

                emoji = config.get("emoji", "")
                if not isinstance(emoji, str):
                    logger.warning(
                        "emoji_not_string",
                        name=event_name,
                        emoji_type=type(emoji).__name__,
                        file=str(yaml_file)
                    )
                    emoji = ""  # Use default instead of failing

                message = config.get("message", "{player}: {message}")
                if not isinstance(message, str):
                    logger.warning(
                        "message_not_string",
                        name=event_name,
                        message_type=type(message).__name__,
                        file=str(yaml_file)
                    )
                    message = "{player}: {message}"  # Use default

                priority = config.get("priority", 10)
                if not isinstance(priority, int):
                    logger.warning(
                        "priority_not_int",
                        name=event_name,
                        priority_type=type(priority).__name__,
                        file=str(yaml_file)
                    )
                    priority = 10  # Use default

                enabled = config.get("enabled", True)
                if not isinstance(enabled, bool):
                    logger.warning(
                        "enabled_not_bool",
                        name=event_name,
                        enabled_type=type(enabled).__name__,
                        file=str(yaml_file)
                    )
                    enabled = True  # Use default

                # Check for duplicate event names across files
                if any(p.name == event_name for p in self.patterns):
                    logger.warning(
                        "duplicate_event_pattern_name",
                        name=event_name,
                        file=str(yaml_file),
                    )
                    continue

                # Extract channel (optional)
                channel: Optional[str] = config.get('channel')
                if channel is not None and not isinstance(channel, str):
                    logger.warning(
                        "channel_not_string",
                        name=event_name,
                        channel_type=type(channel).__name__,
                        file=str(yaml_file)
                    )
                    channel = None

                # Create pattern (this validates all fields via assertions)
                pattern = EventPattern(
                    name=event_name,
                    pattern=pattern_str,
                    event_type=event_type,
                    emoji=emoji,
                    message_template=message,
                    enabled=enabled,
                    priority=priority,
                    channel=channel
                )

                self.patterns.append(pattern)
                count += 1

                # Log successful creation
                logger.debug(
                    "pattern_loaded",
                    name=event_name,
                    type=event_type,
                    priority=priority,
                    enabled=enabled,
                    file=str(yaml_file),
                )

                if not enabled:
                    logger.debug("pattern_disabled", name=event_name, file=str(yaml_file))

            except AssertionError as e:
                logger.warning(
                    "pattern_creation_failed",
                    name=event_name,
                    error=str(e),
                    file=str(yaml_file)
                )
                continue
            except Exception as e:
                logger.error(
                    "unexpected_error_loading_pattern",
                    name=event_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    file=str(yaml_file)
                )
                continue

        return count

    def get_patterns(self, enabled_only: bool = True) -> List[EventPattern]:
        """
        Get loaded patterns.

        Args:
            enabled_only: Only return enabled patterns

        Returns:
            List of event patterns
        """
        assert isinstance(enabled_only, bool), \
            f"enabled_only must be bool, got {type(enabled_only)}"

        result: List[EventPattern]
        if enabled_only:
            result = [p for p in self.patterns if p.enabled]
        else:
            result = list(self.patterns)

        # Verify all returned items are EventPattern
        assert all(isinstance(p, EventPattern) for p in result), \
            "All returned patterns must be EventPattern instances"

        return result

    def get_patterns_by_type(self, event_type: str) -> List[EventPattern]:
        """
        Get patterns for a specific event type.

        Args:
            event_type: Event type to filter by

        Returns:
            List of matching patterns
        """
        assert isinstance(event_type, str), \
            f"event_type must be str, got {type(event_type)}"
        assert len(event_type) > 0, "event_type cannot be empty"

        result = [p for p in self.patterns if p.event_type == event_type and p.enabled]

        # Verify all returned items are EventPattern
        assert all(isinstance(p, EventPattern) for p in result), \
            "All returned patterns must be EventPattern instances"

        return result

    def reload(self) -> int:
        """
        Reload all patterns from disk.

        Returns:
            Number of patterns loaded
        """
        self.patterns.clear()
        self._loaded_files.clear()
        assert len(self.patterns) == 0, "patterns should be empty after clear"
        assert len(self._loaded_files) == 0, "_loaded_files should be empty after clear"

        count = self.load_patterns()
        assert isinstance(count, int), f"load_patterns must return int, got {type(count)}"

        return count
