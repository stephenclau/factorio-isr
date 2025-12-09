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

    def test_read_secret_local_empty_falls_through_to_docker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty local files should cause read_secret to try Docker secrets."""
        monkeypatch.chdir(tmp_path)
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "token.txt").write_text(" ")
        (secrets_dir / "token").write_text("\t")

        checked_paths: list[str] = []

        def mock_exists(p: Path) -> bool:
            s = str(p)
            checked_paths.append(s)
            return (
                s.endswith(".secrets/token.txt")
                or s.endswith(".secrets/token")
                or s.endswith("/run/secrets/token")
            )

        def mock_read_text(p: Path, *args: Any, **kwargs: Any) -> str:
            s = str(p)
            if s.endswith("/run/secrets/token"):
                return "docker_value"
            return " "

        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                result = read_secret("token")

        assert result == "docker_value"
        assert any("/run/secrets/token" in p for p in checked_paths)

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

    def test_read_secret_docker_empty_returns_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty Docker secret should result in default."""
        monkeypatch.chdir(tmp_path)

        def mock_exists(p: Path) -> bool:
            return str(p).endswith("/run/secrets/EMPTY")

        def mock_read_text(p: Path, *args: Any, **kwargs: Any) -> str:
            return " \n\t "

        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                result = read_secret("EMPTY", default=None)

        assert result is None

    def test_read_secret_checks_all_three_locations_when_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Confirm all three locations (.txt, plain, Docker) are consulted when earlier ones are empty."""
        monkeypatch.chdir(tmp_path)
        secrets_dir = tmp_path / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "token.txt").write_text("")
        (secrets_dir / "token").write_text(" ")

        checked_paths: list[str] = []

        def mock_exists(p: Path) -> bool:
            s = str(p)
            checked_paths.append(s)
            return "token" in s or "/run/secrets/" in s

        def mock_read_text(p: Path, *args: Any, **kwargs: Any) -> str:
            s = str(p)
            if "/run/secrets/" in s:
                return "docker_token"
            return ""

        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "read_text", mock_read_text):
                result = read_secret("token")

        assert result == "docker_token"
        assert any("token.txt" in p for p in checked_paths)
        assert any("/run/secrets/" in p for p in checked_paths)


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

    def test_parse_webhook_channels_type_error(self) -> None:
        assert parse_webhook_channels(123) == {}  # type: ignore[arg-type]


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

    def test_parse_pattern_files_type_error(self) -> None:
        assert parse_pattern_files(123) is None  # type: ignore[arg-type]


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
        assert cfg.discord_event_channel_id is None
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
        monkeypatch.setenv("SEND_TEST_MESSAGE", "true")
        monkeypatch.setenv("RCON_ENABLED", "true")
        monkeypatch.setenv("RCON_HOST", "factorio.local")
        monkeypatch.setenv("RCON_PORT", "27016")
        monkeypatch.setenv("RCON_PASSWORD", "rcon_secret")
        monkeypatch.setenv("STATS_INTERVAL", "600")
        monkeypatch.setenv("RCON_BREAKDOWN_MODE", "interval")
        monkeypatch.setenv("RCON_BREAKDOWN_INTERVAL", "120")
        monkeypatch.setenv("DISCORD_EVENT_CHANNEL_ID", "1234567890")

        cfg = load_config()
        assert cfg.log_level == "debug"
        assert cfg.log_format == "json"
        assert cfg.health_check_host == "0.0.0.0"
        assert cfg.health_check_port == 8080
        assert cfg.patterns_dir == Path("custom_patterns")
        assert cfg.pattern_files == ["pattern1.yaml"]
        assert cfg.webhook_channels == {"general": "webhook1"}
        assert cfg.send_test_message is True
        assert cfg.rcon_enabled is True
        assert cfg.rcon_host == "factorio.local"
        assert cfg.rcon_port == 27016
        assert cfg.rcon_password == "rcon_secret"
        assert cfg.stats_interval == 600
        assert cfg.rcon_breakdown_mode == "interval"
        assert cfg.rcon_breakdown_interval == 120
        assert cfg.discord_event_channel_id == 1234567890

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

# ========================================================================
# PHASE 6: parse_servers_from_yaml Tests
# ========================================================================

def test_parse_servers_from_yaml_file_not_found(tmp_path: Path) -> None:
    """Test parse_servers_from_yaml when file doesn't exist."""
    yaml_path = tmp_path / "nonexistent.yml"
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is None


def test_parse_servers_from_yaml_missing_servers_key(tmp_path: Path) -> None:
    """Test parse_servers_from_yaml with missing 'servers' key."""
    yaml_path = tmp_path / "invalid.yml"
    yaml_path.write_text("other_key: value\n")
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is None


def test_parse_servers_from_yaml_empty_file(tmp_path: Path) -> None:
    """Test parse_servers_from_yaml with empty file."""
    yaml_path = tmp_path / "empty.yml"
    yaml_path.write_text("")
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is None


def test_parse_servers_from_yaml_success_with_password(tmp_path: Path) -> None:
    """Test successful parsing with password in YAML."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  prod:
    name: "Production"
    description: "Main server"
    rcon_host: "factorio-prod"
    rcon_port: 27015
    rcon_password: "secret123"
    event_channel_id: 123456789
    stats_interval: 300
"""
    yaml_path.write_text(yaml_content)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is not None
    assert "prod" in result
    assert result["prod"].name == "Production"
    assert result["prod"].rcon_host == "factorio-prod"
    assert result["prod"].rcon_port == 27015
    assert result["prod"].rcon_password == "secret123"
    assert result["prod"].description == "Main server"
    assert result["prod"].event_channel_id == 123456789


def test_parse_servers_from_yaml_default_values(tmp_path: Path) -> None:
    """Test parsing with default values for optional fields."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  test:
    name: "Test Server"
    rcon_host: "localhost"
    rcon_password: "test"
"""
    yaml_path.write_text(yaml_content)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is not None
    assert result["test"].rcon_port == 27015  # Default
    assert result["test"].stats_interval == 300  # Default
    assert result["test"].description is None
    assert result["test"].event_channel_id is None
    assert result["test"].rcon_breakdown_mode == "transition"
    assert result["test"].rcon_breakdown_interval == 300


def test_parse_servers_from_yaml_password_from_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test password loading from secrets when not in YAML."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  prod:
    name: "Production"
    rcon_host: "factorio-prod"
"""
    yaml_path.write_text(yaml_content)
    
    # Mock read_secret to return a password
    def mock_read_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
        if secret_name == "RCON_PASSWORD_PROD":
            return "secret_from_file"
        return default
    
    monkeypatch.setattr("config.read_secret", mock_read_secret)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is not None
    assert result["prod"].rcon_password == "secret_from_file"


def test_parse_servers_from_yaml_password_fallback_generic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback to generic RCON_PASSWORD secret."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  test:
    name: "Test"
    rcon_host: "localhost"
"""
    yaml_path.write_text(yaml_content)
    
    # Mock read_secret to return generic password
    def mock_read_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
        if secret_name == "RCON_PASSWORD":
            return "generic_secret"
        return default
    
    monkeypatch.setattr("config.read_secret", mock_read_secret)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is not None
    assert result["test"].rcon_password == "generic_secret"


def test_parse_servers_from_yaml_invalid_tag_format(tmp_path: Path) -> None:
    """Test validation failure for invalid tag format."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  INVALID_TAG:
    name: "Invalid"
    rcon_host: "localhost"
    rcon_password: "test"
"""
    yaml_path.write_text(yaml_content)
    
    with pytest.raises(ValueError, match="Invalid tag"):
        parse_servers_from_yaml(yaml_path)


def test_parse_servers_from_yaml_tag_too_long(tmp_path: Path) -> None:
    """Test validation failure for tag longer than 16 chars."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  this-is-way-too-long-tag:
    name: "Test"
    rcon_host: "localhost"
    rcon_password: "test"
"""
    yaml_path.write_text(yaml_content)
    
    with pytest.raises(ValueError, match="Invalid tag"):
        parse_servers_from_yaml(yaml_path)


def test_parse_servers_from_yaml_missing_required_field(tmp_path: Path) -> None:
    """Test error when required field 'name' is missing causes KeyError."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  prod:
    rcon_host: "localhost"
    rcon_password: "test"
"""
    yaml_path.write_text(yaml_content)
    
    # KeyError is caught by the outer exception handler and None is returned
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is None



def test_parse_servers_from_yaml_multiple_servers(tmp_path: Path) -> None:
    """Test parsing multiple servers."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  prod:
    name: "Production"
    rcon_host: "factorio-prod"
    rcon_password: "secret1"
  staging:
    name: "Staging"
    rcon_host: "factorio-stg"
    rcon_password: "secret2"
  dev:
    name: "Development"
    rcon_host: "localhost"
    rcon_password: "secret3"
"""
    yaml_path.write_text(yaml_content)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is not None
    assert len(result) == 3
    assert "prod" in result
    assert "staging" in result
    assert "dev" in result


def test_parse_servers_from_yaml_all_optional_fields(tmp_path: Path) -> None:
    """Test parsing with all optional fields present."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  prod:
    name: "Production"
    rcon_host: "factorio-prod"
    rcon_port: 27020
    rcon_password: "secret"
    description: "24/7 main server"
    event_channel_id: 987654321
    stats_interval: 600
    rcon_breakdown_mode: "interval"
    rcon_breakdown_interval: 900
    collect_ups: true
    collect_evolution: false
    enable_alerts: true
    alert_check_interval: 120
    alert_samples_required: 5
    ups_warning_threshold: 50.0
    ups_recovery_threshold: 55.0
    alert_cooldown: 600
    ups_ema_alpha: 0.3
"""
    yaml_path.write_text(yaml_content)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is not None
    server = result["prod"]
    assert server.rcon_port == 27020
    assert server.description == "24/7 main server"
    assert server.stats_interval == 600
    assert server.rcon_breakdown_mode == "interval"
    assert server.rcon_breakdown_interval == 900
    assert server.collect_ups is True
    assert server.collect_evolution is False
    assert server.enable_alerts is True
    assert server.alert_check_interval == 120
    assert server.alert_samples_required == 5
    assert server.ups_warning_threshold == 50.0
    assert server.ups_recovery_threshold == 55.0
    assert server.alert_cooldown == 600
    assert server.ups_ema_alpha == 0.3


def test_parse_servers_from_yaml_invalid_yaml_syntax(tmp_path: Path) -> None:
    """Test handling of invalid YAML syntax."""
    yaml_path = tmp_path / "invalid.yml"
    yaml_path.write_text("servers:\n  prod:\n    name: [invalid yaml\n")
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is None  # Should catch YAML parse error


def test_parse_servers_from_yaml_no_yaml_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handling when PyYAML is not installed."""
    yaml_path = tmp_path / "servers.yml"
    yaml_path.write_text("servers:\n  prod:\n    name: Test\n")
    
    # Mock import to fail
    import builtins
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("No module named yaml")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is None


def test_parse_servers_from_yaml_io_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handling of file I/O errors."""
    yaml_path = tmp_path / "servers.yml"
    yaml_path.write_text("servers:\n  prod:\n    name: Test\n")
    
    # Make file unreadable
    original_open = open
    
    def mock_open(*args, **kwargs):
        if str(yaml_path) in str(args[0]):
            raise IOError("Permission denied")
        return original_open(*args, **kwargs)
    
    monkeypatch.setattr("builtins.open", mock_open)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is None


def test_parse_servers_from_yaml_empty_password_uses_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that empty password string in YAML falls back to secrets."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  prod:
    name: "Production"
    rcon_host: "localhost"
    rcon_password: ""
"""
    yaml_path.write_text(yaml_content)
    
    # Mock read_secret to return a password
    def mock_read_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
        if secret_name == "RCON_PASSWORD_PROD":
            return "from_secret"
        return default
    
    monkeypatch.setattr("config.read_secret", mock_read_secret)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is not None
    assert result["prod"].rcon_password == "from_secret"


def test_parse_servers_from_yaml_breakdown_mode_case_insensitive(tmp_path: Path) -> None:
    """Test that rcon_breakdown_mode is lowercased."""
    yaml_path = tmp_path / "servers.yml"
    yaml_content = """
servers:
  prod:
    name: "Production"
    rcon_host: "localhost"
    rcon_password: "test"
    rcon_breakdown_mode: "INTERVAL"
"""
    yaml_path.write_text(yaml_content)
    
    result = parse_servers_from_yaml(yaml_path)
    
    assert result is not None
    assert result["prod"].rcon_breakdown_mode == "interval"  # Lowercased
