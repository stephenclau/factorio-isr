---
layout: default
title: Architecture
---


# 🗼 Architecture Guide

Complete overview of Factorio ISR system design, evolution from single-server to multi-server support, and extensibility patterns.

## Table of Contents

- [System Components](#system-components)
- [Evolution: Single-Server → Multi-Server](#evolution-single-server--multi-server)
- [Configuration System: Hardcoded → YAML-Based](#configuration-system-hardcoded--yaml-based)
- [Discord Integration Evolution](#discord-integration-evolution)
- [Event Flow](#event-flow)
- [Security & Hardening](#security--hardening)
- [Performance Considerations](#performance-considerations)
- [Design Decisions](#design-decisions)
- [Extension Points](#extension-points)

---

## System Components

### Core Pipeline (Log Tailer → Parser → Discord)

- **Log Tailer** (`log_tailer.py`) – Monitors Factorio server console.log with file rotation support. Emits lines in real-time.

- **Event Parser** (`event_parser.py`) – Extracts structured events from log lines using YAML-based regex patterns. Validates input for security (ReDoS protection, safe regex compilation).

- **Pattern Loader** (`pattern_loader.py`) – Loads and validates YAML pattern files. Enforces strict schema, regex timeout limits, and safe defaults.

- **Security Monitor** (`security_monitor.py`) – Runtime checks for malicious patterns and rate limiting. Prevents abuse (spam mentions, injection attempts).

- **Mention Resolver** (`mention_resolver.py`) – Safely resolves @mention tokens using curated `mentions.yml` vocabulary. Prevents arbitrary role escalation.

- **Discord Client** (`discord_client.py`) – Webhook-based message sending (deprecated, kept for legacy compatibility).

- **Discord Bot** (`discord_bot.py`) – Modern Discord bot with slash commands, event handling, RCON integration, and admin capabilities.

- **Discord Interface** (`discord_interface.py`) – Unified abstraction layer supporting both webhook and bot modes (though bot is now primary).

### Server Management (Multi-Server Support)

- **Server Manager** (`server_manager.py`) – Coordinates multiple independent Factorio servers. Each server has its own log tailer, RCON client, and parser instance.

- **RCON Client** (`rcon_client.py`) – Asynchronous RCON queries for real-time stats. Polls every configurable interval. Memory-optimized with FIFO eviction for metrics history.

### Infrastructure

- **Configuration Loader** (`config.py`) – Reads config from environment variables, Docker secrets, and YAML files with validation.

- **Health Monitor** (`health.py`) – HTTP endpoint for container orchestration (Kubernetes, Docker Compose health checks).

- **Application** (`main.py`) – Entry point. Orchestrates log tailers, Discord bot, RCON clients, and health checks.

---

## Evolution: Single-Server → Multi-Server

### Phase 1-2: Single-Server Design

```text
┌──────────────────────────────────────────────────────┐
│                  Single-Server ISR                   │
│                                                       │
│  [Factorio Log] → [Log Tailer] → [Event Parser] ─┐  │
│                                                    │  │
│                     [Discord Bot] ←─────────────────┤  │
│                                                    │  │
│                   [Health Check]                  │  │
│                                                    │  │
└──────────────────────────────────────────────────────┘
```

**Hardcoded assumptions:**
- Single Factorio log path (`FACTORIO_LOG_PATH`)
- Single Discord event channel (`DISCORD_EVENT_CHANNEL_ID`)
- Single RCON server (`RCON_HOST`, `RCON_PORT`)

**Limitations:**
- Admin had to run separate ISR instances for each server
- No shared bot state or presence
- Config duplication across deployments

### Phase 3+: Multi-Server Architecture

```text
┌──────────────────────────────────────────────────────────────────┐
│                   Multi-Server ISR (Current)                     │
│                                                                  │
│  ┌──────────────────────┐     ┌──────────────────────┐          │
│  │  Server: Los Heros   │     │  Server: Space Age   │          │
│  │  ┌────────────────┐  │     │  ┌────────────────┐  │          │
│  │  │  Log Tailer    │  │     │  │  Log Tailer    │  │          │
│  │  └────────────────┘  │     │  └────────────────┘  │          │
│  │         ↓            │     │         ↓            │          │
│  │  ┌────────────────┐  │     │  ┌────────────────┐  │          │
│  │  │ Event Parser   │  │     │  │ Event Parser   │  │          │
│  │  └────────────────┘  │     │  └────────────────┘  │          │
│  │         ↓            │     │         ↓            │          │
│  │  ┌────────────────┐  │     │  ┌────────────────┐  │          │
│  │  │ RCON Client    │  │     │  │ RCON Client    │  │          │
│  │  └────────────────┘  │     │  └────────────────┘  │          │
│  └──────────────────────┘     └──────────────────────┘          │
│           ↓                              ↓                       │
│  ┌─────────────────────────────────────────────────┐            │
│  │         Server Manager (Coordinator)            │            │
│  │                                                 │            │
│  │  - Manages all server instances                │            │
│  │  - Coordinates events to Discord               │            │
│  │  - Updates shared bot presence                 │            │
│  └─────────────────────────────────────────────────┘            │
│           ↓                                                      │
│  ┌──────────────────────────────────────────────┐               │
│  │         Discord Bot (Single Instance)         │               │
│  │                                               │               │
│  │  - Slash commands (status, players, etc.)    │               │
│  │  - Per-server notifications                  │               │
│  │  - Admin commands                            │               │
│  │  - Presence: "3/3 servers online"            │               │
│  └──────────────────────────────────────────────┘               │
│           ↓                                                      │
│  ┌──────────────────────────────────────────────┐               │
│  │     Discord (Multiple Channels)               │               │
│  │  [#los-heros-events] [#space-age-events]    │               │
│  └──────────────────────────────────────────────┘               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Configuration-driven (`config/servers.yml`):**

```yaml
servers:
  los_hermanos:
    log_path: /factorio/los_hermanos/console.log
    rcon_host: factorio-1.internal
    rcon_port: 27015
    discord_channel_id: 123456789012345678
    stats_interval: 300

  space_age:
    log_path: /factorio/space_age/console.log
    rcon_host: factorio-2.internal
    rcon_port: 27015
    discord_channel_id: 987654321098765432
    stats_interval: 300
```

**Benefits:**
- Single bot instance serves multiple servers
- Unified presence and command interface
- Event routing per server to different channels
- Shared RCON polling and metrics
- No config duplication

---

## Configuration System: Hardcoded → YAML-Based

### Phase 1-2: Hardcoded & Environment-Only

**Limitations:**
- Event patterns embedded in code
- No pattern reloading without restart
- Hard to customize for specific Factorio mods
- Admin had to edit Python source or write long env vars

### Phase 2+: YAML Pattern System

**Event patterns** (`patterns/vanilla.yml`, `patterns/custom.yml`, etc.):

```yaml
events:
  player_join:
    pattern: '(\w+) (joined|connected)'
    type: player
    emoji: "✅"
    message: "{player} joined the server"
    enabled: true
    priority: 10
    channel: general

  rocket_launch:
    pattern: 'rocket.*launched'
    type: milestone
    emoji: "🚀"
    message: "Rocket launched! 🎉"
    enabled: true
    priority: 5
    channel: milestones
```

**Server configuration** (`config/servers.yml`):

```yaml
servers:
  production:
    log_path: /factorio/console.log
    rcon_host: localhost
    discord_channel_id: 123456789
```

**Mention vocabulary** (`config/mentions.yml`):

```yaml
mentions:
  roles:
    admin:
      - "admin"
      - "admins"
    moderators:
      - "mods"
      - "moderators"
```

**Security policy** (`config/secmon.yml`):

```yaml
security:
  enabled: true
  alert_channel: "security-alerts"
  patterns:
    code_injection:
      enabled: true
      auto_ban: true
      severity: critical
  rate_limits:
    mention_admin:
      max_events: 5
      time_window_seconds: 60
```

**Benefits:**
- **No code changes** to add patterns or servers
- **Hot-load capable** (future enhancement)
- **Admin-friendly** – YAML, not Python
- **Validated at load time** – schema and regex checks
- **Auditable** – config files in version control

---

## Discord Integration Evolution

### Phase 1: Webhook-Only (Deprecated)

**Characteristics:**
- Simple HTTP POST to Discord webhook URL
- One-way notifications only
- No command handling
- No presence or status updates

**Limitation:** No interaction with users.

### Phase 4+: Full Discord Bot (Current)

**Characteristics:**
- Native Discord.py bot client
- Slash commands: `/factorio status`, `/factorio players`, `/factorio admin save`
- Real-time presence: "Watching 3/3 servers online"
- Event notifications with embeds
- Permission system
- Admin commands with audit logging

**Slash Commands:**

```
/factorio status        → Show all server stats
/factorio players [server] → List online players
/factorio admin save [server] → Save game state
/factorio metrics [server] → Get UPS, evolution, player count
/factorio help          → Command reference
```

**Benefits over webhook:**
- **Interactivity** – Admins can query and control servers
- **Presence** – Real-time bot status showing server health
- **Permissions** – Role-based access control for commands
- **Logging** – All commands logged to Discord
- **Rich formatting** – Embeds, mentions, reactions

---

## Event Flow

### Complete Pipeline (Multi-Server)

```text
Multiple Servers
│
├─ Server 1: Los Hermanos
│  └─ [console.log] → [Log Tailer] → [Event Parser] → [Event Queue]
│                                          ↓
│                                   [Security Monitor]
│                                   [Mention Resolver]
│
├─ Server 2: Space Age
│  └─ [console.log] → [Log Tailer] → [Event Parser] → [Event Queue]
│                                          ↓
│                                   [Security Monitor]
│                                   [Mention Resolver]
│
└─ RCON (All servers)
   └─ [Periodic Poll] → [RCON Client] → [Metrics] → [Stats Queue]

All Events + Stats
│
└─ [Server Manager] → [Discord Bot]
                           ├─ [Event Dispatcher]
                           ├─ [Stats Poster]
                           ├─ [Slash Command Handler]
                           └─ [Presence Updater]
                                    ↓
                           [Discord Channels]
```

### Single Event Lifecycle

```text
Log Line: "[12:34:56] Alice joined the game"
         │
         ↓
    [Log Tailer] - Read, buffer, emit line
         │
         ↓
    [Event Parser] - Regex match against patterns
         │
         ├─ No match? → Discard
         ├─ Match! → Extract groups
         │
         ↓
    [Security Monitor] - Check rate limits, injection patterns
         │
         ├─ Threat detected? → Alert + discard
         │
         ↓
    [Mention Resolver] - Resolve @mentions safely
         │
         ├─ Invalid mention? → Replace with plain text
         │
         ↓
    [Format Event] - Build Discord embed
         │
         └─ [Post to Discord] → [#server-events]
```

---

## Security & Hardening

### Phase 1-2: Basic Input Validation

- User logs trusted; only validated by Factorio server
- Webhook URL injected via env; assumed secure

### Phase 6: Comprehensive Hardening

#### Regex Protection (ReDoS Prevention)

- **RE2 engine** (if available via `google-re2` package) for deterministic regex evaluation
- **Timeout limits** on all pattern compilation and execution (300ms default)
- **Pattern review** at load time for known ReDoS patterns

```python
# Pattern Loader validates
try:
    re.compile(pattern, timeout=0.3)  # Timeout in seconds
except TimeoutError:
    raise ValueError(f"Pattern {name} took too long (ReDoS risk)")
```

#### Input Sanitization

- Log content treated as **untrusted user input**
- Escape special characters before Discord formatting
- Validate extracted groups (player names, messages, etc.)
- Length limits on extracted fields

#### Mention Safety via `mentions.yml`

- Player can only @mention roles in the approved vocabulary
- Prevents privilege escalation (e.g., `@everyone`, `@here`)
- Centralized role whitelist

#### Rate Limiting (`secmon.yml`)

- Per-user throttles on high-priority actions
- Spam detection on repeated mentions or commands
- Automatic alerts and optional enforcement

#### Configuration Validation

- **YAML schema enforcement** – Required fields, type checking
- **Filename allowlisting** – Only load patterns from approved list
- **Secret file isolation** – `.secrets/` directory with 700 permissions

#### Runtime Authorizations

- Discord bot slash commands check user roles
- RCON write operations (save, admin commands) require explicit permission
- All admin actions logged to audit channel

### Threat Model

| Threat | Vector | Mitigation |
|--------|--------|-----------|
| ReDoS via malicious pattern | YAML pattern file | Timeout limits, pattern review |
| Log injection / escaping | Factorio console.log | Input sanitization, Discord escaping |
| Role escalation | @mentions in chat | `mentions.yml` vocabulary whitelist |
| Command abuse | Slash command spam | Rate limiting in `secmon.yml` |
| Unauthorized writes | RCON admin commands | Role-based access control |
| Secret exposure | Env vars, config | Docker secrets, `.secrets/` folder |

---

## Performance Considerations

### Memory Efficiency

**RCON Metrics History (Bounded):**
- Stores last 288 stats (24 hours @ 5-min intervals)
- FIFO eviction when limit reached
- No unbounded growth
- Estimated: ~10 KB per metric per server

**Log Tailer:**
- Streaming reads (no full-file buffering)
- Single file descriptor per server
- Garbage collected completed log chunks

**Event Parser:**
- Stateless – no event queue buildup
- Patterns compiled once at startup
- Regex execution bounded by timeout

### Polling Strategy (RCON)

```python
# config/servers.yml
stats_interval: 300  # Poll every 5 minutes (default)
```

**Rationale:**
- 5-minute interval balances responsiveness and CPU/network load
- Multiple servers polled in parallel (async)
- Metrics gracefully degrade if RCON is unavailable

### Scalability

**Tested configurations:**
- Single bot + 3 Factorio servers: <50 MB memory
- RCON polling @ 5-min intervals: <1 CPU per server
- Pattern matching: <1 ms per event (typical)
- Discord posting: Non-blocking (async)

**Expected limits:**
- ~10 servers on modest hardware (1 CPU, 512 MB RAM)
- More servers possible with tuning (polling intervals, pattern simplification)

---

## Design Decisions

### Stateless Architecture

**Why:** Minimal operational overhead, easy horizontal scaling (future).

**Trade-off:** Cannot persist session data (e.g., ongoing votes, player statistics). Mitigated by optional external storage layer (future roadmap).

### Single Discord Bot Instance

**Why:** Simplifies presence management, unified permissions, one set of secrets.

**Trade-off:** Requires robust error handling and reconnection logic. Mitigated by persistent connection monitoring and health checks.

### YAML-Based Configuration

**Why:** Admin-friendly, no code changes needed, auditable, composable.

**Trade-off:** Slower startup (file I/O + validation). Mitigated by caching (future).

### Async I/O (Discord, RCON)

**Why:** High concurrency (multiple servers, events, commands) without thread overhead.

**Trade-off:** Steeper learning curve for developers. Mitigated by comprehensive test suite.

### No Database

**Why:** Simplifies deployment, reduces operational complexity.

**Trade-off:** No persistent statistics or replay. Mitigated by optional JSON export (future roadmap).

---

## Extension Points

### Adding a New Event Pattern

1. **Create pattern file:** `patterns/custom.yml`
2. **Define pattern:**
   ```yaml
   events:
     my_event:
       pattern: '...'  # Regex
       type: custom
       emoji: "🎯"
       message: "..."
       enabled: true
       priority: 5
       channel: events
   ```
3. **Load at startup:** Set `PATTERN_FILES=["vanilla.yml", "custom.yml"]`
4. **Test:** Use debug logging and `pytest`

### Adding a New Discord Slash Command

1. **Extend `discord_bot.py`:**
   ```python
   @factorio_group.command(name="mycommand")
   async def my_command(interaction: discord.Interaction) -> None:
       """My custom command."""
       await interaction.response.defer()
       # Your logic here
       await interaction.followup.send("Result")
   ```
2. **Add tests** in `tests/test_discord_bot.py`
3. **Document** in slash commands reference

### Adding a New Server

1. **Edit `config/servers.yml`:**
   ```yaml
   servers:
     # ... existing ...
     new_server:
       log_path: /factorio/new_server/console.log
       rcon_host: new-server.internal
       discord_channel_id: 999999999999
   ```
2. **Restart ISR** (future: hot-load via admin command)
3. **Verify** with `/factorio status`

### Extending Security Monitoring

1. **Add pattern to `config/secmon.yml`:**
   ```yaml
   security:
     patterns:
       my_threat:
         enabled: true
         severity: high
   ```
2. **Implement check** in `security_monitor.py`
3. **Test** with malicious input samples

### Adding Metrics Export

1. **Implement exporter** (e.g., Prometheus format)
2. **Integrate** into `server_manager.py`
3. **Expose** via health check endpoint or separate port

---

## Roadmap

| Phase | Status | Features | Versions |
|-------|--------|----------|----------|
| **1** | ✅ Complete | Log tailing, event parsing, webhook/bot | v0.1.0 
| **2** | ✅ Complete | YAML patterns, multi-channel routing | v0.2.1
| **3** | ✅ Complete | RCON stats, player tracking | v0.3.0 to v0.4.0
| **4** | ✅ Complete | Discord bot, slash commands | v1.0.0f
| **5** | ✅ Complete | Admin commands, RCON writes, multi-server | v1.0.0f to v2.0.0
| **6** | ✅ In use | Metrics, UPS alerts, security hardening | v2.1.1
| **Future** | 📋 Planned | Hot-load config, analytics, database persistence, Prometheus metrics, control plane UI |

See [Roadmap](roadmap.md) for detailed future plans.

---

## Related Documentation

- **[Configuration Guide](configuration.md)** – Environment variables, YAML format
- **[Development Guide](development.md)** – Running tests, adding features
- **[Deployment Guide](DEPLOYMENT.md)** – Production setup
- **[RCON Setup](RCON_SETUP.md)** – Server stats configuration
- **[Pattern Reference](PATTERNS.md)** – Event pattern syntax
- **[Security Guide](secmon.md)** – Rate limiting and threat model
- **[Mentions Guide](mentions.md)** – Safe @mention vocabulary
