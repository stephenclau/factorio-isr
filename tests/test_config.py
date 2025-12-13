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

from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from tempfile import TemporaryDirectory
import yaml

from config import (
    Config,
    ServerConfig,
    get_config_value,
    _read_docker_secret,
    _safe_int,
    _safe_float,
    _expand_env_vars,
    load_config,
    validate_config,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_env(monkeypatch):
    """Clear and provide a clean environment for each test."""
    # Clean up any existing vars
    for key in list(os.environ.keys()):
        if key.startswith(("DISCORD", "RCON", "HEALTH", "LOG", "DEBUG")):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def base_server_config_dict():
    """Provide base server configuration dictionary."""
    return {
        "tag": "prod",
        "name": "Production",
        "rcon_host": "localhost",
        "rcon_port": 27015,
        "rcon_password": "secret123",
    }


@pytest.fixture
def full_servers_yml():
    """Provide a complete servers.yml configuration."""
    return {
        "servers": {
            "prod": {
                "name": "Production",
                "rcon_host": "localhost",
                "rcon_port": 27015,
                "rcon_password": "prod-secret",
                "event_channel_id": 123456789,
                "stats_interval": 300,
            },
            "staging": {
                "name": "Staging",
                "rcon_host": "staging.local",
                "rcon_port": 27015,
                "rcon_password": "staging-secret",
                "event_channel_id": 987654321,
            },
        }
    }


# ============================================================================
# get_config_value() Tests (10 tests)
# ============================================================================

class TestGetConfigValue:
    """Test get_config_value function."""

    def test_get_from_docker_secret_prioritized(self, mock_env):
        """Test Docker secret is prioritized over env var."""
        with patch("config._read_docker_secret", return_value="secret-value"):
            mock_env.setenv("TEST_VAR", "env-value")
            result = get_config_value(env_var="TEST_VAR", secret_name="test_secret")
            assert result == "secret-value"

    def test_get_from_env_var_when_no_secret(self, mock_env):
        """Test fallback to environment variable when no secret."""
        with patch("config._read_docker_secret", return_value=None):
            mock_env.setenv("TEST_VAR", "env-value")
            result = get_config_value(env_var="TEST_VAR")
            assert result == "env-value"

    def test_get_from_default_when_no_secret_or_env(self, mock_env):
        """Test fallback to default when no secret or env var."""
        with patch("config._read_docker_secret", return_value=None):
            mock_env.delenv("TEST_VAR", raising=False)
            result = get_config_value(env_var="TEST_VAR", default="default-value")
            assert result == "default-value"

    def test_return_none_when_not_required_and_missing(self, mock_env):
        """Test returns None when not required and value missing."""
        with patch("config._read_docker_secret", return_value=None):
            mock_env.delenv("TEST_VAR", raising=False)
            result = get_config_value(env_var="TEST_VAR", required=False)
            assert result is None

    def test_raise_error_when_required_and_missing(self, mock_env):
        """Test raises ValueError when required and missing."""
        with patch("config._read_docker_secret", return_value=None):
            mock_env.delenv("TEST_VAR", raising=False)
            with pytest.raises(ValueError, match="Required configuration value not found"):
                get_config_value(env_var="TEST_VAR", required=True)

    def test_secret_name_derived_from_env_var(self, mock_env):
        """Test secret_name defaults to lowercased env_var."""
        with patch("config._read_docker_secret") as mock_read:
            mock_read.return_value = None
            mock_env.setenv("DISCORD_BOT_TOKEN", "token123")
            result = get_config_value(env_var="DISCORD_BOT_TOKEN")
            # Secret name should have been called with lowercase version
            mock_read.assert_called_once_with("discord_bot_token")
            assert result == "token123"

    def test_explicit_secret_name_used(self, mock_env):
        """Test explicit secret_name parameter is used."""
        with patch("config._read_docker_secret") as mock_read:
            mock_read.return_value = "secret-value"
            result = get_config_value(
                env_var="MY_VAR",
                secret_name="custom_secret_name"
            )
            mock_read.assert_called_once_with("custom_secret_name")
            assert result == "secret-value"

    def test_empty_string_is_not_considered_none(self, mock_env):
        """Test that empty string from env is returned (not treated as missing)."""
        with patch("config._read_docker_secret", return_value=None):
            mock_env.setenv("TEST_VAR", "")
            result = get_config_value(env_var="TEST_VAR", default="default")
            # Empty string from os.getenv should be returned
            assert result == ""

    def test_priority_order_complete(self, mock_env):
        """Test complete priority: secret > env > default > error."""
        # Scenario 1: Secret takes priority
        with patch("config._read_docker_secret", return_value="from-secret"):
            mock_env.setenv("VAR1", "from-env")
            result = get_config_value(env_var="VAR1", default="from-default")
            assert result == "from-secret"

        # Scenario 2: Env takes priority over default
        with patch("config._read_docker_secret", return_value=None):
            mock_env.setenv("VAR2", "from-env")
            result = get_config_value(env_var="VAR2", default="from-default")
            assert result == "from-env"

        # Scenario 3: Default when nothing else
        with patch("config._read_docker_secret", return_value=None):
            mock_env.delenv("VAR3", raising=False)
            result = get_config_value(env_var="VAR3", default="from-default")
            assert result == "from-default"

    def test_discord_bot_token_required_use_case(self, mock_env):
        """Test real-world use case: required Discord bot token."""
        with patch("config._read_docker_secret", return_value=None):
            mock_env.delenv("DISCORD_BOT_TOKEN", raising=False)
            with pytest.raises(ValueError, match="Required configuration value not found for 'DISCORD_BOT_TOKEN'"):
                get_config_value(
                    env_var="DISCORD_BOT_TOKEN",
                    secret_name="discord_bot_token",
                    required=True
                )


# ============================================================================
# _read_docker_secret() Tests (2 tests)
# ============================================================================

class TestReadDockerSecret:
    """Test _read_docker_secret function."""

    def test_read_secret_from_file(self):
        """Test reading secret from /run/secrets file."""
        with patch("config.Path.exists", return_value=True):
            with patch("config.Path.read_text", return_value="secret-value\n"):
                result = _read_docker_secret("test_secret")
                assert result == "secret-value"

    def test_return_none_when_secret_file_missing(self):
        """Test returns None when secret file missing."""
        with patch("config.Path.exists", return_value=False):
            result = _read_docker_secret("nonexistent_secret")
            assert result is None


# ============================================================================
# Type Safety Tests (_safe_int, _safe_float) - 3 tests
# ============================================================================

class TestTypeSafety:
    """Test type conversion safety functions."""

    def test_safe_int_from_none_returns_default(self):
        """Test _safe_int returns default when None."""
        result = _safe_int(None, "test_field", 42)
        assert result == 42

    def test_safe_int_from_int(self):
        """Test _safe_int accepts int directly."""
        result = _safe_int(100, "test_field", 42)
        assert result == 100

    def test_safe_int_from_string(self):
        """Test _safe_int converts string to int."""
        result = _safe_int("200", "test_field", 42)
        assert result == 200

    def test_safe_int_invalid_string_raises_error(self):
        """Test _safe_int raises ValueError for invalid string."""
        with pytest.raises(ValueError, match="Invalid integer"):
            _safe_int("not-a-number", "test_field", 42)

    def test_safe_int_invalid_type_raises_error(self):
        """Test _safe_int raises ValueError for unsupported type."""
        with pytest.raises(ValueError, match="Cannot convert"):
            _safe_int([1, 2, 3], "test_field", 42)

    def test_safe_float_from_none_returns_default(self):
        """Test _safe_float returns default when None."""
        result = _safe_float(None, "test_field", 3.14)
        assert result == 3.14

    def test_safe_float_from_float(self):
        """Test _safe_float accepts float directly."""
        result = _safe_float(2.71, "test_field", 3.14)
        assert result == 2.71

    def test_safe_float_from_int(self):
        """Test _safe_float converts int to float."""
        result = _safe_float(42, "test_field", 3.14)
        assert result == 42.0

    def test_safe_float_from_string(self):
        """Test _safe_float converts string to float."""
        result = _safe_float("1.99", "test_field", 3.14)
        assert result == 1.99

    def test_safe_float_invalid_string_raises_error(self):
        """Test _safe_float raises ValueError for invalid string."""
        with pytest.raises(ValueError, match="Invalid float"):
            _safe_float("not-a-number", "test_field", 3.14)


# ============================================================================
# ServerConfig Tests (8 tests)
# ============================================================================

class TestServerConfig:
    """Test ServerConfig dataclass."""

    def test_server_config_initialization_minimal(self, base_server_config_dict):
        """Test ServerConfig with minimal required fields."""
        config = ServerConfig(**base_server_config_dict)
        assert config.tag == "prod"
        assert config.name == "Production"
        assert config.rcon_host == "localhost"
        assert config.rcon_port == 27015
        assert config.rcon_password == "secret123"
        assert config.description is None
        assert config.log_path is None
        assert config.event_channel_id is None

    def test_server_config_defaults(self, base_server_config_dict):
        """Test ServerConfig applies correct defaults."""
        config = ServerConfig(**base_server_config_dict)
        assert config.stats_interval == 300
        assert config.rcon_status_alert_mode == "transition"
        assert config.rcon_status_alert_interval == 300
        assert config.enable_stats_collector is True
        assert config.enable_ups_stat is True
        assert config.enable_evolution_stat is True
        assert config.enable_alerts is True
        assert config.alert_check_interval == 60
        assert config.alert_samples_required == 3
        assert config.ups_warning_threshold == 55.0
        assert config.ups_recovery_threshold == 58.0
        assert config.alert_cooldown == 300
        assert config.ups_ema_alpha == 0.2

    def test_server_config_invalid_tag_format(self, base_server_config_dict):
        """Test ServerConfig rejects invalid tag format."""
        base_server_config_dict["tag"] = "@invalid!"
        with pytest.raises(ValueError, match="alphanumeric"):
            ServerConfig(**base_server_config_dict)

    def test_server_config_valid_tag_formats(self, base_server_config_dict):
        """Test ServerConfig accepts valid tag formats."""
        valid_tags = ["prod", "staging_v1", "test-2", "dev_prod_main"]
        for tag in valid_tags:
            base_server_config_dict["tag"] = tag
            config = ServerConfig(**base_server_config_dict)
            assert config.tag == tag

    def test_server_config_invalid_rcon_port(self, base_server_config_dict):
        """Test ServerConfig rejects invalid RCON port."""
        base_server_config_dict["rcon_port"] = 99999
        with pytest.raises(ValueError, match="Invalid RCON port"):
            ServerConfig(**base_server_config_dict)

    def test_server_config_empty_password_rejected(self, base_server_config_dict):
        """Test ServerConfig rejects empty RCON password."""
        base_server_config_dict["rcon_password"] = ""
        with pytest.raises(ValueError, match="RCON password cannot be empty"):
            ServerConfig(**base_server_config_dict)

    def test_server_config_invalid_alert_mode(self, base_server_config_dict):
        """Test ServerConfig rejects invalid alert mode."""
        base_server_config_dict["rcon_status_alert_mode"] = "invalid"
        with pytest.raises(ValueError, match="must be 'transition' or 'interval'"):
            ServerConfig(**base_server_config_dict)

    def test_server_config_alert_validation_when_enabled(self, base_server_config_dict):
        """Test ServerConfig validates alert settings when enabled."""
        base_server_config_dict["enable_alerts"] = True
        base_server_config_dict["alert_check_interval"] = 0  # Invalid
        with pytest.raises(ValueError, match="alert_check_interval must be > 0"):
            ServerConfig(**base_server_config_dict)

    def test_server_config_path_conversion(self, base_server_config_dict):
        """Test ServerConfig converts log_path to Path object."""
        base_server_config_dict["log_path"] = "./console.log"
        config = ServerConfig(**base_server_config_dict)
        assert isinstance(config.log_path, Path)
        assert str(config.log_path) == "./console.log"


# ============================================================================
# Config Tests (5 tests)
# ============================================================================

class TestConfig:
    """Test Config dataclass."""

    def test_config_initialization_minimal(self):
        """Test Config with required fields."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="secret",
        )
        config = Config(
            discord_bot_token="token123",
            servers={"test": server},
        )
        assert config.discord_bot_token == "token123"
        assert "test" in config.servers

    def test_config_requires_discord_token(self):
        """Test Config requires discord_bot_token."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="secret",
        )
        with pytest.raises(ValueError, match="discord_bot_token is REQUIRED"):
            Config(discord_bot_token="", servers={"test": server})

    def test_config_requires_servers(self):
        """Test Config requires servers dictionary."""
        with pytest.raises(ValueError, match="servers configuration is REQUIRED"):
            Config(discord_bot_token="token123", servers=None)

    def test_config_invalid_log_level(self):
        """Test Config rejects invalid log level."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="secret",
        )
        with pytest.raises(ValueError, match="Invalid log_level"):
            Config(
                discord_bot_token="token123",
                servers={"test": server},
                log_level="invalid",
            )

    def test_config_invalid_health_check_port(self):
        """Test Config rejects invalid health check port."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="secret",
        )
        with pytest.raises(ValueError, match="Invalid health_check_port"):
            Config(
                discord_bot_token="token123",
                servers={"test": server},
                health_check_port=99999,
            )

    def test_config_valid_log_levels(self):
        """Test Config accepts valid log levels."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="secret",
        )
        for level in ["debug", "info", "warning", "error"]:
            config = Config(
                discord_bot_token="token123",
                servers={"test": server},
                log_level=level,
            )
            assert config.log_level == level


# ============================================================================
# validate_config() Tests (3 tests)
# ============================================================================

class TestValidateConfig:
    """Test validate_config function."""

    def test_validate_config_success(self):
        """Test validate_config returns True for valid config."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="secret",
            event_channel_id=123456789,
        )
        config = Config(
            discord_bot_token="token123",
            servers={"test": server},
        )
        result = validate_config(config)
        assert result is True

    def test_validate_config_fails_without_event_channel(self):
        """Test validate_config fails when server missing event_channel_id."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="secret",
            event_channel_id=None,  # Missing
        )
        config = Config(
            discord_bot_token="token123",
            servers={"test": server},
        )
        result = validate_config(config)
        assert result is False

    def test_validate_config_warns_missing_patterns_dir(self):
        """Test validate_config warns when patterns dir missing."""
        server = ServerConfig(
            tag="test",
            name="Test",
            rcon_host="localhost",
            rcon_port=27015,
            rcon_password="secret",
            event_channel_id=123456789,
        )
        config = Config(
            discord_bot_token="token123",
            servers={"test": server},
            patterns_dir=Path("/nonexistent/patterns"),
        )
        result = validate_config(config)
        assert result is True  # Still valid, just warns


# ============================================================================
# _expand_env_vars() Tests (2 tests)
# ============================================================================

class TestExpandEnvVars:
    """Test _expand_env_vars function."""

    def test_expand_env_vars_with_variable(self, mock_env):
        """Test expanding ${VAR} in string."""
        mock_env.setenv("TEST_VAR", "value123")
        result = _expand_env_vars("prefix-${TEST_VAR}-suffix")
        assert result == "prefix-value123-suffix"

    def test_expand_env_vars_missing_variable_unchanged(self, mock_env):
        """Test missing ${VAR} remains unchanged."""
        mock_env.delenv("MISSING_VAR", raising=False)
        result = _expand_env_vars("prefix-${MISSING_VAR}-suffix")
        assert result == "prefix-${MISSING_VAR}-suffix"


# ============================================================================
# load_config() Integration Tests (6 tests)
# ============================================================================

class TestLoadConfig:
    """Test load_config end-to-end function."""

    def test_load_config_raises_when_servers_yml_missing(self, mock_env):
        """Test load_config raises FileNotFoundError when servers.yml missing."""
        with patch("config.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="servers.yml not found"):
                load_config()

    def test_load_config_raises_when_servers_key_missing(self, mock_env):
        """Test load_config raises ValueError when servers.yml missing 'servers' key."""
        with patch("config.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid: yaml")):
                with patch("config.get_config_value", return_value="token"):
                    with pytest.raises(ValueError, match="must contain 'servers' key"):
                        load_config()

    def test_load_config_success_single_server(self, mock_env, full_servers_yml):
        """Test load_config successfully loads single server."""
        yml_content = yaml.dump(full_servers_yml)
        with patch("config.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=yml_content)):
                with patch("config.get_config_value", return_value="token123"):
                    with patch("config._read_docker_secret", return_value=None):
                        config = load_config()
                        assert config.discord_bot_token == "token123"
                        assert "prod" in config.servers
                        assert "staging" in config.servers
                        assert config.servers["prod"].rcon_password == "prod-secret"

    def test_load_config_env_expansion_in_password(self, mock_env, full_servers_yml):
        """Test load_config expands environment variables in rcon_password."""
        mock_env.setenv("RCON_PWD", "expanded-secret")
        full_servers_yml["servers"]["prod"]["rcon_password"] = "${RCON_PWD}"
        yml_content = yaml.dump(full_servers_yml)
        with patch("config.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=yml_content)):
                with patch("config.get_config_value", return_value="token123"):
                    with patch("config._read_docker_secret", return_value=None):
                        config = load_config()
                        assert config.servers["prod"].rcon_password == "expanded-secret"

    def test_load_config_rcon_secret_fallback(self, mock_env, full_servers_yml):
        """Test load_config falls back to Docker secret for RCON password."""
        # Remove password from YAML to force secret lookup
        full_servers_yml["servers"]["prod"].pop("rcon_password")
        yml_content = yaml.dump(full_servers_yml)
        with patch("config.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=yml_content)):
                with patch("config.get_config_value", return_value="token123"):
                    with patch("config._read_docker_secret", return_value="secret-from-docker"):
                        config = load_config()
                        assert config.servers["prod"].rcon_password == "secret-from-docker"

    def test_load_config_type_conversions(self, mock_env, full_servers_yml):
        """Test load_config properly converts types from YAML."""
        full_servers_yml["servers"]["prod"]["rcon_port"] = "27015"  # String in YAML
        full_servers_yml["servers"]["prod"]["stats_interval"] = "600"  # String in YAML
        full_servers_yml["servers"]["prod"]["ups_warning_threshold"] = "50.5"  # String in YAML
        yml_content = yaml.dump(full_servers_yml)
        with patch("config.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=yml_content)):
                with patch("config.get_config_value", return_value="token123"):
                    with patch("config._read_docker_secret", return_value=None):
                        config = load_config()
                        assert config.servers["prod"].rcon_port == 27015
                        assert isinstance(config.servers["prod"].rcon_port, int)
                        assert config.servers["prod"].stats_interval == 600
                        assert config.servers["prod"].ups_warning_threshold == 50.5
                        assert isinstance(config.servers["prod"].ups_warning_threshold, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
