"""Exception Handler Tests for All Command Handlers.

This module systematically tests the exception handlers (except Exception as e:)
for all command handlers in command_handlers.py.

Target: 100% coverage of exception handling blocks
Focus: RCON execution failures, unexpected errors, logger verification

Test Pattern for Each Handler:
1. Setup: Mock RCON client to raise exception during execute()
2. Execute: Call handler.execute() with valid parameters
3. Verify:
   - Result: success=False
   - Embed: error_embed called with proper message
   - Ephemeral: True (errors are private)
   - Logger: error() called with exc_info=True

Handlers Covered:
- StatusCommandHandler
- EvolutionCommandHandler (single + aggregate)
- ResearchCommandHandler (status, research_all, research_single, undo)
- KickCommandHandler
- BanCommandHandler
- UnbanCommandHandler
- MuteCommandHandler
- UnmuteCommandHandler
"""

from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from discord_interface import EmbedBuilder
from bot.commands.command_handlers import (
    StatusCommandHandler,
    EvolutionCommandHandler,
    ResearchCommandHandler,
    KickCommandHandler,
    BanCommandHandler,
    UnbanCommandHandler,
    MuteCommandHandler,
    UnmuteCommandHandler,
)


# ════════════════════════════════════════════════════════════════════════════
# STATUSCOMMANDHANDLER EXCEPTION TESTS
# ════════════════════════════════════════════════════════════════════════════


class TestStatusCommandHandlerExceptions:
    """Test exception handling in StatusCommandHandler."""

    @pytest.mark.asyncio
    async def test_status_metrics_engine_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
        mock_server_manager: MagicMock,
    ) -> None:
        """Coverage: Status command handles metrics engine exception.
        
        Validates:
        - Exception raised during gather_all_metrics()
        - Caught by except Exception as e block
        - error_embed called with exception message
        - Logger records error with exc_info=True
        - Result: success=False, ephemeral=True
        
        Coverage:
        - Line: except Exception as e
        - Line: embed = self.embed_builder.error_embed(...)
        - Line: logger.error("status_command_failed", ...)
        """
        # Setup: RCON connected, but metrics engine throws exception
        mock_user_context.get_rcon_for_user.return_value = MagicMock(is_connected=True)
        
        metrics_engine = MagicMock()
        metrics_engine.gather_all_metrics = AsyncMock(
            side_effect=RuntimeError("Metrics collection timeout")
        )
        mock_server_manager.get_metrics_engine.return_value = metrics_engine
        
        handler = StatusCommandHandler(
            user_context=mock_user_context,
            server_manager=mock_server_manager,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(mock_interaction)
        
        # Verify exception handling
        assert result.success is False
        assert result.ephemeral is True
        assert result.followup is True
        
        # Verify error embed called
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Failed to get status" in call_args
        assert "Metrics collection timeout" in call_args
        
        # Verify logger called with exc_info
        mock_logger.error.assert_called_once()
        assert mock_logger.error.call_args[1].get("exc_info") is True


# ════════════════════════════════════════════════════════════════════════════
# EVOLUTIONCOMMANDHANDLER EXCEPTION TESTS
# ════════════════════════════════════════════════════════════════════════════


class TestEvolutionCommandHandlerExceptions:
    """Test exception handling in EvolutionCommandHandler."""

    @pytest.mark.asyncio
    async def test_evolution_aggregate_rcon_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Evolution aggregate handles RCON exception.
        
        Coverage:
        - Line: except Exception as e (in execute)
        - Error embed with exception details
        - Logger error call
        """
        # Setup: RCON throws exception during Lua execution
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=ConnectionError("RCON connection lost")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(mock_interaction, target="all")
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Failed to get evolution" in call_args
        
        # Verify logger
        mock_logger.error.assert_called_once()
        assert "evolution_command_failed" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_evolution_single_surface_rcon_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Evolution single surface handles RCON exception.
        
        Coverage:
        - Exception during single surface query
        - Same except block as aggregate
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=TimeoutError("Lua execution timeout")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = EvolutionCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(mock_interaction, target="nauvis")
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        mock_logger.error.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# RESEARCHCOMMANDHANDLER EXCEPTION TESTS
# ════════════════════════════════════════════════════════════════════════════


class TestResearchCommandHandlerExceptions:
    """Test exception handling in ResearchCommandHandler."""

    @pytest.mark.asyncio
    async def test_research_status_rcon_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Research status handles RCON exception.
        
        Coverage:
        - Line: except Exception as e (in main execute)
        - Top-level exception handler
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=RuntimeError("Server script error")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(
                mock_interaction, force="player", action=None, technology=None
            )
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Research command failed" in call_args
        
        mock_logger.error.assert_called_once()
        assert "research_command_failed" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_research_single_technology_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Research single technology handles exception.
        
        Coverage:
        - Line: except Exception as e (in _handle_research_single)
        - Nested exception handler with force/technology context
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=ValueError("Invalid technology name")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(
                mock_interaction,
                force="player",
                action="automation-2",
                technology=None,
            )
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Failed to research technology" in call_args
        
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_undo_single_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Research undo single technology handles exception.
        
        Coverage:
        - Line: except Exception as e (in _handle_undo)
        - Undo-specific exception handler
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=RuntimeError("Cannot undo researched technology")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = ResearchCommandHandler(
            user_context=mock_user_context,
            cooldown=mock_cooldown,
            embed_builder=mock_embed_builder,
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(
                mock_interaction,
                force="player",
                action="undo",
                technology="automation-2",
            )
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        mock_logger.error.assert_called_once()
        assert "research_undo_failed" in str(mock_logger.error.call_args)


# ════════════════════════════════════════════════════════════════════════════
# BATCH1 HANDLERS EXCEPTION TESTS
# ════════════════════════════════════════════════════════════════════════════


class TestBatch1HandlersExceptions:
    """Test exception handling for all Batch1 player management handlers."""

    @pytest.mark.asyncio
    async def test_kick_rcon_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Kick command handles RCON exception.
        
        Coverage:
        - Line: except Exception as e (in KickCommandHandler.execute)
        - logger.error("kick_command_failed", ...)
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=RuntimeError("Player not found on server")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = KickCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(
                mock_interaction, player="TestPlayer", reason="Testing"
            )
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Failed to kick player" in call_args
        assert "Player not found" in call_args
        
        mock_logger.error.assert_called_once()
        assert "kick_command_failed" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_ban_rcon_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Ban command handles RCON exception.
        
        Coverage:
        - Line: except Exception as e (in BanCommandHandler.execute)
        - logger.error("ban_command_failed", ...)
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=PermissionError("Insufficient permissions")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = BanCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(
                mock_interaction, player="TestPlayer", reason="Violation"
            )
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        mock_logger.error.assert_called_once()
        assert "ban_command_failed" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_unban_rcon_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Unban command handles RCON exception.
        
        Coverage:
        - Line: except Exception as e (in UnbanCommandHandler.execute)
        - logger.error("unban_command_failed", ...)
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=ValueError("Player not in ban list")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = UnbanCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(mock_interaction, player="TestPlayer")
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        mock_logger.error.assert_called_once()
        assert "unban_command_failed" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_mute_rcon_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Mute command handles RCON exception.
        
        Coverage:
        - Line: except Exception as e (in MuteCommandHandler.execute)
        - logger.error("mute_command_failed", ...)
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=ConnectionError("Server not responding")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = MuteCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(mock_interaction, player="TestPlayer")
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Failed to mute player" in call_args
        
        mock_logger.error.assert_called_once()
        assert "mute_command_failed" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_unmute_rcon_exception(
        self,
        mock_interaction: MagicMock,
        mock_user_context: MagicMock,
        mock_cooldown: MagicMock,
        mock_embed_builder: MagicMock,
    ) -> None:
        """Coverage: Unmute command handles RCON exception.
        
        Coverage:
        - Line: except Exception as e (in UnmuteCommandHandler.execute)
        - logger.error("unmute_command_failed", ...)
        """
        mock_rcon = MagicMock()
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(
            side_effect=TimeoutError("Command execution timeout")
        )
        mock_user_context.get_rcon_for_user.return_value = mock_rcon
        
        handler = UnmuteCommandHandler(
            user_context_provider=mock_user_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,  # type: ignore[arg-type]
        )
        
        with patch("bot.commands.command_handlers.logger") as mock_logger:
            result = await handler.execute(mock_interaction, player="TestPlayer")
        
        assert result.success is False
        assert result.ephemeral is True
        mock_embed_builder.error_embed.assert_called_once()
        call_args = mock_embed_builder.error_embed.call_args[0][0]
        assert "Failed to unmute player" in call_args
        
        mock_logger.error.assert_called_once()
        assert "unmute_command_failed" in str(mock_logger.error.call_args)
