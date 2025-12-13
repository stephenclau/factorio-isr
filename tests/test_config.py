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
Comprehensive tests for config.py with 95%+ code coverage.

Covers Phase 6 Multi-Server Architecture with Docker Secrets:
- Config dataclass with servers.yml requirement
- ServerConfig per-server configuration
- load_config() from environment + servers.yml
- validate_config() checks
- get_config_value() for secure secret handling
- _read_docker_secret() for Docker/K8s secret mounts
- Safe type conversion functions
- Environment variable expansion in config values
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import patch, MagicMock

import pytest
import yaml

from config import (
    Config,
    ServerConfig,
    load_config,
    validate_config,
    get_config_value,
    _read_docker_secret,
    _safe_int,
    _safe_float,
    _expand_env_vars,
)


# ======================================================================
# Global fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate tests from real environment and filesystem."""
    monkeypatch.chdir(tmp_path)

    # Clear config-related environment variables
    prefixes = [
        "DISCORD_",
        "FACTORIO_",
        "BOT_",
        "LOG_",
        "HEALTH_",
        "PATTERNS_",
        "PATTERN_",
        "CONFIG_",
        "RCON_",
        "DEBUG",
    ]
    for key in list(os.environ.keys()):
        if any(key.startswith(p) for p in prefixes):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def temp_servers_yml(tmp_path: Path) -> Path:
    """Create temporary servers.yml for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    servers_yml = config_dir / "servers.yml"

    # Create a valid servers.yml
    servers_content = {
        "servers": {
            "prod": {
                "name": "Production",
                "log_path": "console.log",
                "rcon_host": "prod.example.com",
                "rcon_port": 27015,
                "rcon_password": "prod_secret",
                "event_channel_id": 123456789,
                "rcon_breakdown_mode": "transition",
                "rcon_breakdown_interval": 300,
            }
        }
    }

    with open(servers_yml, "w") as f:
        yaml.dump(servers_content, f)

    return servers_yml


# ======================================================================
# Docker Secrets Tests
# ======================================================================


class TestReadDockerSecret:
    """Tests for _read_docker_secret() function."""

    def test_reads_docker_secret_file(self, tmp_path: Path) -> None:
        """_read_docker_secret should read from /run/secrets/* location."""
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        secret_file = secrets_dir / "test_secret"
        secret_file.write_text("secret_value_xyz")
        
        with patch("config.Path") as mock_path:
            # Mock Path to return our test location
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = "secret_value_xyz"
            
            result = _read_docker_secret("test_secret")
            assert result == "secret_value_xyz"

    def test_strips_whitespace_from_secret(self, tmp_path: Path) -> None:
        """_read_docker_secret should strip whitespace from secret content."""
        with patch("config.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = "  secret_value  \n"
            
            result = _read_docker_secret("test_secret")
            assert result == "secret_value"

    def test_returns_none_for_missing_secret(self) -> None:
        """_read_docker_secret should return None if secret file not found."""
        with patch("config.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            
            result = _read_docker_secret("nonexistent_secret")
            assert result is None

    def test_handles_io_error_gracefully(self) -> None:
        """_read_docker_secret should return None on IO error."""
        with patch("config.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.side_effect = IOError("Permission denied")
            
            result = _read_docker_secret("test_secret")
            assert result is None


class TestGetConfigValue:
    """Tests for get_config_value() function."""

    def test_gets_value_from_docker_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_config_value should prefer Docker secret over environment variable."""
        monkeypatch.setenv("DISCORD_TOKEN", "env_value")
        
        with patch("config._read_docker_secret") as mock_secret:
            mock_secret.return_value = "secret_value"
            
            result = get_config_value(
                env_var="DISCORD_TOKEN",
                secret_name="discord_token",
            )
            assert result == "secret_value"
            mock_secret.assert_called_once_with("discord_token")

    def test_fallback_to_env_when_no_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_config_value should fall back to env var when secret not found."""
        monkeypatch.setenv("BOT_TOKEN", "env_value")
        
        with patch("config._read_docker_secret") as mock_secret:
            mock_secret.return_value = None
            
            result = get_config_value(
                env_var="BOT_TOKEN",
                secret_name="bot_token",
            )
            assert result == "env_value"

    def test_uses_default_when_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_config_value should use default when not found in secret or env."""
        with patch("config._read_docker_secret") as mock_secret:
            mock_secret.return_value = None
            monkeypatch.delenv("MISSING_VAR", raising=False)
            
            result = get_config_value(
                env_var="MISSING_VAR",
                secret_name="missing_var",
                default="default_value",
            )
            assert result == "default_value"

    def test_raises_when_required_and_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_config_value should raise ValueError when required=True and value missing."""
        with patch("config._read_docker_secret") as mock_secret:
            mock_secret.return_value = None
            monkeypatch.delenv("REQUIRED_VAR", raising=False)
            
            with pytest.raises(ValueError, match="Required configuration value not found"):
                get_config_value(
                    env_var="REQUIRED_VAR",
                    secret_name="required_var",
                    required=True,
                )

    def test_derives_secret_name_from_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_config_value should derive secret_name from env_var if not provided."""
        monkeypatch.setenv("MY_TOKEN", "env_value")
        
        with patch("config._read_docker_secret") as mock_secret:
            mock_secret.return_value = None
            
            result = get_config_value(env_var="MY_TOKEN")
            mock_secret.assert_called_once_with("my_token")  # Lowercased
            assert result == "env_value"


class TestExpandEnvVars:
    """Tests for _expand_env_vars() function."""

    def test_expands_env_var_in_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_expand_env_vars should expand ${VAR_NAME} syntax."""
        monkeypatch.setenv("SECRET_PASSWORD", "super_secret")
        
        result = _expand_env_vars("password_is_${SECRET_PASSWORD}")
        assert result == "password_is_super_secret"

    def test_handles_missing_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_expand_env_vars should fall back to original if variable not found."""
        monkeypatch.delenv("MISSING", raising=False)
        
        result = _expand_env_vars("value_${MISSING}_here")
        assert result == "value_${MISSING}_here"

    def test_handles_multiple_expansions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_expand_env_vars should handle multiple variable expansions."""
        monkeypatch.setenv("HOST", "prod.example.com")
        monkeypatch.setenv("PORT", "27015")
        
        result = _expand_env_vars("rcon://${HOST}:${PORT}")
        assert result == "rcon://prod.example.com:27015"

    def test_handles_non_string_input(self) -> None:
        """_expand_env_vars should return non-string input unchanged."""
        result = _expand_env_vars(12345)  # type: ignore
        assert result == 12345


# ======================================================================
# Safe conversion function tests
# ======================================================================


class TestSafeInt:
    """Tests for _safe_int() conversion."""

    def test_converts_int(self) -> None:
        """_safe_int should return int as-is."""
        result = _safe_int(27015, "rcon_port", 27015)
        assert result == 27015

    def test_converts_string_int(self) -> None:
        """_safe_int should convert string to int."""
        result = _safe_int("8080", "health_check_port", 8080)
        assert result == 8080

    def test_returns_default_for_none(self) -> None:
        """_safe_int should return default when value is None."""
        result = _safe_int(None, "field", 42)
        assert result == 42

    def test_raises_on_invalid_string(self) -> None:
        """_safe_int should raise ValueError for non-numeric string."""
        with pytest.raises(ValueError, match="Invalid integer"):
            _safe_int("not_a_number", "field", 0)

    def test_raises_on_invalid_type(self) -> None:
        """_safe_int should raise ValueError for unsupported type."""
        with pytest.raises(ValueError, match="Cannot convert"):
            _safe_int([1, 2, 3], "field", 0)


class TestSafeFloat:
    """Tests for _safe_float() conversion."""

    def test_converts_float(self) -> None:
        """_safe_float should return float as-is."""
        result = _safe_float(3.14, "threshold", 0.0)
        assert result == 3.14

    def test_converts_int_to_float(self) -> None:
        """_safe_float should convert int to float."""
        result = _safe_float(42, "threshold", 0.0)
        assert result == 42.0

    def test_converts_string_float(self) -> None:
        """_safe_float should convert string to float."""
        result = _safe_float("3.14", "threshold", 0.0)
        assert result == 3.14

    def test_returns_default_for_none(self) -> None:
        """_safe_float should return default when value is None."""
        result = _safe_float(None, "field", 1.5)
        assert result == 1.5

    def test_raises_on_invalid_string(self) -> None:
        """_safe_float should raise ValueError for non-numeric string."""
        with pytest.raises(ValueError, match="Invalid float"):
            _safe_float("not_a_float", "field", 0.0)


# ======================================================================
# ServerConfig tests
# ======================================================================


class TestServerConfig:
    """Tests for ServerConfig dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """ServerConfig should create with required fields."""
        config = ServerConfig(
            name="Production",
            tag="prod",
            log_path=Path("/var/log/console.log"),
            rcon_host="prod.example.com",
            rcon_port=27015,
            rcon_password="secret123",
            event_channel_id=123456789,
        )

        assert config.name == "Production"
        assert config.tag == "prod"
        assert config.rcon_host == "prod.example.com"
        assert config.event_channel_id == 123456789
        assert config.rcon_breakdown_mode == "transition"
        assert config.rcon_breakdown_interval == 300

    def test_converts_log_path_string(self) -> None:
        """ServerConfig should convert string log_path to Path."""
        config = ServerConfig(
            name="Test",
            tag="test",
            log_path="/tmp/console.log",  # type: ignore
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=111111111,
        )

        assert isinstance(config.log_path, Path)
        assert str(config.log_path) == "/tmp/console.log"

    def test_validates_invalid_tag(self) -> None:
        """ServerConfig should reject invalid tag format."""
        with pytest.raises(ValueError, match="Server tag must be alphanumeric"):
            ServerConfig(
                name="Bad",
                tag="Invalid-Tag!",
                log_path=Path("/tmp/test.log"),
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="pass",
                event_channel_id=111111111,
            )

    def test_validates_invalid_port(self) -> None:
        """ServerConfig should reject invalid port numbers."""
        with pytest.raises(ValueError, match="Invalid RCON port"):
            ServerConfig(
                name="Bad",
                tag="bad",
                log_path=Path("/tmp/test.log"),
                rcon_host="localhost",
                rcon_port=99999,
                rcon_password="pass",
                event_channel_id=111111111,
            )

    def test_validates_empty_password(self) -> None:
        """ServerConfig should reject empty RCON password."""
        with pytest.raises(ValueError, match="RCON password cannot be empty"):
            ServerConfig(
                name="Bad",
                tag="bad",
                log_path=Path("/tmp/test.log"),
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="",
                event_channel_id=111111111,
            )

    def test_validates_breakdown_mode(self) -> None:
        """ServerConfig should validate rcon_breakdown_mode."""
        with pytest.raises(ValueError, match="rcon_breakdown_mode must be"):
            ServerConfig(
                name="Bad",
                tag="bad",
                log_path=Path("/tmp/test.log"),
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="pass",
                event_channel_id=111111111,
                rcon_breakdown_mode="invalid",
            )

    def test_validates_breakdown_interval(self) -> None:
        """ServerConfig should validate rcon_breakdown_interval > 0."""
        with pytest.raises(ValueError, match="rcon_breakdown_interval must be"):
            ServerConfig(
                name="Bad",
                tag="bad",
                log_path=Path("/tmp/test.log"),
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="pass",
                event_channel_id=111111111,
                rcon_breakdown_interval=-1,
            )


# ======================================================================
# Config dataclass tests
# ======================================================================


class TestConfigDataclass:
    """Tests for Config dataclass."""

    def test_creates_with_required_fields(self, tmp_path: Path) -> None:
        """Config should create with required fields."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="test_token_xyz",
            bot_name="TestBot",
            servers={"test": server},
        )

        assert config.discord_bot_token == "test_token_xyz"
        assert config.bot_name == "TestBot"
        assert "test" in config.servers

    def test_validates_missing_servers(self) -> None:
        """Config should require servers configuration."""
        with pytest.raises(ValueError, match="servers configuration is REQUIRED"):
            Config(
                discord_bot_token="token",
                bot_name="Bot",
                servers=None,
            )

    def test_validates_empty_servers(self, tmp_path: Path) -> None:
        """Config should reject empty servers dict."""
        with pytest.raises(ValueError, match="servers configuration is REQUIRED. Multi-server mode requires servers.yml with at least one server."):
            Config(
                discord_bot_token="token",
                bot_name="Bot",
                servers={},
            )

    def test_validates_missing_bot_token(self, tmp_path: Path) -> None:
        """Config should require Discord bot token."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        with pytest.raises(ValueError, match="discord_bot_token is REQUIRED"):
            Config(
                discord_bot_token="",
                bot_name="Bot",
                servers={"test": server},
            )

    def test_validates_invalid_log_level(self, tmp_path: Path) -> None:
        """Config should validate log_level."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        with pytest.raises(ValueError, match="Invalid log_level"):
            Config(
                discord_bot_token="token",
                bot_name="Bot",
                servers={"test": server},
                log_level="invalid_level",
            )

    def test_validates_invalid_health_check_port(self, tmp_path: Path) -> None:
        """Config should validate health_check_port."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        with pytest.raises(ValueError, match="Invalid health_check_port"):
            Config(
                discord_bot_token="token",
                bot_name="Bot",
                servers={"test": server},
                health_check_port=99999,
            )


# ======================================================================
# load_config tests
# ======================================================================


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_raises_on_missing_servers_yml(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should raise if servers.yml is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "config"))

        with pytest.raises(FileNotFoundError, match="servers.yml not found"):
            load_config()

    def test_raises_on_missing_bot_token(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should raise if DISCORD_BOT_TOKEN is missing."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        servers_content = {
            "servers": {
                "test": {
                    "name": "Test",
                    "log_path": "console.log",
                    "rcon_host": "localhost",
                    "rcon_port": 27015,
                    "rcon_password": "pass",
                    "event_channel_id": 123456789,
                }
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

        with pytest.raises(ValueError, match="Required configuration value not found for 'DISCORD_BOT_TOKEN'. Checked: Docker secret 'discord_bot_token', environment variable 'DISCORD_BOT_TOKEN'"):
            load_config()

    def test_loads_config_successfully(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should load valid configuration."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        servers_content = {
            "servers": {
                "prod": {
                    "name": "Production",
                    "log_path": "console.log",
                    "rcon_host": "prod.example.com",
                    "rcon_port": 27015,
                    "rcon_password": "prod_secret",
                    "event_channel_id": 123456789,
                }
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("BOT_NAME", "TestBot")

        config = load_config()

        assert config.discord_bot_token == "test_token"
        assert config.bot_name == "TestBot"
        assert "prod" in config.servers
        assert config.servers["prod"].name == "Production"
        assert config.servers["prod"].event_channel_id == 123456789

    def test_loads_from_docker_secret(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should read RCON password from Docker secret if available."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        servers_content = {
            "servers": {
                "prod": {
                    "name": "Production",
                    "log_path": "console.log",
                    "rcon_host": "localhost",
                    "rcon_port": 27015,
                    "rcon_password": "default_pass",
                    "event_channel_id": 123456789,
                }
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")

        with patch("config.get_config_value") as mock_get:
            def side_effect(**kwargs: Any) -> Optional[str]:
                if kwargs.get("env_var") == "DISCORD_BOT_TOKEN":
                    return "test_token"
                if kwargs.get("env_var") == "RCON_PASSWORD_PROD":
                    return "secret_from_docker"  # Simulating Docker secret
                return kwargs.get("default")
            
            mock_get.side_effect = side_effect
            config = load_config()
            
            assert config.servers["prod"].rcon_password == "secret_from_docker"

    def test_expands_env_vars_in_password(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should expand ${VAR_NAME} in rcon_password."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        servers_content = {
            "servers": {
                "prod": {
                    "name": "Production",
                    "log_path": "console.log",
                    "rcon_host": "localhost",
                    "rcon_port": 27015,
                    "rcon_password": "prefix_${RCON_SECRET}_suffix",
                    "event_channel_id": 123456789,
                }
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("RCON_SECRET", "expanded_value")

        config = load_config()

        assert config.servers["prod"].rcon_password == "prefix_expanded_value_suffix"

    def test_loads_defaults_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should use default values when env vars not set."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        servers_content = {
            "servers": {
                "test": {
                    "name": "Test",
                    "log_path": "console.log",
                    "rcon_host": "localhost",
                    "rcon_port": 27015,
                    "rcon_password": "pass",
                    "event_channel_id": 123456789,
                }
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
        for var in ["BOT_NAME", "HEALTH_CHECK_HOST", "HEALTH_CHECK_PORT", "LOG_LEVEL", "LOG_FORMAT"]:
            monkeypatch.delenv(var, raising=False)

        config = load_config()

        assert config.bot_name == "Factorio ISR"  # default
        assert config.health_check_host == "0.0.0.0"  # default
        assert config.health_check_port == 8080  # default
        assert config.log_level == "info"  # default
        assert config.log_format == "console"  # default


# ======================================================================
# validate_config tests
# ======================================================================


class TestValidateConfig:
    """Tests for validate_config() function."""

    def test_validates_valid_config(self, tmp_path: Path) -> None:
        """validate_config should return True for valid config."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="token",
            bot_name="Bot",
            servers={"test": server},
        )

        assert validate_config(config) is True

    def test_rejects_no_servers(self, tmp_path: Path) -> None:
        """validate_config should reject config with no servers."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="token",
            bot_name="Bot",
            servers={"test": server},
        )

        # Manually remove servers to test validation
        config.servers = None

        # Validation should catch this
        result = validate_config(config)
        assert result is False

    def test_rejects_server_missing_event_channel(self, tmp_path: Path) -> None:
        """validate_config should reject server with missing event_channel_id."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=0,  # Invalid - must be set
        )

        config = Config(
            discord_bot_token="token",
            bot_name="Bot",
            servers={"test": server},
        )

        assert validate_config(config) is False

    def test_rejects_no_bot_token(self, tmp_path: Path) -> None:
        """validate_config should reject config with no bot token."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="token",
            bot_name="Bot",
            servers={"test": server},
        )

        # Manually remove token to test validation
        config.discord_bot_token = ""

        assert validate_config(config) is False

    def test_warns_on_missing_patterns_dir(self, tmp_path: Path) -> None:
        """validate_config should warn but not fail if patterns_dir missing."""
        server = ServerConfig(
            name="Test",
            tag="test",
            log_path=tmp_path / "console.log",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="token",
            bot_name="Bot",
            servers={"test": server},
            patterns_dir=tmp_path / "nonexistent",  # Doesn't exist
        )

        # Should not fail, just warn
        assert validate_config(config) is True


# ======================================================================
# Integration tests
# ======================================================================


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_load_and_validate(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Full integration: load config and validate."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        servers_content = {
            "servers": {
                "prod": {
                    "name": "Production",
                    "log_path": "console.log",
                    "rcon_host": "prod.example.com",
                    "rcon_port": 27015,
                    "rcon_password": "prod_secret",
                    "event_channel_id": 111111111,
                    "rcon_breakdown_mode": "interval",
                    "rcon_breakdown_interval": 600,
                },
                "staging": {
                    "name": "Staging",
                    "log_path": "console.log",
                    "rcon_host": "staging.example.com",
                    "rcon_port": 27015,
                    "rcon_password": "staging_secret",
                    "event_channel_id": 222222222,
                },
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "integration_test_token")
        monkeypatch.setenv("BOT_NAME", "IntegrationBot")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        # Load config
        config = load_config()

        # Validate config
        assert validate_config(config) is True

        # Check loaded values
        assert config.bot_name == "IntegrationBot"
        assert config.log_level == "debug"
        assert len(config.servers) == 2
        assert config.servers["prod"].rcon_breakdown_mode == "interval"
        assert config.servers["prod"].rcon_breakdown_interval == 600
        assert config.servers["staging"].rcon_breakdown_mode == "transition"  # default
        assert config.servers["staging"].rcon_breakdown_interval == 300  # default
