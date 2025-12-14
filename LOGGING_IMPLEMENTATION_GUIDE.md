# 🔍 Handler Entry Logging Implementation Guide

**Status:** Ready for implementation  
**Complexity:** Low (purely additive logging)  
**Risk Level:** Minimal (no logic changes)  
**Test Coverage Target:** 91% (existing + new logging tests)

---

## 🌟 Overview

This implementation adds **handler invocation logging** to all 25 command handlers in `src/bot/commands/command_handlers.py`. The goal is to create a complete audit trail of command execution at the handler level.

### Current State
- ❌ **No entry logs** when handlers start executing
- ✅ **Internal logs** when handlers complete (success/error)
- ❌ **No exit logs** when handlers finish

### After Implementation
- ✅ **Entry logs** on handler invocation
- ✅ **Internal logs** on completion (existing)
- ✅ **Exit logs** on completion (Phase 2)

---

## 🚀 Quick Start

### Option A: Automated (Recommended)

```bash
# From repo root
cd scripts
python apply_handler_logging.py

# Review changes
git diff ../src/bot/commands/command_handlers.py

# Approve and commit
git add ../src/bot/commands/command_handlers.py
git commit -m "🔍 Add handler entry logging across all 25 command handlers"
```

### Option B: Manual (Detailed Guidance)

1. Open `src/bot/commands/command_handlers.py`
2. For each of 25 handlers, apply patches from `HANDLER_LOGGING_IMPLEMENTATION.md`
3. Verify with `git diff`
4. Test with real commands
5. Commit when satisfied

---

## 📊 Handlers Affected (25 Total)

### Server Information (7)
```
StatusCommandHandler (line ~212)
PlayersCommandHandler (line ~381)
VersionCommandHandler (line ~421)
SeedCommandHandler (line ~461)
EvolutionCommandHandler (line ~501)
AdminsCommandHandler (line ~623)
HealthCommandHandler (line ~663)
```

### Player Management (7)
```
KickCommandHandler (line ~724)
BanCommandHandler (line ~773)
UnbanCommandHandler (line ~822)
MuteCommandHandler (line ~870)
UnmuteCommandHandler (line ~918)
PromoteCommandHandler (line ~966)
DemoteCommandHandler (line ~1014)
```

### Server Management (4)
```
SaveCommandHandler (line ~1062)
BroadcastCommandHandler (line ~1109)
WhisperCommandHandler (line ~1156)
WhitelistCommandHandler (line ~1203)
```

### Game Control (3)
```
ClockCommandHandler (line ~1300)
SpeedCommandHandler (line ~1408)
ResearchCommandHandler (line ~1464)
```

### Advanced (2)
```
RconCommandHandler (line ~1710)
HelpCommandHandler (line ~1765)
```

### Multi-Server (2)
```
ServersCommandHandler (line ~1808)
ConnectCommandHandler (line ~1879)
```

---

## 🔧 Implementation Pattern

### Standard Handler (no extra parameters)

```python
async def execute(self, interaction: discord.Interaction) -> CommandResult:
    """Execute status command."""
    logger.info("handler_invoked", handler="StatusCommandHandler", user=interaction.user.name)
    
    is_limited, retry = self.cooldown.is_rate_limited(interaction.user.id)
    # ... rest of method ...
```

### Handler with parameters

```python
async def execute(self, interaction: discord.Interaction, player: str, reason: Optional[str] = None) -> CommandResult:
    """Execute kick command."""
    logger.info("handler_invoked", handler="KickCommandHandler", user=interaction.user.name, player=player)
    
    is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
    # ... rest of method ...
```

### Parameter Context

| Handler | Extra Parameter |
|---------|------------------|
| Kick, Ban, Unban, Mute, Unmute, Promote, Demote, Whisper | `player=player` |
| Whitelist | `action=action` |
| Speed | `speed=value` |
| Research | `force=force` |
| Connect | `server=server` |
| All others | None |

---

## ✅ Quality Checklist

### Pre-Implementation
- [ ] Reviewed this guide
- [ ] Understand the pattern
- [ ] Have copy of `HANDLER_LOGGING_IMPLEMENTATION.md` nearby

### During Implementation
- [ ] Using Option A (automated) or Option B (manual)
- [ ] Only adding logger.info calls (no other changes)
- [ ] Single blank line after each logger.info call
- [ ] Handler class name matches exactly
- [ ] Extra parameters captured where relevant

### Post-Implementation
- [ ] All 25 handlers have entry logging
- [ ] `git diff` shows only logger.info additions
- [ ] No accidental formatting changes
- [ ] Code still passes linting/type checking
- [ ] Tests pass (run: `pytest tests/`)
- [ ] Manual testing:
  - [ ] `/factorio status` → Check logs for `handler_invoked`
  - [ ] `/factorio players` → Check logs
  - [ ] `/factorio kick <player>` → Check logs contain player name
  - [ ] `/factorio speed 2.0` → Check logs contain speed value

### Pre-Commit
- [ ] Review full diff: `git diff src/bot/commands/command_handlers.py`
- [ ] ~25 new logger.info lines added
- [ ] No deletions, only additions
- [ ] Commit message references "handler entry logging"

---

## 🤍 Logging Format

Each log entry follows this format:

```python
logger.info(
    "handler_invoked",
    handler="[HandlerClassName]",
    user=interaction.user.name,
    [optional_context_param]=[value]  # if applicable
)
```

### Example Logs

```json
{
  "event": "handler_invoked",
  "handler": "StatusCommandHandler",
  "user": "alice",
  "timestamp": "2025-12-14T08:33:00Z"
}

{
  "event": "handler_invoked",
  "handler": "KickCommandHandler",
  "user": "moderator",
  "player": "troublemaker",
  "timestamp": "2025-12-14T08:34:15Z"
}

{
  "event": "handler_invoked",
  "handler": "ResearchCommandHandler",
  "user": "admin",
  "force": "player",
  "timestamp": "2025-12-14T08:35:42Z"
}
```

---

## 📑 Testing Strategy

### Unit Tests

Add tests to `tests/test_command_handlers.py`:

```python
def test_status_handler_logs_invocation(caplog, mock_dependencies):
    """Verify status handler logs entry point."""
    handler = StatusCommandHandler(**mock_dependencies)
    result = asyncio.run(handler.execute(mock_interaction))
    
    assert "handler_invoked" in caplog.text
    assert "StatusCommandHandler" in caplog.text
    assert "test_user" in caplog.text

def test_kick_handler_logs_player_context(caplog, mock_dependencies):
    """Verify kick handler logs player parameter."""
    handler = KickCommandHandler(**mock_dependencies)
    result = asyncio.run(handler.execute(mock_interaction, player="badplayer"))
    
    assert "KickCommandHandler" in caplog.text
    assert "badplayer" in caplog.text
```

### Integration Tests

```bash
# Run real bot and execute command
python bot.py  # in test mode

# In Discord
/factorio status

# Check logs
tail -f logs/bot.log | grep handler_invoked
```

---

## 🔎 Verification

### Step 1: Check Implementation

```bash
grep -n "handler_invoked" src/bot/commands/command_handlers.py | wc -l
# Should output: 25
```

### Step 2: Test Individual Handler

```bash
python -c "
from src.bot.commands.command_handlers import StatusCommandHandler
import inspect

source = inspect.getsource(StatusCommandHandler.execute)
assert 'logger.info' in source
assert 'handler_invoked' in source
print('✓ StatusCommandHandler correctly patched')
"
```

### Step 3: Run Full Test Suite

```bash
pytest tests/ -v --cov=src/bot/commands/command_handlers --cov-fail-under=91
```

---

## 🔗 Related Files

- **Implementation Guide:** `HANDLER_LOGGING_IMPLEMENTATION.md` (25 detailed patches)
- **Automated Script:** `scripts/apply_handler_logging.py` (run this to auto-patch)
- **Audit Report:** `Logging_Audit_Report.md` (original findings)
- **Test File:** `tests/test_command_handlers.py` (add new tests here)

---

## 📚 Architecture Notes

### Why Handler-Level Logging?

```
Discord User invokes: /factorio status
    ↓
factorio.py wrapper (no logging) ❌
    ↓
StatusCommandHandler.execute() ← ADD ENTRY LOG HERE ✅
    ↓
Rate limit check
    ↓
RCON validation
    ↓
Metrics gathering (logs on success/error)
    ↓
Response sent
    ↓
Wrapper exits (no logging) ❌
```

**Result:** Complete handler-level traceability without wrapper overhead

### Log Aggregation Pattern

With this implementation, logs will show:

```
08:33:00 handler_invoked handler=StatusCommandHandler user=alice
08:33:01 status_command_executed user=alice ups=60 evolution=0.42
08:33:02 handler_invoked handler=KickCommandHandler user=mod player=baduser
08:33:02 player_kicked player=baduser moderator=mod
```

**Benefit:** Can correlate invocation → execution → completion

---

## 🔚 Rollback Plan

If implementation needs rollback:

```bash
# Undo commits
git revert <commit-sha>

# Or reset to before implementation
git reset --hard <before-sha>

# Verify
git log --oneline -5
```

No data/config changes, so rollback is clean.

---

## 📐 Estimated Effort

| Task | Time | Notes |
|------|------|-------|
| Run automated script | 5 min | `python scripts/apply_handler_logging.py` |
| Review diff | 10 min | Verify 25 entries added, no deletions |
| Run tests | 5 min | Existing tests should pass |
| Manual test (1-2 commands) | 10 min | Real bot invocation |
| Commit & document | 5 min | Write commit message |
| **Total** | **35 min** | Low complexity, high value |

---

## 🣀 Questions?

Refer to:
- `HANDLER_LOGGING_IMPLEMENTATION.md` for detailed patches
- `scripts/apply_handler_logging.py` for automation help
- `Logging_Audit_Report.md` for why this matters

---

**Document Version:** 1.0  
**Last Updated:** December 14, 2025, 12:35 AM PST  
**Status:** Ready for Implementation  
**Complexity:** 🟢 LOW | **Risk:** 🟢 MINIMAL | **Value:** 🟠 HIGH