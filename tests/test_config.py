"""
Comprehensive tests for config.py with 95%+ coverage.

Tests configuration loading, validation, Docker secrets support,
and multi-channel webhook parsing.
"""

import pytest
from pathlib import Path
from typing import Dict, Optional
import os
import sys
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from config import Config, get_config_value_safe, load_config, validate_config


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables before each test."""
    env_vars = [
        "DISCORD_WEBHOOK_URL",
        "BOT_NAME",
        "BOT_AVATAR_URL",
        "FACTORIO_LOG_PATH",
        "PATTERNS_DIR",
        "PATTERN_FILES",
        "WEBHOOK_CHANNELS",
        "HEALTHCHECK_HOST",
        "HEALTHCHECK_PORT",
        "LOG_LEVEL",
        "LOG_FORMAT",
    ]
    
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    
    return monkeypatch


@pytest.fixture
def valid_webhook_url() -> str:
    """Valid Discord webhook URL for testing."""
    return "https://discord.com/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz"


@pytest.fixture
def valid_webhook_channels() -> Dict[str, str]:
    """Valid webhook channels configuration."""
    return {
        "chat": "https://discord.com/api/webhooks/111/chat_token",
        "admin": "https://discord.com/api/webhooks/222/admin_token",
        "milestones": "https://discord.com/api/webhooks/333/milestone_token",
    }


@pytest.fixture
def minimal_env_config(clean_env, valid_webhook_url):
    """Set up minimal required environment configuration."""
    clean_env.setenv("DISCORD_WEBHOOK_URL", valid_webhook_url)
    return clean_env


@pytest.fixture
def full_env_config(clean_env, valid_webhook_url, valid_webhook_channels):
    """Set up full environment configuration with all options."""
    clean_env.setenv("DISCORD_WEBHOOK_URL", valid_webhook_url)
    clean_env.setenv("BOT_NAME", "Test Bot")
    clean_env.setenv("BOT_AVATAR_URL", "https://example.com/avatar.png")
    clean_env.setenv("FACTORIO_LOG_PATH", "/custom/path/console.log")
    clean_env.setenv("PATTERNS_DIR", "custom_patterns")
    clean_env.setenv("PATTERN_FILES", "vanilla.yml,custom.yml,mods.yml")
    
    # Format webhook channels as env var
    channels_str = ",".join([f"{k}={v}" for k, v in valid_webhook_channels.items()])
    clean_env.setenv("WEBHOOK_CHANNELS", channels_str)
    
    clean_env.setenv("HEALTHCHECK_HOST", "127.0.0.1")
    clean_env.setenv("HEALTHCHECK_PORT", "9090")
    clean_env.setenv("LOG_LEVEL", "DEBUG")
    clean_env.setenv("LOG_FORMAT", "console")
    
    return clean_env

# ============================================================================
# Config Dataclass Tests
# ============================================================================

class TestConfigDataclass:
    """Test Config dataclass behavior."""
    
    def test_config_creation_with_required_fields(self, valid_webhook_url):
        """Test creating Config with only required fields."""
        config = Config(discord_webhook_url=valid_webhook_url)
        
        assert config.discord_webhook_url == valid_webhook_url
        assert config.bot_name == "Factorio ISR Bridge"
        assert config.bot_avatar_url is None
        assert isinstance(config.webhook_channels, dict)
        assert len(config.webhook_channels) == 0
        assert config.factorio_log_path == Path("logs/console.log")
        assert config.patterns_dir == Path("patterns")
        assert config.pattern_files is None
        assert config.healthcheck_host == "0.0.0.0"
        assert config.healthcheck_port == 8080
        assert config.loglevel == "info"
        assert config.logformat == "json"
    
    def test_config_creation_with_all_fields(self, valid_webhook_url, valid_webhook_channels):
        """Test creating Config with all fields specified."""
        config = Config(
            discord_webhook_url=valid_webhook_url,
            bot_name="Custom Bot",
            bot_avatar_url="https://example.com/avatar.png",
            webhook_channels=valid_webhook_channels,
            factorio_log_path=Path("/custom/log.txt"),
            patterns_dir=Path("/custom/patterns"),
            pattern_files=["pattern1.yml", "pattern2.yml"],
            healthcheck_host="127.0.0.1",
            healthcheck_port=9090,
            loglevel="debug",
            logformat="console",
        )
        
        assert config.discord_webhook_url == valid_webhook_url
        assert config.bot_name == "Custom Bot"
        assert config.bot_avatar_url == "https://example.com/avatar.png"
        assert config.webhook_channels == valid_webhook_channels
        assert config.factorio_log_path == Path("/custom/log.txt")
        assert config.patterns_dir == Path("/custom/patterns")
        assert config.pattern_files == ["pattern1.yml", "pattern2.yml"]
        assert config.healthcheck_host == "127.0.0.1"
        assert config.healthcheck_port == 9090
        assert config.loglevel == "debug"
        assert config.logformat == "console"
    
    def test_config_webhook_channels_default_factory(self, valid_webhook_url):
        """Test that webhook_channels uses default_factory to create independent dicts."""
        config1 = Config(discord_webhook_url=valid_webhook_url)
        config2 = Config(discord_webhook_url=valid_webhook_url)
        
        # Both should have empty dicts
        assert config1.webhook_channels == {}
        assert config2.webhook_channels == {}
        
        # But they should be different dict objects (not shared)
        assert config1.webhook_channels is not config2.webhook_channels
        
        # Modifying one should not affect the other
        config1.webhook_channels["test"] = "value"
        assert "test" in config1.webhook_channels
        assert "test" not in config2.webhook_channels
    
    def test_config_webhook_channels_is_dict_by_default(self, valid_webhook_url):
        """Test that webhook_channels defaults to empty dict, not None."""
        config = Config(discord_webhook_url=valid_webhook_url)
        
        assert isinstance(config.webhook_channels, dict)
        assert config.webhook_channels == {}
    
    def test_config_type_correctness(self, valid_webhook_url, valid_webhook_channels):
        """Test that all fields have correct types."""
        config = Config(
            discord_webhook_url=valid_webhook_url,
            webhook_channels=valid_webhook_channels,
        )
        
        assert isinstance(config.discord_webhook_url, str)
        assert isinstance(config.bot_name, str)
        assert config.bot_avatar_url is None or isinstance(config.bot_avatar_url, str)
        assert isinstance(config.webhook_channels, dict)
        assert isinstance(config.factorio_log_path, Path)
        assert isinstance(config.patterns_dir, Path)
        assert config.pattern_files is None or isinstance(config.pattern_files, list)
        assert isinstance(config.healthcheck_host, str)
        assert isinstance(config.healthcheck_port, int)
        assert isinstance(config.loglevel, str)
        assert isinstance(config.logformat, str)



# ============================================================================
# get_config_value_safe() Tests
# ============================================================================

class TestGetConfigValueSafe:
    """Test get_config_value_safe() function."""
    
    def test_returns_env_var_when_set(self, clean_env):
        """Test that environment variable is returned when set."""
        clean_env.setenv("TEST_VAR", "env_value")
        
        result = get_config_value_safe("TEST_VAR", default="default_value")
        
        assert result == "env_value"
    
    def test_returns_default_when_env_var_not_set(self, clean_env):
        """Test that default is returned when env var not set."""
        result = get_config_value_safe("NONEXISTENT_VAR", default="default_value")
        
        assert result == "default_value"
    
    def test_returns_empty_string_when_no_default(self, clean_env):
        """Test that empty string is returned when no default provided."""
        result = get_config_value_safe("NONEXISTENT_VAR")
        
        assert result == ""
    
    def test_reads_from_docker_secret_file(self, clean_env, tmp_path, monkeypatch):
        """Test reading from Docker secrets file."""
        # Create a temporary secrets directory structure
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        secret_file = secrets_dir / "TEST_SECRET"
        secret_file.write_text("secret_value\n")
        
        # Patch Path in the config module to redirect /run/secrets
        import config as config_module
        original_path = Path
        
        class MockPath(type(Path())):
            def __new__(cls, *args, **kwargs):
                if args and "/run/secrets/" in str(args[0]):
                    # Redirect to our temp directory
                    key = str(args[0]).replace("/run/secrets/", "")
                    return original_path(secrets_dir / key)
                return original_path(*args, **kwargs)
        
        monkeypatch.setattr(config_module, "Path", MockPath)
        
        result = config_module.get_config_value_safe("TEST_SECRET", default="default")
        
        assert result == "secret_value"
    
    def test_handles_exception_reading_secret_file(self, clean_env, tmp_path, monkeypatch):
        """Test that exceptions when reading secret files are handled gracefully."""
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        # Create a directory instead of a file (will cause read error)
        secret_dir = secrets_dir / "UNREADABLE_SECRET"
        secret_dir.mkdir()
        
        # Patch Path in the config module
        import config as config_module
        original_path = Path
        
        class MockPath(type(Path())):
            def __new__(cls, *args, **kwargs):
                if args and "/run/secrets/" in str(args[0]):
                    key = str(args[0]).replace("/run/secrets/", "")
                    return original_path(secrets_dir / key)
                return original_path(*args, **kwargs)
        
        monkeypatch.setattr(config_module, "Path", MockPath)
        
        result = config_module.get_config_value_safe("UNREADABLE_SECRET", default="fallback")
        
        # Should return default when file can't be read
        assert result == "fallback"
    
    def test_env_var_takes_precedence_over_secret(self, clean_env, tmp_path, monkeypatch):
        """Test that environment variable takes precedence over Docker secret."""
        clean_env.setenv("PRIORITY_TEST", "env_value")
        
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        secret_file = secrets_dir / "PRIORITY_TEST"
        secret_file.write_text("secret_value")
        
        # Patch Path in the config module
        import config as config_module
        original_path = Path
        
        class MockPath(type(Path())):
            def __new__(cls, *args, **kwargs):
                if args and "/run/secrets/" in str(args[0]):
                    key = str(args[0]).replace("/run/secrets/", "")
                    return original_path(secrets_dir / key)
                return original_path(*args, **kwargs)
        
        monkeypatch.setattr(config_module, "Path", MockPath)
        
        result = config_module.get_config_value_safe("PRIORITY_TEST", default="default")
        
        # Environment variable should win
        assert result == "env_value"
    
    def test_secret_file_strips_whitespace(self, clean_env, tmp_path, monkeypatch):
        """Test that secret values have whitespace stripped."""
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        secret_file = secrets_dir / "WHITESPACE_SECRET"
        secret_file.write_text("  secret_value  \n\n")
        
        # Patch Path in the config module
        import config as config_module
        original_path = Path
        
        class MockPath(type(Path())):
            def __new__(cls, *args, **kwargs):
                if args and "/run/secrets/" in str(args[0]):
                    key = str(args[0]).replace("/run/secrets/", "")
                    return original_path(secrets_dir / key)
                return original_path(*args, **kwargs)
        
        monkeypatch.setattr(config_module, "Path", MockPath)
        
        result = config_module.get_config_value_safe("WHITESPACE_SECRET", default="default")
        
        assert result == "secret_value"
    
    def test_nonexistent_secret_file_returns_default(self, clean_env, tmp_path, monkeypatch):
        """Test that nonexistent secret file returns default value."""
        secrets_dir = tmp_path / "run" / "secrets"
        secrets_dir.mkdir(parents=True)
        
        # Patch Path in the config module
        import config as config_module
        original_path = Path
        
        class MockPath(type(Path())):
            def __new__(cls, *args, **kwargs):
                if args and "/run/secrets/" in str(args[0]):
                    key = str(args[0]).replace("/run/secrets/", "")
                    return original_path(secrets_dir / key)
                return original_path(*args, **kwargs)
        
        monkeypatch.setattr(config_module, "Path", MockPath)
        
        result = config_module.get_config_value_safe("NONEXISTENT_SECRET", default="default")
        
        assert result == "default"


# ============================================================================
# load_config() Tests
# ============================================================================

class TestLoadConfig:
    """Test load_config() function."""
    
    def test_load_config_with_minimal_env(self, minimal_env_config, valid_webhook_url):
        """Test loading config with only required environment variables."""
        config = load_config()
        
        assert config.discord_webhook_url == valid_webhook_url
        assert config.bot_name == "Factorio ISR Bridge"
        assert config.bot_avatar_url is None
        assert config.webhook_channels == {}
        assert config.factorio_log_path == Path("logs/console.log")
        assert config.patterns_dir == Path("patterns")
        assert config.pattern_files is None
        assert config.healthcheck_host == "0.0.0.0"
        assert config.healthcheck_port == 8080
        assert config.loglevel == "info"
        assert config.logformat == "json"
    
    def test_load_config_with_full_env(self, full_env_config, valid_webhook_url, valid_webhook_channels):
        """Test loading config with all environment variables set."""
        config = load_config()
        
        assert config.discord_webhook_url == valid_webhook_url
        assert config.bot_name == "Test Bot"
        assert config.bot_avatar_url == "https://example.com/avatar.png"
        assert config.webhook_channels == valid_webhook_channels
        assert config.factorio_log_path == Path("/custom/path/console.log")
        assert config.patterns_dir == Path("custom_patterns")
        assert config.pattern_files == ["vanilla.yml", "custom.yml", "mods.yml"]
        assert config.healthcheck_host == "127.0.0.1"
        assert config.healthcheck_port == 9090
        assert config.loglevel == "debug"
        assert config.logformat == "console"
    
    def test_load_config_raises_when_webhook_url_missing(self, clean_env):
        """Test that ValueError is raised when DISCORD_WEBHOOK_URL is not set."""
        with pytest.raises(ValueError, match="DISCORD_WEBHOOK_URL is required"):
            load_config()
    
    def test_load_config_bot_avatar_url_none_when_empty(self, minimal_env_config):
        """Test that bot_avatar_url is None when empty string is provided."""
        minimal_env_config.setenv("BOT_AVATAR_URL", "")
        
        config = load_config()
        
        assert config.bot_avatar_url is None
    
    def test_load_config_bot_avatar_url_set_when_provided(self, minimal_env_config):
        """Test that bot_avatar_url is set when non-empty string is provided."""
        avatar_url = "https://example.com/avatar.png"
        minimal_env_config.setenv("BOT_AVATAR_URL", avatar_url)
        
        config = load_config()
        
        assert config.bot_avatar_url == avatar_url
    
    def test_load_config_parses_pattern_files(self, minimal_env_config):
        """Test that PATTERN_FILES is correctly parsed as comma-separated list."""
        minimal_env_config.setenv("PATTERN_FILES", "file1.yml, file2.yml , file3.yml")
        
        config = load_config()
        
        assert config.pattern_files == ["file1.yml", "file2.yml", "file3.yml"]
    
    def test_load_config_pattern_files_none_when_empty(self, minimal_env_config):
        """Test that pattern_files is None when PATTERN_FILES is empty."""
        minimal_env_config.setenv("PATTERN_FILES", "")
        
        config = load_config()
        
        assert config.pattern_files is None
    
    def test_load_config_parses_webhook_channels(self, minimal_env_config):
        """Test that WEBHOOK_CHANNELS is correctly parsed."""
        channels = "chat=https://discord.com/api/webhooks/111/token1,admin=https://discord.com/api/webhooks/222/token2"
        minimal_env_config.setenv("WEBHOOK_CHANNELS", channels)
        
        config = load_config()
        
        assert len(config.webhook_channels) == 2
        assert config.webhook_channels["chat"] == "https://discord.com/api/webhooks/111/token1"
        assert config.webhook_channels["admin"] == "https://discord.com/api/webhooks/222/token2"
    
    def test_load_config_webhook_channels_empty_when_not_set(self, minimal_env_config):
        """Test that webhook_channels is empty dict when WEBHOOK_CHANNELS not set."""
        config = load_config()
        
        assert config.webhook_channels == {}
    
    def test_load_config_ignores_malformed_webhook_channels(self, minimal_env_config):
        """Test that malformed webhook channel entries are ignored."""
        channels = "valid=https://discord.com/api/webhooks/111/token,invalid_no_equals,another=https://discord.com/api/webhooks/222/token"
        minimal_env_config.setenv("WEBHOOK_CHANNELS", channels)
        
        config = load_config()
        
        # Only valid entries should be parsed
        assert len(config.webhook_channels) == 2
        assert "valid" in config.webhook_channels
        assert "another" in config.webhook_channels
        assert "invalid_no_equals" not in config.webhook_channels
    
    def test_load_config_webhook_channels_strips_whitespace(self, minimal_env_config):
        """Test that webhook channel names and URLs have whitespace stripped."""
        channels = " chat = https://discord.com/api/webhooks/111/token , admin = https://discord.com/api/webhooks/222/token "
        minimal_env_config.setenv("WEBHOOK_CHANNELS", channels)
        
        config = load_config()
        
        assert "chat" in config.webhook_channels
        assert "admin" in config.webhook_channels
        assert config.webhook_channels["chat"] == "https://discord.com/api/webhooks/111/token"
    
    def test_load_config_healthcheck_port_as_int(self, minimal_env_config):
        """Test that HEALTHCHECK_PORT is correctly converted to int."""
        minimal_env_config.setenv("HEALTHCHECK_PORT", "3000")
        
        config = load_config()
        
        assert isinstance(config.healthcheck_port, int)
        assert config.healthcheck_port == 3000
    
    def test_load_config_loglevel_lowercase(self, minimal_env_config):
        """Test that LOG_LEVEL is converted to lowercase."""
        minimal_env_config.setenv("LOG_LEVEL", "DEBUG")
        
        config = load_config()
        
        assert config.loglevel == "debug"
    
    def test_load_config_logformat_lowercase(self, minimal_env_config):
        """Test that LOG_FORMAT is converted to lowercase."""
        minimal_env_config.setenv("LOG_FORMAT", "CONSOLE")
        
        config = load_config()
        
        assert config.logformat == "console"


# ============================================================================
# validate_config() Tests
# ============================================================================

class TestValidateConfig:
    """Test validate_config() function."""
    
    def test_validate_config_success_with_minimal_config(self, valid_webhook_url):
        """Test that validation passes with minimal valid configuration."""
        config = Config(discord_webhook_url=valid_webhook_url)
        
        result = validate_config(config)
        
        assert result is True
    
    def test_validate_config_success_with_webhook_channels(self, valid_webhook_url, valid_webhook_channels):
        """Test that validation passes with valid webhook channels."""
        config = Config(
            discord_webhook_url=valid_webhook_url,
            webhook_channels=valid_webhook_channels
        )
        
        result = validate_config(config)
        
        assert result is True
    
    def test_validate_config_fails_when_webhook_url_empty(self):
        """Test that validation fails when discord_webhook_url is empty."""
        config = Config(discord_webhook_url="")
        
        result = validate_config(config)
        
        assert result is False
    
    def test_validate_config_fails_when_webhook_url_invalid_format(self):
        """Test that validation fails when webhook URL has invalid format."""
        invalid_urls = [
            "http://discord.com/api/webhooks/123/token",  # http instead of https
            "https://discord.com/webhooks/123/token",  # missing 'api'
            "https://example.com/api/webhooks/123/token",  # wrong domain
            "not-a-url",
            "https://discord.com/api/webhooks",  # incomplete
        ]
        
        for invalid_url in invalid_urls:
            config = Config(discord_webhook_url=invalid_url)
            result = validate_config(config)
            assert result is False, f"Should reject invalid URL: {invalid_url}"
    
    def test_validate_config_fails_when_channel_webhook_invalid(self, valid_webhook_url):
        """Test that validation fails when a channel webhook URL is invalid."""
        config = Config(
            discord_webhook_url=valid_webhook_url,
            webhook_channels={
                "valid": "https://discord.com/api/webhooks/111/token",
                "invalid": "http://discord.com/api/webhooks/222/token",  # http not https
            }
        )
        
        result = validate_config(config)
        
        assert result is False
    
    def test_validate_config_accepts_valid_webhook_formats(self):
        """Test that various valid webhook URL formats are accepted."""
        valid_urls = [
            "https://discord.com/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz",
            "https://discord.com/api/webhooks/987654321/ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "https://discord.com/api/webhooks/111111111/abc123ABC-_",
        ]
        
        for valid_url in valid_urls:
            config = Config(discord_webhook_url=valid_url)
            result = validate_config(config)
            assert result is True, f"Should accept valid URL: {valid_url}"
    
    def test_validate_config_checks_all_webhook_channels(self, valid_webhook_url):
        """Test that all webhook channels are validated."""
        config = Config(
            discord_webhook_url=valid_webhook_url,
            webhook_channels={
                "channel1": "https://discord.com/api/webhooks/111/token1",
                "channel2": "https://discord.com/api/webhooks/222/token2",
                "channel3": "https://discord.com/api/webhooks/333/token3",
            }
        )
        
        result = validate_config(config)
        
        assert result is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestConfigIntegration:
    """Integration tests for complete config workflows."""
    
    def test_load_and_validate_minimal_config(self, minimal_env_config):
        """Test loading and validating minimal configuration."""
        config = load_config()
        is_valid = validate_config(config)
        
        assert is_valid is True
    
    def test_load_and_validate_full_config(self, full_env_config):
        """Test loading and validating full configuration."""
        config = load_config()
        is_valid = validate_config(config)
        
        assert is_valid is True
    
    def test_load_with_invalid_webhook_fails_validation(self, clean_env):
        """Test that loading with invalid webhook URL fails validation."""
        clean_env.setenv("DISCORD_WEBHOOK_URL", "http://invalid-url.com")
        
        config = load_config()
        is_valid = validate_config(config)
        
        assert is_valid is False
    
    def test_config_immutability_after_load(self, minimal_env_config, valid_webhook_url):
        """Test that loaded config can be used as expected."""
        config = load_config()
        
        # Verify we can read all fields
        assert config.discord_webhook_url == valid_webhook_url
        assert isinstance(config.webhook_channels, dict)
        assert isinstance(config.factorio_log_path, Path)
        assert isinstance(config.patterns_dir, Path)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_healthcheck_port_invalid_raises_exception(self, minimal_env_config):
        """Test that invalid HEALTHCHECK_PORT raises ValueError."""
        minimal_env_config.setenv("HEALTHCHECK_PORT", "not_a_number")
        
        with pytest.raises(ValueError):
            load_config()
    
    def test_empty_webhook_channels_string(self, minimal_env_config):
        """Test that empty WEBHOOK_CHANNELS string results in empty dict."""
        minimal_env_config.setenv("WEBHOOK_CHANNELS", "")
        
        config = load_config()
        
        assert config.webhook_channels == {}
    
    def test_webhook_channels_with_only_commas(self, minimal_env_config):
        """Test that WEBHOOK_CHANNELS with only commas results in empty dict."""
        minimal_env_config.setenv("WEBHOOK_CHANNELS", ",,,")
        
        config = load_config()
        
        assert config.webhook_channels == {}
    
    def test_pattern_files_single_file(self, minimal_env_config):
        """Test that single pattern file is parsed correctly."""
        minimal_env_config.setenv("PATTERN_FILES", "single.yml")
        
        config = load_config()
        
        assert config.pattern_files == ["single.yml"]
    
    def test_webhook_channels_url_with_equals_in_token(self, minimal_env_config):
        """Test parsing webhook channel with '=' character in the URL token."""
        # Some webhook tokens might contain '=' (base64 encoding)
        channels = "chat=https://discord.com/api/webhooks/123/token=withequals"
        minimal_env_config.setenv("WEBHOOK_CHANNELS", channels)
        
        config = load_config()
        
        assert config.webhook_channels["chat"] == "https://discord.com/api/webhooks/123/token=withequals"
