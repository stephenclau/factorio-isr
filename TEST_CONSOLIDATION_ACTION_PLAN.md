# 🚀 Test Consolidation Action Plan – Execution Ready

**Status:** ✅ Decision confirmed — Ready to execute  
**Date:** 2025-12-13  
**Consolidation Target:** 7 test files → 2 canonical files

---

## ✅ Confirmed Decisions (User Input)

| Question | Answer | Implication |
|----------|--------|------------|
| Integration tests require real Discord API? | **YES** | ➜ MOVE to `tests/manual/` |
| Real harness tests require real RCON? | **NO** | ➜ Consolidate into primary suite OR delete if redundant |
| Gap filler file exists? | **DELETED** | ✓ Already removed |
| Complete tests file exists? | **DELETED** | ✓ Already removed |
| Legacy tests still valid? | **NO** | ✓ Patterns refactored away |

---

## 📊 Current Status

### Files Already Cleaned ✅
```bash
❌ test_factorio_commands_gap_filler.py       # Already deleted
❌ test_factorio_commands_complete.py         # Already deleted  
❌ test_factorio_commands_legacy.py           # Already deleted
```

### Files Remaining for Action 🎯
```bash
✅ tests/test_factorio_commands.py            # PRIMARY - KEEP
✅ tests/manual/smoke_test_factorio_commands.py  # MANUAL - KEEP
⚠️  tests/test_factorio_commands_integration.py   # MOVE to manual/ (Discord API required)
❓ tests/test_factorio_commands_real_harness.py  # REVIEW & DELETE or CONSOLIDATE
```

---

## 🎯 Action Items (In Order)

### PHASE 1: Review Real Harness Tests (5 min)

**Goal:** Determine if real_harness tests are redundant or necessary

```bash
# 1. Check file size and structure
wc -l tests/test_factorio_commands_real_harness.py
head -50 tests/test_factorio_commands_real_harness.py

# 2. Compare against integration tests
diff <(grep "^class Test" tests/test_factorio_commands_real_harness.py) \
     <(grep "^class Test" tests/test_factorio_commands_integration.py)

# 3. Search for unique test patterns
grep "async def test_" tests/test_factorio_commands_real_harness.py | \
  comm -23 \
    <(grep "async def test_" tests/test_factorio_commands_real_harness.py | sort) \
    <(grep "async def test_" tests/test_factorio_commands_integration.py | sort)
```

**Decision Tree:**
```
IF real_harness has unique tests (not in integration):
  ➜ Consolidate into integration file
  
ELSE:
  ➜ Delete real_harness file (redundant)
```

---

### PHASE 2: Move Integration Tests to Manual Suite (10 min)

**Current Location:** `tests/test_factorio_commands_integration.py`  
**New Location:** `tests/manual/test_factorio_commands_integration.py`

**Why Move?** Integration tests require real Discord API (per your answer)

```bash
# 1. Move file to manual directory
mkdir -p tests/manual
mv tests/test_factorio_commands_integration.py tests/manual/

# 2. Update imports in moved file (if any relative imports broken)
# Add this at top of tests/manual/test_factorio_commands_integration.py:
# import sys
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# 3. Verify pytest can still find it
pytest tests/manual/test_factorio_commands_integration.py --collect-only
```

**Update CI/CD if needed:**
```yaml
# Add to .github/workflows/test.yml (if it exists)
- name: Unit tests (mocked, fast)
  run: pytest tests/test_factorio_commands.py -v

- name: Manual integration tests (requires real Discord API)
  run: pytest tests/manual/ -v -m manual
  if: ${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}
```

---

### PHASE 3: Review & Action Real Harness Tests (5 min)

```bash
# Step A: Review file structure
cat tests/test_factorio_commands_real_harness.py | head -100

# Step B: Check for unique test logic
if [[ $(grep -c "async def test_" tests/test_factorio_commands_real_harness.py) -eq 0 ]]; then
  # No tests, just delete
  rm tests/test_factorio_commands_real_harness.py
  echo "✓ Deleted: test_factorio_commands_real_harness.py (empty)"
else
  # Has tests, consolidate
  echo "ℹ️ Consolidating unique tests from real_harness into integration..."
  # (Manual merge required - ask if needed)
fi
```

---

### PHASE 4: Verify Final Structure (5 min)

```bash
# Check directory structure
echo "📁 Tests Structure After Consolidation:"
tree tests/ -I '__pycache__'

# Expected output:
# tests/
# ├── conftest.py
# ├── test_factorio_commands.py           ← PRIMARY (1,200+ lines)
# │   ├── TestMultiServerCommands
# │   ├── TestServerInformation
# │   ├── TestPlayerManagement
# │   ├── TestServerManagement
# │   ├── TestGameControl
# │   ├── TestAdvancedCommands
# │   ├── TestErrorPaths
# │   ├── TestEdgeCases
# │   └── TestCommandRegistration
# └── manual/
#     ├── smoke_test_factorio_commands.py    ← MANUAL SMOKE
#     └── test_factorio_commands_integration.py  ← MANUAL INTEGRATION (Discord API required)
```

---

### PHASE 5: Run Full Test Suite (10 min)

```bash
# 1. Run unit tests (should be fast, mocked)
echo "🧪 Running unit tests..."
pytest tests/test_factorio_commands.py -v --tb=short --cov=bot.commands.factorio --cov-report=term-missing

# 2. Verify 91% coverage target maintained
echo "📊 Coverage report:"
pytest tests/test_factorio_commands.py --cov=bot.commands.factorio --cov-report=term-missing --cov-fail-under=91

# 3. List all remaining test files
echo "📋 All test files after consolidation:"
find tests/ -name "test_*.py" -o -name "*_test.py" | sort
```

---

### PHASE 6: Commit Changes (5 min)

```bash
# 1. Stage changes
git add tests/
git add TEST_CONSOLIDATION_ACTION_PLAN.md

# 2. Create commit
git commit -m "refactor: consolidate test suite (7→2 files)

- MOVED: test_factorio_commands_integration.py → tests/manual/ (requires real Discord API)
- DELETED: test_factorio_commands_real_harness.py (redundant with integration tests)
- KEPT: test_factorio_commands.py (primary unit test suite, 91% coverage target)
- KEPT: smoke_test_factorio_commands.py (manual smoke testing)

Benefits:
- 71% reduction in test files (7→2)
- Single canonical source of truth for unit tests
- Clear separation: unit tests (mocked) vs manual integration tests
- Easier maintenance and clearer ownership

Consolidation decisions per review:
✓ Integration tests require real Discord API → moved to manual/
✓ Real harness tests reviewed and consolidated
✓ Gap filler, complete, legacy files already removed
"

# 3. Verify commit
git log -1 --stat
```

---

## ✅ Final Checklist

- [ ] **Phase 1 Complete:** Real harness tests reviewed
  - [ ] Decision made: DELETE or CONSOLIDATE
  - [ ] Action taken
  
- [ ] **Phase 2 Complete:** Integration tests moved to manual/
  - [ ] File moved: `tests/test_factorio_commands_integration.py` → `tests/manual/`
  - [ ] Imports verified
  - [ ] Pytest can collect tests
  
- [ ] **Phase 3 Complete:** Real harness tests handled
  - [ ] File deleted or consolidated
  - [ ] Redundant tests removed
  
- [ ] **Phase 4 Complete:** Final structure verified
  - [ ] `tests/` contains only unit test file + conftest
  - [ ] `tests/manual/` contains integration + smoke tests
  - [ ] No orphaned test files
  
- [ ] **Phase 5 Complete:** Tests pass
  - [ ] Unit tests: `pytest tests/test_factorio_commands.py` ✓
  - [ ] Coverage maintained: 91%+ ✓
  - [ ] Manual tests discoverable: `pytest tests/manual/` ✓
  
- [ ] **Phase 6 Complete:** Committed
  - [ ] Changes staged: `git add tests/`
  - [ ] Commit created with clear message
  - [ ] Log verified: `git log -1`

---

## 📈 Expected Outcomes

### Before Consolidation
```
7 test files
├── test_factorio_commands.py (canonical)
├── test_factorio_commands_integration.py (unclear scope)
├── test_factorio_commands_real_harness.py (redundant?)
├── test_factorio_commands_gap_filler.py (ad-hoc) ✗ DELETED
├── test_factorio_commands_complete.py (conflict) ✗ DELETED
├── test_factorio_commands_legacy.py (outdated) ✗ DELETED
└── smoke_test_factorio_commands.py (manual)

Maintenance burden: HIGH (unclear ownership, overlapping scope)
```

### After Consolidation
```
2 focused test files
├── tests/
│   └── test_factorio_commands.py (CANONICAL - all unit tests)
│       ├── 1,200+ lines
│       ├── 25 commands covered
│       ├── 91% coverage target
│       └── Happy path + error path + edge cases
│
└── tests/manual/
    ├── smoke_test_factorio_commands.py (real infrastructure testing)
    └── test_factorio_commands_integration.py (Discord API integration)

Maintenance burden: LOW (clear ownership, separated concerns)
```

### Quality Improvements
| Metric | Before | After | Gain |
|--------|--------|-------|------|
| Test Files | 7 | 2 | **71% reduction** |
| Duplicate Coverage | High | None | **Eliminated** |
| Maintenance Points | 7 | 2 | **71% fewer** |
| Clear Ownership | ❌ | ✅ | **Clarity** |
| CI/CD Time | Slower | Faster | **⚡ Optimized** |
| Developer Experience | Confusing | Clear | **✅ Better** |

---

## 🎓 Key Insights

### Why Integration Tests → Manual?
- **Integration tests execute actual command closures** (not mocks)
- **Require Discord.py to be instantiated** (real API expectations)
- **Not suitable for CI/CD automated testing** (need manual verification)
- **Better as pre-deployment validation** (catch real-world issues)

### Why Primary Suite Stays?
- **Unit tests mock all dependencies** (fast, repeatable)
- **91% coverage target** drives comprehensiveness
- **Suitable for CI/CD** (automated on every push)
- **Happy path + error path methodology** proves code quality
- **Well-organized structure** makes maintenance easy

### Why Manual Smoke Tests?
- **Separate concern:** manual verification vs automated testing
- **Real infrastructure:** Discord bot token, RCON server
- **Pre-deployment gate:** catch issues before production

---

## 🤝 Next Steps

1. **Review this action plan** – Any questions?
2. **Run Phase 1** – Check real_harness tests
3. **Execute Phases 2-6** – Complete consolidation
4. **Verify coverage** – Confirm 91%+ maintained
5. **Commit changes** – Push consolidated structure

Once you confirm readiness or ask clarifying questions, I can automate these phases! 🚀

---

## 📞 Questions?

Before executing:

1. Should I automate the full consolidation (Phases 1-6)?
2. Should real_harness tests be consolidated or deleted? (I can review the file)
3. Any CI/CD pipeline updates needed for the new structure?
4. Should manual tests be gated behind a flag in CI/CD?

Let me know and we'll execute! ✨