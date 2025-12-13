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

"""DISCRETE TESTS: Target 328 remaining statements for 91% coverage.

🎯 COVERAGE GAPS ADDRESSED:

Gap 1: Server Management (48 statements)
├─ Server context switching
├─ Multi-server status aggregation  
├─ Server configuration lifecycle
└─ Connection state validation

Gap 2: Evolution Command (52 statements)
├─ Per-surface queries
├─ Platform surface filtering
├─ Aggregate calculations
└─ Error scenarios

Gap 3: Clock Command (45 statements)
├─ Eternal day/night mode
├─ Float validation (0.0-1.0)
├─ Freeze daytime mechanics
└─ Time formatting

Gap 4: Research Command (60 statements)
├─ Multi-force support
├─ Technology status counts
├─ Research all workflow
├─ Undo scenarios
└─ Invalid force handling

Gap 5: Whitelist Command (42 statements)
├─ Add/remove operations
├─ Enable/disable toggles
├─ List display
└─ Player validation

Gap 6: Metrics Integration (35 statements)
├─ Engine instantiation
├─ Metrics gathering
├─ Multi-surface evolution
└─ Play time extraction

Gap 7: Error Handling (46 statements)
├─ Exception paths
├─ RCON state checks
├─ Response parsing
└─ Logging verification

TOTAL: 328 statements → 91% coverage
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone
import discord
from discord import app_commands

from bot.commands.factorio import register_factorio_commands
from discord_interface import EmbedBuilder


class CommandExtractor:
    """Extract commands from bot.tree after registration."""
    
    @staticmethod
    def get_registered_group(mock_bot):
        if mock_bot.tree.add_command.called:
            return mock_bot.tree.add_command.call_args[0][0]
        return None
    
    @staticmethod
    def extract_command(group, name):
        for cmd in group.commands:
            if cmd.name == name:
                return cmd
        return None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# GAP 1: SERVER MANAGEMENT ADVANCED (48 statements)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class TestServerManagementAdvanced:
    """Test server context switching and configuration (48 statements)."""
    
    @pytest.mark.asyncio
    async def test_servers_command_multi_server_display(self, mock_bot, mock_interaction):
        """Display multiple servers with status and context indicator."""
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.list_tags.return_value = ["prod", "staging", "dev"]
        mock_bot.server_manager.list_servers.return_value = {
            "prod": MagicMock(name="Production", description="Main server", rcon_host="1.2.3.4", rcon_port=5000),
            "staging": MagicMock(name="Staging", description="Test server", rcon_host="1.2.3.5", rcon_port=5001),
            "dev": MagicMock(name="Dev", description=None, rcon_host="1.2.3.6", rcon_port=5002),
        }
        mock_bot.server_manager.get_status_summary.return_value = {
            "prod": True,
            "staging": False,
            "dev": True,
        }
        mock_bot.user_context.get_user_server.return_value = "prod"
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        servers_cmd = CommandExtractor.extract_command(group, "servers")
        
        await servers_cmd.callback(mock_interaction)
        
        # Should defer and send embed
        assert mock_interaction.response.defer.called
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert embed is not None
        assert len(embed.fields) == 3  # 3 servers
    
    @pytest.mark.asyncio
    async def test_servers_command_no_servers_configured(self, mock_bot, mock_interaction):
        """Handle case when no servers are configured."""
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.list_tags.return_value = []
        mock_bot.server_manager.list_servers.return_value = {}
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        servers_cmd = CommandExtractor.extract_command(group, "servers")
        
        await servers_cmd.callback(mock_interaction)
        
        # Should show "No servers configured"
        assert mock_interaction.response.send_message.called
        embed = mock_interaction.response.send_message.call_args.kwargs['embed']
        assert "Single-server mode" in embed.description.lower()
    
    @pytest.mark.asyncio
    async def test_connect_command_valid_server_switch(self, mock_bot, mock_rcon_client, mock_interaction):
        """Switch user context to different server with connection status."""
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.clients = {"prod": mock_rcon_client, "staging": MagicMock()}
        mock_bot.server_manager.list_servers.return_value = {
            "prod": MagicMock(name="Production", description="Main", rcon_host="1.2.3.4", rcon_port=5000),
            "staging": MagicMock(name="Staging", description="Test", rcon_host="1.2.3.5", rcon_port=5001),
        }
        mock_bot.server_manager.get_config.return_value = MagicMock(
            name="Production", description="Main server", rcon_host="1.2.3.4", rcon_port=5000
        )
        mock_bot.server_manager.get_client.return_value = mock_rcon_client
        mock_rcon_client.is_connected = True
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command(group, "connect")
        
        await connect_cmd.callback(mock_interaction, server="prod")
        
        # Should set user server and show confirmation
        assert mock_bot.user_context.set_user_server.called
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "Connected" in embed.title
    
    @pytest.mark.asyncio
    async def test_connect_command_server_not_found(self, mock_bot, mock_interaction):
        """Handle connecting to non-existent server."""
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.clients = {"prod": MagicMock()}
        mock_bot.server_manager.list_servers.return_value = {
            "prod": MagicMock(name="Production", description=None, rcon_host="1.2.3.4", rcon_port=5000),
        }
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command(group, "connect")
        
        await connect_cmd.callback(mock_interaction, server="nonexistent")
        
        # Should show error about server not found
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "not found" in embed.description.lower()
    
    @pytest.mark.asyncio
    async def test_server_autocomplete_filtering(self, mock_bot, mock_interaction):
        """Test server autocomplete filters by tag, name, and description."""
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.list_servers.return_value = {
            "prod": MagicMock(name="Production", description="Main server"),
            "staging": MagicMock(name="Staging", description="Test environment"),
            "dev": MagicMock(name="Developer", description="Local"),
        }
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command(group, "connect")
        
        # Test autocomplete callback
        autocomplete_func = connect_cmd.autocomplete
        mock_interaction.client = mock_bot
        
        # Filter by "prod"
        choices = await autocomplete_func(mock_interaction, "prod")
        assert len(choices) > 0
        assert any("prod" in c.value.lower() for c in choices)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# GAP 2: EVOLUTION COMMAND ADVANCED (52 statements)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class TestEvolutionCommandAdvanced:
    """Test evolution command advanced paths (52 statements)."""
    
    @pytest.mark.asyncio
    async def test_evolution_per_surface_query(self, mock_bot, mock_rcon_client, mock_interaction):
        """Query evolution for specific surface."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="45.32%")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        evo_cmd = CommandExtractor.extract_command(group, "evolution")
        
        await evo_cmd.callback(mock_interaction, target="nauvis")
        
        # Should execute with surface-specific Lua
        assert mock_rcon_client.execute.called
        lua_cmd = mock_rcon_client.execute.call_args[0][0]
        assert "nauvis" in lua_cmd
        assert mock_interaction.followup.send.called
    
    @pytest.mark.asyncio
    async def test_evolution_aggregate_all_surfaces(self, mock_bot, mock_rcon_client, mock_interaction):
        """Aggregate evolution across non-platform surfaces."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="AGG:42.50%\nnauvis:42.50%\ngleba:42.50%")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        evo_cmd = CommandExtractor.extract_command(group, "evolution")
        
        await evo_cmd.callback(mock_interaction, target="all")
        
        # Should parse aggregate and per-surface lines
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "All Non-platform" in embed.title
    
    @pytest.mark.asyncio
    async def test_evolution_platform_surface_rejection(self, mock_bot, mock_rcon_client, mock_interaction):
        """Reject platform surfaces from evolution query."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="SURFACE_PLATFORM_IGNORED")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        evo_cmd = CommandExtractor.extract_command(group, "evolution")
        
        await evo_cmd.callback(mock_interaction, target="platform-surface")
        
        # Should send error about platform surface
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "platform" in embed.description.lower()
    
    @pytest.mark.asyncio
    async def test_evolution_surface_not_found(self, mock_bot, mock_rcon_client, mock_interaction):
        """Handle surface not found error."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="SURFACE_NOT_FOUND")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        evo_cmd = CommandExtractor.extract_command(group, "evolution")
        
        await evo_cmd.callback(mock_interaction, target="nonexistent")
        
        # Should send error about surface not found
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "not found" in embed.description.lower()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# GAP 3: CLOCK COMMAND IMPLEMENTATION (45 statements)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class TestClockCommandImplementation:
    """Test clock command with daytime and freeze mechanics (45 statements)."""
    
    @pytest.mark.asyncio
    async def test_clock_display_current_time(self, mock_bot, mock_rcon_client, mock_interaction):
        """Display current game time."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Current daytime: 0.50 (🕐 12:00)")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        clock_cmd = CommandExtractor.extract_command(group, "clock")
        
        await clock_cmd.callback(mock_interaction, value=None)
        
        # Should display current time
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "12:00" in embed.description
    
    @pytest.mark.asyncio
    async def test_clock_set_eternal_day(self, mock_bot, mock_rcon_client, mock_interaction):
        """Set eternal day (noon, frozen)."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="☀️ Set to eternal day (12:00)")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        clock_cmd = CommandExtractor.extract_command(group, "clock")
        
        await clock_cmd.callback(mock_interaction, value="day")
        
        # Should set freeze_daytime to 0.5
        assert mock_rcon_client.execute.called
        lua = mock_rcon_client.execute.call_args[0][0]
        assert "freeze_daytime = 0.5" in lua
        assert "daytime = 0.5" in lua
    
    @pytest.mark.asyncio
    async def test_clock_set_eternal_night(self, mock_bot, mock_rcon_client, mock_interaction):
        """Set eternal night (midnight, frozen)."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="🌙 Set to eternal night (00:00)")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        clock_cmd = CommandExtractor.extract_command(group, "clock")
        
        await clock_cmd.callback(mock_interaction, value="eternal-night")
        
        # Should set freeze_daytime to 0.0
        assert mock_rcon_client.execute.called
        lua = mock_rcon_client.execute.call_args[0][0]
        assert "freeze_daytime = 0.0" in lua
        assert "daytime = 0.0" in lua
    
    @pytest.mark.asyncio
    async def test_clock_set_custom_daytime_float(self, mock_bot, mock_rcon_client, mock_interaction):
        """Set daytime to custom float value (0.0-1.0)."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Set daytime to 0.25 (🕐 06:00)")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        clock_cmd = CommandExtractor.extract_command(group, "clock")
        
        await clock_cmd.callback(mock_interaction, value="0.25")
        
        # Should set daytime and unfreeze time
        assert mock_rcon_client.execute.called
        lua = mock_rcon_client.execute.call_args[0][0]
        assert "daytime = 0.25" in lua
        assert "freeze_daytime = nil" in lua
    
    @pytest.mark.asyncio
    async def test_clock_invalid_float_value(self, mock_bot, mock_rcon_client, mock_interaction):
        """Reject invalid daytime float values."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        clock_cmd = CommandExtractor.extract_command(group, "clock")
        
        # Test value > 1.0
        await clock_cmd.callback(mock_interaction, value="2.0")
        
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "Invalid" in embed.description


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# GAP 4: RESEARCH COMMAND MULTI-FORCE (60 statements)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class TestResearchCommandMultiForce:
    """Test research command with multi-force support (60 statements)."""
    
    @pytest.mark.asyncio
    async def test_research_display_status_player_force(self, mock_bot, mock_rcon_client, mock_interaction):
        """Display technology research status for player force."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="25/50")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        research_cmd = CommandExtractor.extract_command(group, "research")
        
        await research_cmd.callback(mock_interaction, force=None, action=None, technology=None)
        
        # Should show 25/50 researched
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "25/50" in embed.description
    
    @pytest.mark.asyncio
    async def test_research_display_status_custom_force(self, mock_bot, mock_rcon_client, mock_interaction):
        """Display technology status for custom force."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="10/50")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        research_cmd = CommandExtractor.extract_command(group, "research")
        
        await research_cmd.callback(mock_interaction, force="enemy", action=None, technology=None)
        
        # Should use enemy force
        assert mock_rcon_client.execute.called
        lua = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["enemy"]' in lua
    
    @pytest.mark.asyncio
    async def test_research_all_technologies(self, mock_bot, mock_rcon_client, mock_interaction):
        """Research all technologies for a force."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="All technologies researched")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        research_cmd = CommandExtractor.extract_command(group, "research")
        
        await research_cmd.callback(mock_interaction, force="player", action="all", technology=None)
        
        # Should call research_all_technologies
        assert mock_rcon_client.execute.called
        lua = mock_rcon_client.execute.call_args[0][0]
        assert "research_all_technologies" in lua
    
    @pytest.mark.asyncio
    async def test_research_single_technology(self, mock_bot, mock_rcon_client, mock_interaction):
        """Research a single technology."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Technology researched: automation-2")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        research_cmd = CommandExtractor.extract_command(group, "research")
        
        await research_cmd.callback(mock_interaction, force="player", action="automation-2", technology=None)
        
        # Should set technology.researched = true
        assert mock_rcon_client.execute.called
        lua = mock_rcon_client.execute.call_args[0][0]
        assert "automation-2" in lua
        assert "researched = true" in lua
    
    @pytest.mark.asyncio
    async def test_research_undo_all_technologies(self, mock_bot, mock_rcon_client, mock_interaction):
        """Undo all technology research."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="All technologies reverted")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        research_cmd = CommandExtractor.extract_command(group, "research")
        
        await research_cmd.callback(mock_interaction, force="player", action="undo", technology="all")
        
        # Should set all tech researched = false
        assert mock_rcon_client.execute.called
        lua = mock_rcon_client.execute.call_args[0][0]
        assert "tech.researched = false" in lua
    
    @pytest.mark.asyncio
    async def test_research_undo_single_technology(self, mock_bot, mock_rcon_client, mock_interaction):
        """Undo specific technology research."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Technology reverted: automation-2")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        research_cmd = CommandExtractor.extract_command(group, "research")
        
        await research_cmd.callback(mock_interaction, force="player", action="undo", technology="automation-2")
        
        # Should revert specific technology
        assert mock_rcon_client.execute.called
        lua = mock_rcon_client.execute.call_args[0][0]
        assert "automation-2" in lua
        assert "researched = false" in lua


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# GAP 5: WHITELIST COMMAND STATE MANAGEMENT (42 statements)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class TestWhitelistCommandStateManagement:
    """Test whitelist command with add/remove/enable/disable (42 statements)."""
    
    @pytest.mark.asyncio
    async def test_whitelist_list_action(self, mock_bot, mock_rcon_client, mock_interaction):
        """List whitelisted players."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="player1\nplayer2\nplayer3")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        whitelist_cmd = CommandExtractor.extract_command(group, "whitelist")
        
        await whitelist_cmd.callback(mock_interaction, action="list", player=None)
        
        # Should display whitelist
        assert mock_rcon_client.execute.called
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "Whitelist" in embed.title
    
    @pytest.mark.asyncio
    async def test_whitelist_add_player(self, mock_bot, mock_rcon_client, mock_interaction):
        """Add player to whitelist."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Player newplayer added to whitelist")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        whitelist_cmd = CommandExtractor.extract_command(group, "whitelist")
        
        await whitelist_cmd.callback(mock_interaction, action="add", player="newplayer")
        
        # Should call whitelist add
        assert mock_rcon_client.execute.called
        cmd = mock_rcon_client.execute.call_args[0][0]
        assert "/whitelist add newplayer" in cmd
    
    @pytest.mark.asyncio
    async def test_whitelist_remove_player(self, mock_bot, mock_rcon_client, mock_interaction):
        """Remove player from whitelist."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Player oldplayer removed from whitelist")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        whitelist_cmd = CommandExtractor.extract_command(group, "whitelist")
        
        await whitelist_cmd.callback(mock_interaction, action="remove", player="oldplayer")
        
        # Should call whitelist remove
        assert mock_rcon_client.execute.called
        cmd = mock_rcon_client.execute.call_args[0][0]
        assert "/whitelist remove oldplayer" in cmd
    
    @pytest.mark.asyncio
    async def test_whitelist_enable(self, mock_bot, mock_rcon_client, mock_interaction):
        """Enable whitelist."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Whitelist is now enabled")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        whitelist_cmd = CommandExtractor.extract_command(group, "whitelist")
        
        await whitelist_cmd.callback(mock_interaction, action="enable", player=None)
        
        # Should enable whitelist
        assert mock_rcon_client.execute.called
        cmd = mock_rcon_client.execute.call_args[0][0]
        assert "/whitelist enable" in cmd
    
    @pytest.mark.asyncio
    async def test_whitelist_disable(self, mock_bot, mock_rcon_client, mock_interaction):
        """Disable whitelist."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Whitelist is now disabled")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        whitelist_cmd = CommandExtractor.extract_command(group, "whitelist")
        
        await whitelist_cmd.callback(mock_interaction, action="disable", player=None)
        
        # Should disable whitelist
        assert mock_rcon_client.execute.called
        cmd = mock_rcon_client.execute.call_args[0][0]
        assert "/whitelist disable" in cmd
    
    @pytest.mark.asyncio
    async def test_whitelist_add_missing_player_param(self, mock_bot, mock_rcon_client, mock_interaction):
        """Error when add/remove missing player parameter."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        whitelist_cmd = CommandExtractor.extract_command(group, "whitelist")
        
        await whitelist_cmd.callback(mock_interaction, action="add", player=None)
        
        # Should show error
        assert mock_interaction.followup.send.called
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "Player name required" in embed.description


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# GAP 6: METRICS ENGINE INTEGRATION (35 statements)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class TestMetricsEngineIntegration:
    """Test metrics engine integration in status command (35 statements)."""
    
    @pytest.mark.asyncio
    async def test_status_metrics_engine_instantiation(self, mock_bot, mock_rcon_client, mock_interaction):
        """Instantiate metrics engine in status command."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_bot.user_context.get_user_server.return_value = "prod"
        mock_rcon_client.is_connected = True
        
        # Mock metrics engine
        mock_metrics_engine = AsyncMock()
        mock_metrics_engine.gather_all_metrics = AsyncMock(return_value={
            "ups": 60.0,
            "ups_sma": 59.9,
            "ups_ema": 59.95,
            "player_count": 3,
            "is_paused": False,
            "evolution_factor": 0.35,
            "evolution_by_surface": {"nauvis": 0.35, "gleba": 0.28},
            "players": ["player1", "player2"],
            "play_time": "10h 30m",
        })
        mock_bot.server_manager.get_metrics_engine = MagicMock(return_value=mock_metrics_engine)
        
        mock_bot.rcon_monitor = MagicMock()
        mock_bot.rcon_monitor.rcon_server_states = {
            "prod": {"last_connected": datetime.now(timezone.utc)}
        }
        mock_bot._connected = True
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        status_cmd = CommandExtractor.extract_command(group, "status")
        
        await status_cmd.callback(mock_interaction)
        
        # Should get metrics engine
        assert mock_bot.server_manager.get_metrics_engine.called
        assert mock_metrics_engine.gather_all_metrics.called
        assert mock_interaction.followup.send.called
    
    @pytest.mark.asyncio
    async def test_status_ups_metrics_display(self, mock_bot, mock_rcon_client, mock_interaction):
        """Display UPS metrics (SMA, EMA)."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_bot.user_context.get_user_server.return_value = "prod"
        mock_rcon_client.is_connected = True
        
        mock_metrics_engine = AsyncMock()
        mock_metrics_engine.gather_all_metrics = AsyncMock(return_value={
            "ups": 59.8,
            "ups_sma": 59.5,
            "ups_ema": 59.7,
            "player_count": 2,
            "is_paused": False,
            "evolution_factor": 0.40,
        })
        mock_bot.server_manager.get_metrics_engine = MagicMock(return_value=mock_metrics_engine)
        mock_bot.rcon_monitor = MagicMock()
        mock_bot.rcon_monitor.rcon_server_states = {"prod": {"last_connected": datetime.now(timezone.utc)}}
        mock_bot._connected = True
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        status_cmd = CommandExtractor.extract_command(group, "status")
        
        await status_cmd.callback(mock_interaction)
        
        # Should display UPS fields
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        field_names = [f.name for f in embed.fields]
        assert any("UPS (SMA)" in name for name in field_names)
        assert any("UPS (EMA)" in name for name in field_names)
    
    @pytest.mark.asyncio
    async def test_status_multi_surface_evolution(self, mock_bot, mock_rcon_client, mock_interaction):
        """Display multi-surface evolution (nauvis, gleba)."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_bot.user_context.get_user_server.return_value = "prod"
        mock_rcon_client.is_connected = True
        
        mock_metrics_engine = AsyncMock()
        mock_metrics_engine.gather_all_metrics = AsyncMock(return_value={
            "ups": 60.0,
            "player_count": 1,
            "is_paused": False,
            "evolution_by_surface": {
                "nauvis": 0.35,
                "gleba": 0.28,
            },
        })
        mock_bot.server_manager.get_metrics_engine = MagicMock(return_value=mock_metrics_engine)
        mock_bot.rcon_monitor = MagicMock()
        mock_bot.rcon_monitor.rcon_server_states = {"prod": {"last_connected": datetime.now(timezone.utc)}}
        mock_bot._connected = True
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        status_cmd = CommandExtractor.extract_command(group, "status")
        
        await status_cmd.callback(mock_interaction)
        
        # Should display both nauvis and gleba evolution
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        field_names = [f.name for f in embed.fields]
        assert any("Nauvis" in name for name in field_names)
        assert any("Gleba" in name for name in field_names)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# GAP 7: ERROR HANDLING & EDGE CASES (46 statements)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class TestErrorHandlingEdgeCases:
    """Test error handling and edge cases (46 statements)."""
    
    @pytest.mark.asyncio
    async def test_save_command_auto_save_default(self, mock_bot, mock_rcon_client, mock_interaction):
        """Save with auto-save when no name provided."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Saving map to /path/to/LosHermanos.zip")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        save_cmd = CommandExtractor.extract_command(group, "save")
        
        await save_cmd.callback(mock_interaction, name=None)
        
        # Should parse save name from response
        assert mock_rcon_client.execute.called
        cmd = mock_rcon_client.execute.call_args[0][0]
        assert "/save" == cmd  # No name parameter
        
        # Should extract LosHermanos from path
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "LosHermanos" in embed.description
    
    @pytest.mark.asyncio
    async def test_broadcast_message_escaping(self, mock_bot, mock_rcon_client, mock_interaction):
        """Escape quotes in broadcast message."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="Message broadcasted")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        broadcast_cmd = CommandExtractor.extract_command(group, "broadcast")
        
        message = 'Hello "World"'
        await broadcast_cmd.callback(mock_interaction, message=message)
        
        # Should escape double quotes
        assert mock_rcon_client.execute.called
        cmd = mock_rcon_client.execute.call_args[0][0]
        assert '\\"' in cmd  # Escaped quotes
    
    @pytest.mark.asyncio
    async def test_players_command_response_parsing(self, mock_bot, mock_rcon_client, mock_interaction):
        """Parse players response with (online) indicator."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="- player1 (online)\n- player2 (online)\n- player3 (offline)")
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        players_cmd = CommandExtractor.extract_command(group, "players")
        
        await players_cmd.callback(mock_interaction)
        
        # Should parse online players only
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert "2" in embed.fields[0].name  # 2 players online
    
    @pytest.mark.asyncio
    async def test_rcon_command_response_truncation(self, mock_bot, mock_rcon_client, mock_interaction):
        """Truncate long RCON response to 1024 chars."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        long_response = "x" * 2000
        mock_rcon_client.execute = AsyncMock(return_value=long_response)
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        rcon_cmd = CommandExtractor.extract_command(group, "rcon")
        
        await rcon_cmd.callback(mock_interaction, command="/version")
        
        # Should truncate response
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        response_field = [f for f in embed.fields if f.name == "Response"][0]
        assert "..." in response_field.value
        assert len(response_field.value) <= 1030  # Truncated + markdown
    
    @pytest.mark.asyncio
    async def test_speed_command_validation_bounds(self, mock_bot, mock_rcon_client, mock_interaction):
        """Validate game speed bounds (0.1-10.0)."""
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod"
        mock_rcon_client.is_connected = True
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        speed_cmd = CommandExtractor.extract_command(group, "speed")
        
        # Test too low
        await speed_cmd.callback(mock_interaction, value=0.05)
        
        assert mock_interaction.response.send_message.called
        embed = mock_interaction.response.send_message.call_args.kwargs['embed']
        assert "between 0.1 and 10.0" in embed.description
