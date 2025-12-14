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
Command handlers with explicit dependency injection (POC).

This module demonstrates a cleaner architecture for testable Discord commands.
Each handler encapsulates business logic with explicit dependencies, making
unit testing straightforward without complex mocking of the bot object.

Handlers are instantiated in `register_factorio_commands()` with concrete
dependencies and delegated to by the Discord command closures.

Pattern:
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

from typing import Any, Dict, List, Optional, Protocol
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


class RconClientProvider(Protocol):
    """Interface for RCON command execution."""

    async def execute(self, command: str) -> str:
        """Execute RCON command and return response."""
        ...


class RateLimiter(Protocol):
    """Interface for rate limiting."""

    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[float]]:
        """Check if user is rate limited. Returns (is_limited, retry_after)."""
        ...


class EmbedBuilderType(Protocol):
    """Interface for embed building utilities."""

    COLOR_SUCCESS: int
    COLOR_WARNING: int
    COLOR_INFO: int
    COLOR_ADMIN: int

    @staticmethod
    def cooldown_embed(retry_after: Optional[float]) -> discord.Embed:
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


# ═════════════════════════════════════════════════════════════════════════════
# RESULT TYPES (Type-safe command outputs)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class CommandResult:
    """Base result type for all command handlers."""

    success: bool
    embed: discord.Embed
    ephemeral: bool = False
    followup: bool = False  # If True, use interaction.followup.send()


# ═════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS (Encapsulate business logic with DI)
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
        # Rate limiting
        is_limited, retry = self.cooldown.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(retry)
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
        # Rate limiting
        is_limited, retry = self.cooldown.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(retry)
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
        # Rate limiting
        is_limited, retry = self.cooldown.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = self.embed_builder.cooldown_embed(retry)
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
