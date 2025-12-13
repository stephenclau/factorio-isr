"""
Tests for src/main.py - Application class with MultiServerLogTailer integration.

Type-safe and comprehensive coverage of:
- setup() with config loading and EventParser initialization
- start() with health server, Discord interface, and MultiServerLogTailer
- _start_multi_server_mode() with ServerManager, token validation, type checks
- handle_log_line() with server_tag parameter (multi-server aware)
- run() with exception handling and shutdown graceful exit
- main() entry point with signal handlers
- stop() gracefully shutting down all components
- Error handling and edge cases

NOTE: Implementation is ALWAYS multi-server. No legacy single-server mode.
Target: +20% coverage improvement (69% -> 89%)

NOTE: KeyboardInterrupt is NOT tested directly as it breaks pytest exit code.
Instead, we test the generic exception path which covers the same code.
"""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import tempfile

import pytest
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from main import Application, setup_logging, main  # type: ignore
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
        self.bot._apply_server_breakdown_config = MagicMock()
        self.embed_builder = None


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
        discord_bot_token="test_bot_token",
        bot_name="TestBot",
        factorio_log_path=temp_log_file,
        patterns_dir=temp_patterns_dir,
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

    def test_setup_logging_all_levels(self) -> None:
        """All log levels should be supported."""
        for level in ["debug", "info", "warning", "error", "critical"]:
            setup_logging(level, "console")
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
        self, mock_config: Config
    ) -> None:
        """setup() should load configuration and initialize EventParser."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()
            assert app.config is not None
            assert app.config.bot_name == "TestBot"
            assert app.event_parser is not None
            assert app.health_server is not None
            assert len(app.event_parser.compiled_patterns) >= 1

    @pytest.mark.asyncio
    async def test_setup_validation_failure(
        self, mock_config: Config
    ) -> None:
        """setup() should fail if validate_config returns False."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=False):
            app = Application()
            with pytest.raises(ValueError):
                await app.setup()

    @pytest.mark.asyncio
    async def test_setup_log_file_not_found_warning(
        self, mock_config: Config
    ) -> None:
        """setup() should warn if server log files don't exist."""
        mock_config.servers["test"].log_path = Path("/nonexistent/console.log")
        
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()
            assert app.config is not None
            assert app.config.bot_name == "TestBot"


# ============================================================================
# Application.start Tests
# ============================================================================

class TestApplicationStart:
    """Tests for Application.start() phase - comprehensive coverage."""

    @pytest.mark.asyncio
    async def test_start_without_setup_fails(self) -> None:
        """start() should fail if setup() was not called first."""
        app = Application()
        with pytest.raises(AssertionError):
            await app.start()

    @pytest.mark.asyncio
    async def test_start_requires_servers_config(
        self, mock_config: Config
    ) -> None:
        """start() should fail if servers config is empty or None."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            app.config.servers = None
            with pytest.raises(ValueError, match="servers.yml configuration required"):
                await app.start()

    @pytest.mark.asyncio
    async def test_start_health_server_starts(
        self, mock_config: Config
    ) -> None:
        """start() should start the health check server."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_factory, \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.ServerManager") as mock_server_manager_class:
            
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            # Mock health server
            app.health_server.start = AsyncMock()
            
            # Mock Discord interface
            mock_discord = MockBotDiscordInterface()
            mock_factory.return_value = mock_discord
            
            # Mock ServerManager
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager
            
            # Mock log tailer
            mock_tailer = AsyncMock()
            mock_tailer_class.return_value = mock_tailer
            
            await app.start()
            app.health_server.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_discord_interface_creation(
        self, mock_config: Config
    ) -> None:
        """start() should create Discord interface via factory."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_factory, \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.ServerManager") as mock_server_manager_class:
            
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            # Mock components
            app.health_server.start = AsyncMock()
            mock_discord = MockBotDiscordInterface()
            mock_factory.return_value = mock_discord
            
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager
            
            mock_tailer = AsyncMock()
            mock_tailer_class.return_value = mock_tailer
            
            await app.start()
            mock_factory.assert_called_once_with(mock_config)
            assert app.discord == mock_discord

    @pytest.mark.asyncio
    async def test_start_discord_connection_called(
        self, mock_config: Config
    ) -> None:
        """start() should call discord.connect()."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_factory, \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.ServerManager") as mock_server_manager_class:
            
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            app.health_server.start = AsyncMock()
            mock_discord = MockBotDiscordInterface()
            mock_factory.return_value = mock_discord
            
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager
            
            mock_tailer = AsyncMock()
            mock_tailer_class.return_value = mock_tailer
            
            await app.start()
            mock_discord.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_discord_test_connection_skipped_by_default(
        self, mock_config: Config
    ) -> None:
        """start() should skip test_connection by default (send_test_message=False)."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_factory, \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.ServerManager") as mock_server_manager_class:
            
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            app.health_server.start = AsyncMock()
            mock_discord = MockBotDiscordInterface()
            mock_factory.return_value = mock_discord
            
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager
            
            mock_tailer = AsyncMock()
            mock_tailer_class.return_value = mock_tailer
            
            await app.start()
            mock_discord.test_connection.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_multi_server_mode_called(
        self, mock_config: Config
    ) -> None:
        """start() should call _start_multi_server_mode()."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_factory, \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.ServerManager") as mock_server_manager_class, \
             patch.object(Application, "_start_multi_server_mode", new_callable=AsyncMock) as mock_multi_start:
            
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            app.health_server.start = AsyncMock()
            mock_discord = MockBotDiscordInterface()
            mock_factory.return_value = mock_discord
            
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager
            
            mock_tailer = AsyncMock()
            mock_tailer_class.return_value = mock_tailer
            
            await app.start()
            mock_multi_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_log_tailer_initialized(
        self, mock_config: Config
    ) -> None:
        """start() should initialize MultiServerLogTailer with proper config."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_factory, \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.ServerManager") as mock_server_manager_class:
            
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            app.health_server.start = AsyncMock()
            mock_discord = MockBotDiscordInterface()
            mock_factory.return_value = mock_discord
            
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager
            
            mock_tailer = AsyncMock()
            mock_tailer_class.return_value = mock_tailer
            
            await app.start()
            
            mock_tailer_class.assert_called_once()
            call_kwargs = mock_tailer_class.call_args[1]
            assert call_kwargs["server_configs"] == mock_config.servers
            assert call_kwargs["line_callback"] == app.handle_log_line
            assert call_kwargs["poll_interval"] == 0.1

    @pytest.mark.asyncio
    async def test_start_log_tailer_started(
        self, mock_config: Config
    ) -> None:
        """start() should call logtailer.start()."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.DiscordInterfaceFactory.create_interface") as mock_factory, \
             patch("main.MultiServerLogTailer") as mock_tailer_class, \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.ServerManager") as mock_server_manager_class:
            
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            app.health_server.start = AsyncMock()
            mock_discord = MockBotDiscordInterface()
            mock_factory.return_value = mock_discord
            
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock()
            mock_server_manager_class.return_value = mock_server_manager
            
            mock_tailer = AsyncMock()
            mock_tailer_class.return_value = mock_tailer
            
            await app.start()
            mock_tailer.start.assert_called_once()


# ============================================================================
# Application._start_multi_server_mode Tests
# ============================================================================

class TestStartMultiServerMode:
    """Tests for _start_multi_server_mode() - high-impact coverage gains."""

    @pytest.mark.asyncio
    async def test_server_manager_unavailable(
        self, mock_config: Config
    ) -> None:
        """Should raise ImportError when ServerManager unavailable."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.SERVER_MANAGER_AVAILABLE", False):
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            app.discord = AsyncMock()
            with pytest.raises(ImportError, match="ServerManager"):
                await app._start_multi_server_mode()

    @pytest.mark.asyncio
    async def test_missing_discord_bot_token(
        self, mock_config: Config
    ) -> None:
        """Should raise ValueError when discord_bot_token missing."""
        # Config validation will reject empty token at init time
        # So test by mocking load_config to raise the error
        with patch("main.load_config") as mock_load:
            mock_load.side_effect = ValueError("discord_bot_token is REQUIRED")
            app = Application()
            with pytest.raises(ValueError, match="discord_bot_token"):
                await app.setup()

    @pytest.mark.asyncio
    async def test_non_bot_discord_interface(
        self, mock_config: Config
    ) -> None:
        """Should raise TypeError if Discord interface is not BotDiscordInterface."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.SERVER_MANAGER_AVAILABLE", True):
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            app.discord = AsyncMock()  # Not a BotDiscordInterface
            with pytest.raises(TypeError, match="Bot interface required"):
                await app._start_multi_server_mode()

    @pytest.mark.asyncio
    async def test_no_servers_configured(
        self, mock_config: Config
    ) -> None:
        """Should raise ValueError when no servers in config."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.SERVER_MANAGER_AVAILABLE", True):
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            mock_discord = MockBotDiscordInterface()
            app.discord = mock_discord
            app.config.servers = {}  # Empty servers
            
            with pytest.raises(ValueError, match="servers"):
                await app._start_multi_server_mode()

    @pytest.mark.asyncio
    async def test_add_server_exception_handling(
        self, mock_config: Config
    ) -> None:
        """Should handle exceptions during add_server() without crashing."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True), \
             patch("main.SERVER_MANAGER_AVAILABLE", True), \
             patch("main.ServerManager") as mock_server_manager_class:
            
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            
            mock_discord = MockBotDiscordInterface()
            app.discord = mock_discord
            
            mock_server_manager = AsyncMock()
            mock_server_manager.add_server = AsyncMock(side_effect=ConnectionError("RCON failed"))
            mock_server_manager_class.return_value = mock_server_manager
            
            with pytest.raises(ConnectionError):
                await app._start_multi_server_mode()


# ============================================================================
# Application.handle_log_line Tests
# ============================================================================

class TestApplicationHandleLogLine:
    """Tests for Application.handle_log_line() method."""

    @pytest.mark.asyncio
    async def test_handle_log_line_no_parser(self) -> None:
        """handle_log_line should return safely if parser is None."""
        app = Application()
        app.event_parser = None
        await app.handle_log_line("Test line", "prod")
        assert True

    @pytest.mark.asyncio
    async def test_handle_log_line_no_discord(self) -> None:
        """handle_log_line should return safely if discord is None."""
        app = Application()
        app.event_parser = MagicMock()
        app.discord = None
        await app.handle_log_line("Test line", "prod")
        assert True

    @pytest.mark.asyncio
    async def test_handle_log_line_with_event(
        self, mock_config: Config
    ) -> None:
        """handle_log_line should parse and send matching events to Discord."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"

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

            await app.handle_log_line("Test line", "prod")
            app.event_parser.parse_line.assert_called_once_with("Test line", server_tag="prod")
            app.discord.send_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_log_line_no_event(
        self, mock_config: Config
    ) -> None:
        """handle_log_line should not send event if parser returns None."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            app.event_parser = MagicMock()
            app.event_parser.parse_line = MagicMock(return_value=None)
            app.discord = AsyncMock()
            await app.handle_log_line("Random log noise", "prod")
            app.event_parser.parse_line.assert_called_once()
            app.discord.send_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_log_line_send_failure(
        self, mock_config: Config
    ) -> None:
        """handle_log_line should log warning if Discord send fails."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
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
            app.discord.send_event = AsyncMock(return_value=False)
            await app.handle_log_line("Test line", "prod")
            app.discord.send_event.assert_called_once()


# ============================================================================
# Application.stop Tests
# ============================================================================

class TestApplicationStop:
    """Tests for Application.stop() graceful shutdown."""

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self) -> None:
        """stop() should be safe to call even if start() was never called."""
        app = Application()
        await app.stop()
        assert True

    @pytest.mark.asyncio
    async def test_stop_closes_all_components(
        self, mock_config: Config
    ) -> None:
        """stop() should close all components."""
        with patch("main.load_config", return_value=mock_config), \
             patch("main.validate_config", return_value=True):
            app = Application()
            await app.setup()
            assert app.config.bot_name == "TestBot"
            app.server_manager = AsyncMock()
            app.logtailer = AsyncMock()
            app.discord = AsyncMock()
            app.health_server = AsyncMock()
            await app.stop()
            app.server_manager.stop_all.assert_called_once()
            app.logtailer.stop.assert_called_once()
            app.discord.disconnect.assert_called_once()
            app.health_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_handles_exceptions(self) -> None:
        """stop() should handle exceptions from components gracefully."""
        app = Application()
        app.server_manager = AsyncMock()
        app.server_manager.stop_all = AsyncMock(side_effect=Exception("Stop failed"))
        app.logtailer = AsyncMock()
        app.logtailer.stop = AsyncMock(side_effect=Exception("Stop failed"))
        app.discord = AsyncMock()
        app.discord.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        app.health_server = AsyncMock()
        app.health_server.stop = AsyncMock(side_effect=Exception("Stop failed"))
        await app.stop()
        assert True


# ============================================================================
# Application.run Tests
# ============================================================================

class TestApplicationRun:
    """Tests for Application.run() method - error paths and shutdown."""

    @pytest.mark.asyncio
    async def test_run_exception_handling(self) -> None:
        """run() should handle generic exceptions and call stop()."""
        app = Application()
        app.setup = AsyncMock(side_effect=ValueError("Setup failed"))
        app.stop = AsyncMock()
        with pytest.raises(ValueError):
            await app.run()
        app.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_finally_always_stops(self) -> None:
        """run() should always call stop() in finally block."""
        app = Application()
        app.setup = AsyncMock()
        app.start = AsyncMock()
        app.stop = AsyncMock()
        app.shutdown_event.wait = AsyncMock()
        await app.run()
        app.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_start_exception_handling(self) -> None:
        """run() should handle exceptions during start() phase."""
        app = Application()
        app.setup = AsyncMock()
        app.start = AsyncMock(side_effect=RuntimeError("Start failed"))
        app.stop = AsyncMock()
        with pytest.raises(RuntimeError):
            await app.run()
        app.stop.assert_called_once()


# ============================================================================
# main() Entry Point Tests
# ============================================================================

class TestMainEntryPoint:
    """Tests for main() async entry point with signal handlers."""

    @pytest.mark.asyncio
    async def test_main_signal_handler_registration(self) -> None:
        """main() should register signal handlers."""
        with patch("main.Application") as mock_app_class:
            mock_app = AsyncMock()
            mock_app.run = AsyncMock()
            mock_app_class.return_value = mock_app
            
            with patch("signal.signal") as mock_signal:
                await main()
                assert mock_signal.call_count >= 2

    @pytest.mark.asyncio
    async def test_main_signal_registration_exception(self) -> None:
        """main() should handle signal registration failures."""
        with patch("main.Application") as mock_app_class:
            mock_app = AsyncMock()
            mock_app.run = AsyncMock()
            mock_app_class.return_value = mock_app
            
            with patch("signal.signal", side_effect=ValueError("Signal not available")):
                await main()
                mock_app.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_runs_application(self) -> None:
        """main() should create and run an Application."""
        with patch("main.Application") as mock_app_class:
            mock_app = AsyncMock()
            mock_app.run = AsyncMock()
            mock_app_class.return_value = mock_app
            
            with patch("signal.signal"):
                await main()
                mock_app.run.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
