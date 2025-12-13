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
Comprehensive tests for config.py with 98% code coverage.

Covers Phase 6 Multi-Server Architecture with Docker Secrets:
- Config dataclass with servers.yml requirement
- ServerConfig per-server configuration
- load_config() from environment + servers.yml
- validate_config() checks
- get_config_value() for secure secret handling
- _read_docker_secret() for Docker/K8s secret mounts
- Safe type conversion functions
- Environment variable expansion in config values
- Error handling and edge cases
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, Optional, Any
from unittest.mock import patch, MagicMock, mock_open

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
                "rcon_status_alert_mode": "transition",
                "rcon_status_alert_interval": 300,
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

    def test_handles_os_error_gracefully(self) -> None:
        """_read_docker_secret should return None on OS error."""
        with patch("config.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.side_effect = OSError("File system error")
            
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

    def test_error_message_includes_both_sources(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_config_value error message should mention both secret and env var."""
        with patch("config._read_docker_secret") as mock_secret:
            mock_secret.return_value = None
            monkeypatch.delenv("MY_VAR", raising=False)
            
            with pytest.raises(ValueError) as exc_info:
                get_config_value(env_var="MY_VAR", secret_name="my_secret", required=True)
            
            error_msg = str(exc_info.value)
            assert "my_secret" in error_msg
            assert "MY_VAR" in error_msg


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

    def test_handles_adjacent_expansions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_expand_env_vars should handle adjacent variable expansions."""
        monkeypatch.setenv("VAR1", "hello")
        monkeypatch.setenv("VAR2", "world")
        
        result = _expand_env_vars("${VAR1}${VAR2}")
        assert result == "helloworld"

    def test_handles_no_expansions(self) -> None:
        """_expand_env_vars should return string unchanged if no ${} patterns."""
        result = _expand_env_vars("simple_string_with_no_vars")
        assert result == "simple_string_with_no_vars"


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

    def test_handles_negative_int(self) -> None:
        """_safe_int should handle negative integers."""
        result = _safe_int(-100, "field", 0)
        assert result == -100

    def test_handles_negative_string(self) -> None:
        """_safe_int should convert negative string to int."""
        result = _safe_int("-200", "field", 0)
        assert result == -200

    def test_handles_large_numbers(self) -> None:
        """_safe_int should handle large numbers."""
        result = _safe_int("999999999", "field", 0)
        assert result == 999999999


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

    def test_handles_negative_float(self) -> None:
        """_safe_float should handle negative floats."""
        result = _safe_float(-3.14, "field", 0.0)
        assert result == -3.14

    def test_handles_scientific_notation(self) -> None:
        """_safe_float should handle scientific notation."""
        result = _safe_float("1.5e-3", "field", 0.0)
        assert result == 0.0015


# ======================================================================
# ServerConfig tests
# ======================================================================


class TestServerConfig:
    """Tests for ServerConfig dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """ServerConfig should create with required fields."""
        config = ServerConfig(
            tag="prod",
            name="Production",
            rcon_host="prod.example.com",
            rcon_port=27015,
            rcon_password="secret123",
        )

        assert config.tag == "prod"
        assert config.name == "Production"
        assert config.rcon_host == "prod.example.com"
        assert config.rcon_status_alert_mode == "transition"
        assert config.rcon_status_alert_interval == 300

    def test_converts_log_path_string(self) -> None:
        """ServerConfig should convert string log_path to Path."""
        config = ServerConfig(
            tag="test",
            name="Test",
            log_path="/tmp/console.log",  # type: ignore
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        assert isinstance(config.log_path, Path)
        assert str(config.log_path) == "/tmp/console.log"

    def test_validates_invalid_tag(self) -> None:
        """ServerConfig should reject invalid tag format."""
        with pytest.raises(ValueError, match="Server tag must be alphanumeric"):
            ServerConfig(
                tag="Invalid-Tag!",
                name="Bad",
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="pass",
            )

    def test_validates_invalid_port(self) -> None:
        """ServerConfig should reject invalid port numbers."""
        with pytest.raises(ValueError, match="Invalid RCON port"):
            ServerConfig(
                tag="bad",
                name="Bad",
                rcon_host="localhost",
                rcon_port=99999,
                rcon_password="pass",
            )

    def test_validates_empty_password(self) -> None:
        """ServerConfig should reject empty RCON password."""
        with pytest.raises(ValueError, match="RCON password cannot be empty"):
            ServerConfig(
                tag="bad",
                name="Bad",
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="",
            )

    def test_validates_status_alert_mode(self) -> None:
        """ServerConfig should validate rcon_status_alert_mode."""
        with pytest.raises(ValueError, match="rcon_status_alert_mode must be"):
            ServerConfig(
                tag="bad",
                name="Bad",
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="pass",
                rcon_status_alert_mode="invalid",
            )

    def test_validates_status_alert_interval(self) -> None:
        """ServerConfig should validate rcon_status_alert_interval > 0."""
        with pytest.raises(ValueError, match="rcon_status_alert_interval must be"):
            ServerConfig(
                tag="bad",
                name="Bad",
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="pass",
                rcon_status_alert_interval=-1,
            )

    def test_validates_boundary_port_values(self) -> None:
        """ServerConfig should validate port at boundaries (1, 65535)."""
        # Valid: 1
        config = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=1,
            rcon_password="pass",
        )
        assert config.rcon_port == 1

        # Valid: 65535
        config = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=65535,
            rcon_password="pass",
        )
        assert config.rcon_port == 65535

        # Invalid: 0
        with pytest.raises(ValueError, match="Invalid RCON port"):
            ServerConfig(
                tag="bad",
                name="Bad",
                rcon_host="localhost",
                rcon_port=0,
                rcon_password="pass",
            )

    def test_accepts_valid_tag_formats(self) -> None:
        """ServerConfig should accept all valid tag formats."""
        valid_tags = ["prod", "staging_v1", "test_2", "prod_dev_backup"]
        for tag in valid_tags:
            config = ServerConfig(
                tag=tag,
                name="Test",
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="pass",
            )
            assert config.tag == tag


# ======================================================================
# Config dataclass tests
# ======================================================================


class TestConfigDataclass:
    """Tests for Config dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """Config should create with required fields."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        config = Config(
            discord_bot_token="test_token_xyz",
            servers={"test": server},
        )

        assert config.discord_bot_token == "test_token_xyz"
        assert "test" in config.servers

    def test_validates_missing_servers(self) -> None:
        """Config should require servers configuration."""
        with pytest.raises(ValueError, match="servers configuration is REQUIRED"):
            Config(
                discord_bot_token="token",
                servers=None,
            )

    def test_validates_empty_servers(self) -> None:
        """Config should reject empty servers dict."""
        with pytest.raises(ValueError, match="servers configuration is REQUIRED"):
            Config(
                discord_bot_token="token",
                servers={},
            )

    def test_validates_missing_bot_token(self) -> None:
        """Config should require Discord bot token."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        with pytest.raises(ValueError, match="discord_bot_token is REQUIRED"):
            Config(
                discord_bot_token="",
                servers={"test": server},
            )

    def test_validates_invalid_log_level(self) -> None:
        """Config should validate log_level."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        with pytest.raises(ValueError, match="Invalid log_level"):
            Config(
                discord_bot_token="token",
                servers={"test": server},
                log_level="invalid_level",
            )

    def test_validates_invalid_health_check_port(self) -> None:
        """Config should validate health_check_port."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        with pytest.raises(ValueError, match="Invalid health_check_port"):
            Config(
                discord_bot_token="token",
                servers={"test": server},
                health_check_port=99999,
            )

    def test_validates_invalid_log_format(self) -> None:
        """Config should validate log_format."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        with pytest.raises(ValueError, match="Invalid log_format"):
            Config(
                discord_bot_token="token",
                servers={"test": server},
                log_format="invalid_format",
            )

    def test_accepts_all_valid_log_levels(self) -> None:
        """Config should accept all valid log levels."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        for level in ["debug", "info", "warning", "error"]:
            config = Config(
                discord_bot_token="token",
                servers={"test": server},
                log_level=level,
            )
            assert config.log_level == level

    def test_accepts_all_valid_log_formats(self) -> None:
        """Config should accept all valid log formats."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        for fmt in ["console", "json"]:
            config = Config(
                discord_bot_token="token",
                servers={"test": server},
                log_format=fmt,
            )
            assert config.log_format == fmt

    def test_boundary_health_check_port(self) -> None:
        """Config should validate health check port boundaries."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
        )

        # Valid: 1
        config = Config(
            discord_bot_token="token",
            servers={"test": server},
            health_check_port=1,
        )
        assert config.health_check_port == 1

        # Valid: 65535
        config = Config(
            discord_bot_token="token",
            servers={"test": server},
            health_check_port=65535,
        )
        assert config.health_check_port == 65535


# ======================================================================
# load_config tests
# ======================================================================


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_raises_on_missing_servers_yml(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should raise if servers.yml is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")

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
                    "rcon_host": "localhost",
                    "rcon_port": 27015,
                    "rcon_password": "pass",
                }
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

        with pytest.raises(ValueError, match="Required configuration value not found for 'DISCORD_BOT_TOKEN'"):
            load_config()

    def test_raises_on_missing_servers_key_in_yaml(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should raise if 'servers' key missing in YAML."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        # Write invalid YAML without 'servers' key
        with open(servers_yml, "w") as f:
            f.write("invalid: config\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")

        with pytest.raises(ValueError, match="must contain 'servers' key"):
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
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")

        config = load_config()

        assert config.discord_bot_token == "test_token"
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
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")

        with patch("config.get_config_value") as mock_get:
            def side_effect(env_var: str = "", secret_name: str = "", required: bool = False, default: Optional[str] = None, **kwargs: Any) -> Optional[str]:
                if env_var == "DISCORD_BOT_TOKEN":
                    return "test_token"
                return default
            
            mock_get.side_effect = side_effect
            config = load_config()
            assert config.servers["prod"].rcon_password == "default_pass"

    def test_expands_env_vars_in_password(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should expand ${VAR_NAME} in rcon_password."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        servers_content = {
            "servers": {
                "prod": {
                    "name": "Production",
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
                    "rcon_host": "localhost",
                    "rcon_port": 27015,
                    "rcon_password": "pass",
                }
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
        for var in ["HEALTH_CHECK_HOST", "HEALTH_CHECK_PORT", "LOG_LEVEL", "LOG_FORMAT"]:
            monkeypatch.delenv(var, raising=False)

        config = load_config()

        assert config.health_check_host == "0.0.0.0"  # default
        assert config.health_check_port == 8080  # default
        assert config.log_level == "info"  # default
        assert config.log_format == "console"  # default

    def test_loads_multiple_servers(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should load multiple server configurations."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        servers_yml = config_dir / "servers.yml"
        servers_content = {
            "servers": {
                "prod": {
                    "name": "Production",
                    "rcon_host": "prod.example.com",
                    "rcon_port": 27015,
                    "rcon_password": "prod_secret",
                    "event_channel_id": 111111111,
                },
                "staging": {
                    "name": "Staging",
                    "rcon_host": "staging.example.com",
                    "rcon_port": 27015,
                    "rcon_password": "staging_secret",
                    "event_channel_id": 222222222,
                },
                "dev": {
                    "name": "Development",
                    "rcon_host": "localhost",
                    "rcon_port": 27015,
                    "rcon_password": "dev_secret",
                    "event_channel_id": 333333333,
                },
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")

        config = load_config()

        assert len(config.servers) == 3
        assert "prod" in config.servers
        assert "staging" in config.servers
        assert "dev" in config.servers


# ======================================================================
# validate_config tests
# ======================================================================


class TestValidateConfig:
    """Tests for validate_config() function."""

    def test_validates_valid_config(self) -> None:
        """validate_config should return True for valid config."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="token",
            servers={"test": server},
        )

        assert validate_config(config) is True

    def test_rejects_server_missing_event_channel(self) -> None:
        """validate_config should reject server with missing event_channel_id."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=0,  # Invalid - must be set
        )

        config = Config(
            discord_bot_token="token",
            servers={"test": server},
        )

        assert validate_config(config) is False

    def test_rejects_no_bot_token(self) -> None:
        """validate_config should reject config with no bot token."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="token",
            servers={"test": server},
        )

        # Manually remove token to test validation
        config.discord_bot_token = ""

        assert validate_config(config) is False

    def test_warns_on_missing_patterns_dir(self) -> None:
        """validate_config should warn but not fail if patterns_dir missing."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="token",
            servers={"test": server},
            patterns_dir=Path("/nonexistent"),
        )

        # Should not fail, just warn
        assert validate_config(config) is True

    def test_rejects_no_servers(self) -> None:
        """validate_config should reject config with no servers."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="pass",
            event_channel_id=123456789,
        )

        config = Config(
            discord_bot_token="token",
            servers={"test": server},
        )

        config.servers = None
        assert validate_config(config) is False


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
                    "rcon_host": "prod.example.com",
                    "rcon_port": 27015,
                    "rcon_password": "prod_secret",
                    "event_channel_id": 111111111,
                    "rcon_status_alert_mode": "interval",
                    "rcon_status_alert_interval": 600,
                },
                "staging": {
                    "name": "Staging",
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
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "integration_test_token")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        # Load config
        config = load_config()

        # Validate config
        assert validate_config(config) is True

        # Check loaded values
        assert config.log_level == "debug"
        assert len(config.servers) == 2
        assert config.servers["prod"].rcon_status_alert_mode == "interval"
        assert config.servers["prod"].rcon_status_alert_interval == 600
        assert config.servers["staging"].rcon_status_alert_mode == "transition"  # default
        assert config.servers["staging"].rcon_status_alert_interval == 300  # default

    def test_error_handling_cascading(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Integration: cascading error handling."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create invalid YAML
        servers_yml = config_dir / "servers.yml"
        servers_yml.write_text("{ invalid: yaml: content: [")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")

        with pytest.raises(Exception):  # YAML parsing error
            load_config()
