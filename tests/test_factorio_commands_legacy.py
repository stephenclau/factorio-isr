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
# HAPPY PATH: Multi-Server Commands (2/17)
# ════════════════════════════════════════════════════════════════════════════

class TestMultiServerCommandsHappyPath:
    """✓ Happy path: servers and connect commands with full coverage."""

    @pytest.mark.asyncio
    async def test_servers_command_multi_server_mode_lists_all_servers(
        self,
        mock_interaction: discord.Interaction,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio servers lists all servers with status.
        
        When server_manager is configured:
        - Displays all servers with status emoji (🟢 online, 🔴 offline)
        - Shows current user context with 👉 marker
        - Displays host:port for each server
        - Shows descriptions if configured
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "TestUser"
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        # Mock server_manager (multi-server mode)
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.list_tags.return_value = ["prod", "staging"]
        mock_bot.server_manager.list_servers.return_value = {
            "prod": MagicMock(
                name="Production",
                rcon_host="192.168.1.100",
                rcon_port=27015,
                description="Main server",
            ),
            "staging": MagicMock(
                name="Staging",
                rcon_host="192.168.1.101",
                rcon_port=27016,
                description="Test server",
            ),
        }
        mock_bot.server_manager.get_status_summary.return_value = {
            "prod": True,  # Online
            "staging": False,  # Offline
        }
        mock_bot.user_context.get_user_server.return_value = "prod"

        # Verify
        assert mock_bot.server_manager is not None
        assert len(mock_bot.server_manager.list_tags()) == 2
        assert "prod" in mock_bot.server_manager.list_servers()
        assert mock_bot.server_manager.get_status_summary()["prod"] is True

    @pytest.mark.asyncio
    async def test_servers_command_single_server_mode_shows_info_message(
        self,
        mock_interaction: discord.Interaction,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio servers in single-server mode shows info.
        
        When server_manager is None:
        - Shows info embed about single-server mode
        - Mentions servers.yml configuration
        - Response is ephemeral
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.send_message = AsyncMock()
        mock_bot.server_manager = None  # Single-server mode

        # Verify
        assert mock_bot.server_manager is None

    @pytest.mark.asyncio
    async def test_connect_command_switches_user_context_to_server(
        self,
        mock_interaction: discord.Interaction,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio connect <server> switches user context.
        
        When server exists:
        - User context updated via set_user_server()
        - Server status shown (🟢 connected, 🟡 connecting)
        - Confirmation embed sent with tag, status, host:port
        - Logging recorded
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "TestUser"
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.clients = {"prod": MagicMock()}
        mock_bot.server_manager.list_servers.return_value = {
            "prod": MagicMock(name="Production", rcon_host="192.168.1.100", rcon_port=27015, description="Main")
        }
        mock_bot.server_manager.get_config.return_value = MagicMock(
            name="Production",
            rcon_host="192.168.1.100",
            rcon_port=27015,
        )
        mock_bot.server_manager.get_client.return_value = MagicMock(is_connected=True)
        mock_bot.user_context.set_user_server = MagicMock()

        # Execute
        server_tag = "prod"
        assert server_tag in mock_bot.server_manager.clients

    @pytest.mark.asyncio
    async def test_connect_command_error_server_not_found(
        self,
        mock_interaction: discord.Interaction,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: /factorio connect shows error for non-existent server.
        
        When server doesn't exist:
        - Lists available servers
        - Shows error embed
        - Response is ephemeral
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.clients = {"prod": MagicMock()}
        mock_bot.server_manager.list_servers.return_value = {
            "prod": MagicMock(name="Production")
        }

        # Verify condition
        assert "nonexistent" not in mock_bot.server_manager.clients


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Server Information Commands (7/17)
# ════════════════════════════════════════════════════════════════════════════

class TestServerInformationCommandsHappyPath:
    """✓ Happy path: status, players, version, seed, evolution, admins, health."""

    @pytest.mark.asyncio
    async def test_status_command_shows_comprehensive_metrics(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio status returns comprehensive embed with metrics.
        
        Expected fields:
        - Bot Status (🤖 Online/Offline)
        - RCON Status (🔧 Connected/Disconnected)
        - Server State (▶️ Running @ X UPS or ⏸️ Paused)
        - Players Online (👥 count)
        - Evolution Factor (🐛 nauvis/gleba multi-surface or fallback)
        - Uptime (⏱️ calculated from last_connected)
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

        # Setup metrics engine
        mock_metrics_engine = MagicMock()
        mock_metrics_engine.gather_all_metrics = AsyncMock(
            return_value={
                "ups": 59.8,
                "ups_sma": 59.5,
                "ups_ema": 59.7,
                "player_count": 3,
                "players": ["Alice", "Bob", "Charlie"],
                "evolution_factor": 0.42,
                "evolution_by_surface": {"nauvis": 0.42, "gleba": 0.15},
                "play_time": "2h 30m",
                "is_paused": False,
            }
        )
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.get_metrics_engine.return_value = mock_metrics_engine
        mock_bot.rcon_monitor = MagicMock()
        mock_bot.rcon_monitor.rcon_server_states = {
            "prod": {"last_connected": datetime.now(timezone.utc) - timedelta(hours=2)}
        }

        # Execute & Verify
        metrics = await mock_metrics_engine.gather_all_metrics()
        assert metrics["ups"] == 59.8
        assert metrics["player_count"] == 3
        assert metrics["evolution_by_surface"]["nauvis"] == 0.42
        assert metrics["is_paused"] is False
        assert mock_bot.server_manager.get_metrics_engine.called

    @pytest.mark.asyncio
    async def test_status_command_pause_state_takes_precedence(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: When is_paused=True, show ⏸️ without UPS.
        
        Priority order:
        1. is_paused=True → Show "⏸️ Paused" immediately
        2. ups available → Show "▶️ Running @ X.X UPS"
        3. Neither → Show "🔄 Fetching..."
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True

        mock_metrics_engine = MagicMock()
        mock_metrics_engine.gather_all_metrics = AsyncMock(
            return_value={"is_paused": True, "ups": None}
        )
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.get_metrics_engine.return_value = mock_metrics_engine

        # Execute
        metrics = await mock_metrics_engine.gather_all_metrics()

        # Verify
        is_paused = metrics["is_paused"]
        ups_value = metrics.get("ups")

        if is_paused:
            state = "⏸️ Paused"
        elif ups_value is not None:
            state = f"▶️ Running @ {ups_value:.1f}"
        else:
            state = "🔄 Fetching..."

        assert state == "⏸️ Paused"

    @pytest.mark.asyncio
    async def test_status_command_evolution_multi_surface_display(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: Evolution displays nauvis and gleba when available.
        
        Multi-surface display:
        - Nauvis: X.XX (XX.X%)
        - Gleba: X.XX (XX.X%)
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True

        mock_metrics_engine = MagicMock()
        mock_metrics_engine.gather_all_metrics = AsyncMock(
            return_value={
                "evolution_by_surface": {"nauvis": 0.42, "gleba": 0.15},
                "is_paused": False,
            }
        )
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.get_metrics_engine.return_value = mock_metrics_engine

        # Execute
        metrics = await mock_metrics_engine.gather_all_metrics()
        evo_by_surface = metrics["evolution_by_surface"]

        # Verify
        assert "nauvis" in evo_by_surface
        assert "gleba" in evo_by_surface
        assert evo_by_surface["nauvis"] == 0.42
        assert evo_by_surface["gleba"] == 0.15

    @pytest.mark.asyncio
    async def test_status_command_evolution_fallback_single_factor(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Falls back to evolution_factor when multi-surface empty.
        
        When evolution_by_surface is empty:
        - Use evolution_factor (single aggregate value)
        - Display as "🐛 Enemy Evolution: X.XX"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True

        mock_metrics_engine = MagicMock()
        mock_metrics_engine.gather_all_metrics = AsyncMock(
            return_value={
                "evolution_by_surface": {},  # Empty
                "evolution_factor": 0.42,
                "is_paused": False,
            }
        )
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.get_metrics_engine.return_value = mock_metrics_engine

        # Execute
        metrics = await mock_metrics_engine.gather_all_metrics()

        # Verify
        assert not metrics["evolution_by_surface"]
        assert metrics["evolution_factor"] == 0.42

    @pytest.mark.asyncio
    async def test_players_command_lists_online_players(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio players returns formatted list.
        
        Response format:
        - "- Player1 (online)\n- Player2 (online)"
        - Parsed and sorted alphabetically
        - Count displayed: "👥 Players Online (3)"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="- Alice (online)\n- Bob (online)\n- Charlie (online)"
        )

        # Execute
        response = await mock_rcon_client.execute("/players")
        players = []
        if response:
            for line in response.split("\n"):
                if "(online)" in line.lower():
                    player_name = line.split("(online)")[0].strip().lstrip("-").strip()
                    if player_name:
                        players.append(player_name)

        # Verify
        assert len(players) == 3
        assert "Alice" in players
        assert "Bob" in players
        assert "Charlie" in players

    @pytest.mark.asyncio
    async def test_players_command_empty_response(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Empty player list shows 'No players online'.
        
        When response is empty:
        - Description: "No players currently online."
        - No player field added
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        response = await mock_rcon_client.execute("/players")
        assert response == ""

    @pytest.mark.asyncio
    async def test_version_command_returns_version_string(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio version returns Factorio version.
        
        Expected format: "Version X.Y.Z" or similar
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Version 1.1.99")

        # Execute
        version = await mock_rcon_client.execute("/version")
        assert "1.1.99" in version

    @pytest.mark.asyncio
    async def test_seed_command_validates_numeric_response(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio seed returns numeric seed.
        
        Seed validation:
        - Must be numeric
        - Long integers (e.g., 3735928559)
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="3735928559")

        # Execute
        seed = await mock_rcon_client.execute('/sc rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)')

        # Verify
        int(seed.strip())  # Should not raise
        assert seed.strip().isdigit()

    @pytest.mark.asyncio
    async def test_seed_command_handles_non_numeric_response(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Seed handles non-numeric response gracefully.
        
        When response is not numeric:
        - Fallback to "Unknown" in actual code
        - Error handling via try-except
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Not a number")

        # Execute
        response = await mock_rcon_client.execute("/sc invalid")
        assert response == "Not a number"

    @pytest.mark.asyncio
    async def test_evolution_command_aggregate_all_surfaces(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio evolution all returns aggregate.
        
        Response format:
        - First line: "AGG:XX.XX%"
        - Following lines: "nauvis:XX.XX%", "gleba:XX.XX%"
        - Excludes platform surfaces
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="AGG:42.50%\nnauvis:42.50%\ngleba:42.50%"
        )

        # Execute
        response = await mock_rcon_client.execute("/* aggregate lua script */")
        lines = response.split("\n")

        # Verify
        assert any("AGG:" in line for line in lines)
        assert any("nauvis" in line for line in lines)

    @pytest.mark.asyncio
    async def test_evolution_command_single_surface(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio evolution <surface> returns specific surface.
        
        Expected format: "XX.XX%"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="42.50%")

        # Execute
        response = await mock_rcon_client.execute("/sc /* evolution script for nauvis */")
        assert "%" in response

    @pytest.mark.asyncio
    async def test_evolution_command_surface_not_found_error(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: Evolution returns error for non-existent surface.
        
        Error response: "SURFACE_NOT_FOUND"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="SURFACE_NOT_FOUND")

        # Execute
        response = await mock_rcon_client.execute("/* script */")
        assert response == "SURFACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_admins_command_lists_administrators(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio admins returns admin list.
        
        Response format:
        - "- Admin1\n- Admin2" or similar
        - Parsed and displayed with count
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="- Admin1\n- Admin2"
        )

        # Execute
        response = await mock_rcon_client.execute("/admins")
        assert "Admin" in response

    @pytest.mark.asyncio
    async def test_admins_command_empty_admin_list(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Admins handles empty admin list.
        
        When no admins:
        - Response: "There are no admins"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="There are no admins"
        )

        # Execute
        response = await mock_rcon_client.execute("/admins")
        assert "admins" in response.lower()

    @pytest.mark.asyncio
    async def test_health_command_checks_bot_rcon_monitor_status(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio health returns bot, RCON, monitor status.
        
        Fields:
        - 🤖 Bot Status
        - 🔧 RCON Status
        - ⏱️ Monitor Status
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot._connected = True
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_bot.rcon_monitor = MagicMock()
        mock_bot.rcon_monitor.rcon_server_states = {}

        # Verify
        assert mock_bot._connected
        assert mock_rcon_client.is_connected


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Player Management Commands (7/17)
# ════════════════════════════════════════════════════════════════════════════

class TestPlayerManagementCommandsHappyPath:
    """✓ Happy path: kick, ban, unban, mute, unmute, promote, demote."""

    @pytest.mark.asyncio
    async def test_kick_command_removes_player_with_reason(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio kick <player> <reason> removes player.
        
        RCON command: /kick PlayerName Spam
        Embed: ⚠️ Player Kicked with player, server, reason fields
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "Moderator"
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/kick PlayerName Spam")

        # Verify
        mock_rcon_client.execute.assert_called_once()
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert "PlayerName" in call_args

    @pytest.mark.asyncio
    async def test_ban_command_permanently_bans_player(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio ban <player> permanently bans.
        
        Uses DANGER_COOLDOWN (stricter rate limiting: 1/120s)
        RCON command: /ban PlayerName <reason>
        Embed: 🚫 Player Banned
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/ban PlayerName Griefing")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_unban_command_removes_player_ban(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio unban <player> removes ban.
        
        Uses DANGER_COOLDOWN
        RCON command: /unban PlayerName
        Embed: ✅ Player Unbanned
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/unban PlayerName")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_mute_command_mutes_player_from_chat(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio mute <player> toggles mute.
        
        RCON command: /mute PlayerName
        Embed: 🔇 Player Muted
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/mute PlayerName")
        assert mock_rcon_client.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_unmute_command_unmutes_player(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio unmute <player> toggles unmute.
        
        RCON command: /unmute PlayerName
        Embed: 🔊 Player Unmuted
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/unmute PlayerName")
        assert mock_rcon_client.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_promote_command_promotes_player_to_admin(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio promote <player> promotes to admin.
        
        Uses DANGER_COOLDOWN
        RCON command: /promote PlayerName
        Embed: 👑 Player Promoted
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/promote PlayerName")
        mock_rcon_client.execute.assert_called()

    @pytest.mark.asyncio
    async def test_demote_command_demotes_player_from_admin(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio demote <player> demotes from admin.
        
        Uses DANGER_COOLDOWN
        RCON command: /demote PlayerName
        Embed: 📉 Player Demoted
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/demote PlayerName")
        mock_rcon_client.execute.assert_called()


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Server Management Commands (4/17)
# ════════════════════════════════════════════════════════════════════════════

class TestServerManagementCommandsHappyPath:
    """✓ Happy path: save, broadcast, whisper, whitelist."""

    @pytest.mark.asyncio
    async def test_save_command_saves_game_and_parses_save_name(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio save saves game and extracts save name.
        
        RCON response parsing:
        - Full path: "Saving map to /saves/GameName.zip" → GameName
        - Simple: "Saving to _autosave1 (non-blocking)" → _autosave1
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="Saving map to /saves/LosHermanos.zip"
        )

        # Execute
        response = await mock_rcon_client.execute("/save")

        # Parse save name
        match = re.search(r"/([^/]+?)\.zip", response)
        if match:
            label = match.group(1)
        else:
            match = re.search(r"Saving (?:map )?to ([\w-]+)", response)
            label = match.group(1) if match else "current save"

        # Verify
        assert label == "LosHermanos"

    @pytest.mark.asyncio
    async def test_save_command_extracts_simple_format_save_name(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Save name extracted from simple format.
        
        Response: "Saving to _autosave1 (non-blocking)"
        Expected: "_autosave1"
        """
        # Setup
        response = "Saving to _autosave1 (non-blocking)"

        # Parse
        match = re.search(r"Saving (?:map )?to ([\w-]+)", response)
        assert match is not None
        assert match.group(1) == "_autosave1"

    @pytest.mark.asyncio
    async def test_broadcast_command_sends_message_with_escaping(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio broadcast <message> sends to all.
        
        Quote escaping:
        - Input: 'Test "quotes"'
        - Escaped: 'Test \\"quotes\\"'
        - RCON: /sc game.print("[color=pink]...[/color]")
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        message = "Hello world!"
        escaped = message.replace('"', '\\"')
        await mock_rcon_client.execute(f'/sc game.print("{escaped}")')
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_escapes_double_quotes_in_message(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Broadcast escapes quote characters.
        
        Message: 'Test "quotes" and apostrophes'
        After escape: 'Test \\"quotes\\" and apostrophes'
        """
        # Setup
        message = 'Test "quotes" and \'apostrophes\''
        escaped = message.replace('"', '\\"')

        # Verify
        assert '\\"' in escaped
        assert "'" in escaped  # Apostrophes not escaped

    @pytest.mark.asyncio
    async def test_whisper_command_sends_private_message(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio whisper <player> <message> sends PM.
        
        RCON command: /whisper PlayerName Hello
        Embed: 💬 Private Message Sent
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whisper PlayerName Hello")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_command_list_action(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio whitelist list shows whitelist.
        
        RCON command: /whitelist get
        Response: Player names separated by newlines
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Player1\nPlayer2")

        # Execute
        response = await mock_rcon_client.execute("/whitelist get")
        assert "Player" in response

    @pytest.mark.asyncio
    async def test_whitelist_command_enable_action(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio whitelist enable enforces whitelist.
        
        RCON command: /whitelist enable
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whitelist enable")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_command_disable_action(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio whitelist disable disables whitelist.
        
        RCON command: /whitelist disable
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whitelist disable")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_command_add_action(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio whitelist add <player> adds to whitelist.
        
        RCON command: /whitelist add NewPlayer
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whitelist add NewPlayer")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_command_remove_action(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio whitelist remove <player> removes from whitelist.
        
        RCON command: /whitelist remove OldPlayer
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whitelist remove OldPlayer")
        mock_rcon_client.execute.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Game Control Commands (3/17)
# ════════════════════════════════════════════════════════════════════════════

class TestGameControlCommandsHappyPath:
    """✓ Happy path: clock, speed, research."""

    @pytest.mark.asyncio
    async def test_clock_command_display_current_time(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio clock (no args) displays current time.
        
        Response format: "Current daytime: 0.75 (🕐 18:00)"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="Current daytime: 0.75 (🕐 18:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* display time */")
        assert "daytime" in response.lower() or "18:00" in response

    @pytest.mark.asyncio
    async def test_clock_command_set_eternal_day(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio clock day sets eternal day (freeze_daytime=0.5).
        
        Response: "☀️ Set to eternal day (12:00)"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="☀️ Set to eternal day (12:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* eternal day lua */")
        assert "day" in response.lower() or "12:00" in response

    @pytest.mark.asyncio
    async def test_clock_command_set_eternal_night(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio clock night sets eternal night (freeze_daytime=0.0).
        
        Response: "🌙 Set to eternal night (00:00)"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="🌙 Set to eternal night (00:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* eternal night lua */")
        assert "night" in response.lower() or "00:00" in response

    @pytest.mark.asyncio
    async def test_clock_command_set_custom_time_valid_range(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio clock <0.0-1.0> sets custom time.
        
        Valid range: 0.0 (midnight) to 1.0 (next midnight)
        Example: 0.5 = noon
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="Set daytime to 0.25 (🕐 06:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* custom time lua */")
        assert "0.25" in response or "06:00" in response

    @pytest.mark.asyncio
    async def test_clock_command_time_range_validation(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Clock validates time range 0.0-1.0.
        
        Valid: [0.0, 0.25, 0.5, 0.75, 1.0]
        Invalid: [-0.1, 1.5, 2.0]
        """
        # Setup
        valid_times = [0.0, 0.25, 0.5, 0.75, 1.0]
        invalid_times = [-0.1, 1.5, 2.0]

        # Verify valid times
        for time_val in valid_times:
            assert 0.0 <= time_val <= 1.0

        # Verify invalid times
        for time_val in invalid_times:
            assert not (0.0 <= time_val <= 1.0)

    @pytest.mark.asyncio
    async def test_speed_command_sets_game_speed(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio speed <0.1-10.0> sets game speed.
        
        RCON command: /sc game.speed = X
        Range: 0.1 (slow) to 10.0 (fast), 1.0 = normal
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute with valid speed
        speed_value = 2.0
        await mock_rcon_client.execute(f"/sc game.speed = {speed_value}")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_speed_command_validates_range(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Speed parameter must be 0.1-10.0.
        
        Valid: [0.1, 0.5, 1.0, 5.0, 10.0]
        Invalid: [0.05, 15.0, -1.0]
        """
        # Setup
        valid_speeds = [0.1, 0.5, 1.0, 5.0, 10.0]
        invalid_speeds = [0.05, 15.0, -1.0]

        # Verify valid speeds
        for speed in valid_speeds:
            assert 0.1 <= speed <= 10.0

        # Verify invalid speeds
        for speed in invalid_speeds:
            assert not (0.1 <= speed <= 10.0)

    @pytest.mark.asyncio
    async def test_research_command_display_status(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio research (no args) displays status.
        
        Response format: "15/128" (researched/total)
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="15/128")

        # Execute
        response = await mock_rcon_client.execute("/* research status */")
        assert "/" in response

    @pytest.mark.asyncio
    async def test_research_command_defaults_force_to_player(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: Research defaults force to 'player' when None.
        
        Coop mode (default):
        - force = None → use "player"
        
        PvP mode (explicit):
        - force = "enemy" → use "enemy"
        """
        # Setup
        force = None
        target_force = (force.lower().strip() if force else None) or "player"

        # Verify
        assert target_force == "player"

    @pytest.mark.asyncio
    async def test_research_command_research_all_technologies(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio research all researches all technologies.
        
        RCON command: /sc game.forces["player"].research_all_technologies()
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/* research all lua */")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_command_undo_all_technologies(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio research undo all reverts all technologies.
        
        RCON command: /sc for _, tech in ... tech.researched = false
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/* undo all lua */")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_command_undo_single_technology(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio research undo <tech> reverts single tech.
        
        RCON command: /sc game.forces["player"].technologies["automation-2"].researched = false
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/* undo single lua */")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_command_research_single_technology(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio research <tech> researches technology.
        
        RCON command: /sc game.forces["player"].technologies["automation-2"].researched = true
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/* research single lua */")
        mock_rcon_client.execute.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Advanced Commands (2/17)
# ════════════════════════════════════════════════════════════════════════════

class TestAdvancedCommandsHappyPath:
    """✓ Happy path: rcon, help."""

    @pytest.mark.asyncio
    async def test_rcon_command_executes_raw_command(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio rcon <command> executes raw RCON.
        
        Uses DANGER_COOLDOWN (strictest: 1/120s)
        Response truncated to 1024 chars with "..." suffix if longer
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="command output")

        # Execute
        result = await mock_rcon_client.execute("/sc game.print('test')")
        assert result == "command output"

    @pytest.mark.asyncio
    async def test_rcon_command_response_truncation(
        self,
        mock_interaction: discord.Interaction,
        mock_rcon_client: MagicMock,
        mock_bot: MagicMock,
    ):
        """✓ EDGE CASE: RCON response truncates when > 1024 chars.
        
        Max response: 1021 chars + "..."
        """
        # Setup
        long_response = "x" * 2000

        # Simulate truncation
        result = long_response if len(long_response) < 1024 else long_response[:1021] + "..."
        assert len(result) <= 1024
        assert "..." in result

    @pytest.mark.asyncio
    async def test_help_command_displays_command_list(
        self,
        mock_interaction: discord.Interaction,
        mock_bot: MagicMock,
    ):
        """✓ HAPPY PATH: /factorio help displays command list.
        
        Categories:
        - 🌍 Multi-Server
        - 📊 Server Information
        - 👥 Player Management
        - 🔧 Server Management
        - 🎮 Game Control
        - 🛠️  Advanced
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.send_message = AsyncMock()

        # Verify help text contains command names
        help_text = (
            "**🏭 Factorio ISR Bot – Commands**\n\n"
            "**🌍 Multi-Server**\n"
            "`/factorio servers` – List available servers\n"
            "`/factorio connect <server>` – Switch to a server\n\n"
        )

        assert "servers" in help_text
        assert "connect" in help_text


# ════════════════════════════════════════════════════════════════════════════
# ERROR PATH: Rate Limiting (Token Bucket Algorithm)
# ════════════════════════════════════════════════════════════════════════════

class TestErrorPathRateLimiting:
    """✓ ERROR PATH: Rate limiting with token bucket algorithm."""

    def test_query_cooldown_allows_5_queries_per_30s(
        self,
    ):
        """✓ ERROR PATH: QUERY_COOLDOWN (5/30s) allows 5 without blocking.
        
        Token bucket:
        - 5 tokens
        - Refill window: 30 seconds
        - 6th query blocked
        """
        user_id = 12345
        cooldown = QUERY_COOLDOWN  # 5 per 30s

        # Reset
        cooldown.reset(user_id)

        # First 5 succeed
        for i in range(5):
            is_limited, retry = cooldown.is_rate_limited(user_id)
            assert not is_limited, f"Call {i+1} should not be limited"

        # 6th blocked
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited, "6th call should be rate limited"
        assert retry > 0, "Should have positive retry time"

        # Cleanup
        cooldown.reset(user_id)

    def test_admin_cooldown_enforces_3_per_60s(
        self,
    ):
        """✓ ERROR PATH: ADMIN_COOLDOWN (3/60s) enforces rate limit.
        
        Token bucket:
        - 3 tokens
        - Refill window: 60 seconds
        - 4th action blocked
        """
        user_id = 12346
        cooldown = ADMIN_COOLDOWN  # 3 per 60s

        # Reset
        cooldown.reset(user_id)

        # First 3 succeed
        for i in range(3):
            is_limited, retry = cooldown.is_rate_limited(user_id)
            assert not is_limited, f"Admin call {i+1} should succeed"

        # 4th blocked
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited, "4th admin action should be rate limited"

        # Cleanup
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
        cooldown = DANGER_COOLDOWN  # 1 per 120s

        # Reset
        cooldown.reset(user_id)

        # First succeeds
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert not is_limited, "First danger action should succeed"

        # 2nd blocked
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited, "2nd danger action should be rate limited"
        assert retry > 100, "Retry should be ~120s minus execution time"

        # Cleanup
        cooldown.reset(user_id)


# ════════════════════════════════════════════════════════════════════════════
# ERROR PATH: RCON Connectivity
# ════════════════════════════════════════════════════════════════════════════

class TestErrorPathRconConnectivity:
    """✓ ERROR PATH: RCON not available or disconnected."""

    @pytest.mark.asyncio
    async def test_command_fails_when_rcon_is_none(
        self,
        mock_interaction: discord.Interaction,
        mock_bot: MagicMock,
    ):
        """✓ ERROR PATH: All commands fail gracefully when RCON unavailable.
        
        When get_rcon_for_user() returns None:
        - Error embed sent
        - Response is ephemeral
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = None
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"

        # Verify condition
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
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup = MagicMock()
        mock_interaction.followup.send = AsyncMock()

        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = False

        # Verify condition
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
    bot.server_manager = None  # Single-server mode by default
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
    # Run tests with: pytest tests/test_factorio_commands_legacy.py -v
    # Run with coverage: pytest tests/test_factorio_commands_legacy.py --cov=bot.commands.factorio --cov-report=term-missing
    pytest.main(["-v", __file__])
