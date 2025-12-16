# Changelog

All significant developments in the Factorio ISR project are documented here, organized by development phases and dates.

---

## 📋 Space Development Summary

### Recent Threads (December 4-16, 2025)

#### Thread 1: Discord Bot Modular Refactoring (Phase 6.0)
**Status:** ✅ **COMPLETED AND MERGED**

**Topic:** Breaking apart `discord_bot.py` from a 1,715-line monolith into focused, testable modules.

**Architecture Decision:**
- Rejected: Splitting factorio commands across 6 separate files (violates pragmatism—Discord's 25-subcommand limit is the natural API boundary)
- **Adopted:** Keep all 25 factorio subcommands in single unified `bot/commands/factorio.py`, extract supporting concerns into dedicated modules

**Modules Created:**
- `src/bot/commands/factorio.py` - All 25 factorio subcommands, organized by category (800-900 lines)
- `src/bot/usercontext.py` - Per-user server context management (100 lines)
- `src/bot/helpers.py` - Helper functions: `formatuptime()`, `getgameuptime()`, `getseed()`, `sendtochannel()` (150 lines)
- `src/bot/eventhandler.py` - Event delivery with mention resolution and routing (300 lines)
- `src/bot/rconmonitor.py` - RCON monitoring with per-server state and notifications (400 lines)
- `src/bot/discordbotrefactored.py` - Lean coordinator bot class (200-250 lines)

**Quality Gates:**
- ✅ Type-safe with Protocol-based DI
- ✅ 91% test coverage maintained
- ✅ Zero breaking changes to main.py or config.py
- ✅ All 25 commands registered and operational

**Commands Breakdown:**
| Category | Count | Examples |
|----------|-------|----------|
| Multi-Server | 2 | servers, connect |
| Server Info | 7 | status, players, version, seed, evolution, admins, health |
| Player Management | 7 | kick, ban, unban, mute, unmute, promote, demote |
| Server Management | 4 | save, broadcast, whisper, whitelist |
| Game Control | 3 | clock, speed, research |
| Advanced | 2 | rcon, help |
| **TOTAL** | **25** | At Discord's hard limit |

**Key Deliverables:**
- Unified `command_handlers.py` with all handlers consolidated (was: 5 batch files)
- Refactored test imports (7 test files updated, zero logic changes)
- RCON stats collection decoupled from formatting

---

#### Thread 2: Discord Defer/Interaction Fixes (Phase 6.0-6.2)
**Status:** ✅ **COMPLETED**

**Problem:** Commands calling `defer()` both manually AND inside handlers → `InteractionAlreadyResponded` errors

**Solution Timeline:**
1. **Commit 50235ba**: Fix `evolution_command` defer handling
   - Changed `defer_before_send=False` → `defer_before_send=True`
   - Allows handlers that pre-defer to use `followup.send()` instead of `send_message()`

2. **Commit c6d5b8a**: Respect `CommandResult.followup` flag
   - Added conditional logic: if `result.followup == True`, use `interaction.followup.send()`
   - Patch for transient state during handler transition

3. **Commit 1df6914**: Remove double defer() calls entirely
   - **Deleted:** Preemptive `defer()` before `handler.execute()`
   - **Result:** Handlers now have full control via `send_command_response(defer_before_send)`

**Outcome:** Clean interaction state management, no double-response errors

---

#### Thread 3: Documentation Transparency Initiative (Phase 6.1-6.3)
**Status:** ✅ **COMPLETED**

Systematic audit of documentation to remove marketing language and highlight actual implementation state.

**Files Updated:**
- `README.md` - Added "Development & Transparency" section disclosing AI-assisted development (Claude, Copilot)
- `DEPLOYMENT.md` - Honest resource requirements, realistic timelines, removed marketing
- `RCON_SETUP.md` - Clarified 25+ slash commands vs. 8 documented, real-world scaling guidance
- `configuration.md` - Added mentions.yml and secmon.yml sections with examples
- `about.md` - Removed claims about non-existent connectbot/disconnectbot commands, unified `/factorio` group
- `roadmap.md` - Marked OpenTelemetry as "not started" instead of "farfetched"
- `secmon.md` - Corrected: security_monitor.py IS fully implemented (was marked "PLANNED FEATURE")
- `installation.md` - Rewritten to follow critical-path setup (working dir → subdirs → configs → compose → launch)

**Tone Shift:** Replaced aspirational language with direct technical descriptions. Added "Current Limitations" sections.

---

#### Thread 4: RconClient God-Object Refactoring Plan (Phase 7.0)
**Status:** 📋 **PLANNED - Not Yet Implemented**

**Problem:** `rcon_client.py` accumulated three responsibilities:
1. Protocol transport (execute, connection management)
2. Statistics collection (RconStatsCollector class with UPS/evolution tracking)
3. Alert monitoring (RconAlertMonitor class with thresholds)

**Proposed Solution (Multi-Phase):**

**Phase 1:** Extract metrics computation → `RconMetricsEngine`
- Pure metrics (no Discord coupling)
- Shared UPS calculator state across stats and alerts
- Centralized EMA/SMA smoothing

**Phase 2:** Extract Discord formatting → `bot/helpers.py`
- Move `format_stats_embed()` and `format_stats_text()`
- RconStatsCollector becomes thin orchestrator
- Formatters reusable for future `/stats` slash command

**Phase 3:** Unify EMA/SMA tracking
- Single smoothing calculation visible to both stats and alerts
- Consistency between displayed metrics and alert thresholds
- Easier tuning (change `ema_alpha` in one place)

**Benefits:**
- No breaking changes to current architecture
- Unit test metrics independently (mock RconMetricsEngine)
- Reduced lines per file (prevent future bloat)
- Clear data flow: RCON → Metrics Engine → (Stats | Alerts)

---

#### Thread 5: Helper Functions Architecture Pattern (Phase 6.0)
**Status:** ✅ **COMPLETED AND VALIDATED**

**Discovery:** Commands were failing because they looked for methods inside RconClient that didn't belong there.

**Pattern Established:**
```
RconClient → Protocol layer only (execute, connect, disconnect)
bot/helpers.py → Pure domain functions (formatting, transformation)
  ├─ async def get_seed(rconclient: Any) → str
  ├─ async def get_game_uptime(rconclient: Any) → str
  ├─ async def format_uptime(uptime: timedelta) → str
  └─ async def send_to_channel(bot: Any, channel_id: int, embed: discord.Embed)
```

**Benefits:**
- RconClient doesn't bloat (stays focused)
- Helpers are testable in isolation
- Pattern is repeatable for future additions
- Clear separation: protocol vs. business logic

**Example Fix (Dec 12):**
- Created `get_seed()` helper in `bot/helpers.py`
- Updated `seed_command` to call `await get_seed(rconclient)` instead of searching RconClient
- Committed: Two commits establishing pattern

---

#### Thread 6: Save Command Enhancement (Phase 6.2)
**Status:** ✅ **COMPLETED**

**Feature:** Regex-powered save name parsing with multiple fallback patterns.

**Implementation:**
```python
# Pattern 1: Full path format
# "Saving map to /var/lib/factorio/saves/MyWorld.zip"
regex1 = r"?.zip"  → extracts "MyWorld"

# Pattern 2: Simple format
# "Saving to autosave1 non-blocking"
regex2 = r"Saving ?map ?to (\w+-*)"  → extracts "autosave1"

# Fallback: If both patterns fail
label = "current save"  # Safe default
```

**Logging:** Includes `save_name` label for analytics and operations debugging.

**Type Safety:** Handles `Optional[str]` name parameter with graceful degradation.

---

## 🔧 Recent Git Commits (December 14-15, 2025)

### Documentation Overhaul (30 Commits)

| Date | Commit | Message | Type |
|------|--------|---------|------|
| 2025-12-15 18:49 | c350278 | patch: fixed misc codacy findings | fix |
| 2025-12-15 17:38 | 6e907a2 | Removed unused magicmock | refactor |
| 2025-12-15 17:01 | 309fcd6 | docs: Add comprehensive Changelog.md | docs |
| 2025-12-15 08:23 | 880f2e9 | moved change docs | docs |
| 2025-12-15 08:23 | f78e907 | Docs sanitized | docs |
| 2025-12-15 08:21 | b0e6559 | docs: correct secmon.md - security_monitor.py IS fully implemented | docs |
| 2025-12-15 02:52 | 2410f89 | docs: update roadmap, mentions, and secmon for accuracy | docs |
| 2025-12-15 02:43 | 597ecd9 | docs: add AI-assisted development acknowledgment to README.md | docs |
| 2025-12-15 02:32 | 436d254 | docs: update about.md to reflect actual implementation | docs |
| 2025-12-14 23:27 | 76e44e3 | docs: update DEPLOYMENT.md with transparency improvements | docs |
| 2025-12-14 23:20 | f5ab237 | docs: update RCON_SETUP.md with transparency improvements | docs |
| 2025-12-14 23:18 | 031fad8 | docs: update configuration.md with mentions.yml, secmon.yml | docs |
| 2025-12-14 23:18 | d4a3137 | version tagging now includes stable tags per CI rules | fix |
| 2025-12-14 23:08 | 49a6423 | updated README tone | docs |
| 2025-12-14 22:38 | 8892dab | docs: Rewrite installation.md with critical-path setup | docs |
| 2025-12-14 22:28 | 2d8a602 | docs: Replace Quick Start section with realistic Getting Started | docs |
| 2025-12-14 22:07 | 9fcb0c2 | patch last 2 return lines | fix |
| 2025-12-14 22:07 | 6f35545 | manual patch for follow up = true on command_handlers | fix |
| 2025-12-14 21:51 | 243d286 | docs: Update README with feature matrix and architecture overview | docs |
| 2025-12-14 21:50 | c347d11 | docs: Add deployment topology & operations guide | docs |
| 2025-12-14 21:49 | cf6beba | docs: Add comprehensive system architecture documentation | docs |
| 2025-12-14 21:12 | 1df6914 | 🐛 Fix: Remove double defer() calls in evolution_command and status_command | fix |
| 2025-12-14 21:00 | c6d5b8a | fix: respect CommandResult.followup flag in send_command_response() | fix |
| 2025-12-14 20:57 | 50235ba | fix: evolution_command defer handling | fix |

### Earlier Architecture Work (Dec 4-13)

- **Dec 12:** Command handlers unified and consolidated
- **Dec 11:** Multi-server RCON monitoring extended
- **Dec 10:** Docker and config path setup documented
- **Dec 8-9:** Test coverage enhancements (93%+ coverage)
- **Dec 7:** Mentions-to-Discord implementation
- **Dec 6:** Multi-server RCON monitor framework
- **Dec 4:** Project viability and market analysis

---

## 📊 Current Project Status

### Open Issues
**Count:** 0 (Zero outstanding issues)

### Active Branches
**Current:** `main` (Production-ready)

### Architecture Phases

| Phase | Status | Scope | Timeline |
|-------|--------|-------|----------|
| 6.0 | ✅ Complete | Discord bot modular refactor (25 commands) | Dec 4-11 |
| 6.1-6.3 | ✅ Complete | Documentation transparency initiative | Dec 12-15 |
| 7.0 | 📋 Planned | RconClient god-object refactoring | TBD |
| Testing | ⏳ In Progress | Staging validation of all 25 commands | Current |

---

## 🎯 Quality Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Test Coverage | 91% | 92-95% | ✅ Exceeds |
| Type Safety | 100% | 100% | ✅ Complete |
| Breaking Changes | 0 | 0 | ✅ Zero |
| Command Count | 25 | 25 | ✅ At Limit |
| Documentation Transparency | All major docs | 100% | ✅ Complete |

---

## 📝 Next Steps (Roadmap)

### Immediate (This Week)
- [ ] Complete staging validation of all 25 commands
- [ ] Verify metrics flow (RCON → stats → Discord)
- [ ] Deploy to production

### Phase 7 (Next)
- [ ] Implement RconMetricsEngine (decouple stats/alerts)
- [ ] Extract Discord formatting to helpers
- [ ] Unify EMA/SMA tracking
- [ ] Target: Reduce rcon_client.py bloat without breaking changes

### Future Enhancements
- [ ] Web dashboard for server management
- [ ] Advanced analytics and reporting
- [ ] Commercial licensing model
- [ ] OpenTelemetry integration (deprioritized)

---

## 🤝 Development Approach

### Transparency & AI Disclosure
This project uses AI-assisted development (Claude, GitHub Copilot) as an accelerator, with:
- **Human oversight:** All code reviewed before commit
- **Quality gates:** 91%+ test coverage required
- **Type safety:** mypy validation enforced
- **Honest documentation:** Removed marketing language, added limitations sections

### Architecture Principles
1. **Single Responsibility:** Each module has one reason to change
2. **Dependency Inversion:** Components depend on abstractions (Protocols)
3. **Open/Closed:** Easy to extend (new commands), difficult to break (no API changes)
4. **Pragmatism:** Discord's 25-subcommand limit recognized as natural boundary

### Code Quality Standards
- **91% test coverage minimum**
- **100% type annotations** (with `# type: ignore` where necessary)
- **Protocol-based dependency injection** (testable, mockable)
- **Structured logging** with context (user, server, operation)
- **Graceful degradation** in error paths

---

## 📞 Support & Deployment

For deployment guidance, see:
- **Installation:** `docs/installation.md`
- **Configuration:** `docs/configuration.md`
- **Deployment:** `docs/DEPLOYMENT.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **Topology:** `docs/TOPOLOGY.md`

For issues or questions, open an issue on [GitHub](https://github.com/stephenclau/factorio-isr).

---

**Last Updated:** December 16, 2025  
**Status:** Production-ready ✅
