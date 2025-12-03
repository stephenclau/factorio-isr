"""
Discord bot client for Factorio ISR Phase 4.
Provides interactive bot functionality with slash commands and event handling.
"""

import asyncio
from typing import Optional, Any

import discord
from discord import app_commands
import structlog

# Import event parser and formatter
try:
    from .event_parser import FactorioEvent, FactorioEventFormatter
except ImportError:
    from event_parser import FactorioEvent, FactorioEventFormatter  # type: ignore

logger = structlog.get_logger()


class DiscordBot(discord.Client):
    """Discord bot client with slash command support."""

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

        logger.info("discord_bot_initialized", bot_name=bot_name)

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
        
        @factorio_group.command(name="ping", description="Ping the Factorio server via RCON")
        async def ping_command(interaction: discord.Interaction) -> None:
            """
            Check connectivity to the Factorio server and RCON.
            """
            await interaction.response.defer()

            # If RCON is not configured
            if self.rcon_client is None:
                await interaction.followup.send(
                    "ℹ️ **Ping Result**\n\n"
                    "🤖 Bot is online\n"
                    "⚠️ RCON is not configured, cannot ping Factorio server."
                )
                return

            try:
                # Simple, low-impact RCON command
                # You can switch to something else if you prefer, e.g. /players online
                response = await self.rcon_client.execute("/time")

                msg = (
                    "✅ **Ping Successful**\n\n"
                    "🤖 Bot → RCON → Factorio server is reachable.\n"
                    f"🖥️ Command: `/time`\n"
                    f"📨 Response:\n{response}"
                )
                await interaction.followup.send(msg)
                logger.info("factorio_ping_success", user=interaction.user.name)

            except Exception as e:
                logger.error("factorio_ping_failed", error=str(e))
                await interaction.followup.send(
                    "❌ **Ping Failed**\n\n"
                    "Bot is online but could not reach the Factorio server via RCON.\n"
                    f"Error: {str(e)}"
                )
            
        @factorio_group.command(name="status", description="Show Factorio server status")
        async def status_command(interaction: discord.Interaction) -> None:
            await interaction.response.defer()
            try:
                msg = await self._get_server_status()
                await interaction.followup.send(msg)
            except Exception as e:
                logger.error("status_command_failed", error=str(e))
                await interaction.followup.send("❌ Failed to get server status")

        @factorio_group.command(name="players", description="List players currently online")
        async def players_command(interaction: discord.Interaction) -> None:
            await interaction.response.defer()
            try:
                msg = await self._get_players_list()
                await interaction.followup.send(msg)
            except Exception as e:
                logger.error("players_command_failed", error=str(e))
                await interaction.followup.send("❌ Failed to get player list")
        
        @factorio_group.command(name="ban", description="Ban a player from the server")
        @app_commands.describe(player="Player name to ban")
        async def ban_command(interaction: discord.Interaction, player: str) -> None:
            await interaction.response.defer()
            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot ban players.")
                return
            try:
                resp = await self.rcon_client.execute(f"/ban {player}")
                msg = (
                    f"🔨 **Player Banned**\n\n"
                    f"Player **{player}** has been banned.\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("player_banned", player=player, moderator=interaction.user.name)
            except Exception as e:
                logger.error("ban_command_failed", error=str(e), player=player)
                await interaction.followup.send(f"❌ Failed to ban player: {str(e)}")

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
            await interaction.response.defer()
            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot kick players.")
                return
            try:
                reason_part = f" {reason}" if reason else ""
                cmd = f"/kick {player}{reason_part}"
                resp = await self.rcon_client.execute(cmd)
                msg = (
                    f"👢 **Player Kicked**\n\n"
                    f"Player **{player}** has been kicked.\n"
                    f"Reason: {reason or 'None provided'}\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("player_kicked", player=player, reason=reason, moderator=interaction.user.name)
            except Exception as e:
                logger.error("kick_command_failed", error=str(e), player=player)
                await interaction.followup.send(f"❌ Failed to kick player: {str(e)}")

        @factorio_group.command(name="unban", description="Unban a player from the server")
        @app_commands.describe(player="Player name to unban")
        async def unban_command(interaction: discord.Interaction, player: str) -> None:
            await interaction.response.defer()
            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot unban players.")
                return
            try:
                resp = await self.rcon_client.execute(f"/unban {player}")
                msg = (
                    f"✅ **Player Unbanned**\n\n"
                    f"Player **{player}** has been unbanned.\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("player_unbanned", player=player, moderator=interaction.user.name)
            except Exception as e:
                logger.error("unban_command_failed", error=str(e), player=player)
                await interaction.followup.send(f"❌ Failed to unban player: {str(e)}")
                
        @factorio_group.command(name="save", description="Save the Factorio game")
        @app_commands.describe(name="Optional save name")
        async def save_command(interaction: discord.Interaction, name: str | None = None) -> None:
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
        # @factorio_group.command(name="save", description="Save the Factorio game")
        # @app_commands.describe(name="Optional save name")
        # async def save_command(interaction: discord.Interaction, name: str | None = None) -> None:
        #     await interaction.response.defer()
        #     if self.rcon_client is None:
        #         await interaction.followup.send("⚠️ RCON not available. Cannot save game.")
        #         return
        #     try:
        #         cmd = f"/save {name}" if name else "/save"
        #         resp = await self.rcon_client.execute(cmd)
        #         label = name or "(default)"
        #         msg = (
        #             f"💾 **Game Saved**\n\n"
        #             f"Save name: **{label}**\n\n"
        #             f"Server response:\n{resp}"
        #         )
        #         await interaction.followup.send(msg)
        #         logger.info("game_saved", name=name, moderator=interaction.user.name)
        #     except Exception as e:
        #         logger.error("save_command_failed", error=str(e), name=name)
        #         await interaction.followup.send(f"❌ Failed to save game: {str(e)}")

        @factorio_group.command(name="rcon", description="Run a raw RCON command")
        @app_commands.describe(command="Raw RCON command, e.g. /time or /ban Alice")
        async def rcon_command(interaction: discord.Interaction, command: str) -> None:
            await interaction.response.defer()
            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot run commands.")
                return
            try:
                resp = await self.rcon_client.execute(command)
                msg = (
                    f"🖥️ **RCON Executed**\n\n"
                    f"Command: `{command}`\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info(
                    "raw_rcon_executed",
                    command=command,
                    moderator=interaction.user.name,
                )
            except Exception as e:
                logger.error("rcon_command_failed", error=str(e), command=command)
                await interaction.followup.send(f"❌ Failed to run RCON: {str(e)}")

        # ========================================================================
        # PHASE 5: Additional Admin Commands
        # ========================================================================

        @factorio_group.command(name="broadcast", description="Send a message to all players")
        @app_commands.describe(message="Message to broadcast to all players")
        async def broadcast_command(interaction: discord.Interaction, message: str) -> None:
            """Broadcast a message to all players on the server."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot broadcast messages.")
                return

            try:
                # Factorio RCON command format: /c game.print("message")
                # or simply send the message directly
                escaped_msg = message.replace('"', '\\"')
                resp = await self.rcon_client.execute(f'/c game.print("{escaped_msg}")')

                msg = (
                    f"📢 **Broadcast Sent**\n\n"
                    f"Message: _{message}_\n\n"
                    f"All online players have been notified.\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("message_broadcast", message=message, moderator=interaction.user.name)
            except Exception as e:
                logger.error("broadcast_command_failed", error=str(e), message=message)
                await interaction.followup.send(f"❌ Failed to broadcast message: {str(e)}")

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
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot manage whitelist.")
                return

            action = action.lower()

            try:
                if action == "list":
                    resp = await self.rcon_client.execute("/whitelist get")
                    msg = f"📋 **Whitelist**\n\n{resp}"
                elif action == "enable":
                    resp = await self.rcon_client.execute("/whitelist enable")
                    msg = f"✅ **Whitelist Enabled**\n\n{resp}"
                elif action == "disable":
                    resp = await self.rcon_client.execute("/whitelist disable")
                    msg = f"⚠️ **Whitelist Disabled**\n\n{resp}"
                elif action == "add":
                    if not player:
                        await interaction.followup.send("❌ Player name required for 'add' action")
                        return
                    resp = await self.rcon_client.execute(f"/whitelist add {player}")
                    msg = f"✅ **Player Added to Whitelist**\n\nPlayer: **{player}**\n\n{resp}"
                    logger.info("whitelist_add", player=player, moderator=interaction.user.name)
                elif action == "remove":
                    if not player:
                        await interaction.followup.send("❌ Player name required for 'remove' action")
                        return
                    resp = await self.rcon_client.execute(f"/whitelist remove {player}")
                    msg = f"🚫 **Player Removed from Whitelist**\n\nPlayer: **{player}**\n\n{resp}"
                    logger.info("whitelist_remove", player=player, moderator=interaction.user.name)
                else:
                    await interaction.followup.send(
                        f"❌ Invalid action: {action}\n"
                        "Valid actions: add, remove, list, enable, disable"
                    )
                    return

                await interaction.followup.send(msg)
            except Exception as e:
                logger.error("whitelist_command_failed", error=str(e), action=action, player=player)
                await interaction.followup.send(f"❌ Whitelist command failed: {str(e)}")

        @factorio_group.command(name="promote", description="Promote a player to admin")
        @app_commands.describe(player="Player name to promote")
        async def promote_command(interaction: discord.Interaction, player: str) -> None:
            """Promote a player to admin status."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot promote players.")
                return

            try:
                resp = await self.rcon_client.execute(f"/promote {player}")
                msg = (
                    f"⬆️ **Player Promoted**\n\n"
                    f"Player **{player}** is now an admin.\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("player_promoted", player=player, moderator=interaction.user.name)
            except Exception as e:
                logger.error("promote_command_failed", error=str(e), player=player)
                await interaction.followup.send(f"❌ Failed to promote player: {str(e)}")

        @factorio_group.command(name="demote", description="Demote a player from admin")
        @app_commands.describe(player="Player name to demote")
        async def demote_command(interaction: discord.Interaction, player: str) -> None:
            """Demote a player from admin status."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot demote players.")
                return

            try:
                resp = await self.rcon_client.execute(f"/demote {player}")
                msg = (
                    f"⬇️ **Player Demoted**\n\n"
                    f"Player **{player}** is no longer an admin.\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("player_demoted", player=player, moderator=interaction.user.name)
            except Exception as e:
                logger.error("demote_command_failed", error=str(e), player=player)
                await interaction.followup.send(f"❌ Failed to demote player: {str(e)}")

        @factorio_group.command(name="mute", description="Mute a player (prevent chat)")
        @app_commands.describe(player="Player name to mute")
        async def mute_command(interaction: discord.Interaction, player: str) -> None:
            """Mute a player to prevent them from chatting."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot mute players.")
                return

            try:
                resp = await self.rcon_client.execute(f"/mute {player}")
                msg = (
                    f"🔇 **Player Muted**\n\n"
                    f"Player **{player}** has been muted.\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("player_muted", player=player, moderator=interaction.user.name)
            except Exception as e:
                logger.error("mute_command_failed", error=str(e), player=player)
                await interaction.followup.send(f"❌ Failed to mute player: {str(e)}")

        @factorio_group.command(name="unmute", description="Unmute a player")
        @app_commands.describe(player="Player name to unmute")
        async def unmute_command(interaction: discord.Interaction, player: str) -> None:
            """Unmute a player to allow them to chat again."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot unmute players.")
                return

            try:
                resp = await self.rcon_client.execute(f"/unmute {player}")
                msg = (
                    f"🔊 **Player Unmuted**\n\n"
                    f"Player **{player}** can chat again.\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("player_unmuted", player=player, moderator=interaction.user.name)
            except Exception as e:
                logger.error("unmute_command_failed", error=str(e), player=player)
                await interaction.followup.send(f"❌ Failed to unmute player: {str(e)}")

        @factorio_group.command(name="seed", description="Show the map seed")
        async def seed_command(interaction: discord.Interaction) -> None:
            """Display the current map seed."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot get map seed.")
                return

            try:
                # Use Lua to get the seed
                resp = await self.rcon_client.execute('/c rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)')
                msg = (
                    f"🌱 **Map Seed**\n\n"
                    f"Seed: `{resp.strip()}`\n\n"
                    f"Use this seed to generate an identical map."
                )
                await interaction.followup.send(msg)
                logger.info("seed_requested", moderator=interaction.user.name)
            except Exception as e:
                logger.error("seed_command_failed", error=str(e))
                await interaction.followup.send(f"❌ Failed to get map seed: {str(e)}")

        @factorio_group.command(name="version", description="Show Factorio server version")
        async def version_command(interaction: discord.Interaction) -> None:
            """Display the Factorio server version."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot get version.")
                return

            try:
                resp = await self.rcon_client.execute("/version")
                msg = f"🎮 **Factorio Version**\n\n{resp}"
                await interaction.followup.send(msg)
                logger.info("version_requested", moderator=interaction.user.name)
            except Exception as e:
                logger.error("version_command_failed", error=str(e))
                await interaction.followup.send(f"❌ Failed to get version: {str(e)}")

        @factorio_group.command(name="evolution", description="Show evolution factor")
        async def evolution_command(interaction: discord.Interaction) -> None:
            """Display the current evolution factor."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot get evolution.")
                return

            try:
                resp = await self.rcon_client.execute('/c rcon.print(string.format("%.2f%%", game.forces["enemy"].evolution_factor * 100))')
                msg = (
                    f"🐛 **Evolution Factor**\n\n"
                    f"Current evolution: **{resp.strip()}**\n\n"
                    f"Higher evolution means stronger biters!"
                )
                await interaction.followup.send(msg)
                logger.info("evolution_requested", moderator=interaction.user.name)
            except Exception as e:
                logger.error("evolution_command_failed", error=str(e))
                await interaction.followup.send(f"❌ Failed to get evolution: {str(e)}")

        @factorio_group.command(name="time", description="Set or display game time")
        @app_commands.describe(value="Time value (e.g., 0.5 for noon, 0 for midnight) or leave empty to view")
        async def time_command(interaction: discord.Interaction, value: float | None = None) -> None:
            """Set or display the game time."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot manage time.")
                return

            try:
                if value is None:
                    # Display current time
                    resp = await self.rcon_client.execute("/time")
                    msg = f"🕐 **Current Game Time**\n\n{resp}"
                else:
                    # Set time
                    resp = await self.rcon_client.execute(f'/c game.surfaces["nauvis"].daytime = {value}')
                    time_desc = "noon" if abs(value - 0.5) < 0.1 else "midnight" if value < 0.1 else f"{value}"
                    msg = (
                        f"🕐 **Time Changed**\n\n"
                        f"Game time set to: **{time_desc}**\n\n"
                        f"Server response:\n{resp}"
                    )
                    logger.info("time_changed", value=value, moderator=interaction.user.name)

                await interaction.followup.send(msg)
            except Exception as e:
                logger.error("time_command_failed", error=str(e), value=value)
                await interaction.followup.send(f"❌ Failed to manage time: {str(e)}")

        @factorio_group.command(name="speed", description="Set game speed (admin only)")
        @app_commands.describe(speed="Game speed multiplier (0.1 to 10.0, default 1.0)")
        async def speed_command(interaction: discord.Interaction, speed: float) -> None:
            """Set the game speed multiplier."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot change speed.")
                return

            # Validate speed range
            if speed < 0.1 or speed > 10.0:
                await interaction.followup.send("❌ Speed must be between 0.1 and 10.0")
                return

            try:
                resp = await self.rcon_client.execute(f"/c game.speed = {speed}")
                msg = (
                    f"⚡ **Game Speed Changed**\n\n"
                    f"Speed multiplier: **{speed}x**\n\n"
                    f"Server response:\n{resp}\n\n"
                    f"⚠️ This affects all players!"
                )
                await interaction.followup.send(msg)
                logger.info("speed_changed", speed=speed, moderator=interaction.user.name)
            except Exception as e:
                logger.error("speed_command_failed", error=str(e), speed=speed)
                await interaction.followup.send(f"❌ Failed to change speed: {str(e)}")

        @factorio_group.command(name="research", description="Force research a technology")
        @app_commands.describe(technology="Technology name to research")
        async def research_command(interaction: discord.Interaction, technology: str) -> None:
            """Force research a technology."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot force research.")
                return

            try:
                # Factorio Lua command to force research
                cmd = f'/c game.forces["player"].technologies["{technology}"].researched = true'
                resp = await self.rcon_client.execute(cmd)
                msg = (
                    f"🔬 **Technology Researched**\n\n"
                    f"Technology: **{technology}**\n\n"
                    f"The technology has been forcefully researched.\n\n"
                    f"Server response:\n{resp}"
                )
                await interaction.followup.send(msg)
                logger.info("tech_researched", technology=technology, moderator=interaction.user.name)
            except Exception as e:
                logger.error("research_command_failed", error=str(e), technology=technology)
                await interaction.followup.send(
                    f"❌ Failed to research technology: {str(e)}\n\n"
                    f"Make sure the technology name is correct (e.g., 'automation', 'logistics')"
                )

        @factorio_group.command(name="admins", description="List server admins")
        async def admins_command(interaction: discord.Interaction) -> None:
            """List all server administrators."""
            await interaction.response.defer()

            if self.rcon_client is None:
                await interaction.followup.send("⚠️ RCON not available. Cannot list admins.")
                return

            try:
                resp = await self.rcon_client.execute("/admins")
                msg = f"👑 **Server Administrators**\n\n{resp}"
                await interaction.followup.send(msg)
                logger.info("admins_listed", moderator=interaction.user.name)
            except Exception as e:
                logger.error("admins_command_failed", error=str(e))
                await interaction.followup.send(f"❌ Failed to list admins: {str(e)}")


        # UPDATED HELP COMMAND
        # Replace your existing help_command with this:


        @factorio_group.command(name="help", description="Show available Factorio commands")
        async def help_command(interaction: discord.Interaction) -> None:
            help_text = (
                "**🏭 Factorio ISR Bot – Commands**\n\n"
                "**📊 Server Information**\n"
                "`/factorio status` – Show server status and uptime\n"
                "`/factorio players` – List players currently online\n"
                "`/factorio ping` – Ping the Factorio server via RCON\n"
                "`/factorio version` – Show Factorio server version\n"
                "`/factorio seed` – Show map seed\n"
                "`/factorio evolution` – Show biter evolution factor\n"
                "`/factorio admins` – List server administrators\n\n"
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
                "  └ Actions: add, remove, list, enable, disable\n\n"
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

        
        # Register the group as the single root command
        self.tree.add_command(factorio_group)
        logger.info(
            "slash_commands_registered",
            root=factorio_group.name,
            subcommands=[cmd.name for cmd in factorio_group.commands],
        )

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
        )

        # Log channel permissions
        if self.event_channel_id:
            channel = self.get_channel(self.event_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                perms = channel.permissions_for(channel.guild.me)
                logger.info(
                    "bot_channel_permissions",
                    channel_id=self.event_channel_id,
                    channel_name=channel.name,
                    send_messages=perms.send_messages,
                    read_messages=perms.read_messages,
                    embed_links=perms.embed_links,
                )
            elif channel:
                logger.warning(
                    "event_channel_not_text_channel",
                    channel_id=self.event_channel_id,
                    channel_type=type(channel).__name__,
                )

        # Set connected flag and signal ready
        self._connected = True
        self._ready.set()

        try:
            # 1) Global sync
            synced_global = await self.tree.sync()
            logger.info(
                "commands_synced_globally",
                count=len(synced_global),
                commands=[cmd.name for cmd in synced_global],
            )

            # 2) Copy globals to each guild and sync
            for guild in self.guilds:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)

                # Inspect the tree directly for this guild
                top_level = self.tree.get_commands(guild=guild)
                top_level_count = len(top_level)

                command_summaries = []
                leaf_subcommand_count = 0

                for cmd in top_level:
                    if isinstance(cmd, app_commands.Group):
                        sub_names = [sub.name for sub in cmd.commands]
                        leaf_subcommand_count += len(sub_names)
                        command_summaries.append(
                            {
                                "name": cmd.name,
                                "type": "group",
                                "subcommands": sub_names,
                            }
                        )
                    else:
                        leaf_subcommand_count += 1
                        command_summaries.append(
                            {
                                "name": cmd.name,
                                "type": "command",
                                "subcommands": [],
                            }
                        )

                logger.info(
                    "commands_synced_to_guild",
                    guild_name=guild.name,
                    guild_id=guild.id,
                    top_level_count=top_level_count,
                    leaf_subcommand_count=leaf_subcommand_count,
                    commands=command_summaries,
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

    async def connect_bot(self) -> None:
        """Connect the bot to Discord."""
        try:
            logger.info("connecting_to_discord")

            # Login first (authenticate)
            await self.login(self.token)

            # Then connect in background
            self._connection_task = asyncio.create_task(self.connect())

            # Wait for ready event (with timeout)
            await asyncio.wait_for(self._ready.wait(), timeout=30.0)
            logger.info("discord_bot_connected")

            # Now that bot is ready and _connected=True, send notification
            await self._send_connection_notification()

        except asyncio.TimeoutError:
            logger.error("discord_bot_connection_timeout")
            # Cancel the connection task if it exists
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
        """Disconnect the bot from Discord."""
        if self._connected or self._connection_task is not None:
            logger.info("disconnecting_from_discord")

            # Send disconnection notification to Discord before closing
            await self._send_disconnection_notification()

            # Cancel connection task if still running
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

            message = (
                f"🤖 **{bot_name} Connected**\n\n"
                f"✅ Bot is now online and monitoring Factorio server\n"
                f"📡 Connected to {guild_count} server{'s' if guild_count != 1 else ''}\n"
                f"💬 Type `/factorio help` to see available commands"
            )

            await channel.send(message)
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

            message = (
                f"👋 **{bot_name} Disconnecting**\n\n"
                f"⚠️ Bot is going offline\n"
                f"🔄 Monitoring will resume when bot reconnects"
            )

            await channel.send(message)
            logger.info("disconnection_notification_sent", channel_id=self.event_channel_id)

            await asyncio.sleep(0.5)

        except discord.errors.Forbidden:
            logger.warning("disconnection_notification_forbidden")
        except Exception as e:
            logger.warning("disconnection_notification_failed", error=str(e))

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

            logger.debug(
                "attempting_send_event",
                event_type=event.event_type.value,
                channel_id=self.event_channel_id,
                message_preview=message[:50] if len(message) > 50 else message,
            )

            await channel.send(message)
            logger.debug(
                "event_sent",
                event_type=event.event_type.value,
                channel_id=self.event_channel_id,
            )
            return True

        except discord.errors.Forbidden as e:
            logger.error(
                "send_event_forbidden",
                channel_id=self.event_channel_id,
                error=str(e),
            )
            return False
        except discord.errors.HTTPException as e:
            logger.error("send_event_http_error", error=str(e), channel_id=self.event_channel_id)
            return False
        except Exception as e:
            logger.error("send_event_unexpected_error", error=str(e), exc_info=True)
            return False

    def set_event_channel(self, channel_id: int) -> None:
        """Set the channel where Factorio events will be sent."""
        self.event_channel_id = channel_id
        logger.info("event_channel_set", channel_id=channel_id)

    def set_rcon_client(self, rcon_client: Any) -> None:
        """Set RCON client for server queries."""
        self.rcon_client = rcon_client
        logger.info("rcon_client_set_for_bot_commands")

    async def _get_server_status(self) -> str:
        """
        Get server status information.

        Returns:
            Formatted status message
        """
        if self.rcon_client is None:
            return "ℹ️ **Server Status**\n\n🤖 Bot is connected\n⚠️ RCON not available (status limited)"

        try:
            response = await self.rcon_client.execute("/players online")

            players_online = 0
            if "Online players" in response:
                import re
                match = re.search(r"Online players \((\d+)\)", response)
                if match:
                    players_online = int(match.group(1))

            status_msg = (
                f"ℹ️ **Server Status**\n\n"
                f"🟢 Server is running\n"
                f"👥 Players online: **{players_online}**\n"
                f"🤖 Bot connected: **Yes**\n"
                f"🔧 RCON: **Enabled**"
            )
            return status_msg
        except Exception as e:
            logger.error("get_server_status_failed", error=str(e))
            return f"⚠️ **Server Status**\n\nFailed to query server: {str(e)}"

    async def _get_players_list(self) -> str:
        """
        Get list of online players.

        Returns:
            Formatted players list message
        """
        if self.rcon_client is None:
            return "⚠️ RCON not available. Cannot fetch player list."

        try:
            response = await self.rcon_client.execute("/players online")

            if "Online players (0)" in response:
                return "👥 **Players Online**\n\nNo players currently online"

            import re
            match = re.search(r"Online players \((\d+)\): (.+)", response)
            if match:
                count = match.group(1)
                players = match.group(2).split(", ")
                players_list = "\n".join(f"• {player}" for player in players)
                return f"👥 **Players Online ({count})**\n\n{players_list}"

            return f"👥 **Players Online**\n\n{response}"
        except Exception as e:
            logger.error("get_players_list_failed", error=str(e))
            return f"⚠️ Failed to get player list: {str(e)}"

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
