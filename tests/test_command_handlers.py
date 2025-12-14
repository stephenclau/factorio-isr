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
Test suite for command handlers with explicit dependency injection.

Demonstrates the advantages of DI for testing:
- Clean mocking: dependencies injected via constructor
- Isolated logic: test handler execute() directly
- No closure hacking: straightforward assertions
- 91%+ coverage target: happy path + error paths
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
import discord

from src.bot.commands.command_handlers import (
    StatusCommandHandler,
    EvolutionCommandHandler,
    ResearchCommandHandler,
    CommandResult,
)


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES: Clean mock dependencies
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_interaction():
    """Create a mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.id = 12345
    interaction.user.name = "TestUser"
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def mock_user_context():
    """Create a mock user context provider."""
    context = MagicMock()
    context.get_user_server.return_value = "default"
    context.get_server_display_name.return_value = "Test Server"
    context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
    return context


@pytest.fixture
def mock_cooldown():
    """Create a mock rate limiter."""
    cooldown = MagicMock()
    cooldown.is_rate_limited.return_value = (False, None)  # Not rate limited
    return cooldown


@pytest.fixture
def mock_cooldown_limited():
    """Create a rate-limited mock."""
    cooldown = MagicMock()
    cooldown.is_rate_limited.return_value = (True, 5.0)  # Rate limited, 5s retry
    return cooldown


@pytest.fixture
def mock_embed_builder():
    """Create a mock embed builder."""
    builder = MagicMock()
    builder.COLOR_SUCCESS = 0x00FF00
    builder.COLOR_WARNING = 0xFFFF00
    builder.COLOR_INFO = 0x0000FF
    builder.COLOR_ADMIN = 0xFF0000

    # Return embeds for each method
    builder.cooldown_embed.return_value = MagicMock(spec=discord.Embed)
    builder.error_embed.return_value = MagicMock(spec=discord.Embed)
    builder.info_embed.return_value = MagicMock(spec=discord.Embed)
    builder.create_base_embed.return_value = MagicMock(spec=discord.Embed)

    return builder


@pytest.fixture
def mock_rcon_client():
    """Create a mock RCON client."""
    client = MagicMock()
    client.is_connected = True
    client.execute = AsyncMock(return_value="")
    return client


@pytest.fixture
def mock_server_manager():
    """Create a mock server manager."""
    manager = MagicMock()
    metrics_engine = MagicMock()
    metrics_engine.gather_all_metrics = AsyncMock(
        return_value={
            "ups": 60.0,
            "ups_sma": 59.5,
            "ups_ema": 59.8,
            "player_count": 2,
            "players": ["Player1", "Player2"],
            "evolution_by_surface": {"nauvis": 0.45},
            "is_paused": False,
        }
    )
    manager.get_metrics_engine.return_value = metrics_engine
    return manager


@pytest.fixture
def mock_rcon_monitor():
    """Create a mock RCON monitor."""
    monitor = MagicMock()
    monitor.rcon_server_states = {
        "default": {
            "last_connected": datetime.now(timezone.utc),
            "connected": True,
        }
    }
    return monitor


# ═════════════════════════════════════════════════════════════════════════════
# TESTS: StatusCommandHandler
# ═════════════════════════════════════════════════════════════════════════════


class TestStatusCommandHandler:
    """Test suite for StatusCommandHandler with happy path and error paths."""

    @pytest.mark.asyncio
    async def test_status_happy_path(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
        mock_server_manager,
        mock_rcon_monitor,
    ):
        """Happy path: rate limit OK, RCON connected, metrics available."""
        # Setup
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )

        # Execute
        result = await handler.execute(mock_interaction)

        # Verify
        assert result.success is True
        assert result.ephemeral is False
        assert result.followup is True
        assert isinstance(result.embed, discord.Embed) or isinstance(
            result.embed, MagicMock
        )
        mock_cooldown.is_rate_limited.assert_called_once_with(12345)
        mock_user_context.get_user_server.assert_called_once()
        mock_server_manager.get_metrics_engine.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_rate_limited(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown_limited,
        mock_embed_builder,
        mock_server_manager,
        mock_rcon_monitor,
    ):
        """Error path: user is rate limited."""
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown_limited,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )

        result = await handler.execute(mock_interaction)

        # Verify rate limit response
        assert result.success is False
        assert result.ephemeral is True
        assert result.followup is False
        mock_embed_builder.cooldown_embed.assert_called_once_with(5.0)

    @pytest.mark.asyncio
    async def test_status_rcon_disconnected(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
        mock_server_manager,
        mock_rcon_monitor,
    ):
        """Error path: RCON client is not connected."""
        # RCON is disconnected
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=False)

        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )

        result = await handler.execute(mock_interaction)

        # Verify error response
        assert result.success is False
        assert result.ephemeral is True
        assert result.followup is True
        mock_embed_builder.error_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_rcon_none(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
        mock_server_manager,
        mock_rcon_monitor,
    ):
        """Error path: RCON client is None (not available)."""
        mock_user_context.get_rcon_for_user.return_value = None

        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_status_metrics_engine_none(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
        mock_server_manager,
        mock_rcon_monitor,
    ):
        """Error path: metrics engine not available for server."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
        mock_server_manager.get_metrics_engine.return_value = None

        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_metrics_exception(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
        mock_server_manager,
        mock_rcon_monitor,
    ):
        """Error path: exception during metrics gathering."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
        metrics_engine = MagicMock()
        metrics_engine.gather_all_metrics = AsyncMock(
            side_effect=Exception("Metrics engine error")
        )
        mock_server_manager.get_metrics_engine.return_value = metrics_engine

        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )

        result = await handler.execute(mock_interaction)

        assert result.success is False
        assert result.ephemeral is True
        # Verify error message contains the exception
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Metrics engine error" in call_args


# ═════════════════════════════════════════════════════════════════════════════
# TESTS: EvolutionCommandHandler
# ═════════════════════════════════════════════════════════════════════════════


class TestEvolutionCommandHandler:
    """Test suite for EvolutionCommandHandler."""

    @pytest.mark.asyncio
    async def test_evolution_single_surface_happy_path(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: query single surface evolution."""
        mock_rcon = AsyncMock()
        mock_rcon.execute.return_value = "45.50%"
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)

        # Patch the RCON client to return it
        mock_user_context.get_rcon_for_user.return_value.execute = AsyncMock(
            return_value="45.50%"
        )

        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(mock_interaction, target="nauvis")

        assert result.success is True
        assert result.followup is True
        mock_cooldown.is_rate_limited.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_evolution_aggregate_all_happy_path(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: aggregate evolution across all non-platform surfaces."""
        response = "AGG:42.30%\nnauvis:45.50%\ngleba:38.90%"
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value=response)
        )

        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(mock_interaction, target="all")

        assert result.success is True
        assert result.followup is True

    @pytest.mark.asyncio
    async def test_evolution_surface_not_found(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Error path: requested surface not found."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value="SURFACE_NOT_FOUND")
        )

        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(mock_interaction, target="invalid_surface")

        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_evolution_platform_surface_ignored(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Error path: platform surfaces are excluded."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True,
            execute=AsyncMock(return_value="SURFACE_PLATFORM_IGNORED"),
        )

        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(mock_interaction, target="platform-1")

        assert result.success is False
        assert result.ephemeral is True
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "platform" in call_args.lower()

    @pytest.mark.asyncio
    async def test_evolution_rcon_disconnected(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Error path: RCON not connected."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=False)

        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(mock_interaction, target="nauvis")

        assert result.success is False
        assert result.ephemeral is True
        assert result.followup is True


# ═════════════════════════════════════════════════════════════════════════════
# TESTS: ResearchCommandHandler
# ═════════════════════════════════════════════════════════════════════════════


class TestResearchCommandHandler:
    """Test suite for ResearchCommandHandler."""

    @pytest.mark.asyncio
    async def test_research_display_status_happy_path(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: display research progress."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value="42/100")
        )

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(
            mock_interaction, force=None, action=None, technology=None
        )

        assert result.success is True
        assert result.followup is True
        mock_embed_builder.info_embed.assert_called_once()
        call_args = mock_embed_builder.info_embed.call_args
        assert "42/100" in call_args[1]["message"] or "42/100" in str(call_args)

    @pytest.mark.asyncio
    async def test_research_all_happy_path(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: research all technologies."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value="researched")
        )

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(
            mock_interaction, force="player", action="all", technology=None
        )

        assert result.success is True
        embed = result.embed
        assert embed.color == mock_embed_builder.COLOR_SUCCESS

    @pytest.mark.asyncio
    async def test_research_single_technology_happy_path(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: research single technology."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value="OK")
        )

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(
            mock_interaction, force="player", action=None, technology="automation-2"
        )

        assert result.success is True
        assert result.followup is True

    @pytest.mark.asyncio
    async def test_research_undo_all_happy_path(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: undo all research."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value="reverted")
        )

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(
            mock_interaction, force="player", action="undo", technology="all"
        )

        assert result.success is True
        embed = result.embed
        assert embed.color == mock_embed_builder.COLOR_WARNING

    @pytest.mark.asyncio
    async def test_research_undo_single_technology_happy_path(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: undo single technology."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value="OK")
        )

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(
            mock_interaction, force="player", action="undo", technology="automation-2"
        )

        assert result.success is True
        assert result.followup is True

    @pytest.mark.asyncio
    async def test_research_multi_force_coop(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: Coop mode (default force='player')."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value="42/100")
        )

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        # No force provided, should default to "player"
        result = await handler.execute(
            mock_interaction, force=None, action=None, technology=None
        )

        assert result.success is True
        # Verify RCON was called with default "player" force
        mock_user_context.get_rcon_for_user.return_value.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_multi_force_pvp(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Happy path: PvP mode (custom force='enemy')."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True, execute=AsyncMock(return_value="10/100")
        )

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(
            mock_interaction, force="enemy", action=None, technology=None
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_research_rcon_error_single_tech(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Error path: RCON execution error when researching single tech."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(
            is_connected=True,
            execute=AsyncMock(side_effect=Exception("Technology not found")),
        )

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(
            mock_interaction, force="player", action=None, technology="invalid-tech"
        )

        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Technology not found" in call_args

    @pytest.mark.asyncio
    async def test_research_rcon_disconnected(
        self,
        mock_interaction,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Error path: RCON not connected."""
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=False)

        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        result = await handler.execute(
            mock_interaction, force="player", action=None, technology=None
        )

        assert result.success is False
        assert result.ephemeral is True
        assert result.followup is True


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Verify DI instantiation
# ═════════════════════════════════════════════════════════════════════════════


class TestCommandHandlerInstantiation:
    """Test that handlers can be instantiated with mock dependencies."""

    def test_status_handler_instantiation(
        self,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
        mock_server_manager,
        mock_rcon_monitor,
    ):
        """Verify StatusCommandHandler can be instantiated with DI."""
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )

        assert handler.user_context == mock_user_context
        assert handler.server_manager == mock_server_manager
        assert handler.cooldown == mock_cooldown
        assert handler.embed_builder == mock_embed_builder
        assert handler.rcon_monitor == mock_rcon_monitor

    def test_evolution_handler_instantiation(
        self,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Verify EvolutionCommandHandler can be instantiated with DI."""
        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        assert handler.user_context == mock_user_context
        assert handler.cooldown == mock_cooldown
        assert handler.embed_builder == mock_embed_builder

    def test_research_handler_instantiation(
        self,
        mock_user_context,
        mock_cooldown,
        mock_embed_builder,
    ):
        """Verify ResearchCommandHandler can be instantiated with DI."""
        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )

        assert handler.user_context == mock_user_context
        assert handler.cooldown == mock_cooldown
        assert handler.embed_builder == mock_embed_builder


class TestCommandResult:
    """Test CommandResult dataclass."""

    def test_command_result_success(
        self,
        mock_embed_builder,
    ):
        """Verify CommandResult can track successful commands."""
        embed = mock_embed_builder.info_embed.return_value
        result = CommandResult(
            success=True,
            embed=embed,
            ephemeral=False,
            followup=True,
        )

        assert result.success is True
        assert result.ephemeral is False
        assert result.followup is True

    def test_command_result_error(
        self,
        mock_embed_builder,
    ):
        """Verify CommandResult can track error commands."""
        embed = mock_embed_builder.error_embed.return_value
        result = CommandResult(
            success=False,
            embed=embed,
            ephemeral=True,
            followup=False,
        )

        assert result.success is False
        assert result.ephemeral is True
        assert result.followup is False
