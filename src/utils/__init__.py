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
