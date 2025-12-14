# 🚀 Phase 2: Integration — From POC to Production

**Status**: Ready for implementation
**Scope**: Replace 3 closure-based commands with handler-based delegation
**Effort**: 2-3 hours (implementation + testing)
**Risk**: Low (closes closures, adds handlers, no breaking changes)

---

## 📋 Overview

You have:
- ✅ **3 handler classes** with explicit DI (StatusCommandHandler, EvolutionCommandHandler, ResearchCommand)
- ✅ **95%+ test coverage** (40+ tests)
- ✅ **Type-safe protocols** (UserContextProvider, etc.)
- ✅ **POC verified** to work in isolation

Phase 2 **integrates them into `factorio.py`**, replacing:
1. `/factorio status` (150+ lines) → StatusCommandHandler.execute()
2. `/factorio evolution <target>` (120+ lines) → EvolutionCommandHandler.execute()
3. `/factorio research [force] [action] [technology]` (180+ lines) → ResearchCommand.execute()

---

## ⚙️ Integration Pattern

### Before (Closure Capture)

```python
# 150 lines of inline logic mixed with Discord mechanics
@factorio_group.command(name="status", description="Show Factorio server status")
async def status_command(interaction: discord.Interaction) -> None:
    # Cooldown check
    is_limited, retry = QUERY_COOLDOWN.is_rate_limited(...)
    if is_limited:
        # Error handling
        ...
    
    await interaction.response.defer()
    
    # Get context (via implicit closure capture from bot)
    server_tag = bot.user_context.get_user_server(...)  # Hidden in closure!
    rcon_client = bot.user_context.get_rcon_for_user(...)  # Hidden!
    
    # 140 lines of logic here
    # Testing requires CommandExtractor + closure scope hacking
    # Coverage: ~70%
```

### After (Command Pattern + DI)

```python
# Step 1: Import handler
from bot.commands.command_handlers import StatusCommandHandler

# Step 2: Create at startup (Composition Root)
status_handler = StatusCommandHandler(
    user_context_provider=bot.user_context,
    server_manager_provider=bot.server_manager,
    rate_limiter=QUERY_COOLDOWN,
    embed_builder_type=EmbedBuilder,
)

# Step 3: Discord closure delegates (routing + mechanics only)
@factorio_group.command(name="status", description="Show Factorio server status")
async def status_command(interaction: discord.Interaction) -> None:
    # ✅ Explicit result object
    result = await status_handler.execute(interaction)
    
    # ✅ Consistent error handling
    if result.success:
        await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
    else:
        await interaction.followup.send(
            embed=result.error_embed,
            ephemeral=result.ephemeral,
        )
```

**Benefits**:
- ✅ Logic encapsulated in handler (150 lines → 1 line)
- ✅ Dependencies explicit (in handler.__init__)
- ✅ Testing direct (no closure scope hacks)
- ✅ Reusable (HTTP API, scheduled tasks)
- ✅ Type-safe (Protocols define contracts)

---

## 🛠️ Step-by-Step Integration

### Step 1: Import Handlers

**File**: `src/bot/commands/factorio.py` (top of file, after existing imports)

```python
# Add after existing imports
from bot.commands.command_handlers import (
    StatusCommandHandler,
    EvolutionCommandHandler,
    ResearchCommand,
)
```

### Step 2: Create Composition Root Function

**File**: `src/bot/commands/factorio.py` (add new function before `register_factorio_commands`)

```python
def _create_command_handlers(bot: Any) -> tuple[
    StatusCommandHandler,
    EvolutionCommandHandler,
    ResearchCommand,
]:
    """Composition Root: Wire command handlers with dependencies.
    
    This function instantiates all command handlers with real dependencies.
    Called once at bot startup to initialize handlers.
    
    Args:
        bot: DiscordBot instance with user_context, server_manager, rcon_monitor
        
    Returns:
        Tuple of (status_handler, evolution_handler, research_handler)
    """
    # Status Command Handler
    status_handler = StatusCommandHandler(
        user_context_provider=bot.user_context,
        server_manager_provider=bot.server_manager,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
        rcon_monitor=bot.rcon_monitor,  # For uptime calculation
    )
    
    # Evolution Command Handler
    evolution_handler = EvolutionCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    
    # Research Command Handler
    research_handler = ResearchCommand(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    
    logger.info(
        "command_handlers_initialized",
        handlers=["status", "evolution", "research"],
        phase="phase_2_integration",
    )
    
    return status_handler, evolution_handler, research_handler
```

### Step 3: Integrate Status Command

**File**: `src/bot/commands/factorio.py` (replace existing `@status_command` block)

**Location**: Around line 630 (after version, players commands)

**BEFORE** (150+ lines):
```python
@factorio_group.command(name="status", description="Show Factorio server status")
async def status_command(interaction: discord.Interaction) -> None:
    """Get comprehensive server status with rich embed including metrics."""
    is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
    if is_limited:
        embed = EmbedBuilder.cooldown_embed(retry)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # ... 140+ lines of logic ...
```

**AFTER** (5 lines):
```python
@factorio_group.command(name="status", description="Show Factorio server status")
async def status_command(interaction: discord.Interaction) -> None:
    """Get comprehensive server status with rich embed including metrics.
    
    Delegates to StatusCommandHandler for business logic.
    """
    result = await status_handler.execute(interaction)
    
    if result.success:
        await interaction.followup.send(
            embed=result.embed,
            ephemeral=result.ephemeral,
        )
    else:
        await interaction.followup.send(
            embed=result.error_embed,
            ephemeral=result.ephemeral,
        )
```

✅ **Result**: 150 lines → 12 lines of closure code

### Step 4: Integrate Evolution Command

**File**: `src/bot/commands/factorio.py` (replace existing `@evolution_command` block)

**Location**: Around line 900 (after seed command)

**BEFORE** (120+ lines):
```python
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
    """Get evolution for a surface or all surfaces."""
    # ... 120+ lines of Lua generation, parsing, formatting ...
```

**AFTER** (8 lines):
```python
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
    """Show evolution for a surface or all surfaces.
    
    Delegates to EvolutionCommandHandler for business logic.
    """
    result = await evolution_handler.execute(interaction, target=target)
    
    if result.success:
        await interaction.followup.send(
            embed=result.embed,
            ephemeral=result.ephemeral,
        )
    else:
        await interaction.followup.send(
            embed=result.error_embed,
            ephemeral=result.ephemeral,
        )
```

✅ **Result**: 120 lines → 15 lines of closure code

### Step 5: Integrate Research Command

**File**: `src/bot/commands/factorio.py` (replace existing `@research_command` block)

**Location**: Around line 1300 (last game control command)

**BEFORE** (180+ lines):
```python
@factorio_group.command(
    name="research",
    description="Manage technology research (Coop: player force, PvP: specify force)"
)
@app_commands.describe(...)
async def research_command(
    interaction: discord.Interaction,
    force: Optional[str] = None,
    action: Optional[str] = None,
    technology: Optional[str] = None,
) -> None:
    """Manage technology research with multi-force support."""
    # ... 180+ lines of parameter resolution, Lua generation, mode dispatch ...
```

**AFTER** (10 lines):
```python
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
    """Manage technology research with multi-force support.
    
    Delegates to ResearchCommand for business logic.
    """
    result = await research_handler.execute(
        interaction,
        force=force,
        action=action,
        technology=technology,
    )
    
    if result.success:
        await interaction.followup.send(
            embed=result.embed,
            ephemeral=result.ephemeral,
        )
    else:
        await interaction.followup.send(
            embed=result.error_embed,
            ephemeral=result.ephemeral,
        )
```

✅ **Result**: 180 lines → 26 lines of closure code

### Step 6: Update `register_factorio_commands` Function Signature

**File**: `src/bot/commands/factorio.py` (update function signature)

**BEFORE**:
```python
def register_factorio_commands(bot: Any) -> None:
    """Register all /factorio subcommands."""
    factorio_group = app_commands.Group(...)
    # ... all 17 commands here ...
    bot.tree.add_command(factorio_group)
```

**AFTER**:
```python
def register_factorio_commands(bot: Any) -> None:
    """Register all /factorio subcommands.
    
    This function:
    1. Creates command handlers (Composition Root)
    2. Registers Discord command group
    3. Wires closures to delegate to handlers
    
    Args:
        bot: DiscordBot instance with required attributes
    """
    # 🎯 Step 1: Initialize command handlers
    global status_handler, evolution_handler, research_handler
    status_handler, evolution_handler, research_handler = _create_command_handlers(bot)
    
    # Create Discord group
    factorio_group = app_commands.Group(...)
    
    # ... SERVERS command (unchanged) ...
    # ... CONNECT command (unchanged) ...
    # ... PLAYERS command (unchanged) ...
    # ... VERSION command (unchanged) ...
    # ... SEED command (unchanged) ...
    # ... STATUS command (UPDATED - delegates to handler) ...
    # ... EVOLUTION command (UPDATED - delegates to handler) ...
    # ... ADMINS command (unchanged) ...
    # ... HEALTH command (unchanged) ...
    # ... remaining commands (unchanged) ...
    # ... RESEARCH command (UPDATED - delegates to handler) ...
    
    bot.tree.add_command(factorio_group)
```

**Alternative** (cleaner):

You could also make handlers instance attributes:

```python
def register_factorio_commands(bot: Any) -> None:
    """Register all /factorio subcommands."""
    # Store handlers on bot for reference
    bot.command_handlers = _create_command_handlers(bot)
    status_handler, evolution_handler, research_handler = bot.command_handlers
    
    # ... rest of function ...
```

---

## ✅ Integration Checklist

### Pre-Integration

- [ ] Handlers code reviewed
- [ ] Tests passing (40+, 95%+ coverage)
- [ ] `factorio.py` current backup saved
- [ ] Git working tree clean (no uncommitted changes)

### Integration Steps

- [ ] Add imports for 3 handlers (StatusCommandHandler, EvolutionCommandHandler, ResearchCommand)
- [ ] Add `_create_command_handlers()` function
- [ ] Replace 3 command closures with delegation
- [ ] Update `register_factorio_commands()` to call `_create_command_handlers()`
- [ ] Verify no syntax errors (syntax check)

### Post-Integration (Local Testing)

- [ ] Bot starts without errors (`python -m src.main`)
- [ ] `/factorio help` works (command group loads)
- [ ] `/factorio status` returns valid embed (NOT error)
  - Check response has player count, UPS, evolution
  - Check rate limit cooldown appears
- [ ] `/factorio evolution nauvis` returns valid embed
  - Check surface evolution displayed correctly
  - Check rate limit cooldown appears
- [ ] `/factorio research` shows technology count
  - Check response shows "X/Y" technologies researched
  - Check admin cooldown appears
- [ ] Check bot logs for `command_handlers_initialized`
- [ ] No uncaught exceptions in logs

### Smoke Testing (Optional)

- [ ] Deploy to test Discord server
- [ ] Run `/factorio servers` (no changes expected)
- [ ] Run `/factorio status` (same output as before)
- [ ] Run `/factorio evolution nauvis` (same output as before)
- [ ] Run `/factorio research` (same output as before)
- [ ] Run `/factorio help` (unchanged)

---

## 📊 Code Changes Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Status Command** | 150 lines | 12 lines | -90% |
| **Evolution Command** | 120 lines | 15 lines | -87% |
| **Research Command** | 180 lines | 26 lines | -86% |
| **Subtotal (3 commands)** | 450 lines | 53 lines | -88% |
| **factorio.py Total** | ~1,750 lines | ~1,350 lines | -230 lines (23% reduction) |
| **Testability** | ~70% | ~95%+ | +25% |
| **Type Safety** | Implicit | Explicit Protocols | Full ✅ |
| **Reusability** | Discord only | Any interface | Unlimited |

---

## 🧪 Testing After Integration

### Unit Tests (No Changes Required)

```bash
pytest tests/test_command_handlers.py -v --cov=src.bot.commands.command_handlers --cov-report=term-missing
```

✅ All 40+ tests should pass
✅ Coverage should remain 95%+

### Integration Test (New)

```python
# tests/test_factorio_integration.py (optional)
import pytest
from unittest.mock import MagicMock, AsyncMock
import discord


class TestFactorioIntegration:
    """Integration tests for command handler delegation in factorio.py."""

    @pytest.mark.asyncio
    async def test_status_command_delegates_to_handler(self):
        """Verify status command closure delegates to handler."""
        # Create mock bot
        bot = MagicMock()
        bot.user_context = MagicMock()
        bot.server_manager = MagicMock()
        bot.rcon_monitor = MagicMock()
        
        # Import and register
        from src.bot.commands.factorio import register_factorio_commands
        register_factorio_commands(bot)
        
        # Verify handlers created
        assert hasattr(bot, 'command_handlers')
        status_handler, evolution_handler, research_handler = bot.command_handlers
        
        assert status_handler is not None
        assert evolution_handler is not None
        assert research_handler is not None

    @pytest.mark.asyncio
    async def test_status_command_response_structure(self):
        """Verify status command response has correct structure."""
        # Create mock interaction
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user.id = 123
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # ... test closure calls handler.execute() and sends response ...
```

---

## 🔄 Rollback Plan

If issues arise, rollback is simple:

```bash
# Restore from git
git checkout HEAD -- src/bot/commands/factorio.py

# Or restore from backup
cp factorio.py.backup src/bot/commands/factorio.py

# Restart bot
python -m src.main
```

**Why safe?**
- No schema changes
- No database migrations
- No config changes
- Handlers are optional (sit alongside closures)
- All 14 other commands unchanged

---

## 📝 Phase 2 Deliverables

After integration:

1. ✅ **Modified `factorio.py`** (230 lines removed, 3 handlers delegated)
2. ✅ **Updated imports** (3 handler classes)
3. ✅ **Composition Root function** (`_create_command_handlers`)
4. ✅ **Verified no breaking changes** (all 17 commands work)
5. ✅ **Tests still passing** (40+, 95%+ coverage)
6. ✅ **Ready for Phase 3** (refactor remaining 14 commands)

---

## 🚀 Next: Phase 3

Once Phase 2 is verified:

1. **Extract 4 more handler classes** (Kick, Ban, Unban, Mute/Unmute)
2. **Follow same integration pattern** (same level of simplicity)
3. **Refactor remaining 10 commands** (lower priority)
4. **Celebrate** 🎉 (17/17 commands using DI + Command Pattern)

---

## 💡 FAQ

**Q: Will this break existing commands?**
A: No. Only 3 commands change implementation (closure delegates to handler). Logic, API, outputs identical.

**Q: Can we deploy to production after Phase 2?**
A: Yes. 3 refactored commands are fully tested (95%+ coverage). Other 14 unchanged.

**Q: How long does Phase 2 take?**
A: 2-3 hours (integration + smoke testing). 1 hour if just code changes.

**Q: What if we find bugs in handlers?**
A: Fix in handler + test, then redeploy. Closure just delegates.

**Q: Why not refactor all 17 at once?**
A: Safer to do 3-4 at a time, verify each batch works, then expand. Reduces risk.

---

**Ready? Let's integrate! 🚀**
