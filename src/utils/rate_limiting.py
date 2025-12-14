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
from typing import Dict, Tuple, Optional
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

    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[int]]:
        """
        Check if user is rate limited.

        Args:
            user_id: User's unique ID (Discord user ID, etc.)

        Returns:
            Tuple of (is_limited: bool, retry_seconds: Optional[int])
            - is_limited: True if user is rate limited
            - retry_seconds: Seconds until next allowed use (None if not limited, 0 if immediate)
        """
        now = time.time()
        bucket = self.cooldowns[user_id]

        # Remove timestamps outside the window
        while bucket and bucket[0] < now - self.per:
            bucket.popleft()

        if len(bucket) >= self.rate:
            # Rate limited - calculate retry time in seconds (rounded up to int)
            retry_after = self.per - (now - bucket[0])
            retry_seconds = max(0, int(retry_after) if retry_after <= 0 else int(retry_after) + 1)
            logger.debug(
                "rate_limited",
                user_id=user_id,
                retry_seconds=retry_seconds,
                rate=self.rate,
                per=self.per
            )
            return True, retry_seconds

        # Not rate limited - record this use
        bucket.append(now)
        return False, None

    def reset(self, user_id: int) -> None:
        """
        Reset cooldown for a specific user.

        Args:
            user_id: User's unique ID to reset
        """
        if user_id in self.cooldowns:
            del self.cooldowns[user_id]
            logger.debug("cooldown_reset", user_id=user_id)

    def reset_user(self, user_id: int) -> None:
        """Alias for reset() for backward compatibility."""
        self.reset(user_id)

    def reset_all(self) -> None:
        """Reset all cooldowns."""
        self.cooldowns.clear()
        logger.debug("all_cooldowns_reset")

    def get_usage(self, user_id: int) -> Tuple[int, int]:
        """
        Get current usage and max rate for user.

        Args:
            user_id: User's unique ID

        Returns:
            Tuple of (current_usage_count, max_rate)
        """
        now = time.time()
        bucket = self.cooldowns.get(user_id, deque())

        # Count valid timestamps in current window
        current_usage = sum(1 for ts in bucket if ts >= now - self.per)

        return (current_usage, self.rate)

    def get_usage_count(self, user_id: int) -> int:
        """Get usage count for user."""
        current_usage, _ = self.get_usage(user_id)
        return current_usage


# Global cooldown instances for common use cases
QUERY_COOLDOWN = CommandCooldown(rate=5, per=30.0)    # 5 queries per 30s
ADMIN_COOLDOWN = CommandCooldown(rate=3, per=60.0)    # 3 admin actions per minute
DANGER_COOLDOWN = CommandCooldown(rate=1, per=120.0)  # 1 dangerous command per 2min
