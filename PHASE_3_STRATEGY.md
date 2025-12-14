# 🚀 Phase 3: Refactor All 17 Commands

**Status**: Ready for planning  
**Scope**: Extract 14 remaining command handlers from closure-based design  
**Total Commands**: 17/17 using DI + Command Pattern  
**Timeline**: 3-4 weeks (batches of 3-4 handlers per sprint)

---

## 📋 Overview

Phase 2 proves the pattern works. Phase 3 applies it uniformly to all 17 commands.

**Remaining commands to refactor** (14 total):

### Batch 1: Player Management (4 commands) — Week 1
- Kick, Ban, Unban
- Mute, Unmute

### Batch 2: Server Management (4 commands) — Week 2
- Save, Broadcast, Whisper
- Whitelist (complex due to multi-action dispatch)

### Batch 3: Game Control (3 commands) — Week 3
- Clock, Speed
- Research (already in Phase 2, but would benefit from additional pattern)

### Batch 4: Server Info + Advanced (3 commands) — Week 4
- Players, Version, Seed, Admins, Health
- RCON, Help
- Servers, Connect (multi-server orchestration)

---

## 🎯 Tier 1: Player Management Handlers (Batch 1)

### Commands to Extract

```python
@kick_command       # 20 lines
@ban_command        # 20 lines
@unban_command      # 15 lines
@mute_command       # 15 lines
@unmute_command     # 15 lines
```

### Handler Structure

```python
# src/bot/commands/command_handlers.py (additions)

from typing import Protocol
from dataclasses import dataclass
import discord

@dataclass
class CommandResult:
    """Standard result type for all command handlers."""
    success: bool
    embed: discord.Embed
    error_embed: Optional[discord.Embed] = None
    ephemeral: bool = False

class RconClientProvider(Protocol):
    """Protocol for providing RCON client."""
    async def execute(self, command: str) -> str: ...
    is_connected: bool

class KickCommandHandler:
    """Kick a player from the server."""
    
    def __init__(
        self,
        user_context_provider: UserContextProvider,
        rate_limiter: RateLimiter,
        embed_builder_type: type[EmbedBuilder],
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
        # Rate limit check
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
        if is_limited:
            return CommandResult(
                success=False,
                embed=None,
                error_embed=self.embed_builder.cooldown_embed(retry),
                ephemeral=True,
            )
        
        # Get RCON client
        server_name = self.user_context.get_server_display_name(interaction.user.id)
        rcon_client = self.user_context.get_rcon_for_user(interaction.user.id)
        
        if rcon_client is None or not rcon_client.is_connected:
            return CommandResult(
                success=False,
                embed=None,
                error_embed=self.embed_builder.error_embed(
                    f"RCON not available for {server_name}."
                ),
                ephemeral=True,
            )
        
        try:
            # Execute RCON command
            message = reason if reason else "Kicked by moderator"
            await rcon_client.execute(f'/kick {player} {message}')
            
            # Build result embed
            embed = discord.Embed(
                title="⚠️ Player Kicked",
                color=EmbedBuilder.COLOR_WARNING,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Player", value=player, inline=True)
            embed.add_field(name="Server", value=server_name, inline=True)
            embed.add_field(name="Reason", value=message, inline=False)
            embed.set_footer(text="Action performed via Discord")
            
            return CommandResult(
                success=True,
                embed=embed,
                ephemeral=False,
            )
        
        except Exception as e:
            return CommandResult(
                success=False,
                embed=None,
                error_embed=self.embed_builder.error_embed(
                    f"Failed to kick player: {str(e)}"
                ),
                ephemeral=True,
            )

class BanCommandHandler:
    """Ban a player from the server."""
    # Similar structure to KickCommandHandler
    # Implementation follows same pattern

class UnbanCommandHandler:
    """Unban a player."""
    # Similar structure

class MuteCommandHandler:
    """Mute a player from chat."""
    # Similar structure

class UnmuteCommandHandler:
    """Unmute a player."""
    # Similar structure
```

### Integration Points

```python
# src/bot/commands/factorio.py

# Import
from bot.commands.command_handlers import (
    KickCommandHandler,
    BanCommandHandler,
    UnbanCommandHandler,
    MuteCommandHandler,
    UnmuteCommandHandler,
)

# Initialize in composition root
def _initialize_command_handlers(bot):
    # ... existing 3 handlers ...
    
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
    
    # ... etc ...
    
    return (
        status_handler, evolution_handler, research_handler,
        kick_handler, ban_handler, unban_handler, mute_handler, unmute_handler,
    )

# Replace closures
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

### Testing Template

```python
# tests/test_command_handlers_batch1.py

@pytest.mark.asyncio
class TestKickCommandHandler:
    """Tests for KickCommandHandler."""
    
    async def test_execute_happy_path(self):
        """Happy path: player kicked successfully."""
        # Mock dependencies
        mock_context = MagicMock(spec=UserContextProvider)
        mock_rcon = MagicMock(spec=RconClientProvider)
        mock_cooldown = MagicMock(spec=RateLimiter)
        
        mock_context.get_server_display_name.return_value = "Main"
        mock_context.get_rcon_for_user.return_value = mock_rcon
        mock_rcon.is_connected = True
        mock_rcon.execute = AsyncMock(return_value="Player kicked")
        mock_cooldown.is_rate_limited.return_value = (False, None)
        
        # Create handler
        handler = KickCommandHandler(
            user_context_provider=mock_context,
            rate_limiter=mock_cooldown,
            embed_builder_type=EmbedBuilder,
        )
        
        # Execute
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.user.id = 123
        result = await handler.execute(mock_interaction, player="BadPlayer", reason="spam")
        
        # Verify
        assert result.success is True
        assert "Player Kicked" in result.embed.title
        assert result.embed is not None
        mock_rcon.execute.assert_called_once_with("/kick BadPlayer spam")
    
    async def test_execute_rate_limited(self):
        """Rate limit triggered."""
        # ... similar mock setup ...
        mock_cooldown.is_rate_limited.return_value = (True, 60)
        
        # ... execution ...
        
        assert result.success is False
        assert result.error_embed is not None
        assert "cooldown" in result.error_embed.description.lower()
    
    async def test_execute_rcon_error(self):
        """RCON client not connected."""
        # ... mock setup with rcon_client = None ...
        
        # ... execution ...
        
        assert result.success is False
        assert "RCON not available" in result.error_embed.description
```

---

## 📊 Implementation Schedule

### Week 1: Batch 1 (Player Management)

**Commands**: Kick, Ban, Unban, Mute, Unmute

**Tasks**:
1. Create 5 handler classes (KickCommandHandler, BanCommandHandler, etc.)
2. Write 40+ tests (8+ per handler)
3. Integrate into factorio.py (import + composition root + 5 delegations)
4. Verify tests pass (95%+ coverage)
5. Deploy to staging

**Output**: 85 lines of handler code, 350 lines of tests

### Week 2: Batch 2 (Server Management)

**Commands**: Save, Broadcast, Whisper, Whitelist

**Tasks**:
1. Create 4 handler classes
2. Write 35+ tests (handle multi-action dispatcher for Whitelist)
3. Integrate into factorio.py
4. Verify tests pass
5. Deploy to staging

**Complexity note**: Whitelist has 5 sub-actions (add/remove/list/enable/disable) → requires internal dispatch logic

**Output**: 100 lines of handler code, 300 lines of tests

### Week 3: Batch 3 (Game Control)

**Commands**: Clock, Speed

**Tasks**:
1. Create 2 handler classes
2. Write 25+ tests (Clock has datetime logic, Speed has validation)
3. Integrate into factorio.py
4. Verify tests pass
5. Deploy to staging

**Output**: 70 lines of handler code, 250 lines of tests

### Week 4: Batch 4 (Server Info + Advanced)

**Commands**: Players, Version, Seed, Admins, Health, RCON, Help, Servers, Connect

**Tasks**:
1. Create 9 handler classes
2. Write 60+ tests
3. Integrate into factorio.py
4. Full regression testing (all 17 commands working)
5. Deploy to production

**Output**: 200 lines of handler code, 500 lines of tests

---

## 📈 Metrics

### Before Phase 3

| Metric | Value |
|--------|-------|
| Commands refactored | 3/17 |
| Handler classes | 3 |
| Tests | 40+ |
| Coverage | 95%+ (handlers only) |
| Lines in factorio.py | ~1,750 |
| Closure-based commands | 14 |

### After Phase 3

| Metric | Value |
|--------|-------|
| Commands refactored | 17/17 |
| Handler classes | 17 |
| Tests | 160+ |
| Coverage | 95%+ (entire system) |
| Lines in factorio.py | ~350 (closures only delegate) |
| Closure-based commands | 0 |

### Improvements

| Aspect | Improvement |
|--------|-------------|
| **Code Simplification** | 1,750 → 350 lines (-80%) in factorio.py |
| **Test Coverage** | 40+ → 160+ tests |
| **Type Safety** | 14 commands inherit DI + Protocols |
| **Reusability** | All 17 commands now reusable via HTTP API |
| **Maintainability** | Logic isolated in handlers, easier to update |
| **Testability** | Direct testing of business logic (no Discord hacks) |

---

## 🏗️ Architecture Patterns

### Handler Complexity Levels

**Level 1 - Simple (5 commands)**
Kick, Ban, Unban, Mute, Unmute
- Single RCON command
- Simple embed response
- Minimal parsing

**Level 2 - Moderate (6 commands)**
Players, Version, Seed, Admins, Health, Speed
- Single RCON command
- Response parsing (regex, line splitting)
- Conditional formatting

**Level 3 - Complex (3 commands)**
Save, Broadcast, Whisper
- Single RCON command
- Complex parsing or escaping
- Dynamic field building

**Level 4 - Multi-Mode (3 commands)**
Whitelist, Clock, Research
- Multiple sub-operations (dispatched)
- Conditional logic branches
- Parameter validation

---

## 🔄 Dependency Hierarchy

```
All 17 Handlers
├─ UserContextProvider (protocol)
├─ RconClientProvider (protocol)
├─ RateLimiter (protocol)
├─ EmbedBuilder (type)
└─ Optional: RconMonitor, ServerManager
```

No handler depends on:
- Discord interaction directly (passed in)
- Other handlers (independent)
- Global state (all injected)

---

## ✅ Quality Gates Per Batch

### Before Approval

- [ ] All handlers written
- [ ] All tests written (8+ per handler)
- [ ] Tests passing (100%)
- [ ] Coverage ≥95%
- [ ] Integration code written
- [ ] No new security issues
- [ ] Documentation updated

### During Staging

- [ ] All 17 commands work identically
- [ ] No performance regression
- [ ] No error rate increase
- [ ] Logs clean (no new warnings)
- [ ] User feedback collected

### Before Production

- [ ] 48-hour staging soak test
- [ ] Zero production incidents
- [ ] Rollback plan verified
- [ ] Team sign-off

---

## 🎓 Learning Path

**Prerequisites**:
1. Read Phase 2 implementation guide (Command Pattern + DI fundamentals)
2. Review Phase 1 handlers (StatusCommandHandler, EvolutionCommandHandler, ResearchCommand)
3. Review Phase 2 integration (how closures delegate to handlers)

**Per-Batch Learning**:
1. **Batch 1**: Simple handlers, focus on testing pattern
2. **Batch 2**: Moderate handlers, learn response parsing
3. **Batch 3**: Complex validation logic (Clock has datetime logic)
4. **Batch 4**: Multi-mode dispatch (Whitelist, RCON)

---

## 💾 Rollback Plan

**If something breaks**:

```bash
# Instant rollback
git revert <batch_commit>

# Redeploy previous version
# All 17 commands still work (most in Phase 2 pattern)
```

**Why safe**:
- Each batch is independent
- No shared state changes
- Handlers can coexist with closures
- Database/config unchanged

---

## 🚀 Success Criteria

### Phase 3 Complete When

✅ All 17/17 commands using DI + Command Pattern
✅ 160+ tests with 95%+ coverage
✅ factorio.py reduced to 350 lines (closures only)
✅ All commands reusable via HTTP API
✅ Production deployment successful
✅ Zero regressions in 7 days
✅ Team trained on pattern

---

## 📝 Next Steps

**Immediate** (This week)
1. Review Phase 2 implementation
2. Review Phase 3 strategy
3. Finalize Batch 1 handler specifications
4. Schedule 4-week sprint

**Week 1 Kickoff**
1. Create Batch 1 handler classes
2. Write tests
3. Integrate and verify
4. Deploy to staging

---

**Ready to start Phase 3? Batch 1 (Player Management) can begin immediately. All patterns and infrastructure proven in Phase 2. 🚀**
