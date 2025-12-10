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

Covers Phase 6 Multi-Server Architecture:
- Config dataclass with servers.yml requirement
- ServerConfig per-server configuration
- load_config() from environment + servers.yml
- validate_config() checks
- Safe type conversion functions

Note: get_config_value was removed in refactor - config now loads
directly from environment variables and YAML files.
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
    _safe_int,
    _safe_float,
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
        with pytest.raises(ValueError, match="servers must be a non-empty dictionary"):
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

        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN environment variable is REQUIRED"):
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

    def test_loads_with_environment_variable_password(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """load_config should support ${VAR_NAME} in rcon_password."""
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
                    "rcon_password": "${RCON_PASSWORD_ENV}",
                    "event_channel_id": 123456789,
                }
            }
        }
        with open(servers_yml, "w") as f:
            yaml.dump(servers_content, f)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
        monkeypatch.setenv("RCON_PASSWORD_ENV", "secret_from_env")

        config = load_config()

        assert config.servers["test"].rcon_password == "secret_from_env"


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
        # Can't even create Config without servers, so this tests the validation path
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
