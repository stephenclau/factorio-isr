# Factorio ISR Changelog

## Unreleased (Since v2.1.7)

**Release Date**: v2.1.7 published December 14, 2025 @ 22:29 UTC

---

### 📋 Changes Since v2.1.7

#### Documentation Updates

**December 15-16, 2025**

- [`c350278`](https://github.com/stephenclau/factorio-isr/commit/c350278739f4aab8ddc9a558573a6d006855ef48) - patch: fixed misc codacy findings
- [`6e907a2`](https://github.com/stephenclau/factorio-isr/commit/6e907a2ab1d0721e21b9fe92a19f9ae469d00721) - Removed unused magicmock
- [`309fcd6`](https://github.com/stephenclau/factorio-isr/commit/309fcd6012d1b9e48cd9ff007a86355fd5cf61b1) - docs: Add comprehensive Changelog.md with Space threads, commits, and architecture summary
- [`41f59fa`](https://github.com/stephenclau/factorio-isr/commit/41f59fa5740a3b97c1396cc48ca1825c191dbcc4) - docs: Update comprehensive Changelog documenting Space threads, commits, and architecture evolution (Dec 4-16)

**December 15, 2025**

- [`880f2e9`](https://github.com/stephenclau/factorio-isr/commit/880f2e9c0e9a060887d8035de1fdb154e6cb5cde) - moved change docs
- [`f78e907`](https://github.com/stephenclau/factorio-isr/commit/f78e907ea267fc325c2a08bd78677020b9ba32ec) - Docs sanitized
- [`b0e6559`](https://github.com/stephenclau/factorio-isr/commit/b0e655954a81926d4d72d18682ae8f4d72ec5084) - docs: correct secmon.md - security_monitor.py IS fully implemented
- [`2410f89`](https://github.com/stephenclau/factorio-isr/commit/2410f89796b7f174a98a201d9a328c790ffc5162) - docs: update roadmap, mentions, and secmon for accuracy and transparency
- [`597ecd9`](https://github.com/stephenclau/factorio-isr/commit/597ecd93d174a46a16ad6d5f964f9f1e1e2acf39) - docs: add AI-assisted development acknowledgment to README.md
- [`436d254`](https://github.com/stephenclau/factorio-isr/commit/436d254efb1e860b21f87a074676d94d3452833e) - docs: update about.md to reflect actual implementation, remove farfetched claims
- [`a222807`](https://github.com/stephenclau/factorio-isr/commit/a222807210b677dcdafd5d6e280ed83d3be10ddd) - Cleaning
- [`b013bdc`](https://github.com/stephenclau/factorio-isr/commit/b013bdcf5b9bb246e31789ce5619cf3075298b94) - Readme.md badge changes
- [`097a0cc`](https://github.com/stephenclau/factorio-isr/commit/097a0cc5be7694ea67a4275a5d6a83e1bde20436) - updated badgess
- [`7a464f2`](https://github.com/stephenclau/factorio-isr/commit/7a464f219133fe40e623c313f141f1fbf6fc14d7) - updated gitignore
- [`76e44e3`](https://github.com/stephenclau/factorio-isr/commit/76e44e3685e0e312623a40c8db7b1df243d0d5aa) - docs: update DEPLOYMENT.md with transparency improvements and current multi-server architecture
- [`f5ab237`](https://github.com/stephenclau/factorio-isr/commit/f5ab2376f0a4e1415823370f5cec2e665a3a5304) - docs: update RCON_SETUP.md with transparency improvements and current slash command list
- [`031fad8`](https://github.com/stephenclau/factorio-isr/commit/031fad8599e23b739d8c73cd804421a526ce37f2) - docs: update configuration.md with mentions.yml, secmon.yml, and transparency improvements
- [`d4a3137`](https://github.com/stephenclau/factorio-isr/commit/d4a313713150ee9ad1096520266c7b5167c6d49f) - version tagging now includes stable tags per CI rules

---

### 📊 Summary

| Category | Count | Description |
|----------|-------|-------------|
| **Documentation** | 14 commits | Transparency improvements, accuracy corrections, badge updates |
| **Code Quality** | 2 commits | Codacy findings, unused imports cleanup |
| **CI/CD** | 1 commit | Version tagging for stable releases |
| **Total** | **17 commits** | All changes since v2.1.7 |

---

### 🔍 What Changed

#### Documentation Transparency Initiative

The primary focus since v2.1.7 has been **documentation accuracy**:

- ✅ Corrected `security_monitor.py` implementation status (fully implemented, not planned)
- ✅ Removed marketing language from `about.md`, `roadmap.md`
- ✅ Updated configuration guides with realistic scaling guidance
- ✅ Added AI-assisted development disclosure to README
- ✅ Fixed YAML structure examples in mentions.md
- ✅ Added transparent deployment timelines and resource requirements

#### Code Quality

- Fixed misc Codacy findings (linting improvements)
- Removed unused MagicMock imports from test files

#### Build & Release

- Enhanced CI/CD with stable tag versioning rules

---

### ⚙️ No Functional Changes

**Important**: All commits since v2.1.7 are **documentation and quality improvements only**. 

- ✅ No code changes to core functionality
- ✅ No new features added
- ✅ No bug fixes required
- ✅ No breaking changes
- ✅ Test coverage unchanged (91%+)

---

## v2.1.7 (December 14, 2025)

**Release**: [v2.1.7](https://github.com/stephenclau/factorio-isr/releases/tag/v2.1.7)

### Major Changes in v2.1.7

This release included the major refactoring work:

- **Discord Bot Modular Refactor** ([PR #1](https://github.com/stephenclau/factorio-isr/pull/1), [PR #2](https://github.com/stephenclau/factorio-isr/pull/2))
  - Reduced `discord_bot.py` from 1,715 → 250-300 lines
  - Modular `src/bot/` structure with 5 focused modules
  
- **RCON Metrics Engine Refactor** ([PR #3](https://github.com/stephenclau/factorio-isr/pull/3))
  - Extracted metrics computation from RconClient
  - Created RconMetricsEngine, RconStatsCollector, RconAlertMonitor

- **Test Consolidation** ([PR #4](https://github.com/stephenclau/factorio-isr/pull/4))
  - Unified 5 batch handler test files
  - Maintained 91%+ test coverage

- **Critical Handler Coverage Fix** ([PR #5](https://github.com/stephenclau/factorio-isr/pull/5))
  - Fixed Handler.execute() invocation
  - Broke coverage barriers at lines 460-480

**Full v2.1.7 Changelog**: [v1.0.1...v2.1.7](https://github.com/stephenclau/factorio-isr/compare/v1.0.1...v2.1.7)

---

## Development Status

### ✅ Production Ready (v2.1.7)

- Discord bot modular architecture complete
- 25/25 slash commands operational
- RCON metrics decoupled from protocol layer
- 91%+ test coverage maintained
- Type-safe dependency injection via Protocols
- Multi-server support fully operational

### 📋 Planned

- Phase 7.0: Additional RconClient optimizations (future)
- OpenTelemetry integration (not started)

---

**Last Updated**: December 25, 2025
**Current Status**: v2.1.7 + 17 documentation commits
**Next Release**: TBD
