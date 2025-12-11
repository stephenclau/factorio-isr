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

"""  # START OF FILE

Discord bot client for Factorio ISR - Phase 6.0 Multi-Server Support.

Provides interactive bot functionality with slash commands, event handling,
Phase 5.1 features (embeds, cooldowns), Phase 5.2 RCON monitoring,
and Phase 6.0 multi-server support.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict, List

import discord
from discord import app_commands
import structlog
import yaml  # type: ignore[import]

# Phase 5.1: Rate limiting and embeds
# Import event parser and formatter
# CRITICAL: Use absolute imports first to ensure module identity consistency
try:
    from .event_parser import FactorioEvent, FactorioEventFormatter
    from .utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
    from .discord_interface import EmbedBuilder
except ImportError:
    # Fallback for flat imports - but ensure they come from the same module
    # by validating __module__ attribute matches
    from event_parser import FactorioEvent, FactorioEventFormatter  # type: ignore
    from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN  # type: ignore
    from discord_interface import EmbedBuilder  # type: ignore

# Phase 6: Multi-server support
try:
    from .config import ServerConfig
    from .server_manager import ServerManager
except ImportError:
    try:
        from config import ServerConfig  # type: ignore
        from server_manager import ServerManager  # type: ignore
    except ImportError:
        # ServerManager may not be available in single-server mode
        ServerManager = None  # type: ignore
        ServerConfig = None  # type: ignore

logger = structlog.get_logger()

# Log the module path for debugging import issues
logger.debug(
    "discord_bot_imports_resolved",
    factorio_event_module=FactorioEvent.__module__,
    discord_bot_module=__name__,
)


class DiscordBot(discord.Client):