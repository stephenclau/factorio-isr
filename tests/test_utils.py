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

import pytest

from utils.rate_limiting import CommandCooldown, QUERY_COOLDOWN


# ============================================================================
# Test CommandCooldown
# ============================================================================

class TestCommandCooldown:
    """Test rate limiting functionality."""

    def test_cooldown_initialization(self) -> None:
        """Test cooldown initializes correctly."""
        cooldown = CommandCooldown(rate=3, per=60.0)
        assert cooldown.rate == 3
        assert cooldown.per == 60.0

    def test_not_rate_limited_first_use(self) -> None:
        """Test first use is not rate limited."""
        cooldown = CommandCooldown(rate=3, per=60.0)
        is_limited, retry_after = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is False
        assert retry_after == 0.0

    def test_rate_limited_after_max_uses(self) -> None:
        """Test rate limiting after max uses."""
        cooldown = CommandCooldown(rate=3, per=60.0)

        # Use 3 times (at limit)
        for _ in range(3):
            is_limited, _ = cooldown.is_rate_limited(identifier=12345)
            assert is_limited is False

        # 4th use should be rate limited
        is_limited, retry_after = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is True
        assert retry_after > 0.0

    def test_cooldown_per_identifier(self) -> None:
        """Test cooldowns are per-identifier."""
        cooldown = CommandCooldown(rate=2, per=60.0)

        # Identifier 111 uses twice
        cooldown.is_rate_limited(identifier=111)
        cooldown.is_rate_limited(identifier=111)

        # Identifier 222 should not be rate limited
        is_limited, _ = cooldown.is_rate_limited(identifier=222)
        assert is_limited is False

    def test_cooldown_reset(self) -> None:
        """Test manual cooldown reset."""
        cooldown = CommandCooldown(rate=1, per=60.0)
        cooldown.is_rate_limited(identifier=12345)

        # Should be rate limited now
        is_limited, _ = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is True

        # Reset cooldown
        cooldown.reset(identifier=12345)

        # Should not be rate limited anymore
        is_limited, _ = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is False

    def test_cooldown_reset_user_alias(self) -> None:
        """Test reset_user() alias for backward compatibility."""
        cooldown = CommandCooldown(rate=1, per=60.0)
        cooldown.is_rate_limited(identifier=12345)

        # Should be rate limited now
        is_limited, _ = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is True

        # Reset using reset_user alias
        cooldown.reset_user(identifier=12345)

        # Should not be rate limited anymore
        is_limited, _ = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is False

    def test_cooldown_reset_all(self) -> None:
        """Test resetting all cooldowns."""
        cooldown = CommandCooldown(rate=1, per=60.0)

        # Use for multiple identifiers
        cooldown.is_rate_limited(identifier=111)
        cooldown.is_rate_limited(identifier=222)
        cooldown.is_rate_limited(identifier=333)

        # Reset all
        cooldown.reset_all()

        # All should be reset
        is_limited, _ = cooldown.is_rate_limited(identifier=111)
        assert is_limited is False

    def test_get_usage(self) -> None:
        """Test getting current usage."""
        cooldown = CommandCooldown(rate=5, per=60.0)

        # No usage yet
        current, max_rate = cooldown.get_usage(identifier=12345)
        assert current == 0
        assert max_rate == 5

        # Use twice
        cooldown.is_rate_limited(identifier=12345)
        cooldown.is_rate_limited(identifier=12345)

        current, max_rate = cooldown.get_usage(identifier=12345)
        assert current == 2
        assert max_rate == 5

    def test_get_usage_count(self) -> None:
        """Test getting usage count directly."""
        cooldown = CommandCooldown(rate=5, per=60.0)

        # No usage yet
        count = cooldown.get_usage_count(identifier=12345)
        assert count == 0

        # Use three times
        cooldown.is_rate_limited(identifier=12345)
        cooldown.is_rate_limited(identifier=12345)
        cooldown.is_rate_limited(identifier=12345)

        count = cooldown.get_usage_count(identifier=12345)
        assert count == 3

    def test_global_cooldown_instances(self) -> None:
        """Test pre-configured global instances."""
        assert QUERY_COOLDOWN.rate == 5
        assert QUERY_COOLDOWN.per == 30.0
