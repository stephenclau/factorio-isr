---
layout: default
title: Security Guide
---

# 🛡️ Security Guide

Comprehensive guide for securing your Factorio ISR installation, covering the Security Monitor, threat models, and hardening practices.

## Table of Contents
- [Security Monitor Configuration](#security-monitor-configuration)
- [Threat Model](#threat-model)
- [Hardening Measures](#hardening-measures)
- [Rate Limiting](#rate-limiting)
- [Best Practices](#best-practices)

---

## Security Monitor Configuration

The Security Monitor (`security_monitor.py`) inspects events for risky patterns and applies policies defined in `config/secmon.yml`.

### File Format (`config/secmon.yml`)

```yaml
security:
  enabled: true
  alert_channel: "security-alerts"

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

---

## Threat Model

Factorio ISR bridges a game server (which accepts user input) and Discord (a public platform). This creates several attack vectors we mitigate:

| Threat | Vector | Mitigation |
|--------|--------|-----------|
| **ReDoS** | Malicious YAML patterns | `google-re2` usage (if available), strict regex timeouts (300ms) |
| **Log Injection** | Fake console messages | Input sanitization, strict pattern anchoring |
| **Role Escalation** | `@everyone` spam | `mentions.yml` whitelist, runtime replacement |
| **Command Injection** | RCON commands | Hardcoded command list, role-based access control |
| **Config Tampering** | Modified YAML | Docker read-only mounts, secrets isolation |

---

## Hardening Measures

### 1. ReDoS Mitigation (Regex Denial of Service)
User-supplied regex patterns in YAML files can be crafted to hang the CPU.
- **Timeouts**: All regex compilations and matches have a strict timeout.
- **RE2**: The system attempts to use `google-re2` for deterministic performance.
- **Validation**: Patterns are checked at load time for obvious catastrophic backtracking risks.

### 2. Strict YAML Validation
- **Schema Enforcement**: All YAML files (`servers.yml`, patterns) are validated against a strict schema.
- **Path Locking**: Patterns are only loaded from the hardcoded `/app/patterns` directory. Directory traversal symbols (`../`) are blocked.

### 3. Input Sanitization
- **Console Input**: In-game chat is treated as untrusted.
- **Escaping**: All Discord output is escaped to prevent formatting injection (e.g., hiding text, spoofing links).
- **Mentions**: Raw mentions (e.g., `<@12345>`) in chat are escaped unless they match a mapped role in `mentions.yml`.

---

## Rate Limiting

Rate limits are applied per-user or per-action to prevent flooding.

### Configuration

Defined in `rate_limits` section of `secmon.yml`.

- **`mention_admin`**: Limits how often a user can trigger an admin ping.
- **`chat_message`**: General flood protection for bridging chat to Discord.

Violations trigger a warning in the `alert_channel` and drop the event.

---

## Best Practices

1. **Read-Only Mounts**: Mount your `config` and `patterns` directories as read-only in Docker (`:ro`).
2. **Dedicated Alert Channel**: Use a private Discord channel for `alert_channel` to monitor security incidents without exposing them to public users.
3. **Least Privilege**: The Discord Bot role should only have permissions it needs (Send Messages, Embed Links). Do not give it "Administrator".
4. **Audit RCON**: Ensure your Factorio RCON password is strong and rotated if staff changes.

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)
