
"""
Enhanced unit tests for rate_limiting.CommandCooldown.

Extends coverage to edge cases around time window expiration, retry_after
calculation, deque trimming, and all global cooldown instances.
"""

import time
from typing import Callable

import pytest

from utils.rate_limiting import CommandCooldown, QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN


class TestCommandCooldownEnhanced:
    """Additional tests to improve coverage for CommandCooldown."""

    def test_time_window_expiration_allows_new_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Old timestamps outside the window are purged, allowing new usage."""
        cooldown = CommandCooldown(rate=2, per=10.0)
        identifier = 42

        # Start at t=100
        monkeypatch.setattr(time, "time", lambda: 100.0)
        assert cooldown.is_rate_limited(identifier)[0] is False
        assert cooldown.is_rate_limited(identifier)[0] is False

        # At t=105 (< per), still limited
        monkeypatch.setattr(time, "time", lambda: 105.0)
        is_limited, _ = cooldown.is_rate_limited(identifier)
        assert is_limited is True

        # At t=111 (> per), old entries should be dropped and call allowed
        monkeypatch.setattr(time, "time", lambda: 111.0)
        is_limited, retry_after = cooldown.is_rate_limited(identifier)
        assert is_limited is False
        assert retry_after == 0.0

    def test_retry_after_calculation_precision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """retry_after is computed as remaining window on the oldest entry."""
        cooldown = CommandCooldown(rate=2, per=10.0)
        identifier = 7

        # t=0: first two allowed
        monkeypatch.setattr(time, "time", lambda: 0.0)
        assert cooldown.is_rate_limited(identifier)[0] is False
        assert cooldown.is_rate_limited(identifier)[0] is False

        # t=3: third call should be limited; retry_after ~= 7
        monkeypatch.setattr(time, "time", lambda: 3.0)
        is_limited, retry_after = cooldown.is_rate_limited(identifier)
        assert is_limited is True
        assert 6.9 <= retry_after <= 7.1

    def test_retry_after_never_negative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """max(0, retry_after) guards against negative values."""
        cooldown = CommandCooldown(rate=1, per=5.0)
        identifier = 99

        # First call at t=0 allowed
        monkeypatch.setattr(time, "time", lambda: 0.0)
        assert cooldown.is_rate_limited(identifier)[0] is False

        # Immediately limited, but simulate time drift where now - bucket[0] > per
        # so raw retry_after would be negative without max(0, ...)
        monkeypatch.setattr(time, "time", lambda: 10.0)
        is_limited, retry_after = cooldown.is_rate_limited(identifier)
        # Not limited anymore because entry is purged, but check retry_after value
        assert is_limited is False
        assert retry_after == 0.0

    def test_reset_nonexistent_identifier_is_noop(self) -> None:
        """reset() on an unused identifier should not raise and not affect others."""
        cooldown = CommandCooldown(rate=2, per=60.0)
        a, b = 1, 2
        cooldown.is_rate_limited(a)
        cooldown.is_rate_limited(b)

        # Reset a non-existent id
        cooldown.reset(9999)

        # Existing ids still tracked as expected
        assert cooldown.get_usage_count(a) == 1
        assert cooldown.get_usage_count(b) == 1

    def test_get_usage_for_never_used_identifier(self) -> None:
        """get_usage() handles identifiers that have never been seen."""
        cooldown = CommandCooldown(rate=3, per=60.0)
        current, max_rate = cooldown.get_usage(555)
        assert current == 0
        assert max_rate == 3

    def test_deque_maxlen_trims_old_entries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cooldown = CommandCooldown(rate=3, per=100.0)
        identifier = 1

        monkeypatch.setattr(time, "time", lambda: 0.0)
        for i in range(6):
            monkeypatch.setattr(time, "time", lambda i=i: float(i))
            cooldown.is_rate_limited(identifier)

        bucket = cooldown.cooldowns[identifier]
        assert len(bucket) == 3


    def test_partial_window_recovery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After some time passes, usage should be partially freed within the window."""
        cooldown = CommandCooldown(rate=3, per=10.0)
        identifier = 77

        # Three calls at t=0,1,2
        for i in range(3):
            monkeypatch.setattr(time, "time", lambda i=i: float(i))
            assert cooldown.is_rate_limited(identifier)[0] is False

        # At t=3, still limited
        monkeypatch.setattr(time, "time", lambda: 3.0)
        assert cooldown.is_rate_limited(identifier)[0] is True

        # At t=11, only the last call at t=2 is still in window -> should allow again
        monkeypatch.setattr(time, "time", lambda: 11.0)
        is_limited, retry_after = cooldown.is_rate_limited(identifier)
        assert is_limited is False
        assert retry_after == 0.0

    def test_multiple_identifiers_with_overlapping_usage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple identifiers share the same cooldown instance but have isolated buckets."""
        cooldown = CommandCooldown(rate=2, per=10.0)
        a, b = 10, 20

        # t=0: both use once
        monkeypatch.setattr(time, "time", lambda: 0.0)
        assert cooldown.is_rate_limited(a)[0] is False
        assert cooldown.is_rate_limited(b)[0] is False

        # t=1: a uses again (now at limit), b still only once
        monkeypatch.setattr(time, "time", lambda: 1.0)
        assert cooldown.is_rate_limited(a)[0] is False  # second use
        is_limited_b, _ = cooldown.is_rate_limited(b)   # second use for b
        assert is_limited_b is False

        # t=2: a is now limited, b hits its limit on this call
        monkeypatch.setattr(time, "time", lambda: 2.0)
        is_limited_a, _ = cooldown.is_rate_limited(a)   # third call -> limited
        assert is_limited_a is True
        is_limited_b2, _ = cooldown.is_rate_limited(b)  # third call -> limited
        assert is_limited_b2 is True

    def test_global_admin_cooldown_configuration(self) -> None:
        """ADMIN_COOLDOWN has expected rate and window."""        
        assert ADMIN_COOLDOWN.rate == 3
        assert ADMIN_COOLDOWN.per == 60.0

    def test_global_danger_cooldown_configuration(self) -> None:
        """DANGER_COOLDOWN has expected rate and window."""        
        assert DANGER_COOLDOWN.rate == 1
        assert DANGER_COOLDOWN.per == 120.0

    def test_global_cooldowns_are_independent_instances(self) -> None:
        """Global cooldown instances must not share internal state."""        
        # Use QUERY_COOLDOWN heavily for one id
        QUERY_COOLDOWN.reset_all()
        ADMIN_COOLDOWN.reset_all()
        DANGER_COOLDOWN.reset_all()

        identifier = 123
        for _ in range(QUERY_COOLDOWN.rate):
            assert QUERY_COOLDOWN.is_rate_limited(identifier)[0] is False

        # Hitting limit in QUERY_COOLDOWN must not affect ADMIN/DANGER
        is_limited_admin, _ = ADMIN_COOLDOWN.is_rate_limited(identifier)
        is_limited_danger, _ = DANGER_COOLDOWN.is_rate_limited(identifier)
        assert is_limited_admin is False
        assert is_limited_danger is False
