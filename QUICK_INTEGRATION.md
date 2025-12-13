# 🚀 Quick Integration Guide: Research Command

**TL;DR:** Copy → Paste → Test → Deploy

---

## 1️⃣ GET THE SOURCE CODE

**File:** [`docs/RESEARCH_COMMAND_SOURCE.py`](./docs/RESEARCH_COMMAND_SOURCE.py)

This file contains the **complete, production-ready `research_command` function**.

---

## 2️⃣ LOCATE TARGET IN factorio.py

Open: `src/bot/commands/factorio.py`

Find the existing `research_command` function (around **line 1600-1630**):

```python
@factorio_group.command(name="research", description="Force research a technology")
@app_commands.describe(technology="Technology name")
async def research_command(
    interaction: discord.Interaction,
    technology: str,
) -> None:
    """Force research a technology."""
    # ... existing implementation
```

---

## 3️⃣ COPY THE NEW IMPLEMENTATION

Open [`docs/RESEARCH_COMMAND_SOURCE.py`](./docs/RESEARCH_COMMAND_SOURCE.py)

**Copy everything from `@factorio_group.command` through the final `except Exception as e:` block.**

**Do NOT copy:**
- The triple-quoted docstring at the top
- Comments about copying (lines 1-3)

**DO copy:**
- Everything from `@factorio_group.command(` line onwards
- All the way to the final closing bracket

---

## 4️⃣ REPLACE IN factorio.py

**Delete** the old `research_command` function (entire block from decorator to final `except`).

**Paste** the new implementation in its place.

**Result:**
```python
# OLD: Lines 1600-1630 containing old research_command
# REPLACED WITH: New multi-force research_command (same location)
```

---

## 5️⃣ UPDATE HELP TEXT

Find the `help_command` function in `factorio.py`.

Locate the **Game Control** section (search for `/factorio time` or `/factorio speed`).

**Replace:**
```
/factorio research [tech-name] – Force research a technology
```

**With:**
```
/factorio research [force] [action] [technology] – Manage technology research
  Coop (default player force):
  · (empty) → Show research progress (X/Y researched)
  · all → Research all technologies instantly
  · <tech-name> → Research specific tech (e.g., automation-2)
  · undo <tech-name> → Revert specific tech
  · undo all → Revert all technologies
  
  PvP (force-specific):
  · <force> → Show force research progress
  · <force> all → Research all for force
  · <force> <tech-name> → Research tech for force
  · <force> undo <tech-name> → Revert tech for force
  · <force> undo all → Revert all for force
  
  Examples: player (default), enemy, neutral
```

---

## 6️⃣ RUN TESTS

```bash
# Run the comprehensive test suite
pytest tests/test_research_command.py -v

# Expected output:
# ============ 17 passed in X.XXs ============
```

**All 17 tests should pass:**
- ✅ 5 Coop happy path tests
- ✅ 5 PvP happy path tests
- ✅ 4 error path tests
- ✅ 3 edge case tests

---

## 7️⃣ MANUAL TESTING

### Coop (Default Force)

```
/factorio research
# Expected: "Technologies researched: 42/128" (or similar)

/factorio research all
# Expected: "All Technologies Researched" embed (green/success color)

/factorio research automation-2
# Expected: "Technology Researched: automation-2" embed (green/success color)

/factorio research undo automation-2
# Expected: "Technology Reverted: automation-2" embed (yellow/warning color)

/factorio research undo all
# Expected: "All Technologies Reverted" embed (yellow/warning color)
```

### PvP (Force-Specific)

If you have a PvP server with an "enemy" force:

```
/factorio research enemy
# Expected: "Technologies researched: X/Y" (different from player force)

/factorio research enemy all
# Expected: "All Technologies Researched" (enemy context)

/factorio research enemy automation-2
# Expected: "Technology Researched: automation-2" (enemy context)

/factorio research enemy undo automation-2
# Expected: "Technology Reverted: automation-2" (enemy context)

/factorio research enemy undo all
# Expected: "All Technologies Reverted" (enemy context)
```

### Error Testing

```
/factorio research invalid-force all
# Expected: Error embed "Force 'invalid-force' not found"

/factorio research enemy invalid-tech
# Expected: Error embed with suggestions and force context
```

---

## 8️⃣ COMMIT & DEPLOY

```bash
# Stage the changes
git add src/bot/commands/factorio.py

# Commit with clear message
git commit -m "refactor: implement multi-force research command for Coop/PvP"

# Push to main
git push origin main

# Deploy when ready
# (Your CI/CD pipeline will run tests automatically)
```

---

## ✅ Verification Checklist

- [ ] Old `research_command` function deleted
- [ ] New code pasted from `docs/RESEARCH_COMMAND_SOURCE.py`
- [ ] Help text updated with Coop/PvP examples
- [ ] All imports present (Optional, EmbedBuilder, ADMIN_COOLDOWN, logger)
- [ ] Tests pass: `pytest tests/test_research_command.py -v` (17/17)
- [ ] Manual testing on Coop server
- [ ] Manual testing on PvP server (if available)
- [ ] Commit message describes change
- [ ] Tests pass in CI/CD pipeline
- [ ] Deployed to production

---

## 🔧 Troubleshooting

**Issue: Import errors**
```
ModuleNotFoundError: No module named 'src.discord_interface'
```
Solution: Verify imports at top of `factorio.py`:
```python
from discord_interface import EmbedBuilder
from utils.rate_limiting import ADMIN_COOLDOWN
```

**Issue: Indentation error after paste**
```
IndentationError: unexpected indent
```
Solution: 
1. Ensure the `@factorio_group.command` decorator is at same level as other commands
2. Check that function body is indented consistently (4 spaces per level)
3. Re-copy from source and paste again

**Issue: Tests failing**
```
FAILED tests/test_research_command.py::TestResearchCommand::test_display_status
```
Solution:
1. Verify all function code was copied
2. Check that no lines were accidentally modified
3. Run `pytest tests/test_research_command.py -vv` for detailed output

**Issue: Command not showing in Discord**
```
/factorio research [no autocomplete or description]
```
Solution:
1. Restart the bot
2. Verify decorator includes all `@app_commands.describe` lines
3. Check that function parameters match decorator

---

## 📄 Reference

**Source Code:** [`docs/RESEARCH_COMMAND_SOURCE.py`](./docs/RESEARCH_COMMAND_SOURCE.py)  
**Specification:** [`docs/RESEARCH_COMMAND_IMPLEMENTATION.md`](./docs/RESEARCH_COMMAND_IMPLEMENTATION.md)  
**Tests:** [`tests/test_research_command.py`](./tests/test_research_command.py)  
**Implementation Roadmap:** [`IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md)  

---

## 🌟 Summary

| Item | Details |
|------|----------|
| **Function** | `research_command` |
| **Parameters** | force (optional), action (optional), technology (optional) |
| **Modes** | Display, Research All, Research Single, Undo Single, Undo All |
| **Force Support** | Coop (default "player"), PvP (explicit force names) |
| **Test Coverage** | 17 tests → 91% |
| **File Location** | `src/bot/commands/factorio.py` (~line 1600) |
| **Time to Deploy** | ~10 minutes (copy → test → commit) |

---

**Ready to deploy!** 🚀
