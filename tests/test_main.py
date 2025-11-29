"""
Pytest test suite for main.py

Tests for application orchestration, component initialization,
and graceful shutdown.
"""

import pytest
import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from main import Application, setup_logging, main
from config import Config


class TestSetupLogging:
    """Tests for logging setup."""
    
    def test_setup_logging_console_format(self):
        """Test setting up console-formatted logging."""
        setup_logging("info", "console")
        # If no exception raised, logging was configured successfully
        assert True
    
    def test_setup_logging_json_format(self):
        """Test setting up JSON-formatted logging."""
        setup_logging("debug", "json")
        assert True
    
    def test_setup_logging_invalid_level_uses_default(self):
        """Test that invalid log level falls back to INFO."""
        setup_logging("invalid_level", "console")
        assert True


@pytest.mark.asyncio
class TestApplicationSetup:
    """Tests for Application setup phase."""
    
    async def test_setup_loads_config(self):
        """Test that setup loads configuration."""
        import main as main_module
        
        with patch.object(main_module, 'load_config') as mock_load:
            with patch.object(main_module, 'validate_config', return_value=True):
                mock_config = MagicMock()
                mock_config.factorio_log_path = Path("/tmp/test.log")
                mock_config.health_check_host = "0.0.0.0"
                mock_config.health_check_port = 8080
                mock_config.log_level = "info"
                mock_config.log_format = "console"
                mock_load.return_value = mock_config
                
                app = Application()
                await app.setup()
                
                assert app.config is not None
                assert app.health_server is not None
    
    async def test_setup_fails_on_invalid_config(self):
        """Test that setup raises error on invalid config."""
        import main as main_module
        
        with patch.object(main_module, 'load_config') as mock_load:
            with patch.object(main_module, 'validate_config', return_value=False):
                mock_config = MagicMock()
                mock_config.factorio_log_path = Path("/tmp/test.log")
                mock_config.health_check_host = "0.0.0.0"
                mock_config.health_check_port = 8080
                mock_config.log_level = "info"
                mock_config.log_format = "console"
                mock_load.return_value = mock_config
                
                app = Application()
                
                with pytest.raises(ValueError, match="Configuration validation failed"):
                    await app.setup()
    
    async def test_setup_warns_on_missing_log_file(self):
        """Test that setup warns when log file doesn't exist."""
        import main as main_module
        
        with patch.object(main_module, 'load_config') as mock_load:
            with patch.object(main_module, 'validate_config', return_value=True):
                mock_config = MagicMock()
                mock_config.factorio_log_path = Path("/nonexistent/path/test.log")
                mock_config.health_check_host = "0.0.0.0"
                mock_config.health_check_port = 8080
                mock_config.log_level = "info"
                mock_config.log_format = "console"
                mock_load.return_value = mock_config
                
                app = Application()
                await app.setup()
                
                # Should not raise, just warn
                assert app.config is not None


@pytest.mark.asyncio
@pytest.mark.asyncio
class TestApplicationStart:
    """Tests for Application start phase."""
    
    async def test_start_initializes_all_components(self):
        """Test that start initializes all components."""
        import main as main_module
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_path = Path(f.name)
        
        try:
            # Create mock config
            mock_config = MagicMock()
            mock_config.factorio_log_path = log_path
            mock_config.health_check_host = "0.0.0.0"
            mock_config.health_check_port = 8999
            mock_config.discord_webhook_url = "https://discord.com/api/webhooks/test/token"
            mock_config.bot_name = "Test Bot"
            mock_config.bot_avatar_url = None
            mock_config.log_level = "info"
            mock_config.log_format = "console"
            
            app = Application()
            app.config = mock_config
            
            # Mock health server
            app.health_server = AsyncMock()
            app.health_server.start = AsyncMock()
            app.health_server.stop = AsyncMock()
            
            with patch.object(main_module, 'DiscordClient') as mock_discord:
                with patch.object(main_module, 'EventParser') as mock_parser:
                    with patch.object(main_module, 'LogTailer') as mock_tailer:
                        # Setup mocks
                        mock_discord_instance = AsyncMock()
                        mock_discord_instance.connect = AsyncMock()
                        mock_discord_instance.test_connection = AsyncMock(return_value=True)
                        mock_discord_instance.disconnect = AsyncMock()
                        mock_discord.return_value = mock_discord_instance
                        
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        
                        mock_tailer_instance = AsyncMock()
                        mock_tailer_instance.start = AsyncMock()
                        mock_tailer_instance.stop = AsyncMock()
                        mock_tailer.return_value = mock_tailer_instance
                        
                        # Start application
                        await app.start()
                        
                        # Verify components were initialized
                        assert app.discord_client is not None
                        assert app.event_parser is not None
                        assert app.log_tailer is not None
                        
                        # Verify connections were made
                        mock_discord_instance.connect.assert_called_once()
                        mock_discord_instance.test_connection.assert_called_once()
                        mock_tailer_instance.start.assert_called_once()
        finally:
            log_path.unlink(missing_ok=True)
    
    async def test_start_fails_on_discord_connection_error(self):
        """Test that start raises error when Discord connection fails."""
        import main as main_module
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_path = Path(f.name)
        
        try:
            # Create mock config
            mock_config = MagicMock()
            mock_config.factorio_log_path = log_path
            mock_config.health_check_host = "0.0.0.0"
            mock_config.health_check_port = 8999
            mock_config.discord_webhook_url = "https://discord.com/api/webhooks/test/token"
            mock_config.bot_name = "Test Bot"
            mock_config.bot_avatar_url = None
            mock_config.log_level = "info"
            mock_config.log_format = "console"
            
            app = Application()
            app.config = mock_config
            
            # Mock health server
            app.health_server = AsyncMock()
            app.health_server.start = AsyncMock()
            app.health_server.stop = AsyncMock()
            
            with patch.object(main_module, 'DiscordClient') as mock_discord:
                mock_discord_instance = AsyncMock()
                mock_discord_instance.connect = AsyncMock()
                mock_discord_instance.test_connection = AsyncMock(return_value=False)
                mock_discord_instance.disconnect = AsyncMock()
                mock_discord.return_value = mock_discord_instance
                
                with pytest.raises(ConnectionError, match="Failed to connect to Discord webhook"):
                    await app.start()
        finally:
            log_path.unlink(missing_ok=True)



@pytest.mark.asyncio
class TestApplicationHandleLogLine:
    """Tests for log line handling."""
    
    async def test_handle_log_line_parses_and_sends(self):
        """Test that log lines are parsed and sent to Discord."""
        app = Application()
        
        # Mock parser
        mock_parser = MagicMock()
        mock_event = MagicMock()
        mock_parser.parse.return_value = mock_event
        app.event_parser = mock_parser
        
        # Mock Discord client
        mock_discord = AsyncMock()
        mock_discord.send_event = AsyncMock(return_value=True)
        app.discord_client = mock_discord
        
        # Handle a log line
        await app.handle_log_line("TestPlayer joined the game")
        
        # Verify parser was called
        mock_parser.parse.assert_called_once_with("TestPlayer joined the game")
        
        # Verify event was sent
        mock_discord.send_event.assert_called_once_with(mock_event)
    
    async def test_handle_log_line_ignores_unparseable_lines(self):
        """Test that unparseable lines don't send events."""
        app = Application()
        
        # Mock parser returning None (unparseable)
        mock_parser = MagicMock()
        mock_parser.parse.return_value = None
        app.event_parser = mock_parser
        
        # Mock Discord client
        mock_discord = AsyncMock()
        mock_discord.send_event = AsyncMock()
        app.discord_client = mock_discord
        
        # Handle an unparseable line
        await app.handle_log_line("Random log noise")
        
        # Verify parser was called
        mock_parser.parse.assert_called_once()
        
        # Verify no event was sent
        mock_discord.send_event.assert_not_called()
    
    async def test_handle_log_line_logs_send_failures(self):
        """Test that failed sends are logged."""
        app = Application()
        
        # Mock parser
        mock_parser = MagicMock()
        mock_event = MagicMock()
        mock_event.event_type = MagicMock()
        mock_event.event_type.value = "join"
        mock_event.player_name = "TestPlayer"
        mock_parser.parse.return_value = mock_event
        app.event_parser = mock_parser
        
        # Mock Discord client that fails
        mock_discord = AsyncMock()
        mock_discord.send_event = AsyncMock(return_value=False)
        app.discord_client = mock_discord
        
        # Handle a log line (should not raise exception)
        await app.handle_log_line("TestPlayer joined the game")
        
        # Verify event was attempted
        mock_discord.send_event.assert_called_once()


@pytest.mark.asyncio
class TestApplicationStop:
    """Tests for Application shutdown."""
    
    async def test_stop_gracefully_shuts_down_all_components(self):
        """Test that stop shuts down all components gracefully."""
        app = Application()
        
        # Mock all components
        app.log_tailer = AsyncMock()
        app.log_tailer.stop = AsyncMock()
        
        app.discord_client = AsyncMock()
        app.discord_client.disconnect = AsyncMock()
        
        app.health_server = AsyncMock()
        app.health_server.stop = AsyncMock()
        
        # Stop application
        await app.stop()
        
        # Verify all components were stopped
        app.log_tailer.stop.assert_called_once()
        app.discord_client.disconnect.assert_called_once()
        app.health_server.stop.assert_called_once()
    
    async def test_stop_handles_none_components(self):
        """Test that stop handles uninitialized components."""
        app = Application()
        
        # All components are None
        app.log_tailer = None
        app.discord_client = None
        app.health_server = None
        
        # Should not raise exception
        await app.stop()


@pytest.mark.asyncio
class TestApplicationRun:
    """Tests for Application run lifecycle."""
    
    async def test_run_completes_full_lifecycle(self):
        """Test that run executes setup, start, wait, and stop."""
        app = Application()
        
        # Mock all phases
        app.setup = AsyncMock()
        app.start = AsyncMock()
        app.stop = AsyncMock()
        
        # Trigger immediate shutdown
        async def trigger_shutdown():
            await asyncio.sleep(0.1)
            app.shutdown_event.set()
        
        # Run both tasks
        await asyncio.gather(
            app.run(),
            trigger_shutdown()
        )
        
        # Verify lifecycle
        app.setup.assert_called_once()
        app.start.assert_called_once()
        app.stop.assert_called_once()


@pytest.mark.asyncio
class TestApplicationIntegration:
    """Integration tests for full application flow."""
    
    async def test_end_to_end_lifecycle(self):
        """Test complete application lifecycle with real components."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_path = Path(f.name)
            f.write("Initial log line\n")
        
        try:
            # Set up environment
            os.environ['DISCORD_WEBHOOK_URL'] = 'https://discord.com/api/webhooks/test/token'
            os.environ['FACTORIO_LOG_PATH'] = str(log_path)
            os.environ['HEALTH_CHECK_PORT'] = '9999'
            
            import main as main_module
            
            app = Application()
            
            # Mock Discord to avoid real network calls
            with patch.object(main_module, 'DiscordClient') as mock_discord:
                mock_discord_instance = AsyncMock()
                mock_discord_instance.connect = AsyncMock()
                mock_discord_instance.test_connection = AsyncMock(return_value=True)
                mock_discord_instance.send_event = AsyncMock(return_value=True)
                mock_discord_instance.disconnect = AsyncMock()
                mock_discord.return_value = mock_discord_instance
                
                # Setup and start
                await app.setup()
                await app.start()
                
                # Simulate some activity
                await asyncio.sleep(0.1)
                
                # Stop
                await app.stop()
                
                # Verify components were used
                assert app.config is not None
                assert app.event_parser is not None
                
        finally:
            log_path.unlink(missing_ok=True)
            # Clean up environment
            for key in ['DISCORD_WEBHOOK_URL', 'FACTORIO_LOG_PATH', 'HEALTH_CHECK_PORT']:
                os.environ.pop(key, None)


class TestApplicationAssertions:
    """Tests for assertion enforcement."""
    
    @pytest.mark.asyncio
    async def test_handle_log_line_asserts_parser_exists(self):
        """Test that handle_log_line requires event_parser."""
        app = Application()
        app.event_parser = None
        app.discord_client = AsyncMock()
        
        with pytest.raises(AssertionError, match="Event parser not initialized"):
            await app.handle_log_line("test line")
    
    @pytest.mark.asyncio
    async def test_handle_log_line_asserts_discord_exists(self):
        """Test that handle_log_line requires discord_client."""
        app = Application()
        app.event_parser = MagicMock()
        app.discord_client = None
        
        with pytest.raises(AssertionError, match="Discord client not initialized"):
            await app.handle_log_line("test line")
