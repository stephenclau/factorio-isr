# Copyright (c) 2025 Stephen Clau
#
# Factorio ISR - Dual Licensed (AGPL-3.0 OR Commercial)
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""Remaining Command Handlers (Batch 4).

Handlers for remaining query and info operations:
- PlayersCommandHandler: List online players
- VersionCommandHandler: Get Factorio server version
- SeedCommandHandler: Get map seed
- AdminsCommandHandler: List server admins
- HealthCommandHandler: Check system health
- RconCommandHandler: Execute raw RCON
- HelpCommandHandler: Show help
- ServersCommandHandler: List multi-server info (info-only, no changes)
- ConnectCommandHandler: Switch user server context (info-only in handler)

Note: These handlers are primarily informational with minimal state changes.
"""

from typing import Optional, Protocol, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import discord
import re
import structlog

logger = structlog.get_logger()


class UserContextProvider(Protocol):
    def get_user_server(self, user_id: int) -> str: ...
    def get_server_display_name(self, user_id: int) -> str: ...
    def get_rcon_for_user(self, user_id: int) -> Optional["RconClient"]: ...
    def set_user_server(self, user_id: int, server: str) -> None: ...


class RconClient(Protocol):
    @property
    def is_connected(self) -> bool: ...
    async def execute(self, command: str) -> str: ...


class RateLimiter(Protocol):
    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[int]]: ...


class EmbedBuilderType(Protocol):
    @staticmethod
    def error_embed(message: str) -> discord.Embed: ...
    @staticmethod
    def cooldown_embed(retry_seconds: int) -> discord.Embed: ...
    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed: ...
    COLOR_WARNING: int
    COLOR_SUCCESS: int
    COLOR_INFO: int


class ServerManagerType(Protocol):
    """Protocol for server manager (multi-server support)."""
    def list_servers(self) -> Dict[str, Any]: ...
    def get_config(self, server: str) -> Any: ...
    def get_status_summary(self) -> Dict[str, bool]: ...


class RconMonitorType(Protocol):
    """Protocol for RCON monitor (uptime tracking)."""
    rcon_server_states: Dict[str, Dict[str, Any]]


class BotType(Protocol):
    """Protocol for bot instance."""
    _connected: bool
    user_context: UserContextProvider
    server_manager: Optional[ServerManagerType]
    rcon_monitor: Optional[RconMonitorType]


@dataclass
class CommandResult:
    success: bool
    embed: Optional[discord.Embed] = None
    error_embed: Optional[discord.Embed] = None
    ephemeral: bool = False


# ============================================================================
# Players Command Handler
# ============================================================================

class PlayersCommandHandler:
    """List online players."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute players command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            response = await rcon_client.execute("/players")
            players = []
            if response:
                for line in response.split("\n"):
                    line = line.strip()
                    if "(online)" in line.lower():
                        player_name = line.split("(online)")[0].strip()
                        player_name = player_name.lstrip("-").strip()
                        if player_name and not player_name.startswith("Player"):
                            players.append(player_name)

            embed = discord.Embed(
                title=f"👥 Players on {server_name}",
                color=self.embed_builder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )

            if not players:
                embed.description = "No players currently online."
            else:
                player_list = "\n".join(f"• {name}" for name in sorted(players))
                embed.add_field(
                    name=f"Online Players ({len(players)})",
                    value=player_list,
                    inline=False,
                )

            embed.set_footer(text="Factorio ISR")
            logger.info("players_command_executed", player_count=len(players))
            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("players_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to get players: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Version Command Handler
# ============================================================================

class VersionCommandHandler:
    """Get Factorio server version."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute version command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            response = await rcon_client.execute("/version")
            version = response.strip() if response else "Unknown"

            embed = discord.Embed(
                title=f"📦 {server_name} Version",
                description=f"`{version}`",
                color=self.embed_builder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Factorio ISR")
            logger.info("version_command_executed", version=version)
            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("version_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to get version: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Seed Command Handler
# ============================================================================

class SeedCommandHandler:
    """Get map seed."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute seed command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            response = await rcon_client.execute(
                '/sc rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)'
            )

            seed = "Unknown"
            if response and response.strip():
                try:
                    int(response.strip())
                    seed = response.strip()
                except ValueError:
                    logger.warning("seed_parse_failed", response=response)

            embed = discord.Embed(
                title=f"🌍 {server_name} Map Seed",
                description=f"```\n{seed}\n```",
                color=self.embed_builder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Use this seed to generate the same map")
            logger.info("seed_command_executed")
            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("seed_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to get seed: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Admins Command Handler
# ============================================================================

class AdminsCommandHandler:
    """List server admins."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute admins command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            response = await rcon_client.execute("/admins")
            admins = []
            if response:
                for line in response.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("There are") and not line.startswith("Admins"):
                        admin_name = line.lstrip("- ").strip()
                        if admin_name:
                            admins.append(admin_name)

            embed = discord.Embed(
                title=f"👑 {server_name} Administrators",
                color=self.embed_builder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )

            if not admins:
                embed.description = "No administrators configured."
            else:
                admin_list = "\n".join(f"• {name}" for name in sorted(admins))
                embed.add_field(
                    name=f"Admins ({len(admins)})",
                    value=admin_list,
                    inline=False,
                )

            embed.set_footer(text="Factorio ISR")
            logger.info(
                "admins_command_executed",
                admin_count=len(admins),
                moderator=interaction.user.name,
            )
            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("admins_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to get admins: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Health Command Handler
# ============================================================================

class HealthCommandHandler:
    """Check system health."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
        bot: BotType,
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type
        self.bot = bot

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute health command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)

        try:
            embed = discord.Embed(
                title=f"💚 {server_name} Health Check",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )

            # Bot status
            bot_status = "🟢 Healthy" if self.bot._connected else "🔴 Disconnected"
            embed.add_field(name="Bot Status", value=bot_status, inline=True)

            # RCON status
            rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)
            rcon_status = (
                "🟢 Connected" if rcon_client and rcon_client.is_connected
                else "🔴 Disconnected"
            )
            embed.add_field(name="RCON Status", value=rcon_status, inline=True)

            # Monitor status
            monitor_status = "🟢 Running" if self.bot.rcon_monitor else "🔴 Not available"
            embed.add_field(name="Monitor Status", value=monitor_status, inline=True)

            # Uptime
            if self.bot.rcon_monitor and self.bot.rcon_monitor.rcon_server_states:
                state = self.bot.rcon_monitor.rcon_server_states.get(
                    self.user_context.get_user_server(interaction.user.id)
                )
                if state and state.get("last_connected"):
                    uptime_delta = datetime.now(timezone.utc) - state["last_connected"]
                    days = int(uptime_delta.total_seconds()) // 86400
                    hours = (int(uptime_delta.total_seconds()) % 86400) // 3600
                    minutes = (int(uptime_delta.total_seconds()) % 3600) // 60
                    parts = []
                    if days > 0:
                        parts.append(f"{days}d")
                    if hours > 0:
                        parts.append(f"{hours}h")
                    if minutes > 0:
                        parts.append(f"{minutes}m")
                    uptime = " ".join(parts) if parts else "< 1m"
                    embed.add_field(name="Uptime", value=uptime, inline=True)

            embed.set_footer(text="Factorio ISR Health Check")
            logger.info("health_command_executed")
            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("health_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Health check failed: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# RCON Command Handler
# ============================================================================

class RconCommandHandler:
    """Execute raw RCON command."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilderType],
    ):
        self.user_context = user_context_provider
        self.rate_limiter = rate_limiter
        self.embed_builder = embed_builder_type

    async def execute(
        self,
        interaction: discord.Interaction,
        command: str,
    ) -> CommandResult:
        """Execute raw RCON command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(retry),
                ephemeral=True,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )

        try:
            result = await rcon_client.execute(command)

            embed = discord.Embed(
                title="⌨️ RCON Command Executed",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Command", value=f"```\n{command}\n```", inline=False)
            if result:
                result_text = result if len(result) < 1024 else result[:1021] + "..."
                embed.add_field(
                    name="Response", value=f"```\n{result_text}\n```", inline=False
                )
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Dangerous operation - use with caution")

            logger.warning(
                "raw_rcon_executed",
                command=command[:50],
                user=interaction.user.name,
            )
            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("rcon_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON command failed: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Help Command Handler
# ============================================================================

class HelpCommandHandler:
    """Show help message."""

    def __init__(self, embed_builder_type: type[EmbedBuilderType]):
        self.embed_builder = embed_builder_type

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute help command."""
        help_text = (
            "**🏭 Factorio ISR Bot – Commands**\n\n"
            "**🌍 Multi-Server**\n"
            "`/factorio servers` – List available servers\n"
            "`/factorio connect <server>` – Switch to a server\n\n"
            "**📊 Server Information**\n"
            "`/factorio status` – Show server status and uptime\n"
            "`/factorio players` – List players currently online\n"
            "`/factorio version` – Show Factorio server version\n"
            "`/factorio seed` – Show map seed\n"
            "`/factorio evolution [target]` – Show enemy evolution\n"
            "`/factorio admins` – List server administrators\n"
            "`/factorio health` – Check bot and server health\n\n"
            "**👥 Player Management**\n"
            "`/factorio kick <player> [reason]` – Kick a player\n"
            "`/factorio ban <player> [reason]` – Ban a player\n"
            "`/factorio unban <player>` – Unban a player\n"
            "`/factorio mute <player>` – Mute a player from chat\n"
            "`/factorio unmute <player>` – Unmute a player\n"
            "`/factorio promote <player>` – Promote player to admin\n"
            "`/factorio demote <player>` – Demote player from admin\n\n"
            "**🔧 Server Management**\n"
            "`/factorio broadcast <message>` – Send message to all players\n"
            "`/factorio whisper <player> <message>` – Send private message\n"
            "`/factorio save [name]` – Save the game\n"
            "`/factorio whitelist <action> [player]` – Manage whitelist\n\n"
            "**🎮 Game Control**\n"
            "`/factorio clock [value]` – Show/set game time\n"
            "`/factorio speed <value>` – Set game speed (0.1-10.0)\n"
            "`/factorio research <technology>` – Force research tech\n\n"
            "**🛠️ Advanced**\n"
            "`/factorio rcon <command>` – Run raw RCON command\n"
            "`/factorio help` – Show this help message\n\n"
            "_Most commands require RCON to be enabled._"
        )

        logger.info("help_command_executed")
        return CommandResult(success=True, embed=None, ephemeral=False)


# ============================================================================
# Servers Command Handler (Multi-server info)
# ============================================================================

class ServersCommandHandler:
    """List multi-server information."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        embed_builder_type: type[EmbedBuilderType],
        server_manager: Optional[ServerManagerType],
    ):
        self.user_context = user_context_provider
        self.embed_builder = embed_builder_type
        self.server_manager = server_manager

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute servers command."""
        if not self.server_manager:
            embed = self.embed_builder.info_embed(
                title="📱 Server Information",
                message=(
                    "Single-server mode active.\n\n"
                    "To enable multi-server support, configure a `servers.yml` file "
                    "or set the `SERVERS` environment variable."
                ),
            )
            return CommandResult(success=True, embed=embed, ephemeral=True)

        try:
            current_tag = self.user_context.get_user_server(interaction.user.id)
            status_summary = self.server_manager.get_status_summary()

            embed = discord.Embed(
                title="📱 Available Factorio Servers",
                color=self.embed_builder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )

            if not self.server_manager.list_servers():
                embed.description = "No servers configured."
            else:
                embed.description = f"**Your Context:** `{current_tag}`\n\n"

            for tag, config in self.server_manager.list_servers().items():
                is_connected = status_summary.get(tag, False)
                status_icon = "🟢" if is_connected else "🔴"
                context_icon = "👉 " if tag == current_tag else " "

                field_lines = [
                    f"{status_icon} {'Online' if is_connected else 'Offline'}",
                    f"Host: `{config.rcon_host}:{config.rcon_port}`",
                ]

                if config.description:
                    field_lines.insert(0, f"*{config.description}*")

                embed.add_field(
                    name=f"{context_icon}**{config.name}** (`{tag}`)",
                    value="\n".join(field_lines),
                    inline=False,
                )

            embed.set_footer(text="Use /factorio connect to switch servers")
            logger.info(
                "servers_listed",
                user=interaction.user.name,
                server_count=len(self.server_manager.list_servers()),
            )
            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("servers_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to list servers: {str(e)}"
                ),
                ephemeral=True,
            )


# ============================================================================
# Connect Command Handler (Multi-server context switch)
# ============================================================================

class ConnectCommandHandler:
    """Switch user to a different server."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        embed_builder_type: type[EmbedBuilderType],
        server_manager: Optional[ServerManagerType],
    ):
        self.user_context = user_context_provider
        self.embed_builder = embed_builder_type
        self.server_manager = server_manager

    async def execute(
        self,
        interaction: discord.Interaction,
        server: str,
    ) -> CommandResult:
        """Execute connect command."""
        if not self.server_manager:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    "Multi-server mode not enabled.\n\n"
                    "This bot is running in single-server mode."
                ),
                ephemeral=True,
            )

        try:
            server = server.lower().strip()

            if server not in self.server_manager.clients:
                available_list = []
                for tag, config in self.server_manager.list_servers().items():
                    available_list.append(f"`{tag}` ({config.name})")
                available = ", ".join(available_list) if available_list else "none"
                return CommandResult(
                    success=False,
                    error_embed=self.embed_builder.error_embed(
                        f"❌ Server `{server}` not found.\n\n"
                        f"**Available servers:** {available}\n\n"
                        f"Use `/factorio servers` to see all servers."
                    ),
                    ephemeral=True,
                )

            self.user_context.set_user_server(interaction.user.id, server)

            config = self.server_manager.get_config(server)
            client = self.server_manager.get_client(server)
            is_connected = client.is_connected

            embed = discord.Embed(
                title=f"✅ Connected to {config.name}",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )

            status_icon = "🟢" if is_connected else "🟡"
            status_text = "Connected" if is_connected else "Connecting..."

            embed.add_field(name="Tag", value=f"`{server}`", inline=True)
            embed.add_field(name="Status", value=f"{status_icon} {status_text}", inline=True)
            embed.add_field(
                name="Host",
                value=f"`{config.rcon_host}:{config.rcon_port}`",
                inline=True,
            )

            if config.description:
                embed.add_field(
                    name="Description",
                    value=config.description,
                    inline=False,
                )

            embed.description = "All commands will now target this server."
            embed.set_footer(text="Use /factorio servers to see all servers")

            logger.info(
                "user_connected_to_server",
                user=interaction.user.name,
                user_id=interaction.user.id,
                server_tag=server,
                server_name=config.name,
            )
            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("connect_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to connect: {str(e)}"
                ),
                ephemeral=True,
            )
