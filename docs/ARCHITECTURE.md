# System Architecture

Factorio ISR is a **production-grade multi-server Discord integration system** designed for enterprise Factorio hosting.

## Core Layers

1. **Input & Configuration** – Load servers.yml, patterns, environment variables
2. **Log Ingestion** – Poll multiple Factorio server logs concurrently  
3. **Discord Integration** – Bot mode, slash commands, event routing
4. **Server Control** – RCON clients, UPS metrics, alert thresholds
5. **Bot Commands** – 25+ slash handlers, per-user server preferences
6. **Observability** – HTTP health endpoint, structured logging

## Component Organization

### Layer 1: Input & Configuration

| Component | Responsibility |
|-----------|----------------|
| **config.py** | Load servers.yml, environment variables, validate schema |
| **pattern_loader.py** | YAML → compiled regex with ReDoS protection |
| **event_parser.py** | Match log lines against patterns, extract metadata |
| **security_monitor.py** | Identify malicious input based on config rules |

### Layer 2: Log Ingestion

| Component | Responsibility |
|-----------|----------------|
| **multi_log_tailer.py** | Monitor multiple server logs simultaneously |
| **log_tailer.py** | Poll one Factorio console.log with rotation support |
| **Application** | Coordinate tailers, routing, lifecycle |

### Layer 3: Discord Integration

| Component | Responsibility |
|-----------|----------------|
| **discord_interface.py** | Factory: create bot or webhook interface |
| **discord_bot.py** | Login, sync commands, handle interactions |
| **event_handler.py** | Transform events into Discord embeds |
| **helpers.py** | Construct rich Discord messages |

### Layer 4: Server Control & Monitoring

| Component | Responsibility |
|-----------|----------------|
| **server_manager.py** | Orchestrate RCON clients, stats, alerts per server |
| **rcon_client.py** | RCON authentication, command sending |
| **rcon_metrics_engine.py** | Calculate UPS, evolution, tick deltas |
| **rcon_stats_collector.py** | Periodic snapshots of player count, evolution |
| **rcon_alert_monitor.py** | Threshold logic, alert cooldowns, recovery |

### Layer 5: Bot Commands & Context

| Component | Responsibility |
|-----------|----------------|
| **src/bot/commands/** | 25+ slash handlers (status, players, admin, metrics) |
| **user_context.py** | Track per-user server preferences |
| **rcon_health_monitor.py** | Per-server connection status |

### Layer 6: Observability

| Component | Responsibility |
|-----------|----------------|
| **health.py** | HTTP /health endpoint for Docker, K8s |
| **structlog** | JSON/console logs with context variables |
| **Metrics** | UPS, evolution, uptime, command latency |

## Request Flow: Log Line → Discord

```
MultiServerLogTailer polls console.log
  ↓
New line → EventParser.parse_line(line, server_tag)
  ↓
Pattern matches → FactorioEvent created
  ↓
Event routing → check pattern config (which channel)
  ↓
DiscordInterface.send_event(event)
  ├─ Bot mode: check auth, send via Discord.py
  └─ Webhook mode: POST to webhook
  ↓
Discord channel receives message
```

**Latency:** ~100-500ms (poll + parse + API)

## Multi-Server Orchestration

### ServerManager Pattern

Each server has:
- RCONClient (connected, authenticated)
- StatsCollector (periodic snapshots)
- AlertMonitor (threshold checks)
- Isolated state (uptime, cooldowns)

### Startup Sequence

```
1. load_config() → servers.yml parsed
2. Application.setup() → EventParser initialized  
3. DiscordInterfaceFactory.create_interface() → Bot ready
4. Application._setup_multi_server_manager()
   ├─ ServerManager created
   ├─ For each server:
   │  ├─ add_server(config, defer_stats=True)  
   │  ├─ RCON connects
   │  └─ Stats NOT started yet
   └─ ServerManager → wired to Discord bot
5. discord.connect() → Bot logins
6. Application._start_multi_server_stats_collectors()
   ├─ For each server: start_stats_for_server(tag)
   └─ StatsCollector + AlertMonitor active
```

**Key:** defer_stats=True ensures RCON connects before Discord (no race).

## Security Layers

### Load-Time Validation
```
servers.yml → YAML safe_load → Schema validation → Regex compile (timeout)
```

### Runtime Sanitization  
```
Log line → Regex match (timeout) → Extract → Escape special chars → Discord
```

### Command Authorization
```
/factorio admin command → Check user permissions → Execute or deny
```

## Configuration Example

```yaml
servers:
  prod:
    name: "Production"
    log_path: /factorio/instances/prod/console.log
    rcon_host: localhost
    rcon_port: 27015
    rcon_password: ${RCON_PASSWORD}
    
    enable_stats_collector: true
    enable_ups_stat: true
    enable_evolution_stat: true
    collect_interval_seconds: 30
    
    enable_alerts: true
    ups_warning_threshold: 30.0
    ups_recovery_threshold: 45.0
    alert_cooldown_seconds: 300
    
    alert_channel_id: 1234567890
    status_channel_id: 1234567891
```

## Test Coverage

| Layer | Tests | Coverage |
|-------|-------|----------|
| Config | 80+ | 88%+ |
| Parsing | 150+ | 95%+ |
| RCON | 120+ | 92%+ |
| Discord Bot | 180+ | 91%+ |
| Multi-server | 100+ | 90%+ |
| **Total** | **1000+** | **91%+** |

## Performance

| Operation | Latency |
|-----------|----------|
| Log parse + route | ~50-100ms |
| RCON command | 100-300ms |
| Discord embed send | 500-1000ms |
| UPS calculation | <1ms |
| Multi-server alert cycle | 100-200ms per server |

**Scaling:** Single instance handles 5-10 servers (typical), up to 20+ with optimization.

## Module Reference

| File | Purpose |
|------|----------|
| main.py | Application lifecycle |
| config.py | Configuration loading |
| discord_bot.py | Bot mode |
| server_manager.py | Multi-server orchestration |
| rcon_client.py | RCON protocol |
| event_parser.py | Pattern matching |
| pattern_loader.py | YAML → regex |
| health.py | HTTP health |

---
**Version:** v0.2.1+ | **Status:** Production-ready