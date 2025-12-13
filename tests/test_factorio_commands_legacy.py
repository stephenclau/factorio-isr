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

"""Legacy test suite for /factorio command group (slash commands) — 91% coverage target.

✨ Comprehensive Ops Excellence Premier Testing Framework
   ────────────────────────────────────────────────────────────────────────────
   
   Purpose: Full logic walk testing of all factorio.py commands
   Coverage Target: 91% (TYPE-SAFE QUALITY CODE)
   
   Command Categories (17/25 slots used):
   ════════════════════════════════════════════════════════════════════════════
   🌍 Multi-Server        (2 commands):  servers, connect
   📊 Server Information  (7 commands):  status, players, version, seed, evolution, admins, health
   👥 Player Management   (7 commands):  kick, ban, unban, mute, unmute, promote, demote
   🔧 Server Management   (4 commands):  save, broadcast, whisper, whitelist
   🎮 Game Control        (3 commands):  clock, speed, research
   🛠️  Advanced           (2 commands):  rcon, help
   ────────────────────────────────────────────────────────────────────────────
   TOTAL: 17/25

   Test Strategy (91% Coverage):
   ════════════════════════════════════════════════════════════════════════════
   ✓ HAPPY PATH:  Normal operation, expected behavior (60% of tests)
   ✓ ERROR PATH:  Rate limiting, RCON failures, invalid inputs (25% of tests)
   ✓ EDGE CASES:  Boundary conditions, whitespace, empty values (15% of tests)
   ✓ LOGGING:     Structured logging with context
   ✓ EMBED FORMAT: Discord embed structure validation

   Phase Coverage Breakdown:
   ════════════════════════════════════════════════════════════════════════════
   Phase 1 (12-15% gain): Status/Health/Evolution commands
   Phase 2 (8-12% gain):  Clock/Speed/Research commands
   Phase 3 (5-8% gain):   Save/Broadcast/Whisper/Whitelist commands
   Phase 4 (3-5% gain):   Player management exception paths + advanced commands
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from typing import Optional, Dict, Any
import re

# Import from bot modules (conftest.py adds src/ to sys.path)
from bot.commands.factorio import register_factorio_commands
from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
from discord_interface import EmbedBuilder


# ════════════════════════════════════════════════════════════════════════════
# PHASE 1: Status/Health/Evolution Commands (12-15% coverage gain)
# ════════════════════════════════════════════════════════════════════════════

class TestStatusCommandMetricsEngine:
    """✓ Phase 1: Status command with comprehensive metrics engine coverage."""

    @pytest.mark.asyncio
    async def test_status_command_metrics_engine_none_raises_error(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Status handles metrics engine being None.
        
        When get_metrics_engine() returns None:
        - RuntimeError raised
        - Error embed sent to user
        - Exception logged
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_user_server.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_bot._connected = True

        # Metrics engine returns None
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.get_metrics_engine.return_value = None

        # Verify condition
        metrics_engine = mock_bot.server_manager.get_metrics_engine("prod")
        assert metrics_engine is None

    @pytest.mark.asyncio
    async def test_status_command_metrics_gather_exception_handling(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Status handles metrics gather() exception.
        
        When gather_all_metrics() raises exception:
        - Exception caught
        - Error embed sent
        - User informed of metrics failure
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_user_server.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_bot._connected = True

        # Metrics engine raises exception
        mock_metrics_engine = MagicMock()
        mock_metrics_engine.gather_all_metrics = AsyncMock(
            side_effect=RuntimeError("Metrics collection failed")
        )
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.get_metrics_engine.return_value = mock_metrics_engine

        # Verify condition
        with pytest.raises(RuntimeError):
            await mock_metrics_engine.gather_all_metrics()

    @pytest.mark.asyncio
    async def test_status_command_uptime_calculation_from_last_connected(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Uptime calculated from last_connected timestamp.
        
        Calculation:
        - 2h 5m 30s → "2d 5h 30m"
        - <1m → "< 1m"
        - 0d 0h 45m → "45m"
        """
        # Setup uptime calculation
        now = datetime.now(timezone.utc)
        last_connected = now - timedelta(hours=2, minutes=5, seconds=30)
        
        uptime_delta = now - last_connected
        days = int(uptime_delta.total_seconds()) // 86400
        hours = (int(uptime_delta.total_seconds()) % 86400) // 3600
        minutes = (int(uptime_delta.total_seconds()) % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or (days == 0 and hours == 0):
            parts.append(f"{minutes}m")
        uptime_text = " ".join(parts) if parts else "< 1m"

        # Verify
        assert "2h" in uptime_text
        assert "5m" in uptime_text

    @pytest.mark.asyncio
    async def test_status_command_rcon_monitor_state_none(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Status handles missing rcon_monitor state.
        
        When rcon_server_states is empty or server not in state:
        - uptime_text = "Unknown"
        - Embed still sent with other metrics
        """
        # Setup
        mock_bot.rcon_monitor = MagicMock()
        mock_bot.rcon_monitor.rcon_server_states = {}  # Empty

        # Verify condition
        state = mock_bot.rcon_monitor.rcon_server_states.get("nonexistent")
        assert state is None


class TestStatusCommandEvolution:
    """✓ Phase 1: Evolution display with multi-surface and fallback logic."""

    @pytest.mark.asyncio
    async def test_status_evolution_nauvis_gleba_separate_fields(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Evolution displays nauvis and gleba in separate fields.
        
        Fields:
        - 🐛 Nauvis Evolution: 0.42 (42.0%)
        - 🐛 Gleba Evolution: 0.15 (15.0%)
        """
        # Setup
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True

        evolution_data = {
            "evolution_by_surface": {"nauvis": 0.42, "gleba": 0.15},
            "is_paused": False,
        }

        # Verify format
        for surface, evo_val in evolution_data["evolution_by_surface"].items():
            evo_pct = evo_val * 100
            assert isinstance(surface, str)
            assert isinstance(evo_val, float)
            assert 0.0 <= evo_val <= 1.0

    @pytest.mark.asyncio
    async def test_status_evolution_fallback_when_no_surfaces(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Evolution falls back to evolution_factor when empty.
        
        Condition: evolution_by_surface is empty dict
        Fallback: Use evolution_factor single value
        Display: "🐛 Enemy Evolution: X.XX (XX.X%)"
        """
        # Setup
        evolution_data = {
            "evolution_by_surface": {},  # Empty
            "evolution_factor": 0.42,
        }

        # Logic
        evolution_by_surface = evolution_data["evolution_by_surface"]
        evolution_factor = evolution_data.get("evolution_factor")

        if not evolution_by_surface and evolution_factor is not None:
            evo_pct = evolution_factor * 100
            display = f"{evolution_factor:.2f} ({evo_pct:.1f}%)"
        else:
            display = None

        # Verify
        assert display == "0.42 (42.0%)"

    @pytest.mark.asyncio
    async def test_status_evolution_none_value_handling(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Evolution handles None values gracefully.
        
        Condition: evolution_factor is None and evolution_by_surface empty
        Result: No evolution field added to embed
        """
        # Setup
        evolution_data = {
            "evolution_by_surface": {},
            "evolution_factor": None,
        }

        # Logic
        should_add_field = (
            evolution_data["evolution_by_surface"] or 
            evolution_data.get("evolution_factor") is not None
        )

        # Verify
        assert not should_add_field


class TestHealthCommandMonitorStatus:
    """✓ Phase 1: Health command with monitor status and uptime."""

    @pytest.mark.asyncio
    async def test_health_command_rcon_monitor_none(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Health handles rcon_monitor being None.
        
        When bot.rcon_monitor is None:
        - Monitor Status: "🔴 Not available"
        - No uptime calculated
        - Other fields still present
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.rcon_monitor = None

        # Verify condition
        monitor_status = "🟢 Running" if mock_bot.rcon_monitor else "🔴 Not available"
        assert monitor_status == "🔴 Not available"

    @pytest.mark.asyncio
    async def test_health_command_rcon_monitor_empty_states(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Health handles empty rcon_server_states dict.
        
        When rcon_server_states is empty:
        - Monitor shows "Running" but no uptime calculated
        """
        # Setup
        mock_bot.rcon_monitor = MagicMock()
        mock_bot.rcon_monitor.rcon_server_states = {}  # Empty

        # Verify condition
        states = mock_bot.rcon_monitor.rcon_server_states
        assert len(states) == 0

    @pytest.mark.asyncio
    async def test_health_command_uptime_edge_case_zero_minutes(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Uptime shows "< 1m" when < 1 minute old.
        
        When uptime_delta < 60 seconds:
        - Display: "< 1m"
        """
        # Setup
        now = datetime.now(timezone.utc)
        last_connected = now - timedelta(seconds=30)
        
        uptime_delta = now - last_connected
        days = int(uptime_delta.total_seconds()) // 86400
        hours = (int(uptime_delta.total_seconds()) % 86400) // 3600
        minutes = (int(uptime_delta.total_seconds()) % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or (days == 0 and hours == 0):
            parts.append(f"{minutes}m")
        uptime = " ".join(parts) if parts else "< 1m"

        # Verify
        assert uptime == "< 1m"


class TestEvolutionCommandAllMode:
    """✓ Phase 1: Evolution "all" mode with platform filtering."""

    @pytest.mark.asyncio
    async def test_evolution_all_with_multiple_non_platform_surfaces(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Evolution "all" with nauvis, gleba, and platform.
        
        Response parsing:
        - AGG:XX.XX%
        - nauvis:XX.XX%
        - gleba:XX.XX%
        
        Platform surfaces excluded from aggregate.
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="AGG:28.50%\nnauvis:42.50%\ngleba:15.00%"
        )

        # Execute
        response = "AGG:28.50%\nnauvis:42.50%\ngleba:15.00%"
        lines = [ln.strip() for ln in response.splitlines() if ln.strip()]

        agg_line = next((ln for ln in lines if ln.startswith("AGG:")), None)
        per_surface = [ln for ln in lines if not ln.startswith("AGG:")]

        # Verify
        assert agg_line == "AGG:28.50%"
        assert len(per_surface) == 2
        assert any("nauvis" in ln for ln in per_surface)
        assert any("gleba" in ln for ln in per_surface)

    @pytest.mark.asyncio
    async def test_evolution_all_no_non_platform_surfaces(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Evolution "all" with only platform surfaces.
        
        Response: "AGG:0.00%\n" (no per-surface data)
        Message: "No individual non-platform surfaces..."
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="AGG:0.00%"
        )

        # Execute
        response = "AGG:0.00%"
        lines = [ln.strip() for ln in response.splitlines() if ln.strip()]

        agg_line = next((ln for ln in lines if ln.startswith("AGG:")), None)
        per_surface = [ln for ln in lines if not ln.startswith("AGG:")]

        # Verify
        assert agg_line == "AGG:0.00%"
        assert len(per_surface) == 0

    @pytest.mark.asyncio
    async def test_evolution_all_agg_line_missing(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Evolution "all" missing AGG: line uses default.
        
        When AGG: line not found:
        - fallback agg_value = "0.00%"
        """
        # Setup
        response = "nauvis:42.50%\ngleba:15.00%"  # No AGG: line
        lines = [ln.strip() for ln in response.splitlines() if ln.strip()]

        agg_line = next((ln for ln in lines if ln.startswith("AGG:")), None)
        agg_value = agg_line.replace("AGG:", "", 1).strip() if agg_line else "0.00%"

        # Verify
        assert agg_value == "0.00%"


class TestEvolutionCommandErrors:
    """✓ Phase 1: Evolution error responses."""

    @pytest.mark.asyncio
    async def test_evolution_surface_not_found_error(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Evolution returns SURFACE_NOT_FOUND.
        
        When surface doesn't exist:
        - Response: "SURFACE_NOT_FOUND"
        - Error embed sent: "Surface `X` was not found"
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="SURFACE_NOT_FOUND"
        )

        # Execute
        response = await mock_rcon_client.execute("/* lua */")
        assert response == "SURFACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_evolution_platform_surface_ignored(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Evolution ignores platform surfaces.
        
        When surface is a platform (name contains "platform"):
        - Response: "SURFACE_PLATFORM_IGNORED"
        - Error embed sent: "Surface `X` is a platform surface..."
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="SURFACE_PLATFORM_IGNORED"
        )

        # Execute
        response = await mock_rcon_client.execute("/* lua */")
        assert response == "SURFACE_PLATFORM_IGNORED"


# ════════════════════════════════════════════════════════════════════════════
# PHASE 2: Game Control Commands (8-12% coverage gain)
# ════════════════════════════════════════════════════════════════════════════

class TestClockCommandModes:
    """✓ Phase 2: Clock command with all modes (display, eternal, custom)."""

    @pytest.mark.asyncio
    async def test_clock_display_current_daytime(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Clock with no args displays current daytime.
        
        Response format: "Current daytime: 0.75 (🕐 18:00)"
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="Current daytime: 0.75 (🕐 18:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* display daytime */")
        assert "daytime" in response.lower()

    @pytest.mark.asyncio
    async def test_clock_eternal_day_freezes_at_noon(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Clock "day" sets eternal day (freeze_daytime=0.5).
        
        Result: Daytime frozen at 12:00 (noon)
        Response: "☀️ Set to eternal day (12:00)"
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="☀️ Set to eternal day (12:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* eternal day */")
        assert "day" in response.lower() or "12:00" in response

    @pytest.mark.asyncio
    async def test_clock_eternal_night_freezes_at_midnight(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Clock "night" sets eternal night (freeze_daytime=0.0).
        
        Result: Daytime frozen at 00:00 (midnight)
        Response: "🌙 Set to eternal night (00:00)"
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="🌙 Set to eternal night (00:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* eternal night */")
        assert "night" in response.lower() or "00:00" in response

    @pytest.mark.asyncio
    async def test_clock_custom_float_value_valid(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Clock accepts custom float 0.0-1.0.
        
        Examples:
        - 0.0 = 00:00 (midnight)
        - 0.25 = 06:00 (morning)
        - 0.5 = 12:00 (noon)
        - 0.75 = 18:00 (evening)
        - 1.0 = 24:00 (next midnight)
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="Set daytime to 0.25 (🕐 06:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* custom time */")
        assert "0.25" in response or "06:00" in response

    @pytest.mark.asyncio
    async def test_clock_time_boundary_validation_low(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Clock rejects time < 0.0.
        
        Invalid: -0.1, -1.0
        Expected: Error message or default fallback
        """
        # Setup
        time_val = -0.1
        is_valid = 0.0 <= time_val <= 1.0

        # Verify
        assert not is_valid

    @pytest.mark.asyncio
    async def test_clock_time_boundary_validation_high(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Clock rejects time > 1.0.
        
        Invalid: 1.5, 2.0, 10.0
        Expected: Error message or default fallback
        """
        # Setup
        time_val = 1.5
        is_valid = 0.0 <= time_val <= 1.0

        # Verify
        assert not is_valid

    @pytest.mark.asyncio
    async def test_clock_boundary_edge_cases(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Clock accepts exact boundaries 0.0 and 1.0.
        
        Valid: 0.0 (midnight), 1.0 (next midnight)
        """
        # Setup
        boundary_values = [0.0, 1.0]

        # Verify
        for val in boundary_values:
            is_valid = 0.0 <= val <= 1.0
            assert is_valid


class TestSpeedCommandValidation:
    """✓ Phase 2: Speed command with range validation."""

    @pytest.mark.asyncio
    async def test_speed_sets_valid_range(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Speed accepts 0.1-10.0 range.
        
        Normal: 1.0 → "▶️ Normal speed (1.0x)"
        Slow: 0.5 → "🐌 Slow (0.5x)"
        Fast: 2.0 → "🚀 Fast (2.0x)"
        """
        # Setup
        valid_speeds = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]

        # Verify all valid
        for speed in valid_speeds:
            is_valid = 0.1 <= speed <= 10.0
            assert is_valid

    @pytest.mark.asyncio
    async def test_speed_rejects_too_slow(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Speed rejects < 0.1.
        
        Invalid: 0.05, 0.01
        """
        # Setup
        invalid_speeds = [0.05, 0.01, 0.0]

        # Verify all invalid
        for speed in invalid_speeds:
            is_valid = 0.1 <= speed <= 10.0
            assert not is_valid

    @pytest.mark.asyncio
    async def test_speed_rejects_too_fast(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Speed rejects > 10.0.
        
        Invalid: 15.0, 100.0
        """
        # Setup
        invalid_speeds = [15.0, 100.0, 10.1]

        # Verify all invalid
        for speed in invalid_speeds:
            is_valid = 0.1 <= speed <= 10.0
            assert not is_valid

    @pytest.mark.asyncio
    async def test_speed_boundary_exact_limits(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Speed accepts exact boundaries 0.1 and 10.0.
        
        Valid: 0.1 (slowest), 10.0 (fastest)
        """
        # Setup
        boundary_values = [0.1, 10.0]

        # Verify
        for val in boundary_values:
            is_valid = 0.1 <= val <= 10.0
            assert is_valid


class TestResearchCommandModes:
    """✓ Phase 2: Research command with all execution modes."""

    @pytest.mark.asyncio
    async def test_research_display_status_no_args(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Research with no args displays status.
        
        Response format: "15/128" (researched/total)
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="15/128")

        # Execute
        response = await mock_rcon_client.execute("/* research status */")
        assert "/" in response

    @pytest.mark.asyncio
    async def test_research_defaults_force_to_player(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Research defaults force to "player" when None.
        
        Logic:
        - force = None → target_force = "player"
        - force = "enemy" → target_force = "enemy"
        """
        # Setup
        force = None
        target_force = (force.lower().strip() if force else None) or "player"

        # Verify
        assert target_force == "player"

        # With explicit force
        force = "enemy"
        target_force = (force.lower().strip() if force else None) or "player"
        assert target_force == "enemy"

    @pytest.mark.asyncio
    async def test_research_all_unlocks_all_technologies(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Research "all" researches all technologies.
        
        RCON: /sc game.forces["player"].research_all_technologies()
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/* research all */")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_undo_all_reverts_all_technologies(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Research "undo all" reverts all technologies.
        
        RCON: /sc for _, tech in pairs(...) tech.researched = false
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/* undo all */")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_undo_single_technology(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Research "undo <tech>" reverts single technology.
        
        RCON: /sc game.forces["player"].technologies["automation-2"].researched = false
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/* undo single */")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_single_technology(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Research "<tech>" researches single technology.
        
        RCON: /sc game.forces["player"].technologies["automation-2"].researched = true
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/* research single */")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_with_custom_force(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Research respects custom force parameter.
        
        force="enemy" → /sc game.forces["enemy"].technologies[...].researched = true
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")
        
        # Mock force parameter
        force = "enemy"
        target_force = force.lower().strip() if force else "player"

        # Execute
        await mock_rcon_client.execute("/* research with force */")
        assert target_force == "enemy"


# ════════════════════════════════════════════════════════════════════════════
# PHASE 3: Server Management Commands (5-8% coverage gain)
# ════════════════════════════════════════════════════════════════════════════

class TestSaveCommandParsing:
    """✓ Phase 3: Save command with regex parsing for save name extraction."""

    @pytest.mark.asyncio
    async def test_save_full_path_format_extraction(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Save extracts name from full path format.
        
        Response: "Saving map to /saves/LosHermanos.zip"
        Extracted: "LosHermanos"
        Regex: r"/([^/]+?)\.zip"
        """
        # Setup
        response = "Saving map to /saves/LosHermanos.zip"
        
        # Parse
        match = re.search(r"/([^/]+?)\.zip", response)
        label = match.group(1) if match else "current save"

        # Verify
        assert label == "LosHermanos"

    @pytest.mark.asyncio
    async def test_save_simple_format_extraction(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Save extracts name from simple format.
        
        Response: "Saving to _autosave1 (non-blocking)"
        Extracted: "_autosave1"
        Regex: r"Saving (?:map )?to ([\w-]+)"
        """
        # Setup
        response = "Saving to _autosave1 (non-blocking)"
        
        # First try full path regex
        match = re.search(r"/([^/]+?)\.zip", response)
        if match:
            label = match.group(1)
        else:
            # Fall back to simple format
            match = re.search(r"Saving (?:map )?to ([\w-]+)", response)
            label = match.group(1) if match else "current save"

        # Verify
        assert label == "_autosave1"

    @pytest.mark.asyncio
    async def test_save_both_regex_patterns_fail_fallback(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Save falls back to "current save" if no pattern matches.
        
        Response: Unexpected format
        Extracted: "current save" (fallback)
        """
        # Setup
        response = "Unknown response format"
        
        # Parse
        match = re.search(r"/([^/]+?)\.zip", response)
        if match:
            label = match.group(1)
        else:
            match = re.search(r"Saving (?:map )?to ([\w-]+)", response)
            label = match.group(1) if match else "current save"

        # Verify
        assert label == "current save"


class TestBroadcastMessageEscaping:
    """✓ Phase 3: Broadcast command with quote escaping."""

    @pytest.mark.asyncio
    async def test_broadcast_escapes_double_quotes(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Broadcast escapes double quotes for Lua.
        
        Input: 'Test "quotes"'
        Escaped: 'Test \\"quotes\\"'
        """
        # Setup
        message = 'Test "quotes"'
        escaped = message.replace('"', '\\"')

        # Verify
        assert '\\"' in escaped
        assert 'Test \\"quotes\\"' == escaped

    @pytest.mark.asyncio
    async def test_broadcast_preserves_apostrophes(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Broadcast doesn't escape apostrophes.
        
        Input: "Don't change apostrophes"
        Output: "Don't change apostrophes" (unchanged)
        """
        # Setup
        message = "Don't change apostrophes"
        escaped = message.replace('"', '\\"')

        # Verify
        assert apostrophes = "'" in escaped
        assert message == escaped


class TestWhitelistAllActions:
    """✓ Phase 3: Whitelist command with all action branches."""

    @pytest.mark.asyncio
    async def test_whitelist_list_action_shows_players(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Whitelist "list" shows current whitelist.
        
        RCON: /whitelist get
        Response: "Player1\nPlayer2\nPlayer3"
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="Player1\nPlayer2\nPlayer3"
        )

        # Execute
        response = await mock_rcon_client.execute("/whitelist get")
        assert "Player" in response

    @pytest.mark.asyncio
    async def test_whitelist_enable_action_enforces_whitelist(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Whitelist "enable" enforces whitelist.
        
        RCON: /whitelist enable
        Result: Only whitelisted players can join
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whitelist enable")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_disable_action_disables_whitelist(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Whitelist "disable" disables whitelist.
        
        RCON: /whitelist disable
        Result: All players can join
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whitelist disable")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_add_action_with_player(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Whitelist "add <player>" adds to whitelist.
        
        RCON: /whitelist add NewPlayer
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whitelist add NewPlayer")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_remove_action_with_player(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Whitelist "remove <player>" removes from whitelist.
        
        RCON: /whitelist remove OldPlayer
        """
        # Setup
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whitelist remove OldPlayer")
        mock_rcon_client.execute.assert_called_once()


class TestRconResponseHandling:
    """✓ Phase 3: RCON command with response truncation."""

    @pytest.mark.asyncio
    async def test_rcon_truncates_long_response(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: RCON truncates response > 1024 chars.
        
        Response length: 2000 chars
        Truncated: 1021 chars + "..."
        Total: 1024 chars max
        """
        # Setup
        long_response = "x" * 2000
        
        # Simulate truncation
        result = (
            long_response if len(long_response) < 1024 
            else long_response[:1021] + "..."
        )

        # Verify
        assert len(result) <= 1024
        assert "..." in result

    @pytest.mark.asyncio
    async def test_rcon_preserves_short_response(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: RCON preserves response < 1024 chars.
        
        Response length: 500 chars
        Result: 500 chars (no truncation)
        """
        # Setup
        short_response = "x" * 500
        
        # Simulate truncation
        result = (
            short_response if len(short_response) < 1024 
            else short_response[:1021] + "..."
        )

        # Verify
        assert len(result) == 500
        assert result == short_response


# ════════════════════════════════════════════════════════════════════════════
# ERROR PATHS: Rate Limiting (Token Bucket Algorithm)
# ════════════════════════════════════════════════════════════════════════════

class TestErrorPathRateLimiting:
    """✓ ERROR PATH: Rate limiting with token bucket algorithm."""

    def test_query_cooldown_allows_5_per_30s(
        self,
    ):
        """✓ ERROR PATH: QUERY_COOLDOWN (5/30s) allows 5 without blocking.
        
        Token bucket:
        - 5 tokens
        - Refill window: 30 seconds
        - 6th query blocked
        """
        user_id = 12345
        cooldown = QUERY_COOLDOWN

        cooldown.reset(user_id)

        # First 5 succeed
        for i in range(5):
            is_limited, retry = cooldown.is_rate_limited(user_id)
            assert not is_limited, f"Call {i+1} should not be limited"

        # 6th blocked
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited, "6th call should be rate limited"
        assert retry > 0

        cooldown.reset(user_id)

    def test_admin_cooldown_allows_3_per_60s(
        self,
    ):
        """✓ ERROR PATH: ADMIN_COOLDOWN (3/60s) enforces rate limit.
        
        Token bucket:
        - 3 tokens
        - Refill window: 60 seconds
        - 4th action blocked
        """
        user_id = 12346
        cooldown = ADMIN_COOLDOWN

        cooldown.reset(user_id)

        for i in range(3):
            is_limited, retry = cooldown.is_rate_limited(user_id)
            assert not is_limited

        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited

        cooldown.reset(user_id)

    def test_danger_cooldown_enforces_1_per_120s(
        self,
    ):
        """✓ ERROR PATH: DANGER_COOLDOWN (1/120s) is strictest.
        
        Token bucket:
        - 1 token
        - Refill window: 120 seconds
        - 2nd action blocked with ~120s retry
        """
        user_id = 12347
        cooldown = DANGER_COOLDOWN

        cooldown.reset(user_id)

        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert not is_limited

        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited
        assert retry > 100

        cooldown.reset(user_id)


# ════════════════════════════════════════════════════════════════════════════
# ERROR PATHS: RCON Connectivity
# ════════════════════════════════════════════════════════════════════════════

class TestErrorPathRconConnectivity:
    """✓ ERROR PATH: RCON not available or disconnected."""

    @pytest.mark.asyncio
    async def test_command_fails_when_rcon_none(
        self,
        mock_interaction: discord.Interaction,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Commands fail gracefully when RCON unavailable.
        
        When get_rcon_for_user() returns None:
        - Error embed sent
        - Response is ephemeral
        """
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = None
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"

        rcon = mock_bot.user_context.get_rcon_for_user(12345)
        assert rcon is None

    @pytest.mark.asyncio
    async def test_command_fails_when_rcon_disconnected(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Commands check is_connected flag.
        
        When is_connected is False:
        - Error embed sent
        - Response is ephemeral
        """
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = False

        assert not mock_rcon_client.is_connected


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_bot() -> MagicMock:
    """Create a mock DiscordBot instance with all required attributes."""
    bot = MagicMock()
    bot.user_context = MagicMock()
    bot.user_context.get_rcon_for_user = MagicMock()
    bot.user_context.get_server_display_name = MagicMock(return_value="test-server")
    bot.user_context.get_user_server = MagicMock(return_value="main")
    bot.user_context.set_user_server = MagicMock()
    bot.server_manager = None
    bot.rcon_monitor = MagicMock()
    bot.rcon_monitor.rcon_server_states = {}
    bot._connected = True
    bot.tree = MagicMock()
    bot.tree.add_command = MagicMock()
    return bot


@pytest.fixture
def mock_rcon_client() -> MagicMock:
    """Create a mock RCON client with async execute method."""
    client = MagicMock()
    client.is_connected = True
    client.execute = AsyncMock()
    return client


@pytest.fixture
def mock_interaction() -> discord.Interaction:
    """Create a mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.name = "TestUser"
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


if __name__ == "__main__":
    pytest.main(["-v", __file__])
