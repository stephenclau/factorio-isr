---
layout: default
title: Roadmap
---

# 🛣️ Project Roadmap

This document outlines the development trajectory of Factorio ISR.

For detailed observability plans (logging, metrics, tracing), see **[Observability Roadmap](OBSERVABILITY_ROADMAP.md)**.

## Phase 1: Core Foundation ✅
**Status:** Complete (v0.1.0)

- [x] Log tailing implementation (`log_tailer.py`)
- [x] Basic event parsing (`event_parser.py`)
- [x] Discord Webhook integration (Legacy)
- [x] Docker containerization
- [x] Health check endpoint

## Phase 2: Configuration & Extensibility ✅
**Status:** Complete (v0.2.0)

- [x] YAML-based pattern configuration
- [x] Support for custom event patterns
- [x] ReDoS protection for regex
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
- [x] Slash commands (`/factorio status`, `/factorio players`)
- [x] Embed-based notifications
- [x] Permission system

## Phase 5: Multi-Server Architecture ✅
**Status:** Complete (v2.0.0)

- [x] `servers.yml` configuration
- [x] Server Manager coordinator (`server_manager.py`)
- [x] Multi-server RCON monitoring
- [x] Unified bot presence ("Watching 3 servers")
- [x] Per-server event routing

## Phase 6: Hardening & Observability ✅
**Status:** In Use / Ongoing (v2.1.0)

- [x] Metrics polling & UPS alerts
- [x] Security hardening (Rate limiting, Input sanitization)
- [x] Hardcoded config paths for Docker reliability
- [x] Removal of legacy webhook code
- [ ] OpenTelemetry integration (See [Observability Roadmap](OBSERVABILITY_ROADMAP.md))

## Phase 7: Advanced Features (Planned) 📋

- [ ] **Hot Reloading**: Update patterns/config without restart
- [ ] **Data Persistence**: SQLite/Postgres for long-term stats
- [ ] **Web Dashboard**: Control plane for server management
- [ ] **Mod Portal Integration**: Check for mod updates

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)
