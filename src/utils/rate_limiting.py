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
Rate limiting utilities (framework-agnostic).

Can be used by Discord commands, RCON, Prometheus, Logstash, etc.
"""

import time
from typing import Dict, Tuple
from collections import defaultdict, deque
import structlog

logger = structlog.get_logger()


class CommandCooldown:
    """Rate limiting system to prevent spam across any API."""

    def __init__(self, rate: int = 3, per: float = 60.0):
        """
        Initialize cooldown manager.

        Args:
            rate: Number of uses allowed
            per: Time window in seconds
        """
        self.rate = rate
        self.per = per
        self.cooldowns: Dict[int, deque] = defaultdict(lambda: deque(maxlen=rate))
        logger.debug("cooldown_initialized", rate=rate, per=per)

    def is_rate_limited(self, identifier: int) -> tuple[bool, float]:
        """
        Check if identifier is rate limited.

        Args:
            identifier: Unique ID (user_id, command_hash, etc.)

        Returns:
            (is_limited, retry_after_seconds)
        """
        now = time.time()
        bucket = self.cooldowns[identifier]

        # Remove timestamps outside the window
        while bucket and bucket[0] < now - self.per:
            bucket.popleft()

        if len(bucket) >= self.rate:
            # Rate limited - calculate retry time
            retry_after = self.per - (now - bucket[0])
            logger.debug(
                "rate_limited",
                identifier=identifier,
                retry_after=retry_after,
                rate=self.rate,
                per=self.per
            )
            return True, max(0, retry_after)

        # Not rate limited - record this use
        bucket.append(now)
        return False, 0.0

    def reset(self, identifier: int) -> None:
        """
        Reset cooldown for a specific identifier.

        Args:
            identifier: Unique ID to reset
        """
        if identifier in self.cooldowns:
            del self.cooldowns[identifier]
            logger.debug("cooldown_reset", identifier=identifier)

    def reset_user(self, identifier: int) -> None:
        """Alias for reset() for backward compatibility."""
        self.reset(identifier)

    def reset_all(self) -> None:
        """Reset all cooldowns."""
        self.cooldowns.clear()
        logger.debug("all_cooldowns_reset")

    def get_usage(self, identifier: int) -> Tuple[int, int]:
        """
        Get current usage and max rate for identifier.

        Args:
            identifier: Unique ID

        Returns:
            Tuple of (current_usage_count, max_rate)
        """
        now = time.time()
        bucket = self.cooldowns.get(identifier, deque())

        # Count valid timestamps in current window
        current_usage = sum(1 for ts in bucket if ts >= now - self.per)

        return (current_usage, self.rate)

    def get_usage_count(self, identifier: int) -> int:
        """Get usage count for identifier."""
        current_usage, _ = self.get_usage(identifier)
        return current_usage


# Global cooldown instances for common use cases
QUERY_COOLDOWN = CommandCooldown(rate=5, per=30.0)    # 5 queries per 30s
ADMIN_COOLDOWN = CommandCooldown(rate=3, per=60.0)    # 3 admin actions per minute
DANGER_COOLDOWN = CommandCooldown(rate=1, per=120.0)  # 1 dangerous command per 2min
