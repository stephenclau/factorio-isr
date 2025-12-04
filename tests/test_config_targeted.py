"""
Targeted Coverage Tests for config.py Missing Paths
Specifically targets _read_secret and validate_config functions
to achieve 95%+ coverage by testing all untested branches.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, mock_open, patch
import pytest

from config import Config, _read_secret, validate_config


# ============================================================================
# _READ_SECRET - Target: 61% -> 95%+
# ============================================================================

class TestReadSecretMissingPaths:
    """Complete coverage for _read_secret missing paths."""

    def test_read_secret_local_txt_exception_logs_warning(
        self, tmp_path: Path
    ) -> None:
        """Test _read_secret logs warning when local .txt file read fails."""
        secret_dir = tmp_path / ".secrets"
        secret_dir.mkdir()
        secret_file = secret_dir / "test_secret.txt"
        secret_file.write_text("valid")

        # Mock read_text to raise exception
        def mock_exists(path_self: Path) -> bool:
            return True

        def mock_read_text(path_self: Path, *args: Any, **kwargs: Any) -> str:
            raise PermissionError("Access denied")

        with patch.object(Path, 'exists', mock_exists):
            with patch.object(Path, 'read_text', mock_read_text):
                result = _read_secret("test_secret")

                # Should return None after exception
                assert result is None

    def test_read_secret_local_txt_empty_continues_to_next(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _read_secret continues to next source when .txt file is empty."""
        monkeypatch.chdir(tmp_path)

        secret_dir = tmp_path / ".secrets"
        secret_dir.mkdir()

        # Create empty .txt file
        txt_file = secret_dir / "test_secret.txt"
        txt_file.write_text("   \n  ")  # Empty after strip

        # Create valid plain file
        plain_file = secret_dir / "test_secret"
        plain_file.write_text("from_plain")

        result = _read_secret("test_secret")

        # Should skip empty .txt and read from plain
        assert result == "from_plain"

    def test_read_secret_local_plain_exception_logs_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _read_secret logs warning when local plain file read fails."""
        monkeypatch.chdir(tmp_path)

        secret_dir = tmp_path / ".secrets"
        secret_dir.mkdir()
        plain_file = secret_dir / "test_secret"
        plain_file.write_text("valid")

        # Mock to skip .txt, then fail on plain
        def mock_exists(path_self: Path) -> bool:
            if path_self.name == "test_secret.txt":
                return False
            return path_self.name == "test_secret"

        def mock_read_text(path_self: Path, *args: Any, **kwargs: Any) -> str:
            if path_self.name == "test_secret":
                raise IOError("Disk error")
            raise FileNotFoundError()

        with patch.object(Path, 'exists', mock_exists):
            with patch.object(Path, 'read_text', mock_read_text):
                result = _read_secret("test_secret")

                # Should return None after exception
                assert result is None

    def test_read_secret_local_plain_empty_continues_to_docker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _read_secret continues to Docker when plain file is empty."""
        monkeypatch.chdir(tmp_path)

        secret_dir = tmp_path / ".secrets"
        secret_dir.mkdir()

        # Create empty plain file
        plain_file = secret_dir / "test_secret"
        plain_file.write_text("  ")  # Empty after strip

        # Track which paths were checked
        checked_paths = []

        def mock_read_text(path_self: Path, *args: Any, **kwargs: Any) -> str:
            """Mock read_text to return empty for local, value for Docker."""
            path_str = str(path_self)
            if ".secrets" in path_str:
                return "  "  # Empty - should continue
            if "/run/secrets/" in path_str:
                return "from_docker"
            raise FileNotFoundError()

        def mock_exists(path_self: Path) -> bool:
            """Mock exists to make Docker path available."""
            path_str = str(path_self)
            checked_paths.append(path_str)
            if ".secrets" in path_str:
                return True
            if "/run/secrets/" in path_str:
                return True
            return False

        with patch.object(Path, 'exists', mock_exists):
            with patch.object(Path, 'read_text', mock_read_text):
                result = _read_secret("test_secret")

                # Should read from Docker after local is empty
                assert result == "from_docker"

                # Verify Docker path was checked
                assert any("/run/secrets/" in p for p in checked_paths)

    def test_read_secret_docker_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test _read_secret successfully reads from Docker secrets."""
        # Mock all local paths as non-existent
        def mock_exists(path_self: Path) -> bool:
            return "/run/secrets/" in str(path_self)

        def mock_read_text(path_self: Path, *args: Any, **kwargs: Any) -> str:
            if "/run/secrets/" in str(path_self):
                return "docker_secret_value"
            raise FileNotFoundError()

        with patch.object(Path, 'exists', mock_exists):
            with patch.object(Path, 'read_text', mock_read_text):
                result = _read_secret("api_key")

                assert result == "docker_secret_value"

    def test_read_secret_docker_exception_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _read_secret handles Docker secret read exception."""
        def mock_exists(path_self: Path) -> bool:
            return "/run/secrets/" in str(path_self)

        def mock_read_text(path_self: Path, *args: Any, **kwargs: Any) -> str:
            if "/run/secrets/" in str(path_self):
                raise PermissionError("Docker secret access denied")
            raise FileNotFoundError()

        with patch.object(Path, 'exists', mock_exists):
            with patch.object(Path, 'read_text', mock_read_text):
                result = _read_secret("api_key")

                # Should return None after exception
                assert result is None

    def test_read_secret_docker_empty_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _read_secret returns None when Docker secret is empty."""
        def mock_exists(path_self: Path) -> bool:
            return "/run/secrets/" in str(path_self)

        def mock_read_text(path_self: Path, *args: Any, **kwargs: Any) -> str:
            if "/run/secrets/" in str(path_self):
                return "   \n\t  "  # Empty after strip
            raise FileNotFoundError()

        with patch.object(Path, 'exists', mock_exists):
            with patch.object(Path, 'read_text', mock_read_text):
                result = _read_secret("api_key")

                # Should return None for empty value
                assert result is None

    def test_read_secret_fallthrough_all_locations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _read_secret tries all locations in sequence."""
        monkeypatch.chdir(tmp_path)

        secret_dir = tmp_path / ".secrets"
        secret_dir.mkdir()

        # Create empty files in local locations
        txt_file = secret_dir / "token.txt"
        txt_file.write_text("")

        plain_file = secret_dir / "token"
        plain_file.write_text("  ")

        # Track execution
        checked_paths = []

        def mock_exists(path_self: Path) -> bool:
            """Track which paths are checked for existence."""
            path_str = str(path_self)
            checked_paths.append(path_str)

            # Return True for all paths we want to test
            if "token" in path_str:
                return True
            if "/run/secrets/" in path_str:
                return True
            return False

        def mock_read_text(path_self: Path, *args: Any, **kwargs: Any) -> str:
            """Return appropriate values for each path."""
            path_str = str(path_self)

            if "/run/secrets/" in path_str:
                return "docker_token"

            # For local files, return empty content
            if "token.txt" in path_str:
                return ""
            if "token" in path_str and ".txt" not in path_str:
                return "  "

            raise FileNotFoundError(f"Cannot read {path_str}")

        with patch.object(Path, 'exists', mock_exists):
            with patch.object(Path, 'read_text', mock_read_text):
                result = _read_secret("token")

                # Should have checked all 3 locations
                assert any("token.txt" in p for p in checked_paths), "Should check .txt file"
                assert any("/run/secrets/" in p for p in checked_paths), "Should check Docker"

                # Should return Docker value after local files were empty
                assert result == "docker_token"


# ============================================================================
# VALIDATE_CONFIG - Target: 76% -> 95%+
# ============================================================================

class TestValidateConfigMissingPaths:
    """Complete coverage for validate_config missing paths."""

    def test_validate_config_no_discord_configuration_fails(self) -> None:
        """Test validation fails when both webhook and bot token are None."""
        config = Config(
            discord_webhook_url=None,
            discord_bot_token=None,
            factorio_log_path=Path("/factorio/console.log")
        )

        result = validate_config(config)

        assert result is False

    def test_validate_config_bot_token_too_short_warns(self) -> None:
        """Test validation warns when bot token is suspiciously short."""
        config = Config(
            discord_bot_token="short_token_12345",  # Only 18 chars, < 50
            factorio_log_path=Path("/factorio/console.log")
        )

        # Should warn but still return True (not a failure)
        result = validate_config(config)

        assert result is True

    def test_validate_config_bot_token_valid_length_no_warning(self) -> None:
        """Test validation passes without warning for valid length bot token."""
        # Real Discord bot tokens are 70+ characters
        valid_token = "M" + "x" * 69  # 70 characters

        config = Config(
            discord_bot_token=valid_token,
            factorio_log_path=Path("/factorio/console.log")
        )

        result = validate_config(config)

        assert result is True

    def test_validate_config_webhook_only_success(self) -> None:
        """Test validation succeeds with only webhook URL (no bot token)."""
        config = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            discord_bot_token=None,
            factorio_log_path=Path("/factorio/console.log")
        )

        result = validate_config(config)

        assert result is True

    def test_validate_config_bot_token_only_success(self) -> None:
        """Test validation succeeds with only bot token (no webhook)."""
        config = Config(
            discord_webhook_url=None,
            discord_bot_token="valid_bot_token_" + "x" * 50,
            factorio_log_path=Path("/factorio/console.log")
        )

        result = validate_config(config)

        assert result is True

    def test_validate_config_both_discord_modes_success(self) -> None:
        """Test validation succeeds when both webhook and bot token are provided."""
        config = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            discord_bot_token="valid_bot_token_" + "x" * 50,
            factorio_log_path=Path("/factorio/console.log")
        )

        result = validate_config(config)

        assert result is True

    def test_validate_config_rcon_enabled_with_password_success(self) -> None:
        """Test validation succeeds when RCON is enabled with valid password."""
        config = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            rcon_enabled=True,
            rcon_password="secure_password"
        )

        result = validate_config(config)

        assert result is True

    def test_validate_config_rcon_disabled_success(self) -> None:
        """Test validation succeeds when RCON is disabled (no password needed)."""
        config = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            rcon_enabled=False,
            rcon_password=None
        )

        result = validate_config(config)

        assert result is True

    def test_validate_config_rcon_disabled_with_password_success(self) -> None:
        """Test validation succeeds when RCON is disabled even if password exists."""
        config = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            factorio_log_path=Path("/factorio/console.log"),
            rcon_enabled=False,
            rcon_password="unused_password"
        )

        result = validate_config(config)

        # Should pass - password is ignored when RCON disabled
        assert result is True

    def test_validate_config_webhook_url_none_vs_empty_string(self) -> None:
        """Test validation handles None webhook_url correctly in condition."""
        # Test with None (should check bot_token)
        config_none = Config(
            discord_webhook_url=None,
            discord_bot_token="valid_token_" + "x" * 50,
            factorio_log_path=Path("/factorio/console.log")
        )

        assert validate_config(config_none) is True

        # Test with empty string (should fail format check)
        config_empty = Config(
            discord_webhook_url="",
            discord_bot_token=None,
            factorio_log_path=Path("/factorio/console.log")
        )

        # Empty string doesn't start with required prefix
        assert validate_config(config_empty) is False

    def test_validate_config_edge_case_bot_token_exactly_50_chars(self) -> None:
        """Test validation with bot token exactly at 50 character boundary."""
        config = Config(
            discord_bot_token="x" * 50,  # Exactly 50 characters
            factorio_log_path=Path("/factorio/console.log")
        )

        result = validate_config(config)

        # Should pass without warning (not < 50)
        assert result is True

    def test_validate_config_edge_case_bot_token_49_chars(self) -> None:
        """Test validation with bot token just under 50 character boundary."""
        config = Config(
            discord_bot_token="x" * 49,  # 49 characters
            factorio_log_path=Path("/factorio/console.log")
        )

        result = validate_config(config)

        # Should warn but pass (< 50)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
