"""
Discord webhook client for sending Factorio events.

Sends formatted events to Discord via webhooks with rate limiting
and error handling.
"""

import asyncio
from typing import Optional
import aiohttp
import structlog

# Use try/except to support both relative and absolute imports
try:
    from .event_parser import FactorioEvent, FactorioEventFormatter, EventType
except ImportError:
    from event_parser import FactorioEvent, FactorioEventFormatter, EventType

logger = structlog.get_logger()


class DiscordClient:
    """Discord webhook client for posting Factorio events."""
    
    def __init__(
        self,
        webhook_url: str,
        bot_name: str = "Factorio Bridge",
        bot_avatar_url: Optional[str] = None,
        rate_limit_delay: float = 0.5,
        max_retries: int = 3,
    ):
        """
        Initialize Discord client.
        
        Args:
            webhook_url: Discord webhook URL
            bot_name: Name to display for the bot
            bot_avatar_url: Avatar URL for the bot (optional)
            rate_limit_delay: Minimum delay between messages (seconds)
            max_retries: Maximum retry attempts for failed sends
        """
        self.webhook_url = webhook_url
        self.bot_name = bot_name
        self.bot_avatar_url = bot_avatar_url
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_send_time: float = 0
        self.formatter = FactorioEventFormatter()
        self._send_lock = asyncio.Lock()
    
    async def connect(self) -> None:
        """Initialize HTTP session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("discord_client_connected")
    
    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self.session is not None:
            await self.session.close()
            self.session = None
            logger.info("discord_client_disconnected")
    
    async def send_event(self, event: FactorioEvent) -> bool:
        """
        Send a Factorio event to Discord.
        
        Args:
            event: Parsed Factorio event to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Assert session is connected
        assert self.session is not None, "Client not connected - call connect() first"
        
        # Format event for Discord
        message = self.formatter.format_for_discord(event)
        
        # Add emoji based on event type
        emoji = self._get_emoji(event.event_type)
        formatted_message = f"{emoji} {message}"
        
        # Send to Discord
        return await self.send_message(formatted_message)
    
    async def send_message(self, content: str) -> bool:
        """
        Send a raw message to Discord webhook.
        
        Args:
            content: Message content to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Assert session is connected
        assert self.session is not None, "Client not connected - call connect() first"
        
        # Use lock to prevent concurrent sends
        async with self._send_lock:
            # Rate limiting - wait if needed
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self.last_send_time
            
            if time_since_last < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - time_since_last)
            
            # Build webhook payload
            payload = {
                "content": content,
                "username": self.bot_name,
            }
            
            if self.bot_avatar_url:
                payload["avatar_url"] = self.bot_avatar_url
            
            # Attempt send with retries
            for attempt in range(self.max_retries):
                try:
                    async with self.session.post(self.webhook_url, json=payload) as response:
                        self.last_send_time = asyncio.get_event_loop().time()
                        
                        if response.status == 204:
                            logger.debug(
                                "message_sent",
                                content=content[:50],
                                status=response.status,
                                attempt=attempt + 1,
                            )
                            return True
                        elif response.status == 429:
                            # Rate limited
                            retry_after = await response.json()
                            wait_time = retry_after.get("retry_after", 1)
                            logger.warning(
                                "rate_limited",
                                retry_after=wait_time,
                                attempt=attempt + 1,
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            error_text = await response.text()
                            logger.error(
                                "send_failed",
                                status=response.status,
                                error=error_text[:200],
                                attempt=attempt + 1,
                            )
                            
                            # Don't retry on client errors (4xx)
                            if 400 <= response.status < 500:
                                return False
                            
                except aiohttp.ClientError as e:
                    logger.error(
                        "http_error",
                        error=str(e),
                        attempt=attempt + 1,
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                        continue
                except Exception as e:
                    logger.error(
                        "unexpected_error",
                        error=str(e),
                        exc_info=True,
                        attempt=attempt + 1,
                    )
                    return False
            
            logger.error("send_failed_after_retries", max_retries=self.max_retries)
            return False
    
    async def test_connection(self) -> bool:
        """
        Test webhook connection.
        
        Returns:
            True if webhook is valid and reachable
        """
        # Assert session is connected
        assert self.session is not None, "Client not connected - call connect() first"
        
        test_message = f"🔗 **{self.bot_name}** connection test"
        result = await self.send_message(test_message)
        
        if result:
            logger.info("webhook_test_success")
        else:
            logger.error("webhook_test_failed")
        
        return result
    
    @staticmethod
    def _get_emoji(event_type: EventType) -> str:
        """Get emoji for event type."""
        emoji_map = {
            EventType.JOIN: "✅",
            EventType.LEAVE: "❌",
            EventType.CHAT: "💬",
            EventType.SERVER: "🖥️",
            EventType.MILESTONE: "🏆",
            EventType.TASK: "✔️",
            EventType.RESEARCH: "🔬",
            EventType.DEATH: "💀",
        }
        return emoji_map.get(event_type, "ℹ️")
