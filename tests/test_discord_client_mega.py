"""
Comprehensive test suite for discord_client.py.

Covers:

- DiscordClient initialization and configuration
- Webhook URL resolution and multi-channel routing
- Connection lifecycle
- send_message behavior (including explicit webhook override, rate limiting, retries, and errors)
- send_event behavior with routing, metadata handling, and failure assertions
- test_connection success and failure paths
"""

from __future__ import annotations

import asyncio
from typing import Dict, Optional, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import pytest
import aiohttp

# Import the module under test
try:
    from discord_client import DiscordClient
    from event_parser import FactorioEvent, EventType, FactorioEventFormatter
except ImportError:  # Fallback for direct execution
    import sys

    sys.path.insert(0, ".")
    from discord_client import DiscordClient  # type: ignore
    from event_parser import FactorioEvent, EventType, FactorioEventFormatter  # type: ignore


# ======================================================================
# Initialization tests
# ======================================================================


class TestDiscordClientInit:
    """Test DiscordClient initialization."""

    def test_init_with_minimal_params(self) -> None:
        """Test initialization with only required parameters."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/test")

        assert client.default_webhook_url == "https://discord.com/api/webhooks/test"
        assert client.bot_name == "FactorioISR"
        assert client.bot_avatar_url is None
        assert client.rate_limit_delay == 0.5
        assert client.max_retries == 3
        assert client.webhook_channels == {}
        assert client.session is None
        assert client.last_send_time == 0

    def test_init_with_all_params(self) -> None:
        """Test initialization with all parameters."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin",
            "events": "https://discord.com/webhooks/events",
        }

        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/default",
            bot_name="Test Bot",
            bot_avatar_url="https://example.com/avatar.png",
            rate_limit_delay=1.0,
            max_retries=5,
            webhook_channels=webhook_channels,
        )

        assert client.default_webhook_url == "https://discord.com/api/webhooks/default"
        assert client.bot_name == "Test Bot"
        assert client.bot_avatar_url == "https://example.com/avatar.png"
        assert client.rate_limit_delay == 1.0
        assert client.max_retries == 5
        assert client.webhook_channels == webhook_channels

    def test_init_with_none_webhook_channels(self) -> None:
        """Test that None webhook_channels becomes empty dict."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/test",
            webhook_channels=None,
        )

        assert client.webhook_channels == {}
        assert isinstance(client.webhook_channels, dict)


# ======================================================================
# Webhook URL routing tests
# ======================================================================


class TestGetWebhookUrl:
    """Test webhook URL routing logic."""

    def test_get_webhook_url_default(self) -> None:
        """Test getting default webhook URL."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/default")
        result = client.get_webhook_url()
        assert result == "https://discord.com/webhooks/default"

    def test_get_webhook_url_with_configured_channel(self) -> None:
        """Test getting webhook URL for configured channel."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin",
        }

        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            webhook_channels=webhook_channels,
        )

        result = client.get_webhook_url("admin")
        assert result == "https://discord.com/webhooks/admin"

    def test_get_webhook_url_with_unconfigured_channel(self) -> None:
        """Test fallback to default for unconfigured channel."""
        webhook_channels: Dict[str, str] = {
            "admin": "https://discord.com/webhooks/admin",
        }

        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            webhook_channels=webhook_channels,
        )

        result = client.get_webhook_url("nonexistent")
        assert result == "https://discord.com/webhooks/default"

    def test_get_webhook_url_with_none_channel(self) -> None:
        """Test that None channel returns default URL."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/default")
        result = client.get_webhook_url(None)
        assert result == "https://discord.com/webhooks/default"

    def test_get_webhook_url_with_empty_string_channel(self) -> None:
        """Test that empty string channel returns default URL."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/default")
        result = client.get_webhook_url("")
        assert result == "https://discord.com/webhooks/default"


# ======================================================================
# Multi-channel routing tests
# ======================================================================


class TestMultiChannelRouting:
    """Test multi-channel routing functionality."""

    def test_get_webhook_url_with_channel(self) -> None:
        """Test getting webhook URL for configured channel."""
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token",
            "admin": "https://discord.com/api/webhooks/456/admin_token",
        }

        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/999/default",
            webhook_channels=webhooks,
        )

        assert client.get_webhook_url("chat") == webhooks["chat"]
        assert client.get_webhook_url("admin") == webhooks["admin"]

    def test_get_webhook_url_fallback(self) -> None:
        """Test fallback to default when channel not configured."""
        default_url = "https://discord.com/api/webhooks/999/default"
        client = DiscordClient(webhook_url=default_url, webhook_channels={})

        assert client.get_webhook_url("nonexistent") == default_url
        assert client.get_webhook_url(None) == default_url

    def test_get_webhook_url_no_channel(self) -> None:
        """Test getting default webhook when no channel specified."""
        default_url = "https://discord.com/api/webhooks/999/default"
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token",
        }

        client = DiscordClient(
            webhook_url=default_url,
            webhook_channels=webhooks,
        )

        assert client.get_webhook_url() == default_url
        assert client.get_webhook_url(None) == default_url

    def test_webhook_channels_defaults_to_empty_dict(self) -> None:
        """Test that webhook_channels defaults to empty dict when None."""
        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/999/default",
            webhook_channels=None,
        )

        assert isinstance(client.webhook_channels, dict)
        assert len(client.webhook_channels) == 0


# ======================================================================
# Connection tests
# ======================================================================


class TestConnect:
    """Test connection establishment."""

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Test successful connection."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        # Patch send_message to avoid real HTTP
        with patch.object(client, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await client.connect()

        assert client.session is not None
        assert isinstance(client.session, aiohttp.ClientSession)
        mock_send.assert_called_once()
        await client.session.close()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_connect_already_connected(self) -> None:
        """Test that connecting when already connected doesn't create new session."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        with patch.object(client, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await client.connect()
            first_session = client.session

            await client.connect()
            second_session = client.session

        assert first_session is second_session
        await client.session.close()  # type: ignore[union-attr]


class TestDisconnect:
    """Tests for disconnect lifecycle."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_session_and_sends_message(self) -> None:
        """disconnect should send a message and close the session when connected."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")

        fake_session = MagicMock(spec=aiohttp.ClientSession)
        fake_session.close = AsyncMock()
        client.session = fake_session

        with patch.object(client, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await client.disconnect()

        mock_send.assert_awaited_once()
        fake_session.close.assert_awaited_once()
        assert client.session is None

    @pytest.mark.asyncio
    async def test_disconnect_no_session_is_noop(self) -> None:
        """disconnect should be a no-op when session is None."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/test")
        client.session = None

        # If send_message were called with no session, it would assert,
        # so ensure disconnect does not attempt to send in this case.
        await client.disconnect()
        assert client.session is None


# ======================================================================
# send_message tests
# ======================================================================


class TestSendMessage:
    """Test send_message behavior."""

    @pytest.mark.asyncio
    async def test_send_message_uses_default_webhook(self) -> None:
        """Test send_message uses default webhook when none provided."""
        client = DiscordClient(webhook_url="https://discord.com/webhooks/default")
        client.session = MagicMock(spec=aiohttp.ClientSession)

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        client.session.post = MagicMock(return_value=mock_response)  # type: ignore[assignment]

        result = await client.send_message("Test message")

        assert result is True
        client.session.post.assert_called_once()  # type: ignore[union-attr]
        url_arg = client.session.post.call_args[0][0]  # type: ignore[union-attr]
        assert url_arg == "https://discord.com/webhooks/default"

    @pytest.mark.asyncio
    async def test_send_message_with_specific_webhook(self) -> None:
        """Test send_message with explicit webhook URL."""
        default_url = "https://discord.com/api/webhooks/999/default"
        custom_url = "https://discord.com/api/webhooks/888/custom"
        client = DiscordClient(webhook_url=default_url)
        client.session = MagicMock(spec=aiohttp.ClientSession)

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        client.session.post = MagicMock(return_value=mock_response)  # type: ignore[assignment]

        result = await client.send_message("Test message", webhook_url=custom_url)

        assert result is True
        call_args = client.session.post.call_args  # type: ignore[union-attr]
        assert call_args[0][0] == custom_url

    @pytest.mark.asyncio
    async def test_send_message_adds_avatar_url_when_present(self) -> None:
        """send_message should include avatar_url in payload when configured."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            bot_avatar_url="https://example.com/avatar.png",
        )
        client.session = MagicMock(spec=aiohttp.ClientSession)

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        client.session.post = MagicMock(return_value=mock_response)  # type: ignore[assignment]

        await client.send_message("With avatar")

        _, kwargs = client.session.post.call_args  # type: ignore[union-attr]
        payload = kwargs["json"]
        assert payload["avatar_url"] == "https://example.com/avatar.png"

    @pytest.mark.asyncio
    async def test_send_message_respects_rate_limit_delay(self, monkeypatch: Any) -> None:
        """Rate limiting branch: when time_since_last < rate_limit_delay, sleep is awaited."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            rate_limit_delay=1.0,
        )
        client.session = MagicMock(spec=aiohttp.ClientSession)

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        client.session.post = MagicMock(return_value=mock_response)  # type: ignore[assignment]

        # Fake clock so that time_since_last < rate_limit_delay
        fake_time = 100.0
        client.last_send_time = fake_time  # same as current to force sleep

        def fake_get_event_loop() -> Any:
            loop = Mock()
            loop.time = Mock(return_value=fake_time)
            return loop

        monkeypatch.setattr(asyncio, "get_event_loop", fake_get_event_loop)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client.send_message("Rate-limited message")

        mock_sleep.assert_awaited()  # sleep was triggered

    @pytest.mark.asyncio
    async def test_send_message_client_error_triggers_retry_and_then_fails(self) -> None:
        """ClientError path: retries then logs failure and returns False."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            max_retries=2,
        )
        client.session = MagicMock(spec=aiohttp.ClientSession)

        # session.post raises ClientError each time
        async def failing_post(*_: Any, **__: Any) -> Any:
            raise aiohttp.ClientError("boom")

        client.session.post = failing_post  # type: ignore[assignment]

        result = await client.send_message("Test client error")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_unexpected_exception_returns_false(self) -> None:
        """Generic Exception inside loop should return False immediately."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            max_retries=3,
        )
        client.session = MagicMock(spec=aiohttp.ClientSession)

        async def raising_post(*_: Any, **__: Any) -> Any:
            raise RuntimeError("unexpected")

        client.session.post = raising_post  # type: ignore[assignment]

        result = await client.send_message("Test unexpected error")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_4xx_client_error_does_not_retry(self) -> None:
        """For 4xx responses, send_message should not retry and should return False."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            max_retries=3,
        )
        client.session = MagicMock(spec=aiohttp.ClientSession)

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not found")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        call_counter = {"count": 0}

        def post_once(*_: Any, **__: Any) -> Any:
            call_counter["count"] += 1
            return mock_response

        client.session.post = post_once  # type: ignore[assignment]

        result = await client.send_message("Client error 4xx")

        assert result is False
        assert call_counter["count"] == 1

    @pytest.mark.asyncio
    async def test_send_message_429_rate_limit_retries_and_succeeds(self) -> None:
        """On 429, send_message should honor retry_after and retry."""
        client = DiscordClient(
            webhook_url="https://discord.com/webhooks/default",
            max_retries=3,
        )
        client.session = MagicMock(spec=aiohttp.ClientSession)

        # First response: 429 with retry_after
        rate_limited = AsyncMock()
        rate_limited.status = 429
        rate_limited.json = AsyncMock(return_value={"retry_after": 0})
        rate_limited.__aenter__ = AsyncMock(return_value=rate_limited)
        rate_limited.__aexit__ = AsyncMock(return_value=None)

        # Second response: success
        success = AsyncMock()
        success.status = 204
        success.__aenter__ = AsyncMock(return_value=success)
        success.__aexit__ = AsyncMock(return_value=None)

        calls = [rate_limited, success]

        def side_effect_post(*_: Any, **__: Any) -> Any:
            return calls.pop(0)

        client.session.post = side_effect_post  # type: ignore[assignment]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client.send_message("Retry after 429")

        assert result is True
        mock_sleep.assert_awaited()  # sleep after 429


# ======================================================================
# send_event tests
# ======================================================================


class TestSendEventRouting:
    """Tests for send_event routing behavior."""

    @pytest.mark.asyncio
    async def test_send_event_with_channel_in_metadata(self) -> None:
        """Test sending event with channel from metadata."""
        webhooks = {
            "milestone": "https://discord.com/api/webhooks/123/milestone_token",
        }

        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/999/default",
            webhook_channels=webhooks,
        )

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session

        event = FactorioEvent(
            event_type=EventType.MILESTONE,
            player_name="TestPlayer",
            message="Rocket launched",
            raw_line="test",
            emoji="🚀",
            formatted_message="TestPlayer: Rocket launched",
            metadata={"channel": "milestone"},
        )

        # Patch formatter to avoid depending on formatting details
        with patch.object(
            client, "formatter", autospec=True
        ) as mock_formatter:
            mock_formatter.format_for_discord.return_value = "Formatted milestone"

            result = await client.send_event(event)

        assert result is True
        call_args = mock_session.post.call_args
        assert call_args[0][0] == webhooks["milestone"]
        mock_formatter.format_for_discord.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_send_event_with_explicit_channel_override(self) -> None:
        """Test sending event with explicit channel parameter."""
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token",
            "admin": "https://discord.com/api/webhooks/456/admin_token",
        }

        client = DiscordClient(
            webhook_url="https://discord.com/api/webhooks/999/default",
            webhook_channels=webhooks,
        )

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session

        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="Hello",
            raw_line="test",
            emoji="💬",
            formatted_message="TestPlayer: Hello",
            metadata={"channel": "chat"},
        )

        with patch.object(
            client, "formatter", autospec=True
        ) as mock_formatter:
            mock_formatter.format_for_discord.return_value = "Formatted chat"

            result = await client.send_event(event, channel="admin")

        assert result is True
        call_args = mock_session.post.call_args
        assert call_args[0][0] == webhooks["admin"]
        mock_formatter.format_for_discord.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_send_event_fallback_to_default(self) -> None:
        """Test event falls back to default when channel not configured."""
        default_url = "https://discord.com/api/webhooks/999/default"
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token",
        }

        client = DiscordClient(
            webhook_url=default_url,
            webhook_channels=webhooks,
        )

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session

        event = FactorioEvent(
            event_type=EventType.MILESTONE,
            player_name="TestPlayer",
            message="Achievement",
            raw_line="test",
            emoji="🏆",
            formatted_message="TestPlayer: Achievement",
            metadata={"channel": "unconfigured"},
        )

        with patch.object(
            client, "formatter", autospec=True
        ) as mock_formatter:
            mock_formatter.format_for_discord.return_value = "Formatted achievement"

            result = await client.send_event(event)

        assert result is True
        call_args = mock_session.post.call_args
        assert call_args[0][0] == default_url
        mock_formatter.format_for_discord.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_send_event_no_metadata(self) -> None:
        """Test sending event with no metadata uses default webhook."""
        default_url = "https://discord.com/api/webhooks/999/default"
        webhooks = {
            "chat": "https://discord.com/api/webhooks/123/chat_token",
        }

        client = DiscordClient(
            webhook_url=default_url,
            webhook_channels=webhooks,
        )

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client.session = mock_session

        event = FactorioEvent(
            event_type=EventType.JOIN,
            player_name="TestPlayer",
            raw_line="test",
            emoji="✅",
            formatted_message="TestPlayer joined",
            metadata={},  # Empty metadata
        )

        with patch.object(
            client, "formatter", autospec=True
        ) as mock_formatter:
            mock_formatter.format_for_discord.return_value = "Formatted join"

            result = await client.send_event(event)

        assert result is True
        call_args = mock_session.post.call_args
        assert call_args[0][0] == default_url
        mock_formatter.format_for_discord.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_send_event_asserts_when_not_connected(self) -> None:
        """send_event should assert if session is None."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/default")
        client.session = None

        event = FactorioEvent(
            event_type=EventType.CHAT,
            player_name="TestPlayer",
            message="hi",
            raw_line="test",
            emoji="💬",
            formatted_message="TestPlayer: hi",
            metadata={},
        )

        with pytest.raises(AssertionError):
            await client.send_event(event)


# ======================================================================
# test_connection tests
# ======================================================================


class TestTestConnection:
    """Tests for test_connection helper."""

    @pytest.mark.asyncio
    async def test_test_connection_success(self) -> None:
        """When send_message returns True, test_connection should log success and return True."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/default")
        client.session = MagicMock(spec=aiohttp.ClientSession)

        with patch.object(client, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            result = await client.test_connection()

        assert result is True
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_test_connection_failure(self) -> None:
        """When send_message returns False, test_connection should log failure and return False."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/default")
        client.session = MagicMock(spec=aiohttp.ClientSession)

        with patch.object(client, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False
            result = await client.test_connection()

        assert result is False
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_test_connection_asserts_if_not_connected(self) -> None:
        """test_connection should assert if called without a session."""
        client = DiscordClient(webhook_url="https://discord.com/api/webhooks/default")
        client.session = None

        with pytest.raises(AssertionError):
            await client.test_connection()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
