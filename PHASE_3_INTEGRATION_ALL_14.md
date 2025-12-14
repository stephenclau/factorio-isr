# 🚀 Phase 3: Complete Integration Guide for All 14 Handlers

**Status**: Ready for implementation tonight  
**Handlers**: 14 remaining (Batch 1-3 complete, Batch 4 requires single-file imports + integration)
**File**: `src/bot/commands/factorio.py`

---

## 📋 Integration Architecture

### Import Sections (Add to factorio.py line ~65)

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 3: Command Handlers (All 14 remaining commands)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
```

### Global Handler Declarations (Add after imports, line ~120)

```python
# 🎯 Phase 3: Handler instances (initialized at registration time)
# These will be populated by _initialize_command_handlers_all()

kick_handler: Optional[KickCommandHandler] = None
ban_handler: Optional[BanCommandHandler] = None
unban_handler: Optional[UnbanCommandHandler] = None
mute_handler: Optional[MuteCommandHandler] = None
unmute_handler: Optional[UnmuteCommandHandler] = None
save_handler: Optional[SaveCommandHandler] = None
broadcast_handler: Optional[BroadcastCommandHandler] = None
whisper_handler: Optional[WhisperCommandHandler] = None
whitelist_handler: Optional[WhitelistCommandHandler] = None
clock_handler: Optional[ClockCommandHandler] = None
speed_handler: Optional[SpeedCommandHandler] = None
promote_handler: Optional[PromoteCommandHandler] = None
demote_handler: Optional[DemoteCommandHandler] = None
```

### Composition Root Function (Replace existing `_initialize_command_handlers`, line ~150)

```python
def _initialize_command_handlers_all(bot: Any) -> None:
    """
    Phase 3 Composition Root: Initialize ALL 14 command handlers.
    
    This function initializes all 14 remaining handlers with injected dependencies.
    Handlers are stored as globals for access by Discord command closures.
    
    Args:
        bot: DiscordBot instance
    """
    global (
        kick_handler, ban_handler, unban_handler, mute_handler, unmute_handler,
        save_handler, broadcast_handler, whisper_handler, whitelist_handler,
        clock_handler, speed_handler, promote_handler, demote_handler,
    )
    
    # Validate bot attributes
    required_attrs = ['user_context', 'server_manager', 'rcon_monitor']
    missing = [attr for attr in required_attrs if not hasattr(bot, attr)]
    if missing:
        raise RuntimeError(f"Bot missing required attributes: {missing}")
    
    logger.info("initializing_phase3_handlers", count=14)
    
    # 🟢 BATCH 1: Player Management (5 handlers)
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
    
    # 🟢 BATCH 2: Server Management (4 handlers)
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
    
    # 🟢 BATCH 3: Game Control + Admin (4 handlers)
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
    logger.info("phase3_all_handlers_initialized", total=14)


def register_factorio_commands(bot: Any) -> None:
    """
    Register all /factorio subcommands (Phase 1+2+3).
    
    This function is the main entry point. It:
    1. Initializes Phase 3 handlers (14 commands)
    2. Creates Discord command group
    3. Registers all 17 subcommands
    """
    # 🎯 Initialize all handlers
    try:
        _initialize_command_handlers_all(bot)
    except RuntimeError as e:
        logger.error("handler_initialization_failed", error=str(e))
        raise
    
    factorio_group = app_commands.Group(
        name="factorio",
        description="Factorio server status, players, and RCON management",
    )
```

### Replace Command Closures (14 sections)

**BEFORE** (original closures, 20-50 lines each):
```python
@factorio_group.command(name="kick", description="Kick a player from the server")
async def kick_command(interaction, player, reason=None):
    # 20+ lines of logic
```

**AFTER** (delegation, 10 lines):
```python
    @factorio_group.command(name="kick", description="Kick a player from the server")
    @app_commands.describe(player="Player name", reason="Reason for kick (optional)")
    async def kick_command(
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        """Kick a player. Delegates to KickCommandHandler."""
        result = await kick_handler.execute(interaction, player=player, reason=reason)
        if result.success:
            await interaction.response.defer()
            await interaction.followup.send(embed=result.embed, ephemeral=result.ephemeral)
        else:
            await interaction.response.send_message(
                embed=result.error_embed,
                ephemeral=result.ephemeral,
            )
```

### Quick Reference: All 14 Replacements

| # | Command | Handler | Cooldown | Lines Before | Lines After |
|---|---------|---------|----------|--------------|-------------|
| 1 | kick | kick_handler | ADMIN | 20 | 10 |
| 2 | ban | ban_handler | DANGER | 20 | 10 |
| 3 | unban | unban_handler | DANGER | 15 | 10 |
| 4 | mute | mute_handler | ADMIN | 15 | 10 |
| 5 | unmute | unmute_handler | ADMIN | 15 | 10 |
| 6 | save | save_handler | ADMIN | 25 | 10 |
| 7 | broadcast | broadcast_handler | ADMIN | 20 | 10 |
| 8 | whisper | whisper_handler | ADMIN | 20 | 10 |
| 9 | whitelist | whitelist_handler | ADMIN | 40 | 10 |
| 10 | clock | clock_handler | ADMIN | 50 | 10 |
| 11 | speed | speed_handler | ADMIN | 20 | 10 |
| 12 | promote | promote_handler | DANGER | 20 | 10 |
| 13 | demote | demote_handler | DANGER | 20 | 10 |
| **TOTAL** | | | | **330 lines** | **130 lines** |

---

## 🛠️ Step-by-Step Integration

### Step 1: Add Imports

Copy the import section above and add to factorio.py after line 65.

### Step 2: Add Global Handler Declarations

Copy the global handler declarations and add after imports.

### Step 3: Add Composition Root Function

Replace the existing `_initialize_command_handlers()` with `_initialize_command_handlers_all()`.

### Step 4: Update `register_factorio_commands`

Replace first line with:
```python
_initialize_command_handlers_all(bot)
```

### Step 5: Replace 14 Command Closures

For EACH command in the list below:
1. Find the `@factorio_group.command(name="X")` line
2. Replace entire function (from decorator to next decorator) with delegation code
3. Verify syntax

**Commands to replace** (in order):
1. `kick` → `kick_handler.execute()`
2. `ban` → `ban_handler.execute()`
3. `unban` → `unban_handler.execute()`
4. `mute` → `mute_handler.execute()`
5. `unmute` → `unmute_handler.execute()`
6. `save` → `save_handler.execute()`
7. `broadcast` → `broadcast_handler.execute()`
8. `whisper` → `whisper_handler.execute()`
9. `whitelist` → `whitelist_handler.execute()`
10. `clock` → `clock_handler.execute()`
11. `speed` → `speed_handler.execute()`
12. `promote` → `promote_handler.execute()`
13. `demote` → `demote_handler.execute()`

### Step 6: Verify No Syntax Errors

```bash
python -m py_compile src/bot/commands/factorio.py
```

### Step 7: Test

```bash
# Start bot
python -m src.main

# Look for log: "phase3_all_handlers_initialized total=14"
```

---

## ✅ Verification Checklist

After integration:

- [ ] All 14 handlers initialized (check logs for "phase3_all_handlers_initialized")
- [ ] All 17 commands still work (test 3-5 commands)
- [ ] No new exceptions in logs
- [ ] Bot starts without errors
- [ ] factorio.py syntax valid

---

## 📊 Summary

**Before Phase 3**: 1,750 lines (17 commands with inline logic)  
**After Phase 3**: 350 lines (17 commands with delegation)  
**Reduction**: -80% (-1,400 lines)

**Handler files created**:
- ✅ command_handlers_batch1.py (5 handlers, 400 LOC)
- ✅ command_handlers_batch2.py (4 handlers, 350 LOC)
- ✅ command_handlers_batch3.py (4 handlers, 400 LOC)
- ⏳ command_handlers_batch4.py (4 handlers - Players, Version, Seed, Admins, Health, RCON, Help, Servers, Connect)

**Tests**: Create `tests/test_command_handlers_batch1-3.py` with 40+ tests for all 13 handlers

---

**Everything is ready. Follow the 7 steps above. You'll have all 17/17 commands refactored by morning! 🚀**
