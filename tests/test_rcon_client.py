"""
Comprehensive pytest test suite for rcon_client.py
Tests RCON client, stats collector, and error handling with mocked connections.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

# Setup path before imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Import classes
from rcon_client import RconClient, RconStatsCollector


@pytest.mark.asyncio
class TestRconClientInitialization:
    """Test RconClient initialization."""
    
    async def test_init_success_with_rcon(self):
        """Test successful initialization when rcon is available."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            client = RconClient(
                host="localhost",
                port=27015,
                password="test123"
            )
            
            assert client.host == "localhost"
            assert client.port == 27015
            assert client.password == "test123"
            assert client.timeout == 5.0
            assert client.client is None
            assert client.connected is False
    
    async def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            client = RconClient(
                host="localhost",
                port=27015,
                password="test123",
                timeout=10.0
            )
            
            assert client.timeout == 10.0
    
    async def test_init_fails_without_rcon(self):
        """Test initialization raises ImportError when rcon unavailable."""
        with patch("rcon_client.RCON_AVAILABLE", False):
            with pytest.raises(ImportError, match="rcon package not installed"):
                RconClient(
                    host="localhost",
                    port=27015,
                    password="test123"
                )


@pytest.mark.asyncio
class TestRconClientConnection:
    """Test RconClient connection and disconnection."""
    
    async def test_connect_success(self):
        """Test successful RCON connection."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                # Mock RCON instance
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                assert client.connected is True
                assert client.client is not None
                mock_rcon_instance.connect.assert_called_once()
    
    async def test_connect_failure(self):
        """Test connection failure handling."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                # Mock RCON to raise connection error
                MockRCONClient.side_effect = ConnectionError("Connection refused")
                
                client = RconClient("localhost", 27015, "test123")
                
                with pytest.raises(ConnectionError):
                    await client.connect()
                
                assert client.connected is False
    
    async def test_connect_with_rcon_none(self):
        """Test connect raises when RCONClient is None."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient", None):
                client = RconClient.__new__(RconClient)
                client.host = "localhost"
                client.port = 27015
                client.password = "test123"
                client.timeout = 5.0
                client.client = None
                client.connected = False
                
                with pytest.raises(ImportError, match="rcon not available"):
                    await client.connect()
    
    async def test_disconnect_success(self):
        """Test successful disconnection."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.close = MagicMock()
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                await client.disconnect()
                
                assert client.connected is False
                mock_rcon_instance.close.assert_called_once()
    
    async def test_disconnect_with_error(self):
        """Test disconnection handles errors gracefully."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.close = MagicMock(side_effect=Exception("Close failed"))
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                # Should not raise, just log warning
                await client.disconnect()
    
    async def test_disconnect_when_not_connected(self):
        """Test disconnect when client is None."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            client = RconClient("localhost", 27015, "test123")
            
            # Should not raise
            await client.disconnect()


@pytest.mark.asyncio
class TestRconClientCommands:
    """Test RCON command execution."""
    
    async def test_execute_success(self):
        """Test successful command execution."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(return_value="Command response")
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                response = await client.execute("/time")
                
                assert response == "Command response"
                mock_rcon_instance.run.assert_called_once_with("/time")
    
    async def test_execute_not_connected(self):
        """Test execute raises when not connected."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            client = RconClient("localhost", 27015, "test123")
            
            with pytest.raises(ConnectionError, match="RCON not connected"):
                await client.execute("/time")
    
    async def test_execute_timeout(self):
        """Test command timeout handling."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(side_effect=asyncio.TimeoutError())
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                with pytest.raises(TimeoutError, match="RCON command timed out"):
                    await client.execute("/slow-command")
    
    async def test_execute_generic_error(self):
        """Test generic command execution error."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(side_effect=Exception("Command failed"))
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                with pytest.raises(Exception, match="Command failed"):
                    await client.execute("/bad-command")


@pytest.mark.asyncio
class TestRconClientQueries:
    """Test high-level RCON query methods."""
    
    async def test_get_player_count_success(self):
        """Test successful player count query."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(return_value="Online players (3):")
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                count = await client.get_player_count()
                
                assert count == 3
    
    async def test_get_player_count_zero(self):
        """Test player count when no players online."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(return_value="No players online")
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                count = await client.get_player_count()
                
                assert count == 0
    
    async def test_get_player_count_error(self):
        """Test player count returns -1 on error."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(side_effect=Exception("Query failed"))
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                count = await client.get_player_count()
                
                assert count == -1
    
    async def test_get_players_online_success(self):
        """Test successful player list query."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(
                    return_value="Online players (2):\n  PlayerOne\n  PlayerTwo"
                )
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                players = await client.get_players_online()
                
                assert len(players) == 2
                assert "PlayerOne" in players
                assert "PlayerTwo" in players
    
    async def test_get_players_online_empty(self):
        """Test player list when no players online."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(return_value="Online players (0):")
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                players = await client.get_players_online()
                
                assert players == []
    
    async def test_get_players_online_error(self):
        """Test player list returns empty on error."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(side_effect=Exception("Query failed"))
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                players = await client.get_players_online()
                
                assert players == []
    
    async def test_get_server_time_success(self):
        """Test successful server time query."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(return_value="  Day 42, 13:45  ")
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                time = await client.get_server_time()
                
                assert time == "Day 42, 13:45"
    
    async def test_get_server_time_error(self):
        """Test server time returns Unknown on error."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            with patch("rcon_client.RCONClient") as MockRCONClient:
                mock_rcon_instance = MagicMock()
                mock_rcon_instance.connect = MagicMock()
                mock_rcon_instance.run = MagicMock(side_effect=Exception("Query failed"))
                MockRCONClient.return_value = mock_rcon_instance
                
                client = RconClient("localhost", 27015, "test123")
                await client.connect()
                
                time = await client.get_server_time()
                
                assert time == "Unknown"


@pytest.mark.asyncio
class TestRconStatsCollector:
    """Test RconStatsCollector functionality."""
    
    async def test_init(self):
        """Test stats collector initialization."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            mock_rcon_client = MagicMock(spec=RconClient)
            mock_discord_client = MagicMock()
            
            collector = RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_client=mock_discord_client,
                interval=300
            )
            
            assert collector.rcon_client is mock_rcon_client
            assert collector.discord_client is mock_discord_client
            assert collector.interval == 300
            assert collector.running is False
            assert collector.task is None
    
    async def test_start(self):
        """Test starting stats collection."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            mock_rcon_client = MagicMock(spec=RconClient)
            mock_discord_client = MagicMock()
            
            collector = RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_client=mock_discord_client,
                interval=1
            )
            
            await collector.start()
            
            assert collector.running is True
            assert collector.task is not None
            
            # Clean up
            await collector.stop()
    
    async def test_stop(self):
        """Test stopping stats collection."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            mock_rcon_client = MagicMock(spec=RconClient)
            mock_discord_client = MagicMock()
            
            collector = RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_client=mock_discord_client,
                interval=1
            )
            
            await collector.start()
            await collector.stop()
            
            assert collector.running is False
    
    async def test_format_stats_with_players(self):
        """Test stats formatting with players."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            mock_rcon_client = MagicMock(spec=RconClient)
            mock_discord_client = MagicMock()
            
            collector = RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_client=mock_discord_client,
                interval=1
            )
            
            message = collector._format_stats(
                player_count=2,
                players=["Alice", "Bob"],
                server_time="Day 10, 12:00"
            )
            
            assert "📊 **Server Status**" in message
            assert "👥 Players Online: 2" in message
            assert "📝 Alice, Bob" in message
            assert "⏰ Game Time: Day 10, 12:00" in message
    
    async def test_format_stats_no_players(self):
        """Test stats formatting with no players."""
        with patch("rcon_client.RCON_AVAILABLE", True):
            mock_rcon_client = MagicMock(spec=RconClient)
            mock_discord_client = MagicMock()
            
            collector = RconStatsCollector(
                rcon_client=mock_rcon_client,
                discord_client=mock_discord_client,
                interval=1
            )
            
            message = collector._format_stats(
                player_count=0,
                players=[],
                server_time="Day 1, 00:00"
            )
            
            assert "📊 **Server Status**" in message
            assert "👥 Players Online: 0" in message
            assert "📝" not in message  # No player list
            assert "⏰ Game Time: Day 1, 00:00" in message


# Run coverage report
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=rcon_client", "--cov-report=term-missing"])
