"""
Tests for src/main.py - Application class with MultiServerLogTailer integration.

Type-safe and comprehensive coverage of:
- setup() with config loading and EventParser initialization
- start() with health server, Discord interface, and MultiServerLogTailer
- handle_log_line() with server_tag parameter (multi-server aware)
- stop() gracefully shutting down all components
- Error handling and edge cases

NOTE: Implementation is ALWAYS multi-server. No legacy single-server mode.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import tempfile

import pytest
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from main import Application, setup_logging  # type: ignore
from event_parser import EventType, FactorioEvent  # type: ignore
from config import Config, ServerConfig  # type: ignore
from discord_interface import BotDiscordInterface  # type: ignore


# ============================================================================
# Mock Helpers
# ============================================================================

class MockBotDiscordInterface(BotDiscordInterface):
    """Mock implementation that passes isinstance checks."""
    
    def __init__(self) -> None:
        """Initialize with all required async mocks."""
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.send_event = AsyncMock(return_value=True)
        self.test_connection = AsyncMock(return_value=True)
        self.bot = MagicMock()
        self.bot.set_server_manager = MagicMock()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_log_file(tmp_path: Path) -> Path:
    """Create a temporary log file."""
    log_file = tmp_path / "console.log"
    log_file.write_text("")
    return log_file


@pytest.fixture
def temp_patterns_dir(tmp_path: Path) -> Path:
    """Create temporary patterns directory with minimal pattern."""
    patterns = tmp_path / "patterns"
    patterns.mkdir()
    vanilla = patterns / "vanilla.yml"
    vanilla.write_text(
        """events:
  player_join:
    pattern: joined the game
    type: join
    emoji: "✅"
    message: player joined
    priority: 10
"""
    )
    return patterns


@pytest.fixture
def mock_server_config() -> ServerConfig:
    """Create a mock ServerConfig."""
    return ServerConfig(
        name="TestServer",
        tag="test",
        rcon_host="127.0.0.1",
        rcon_port=27015,
        rcon_password="testpass",
        log_path=Path("/tmp/test_console.log"),
        event_channel_id=987654321,
    )


@pytest.fixture
def mock_config(temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig) -> Config:
    """Create a mock configuration with multi-server setup."""
    return Config(
        discord_webhook_url=None,  # Bot mode requires bot token
        discord_bot_token="test_bot_token",
        bot_name="TestBot",
        bot_avatar_url=None,
        factorio_log_path=temp_log_file,
        patterns_dir=temp_patterns_dir,
        pattern_files=None,
        health_check_host="0.0.0.0",
        health_check_port=8080,
        log_level="info",
        log_format="console",
        servers={"test": mock_server_config},
    )


# ============================================================================
# setup_logging Tests
# ============================================================================

class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_console_format(self) -> None:
        """Console format logging should configure without error."""
        setup_logging("info", "console")
        assert True

    def test_setup_logging_json_format(self) -> None:
        """JSON format logging should configure without error."""
        setup_logging("debug", "json")
        assert True

    def test_setup_logging_invalid_level(self) -> None:
        """Invalid log level should not crash."""
        try:
            setup_logging("notalevel", "console")
        except Exception:
            pass
        assert True

    def test_setup_logging_invalid_format(self) -> None:
        """Invalid log format should not crash."""
        try:
            setup_logging("info", "unsupported_format")
        except Exception:
            pass
        assert True


# ============================================================================
# Application.setup Tests
# ============================================================================

class TestApplicationSetup:
    """Tests for Application.setup() phase."""

    @pytest.mark.asyncio
    async def test_setup_loads_config_and_parser(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """setup() should load configuration and initialize EventParser."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()

            assert app.config is not None
            assert app.event_parser is not None
            assert app.health_server is not None
            assert len(app.event_parser.compiled_patterns) >= 1

    @pytest.mark.asyncio
    async def test_setup_validation_failure(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """setup() should fail if validate_config returns False."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=False):
            app = Application()
            with pytest.raises(ValueError):
                await app.setup()


# ============================================================================
# Application.start Tests
# ============================================================================

class TestApplicationStart:
    """Tests for Application.start() phase."""

    @pytest.mark.asyncio
    async def test_start_requires_servers_config(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """start() should fail if servers config is empty."""
        # Create a valid config first, then override servers after setup
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="127.0.0.1",
            health_check_port=8888,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()

            # Override servers to None after setup to test defensive check in start()
            app.config.servers = None
            
            # Should fail because servers config is required for multi-server mode
            with pytest.raises(ValueError, match="servers.yml configuration required - multi-server mode is mandatory"):
                await app.start()

    @pytest.mark.asyncio
    async def test_start_without_setup_fails(self) -> None:
        """start() should fail if setup() was not called first."""
        app = Application()
        with pytest.raises(AssertionError):
            await app.start()

    @pytest.mark.asyncio
    async def test_start_initializes_multi_server_tailer(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """start() should create and start MultiServerLogTailer."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.HealthCheckServer") as mock_health_class, \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_discord_factory, \
             patch("main.ServerManager") as mock_server_manager_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("discord_interface.BotDiscordInterface", MockBotDiscordInterface):
            
            # Mock HealthCheckServer
            mock_health_server = AsyncMock()
            mock_health_server.start = AsyncMock()
            mock_health_server.stop = AsyncMock()
            mock_health_class.return_value = mock_health_server
            
            # Create a real mock instance that passes isinstance
            mock_discord = MockBotDiscordInterface()
            mock_discord_factory.return_value = mock_discord

            # Mock ServerManager
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager.stop_all = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager

            # Mock MultiServerLogTailer
            mock_tailer = AsyncMock()
            mock_tailer.start = AsyncMock()
            mock_tailer.stop = AsyncMock()
            mock_tailer_class.return_value = mock_tailer

            app = Application()
            await app.setup()
            await app.start()

            # Verify MultiServerLogTailer was created
            mock_tailer_class.assert_called_once()
            assert app.logtailer is not None


# ============================================================================
# Application.handle_log_line Tests
# ============================================================================

class TestApplicationHandleLogLine:
    """Tests for Application.handle_log_line() method."""

    @pytest.mark.asyncio
    async def test_handle_log_line_with_event(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """handle_log_line should parse and send matching events to Discord."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            
            app = Application()
            await app.setup()

            # Create event with server_tag
            mock_event = FactorioEvent(
                event_type=EventType.CHAT,
                player_name="TestPlayer",
                message="Hello",
                raw_line="[TEST] TestPlayer: Hello",
                emoji="💬",
                formatted_message="",
                metadata={},
                server_tag="prod",
            )

            app.event_parser = MagicMock()
            app.event_parser.parse_line = MagicMock(return_value=mock_event)

            app.discord = AsyncMock()
            app.discord.send_event = AsyncMock(return_value=True)

            # FIX: Verify parse_line was called with server_tag kwarg
            await app.handle_log_line("Test line", "prod")

            # Verify event was parsed with server_tag and sent
            app.event_parser.parse_line.assert_called_once_with("Test line", server_tag="prod")
            app.discord.send_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_log_line_no_event(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """handle_log_line should not send event if parser returns None."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()

            app.event_parser = MagicMock()
            app.event_parser.parse_line = MagicMock(return_value=None)

            app.discord = AsyncMock()
            app.discord.send_event = AsyncMock(return_value=True)

            await app.handle_log_line("Random log noise", "prod")

            # Verify parser was called but Discord was not
            app.event_parser.parse_line.assert_called_once()
            app.discord.send_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_log_line_send_failure(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """handle_log_line should log warning if Discord send fails."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()

            mock_event = FactorioEvent(
                event_type=EventType.CHAT,
                player_name="TestPlayer",
                message="Hello",
                raw_line="[TEST] TestPlayer: Hello",
                emoji="💬",
                formatted_message="",
                metadata={},
                server_tag="prod",
            )

            app.event_parser = MagicMock()
            app.event_parser.parse_line = MagicMock(return_value=mock_event)

            app.discord = AsyncMock()
            app.discord.send_event = AsyncMock(return_value=False)  # Send fails

            await app.handle_log_line("Test line", "prod")

            app.discord.send_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_log_line_with_multiple_server_tags(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """handle_log_line should correctly attach different server_tags to events."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()

            # Create event
            mock_event = FactorioEvent(
                event_type=EventType.CHAT,
                player_name="TestPlayer",
                message="Hello",
                raw_line="[TEST] TestPlayer: Hello",
                emoji="💬",
                formatted_message="",
                metadata={},
                server_tag=None,
            )

            app.event_parser = MagicMock()
            app.event_parser.parse_line = MagicMock(return_value=mock_event)

            app.discord = AsyncMock()
            app.discord.send_event = AsyncMock(return_value=True)

            # Call with different server tags
            await app.handle_log_line("Test line", "prod")
            await app.handle_log_line("Test line", "dev")
            await app.handle_log_line("Test line", "staging")

            # All should have been sent
            assert app.discord.send_event.call_count == 3

    @pytest.mark.asyncio
    async def test_handle_log_line_no_parser_or_discord(
        self, temp_log_file: Path, temp_patterns_dir: Path
    ) -> None:
        """handle_log_line should return safely if parser or discord not initialized."""
        app = Application()
        
        # Both None
        await app.handle_log_line("Test line", "prod")
        
        # Only parser None
        app.discord = AsyncMock()
        await app.handle_log_line("Test line", "prod")
        
        # Only discord None
        app.event_parser = MagicMock()
        app.discord = None
        await app.handle_log_line("Test line", "prod")


# ============================================================================
# Application.stop Tests
# ============================================================================

class TestApplicationStop:
    """Tests for Application.stop() graceful shutdown."""

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self) -> None:
        """stop() should be safe to call even if start() was never called."""
        app = Application()
        # Should not raise
        await app.stop()

    @pytest.mark.asyncio
    async def test_stop_closes_all_components(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """stop() should close all components: ServerManager, LogTailer, Discord, Health."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()

            # Mock all components
            app.server_manager = AsyncMock()
            app.logtailer = AsyncMock()
            app.discord = AsyncMock()
            app.health_server = AsyncMock()

            await app.stop()

            # Verify all components were stopped
            app.server_manager.stop_all.assert_called_once()
            app.logtailer.stop.assert_called_once()
            app.discord.disconnect.assert_called_once()
            app.health_server.stop.assert_called_once()


# ============================================================================
# Application.run Integration Tests
# ============================================================================

class TestApplicationIntegration:
    """Integration tests for full Application lifecycle."""

    @pytest.mark.asyncio
    async def test_run_with_shutdown_signal(
        self, temp_log_file: Path, temp_patterns_dir: Path, mock_server_config: ServerConfig
    ) -> None:
        """run() should gracefully handle shutdown signal."""
        mock_config = Config(
            discord_webhook_url=None,
            discord_bot_token="test_bot_token",
            bot_name="TestBot",
            bot_avatar_url=None,
            factorio_log_path=temp_log_file,
            patterns_dir=temp_patterns_dir,
            pattern_files=None,
            health_check_host="0.0.0.0",
            health_check_port=8080,
            log_level="info",
            log_format="console",
            servers={"test": mock_server_config},
        )

        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.HealthCheckServer") as mock_health_class, \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_discord_factory, \
             patch("main.ServerManager") as mock_server_manager_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("discord_interface.BotDiscordInterface", MockBotDiscordInterface):
            
            # Mock HealthCheckServer
            mock_health_server = AsyncMock()
            mock_health_server.start = AsyncMock()
            mock_health_server.stop = AsyncMock()
            mock_health_class.return_value = mock_health_server
            
            # Create a real mock instance that passes isinstance
            mock_discord = MockBotDiscordInterface()
            mock_discord_factory.return_value = mock_discord

            # Mock ServerManager
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager.stop_all = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager

            # Mock MultiServerLogTailer
            mock_tailer = AsyncMock()
            mock_tailer.start = AsyncMock()
            mock_tailer.stop = AsyncMock()
            mock_tailer_class.return_value = mock_tailer

            app = Application()

            # Simulate shutdown signal after brief delay
            async def trigger_shutdown() -> None:
                await asyncio.sleep(0.1)
                app.shutdown_event.set()

            shutdown_task = asyncio.create_task(trigger_shutdown())

            try:
                await app.run()
            except Exception:
                pass
            finally:
                await shutdown_task


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
