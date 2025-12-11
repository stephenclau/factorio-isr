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

"""Discord slash command registration.

Exports register_factorio_commands() which registers all /factorio subcommands
under the command limit of 25 per Discord group.
"""

from .factorio import register_factorio_commands

__all__ = ["register_factorio_commands"]
