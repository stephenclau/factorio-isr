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

"""🚨 CRITICAL: Integration Tests for Factorio Command Wrappers

This file ACTUALLY EXECUTES the command handlers to achieve REAL code coverage.

Why separate file?
- factorio.py defines all commands as wrappers that delegate to handlers
- Unit tests cannot access wrappers without executing registration
- This file tests handlers directly with full Discord.py mocks
- Tests the handler → send_command_response flow

Target: 70-80% coverage (handler execution + send response flow)
Approach: Integration testing with full Discord mocks + handler DI
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import discord

from bot.commands.command_handlers import (
    StatusCommandHandler,
    PlayersCommandHandler,
    ResearchCommandHandler,
    EvolutionCommandHandler,
    CommandResult,
)
from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN
from discord_interface import EmbedBuilder


class IntegrationTestHelper:
    """Helper to create full mocks for integration testing."""

    @staticmethod
    def create_interaction_mock(user_id=12345, user_name="TestUser"):
        """Create a fully-featured Discord interaction mock."""
        interaction = MagicMock(spec=discord.Interaction)
        
        # User
        interaction.user = MagicMock()
        interaction.user.id = user_id
        interaction.user.name = user_name
        interaction.user.mention = f"<@{user_id}>"
        
        # Response
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        
        # Followup
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        
        return interaction

    @staticmethod
    def create_user_context_mock(rcon_client=None, server_name="main"):
        """Create a user context provider mock."""
        context = MagicMock()
        context.get_user_server.return_value = "main"
        context.get_server_display_name.return_value = server_name
        context.get_rcon_for_user.return_value = rcon_client
        context.set_user_server = MagicMock()
        return context

    @staticmethod
    def create_rate_limiter_mock(is_limited=False):
        """Create a rate limiter mock."""
        limiter = MagicMock()
        limiter.is_rate_limited.return_value = (is_limited, 30 if is_limited else None)
        return limiter


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTEGRATION TEST: Players Command
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPlayersCommandIntegration:
    """Integration test: /factorio players handler execution."""

    @pytest.mark.asyncio
    async def test_players_command_execution(self):
        """Test: players handler ACTUALLY EXECUTES with full mock setup."""
        # Setup interaction and RCON
        interaction = IntegrationTestHelper.create_interaction_mock()
        rcon_client = MagicMock()
        rcon_client.is_connected = True
        rcon_client.execute = AsyncMock(
            return_value="- Alice (online)\n- Bob (online)\n- Charlie (online)"
        )
        
        # Create handler with all dependencies
        handler = PlayersCommandHandler(
            user_context_provider=IntegrationTestHelper.create_user_context_mock(rcon_client),
            rate_limiter=IntegrationTestHelper.create_rate_limiter_mock(is_limited=False),
            embed_builder_type=EmbedBuilder,
        )
        
        # Execute handler
        result = await handler.execute(interaction)
        
        # Verify result
        assert result.success is True
        assert result.embed is not None
        assert "Players" in result.embed.title
        assert "Alice" in result.embed.fields[0].value
        assert rcon_client.execute.called


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTEGRATION TEST: Status Command
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestStatusCommandIntegration:
    """Integration test: /factorio status handler execution."""

    @pytest.mark.asyncio
    async def test_status_command_happy_path(self):
        """Test: status handler executes with Phase 2 handler.
        
        This ACTUALLY RUNS the StatusCommandHandler.execute()
        """
        # Setup interaction and RCON
        interaction = IntegrationTestHelper.create_interaction_mock()
        rcon_client = MagicMock()
        rcon_client.is_connected = True
        
        # Setup metrics engine
        metrics_engine_mock = MagicMock()
        metrics_engine_mock.gather_all_metrics = AsyncMock(
            return_value={
                "ups": 59.8,
                "ups_sma": 59.5,
                "ups_ema": 59.7,
                "player_count": 3,
                "players": ["Alice", "Bob", "Charlie"],
                "evolution_factor": 0.42,
                "evolution_by_surface": {"nauvis": 0.42},
                "play_time": "2h 30m",
                "is_paused": False,
            }
        )
        
        # Setup server manager
        server_manager = MagicMock()
        server_manager.get_metrics_engine.return_value = metrics_engine_mock
        
        # Reset rate limiter
        QUERY_COOLDOWN.reset(interaction.user.id)
        
        # Create handler
        handler = StatusCommandHandler(
            user_context=IntegrationTestHelper.create_user_context_mock(rcon_client),
            server_manager=server_manager,
            cooldown=IntegrationTestHelper.create_rate_limiter_mock(is_limited=False),
            embed_builder=EmbedBuilder,
            rcon_monitor=None,
        )
        
        # Execute handler
        result = await handler.execute(interaction)
        
        # Verify result
        assert result.success is True
        assert result.embed is not None
        assert "Status" in result.embed.title
        assert "59.5" in str(result.embed.fields)  # UPS SMA


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTEGRATION TEST: Research Command
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestResearchCommandIntegration:
    """Integration test: /factorio research handler execution."""

    @pytest.mark.asyncio
    async def test_research_command_display_status(self):
        """Test: research handler DISPLAYS status via execute()."""
        # Setup
        interaction = IntegrationTestHelper.create_interaction_mock()
        rcon_client = MagicMock()
        rcon_client.is_connected = True
        rcon_client.execute = AsyncMock(return_value="42/128")
        
        # Reset rate limiter
        ADMIN_COOLDOWN.reset(interaction.user.id)
        
        # Create handler
        handler = ResearchCommandHandler(
            user_context=IntegrationTestHelper.create_user_context_mock(rcon_client),
            cooldown=IntegrationTestHelper.create_rate_limiter_mock(is_limited=False),
            embed_builder=EmbedBuilder,
        )
        
        # Execute with no action = display status
        result = await handler.execute(interaction, force=None, action=None, technology=None)
        
        # Verify
        assert result.success is True
        assert result.embed is not None
        assert rcon_client.execute.called

    @pytest.mark.asyncio
    async def test_research_command_research_all(self):
        """Test: research handler RESEARCHES ALL via execute()."""
        # Setup
        interaction = IntegrationTestHelper.create_interaction_mock()
        rcon_client = MagicMock()
        rcon_client.is_connected = True
        rcon_client.execute = AsyncMock(return_value="All technologies researched")
        
        # Reset rate limiter
        ADMIN_COOLDOWN.reset(interaction.user.id)
        
        # Create handler
        handler = ResearchCommandHandler(
            user_context=IntegrationTestHelper.create_user_context_mock(rcon_client),
            cooldown=IntegrationTestHelper.create_rate_limiter_mock(is_limited=False),
            embed_builder=EmbedBuilder,
        )
        
        # Execute with action="all"
        result = await handler.execute(interaction, force=None, action="all", technology=None)
        
        # Verify
        assert result.success is True
        assert result.embed is not None
        assert rcon_client.execute.called


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTEGRATION TEST: Evolution Command
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestEvolutionCommandIntegration:
    """Integration test: /factorio evolution handler execution."""

    @pytest.mark.asyncio
    async def test_evolution_command_single_surface(self):
        """Test: evolution handler queries single surface."""
        # Setup
        interaction = IntegrationTestHelper.create_interaction_mock()
        rcon_client = MagicMock()
        rcon_client.is_connected = True
        rcon_client.execute = AsyncMock(return_value="42.50%")
        
        # Reset rate limiter
        QUERY_COOLDOWN.reset(interaction.user.id)
        
        # Create handler
        handler = EvolutionCommandHandler(
            user_context=IntegrationTestHelper.create_user_context_mock(rcon_client),
            cooldown=IntegrationTestHelper.create_rate_limiter_mock(is_limited=False),
            embed_builder=EmbedBuilder,
        )
        
        # Execute with single surface
        result = await handler.execute(interaction, target="nauvis")
        
        # Verify
        assert result.success is True
        assert result.embed is not None
        assert "nauvis" in result.embed.title
        assert rcon_client.execute.called

    @pytest.mark.asyncio
    async def test_evolution_command_aggregate_all(self):
        """Test: evolution handler aggregates all surfaces."""
        # Setup
        interaction = IntegrationTestHelper.create_interaction_mock()
        rcon_client = MagicMock()
        rcon_client.is_connected = True
        rcon_client.execute = AsyncMock(
            return_value="AGG:35.00%\nnauvis:42.50%\ngleba:25.00%"
        )
        
        # Reset rate limiter
        QUERY_COOLDOWN.reset(interaction.user.id)
        
        # Create handler
        handler = EvolutionCommandHandler(
            user_context=IntegrationTestHelper.create_user_context_mock(rcon_client),
            cooldown=IntegrationTestHelper.create_rate_limiter_mock(is_limited=False),
            embed_builder=EmbedBuilder,
        )
        
        # Execute with "all"
        result = await handler.execute(interaction, target="all")
        
        # Verify
        assert result.success is True
        assert result.embed is not None
        assert "All Non-platform" in result.embed.title
        assert rcon_client.execute.called


if __name__ == "__main__":
    # Run with: pytest tests/test_factorio_commands_integration.py -v
    # Run with coverage: pytest tests/test_factorio_commands_integration.py --cov=bot.commands --cov-report=term-missing
    pytest.main(["-v", __file__])
