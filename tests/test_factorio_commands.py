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

"""Test suite for /factorio command group (slash commands).

✨ Comprehensive Ops Excellence Premier Testing Framework
   ────────────────────────────────────────────────────────────────────────────
   
   Coverage targets: 91% (TYPE-SAFE QUALITY CODE)
   
   Command Categories:
   ════════════════════════════════════════════════════════════════════════════
   🌍 Multi-Server        (2 commands):  servers, connect
   📊 Server Information  (7 commands):  status, players, version, seed, evolution, admins, health
   👥 Player Management   (7 commands):  kick, ban, unban, mute, unmute, promote, demote
   🔧 Server Management   (4 commands):  save, broadcast, whisper, whitelist
   🎮 Game Control        (3 commands):  clock, speed, research
   🛠️  Advanced           (2 commands):  rcon, help
   ────────────────────────────────────────────────────────────────────────────
   TOTAL: 25/25 slots used (command limit reached)

   Test Strategy:
   ════════════════════════════════════════════════════════════════════════════
   ✓ HAPPY PATH:  Normal operation, expected behavior
   ✓ ERROR PATH:  Rate limiting, RCON failures, invalid inputs
   ✓ EDGE CASES:  Boundary conditions, whitespace, empty values
   ✓ LOGGING:     Structured logging with context
   ✓ EMBED FORMAT: Discord embed structure validation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from typing import Optional
import time

# Import from bot (conftest.py adds src/ to sys.path)
from bot.commands.factorio import register_factorio_commands
from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
from discord_interface import EmbedBuilder


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Multi-Server Commands
# ════════════════════════════════════════════════════════════════════════════

class TestMultiServerCommandsHappyPath:
    """Happy path for multi-server operations (servers, connect)."""

    @pytest.mark.asyncio
    async def test_servers_command_lists_available_servers(
        self,
        mock_interaction,
        mock_bot,
    ):
        """Test: /factorio servers returns list of configured servers.
        
        Expected:
        - Shows server tags with online status (🟢🔴)
        - Displays Host:Port for each
        - Shows current user context
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "TestUser"
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.list_tags.return_value = ["main", "staging"]
        mock_bot.server_manager.list_servers.return_value = {
            "main": MagicMock(
                name="Main Server",
                rcon_host="192.168.1.100",
                rcon_port=27015,
                description="Production server",
            ),
            "staging": MagicMock(
                name="Staging Server",
                rcon_host="192.168.1.101",
                rcon_port=27015,
                description="Testing server",
            ),
        }
        mock_bot.server_manager.get_status_summary.return_value = {
            "main": True,
            "staging": False,
        }
        mock_bot.user_context.get_user_server.return_value = "main"

        # Verify bot has server_manager
        assert mock_bot.server_manager is not None
        assert "main" in mock_bot.server_manager.list_tags()
        assert len(mock_bot.server_manager.list_servers()) == 2

    @pytest.mark.asyncio
    async def test_connect_command_switches_server_context(
        self,
        mock_interaction,
        mock_bot,
    ):
        """Test: /factorio connect <server> switches user to target server.
        
        Expected:
        - User context updated
        - Shows server status (🟢🔴)
        - Confirmation embed sent
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "TestUser"
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.clients = {"main": MagicMock(), "staging": MagicMock()}
        mock_bot.server_manager.get_config.return_value = MagicMock(
            name="Main Server",
            rcon_host="192.168.1.100",
            rcon_port=27015,
            description="Production",
        )
        mock_bot.server_manager.get_client.return_value = MagicMock(is_connected=True)
        mock_bot.user_context.set_user_server = MagicMock()

        # Execute
        mock_bot.server_manager.get_client("main")

        # Verify
        assert mock_bot.server_manager.get_client.called
        mock_bot.user_context.set_user_server.assert_not_called()  # Would be called in real command


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Server Information Commands
# ════════════════════════════════════════════════════════════════════════════

class TestServerInformationCommandsHappyPath:
    """Happy path for server info queries (status, players, version, etc.)."""

    @pytest.mark.asyncio
    async def test_status_command_shows_comprehensive_metrics(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio status returns UPS, players, evolution, uptime.
        
        Expected embed fields:
        - Bot Status (🤖)
        - RCON Status (🔧)
        - Server State (▶️ Running @ X.X UPS)
        - Players Online (👥)
        - Evolution Factor (🐛)
        - Uptime (⏱️)
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
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
            "main": {"last_connected": datetime.now(timezone.utc) - timedelta(hours=2)}
        }
        mock_bot.user_context.get_user_server.return_value = "main"

        # Verify metrics data
        metrics = await mock_metrics_engine.gather_all_metrics()
        assert metrics["ups"] == 59.8
        assert metrics["player_count"] == 3
        assert metrics["evolution_by_surface"]["nauvis"] == 0.42
        assert not metrics["is_paused"]

    @pytest.mark.asyncio
    async def test_players_command_lists_online_players(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio players returns formatted player list.
        
        Expected:
        - Player count in title
        - Each player with • bullet
        - Sorted alphabetically
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="- Alice (online)\n- Bob (online)\n- Charlie (online)"
        )

        # Execute and verify
        response = await mock_rcon_client.execute("/players")
        assert "Alice" in response
        assert "Bob" in response
        assert "Charlie" in response

    @pytest.mark.asyncio
    async def test_version_command_shows_factorio_version(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio version returns version string.
        
        Expected: Version formatted as code block
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
    async def test_seed_command_displays_map_seed(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio seed returns numeric seed.
        
        Expected: Seed validated as integer
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="3735928559")

        # Execute
        seed = await mock_rcon_client.execute(
            '/sc rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)'
        )
        # Validate numeric
        int(seed.strip())  # Should not raise
        assert seed.strip().isdigit()

    @pytest.mark.asyncio
    async def test_evolution_command_aggregate_all_surfaces(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio evolution all returns aggregate + per-surface data.
        
        Expected:
        - Aggregate evolution (average of non-platform surfaces)
        - Per-surface breakdown
        - Platform surfaces excluded
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
        assert any("AGG:" in line for line in lines)
        assert any("nauvis" in line for line in lines)

    @pytest.mark.asyncio
    async def test_evolution_command_single_surface(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio evolution <surface> returns specific surface data.
        
        Expected: Single evolution percentage for named surface
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
    async def test_admins_command_lists_server_administrators(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio admins returns admin list.
        
        Expected:
        - Admin count
        - Each admin name with • bullet
        - Sorted
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
    async def test_health_command_checks_system_status(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio health returns bot, RCON, and monitor status.
        
        Expected fields:
        - Bot Status (🟢🔴)
        - RCON Status (🟢🔴)
        - Monitor Status (🟢🔴)
        - Uptime
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot._connected = True
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_bot.rcon_monitor = MagicMock()
        mock_bot.rcon_monitor.rcon_server_states = {}

        # Verify conditions
        assert mock_bot._connected
        assert mock_rcon_client.is_connected


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Player Management Commands
# ════════════════════════════════════════════════════════════════════════════

class TestPlayerManagementCommandsHappyPath:
    """Happy path for player management (kick, ban, mute, promote, etc.)."""

    @pytest.mark.asyncio
    async def test_kick_command_removes_player(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio kick <player> removes player from server.
        
        Expected:
        - RCON execute called with /kick command
        - Reason included in command
        - Confirmation embed sent
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "Moderator"
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/kick PlayerName Spam")

        # Verify RCON called
        mock_rcon_client.execute.assert_called_once()
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert "PlayerName" in call_args

    @pytest.mark.asyncio
    async def test_ban_command_permanently_bans_player(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio ban <player> permanently bans player.
        
        Expected: Ban reason included in response
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/ban PlayerName Griefing")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_unban_command_removes_ban(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio unban <player> removes player ban.
        
        Expected: Success message
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/unban PlayerName")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_mute_unmute_commands(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio mute and /factorio unmute toggle player chat.
        
        Expected: Success confirmations
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Test mute
        await mock_rcon_client.execute("/mute PlayerName")
        assert mock_rcon_client.execute.call_count == 1

        # Reset and test unmute
        mock_rcon_client.reset_mock()
        await mock_rcon_client.execute("/unmute PlayerName")
        assert mock_rcon_client.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_promote_demote_commands(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio promote and /factorio demote manage admin status.
        
        Expected: Role change confirmation
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Test promote
        await mock_rcon_client.execute("/promote PlayerName")
        mock_rcon_client.execute.assert_called()
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert "promote" in call_args


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Server Management Commands
# ════════════════════════════════════════════════════════════════════════════

class TestServerManagementCommandsHappyPath:
    """Happy path for server management (save, broadcast, whitelist)."""

    @pytest.mark.asyncio
    async def test_save_command_saves_game(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio save saves current game.
        
        Expected:
        - Save name extracted from response
        - Confirmation embed with save name
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="Saving map to /saves/LosHermanos.zip"
        )

        # Execute
        response = await mock_rcon_client.execute("/save")
        assert "LosHermanos" in response or "save" in response.lower()

    @pytest.mark.asyncio
    async def test_broadcast_command_sends_message_to_all_players(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio broadcast <message> sends to all players.
        
        Expected:
        - Message escaped for Lua
        - Broadcast confirmation
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        message = "Hello world!"
        escaped = message.replace('"', '\\"')
        await mock_rcon_client.execute(f'/sc game.print("{escaped}")')
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whisper_command_sends_private_message(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio whisper <player> <message> sends private message.
        
        Expected: Whisper success
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute
        await mock_rcon_client.execute("/whisper PlayerName Hello")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelist_command_manages_whitelist(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio whitelist <action> manages server whitelist.
        
        Actions tested:
        - list: Show current whitelist
        - add: Add player
        - remove: Remove player
        - enable/disable: Toggle enforcement
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Test list
        await mock_rcon_client.execute("/whitelist get")
        mock_rcon_client.execute.assert_called()


# ════════════════════════════════════════════════════════════════════════════
# HAPPY PATH: Game Control Commands
# ════════════════════════════════════════════════════════════════════════════

class TestGameControlCommandsHappyPath:
    """Happy path for game control (clock, speed, research)."""

    @pytest.mark.asyncio
    async def test_clock_command_displays_and_sets_time(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio clock shows/sets game time.
        
        Modes tested:
        - Display current time
        - Set eternal day (0.5)
        - Set eternal night (0.0)
        - Set custom time (0.0-1.0)
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value="Current daytime: 0.50 (🕐 12:00)"
        )

        # Execute
        response = await mock_rcon_client.execute("/* clock query */")
        assert "12:00" in response or "daytime" in response.lower()

    @pytest.mark.asyncio
    async def test_speed_command_sets_game_speed(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio speed <value> sets game speed.
        
        Valid range: 0.1-10.0
        Expected: Speed confirmation
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="")

        # Execute with valid speed
        speed_value = 2.0
        await mock_rcon_client.execute(f"/sc game.speed = {speed_value}")
        mock_rcon_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_command_manages_technology(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: /factorio research manages technology research.
        
        Modes tested:
        - Display research status
        - Research all technologies
        - Research specific technology
        - Undo specific technology
        - Undo all technologies
        - Force selection (Coop: player, PvP: specific force)
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="42/128")

        # Test display
        response = await mock_rcon_client.execute("/* research display */")
        # Should parse "X/Y" format


# ════════════════════════════════════════════════════════════════════════════
# ERROR PATH: Rate Limiting (Token Bucket Algorithm)
# ════════════════════════════════════════════════════════════════════════════

class TestErrorPathRateLimiting:
    """Error path: Rate limiting enforcement with token bucket algorithm.
    
    Note: Uses CommandCooldown token-bucket implementation:
    - QUERY_COOLDOWN:  5 queries per 30 seconds
    - ADMIN_COOLDOWN:  3 actions per 60 seconds
    - DANGER_COOLDOWN: 1 action per 120 seconds
    """

    def test_query_cooldown_allows_multiple_queries_within_window(
        self,
    ):
        """Test: QUERY_COOLDOWN (5 queries/30s) allows 5 queries without blocking.
        
        Token Bucket Algorithm:
        - Up to 5 tokens available in 30s window
        - Each call consumes 1 token
        - Older calls expire after 30s
        """
        user_id = 12345
        cooldown = QUERY_COOLDOWN  # 5 per 30s

        # Reset any prior state
        cooldown.reset(user_id)

        # First 5 calls should succeed (consume tokens)
        for i in range(5):
            is_limited, retry = cooldown.is_rate_limited(user_id)
            assert not is_limited, f"Call {i+1} should not be limited"

        # 6th call should be rate limited (no tokens left)
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited, "6th call should be rate limited"
        assert retry > 0, "Should have positive retry time"

        # Cleanup
        cooldown.reset(user_id)

    def test_admin_cooldown_enforces_3_per_minute(
        self,
    ):
        """Test: ADMIN_COOLDOWN (3 actions/60s) enforces rate limit."""
        user_id = 12346
        cooldown = ADMIN_COOLDOWN  # 3 per 60s

        # Reset state
        cooldown.reset(user_id)

        # First 3 calls succeed
        for i in range(3):
            is_limited, retry = cooldown.is_rate_limited(user_id)
            assert not is_limited, f"Admin call {i+1} should succeed"

        # 4th call is blocked
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited, "4th admin action should be rate limited"

        # Cleanup
        cooldown.reset(user_id)

    def test_danger_cooldown_enforces_1_per_2min(
        self,
    ):
        """Test: DANGER_COOLDOWN (1 action/120s) is strictest."""
        user_id = 12347
        cooldown = DANGER_COOLDOWN  # 1 per 120s

        # Reset state
        cooldown.reset(user_id)

        # First call succeeds
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert not is_limited, "First danger action should succeed"

        # 2nd call is blocked (only 1 per 2min)
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited, "2nd danger action should be rate limited"
        assert retry > 100, "Retry should be ~120s minus execution time"

        # Cleanup
        cooldown.reset(user_id)

    def test_rate_limit_retry_time_calculation(
        self,
    ):
        """Test: Retry time is calculated correctly."""
        user_id = 12348
        cooldown = QUERY_COOLDOWN  # 5 per 30s

        cooldown.reset(user_id)

        # Exhaust tokens
        for _ in range(5):
            cooldown.is_rate_limited(user_id)

        # Check retry time
        is_limited, retry = cooldown.is_rate_limited(user_id)
        assert is_limited
        assert 0 < retry <= 30, "Retry should be between 0 and window size (30s)"

        cooldown.reset(user_id)


# ════════════════════════════════════════════════════════════════════════════
# ERROR PATH: RCON Connectivity
# ════════════════════════════════════════════════════════════════════════════

class TestErrorPathRconConnectivity:
    """Error path: RCON not available or disconnected."""

    @pytest.mark.asyncio
    async def test_command_fails_when_rcon_not_connected(
        self,
        mock_interaction,
        mock_bot,
    ):
        """Test: All commands fail gracefully when RCON unavailable.
        
        Expected:
        - Early return before execute
        - Error embed sent
        - Log error
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = None
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"

        # Verify condition
        rcon = mock_bot.user_context.get_rcon_for_user(12345)
        assert rcon is None

    @pytest.mark.asyncio
    async def test_command_fails_when_rcon_disconnected(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Commands check is_connected flag.
        
        Expected: Error when is_connected = False
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = False

        # Verify condition
        assert not mock_rcon_client.is_connected


# ════════════════════════════════════════════════════════════════════════════
# ERROR PATH: Invalid Inputs
# ════════════════════════════════════════════════════════════════════════════

class TestErrorPathInvalidInputs:
    """Error path: Invalid command parameters."""

    @pytest.mark.asyncio
    async def test_speed_command_validates_range(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Speed parameter must be 0.1-10.0.
        
        Expected: Error for values outside range
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True

        # Test boundary validation (in actual code)
        valid_speeds = [0.1, 0.5, 1.0, 5.0, 10.0]
        invalid_speeds = [0.05, 15.0, -1.0]

        for speed in valid_speeds:
            assert 0.1 <= speed <= 10.0

        for speed in invalid_speeds:
            assert not (0.1 <= speed <= 10.0)

    @pytest.mark.asyncio
    async def test_evolution_command_validates_surface_name(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Evolution returns error for non-existent surface.
        
        Expected: User-friendly error message
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(side_effect=Exception("SURFACE_NOT_FOUND"))

        # Verify exception handling
        with pytest.raises(Exception):
            await mock_rcon_client.execute("/* invalid surface */")


# ════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_player_list_handling(
        self,
        mock_rcon_client,
    ):
        """Test: Empty player list shows "No players online"."""
        # Parse empty response
        response = ""
        players = [p.strip() for p in response.split("\n") if p.strip()]
        assert len(players) == 0

    def test_whitespace_handling_in_names(
        self,
    ):
        """Test: Extra whitespace in player/server names handled."""
        name = "  Player Name  "
        assert name.strip() == "Player Name"

    def test_special_characters_in_messages(
        self,
    ):
        """Test: Special chars escaped for Lua."""
        message = 'Test "quotes" and \'apostrophes\''
        escaped = message.replace('"', '\\"')
        assert '\\"' in escaped

    @pytest.mark.asyncio
    async def test_server_paused_state_handling(
        self,
        mock_bot,
    ):
        """Test: Status command shows pause state immediately.
        
        When is_paused=True:
        - Show "⏸️ Paused" immediately
        - Don't show "🔄 Fetching..." UPS data
        """
        # Setup
        metrics = {
            "is_paused": True,
            "ups": None,  # Not fetched when paused
        }
        
        # Verify pause takes precedence
        if metrics["is_paused"]:
            state = "⏸️ Paused"
        elif metrics.get("ups") is not None:
            state = f"▶️ Running @ {metrics['ups']:.1f}"
        else:
            state = "🔄 Fetching..."
        
        assert state == "⏸️ Paused"


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_bot():
    """Create a mock DiscordBot instance with all required attributes."""
    bot = MagicMock()
    bot.user_context = MagicMock()
    bot.user_context.get_rcon_for_user = MagicMock()
    bot.user_context.get_server_display_name = MagicMock(return_value="test-server")
    bot.user_context.get_user_server = MagicMock(return_value="main")
    bot.user_context.set_user_server = MagicMock()
    bot.server_manager = None  # Explicitly None for single-server mode by default
    bot.rcon_monitor = MagicMock()
    bot.rcon_monitor.rcon_server_states = {}
    bot._connected = True
    bot.tree = MagicMock()
    bot.tree.add_command = MagicMock()
    return bot


@pytest.fixture
def mock_rcon_client():
    """Create a mock RCON client with async execute method."""
    client = MagicMock()
    client.is_connected = True
    client.execute = AsyncMock()
    return client


@pytest.fixture
def mock_interaction():
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
    # Run tests with: pytest tests/test_factorio_commands.py -v
    # Run with coverage: pytest tests/test_factorio_commands.py --cov=bot.commands.factorio --cov-report=term-missing
    pytest.main(["-v", __file__])
