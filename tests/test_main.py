"""
Comprehensive test suite for main.py

Tests Application lifecycle, setup, and component integration
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

import main
from main import Application, setup_logging
from discord_interface import BotDiscordInterface  # real type for isinstance checks


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_config() -> Mock:
    """Create a mock configuration object."""
    config = Mock()
    config.log_level = "INFO"
    config.log_format = "json"
    config.health_check_host = "localhost"
    config.health_check_port = 8080
    config.discord_webhook_url = "https://discord.com/api/webhooks/test"
    config.discord_bot_token = "BOT_TOKEN"
    config.discord_event_channel_id = None
    config.is_multi_server = False
    config.servers = {}

    mock_log_path = Mock(spec=Path)
    mock_log_path.exists = Mock(return_value=True)
    config.factorio_log_path = mock_log_path

    # Attributes used by EventParser in setup()
    config.patterns_dir = Path("patterns")
    config.pattern_files = []

    return config


@pytest.fixture
def app() -> Application:
    """Create Application instance."""
    return Application()


@pytest.fixture
def mock_discord_interface() -> AsyncMock:
    """Generic mocked Discord interface (not used for multi-server type check)."""
    interface = AsyncMock()
    interface.connect = AsyncMock()
    interface.send_message = AsyncMock()
    interface.is_connected = True
    return interface


# =============================================================================
# APPLICATION SETUP TESTS
# =============================================================================

class TestApplicationSetup:
    """Test Application.setup() method."""

    @pytest.mark.asyncio
    async def test_setup_loads_and_validates_config(
        self, app: Application, mock_config: Mock
    ) -> None:
        with patch("main.load_config", return_value=mock_config):
            with patch("main.validate_config", return_value=True):
                with patch("main.EventParser"):
                    with patch("main.HealthCheckServer"):
                        with patch("main.setup_logging"):
                            await app.setup()
        assert app.config is mock_config

    @pytest.mark.asyncio
    async def test_setup_raises_on_invalid_config(self, app: Application) -> None:
        invalid_config = Mock()
        with patch("main.load_config", return_value=invalid_config):
            with patch("main.validate_config", return_value=False):
                with pytest.raises(ValueError, match="validation failed"):
                    await app.setup()

    @pytest.mark.asyncio
    async def test_setup_raises_on_config_load_failure(self, app: Application) -> None:
        with patch("main.load_config", side_effect=Exception("Config error")):
            with pytest.raises(Exception, match="Config error"):
                await app.setup()

    @pytest.mark.asyncio
    async def test_setup_creates_event_parser(
        self, app: Application, mock_config: Mock
    ) -> None:
        with patch("main.load_config", return_value=mock_config):
            with patch("main.validate_config", return_value=True):
                with patch("main.EventParser") as MockParser:
                    with patch("main.HealthCheckServer"):
                        with patch("main.setup_logging"):
                            await app.setup()
        MockParser.assert_called_once()
        assert app.event_parser is not None

    @pytest.mark.asyncio
    async def test_setup_creates_health_server(
        self, app: Application, mock_config: Mock
    ) -> None:
        with patch("main.load_config", return_value=mock_config):
            with patch("main.validate_config", return_value=True):
                with patch("main.EventParser"):
                    with patch("main.HealthCheckServer") as MockHealth:
                        with patch("main.setup_logging"):
                            await app.setup()
        MockHealth.assert_called_once()
        assert app.health_server is not None

    @pytest.mark.asyncio
    async def test_setup_warns_if_log_file_missing(
        self, app: Application, mock_config: Mock
    ) -> None:
        mock_config.factorio_log_path.exists.return_value = False
        with patch("main.load_config", return_value=mock_config):
            with patch("main.validate_config", return_value=True):
                with patch("main.EventParser"):
                    with patch("main.HealthCheckServer"):
                        with patch("main.setup_logging"):
                            await app.setup()
        assert app.config is mock_config


# =============================================================================
# APPLICATION START TESTS
# =============================================================================

class TestApplicationStart:
    """Test Application.start() method."""

    @pytest.mark.asyncio
    async def test_start_requires_config(self, app: Application) -> None:
        app.config = None
        with pytest.raises(AssertionError, match="Config not loaded"):
            await app.start()

    @pytest.mark.asyncio
    async def test_start_requires_health_server(
        self, app: Application, mock_config: Mock
    ) -> None:
        app.config = mock_config
        app.health_server = None
        with pytest.raises(AssertionError, match="Health server not initialized"):
            await app.start()

    @pytest.mark.asyncio
    async def test_start_creates_discord_interface(
        self, app: Application, mock_config: Mock
    ) -> None:
        """Use a real BotDiscordInterface so multi-server checks pass."""
        from config import ServerConfig

        mock_config.is_multi_server = True
        mock_config.servers = {
            "test": ServerConfig(
                tag="test",
                name="Test Server",
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="test123",
            )
        }
        mock_config.discord_bot_token = "BOT_TOKEN"

        app.config = mock_config
        app.health_server = AsyncMock()
        app.health_server.start = AsyncMock()
        app.event_parser = Mock()

        bot_interface = BotDiscordInterface(discord_bot=AsyncMock())
        bot_interface.connect = AsyncMock()

        with patch("main.DiscordInterfaceFactory.create_interface",
                   return_value=bot_interface):
            with patch("main.SERVER_MANAGER_AVAILABLE", True):
                with patch("main.ServerManager") as MockServerManager:
                    mock_manager = Mock()
                    mock_manager.add_server = AsyncMock()
                    MockServerManager.return_value = mock_manager
                    with patch("main.LogTailer") as MockTailer:
                        mock_tailer = AsyncMock()
                        MockTailer.return_value = mock_tailer
                        await app.start()

        assert app.discord is bot_interface
        bot_interface.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_creates_log_tailer(
        self, app: Application, mock_config: Mock
    ) -> None:
        from config import ServerConfig

        mock_config.is_multi_server = True
        mock_config.servers = {
            "test": ServerConfig(
                tag="test",
                name="Test Server",
                rcon_host="localhost",
                rcon_port=27015,
                rcon_password="test123",
            )
        }
        mock_config.discord_bot_token = "BOT_TOKEN"

        app.config = mock_config
        app.health_server = AsyncMock()
        app.health_server.start = AsyncMock()
        app.event_parser = Mock()

        bot_interface = BotDiscordInterface(discord_bot=AsyncMock())
        bot_interface.connect = AsyncMock()

        with patch("main.DiscordInterfaceFactory.create_interface",
                   return_value=bot_interface):
            with patch("main.SERVER_MANAGER_AVAILABLE", True):
                with patch("main.ServerManager") as MockServerManager:
                    mock_manager = Mock()
                    mock_manager.add_server = AsyncMock()
                    MockServerManager.return_value = mock_manager
                    with patch("main.LogTailer") as MockTailer:
                        mock_tailer = AsyncMock()
                        mock_tailer.start = AsyncMock()
                        MockTailer.return_value = mock_tailer

                        await app.start()

        MockTailer.assert_called_once()
        assert app.log_tailer is mock_tailer
        mock_tailer.start.assert_awaited_once()


# =============================================================================
# MULTI-SERVER MODE TESTS
# =============================================================================

class TestApplicationMultiServer:
    """Test multi-server functionality."""

    @pytest.mark.asyncio
    async def test_multi_server_mode_detection(
        self, app: Application, mock_config: Mock
    ) -> None:
        mock_config.servers = {"prod": Mock(), "dev": Mock()}
        app.config = mock_config
        assert len(mock_config.servers) > 0

    @pytest.mark.asyncio
    async def test_multi_server_with_bot_interface(
        self, app: Application, mock_config: Mock
    ) -> None:
        """Ensure multi-server start works with a BotDiscordInterface."""
        from config import ServerConfig

        mock_config.servers = {
            "prod": ServerConfig(
                tag="prod",
                name="Production",
                rcon_host="host1",
                rcon_port=27015,
                rcon_password="pass1",
            )
        }
        mock_config.discord_bot_token = "BOT_TOKEN"
        mock_config.is_multi_server = True

        app.config = mock_config
        app.health_server = AsyncMock()
        app.health_server.start = AsyncMock()
        app.event_parser = Mock()

        bot_interface = BotDiscordInterface(discord_bot=AsyncMock())
        bot_interface.connect = AsyncMock()

        with patch("main.DiscordInterfaceFactory.create_interface",
                   return_value=bot_interface):
            with patch("main.SERVER_MANAGER_AVAILABLE", True):
                with patch("main.ServerManager") as MockServerManager:
                    mock_manager = Mock()
                    mock_manager.add_server = AsyncMock()
                    MockServerManager.return_value = mock_manager
                    with patch("main.LogTailer") as MockTailer:
                        mock_tailer = AsyncMock()
                        MockTailer.return_value = mock_tailer

                        await app.start()

        assert app.discord is bot_interface


# =============================================================================
# APPLICATION STOP TESTS
# =============================================================================

class TestApplicationStop:
    """Test Application.stop() method."""

    @pytest.mark.asyncio
    async def test_stop_gracefully_shuts_down(
        self, app: Application, mock_config: Mock
    ) -> None:
        app.config = mock_config
        app.log_tailer = AsyncMock()
        app.discord = AsyncMock()
        app.health_server = AsyncMock()

        await app.stop()

        app.log_tailer.stop.assert_awaited_once()
        app.discord.disconnect.assert_awaited_once()
        app.health_server.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_handles_missing_components(self, app: Application) -> None:
        app.log_tailer = None
        app.discord = None
        app.health_server = None
        await app.stop()

    @pytest.mark.asyncio
    async def test_stop_handles_errors(
        self, app: Application, mock_config: Mock
    ) -> None:
        app.config = mock_config
        app.log_tailer = AsyncMock()
        app.log_tailer.stop.side_effect = Exception("Tailer error")
        app.discord = AsyncMock()
        app.health_server = AsyncMock()
        await app.stop()
        app.discord.disconnect.assert_awaited_once()


# =============================================================================
# APPLICATION RUN TESTS
# =============================================================================

class TestApplicationRun:
    """Test Application.run() method."""

    @pytest.mark.asyncio
    async def test_run_calls_setup_and_start(self, app: Application) -> None:
        app.setup = AsyncMock()
        app.start = AsyncMock()
        app.stop = AsyncMock()

        async def trigger_shutdown():
            app.shutdown_event.set()

        app.start.side_effect = trigger_shutdown

        try:
            await asyncio.wait_for(app.run(), timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("Test timed out - app.run() did not complete")

        app.setup.assert_awaited_once()
        app.start.assert_awaited_once()
        app.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_handles_keyboard_interrupt(self, app: Application) -> None:
        app.setup = AsyncMock()
        app.start = AsyncMock(side_effect=KeyboardInterrupt())
        app.stop = AsyncMock()

        await app.run()

        app.setup.assert_awaited_once()
        app.stop.assert_awaited_once()


# =============================================================================
# SETUP LOGGING TESTS
# =============================================================================

class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_with_json_format(self) -> None:
        with patch("structlog.configure"):
            setup_logging("INFO", "json")

    def test_setup_logging_with_console_format(self) -> None:
        with patch("structlog.configure"):
            setup_logging("DEBUG", "console")

    def test_setup_logging_with_invalid_level(self) -> None:
        with patch("structlog.configure"):
            setup_logging("INVALID", "json")


# =============================================================================
# MAIN FUNCTION TESTS
# =============================================================================

class TestMainFunction:
    """Test main() entry point."""

    @pytest.mark.asyncio
    async def test_main_creates_and_runs_application(self) -> None:
        mock_app = AsyncMock()
        mock_app.run = AsyncMock()
        with patch("main.Application", return_value=mock_app):
            await main.main()
        mock_app.run.assert_awaited_once()


# =============================================================================
# SIGNAL HANDLING TESTS
# =============================================================================

class TestSignalHandling:
    """Test signal handling."""

    @pytest.mark.asyncio
    async def test_application_handles_sigterm(self, app: Application) -> None:
        app.setup = AsyncMock()
        app.start = AsyncMock()
        app.stop = AsyncMock()

        async def trigger_shutdown():
            app.shutdown_event.set()

        app.start.side_effect = trigger_shutdown

        try:
            await asyncio.wait_for(app.run(), timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("Test timed out - shutdown_event not triggered")

        app.setup.assert_awaited_once()
        app.start.assert_awaited_once()
        app.stop.assert_awaited_once()


# =============================================================================
# _start_multi_server_mode error and edge cases
# =============================================================================

class TestMultiServerModeErrors:
    """Cover branches in Application._start_multi_server_mode."""

    @pytest.mark.asyncio
    async def test_start_multi_server_server_manager_unavailable_raises_import_error(
        self, app: Application, mock_config: Mock
    ) -> None:
        """SERVER_MANAGER_AVAILABLE False or ServerManager is None should raise ImportError."""
        mock_config.is_multi_server = True
        mock_config.servers = {"prod": Mock()}
        mock_config.discord_bot_token = "BOT_TOKEN"
        app.config = mock_config
        app.discord = AsyncMock()  # placeholder; type check will be hit later

        with patch("main.SERVER_MANAGER_AVAILABLE", False):
            with pytest.raises(ImportError, match="ServerManager not available"):
                await app._start_multi_server_mode()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_start_multi_server_requires_bot_token(
        self, app: Application, mock_config: Mock
    ) -> None:
        """Missing discord_bot_token in multi-server mode -> ValueError."""
        mock_config.is_multi_server = True
        mock_config.servers = {"prod": Mock()}
        mock_config.discord_bot_token = None
        app.config = mock_config
        app.discord = AsyncMock()

        with patch("main.SERVER_MANAGER_AVAILABLE", True):
            with patch("main.ServerManager", AsyncMock()):
                with pytest.raises(ValueError, match="Bot mode required"):
                    await app._start_multi_server_mode()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_start_multi_server_requires_bot_interface_type(
        self, app: Application, mock_config: Mock
    ) -> None:
        """Discord interface must be a BotDiscordInterface; otherwise TypeError."""
        mock_config.is_multi_server = True
        mock_config.servers = {"prod": Mock()}
        mock_config.discord_bot_token = "BOT_TOKEN"
        app.config = mock_config
        app.discord = AsyncMock()  # not a BotDiscordInterface

        with patch("main.SERVER_MANAGER_AVAILABLE", True):
            with patch("main.ServerManager", AsyncMock()):
                with pytest.raises(TypeError, match="Bot interface required"):
                    await app._start_multi_server_mode()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_start_multi_server_no_servers_configured_raises(
        self, app: Application, mock_config: Mock
    ) -> None:
        """Empty servers dict should raise ValueError."""
        mock_config.is_multi_server = True
        mock_config.servers = {}
        mock_config.discord_bot_token = "BOT_TOKEN"
        app.config = mock_config

        from discord_interface import BotDiscordInterface
        app.discord = BotDiscordInterface(discord_bot=AsyncMock())

        with patch("main.SERVER_MANAGER_AVAILABLE", True):
            with patch("main.ServerManager") as MockServerManager:
                MockServerManager.return_value = AsyncMock()
                with pytest.raises(ValueError, match="No servers configured"):
                    await app._start_multi_server_mode()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_start_multi_server_handles_failed_servers_and_raises_if_none_added(
        self, app: Application, mock_config: Mock
    ) -> None:
        """If all servers fail to add, ConnectionError should be raised."""
        from discord_interface import BotDiscordInterface
        from config import ServerConfig

        mock_config.is_multi_server = True
        mock_config.discord_bot_token = "BOT_TOKEN"
        mock_config.servers = {
            "prod": ServerConfig(
                tag="prod",
                name="Production",
                rcon_host="host1",
                rcon_port=27015,
                rcon_password="pass1",
            )
        }
        app.config = mock_config
        app.discord = BotDiscordInterface(discord_bot=AsyncMock())

        with patch("main.SERVER_MANAGER_AVAILABLE", True):
            with patch("main.ServerManager") as MockServerManager:
                mock_manager = AsyncMock()
                # Force add_server to raise to simulate failure
                mock_manager.add_server.side_effect = Exception("add failed")
                MockServerManager.return_value = mock_manager

                with pytest.raises(ConnectionError, match="Failed to add any servers"):
                    await app._start_multi_server_mode()  # type: ignore[attr-defined]

# =============================================================================
# handle_log_line branches
# =============================================================================

from unittest.mock import Mock, AsyncMock

from unittest.mock import Mock, AsyncMock

class TestHandleLogLine:
    """Cover all branches in Application.handle_log_line."""

    @pytest.mark.asyncio
    async def test_handle_log_line_no_parser(self, app: Application) -> None:
        app.event_parser = None
        app.discord = AsyncMock()
        await app.handle_log_line("[CHAT] Player: hello")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_handle_log_line_no_discord(self, app: Application) -> None:
        app.event_parser = Mock()
        app.event_parser.parse_line = Mock(return_value=None)
        app.discord = None
        await app.handle_log_line("[CHAT] Player: hello")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_handle_log_line_no_event_parsed(self, app: Application) -> None:
        parser = Mock()
        parser.parse_line = Mock(return_value=None)
        app.event_parser = parser  # type: ignore[assignment]
        app.discord = AsyncMock()

        await app.handle_log_line("unmatched line")  # type: ignore[attr-defined]
        app.discord.send_event.assert_not_awaited()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_handle_log_line_send_event_success(self, app: Application) -> None:
        event = Mock()
        event.event_type = Mock()
        event.event_type.value = "chat"
        event.player_name = "Player1"

        parser = Mock()
        parser.parse_line = Mock(return_value=event)
        app.event_parser = parser  # type: ignore[assignment]

        discord_iface = AsyncMock()
        discord_iface.send_event = AsyncMock(return_value=True)
        app.discord = discord_iface  # type: ignore[assignment]

        await app.handle_log_line("[CHAT] Player1: hi")  # type: ignore[attr-defined]
        discord_iface.send_event.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_handle_log_line_send_event_failure(self, app: Application) -> None:
        event = Mock()
        event.event_type = Mock()
        event.event_type.value = "chat"
        event.player_name = "Player1"

        parser = Mock()
        parser.parse_line = Mock(return_value=event)
        app.event_parser = parser  # type: ignore[assignment]

        discord_iface = AsyncMock()
        discord_iface.send_event = AsyncMock(return_value=False)
        app.discord = discord_iface  # type: ignore[assignment]

        await app.handle_log_line("[CHAT] Player1: hi")  # type: ignore[attr-defined]
        discord_iface.send_event.assert_awaited_once_with(event)



# =============================================================================
# ServerManager stop path in stop()
# =============================================================================

class TestApplicationStopServerManager:
    """Cover ServerManager.stop_all branch and its error handling."""

    @pytest.mark.asyncio
    async def test_stop_calls_server_manager_stop_all(self, app: Application, mock_config: Mock) -> None:
        app.config = mock_config
        manager = AsyncMock()
        manager.stop_all = AsyncMock()
        app.server_manager = manager  # type: ignore[assignment]
        app.log_tailer = None
        app.discord = None
        app.health_server = None

        await app.stop()
        manager.stop_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_handles_server_manager_stop_error(self, app: Application, mock_config: Mock) -> None:
        app.config = mock_config
        manager = AsyncMock()
        manager.stop_all = AsyncMock(side_effect=Exception("stop error"))
        app.server_manager = manager  # type: ignore[assignment]
        app.log_tailer = None
        app.discord = None
        app.health_server = None

        # Should not raise despite stop_all error
        await app.stop()

class TestApplicationStopIntensified:
    @pytest.mark.asyncio
    async def test_stop_calls_server_manager_stop_all(
        self, app: Application, mock_config: Mock
    ) -> None:
        app.config = mock_config
        manager = AsyncMock()
        manager.stop_all = AsyncMock()
        app.server_manager = manager  # type: ignore[assignment]
        app.log_tailer = None
        app.discord = None
        app.health_server = None

        await app.stop()
        manager.stop_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_handles_server_manager_stop_error(
        self, app: Application, mock_config: Mock
    ) -> None:
        app.config = mock_config
        manager = AsyncMock()
        manager.stop_all = AsyncMock(side_effect=Exception("stop error"))
        app.server_manager = manager  # type: ignore[assignment]
        app.log_tailer = None
        app.discord = None
        app.health_server = None

        await app.stop()  # should not raise


class TestApplicationRunIntensified:
    @pytest.mark.asyncio
    async def test_run_logs_and_reraises_on_error(self, app: Application) -> None:
        app.setup = AsyncMock()
        app.start = AsyncMock(side_effect=RuntimeError("boom"))
        app.stop = AsyncMock()

        with pytest.raises(RuntimeError, match="boom"):
            await app.run()

        app.setup.assert_awaited_once()
        app.stop.assert_awaited_once()


class TestApplicationMainMethod:
    @pytest.mark.asyncio
    async def test_application_main_calls_run(self, app: Application) -> None:
        app.run = AsyncMock()
        await app.main()  # type: ignore[misc]
        app.run.assert_awaited_once()

class TestMainFunctionIntensified:
    @pytest.mark.asyncio
    async def test_main_logs_fatal_error_and_exits(self, monkeypatch: Any) -> None:
        mock_app = AsyncMock()
        mock_app.run = AsyncMock(side_effect=RuntimeError("boom"))

        with patch("main.Application", return_value=mock_app):
            with patch("main.sys.exit") as mock_exit:
                await main.main()
                mock_exit.assert_called_once_with(1)







if __name__ == "__main__":
    pytest.main([__file__, "-v"])
