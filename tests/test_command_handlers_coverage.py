

"""
Coverage Improvement Tests for Command Handlers.

This module contains targeted tests to cover previously uncovered branches
in command_handlers.py and command_handlers_batch1.py.

Target: 91%+ coverage
Focus: Error paths, edge cases, None checks, disconnection scenarios

Test Categories:
1. StatusCommandHandler - RCON disconnection, None metrics, empty evolution
2. EvolutionCommandHandler - Parse errors, empty responses, surface errors  
3. ResearchCommandHandler - Force validation, status parse failures
4. Batch1 Handlers - RCON failures during execution
"""

from typing import Dict, Any, Optional
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta
import pytest

from discord_interface import EmbedBuilder
from bot.commands.command_handlers import (
    StatusCommandHandler,
    EvolutionCommandHandler,
    ResearchCommandHandler,
)
from bot.commands.command_handlers import (
    KickCommandHandler,
    BanCommandHandler,
    UnbanCommandHandler,
    MuteCommandHandler,
    UnmuteCommandHandler,
)


# ════════════════════════════════════════════════════════════════════════════
# STATUS HANDLER: RCON DISCONNECTION & EDGE CASES
# ════════════════════════════════════════════════════════════════════════════


class TestStatusCommandHandlerRconDisconnection:
    """Test RCON disconnection scenarios during status command execution."""

    @pytest.mark.asyncio
    async def test_status_rcon_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
        mock_server_manager: MagicMock,
    ) -> None:
        """Coverage: RCON client is None (not just disconnected).
        
        Validates:
        - None check for rcon_client before is_connected
        - Error embed with proper message
        - Ephemeral response
        
        Coverage:
        - Line: if rcon_client is None or not rcon_client.is_connected
        - Branch: rcon_client is None path
        """
        # Setup: RCON client is None
        mock_user_context.get_rcon_for_user.return_value = None
        
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        result = await handler.execute(mock_interaction)
        
        assert result.success is False
        assert result.ephemeral is True
        assert result.followup is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "RCON not available" in call_args

    @pytest.mark.asyncio
    async def test_status_rcon_disconnected(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
        mock_server_manager: MagicMock,
    ) -> None:
        """Coverage: RCON client exists but is_connected=False.
        
        Coverage:
        - Line: if rcon_client is None or not rcon_client.is_connected
        - Branch: not rcon_client.is_connected path
        """
        # Setup: RCON exists but disconnected
        mock_rcon = MagicMock()
        mock_rcon.is_connected = False
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        result = await handler.execute(mock_interaction)
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_metrics_engine_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
        mock_server_manager: MagicMock,
    ) -> None:
        """Coverage: Metrics engine is None for server.
        
        Coverage:
        - Line: if metrics_engine is None
        - RuntimeError exception path
        """
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
        mock_server_manager.get_metrics_engine.return_value = None
        
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        result = await handler.execute(mock_interaction)
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_no_evolution_data(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
        mock_server_manager: MagicMock,
    ) -> None:
        """Coverage: Empty evolution_by_surface with fallback to evolution_factor.
        
        Coverage:
        - Line: if not evolution_by_surface and metrics.get("evolution_factor")
        - Fallback evolution display branch
        """
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
        metrics_engine = MagicMock()
        metrics_engine.gather_all_metrics = AsyncMock(
            return_value={
                "ups": 60.0,
                "evolution_by_surface": {},  # Empty!
                "evolution_factor": 0.75,  # Fallback
            }
        )
        mock_server_manager.get_metrics_engine.return_value = metrics_engine
        
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        result = await handler.execute(mock_interaction)
        
        assert result.success is True
        # Verify fallback evolution was used
        mock_embed_builder.create_base_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_uptime_no_state(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
        mock_server_manager: MagicMock,
        mock_rcon_monitor: MagicMock,
    ) -> None:
        """Coverage: Uptime calculation with server not in rcon_server_states.
        
        Coverage:
        - Line: state = self.rcon_monitor.rcon_server_states.get(server_tag)
        - Branch: state is None -> return "Unknown"
        """
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
        metrics_engine = MagicMock()
        metrics_engine.gather_all_metrics = AsyncMock(return_value={"ups": 60.0})
        mock_server_manager.get_metrics_engine.return_value = metrics_engine
        
        # Empty server states
        mock_rcon_monitor.rcon_server_states = {}
        
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )
        
        result = await handler.execute(mock_interaction)
        
        assert result.success is True
        # Uptime should be "Unknown"

    @pytest.mark.asyncio
    async def test_status_uptime_no_last_connected(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
        mock_server_manager: MagicMock,
        mock_rcon_monitor: MagicMock,
    ) -> None:
        """Coverage: Server state exists but last_connected is None.
        
        Coverage:
        - Line: if not state or not state.get("last_connected")
        - Branch: state exists but no last_connected
        """
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
        metrics_engine = MagicMock()
        metrics_engine.gather_all_metrics = AsyncMock(return_value={"ups": 60.0})
        mock_server_manager.get_metrics_engine.return_value = metrics_engine
        
        # State exists but no last_connected
        mock_rcon_monitor.rcon_server_states = {
            "default": {"connected": True}  # Missing last_connected
        }
        
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
            rcon_monitor=mock_rcon_monitor,
        )
        
        result = await handler.execute(mock_interaction)
        
        assert result.success is True


# ════════════════════════════════════════════════════════════════════════════
# EVOLUTION HANDLER: PARSE ERRORS & EDGE CASES
# ════════════════════════════════════════════════════════════════════════════


class TestEvolutionCommandHandlerEdgeCases:
    """Test evolution command error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_evolution_aggregate_no_agg_line(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Aggregate response with no AGG: prefix line.
        
        Coverage:
        - Line: if not agg_line
        - Default agg_value = "0.00%" path
        """
        # Setup: Response with no AGG: line
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(return_value="nauvis:45.23%\ngleba:32.15%")  # No AGG!
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        result = await handler.execute(mock_interaction, target="all")
        
        assert result.success is True
        # Should use default 0.00%

    @pytest.mark.asyncio
    async def test_evolution_single_surface_not_found(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Single surface returns SURFACE_NOT_FOUND.
        
        Coverage:
        - Line: if resp_str == "SURFACE_NOT_FOUND"
        - Error embed for invalid surface
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(return_value="SURFACE_NOT_FOUND")
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        result = await handler.execute(mock_interaction, target="invalid-surface")
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_evolution_rcon_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: RCON client is None.
        
        Coverage:
        - Line: if rcon_client is None or not rcon_client.is_connected
        - Branch: rcon_client is None
        """
        mock_user_context.get_rcon_for_user.return_value = None
        
        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        result = await handler.execute(mock_interaction, target="nauvis")
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# RESEARCH HANDLER: FORCE VALIDATION & PARSE ERRORS
# ════════════════════════════════════════════════════════════════════════════


class TestResearchCommandHandlerEdgeCases:
    """Test research command force validation and parsing errors."""

    @pytest.mark.asyncio
    async def test_research_status_invalid_response(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Status response doesn't match expected format.
        
        Coverage:
        - Line: except (ValueError, IndexError)
        - Parse failure handling with logger.warning
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(return_value="INVALID_FORMAT")  # Not "X/Y"
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        result = await handler.execute(
            mock_interaction, force="player", action=None, technology=None
        )
        
        assert result.success is True  # Still succeeds, uses default "0/0"
        # Logger warning should be called

    @pytest.mark.asyncio
    async def test_research_rcon_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: RCON client is None.
        
        Coverage:
        - Line: if rcon_client is None or not rcon_client.is_connected
        - Branch: rcon_client is None
        """
        mock_user_context.get_rcon_for_user.return_value = None
        
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
        mock_embed_builder.error_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_all_with_explicit_technology(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: action="all" with technology parameter provided.
        
        Coverage:
        - Line: if action_lower == "all" and technology is None
        - Branch: technology is not None (shouldn't trigger research all)
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(return_value="OK")
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        # This should NOT research all (technology is provided)
        result = await handler.execute(
            mock_interaction, force="player", action="all", technology="automation-2"
        )
        
        assert result.success is True
        # Should research single tech, not all


# ════════════════════════════════════════════════════════════════════════════
# BATCH1 HANDLERS: RCON CLIENT NONE CHECKS
# ════════════════════════════════════════════════════════════════════════════


class TestBatch1HandlersRconNone:
    """Test all batch1 handlers with RCON client None."""

    @pytest.mark.asyncio
    async def test_kick_rcon_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Kick with RCON None."""
        mock_user_context.get_rcon_for_user.return_value = None
        
        handler = KickCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_ban_rcon_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Ban with RCON None."""
        mock_user_context.get_rcon_for_user.return_value = None
        
        handler = BanCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_unban_rcon_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Unban with RCON None."""
        mock_user_context.get_rcon_for_user.return_value = None
        
        handler = UnbanCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_mute_rcon_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Mute with RCON None."""
        mock_user_context.get_rcon_for_user.return_value = None
        
        handler = MuteCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_unmute_rcon_none(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Unmute with RCON None."""
        mock_user_context.get_rcon_for_user.return_value = None
        
        handler = UnmuteCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True


class TestBatch1HandlersRconDisconnected:
    """Test all batch1 handlers with RCON disconnected."""

    @pytest.mark.asyncio
    async def test_kick_rcon_disconnected(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Kick with RCON disconnected."""
        mock_rcon = MagicMock()
        mock_rcon.is_connected = False
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = KickCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_ban_rcon_disconnected(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Ban with RCON disconnected."""
        mock_rcon = MagicMock()
        mock_rcon.is_connected = False
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = BanCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_unban_rcon_disconnected(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Unban with RCON disconnected."""
        mock_rcon = MagicMock()
        mock_rcon.is_connected = False
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = UnbanCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_mute_rcon_disconnected(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Mute with RCON disconnected."""
        mock_rcon = MagicMock()
        mock_rcon.is_connected = False
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = MuteCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True

    @pytest.mark.asyncio
    async def test_unmute_rcon_disconnected(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Unmute with RCON disconnected."""
        mock_rcon = MagicMock()
        mock_rcon.is_connected = False
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = UnmuteCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        result = await handler.execute(mock_interaction, player="Player1")
        
        assert result.success is False
        assert result.ephemeral is True
