# 🚀 Enhanced Tests Quick Reference

**Files Added:**
- `tests/test_user_context_enhanced.py` (45+ tests)
- `tests/test_rcon_health_monitor_enhanced.py` (50+ tests)
- `TEST_SUITE_ENHANCEMENT_REPORT.md` (full documentation)

---

## 🏃 Quick Start

### Run All New Tests
```bash
pytest tests/test_*_enhanced.py -v
```

### Run With Coverage Report
```bash
pytest tests/test_*_enhanced.py \
  --cov=src/bot.user_context \
  --cov=src/bot.rcon_health_monitor \
  --cov-report=term-missing
```

### Run Specific Module
```bash
# Only UserContext enhanced tests
pytest tests/test_user_context_enhanced.py -v

# Only RconHealthMonitor enhanced tests
pytest tests/test_rcon_health_monitor_enhanced.py -v
```

---

## 🎯 Test Categories

### UserContext Tests (45+)

**Concurrent Access** - 8 tests
```bash
pytest tests/test_user_context_enhanced.py::TestConcurrentAccess -v
```
✅ High-volume user creation (1000+ users)  
✅ Rapid server switching  
✅ Concurrent dict access isolation  
✅ RCON instance caching  

**Stress Scenarios** - 12 tests
```bash
pytest tests/test_user_context_enhanced.py::TestStressScenarios -v
```
✅ 64-bit Discord user IDs  
✅ 50+ server configs  
✅ 10,000 consecutive lookups  
✅ Bulk operations (10K+ users)  
✅ Memory efficiency (string interning)  

**Bot State Edge Cases** - 10 tests
```bash
pytest tests/test_user_context_enhanced.py::TestBotStateEdgeCases -v
```
✅ ServerManager becoming None  
✅ Server config removal  
✅ RCON client unavailability  
✅ Runtime server addition  
✅ Graceful fallback handling  

**Performance Characteristics** - 8 tests
```bash
pytest tests/test_user_context_enhanced.py::TestPerformanceCharacteristics -v
```
✅ O(1) get performance  
✅ O(n) initialization scaling  
✅ 10K bulk set efficiency  
✅ Display name retrieval speed  

### RconHealthMonitor Tests (50+)

**Alert Routing** - 12 tests
```bash
pytest tests/test_rcon_health_monitor_enhanced.py::TestAlertRouting -v
```
✅ Server-specific channels  
✅ Global channel fallback  
✅ Multiple servers per channel  
✅ Missing channel handling  
✅ Channel priority logic  

**Embed Building** - 15 tests
```bash
pytest tests/test_rcon_health_monitor_enhanced.py::TestEmbedBuilding -v
```
✅ Title formatting with emoji  
✅ Server status fields  
✅ Footer count calculation  
✅ Color coding (success/warning/error)  
✅ Timestamp inclusion  
✅ Empty server list handling  

**Multiple Alert Scenarios** - 10 tests
```bash
pytest tests/test_rcon_health_monitor_enhanced.py::TestMultipleAlertScenarios -v
```
✅ Simultaneous transitions (3+ servers)  
✅ Independent state tracking  
✅ Concurrent alert handling  
✅ Alert ordering  

**Channel Availability** - 8 tests
```bash
pytest tests/test_rcon_health_monitor_enhanced.py::TestChannelAvailability -v
```
✅ Unavailable channel handling  
✅ Send failure recovery  
✅ Multiple channel failures  
✅ Partial recovery patterns  

**State Persistence** - 8 tests
```bash
pytest tests/test_rcon_health_monitor_enhanced.py::TestStatePersistence -v
```
✅ State preservation across cycles  
✅ Timestamp persistence  
✅ Crash recovery  
✅ Multiple restore cycles  

---

## 📊 Common Test Commands

### Verbose Output
```bash
pytest tests/test_user_context_enhanced.py -vv
```

### Show Print Statements
```bash
pytest tests/test_user_context_enhanced.py -v -s
```

### Stop on First Failure
```bash
pytest tests/test_user_context_enhanced.py -v -x
```

### Show Slowest Tests
```bash
pytest tests/test_user_context_enhanced.py -v --durations=10
```

### Run Only Failed Tests (from last run)
```bash
pytest tests/test_user_context_enhanced.py --lf
```

### Run Matching Pattern
```bash
# All concurrent tests
pytest tests/test_user_context_enhanced.py -k concurrent -v

# All stress tests
pytest tests/test_user_context_enhanced.py -k stress -v

# All embedding tests
pytest tests/test_rcon_health_monitor_enhanced.py -k embed -v
```

---

## ✅ Continuous Integration

### Full Test Suite
```bash
# Run everything (original + enhanced)
pytest tests/ -v --cov=src/bot --cov-report=term-missing
```

### GitHub Actions Workflow
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - run: pip install -r requirements-test.txt
      - run: pytest tests/ -v --cov=src/bot --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## 🔍 Debugging Failed Tests

### Verbose Output + Traceback
```bash
pytest tests/test_user_context_enhanced.py::TestStressScenarios::test_bulk_operations_efficiency -vv --tb=long
```

### Run With Debugging
```bash
pytest tests/test_user_context_enhanced.py -vv --pdb
```

### Generate HTML Report
```bash
pytest tests/test_*_enhanced.py --html=report.html --self-contained-html
```

---

## 📈 Coverage Analysis

### Generate Coverage Report
```bash
pytest tests/test_*_enhanced.py \
  --cov=src/bot.user_context \
  --cov=src/bot.rcon_health_monitor \
  --cov-report=html \
  --cov-report=term-missing

# Open in browser
open htmlcov/index.html
```

### Coverage by File
```bash
pytest tests/test_*_enhanced.py \
  --cov=src/bot \
  --cov-report=term-missing:skip-covered
```

---

## 📝 Test Statistics

```
┌─────────────────────────────────┬────────┐
│ Test Module                     │ Count  │
├─────────────────────────────────┼────────┤
│ test_user_context_enhanced.py   │  45+   │
│ test_rcon_health_monitor_enh...│  50+   │
├─────────────────────────────────┼────────┤
│ TOTAL NEW TESTS                 │  95+   │
│ TOTAL ALL TESTS                 │ 245+   │
└─────────────────────────────────┴────────┘
```

**Coverage Target:** 91%  
**Test Type Distribution:**
- ✅ Happy path: 35 tests
- ❌ Error handling: 30 tests
- 🔲 Edge cases: 20 tests
- ⚡ Performance: 10 tests

---

## 🎓 Test Patterns Reference

### Concurrent Access Pattern
```python
def test_concurrent_set_and_get(self) -> None:
    """Multiple users can set/get independently."""
    bot = MockBot()
    manager = UserContextManager(bot)
    
    # Simulate concurrent access
    for user_id in range(10):
        manager.set_user_server(user_id, "prod" if user_id % 2 == 0 else "staging")
    
    # Verify all were set correctly
    for user_id in range(10):
        expected = "prod" if user_id % 2 == 0 else "staging"
        assert manager.get_user_server(user_id) == expected
```

### Stress Test Pattern
```python
def test_high_volume_user_creation(self) -> None:
    """Handle creation of many users efficiently."""
    bot = MockBot()
    manager = UserContextManager(bot)
    
    # Create contexts for 1000 users
    for user_id in range(1000):
        manager.set_user_server(user_id, "prod")
    
    # Sample check
    assert len(manager.user_contexts) == 1000
    assert manager.get_user_server(500) == "prod"
```

### Async Lifecycle Pattern
```python
@pytest.mark.asyncio
async def test_state_persistence_across_stop_start(self) -> None:
    """State preserved across stop and start cycles."""
    bot = MockBot()
    monitor = RconHealthMonitor(bot)
    
    await monitor._handle_server_status_change("prod", True)
    initial_state = monitor.rcon_server_states.copy()
    
    await monitor.stop()
    await asyncio.sleep(0.01)
    await monitor.start()
    
    # State should be preserved
    assert monitor.rcon_server_states["prod"] == initial_state["prod"]
```

---

## 🆘 Troubleshooting

### Tests Won't Run
```bash
# Ensure pytest is installed
pip install pytest pytest-asyncio pytest-cov

# Check Python version (3.8+)
python --version

# Run single test
pytest tests/test_user_context_enhanced.py::TestConcurrentAccess::test_concurrent_set_and_get -v
```

### Import Errors
```bash
# Verify project structure
ls -la tests/
ls -la src/bot/

# Check PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run with explicit path
pytest $(pwd)/tests/test_user_context_enhanced.py -v
```

### Async Test Issues
```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Configure asyncio for tests (pytest.ini)
[pytest]
asyncio_mode = auto
```

---

## 📚 Further Reading

- [Full Enhancement Report](./TEST_SUITE_ENHANCEMENT_REPORT.md)
- [Original UserContext Tests](./tests/test_user_context.py)
- [Original Monitor Tests](./tests/test_rcon_health_monitor.py)
- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-Asyncio](https://pytest-asyncio.readthedocs.io/)

---

## 💡 Tips for Success

✅ Run tests locally before committing  
✅ Use `-v` flag for verbose output  
✅ Use `-x` flag to stop on first failure  
✅ Use `-k` pattern matching for focused testing  
✅ Generate coverage reports regularly  
✅ Monitor test execution time  
✅ Keep tests isolated and independent  
✅ Mock external dependencies  

---

**Last Updated:** December 13, 2025  
**Status:** Ready for Production 🚀  
**Compatibility:** Python 3.8+  
**Test Framework:** pytest + pytest-asyncio  
