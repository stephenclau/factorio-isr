"""Factorio slash command group registration.

All /factorio subcommands are defined in this single file to respect Discord's
25 subcommand-per-group limit. Currently using 25/25 slots.

Command Breakdown:
- Multi-Server Commands: 2/25 (servers, connect)
- Server Information: 7/25 (status, players, version, seed, evolution, admins, health)
- Player Management: 7/25 (kick, ban, unban, mute, unmute, promote, demote)
- Server Management: 4/25 (save, broadcast, whisper, whitelist)
- Game Control: 3/25 (clock, speed, research)
- Advanced: 2/25 (rcon, help)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: 25/25

"""

from typing import Any, List, Optional, Protocol, runtime_checkable
from datetime import datetime, timezone
import asyncio
import discord
from discord import app_commands
import re
import structlog

try:
    # Try flat layout first (when run from src/ directory)
    from utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN
    from discord_interface import EmbedBuilder
except ImportError:
    try:
        # Fallback to package style (when installed as package)
        from src.utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN  # type: ignore
        from src.discord_interface import EmbedBuilder  # type: ignore
    except ImportError:
        # Last resort: use relative imports from parent
        try:
            from ..utils.rate_limiting import QUERY_COOLDOWN, ADMIN_COOLDOWN, DANGER_COOLDOWN  # type: ignore
            from ..discord_interface import EmbedBuilder  # type: ignore
        except ImportError:
            raise ImportError(
                "Could not import rate_limiting or discord_interface from any path"
            )

# ════════════════════════════════════════════════════════════════════════════
# TYPE PROTOCOL: FactorioBot (for type safety)
# ════════════════════════════════════════════════════════════════════════════

@runtime_checkable
class FactorioBot(Protocol):
    """Protocol defining expected bot attributes for Factorio commands."""
    user_context: Any
    server_manager: Any
    tree: app_commands.CommandTree
    
    def get_rcon_for_user(self, user_id: int) -> Any:
        """Get RCON client for a user."""
        ...
    
    def get_server_display_name(self, user_id: int) -> str:
        """Get server display name for a user."""
        ...


# ════════════════════════════════════════════════════════════════════════════
# 🎯 UNIFIED HANDLER IMPORTS
# ════════════════════════════════════════════════════════════════════════════

try:
    from bot.commands.command_handlers import (
        # Server Information
        StatusCommandHandler,
        PlayersCommandHandler,
        VersionCommandHandler,
        SeedCommandHandler,
        EvolutionCommandHandler,
        AdminsCommandHandler,
        HealthCommandHandler,
        # Player Management
        KickCommandHandler,
        BanCommandHandler,
        UnbanCommandHandler,
        MuteCommandHandler,
        UnmuteCommandHandler,
        PromoteCommandHandler,
        DemoteCommandHandler,
        # Server Management
        SaveCommandHandler,
        BroadcastCommandHandler,
        WhisperCommandHandler,
        WhitelistCommandHandler,
        # Game Control
        ClockCommandHandler,
        SpeedCommandHandler,
        ResearchCommandHandler,
        # Advanced
        RconCommandHandler,
        HelpCommandHandler,
        # Multi-Server
        ServersCommandHandler,
        ConnectCommandHandler,
    )
except ImportError:
    try:
        from src.bot.commands.command_handlers import (  # type: ignore
            # Server Information
            StatusCommandHandler,
            PlayersCommandHandler,
            VersionCommandHandler,
            SeedCommandHandler,
            EvolutionCommandHandler,
            AdminsCommandHandler,
            HealthCommandHandler,
            # Player Management
            KickCommandHandler,
            BanCommandHandler,
            UnbanCommandHandler,
            MuteCommandHandler,
            UnmuteCommandHandler,
            PromoteCommandHandler,
            DemoteCommandHandler,
            # Server Management
            SaveCommandHandler,
            BroadcastCommandHandler,
            WhisperCommandHandler,
            WhitelistCommandHandler,
            # Game Control
            ClockCommandHandler,
            SpeedCommandHandler,
            ResearchCommandHandler,
            # Advanced
            RconCommandHandler,
            HelpCommandHandler,
            # Multi-Server
            ServersCommandHandler,
            ConnectCommandHandler,
        )
    except ImportError:
        from .command_handlers import (
            # Server Information
            StatusCommandHandler,
            PlayersCommandHandler,
            VersionCommandHandler,
            SeedCommandHandler,
            EvolutionCommandHandler,
            AdminsCommandHandler,
            HealthCommandHandler,
            # Player Management
            KickCommandHandler,
            BanCommandHandler,
            UnbanCommandHandler,
            MuteCommandHandler,
            UnmuteCommandHandler,
            PromoteCommandHandler,
            DemoteCommandHandler,
            # Server Management
            SaveCommandHandler,
            BroadcastCommandHandler,
            WhisperCommandHandler,
            WhitelistCommandHandler,
            # Game Control
            ClockCommandHandler,
            SpeedCommandHandler,
            ResearchCommandHandler,
            # Advanced
            RconCommandHandler,
            HelpCommandHandler,
            # Multi-Server
            ServersCommandHandler,
            ConnectCommandHandler,
        )

logger = structlog.get_logger()

# ════════════════════════════════════════════════════════════════════════════
# 🔧 HELPER: Null-Safe Response Handler
# ════════════════════════════════════════════════════════════════════════════

async def send_command_response(
    interaction: discord.Interaction,
    result: Any,
    defer_before_send: bool = False,
) -> None:
    """
    Safely send command response handling null embeds and deferred responses.
    """
    if result.success and result.embed:
        if defer_before_send:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(embed=result.embed, ephemeral=result.ephemeral)
    else:
        error_embed = result.error_embed if hasattr(result, 'error_embed') and result.error_embed else EmbedBuilder.error_embed(
            "An unexpected error occurred. Please try again later."
        )
        await interaction.response.send_message(
            embed=error_embed,
            ephemeral=result.ephemeral,
        )


# ════════════════════════════════════════════════════════════════════════════
# 🔧 HELPER: Initialize All Command Handlers
# ════════════════════════════════════════════════════════════════════════════

# Global handler instance variables
status_handler: Optional[StatusCommandHandler] = None
players_handler: Optional[PlayersCommandHandler] = None
version_handler: Optional[VersionCommandHandler] = None
seed_handler: Optional[SeedCommandHandler] = None
evolution_handler: Optional[EvolutionCommandHandler] = None
admins_handler: Optional[AdminsCommandHandler] = None
health_handler: Optional[HealthCommandHandler] = None

kick_handler: Optional[KickCommandHandler] = None
ban_handler: Optional[BanCommandHandler] = None
unban_handler: Optional[UnbanCommandHandler] = None
mute_handler: Optional[MuteCommandHandler] = None
unmute_handler: Optional[UnmuteCommandHandler] = None
promote_handler: Optional[PromoteCommandHandler] = None
demote_handler: Optional[DemoteCommandHandler] = None

save_handler: Optional[SaveCommandHandler] = None
broadcast_handler: Optional[BroadcastCommandHandler] = None
whisper_handler: Optional[WhisperCommandHandler] = None
whitelist_handler: Optional[WhitelistCommandHandler] = None

clock_handler: Optional[ClockCommandHandler] = None
speed_handler: Optional[SpeedCommandHandler] = None
research_handler: Optional[ResearchCommandHandler] = None

rcon_handler: Optional[RconCommandHandler] = None
help_handler: Optional[HelpCommandHandler] = None

servers_handler: Optional[ServersCommandHandler] = None
connect_handler: Optional[ConnectCommandHandler] = None


def _initialize_all_handlers(bot: FactorioBot) -> None:
    """Initialize all 25 command handlers with dependency injection."""
    global status_handler, players_handler, version_handler, seed_handler
    global evolution_handler, admins_handler, health_handler
    global kick_handler, ban_handler, unban_handler, mute_handler, unmute_handler
    global promote_handler, demote_handler
    global save_handler, broadcast_handler, whisper_handler, whitelist_handler
    global clock_handler, speed_handler, research_handler
    global rcon_handler, help_handler
    global servers_handler, connect_handler

    logger.info("initializing_all_handlers", count=25)

    # Server Information (7)
    status_handler = StatusCommandHandler(
        user_context=bot.user_context,
        server_manager=bot.server_manager,
        cooldown=QUERY_COOLDOWN,
        embed_builder=EmbedBuilder,
        rcon_monitor=getattr(bot, "rcon_monitor", None),
    )
    players_handler = PlayersCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    version_handler = VersionCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    seed_handler = SeedCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    evolution_handler = EvolutionCommandHandler(
        user_context=bot.user_context,
        cooldown=QUERY_COOLDOWN,
        embed_builder=EmbedBuilder,
    )
    admins_handler = AdminsCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    health_handler = HealthCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
        bot=bot,  # type: ignore
    )

    # Player Management (7)
    kick_handler = KickCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    ban_handler = BanCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    unban_handler = UnbanCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    mute_handler = MuteCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    unmute_handler = UnmuteCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    promote_handler = PromoteCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    demote_handler = DemoteCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )

    # Server Management (4)
    save_handler = SaveCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    broadcast_handler = BroadcastCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    whisper_handler = WhisperCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    whitelist_handler = WhitelistCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )

    # Game Control (3)
    clock_handler = ClockCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    speed_handler = SpeedCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    research_handler = ResearchCommandHandler(
        user_context=bot.user_context,
        cooldown=ADMIN_COOLDOWN,
        embed_builder=EmbedBuilder,
    )

    # Advanced (2)
    rcon_handler = RconCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    help_handler = HelpCommandHandler(embed_builder_type=EmbedBuilder)

    # Multi-Server (2)
    servers_handler = ServersCommandHandler(
        user_context_provider=bot.user_context,
        embed_builder_type=EmbedBuilder,
        server_manager=bot.server_manager,
    )
    connect_handler = ConnectCommandHandler(
        user_context_provider=bot.user_context,
        embed_builder_type=EmbedBuilder,
        server_manager=bot.server_manager,
    )

    logger.info("all_handlers_initialized_complete", total=25)


def register_factorio_commands(bot: FactorioBot) -> None:
    """
    Register all /factorio subcommands.

    This function creates and registers the complete /factorio command tree.
    Discord limit: 25 subcommands per group (currently using 25/25).

    Args:
        bot: FactorioBot instance with user_context, server_manager attributes
    """
    _initialize_all_handlers(bot)

    factorio_group = app_commands.Group(
        name="factorio",
        description="Factorio server status, players, and RCON management",
    )

    # ════════════════════════════════════════════════════════════════════════════
    # MULTI-SERVER (2)
    # ════════════════════════════════════════════════════════════════════════════

    async def server_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete server tags with display names."""
        if not hasattr(interaction.client, "server_manager"):
            return []

        server_manager = interaction.client.server_manager  # type: ignore
        if not server_manager:
            return []

        current_lower = current.lower()
        choices = []
        for tag, config in server_manager.list_servers().items():
            if (
                current_lower in tag.lower()
                or current_lower in config.name.lower()
                or (config.description and current_lower in config.description.lower())
            ):
                display = f"{tag} - {config.name}"
                if config.description:
                    display += f" ({config.description})"
                choices.append(
                    app_commands.Choice(
                        name=display[:100],
                        value=tag,
                    )
                )

        return choices[:25]

    @factorio_group.command(name="servers", description="List available Factorio servers")
    async def servers_command(interaction: discord.Interaction) -> None:
        if not servers_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Server handler not initialized"),
                ephemeral=True,
            )
            return
        result = await servers_handler.execute(interaction)
        await send_command_response(interaction, result, defer_before_send=False)

    @factorio_group.command(
        name="connect", description="Connect to a specific Factorio server"
    )
    @app_commands.describe(server="Server tag (use autocomplete or /factorio servers)")
    @app_commands.autocomplete(server=server_autocomplete)
    async def connect_command(interaction: discord.Interaction, server: str) -> None:
        if not connect_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Connect handler not initialized"),
                ephemeral=True,
            )
            return
        result = await connect_handler.execute(interaction, server=server)
        await send_command_response(interaction, result, defer_before_send=True)

    # ════════════════════════════════════════════════════════════════════════════
    # SERVER INFORMATION (7)
    # ════════════════════════════════════════════════════════════════════════════

    @factorio_group.command(name="status", description="Show Factorio server status")
    async def status_command(interaction: discord.Interaction) -> None:
        try:
            if not status_handler:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error_embed(
                        "Status handler not available. This is a bot configuration error.\n\n"
                        "Contact bot administrators."
                    ),
                    ephemeral=True,
                )
                logger.error("status_command_failed_no_handler", user=interaction.user.name)
                return
            
            result = await status_handler.execute(interaction)
            await send_command_response(interaction, result, defer_before_send=True)
        except Exception as e:
            logger.error("status_command_exception", error=str(e), exc_info=True)
            embed = EmbedBuilder.error_embed(f"Status command error: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @factorio_group.command(name="players", description="List players currently online")
    async def players_command(interaction: discord.Interaction) -> None:
        if not players_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Players handler not initialized"),
                ephemeral=True,
            )
            return
        result = await players_handler.execute(interaction)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="version", description="Show Factorio server version")
    async def version_command(interaction: discord.Interaction) -> None:
        if not version_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Version handler not initialized"),
                ephemeral=True,
            )
            return
        result = await version_handler.execute(interaction)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="seed", description="Show map seed")
    async def seed_command(interaction: discord.Interaction) -> None:
        if not seed_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Seed handler not initialized"),
                ephemeral=True,
            )
            return
        result = await seed_handler.execute(interaction)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(
        name="evolution",
        description="Show evolution for a surface or all non-platform surfaces",
    )
    @app_commands.describe(
        target='Surface/planet name (e.g. "nauvis") or the keyword "all"',
    )
    async def evolution_command(
        interaction: discord.Interaction,
        target: str,
    ) -> None:
        """Show enemy evolution with guaranteed response handling and timeout protection."""
        try:
            if not evolution_handler:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error_embed(
                        "Evolution handler not available. This is a bot configuration error.\n\n"
                        "Contact bot administrators."
                    ),
                    ephemeral=True,
                )
                logger.error("evolution_command_failed_no_handler", user=interaction.user.name)
                return
            
            await interaction.response.defer(ephemeral=False)
            result = await evolution_handler.execute(interaction, target)
            await send_command_response(interaction, result, defer_before_send=False)
        except Exception as e:
            logger.error("evolution_command_exception", error=str(e), exc_info=True)
            embed = EmbedBuilder.error_embed(f"Evolution command error: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)

    @factorio_group.command(name="admins", description="List server administrators")
    async def admins_command(interaction: discord.Interaction) -> None:
        if not admins_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Admins handler not initialized"),
                ephemeral=True,
            )
            return
        result = await admins_handler.execute(interaction)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="health", description="Check bot and server health")
    async def health_command(interaction: discord.Interaction) -> None:
        if not health_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Health handler not initialized"),
                ephemeral=True,
            )
            return
        result = await health_handler.execute(interaction)
        await send_command_response(interaction, result, defer_before_send=True)

    # ════════════════════════════════════════════════════════════════════════════
    # PLAYER MANAGEMENT (7)
    # ════════════════════════════════════════════════════════════════════════════

    @factorio_group.command(name="kick", description="Kick a player from the server")
    @app_commands.describe(player="Player name", reason="Reason for kick (optional)")
    async def kick_command(
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        if not kick_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Kick handler not initialized"),
                ephemeral=True,
            )
            return
        result = await kick_handler.execute(interaction, player=player, reason=reason)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="ban", description="Ban a player from the server")
    @app_commands.describe(player="Player name", reason="Reason for ban (optional)")
    async def ban_command(
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        if not ban_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Ban handler not initialized"),
                ephemeral=True,
            )
            return
        result = await ban_handler.execute(interaction, player=player, reason=reason)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="unban", description="Unban a player")
    @app_commands.describe(player="Player name")
    async def unban_command(
        interaction: discord.Interaction,
        player: str,
    ) -> None:
        if not unban_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Unban handler not initialized"),
                ephemeral=True,
            )
            return
        result = await unban_handler.execute(interaction, player=player)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="mute", description="Mute a player")
    @app_commands.describe(player="Player name")
    async def mute_command(interaction: discord.Interaction, player: str) -> None:
        if not mute_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Mute handler not initialized"),
                ephemeral=True,
            )
            return
        result = await mute_handler.execute(interaction, player=player)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="unmute", description="Unmute a player")
    @app_commands.describe(player="Player name")
    async def unmute_command(interaction: discord.Interaction, player: str) -> None:
        if not unmute_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Unmute handler not initialized"),
                ephemeral=True,
            )
            return
        result = await unmute_handler.execute(interaction, player=player)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="promote", description="Promote player to admin")
    @app_commands.describe(player="Player name")
    async def promote_command(interaction: discord.Interaction, player: str) -> None:
        if not promote_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Promote handler not initialized"),
                ephemeral=True,
            )
            return
        result = await promote_handler.execute(interaction, player=player)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="demote", description="Demote player from admin")
    @app_commands.describe(player="Player name")
    async def demote_command(interaction: discord.Interaction, player: str) -> None:
        if not demote_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Demote handler not initialized"),
                ephemeral=True,
            )
            return
        result = await demote_handler.execute(interaction, player=player)
        await send_command_response(interaction, result, defer_before_send=True)

    # ════════════════════════════════════════════════════════════════════════════
    # SERVER MANAGEMENT (4)
    # ════════════════════════════════════════════════════════════════════════════

    @factorio_group.command(name="save", description="Save the game")
    @app_commands.describe(name="Save name (optional, defaults to auto-save)")
    async def save_command(interaction: discord.Interaction, name: Optional[str] = None) -> None:
        if not save_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Save handler not initialized"),
                ephemeral=True,
            )
            return
        result = await save_handler.execute(interaction, name=name)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="broadcast", description="Send message to all players")
    @app_commands.describe(message="Message to broadcast")
    async def broadcast_command(interaction: discord.Interaction, message: str) -> None:
        if not broadcast_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Broadcast handler not initialized"),
                ephemeral=True,
            )
            return
        result = await broadcast_handler.execute(interaction, message=message)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="whisper", description="Send private message to a player")
    @app_commands.describe(player="Player name", message="Message to send")
    async def whisper_command(
        interaction: discord.Interaction,
        player: str,
        message: str,
    ) -> None:
        if not whisper_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Whisper handler not initialized"),
                ephemeral=True,
            )
            return
        result = await whisper_handler.execute(interaction, player=player, message=message)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="whitelist", description="Manage server whitelist")
    @app_commands.describe(
        action="Action to perform (add/remove/list/enable/disable)",
        player="Player name (required for add/remove)",
    )
    async def whitelist_command(
        interaction: discord.Interaction,
        action: str,
        player: Optional[str] = None,
    ) -> None:
        if not whitelist_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Whitelist handler not initialized"),
                ephemeral=True,
            )
            return
        result = await whitelist_handler.execute(interaction, action=action, player=player)
        await send_command_response(interaction, result, defer_before_send=True)

    # ════════════════════════════════════════════════════════════════════════════
    # GAME CONTROL (3)
    # ════════════════════════════════════════════════════════════════════════════

    @factorio_group.command(name="clock", description="Set or display game daytime")
    @app_commands.describe(value="'day'/'night' or 0.0-1.0, or leave empty to view")
    async def clock_command(interaction: discord.Interaction, value: Optional[str] = None) -> None:
        if not clock_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Clock handler not initialized"),
                ephemeral=True,
            )
            return
        result = await clock_handler.execute(interaction, value=value)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="speed", description="Set game speed")
    @app_commands.describe(value="Game speed (0.1-10.0, 1.0 = normal)")
    async def speed_command(interaction: discord.Interaction, value: float) -> None:
        if not speed_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Speed handler not initialized"),
                ephemeral=True,
            )
            return
        result = await speed_handler.execute(interaction, value=value)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(
        name="research",
        description="Manage technology research (Coop: player force, PvP: specify force)"
    )
    @app_commands.describe(
        force='Force name (e.g., "player", "enemy"). Defaults to "player".',
        action='Action: "all", tech name, "undo", or empty to display status',
        technology='Technology name (for undo operations with specific tech)',
    )
    async def research_command(
        interaction: discord.Interaction,
        force: Optional[str] = None,
        action: Optional[str] = None,
        technology: Optional[str] = None,
    ) -> None:
        try:
            if not research_handler:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error_embed("Research handler not available"),
                    ephemeral=True,
                )
                return
            result = await research_handler.execute(
                interaction, force=force, action=action, technology=technology
            )
            await send_command_response(interaction, result, defer_before_send=True)
        except Exception as e:
            logger.error("research_command_exception", error=str(e), exc_info=True)
            embed = EmbedBuilder.error_embed(f"Research command error: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════════
    # ADVANCED (2)
    # ════════════════════════════════════════════════════════════════════════════

    @factorio_group.command(name="rcon", description="Run raw RCON command")
    @app_commands.describe(command="RCON command to execute")
    async def rcon_command(interaction: discord.Interaction, command: str) -> None:
        if not rcon_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("RCON handler not initialized"),
                ephemeral=True,
            )
            return
        result = await rcon_handler.execute(interaction, command=command)
        await send_command_response(interaction, result, defer_before_send=True)

    @factorio_group.command(name="help", description="Show available Factorio commands")
    async def help_command(interaction: discord.Interaction) -> None:
        if not help_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Help handler not initialized"),
                ephemeral=True,
            )
            return
        result = await help_handler.execute(interaction)
        if result.success:
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
            await interaction.response.send_message(help_text, ephemeral=True)
        else:
            await interaction.response.send_message(
                embed=result.error_embed or EmbedBuilder.error_embed("Help command failed"),
                ephemeral=True,
            )

    bot.tree.add_command(factorio_group)
    logger.info(
        "slash_commands_registered_complete",
        root=factorio_group.name,
        command_count=len(factorio_group.commands),
        status="25/25 commands registered and operational",
    )
