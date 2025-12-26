---
layout: default
title: Roadmap
---

# 🛣️ Project Roadmap

Development trajectory of Factorio ISR with honest status assessments.

For detailed observability plans (logging, metrics, tracing), see **[Observability Roadmap](OBSERVABILITY_ROADMAP.md)**.

## Phase 1: Core Foundation ✅
**Status:** Complete (v0.1.0)

- [x] Log tailing implementation (`log_tailer.py`)
- [x] Basic event parsing (`event_parser.py`)
- [x] Discord Webhook integration (Legacy, removed in v2.x)
- [x] Docker containerization
- [x] Health check endpoint

## Phase 2: Configuration & Extensibility ✅
**Status:** Complete (v0.2.0)

- [x] YAML-based pattern configuration
- [x] Support for custom event patterns
- [x] ReDoS protection for regex (300ms timeout + validation)
- [x] Strict configuration validation

## Phase 3: RCON Integration ✅
**Status:** Complete (v0.3.0)

- [x] RCON client implementation (`rcon_client.py`)
- [x] Authentication & Reconnection logic
- [x] Server stats (players, game time)
- [x] Player online list
- [x] Evolution factor tracking

## Phase 4: Discord Bot & Commands ✅
**Status:** Complete (v1.0.0)

- [x] Native Discord bot implementation (`discord_bot.py`)
- [x] Slash commands (`/stats`, `/players`, `/time`, etc.)
- [x] Embed-based notifications
- [x] Permission system

## Phase 5: Multi-Server Architecture ✅
**Status:** Complete (v2.0.0)

- [x] `servers.yml` configuration
- [x] Server Manager coordinator (`server_manager.py`)
- [x] Multi-server RCON monitoring
- [x] Unified bot presence ("Watching 3/3 servers online")
- [x] Per-server event routing
- [x] Per-server stats intervals and alert thresholds

## Phase 6: Hardening & Observability ✅/🚧
**Status:** Partially Complete (v2.1.x)

### Completed ✅
- [x] Metrics polling & UPS alerts (`RconAlertMonitor`)
- [x] Security hardening (Rate limiting in `rate_limiting.py`)
- [x] Input sanitization (Discord message escaping)
- [x] Hardcoded config paths for Docker reliability
- [x] Removal of legacy webhook code
- [x] RCON health monitoring (`RconHealthMonitor`)
- [x] Modular bot architecture (Phase 7.0 refactor)

### Planned 🚧
- [ ] **OpenTelemetry integration** (See [Observability Roadmap](OBSERVABILITY_ROADMAP.md))
  - *Status:* Not started, requires metrics pipeline design
  - *Timeline:* Q2 2026 earliest
- [ ] **Dedicated `security_monitor.py` module** (See [secmon.md](secmon.md))
  - *Status:* ReDoS protection exists, but no unified security monitor yet
  - *Timeline:* TBD

## Phase 7: Advanced Features 📋
**Status:** Planned (timeline TBD)

### High Priority
- [ ] **Hot Reloading**: Update patterns/config without restart
  - *Complexity:* Medium (requires file watchers + safe reload logic)
  - *Timeline:* Q1-Q2 2026

### Medium Priority
- [ ] **Data Persistence**: SQLite/Postgres for long-term stats
  - *Use case:* Historical UPS trends, player activity graphs
  - *Complexity:* Medium (schema design + migration strategy)
  - *Timeline:* Q2-Q3 2026

### Low Priority
- [ ] **Web Dashboard**: Control plane for server management
  - *Complexity:* High (requires frontend + auth + API)
  - *Timeline:* Q3-Q4 2026 (dependent on commercial demand)
- [ ] **Mod Portal Integration**: Check for mod updates
  - *Complexity:* Low (Factorio API scraping)
  - *Timeline:* Q2 2026 (nice-to-have)

---

## Honest Assessment

**What's production-ready:**
- Multi-server monitoring with RCON
- Discord bot with 25+ slash commands
- UPS alerting and health monitoring
- Docker/Kubernetes deployment
- 80%+ test coverage

**What's not ready:**
- OpenTelemetry (requires significant R&D)
- Web dashboard (no frontend exists)
- Data persistence (no database layer)
- Hot reloading (requires careful implementation)

**Development pace:**
- Core features: Actively maintained
- Advanced features: Dependent on commercial adoption
- Community PRs: Welcomed and reviewed

---

## Contributing

Interested in contributing to Phase 7 features? See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

**Priority areas:**
- Hot reloading implementation
- SQLite persistence layer
- OpenTelemetry integration
- Security enhancements

---

> **📄 Licensing Information**
> 
> This project is open licensed:
> - **[MIT](../LICENSE)** – Open source use (free)