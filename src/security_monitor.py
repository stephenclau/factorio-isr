

"""
Security monitor for detecting and responding to malicious patterns.

Provides:
- Malicious pattern detection and automatic bans
- Rate limiting for Discord actions per event type
- Infraction logging and notifications
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json
import os
import re
import structlog

logger = structlog.get_logger()

# Security pattern definitions
MALICIOUS_PATTERNS = {
    "code_injection": {
        "patterns": [
            r"eval\s*\(",
            r"exec\s*\(",
            r"__import__\s*\(",
            r"compile\s*\(",
            r"ast\.literal_eval",
            r"subprocess.*shell\s*=\s*True",
            r"os\.system\s*\(",
            r"importlib\.import_module",
        ],
        "severity": "critical",
        "auto_ban": True,
        "description": "Attempted code injection",
    },
    "path_traversal": {
        "patterns": [
            r"\.\./",
            r"\.\.\\",
            r"/etc/passwd",
            r"/proc/self",
        ],
        "severity": "high",
        "auto_ban": False,
        "description": "Path traversal attempt",
    },
    "command_injection": {
        "patterns": [
            r"&&\s*[a-z]+",
            r";\s*rm\s+-rf",
            r"\|\s*sh",
            r"`.*`",
            r"\$\(.*\)",
        ],
        "severity": "critical",
        "auto_ban": True,
        "description": "Shell command injection",
    },
}


@dataclass
class Infraction:
    """Security infraction record."""

    player_name: str
    timestamp: datetime
    pattern_type: str
    matched_pattern: str
    raw_text: str
    severity: str
    auto_banned: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "player_name": self.player_name,
            "timestamp": self.timestamp.isoformat(),
            "pattern_type": self.pattern_type,
            "matched_pattern": self.matched_pattern,
            "raw_text": self.raw_text[:200],
            "severity": self.severity,
            "auto_banned": self.auto_banned,
            "metadata": self.metadata,
        }


@dataclass
class RateLimit:
    """Rate limit configuration for an action type."""

    max_events: int
    time_window_seconds: int
    action_type: str


class SecurityMonitor:
    """Monitor for malicious patterns and rate limiting."""

    def __init__(
        self,
        infractions_file: Path = Path("config/infractions.jsonl"),
        banned_players_file: Optional[Path] = None,
    ) -> None:
        """Initialize security monitor.

        Args:
            infractions_file: Path to append-only infraction log.
                Default: ./config/infractions.jsonl
            banned_players_file: Optional explicit path to ban list.
                If None, resolve from FACTORIO_ISR_BANLIST_DIR environment variable
                or default to ./config/server-banlist.json.
        """
        self.infractions_file = infractions_file

        # Resolve banlist path: ENV > explicit arg > default ./config
        if banned_players_file is None:
            banlist_dir_env = os.getenv("FACTORIO_ISR_BANLIST_DIR")
            if banlist_dir_env:
                base_dir = Path(banlist_dir_env)
            else:
                base_dir = Path("config")
            banned_players_file = base_dir / "server-banlist.json"

        self.banned_players_file = banned_players_file

        # Ensure directories exist
        self.infractions_file.parent.mkdir(parents=True, exist_ok=True)
        self.banned_players_file.parent.mkdir(parents=True, exist_ok=True)

        # Compile malicious patterns
        self.compiled_patterns: Dict[str, Dict[str, Any]] = {}
        self._compile_security_patterns()

        # Load banned players
        self.banned_players: set[str] = self._load_banned_players()

        # Rate limiting state: {action_type: [(timestamp, player), ...]}
        self.rate_limit_state: Dict[str, List[Tuple[datetime, str]]] = {}

        # Rate limit configurations
        self.rate_limits: Dict[str, RateLimit] = {
            "mention_admin": RateLimit(
                max_events=5,
                time_window_seconds=60,
                action_type="mention_admin",
            ),
            "mention_everyone": RateLimit(
                max_events=1,
                time_window_seconds=300,
                action_type="mention_everyone",
            ),
            "chat_message": RateLimit(
                max_events=20,
                time_window_seconds=60,
                action_type="chat_message",
            ),
        }

        logger.info(
            "security_monitor_initialized",
            patterns=len(self.compiled_patterns),
            banned_players=len(self.banned_players),
            rate_limits=len(self.rate_limits),
            infractions_file=str(self.infractions_file),
            banned_players_file=str(self.banned_players_file),
        )

    def _compile_security_patterns(self) -> None:
        """Compile all malicious patterns."""
        for pattern_type, config in MALICIOUS_PATTERNS.items():
            compiled = []
            for pattern_str in config["patterns"]:
                try:
                    compiled.append(re.compile(pattern_str, re.IGNORECASE))
                except re.error as exc:
                    logger.error(
                        "security_pattern_compile_failed",
                        type=pattern_type,
                        pattern=pattern_str,
                        error=str(exc),
                    )
                    continue

            self.compiled_patterns[pattern_type] = {
                "patterns": compiled,
                "severity": config["severity"],
                "auto_ban": config["auto_ban"],
                "description": config["description"],
            }

            logger.debug(
                "security_patterns_compiled",
                type=pattern_type,
                count=len(compiled),
            )

    def _load_banned_players(self) -> set[str]:
        """Load banned players from file."""
        if not self.banned_players_file.exists():
            return set()

        try:
            with open(self.banned_players_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                players = data.get("banned_players", [])
                if not isinstance(players, list):
                    logger.warning(
                        "banned_players_not_list",
                        type=type(players).__name__,
                        file=str(self.banned_players_file),
                    )
                    return set()
                return set(str(p) for p in players)
        except Exception as exc:
            logger.error(
                "failed_to_load_banned_players",
                error=str(exc),
                file=str(self.banned_players_file),
            )
            return set()

    def _save_banned_players(self) -> None:
        """Save banned players to file."""
        try:
            with open(self.banned_players_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "banned_players": sorted(list(self.banned_players)),
                        "last_updated": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )
        except Exception as exc:
            logger.error(
                "failed_to_save_banned_players",
                error=str(exc),
                file=str(self.banned_players_file),
            )

    def check_malicious_pattern(
        self,
        text: str,
        player_name: Optional[str] = None,
    ) -> Optional[Infraction]:
        """Check text for malicious patterns.

        Args:
            text: Text to scan.
            player_name: Player who generated the text.

        Returns:
            Infraction object if malicious pattern detected, None otherwise.
        """
        if not text or not player_name:
            return None

        # Check if player is already banned
        if player_name in self.banned_players:
            logger.debug(
                "blocked_banned_player",
                player=player_name,
            )
            return None

        # Check each pattern type
        for pattern_type, config in self.compiled_patterns.items():
            for pattern in config["patterns"]:
                match = pattern.search(text)
                if match:
                    infraction = Infraction(
                        player_name=player_name,
                        timestamp=datetime.now(),
                        pattern_type=pattern_type,
                        matched_pattern=pattern.pattern,
                        raw_text=text,
                        severity=config["severity"],
                        auto_banned=config["auto_ban"],
                        metadata={
                            "match": match.group(0),
                            "description": config["description"],
                        },
                    )

                    self._log_infraction(infraction)

                    if config["auto_ban"]:
                        self.ban_player(player_name, reason=config["description"])

                    logger.warning(
                        "malicious_pattern_detected",
                        player=player_name,
                        type=pattern_type,
                        severity=config["severity"],
                        auto_banned=config["auto_ban"],
                        match=match.group(0)[:50],
                    )

                    return infraction

        return None

    def _log_infraction(self, infraction: Infraction) -> None:
        """Append infraction to JSONL log file."""
        try:
            with open(self.infractions_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(infraction.to_dict()) + "\n")
        except Exception as exc:
            logger.error(
                "failed_to_log_infraction",
                player=infraction.player_name,
                error=str(exc),
                file=str(self.infractions_file),
            )

    def ban_player(self, player_name: str, reason: str = "Security violation") -> None:
        """Ban a player and persist the ban list."""
        if player_name in self.banned_players:
            logger.debug("player_already_banned", player=player_name)
            return

        self.banned_players.add(player_name)
        self._save_banned_players()

        logger.warning(
            "player_banned",
            player=player_name,
            reason=reason,
            total_banned=len(self.banned_players),
        )

    def unban_player(self, player_name: str) -> bool:
        """Unban a player.

        Returns True if player was unbanned, False if not banned.
        """
        if player_name not in self.banned_players:
            return False

        self.banned_players.remove(player_name)
        self._save_banned_players()

        logger.info("player_unbanned", player=player_name)
        return True

    def is_banned(self, player_name: str) -> bool:
        """Check if a player is banned."""
        return player_name in self.banned_players

    def check_rate_limit(
        self,
        action_type: str,
        player_name: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check if action is rate-limited.

        Args:
            action_type: Type of action (e.g., "mention_admin").
            player_name: Player attempting action.

        Returns:
            (allowed, reason) - True if allowed, False if rate-limited.
        """
        if action_type not in self.rate_limits:
            return True, None

        limit = self.rate_limits[action_type]
        now = datetime.now()
        cutoff = now - timedelta(seconds=limit.time_window_seconds)

        if action_type not in self.rate_limit_state:
            self.rate_limit_state[action_type] = []

        # Remove entries outside the window
        self.rate_limit_state[action_type] = [
            (ts, player)
            for ts, player in self.rate_limit_state[action_type]
            if ts > cutoff
        ]

        player_events = [
            ts
            for ts, player in self.rate_limit_state[action_type]
            if player == player_name
        ]

        if len(player_events) >= limit.max_events:
            reason = (
                f"Rate limit exceeded: {len(player_events)}/{limit.max_events} "
                f"{action_type} events in {limit.time_window_seconds}s"
            )
            logger.warning(
                "rate_limit_exceeded",
                player=player_name,
                action_type=action_type,
                count=len(player_events),
                limit=limit.max_events,
                window=limit.time_window_seconds,
            )
            return False, reason

        self.rate_limit_state[action_type].append((now, player_name))
        return True, None

    def get_infractions(
        self,
        player_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent infractions (most recent first)."""
        if not self.infractions_file.exists():
            return []

        infractions: List[Dict[str, Any]] = []
        try:
            with open(self.infractions_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    infraction = json.loads(line)
                    if player_name is None or infraction.get("player_name") == player_name:
                        infractions.append(infraction)
        except Exception as exc:
            logger.error(
                "failed_to_load_infractions",
                error=str(exc),
                file=str(self.infractions_file),
            )

        return infractions[-limit:][::-1]
