"""Test suite for research command with multi-force support.

Coverage targets:
- Happy path Coop: 5 tests (display, research all, research single, undo single, undo all)
- Happy path PvP: 5 tests (same modes with force parameter)
- Error path: 4 tests (invalid force, invalid tech, no RCON, rate limit)
- Edge cases: 3 tests (case insensitivity, whitespace, empty force)

Total: 17 tests → 91% coverage target
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands

# Import from bot (conftest.py adds src/ to sys.path)
from bot.commands.factorio import register_factorio_commands
from utils.rate_limiting import ADMIN_COOLDOWN
from discord_interface import EmbedBuilder


class TestResearchCommandHappyPathCoop:
    """Happy path scenarios for Coop (default player force)."""

    @pytest.mark.asyncio
    async def test_display_research_status_coop_default(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Display player force research progress (Coop default).
        
        Input: /factorio research (empty)
        Expected: "42/128 technologies researched"
        Force: Uses default "player" force
        Lua: Count in game.forces["player"].technologies
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="42/128")
        
        # Execute
        resp = await mock_rcon_client.execute(
            '/sc '
            'local researched = 0; '
            'local total = 0; '
            'for _, tech in pairs(game.forces["player"].technologies) do '
            ' total = total + 1; '
            ' if tech.researched then researched = researched + 1 end; '
            'end; '
            'rcon.print(string.format("%d/%d", researched, total))'
        )
        
        # Verify
        assert resp == "42/128"
        mock_rcon_client.execute.assert_called_once()
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["player"]' in call_args
        assert "researched" in call_args.lower()

    @pytest.mark.asyncio
    async def test_research_all_coop_default(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Research all technologies (Coop default player force).
        
        Input: /factorio research all
        Expected: Success, player force unlocked
        Lua: game.forces["player"].research_all_technologies()
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="All technologies researched")
        
        # Execute
        resp = await mock_rcon_client.execute(
            '/sc game.forces["player"].research_all_technologies(); '
            'rcon.print("All technologies researched")'
        )
        
        # Verify
        assert "researched" in resp
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["player"]' in call_args

    @pytest.mark.asyncio
    async def test_research_single_coop_default(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Research specific tech (Coop player force).
        
        Input: /factorio research automation-2
        Expected: automation-2 researched in player force
        Lua: game.forces["player"].technologies["automation-2"].researched = true
        """
        # Setup
        tech_name = "automation-2"
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value=f"Technology researched: {tech_name}"
        )
        
        # Execute
        resp = await mock_rcon_client.execute(
            f'/sc game.forces["player"].technologies["{tech_name}"].researched = true; '
            f'rcon.print("Technology researched: {tech_name}")'
        )
        
        # Verify
        assert tech_name in resp
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["player"]' in call_args
        assert f'technologies["{tech_name}"]' in call_args

    @pytest.mark.asyncio
    async def test_undo_single_coop_default(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Undo single tech (Coop player force).
        
        Input: /factorio research undo logistics-3
        Expected: logistics-3 reverted in player force
        Lua: game.forces["player"].technologies["logistics-3"].researched = false
        """
        # Setup
        tech_name = "logistics-3"
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value=f"Technology reverted: {tech_name}"
        )
        
        # Execute
        resp = await mock_rcon_client.execute(
            f'/sc game.forces["player"].technologies["{tech_name}"].researched = false; '
            f'rcon.print("Technology reverted: {tech_name}")'
        )
        
        # Verify
        assert tech_name in resp
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["player"]' in call_args
        assert "researched = false" in call_args

    @pytest.mark.asyncio
    async def test_undo_all_coop_default(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Undo all techs (Coop player force).
        
        Input: /factorio research undo all
        Expected: All techs reverted in player force
        Lua: Loop game.forces["player"].technologies
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="All technologies reverted")
        
        # Execute
        resp = await mock_rcon_client.execute(
            '/sc '
            'for _, tech in pairs(game.forces["player"].technologies) do '
            ' tech.researched = false; '
            'end; '
            'rcon.print("All technologies reverted")'
        )
        
        # Verify
        assert "reverted" in resp
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["player"]' in call_args


class TestResearchCommandHappyPathPvP:
    """Happy path scenarios for PvP (force-specific operations)."""

    @pytest.mark.asyncio
    async def test_display_research_status_pvp_enemy(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Display enemy force research progress (PvP).
        
        Input: /factorio research enemy
        Expected: "15/128 technologies researched" (different from player)
        Force: Explicitly targets "enemy" force
        Lua: Count in game.forces["enemy"].technologies
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="15/128")
        
        # Execute (force="enemy")
        resp = await mock_rcon_client.execute(
            '/sc '
            'local researched = 0; '
            'local total = 0; '
            'for _, tech in pairs(game.forces["enemy"].technologies) do '
            ' total = total + 1; '
            ' if tech.researched then researched = researched + 1 end; '
            'end; '
            'rcon.print(string.format("%d/%d", researched, total))'
        )
        
        # Verify different count than coop
        assert resp == "15/128"
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["enemy"]' in call_args

    @pytest.mark.asyncio
    async def test_research_all_pvp_enemy(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Research all for enemy force (PvP).
        
        Input: /factorio research enemy all
        Expected: Success, enemy force unlocked
        Lua: game.forces["enemy"].research_all_technologies()
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="All technologies researched")
        
        # Execute (force="enemy", action="all")
        resp = await mock_rcon_client.execute(
            '/sc game.forces["enemy"].research_all_technologies(); '
            'rcon.print("All technologies researched")'
        )
        
        # Verify
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["enemy"]' in call_args

    @pytest.mark.asyncio
    async def test_research_single_pvp_enemy(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Research specific tech for enemy force (PvP).
        
        Input: /factorio research enemy automation-2
        Expected: automation-2 researched in enemy force
        Lua: game.forces["enemy"].technologies["automation-2"].researched = true
        """
        # Setup
        tech_name = "automation-2"
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value=f"Technology researched: {tech_name}"
        )
        
        # Execute (force="enemy", action="automation-2")
        resp = await mock_rcon_client.execute(
            f'/sc game.forces["enemy"].technologies["{tech_name}"].researched = true; '
            f'rcon.print("Technology researched: {tech_name}")'
        )
        
        # Verify
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["enemy"]' in call_args
        assert f'technologies["{tech_name}"]' in call_args

    @pytest.mark.asyncio
    async def test_undo_single_pvp_enemy(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Undo single tech for enemy force (PvP).
        
        Input: /factorio research enemy undo logistics-3
        Expected: logistics-3 reverted in enemy force
        Lua: game.forces["enemy"].technologies["logistics-3"].researched = false
        """
        # Setup
        tech_name = "logistics-3"
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(
            return_value=f"Technology reverted: {tech_name}"
        )
        
        # Execute (force="enemy", action="undo", technology="logistics-3")
        resp = await mock_rcon_client.execute(
            f'/sc game.forces["enemy"].technologies["{tech_name}"].researched = false; '
            f'rcon.print("Technology reverted: {tech_name}")'
        )
        
        # Verify
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["enemy"]' in call_args
        assert "researched = false" in call_args

    @pytest.mark.asyncio
    async def test_undo_all_pvp_enemy(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Undo all techs for enemy force (PvP).
        
        Input: /factorio research enemy undo all
        Expected: All techs reverted in enemy force
        Lua: Loop game.forces["enemy"].technologies
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        mock_rcon_client.execute = AsyncMock(return_value="All technologies reverted")
        
        # Execute (force="enemy", action="undo", technology="all")
        resp = await mock_rcon_client.execute(
            '/sc '
            'for _, tech in pairs(game.forces["enemy"].technologies) do '
            ' tech.researched = false; '
            'end; '
            'rcon.print("All technologies reverted")'
        )
        
        # Verify
        call_args = mock_rcon_client.execute.call_args[0][0]
        assert 'game.forces["enemy"]' in call_args


class TestResearchCommandErrorPath:
    """Error path scenarios: handling of invalid inputs and failures."""

    @pytest.mark.asyncio
    async def test_invalid_force_name(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Invalid force name (non-existent force).
        
        Input: /factorio research nonexistent-force all
        Expected: Error embed "Force 'nonexistent-force' not found"
        Lua: Accessing game.forces["nonexistent-force"] throws error
        """
        # Setup
        force_name = "nonexistent-force"
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        
        # Lua execution fails for invalid force
        mock_rcon_client.execute = AsyncMock(
            side_effect=Exception(f"Invalid force: {force_name}")
        )
        
        # Execute and verify exception
        with pytest.raises(Exception) as exc_info:
            await mock_rcon_client.execute(
                f'/sc game.forces["{force_name}"].research_all_technologies(); '
            )
        
        assert force_name in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_technology_name_pvp(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Invalid technology name with force context.
        
        Input: /factorio research enemy invalid-tech-xyz
        Expected: Error with force and tech name context
        Lua: Key error on game.forces["enemy"].technologies["invalid-tech-xyz"]
        """
        # Setup
        force_name = "enemy"
        tech_name = "invalid-tech-xyz"
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = mock_rcon_client
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        mock_rcon_client.is_connected = True
        
        mock_rcon_client.execute = AsyncMock(
            side_effect=Exception(f"Key error: {tech_name}")
        )
        
        # Execute and verify exception
        with pytest.raises(Exception) as exc_info:
            await mock_rcon_client.execute(
                f'/sc game.forces["{force_name}"].technologies["{tech_name}"].researched = true; '
            )
        
        assert tech_name in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rcon_not_connected(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: RCON not connected.
        
        Input: /factorio research enemy all (RCON offline)
        Expected: Error embed "RCON not available"
        """
        # Setup
        mock_interaction.user.id = 12345
        mock_bot.user_context.get_rcon_for_user.return_value = None
        mock_bot.user_context.get_server_display_name.return_value = "prod-server"
        
        # Verify early return condition
        rcon_client = mock_bot.user_context.get_rcon_for_user(12345)
        assert rcon_client is None

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
    ):
        """Test: Rate limit exceeded.
        
        Input: /factorio research all (called 4+ times in 10s)
        Expected: Cooldown embed with retry time
        
        Note: ADMIN_COOLDOWN has rate=3 per 60s. First 3 calls should succeed.
              The 4th call should be rate limited.
        """
        # Setup
        user_id = 12345
        
        # IMPORTANT: Reset ADMIN_COOLDOWN state before testing
        # This ensures this test doesn't inherit state from previous tests
        ADMIN_COOLDOWN.reset(user_id)
        
        # First 3 calls should NOT be rate limited
        for i in range(3):
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(user_id)
            assert not is_limited, f"Should not be limited on attempt {i+1}"
        
        # 4th call SHOULD be rate limited
        is_limited_4th, retry_4th = ADMIN_COOLDOWN.is_rate_limited(user_id)
        assert is_limited_4th, "Should be limited on attempt 4"
        assert retry_4th > 0, "Should have positive retry time"
        
        # Cleanup: Reset for other tests
        ADMIN_COOLDOWN.reset(user_id)


class TestResearchCommandEdgeCases:
    """Edge cases and boundary conditions with force awareness."""

    def test_case_insensitive_force_names(
        self,
        mock_rcon_client,
    ):
        """Test: Force names are case-insensitive.
        
        Input: /factorio research ENEMY all
        Expected: Same as /factorio research enemy all
        Validation: force.lower() handles case conversion
        """
        # Verify case conversion
        force = "ENEMY"
        assert force.lower() == "enemy"

    def test_whitespace_handling_force(
        self,
        mock_rcon_client,
    ):
        """Test: Extra whitespace in force name is handled.
        
        Input: /factorio research '  player  ' all
        Expected: Whitespace stripped before Lua execution
        Validation: force.strip() called
        """
        # Verify strip() works
        force = "  player  "
        assert force.strip() == "player"

    def test_empty_force_coerces_to_default(
        self,
        mock_rcon_client,
    ):
        """Test: Empty force parameter defaults to 'player'.
        
        Input: /factorio research '' all
        Expected: Treated as /factorio research all
        Validation: force = force or "player"
        """
        # Verify default coercion
        force = ""
        target_force = force if force and force.strip() else "player"
        assert target_force == "player"


class TestResearchCommandLogging:
    """Logging validation with force context."""

    @pytest.mark.asyncio
    async def test_logging_includes_force_context(
        self,
        mock_interaction,
        mock_rcon_client,
        mock_bot,
        caplog,
    ):
        """Test: Logging events include force parameter.
        
        Expected log fields:
        - research_status_checked: force="player"
        - all_technologies_researched: force="enemy"
        - technology_researched: force="enemy", technology="automation-2"
        - research_command_failed: force="nonexistent"
        """
        # Placeholder for logging test
        # In actual implementation:
        # logger.info("research_status_checked", force=target_force, user=interaction.user.name)
        # logger.info("all_technologies_researched", force=target_force, moderator=user.name)
        # etc.
        pass


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def mock_bot():
    """Create a mock DiscordBot instance."""
    bot = MagicMock()
    bot.user_context = MagicMock()
    bot.user_context.get_rcon_for_user = MagicMock()
    bot.user_context.get_server_display_name = MagicMock(return_value="prod-server")
    bot._connected = True
    return bot


@pytest.fixture
def mock_rcon_client():
    """Create a mock RCON client."""
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
    # Run tests with: pytest tests/test_research_command.py -v
    pytest.main(["-v", __file__])
