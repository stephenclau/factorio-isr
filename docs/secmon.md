---
layout: default
title: Security Guide
---

# 🛡️ Security Guide

Comprehensive guide for securing your Factorio ISR installation, covering implemented security features, threat models, and hardening practices.

## ⚠️ Implementation Status

**CURRENT STATE:** Security features are **partially implemented**. This document describes:

1. ✅ **Implemented features** (ReDoS protection, input sanitization, rate limiting)
2. 🚧 **Planned features** (Security Monitor module, `secmon.yml` configuration)

**What exists today:**
- ReDoS protection in `event_parser.py` (regex timeouts, validation)
- Input sanitization in `event_handler.py` (Discord message escaping)
- Rate limiting in `utils/rate_limiting.py` (QUERY_COOLDOWN, ADMIN_COOLDOWN, etc.)
- Docker security best practices (read-only mounts, secrets isolation)

**What doesn't exist yet:**
- `security_monitor.py` module
- `config/secmon.yml` configuration file
- Auto-ban policies
- Dedicated security alerts channel

---

## Table of Contents
- [Implementation Status](#implementation-status)
- [Current Security Features](#current-security-features)
- [Threat Model](#threat-model)
- [Hardening Measures](#hardening-measures)
- [Planned Security Monitor](#planned-security-monitor)
- [Best Practices](#best-practices)

---

## Current Security Features

### 1. ReDoS Mitigation (Regex Denial of Service)

**Implemented in:** `src/event_parser.py`

User-supplied regex patterns in YAML files can be crafted to hang the CPU (catastrophic backtracking).

**Mitigations:**
- **Timeouts**: All regex compilations and matches have a strict 300ms timeout
- **Validation**: Patterns are checked at load time for obvious catastrophic backtracking risks
- **Fail-safe**: If timeout is exceeded, pattern is disabled and logged

**Example protection:**
```python
# Malicious pattern that would cause ReDoS
pattern: '(a+)+b'

# Result: Detected at load time, pattern disabled
logger.error("redos_risk_detected", pattern=pattern)
```

---

### 2. Input Sanitization

**Implemented in:** `src/bot/event_handler.py`

In-game chat is treated as untrusted input.

**Mitigations:**
- **Discord escaping**: All output is escaped to prevent formatting injection
- **Mention whitelisting**: Raw mentions (e.g., `<@12345>`) are escaped unless in `mentions.yml`
- **Link validation**: URLs are not auto-embedded (Discord handles this)

**Example:**
```python
# Input from Factorio chat
message = "Check this out: <@everyone> FREE ITEMS"

# Output to Discord (escaped)
message = "Check this out: \<@everyone\> FREE ITEMS"
```

---

### 3. Rate Limiting

**Implemented in:** `src/utils/rate_limiting.py`

**Limits:**
- `QUERY_COOLDOWN = 10` seconds (e.g., `/stats`, `/players`)
- `ADMIN_COOLDOWN = 5` seconds (e.g., `/kick`, `/ban`)
- `DANGER_COOLDOWN = 1` second (emergency commands)

**Protection:**
- Prevents command spam
- Throttles expensive RCON queries
- Avoids Discord rate limits

---

## Threat Model

Factorio ISR bridges a game server (which accepts user input) and Discord (a public platform). This creates several attack vectors we mitigate:

| Threat | Vector | Mitigation | Status |
|--------|--------|-----------|--------|
| **ReDoS** | Malicious YAML patterns | Regex timeouts (300ms), validation | ✅ Implemented |
| **Log Injection** | Fake console messages | Input sanitization, strict pattern anchoring | ✅ Implemented |
| **Role Escalation** | `@everyone` spam | `mentions.yml` whitelist, runtime escaping | ✅ Implemented |
| **Command Injection** | RCON commands | Hardcoded command list, role-based access | ✅ Implemented |
| **Config Tampering** | Modified YAML | Docker read-only mounts, secrets isolation | ✅ Best practice |
| **Auto-ban Policies** | Security violations | Planned `security_monitor.py` | 🚧 Planned |
| **Audit Logging** | Security events | Planned dedicated channel | 🚧 Planned |

---

## Hardening Measures

### 1. ReDoS Mitigation Details

**Problem:** User-supplied regex can hang CPU

**Solution:**
- Strict 300ms timeout per regex match
- Pattern validation at load time
- Disabled patterns are logged but don't crash the app

**Code:** See `src/event_parser.py` → `_compile_pattern()`

---

### 2. Strict YAML Validation

**Problem:** Malformed YAML can cause crashes

**Solution:**
- Schema enforcement (all YAML files validated)
- Path locking (patterns only from `/app/patterns`)
- Directory traversal blocked (`../` rejected)

**Code:** See `src/config.py` → `load_servers_config()`

---

### 3. Input Sanitization Details

**Problem:** Factorio chat is untrusted

**Solution:**
- All Discord output is escaped
- Mentions are whitelisted via `mentions.yml`
- Raw HTML/markdown is neutralized

**Code:** See `src/bot/event_handler.py` → `_resolve_mentions()`

---

## Planned Security Monitor

**Status:** 🚧 **NOT IMPLEMENTED YET**

The Security Monitor (`security_monitor.py`) will inspect events for risky patterns and apply policies defined in `config/secmon.yml`.

### Planned File Format (`config/secmon.yml`)

```yaml
security:
  enabled: true
  alert_channel_id: 999888777666555444  # Discord channel for security alerts

  patterns:
    code_injection:
      enabled: true
      auto_ban: true
      severity: critical
    command_injection:
      enabled: true
      auto_ban: true
      severity: critical

  rate_limits:
    mention_admin:
      max_events: 5
      time_window_seconds: 60
    mention_everyone:
      max_events: 1
      time_window_seconds: 300
```

### Planned Features

- 🚧 Auto-ban on security violations
- 🚧 Dedicated security alerts channel
- 🚧 Pattern-based threat detection
- 🚧 Configurable severity levels
- 🚧 Rate limit enforcement per user

---

## Best Practices

### 1. Docker Security

**Read-Only Mounts:**
```yaml
volumes:
  - ./config:/app/config:ro
  - ./patterns:/app/patterns:ro
  - /factorio/logs:/factorio:ro
```

**Secrets Isolation:**
```yaml
secrets:
  DISCORD_BOT_TOKEN:
    file: .secrets/DISCORD_BOT_TOKEN.txt
  RCON_PASSWORD:
    file: .secrets/RCON_PASSWORD
```

### 2. Discord Bot Permissions

**Least Privilege:**
- ✅ Send Messages
- ✅ Embed Links
- ✅ Use Slash Commands
- ❌ **NOT** Administrator
- ❌ **NOT** Manage Server

### 3. RCON Security

**Strong Passwords:**
- Minimum 16 characters
- Use password manager to generate
- Rotate if staff changes

**Network Isolation:**
- Bind RCON to `127.0.0.1` if bot is on same host
- Use firewall rules to restrict RCON port access

### 4. Monitoring

**Enable structured logging:**
```bash
LOG_LEVEL=info
LOG_FORMAT=json
```

**Watch for security events:**
```bash
docker logs factorio-isr | grep -E "redos_risk|rate_limit_exceeded|unauthorized"
```

---

## Next Steps

- See [Configuration](configuration.md) for all security-related environment variables
- See [Deployment](DEPLOYMENT.md) for production security checklist
- See [Troubleshooting](TROUBLESHOOTING.md) for diagnosing security issues

---

## Contributing

Interested in implementing the Security Monitor? See [CONTRIBUTING.md](../CONTRIBUTING.md) or open an issue on GitHub.

**Priority:**
- Implement `security_monitor.py` module
- Design `secmon.yml` schema
- Add auto-ban policies
- Create security alerts channel integration

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](../LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)