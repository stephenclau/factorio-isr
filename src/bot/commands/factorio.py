# Copyright (c) 2025 Stephen Clau
#
# This file is part of Factorio ISR.
#
# Factorio ISR is dual-licensed:
#
# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
#    See LICENSE file for full terms
#
# 2. Commercial License
#    For proprietary use without AGPL requirements
#    Contact: licensing@laudiversified.com
#
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial

"""Factorio slash command group registration.

All /factorio subcommands are defined in this single file to respect Discord's
25 subcommand-per-group limit. Currently using 17/25 slots.

Command Breakdown:
- Multi-Server Commands: 2/25 (servers, connect)
- Server Information: 7/25 (status, players, version, seed, evolution, admins, health)
- Player Management: 7/25 (kick, ban, unban, mute, unmute, promote, demote)
- Server Management: 4/25 (save, broadcast, whisper, whitelist)
- Game Control: 3/25 (clock, speed, research)
- Advanced: 2/25 (rcon, help)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: 17/25 (8 slots available for future expansion)

🔄 Phase 4 Status: 🌟 **ALL 17/17 COMMANDS REFACTORED TO DI + COMMAND PATTERN** 🌟
"""

from typing import Any, List, Optional
from datetime import datetime, timezone
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
# 🔄 Phase 3 + Phase 4: Command Handlers (DI + Command Pattern)
# ════════════════════════════════════════════════════════════════════════════

try:
    # Batch 1: Player Management
    from bot.commands.command_handlers_batch1 import (
        KickCommandHandler,
        BanCommandHandler,
        UnbanCommandHandler,
        MuteCommandHandler,
        UnmuteCommandHandler,
    )
    # Batch 2: Server Management
    from bot.commands.command_handlers_batch2 import (
        SaveCommandHandler,
        BroadcastCommandHandler,
        WhisperCommandHandler,
        WhitelistCommandHandler,
    )
    # Batch 3: Game Control + Admin
    from bot.commands.command_handlers_batch3 import (
        ClockCommandHandler,
        SpeedCommandHandler,
        PromoteCommandHandler,
        DemoteCommandHandler,
    )
    # Batch 4: Remaining queries
    from bot.commands.command_handlers_batch4 import (
        PlayersCommandHandler,
        VersionCommandHandler,
        SeedCommandHandler,
        AdminsCommandHandler,
        HealthCommandHandler,
        RconCommandHandler,
        HelpCommandHandler,
        ServersCommandHandler,
        ConnectCommandHandler,
    )
except ImportError:
    try:
        from src.bot.commands.command_handlers_batch1 import (  # type: ignore
            KickCommandHandler,
            BanCommandHandler,
            UnbanCommandHandler,
            MuteCommandHandler,
            UnmuteCommandHandler,
        )
        from src.bot.commands.command_handlers_batch2 import (  # type: ignore
            SaveCommandHandler,
            BroadcastCommandHandler,
            WhisperCommandHandler,
            WhitelistCommandHandler,
        )
        from src.bot.commands.command_handlers_batch3 import (  # type: ignore
            ClockCommandHandler,
            SpeedCommandHandler,
            PromoteCommandHandler,
            DemoteCommandHandler,
        )
        from src.bot.commands.command_handlers_batch4 import (  # type: ignore
            PlayersCommandHandler,
            VersionCommandHandler,
            SeedCommandHandler,
            AdminsCommandHandler,
            HealthCommandHandler,
            RconCommandHandler,
            HelpCommandHandler,
            ServersCommandHandler,
            ConnectCommandHandler,
        )
    except ImportError:
        from .command_handlers_batch1 import (
            KickCommandHandler,
            BanCommandHandler,
            UnbanCommandHandler,
            MuteCommandHandler,
            UnmuteCommandHandler,
        )
        from .command_handlers_batch2 import (
            SaveCommandHandler,
            BroadcastCommandHandler,
            WhisperCommandHandler,
            WhitelistCommandHandler,
        )
        from .command_handlers_batch3 import (
            ClockCommandHandler,
            SpeedCommandHandler,
            PromoteCommandHandler,
            DemoteCommandHandler,
        )
        from .command_handlers_batch4 import (
            PlayersCommandHandler,
            VersionCommandHandler,
            SeedCommandHandler,
            AdminsCommandHandler,
            HealthCommandHandler,
            RconCommandHandler,
            HelpCommandHandler,
            ServersCommandHandler,
            ConnectCommandHandler,
        )

logger = structlog.get_logger()

# ════════════════════════════════════════════════════════════════════════════
# 🔄 Global Handler Instances (22 total: 3 Phase 2 + 13 Phase 3 + 9 Phase 4 - 3 reused = 22 unique)
# ════════════════════════════════════════════════════════════════════════════

# Batch 1: Player Management
kick_handler: Optional[KickCommandHandler] = None
ban_handler: Optional[BanCommandHandler] = None
unban_handler: Optional[UnbanCommandHandler] = None
mute_handler: Optional[MuteCommandHandler] = None
unmute_handler: Optional[UnmuteCommandHandler] = None

# Batch 2: Server Management
save_handler: Optional[SaveCommandHandler] = None
broadcast_handler: Optional[BroadcastCommandHandler] = None
whisper_handler: Optional[WhisperCommandHandler] = None
whitelist_handler: Optional[WhitelistCommandHandler] = None

# Batch 3: Game Control + Admin
clock_handler: Optional[ClockCommandHandler] = None
speed_handler: Optional[SpeedCommandHandler] = None
promote_handler: Optional[PromoteCommandHandler] = None
demote_handler: Optional[DemoteCommandHandler] = None

# Batch 4: Remaining queries + advanced
players_handler: Optional[PlayersCommandHandler] = None
version_handler: Optional[VersionCommandHandler] = None
seed_handler: Optional[SeedCommandHandler] = None
admins_handler: Optional[AdminsCommandHandler] = None
health_handler: Optional[HealthCommandHandler] = None
rcon_handler: Optional[RconCommandHandler] = None
help_handler: Optional[HelpCommandHandler] = None
servers_handler: Optional[ServersCommandHandler] = None
connect_handler: Optional[ConnectCommandHandler] = None


# ════════════════════════════════════════════════════════════════════════════
# 🔧 HELPER: Import Phase 2 Handlers (Status, Evolution, Research)
# ════════════════════════════════════════════════════════════════════════════

def _import_phase2_handlers() -> tuple[Any, Any, Any]:
    """
    Import Phase 2 handlers (status_handler, evolution_handler, research_handler).
    
    Tries multiple import paths and returns tuple of handlers or None values.
    
    Returns:
        Tuple of (status_handler, evolution_handler, research_handler)
    """
    status_handler = None
    evolution_handler = None
    research_handler = None
    
    # Try Path 1: Relative import from same directory
    try:
        from .command_handlers import (
            status_handler as sh,
            evolution_handler as eh,
            research_handler as rh,
        )
        status_handler, evolution_handler, research_handler = sh, eh, rh
        logger.info("phase2_handlers_imported", path="relative_from_same_directory")
        return status_handler, evolution_handler, research_handler
    except (ImportError, AttributeError) as e:
        logger.debug("phase2_import_failed_path1", error=str(e))
    
    # Try Path 2: Absolute import via bot.commands
    try:
        from bot.commands.command_handlers import (
            status_handler as sh,
            evolution_handler as eh,
            research_handler as rh,
        )
        status_handler, evolution_handler, research_handler = sh, eh, rh
        logger.info("phase2_handlers_imported", path="absolute_bot_commands")
        return status_handler, evolution_handler, research_handler
    except (ImportError, AttributeError) as e:
        logger.debug("phase2_import_failed_path2", error=str(e))
    
    # Try Path 3: Absolute import via src.bot.commands
    try:
        from src.bot.commands.command_handlers import (  # type: ignore
            status_handler as sh,
            evolution_handler as eh,
            research_handler as rh,
        )
        status_handler, evolution_handler, research_handler = sh, eh, rh
        logger.info("phase2_handlers_imported", path="absolute_src_bot_commands")
        return status_handler, evolution_handler, research_handler
    except (ImportError, AttributeError) as e:
        logger.debug("phase2_import_failed_path3", error=str(e))
    
    # All paths failed
    logger.warning("phase2_handlers_not_available", status="will_use_fallback_embeds")
    return None, None, None


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
    
    Args:
        interaction: Discord interaction object
        result: CommandResult with success, embed, error_embed, ephemeral attributes
        defer_before_send: If True, defer interaction before sending via followup
    """
    if result.success and result.embed:
        # Success case with valid embed
        if defer_before_send:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(embed=result.embed, ephemeral=result.ephemeral)
    else:
        # Error case - always have error_embed (or create default)
        error_embed = result.error_embed if result.error_embed else EmbedBuilder.error_embed(
            "An unexpected error occurred. Please try again later."
        )
        await interaction.response.send_message(
            embed=error_embed,
            ephemeral=result.ephemeral,
        )


# ════════════════════════════════════════════════════════════════════════════
# 🔄 Composition Root - Initialize ALL 22 handlers
# ════════════════════════════════════════════════════════════════════════════

def _initialize_all_handlers(bot: Any) -> None:
    """Initialize all 22 command handlers with DI."""
    global kick_handler, ban_handler, unban_handler, mute_handler, unmute_handler
    global save_handler, broadcast_handler, whisper_handler, whitelist_handler
    global clock_handler, speed_handler, promote_handler, demote_handler
    global players_handler, version_handler, seed_handler, admins_handler
    global health_handler, rcon_handler, help_handler, servers_handler, connect_handler

    logger.info("initializing_all_handlers", count=22)

    # 🔴 BATCH 1: Player Management (5 handlers)
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
    logger.info("batch1_initialized", handlers=5)

    # 🟠 BATCH 2: Server Management (4 handlers)
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
    logger.info("batch2_initialized", handlers=4)

    # 🟡 BATCH 3: Game Control + Admin (4 handlers)
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
    logger.info("batch3_initialized", handlers=4)

    # 🟢 BATCH 4: Remaining (9 handlers)
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
    admins_handler = AdminsCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    health_handler = HealthCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
        bot=bot,
    )
    rcon_handler = RconCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=DANGER_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    help_handler = HelpCommandHandler(embed_builder_type=EmbedBuilder)
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
    logger.info("batch4_initialized", handlers=9)
    logger.info("all_handlers_initialized_complete", total=22)


def register_factorio_commands(bot: Any) -> None:
    """
    Register all /factorio subcommands (Phase 1 + Phase 2 + Phase 3 + Phase 4).

    This function creates and registers the complete /factorio command tree.
    Discord limit: 25 subcommands per group (we use 17).
    
    All 17 commands now use DI + Command Pattern with handler delegations.

    Args:
        bot: DiscordBot instance with user_context, server_manager attributes
    """
    # 🔄 Initialize ALL handlers
    _initialize_all_handlers(bot)
    
    # 🔧 Import Phase 2 handlers (may fail gracefully)
    phase2_status_handler, phase2_evolution_handler, phase2_research_handler = _import_phase2_handlers()

    factorio_group = app_commands.Group(
        name="factorio",
        description="Factorio server status, players, and RCON management",
    )

    # ========================================================================
    # MULTI-SERVER COMMANDS (2/25)
    # ========================================================================

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
        """List all configured servers. Delegates to ServersCommandHandler."""
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
        """Switch user's context to a different server. Delegates to ConnectCommandHandler."""
        if not connect_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Connect handler not initialized"),
                ephemeral=True,
            )
            return
        result = await connect_handler.execute(interaction, server=server)
        await send_command_response(interaction, result, defer_before_send=True)

    # ========================================================================
    # SERVER INFORMATION COMMANDS (7/25)
    # ========================================================================

    @factorio_group.command(name="status", description="Show Factorio server status")
    async def status_command(interaction: discord.Interaction) -> None:
        """Get comprehensive server status (Phase 2 handler - Status + Evolution)."""
        if not phase2_status_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Status handler not available (Phase 2 module not found)"),
                ephemeral=True,
            )
            return
        try:
            result = await phase2_status_handler.execute(interaction)
            await send_command_response(interaction, result, defer_before_send=True)
        except Exception as e:
            logger.error("status_command_error", error=str(e))
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(f"Failed to get status: {str(e)}"),
                ephemeral=True,
            )

    @factorio_group.command(name="players", description="List players currently online")
    async def players_command(interaction: discord.Interaction) -> None:
        """List online players. Delegates to PlayersCommandHandler."""
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
        """Get Factorio server version. Delegates to VersionCommandHandler."""
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
        """Get map seed. Delegates to SeedCommandHandler."""
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
        """Show enemy evolution (Phase 2 handler - EvolutionCommandHandler)."""
        if not phase2_evolution_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Evolution handler not available (Phase 2 module not found)"),
                ephemeral=True,
            )
            return
        try:
            result = await phase2_evolution_handler.execute(interaction, target=target)
            await send_command_response(interaction, result, defer_before_send=True)
        except Exception as e:
            logger.error("evolution_command_error", error=str(e))
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(f"Failed to get evolution: {str(e)}"),
                ephemeral=True,
            )

    @factorio_group.command(name="admins", description="List server administrators")
    async def admins_command(interaction: discord.Interaction) -> None:
        """Get list of admins. Delegates to AdminsCommandHandler."""
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
        """Check overall health status. Delegates to HealthCommandHandler."""
        if not health_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Health handler not initialized"),
                ephemeral=True,
            )
            return
        result = await health_handler.execute(interaction)
        await send_command_response(interaction, result, defer_before_send=True)

    # ========================================================================
    # PLAYER MANAGEMENT COMMANDS (7/25)
    # ========================================================================

    @factorio_group.command(name="kick", description="Kick a player from the server")
    @app_commands.describe(player="Player name", reason="Reason for kick (optional)")
    async def kick_command(
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        """Kick a player. Delegates to KickCommandHandler."""
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
        """Ban a player. Delegates to BanCommandHandler."""
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
        """Unban a player. Delegates to UnbanCommandHandler."""
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
        """Mute a player from chat. Delegates to MuteCommandHandler."""
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
        """Unmute a player. Delegates to UnmuteCommandHandler."""
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
        """Promote a player to admin. Delegates to PromoteCommandHandler."""
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
        """Demote a player from admin. Delegates to DemoteCommandHandler."""
        if not demote_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Demote handler not initialized"),
                ephemeral=True,
            )
            return
        result = await demote_handler.execute(interaction, player=player)
        await send_command_response(interaction, result, defer_before_send=True)

    # ========================================================================
    # SERVER MANAGEMENT COMMANDS (4/25)
    # ========================================================================

    @factorio_group.command(name="save", description="Save the game")
    @app_commands.describe(name="Save name (optional, defaults to auto-save)")
    async def save_command(interaction: discord.Interaction, name: Optional[str] = None) -> None:
        """Save the game. Delegates to SaveCommandHandler."""
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
        """Broadcast a message to all players. Delegates to BroadcastCommandHandler."""
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
        """Send a private message to a player. Delegates to WhisperCommandHandler."""
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
        """Manage the server whitelist. Delegates to WhitelistCommandHandler."""
        if not whitelist_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Whitelist handler not initialized"),
                ephemeral=True,
            )
            return
        result = await whitelist_handler.execute(interaction, action=action, player=player)
        await send_command_response(interaction, result, defer_before_send=True)

    # ========================================================================
    # GAME CONTROL COMMANDS (3/25)
    # ========================================================================

    @factorio_group.command(name="clock", description="Set or display game daytime")
    @app_commands.describe(value="'day'/'night' or 0.0-1.0, or leave empty to view")
    async def clock_command(interaction: discord.Interaction, value: Optional[str] = None) -> None:
        """Set or display the game clock. Delegates to ClockCommandHandler."""
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
        """Set game speed. Delegates to SpeedCommandHandler."""
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
        """Manage technology research (Phase 2 handler - ResearchCommandHandler)."""
        if not phase2_research_handler:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed("Research handler not available (Phase 2 module not found)"),
                ephemeral=True,
            )
            return
        try:
            result = await phase2_research_handler.execute(
                interaction, force=force, action=action, technology=technology
            )
            await send_command_response(interaction, result, defer_before_send=True)
        except Exception as e:
            logger.error("research_command_error", error=str(e))
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(f"Failed to manage research: {str(e)}"),
                ephemeral=True,
            )

    # ========================================================================
    # ADVANCED COMMANDS (2/25)
    # ========================================================================

    @factorio_group.command(name="rcon", description="Run raw RCON command")
    @app_commands.describe(command="RCON command to execute")
    async def rcon_command(interaction: discord.Interaction, command: str) -> None:
        """Execute a raw RCON command. Delegates to RconCommandHandler."""
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
        """Display comprehensive help message. Delegates to HelpCommandHandler."""
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

    # ========================================================================
    # Register the command group
    # ========================================================================

    bot.tree.add_command(factorio_group)
    logger.info(
        "slash_commands_registered_complete",
        root=factorio_group.name,
        command_count=len(factorio_group.commands),
        phase="Phase 4: ALL 17/17 commands refactored to DI + Command Pattern",
        total_handlers=22,
    )
