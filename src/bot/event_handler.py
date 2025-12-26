

"""Event handling and Discord message delivery with mention resolution."""

import os
from typing import Any, Optional, List, Dict
import discord
import yaml  # type: ignore[import]
import structlog

logger = structlog.get_logger()


class EventHandler:
    """Handle Factorio event delivery to Discord with mention resolution."""

    def __init__(self, bot: Any) -> None:
        """
        Initialize event handler.

        Args:
            bot: DiscordBot instance with server_manager
        """
        self.bot = bot
        self._mention_group_keywords: Dict[str, List[str]] = {}
        self._load_mention_config()

    def _load_mention_config(self) -> None:
        """
        Load custom mention group keywords from config/mentions.yml.

        Expected format:

        mentions:
          groups:
            operations:
              - "operations"
              - "ops"
        """
        config_path = os.path.join("config", "mentions.yml")
        if not os.path.exists(config_path):
            logger.info("mention_config_not_found", path=config_path)
            self._mention_group_keywords = {}
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("mention_config_load_failed", path=config_path, error=str(e))
            self._mention_group_keywords = {}
            return

        mentions = data.get("mentions") or {}
        groups = mentions.get("roles") or {}

        result: Dict[str, List[str]] = {}
        for group_name, tokens in groups.items():
            if isinstance(tokens, list):
                cleaned = [str(t).strip() for t in tokens if str(t).strip()]
                if cleaned:
                    result[group_name] = cleaned

        self._mention_group_keywords = result
        logger.info(
            "mention_config_loaded",
            path=config_path,
            groups=len(self._mention_group_keywords),
        )

    def _get_channel_for_event(self, event: Any) -> Optional[int]:
        """
        Determine which Discord channel should receive this event.

        Uses per-server event_channel_id from ServerConfig.

        Args:
            event: Factorio event with server_tag

        Returns:
            Discord channel ID or None if not configured
        """
        server_tag = getattr(event, "server_tag", None)

        if not server_tag:
            logger.warning("event_missing_server_tag", event_type=event.event_type.value)
            return None

        if not self.bot.server_manager:
            logger.warning("no_server_manager_for_event_routing")
            return None

        try:
            config = self.bot.server_manager.get_config(server_tag)
            channel_id = config.event_channel_id

            if channel_id is None:
                logger.warning(
                    "server_has_no_event_channel",
                    server_tag=server_tag,
                )

            return channel_id
        except KeyError:
            logger.error(
                "server_tag_not_found_in_manager",
                server_tag=server_tag,
            )
            return None

    async def send_event(self, event: Any) -> bool:
        """
        Send a Factorio event to Discord with @mention support.

        Args:
            event: Factorio event to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            from .event_parser import FactorioEvent  # type: ignore
        except ImportError:
            try:
                from event_parser import FactorioEvent  # type: ignore
            except ImportError:
                logger.error("event_parser_not_available")
                return False

        try:
            from .discord_interface import EmbedBuilder  # type: ignore
        except ImportError:
            try:
                from discord_interface import EmbedBuilder  # type: ignore
            except ImportError:
                logger.error("discord_interface_not_available")
                return False

        try:
            from .event_parser import FactorioEventFormatter  # type: ignore
        except ImportError:
            try:
                from event_parser import FactorioEventFormatter  # type: ignore
            except ImportError:
                logger.error("event_formatter_not_available")
                return False

        if not self.bot._connected:
            logger.warning("send_event_not_connected", event_type=event.event_type.value)
            return False

        # Get per-server channel from ServerManager
        channel_id = self._get_channel_for_event(event)

        if channel_id is None:
            logger.warning(
                "send_event_no_channel_configured",
                event_type=event.event_type.value,
                server_tag=getattr(event, "server_tag", None),
            )
            return False

        try:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                logger.error(
                    "send_event_channel_not_found",
                    channel_id=channel_id,
                    server_tag=getattr(event, "server_tag", None),
                )
                return False

            if not isinstance(channel, discord.TextChannel):
                logger.error(
                    "send_event_invalid_channel_type",
                    channel_id=channel_id,
                    server_tag=getattr(event, "server_tag", None),
                )
                return False

            # Base formatted message
            message = FactorioEventFormatter.format_for_discord(event)

            # Mention handling – use metadata from EventParser
            mentions = event.metadata.get("mentions", [])
            if mentions:
                discord_mentions = await self._resolve_mentions(channel.guild, mentions)
                if discord_mentions:
                    # If the formatted message already contains @tokens, replace them.
                    for token, resolved in zip(mentions, discord_mentions):
                        raw_token = f"@{token}"
                        if raw_token in message:
                            message = message.replace(raw_token, resolved)
                        else:
                            # Fallback: append if not present in text
                            message = f"{message}\n{resolved}"

                    logger.info(
                        "mentions_added_to_message",
                        event_type=event.event_type.value,
                        mention_count=len(discord_mentions),
                    )

            await channel.send(message)
            logger.debug(
                "event_sent",
                event_type=event.event_type.value,
                server_tag=getattr(event, "server_tag", None),
                channel_id=channel_id,
            )
            return True
        except Exception as e:
            logger.error(
                "send_event_unexpected_error",
                error=str(e),
                server_tag=getattr(event, "server_tag", None),
                channel_id=channel_id,
                exc_info=True,
            )
            return False

    async def _resolve_mentions(
        self,
        guild: discord.Guild,
        mentions: List[str],
    ) -> List[str]:
        """
        Resolve Factorio @mentions to actual Discord mentions.

        - User tokens try to map to members.
        - Group tokens try to map to roles or special @everyone / @here.

        Returns:
            List of mention strings you can append to a message.
        """
        discord_mentions: List[str] = []

        # Built-in groups
        base_group_keywords: Dict[str, List[str]] = {
            "admins": ["admin", "admins", "administrator", "administrators"],
            "mods": ["mod", "mods", "moderator", "moderators"],
            "everyone": ["everyone"],
            "here": ["here"],
            "staff": ["staff"],
        }

        # Merge in custom groups from config/mentions.yml (may override built-ins)
        group_keywords: Dict[str, List[str]] = {**base_group_keywords, **self._mention_group_keywords}

        for token in mentions:
            token_lower = token.lower()
            is_group = False

            for group_key, variants in group_keywords.items():
                if token_lower in [v.lower() for v in variants]:
                    is_group = True

                    if group_key == "everyone":
                        discord_mentions.append("@everyone")
                        logger.debug(
                            "mention_resolved_to_everyone",
                            original=token,
                        )
                        break

                    if group_key == "here":
                        discord_mentions.append("@here")
                        logger.debug(
                            "mention_resolved_to_here",
                            original=token,
                        )
                        break

                    role = self._find_role_by_name(guild, variants)
                    if role:
                        discord_mentions.append(role.mention)
                        logger.debug(
                            "mention_resolved_to_role",
                            original=token,
                            role_name=role.name,
                            role_id=role.id,
                        )
                    else:
                        logger.warning(
                            "mention_role_not_found",
                            original=token,
                            searched_names=variants,
                        )
                    break

            if is_group:
                continue

            # User resolution
            member = await self._find_member_by_name(guild, token)
            if member:
                discord_mentions.append(member.mention)
                logger.debug(
                    "mention_resolved_to_user",
                    original=token,
                    user_name=member.name,
                    user_id=member.id,
                )
            else:
                logger.debug("mention_user_not_found", original=token)

        return discord_mentions

    def _find_role_by_name(
        self,
        guild: discord.Guild,
        role_names: List[str],
    ) -> Optional[discord.Role]:
        """
        Find a role by trying multiple name variants (case-insensitive).
        """
        for role in guild.roles:
            role_name_lower = role.name.lower()
            for candidate in role_names:
                if role_name_lower == candidate.lower():
                    return role
        return None

    async def _find_member_by_name(
        self,
        guild: discord.Guild,
        name: str,
    ) -> Optional[discord.Member]:
        """
        Find a guild member by username or display name (exact, then partial).
        """
        name_lower = name.lower()

        # Exact match
        for member in guild.members:
            if (
                member.name.lower() == name_lower
                or member.display_name.lower() == name_lower
            ):
                return member

        # Partial match
        for member in guild.members:
            if (
                name_lower in member.name.lower()
                or name_lower in member.display_name.lower()
            ):
                return member

        return None
