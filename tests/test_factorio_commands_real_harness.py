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

"""REAL TEST HARNESS: Actually invoke nested async command closures.

🔥 THE PROBLEM:
   Commands are defined as async closures INSIDE register_factorio_commands():
   
   def register_factorio_commands(bot):
       @group.command(name='evolution')
       async def evolution_command(interaction, target):  # <- CLOSURE
           ... (55 statements, 0% coverage)
   
   These can't be tested directly — they must be extracted from the bot.tree
   after calling register_factorio_commands().

🎯 THE SOLUTION:
   1. Create mock bot with all required attributes
   2. Call register_factorio_commands(mock_bot)
   3. Extract command from bot.tree.add_command() call
   4. INVOKE with mock interaction
   5. Validate response

✨ COVERAGE TARGETS:
   Phase 1 (0% → 70%+): evolution, health, connect, admins (86 statements)
   Phase 2 (0% → 70%+): kick, ban, promote, demote, whisper (129 statements)
   Phase 3 (37-57% → 85%+): clock, research, save, whitelist (138 statements)
   Phase 4 (0% → 85%+): broadcast, speed, seed, rcon, help (127 statements)
   Phase 5 (NEW): unban, unmute, server_autocomplete (75 statements)
   
   Total new coverage: 555 statements → ~91%+ overall
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from typing import Optional, Any, Dict, List
import re

# Import the registration function
from bot.commands.factorio import register_factorio_commands
from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
from discord_interface import EmbedBuilder


class CommandExtractor:
    """Helper to extract commands from bot.tree after registration."""

    @staticmethod
    def extract_command_from_group(group: app_commands.Group, name: str) -> Optional[Any]:
        """Extract a subcommand from a command group."""
        for cmd in group.commands:
            if cmd.name == name:
                return cmd
        return None

    @staticmethod
    def get_registered_group(mock_bot: MagicMock) -> Optional[app_commands.Group]:
        """Extract the factorio group from bot.tree.add_command() call."""
        # register_factorio_commands() calls bot.tree.add_command(factorio_group)
        if mock_bot.tree.add_command.called:
            call_args = mock_bot.tree.add_command.call_args
            if call_args and call_args[0]:  # positional args
                return call_args[0][0]  # First positional arg is the group
        return None


# ════════════════════════════════════════════════════════════════════════════
# NEW: UNBAN COMMAND (DANGER_COOLDOWN, Real closure, 21 statements)
# ════════════════════════════════════════════════════════════════════════════

class TestUnbanCommandClosure:
    """Test unban_command closure — currently 0% coverage (21 statements).
    
    Code path:
    1. Rate limit check (DANGER_COOLDOWN)
    2. Defer interaction
    3. Get RCON client
    4. Validate RCON connected
    5. Execute /unban {player}
    6. Build success embed
    7. Send embed
    8. Log action
    """

    @pytest.mark.asyncio
    async def test_unban_player_happy_path(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """INVOKE unban command with valid player (happy path).
        
        Code path:
        1. Rate limit check passes
        2. RCON client available
        3. Execute /unban command
        4. Build success embed with player name
        5. Send embed
        """
        # Setup
        DANGER_COOLDOWN.reset(mock_interaction.user.id)
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute.return_value = "Player BannedUser unbanned."
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        assert group is not None
        unban_cmd = CommandExtractor.extract_command_from_group(group, "unban")
        assert unban_cmd is not None
        
        # INVOKE
        await unban_cmd.callback(mock_interaction, player="BannedUser")
        
        # VALIDATE: interaction deferred
        mock_interaction.response.defer.assert_called_once()
        
        # VALIDATE: response sent
        mock_interaction.followup.send.assert_called_once()
        
        # VALIDATE: embed sent
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        embed = call_kwargs.get('embed')
        assert embed is not None
        assert "Unbanned" in embed.title or "✅" in embed.title
        assert "BannedUser" in embed.description or "BannedUser" in str([f.value for f in embed.fields])
        
        # VALIDATE: success color
        assert embed.color.value == EmbedBuilder.COLOR_SUCCESS
        
        # VALIDATE: RCON execute called
        mock_rcon_client.execute.assert_called_once()
        rcon_cmd = mock_rcon_client.execute.call_args[0][0]
        assert "/unban BannedUser" in rcon_cmd

    @pytest.mark.asyncio
    async def test_unban_rate_limited(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Force unban command rate limit (DANGER_COOLDOWN exhaustion).
        
        Pattern 11: Test error branch
        🔴 Forces: if is_limited: send cooldown_embed; return
        ✅ Validates: Cooldown embed sent, no RCON execute
        """
        # 🔴 Setup: Exhaust DANGER_COOLDOWN (1 use per 60s)
        user_id = mock_interaction.user.id
        DANGER_COOLDOWN.check_rate_limit(user_id)  # Exhaust quota
        
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        unban_cmd = CommandExtractor.extract_command_from_group(group, "unban")
        
        # INVOKE (2nd call hits rate limit)
        await unban_cmd.callback(mock_interaction, player="BannedUser")
        
        # ✅ VALIDATE: Cooldown embed sent
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert embed.color.value == EmbedBuilder.COLOR_WARNING
        assert "Slow Down" in embed.title or "⏱️" in embed.title or "seconds" in embed.description.lower()
        assert mock_interaction.followup.send.call_args.kwargs['ephemeral'] is True
        
        # ✅ VALIDATE: No RCON execute
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unban_rcon_unavailable(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Force unban command error when RCON unavailable.
        
        Pattern 11: Test error branch
        🔴 Forces: if rcon_client is None
        ✅ Validates: Error embed sent, ephemeral=True
        """
        # 🔴 Setup: RCON unavailable
        DANGER_COOLDOWN.reset(mock_interaction.user.id)
        mock_bot.user_context.get_rcon_for_user.return_value = None  # 🔴
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        unban_cmd = CommandExtractor.extract_command_from_group(group, "unban")
        
        # INVOKE
        await unban_cmd.callback(mock_interaction, player="BannedUser")
        
        # ✅ VALIDATE: Error embed
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert embed.color.value == EmbedBuilder.COLOR_ERROR
        assert "RCON not available" in embed.description
        assert mock_interaction.followup.send.call_args.kwargs['ephemeral'] is True
        
        # ✅ VALIDATE: No RCON execute
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unban_rcon_disconnected(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Force unban command error when RCON disconnected.
        
        Pattern 11: Test error branch
        🔴 Forces: if not rcon_client.is_connected
        ✅ Validates: Error embed, no execute calls
        """
        # 🔴 Setup: RCON disconnected
        DANGER_COOLDOWN.reset(mock_interaction.user.id)
        mock_rcon_client.is_connected = False  # 🔴
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        unban_cmd = CommandExtractor.extract_command_from_group(group, "unban")
        
        # INVOKE
        await unban_cmd.callback(mock_interaction, player="BannedUser")
        
        # ✅ VALIDATE
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert embed.color.value == EmbedBuilder.COLOR_ERROR
        assert mock_interaction.followup.send.call_args.kwargs['ephemeral'] is True
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unban_exception_handler(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Force unban command exception handler.
        
        Pattern 11: Test error branch
        🔴 Forces: except Exception as e
        ✅ Validates: Error embed with exception message
        """
        # 🔴 Setup: RCON execute raises exception
        DANGER_COOLDOWN.reset(mock_interaction.user.id)
        mock_rcon_client.is_connected = True
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.execute.side_effect = Exception("RCON command failed")  # 🔴
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        unban_cmd = CommandExtractor.extract_command_from_group(group, "unban")
        
        # INVOKE
        await unban_cmd.callback(mock_interaction, player="BannedUser")
        
        # ✅ VALIDATE: Error embed with exception message
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert embed.color.value == EmbedBuilder.COLOR_ERROR
        assert "failed" in embed.description.lower() or "error" in embed.description.lower()
        assert mock_interaction.followup.send.call_args.kwargs['ephemeral'] is True


# ════════════════════════════════════════════════════════════════════════════
# NEW: UNMUTE COMMAND (ADMIN_COOLDOWN, Real closure, 24 statements)
# ════════════════════════════════════════════════════════════════════════════

class TestUnmuteCommandClosure:
    """Test unmute_command closure — currently 0% coverage (24 statements).
    
    Code path:
    1. Rate limit check (ADMIN_COOLDOWN)
    2. Defer interaction
    3. Get RCON client
    4. Validate RCON connected
    5. Execute /unmute {player}
    6. Build success embed
    7. Send embed with player details
    8. Log action
    """

    @pytest.mark.asyncio
    async def test_unmute_player_happy_path(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """INVOKE unmute command with valid player (happy path).
        
        Code path:
        1. Rate limit check passes
        2. RCON client available
        3. Execute /unmute command
        4. Build success embed with player name
        5. Send embed
        """
        # Setup
        ADMIN_COOLDOWN.reset(mock_interaction.user.id)
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute.return_value = "Player Spammer has been unmuted."
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        assert group is not None
        unmute_cmd = CommandExtractor.extract_command_from_group(group, "unmute")
        assert unmute_cmd is not None
        
        # INVOKE
        await unmute_cmd.callback(mock_interaction, player="Spammer")
        
        # VALIDATE: interaction deferred
        mock_interaction.response.defer.assert_called_once()
        
        # VALIDATE: response sent
        mock_interaction.followup.send.assert_called_once()
        
        # VALIDATE: embed sent
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        embed = call_kwargs.get('embed')
        assert embed is not None
        assert "Unmuted" in embed.title or "🔊" in embed.title
        assert "Spammer" in embed.description or "Spammer" in str([f.value for f in embed.fields])
        
        # VALIDATE: success color
        assert embed.color.value == EmbedBuilder.COLOR_SUCCESS
        
        # VALIDATE: RCON execute called
        mock_rcon_client.execute.assert_called_once()
        rcon_cmd = mock_rcon_client.execute.call_args[0][0]
        assert "/unmute Spammer" in rcon_cmd

    @pytest.mark.asyncio
    async def test_unmute_rate_limited(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Force unmute command rate limit (ADMIN_COOLDOWN exhaustion).
        
        Pattern 11: Test error branch
        🔴 Forces: if is_limited: send cooldown_embed; return
        ✅ Validates: Cooldown embed sent, no RCON execute
        """
        # 🔴 Setup: Exhaust ADMIN_COOLDOWN (3 uses per 60s)
        user_id = mock_interaction.user.id
        for _ in range(3):
            ADMIN_COOLDOWN.check_rate_limit(user_id)  # Exhaust quota
        
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        unmute_cmd = CommandExtractor.extract_command_from_group(group, "unmute")
        
        # INVOKE (4th call hits rate limit)
        await unmute_cmd.callback(mock_interaction, player="Spammer")
        
        # ✅ VALIDATE: Cooldown embed sent
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert embed.color.value == EmbedBuilder.COLOR_WARNING
        assert "Slow Down" in embed.title or "⏱️" in embed.title or "seconds" in embed.description.lower()
        assert mock_interaction.followup.send.call_args.kwargs['ephemeral'] is True
        
        # ✅ VALIDATE: No RCON execute
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unmute_rcon_unavailable(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Force unmute command error when RCON unavailable.
        
        Pattern 11: Test error branch
        🔴 Forces: if rcon_client is None
        ✅ Validates: Error embed sent, ephemeral=True
        """
        # 🔴 Setup: RCON unavailable
        ADMIN_COOLDOWN.reset(mock_interaction.user.id)
        mock_bot.user_context.get_rcon_for_user.return_value = None  # 🔴
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        unmute_cmd = CommandExtractor.extract_command_from_group(group, "unmute")
        
        # INVOKE
        await unmute_cmd.callback(mock_interaction, player="Spammer")
        
        # ✅ VALIDATE: Error embed
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert embed.color.value == EmbedBuilder.COLOR_ERROR
        assert "RCON not available" in embed.description
        assert mock_interaction.followup.send.call_args.kwargs['ephemeral'] is True
        
        # ✅ VALIDATE: No RCON execute
        mock_rcon_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unmute_exception_handler(
        self,
        mock_bot: MagicMock,
        mock_rcon_client: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Force unmute command exception handler.
        
        Pattern 11: Test error branch
        🔴 Forces: except Exception as e
        ✅ Validates: Error embed with exception message
        """
        # 🔴 Setup: RCON execute raises exception
        ADMIN_COOLDOWN.reset(mock_interaction.user.id)
        mock_rcon_client.is_connected = True
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_rcon_client.execute.side_effect = Exception("Player not found")  # 🔴
        
        # Register and extract
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        unmute_cmd = CommandExtractor.extract_command_from_group(group, "unmute")
        
        # INVOKE
        await unmute_cmd.callback(mock_interaction, player="Spammer")
        
        # ✅ VALIDATE: Error embed with exception message
        embed = mock_interaction.followup.send.call_args.kwargs['embed']
        assert embed.color.value == EmbedBuilder.COLOR_ERROR
        assert "failed" in embed.description.lower() or "error" in embed.description.lower()
        assert mock_interaction.followup.send.call_args.kwargs['ephemeral'] is True


# ════════════════════════════════════════════════════════════════════════════
# NEW: SERVER_AUTOCOMPLETE FUNCTION (Standalone, 30 statements)
# ════════════════════════════════════════════════════════════════════════════

class TestServerAutocompleteFunction:
    """Test server_autocomplete function — currently 0% coverage (30 statements).
    
    Code path:
    1. Check if interaction.client has server_manager
    2. If not, return []
    3. Get list of servers
    4. Filter by current string (tag, name, description)
    5. Build display string ("tag - name (description)")
    6. Create Choice objects
    7. Truncate to 25 choices
    8. Return list
    
    Edge cases:
    - No server_manager → return []
    - Empty server list → return []
    - Current string matches tag → include
    - Current string matches name → include
    - Current string matches description → include
    - Multiple matches → all included
    - >25 matches → truncate to 25
    - Display text >100 chars → truncate
    """

    @pytest.mark.asyncio
    async def test_autocomplete_tag_match(
        self,
        mock_bot: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Test server_autocomplete matching tag.
        
        Pattern 5: Test filtering logic
        Current: 'prod'
        Tag: 'prod-server'
        Expected: Match, Choice added
        """
        # Setup mock servers
        mock_bot.server_manager = MagicMock()
        mock_servers = {
            "prod-server": MagicMock(
                name="Production Server",
                description="Main game server"
            ),
            "dev-server": MagicMock(
                name="Development Server",
                description="Testing only"
            ),
        }
        mock_bot.server_manager.list_servers.return_value = mock_servers
        mock_interaction.client.server_manager = mock_bot.server_manager
        
        # Get autocomplete function
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        
        # Extract connect command which has server_autocomplete
        connect_cmd = CommandExtractor.extract_command_from_group(group, "connect")
        assert connect_cmd is not None
        
        # Get autocomplete function from command
        # (server_autocomplete is attached as autocomplete callback)
        # We need to test it directly
        autocomplete_fn = connect_cmd._app_commands_autocomplete_callbacks.get('server')
        assert autocomplete_fn is not None
        
        # INVOKE autocomplete
        choices = await autocomplete_fn(mock_interaction, 'prod')
        
        # ✅ VALIDATE: Tag matches, choice returned
        assert len(choices) > 0
        assert any('prod-server' in c.value for c in choices)
        
        # ✅ VALIDATE: Display text includes name
        assert any('Production Server' in c.name for c in choices)

    @pytest.mark.asyncio
    async def test_autocomplete_name_match(
        self,
        mock_bot: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Test server_autocomplete matching name.
        
        Pattern 5: Test filtering logic
        Current: 'production'
        Name: 'Production Server'
        Expected: Match, Choice added
        """
        # Setup mock servers
        mock_bot.server_manager = MagicMock()
        mock_servers = {
            "prod": MagicMock(
                name="Production Server",
                description="Main"
            ),
            "dev": MagicMock(
                name="Development",
                description="Testing"
            ),
        }
        mock_bot.server_manager.list_servers.return_value = mock_servers
        mock_interaction.client.server_manager = mock_bot.server_manager
        
        # Register to get autocomplete function
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command_from_group(group, "connect")
        autocomplete_fn = connect_cmd._app_commands_autocomplete_callbacks.get('server')
        
        # INVOKE autocomplete
        choices = await autocomplete_fn(mock_interaction, 'production')
        
        # ✅ VALIDATE: Name matches
        assert len(choices) > 0
        assert any('prod' in c.value for c in choices)

    def test_autocomplete_empty_server_list(
        self,
        mock_bot: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Test server_autocomplete with empty server list.
        
        Pattern 6: Test empty/error states
        Servers: {}
        Expected: Return []
        """
        # Setup mock with empty servers
        mock_bot.server_manager = MagicMock()
        mock_bot.server_manager.list_servers.return_value = {}  # Empty
        mock_interaction.client.server_manager = mock_bot.server_manager
        
        # Import and test directly
        from bot.commands.factorio import register_factorio_commands
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command_from_group(group, "connect")
        autocomplete_fn = connect_cmd._app_commands_autocomplete_callbacks.get('server')
        
        # Can't await non-async function in sync test
        # So we'll create an async wrapper
        async def run_test():
            choices = await autocomplete_fn(mock_interaction, 'any')
            assert len(choices) == 0
        
        import asyncio
        asyncio.run(run_test())

    def test_autocomplete_no_server_manager(
        self,
        mock_bot: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Test server_autocomplete when no server_manager.
        
        Pattern 6: Test error states
        server_manager: None
        Expected: Return []
        """
        # Setup mock without server_manager
        mock_interaction.client.server_manager = None  # No manager
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command_from_group(group, "connect")
        autocomplete_fn = connect_cmd._app_commands_autocomplete_callbacks.get('server')
        
        async def run_test():
            choices = await autocomplete_fn(mock_interaction, 'any')
            assert len(choices) == 0
        
        import asyncio
        asyncio.run(run_test())

    @pytest.mark.asyncio
    async def test_autocomplete_truncates_to_25(
        self,
        mock_bot: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Test server_autocomplete truncates >25 matches to 25.
        
        Pattern 6: Test edge case
        Matches: 50 servers all matching
        Expected: Return only 25 choices
        """
        # Setup mock with 50 matching servers
        mock_bot.server_manager = MagicMock()
        mock_servers = {
            f"server-{i}": MagicMock(
                name=f"Server {i}",
                description="Test"
            )
            for i in range(50)
        }
        mock_bot.server_manager.list_servers.return_value = mock_servers
        mock_interaction.client.server_manager = mock_bot.server_manager
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command_from_group(group, "connect")
        autocomplete_fn = connect_cmd._app_commands_autocomplete_callbacks.get('server')
        
        # INVOKE with empty current (all match)
        choices = await autocomplete_fn(mock_interaction, '')
        
        # ✅ VALIDATE: Truncated to 25
        assert len(choices) == 25

    @pytest.mark.asyncio
    async def test_autocomplete_display_truncates_100_chars(
        self,
        mock_bot: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Test server_autocomplete display text truncates >100 chars.
        
        Pattern 6: Test truncation edge case
        Display: 'tag - name (very long description......)' > 100 chars
        Expected: Truncate to 100 chars
        """
        # Setup mock with long description
        mock_bot.server_manager = MagicMock()
        mock_servers = {
            "srv": MagicMock(
                name="Production",
                description="A" * 200  # Very long description
            ),
        }
        mock_bot.server_manager.list_servers.return_value = mock_servers
        mock_interaction.client.server_manager = mock_bot.server_manager
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command_from_group(group, "connect")
        autocomplete_fn = connect_cmd._app_commands_autocomplete_callbacks.get('server')
        
        # INVOKE
        choices = await autocomplete_fn(mock_interaction, '')
        
        # ✅ VALIDATE: Display text truncated to 100
        assert len(choices) > 0
        assert len(choices[0].name) <= 100

    @pytest.mark.asyncio
    async def test_autocomplete_case_insensitive(
        self,
        mock_bot: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Test server_autocomplete is case-insensitive.
        
        Pattern 5: Test filtering robustness
        Current: 'PROD'
        Tag: 'prod-server'
        Expected: Match (case-insensitive)
        """
        # Setup mock servers
        mock_bot.server_manager = MagicMock()
        mock_servers = {
            "prod-server": MagicMock(
                name="Production",
                description="Main"
            ),
        }
        mock_bot.server_manager.list_servers.return_value = mock_servers
        mock_interaction.client.server_manager = mock_bot.server_manager
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command_from_group(group, "connect")
        autocomplete_fn = connect_cmd._app_commands_autocomplete_callbacks.get('server')
        
        # INVOKE with uppercase
        choices = await autocomplete_fn(mock_interaction, 'PROD')
        
        # ✅ VALIDATE: Case-insensitive match
        assert len(choices) > 0
        assert any('prod-server' in c.value for c in choices)

    @pytest.mark.asyncio
    async def test_autocomplete_no_matches(
        self,
        mock_bot: MagicMock,
        mock_interaction: discord.Interaction,
    ):
        """Test server_autocomplete with no matches.
        
        Pattern 6: Test edge case
        Current: 'xyz'
        Servers: prod, dev (neither match)
        Expected: Return []
        """
        # Setup mock servers
        mock_bot.server_manager = MagicMock()
        mock_servers = {
            "prod": MagicMock(
                name="Production",
                description="Main"
            ),
            "dev": MagicMock(
                name="Development",
                description="Testing"
            ),
        }
        mock_bot.server_manager.list_servers.return_value = mock_servers
        mock_interaction.client.server_manager = mock_bot.server_manager
        
        register_factorio_commands(mock_bot)
        group = CommandExtractor.get_registered_group(mock_bot)
        connect_cmd = CommandExtractor.extract_command_from_group(group, "connect")
        autocomplete_fn = connect_cmd._app_commands_autocomplete_callbacks.get('server')
        
        # INVOKE with non-matching current
        choices = await autocomplete_fn(mock_interaction, 'xyz')
        
        # ✅ VALIDATE: No matches
        assert len(choices) == 0


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_bot() -> MagicMock:
    """Create mock bot with all required attributes."""
    bot = MagicMock()
    
    # user_context
    bot.user_context = MagicMock()
    bot.user_context.get_rcon_for_user = MagicMock()
    bot.user_context.get_server_display_name = MagicMock(return_value="test-server")
    bot.user_context.get_user_server = MagicMock(return_value="main")
    bot.user_context.set_user_server = MagicMock()
    
    # server_manager
    bot.server_manager = MagicMock()
    bot.server_manager.clients = {"main": MagicMock()}
    bot.server_manager.get_config = MagicMock()
    bot.server_manager.get_client = MagicMock()
    bot.server_manager.get_metrics_engine = MagicMock()
    bot.server_manager.list_servers = MagicMock(return_value={"main": MagicMock()})
    bot.server_manager.list_tags = MagicMock(return_value=["main"])
    
    # rcon_monitor
    bot.rcon_monitor = MagicMock()
    bot.rcon_monitor.rcon_server_states = {}
    
    # tree (Discord.py command tree)
    bot.tree = MagicMock()
    bot.tree.add_command = MagicMock()
    
    # Bot status
    bot._connected = True
    
    return bot


@pytest.fixture
def mock_rcon_client() -> MagicMock:
    """Create mock RCON client."""
    client = MagicMock()
    client.is_connected = True
    client.execute = AsyncMock()
    return client


@pytest.fixture
def mock_interaction() -> discord.Interaction:
    """Create mock Discord interaction."""
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
    pytest.main(["-v", __file__, "-s"])
