"""
General-purpose utilities for Factorio ISR.

Framework-agnostic tools that can be used by Discord, RCON, Prometheus, etc.
"""

from .rate_limiting import CommandCooldown, QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN

__all__ = [
    # Rate limiting
    "CommandCooldown",
    "QUERY_COOLDOWN",
    "ADMIN_COOLDOWN",
    "DANGER_COOLDOWN",
]
