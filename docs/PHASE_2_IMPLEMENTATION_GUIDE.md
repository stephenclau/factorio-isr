# 🔧 Phase 2: Implementation Guide

**Copy-paste ready code to integrate handlers into `factorio.py`**

---

## 📋 Table of Contents

1. [Step 1: Add Imports](#step-1-add-imports)
2. [Step 2: Add Composition Root](#step-2-add-composition-root)
3. [Step 3: Replace Status Command](#step-3-replace-status-command)
4. [Step 4: Replace Evolution Command](#step-4-replace-evolution-command)
5. [Step 5: Replace Research Command](#step-5-replace-research-command)
6. [Step 6: Update register_factorio_commands](#step-6-update-register_factorio_commands)
7. [Step 7: Verify & Test](#step-7-verify--test)

---

## ✅ Step 1: Add Imports

**File**: `src/bot/commands/factorio.py`

**Location**: After existing imports, around line 65

**Add this block**:

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Command Handlers (DI-based, Phase 2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
try:
    # Try flat layout first (when run from src/ directory)
    from bot.commands.command_handlers import (
        StatusCommandHandler,
        EvolutionCommandHandler,
        ResearchCommand,
    )
except ImportError:
    try:
        # Fallback to package style (when installed as package)
        from src.bot.commands.command_handlers import (  # type: ignore
            StatusCommandHandler,
            EvolutionCommandHandler,
            ResearchCommand,
        )
    except ImportError:
        # Last resort: use relative imports from parent
        from .command_handlers import (
            StatusCommandHandler,
            EvolutionCommandHandler,
            ResearchCommand,
        )
```

✅ **Result**: Handlers imported with fallback logic matching existing import pattern

---

## ✅ Step 2: Add Composition Root

**File**: `src/bot/commands/factorio.py`

**Location**: Right before `register_factorio_commands()` function (around line 85)

**Add this function**:

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Composition Root: Handler Initialization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _initialize_command_handlers(bot: Any) -> tuple[StatusCommandHandler, EvolutionCommandHandler, ResearchCommand]:
    """
    Composition Root: Initialize all command handlers with injected dependencies.
    
    This function is called once during bot startup to create handler instances
    with real dependencies from the bot. Handlers are then used by Discord
    command closures to execute business logic.
    
    Args:
        bot: DiscordBot instance with user_context, server_manager, rcon_monitor
        
    Returns:
        Tuple of (status_handler, evolution_handler, research_handler)
        
    Raises:
        RuntimeError: If required bot attributes are missing
    """
    # Validate bot has required attributes
    required_attrs = ['user_context', 'server_manager', 'rcon_monitor']
    missing = [attr for attr in required_attrs if not hasattr(bot, attr)]
    if missing:
        raise RuntimeError(f"Bot missing required attributes: {missing}")
    
    # 🟢 Status Command Handler
    # ────────────────────────────
    status_handler = StatusCommandHandler(
        user_context_provider=bot.user_context,
        server_manager_provider=bot.server_manager,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
        rcon_monitor=bot.rcon_monitor,
    )
    logger.info("handler_initialized", handler="StatusCommandHandler")
    
    # 🟢 Evolution Command Handler
    # ─────────────────────────────
    evolution_handler = EvolutionCommandHandler(
        user_context_provider=bot.user_context,
        rate_limiter=QUERY_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    logger.info("handler_initialized", handler="EvolutionCommandHandler")
    
    # 🟢 Research Command Handler
    # ────────────────────────────
    research_handler = ResearchCommand(
        user_context_provider=bot.user_context,
        rate_limiter=ADMIN_COOLDOWN,
        embed_builder_type=EmbedBuilder,
    )
    logger.info("handler_initialized", handler="ResearchCommand")
    
    logger.info(
        "all_command_handlers_initialized",
        count=3,
        handlers=["status", "evolution", "research"],
        phase="2_integration",
    )
    
    return status_handler, evolution_handler, research_handler
```

✅ **Result**: Composition root created, ready to wire dependencies

---

## ✅ Step 3: Replace Status Command

**File**: `src/bot/commands/factorio.py`

**Location**: Find `@factorio_group.command(name="status", description="Show Factorio server status")` (around line 630)

**Find and Replace**: The entire status_command function (entire block from `@factorio_group.command` to end of function before next `@factorio_group.command`)

**With this**:

```python
    @factorio_group.command(name="status", description="Show Factorio server status")
    async def status_command(interaction: discord.Interaction) -> None:
        """Get comprehensive server status with rich embed including metrics.
        
        Delegates business logic to StatusCommandHandler.
        Closure handles Discord mechanics only.
        """
        # Execute handler
        result = await status_handler.execute(interaction)
        
        # Send response
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(
                embed=result.embed,
                ephemeral=result.ephemeral,
            )
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )
```

✅ **Result**: 150 lines → 12 lines, delegates to handler

---

## ✅ Step 4: Replace Evolution Command

**File**: `src/bot/commands/factorio.py`

**Location**: Find `@factorio_group.command(name="evolution", description="Show evolution for a surface or all non-platform surfaces")` (around line 900)

**Find and Replace**: The entire evolution_command function

**With this**:

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
        """Show evolution for a surface or all non-platform surfaces.
        
        Delegates business logic to EvolutionCommandHandler.
        Closure handles Discord mechanics only.
        """
        # Execute handler
        result = await evolution_handler.execute(interaction, target=target)
        
        # Send response
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(
                embed=result.embed,
                ephemeral=result.ephemeral,
            )
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )
```

✅ **Result**: 120 lines → 18 lines, delegates to handler

---

## ✅ Step 5: Replace Research Command

**File**: `src/bot/commands/factorio.py`

**Location**: Find `@factorio_group.command(name="research", description="Manage technology research...`)` (around line 1300)

**Find and Replace**: The entire research_command function

**With this**:

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
        
        Delegates business logic to ResearchCommand.
        Closure handles Discord mechanics only.
        """
        # Execute handler
        result = await research_handler.execute(
            interaction,
            force=force,
            action=action,
            technology=technology,
        )
        
        # Send response
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(
                embed=result.embed,
                ephemeral=result.ephemeral,
            )
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )
```

✅ **Result**: 180 lines → 28 lines, delegates to handler

---

## ✅ Step 6: Update register_factorio_commands

**File**: `src/bot/commands/factorio.py`

**Location**: Find `def register_factorio_commands(bot: Any) -> None:` function start (around line 85)

**Update the docstring and add initialization**:

**From**:
```python
def register_factorio_commands(bot: Any) -> None:
    """
    Register all /factorio subcommands.

    This function creates and registers the complete /factorio command tree.
    Discord limit: 25 subcommands per group (we use 17).

    Each command is self-contained: RCON execute → parse → format → send.

    Args:
        bot: DiscordBot instance with user_context, server_manager attributes
    """
    factorio_group = app_commands.Group(
        name="factorio",
        description="Factorio server status, players, and RCON management",
    )
```

**To**:
```python
def register_factorio_commands(bot: Any) -> None:
    """
    Register all /factorio subcommands.

    This function:
    1. Initializes command handlers (Composition Root)
    2. Creates Discord command group
    3. Registers all 17 subcommands with handlers providing business logic

    Discord limit: 25 subcommands per group (we use 17).

    Command Handler Architecture (Phase 2 Refactor):
    - 3 commands (status, evolution, research): DI-based handlers
    - 14 commands: Traditional closure-based (Phase 3+ candidates)

    Args:
        bot: DiscordBot instance with user_context, server_manager, rcon_monitor
    """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Phase 2: Initialize command handlers
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    global status_handler, evolution_handler, research_handler
    try:
        status_handler, evolution_handler, research_handler = _initialize_command_handlers(bot)
    except RuntimeError as e:
        logger.error("command_handlers_initialization_failed", error=str(e))
        raise
    
    factorio_group = app_commands.Group(
        name="factorio",
        description="Factorio server status, players, and RCON management",
    )
```

✅ **Result**: Handlers initialized before commands registered

---

## ✅ Step 7: Verify & Test

### 7.1 Syntax Check

```bash
# Check for syntax errors
python -m py_compile src/bot/commands/factorio.py

# If no output, syntax is valid ✅
```

### 7.2 Import Check

```bash
# Check imports work
python -c "from src.bot.commands.factorio import register_factorio_commands; print('✅ Imports OK')"
```

### 7.3 Bot Startup

```bash
# Start bot (CTRL+C to stop after startup message)
python -m src.main

# Look for log line:
# "all_command_handlers_initialized count=3 handlers=['status', 'evolution', 'research']"
```

### 7.4 Command Testing (Discord)

In any Discord channel where bot has permissions:

```
# Test 1: Status command
/factorio status
# Expected: Normal status embed (unchanged output)

# Test 2: Evolution command
/factorio evolution nauvis
# Expected: Evolution factor for nauvis

# Test 3: Research command
/factorio research
# Expected: Technology count display (X/Y)

# Test 4: Help command
/factorio help
# Expected: Help text (unchanged)

# Test 5: Another command (unchanged)
/factorio players
# Expected: Player list (unchanged, not refactored yet)
```

✅ **Expected**: All commands work identically to before (no behavior change)

### 7.5 Verify Tests Still Pass

```bash
# Run handler tests
pytest tests/test_command_handlers.py -v --cov=src.bot.commands.command_handlers

# Expected output:
# ✅ 40+ tests passed
# ✅ Coverage: 95%+
# ✅ No failures
```

---

## 🎯 Quick Reference: What Changed

### Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `src/bot/commands/factorio.py` | Added imports, composition root, replaced 3 commands | +80, -450, net -370 |

### Files Created

| File | Purpose |
|------|----------|
| `docs/PHASE_2_INTEGRATION.md` | Integration architecture guide |
| `docs/PHASE_2_IMPLEMENTATION_GUIDE.md` | This file - copy-paste code |

### Files Unchanged

| File | Why |
|------|-----|
| `src/bot/commands/command_handlers.py` | Already complete from Phase 1 |
| `tests/test_command_handlers.py` | Tests validate handlers, independent of factorio.py |
| All other bot files | No dependencies on factorio.py command structure |

---

## 🔍 Validation Checklist

Before committing:

- [ ] Syntax check passes (`py_compile`)
- [ ] Imports check passes
- [ ] Bot starts without errors
- [ ] Handler initialization log appears
- [ ] `/factorio status` returns embed
- [ ] `/factorio evolution nauvis` returns embed
- [ ] `/factorio research` returns status
- [ ] Tests pass (40+, 95%+ coverage)
- [ ] No new exceptions in logs
- [ ] No warnings about missing handlers

---

## 🚀 After Phase 2: What's Next?

Once Phase 2 is verified and working:

### Option A: Deploy to Production

```bash
# 1. Commit changes
git add src/bot/commands/factorio.py
git commit -m "refactor(commands): integrate DI handlers for status, evolution, research (Phase 2)"

# 2. Push to prod branch
git push origin main

# 3. Deploy (your process)
```

### Option B: Continue to Phase 3 (Recommended)

Refactor remaining 14 commands using same pattern:

```python
# Phase 3 targets (example)
class KickCommandHandler:
    async def execute(self, interaction, player, reason=None) -> CommandResult: ...

class BanCommandHandler:
    async def execute(self, interaction, player, reason=None) -> CommandResult: ...

class UnbanCommandHandler:
    async def execute(self, interaction, player) -> CommandResult: ...

class MuteCommandHandler:
    async def execute(self, interaction, player) -> CommandResult: ...

# ... and 10 more
```

**Timeline**: 2-3 weeks for all 17 commands

---

## ❓ FAQ

**Q: What if I make a mistake?**
A: Git rollback: `git checkout HEAD -- src/bot/commands/factorio.py`

**Q: Can I commit just part of the changes?**
A: Yes. You can integrate handlers one at a time and commit separately.

**Q: Will existing users see any difference?**
A: No. Command output, behavior, API all identical.

**Q: How do I know if the integration worked?**
A: Check logs for `all_command_handlers_initialized`. If present, handlers loaded.

**Q: What if tests fail after integration?**
A: Rollback and debug. Tests validate handlers independently, so likely import/syntax issue.

---

## 📞 Support

If you get stuck:

1. Check `PHASE_2_INTEGRATION.md` for architecture explanation
2. Check `DI_vs_COMMAND_PATTERN.md` for design rationale
3. Compare with `src/bot/commands/command_handlers.py` for handler structure
4. Review test file `tests/test_command_handlers.py` for usage examples

---

**Ready? Start with Step 1! 🚀**
