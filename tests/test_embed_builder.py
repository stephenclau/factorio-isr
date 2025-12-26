

"""COMPREHENSIVE TESTS: EmbedBuilder coverage for all embed types.

🌟 TARGET: Test every EmbedBuilder method that's used in factorio.py commands
   - create_base_embed (foundation for all embeds)
   - error_embed (RCON not connected, command failures)
   - cooldown_embed (rate limit exhaustion)
   - info_embed (status displays, confirmations)
   - admin_action_embed (kick, ban, promote, demote)
   - players_list_embed (players command)
   - server_status_embed (status command)

📊 COVERAGE:
   - All 7 static methods
   - Color scheme constants
   - Footer timestamps
   - Field formatting
   - Optional parameter handling
   - Edge cases (empty lists, None values, long text)
"""

import pytest
from unittest.mock import MagicMock, patch
import discord
from datetime import datetime, timezone

from discord_interface import EmbedBuilder


class TestEmbedBuilderColors:
    """Test EmbedBuilder color constants."""
    
    def test_color_scheme_exists(self):
        """Verify all color constants are defined."""
        assert hasattr(EmbedBuilder, 'COLOR_SUCCESS')
        assert hasattr(EmbedBuilder, 'COLOR_INFO')
        assert hasattr(EmbedBuilder, 'COLOR_WARNING')
        assert hasattr(EmbedBuilder, 'COLOR_ERROR')
        assert hasattr(EmbedBuilder, 'COLOR_ADMIN')
        assert hasattr(EmbedBuilder, 'COLOR_FACTORIO')
    
    def test_color_values(self):
        """Verify color values are valid hex."""
        assert EmbedBuilder.COLOR_SUCCESS == 0x00FF00  # Green
        assert EmbedBuilder.COLOR_INFO == 0x3498DB     # Blue
        assert EmbedBuilder.COLOR_WARNING == 0xFFA500  # Orange
        assert EmbedBuilder.COLOR_ERROR == 0xFF0000    # Red
        assert EmbedBuilder.COLOR_ADMIN == 0xFFC0CB    # Pink
        assert EmbedBuilder.COLOR_FACTORIO == 0xFF6B00 # Factorio orange


class TestCreateBaseEmbed:
    """Test EmbedBuilder.create_base_embed() - foundation for all embeds."""
    
    def test_create_base_embed_minimal(self):
        """Create base embed with just title."""
        embed = EmbedBuilder.create_base_embed(title="Test Title")
        
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Test Title"
        assert embed.description is None
        # Compare Colour.value to int
        assert embed.color.value == EmbedBuilder.COLOR_INFO  # Default color
        assert embed.timestamp is not None
    
    def test_create_base_embed_with_description(self):
        """Create base embed with title and description."""
        embed = EmbedBuilder.create_base_embed(
            title="Test Title",
            description="Test Description"
        )
        
        assert embed.title == "Test Title"
        assert embed.description == "Test Description"
    
    def test_create_base_embed_with_custom_color(self):
        """Create base embed with custom color."""
        embed = EmbedBuilder.create_base_embed(
            title="Test",
            color=EmbedBuilder.COLOR_SUCCESS
        )
        
        assert embed.color.value == EmbedBuilder.COLOR_SUCCESS
    
    def test_create_base_embed_has_footer(self):
        """Verify base embed has Factorio ISR footer."""
        embed = EmbedBuilder.create_base_embed(title="Test")
        
        assert embed.footer.text == "Factorio ISR"
    
    def test_create_base_embed_has_timestamp(self):
        """Verify base embed has UTC timestamp."""
        before = discord.utils.utcnow()
        embed = EmbedBuilder.create_base_embed(title="Test")
        after = discord.utils.utcnow()
        
        assert embed.timestamp is not None
        assert before <= embed.timestamp <= after


class TestErrorEmbed:
    """Test EmbedBuilder.error_embed() - error responses."""
    
    def test_error_embed_basic(self):
        """Create basic error embed."""
        embed = EmbedBuilder.error_embed("Something went wrong")
        
        assert isinstance(embed, discord.Embed)
        assert embed.title == "❌ Error"
        assert embed.description == "Something went wrong"
        assert embed.color.value == EmbedBuilder.COLOR_ERROR
    
    def test_error_embed_long_message(self):
        """Error embed with long error message."""
        long_msg = "This is a very long error message " * 10
        embed = EmbedBuilder.error_embed(long_msg)
        
        assert embed.description == long_msg
    
    def test_error_embed_empty_message(self):
        """Error embed with empty message."""
        embed = EmbedBuilder.error_embed("")
        
        assert embed.description == ""
        assert embed.title == "❌ Error"
    
    def test_error_embed_special_characters(self):
        """Error embed with special characters."""
        msg = "Error: Server /offline & disconnected (timeout)"
        embed = EmbedBuilder.error_embed(msg)
        
        assert embed.description == msg
    
    def test_error_embed_rcon_not_connected(self):
        """Error embed for RCON disconnection scenario."""
        msg = "RCON not available for prod.\n\nUse `/factorio servers` to see available servers."
        embed = EmbedBuilder.error_embed(msg)
        
        assert "RCON not available" in embed.description
        assert embed.color.value == EmbedBuilder.COLOR_ERROR


class TestCooldownEmbed:
    """Test EmbedBuilder.cooldown_embed() - rate limiting."""
    
    def test_cooldown_embed_basic(self):
        """Create cooldown embed."""
        embed = EmbedBuilder.cooldown_embed(30.5)
        
        assert embed.title == "⏱️ Slow Down!"
        assert "30.5" in embed.description
        assert "seconds" in embed.description
        assert embed.color.value == EmbedBuilder.COLOR_WARNING
    
    def test_cooldown_embed_different_times(self):
        """Cooldown embeds with various retry times."""
        for retry_time in [5, 10.5, 60, 0.1]:
            embed = EmbedBuilder.cooldown_embed(retry_time)
            assert str(retry_time) in embed.description
    
    def test_cooldown_embed_zero_retry(self):
        """Cooldown embed with zero retry (edge case)."""
        embed = EmbedBuilder.cooldown_embed(0.0)
        
        assert "0.0" in embed.description
    
    def test_cooldown_embed_message_format(self):
        """Verify cooldown message has correct format."""
        embed = EmbedBuilder.cooldown_embed(45.2)
        
        assert "too quickly" in embed.description.lower()
        assert "try again" in embed.description.lower()
        assert "45.2" in embed.description


class TestInfoEmbed:
    """Test EmbedBuilder.info_embed() - informational messages."""
    
    def test_info_embed_basic(self):
        """Create basic info embed."""
        embed = EmbedBuilder.info_embed("Server Status", "All systems operational")
        
        assert embed.title == "Server Status"
        assert embed.description == "All systems operational"
        assert embed.color.value == EmbedBuilder.COLOR_INFO
    
    def test_info_embed_with_emojis(self):
        """Info embed with emoji titles."""
        embed = EmbedBuilder.info_embed("🕐 Game Clock", "Current daytime: 0.50 (12:00)")
        
        assert "🕐" in embed.title
        assert "Game Clock" in embed.title
    
    def test_info_embed_multiline_message(self):
        """Info embed with multiline message."""
        msg = "Line 1\nLine 2\nLine 3"
        embed = EmbedBuilder.info_embed("Title", msg)
        
        assert embed.description == msg
    
    def test_info_embed_evolution_status(self):
        """Info embed for evolution status (actual use case)."""
        embed = EmbedBuilder.info_embed(
            "🐛 Evolution – All Surfaces",
            "Aggregate enemy evolution: **0.45 (45.0%)**\n\nPer-surface evolution:\n• nauvis:0.45 (45.0%)"
        )
        
        assert "Evolution" in embed.title
        assert "45.0%" in embed.description
    
    def test_info_embed_save_confirmation(self):
        """Info embed for save command confirmation (actual use case)."""
        embed = EmbedBuilder.info_embed(
            "💾 Game Saved",
            "Save name: **autosave1**\n\nServer response: Saving map..."
        )
        
        assert "Game Saved" in embed.title
        assert "autosave1" in embed.description


class TestAdminActionEmbed:
    """Test EmbedBuilder.admin_action_embed() - admin actions."""
    
    def test_admin_action_embed_minimal(self):
        """Create admin action embed with required fields only."""
        embed = EmbedBuilder.admin_action_embed(
            action="Player Kicked",
            player="PlayerName",
            moderator="Moderator"
        )
        
        assert "Player Kicked" in embed.title
        assert embed.color.value == EmbedBuilder.COLOR_ADMIN
        # Check fields exist
        field_names = [f.name for f in embed.fields]
        assert "Player" in field_names
        assert "Moderator" in field_names
    
    def test_admin_action_embed_with_reason(self):
        """Admin action embed with reason."""
        embed = EmbedBuilder.admin_action_embed(
            action="Player Banned",
            player="Hacker",
            moderator="Admin",
            reason="Cheating detected"
        )
        
        field_names = [f.name for f in embed.fields]
        assert "Reason" in field_names
        # Find and verify reason value
        reason_field = next((f for f in embed.fields if f.name == "Reason"), None)
        assert reason_field is not None
        assert "Cheating" in reason_field.value
    
    def test_admin_action_embed_with_response(self):
        """Admin action embed with server response."""
        embed = EmbedBuilder.admin_action_embed(
            action="Save Game",
            player="N/A",
            moderator="Bot",
            response="Saving map to autosave1.zip"
        )
        
        field_names = [f.name for f in embed.fields]
        assert "Server Response" in field_names
    
    def test_admin_action_embed_long_response(self):
        """Admin action embed truncates long response."""
        long_response = "x" * 2000
        embed = EmbedBuilder.admin_action_embed(
            action="Long Response",
            player="Test",
            moderator="Bot",
            response=long_response
        )
        
        response_field = next((f for f in embed.fields if f.name == "Server Response"), None)
        assert response_field is not None
        assert len(response_field.value) <= 1010  # 1000 + "..." + code fence
    
    def test_admin_action_embed_kick(self):
        """Admin action embed for kick command (actual use case)."""
        embed = EmbedBuilder.admin_action_embed(
            action="Player Kicked",
            player="Spammer",
            moderator="Moderator",
            reason="Spam detected"
        )
        
        assert "Kicked" in embed.title
        assert embed.color.value == EmbedBuilder.COLOR_ADMIN
    
    def test_admin_action_embed_ban(self):
        """Admin action embed for ban command (actual use case)."""
        embed = EmbedBuilder.admin_action_embed(
            action="Player Banned",
            player="Hacker",
            moderator="Admin",
            reason="Griefing"
        )
        
        assert "Banned" in embed.title
    
    def test_admin_action_embed_promote(self):
        """Admin action embed for promote command (actual use case)."""
        embed = EmbedBuilder.admin_action_embed(
            action="Player Promoted",
            player="Trusted",
            moderator="Admin"
        )
        
        assert "Promoted" in embed.title
        assert "Admin" in embed.title or "Promoted" in embed.title


class TestPlayersListEmbed:
    """Test EmbedBuilder.players_list_embed() - player listings."""
    
    def test_players_list_empty(self):
        """Players embed with no players online."""
        embed = EmbedBuilder.players_list_embed([])
        
        assert "Players Online" in embed.title
        assert "No players" in embed.description
        assert embed.color.value == EmbedBuilder.COLOR_INFO
    
    def test_players_list_single(self):
        """Players embed with single player."""
        embed = EmbedBuilder.players_list_embed(["PlayerOne"])
        
        assert "(1)" in embed.title
        assert "PlayerOne" in embed.description
        assert embed.color.value == EmbedBuilder.COLOR_SUCCESS
    
    def test_players_list_multiple(self):
        """Players embed with multiple players."""
        players = ["Alice", "Bob", "Charlie"]
        embed = EmbedBuilder.players_list_embed(players)
        
        assert "(3)" in embed.title
        for player in players:
            assert player in embed.description
        assert embed.description.count("•") == 3  # Bullet points
    
    def test_players_list_many(self):
        """Players embed with many players."""
        players = [f"Player{i}" for i in range(20)]
        embed = EmbedBuilder.players_list_embed(players)
        
        assert "(20)" in embed.title
        assert len(embed.description.split("\n")) == 20
    
    def test_players_list_special_names(self):
        """Players embed with special character names."""
        players = ["Player[Bot]", "User@Host", "Test_Name"]
        embed = EmbedBuilder.players_list_embed(players)
        
        for player in players:
            assert player in embed.description


class TestServerStatusEmbed:
    """Test EmbedBuilder.server_status_embed() - server status."""
    
    def test_server_status_basic(self):
        """Create basic server status embed."""
        embed = EmbedBuilder.server_status_embed(
            status="Running",
            players_online=5,
            rcon_enabled=True
        )
        
        assert "Server Status" in embed.title
        assert embed.color.value == EmbedBuilder.COLOR_SUCCESS  # RCON enabled = green
    
    def test_server_status_rcon_disabled(self):
        """Server status embed with RCON disabled."""
        embed = EmbedBuilder.server_status_embed(
            status="Running",
            players_online=0,
            rcon_enabled=False
        )
        
        assert embed.color.value == EmbedBuilder.COLOR_WARNING  # RCON disabled = warning
    
    def test_server_status_with_uptime(self):
        """Server status embed with uptime."""
        embed = EmbedBuilder.server_status_embed(
            status="Online",
            players_online=10,
            rcon_enabled=True,
            uptime="5d 12h 30m"
        )
        
        field_names = [f.name for f in embed.fields]
        assert "Uptime" in field_names
    
    def test_server_status_no_uptime(self):
        """Server status embed without uptime."""
        embed = EmbedBuilder.server_status_embed(
            status="Starting",
            players_online=0,
            rcon_enabled=False
        )
        
        field_names = [f.name for f in embed.fields]
        assert "Uptime" not in field_names
    
    def test_server_status_fields(self):
        """Verify server status embed has all expected fields."""
        embed = EmbedBuilder.server_status_embed(
            status="Online",
            players_online=7,
            rcon_enabled=True,
            uptime="2d 1h"
        )
        
        field_names = [f.name for f in embed.fields]
        assert "Status" in field_names
        assert "Players Online" in field_names
        assert "RCON" in field_names
        assert "Uptime" in field_names


class TestEmbedBuilderIntegration:
    """Integration tests for EmbedBuilder - realistic scenarios."""
    
    def test_embed_builder_evolution_workflow(self):
        """Test evolution command embed workflow."""
        # RCON not connected scenario
        error_embed = EmbedBuilder.error_embed("RCON not available for prod.")
        assert error_embed is not None
        
        # Success scenario
        info_embed = EmbedBuilder.info_embed(
            "🐛 Evolution – Surface `nauvis`",
            "Enemy evolution on `nauvis`: **0.50 (50.0%)**"
        )
        assert info_embed is not None
    
    def test_embed_builder_player_management_workflow(self):
        """Test player management command embed workflow."""
        # List players
        players_embed = EmbedBuilder.players_list_embed(["Alice", "Bob"])
        assert players_embed is not None
        
        # Kick action
        action_embed = EmbedBuilder.admin_action_embed(
            action="Player Kicked",
            player="Bob",
            moderator="Admin",
            reason="Spamming"
        )
        assert action_embed is not None
    
    def test_embed_builder_rate_limit_workflow(self):
        """Test rate limit error workflow."""
        # First command succeeds
        info_embed = EmbedBuilder.info_embed("Status", "OK")
        assert info_embed is not None
        
        # Second command hits rate limit
        cooldown_embed = EmbedBuilder.cooldown_embed(15.0)
        assert cooldown_embed is not None
        assert "15.0" in cooldown_embed.description
    
    def test_embed_builder_broadcast_workflow(self):
        """Test broadcast command embed workflow."""
        embed = EmbedBuilder.info_embed(
            "📢 Broadcast Sent",
            "Message: _Server maintenance in 5 minutes_\n\nAll online players have been notified."
        )
        
        assert embed is not None
        assert "Broadcast" in embed.title
        assert "maintenance" in embed.description.lower()
    
    def test_embed_builder_save_workflow(self):
        """Test save command embed workflow."""
        embed = EmbedBuilder.info_embed(
            "💾 Game Saved",
            "Save name: **autosave1**\n\nGame has been saved successfully."
        )
        
        assert embed is not None
        assert "Saved" in embed.title


class TestEmbedBuilderEdgeCases:
    """Test edge cases and error handling."""
    
    def test_embed_with_unicode(self):
        """Embeds handle unicode characters."""
        embed = EmbedBuilder.info_embed(
            "🐛 émojis & spëcial çhars",
            "Unicode: ñ, ü, ö, 中文, 日本語"
        )
        
        assert embed is not None
        assert "émojis" in embed.title
    
    def test_embed_with_code_blocks(self):
        """Embeds handle code block formatting."""
        embed = EmbedBuilder.error_embed(
            "```Error in code\nLine 1\nLine 2\n```"
        )
        
        assert embed is not None
    
    def test_embed_with_markdown(self):
        """Embeds preserve markdown formatting."""
        embed = EmbedBuilder.info_embed(
            "Title",
            "**Bold** *italic* __underline__ ~~strikethrough~~"
        )
        
        assert embed is not None
        assert "**Bold**" in embed.description
    
    def test_embed_colors_are_valid_hex(self):
        """All color constants are valid hex values."""
        colors = [
            EmbedBuilder.COLOR_SUCCESS,
            EmbedBuilder.COLOR_INFO,
            EmbedBuilder.COLOR_WARNING,
            EmbedBuilder.COLOR_ERROR,
            EmbedBuilder.COLOR_ADMIN,
            EmbedBuilder.COLOR_FACTORIO,
        ]
        
        for color in colors:
            assert isinstance(color, int)
            assert 0 <= color <= 0xFFFFFF  # Valid 24-bit color
    
    def test_embed_timestamp_is_utc(self):
        """All embeds have UTC timestamps."""
        embed = EmbedBuilder.create_base_embed(title="Test")
        
        assert embed.timestamp is not None
        # discord.utils.utcnow() returns timezone-aware UTC
        assert embed.timestamp.tzinfo is not None or embed.timestamp.tzinfo == timezone.utc


if __name__ == "__main__":
    pytest.main(["-v", __file__, "-s"])
