"""
Discord bot client for Factorio ISR - Phase 5.2 Complete.

Provides interactive bot functionality with slash commands, event handling,
Phase 5.1 features (embeds, cooldowns), and Phase 5.2 RCON monitoring.
"""

import asyncio
from datetime import datetime
from typing import Optional, Any
import discord
from discord import app_commands
import structlog

# Phase 5.1: Rate limiting and embeds
from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
from discord_interface import EmbedBuilder

# Import event parser and formatter
try:
    from .event_parser import FactorioEvent, FactorioEventFormatter
except ImportError:
    from event_parser import FactorioEvent, FactorioEventFormatter  # type: ignore

logger = structlog.get_logger()


class DiscordBot(discord.Client):
    """Discord bot client with slash command support and RCON monitoring."""

    def __init__(
        self,
        token: str,
        bot_name: str = "Factorio ISR",
        *,
        intents: Optional[discord.Intents] = None,
    ):
        """
        Initialize Discord bot.

        Args:
            token: Discord bot token
            bot_name: Display name for the bot
            intents: Discord intents (auto-configured if None)
        """
        # Configure intents
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True  # Required to read messages
            intents.guilds = True
            intents.members = True  # Optional, for advanced features

        super().__init__(intents=intents)

        self.token = token
        self.bot_name = bot_name
        self.tree = app_commands.CommandTree(self)
        self._ready = asyncio.Event()
        self._connected = False
        self._connection_task: Optional[asyncio.Task] = None

        # Channel for sending Factorio events (set by application)
        self.event_channel_id: Optional[int] = None

        # RCON client for slash commands (set by application)
        self.rcon_client: Optional[Any] = None

        # Phase 5.2: RCON status monitoring
        self.rcon_last_connected: Optional[datetime] = None
        self.rcon_status_notified = False
        self.rcon_monitor_task: Optional[asyncio.Task] = None

        logger.info("discord_bot_initialized", bot_name=bot_name, phase="5.2")

    # ========================================================================
    # PHASE 5.2: RCON Status Monitoring
    # ========================================================================

    async def update_presence(self) -> None:
        """Update bot presence to reflect RCON connection status."""
        if not self._connected or not hasattr(self, 'user') or self.user is None:
            return

        try:
            if self.rcon_client and self.rcon_client.is_connected:
                # RCON connected - blue status
                status_text = "🔹RCON On"
                status = discord.Status.online
                activity_type = discord.ActivityType.watching
            else:
                # RCON disconnected - warning status
                status_text = "🔺RCON Off"
                status = discord.Status.idle  # Yellow dot
                activity_type = discord.ActivityType.watching

            activity = discord.Activity(
                type=activity_type,
                name=f"{status_text} | /factorio help"
            )

            await self.change_presence(status=status, activity=activity)
            logger.debug("presence_updated", status=status_text)

        except Exception as e:
            logger.warning("presence_update_failed", error=str(e))

    async def _monitor_rcon_status(self) -> None:
        """Monitor RCON connection status and send notifications on changes."""
        logger.info("rcon_status_monitor_started")
        previous_status = None

        while self._connected:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds

                if not self.rcon_client:
                    continue

                current_status = self.rcon_client.is_connected

                # Detect status change
                if previous_status is not None and current_status != previous_status:
                    if current_status:
                        # RCON just reconnected
                        await self._notify_rcon_reconnected()
                        self.rcon_last_connected = datetime.utcnow()
                    else:
                        # RCON just disconnected
                        await self._notify_rcon_disconnected()

                # Update presence to reflect current status
                await self.update_presence()

                # Track last connected time
                if current_status:
                    self.rcon_last_connected = datetime.utcnow()

                previous_status = current_status

            except asyncio.CancelledError:
                logger.info("rcon_status_monitor_cancelled")
                break
            except Exception as e:
                logger.error("rcon_status_monitor_error", error=str(e), exc_info=True)
                await asyncio.sleep(10)

    async def _notify_rcon_disconnected(self) -> None:
        """Send notification when RCON disconnects."""
        if not self.event_channel_id or self.rcon_status_notified:
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                embed = EmbedBuilder.info_embed(
                    title="⚠️ RCON Connection Lost",
                    message=(
                        "Connection to Factorio server lost.\n"
                        "Bot will automatically reconnect when server is available.\n\n"
                        "Commands requiring RCON will be unavailable until reconnection."
                    )
                )
                embed.color = EmbedBuilder.COLOR_WARNING

                await channel.send(embed=embed)
                self.rcon_status_notified = True
                logger.info("rcon_disconnection_notified", channel_id=self.event_channel_id)

        except Exception as e:
            logger.warning("rcon_disconnection_notification_failed", error=str(e))

    async def _notify_rcon_reconnected(self) -> None:
        """Send notification when RCON reconnects."""
        if not self.event_channel_id:
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                # Calculate downtime if we know when we lost connection
                downtime_msg = ""
                if self.rcon_last_connected:
                    downtime = datetime.utcnow() - self.rcon_last_connected
                    minutes = int(downtime.total_seconds() / 60)
                    if minutes > 0:
                        downtime_msg = f"\nDowntime: ~{minutes} minute{'s' if minutes != 1 else ''}"

                embed = EmbedBuilder.info_embed(
                    title="✅ RCON Reconnected",
                    message=(
                        f"Successfully reconnected to Factorio server!{downtime_msg}\n\n"
                        "All bot commands are now fully operational."
                    )
                )
                embed.color = EmbedBuilder.COLOR_SUCCESS

                await channel.send(embed=embed)
                self.rcon_status_notified = False
                logger.info("rcon_reconnection_notified", channel_id=self.event_channel_id)

        except Exception as e:
            logger.warning("rcon_reconnection_notification_failed", error=str(e))

    # ========================================================================
    # Bot Lifecycle
    # ========================================================================

    async def clear_global_commands(self) -> None:
        """Clear all global commands (one-time cleanup)."""
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            logger.info("global_commands_cleared")
        except Exception as e:
            logger.error("clear_global_commands_failed", error=str(e))

    async def setup_hook(self) -> None:
        """Called when the bot is starting up. Set up commands here."""
        await self._register_commands()
        logger.info("discord_bot_setup_complete")

    async def _register_commands(self) -> None:
        """Register slash commands with a single root and subcommands."""
        factorio_group = app_commands.Group(
            name="factorio",
            description="Factorio server status, players, and RCON management",
        )

        # ====================================================================
        # Server Information Commands
        # ====================================================================

        @factorio_group.command(name="ping", description="Ping the Factorio server via RCON")
        async def ping_command(interaction: discord.Interaction) -> None:
            """Check connectivity to the Factorio server and RCON."""
            is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed(
                    "RCON is not configured. Cannot ping Factorio server."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                response = await self.rcon_client.execute("/time")
                embed = EmbedBuilder.info_embed(
                    title="✅ Ping Successful",
                    message=f"Bot → RCON → Factorio server is reachable.\n\n**Response:** {response}"
                )
                await interaction.followup.send(embed=embed)
                logger.info("factorio_ping_success", user=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(
                    f"Could not reach Factorio server via RCON.\n**Error:** {str(e)}"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("factorio_ping_failed", error=str(e))

        @factorio_group.command(name="status", description="Show Factorio server status")
        async def status_command(interaction: discord.Interaction) -> None:
            """Get comprehensive server status with rich embed."""
            is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            try:
                if self.rcon_client and self.rcon_client.is_connected:
                    players = await self.rcon_client.get_players()
                    player_count = len(players)
                    rcon_status = True
                    server_status = "Online"
                else:
                    player_count = 0
                    rcon_status = False
                    server_status = "RCON Disconnected"

                embed = EmbedBuilder.server_status_embed(
                    status=server_status,
                    players_online=player_count,
                    rcon_enabled=rcon_status,
                    uptime="Unknown"
                )

                await interaction.followup.send(embed=embed)

            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Failed to get status: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("status_command_failed", error=str(e))

        @factorio_group.command(name="players", description="List players currently online")
        async def players_command(interaction: discord.Interaction) -> None:
            """List online players with rich embed."""
            is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            try:
                if not self.rcon_client or not self.rcon_client.is_connected:
                    embed = EmbedBuilder.error_embed("RCON not connected")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                players = await self.rcon_client.get_players()
                embed = EmbedBuilder.players_list_embed(players)
                await interaction.followup.send(embed=embed)

            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Failed to get players: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("players_command_failed", error=str(e))

        @factorio_group.command(name="version", description="Show Factorio server version")
        async def version_command(interaction: discord.Interaction) -> None:
            """Display the Factorio server version."""
            is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute("/version")
                embed = EmbedBuilder.info_embed(
                    title="🎮 Factorio Version",
                    message=resp
                )
                await interaction.followup.send(embed=embed)
                logger.info("version_requested", moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Failed to get version: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("version_command_failed", error=str(e))

        @factorio_group.command(name="seed", description="Show the map seed")
        async def seed_command(interaction: discord.Interaction) -> None:
            """Display the current map seed."""
            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute('/c rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)')
                embed = EmbedBuilder.info_embed(
                    title="🌱 Map Seed",
                    message=f"Seed: `{resp.strip()}`\n\nUse this seed to generate an identical map."
                )
                await interaction.followup.send(embed=embed)
                logger.info("seed_requested", moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Failed to get map seed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("seed_command_failed", error=str(e))

        @factorio_group.command(name="evolution", description="Show evolution factor")
        async def evolution_command(interaction: discord.Interaction) -> None:
            """Display the current evolution factor."""
            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute('/c rcon.print(string.format("%.2f%%", game.forces["enemy"].evolution_factor * 100))')
                embed = EmbedBuilder.info_embed(
                    title="🐛 Evolution Factor",
                    message=f"Current evolution: **{resp.strip()}**\n\nHigher evolution means stronger biters!"
                )
                await interaction.followup.send(embed=embed)
                logger.info("evolution_requested", moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Failed to get evolution: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("evolution_command_failed", error=str(e))

        @factorio_group.command(name="admins", description="List server admins")
        async def admins_command(interaction: discord.Interaction) -> None:
            """List all server administrators."""
            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute("/admins")
                embed = EmbedBuilder.info_embed(
                    title="👑 Server Administrators",
                    message=resp
                )
                await interaction.followup.send(embed=embed)
                logger.info("admins_listed", moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Failed to list admins: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("admins_command_failed", error=str(e))

        # PHASE 5.2: Health Check Command
        @factorio_group.command(name="health", description="Check bot and server health status")
        async def health_command(interaction: discord.Interaction) -> None:
            """Display comprehensive health status of bot and connections."""
            await interaction.response.defer()

            # Gather health information
            bot_online = self._connected
            discord_online = self._connected
            rcon_online = self.rcon_client.is_connected if self.rcon_client else False

            # Calculate uptime
            if self.rcon_last_connected and rcon_online:
                uptime = datetime.utcnow() - self.rcon_last_connected
                uptime_str = f"{int(uptime.total_seconds() / 60)} minutes"
            else:
                uptime_str = "N/A"

            # Create health status embed
            embed = discord.Embed(
                title="🏥 Bot Health Status",
                color=EmbedBuilder.COLOR_SUCCESS if rcon_online else EmbedBuilder.COLOR_WARNING,
                timestamp=discord.utils.utcnow()
            )

            # Bot status
            bot_status = "🟢 Online" if bot_online else "🔴 Offline"
            embed.add_field(name="Bot Status", value=bot_status, inline=True)

            # Discord connection
            discord_status = "🟢 Connected" if discord_online else "🔴 Disconnected"
            embed.add_field(name="Discord", value=discord_status, inline=True)

            # RCON connection
            rcon_status = "🟢 Connected" if rcon_online else "🔴 Disconnected"
            embed.add_field(name="RCON", value=rcon_status, inline=True)

            # Additional details
            if self.rcon_client:
                rcon_host = f"{self.rcon_client.host}:{self.rcon_client.port}"
                embed.add_field(name="RCON Host", value=rcon_host, inline=True)

            embed.add_field(name="RCON Uptime", value=uptime_str, inline=True)

            # Guild info
            guild_count = len(self.guilds)
            embed.add_field(name="Servers", value=str(guild_count), inline=True)

            # Overall status
            if bot_online and discord_online and rcon_online:
                overall = "✅ All systems operational"
                embed.color = EmbedBuilder.COLOR_SUCCESS
            elif bot_online and discord_online:
                overall = "⚠️ Bot online, RCON unavailable"
                embed.color = EmbedBuilder.COLOR_WARNING
            else:
                overall = "❌ System issues detected"
                embed.color = EmbedBuilder.COLOR_ERROR

            embed.add_field(name="Overall Status", value=overall, inline=False)
            embed.set_footer(text="Factorio ISR Bot")

            await interaction.followup.send(embed=embed)
            logger.info("health_check_requested", user=interaction.user.name)

        # ====================================================================
        # Player Management Commands
        # ====================================================================

        @factorio_group.command(name="kick", description="Kick a player from the server")
        @app_commands.describe(
            player="Player name to kick",
            reason="Optional reason shown to the player",
        )
        async def kick_command(
            interaction: discord.Interaction,
            player: str,
            reason: str | None = None,
        ) -> None:
            """Kick a player with admin cooldown."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                reason_part = f" {reason}" if reason else ""
                cmd = f"/kick {player}{reason_part}"
                resp = await self.rcon_client.execute(cmd)

                embed = EmbedBuilder.admin_action_embed(
                    action="Player Kicked",
                    player=player,
                    moderator=interaction.user.name,
                    reason=reason,
                    response=resp
                )

                await interaction.followup.send(embed=embed)
                logger.info("player_kicked", player=player, reason=reason, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Kick failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("kick_command_failed", error=str(e), player=player)

        @factorio_group.command(name="ban", description="Ban a player from the server")
        @app_commands.describe(player="Player name to ban")
        async def ban_command(interaction: discord.Interaction, player: str) -> None:
            """Ban a player with admin cooldown."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute(f"/ban {player}")

                embed = EmbedBuilder.admin_action_embed(
                    action="Player Banned",
                    player=player,
                    moderator=interaction.user.name,
                    reason=None,
                    response=resp
                )

                await interaction.followup.send(embed=embed)
                logger.info("player_banned", player=player, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Ban failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("ban_command_failed", error=str(e), player=player)

        @factorio_group.command(name="unban", description="Unban a player from the server")
        @app_commands.describe(player="Player name to unban")
        async def unban_command(interaction: discord.Interaction, player: str) -> None:
            """Unban a player."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute(f"/unban {player}")

                embed = EmbedBuilder.admin_action_embed(
                    action="Player Unbanned",
                    player=player,
                    moderator=interaction.user.name,
                    reason=None,
                    response=resp
                )

                await interaction.followup.send(embed=embed)
                logger.info("player_unbanned", player=player, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Unban failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("unban_command_failed", error=str(e), player=player)

        @factorio_group.command(name="mute", description="Mute a player (prevent chat)")
        @app_commands.describe(player="Player name to mute")
        async def mute_command(interaction: discord.Interaction, player: str) -> None:
            """Mute a player to prevent them from chatting."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute(f"/mute {player}")

                embed = EmbedBuilder.admin_action_embed(
                    action="Player Muted",
                    player=player,
                    moderator=interaction.user.name,
                    reason=None,
                    response=resp
                )

                await interaction.followup.send(embed=embed)
                logger.info("player_muted", player=player, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Mute failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("mute_command_failed", error=str(e), player=player)

        @factorio_group.command(name="unmute", description="Unmute a player")
        @app_commands.describe(player="Player name to unmute")
        async def unmute_command(interaction: discord.Interaction, player: str) -> None:
            """Unmute a player to allow them to chat again."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute(f"/unmute {player}")

                embed = EmbedBuilder.admin_action_embed(
                    action="Player Unmuted",
                    player=player,
                    moderator=interaction.user.name,
                    reason=None,
                    response=resp
                )

                await interaction.followup.send(embed=embed)
                logger.info("player_unmuted", player=player, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Unmute failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("unmute_command_failed", error=str(e), player=player)

        @factorio_group.command(name="promote", description="Promote a player to admin")
        @app_commands.describe(player="Player name to promote")
        async def promote_command(interaction: discord.Interaction, player: str) -> None:
            """Promote a player to admin status."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute(f"/promote {player}")

                embed = EmbedBuilder.admin_action_embed(
                    action="Player Promoted",
                    player=player,
                    moderator=interaction.user.name,
                    reason="Promoted to admin",
                    response=resp
                )

                await interaction.followup.send(embed=embed)
                logger.info("player_promoted", player=player, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Promote failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("promote_command_failed", error=str(e), player=player)

        @factorio_group.command(name="demote", description="Demote a player from admin")
        @app_commands.describe(player="Player name to demote")
        async def demote_command(interaction: discord.Interaction, player: str) -> None:
            """Demote a player from admin status."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute(f"/demote {player}")

                embed = EmbedBuilder.admin_action_embed(
                    action="Player Demoted",
                    player=player,
                    moderator=interaction.user.name,
                    reason="Demoted from admin",
                    response=resp
                )

                await interaction.followup.send(embed=embed)
                logger.info("player_demoted", player=player, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Demote failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("demote_command_failed", error=str(e), player=player)

        # ====================================================================
        # Server Management Commands
        # ====================================================================

        @factorio_group.command(name="save", description="Save the Factorio game")
        @app_commands.describe(name="Optional save name")
        async def save_command(interaction: discord.Interaction, name: str | None = None) -> None:
            is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                await interaction.followup.send(
                    f"⏱️ Slow down! Try again in {retry:.1f}s"
                )
                return
            
            await interaction.response.defer()
            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot save game.")
                return
            try:
                cmd = f"/save {name}" if name else "/save"
                resp = await self.rcon_client.execute(cmd)
                
                # Determine the display label
                if name:
                    # Custom save name provided
                    label = name
                else:
                    # No custom name - parse response or query server
                    # Try to extract save name from response like "Saving to _autosave1 (non-blocking)."
                    import re
                    
                    # First try to get from server directly
                    try:
                        save_name_resp = await self.rcon_client.execute(
                            '/c rcon.print(game.server_save or "unknown")'
                        )
                        label = save_name_resp.strip()
                        if label == "unknown" or not label:
                            # Fallback: try to parse from save response
                            match = re.search(r"Saving to ([\\w-_]+)", resp)
                            label = match.group(1) if match else "current save"
                    except Exception:
                        # Last resort: parse response
                        match = re.search(r"Saving to ([\\w-_]+)", resp)
                        label = match.group(1) if match else "current save"
                
                msg = (
                    f"💾 **Game Saved**\\n\\n"
                    f"Save name: **{label}**\\n\\n"
                    f"Server response:\\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("game_saved", name=label, moderator=interaction.user.name)
            except Exception as e:
                logger.error("save_command_failed", error=str(e), name=name)
                await interaction.followup.send(f"❌ Failed to save game: {str(e)}")

        @factorio_group.command(name="broadcast", description="Send a message to all players")
        @app_commands.describe(message="Message to broadcast to all players")
        async def broadcast_command(interaction: discord.Interaction, message: str) -> None:
            """Broadcast a message to all players on the server."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                escaped_msg = message.replace('"', '\\"')
                resp = await self.rcon_client.execute(f'/c game.print("{escaped_msg}")')

                embed = EmbedBuilder.info_embed(
                    title="📢 Broadcast Sent",
                    message=f"Message: _{message}_\n\nAll online players have been notified."
                )
                embed.color = EmbedBuilder.COLOR_SUCCESS

                await interaction.followup.send(embed=embed)
                logger.info("message_broadcast", message=message, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Broadcast failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("broadcast_command_failed", error=str(e), message=message)

        @factorio_group.command(name="whitelist", description="Manage server whitelist")
        @app_commands.describe(
            action="Action to perform (add/remove/list/enable/disable)",
            player="Player name (required for add/remove)"
        )
        async def whitelist_command(
            interaction: discord.Interaction,
            action: str,
            player: str | None = None
        ) -> None:
            """Manage the server whitelist."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            action = action.lower()

            try:
                if action == "list":
                    resp = await self.rcon_client.execute("/whitelist get")
                    title = "📋 Whitelist"
                elif action == "enable":
                    resp = await self.rcon_client.execute("/whitelist enable")
                    title = "✅ Whitelist Enabled"
                elif action == "disable":
                    resp = await self.rcon_client.execute("/whitelist disable")
                    title = "⚠️ Whitelist Disabled"
                elif action == "add":
                    if not player:
                        embed = EmbedBuilder.error_embed("Player name required for 'add' action")
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
                    resp = await self.rcon_client.execute(f"/whitelist add {player}")
                    title = f"✅ {player} Added to Whitelist"
                    logger.info("whitelist_add", player=player, moderator=interaction.user.name)
                elif action == "remove":
                    if not player:
                        embed = EmbedBuilder.error_embed("Player name required for 'remove' action")
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
                    resp = await self.rcon_client.execute(f"/whitelist remove {player}")
                    title = f"🚫 {player} Removed from Whitelist"
                    logger.info("whitelist_remove", player=player, moderator=interaction.user.name)
                else:
                    embed = EmbedBuilder.error_embed(
                        f"Invalid action: {action}\nValid actions: add, remove, list, enable, disable"
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                embed = EmbedBuilder.info_embed(title=title, message=resp)
                await interaction.followup.send(embed=embed)

            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Whitelist command failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("whitelist_command_failed", error=str(e), action=action, player=player)

        # ====================================================================
        # Game Control Commands
        # ====================================================================

        @factorio_group.command(name="time", description="Set or display game time")
        @app_commands.describe(value="Time value (e.g., 0.5 for noon, 0 for midnight) or leave empty to view")
        async def time_command(interaction: discord.Interaction, value: float | None = None) -> None:
            """Set or display the game time."""
            is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                if value is None:
                    # Display current time
                    resp = await self.rcon_client.execute("/time")
                    embed = EmbedBuilder.info_embed(
                        title="🕐 Current Game Time",
                        message=resp
                    )
                else:
                    # Set time
                    resp = await self.rcon_client.execute(f'/c game.surfaces["nauvis"].daytime = {value}')
                    time_desc = "noon" if abs(value - 0.5) < 0.1 else "midnight" if value < 0.1 else f"{value}"
                    embed = EmbedBuilder.info_embed(
                        title="🕐 Time Changed",
                        message=f"Game time set to: **{time_desc}**\n\nServer response:\n{resp}"
                    )
                    logger.info("time_changed", value=value, moderator=interaction.user.name)

                await interaction.followup.send(embed=embed)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Time command failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("time_command_failed", error=str(e), value=value)

        @factorio_group.command(name="speed", description="Set game speed (admin only)")
        @app_commands.describe(speed="Game speed multiplier (0.1 to 10.0, default 1.0)")
        async def speed_command(interaction: discord.Interaction, speed: float) -> None:
            """Set the game speed multiplier."""
            is_limited, retry = DANGER_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if speed < 0.1 or speed > 10.0:
                embed = EmbedBuilder.error_embed("Speed must be between 0.1 and 10.0")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute(f"/c game.speed = {speed}")
                embed = EmbedBuilder.info_embed(
                    title="⚡ Game Speed Changed",
                    message=f"Speed multiplier: **{speed}x**\n\n⚠️ This affects all players!\n\nServer response:\n{resp}"
                )
                embed.color = EmbedBuilder.COLOR_WARNING

                await interaction.followup.send(embed=embed)
                logger.info("speed_changed", speed=speed, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"Speed change failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("speed_command_failed", error=str(e), speed=speed)

        @factorio_group.command(name="research", description="Force research a technology")
        @app_commands.describe(technology="Technology name to research")
        async def research_command(interaction: discord.Interaction, technology: str) -> None:
            """Force research a technology."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                cmd = f'/c game.forces["player"].technologies["{technology}"].researched = true'
                resp = await self.rcon_client.execute(cmd)

                embed = EmbedBuilder.info_embed(
                    title="🔬 Technology Researched",
                    message=f"Technology: **{technology}**\n\nThe technology has been forcefully researched.\n\nServer response:\n{resp}"
                )
                embed.color = EmbedBuilder.COLOR_SUCCESS

                await interaction.followup.send(embed=embed)
                logger.info("tech_researched", technology=technology, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(
                    f"Research failed: {str(e)}\n\nMake sure the technology name is correct (e.g., 'automation', 'logistics')"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("research_command_failed", error=str(e), technology=technology)

        # ====================================================================
        # Advanced Commands
        # ====================================================================

        @factorio_group.command(name="rcon", description="Run a raw RCON command")
        @app_commands.describe(command="Raw RCON command, e.g. /time or /ban Alice")
        async def rcon_command(interaction: discord.Interaction, command: str) -> None:
            """Execute raw RCON command."""
            is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            if self.rcon_client is None:
                embed = EmbedBuilder.error_embed("RCON not available")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                resp = await self.rcon_client.execute(command)

                embed = EmbedBuilder.info_embed(
                    title="🖥️ RCON Executed",
                    message=f"Command: `{command}`\n\nServer response:\n{resp}"
                )

                await interaction.followup.send(embed=embed)
                logger.info("raw_rcon_executed", command=command, moderator=interaction.user.name)
            except Exception as e:
                embed = EmbedBuilder.error_embed(f"RCON command failed: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error("rcon_command_failed", error=str(e), command=command)

        @factorio_group.command(name="help", description="Show available Factorio commands")
        async def help_command(interaction: discord.Interaction) -> None:
            """Display comprehensive help message."""
            is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
            if is_limited:
                embed = EmbedBuilder.cooldown_embed(retry)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            help_text = (
                "**🏭 Factorio ISR Bot – Commands**\n\n"
                "**📊 Server Information**\n"
                "`/factorio status` – Show server status and uptime\n"
                "`/factorio players` – List players currently online\n"
                "`/factorio ping` – Ping the Factorio server via RCON\n"
                "`/factorio version` – Show Factorio server version\n"
                "`/factorio seed` – Show map seed\n"
                "`/factorio evolution` – Show biter evolution factor\n"
                "`/factorio admins` – List server administrators\n"
                "`/factorio health` – Check bot and server health\n\n"
                "**👥 Player Management**\n"
                "`/factorio kick <player> [reason]` – Kick a player\n"
                "`/factorio ban <player>` – Ban a player\n"
                "`/factorio unban <player>` – Unban a player\n"
                "`/factorio mute <player>` – Mute a player from chat\n"
                "`/factorio unmute <player>` – Unmute a player\n"
                "`/factorio promote <player>` – Promote player to admin\n"
                "`/factorio demote <player>` – Demote player from admin\n\n"
                "**🔧 Server Management**\n"
                "`/factorio broadcast <message>` – Send message to all players\n"
                "`/factorio save [name]` – Save the game\n"
                "`/factorio whitelist <action> [player]` – Manage whitelist\n"
                " └ Actions: add, remove, list, enable, disable\n\n"
                "**🎮 Game Control**\n"
                "`/factorio time [value]` – Set/display game time\n"
                "`/factorio speed <multiplier>` – Set game speed (0.1-10.0)\n"
                "`/factorio research <technology>` – Force research tech\n\n"
                "**🛠️ Advanced**\n"
                "`/factorio rcon <command>` – Run raw RCON command\n"
                "`/factorio help` – Show this help message\n\n"
                "_Most commands require RCON to be enabled._"
            )

            await interaction.response.send_message(help_text)

        # Register the group
        self.tree.add_command(factorio_group)
        logger.info(
            "slash_commands_registered",
            root=factorio_group.name,
            command_count=len(factorio_group.commands),
            phase="5.2",
        )

    # ========================================================================
    # Discord Event Handlers
    # ========================================================================

    async def on_ready(self) -> None:
        """Called when bot is ready."""
        if self.user is None:
            logger.error("discord_bot_ready_but_no_user")
            return

        logger.info(
            "discord_bot_ready",
            bot_name=self.user.name,
            bot_id=self.user.id,
            guilds=len(self.guilds),
            phase="5.2"
        )

        # Set connected flag and signal ready
        self._connected = True
        self._ready.set()

        try:
            # Sync commands globally
            synced_global = await self.tree.sync()
            logger.info(
                "commands_synced_globally",
                count=len(synced_global),
                commands=[cmd.name for cmd in synced_global],
            )

            # Copy to guilds
            for guild in self.guilds:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)

                top_level = self.tree.get_commands(guild=guild)
                logger.info(
                    "commands_synced_to_guild",
                    guild_name=guild.name,
                    guild_id=guild.id,
                    command_count=len(top_level),
                )

        except Exception as e:
            logger.error("command_sync_failed", error=str(e), exc_info=True)

    async def on_disconnect(self) -> None:
        """Called when bot disconnects."""
        self._connected = False
        logger.warning("discord_bot_disconnected")

    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Called when an error occurs."""
        logger.error("discord_bot_error", event=event, exc_info=True)

    # ========================================================================
    # Connection Management (Phase 5.2 Enhanced)
    # ========================================================================

    async def connect_bot(self) -> None:
        """Connect the bot to Discord with RCON monitoring."""
        try:
            logger.info("connecting_to_discord", phase="5.2")

            await self.login(self.token)
            self._connection_task = asyncio.create_task(self.connect())

            try:
                await asyncio.wait_for(self._ready.wait(), timeout=30.0)
                logger.info("discord_bot_connected")

                # Send connection notification
                await self._send_connection_notification()

                # PHASE 5.2: Start RCON status monitoring
                if not self.rcon_monitor_task:
                    self.rcon_monitor_task = asyncio.create_task(
                        self._monitor_rcon_status()
                    )
                    logger.info("rcon_status_monitoring_enabled")

                # Initial presence update
                await self.update_presence()

            except asyncio.TimeoutError:
                logger.error("discord_bot_connection_timeout")
                if self._connection_task is not None:
                    self._connection_task.cancel()
                    try:
                        await self._connection_task
                    except asyncio.CancelledError:
                        pass
                raise ConnectionError("Discord bot connection timed out after 30 seconds")

        except discord.errors.LoginFailure as e:
            logger.error("discord_login_failed", error=str(e))
            raise ConnectionError(f"Discord login failed: {e}")
        except Exception as e:
            logger.error("discord_bot_connection_failed", error=str(e), exc_info=True)
            raise

    async def disconnect_bot(self) -> None:
        """Disconnect the bot from Discord and stop monitoring."""
        if self._connected or self._connection_task is not None:
            logger.info("disconnecting_from_discord", phase="5.2")

            # PHASE 5.2: Stop RCON monitoring
            if self.rcon_monitor_task:
                self.rcon_monitor_task.cancel()
                try:
                    await self.rcon_monitor_task
                except asyncio.CancelledError:
                    pass
                self.rcon_monitor_task = None
                logger.info("rcon_status_monitoring_disabled")

            # Send disconnection notification
            await self._send_disconnection_notification()

            # Cancel connection task if exists
            if self._connection_task is not None:
                if not self._connection_task.done():
                    self._connection_task.cancel()
                    try:
                        await self._connection_task
                    except asyncio.CancelledError:
                        pass
                self._connection_task = None

            # Close the bot if not already closed
            if not self.is_closed():
                await self.close()

            self._connected = False
            logger.info("discord_bot_disconnected")

    # ========================================================================
    # Notification Methods
    # ========================================================================

    async def _send_connection_notification(self) -> None:
        """Send a notification to Discord when bot connects."""
        if self.event_channel_id is None:
            logger.debug("skip_connection_notification_no_channel")
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel is None or not isinstance(channel, discord.TextChannel):
                logger.warning("connection_notification_invalid_channel")
                return

            bot_name = self.user.name if self.user else "Factorio ISR Bot"
            guild_count = len(self.guilds)

            embed = EmbedBuilder.info_embed(
                title=f"🤖 {bot_name} Connected",
                message=(
                    f"✅ Bot connected with Discord\n"
                    f"📡 Connected to {guild_count} server{'s' if guild_count != 1 else ''}\n"
                    f"💬 Type `/factorio help` to see available commands"
                )
            )
            embed.color = EmbedBuilder.COLOR_SUCCESS

            await channel.send(embed=embed)
            logger.info("connection_notification_sent", channel_id=self.event_channel_id)
        except discord.errors.Forbidden:
            logger.warning("connection_notification_forbidden")
        except Exception as e:
            logger.warning("connection_notification_failed", error=str(e))

    async def _send_disconnection_notification(self) -> None:
        """Send a notification to Discord when bot disconnects."""
        if not self._connected:
            logger.debug("skip_disconnection_notification_not_connected")
            return

        if self.event_channel_id is None:
            logger.debug("skip_disconnection_notification_no_channel")
            return

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel is None or not isinstance(channel, discord.TextChannel):
                logger.warning("disconnection_notification_invalid_channel")
                return

            bot_name = self.user.name if self.user else "Factorio ISR Bot"

            embed = EmbedBuilder.info_embed(
                title=f"👋 {bot_name} Disconnecting",
                message=(
                    "⚠️ Bot lost connection with Discord\n"
                    "🔄 Monitoring will resume when bot reconnects"
                )
            )
            embed.color = EmbedBuilder.COLOR_WARNING

            await channel.send(embed=embed)
            logger.info("disconnection_notification_sent", channel_id=self.event_channel_id)
            await asyncio.sleep(0.5)
        except discord.errors.Forbidden:
            logger.warning("disconnection_notification_forbidden")
        except Exception as e:
            logger.warning("disconnection_notification_failed", error=str(e))

    # ========================================================================
    # Event Sending
    # ========================================================================

    async def send_event(self, event: FactorioEvent) -> bool:
        """
        Send a Factorio event to Discord.

        Args:
            event: Factorio event to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._connected:
            logger.warning("send_event_not_connected", event_type=event.event_type.value)
            return False

        if self.event_channel_id is None:
            logger.warning("send_event_no_channel_configured", event_type=event.event_type.value)
            return False

        try:
            channel = self.get_channel(self.event_channel_id)
            if channel is None:
                logger.error("send_event_channel_not_found", channel_id=self.event_channel_id)
                return False

            if not isinstance(channel, discord.TextChannel):
                logger.error("send_event_invalid_channel_type", channel_id=self.event_channel_id)
                return False

            message = FactorioEventFormatter.format_for_discord(event)

            await channel.send(message)
            logger.debug("event_sent", event_type=event.event_type.value)
            return True

        except discord.errors.Forbidden as e:
            logger.error("send_event_forbidden", error=str(e))
            return False
        except discord.errors.HTTPException as e:
            logger.error("send_event_http_error", error=str(e))
            return False
        except Exception as e:
            logger.error("send_event_unexpected_error", error=str(e), exc_info=True)
            return False

    # ========================================================================
    # Configuration Methods
    # ========================================================================

    def set_event_channel(self, channel_id: int) -> None:
        """Set the channel where Factorio events will be sent."""
        self.event_channel_id = channel_id
        logger.info("event_channel_set", channel_id=channel_id)

    def set_rcon_client(self, rcon_client: Any) -> None:
        """Set RCON client for server queries."""
        self.rcon_client = rcon_client
        logger.info("rcon_client_set_for_bot_commands")

    @property
    def is_connected(self) -> bool:
        """Check if bot is connected to Discord."""
        return self._connected


class DiscordBotFactory:
    """Factory for creating Discord bot instances."""

    @staticmethod
    def create_bot(token: str, bot_name: str = "Factorio ISR") -> DiscordBot:
        """Create a Discord bot instance."""
        return DiscordBot(token=token, bot_name=bot_name)
