

"""User context management for multi-server Discord bot.

Handles per-user server context tracking and RCON client routing.
"""

from typing import Optional, Any, Dict
import structlog

logger = structlog.get_logger()


class UserContextManager:
    """Manage per-user server context in multi-server mode."""

    def __init__(self, bot: Any) -> None:
        """
        Initialize user context manager.

        Args:
            bot: DiscordBot instance with server_manager attribute
        """
        self.bot = bot
        self.user_contexts: Dict[int, str] = {}  # {user_id: server_tag}

    def get_user_server(self, user_id: int) -> str:
        """
        Get user's current server context.

        Args:
            user_id: Discord user ID

        Returns:
            Server tag (defaults to first server for new users)
            
        Raises:
            RuntimeError: If ServerManager not configured or no servers
        """
        if user_id in self.user_contexts:
            return self.user_contexts[user_id]

        # Multi-server is required
        if not self.bot.server_manager:
            raise RuntimeError(
                "ServerManager is not configured (multi-server mode required)"
            )

        tags = self.bot.server_manager.list_tags()
        if not tags:
            raise RuntimeError("No servers configured in ServerManager")

        default_tag = tags[0]
        logger.debug(
            "user_server_context_defaulted",
            user_id=user_id,
            server_tag=default_tag,
        )
        return default_tag

    def set_user_server(self, user_id: int, server_tag: str) -> None:
        """
        Set user's current server context.

        Args:
            user_id: Discord user ID
            server_tag: Server tag to set as context
        """
        self.user_contexts[user_id] = server_tag
        logger.info(
            "user_server_context_changed",
            user_id=user_id,
            server_tag=server_tag,
        )

    def get_rcon_for_user(self, user_id: int) -> Optional[Any]:
        """
        Get RCON client for user's current server context.

        Args:
            user_id: Discord user ID

        Returns:
            RconClient instance or None if not available
            
        Raises:
            RuntimeError: If ServerManager not configured
        """
        if not self.bot.server_manager:
            raise RuntimeError(
                "ServerManager is not configured (multi-server mode required)"
            )

        server_tag = self.get_user_server(user_id)
        try:
            return self.bot.server_manager.get_client(server_tag)
        except KeyError:
            logger.warning(
                "user_server_context_invalid",
                user_id=user_id,
                server_tag=server_tag,
            )
            return None

    def get_server_display_name(self, user_id: int) -> str:
        """
        Get display name of user's current server.

        Args:
            user_id: Discord user ID

        Returns:
            Server display name or "Unknown" if unavailable
            
        Note:
            Returns "Unknown" gracefully on any error (KeyError, manager broken, etc.)
            Never raises to ensure robust operation.
        """
        if not self.bot.server_manager:
            return "Unknown"

        try:
            server_tag = self.get_user_server(user_id)
            config = self.bot.server_manager.get_config(server_tag)
            return config.name
        except (KeyError, RuntimeError, AttributeError, Exception) as e:
            # Gracefully handle:
            # - KeyError: server_tag not in configs
            # - RuntimeError: from get_user_server when manager broken
            # - AttributeError: config missing .name attribute
            # - Generic Exception: any other manager failures
            logger.debug(
                "get_server_display_name_fallback",
                user_id=user_id,
                error=str(e),
            )
            return "Unknown"
