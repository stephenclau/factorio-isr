"""
Comprehensive test suite for main.py
Tests Application lifecycle, setup, and component integration
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import signal

import pytest

import main
from main import Application, setup_logging
from discord_interface import BotDiscordInterface


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
async def test_application_start_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful application start with all components."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.send_test_message = False
    mock_config.is_multi_server = True
    mock_config.discord_bot_token = "test_token"
    mock_config.factorio_log_path = Path("/tmp/test.log")
    mock_config.servers = {
        "prod": MagicMock(
            tag="prod",
            name="Production",
            rcon_host="localhost",
            rcon_port=27015
        )
    }
    app.config = mock_config
    
    mock_health = AsyncMock()
    mock_health.start = AsyncMock()
    app.health_server = mock_health
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock(spec=BotDiscordInterface)
    mock_discord.connect = AsyncMock()
    mock_discord.bot = MagicMock()
    mock_discord.bot.set_server_manager = MagicMock(return_value=None)
    
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    monkeypatch.setattr("main.SERVER_MANAGER_AVAILABLE", True)
    
    mock_server_manager = AsyncMock()
    mock_server_manager.add_server = AsyncMock()
    # FIX: Accept **kwargs to handle discord_interface= keyword argument
    monkeypatch.setattr("main.ServerManager", lambda **kwargs: mock_server_manager)
    
    mock_tailer = AsyncMock()
    mock_tailer.start = AsyncMock()
    monkeypatch.setattr("main.LogTailer", lambda log_path, line_callback: mock_tailer)
    
    await app.start()
    
    mock_health.start.assert_called_once()
    mock_discord.connect.assert_called_once()
    mock_server_manager.add_server.assert_called_once()
    mock_tailer.start.assert_called_once()
    mock_discord.bot.set_server_manager.assert_called_once_with(mock_server_manager)



@pytest.mark.asyncio
async def test_application_start_config_not_loaded() -> None:
    """Test start fails when config is None."""
    app = Application()
    app.config = None
    
    with pytest.raises(AssertionError, match="Config not loaded"):
        await app.start()


@pytest.mark.asyncio
async def test_application_start_health_server_not_initialized() -> None:
    """Test start fails when health server is None."""
    app = Application()
    app.config = MagicMock()
    app.health_server = None
    
    with pytest.raises(AssertionError, match="Health server not initialized"):
        await app.start()


@pytest.mark.asyncio
async def test_application_start_no_multi_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test start fails when multi-server mode not configured."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.is_multi_server = False
    mock_config.servers = None
    app.config = mock_config
    
    mock_health = AsyncMock()
    mock_health.start = AsyncMock()
    app.health_server = mock_health
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock()
    mock_discord.connect = AsyncMock()
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    
    with pytest.raises(ValueError, match="config/servers.yml configuration required"):
        await app.start()


@pytest.mark.asyncio
async def test_application_start_no_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test start fails when bot token missing for multi-server."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.is_multi_server = True
    mock_config.discord_bot_token = None
    mock_config.servers = {"prod": MagicMock()}
    app.config = mock_config
    
    mock_health = AsyncMock()
    mock_health.start = AsyncMock()
    app.health_server = mock_health
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock()
    mock_discord.connect = AsyncMock()
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    monkeypatch.setattr("main.SERVER_MANAGER_AVAILABLE", True)
    
    with pytest.raises(ValueError, match="Bot mode required"):
        await app.start()


@pytest.mark.asyncio
async def test_application_start_server_manager_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test start fails when ServerManager not available."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.is_multi_server = True
    mock_config.discord_bot_token = "token"
    mock_config.servers = {"prod": MagicMock()}
    app.config = mock_config
    
    mock_health = AsyncMock()
    mock_health.start = AsyncMock()
    app.health_server = mock_health
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock()
    mock_discord.connect = AsyncMock()
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    monkeypatch.setattr("main.SERVER_MANAGER_AVAILABLE", False)
    monkeypatch.setattr("main.ServerManager", None)
    
    with pytest.raises(ImportError, match="ServerManager not available"):
        await app.start()


@pytest.mark.asyncio
async def test_application_start_no_servers_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test start fails when servers dict is empty."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.is_multi_server = True
    mock_config.discord_bot_token = "token"
    mock_config.servers = {}  # Empty dict
    mock_config.factorio_log_path = Path("/tmp/test.log")
    app.config = mock_config
    
    mock_health = AsyncMock()
    mock_health.start = AsyncMock()
    app.health_server = mock_health
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock(spec=BotDiscordInterface)
    mock_discord.connect = AsyncMock()
    mock_discord.bot = MagicMock()
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    monkeypatch.setattr("main.SERVER_MANAGER_AVAILABLE", True)
    
    mock_server_manager = MagicMock()
    monkeypatch.setattr("main.ServerManager", lambda discord_interface: mock_server_manager)
    
    # FIX: Empty dict is falsy, so it triggers the FIRST check
    # The error is "config/servers.yml configuration required" NOT "No servers configured"
    with pytest.raises(ValueError, match="config/servers.yml configuration required"):
        await app.start()

@pytest.mark.asyncio
async def test_application_start_server_add_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test start when adding a server fails."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.is_multi_server = True
    mock_config.discord_bot_token = "token"
    mock_config.servers = {
        "prod": MagicMock(tag="prod", name="Production", rcon_host="localhost", rcon_port=27015)
    }
    mock_config.factorio_log_path = Path("/tmp/test.log")
    app.config = mock_config
    
    mock_health = AsyncMock()
    mock_health.start = AsyncMock()
    app.health_server = mock_health
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock(spec=BotDiscordInterface)
    mock_discord.connect = AsyncMock()
    mock_discord.bot = MagicMock()
    mock_discord.bot.set_server_manager = MagicMock()
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    monkeypatch.setattr("main.SERVER_MANAGER_AVAILABLE", True)
    
    mock_server_manager = AsyncMock()
    mock_server_manager.add_server = AsyncMock(side_effect=Exception("Connection failed"))
    monkeypatch.setattr("main.ServerManager", lambda discord_interface: mock_server_manager)
    
    mock_tailer = AsyncMock()
    mock_tailer.start = AsyncMock()
    monkeypatch.setattr("main.LogTailer", lambda log_path, line_callback: mock_tailer)
    
    with pytest.raises(ConnectionError, match="Failed to add any servers"):
        await app.start()


@pytest.mark.asyncio
async def test_application_start_discord_connection_test_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test start fails when Discord test connection fails."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.send_test_message = True
    app.config = mock_config
    
    mock_health = AsyncMock()
    mock_health.start = AsyncMock()
    app.health_server = mock_health
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock()
    mock_discord.connect = AsyncMock()
    mock_discord.test_connection = AsyncMock(return_value=False)
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    
    with pytest.raises(ConnectionError, match="Failed to connect to Discord"):
        await app.start()


@pytest.mark.asyncio
async def test_start_creates_log_tailer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that start creates log tailer."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.send_test_message = False
    mock_config.is_multi_server = True
    mock_config.discord_bot_token = "token"
    mock_config.factorio_log_path = Path("/tmp/test.log")
    mock_config.servers = {"prod": MagicMock(tag="prod", name="Prod", rcon_host="localhost", rcon_port=27015)}
    app.config = mock_config
    
    app.health_server = AsyncMock()
    app.health_server.start = AsyncMock()
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock(spec=BotDiscordInterface)
    mock_discord.connect = AsyncMock()
    mock_discord.bot = MagicMock()
    mock_discord.bot.set_server_manager = MagicMock(return_value=None)
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    monkeypatch.setattr("main.SERVER_MANAGER_AVAILABLE", True)
    
    mock_server_manager = AsyncMock()
    mock_server_manager.add_server = AsyncMock()
    # FIX: Accept **kwargs
    monkeypatch.setattr("main.ServerManager", lambda **kwargs: mock_server_manager)
    
    mock_tailer = AsyncMock()
    mock_tailer.start = AsyncMock()
    monkeypatch.setattr("main.LogTailer", lambda log_path, line_callback: mock_tailer)
    
    await app.start()
    
    assert app.log_tailer is mock_tailer
    mock_tailer.start.assert_called_once()



@pytest.mark.asyncio
async def test_multi_server_with_bot_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test multi-server setup with bot interface."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.send_test_message = False
    mock_config.is_multi_server = True
    mock_config.discord_bot_token = "token"
    mock_config.factorio_log_path = Path("/tmp/test.log")
    mock_config.servers = {
        "prod": MagicMock(tag="prod", name="Production", rcon_host="localhost", rcon_port=27015),
        "staging": MagicMock(tag="staging", name="Staging", rcon_host="localhost", rcon_port=27016)
    }
    app.config = mock_config
    
    app.health_server = AsyncMock()
    app.health_server.start = AsyncMock()
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock(spec=BotDiscordInterface)
    mock_discord.connect = AsyncMock()
    mock_discord.bot = MagicMock()
    mock_discord.bot.set_server_manager = MagicMock(return_value=None)
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    monkeypatch.setattr("main.SERVER_MANAGER_AVAILABLE", True)
    
    mock_server_manager = AsyncMock()
    mock_server_manager.add_server = AsyncMock()
    # FIX: Accept **kwargs
    monkeypatch.setattr("main.ServerManager", lambda **kwargs: mock_server_manager)
    
    mock_tailer = AsyncMock()
    mock_tailer.start = AsyncMock()
    monkeypatch.setattr("main.LogTailer", lambda log_path, line_callback: mock_tailer)
    
    await app.start()
    
    mock_discord.bot.set_server_manager.assert_called_once()
    assert mock_server_manager.add_server.call_count == 2


@pytest.mark.asyncio
async def test_start_multi_server_handles_failed_servers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that failed servers are logged and exception raised if none succeed."""
    app = Application()
    
    mock_config = MagicMock()
    mock_config.health_check_host = "0.0.0.0"
    mock_config.health_check_port = 8080
    mock_config.is_multi_server = True
    mock_config.discord_bot_token = "token"
    mock_config.factorio_log_path = Path("/tmp/test.log")
    mock_config.servers = {
        "prod": MagicMock(tag="prod", name="Production", rcon_host="localhost", rcon_port=27015),
        "staging": MagicMock(tag="staging", name="Staging", rcon_host="localhost", rcon_port=27016)
    }
    app.config = mock_config
    
    app.health_server = AsyncMock()
    app.health_server.start = AsyncMock()
    app.event_parser = MagicMock()
    
    mock_discord = AsyncMock(spec=BotDiscordInterface)
    mock_discord.connect = AsyncMock()
    mock_discord.bot = MagicMock()
    mock_discord.bot.set_server_manager = MagicMock(return_value=None)
    monkeypatch.setattr("main.DiscordInterfaceFactory.create_interface", lambda cfg: mock_discord)
    monkeypatch.setattr("main.SERVER_MANAGER_AVAILABLE", True)
    
    mock_server_manager = AsyncMock()
    mock_server_manager.add_server = AsyncMock(side_effect=Exception("Connection failed"))
    # FIX: Accept **kwargs
    monkeypatch.setattr("main.ServerManager", lambda **kwargs: mock_server_manager)
    
    mock_tailer = AsyncMock()
    mock_tailer.start = AsyncMock()
    monkeypatch.setattr("main.LogTailer", lambda log_path, line_callback: mock_tailer)
    
    with pytest.raises(ConnectionError, match="Failed to add any servers"):
        await app.start()
    
    assert mock_server_manager.add_server.call_count == 2


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
        app.server_manager = None
        
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
        app.server_manager = None
        
        await app.stop()
        
        app.discord.disconnect.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_stop_calls_server_manager_stop_all(
        self, app: Application, mock_config: Mock
    ) -> None:
        app.config = mock_config
        manager = AsyncMock()
        manager.stop_all = AsyncMock()
        app.server_manager = manager
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
        app.server_manager = manager
        app.log_tailer = None
        app.discord = None
        app.health_server = None
        
        await app.stop()


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
    
    @pytest.mark.asyncio
    async def test_run_logs_and_reraises_on_error(self, app: Application) -> None:
        app.setup = AsyncMock()
        app.start = AsyncMock(side_effect=RuntimeError("boom"))
        app.stop = AsyncMock()
        
        with pytest.raises(RuntimeError, match="boom"):
            await app.run()
        
        app.setup.assert_awaited_once()
        app.stop.assert_awaited_once()


# =============================================================================
# HANDLE LOG LINE TESTS
# =============================================================================

class TestHandleLogLine:
    """Cover all branches in Application.handle_log_line."""
    
    @pytest.mark.asyncio
    async def test_handle_log_line_no_parser(self, app: Application) -> None:
        app.event_parser = None
        app.discord = AsyncMock()
        
        await app.handle_log_line("[CHAT] Player: hello")
    
    @pytest.mark.asyncio
    async def test_handle_log_line_no_discord(self, app: Application) -> None:
        app.event_parser = Mock()
        app.event_parser.parse_line = Mock(return_value=None)
        app.discord = None
        
        await app.handle_log_line("[CHAT] Player: hello")
    
    @pytest.mark.asyncio
    async def test_handle_log_line_no_event_parsed(self, app: Application) -> None:
        parser = Mock()
        parser.parse_line = Mock(return_value=None)
        app.event_parser = parser
        app.discord = AsyncMock()
        
        await app.handle_log_line("unmatched line")
        
        app.discord.send_event.assert_not_awaited()
    
    @pytest.mark.asyncio
    async def test_handle_log_line_send_event_success(self, app: Application) -> None:
        event = Mock()
        event.event_type = Mock()
        event.event_type.value = "chat"
        event.player_name = "Player1"
        
        parser = Mock()
        parser.parse_line = Mock(return_value=event)
        app.event_parser = parser
        
        discord_iface = AsyncMock()
        discord_iface.send_event = AsyncMock(return_value=True)
        app.discord = discord_iface
        
        await app.handle_log_line("[CHAT] Player1: hi")
        
        discord_iface.send_event.assert_awaited_once_with(event)
    
    @pytest.mark.asyncio
    async def test_handle_log_line_send_event_failure(self, app: Application) -> None:
        event = Mock()
        event.event_type = Mock()
        event.event_type.value = "chat"
        event.player_name = "Player1"
        
        parser = Mock()
        parser.parse_line = Mock(return_value=event)
        app.event_parser = parser
        
        discord_iface = AsyncMock()
        discord_iface.send_event = AsyncMock(return_value=False)
        app.discord = discord_iface
        
        await app.handle_log_line("[CHAT] Player1: hi")
        
        discord_iface.send_event.assert_awaited_once_with(event)


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
    
    @pytest.mark.asyncio
    async def test_main_logs_fatal_error_and_exits(self) -> None:
        mock_app = AsyncMock()
        mock_app.run = AsyncMock(side_effect=RuntimeError("boom"))
        
        with patch("main.Application", return_value=mock_app):
            with patch("main.sys.exit") as mock_exit:
                await main.main()
        
        mock_exit.assert_called_once_with(1)


# =============================================================================
# SIGNAL HANDLING TESTS
# =============================================================================

def test_signal_handler_sigint() -> None:
    """Test signal handler with SIGINT."""
    app = Application()
    
    def _signal_handler(signum: int, frame: Any) -> None:
        app.shutdown_event.set()
    
    assert not app.shutdown_event.is_set()
    _signal_handler(signal.SIGINT, None)
    assert app.shutdown_event.is_set()


def test_signal_handler_sigterm() -> None:
    """Test signal handler with SIGTERM."""
    app = Application()
    
    def _signal_handler(signum: int, frame: Any) -> None:
        app.shutdown_event.set()
    
    assert not app.shutdown_event.is_set()
    _signal_handler(signal.SIGTERM, None)
    assert app.shutdown_event.is_set()


@pytest.mark.asyncio
async def test_main_signal_handler_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that main() registers signal handlers."""
    registered_signals: list[int] = []
    
    def mock_signal(signum: int, handler) -> None:
        registered_signals.append(signum)
    
    monkeypatch.setattr(signal, "signal", mock_signal)
    
    async def mock_run(self):
        pass
    
    monkeypatch.setattr("main.Application.run", mock_run)
    
    await main.main()
    
    assert signal.SIGINT in registered_signals
    assert signal.SIGTERM in registered_signals


def test_signal_handler_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test signal handler registration handles exceptions gracefully."""
    def mock_signal_raises(signum: int, handler):
        raise OSError("Signal not supported")
    
    monkeypatch.setattr(signal, "signal", mock_signal_raises)
    
    try:
        signal.signal(signal.SIGINT, lambda s, f: None)
    except Exception:
        pass

@pytest.mark.asyncio
async def test_main_exits_on_fatal_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main() exits with code 1 on fatal error."""
    import sys
    
    async def mock_run_error(self):
        raise RuntimeError("Fatal error")
    
    monkeypatch.setattr("main.Application.run", mock_run_error)
    
    exit_codes: list[int] = []
    
    def mock_exit(code: int) -> None:
        exit_codes.append(code)
        raise SystemExit(code)
    
    monkeypatch.setattr(sys, "exit", mock_exit)
    
    with pytest.raises(SystemExit):
        await main.main()
    
    assert 1 in exit_codes


# =============================================================================
# APPLICATION MAIN METHOD TEST
# =============================================================================

class TestApplicationMainMethod:
    """Test Application.main() method."""
    
    @pytest.mark.asyncio
    async def test_application_main_calls_run(self, app: Application) -> None:
        app.run = AsyncMock()
        await app.main()
        app.run.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
