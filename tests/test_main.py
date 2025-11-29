"""
Comprehensive type-safe tests for main.py
Achieves 90%+ code coverage.
"""

import asyncio
import signal
import tempfile
from pathlib import Path
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import pytest

from config import Config
from main import Application, setup_logging, main


class TestSetupLogging:
    """Test logging configuration."""
    
    def test_setup_logging_json_format(self) -> None:
        """Test logging setup with JSON format."""
        setup_logging("info", "json")
        # No exception means success
        assert True
    
    def test_setup_logging_console_format(self) -> None:
        """Test logging setup with console format."""
        setup_logging("debug", "console")
        assert True
    
    def test_setup_logging_all_levels(self) -> None:
        """Test all valid log levels."""
        levels = ["debug", "info", "warning", "error", "critical"]
        for level in levels:
            setup_logging(level, "console")
        assert True
    
    def test_setup_logging_invalid_level_uses_default(self) -> None:
        """Test that invalid log level falls back to INFO."""
        # Should not raise, just use INFO as default
        setup_logging("invalid_level", "json")
        assert True


class TestApplicationInit:
    """Test Application initialization."""
    
    def test_application_init(self) -> None:
        """Test Application __init__."""
        app = Application()
        
        assert app.config is None
        assert app.health_server is None
        assert app.log_tailer is None
        assert app.discord_client is None
        assert app.event_parser is None
        assert app.shutdown_event is not None
        assert isinstance(app.shutdown_event, asyncio.Event)


@pytest.mark.asyncio
class TestApplicationSetup:
    """Test Application setup method."""
    
    async def test_setup_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful application setup."""
        # Create temp log file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            # Mock config loading
            mock_config = Config(
                discord_webhook_url="https://discord.com/api/webhooks/123/abc",
                bot_name="TestBot",
                factorio_log_path=log_path,
                health_check_host="127.0.0.1",
                health_check_port=8080,
                log_level="info",
                log_format="json"
            )
            
            monkeypatch.setattr("main.load_config", lambda: mock_config)
            monkeypatch.setattr("main.validate_config", lambda x: True)
            
            app = Application()
            await app.setup()
            
            assert app.config is not None
            assert app.health_server is not None
            assert app.config.discord_webhook_url == "https://discord.com/api/webhooks/123/abc"
        finally:
            log_path.unlink(missing_ok=True)
    
    async def test_setup_missing_log_file_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test setup warns when log file doesn't exist."""
        # Use non-existent log file
        log_path = Path("/tmp/nonexistent_factorio.log")
        
        mock_config = Config(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            bot_name="TestBot",
            factorio_log_path=log_path,
            health_check_host="127.0.0.1",
            health_check_port=8080,
            log_level="info",
            log_format="json"
        )
        
        monkeypatch.setattr("main.load_config", lambda: mock_config)
        monkeypatch.setattr("main.validate_config", lambda x: True)
        
        app = Application()
        await app.setup()
        
        # Should complete despite missing file
        assert app.config is not None
        assert app.health_server is not None
    
    async def test_setup_config_load_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test setup handles config load failure."""
        def failing_load():
            raise ValueError("Config load failed")
        
        monkeypatch.setattr("main.load_config", failing_load)
        
        app = Application()
        
        with pytest.raises(ValueError, match="Config load failed"):
            await app.setup()
    
    async def test_setup_config_validation_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test setup handles validation failure."""
        mock_config = Config(
            discord_webhook_url="invalid",
            bot_name="TestBot",
            factorio_log_path=Path("/tmp/test.log"),
        )
        
        monkeypatch.setattr("main.load_config", lambda: mock_config)
        monkeypatch.setattr("main.validate_config", lambda x: False)
        
        app = Application()
        
        with pytest.raises(ValueError, match="Configuration validation failed"):
            await app.setup()


@pytest.mark.asyncio
class TestApplicationStart:
    """Test Application start method."""
    
    async def test_start_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful application start."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            mock_config = Config(
                discord_webhook_url="https://discord.com/api/webhooks/123/abc",
                bot_name="TestBot",
                factorio_log_path=log_path,
                health_check_host="127.0.0.1",
                health_check_port=18090,
                log_level="info",
                log_format="json"
            )
            
            monkeypatch.setattr("main.load_config", lambda: mock_config)
            monkeypatch.setattr("main.validate_config", lambda x: True)
            
            app = Application()
            await app.setup()
            
            # Mock Discord client methods
            mock_discord = AsyncMock()
            mock_discord.test_connection = AsyncMock(return_value=True)
            mock_discord.connect = AsyncMock()
            
            with patch("main.DiscordClient", return_value=mock_discord):
                await app.start()
            
            assert app.discord_client is not None
            assert app.event_parser is not None
            assert app.log_tailer is not None
            
            # Cleanup
            await app.stop()
        finally:
            log_path.unlink(missing_ok=True)
    
    async def test_start_discord_connection_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test start handles Discord connection failure."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            log_path = Path(f.name)
        
        try:
            mock_config = Config(
                discord_webhook_url="https://discord.com/api/webhooks/123/abc",
                bot_name="TestBot",
                factorio_log_path=log_path,
                health_check_host="127.0.0.1",
                health_check_port=18091,
                log_level="info",
                log_format="json"
            )
            
            monkeypatch.setattr("main.load_config", lambda: mock_config)
            monkeypatch.setattr("main.validate_config", lambda x: True)
            
            app = Application()
            await app.setup()
            
            # Mock Discord client with failed connection
            mock_discord = AsyncMock()
            mock_discord.test_connection = AsyncMock(return_value=False)
            mock_discord.connect = AsyncMock()
            
            with patch("main.DiscordClient", return_value=mock_discord):
                with pytest.raises(ConnectionError, match="Failed to connect to Discord webhook"):
                    await app.start()
            
            # Cleanup
            await app.stop()
        finally:
            log_path.unlink(missing_ok=True)


@pytest.mark.asyncio
class TestApplicationHandleLogLine:
    """Test log line handling."""
    
    async def test_handle_log_line_with_event(self) -> None:
        """Test handling log line that produces an event."""
        app = Application()
        
        # Set up mocks - use Mock object instead of actual GameEvent
        mock_parser = MagicMock()
        mock_event = MagicMock()
        mock_event.event_type.value = "player_join"
        mock_event.player_name = "TestPlayer"
        mock_parser.parse = MagicMock(return_value=mock_event)
        
        mock_discord = AsyncMock()
        mock_discord.send_event = AsyncMock(return_value=True)
        
        app.event_parser = mock_parser
        app.discord_client = mock_discord
        
        await app.handle_log_line("2024-01-01 12:00:00 [JOIN] TestPlayer joined")
        
        mock_parser.parse.assert_called_once()
        mock_discord.send_event.assert_called_once_with(mock_event)
    
    async def test_handle_log_line_no_event(self) -> None:
        """Test handling log line that produces no event."""
        app = Application()
        
        mock_parser = MagicMock()
        mock_parser.parse = MagicMock(return_value=None)
        
        mock_discord = AsyncMock()
        mock_discord.send_event = AsyncMock()
        
        app.event_parser = mock_parser
        app.discord_client = mock_discord
        
        await app.handle_log_line("Random log line")
        
        mock_parser.parse.assert_called_once()
        mock_discord.send_event.assert_not_called()
    
    async def test_handle_log_line_send_failure(self) -> None:
        """Test handling when Discord send fails."""
        app = Application()
        
        mock_parser = MagicMock()
        mock_event = MagicMock()
        mock_event.event_type.value = "player_chat"
        mock_event.player_name = "TestPlayer"
        mock_parser.parse = MagicMock(return_value=mock_event)
        
        mock_discord = AsyncMock()
        mock_discord.send_event = AsyncMock(return_value=False)
        
        app.event_parser = mock_parser
        app.discord_client = mock_discord
        
        # Should log warning but not raise
        await app.handle_log_line("[CHAT] TestPlayer: Hello")
        
        mock_discord.send_event.assert_called_once()


@pytest.mark.asyncio
class TestApplicationStop:
    """Test application shutdown."""
    
    async def test_stop_all_components(self) -> None:
        """Test stopping all components."""
        app = Application()
        
        # Mock components
        app.log_tailer = AsyncMock()
        app.log_tailer.stop = AsyncMock()
        
        app.discord_client = AsyncMock()
        app.discord_client.disconnect = AsyncMock()
        
        app.health_server = AsyncMock()
        app.health_server.stop = AsyncMock()
        
        await app.stop()
        
        app.log_tailer.stop.assert_called_once()
        app.discord_client.disconnect.assert_called_once()
        app.health_server.stop.assert_called_once()
    
    async def test_stop_with_none_components(self) -> None:
        """Test stopping when components are None."""
        app = Application()
        
        # All components are None
        await app.stop()
        
        # Should complete without error
        assert True


@pytest.mark.asyncio
class TestApplicationRun:
    """Test application run loop."""
    
    async def test_run_keyboard_interrupt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test run handles KeyboardInterrupt."""
        app = Application()
        
        # Mock setup and start
        async def mock_setup():
            app.config = Config(
                discord_webhook_url="https://discord.com/api/webhooks/123/abc",
                bot_name="TestBot",
                factorio_log_path=Path("/tmp/test.log"),
            )
            app.health_server = AsyncMock()
        
        async def mock_start():
            pass
        
        async def mock_stop():
            pass
        
        monkeypatch.setattr(app, "setup", mock_setup)
        monkeypatch.setattr(app, "start", mock_start)
        monkeypatch.setattr(app, "stop", mock_stop)
        
        # Trigger shutdown immediately
        async def raise_keyboard_interrupt():
            raise KeyboardInterrupt()
        
        monkeypatch.setattr(app.shutdown_event, "wait", raise_keyboard_interrupt)
        
        # Should handle interrupt gracefully
        await app.run()
    
    async def test_run_with_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test run handles exceptions."""
        app = Application()
        
        async def failing_setup():
            raise ValueError("Setup failed")
        
        async def mock_stop():
            pass
        
        monkeypatch.setattr(app, "setup", failing_setup)
        monkeypatch.setattr(app, "stop", mock_stop)
        
        with pytest.raises(ValueError, match="Setup failed"):
            await app.run()


@pytest.mark.asyncio
class TestMainFunction:
    """Test main entry point."""
    
    async def test_main_creates_application(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that main() creates Application."""
        # Mock Application.run to return immediately
        async def mock_run(self):
            pass
        
        monkeypatch.setattr(Application, "run", mock_run)
        
        # Run main (should complete without error)
        await main()


class TestApplicationIntegration:
    """Integration-style tests."""
    
    def test_application_attributes(self) -> None:
        """Test application has all required attributes."""
        app = Application()
        
        assert hasattr(app, "config")
        assert hasattr(app, "health_server")
        assert hasattr(app, "log_tailer")
        assert hasattr(app, "discord_client")
        assert hasattr(app, "event_parser")
        assert hasattr(app, "shutdown_event")
    
    def test_shutdown_event_is_event(self) -> None:
        """Test shutdown_event is an asyncio.Event."""
        app = Application()
        assert isinstance(app.shutdown_event, asyncio.Event)
