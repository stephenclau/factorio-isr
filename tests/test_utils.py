"""
Unit tests for utils package.

Tests framework-agnostic utilities that can be used by any component.
"""

import pytest
import time
from utils.rate_limiting import CommandCooldown, QUERY_COOLDOWN
from utils.multi_server import ServerConfig, MultiServerManager


# ============================================================================
# Test CommandCooldown
# ============================================================================

class TestCommandCooldown:
    """Test rate limiting functionality."""

    def test_cooldown_initialization(self):
        """Test cooldown initializes correctly."""
        cooldown = CommandCooldown(rate=3, per=60.0)
        assert cooldown.rate == 3
        assert cooldown.per == 60.0

    def test_not_rate_limited_first_use(self):
        """Test first use is not rate limited."""
        cooldown = CommandCooldown(rate=3, per=60.0)
        is_limited, retry_after = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is False
        assert retry_after == 0.0

    def test_rate_limited_after_max_uses(self):
        """Test rate limiting after max uses."""
        cooldown = CommandCooldown(rate=3, per=60.0)

        # Use 3 times (at limit)
        for _ in range(3):
            is_limited, _ = cooldown.is_rate_limited(identifier=12345)
            assert is_limited is False

        # 4th use should be rate limited
        is_limited, retry_after = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is True
        assert retry_after > 0

    def test_cooldown_per_identifier(self):
        """Test cooldowns are per-identifier."""
        cooldown = CommandCooldown(rate=2, per=60.0)

        # Identifier 111 uses twice
        cooldown.is_rate_limited(identifier=111)
        cooldown.is_rate_limited(identifier=111)

        # Identifier 222 should not be rate limited
        is_limited, _ = cooldown.is_rate_limited(identifier=222)
        assert is_limited is False

    def test_cooldown_reset(self):
        """Test manual cooldown reset."""
        cooldown = CommandCooldown(rate=1, per=60.0)

        cooldown.is_rate_limited(identifier=12345)

        # Should be rate limited
        is_limited, _ = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is True

        # Reset cooldown
        cooldown.reset(identifier=12345)

        # Should not be rate limited anymore
        is_limited, _ = cooldown.is_rate_limited(identifier=12345)
        assert is_limited is False

    def test_cooldown_reset_all(self):
        """Test resetting all cooldowns."""
        cooldown = CommandCooldown(rate=1, per=60.0)

        # Use for multiple identifiers
        cooldown.is_rate_limited(identifier=111)
        cooldown.is_rate_limited(identifier=222)
        cooldown.is_rate_limited(identifier=333)

        # Reset all
        cooldown.reset_all()

        # All should be reset
        is_limited, _ = cooldown.is_rate_limited(identifier=111)
        assert is_limited is False

    def test_get_usage(self):
        """Test getting current usage."""
        cooldown = CommandCooldown(rate=5, per=60.0)

        # No usage yet
        current, max_rate = cooldown.get_usage(identifier=12345)
        assert current == 0
        assert max_rate == 5

        # Use twice
        cooldown.is_rate_limited(identifier=12345)
        cooldown.is_rate_limited(identifier=12345)

        current, max_rate = cooldown.get_usage(identifier=12345)
        assert current == 2
        assert max_rate == 5

    def test_global_cooldown_instances(self):
        """Test pre-configured global instances."""
        assert QUERY_COOLDOWN.rate == 5
        assert QUERY_COOLDOWN.per == 30.0


# ============================================================================
# Test ServerConfig
# ============================================================================

class TestServerConfig:
    """Test server configuration."""

    def test_server_config_creation(self):
        """Test creating server config."""
        config = ServerConfig(
            server_id="test1",
            name="Test Server",
            host="localhost",
            port=27015,
            credentials="secret"
        )

        assert config.server_id == "test1"
        assert config.name == "Test Server"
        assert config.host == "localhost"
        assert config.port == 27015
        assert config.credentials == "secret"

    def test_server_config_with_metadata(self):
        """Test server config with metadata."""
        config = ServerConfig(
            server_id="test1",
            name="Test Server",
            host="localhost",
            port=27015,
            metadata={"region": "us-east", "tier": "production"}
        )

        assert config.metadata["region"] == "us-east"
        assert config.metadata["tier"] == "production"

    def test_server_config_validation(self):
        """Test server config validation."""
        with pytest.raises(ValueError, match="server_id cannot be empty"):
            ServerConfig(server_id="", name="Test", host="localhost", port=27015)

        with pytest.raises(ValueError, match="name cannot be empty"):
            ServerConfig(server_id="test", name="", host="localhost", port=27015)

        with pytest.raises(ValueError, match="host cannot be empty"):
            ServerConfig(server_id="test", name="Test", host="", port=27015)

        with pytest.raises(ValueError, match="Invalid port"):
            ServerConfig(server_id="test", name="Test", host="localhost", port=-1)

    def test_connection_string(self):
        """Test connection string generation."""
        config = ServerConfig(
            server_id="test1",
            name="Test Server",
            host="factorio.example.com",
            port=27015
        )

        assert config.connection_string() == "factorio.example.com:27015"


# ============================================================================
# Test MultiServerManager
# ============================================================================

class TestMultiServerManager:
    """Test multi-server management."""

    def test_manager_initialization(self):
        """Test manager initializes empty."""
        manager = MultiServerManager()
        assert manager.count() == 0
        assert manager.default_server is None

    def test_add_server(self):
        """Test adding a server."""
        manager = MultiServerManager()
        config = ServerConfig(
            server_id="test1",
            name="Test Server 1",
            host="localhost",
            port=27015
        )

        manager.add_server(config)

        assert manager.count() == 1
        assert manager.default_server == "test1"

    def test_add_duplicate_server(self):
        """Test adding duplicate server fails."""
        manager = MultiServerManager()
        config = ServerConfig(
            server_id="test1",
            name="Test Server",
            host="localhost",
            port=27015
        )

        manager.add_server(config)

        with pytest.raises(ValueError, match="already exists"):
            manager.add_server(config)

    def test_get_server(self):
        """Test getting server by ID."""
        manager = MultiServerManager()
        config = ServerConfig(
            server_id="test1",
            name="Test Server 1",
            host="localhost",
            port=27015
        )
        manager.add_server(config)

        server = manager.get_server("test1")
        assert server is not None
        assert server.name == "Test Server 1"

    def test_get_default_server(self):
        """Test getting default server."""
        manager = MultiServerManager()
        config = ServerConfig(
            server_id="test1",
            name="Test Server 1",
            host="localhost",
            port=27015
        )
        manager.add_server(config)

        # Get without specifying ID should return default
        server = manager.get_server()
        assert server is not None
        assert server.server_id == "test1"

    def test_list_servers(self):
        """Test listing all servers."""
        manager = MultiServerManager()

        for i in range(3):
            config = ServerConfig(
                server_id=f"test{i}",
                name=f"Test Server {i}",
                host="localhost",
                port=27015 + i
            )
            manager.add_server(config)

        servers = manager.list_servers()
        assert len(servers) == 3

    def test_get_server_names(self):
        """Test getting server names for autocomplete."""
        manager = MultiServerManager()

        config1 = ServerConfig(
            server_id="prod",
            name="Production",
            host="localhost",
            port=27015
        )
        config2 = ServerConfig(
            server_id="test",
            name="Testing",
            host="localhost",
            port=27016
        )

        manager.add_server(config1)
        manager.add_server(config2)

        names = manager.get_server_names()
        assert "Production" in names
        assert "Testing" in names

    def test_remove_server(self):
        """Test removing a server."""
        manager = MultiServerManager()
        config = ServerConfig(
            server_id="test1",
            name="Test Server",
            host="localhost",
            port=27015
        )
        manager.add_server(config)

        manager.remove_server("test1")

        assert manager.count() == 0
        assert manager.get_server("test1") is None

    def test_remove_nonexistent_server(self):
        """Test removing nonexistent server fails."""
        manager = MultiServerManager()

        with pytest.raises(ValueError, match="not found"):
            manager.remove_server("nonexistent")

    def test_set_default(self):
        """Test setting default server."""
        manager = MultiServerManager()

        config1 = ServerConfig(server_id="test1", name="Server 1", host="localhost", port=27015)
        config2 = ServerConfig(server_id="test2", name="Server 2", host="localhost", port=27016)

        manager.add_server(config1)
        manager.add_server(config2)

        # Default should be first added
        assert manager.get_default_id() == "test1"

        # Change default
        manager.set_default("test2")
        assert manager.get_default_id() == "test2"

    def test_set_invalid_default(self):
        """Test setting invalid default fails."""
        manager = MultiServerManager()

        with pytest.raises(ValueError, match="not found"):
            manager.set_default("nonexistent")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
