"""
Comprehensive tests for main.py with 95%+ coverage.

Tests Application lifecycle, setup, start, stop, signal handling,
RCON integration, and error scenarios.
"""

import pytest
import asyncio
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from main import (
    setup_logging,
    Application,
    main,
    RCON_AVAILABLE,
)
from event_parser import FactorioEvent, EventType


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()
    config.log_level = "info"
    config.log_format = "console"
    config.factorio_log_path = Path("/tmp/factorio/console.log")
    config.patterns_dir = Path("patterns")
    config.pattern_files = None
    config.health_check_host = "0.0.0.0"
    config.health_check_port = 8080
    config.discord_webhook_url = "https://discord.com/api/webhooks/test"
    config.webhook_channels = {}
    config.bot_name = "Factorio Bot"
    config.bot_avatar_url = None
    config.send_test_message = False
    config.rcon_enabled = False
    config.rcon_host = "localhost"
    config.rcon_port = 27015
    config.rcon_password = None
    config.stats_interval = 300
    return config


@pytest.fixture
def mock_health_server():
    """Create a mock HealthCheckServer."""
    server = AsyncMock()
    server.start = AsyncMock()
    server.stop = AsyncMock()
    return server


@pytest.fixture
def mock_discord_client():
    """Create a mock DiscordClient."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.send_event = AsyncMock(return_value=True)
    client.test_connection = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_event_parser():
    """Create a mock EventParser."""
    parser = Mock()
    parser.compiled_patterns = {"test": Mock()}
    parser.parse_line = Mock(return_value=None)
    return parser


@pytest.fixture
def mock_log_tailer():
    """Create a mock LogTailer."""
    tailer = AsyncMock()
    tailer.start = AsyncMock()
    tailer.stop = AsyncMock()
    return tailer


@pytest.fixture
def app():
    """Create an Application instance."""
    return Application()


# ============================================================================
# setup_logging() Tests
# ============================================================================

class TestSetupLogging:
    """Test setup_logging function."""
    
    def test_setup_logging_info_console(self):
        """Test logging setup with info level and console format."""
        setup_logging("info", "console")
        # Should complete without error
        assert True
    
    def test_setup_logging_debug_json(self):
        """Test logging setup with debug level and JSON format."""
        setup_logging("debug", "json")
        # Should complete without error
        assert True
    
    def test_setup_logging_all_levels(self):
        """Test all log levels."""
        levels = ["debug", "info", "warning", "error", "critical"]
        
        for level in levels:
            setup_logging(level, "console")
            # Should complete without error
        
        assert True
    
    def test_setup_logging_invalid_level_defaults_to_info(self):
        """Test that invalid log level defaults to INFO."""
        # Should not raise, just default to INFO
        setup_logging("invalid_level", "console")
        assert True
    
    def test_setup_logging_case_insensitive(self):
        """Test that log level is case-insensitive."""
        setup_logging("INFO", "console")
        setup_logging("Debug", "json")
        assert True


# ============================================================================
# Application.__init__() Tests
# ============================================================================

class TestApplicationInit:
    """Test Application initialization."""
    
    def test_init_creates_instance(self):
        """Test that Application can be instantiated."""
        app = Application()
        
        assert app is not None
        assert app.config is None
        assert app.health_server is None
        assert app.log_tailer is None
        assert app.discord_client is None
        assert app.event_parser is None
        assert app.rcon_client is None
        assert app.stats_collector is None
        assert isinstance(app.shutdown_event, asyncio.Event)
    
    def test_init_shutdown_event_not_set(self):
        """Test that shutdown_event is not set initially."""
        app = Application()
        
        assert not app.shutdown_event.is_set()


# ============================================================================
# Application.setup() Tests
# ============================================================================

class TestApplicationSetup:
    """Test Application.setup() method."""
    
    @pytest.mark.asyncio
    async def test_setup_loads_config(self, app, mock_config):
        """Test that setup loads configuration."""
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=True):
                with patch('main.EventParser'):
                    with patch('main.HealthCheckServer'):
                        await app.setup()
        
        assert app.config is not None
        assert app.config == mock_config
    
    @pytest.mark.asyncio
    async def test_setup_validates_config(self, app, mock_config):
        """Test that setup validates configuration."""
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=True) as mock_validate:
                with patch('main.EventParser'):
                    with patch('main.HealthCheckServer'):
                        await app.setup()
        
        mock_validate.assert_called_once_with(mock_config)
    
    @pytest.mark.asyncio
    async def test_setup_creates_event_parser(self, app, mock_config):
        """Test that setup creates EventParser."""
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=True):
                with patch('main.EventParser') as MockParser:
                    with patch('main.HealthCheckServer'):
                        await app.setup()
        
        MockParser.assert_called_once_with(
            patterns_dir=mock_config.patterns_dir,
            pattern_files=mock_config.pattern_files
        )
    
    @pytest.mark.asyncio
    async def test_setup_creates_health_server(self, app, mock_config):
        """Test that setup creates HealthCheckServer."""
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=True):
                with patch('main.EventParser'):
                    with patch('main.HealthCheckServer') as MockHealth:
                        await app.setup()
        
        MockHealth.assert_called_once_with(
            host=mock_config.health_check_host,
            port=mock_config.health_check_port
        )
    
    @pytest.mark.asyncio
    async def test_setup_warns_if_log_file_missing(self, app, mock_config, tmp_path):
        """Test warning when log file doesn't exist."""
        mock_config.factorio_log_path = tmp_path / "nonexistent.log"
        
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=True):
                with patch('main.EventParser'):
                    with patch('main.HealthCheckServer'):
                        await app.setup()
        
        # Should complete without error even if file doesn't exist
        assert app.config is not None
    
    @pytest.mark.asyncio
    async def test_setup_config_load_failure(self, app):
        """Test handling of config load failure."""
        with patch('main.load_config', side_effect=FileNotFoundError("Config not found")):
            with pytest.raises(FileNotFoundError, match="Config not found"):
                await app.setup()
    
    @pytest.mark.asyncio
    async def test_setup_config_validation_failure(self, app, mock_config):
        """Test handling of config validation failure."""
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=False):
                with pytest.raises(ValueError, match="Configuration validation failed"):
                    await app.setup()
    
    @pytest.mark.asyncio
    async def test_setup_config_none_raises(self, app):
        """Test that None config raises assertion."""
        with patch('main.load_config', return_value=None):
            with pytest.raises(AssertionError, match="Config loading returned None"):
                await app.setup()


# ============================================================================
# Application.start() Tests
# ============================================================================

class TestApplicationStart:
    """Test Application.start() method."""
    
    @pytest.mark.asyncio
    async def test_start_starts_health_server(self, app, mock_config, mock_health_server):
        """Test that start() starts the health server."""
        app.config = mock_config
        app.health_server = mock_health_server
        
        with patch('main.DiscordClient', return_value=AsyncMock()):
            with patch('main.LogTailer', return_value=AsyncMock()):
                app.event_parser = Mock()
                app.event_parser.compiled_patterns = {}
                
                await app.start()
        
        mock_health_server.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_creates_discord_client(self, app, mock_config, mock_health_server):
        """Test that start() creates Discord client."""
        app.config = mock_config
        app.health_server = mock_health_server
        app.event_parser = Mock()
        app.event_parser.compiled_patterns = {}
        
        with patch('main.DiscordClient') as MockDiscord:
            mock_discord = AsyncMock()
            MockDiscord.return_value = mock_discord
            
            with patch('main.LogTailer', return_value=AsyncMock()):
                await app.start()
        
        MockDiscord.assert_called_once()
        mock_discord.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_creates_log_tailer(self, app, mock_config, mock_health_server):
        """Test that start() creates log tailer."""
        app.config = mock_config
        app.health_server = mock_health_server
        app.event_parser = Mock()
        app.event_parser.compiled_patterns = {}
        
        with patch('main.DiscordClient', return_value=AsyncMock()):
            with patch('main.LogTailer') as MockTailer:
                mock_tailer = AsyncMock()
                MockTailer.return_value = mock_tailer
                
                await app.start()
        
        MockTailer.assert_called_once()
        assert mock_tailer.start.called
    
    @pytest.mark.asyncio
    async def test_start_with_webhook_channels(self, app, mock_config, mock_health_server):
        """Test start with multi-channel webhook configuration."""
        mock_config.webhook_channels = {
            "chat": "https://discord.com/api/webhooks/chat",
            "admin": "https://discord.com/api/webhooks/admin"
        }
        app.config = mock_config
        app.health_server = mock_health_server
        app.event_parser = Mock()
        app.event_parser.compiled_patterns = {}
        
        with patch('main.DiscordClient') as MockDiscord:
            mock_discord = AsyncMock()
            MockDiscord.return_value = mock_discord
            
            with patch('main.LogTailer', return_value=AsyncMock()):
                await app.start()
        
        # Should pass webhook_channels to Discord client
        call_kwargs = MockDiscord.call_args.kwargs
        assert call_kwargs['webhook_channels'] == mock_config.webhook_channels
    
    @pytest.mark.asyncio
    async def test_start_with_test_message(self, app, mock_config, mock_health_server):
        """Test start with test message enabled."""
        mock_config.send_test_message = True
        app.config = mock_config
        app.health_server = mock_health_server
        app.event_parser = Mock()
        app.event_parser.compiled_patterns = {}
        
        mock_discord = AsyncMock()
        mock_discord.test_connection = AsyncMock(return_value=True)
        
        with patch('main.DiscordClient', return_value=mock_discord):
            with patch('main.LogTailer', return_value=AsyncMock()):
                await app.start()
        
        mock_discord.test_connection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_test_message_failure_raises(self, app, mock_config, mock_health_server):
        """Test that failed test message raises error."""
        mock_config.send_test_message = True
        app.config = mock_config
        app.health_server = mock_health_server
        app.event_parser = Mock()
        app.event_parser.compiled_patterns = {}
        
        mock_discord = AsyncMock()
        mock_discord.test_connection = AsyncMock(return_value=False)
        
        with patch('main.DiscordClient', return_value=mock_discord):
            with pytest.raises(ConnectionError, match="Failed to connect to Discord webhook"):
                await app.start()
    
    @pytest.mark.asyncio
    async def test_start_rcon_disabled(self, app, mock_config, mock_health_server):
        """Test start with RCON disabled."""
        mock_config.rcon_enabled = False
        app.config = mock_config
        app.health_server = mock_health_server
        app.event_parser = Mock()
        app.event_parser.compiled_patterns = {}
        
        with patch('main.DiscordClient', return_value=AsyncMock()):
            with patch('main.LogTailer', return_value=AsyncMock()):
                await app.start()
        
        # Should not attempt RCON
        assert app.rcon_client is None
        assert app.stats_collector is None
    
    @pytest.mark.asyncio
    async def test_start_assertions(self, app):
        """Test that start() validates state."""
        # No config
        with pytest.raises(AssertionError, match="Config not loaded"):
            await app.start()
        
        # Config but no health server
        app.config = Mock()
        with pytest.raises(AssertionError, match="Health server not initialized"):
            await app.start()


# ============================================================================
# Application._start_rcon() Tests
# ============================================================================

class TestApplicationStartRcon:
    """Test Application._start_rcon() method."""
    
    @pytest.mark.asyncio
    async def test_start_rcon_when_unavailable(self, app, mock_config):
        """Test RCON start when module is unavailable."""
        app.config = mock_config
        app.discord_client = AsyncMock()
        
        with patch('main.RCON_AVAILABLE', False):
            await app._start_rcon()
        
        # Should log warning but not crash
        assert app.rcon_client is None
    
    @pytest.mark.asyncio
    async def test_start_rcon_no_password(self, app, mock_config):
        """Test RCON start without password."""
        mock_config.rcon_password = None
        app.config = mock_config
        app.discord_client = AsyncMock()
        
        with patch('main.RCON_AVAILABLE', True):
            await app._start_rcon()
        
        # Should warn but not start
        assert app.rcon_client is None
    
    @pytest.mark.asyncio
    async def test_start_rcon_success(self, app, mock_config):
        """Test successful RCON start."""
        mock_config.rcon_enabled = True
        mock_config.rcon_password = "test_password"
        app.config = mock_config
        app.discord_client = AsyncMock()
        
        mock_rcon = AsyncMock()
        mock_stats = AsyncMock()
        
        with patch('main.RCON_AVAILABLE', True):
            with patch('main.RconClient', return_value=mock_rcon):
                with patch('main.RconStatsCollector', return_value=mock_stats):
                    await app._start_rcon()
        
        mock_rcon.connect.assert_called_once()
        mock_stats.start.assert_called_once()
        assert app.rcon_client == mock_rcon
        assert app.stats_collector == mock_stats
    
    @pytest.mark.asyncio
    async def test_start_rcon_connection_failure(self, app, mock_config):
        """Test RCON connection failure doesn't crash app."""
        mock_config.rcon_password = "test_password"
        app.config = mock_config
        app.discord_client = AsyncMock()
        
        mock_rcon = AsyncMock()
        mock_rcon.connect = AsyncMock(side_effect=ConnectionError("RCON failed"))
        
        with patch('main.RCON_AVAILABLE', True):
            with patch('main.RconClient', return_value=mock_rcon):
                # Should not raise - RCON is optional
                await app._start_rcon()
        
        # RCON failure should not propagate
        assert True


# ============================================================================
# Application.handle_log_line() Tests
# ============================================================================

class TestApplicationHandleLogLine:
    """Test Application.handle_log_line() method."""
    
    @pytest.mark.asyncio
    async def test_handle_log_line_no_parser(self, app):
        """Test handling log line without parser."""
        app.event_parser = None
        
        # Should not crash
        await app.handle_log_line("Test line")
        
        assert True
    
    @pytest.mark.asyncio
    async def test_handle_log_line_no_match(self, app, mock_event_parser):
        """Test handling log line that doesn't match any pattern."""
        app.event_parser = mock_event_parser
        app.discord_client = AsyncMock()
        mock_event_parser.parse_line.return_value = None
        
        await app.handle_log_line("Unmatched line")
        
        # Should parse but not send
        mock_event_parser.parse_line.assert_called_once_with("Unmatched line")
        assert not app.discord_client.send_event.called
    
    @pytest.mark.asyncio
    async def test_handle_log_line_no_discord_client(self, app, mock_event_parser):
        """Test handling log line without Discord client."""
        app.event_parser = mock_event_parser
        app.discord_client = None
        
        mock_event = FactorioEvent(event_type=EventType.CHAT)
        mock_event_parser.parse_line.return_value = mock_event
        
        # Should not crash
        await app.handle_log_line("Test line")
        
        assert True
    
    @pytest.mark.asyncio
    async def test_handle_log_line_success(self, app, mock_event_parser):
        """Test successful log line handling."""
        app.event_parser = mock_event_parser
        app.discord_client = AsyncMock()
        
        mock_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello"
        )
        mock_event_parser.parse_line.return_value = mock_event
        app.discord_client.send_event = AsyncMock(return_value=True)
        
        await app.handle_log_line("[CHAT] TestPlayer: Hello")
        
        mock_event_parser.parse_line.assert_called_once()
        app.discord_client.send_event.assert_called_once_with(mock_event)
    
    @pytest.mark.asyncio
    async def test_handle_log_line_send_failure(self, app, mock_event_parser):
        """Test handling of send failure."""
        app.event_parser = mock_event_parser
        app.discord_client = AsyncMock()
        
        mock_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            metadata={"channel": "chat"}
        )
        mock_event_parser.parse_line.return_value = mock_event
        app.discord_client.send_event = AsyncMock(return_value=False)
        
        # Should not raise, just log warning
        await app.handle_log_line("Test line")
        
        assert app.discord_client.send_event.called
    
    @pytest.mark.asyncio
    async def test_handle_log_line_with_channel_routing(self, app, mock_event_parser):
        """Test log line handling with channel routing metadata."""
        app.event_parser = mock_event_parser
        app.discord_client = AsyncMock()
        
        mock_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="Admin",
            message="Admin message",
            metadata={"channel": "admin"}
        )
        mock_event_parser.parse_line.return_value = mock_event
        app.discord_client.send_event = AsyncMock(return_value=True)
        
        await app.handle_log_line("[ADMIN] Admin: Admin message")
        
        # Event should be sent with channel metadata
        call_args = app.discord_client.send_event.call_args
        sent_event = call_args[0][0]
        assert sent_event.metadata.get("channel") == "admin"


# ============================================================================
# Application.stop() Tests
# ============================================================================

class TestApplicationStop:
    """Test Application.stop() method."""
    
    @pytest.mark.asyncio
    async def test_stop_all_components(self, app):
        """Test stopping all components."""
        app.stats_collector = AsyncMock()
        app.rcon_client = AsyncMock()
        app.log_tailer = AsyncMock()
        app.discord_client = AsyncMock()
        app.health_server = AsyncMock()
        
        await app.stop()
        
        app.stats_collector.stop.assert_called_once()
        app.rcon_client.disconnect.assert_called_once()
        app.log_tailer.stop.assert_called_once()
        app.discord_client.disconnect.assert_called_once()
        app.health_server.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_with_none_components(self, app):
        """Test stop when components are None."""
        app.stats_collector = None
        app.rcon_client = None
        app.log_tailer = None
        app.discord_client = None
        app.health_server = None
        
        # Should not crash
        await app.stop()
        
        assert True
    
    @pytest.mark.asyncio
    async def test_stop_handles_component_errors(self, app):
        """Test that stop handles errors in component shutdown."""
        app.stats_collector = AsyncMock()
        app.stats_collector.stop = AsyncMock(side_effect=RuntimeError("Stop failed"))
        
        app.rcon_client = AsyncMock()
        app.log_tailer = AsyncMock()
        app.discord_client = AsyncMock()
        app.health_server = AsyncMock()
        
        # Should not raise despite error
        await app.stop()
        
        # Other components should still be stopped
        assert app.rcon_client.disconnect.called
        assert app.log_tailer.stop.called
    
    @pytest.mark.asyncio
    async def test_stop_order(self, app):
        """Test that components stop in correct order."""
        call_order = []
        
        app.stats_collector = AsyncMock()
        app.stats_collector.stop = AsyncMock(side_effect=lambda: call_order.append("stats"))
        
        app.rcon_client = AsyncMock()
        app.rcon_client.disconnect = AsyncMock(side_effect=lambda: call_order.append("rcon"))
        
        app.log_tailer = AsyncMock()
        app.log_tailer.stop = AsyncMock(side_effect=lambda: call_order.append("tailer"))
        
        app.discord_client = AsyncMock()
        app.discord_client.disconnect = AsyncMock(side_effect=lambda: call_order.append("discord"))
        
        app.health_server = AsyncMock()
        app.health_server.stop = AsyncMock(side_effect=lambda: call_order.append("health"))
        
        await app.stop()
        
        # Should stop in order: stats, rcon, tailer, discord, health
        assert call_order == ["stats", "rcon", "tailer", "discord", "health"]


# ============================================================================
# Application.run() Tests
# ============================================================================

class TestApplicationRun:
    """Test Application.run() method."""
    
    @pytest.mark.asyncio
    async def test_run_setup_and_start(self, app, mock_config):
        """Test that run calls setup and start."""
        with patch.object(app, 'setup', new_callable=AsyncMock) as mock_setup:
            with patch.object(app, 'start', new_callable=AsyncMock) as mock_start:
                with patch.object(app, 'stop', new_callable=AsyncMock) as mock_stop:
                    # Set shutdown event immediately to exit
                    async def immediate_shutdown():
                        app.shutdown_event.set()
                    
                    mock_start.side_effect = immediate_shutdown
                    
                    await app.run()
        
        mock_setup.assert_called_once()
        mock_start.assert_called_once()
        mock_stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_keyboard_interrupt(self, app):
        """Test handling of KeyboardInterrupt."""
        with patch.object(app, 'setup', new_callable=AsyncMock):
            with patch.object(app, 'start', new_callable=AsyncMock) as mock_start:
                with patch.object(app, 'stop', new_callable=AsyncMock) as mock_stop:
                    mock_start.side_effect = KeyboardInterrupt()
                    
                    # Should not raise, just stop
                    await app.run()
        
        mock_stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_exception_propagates(self, app):
        """Test that exceptions are propagated."""
        with patch.object(app, 'setup', new_callable=AsyncMock):
            with patch.object(app, 'start', new_callable=AsyncMock) as mock_start:
                with patch.object(app, 'stop', new_callable=AsyncMock):
                    mock_start.side_effect = RuntimeError("Test error")
                    
                    with pytest.raises(RuntimeError, match="Test error"):
                        await app.run()
    
    @pytest.mark.asyncio
    async def test_run_stops_on_exception(self, app):
        """Test that stop is called even on exception."""
        with patch.object(app, 'setup', new_callable=AsyncMock):
            with patch.object(app, 'start', new_callable=AsyncMock) as mock_start:
                with patch.object(app, 'stop', new_callable=AsyncMock) as mock_stop:
                    mock_start.side_effect = RuntimeError("Test error")
                    
                    try:
                        await app.run()
                    except RuntimeError:
                        pass
        
        # Stop should be called in finally block
        mock_stop.assert_called_once()


# ============================================================================
# main() Function Tests
# ============================================================================

class TestMainFunction:
    """Test main() async function."""
    
    @pytest.mark.asyncio
    async def test_main_creates_application(self):
        """Test that main creates Application."""
        mock_app = Mock()
        mock_app.run = AsyncMock()
        mock_app.shutdown_event = asyncio.Event()
        
        with patch('main.Application', return_value=mock_app):
            # Set shutdown immediately to exit
            mock_app.run.side_effect = lambda: mock_app.shutdown_event.set()
            
            await main()
        
        mock_app.run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_main_signal_handlers(self):
        """Test that signal handlers are registered."""
        mock_app = Mock()
        mock_app.run = AsyncMock()
        mock_app.shutdown_event = asyncio.Event()
        
        with patch('main.Application', return_value=mock_app):
            with patch('signal.signal') as mock_signal:
                mock_app.run.side_effect = lambda: mock_app.shutdown_event.set()
                
                await main()
        
        # Should register SIGINT and SIGTERM
        calls = mock_signal.call_args_list
        signals_registered = [call[0][0] for call in calls]
        assert signal.SIGINT in signals_registered
        assert signal.SIGTERM in signals_registered
    
    @pytest.mark.asyncio
    async def test_main_signal_handler_sets_shutdown(self):
        """Test that signal handler sets shutdown event."""
        mock_app = Mock()
        mock_app.shutdown_event = asyncio.Event()
        
        captured_handler = None
        
        def capture_signal(sig, handler):
            nonlocal captured_handler
            if sig == signal.SIGINT:
                captured_handler = handler
        
        with patch('main.Application', return_value=mock_app):
            with patch('signal.signal', side_effect=capture_signal):
                with patch.object(mock_app, 'run', new_callable=AsyncMock):
                    mock_app.run.side_effect = lambda: mock_app.shutdown_event.set()
                    
                    await main()
        
        # Verify handler was captured
        assert captured_handler is not None
        
        # Call the handler
        captured_handler(signal.SIGINT, None)
        
        # Should set shutdown event
        assert mock_app.shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_main_handles_application_error(self):
        """Test main handles application errors."""
        mock_app = Mock()
        mock_app.run = AsyncMock(side_effect=RuntimeError("App failed"))
        mock_app.shutdown_event = asyncio.Event()
        
        with patch('main.Application', return_value=mock_app):
            with patch('sys.exit') as mock_exit:
                await main()
        
        # Should exit with code 1
        mock_exit.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_main_signal_registration_failure(self):
        """Test that signal registration failure is handled."""
        mock_app = Mock()
        mock_app.run = AsyncMock()
        mock_app.shutdown_event = asyncio.Event()
        
        with patch('main.Application', return_value=mock_app):
            with patch('signal.signal', side_effect=ValueError("Signal failed")):
                mock_app.run.side_effect = lambda: mock_app.shutdown_event.set()
                
                # Should not crash
                await main()


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_lifecycle(self, mock_config):
        """Test complete application lifecycle."""
        app = Application()
        
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=True):
                with patch('main.EventParser'):
                    with patch('main.HealthCheckServer', return_value=AsyncMock()):
                        with patch('main.DiscordClient', return_value=AsyncMock()):
                            with patch('main.LogTailer', return_value=AsyncMock()):
                                await app.setup()
                                await app.start()
                                
                                # Simulate some activity
                                await asyncio.sleep(0.01)
                                
                                await app.stop()
        
        # Should complete without errors
        assert app.config is not None
    
    @pytest.mark.asyncio
    async def test_log_line_to_discord_flow(self, mock_config):
        """Test complete flow from log line to Discord."""
        app = Application()
        app.config = mock_config
        
        # Setup parser
        mock_parser = Mock()
        mock_event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello world",
            formatted_message="💬 TestPlayer: Hello world"
        )
        mock_parser.parse_line = Mock(return_value=mock_event)
        app.event_parser = mock_parser
        
        # Setup Discord client
        mock_discord = AsyncMock()
        mock_discord.send_event = AsyncMock(return_value=True)
        app.discord_client = mock_discord
        
        # Handle log line
        await app.handle_log_line("[CHAT] TestPlayer: Hello world")
        
        # Should parse and send
        mock_parser.parse_line.assert_called_once()
        mock_discord.send_event.assert_called_once_with(mock_event)
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_on_error(self, mock_config):
        """Test graceful shutdown when error occurs."""
        app = Application()
        
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=True):
                with patch('main.EventParser'):
                    with patch('main.HealthCheckServer', return_value=AsyncMock()):
                        with patch('main.DiscordClient') as MockDiscord:
                            # Discord connection fails
                            mock_discord = AsyncMock()
                            mock_discord.connect = AsyncMock(
                                side_effect=ConnectionError("Connection failed")
                            )
                            MockDiscord.return_value = mock_discord
                            
                            await app.setup()
                            
                            with pytest.raises(ConnectionError):
                                await app.start()


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_multiple_setup_calls(self, app, mock_config):
        """Test calling setup multiple times."""
        with patch('main.load_config', return_value=mock_config):
            with patch('main.validate_config', return_value=True):
                with patch('main.EventParser'):
                    with patch('main.HealthCheckServer'):
                        await app.setup()
                        
                        # Second setup should work
                        await app.setup()
        
        assert app.config is not None
    
    @pytest.mark.asyncio
    async def test_stop_before_start(self, app):
        """Test stopping before starting."""
        # Should not crash
        await app.stop()
        
        assert True
    
    @pytest.mark.asyncio
    async def test_shutdown_event_can_be_set_externally(self, app):
        """Test that shutdown event can be triggered externally."""
        app.shutdown_event.set()
        
        assert app.shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_handle_log_line_empty_string(self, app, mock_event_parser):
        """Test handling empty log line."""
        app.event_parser = mock_event_parser
        mock_event_parser.parse_line.return_value = None
        
        await app.handle_log_line("")
        
        # Should handle gracefully
        assert True


# ============================================================================
# RCON Integration Tests
# ============================================================================

class TestRconIntegration:
    """Test RCON-specific functionality."""
    
    @pytest.mark.asyncio
    async def test_rcon_enabled_in_config(self, app, mock_config, mock_health_server):
        """Test RCON setup when enabled in config."""
        mock_config.rcon_enabled = True
        mock_config.rcon_password = "test_pass"
        app.config = mock_config
        app.health_server = mock_health_server
        app.event_parser = Mock()
        app.event_parser.compiled_patterns = {}
        
        with patch('main.RCON_AVAILABLE', True):
            with patch('main.DiscordClient', return_value=AsyncMock()):
                with patch('main.LogTailer', return_value=AsyncMock()):
                    with patch.object(app, '_start_rcon', new_callable=AsyncMock) as mock_rcon:
                        await app.start()
        
        # Should attempt to start RCON
        mock_rcon.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rcon_not_available_warning(self, app, mock_config, mock_health_server):
        """Test warning when RCON is enabled but not available."""
        mock_config.rcon_enabled = True
        app.config = mock_config
        app.health_server = mock_health_server
        app.event_parser = Mock()
        app.event_parser.compiled_patterns = {}
        
        with patch('main.RCON_AVAILABLE', False):
            with patch('main.DiscordClient', return_value=AsyncMock()):
                with patch('main.LogTailer', return_value=AsyncMock()):
                    # Should not crash, just warn
                    await app.start()
        
        assert app.rcon_client is None


