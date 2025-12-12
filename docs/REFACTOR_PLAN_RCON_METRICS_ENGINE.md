# 📋 RCON Metrics Engine Refactor Plan (Constraint-Aware)

**Date:** 2025-12-12  
**Status:** Phase 1 Ready for Implementation  
**Branch:** `refactor/rcon-metrics-engine`  
**Scope:** Eliminate god-object anti-patterns while preserving parallel connection architecture

---

## 🔒 Critical Constraint

This plan **MUST preserve** the parallel connection model:
- ✅ Per-server `RconClient` instantiation (servers.yml → parallel connections)
- ✅ Persistent in-memory connection binding (1 client = 1 server, no switching)
- ✅ `use_context()` for labeling (NOT connection switching)
- ✅ `/factorio servers` and `/factorio connect` commands
- ✅ Independent stats collection per server

See `rcon-parallel-arch-constraint.md` for locked architectural details.

---

## Merged Metrics Service Model (Option B)

**Key Architecture Decision:** Both `RconStatsCollector` and `RconAlertMonitor` consume from **one shared `RconMetricsEngine` instance per server**.

```
ServerManager["prod"]
  ├─ client["prod"] → RconClient(1.1.1.1:27015)
  │
  ├─ metrics_engine["prod"] → RconMetricsEngine (shared)
  │   ├─ Owns: UPSCalculator, EMA/SMA state, evolution parsing
  │   └─ Provides: sample_ups(), get_evolution_by_surface(), gather_all_metrics()
  │
  ├─ stats_collector["prod"] ──┐
  │   └─ Loop every 30s        ├─ Both call engine methods
  │      └─ Gather → Format → Send      separately on their
  │                            own schedules
  └─ alert_monitor["prod"] ───┘
       └─ Loop every 60s
          └─ Sample → Logic → Alert
```

**Why Merged:**
- Single source of truth for EMA/SMA state
- Shared pause detection (consistent across both)
- Easy to add more consumers (web API, CSV exporter, etc.)
- Stats and alerts remain **independent** (different loop intervals, decision logic)

---

## Current God-Object Anti-Patterns

| Anti-Pattern | Current State | Impact | Fix |
|---|---|---|---|
| **Protocol ↔ Stats coupling** | `RconStatsCollector` owns stats + formatting | Mixed concerns | Extract `RconMetricsEngine` |
| **Duplicate EMA/SMA state** | Both collector + alert monitor track separately | Inconsistent decisions | Shared engine state |
| **Duplicate UPSCalculator** | Two instances, separate pause state | Memory waste, inconsistency | One instance in engine |
| **Lua parsing buried** | Evolution logic mixed with collection | Hard to reuse/test | Extract to engine method |
| **Discord embed inside metrics** | `_format_stats_embed()` in collector | Tight coupling | Move to helpers.py |

---

## Phase 1: Extract RconMetricsEngine (P1 - DO FIRST)

**Scope:** New class consolidating all metrics computation; no breaking changes to external API.

### What Gets Extracted into RconMetricsEngine

```python
class RconMetricsEngine:
    """
    Unified metrics computation layer.
    - Owns: UPSCalculator, EMA/SMA tracking, evolution parsing
    - Provides: Single-shot async methods (no internal loops)
    - Used by: RconStatsCollector, RconAlertMonitor
    """
    
    def __init__(self, rcon_client: RconClient, ema_alpha: float = 0.2):
        self.rcon_client = rcon_client  # 1:1 binding
        self.ups_calculator = UPSCalculator(...)  # Single instance
        self.ema_alpha = ema_alpha
        self.ema_ups: Optional[float] = None
        self._ups_samples_for_sma: List[float] = []
    
    async def sample_ups(self) -> Dict[str, Any]:
        """
        Execute one UPS sample and update EMA/SMA state.
        Returns: {
            'raw_ups': float | None,
            'ema_ups': float (updated),
            'sma_ups': float,
            'is_paused': bool,
            'last_known_ups': float | None,
        }
        """
        ...implementation...
    
    async def get_evolution_by_surface(self) -> Dict[str, float]:
        """Parse evolution per surface from Lua."""
        ...implementation...
    
    async def get_players(self) -> List[str]:
        """Get player list."""
        ...implementation...
    
    async def get_player_count(self) -> int:
        """Get player count."""
        ...implementation...
    
    async def get_server_time(self) -> str:
        """Get server game time."""
        ...implementation...
    
    async def gather_all_metrics(self) -> Dict[str, Any]:
        """
        Gather all metrics in one batch call.
        Used by: RconStatsCollector.gather_and_post()
        """
        ...implementation...
```

### What Changes in RconStatsCollector

```python
class RconStatsCollector:
    """Thin orchestrator: gather → format → send (no metrics computation)."""
    
    def __init__(
        self,
        rcon_client: RconClient,
        metrics_engine: RconMetricsEngine,  # NEW: shared
        discord_interface: Any,
        interval: int = 30,
    ):
        self.rcon_client = rcon_client
        self.metrics_engine = metrics_engine  # Use shared instance
        self.discord_interface = discord_interface
        self.interval = interval
        self.task: Optional[asyncio.Task] = None
    
    async def _collection_loop(self) -> None:
        """Poll metrics on interval."""
        while self.rcon_client.is_connected:
            await asyncio.sleep(self.interval)
            
            # Call shared engine
            metrics = await self.metrics_engine.gather_all_metrics()
            
            # Format and send
            embed = format_stats_embed(metrics)
            await self.discord_interface.send_embed(embed)
```

### Implementation Checklist

- [ ] Create `RconMetricsEngine` class in `rcon_client.py`
- [ ] Extract `UPSCalculator` instantiation into engine
- [ ] Move EMA/SMA tracking into engine
- [ ] Move evolution Lua parsing into `get_evolution_by_surface()`
- [ ] Move player queries into `get_players()`, `get_player_count()`
- [ ] Move server time query into `get_server_time()`
- [ ] Implement `gather_all_metrics()` combining all above
- [ ] Update `RconStatsCollector.__init__()` to accept `metrics_engine`
- [ ] Update `RconStatsCollector._collection_loop()` to use engine
- [ ] Verify existing stats tests still pass
- [ ] **Do NOT touch:** `use_context()`, connection logic, parallel instantiation

**Estimated LOC:**
- `+200` RconMetricsEngine class
- `-80` duplication removed from RconStatsCollector
- **Net: +120**

**Risk:** 🟢 Low (metrics computation unchanged, just reorganized)

---

## Phase 2: Extract Formatters to Helpers (P2 - AFTER P1)

**Scope:** Move `_format_stats_embed()` and `_format_stats_text()` to standalone functions.

### What Gets Extracted

```python
# In bot/helpers.py

def format_stats_embed(
    server_label: str,
    metrics: Dict[str, Any],
) -> discord.Embed:
    """Pure formatting; no RCON, no state."""
    ...implementation from RconStatsCollector...
    return embed

def format_stats_text(
    server_label: str,
    metrics: Dict[str, Any],
) -> str:
    """Pure formatting; no RCON, no state."""
    ...implementation from RconStatsCollector...
    return "\n".join(lines)
```

### What Changes in RconStatsCollector

```python
async def _collection_loop(self) -> None:
    while self.rcon_client.is_connected:
        await asyncio.sleep(self.interval)
        
        metrics = await self.metrics_engine.gather_all_metrics()
        
        # Call pure formatter function
        embed = format_stats_embed(
            server_label=metrics['server_name'],
            metrics=metrics,
        )
        await self.discord_interface.send_embed(embed)
```

**Benefits:** Formatters reusable from slash commands, testable in isolation.

**Risk:** 🟢 Low (pure refactoring)

---

## Phase 3: Unify Alert Monitoring (P3 - AFTER P1)

**Scope:** Refactor `RconAlertMonitor` to use shared `RconMetricsEngine`.

### What Changes

```python
class RconAlertMonitor:
    def __init__(
        self,
        rcon_client: RconClient,
        metrics_engine: RconMetricsEngine,  # NEW: shared
        discord_interface: Any,
        check_interval: int = 60,
        ...
    ):
        self.rcon_client = rcon_client
        self.metrics_engine = metrics_engine  # Use shared
        self.discord_interface = discord_interface
        self.check_interval = check_interval
        self.alert_state = {  # Decision state only
            'low_ups_active': False,
            'consecutive_bad_samples': 0,
        }
    
    async def _check_ups(self) -> None:
        """Check UPS using shared engine."""
        ups_data = await self.metrics_engine.sample_ups()  # Shared call
        
        if ups_data['is_paused']:
            self.alert_state['consecutive_bad_samples'] = 0
            return
        
        # Apply trigger logic to shared EMA
        if ups_data['ema_ups'] < self.ups_warning_threshold:
            self.alert_state['consecutive_bad_samples'] += 1
            if self.alert_state['consecutive_bad_samples'] >= 3:
                await self._send_alert(ups_data)
```

### What Gets Removed

- `self.ups_calculator` (now in engine)
- `self.ema_alpha`, `self.ema_ups` (now in engine)
- Duplicate UPSCalculator instantiation
- Duplicate EMA tracking logic

**Risk:** 🟡 Medium (changes alert decision flow, requires careful testing)

---

## Summary: Phase Breakdown

| Phase | What | Why | LOC | Risk | Priority |
|-------|------|-----|-----|------|----------|
| **P1** | Extract `RconMetricsEngine` | Single UPS source, shared EMA/SMA | +120 | 🟢 Low | **1st** |
| **P2** | Extract formatters to helpers | Reusable, testable formatting | 0 | 🟢 Low | 2nd |
| **P3** | Unify alert monitoring | Remove duplicate state | -80 | 🟡 Med | 3rd |

**Total Refactor:** ~+40 LOC (net), 3 phases, zero constraint violations.

---

## Expected Outcomes Post-Refactor

### Before
```
RconClient (protocol)
RconStatsCollector (owns metrics + formatting)
  ├─ UPSCalculator (pause detection)
  ├─ EMA/SMA state
  └─ Format embed/text methods

RconAlertMonitor (owns metrics + alert logic)
  ├─ UPSCalculator (DUPLICATE!)
  ├─ EMA/SMA state (DUPLICATE!)
  └─ Alert logic
```

### After
```
RconClient (protocol)

RconMetricsEngine (metrics computation)
  ├─ UPSCalculator (single instance)
  ├─ EMA/SMA state (single source)
  └─ All query methods

RconStatsCollector (orchestrator: gather → format → send)
  └─ metrics_engine reference

RconAlertMonitor (decision logic)
  └─ metrics_engine reference (SHARED!)

Formatters (pure functions)
  ├─ format_stats_embed()
  └─ format_stats_text()
```

### Benefits
✅ **Single Responsibility:** Each class does one thing  
✅ **No Duplication:** Metrics computed once, used by two consumers  
✅ **Testability:** Mock one engine, test collector + monitor independently  
✅ **Consistency:** Stats and alerts use same EMA smoothing  
✅ **Reusability:** Formatters callable from slash commands, web API, etc.  
✅ **Parallelism Preserved:** Multi-server instantiation unchanged  
✅ **Independent Schedules:** Stats (30s) and alerts (60s) remain separate  

---

## Commit Strategy

```
Commit 1: Extract RconMetricsEngine (Phase 1)
  - New RconMetricsEngine class
  - Consolidate UPS, evolution, player logic
  - Update RconStatsCollector to use engine
  - All stats tests pass
  - Status: READY FOR MERGE

Commit 2: Extract Formatters (Phase 2)
  - Move format_stats_embed/text to bot/helpers.py
  - Update RconStatsCollector to call helpers
  - All stats tests pass
  - Status: READY FOR MERGE

Commit 3: Unify Alert Monitoring (Phase 3)
  - Update RconAlertMonitor to use shared engine
  - Remove duplicate UPS logic
  - All alert tests pass
  - Status: READY FOR MERGE

Final: Integration Test
  - Run full test suite
  - Verify multi-server stats collection works
  - Verify alerts still trigger correctly
  - Verify /factorio commands unchanged
```

---

## When to Start

🚀 **Phase 1 is ready.** No blockers, fully backward-compatible.

**Branch:** `refactor/rcon-metrics-engine` (already created)  
**Next:** Implement Phase 1, commit, PR for review.

