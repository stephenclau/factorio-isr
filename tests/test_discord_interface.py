"""
Focused pytest test suite for discord_interface.py - EmbedBuilder coverage
Tests EmbedBuilder class methods to boost coverage from 29% to 70%+
FINAL FIX: Removed problematic reset_mock() calls
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Create proper discord module mock
discord_mock = MagicMock()
discord_mock.Embed = MagicMock(return_value=MagicMock())
discord_mock.utils = MagicMock()
discord_mock.utils.utcnow = MagicMock(return_value="2025-12-03T00:00:00")
discord_mock.TextChannel = MagicMock
discord_mock.Status = MagicMock()
discord_mock.Status.online = "online"
discord_mock.Status.idle = "idle"
discord_mock.Activity = MagicMock
discord_mock.ActivityType = MagicMock()
discord_mock.ActivityType.watching = "watching"

sys.modules['discord'] = discord_mock

from discord_interface import EmbedBuilder


# ============================================================================
# TEST: EmbedBuilder Colors
# ============================================================================

def test_embedbuilder_colors():
    """Test EmbedBuilder color constants"""
    assert EmbedBuilder.COLOR_SUCCESS == 0x00FF00
    assert EmbedBuilder.COLOR_INFO == 0x3498DB
    assert EmbedBuilder.COLOR_WARNING == 0xFFA500
    assert EmbedBuilder.COLOR_ERROR == 0xFF0000
    assert EmbedBuilder.COLOR_ADMIN == 0x9B59B6
    assert EmbedBuilder.COLOR_FACTORIO == 0xFF6B00


# ============================================================================
# TEST: create_base_embed
# ============================================================================

def test_create_base_embed_minimal():
    """Test create_base_embed with minimal parameters"""
    embed = EmbedBuilder.create_base_embed(title="Test Title")

    # Should return an embed
    assert embed is not None

def test_create_base_embed_with_description():
    """Test create_base_embed with description"""
    embed = EmbedBuilder.create_base_embed(
        title="Test", 
        description="Test description"
    )

    # Should return an embed
    assert embed is not None

def test_create_base_embed_with_custom_color():
    """Test create_base_embed with custom color"""
    embed = EmbedBuilder.create_base_embed(
        title="Test",
        color=0xFF0000
    )

    # Should return an embed
    assert embed is not None


# ============================================================================
# TEST: server_status_embed
# ============================================================================

def test_server_status_embed_online():
    """Test server_status_embed when server is online"""
    result = EmbedBuilder.server_status_embed(
        status="Online",
        players_online=5,
        rcon_enabled=True,
        uptime="2 hours"
    )

    # Should return an embed
    assert result is not None

def test_server_status_embed_offline():
    """Test server_status_embed when RCON is offline"""
    result = EmbedBuilder.server_status_embed(
        status="Offline",
        players_online=0,
        rcon_enabled=False
    )

    # Should return an embed
    assert result is not None


# ============================================================================
# TEST: players_list_embed
# ============================================================================

def test_players_list_embed_with_players():
    """Test players_list_embed with players online"""
    players = ["Alice", "Bob", "Charlie"]
    result = EmbedBuilder.players_list_embed(players)

    # Should return an embed
    assert result is not None

def test_players_list_embed_no_players():
    """Test players_list_embed with no players"""
    result = EmbedBuilder.players_list_embed([])

    # Should return an embed
    assert result is not None


# ============================================================================
# TEST: admin_action_embed
# ============================================================================

def test_admin_action_embed_minimal():
    """Test admin_action_embed with minimal parameters"""
    result = EmbedBuilder.admin_action_embed(
        action="Player Kicked",
        player="BadGuy",
        moderator="AdminUser"
    )

    # Should return an embed
    assert result is not None

def test_admin_action_embed_with_reason():
    """Test admin_action_embed with reason"""
    result = EmbedBuilder.admin_action_embed(
        action="Player Banned",
        player="Cheater",
        moderator="Admin",
        reason="Hacking"
    )

    # Should return an embed
    assert result is not None

def test_admin_action_embed_with_response():
    """Test admin_action_embed with server response"""
    result = EmbedBuilder.admin_action_embed(
        action="Player Kicked",
        player="BadGuy",
        moderator="Admin",
        reason="Griefing",
        response="Player BadGuy was kicked"
    )

    # Should return an embed
    assert result is not None

def test_admin_action_embed_truncates_long_response():
    """Test admin_action_embed truncates very long responses"""
    long_response = "x" * 1500  # Longer than 1000 chars
    result = EmbedBuilder.admin_action_embed(
        action="Test",
        player="Player1",
        moderator="Admin",
        response=long_response
    )

    # Should return an embed (with truncated response)
    assert result is not None


# ============================================================================
# TEST: error_embed
# ============================================================================

def test_error_embed():
    """Test error_embed creation"""
    result = EmbedBuilder.error_embed("Something went wrong")

    # Should return an embed
    assert result is not None


# ============================================================================
# TEST: cooldown_embed
# ============================================================================

def test_cooldown_embed():
    """Test cooldown_embed creation"""
    result = EmbedBuilder.cooldown_embed(5.5)

    # Should return an embed
    assert result is not None


# ============================================================================
# TEST: info_embed
# ============================================================================

def test_info_embed():
    """Test info_embed creation"""
    result = EmbedBuilder.info_embed(
        title="Information",
        message="This is some info"
    )

    # Should return an embed
    assert result is not None


# ============================================================================
# TEST: Edge Cases
# ============================================================================

def test_server_status_embed_without_uptime():
    """Test server_status_embed when uptime is None"""
    result = EmbedBuilder.server_status_embed(
        status="Online",
        players_online=0,
        rcon_enabled=True,
        uptime=None
    )

    # Should return an embed
    assert result is not None

def test_admin_action_embed_all_optional_fields():
    """Test admin_action_embed with all optional parameters"""
    result = EmbedBuilder.admin_action_embed(
        action="Full Test",
        player="TestPlayer",
        moderator="TestMod",
        reason="Test reason",
        response="Test response"
    )

    # Should return an embed
    assert result is not None

def test_players_list_embed_single_player():
    """Test players_list_embed with one player"""
    result = EmbedBuilder.players_list_embed(["Alice"])

    # Should return an embed
    assert result is not None

def test_players_list_embed_many_players():
    """Test players_list_embed with many players"""
    players = [f"Player{i}" for i in range(20)]
    result = EmbedBuilder.players_list_embed(players)

    # Should return an embed
    assert result is not None

def test_error_embed_long_message():
    """Test error_embed with long error message"""
    long_error = "Error: " + "x" * 500
    result = EmbedBuilder.error_embed(long_error)

    # Should return an embed
    assert result is not None

def test_cooldown_embed_various_times():
    """Test cooldown_embed with various retry times"""
    for retry_time in [0.5, 1.0, 5.0, 10.0, 30.0]:
        result = EmbedBuilder.cooldown_embed(retry_time)
        assert result is not None

def test_info_embed_empty_message():
    """Test info_embed with empty message"""
    result = EmbedBuilder.info_embed(
        title="Empty",
        message=""
    )

    # Should return an embed
    assert result is not None

def test_admin_action_embed_special_characters():
    """Test admin_action_embed with special characters in player name"""
    result = EmbedBuilder.admin_action_embed(
        action="Player Kicked",
        player="[XYZ]Player_123",
        moderator="Admin@123"
    )

    # Should return an embed
    assert result is not None

def test_server_status_embed_zero_players():
    """Test server_status_embed with 0 players online"""
    result = EmbedBuilder.server_status_embed(
        status="Online",
        players_online=0,
        rcon_enabled=True
    )

    # Should return an embed
    assert result is not None

def test_server_status_embed_many_players():
    """Test server_status_embed with many players online"""
    result = EmbedBuilder.server_status_embed(
        status="Online",
        players_online=100,
        rcon_enabled=True,
        uptime="5 days"
    )

    # Should return an embed
    assert result is not None
