---
layout: default
title: About
---

# About Factorio ISR

Factorio ISR is a production-ready Discord integration for Factorio servers with multi-server support, RCON monitoring, and async architecture.

## What It Actually Does

**Discord Integration:** Async Discord bot with proper connection/disconnection lifecycle, event sending with rate limiting, and embed/plaintext fallback support.

**Slash Commands:** Discrete slash commands (`/stats`, `/players`, `/time`, `/save`, etc.) for server control and queries. Each command operates independently—no unified command group.

**Multi-Server Support:** Single bot instance monitors multiple Factorio servers simultaneously, with per-server RCON connections, Discord channels, and configuration.

## Server Monitoring & Metrics

**UPS-Aware Stats Pipeline:** `RconStatsCollector` and `UPSCalculator` sample RCON tick deltas to compute accurate UPS metrics. Periodic stats snapshots are posted to Discord with embed formatting and plaintext fallbacks.

**Performance Alerting:** `RconAlertMonitor` runs per server with configurable thresholds, consecutive-sample logic, and cooldowns. Raises low-UPS alerts and recovery notifications using structured embeds.

**RCON Health Monitoring:** `RconHealthMonitor` tracks RCON connection status per server and posts alerts on connection/disconnection events (configurable modes: `transition` or `interval`).

## Multi-Server Architecture

**ServerManager Orchestration:** `ServerManager` coordinates RCON clients, stats collectors, alert monitors, and log tailers per server. Provides helpers like `get_alert_states()` and `stop_all()` for lifecycle management.

**Rich Per-Server Configuration:** `servers.yml` provides per-server tuning:
- `enable_ups_stat`, `enable_evolution_stat` - Toggle specific metrics
- `stats_interval` - Polling frequency (default: 300s)
- `enable_alerts` - Enable/disable UPS alerts
- `ups_warning_threshold`, `ups_recovery_threshold` - Alert thresholds
- `alert_check_interval`, `alert_samples_required` - Alert sensitivity
- `alert_cooldown` - Throttle repeat alerts
- `rcon_status_alert_mode` - RCON health alert mode (`transition` or `interval`)
- `rcon_status_alert_interval` - Interval for periodic RCON health alerts

## Modular Refactored Architecture (Phase 6.0/7.0)

**Separation of Concerns:** The bot delegates responsibilities to specialized modules:
- `bot.user_context`: Per-user server context management
- `bot.helpers`: Utilities (presence, uptime formatting, channel sending)
- `bot.event_handler`: Event sending with mention resolution
- `bot.rcon_health_monitor`: RCON status monitoring and notifications
- `bot.presence_manager`: Bot presence updates ("Watching X/Y servers online")
- `bot.commands.factorio`: All `/factorio*` slash command implementations

**Public API Preserved:** The `DiscordBot` class maintains backward compatibility while internal implementation uses modular components.

## Test Coverage & Reliability

**High-Coverage pytest Suites:** Test modules for Discord bot, RCON client, log tailer, stats collector, and alert monitor. Tests cover async paths, error handling, and lifecycle edges.

**Unit & Integration:** Tests include both unit-level mocking and integration-style scenarios (e.g., RCON connection validation, command error handling).

## Current Limitations

**No Unified Command Group:** Slash commands are discrete (`/stats`, `/players`) rather than grouped under `/factorio <subcommand>`. This is intentional for Discord UX simplicity.

**No Login System:** Bot uses standard Discord token authentication. No separate user login/auth system.

**No Web Dashboard:** Configuration is file-based (`servers.yml`, `mentions.yml`). No web UI for management.

**RCON Required for Commands:** Most slash commands require RCON to be configured per server. Log-only servers support event monitoring but not interactive commands.

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](../LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)