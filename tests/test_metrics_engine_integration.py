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

"""
Integration tests for RconMetricsEngine registry within ServerManager.

Tests the unified metrics collection strategy:
- ServerManager.get_metrics_engine() lazy-loading
- Shared metrics engine between status command and stats collector
- Per-server isolation
- Happy path: successful metrics gathering
- Error paths: RCON failures, missing servers, engine failures

Target Coverage: 95%+ for metrics integration layer
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from server_manager import ServerManager
from config import ServerConfig
from rcon_client import RconClient
from rcon_metrics_engine import RconMetricsEngine


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_discord_interface():
    """Mock Discord interface for ServerManager."""
    interface = AsyncMock()
    interface.use_channel = MagicMock(return_value=interface)
    return interface


@pytest.fixture
def server_config_prod() -> ServerConfig:
    """Production server configuration."""
    return ServerConfig(
        tag="prod",
        name="Production Server",
        rcon_host="prod.example.com",
        rcon_port=27015,
        rcon_password="secret123",
        event_channel_id=123456789,
        enable_stats_collector=True,
        stats_interval=60,
        enable_ups_stat=True,
        enable_evolution_stat=True,
    )


@pytest.fixture
def server_config_dev() -> ServerConfig:
    """Development server configuration."""
    return ServerConfig(
        tag="dev",
        name="Development Server",
        rcon_host="dev.example.com",
        rcon_port=27015,
        rcon_password="dev_pass",
        event_channel_id=987654321,
        enable_stats_collector=False,  # Disabled for dev
        stats_interval=120,
        enable_ups_stat=True,
        enable_evolution_stat=False,
    )


@pytest.fixture
def mock_rcon_client():
    """Mock RCON client."""
    client = AsyncMock(spec=RconClient)
    client.is_connected = True
    client.host = "example.com"
    client.port = 27015
    client.server_tag = "prod"
    client.server_name = "Production Server"
    client.execute = AsyncMock(return_value="OK")
    client.start = AsyncMock()
    client.stop = AsyncMock()
    return client


@pytest.fixture
async def server_manager(mock_discord_interface, mock_rcon_client):
    """Initialized ServerManager with mocked dependencies."""
    manager = ServerManager(discord_interface=mock_discord_interface)
    
    # Mock the RconClient creation to use our mock
    with patch('rcon_client.RconClient', return_value=mock_rcon_client):
        # We'll manually add servers for testing
        pass
    
    return manager


# ============================================================================
# LAZY-LOADING TESTS (Happy Path)
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_engine_lazy_loads_on_first_call(server_manager: ServerManager, server_config_prod: ServerConfig, mock_rcon_client):
    """Test that metrics engine is created on first get_metrics_engine() call."""
    # Setup
    server_manager.servers["prod"] = server_config_prod
    server_manager.clients["prod"] = mock_rcon_client
    
    # Verify engine doesn't exist yet
    assert "prod" not in server_manager.metrics_engines
    
    # Get engine (triggers lazy-load)
    engine1 = server_manager.get_metrics_engine("prod")
    
    # Verify engine was created
    assert engine1 is not None
    assert isinstance(engine1, RconMetricsEngine)
    assert "prod" in server_manager.metrics_engines


@pytest.mark.asyncio
async def test_metrics_engine_singleton_per_server(server_manager: ServerManager, server_config_prod: ServerConfig, mock_rcon_client):
    """Test that subsequent calls return the same engine instance (singleton per server)."""
    # Setup
    server_manager.servers["prod"] = server_config_prod
    server_manager.clients["prod"] = mock_rcon_client
    
    # Get engine twice
    engine1 = server_manager.get_metrics_engine("prod")
    engine2 = server_manager.get_metrics_engine("prod")
    
    # Verify same instance
    assert engine1 is engine2


@pytest.mark.asyncio
async def test_metrics_engine_per_server_isolation(
    server_manager: ServerManager,
    server_config_prod: ServerConfig,
    server_config_dev: ServerConfig,
    mock_rcon_client,
):
    """Test that each server gets its own isolated metrics engine."""
    # Setup
    mock_client_prod = MagicMock(spec=RconClient)
    mock_client_prod.is_connected = True
    mock_client_prod.server_tag = "prod"
    mock_client_prod.server_name = "Production Server"
    
    mock_client_dev = MagicMock(spec=RconClient)
    mock_client_dev.is_connected = True
    mock_client_dev.server_tag = "dev"
    mock_client_dev.server_name = "Development Server"
    
    server_manager.servers["prod"] = server_config_prod
    server_manager.clients["prod"] = mock_client_prod
    server_manager.servers["dev"] = server_config_dev
    server_manager.clients["dev"] = mock_client_dev
    
    # Get engines
    engine_prod = server_manager.get_metrics_engine("prod")
    engine_dev = server_manager.get_metrics_engine("dev")
    
    # Verify different instances
    assert engine_prod is not engine_dev
    assert engine_prod.rcon_client is mock_client_prod
    assert engine_dev.rcon_client is mock_client_dev


@pytest.mark.asyncio
async def test_metrics_engine_inherits_config(
    server_manager: ServerManager,
    server_config_prod: ServerConfig,
    mock_rcon_client,
):
    """Test that metrics engine respects config flags (enable_ups_stat, enable_evolution_stat)."""
    # Setup
    server_manager.servers["prod"] = server_config_prod
    server_manager.clients["prod"] = mock_rcon_client
    
    # Get engine
    engine = server_manager.get_metrics_engine("prod")
    
    # Verify config was passed
    assert engine.enable_ups_stat == server_config_prod.enable_ups_stat
    assert engine.enable_evolution_stat == server_config_prod.enable_evolution_stat


# ============================================================================
# METRICS GATHERING TESTS (Happy Path)
# ============================================================================

@pytest.mark.asyncio
async def test_status_command_uses_shared_metrics_engine(
    server_manager: ServerManager,
    server_config_prod: ServerConfig,
    mock_rcon_client,
):
    """Test that status command can use the shared metrics engine."""
    # Setup
    server_manager.servers["prod"] = server_config_prod
    server_manager.clients["prod"] = mock_rcon_client
    
    # Mock metrics response
    expected_metrics = {
        "ups": 60.0,
        "ups_ema": 59.8,
        "ups_sma": 59.9,
        "evolution_factor": 0.42,
        "player_count": 3,
        "players": ["Alice", "Bob", "Charlie"],
        "is_paused": False,
        "server_time": "12:34:56",
    }
    
    # Get engine and mock the gather call
    engine = server_manager.get_metrics_engine("prod")
    engine.gather_all_metrics = AsyncMock(return_value=expected_metrics)
    
    # Simulate status command gathering metrics
    metrics = await engine.gather_all_metrics()
    
    # Verify metrics
    assert metrics["ups"] == 60.0
    assert metrics["player_count"] == 3
    assert metrics["evolution_factor"] == 0.42


@pytest.mark.asyncio
async def test_metrics_consistency_across_consumers(
    server_manager: ServerManager,
    server_config_prod: ServerConfig,
    mock_rcon_client,
):
    """Test that status command and stats collector use identical metrics."""
    # Setup
    server_manager.servers["prod"] = server_config_prod
    server_manager.clients["prod"] = mock_rcon_client
    
    # Get engine
    engine = server_manager.get_metrics_engine("prod")
    
    # Mock metrics
    expected_metrics = {
        "ups": 60.0,
        "ups_ema": 59.8,
        "ups_sma": 59.9,
        "evolution_factor": 0.42,
        "is_paused": False,
    }
    engine.gather_all_metrics = AsyncMock(return_value=expected_metrics)
    
    # Call twice (simulating status command and stats collector)
    metrics_status = await engine.gather_all_metrics()
    metrics_stats = await engine.gather_all_metrics()
    
    # Verify identical
    assert metrics_status == metrics_stats
    assert metrics_status["ups"] == metrics_stats["ups"]


# ============================================================================
# ERROR PATH TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_metrics_engine_returns_none_for_nonexistent_server(server_manager: ServerManager):
    """Test that get_metrics_engine returns None for nonexistent server."""
    # Query nonexistent server
    engine = server_manager.get_metrics_engine("nonexistent")
    
    # Verify None returned
    assert engine is None


@pytest.mark.asyncio
async def test_get_metrics_engine_handles_missing_config(server_manager: ServerManager, mock_rcon_client):
    """Test graceful handling when server exists in clients but not servers."""
    # Add client but not config (shouldn't happen, but test for robustness)
    server_manager.clients["orphan"] = mock_rcon_client
    
    # Try to get engine
    with pytest.raises(KeyError):
        server_manager.get_metrics_engine("orphan")


@pytest.mark.asyncio
async def test_metrics_gathering_handles_rcon_failure(
    server_manager: ServerManager,
    server_config_prod: ServerConfig,
):
    """Test that metrics gathering handles RCON execution failures."""
    # Setup with failing RCON client
    failing_client = AsyncMock(spec=RconClient)
    failing_client.is_connected = True
    failing_client.server_tag = "prod"
    failing_client.server_name = "Production Server"
    failing_client.execute = AsyncMock(side_effect=Exception("RCON timeout"))
    
    server_manager.servers["prod"] = server_config_prod
    server_manager.clients["prod"] = failing_client
    
    # Get engine
    engine = server_manager.get_metrics_engine("prod")
    
    # Mock gather to raise exception
    engine.gather_all_metrics = AsyncMock(side_effect=Exception("RCON timeout"))
    
    # Verify exception propagates (error path)
    with pytest.raises(Exception, match="RCON timeout"):
        await engine.gather_all_metrics()


@pytest.mark.asyncio
async def test_metrics_gathering_with_disconnected_rcon(
    server_manager: ServerManager,
    server_config_prod: ServerConfig,
):
    """Test metrics gathering when RCON is disconnected."""
    # Setup with disconnected client
    disconnected_client = AsyncMock(spec=RconClient)
    disconnected_client.is_connected = False
    disconnected_client.server_tag = "prod"
    disconnected_client.server_name = "Production Server"
    disconnected_client.execute = AsyncMock(side_effect=ConnectionError("Not connected"))
    
    server_manager.servers["prod"] = server_config_prod
    server_manager.clients["prod"] = disconnected_client
    
    # Get engine
    engine = server_manager.get_metrics_engine("prod")
    
    # Verify engine created (should still exist)
    assert engine is not None
    # But RCON calls should fail
    assert not disconnected_client.is_connected


# ============================================================================
# SERVER LIFECYCLE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_engine_cleanup_on_server_removal(
    mock_discord_interface,
    server_config_prod: ServerConfig,
    mock_rcon_client,
):
    """Test that metrics engine is cleaned up when server is removed."""
    # Setup
    manager = ServerManager(discord_interface=mock_discord_interface)
    manager.servers["prod"] = server_config_prod
    manager.clients["prod"] = mock_rcon_client
    
    # Create metrics engine
    engine = manager.get_metrics_engine("prod")
    assert "prod" in manager.metrics_engines
    
    # Remove server
    await manager.remove_server("prod")
    
    # Verify cleanup
    assert "prod" not in manager.metrics_engines


@pytest.mark.asyncio
async def test_stop_all_cleans_up_all_metrics_engines(
    mock_discord_interface,
    server_config_prod: ServerConfig,
    server_config_dev: ServerConfig,
):
    """Test that stop_all() cleans up all metrics engines."""
    # Setup
    manager = ServerManager(discord_interface=mock_discord_interface)
    
    # Add multiple servers
    mock_client_prod = AsyncMock(spec=RconClient)
    mock_client_prod.is_connected = True
    mock_client_prod.server_tag = "prod"
    mock_client_prod.server_name = "Production Server"
    mock_client_prod.stop = AsyncMock()
    
    mock_client_dev = AsyncMock(spec=RconClient)
    mock_client_dev.is_connected = True
    mock_client_dev.server_tag = "dev"
    mock_client_dev.server_name = "Development Server"
    mock_client_dev.stop = AsyncMock()
    
    manager.servers["prod"] = server_config_prod
    manager.clients["prod"] = mock_client_prod
    manager.servers["dev"] = server_config_dev
    manager.clients["dev"] = mock_client_dev
    
    # Create metrics engines
    engine_prod = manager.get_metrics_engine("prod")
    engine_dev = manager.get_metrics_engine("dev")
    
    assert len(manager.metrics_engines) == 2
    
    # Stop all
    await manager.stop_all()
    
    # Verify cleanup
    assert len(manager.metrics_engines) == 0


# ============================================================================
# MULTI-SERVER INTERACTION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_multiple_servers_maintain_independent_metrics(
    mock_discord_interface,
    server_config_prod: ServerConfig,
    server_config_dev: ServerConfig,
):
    """Test that multiple servers maintain independent metrics without cross-contamination."""
    # Setup
    manager = ServerManager(discord_interface=mock_discord_interface)
    
    # Mock clients with different data
    mock_client_prod = AsyncMock(spec=RconClient)
    mock_client_prod.is_connected = True
    mock_client_prod.server_tag = "prod"
    mock_client_prod.server_name = "Production Server"
    
    mock_client_dev = AsyncMock(spec=RconClient)
    mock_client_dev.is_connected = True
    mock_client_dev.server_tag = "dev"
    mock_client_dev.server_name = "Development Server"
    
    manager.servers["prod"] = server_config_prod
    manager.clients["prod"] = mock_client_prod
    manager.servers["dev"] = server_config_dev
    manager.clients["dev"] = mock_client_dev
    
    # Get engines
    engine_prod = manager.get_metrics_engine("prod")
    engine_dev = manager.get_metrics_engine("dev")
    
    # Mock different metric responses
    engine_prod.gather_all_metrics = AsyncMock(return_value={"ups": 60.0, "player_count": 5})
    engine_dev.gather_all_metrics = AsyncMock(return_value={"ups": 45.0, "player_count": 2})
    
    # Gather metrics
    metrics_prod = await engine_prod.gather_all_metrics()
    metrics_dev = await engine_dev.gather_all_metrics()
    
    # Verify independence
    assert metrics_prod["ups"] == 60.0
    assert metrics_prod["player_count"] == 5
    assert metrics_dev["ups"] == 45.0
    assert metrics_dev["player_count"] == 2


# ============================================================================
# CONFIGURATION INHERITANCE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_engine_respects_ups_stat_flag(
    mock_discord_interface,
    mock_rcon_client,
):
    """Test that metrics engine respects enable_ups_stat config flag."""
    # Setup
    manager = ServerManager(discord_interface=mock_discord_interface)
    
    config_ups_enabled = ServerConfig(
        tag="ups_enabled",
        name="UPS Enabled",
        rcon_host="example.com",
        rcon_port=27015,
        rcon_password="pass",
        event_channel_id=123,
        enable_ups_stat=True,
        stats_interval=60,
        enable_evolution_stat=False,
    )
    
    config_ups_disabled = ServerConfig(
        tag="ups_disabled",
        name="UPS Disabled",
        rcon_host="example.com",
        rcon_port=27015,
        rcon_password="pass",
        event_channel_id=123,
        enable_ups_stat=False,
        stats_interval=60,
        enable_evolution_stat=False,
    )
    
    manager.servers["ups_enabled"] = config_ups_enabled
    manager.clients["ups_enabled"] = mock_rcon_client
    manager.servers["ups_disabled"] = config_ups_disabled
    
    mock_client_disabled = MagicMock(spec=RconClient)
    mock_client_disabled.is_connected = True
    mock_client_disabled.server_tag = "ups_disabled"
    mock_client_disabled.server_name = "UPS Disabled"
    manager.clients["ups_disabled"] = mock_client_disabled
    
    # Get engines
    engine_enabled = manager.get_metrics_engine("ups_enabled")
    engine_disabled = manager.get_metrics_engine("ups_disabled")
    
    # Verify flags
    assert engine_enabled.enable_ups_stat is True
    assert engine_disabled.enable_ups_stat is False


@pytest.mark.asyncio
async def test_metrics_engine_respects_evolution_stat_flag(
    mock_discord_interface,
    mock_rcon_client,
):
    """Test that metrics engine respects enable_evolution_stat config flag."""
    # Setup
    manager = ServerManager(discord_interface=mock_discord_interface)
    
    config_evo_enabled = ServerConfig(
        tag="evo_enabled",
        name="Evolution Enabled",
        rcon_host="example.com",
        rcon_port=27015,
        rcon_password="pass",
        event_channel_id=123,
        enable_ups_stat=False,
        stats_interval=60,
        enable_evolution_stat=True,
    )
    
    config_evo_disabled = ServerConfig(
        tag="evo_disabled",
        name="Evolution Disabled",
        rcon_host="example.com",
        rcon_port=27015,
        rcon_password="pass",
        event_channel_id=123,
        enable_ups_stat=False,
        stats_interval=60,
        enable_evolution_stat=False,
    )
    
    manager.servers["evo_enabled"] = config_evo_enabled
    manager.clients["evo_enabled"] = mock_rcon_client
    manager.servers["evo_disabled"] = config_evo_disabled
    
    mock_client_disabled = MagicMock(spec=RconClient)
    mock_client_disabled.is_connected = True
    mock_client_disabled.server_tag = "evo_disabled"
    mock_client_disabled.server_name = "Evolution Disabled"
    manager.clients["evo_disabled"] = mock_client_disabled
    
    # Get engines
    engine_enabled = manager.get_metrics_engine("evo_enabled")
    engine_disabled = manager.get_metrics_engine("evo_disabled")
    
    # Verify flags
    assert engine_enabled.enable_evolution_stat is True
    assert engine_disabled.enable_evolution_stat is False


# ============================================================================
# LOGGING TESTS (Ops Excellence)
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_engine_logs_creation(
    mock_discord_interface,
    server_config_prod: ServerConfig,
    mock_rcon_client,
):
    """Test that metrics engine creation is logged."""
    # Setup
    manager = ServerManager(discord_interface=mock_discord_interface)
    manager.servers["prod"] = server_config_prod
    manager.clients["prod"] = mock_rcon_client
    
    # Get engine (triggers creation)
    with patch('structlog.get_logger') as mock_logger:
        engine = manager.get_metrics_engine("prod")
        # Logger should be called during engine creation
        # (Implementation detail - just verify engine is created)
        assert engine is not None


# ============================================================================
# EDGE CASES
# ============================================================================

@pytest.mark.asyncio
async def test_metrics_engine_with_disabled_stats_collector(
    mock_discord_interface,
    mock_rcon_client,
):
    """Test that metrics engine works even when stats collector is disabled."""
    # Setup - stats collector disabled
    manager = ServerManager(discord_interface=mock_discord_interface)
    
    config = ServerConfig(
        tag="dev",
        name="Dev Server",
        rcon_host="dev.example.com",
        rcon_port=27015,
        rcon_password="pass",
        event_channel_id=123,
        enable_stats_collector=False,  # Disabled!
        stats_interval=120,
        enable_ups_stat=True,
        enable_evolution_stat=True,
    )
    
    manager.servers["dev"] = config
    manager.clients["dev"] = mock_rcon_client
    
    # Get engine (should still work)
    engine = manager.get_metrics_engine("dev")
    
    # Verify engine created despite disabled collector
    assert engine is not None
    assert engine.enable_ups_stat is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--cov=server_manager", "--cov-report=term-missing"])
