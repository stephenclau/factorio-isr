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

"""Pytest configuration for real command harness tests.

This module provides:
- Async test markers
- Session-level fixtures for mocking
- Teardown for cooldown resets
- Real command invocation harness
"""

from unittest.mock import MagicMock, AsyncMock
from typing import Any, Generator
from datetime import datetime
import sys
from pathlib import Path
import asyncio
import pytest
import discord

# Add src/ to Python path for absolute imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

pytest_plugins = ['pytest_asyncio']


def pytest_configure(config):
    """Configure pytest with async support."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (deselect with '-m \"not asyncio\"')"
    )


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ═══════════════════════════════════════════════════════════════════════════════════════
# MOCK FIXTURES FOR DISCRETE TESTS
# ═══════════════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_bot() -> MagicMock:
    """Create a mock Discord bot with required attributes."""
    bot = MagicMock()
    
    # Bot state
    bot._connected = True
    
    # User context manager
    bot.user_context = MagicMock()
    bot.user_context.get_user_server = MagicMock(return_value="prod")
    bot.user_context.get_server_display_name = MagicMock(return_value="Production")
    bot.user_context.get_rcon_for_user = MagicMock()
    bot.user_context.set_user_server = MagicMock()
    
    # Server manager (multi-server mode)
    bot.server_manager = MagicMock()
    bot.server_manager.list_tags = MagicMock(return_value=[])
    bot.server_manager.list_servers = MagicMock(return_value={})
    bot.server_manager.get_status_summary = MagicMock(return_value={})
    bot.server_manager.get_config = MagicMock()
    bot.server_manager.get_client = MagicMock()
    bot.server_manager.get_metrics_engine = MagicMock()
    bot.server_manager.clients = {}
    
    # RCON monitor
    bot.rcon_monitor = MagicMock()
    bot.rcon_monitor.rcon_server_states = {}
    
    # Discord tree (command registration)
    bot.tree = MagicMock()
    bot.tree.add_command = MagicMock()
    
    return bot


@pytest.fixture
def mock_rcon_client() -> MagicMock:
    """Create a mock RCON client."""
    client = MagicMock()
    
    # Connection state
    client.is_connected = True
    
    # Async execute method
    client.execute = AsyncMock(return_value="")
    
    return client


@pytest.fixture
def mock_interaction() -> MagicMock:
    """Create a mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    
    # User information
    interaction.user = MagicMock()
    interaction.user.id = 123456789
    interaction.user.name = "testuser"
    
    # Response methods
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    
    # Followup methods
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    
    return interaction
