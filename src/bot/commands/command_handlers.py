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

"""
Unified Command Handlers for Factorio Discord Bot.

This module consolidates all 25 command handlers into a single file, organized
by functional category. Each handler encapsulates business logic with explicit
dependency injection, making unit testing straightforward without complex mocking.

Handler Categories:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📊 Server Information (7):  Status, Players, Version, Seed, Evolution, Admins, Health
  👥 Player Management (7):   Kick, Ban, Unban, Mute, Unmute, Promote, Demote
  🔧 Server Management (4):   Save, Broadcast, Whisper, Whitelist
  🎮 Game Control (3):        Clock, Speed, Research
  🛠️ Advanced (2):            RCON, Help
  🌍 Multi-Server (2):        Servers, Connect
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TOTAL: 25/25 handlers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Architecture Pattern:
    1. Create handler instance with DI: StatusCommandHandler(user_context, ...)
    2. Register Discord command closure
    3. Closure delegates to handler: await handler.execute(interaction)
    4. Test handler directly with mock dependencies

This approach provides:
    ✅ Explicit dependencies (no implicit closures)
    ✅ Easy mocking for unit tests
    ✅ Reusable logic outside Discord context
    ✅ Clear data flow (dependencies → logic → result)
    ✅ Type safety via Protocol/ABC
"""

from typing import Any, ClassVar, Dict, List, Optional, Protocol
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import discord
import structlog

logger = structlog.get_logger()


# ═════════════════════════════════════════════════════════════════════════════
# DEPENDENCY PROTOCOLS (Define interfaces for injection)
# ═════════════════════════════════════════════════════════════════════════════


class UserContextProvider(Protocol):
    """Interface for user context management (per-user server selection)."""

    def get_user_server(self, user_id: int) -> str:
        """Get currently selected server tag for user."""
        ...

    def get_server_display_name(self, user_id: int) -> str:
        """Get display name for user's current server."""
        ...

    def get_rcon_for_user(self, user_id: int) -> Optional[Any]:
        """Get RCON client for user's current server."""
        ...

    def set_user_server(self, user_id: int, server: str) -> None:
        """Set user's active server context."""
        ...


class RconMetricsProvider(Protocol):
    """Interface for gathering metrics from Factorio server."""

    async def gather_all_metrics(self) -> Dict[str, Any]:
        """Gather comprehensive metrics (UPS, players, evolution, etc)."""
        ...


class ServerManagerProvider(Protocol):
    """Interface for server management and metrics."""

    def get_metrics_engine(self, server_tag: str) -> Optional[RconMetricsProvider]:
        """Get metrics engine for a server."""
        ...

    def list_servers(self) -> Dict[str, Any]:
        """List all available servers."""
        ...

    def get_config(self, server: str) -> Any:
        """Get configuration for specific server."""
        ...

    def get_status_summary(self) -> Dict[str, bool]:
        """Get connection status summary for all servers."""
        ...

    def get_client(self, server: str) -> Any:
        """Get RCON client for specific server."""
        ...

    clients: Dict[str, Any]


class RconClientProvider(Protocol):
    """Interface for RCON command execution."""

    @property
    def is_connected(self) -> bool:
        """Whether RCON is connected."""
        ...

    async def execute(self, command: str) -> str:
        """Execute RCON command and return response."""
        ...


class RateLimiter(Protocol):
    """Interface for rate limiting."""

    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[float]]:
        """Check if user is rate limited. Returns (is_limited, retry_after)."""
        ...


class EmbedBuilderType(Protocol):
    """Interface for embed building utilities.
    
    This protocol matches the actual EmbedBuilder implementation:
    - Colors are class variables (ClassVar)
    - cooldown_embed accepts int (retry_seconds from rate limiter)
    """

    COLOR_SUCCESS: ClassVar[int]
    COLOR_WARNING: ClassVar[int]
    COLOR_INFO: ClassVar[int]
    COLOR_ADMIN: ClassVar[int]

    @staticmethod
    def cooldown_embed(retry_seconds: int) -> discord.Embed:
        """Create rate limit embed."""
        ...

    @staticmethod
    def error_embed(message: str) -> discord.Embed:
        """Create error embed."""
        ...

    @staticmethod
    def info_embed(title: str, message: str) -> discord.Embed:
        """Create info embed."""
        ...

    @staticmethod
    def create_base_embed(title: str, color: int) -> discord.Embed:
        """Create base embed with title and color."""
        ...


class RconMonitorType(Protocol):
    """Protocol for RCON monitor (uptime tracking)."""

    rcon_server_states: Dict[str, Dict[str, Any]]


class BotType(Protocol):
    """Protocol for bot instance."""

    _connected: bool
    user_context: UserContextProvider
    server_manager: Optional[ServerManagerProvider]
    rcon_monitor: Optional[RconMonitorType]


# ═════════════════════════════════════════════════════════════════════════════
# RESULT TYPES (Type-safe command outputs)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class CommandResult:
    """Base result type for all command handlers."""

    success: bool
    embed: Optional[discord.Embed] = None
    error_embed: Optional[discord.Embed] = None
    ephemeral: bool = False
    followup: bool = False  # If True, use interaction.followup.send()


# ═════════════════════════════════════════════════════════════════════════════
# 📊 SERVER INFORMATION HANDLERS (7)
# ═════════════════════════════════════════════════════════════════════════════


class StatusCommandHandler:
    """
    Handler for /factorio status command.

    Pure logic: rate limit → validate RCON → gather metrics → format embed.
    No closure dependencies; all injected via constructor.
    """

    def __init__(
        self,
        user_context: UserContextProvider,
        server_manager: ServerManagerProvider,
        cooldown: RateLimiter,
        embed_builder: EmbedBuilderType,
        rcon_monitor: Optional[Any] = None,  # For uptime tracking
    ):
        """Inject all dependencies explicitly."""
        self.user_context = user_context
        self.server_manager = server_manager
        self.cooldown = cooldown
        self.embed_builder = embed_builder
        self.rcon_monitor = rcon_monitor

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute status command with explicit dependency injection."""
        logger.info("handler_invoked", handler="StatusCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="StatusCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
        )

        # Rate limiting
        is_limited, retry = self.cooldown.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=False,
            )

        # Get server context
        server_tag = self.user_context.get_user_server(interaction.user.id)
        server_name = self.user_context.get_server_display_name(interaction.user.id)

        # Get RCON client
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            embed = self.embed_builder.error_embed(
                f"RCON not available for {server_name}.\n"
                "Use `/factorio servers` to see available servers."
            )
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            # Gather metrics via metrics engine
            metrics_engine = self.server_manager.get_metrics_engine(server_tag)
            if metrics_engine is None:
                raise RuntimeError(f"Metrics engine not available for {server_tag}")

            metrics = await metrics_engine.gather_all_metrics()

            # Calculate uptime
            uptime_text = self._calculate_uptime(server_tag)

            # Build embed
            embed = self.embed_builder.create_base_embed(
                title=f"🏭 {server_name} Status",
                color=(
                    self.embed_builder.COLOR_SUCCESS
                    if rcon_client.is_connected
                    else self.embed_builder.COLOR_WARNING
                ),
            )

            # Add fields
            embed.add_field(
                name="🤖 Bot Status",
                value="🟢 Online",  # Simplified; real version checks bot._connected
                inline=True,
            )
            embed.add_field(
                name="🔧 RCON",
                value="🟢 Connected" if rcon_client.is_connected else "🔴 Disconnected",
                inline=True,
            )
            embed.add_field(name="⏱️ Monitoring Uptime", value=uptime_text, inline=True)

            # Server state (pause detection)
            is_paused = metrics.get("is_paused", False)
            ups_value = metrics.get("ups")

            if is_paused:
                embed.add_field(name="📡 Server State", value="⏸️ Paused", inline=True)
            elif ups_value is not None:
                embed.add_field(
                    name="📡 Server State",
                    value=f"▶️ Running @ {ups_value:.1f}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="📡 Server State", value="🔄 Fetching...", inline=True
                )

            # UPS metrics
            if metrics.get("ups_sma") is not None:
                embed.add_field(name="📊 UPS (SMA)", value=f"{metrics['ups_sma']:.1f}", inline=True)

            if metrics.get("ups_ema") is not None:
                embed.add_field(name="📈 UPS (EMA)", value=f"{metrics['ups_ema']:.1f}", inline=True)

            # Players
            player_count = metrics.get("player_count", 0)
            embed.add_field(name="👥 Players Online", value=str(player_count), inline=True)

            # Play time
            if metrics.get("play_time"):
                embed.add_field(
                    name="🎮🕐 Total Play Time",
                    value=metrics["play_time"],
                    inline=True,
                )

            # Online players list
            players = metrics.get("players", [])
            if players:
                player_list = "\n".join(f"• {name}" for name in players[:10])
                if len(players) > 10:
                    player_list += f"\n... and {len(players) - 10} more"
                embed.add_field(name="👥 Online Players", value=player_list, inline=False)

            # Evolution by surface
            evolution_by_surface = metrics.get("evolution_by_surface", {})
            if "nauvis" in evolution_by_surface:
                nauvis_evo = evolution_by_surface["nauvis"]
                embed.add_field(
                    name="🐛 Nauvis Evolution",
                    value=f"{nauvis_evo:.2f} ({nauvis_evo * 100:.1f}%)",
                    inline=True,
                )

            if "gleba" in evolution_by_surface:
                gleba_evo = evolution_by_surface["gleba"]
                embed.add_field(
                    name="🐛 Gleba Evolution",
                    value=f"{gleba_evo:.2f} ({gleba_evo * 100:.1f}%)",
                    inline=True,
                )

            # Fallback
            if not evolution_by_surface and metrics.get("evolution_factor") is not None:
                evo_pct = metrics["evolution_factor"] * 100
                embed.add_field(
                    name="🐛 Enemy Evolution",
                    value=f"{evo_pct:.1f}%",
                    inline=True,
                )

            embed.set_footer(text="Factorio ISR | Metrics via RconMetricsEngine")

            logger.info(
                "status_command_executed",
                user=interaction.user.name,
                server_tag=server_tag,
                ups=metrics.get("ups"),
                evolution=metrics.get("evolution_factor"),
            )

            return CommandResult(
                success=True,
                embed=embed,
                ephemeral=False,
                followup=True,
            )

        except Exception as e:
            embed = self.embed_builder.error_embed(f"Failed to get status: {str(e)}")
            logger.error("status_command_failed", error=str(e), exc_info=True)
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )

    def _calculate_uptime(self, server_tag: str) -> str:
        """Calculate uptime from rcon_monitor state."""
        if not self.rcon_monitor or not self.rcon_monitor.rcon_server_states:
            return "Unknown"

        state = self.rcon_monitor.rcon_server_states.get(server_tag)
        if not state or not state.get("last_connected"):
            return "Unknown"

        last_connected = state["last_connected"]
        uptime_delta = datetime.now(timezone.utc) - last_connected
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

        return " ".join(parts) if parts else "< 1m"


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
        logger.info("handler_invoked", handler="PlayersCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="PlayersCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
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
        logger.info("handler_invoked", handler="VersionCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="VersionCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
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
        logger.info("handler_invoked", handler="SeedCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="SeedCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
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
                color=self.embed_builder.COLOR_INFO,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Map Seed", value=f"`{seed}`", inline=False)
            embed.add_field(
                name="Usage",
                value="Use this seed to generate the same map in a new game",
                inline=False,
            )
            embed.set_footer(text="Factorio ISR")
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


class EvolutionCommandHandler:
    """Handler for /factorio evolution command with multi-surface support."""

    def __init__(
        self,
        user_context: UserContextProvider,
        cooldown: RateLimiter,
        embed_builder: EmbedBuilderType,
    ):
        self.user_context = user_context
        self.cooldown = cooldown
        self.embed_builder = embed_builder

    async def execute(
        self, interaction: discord.Interaction, target: str
    ) -> CommandResult:
        """Execute evolution command for single surface or aggregate all."""
        logger.info("handler_invoked", handler="EvolutionCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="EvolutionCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target=target,
        )

        # Rate limiting
        is_limited, retry = self.cooldown.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=False,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = self.embed_builder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            raw = target.strip()
            lower = raw.lower()

            # MODE 1: Aggregate all non-platform surfaces
            if lower == "all":
                result = await self._handle_aggregate_evolution(rcon_client)
                return result

            # MODE 2: Single surface
            result = await self._handle_single_surface_evolution(rcon_client, raw)
            return result

        except Exception as e:
            embed = self.embed_builder.error_embed(f"Failed to get evolution: {str(e)}")
            logger.error("evolution_command_failed", error=str(e), target=target)
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )

    async def _handle_aggregate_evolution(self, rcon_client: RconClientProvider) -> CommandResult:
        """Query all non-platform surfaces and aggregate evolution."""
        lua = (
            "/sc "
            "local f = game.forces['enemy']; "
            "local total = 0; local count = 0; "
            "local lines = {}; "
            "for _, s in pairs(game.surfaces) do "
            " if not string.find(string.lower(s.name), 'platform') then "
            " local evo = f.get_evolution_factor(s); "
            " total = total + evo; count = count + 1; "
            " table.insert(lines, s.name .. ':' .. string.format('%.2f%%', evo * 100)); "
            " end "
            "end; "
            "if count > 0 then "
            " local avg = total / count; "
            " rcon.print('AGG:' .. string.format('%.2f%%', avg * 100)); "
            "else "
            " rcon.print('AGG:0.00%%'); "
            "end; "
            "for _, line in ipairs(lines) do "
            " rcon.print(line); "
            "end"
        )

        resp = await rcon_client.execute(lua)
        lines = [ln.strip() for ln in resp.splitlines() if ln.strip()]
        agg_line = next((ln for ln in lines if ln.startswith("AGG:")), None)
        per_surface = [ln for ln in lines if not ln.startswith("AGG:")]

        agg_value = "0.00%"
        if agg_line:
            agg_value = agg_line.replace("AGG:", "", 1).strip()

        if not per_surface:
            title = "🐛 Evolution – All Surfaces"
            message = (
                f"Aggregate enemy evolution across non-platform surfaces: **{agg_value}**\n\n"
                "No individual non-platform surfaces returned evolution data."
            )
        else:
            formatted = "\n".join(f"• `{ln}`" for ln in per_surface)
            title = "🐛 Evolution – All Non-platform Surfaces"
            message = (
                f"Aggregate enemy evolution across non-platform surfaces: **{agg_value}**\n\n"
                "Per-surface evolution:\n\n" f"{formatted}"
            )

        embed = self.embed_builder.info_embed(title=title, message=message)
        logger.info("evolution_aggregate_queried")

        return CommandResult(
            success=True,
            embed=embed,
            ephemeral=False,
            followup=True,
        )

    async def _handle_single_surface_evolution(
        self, rcon_client: RconClientProvider, surface: str
    ) -> CommandResult:
        """Query evolution for a single surface."""
        lua = (
            "/sc "
            f"local s = game.get_surface('{surface}'); "
            "if not s then "
            " rcon.print('SURFACE_NOT_FOUND'); "
            " return "
            "end; "
            "if string.find(string.lower(s.name), 'platform') then "
            " rcon.print('SURFACE_PLATFORM_IGNORED'); "
            " return "
            "end; "
            "local evo = game.forces['enemy'].get_evolution_factor(s); "
            "rcon.print(string.format('%.2f%%', evo * 100))"
        )

        resp = await rcon_client.execute(lua)
        resp_str = resp.strip()

        if resp_str == "SURFACE_NOT_FOUND":
            embed = self.embed_builder.error_embed(
                f"Surface `{surface}` was not found.\n\n"
                "Use map tools or an admin command to list available surfaces."
            )
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )

        if resp_str == "SURFACE_PLATFORM_IGNORED":
            embed = self.embed_builder.error_embed(
                f"Surface `{surface}` is a platform surface and is ignored for evolution queries."
            )
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )

        title = f"🐛 Evolution – Surface `{surface}`"
        message = f"Enemy evolution on `{surface}`: **{resp_str}**\n\nHigher evolution means stronger biters!"

        embed = self.embed_builder.info_embed(title=title, message=message)
        logger.info("evolution_single_surface_queried", surface=surface)

        return CommandResult(
            success=True,
            embed=embed,
            ephemeral=False,
            followup=True,
        )


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
        logger.info("handler_invoked", handler="AdminsCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="AdminsCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
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
        logger.info("handler_invoked", handler="HealthCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="HealthCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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


# ═════════════════════════════════════════════════════════════════════════════
# 👥 PLAYER MANAGEMENT HANDLERS (7)
# ═════════════════════════════════════════════════════════════════════════════


class KickCommandHandler:
    """Kick a player from the server."""

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
        player: str,
        reason: Optional[str] = None,
    ) -> CommandResult:
        """Execute kick command."""
        logger.info("handler_invoked", handler="KickCommandHandler", user=interaction.user.name, player=player)
        logger.info(
            "handler_invoked",
            handler="KickCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            message = reason if reason else "Kicked by moderator"
            await rcon_client.execute(f"/kick {player} {message}")

            embed = discord.Embed(
                title="⚠️ Player Kicked",
                color=self.embed_builder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Reason", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_kicked",
                player=player,
                reason=message,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("kick_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to kick player: {str(e)}"
                ),
                ephemeral=True,
            )


class BanCommandHandler:
    """Ban a player from the server."""

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
        player: str,
        reason: Optional[str] = None,
    ) -> CommandResult:
        """Execute ban command."""
        logger.info("handler_invoked", handler="BanCommandHandler", user=interaction.user.name, player=player)
        logger.info(
            "handler_invoked",
            handler="BanCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            message = reason if reason else "Banned by moderator"
            await rcon_client.execute(f"/ban {player} {message}")

            embed = discord.Embed(
                title="🚫 Player Banned",
                color=discord.Color.from_rgb(220, 20, 60),  # Crimson
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Reason", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_banned",
                player=player,
                reason=message,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("ban_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to ban player: {str(e)}"
                ),
                ephemeral=True,
            )


class UnbanCommandHandler:
    """Unban a player."""

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
        player: str,
    ) -> CommandResult:
        """Execute unban command."""
        logger.info("handler_invoked", handler="UnbanCommandHandler", user=interaction.user.name, player=player)
        logger.info(
            "handler_invoked",
            handler="UnbanCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await rcon_client.execute(f"/unban {player}")

            embed = discord.Embed(
                title="✅ Player Unbanned",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_unbanned",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("unban_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to unban player: {str(e)}"
                ),
                ephemeral=True,
            )


class MuteCommandHandler:
    """Mute a player from chat."""

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
        player: str,
    ) -> CommandResult:
        """Execute mute command."""
        logger.info("handler_invoked", handler="MuteCommandHandler", user=interaction.user.name, player=player)
        logger.info(
            "handler_invoked",
            handler="MuteCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await rcon_client.execute(f"/mute {player}")

            embed = discord.Embed(
                title="🔇 Player Muted",
                color=self.embed_builder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_muted",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("mute_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to mute player: {str(e)}"
                ),
                ephemeral=True,
            )


class UnmuteCommandHandler:
    """Unmute a player."""

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
        player: str,
    ) -> CommandResult:
        """Execute unmute command."""
        logger.info("handler_invoked", handler="UnmuteCommandHandler", user=interaction.user.name, player=player)
        logger.info(
            "handler_invoked",
            handler="UnmuteCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await rcon_client.execute(f"/unmute {player}")

            embed = discord.Embed(
                title="🔊 Player Unmuted",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_unmuted",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("unmute_command_failed", error=str(e), player=player)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to unmute player: {str(e)}"
                ),
                ephemeral=True,
            )


class PromoteCommandHandler:
    """Promote player to admin."""

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
        player: str,
    ) -> CommandResult:
        """Execute promote command."""
        logger.info("handler_invoked", handler="PromoteCommandHandler", user=interaction.user.name, player=player)
        logger.info(
            "handler_invoked",
            handler="PromoteCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await rcon_client.execute(f"/promote {player}")

            embed = discord.Embed(
                title="👑 Player Promoted",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Role", value="Administrator", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_promoted",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("promote_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to promote player: {str(e)}"
                ),
                ephemeral=True,
            )


class DemoteCommandHandler:
    """Demote player from admin."""

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
        player: str,
    ) -> CommandResult:
        """Execute demote command."""
        logger.info("handler_invoked", handler="DemoteCommandHandler", user=interaction.user.name, player=player)
        logger.info(
            "handler_invoked",
            handler="DemoteCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await rcon_client.execute(f"/demote {player}")

            embed = discord.Embed(
                title="📙 Player Demoted",
                color=self.embed_builder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Role", value="Player", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "player_demoted",
                player=player,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("demote_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to demote player: {str(e)}"
                ),
                ephemeral=True,
            )


# ═════════════════════════════════════════════════════════════════════════════
# 🔧 SERVER MANAGEMENT HANDLERS (4)
# ═════════════════════════════════════════════════════════════════════════════


class SaveCommandHandler:
    """Save the game."""

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
        name: Optional[str] = None,
    ) -> CommandResult:
        """Execute save command."""
        logger.info("handler_invoked", handler="SaveCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="SaveCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            save_name=name,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            cmd = f"/save {name}" if name else "/save"
            resp = await rcon_client.execute(cmd)

            # Parse save name from response
            if name:
                label = name
            else:
                match = re.search(r"/([^/]+?)\.zip", resp)
                if match:
                    label = match.group(1)
                else:
                    match = re.search(r"Saving (?:map )?to ([\w-]+)", resp)
                    label = match.group(1) if match else "current save"

            embed = self.embed_builder.info_embed(
                title="💾 Game Saved",
                message=f"Save name: **{label}**\n\nServer response:\n{resp}",
            )
            embed.color = self.embed_builder.COLOR_SUCCESS

            logger.info(
                "game_saved",
                save_name=label,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("save_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Failed to save game: {str(e)}"),
                ephemeral=True,
            )


class BroadcastCommandHandler:
    """Send message to all players."""

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
        message: str,
    ) -> CommandResult:
        """Execute broadcast command."""
        logger.info("handler_invoked", handler="BroadcastCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="BroadcastCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            message_length=len(message),
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            escaped_msg = message.replace('"', '\\"')
            await rcon_client.execute(f'/sc game.print("[color=pink]{escaped_msg}[/color]")')

            embed = self.embed_builder.info_embed(
                title="📢 Broadcast Sent",
                message=f"Message: _{message}_\n\nAll online players have been notified.",
            )
            embed.color = self.embed_builder.COLOR_SUCCESS

            logger.info(
                "message_broadcast",
                message=message,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("broadcast_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Broadcast failed: {str(e)}"),
                ephemeral=True,
            )


class WhisperCommandHandler:
    """Send private message to player."""

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
        player: str,
        message: str,
    ) -> CommandResult:
        """Execute whisper command."""
        logger.info("handler_invoked", handler="WhisperCommandHandler", user=interaction.user.name, player=player)
        logger.info(
            "handler_invoked",
            handler="WhisperCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await rcon_client.execute(f"/whisper {player} {message}")

            embed = discord.Embed(
                title="💬 Private Message Sent",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Message", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "whisper_sent",
                player=player,
                message=message[:50],
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("whisper_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Failed to send message: {str(e)}"),
                ephemeral=True,
            )


class WhitelistCommandHandler:
    """Manage server whitelist (multi-action: add/remove/list/enable/disable)."""

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
        action: str,
        player: Optional[str] = None,
    ) -> CommandResult:
        """Execute whitelist command with multi-action dispatch."""
        logger.info("handler_invoked", handler="WhitelistCommandHandler", user=interaction.user.name, action=action)
        logger.info(
            "handler_invoked",
            handler="WhitelistCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            action=action,
            target_player=player,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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

        action_lower = action.lower().strip()
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            if action_lower == "list":
                resp = await rcon_client.execute("/whitelist get")
                embed = self.embed_builder.info_embed(
                    title="📋 Whitelist", message=resp
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif action_lower == "enable":
                resp = await rcon_client.execute("/whitelist enable")
                embed = self.embed_builder.info_embed(
                    title="✅ Whitelist Enabled", message=resp
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif action_lower == "disable":
                resp = await rcon_client.execute("/whitelist disable")
                embed = self.embed_builder.info_embed(
                    title="⚠️ Whitelist Disabled", message=resp
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif action_lower == "add":
                if not player:
                    return CommandResult(
                        success=False,
                        error_embed=self.embed_builder.error_embed(
                            "Player name required for 'add' action"
                        ),
                        ephemeral=True,
                    )
                resp = await rcon_client.execute(f"/whitelist add {player}")
                embed = self.embed_builder.info_embed(
                    title=f"✅ {player} Added to Whitelist", message=resp
                )
                logger.info(
                    "whitelist_add", player=player, moderator=interaction.user.name
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif action_lower == "remove":
                if not player:
                    return CommandResult(
                        success=False,
                        error_embed=self.embed_builder.error_embed(
                            "Player name required for 'remove' action"
                        ),
                        ephemeral=True,
                    )
                resp = await rcon_client.execute(f"/whitelist remove {player}")
                embed = self.embed_builder.info_embed(
                    title=f"🚫 {player} Removed from Whitelist", message=resp
                )
                logger.info(
                    "whitelist_remove", player=player, moderator=interaction.user.name
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            else:
                return CommandResult(
                    success=False,
                    error_embed=self.embed_builder.error_embed(
                        f"Invalid action: {action}\n\nValid actions: add, remove, list, enable, disable"
                    ),
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(
                "whitelist_command_failed",
                error=str(e),
                action=action_lower,
                player=player,
            )
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"Whitelist command failed: {str(e)}"
                ),
                ephemeral=True,
            )


# ═════════════════════════════════════════════════════════════════════════════
# 🎮 GAME CONTROL HANDLERS (3)
# ═════════════════════════════════════════════════════════════════════════════


class ClockCommandHandler:
    """Set or display game daytime."""

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
        value: Optional[str] = None,
    ) -> CommandResult:
        """Execute clock command."""
        logger.info("handler_invoked", handler="ClockCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="ClockCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            value=value,
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
                ephemeral=True,
            )

        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)
        server_name = self.user_context.get_server_display_name(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            if value is None:
                # Display current daytime
                resp = await rcon_client.execute(
                    '/sc local daytime = game.surfaces["nauvis"].daytime; '
                    'local hours = math.floor(daytime * 24); '
                    'local minutes = math.floor((daytime * 24 - hours) * 60); '
                    'rcon.print(string.format("Current daytime: %.2f (🕐 %02d:%02d)", daytime, hours, minutes))'
                )
                embed = self.embed_builder.info_embed(
                    title="🕐 Current Game Clock", message=resp
                )
                return CommandResult(success=True, embed=embed, ephemeral=False)

            value_lower = value.lower().strip()

            if value_lower in ["day", "eternal-day"]:
                resp = await rcon_client.execute(
                    '/sc game.surfaces["nauvis"].daytime = 0.5; '
                    'game.surfaces["nauvis"].freeze_daytime = 0.5; '
                    'rcon.print("☀️ Set to eternal day (12:00)")'
                )
                embed = self.embed_builder.info_embed(
                    title="☀️ Eternal Day Set",
                    message="Game time is now permanently frozen at noon (12:00)\n\nServer response:\n"
                    + resp,
                )
                logger.info("eternal_day_set", moderator=interaction.user.name)
                return CommandResult(success=True, embed=embed, ephemeral=False)

            elif value_lower in ["night", "eternal-night"]:
                resp = await rcon_client.execute(
                    '/sc game.surfaces["nauvis"].daytime = 0.0; '
                    'game.surfaces["nauvis"].freeze_daytime = 0.0; '
                    'rcon.print("🌙 Set to eternal night (00:00)")'
                )
                embed = self.embed_builder.info_embed(
                    title="🌙 Eternal Night Set",
                    message="Game time is now permanently frozen at midnight (00:00)\n\nServer response:\n"
                    + resp,
                )
                logger.info("eternal_night_set", moderator=interaction.user.name)
                return CommandResult(success=True, embed=embed, ephemeral=False)

            else:
                try:
                    daytime_value = float(value_lower)
                    if not 0.0 <= daytime_value <= 1.0:
                        raise ValueError("Value must be between 0.0 and 1.0")

                    resp = await rcon_client.execute(
                        f'/sc game.surfaces["nauvis"].daytime = {daytime_value}; '
                        f'game.surfaces["nauvis"].freeze_daytime = nil; '
                        f'local hours = math.floor({daytime_value} * 24); '
                        f'local minutes = math.floor(({daytime_value} * 24 - hours) * 60); '
                        f'rcon.print(string.format("Set daytime to %.2f (🕐 %02d:%02d)", {daytime_value}, hours, minutes))'
                    )
                    time_desc = (
                        "noon"
                        if abs(daytime_value - 0.5) < 0.05
                        else ("midnight" if daytime_value < 0.05 else f"{daytime_value:.2f}")
                    )
                    embed = self.embed_builder.info_embed(
                        title="🕐 Game Clock Updated",
                        message=f"Game time set to: **{time_desc}**\n\nServer response:\n{resp}",
                    )
                    logger.info(
                        "daytime_set", value=daytime_value, moderator=interaction.user.name
                    )
                    return CommandResult(success=True, embed=embed, ephemeral=False)

                except ValueError:
                    return CommandResult(
                        success=False,
                        error_embed=self.embed_builder.error_embed(
                            f"Invalid time value: {value}\n\nValid formats:\n"
                            f"- 'day' or 'eternal-day' → Eternal noon\n"
                            f"- 'night' or 'eternal-night' → Eternal midnight\n"
                            f"- 0.0-1.0 → Custom time (0=midnight, 0.5=noon)"
                        ),
                        ephemeral=True,
                    )

        except Exception as e:
            logger.error("clock_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Clock command failed: {str(e)}"),
                ephemeral=True,
            )


class SpeedCommandHandler:
    """Set game speed."""

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
        value: float,
    ) -> CommandResult:
        """Execute speed command."""
        logger.info("handler_invoked", handler="SpeedCommandHandler", user=interaction.user.name, speed=speed)
        logger.info(
            "handler_invoked",
            handler="SpeedCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            speed=value,
        )

        # Validate range
        if not 0.1 <= value <= 10.0:
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(
                    "Speed must be between 0.1 and 10.0"
                ),
                ephemeral=True,
            )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            await rcon_client.execute(f"/sc game.speed = {value}")

            embed = discord.Embed(
                title="⚡ Game Speed Set",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="New Speed", value=f"{value}x", inline=True)
            if value < 1.0:
                embed.add_field(name="Effect", value="⬋ Slower", inline=True)
            elif value > 1.0:
                embed.add_field(name="Effect", value="⬊ Faster", inline=True)
            else:
                embed.add_field(name="Effect", value="➡️ Normal", inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.set_footer(text="Action performed via Discord")

            logger.info(
                "game_speed_set",
                speed=value,
                moderator=interaction.user.name,
            )

            return CommandResult(success=True, embed=embed, ephemeral=False)

        except Exception as e:
            logger.error("speed_command_failed", error=str(e))
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.error_embed(f"Failed to set speed: {str(e)}"),
                ephemeral=True,
            )


class ResearchCommandHandler:
    """Handler for /factorio research with multi-force support."""

    def __init__(
        self,
        user_context: UserContextProvider,
        cooldown: RateLimiter,
        embed_builder: EmbedBuilderType,
    ):
        self.user_context = user_context
        self.cooldown = cooldown
        self.embed_builder = embed_builder

    async def execute(
        self,
        interaction: discord.Interaction,
        force: Optional[str],
        action: Optional[str],
        technology: Optional[str],
    ) -> CommandResult:
        """Execute research command with multi-force support."""
        logger.info("handler_invoked", handler="ResearchCommandHandler", user=interaction.user.name, force=force)
        logger.info(
            "handler_invoked",
            handler="ResearchCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            force=force,
            action=action,
        )

        # Rate limiting
        is_limited, retry = self.cooldown.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=False,
            )

        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = self.embed_builder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            # Resolve target force (default to "player" for Coop)
            target_force = (force.lower().strip() if force else None) or "player"

            # MODE 1: Display status (no action)
            if action is None:
                result = await self._handle_status(rcon_client, target_force)
                return result

            action_lower = action.lower().strip()

            # MODE 2: Research all
            if action_lower == "all" and technology is None:
                result = await self._handle_research_all(rcon_client, target_force)
                return result

            # MODE 3: Undo operations
            if action_lower == "undo":
                result = await self._handle_undo(rcon_client, target_force, technology)
                return result

            # MODE 4: Research single technology
            if technology is None:
                tech_name = action_lower
            else:
                tech_name = technology.strip()

            result = await self._handle_research_single(rcon_client, target_force, tech_name)
            return result

        except Exception as e:
            embed = self.embed_builder.error_embed(
                f"Research command failed: {str(e)}"
            )
            logger.error("research_command_failed", error=str(e), force=force)
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )

    async def _handle_status(
        self, rcon_client: RconClientProvider, target_force: str
    ) -> CommandResult:
        """Query research progress for a force."""
        resp = await rcon_client.execute(
            f"/sc "
            f"local researched = 0; "
            f"local total = 0; "
            f"for _, tech in pairs(game.forces[\"{target_force}\"].technologies) do "
            f" total = total + 1; "
            f" if tech.researched then researched = researched + 1 end; "
            f"end; "
            f'rcon.print(string.format("%d/%d", researched, total))'
        )

        researched_count = "0/0"
        try:
            parts = resp.strip().split("/")
            if len(parts) == 2:
                researched_count = resp.strip()
        except (ValueError, IndexError):
            logger.warning("research_status_parse_failed", response=resp, force=target_force)

        message = (
            f"Force: **{target_force}**\n"
            f"Technologies researched: **{researched_count}**\n\n"
            f"Use `/factorio research {target_force if target_force != 'player' else ''}all` to research all.\n"
            f"Or `/factorio research {target_force + ' ' if target_force != 'player' else ''}<tech-name>` for specific tech."
        )

        embed = self.embed_builder.info_embed(
            title="🔬 Technology Status", message=message
        )

        logger.info("research_status_checked", force=target_force)

        return CommandResult(
            success=True,
            embed=embed,
            ephemeral=False,
            followup=True,
        )

    async def _handle_research_all(
        self, rcon_client: RconClientProvider, target_force: str
    ) -> CommandResult:
        """Research all technologies for a force."""
        await rcon_client.execute(
            f'/sc game.forces["{target_force}"].research_all_technologies(); '
            f'rcon.print("All technologies researched")'
        )

        message = (
            f"Force: **{target_force}**\n\n"
            f"All technologies have been instantly unlocked!\n\n"
            f"{target_force.capitalize()} force can now access all previously locked content."
        )

        embed = self.embed_builder.info_embed(
            title="🔬 All Technologies Researched", message=message
        )
        embed.color = self.embed_builder.COLOR_SUCCESS

        logger.info("all_technologies_researched", force=target_force)

        return CommandResult(
            success=True,
            embed=embed,
            ephemeral=False,
            followup=True,
        )

    async def _handle_undo(
        self, rcon_client: RconClientProvider, target_force: str, technology: Optional[str]
    ) -> CommandResult:
        """Undo research (all or single technology)."""
        if technology is None or technology.lower().strip() == "all":
            # Undo all
            await rcon_client.execute(
                f'/sc '
                f'for _, tech in pairs(game.forces["{target_force}"].technologies) do '
                f' tech.researched = false; '
                f'end; '
                f'rcon.print("All technologies reverted")'
            )

            message = (
                f"Force: **{target_force}**\n\n"
                f"All technology research has been undone!\n\n"
                f"{target_force.capitalize()} force must re-research technologies from scratch."
            )

            embed = self.embed_builder.info_embed(
                title="⏮️ All Technologies Reverted", message=message
            )
            embed.color = self.embed_builder.COLOR_WARNING

            logger.info("all_technologies_reverted", force=target_force)

            return CommandResult(
                success=True,
                embed=embed,
                ephemeral=False,
                followup=True,
            )

        # Undo single
        tech_name = technology.strip()
        try:
            await rcon_client.execute(
                f'/sc game.forces["{target_force}"].technologies["{tech_name}"].researched = false; '
                f'rcon.print("Technology reverted: {tech_name}")'
            )

            message = (
                f"Force: **{target_force}**\n"
                f"Technology: **{tech_name}**\n\n"
                f"Technology has been undone."
            )

            embed = self.embed_builder.info_embed(
                title="⏮️ Technology Reverted", message=message
            )
            embed.color = self.embed_builder.COLOR_WARNING

            logger.info("technology_reverted", technology=tech_name, force=target_force)

            return CommandResult(
                success=True,
                embed=embed,
                ephemeral=False,
                followup=True,
            )

        except Exception as e:
            embed = self.embed_builder.error_embed(
                f"Failed to revert technology: {str(e)}\n\n"
                f"Force: `{target_force}`\n"
                f"Technology: `{tech_name}`\n\n"
                f"Verify the force exists and technology name is correct\n"
                f"(e.g., automation-2, logistics-3, steel-processing)"
            )
            logger.error(
                "research_undo_failed",
                technology=tech_name,
                force=target_force,
                error=str(e),
            )
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )

    async def _handle_research_single(
        self, rcon_client: RconClientProvider, target_force: str, tech_name: str
    ) -> CommandResult:
        """Research a single technology."""
        try:
            await rcon_client.execute(
                f'/sc game.forces["{target_force}"].technologies["{tech_name}"].researched = true; '
                f'rcon.print("Technology researched: {tech_name}")'
            )

            message = (
                f"Force: **{target_force}**\n"
                f"Technology: **{tech_name}**\n\n"
                f"Technology has been researched."
            )

            embed = self.embed_builder.info_embed(
                title="🔬 Technology Researched", message=message
            )
            embed.color = self.embed_builder.COLOR_SUCCESS

            logger.info("technology_researched", technology=tech_name, force=target_force)

            return CommandResult(
                success=True,
                embed=embed,
                ephemeral=False,
                followup=True,
            )

        except Exception as e:
            embed = self.embed_builder.error_embed(
                f"Failed to research technology: {str(e)}\n\n"
                f"Force: `{target_force}`\n"
                f"Technology: `{tech_name}`\n\n"
                f"Valid examples: automation-2, logistics-3, steel-processing, electric-furnace\n\n"
                f"Use `/factorio research {target_force if target_force != 'player' else ''}` to see progress."
            )
            logger.error(
                "research_command_failed",
                technology=tech_name,
                force=target_force,
                error=str(e),
            )
            return CommandResult(
                success=False,
                embed=embed,
                ephemeral=True,
                followup=True,
            )


# ═════════════════════════════════════════════════════════════════════════════
# 🛠️ ADVANCED HANDLERS (2)
# ═════════════════════════════════════════════════════════════════════════════


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
        logger.info("handler_invoked", handler="RconCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="RconCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            command=command[:50],
        )

        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(int(retry or 0))
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return CommandResult(
                success=False,
                error_embed=self.embed_builder.cooldown_embed(int(retry or 0)),
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
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            result = await rcon_client.execute(command)

            embed = discord.Embed(
                title="⌨️ RCON Command Executed",
                color=self.embed_builder.COLOR_SUCCESS,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Command", value=command, inline=False)
            if result:
                result_text = result if len(result) < 1024 else result[:1021] + "..."
                embed.add_field(
                    name="Response", value=result_text, inline=False
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


class HelpCommandHandler:
    """Show help message."""

    def __init__(self, embed_builder_type: type[EmbedBuilderType]):
        self.embed_builder = embed_builder_type

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute help command."""
        logger.info("handler_invoked", handler="HelpCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="HelpCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
        )

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


# ═════════════════════════════════════════════════════════════════════════════
# 🌍 MULTI-SERVER HANDLERS (2)
# ═════════════════════════════════════════════════════════════════════════════


class ServersCommandHandler:
    """List multi-server information."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        embed_builder_type: type[EmbedBuilderType],
        server_manager: Optional[ServerManagerProvider],
    ):
        self.user_context = user_context_provider
        self.embed_builder = embed_builder_type
        self.server_manager = server_manager

    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute servers command."""
        logger.info("handler_invoked", handler="ServersCommandHandler", user=interaction.user.name)
        logger.info(
            "handler_invoked",
            handler="ServersCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
        )

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


class ConnectCommandHandler:
    """Switch user to a different server."""

    def __init__(
        self,
        user_context_provider: UserContextProvider,
        embed_builder_type: type[EmbedBuilderType],
        server_manager: Optional[ServerManagerProvider],
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
        logger.info("handler_invoked", handler="ConnectCommandHandler", user=interaction.user.name, server=server)
        logger.info(
            "handler_invoked",
            handler="ConnectCommandHandler",
            user=interaction.user.name,
            user_id=interaction.user.id,
            target_server=server,
        )

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
