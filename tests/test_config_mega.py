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

Merged from:
- test_config.py
- test_config_targeted.py

Covers:
- read_secret (local .txt/.plain, Docker secrets, error paths)
- get_config_value
- parse_webhook_channels / parse_pattern_files
- ServerConfig, parse_servers_from_yaml, parse_servers_from_json
- load_config, validate_config (Discord, RCON, multi-server branches)

Phase 6 Updates:
- Removed tests for discord_event_channel_id (now per-server in ServerConfig)
- Removed tests for send_test_message (not in current Config)
- Updated ServerConfig tests for RCON breakdown configuration
- Added multi-server event_channel_id per-server tests
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

from config import (
    Config,
    ServerConfig,
    get_config_value,
    load_config,
    parse_pattern_files,
    parse_servers_from_json,
    parse_servers_from_yaml,
    parse_webhook_channels,
    read_secret,
    validate_config,
)


# ======================================================================
# Global fixtures
# ======================================================================

@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate tests from real environment and filesystem."""
    # Work in a clean temp directory
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
        "WEBHOOK_",
        "SEND_",
        "RCON_",
        "STATS_",
        "SERVERS",
    ]
    for key in list(os.environ.keys()):
        if any(key.startswith(p) for p in prefixes):
            monkeypatch.delenv(key, raising=False)

    # Prevent .env loading from touching host env
    monkeypatch.setattr("config.load_dotenv", lambda: None)


@pytest.fixture
def minimal_config() -> Config:
    """Minimal valid Config instance."""
    return Config(
        discord_webhook_url="https://discord.com/api/webhooks/123/abc",
        factorio_log_path=Path("/factorio/console.log"),
    )


# ======================================================================
# read_secret tests (from test_config.py)
# ======================================================================

class TestReadSecret:
    """Tests for read_secret()."""

    def test_read_secret_from_local_txt(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "TEST_SECRET.txt").write_text("secret_value_txt\n")
        monkeypatch.chdir(tmp_path)

        result = read_secret("TEST_SECRET")
        assert result == "secret_value_txt"

    def test_read_secret_from_local_plain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "TEST_SECRET").write_text("plain_value\n")
        monkeypatch.chdir(tmp_path)

        result = read_secret("TEST_SECRET")
        assert result == "plain_value"

    def test_read_secret_prefers_txt_over_plain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When both .txt and plain exist, .txt should win."""
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "TEST_SECRET.txt").write_text("txt_value\n")
        (secrets_dir / "TEST_SECRET").write_text("plain_value\n")
        monkeypatch.chdir(tmp_path)

        result = read_secret("TEST_SECRET")
        assert result == "txt_value"

    def test_read_secret_empty_files_return_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty secrets should fall through and ultimately return default."""
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "EMPTY.txt").write_text(" \n")
        (secrets_dir / "EMPTY").write_text("\t")
        monkeypatch.chdir(tmp_path)

        result = read_secret("EMPTY", default="fallback")
        assert result == "fallback"

    def test_read_secret_docker_secret(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Simulate Docker secret by mocking /run/secrets path."""
        monkeypatch.chdir(tmp_path)
        docker_dir = tmp_path / "run" / "secrets"
        docker_dir.mkdir(parents=True)
        (docker_dir / "API_KEY").write_text("docker_value\n")

        def mock_exists(p: Path) -> bool:
            if str(p).endswith("/run/secrets/API_KEY"):
                return True
            return False

        def mock_read_text(p: Path) -> str:
            if str(p).endswith("/run/secrets/API_KEY"):
                return "docker_value\n"
            raise FileNotFoundError

        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                result = read_secret("API_KEY")

        assert result == "docker_value"

    def test_read_secret_all_missing_returns_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = read_secret("MISSING", default="default_value")
        assert result == "default_value"


# ======================================================================
# read_secret targeted tests (from test_config_targeted.py)
# ======================================================================

class TestReadSecretTargeted:
    """Targeted tests for read_secret() missing/edge paths."""

    def test_read_secret_local_txt_exception_logs_and_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exception reading .secrets/*.txt should not crash and should continue to next sources."""
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        txt_file = secrets_dir / "test_secret.txt"
        txt_file.write_text("value\n")
        monkeypatch.chdir(tmp_path)

        def mock_exists(p: Path) -> bool:
            return str(p) == str(txt_file)

        def mock_read_text(p: Path, *args: Any, **kwargs: Any) -> str:
            raise PermissionError("denied")

        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                result = read_secret("test_secret", default="fallback")

        assert result == "fallback"

    def test_read_secret_local_plain_exception_logs_and_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exception reading .secrets/{name} should not crash and should continue to Docker/default."""
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        plain_file = secrets_dir / "test_secret"
        plain_file.write_text("value\n")
        monkeypatch.chdir(tmp_path)

        def mock_exists(p: Path) -> bool:
            return str(p) == str(plain_file)

        def mock_read_text(p: Path, *args: Any, **kwargs: Any) -> str:
            raise OSError("disk error")

        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                result = read_secret("test_secret", default=None)

        assert result is None

    def test_read_secret_docker_exception_returns_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exception reading Docker secret should yield default."""
        monkeypatch.chdir(tmp_path)

        def mock_exists(p: Path) -> bool:
            return str(p).endswith("/run/secrets/API_KEY")

        def mock_read_text(p: Path, *args: Any, **kwargs: Any) -> str:
            raise PermissionError("no access")

        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                result = read_secret("API_KEY", default="fallback")

        assert result == "fallback"


# ======================================================================
# get_config_value tests
# ======================================================================

class TestGetConfigValue:
    """Tests for get_config_value()."""

    def test_get_config_value_secret_beats_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "API_KEY.txt").write_text("secret_api\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("API_KEY", "env_api")

        value = get_config_value("API_KEY")
        assert value == "secret_api"

    def test_get_config_value_env_when_no_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOME_KEY", "env_value")
        value = get_config_value("SOME_KEY")
        assert value == "env_value"

    def test_get_config_value_default_when_no_secret_or_env(self) -> None:
        value = get_config_value("UNKNOWN_KEY", default="fallback")
        assert value == "fallback"

    def test_get_config_value_required_raises(self) -> None:
        with pytest.raises(ValueError, match="Required configuration key not found: MISSING"):
            get_config_value("MISSING", required=True)


# ======================================================================
# parse_webhook_channels / parse_pattern_files tests
# ======================================================================

class TestParseWebhookChannels:
    """Tests for parse_webhook_channels()."""

    def test_parse_webhook_channels_valid(self) -> None:
        s = '{"general": "url1", "alerts": "url2"}'
        result = parse_webhook_channels(s)
        assert result == {"general": "url1", "alerts": "url2"}

    def test_parse_webhook_channels_empty_string(self) -> None:
        assert parse_webhook_channels("") == {}

    def test_parse_webhook_channels_none(self) -> None:
        assert parse_webhook_channels(None) == {}

    def test_parse_webhook_channels_invalid_json(self) -> None:
        assert parse_webhook_channels("{invalid json") == {}

    def test_parse_webhook_channels_not_dict(self) -> None:
        assert parse_webhook_channels('["not", "a", "dict"]') == {}


class TestParsePatternFiles:
    """Tests for parse_pattern_files()."""

    def test_parse_pattern_files_valid(self) -> None:
        s = '["vanilla.yaml", "custom.yaml"]'
        result = parse_pattern_files(s)
        assert result == ["vanilla.yaml", "custom.yaml"]

    def test_parse_pattern_files_empty_string(self) -> None:
        assert parse_pattern_files("") is None

    def test_parse_pattern_files_none(self) -> None:
        assert parse_pattern_files(None) is None

    def test_parse_pattern_files_invalid_json(self) -> None:
        assert parse_pattern_files("[invalid json") is None

    def test_parse_pattern_files_not_list(self) -> None:
        assert parse_pattern_files('{"not": "a list"}') is None


# ======================================================================
# ServerConfig / servers parsing tests
# ======================================================================

class TestServerConfig:
    """Tests for ServerConfig dataclass and validation."""

    def test_server_config_valid(self) -> None:
        cfg = ServerConfig(
            tag="prod",
            name="Production",
            rcon_host="factorio-prod",
            rcon_port=27015,
            rcon_password="secret",
        )
        assert cfg.display_name == "Production"
        assert cfg.collect_ups is True

    def test_server_config_with_breakdown_settings(self) -> None:
        """Phase 6: ServerConfig should support per-server breakdown settings."""
        cfg = ServerConfig(
            tag="prod",
            name="Production",
            rcon_host="factorio-prod",
            rcon_port=27015,
            rcon_password="secret",
            event_channel_id=123456789,
            rcon_breakdown_mode="transition",
            rcon_breakdown_interval=300,
        )
        assert cfg.event_channel_id == 123456789
        assert cfg.rcon_breakdown_mode == "transition"
        assert cfg.rcon_breakdown_interval == 300

    def test_server_config_display_name_with_description(self) -> None:
        cfg = ServerConfig(
            tag="lh",
            name="Los Hermanos",
            description="Main map",
            rcon_host="lh-host",
            rcon_port=27015,
            rcon_password="secret",
        )
        assert cfg.display_name == "Los Hermanos (Main map)"

    def test_server_config_invalid_empty_tag(self) -> None:
        with pytest.raises(ValueError, match="Server tag cannot be empty"):
            ServerConfig(
                tag="",
                name="Bad",
                rcon_host="host",
                rcon_port=27015,
                rcon_password="secret",
            )

    def test_server_config_invalid_tag_pattern(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(
                tag="Invalid_tag",
                name="Bad",
                rcon_host="host",
                rcon_port=27015,
                rcon_password="secret",
            )

    def test_server_config_invalid_port(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(
                tag="prod",
                name="Bad",
                rcon_host="host",
                rcon_port=0,
                rcon_password="secret",
            )


class TestParseServersFromJson:
    """Tests for parse_servers_from_json()."""

    def test_parse_servers_from_json_valid(self) -> None:
        json_str = json.dumps(
            {
                "prod": {
                    "name": "Production",
                    "rcon_host": "factorio-prod",
                    "rcon_port": 27015,
                    "rcon_password": "secret",
                }
            }
        )
        servers = parse_servers_from_json(json_str)
        assert servers is not None
        assert "prod" in servers
        prod = servers["prod"]
        assert isinstance(prod, ServerConfig)
        assert prod.rcon_password == "secret"

    def test_parse_servers_from_json_with_event_channel(self) -> None:
        """Phase 6: parse_servers_from_json should handle event_channel_id per-server."""
        json_str = json.dumps(
            {
                "prod": {
                    "name": "Production",
                    "rcon_host": "factorio-prod",
                    "rcon_port": 27015,
                    "rcon_password": "secret",
                    "event_channel_id": 987654321,
                    "rcon_breakdown_mode": "transition",
                    "rcon_breakdown_interval": 300,
                }
            }
        )
        servers = parse_servers_from_json(json_str)
        assert servers is not None
        assert servers["prod"].event_channel_id == 987654321
        assert servers["prod"].rcon_breakdown_mode == "transition"

    def test_parse_servers_from_json_none(self) -> None:
        assert parse_servers_from_json(None) is None

    def test_parse_servers_from_json_invalid_json(self) -> None:
        assert parse_servers_from_json("{invalid") is None

    def test_parse_servers_from_json_missing_password_becomes_empty_string(self) -> None:
        json_str = json.dumps(
            {"prod": {"name": "Production", "rcon_host": "host", "rcon_port": 27015}}
        )
        servers = parse_servers_from_json(json_str)
        assert servers is not None
        assert servers["prod"].rcon_password == ""


class TestParseServersFromYaml:
    """Tests for parse_servers_from_yaml()."""

    def test_parse_servers_from_yaml_file_missing_returns_none(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "servers.yml"
        servers = parse_servers_from_yaml(yaml_path)
        assert servers is None

    def test_parse_servers_from_yaml_valid(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "servers.yml"
        yaml_path.write_text(
            "servers:\n"
            "  prod:\n"
            "    name: Production\n"
            "    rcon_host: factorio-prod\n"
            "    rcon_port: 27015\n"
            "    rcon_password: secret\n"
        )
        servers = parse_servers_from_yaml(yaml_path)
        assert servers is not None
        assert "prod" in servers
        prod = servers["prod"]
        assert prod.rcon_host == "factorio-prod"
        assert prod.rcon_password == "secret"

    def test_parse_servers_from_yaml_with_per_server_settings(self, tmp_path: Path) -> None:
        """Phase 6: YAML should load per-server event_channel_id and breakdown settings."""
        yaml_path = tmp_path / "servers.yml"
        yaml_path.write_text(
            "servers:\n"
            "  prod:\n"
            "    name: Production\n"
            "    rcon_host: factorio-prod\n"
            "    rcon_port: 27015\n"
            "    rcon_password: secret\n"
            "    event_channel_id: 123456789\n"
            "    rcon_breakdown_mode: transition\n"
            "    rcon_breakdown_interval: 300\n"
        )
        servers = parse_servers_from_yaml(yaml_path)
        assert servers is not None
        prod = servers["prod"]
        assert prod.event_channel_id == 123456789
        assert prod.rcon_breakdown_mode == "transition"
        assert prod.rcon_breakdown_interval == 300

    def test_parse_servers_from_yaml_invalid_tag_raises(self, tmp_path: Path) -> None:
        """Test that invalid server tags raise a ValueError."""
        yaml_path = tmp_path / "servers.yml"
        yaml_path.write_text(
            "servers:\n"
            " Invalid_tag!:\n"
            "  name: Bad\n"
            "  rcon_host: host\n"
            "  rcon_port: 27015\n"
            "  rcon_password: secret\n"
        )

        with pytest.raises(
            ValueError,
            match="Invalid tag 'Invalid_tag!': must be lowercase alphanumeric with hyphens only, 1–16 characters",
        ):
            parse_servers_from_yaml(yaml_path)

    def test_parse_servers_from_yaml_multiple_servers(self, tmp_path: Path) -> None:
        """Test parsing multiple servers with different per-server configs."""
        yaml_path = tmp_path / "servers.yml"
        yaml_path.write_text(
            "servers:\n"
            "  prod:\n"
            "    name: Production\n"
            "    rcon_host: factorio-prod\n"
            "    rcon_port: 27015\n"
            "    rcon_password: secret1\n"
            "    event_channel_id: 111111111\n"
            "    rcon_breakdown_mode: transition\n"
            "  staging:\n"
            "    name: Staging\n"
            "    rcon_host: factorio-stg\n"
            "    rcon_port: 27015\n"
            "    rcon_password: secret2\n"
            "    event_channel_id: 222222222\n"
            "    rcon_breakdown_mode: interval\n"
            "    rcon_breakdown_interval: 600\n"
        )
        servers = parse_servers_from_yaml(yaml_path)

        assert servers is not None
        assert len(servers) == 2
        assert servers["prod"].event_channel_id == 111111111
        assert servers["prod"].rcon_breakdown_mode == "transition"
        assert servers["staging"].event_channel_id == 222222222
        assert servers["staging"].rcon_breakdown_mode == "interval"


# ======================================================================
# Config dataclass and is_multi_server
# ======================================================================

class TestConfigDataclass:
    """Tests for Config dataclass."""

    def test_config_defaults(self) -> None:
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
        )
        assert cfg.patterns_dir == Path("patterns")
        assert cfg.pattern_files is None
        assert cfg.webhook_channels == {}
        assert cfg.rcon_enabled is False
        assert cfg.servers is None
        assert cfg.is_multi_server is False

    def test_config_multi_server_property(self) -> None:
        servers: Dict[str, ServerConfig] = {
            "prod": ServerConfig(
                tag="prod",
                name="Production",
                rcon_host="host",
                rcon_port=27015,
                rcon_password="secret",
            )
        }
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            servers=servers,
        )
        assert cfg.is_multi_server is True

    def test_config_no_global_discord_event_channel_id(self) -> None:
        """Phase 6: Config should NOT have global discord_event_channel_id."""
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
        )
        # discord_event_channel_id should not exist at Config level
        assert not hasattr(cfg, "discord_event_channel_id") or cfg.discord_event_channel_id is None


# ======================================================================
# load_config tests
# ======================================================================

class TestLoadConfig:
    """Tests for load_config()."""

    def test_load_config_minimal_webhook(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/abc")
        monkeypatch.setenv("FACTORIO_LOG_PATH", "/factorio/console.log")

        cfg = load_config()
        assert cfg.discord_webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert cfg.factorio_log_path == Path("/factorio/console.log")
        assert cfg.rcon_enabled is False

    def test_load_config_bot_token_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "x" * 70)
        monkeypatch.setenv("FACTORIO_LOG_PATH", "/factorio/console.log")

        cfg = load_config()
        assert cfg.discord_webhook_url is None
        assert cfg.discord_bot_token == "x" * 70

    def test_load_config_missing_discord_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FACTORIO_LOG_PATH", "/factorio/console.log")

        with pytest.raises(ValueError, match="Either DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN"):
            load_config()

    def test_load_config_missing_log_path_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/abc")

        with pytest.raises(ValueError, match="FACTORIO_LOG_PATH is required"):
            load_config()

    def test_load_config_parses_booleans_and_numbers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/abc")
        monkeypatch.setenv("FACTORIO_LOG_PATH", "/factorio/console.log")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("LOG_FORMAT", "JSON")
        monkeypatch.setenv("HEALTH_CHECK_HOST", "0.0.0.0")
        monkeypatch.setenv("HEALTH_CHECK_PORT", "8080")
        monkeypatch.setenv("PATTERNS_DIR", "custom_patterns")
        monkeypatch.setenv("PATTERN_FILES", '["pattern1.yaml"]')
        monkeypatch.setenv("WEBHOOK_CHANNELS", '{"general": "webhook1"}')
        monkeypatch.setenv("RCON_ENABLED", "true")
        monkeypatch.setenv("RCON_HOST", "factorio.local")
        monkeypatch.setenv("RCON_PORT", "27016")
        monkeypatch.setenv("RCON_PASSWORD", "rcon_secret")
        monkeypatch.setenv("STATS_INTERVAL", "600")
        monkeypatch.setenv("RCON_BREAKDOWN_MODE", "interval")
        monkeypatch.setenv("RCON_BREAKDOWN_INTERVAL", "120")

        cfg = load_config()
        assert cfg.log_level == "debug"
        assert cfg.log_format == "json"
        assert cfg.health_check_host == "0.0.0.0"
        assert cfg.health_check_port == 8080
        assert cfg.patterns_dir == Path("custom_patterns")
        assert cfg.pattern_files == ["pattern1.yaml"]
        assert cfg.webhook_channels == {"general": "webhook1"}
        assert cfg.rcon_enabled is True
        assert cfg.rcon_host == "factorio.local"
        assert cfg.rcon_port == 27016
        assert cfg.rcon_password == "rcon_secret"
        assert cfg.stats_interval == 600
        assert cfg.rcon_breakdown_mode == "interval"
        assert cfg.rcon_breakdown_interval == 120

    def test_load_config_auto_converts_legacy_single_server(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/abc")
        monkeypatch.setenv("FACTORIO_LOG_PATH", "/factorio/console.log")
        monkeypatch.setenv("RCON_ENABLED", "true")
        monkeypatch.setenv("RCON_PASSWORD", "legacy_secret")
        monkeypatch.setenv("RCON_HOST", "legacy-host")
        monkeypatch.setenv("RCON_PORT", "27015")
        monkeypatch.setenv("STATS_INTERVAL", "300")
        monkeypatch.setenv("RCON_BREAKDOWN_MODE", "transition")
        monkeypatch.setenv("RCON_BREAKDOWN_INTERVAL", "300")

        cfg = load_config()
        assert cfg.rcon_enabled is True
        assert cfg.servers is not None
        assert "primary" in cfg.servers


# ======================================================================
# validate_config targeted tests (from test_config_targeted.py)
# ======================================================================

class TestValidateConfigTargeted:
    """Targeted tests for validate_config() branches."""

    def test_validate_config_no_discord_configuration_fails(self) -> None:
        cfg = Config(
            discord_webhook_url=None,
            discord_bot_token=None,
            factorio_log_path=Path("/factorio/console.log"),
        )
        assert validate_config(cfg) is False

    def test_validate_config_webhook_only_succeeds(self) -> None:
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            discord_bot_token=None,
            factorio_log_path=Path("/factorio/console.log"),
        )
        assert validate_config(cfg) is True

    def test_validate_config_bot_token_only_succeeds(self) -> None:
        cfg = Config(
            discord_webhook_url=None,
            discord_bot_token="x" * 70,
            factorio_log_path=Path("/factorio/console.log"),
        )
        assert validate_config(cfg) is True

    def test_validate_config_both_discord_modes_succeed(self) -> None:
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            discord_bot_token="x" * 70,
            factorio_log_path=Path("/factorio/console.log"),
        )
        assert validate_config(cfg) is True

    def test_validate_config_webhook_url_empty_string_fails(self) -> None:
        cfg = Config(
            discord_webhook_url="",
            discord_bot_token=None,
            factorio_log_path=Path("/factorio/console.log"),
        )
        assert validate_config(cfg) is False

    def test_validate_config_bot_token_length_boundaries(self) -> None:
        cfg_50 = Config(
            discord_bot_token="x" * 50,
            factorio_log_path=Path("/factorio/console.log"),
        )
        cfg_49 = Config(
            discord_bot_token="x" * 49,
            factorio_log_path=Path("/factorio/console.log"),
        )
        assert validate_config(cfg_50) is True
        assert validate_config(cfg_49) is True  # warns, but passes

    def test_validate_config_rcon_enabled_no_password_single_server_fails(self) -> None:
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            rcon_enabled=True,
            rcon_password=None,
        )
        assert cfg.is_multi_server is False
        assert validate_config(cfg) is False

    def test_validate_config_rcon_disabled_ignores_password(self) -> None:
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            rcon_enabled=False,
            rcon_password="unused",
        )
        assert validate_config(cfg) is True

    def test_validate_config_multi_server_missing_server_password_fails(self) -> None:
        servers: Dict[str, ServerConfig] = {
            "prod": ServerConfig(
                tag="prod",
                name="Production",
                rcon_host="host",
                rcon_port=27015,
                rcon_password="",  # invalid
            ),
            "stg": ServerConfig(
                tag="stg",
                name="Staging",
                rcon_host="host",
                rcon_port=27015,
                rcon_password="secret",
            ),
        }
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            servers=servers,
        )
        assert cfg.is_multi_server is True
        assert validate_config(cfg) is False

    def test_validate_config_multi_server_all_passwords_present_succeeds(self) -> None:
        servers: Dict[str, ServerConfig] = {
            "prod": ServerConfig(
                tag="prod",
                name="Production",
                rcon_host="host",
                rcon_port=27015,
                rcon_password="secret",
            ),
            "stg": ServerConfig(
                tag="stg",
                name="Staging",
                rcon_host="host",
                rcon_port=27016,
                rcon_password="other",
            ),
        }
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            servers=servers,
        )
        assert validate_config(cfg) is True

    def test_validate_config_invalid_log_level_gets_corrected(self) -> None:
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            log_level="INVALID",
        )
        assert validate_config(cfg) is True
        assert cfg.log_level == "info"
