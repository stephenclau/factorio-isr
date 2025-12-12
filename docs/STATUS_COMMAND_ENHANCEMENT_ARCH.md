# 🎯 Status Command Enhancement: Independent Metrics Collection

## Executive Summary

The `/factorio status` command currently displays only **basic player and uptime data**. You want it to independently capture the **same comprehensive stats** collected by `RconStatsCollector` (UPS, evolution, players, etc.) using the shared `RconMetricsEngine`.

**Key Design Principle:** The status command should execute **on-demand** while stats collector runs **periodically**. Both use the same metrics engine to ensure consistency.

---

## Current Architecture Analysis

### Current Status Command (factorio.py, ~Line 430)

```python
@factorio_group.command(name="status", description="Show Factorio server status")
async def status_command(interaction: discord.Interaction) -> None:
    # Collects:
    # - Players (via /players RCON command)
    # - Uptime (from rcon_monitor.rcon_server_states)
    # 
    # Missing:
    # - UPS (current, SMA, EMA)
    # - Evolution factor (per-surface)
    # - Pause state
    # - Game tick / time
```

### Current RconStatsCollector (rcon_stats_collector.py)

```python
class RconStatsCollector:
    def __init__(self, rcon_client, discord_interface, 
                 metrics_engine=None, ...):
        # Uses RconMetricsEngine for gathering:
        # - gather_all_metrics() → returns comprehensive dict
        #   ├─ ups, ups_sma, ups_ema
        #   ├─ is_paused, last_known_ups
        #   ├─ player_count, players[], server_time
        #   ├─ evolution_factor, evolution_by_surface
        #   └─ tick, game_time_seconds
```

### RconMetricsEngine Architecture (rcon_metrics_engine.py)

```python
class RconMetricsEngine:
    async def gather_all_metrics() -> Dict[str, Any]:
        # Single method returns COMPLETE metrics dict
        # - Creates/maintains UPSCalculator instance
        # - Maintains EMA/SMA smoothing state
        # - Samples UPS with pause detection
        # - Collects evolution per-surface
        # - Gets player list, player count, server time
        # - Returns immediately (no periodic delays)
```

---

## Proposed Enhancement: Three-Tier Architecture

### 🎯 **Tier 1: RconMetricsEngine** (Unchanged)
**Single Source of Truth for Metrics**
- Per-server instance (1:1 binding with RconClient)
- Maintains internal EMA/SMA state
- `gather_all_metrics()` returns complete dictionary
- Called by BOTH status command and stats collector

### 🎯 **Tier 2: Status Command** (Enhanced)
**On-Demand Immediate Metrics Display**
```python
@factorio_group.command(name="status")
async def status_command(interaction):
    rcon_client = bot.user_context.get_rcon_for_user(user_id)
    
    # ✨ NEW: Get/create metrics engine for this server
    metrics_engine = bot.server_manager.get_metrics_engine(server_tag)
    
    # ✨ NEW: Call gather_all_metrics() on-demand
    metrics = await metrics_engine.gather_all_metrics()
    
    # Now metrics dict contains:
    # - ups, ups_sma, ups_ema
    # - is_paused, last_known_ups
    # - player_count, players
    # - evolution_factor, evolution_by_surface
    # - tick, game_time_seconds, server_time
    # - ... (all fields)
    
    # Format rich embed with all metrics
    embed = discord.Embed(...)
    embed.add_field("⚡ UPS", f"{metrics['ups']:.1f} (EMA: {metrics['ups_ema']:.1f})")
    embed.add_field("⏸️ Paused", "Yes" if metrics['is_paused'] else "No")
    embed.add_field("🐛 Evolution", f"{metrics['evolution_factor']*100:.1f}%")
    # ...
```

### 🎯 **Tier 3: Stats Collector** (Unchanged)
**Periodic Background Collection**
- Same `RconMetricsEngine.gather_all_metrics()` call
- Runs on interval (e.g., 300s)
- Posts to Discord periodically
- Uses same `RconStatsCollector` class

---

## Implementation Strategy

### **Step 1: Expose Metrics Engine in ServerManager**

**File:** `src/server_manager.py`

```python
class ServerManager:
    def __init__(self, ...):
        self.clients = {}  # RconClient instances
        self.metrics_engines = {}  # ✨ NEW: Per-server metrics engines
    
    def get_metrics_engine(self, server_tag: str) -> Optional[RconMetricsEngine]:
        """Get or create metrics engine for server."""
        if server_tag not in self.metrics_engines:
            client = self.clients.get(server_tag)
            if not client:
                return None
            # Create new engine, storing in dict
            self.metrics_engines[server_tag] = RconMetricsEngine(
                rcon_client=client,
                enable_ups_stat=True,
                enable_evolution_stat=True,
            )
        return self.metrics_engines[server_tag]
```

### **Step 2: Update Status Command**

**File:** `src/bot/commands/factorio.py` (Status Command, ~Line 430)

```python
@factorio_group.command(name="status", description="Show Factorio server status")
async def status_command(interaction: discord.Interaction) -> None:
    """Enhanced: Get comprehensive server status with metrics."""
    is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
    if is_limited:
        embed = EmbedBuilder.cooldown_embed(retry)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer()

    server_tag = bot.user_context.get_user_server(interaction.user.id)
    server_name = bot.user_context.get_server_display_name(interaction.user.id)

    rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)
    if rcon_client is None or not rcon_client.is_connected:
        embed = EmbedBuilder.error_embed(
            f"RCON not available for {server_name}.\n"
            "Use `/factorio servers` to see available servers."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    try:
        # ✨ NEW: Get metrics engine and gather comprehensive metrics
        metrics_engine = bot.server_manager.get_metrics_engine(server_tag)
        if metrics_engine is None:
            raise RuntimeError(f"Metrics engine not available for {server_tag}")
        
        metrics = await metrics_engine.gather_all_metrics()

        # Get uptime (existing logic)
        uptime_text = "Unknown"
        state = bot.rcon_monitor.rcon_server_states.get(server_tag)
        last_connected = state.get("last_connected") if state else None
        if last_connected is not None:
            uptime_delta = datetime.now(timezone.utc) - last_connected
            days = int(uptime_delta.total_seconds()) // 86400
            hours = (int(uptime_delta.total_seconds()) % 86400) // 3600
            minutes = (int(uptime_delta.total_seconds()) % 3600) // 60
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0 or (days == 0 and hours == 0):
                parts.append(f"{minutes}m")
            uptime_text = " ".join(parts) if parts else "< 1m"

        # ✨ Build rich embed with comprehensive metrics
        embed = EmbedBuilder.create_base_embed(
            title=f"🏭 {server_name} Status",
            color=(
                EmbedBuilder.COLOR_SUCCESS
                if rcon_client.is_connected
                else EmbedBuilder.COLOR_WARNING
            ),
        )

        # Bot and RCON status
        bot_online = bot._connected
        bot_status = "🟢 Online" if bot_online else "🔴 Offline"
        embed.add_field(name="🤖 Bot Status", value=bot_status, inline=True)
        embed.add_field(
            name="🔧 RCON",
            value="🟢 Connected" if rcon_client.is_connected else "🔴 Disconnected",
            inline=True,
        )
        embed.add_field(
            name="⏱️ Uptime",
            value=uptime_text,
            inline=True,
        )

        # ✨ Performance Metrics (from metrics engine)
        pause_indicator = "⏸️" if metrics.get("is_paused") else "▶️"
        if metrics.get("ups") is not None:
            ups_str = f"{metrics['ups']:.1f}"
            embed.add_field(
                name="⚡ UPS (Current)",
                value=f"{pause_indicator} {ups_str}",
                inline=True,
            )
        
        if metrics.get("ups_sma") is not None:
            embed.add_field(
                name="📊 UPS (SMA)",
                value=f"{metrics['ups_sma']:.1f}",
                inline=True,
            )
        
        if metrics.get("ups_ema") is not None:
            embed.add_field(
                name="📈 UPS (EMA)",
                value=f"{metrics['ups_ema']:.1f}",
                inline=True,
            )

        # ✨ Evolution Factor (from metrics engine)
        if metrics.get("evolution_factor") is not None:
            evo_pct = metrics["evolution_factor"] * 100
            evo_icon = "🐛"
            embed.add_field(
                name="🐛 Enemy Evolution",
                value=f"{evo_pct:.1f}%",
                inline=True,
            )

        # Players (from metrics engine)
        player_count = metrics.get("player_count", 0)
        embed.add_field(
            name="👥 Players Online",
            value=str(player_count),
            inline=True,
        )

        # Game time (from metrics engine)
        if metrics.get("server_time"):
            embed.add_field(
                name="🕐 Server Time",
                value=metrics["server_time"],
                inline=True,
            )

        # Online players list (if any)
        players = metrics.get("players", [])
        if players:
            player_list = "\n".join(f"• {name}" for name in players[:10])
            if len(players) > 10:
                player_list += f"\n... and {len(players) - 10} more"
            embed.add_field(
                name="👥 Online Players",
                value=player_list,
                inline=False,
            )

        embed.set_footer(text="Factorio ISR | Metrics via RconMetricsEngine")
        await interaction.followup.send(embed=embed)
        logger.info(
            "status_command_executed",
            user=interaction.user.name,
            server_tag=server_tag,
            has_metrics=True,
            ups=metrics.get("ups"),
            evolution=metrics.get("evolution_factor"),
        )
    except Exception as e:
        embed = EmbedBuilder.error_embed(f"Failed to get status: {str(e)}")
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error("status_command_failed", error=str(e), exc_info=True)
```

### **Step 3: Update Bot Initialization**

**File:** `src/discord_bot.py` (In `__init__` or setup method)

```python
class DiscordBot(discord.Client):
    def __init__(self, ...):
        # ...
        self.server_manager = None  # Already exists
        
        # ✨ When initializing RconStatsCollector, pass shared engine:
        if bot.server_manager:
            for server_tag in bot.server_manager.list_tags():
                rcon_client = bot.server_manager.get_client(server_tag)
                if rcon_client:
                    # Create shared metrics engine
                    metrics_engine = bot.server_manager.get_metrics_engine(server_tag)
                    
                    # Pass to stats collector
                    stats_collector = RconStatsCollector(
                        rcon_client=rcon_client,
                        discord_interface=self.discord_interface,
                        metrics_engine=metrics_engine,  # ✨ Shared instance
                        interval=300,
                        enable_ups_stat=True,
                        enable_evolution_stat=True,
                    )
```

---

## Benefits of This Architecture

| Benefit | Why It Matters |
|---------|----------------|
| **Single Source of Truth** | UPS, evolution, and smoothing state maintained in ONE place |
| **Consistency** | Status command and stats collector show identical metrics |
| **Resource Efficient** | Metrics engine maintains UPSCalculator (pause detection) for both uses |
| **On-Demand vs Periodic** | Status = immediate query, Stats Collector = background loop (different SLAs) |
| **Backward Compatible** | Existing RconStatsCollector unchanged; just gains shared engine |
| **Type-Safe** | All metrics flows through strongly-typed `RconMetricsEngine` |
| **Testable** | Metrics engine can be tested independently |

---

## Data Flow Comparison

### Before (Current)
```
User calls /factorio status
    ↓
status_command() executes:
    ├─ /players (RCON) → player list
    ├─ /uptime (from monitor state)
    └─ No UPS, evolution, or other metrics
    ↓
Returns limited embed

Stats Collector (periodic):
    ↓
RconStatsCollector.gather_all_metrics()
    ↓
RconMetricsEngine (internal)
    ├─ UPS calculation with pause detection
    ├─ Evolution per-surface
    ├─ EMA/SMA smoothing
    └─ Player data
    ↓
Posts to Discord every 300s
```

### After (Proposed)
```
User calls /factorio status
    ↓
status_command() executes:
    ├─ Get/create RconMetricsEngine for server
    ├─ Call engine.gather_all_metrics() immediately
    │   ├─ UPS calculation with pause detection
    │   ├─ Evolution per-surface
    │   ├─ EMA/SMA smoothing  
    │   ├─ Player data
    │   └─ Returns complete metrics dict
    └─ Format rich embed with all metrics
    ↓
Returns comprehensive embed (on-demand)

Stats Collector (periodic):
    ↓
RconStatsCollector._collect_and_post()
    ↓
Same RconMetricsEngine instance (shared!)
    ├─ Calls engine.gather_all_metrics()
    └─ Posts to Discord every 300s

✨ BOTH use identical metrics engine → guaranteed consistency
```

---

## Implementation Phases

### **Phase 1: Core Integration** (2-3 hours)
1. Update `ServerManager.get_metrics_engine()` method
2. Refactor status command to use metrics engine
3. Update bot initialization to create/share engines
4. Test with single server setup

### **Phase 2: Validation** (1-2 hours)
1. Unit tests for metrics engine reuse
2. Integration test: status command vs stats collector output
3. Multi-server validation
4. Test pause detection flow

### **Phase 3: Documentation** (30 mins)
1. Update architecture docs
2. Add inline code comments
3. Document metrics dict schema

---
## Code Examples: Key Changes

### ServerManager Addition

```python
# src/server_manager.py
from rcon_metrics_engine import RconMetricsEngine  # Import

class ServerManager:
    def __init__(self, ...):
        self.clients = {}  
        self.configs = {}
        self.metrics_engines = {}  # ✨ NEW
    
    def get_metrics_engine(self, server_tag: str) -> Optional[RconMetricsEngine]:
        """Lazy-load or return existing metrics engine for server."""
        if server_tag not in self.metrics_engines:
            client = self.clients.get(server_tag)
            if not client:
                return None
            self.metrics_engines[server_tag] = RconMetricsEngine(
                rcon_client=client,
                enable_ups_stat=True,
                enable_evolution_stat=True,
            )
        return self.metrics_engines[server_tag]
    
    def shutdown_metrics_engines(self):
        """Clean up metrics engines on shutdown."""
        self.metrics_engines.clear()
        logger.info("metrics_engines_shutdown")
```

### Status Command Skeleton

```python
# src/bot/commands/factorio.py - status_command

# Get metrics
metrics_engine = bot.server_manager.get_metrics_engine(server_tag)
metrics = await metrics_engine.gather_all_metrics()

# Build embed from metrics dict
embed.add_field(
    name="⚡ UPS (Current/EMA/SMA)",
    value=(
        f"{metrics.get('ups', 'N/A'):.1f} / "
        f"{metrics.get('ups_ema', 'N/A'):.1f} / "
        f"{metrics.get('ups_sma', 'N/A'):.1f}"
    ),
    inline=True,
)
```

---

## Quality Assurance Checklist

- [ ] Metrics engine successfully initialized per server in ServerManager
- [ ] Status command calls `gather_all_metrics()` on-demand
- [ ] Status command displays UPS (current, EMA, SMA)
- [ ] Status command displays evolution factor
- [ ] Status command displays pause state
- [ ] Stats collector receives shared metrics engine
- [ ] Stats collector output matches status command output (same metrics)
- [ ] Multi-server: each server has its own metrics engine instance
- [ ] Pause detection works in both status command and stats collector
- [ ] EMA/SMA smoothing consistent across both uses
- [ ] No performance regressions
- [ ] Type hints updated throughout
- [ ] Logging captures metrics gathered

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------||
| **Circular dependency** | ServerManager already owns RconClient; adding RconMetricsEngine is natural extension |
| **Metrics divergence** | Both status + stats use SAME engine instance → guaranteed consistency |
| **Resource leaks** | Metrics engines stored in ServerManager dict; cleaned on shutdown |
| **Performance spike** | gather_all_metrics() is async; UI remains responsive |
| **Backward compat** | Stats collector signature unchanged; just gains optional shared engine |

---

## Conclusion

This design enables the `/factorio status` command to **independently capture comprehensive metrics** while maintaining **perfect consistency** with the periodic stats collector through a **shared metrics engine**. 

The architecture respects existing principles:
- ✅ Per-server 1:1 RconClient binding
- ✅ Parallel instantiation model preserved
- ✅ Type-safe, extensible design
- ✅ Single source of truth (metrics engine)
- ✅ Clear separation: on-demand (status) vs periodic (stats)

**Timeline:** 3-5 hours for full implementation + testing
**Risk Level:** 🟢 LOW (additive, no breaking changes)
**Type Safety:** 🟢 MAINTAINED (all new code typed)
