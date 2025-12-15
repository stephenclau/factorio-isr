---
layout: default
title: Security Monitor
---

# 🛡️ Security Monitor

Automated detection and response to malicious patterns in Factorio events.

## ✅ Implementation Status

**CURRENT STATE:** Security Monitor is **fully implemented** in `src/security_monitor.py`.

**What exists today:**
- ✅ `SecurityMonitor` class with pattern detection
- ✅ Auto-ban on critical violations
- ✅ Rate limiting per player
- ✅ Infraction logging (JSONL format)
- ✅ Banned players persistence
- ✅ Example `config/secmon.yml` reference

**Current limitation:**
- ⚠️ **`config/secmon.yml` is NOT loaded by the code yet**
- Patterns and rate limits are **hardcoded** in `src/security_monitor.py`
- To customize, you must modify the source code directly

---

## Table of Contents
- [How It Works](#how-it-works)
- [Malicious Patterns](#malicious-patterns)
- [Rate Limiting](#rate-limiting)
- [Infraction Logging](#infraction-logging)
- [Banned Players](#banned-players)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Roadmap](#roadmap)

---

## How It Works

The `SecurityMonitor` class inspects all Factorio events for dangerous patterns:

1. **Pattern matching**: Regex-based detection of code injection, path traversal, command injection
2. **Severity assessment**: `critical`, `high`, or `medium`
3. **Auto-ban**: If `auto_ban: true`, player is immediately banned
4. **Infraction logging**: All violations logged to `config/infractions.jsonl`
5. **Persistence**: Banned players stored in `config/server-banlist.json`

**Code location:** `src/security_monitor.py`

---

## Malicious Patterns

### Hardcoded Pattern Categories

#### **1. Code Injection** (Severity: `critical`, Auto-ban: ✅)

Detects Python code execution attempts:

```python
patterns = [
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__\s*\(",
    r"compile\s*\(",
    r"ast\.literal_eval",
    r"subprocess.*shell\s*=\s*True",
    r"os\.system\s*\(",
    r"importlib\.import_module",
]
```

**Example violation:**
```
[CHAT] alice: Check this out: eval("malicious code")
```

**Result:** Alice is **immediately banned**.

---

#### **2. Path Traversal** (Severity: `high`, Auto-ban: ❌)

Detects directory traversal attempts:

```python
patterns = [
    r"\.\./",
    r"\.\.\\",
    r"/etc/passwd",
    r"/proc/self",
]
```

**Example violation:**
```
[CHAT] bob: Load file: ../../etc/passwd
```

**Result:** Logged as infraction, **NOT auto-banned** (high severity, not critical).

---

#### **3. Command Injection** (Severity: `critical`, Auto-ban: ✅)

Detects shell command injection:

```python
patterns = [
    r"&&\s*[a-z]+",
    r";\s*rm\s+-rf",
    r"\|\s*sh",
    r"`.*`",
    r"\$\(.*\)",
]
```

**Example violation:**
```
[CHAT] eve: Run this: && rm -rf /
```

**Result:** Eve is **immediately banned**.

---

## Rate Limiting

### Hardcoded Rate Limits

Rate limits prevent spam and abuse:

| Action Type | Max Events | Time Window | Description |
|-------------|-----------|-------------|-------------|
| `mention_admin` | 5 | 60s | Player mentions admin role |
| `mention_everyone` | 1 | 300s (5min) | Player mentions `@everyone` |
| `chat_message` | 20 | 60s | General chat messages |

**Implementation:**
```python
self.rate_limits = {
    "mention_admin": RateLimit(
        max_events=5,
        time_window_seconds=60,
        action_type="mention_admin",
    ),
    "mention_everyone": RateLimit(
        max_events=1,
        time_window_seconds=300,
        action_type="mention_everyone",
    ),
    "chat_message": RateLimit(
        max_events=20,
        time_window_seconds=60,
        action_type="chat_message",
    ),
}
```

**Usage:**
```python
allowed, reason = security_monitor.check_rate_limit("mention_admin", "alice")
if not allowed:
    logger.warning("rate_limit_exceeded", player="alice", reason=reason)
```

---

## Infraction Logging

### JSONL Append-Only Log

All violations are logged to `config/infractions.jsonl`:

**File location:** `./config/infractions.jsonl` (created automatically)

**Format:** One JSON object per line (JSONL)

**Example infraction:**
```json
{
  "player_name": "alice",
  "timestamp": "2025-12-15T00:00:00.123456",
  "pattern_type": "code_injection",
  "matched_pattern": "eval\\s*\\(",
  "raw_text": "[CHAT] alice: eval(\"malicious\")",
  "severity": "critical",
  "auto_banned": true,
  "metadata": {
    "match": "eval(",
    "description": "Attempted code injection"
  }
}
```

### Retrieving Infractions

```python
# Get all infractions (last 100)
infractions = security_monitor.get_infractions(limit=100)

# Get infractions for specific player
alice_infractions = security_monitor.get_infractions(player_name="alice")
```

---

## Banned Players

### Ban List File

**Default location:** `./config/server-banlist.json`

**Override via environment:**
```bash
export FACTORIO_ISR_BANLIST_DIR=/path/to/banlist/dir
# Results in: /path/to/banlist/dir/server-banlist.json
```

**Format:**
```json
{
  "banned_players": ["alice", "eve"],
  "last_updated": "2025-12-15T00:00:00.123456"
}
```

### Ban Management

```python
# Ban a player
security_monitor.ban_player("alice", reason="Code injection attempt")

# Unban a player
unbanned = security_monitor.unban_player("alice")  # Returns True if was banned

# Check if banned
is_banned = security_monitor.is_banned("alice")  # Returns bool
```

**Persistence:** Ban list is automatically saved to disk after every ban/unban operation.

---

## Configuration

### Current State (December 2025)

**⚠️ `config/secmon.yml` exists but is NOT loaded by the code.**

The file serves as a **reference example** only. To customize patterns or rate limits, you must:

1. Edit `src/security_monitor.py` directly
2. Modify `MALICIOUS_PATTERNS` dict (line ~30)
3. Modify `self.rate_limits` dict (line ~150)

### Example `config/secmon.yml` (Reference Only)

```yaml
security:
  enabled: true
  alert_channel: "security-alerts"

  patterns:
    code_injection:
      enabled: true
      auto_ban: true
      severity: critical

    path_traversal:
      enabled: true
      auto_ban: false
      severity: high

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

    chat_message:
      max_events: 20
      time_window_seconds: 60
```

**Future work:** Load this file dynamically to allow runtime configuration without code changes.

---

## Usage Examples

### Example 1: Initialize SecurityMonitor

```python
from pathlib import Path
from security_monitor import SecurityMonitor

monitor = SecurityMonitor(
    infractions_file=Path("config/infractions.jsonl"),
    banned_players_file=Path("config/server-banlist.json"),
)
```

### Example 2: Check for Malicious Patterns

```python
# Check player chat message
text = "[CHAT] alice: eval('malicious code')"
infraction = monitor.check_malicious_pattern(text, player_name="alice")

if infraction:
    print(f"Violation detected: {infraction.pattern_type}")
    print(f"Auto-banned: {infraction.auto_banned}")
```

### Example 3: Check Rate Limit

```python
allowed, reason = monitor.check_rate_limit("mention_admin", "bob")

if not allowed:
    print(f"Rate limit exceeded: {reason}")
else:
    # Allow action
    send_mention_to_discord(...)
```

### Example 4: View Infractions

```python
# Get last 10 infractions
recent = monitor.get_infractions(limit=10)

for infraction in recent:
    print(f"{infraction['timestamp']}: {infraction['player_name']} - {infraction['pattern_type']}")
```

---

## Roadmap

### Planned Enhancements

- [ ] **Load `config/secmon.yml` dynamically** (highest priority)
- [ ] **Discord alerts channel** for security violations
- [ ] **Configurable severity levels** per pattern
- [ ] **Whitelist support** (trusted players exempt from auto-ban)
- [ ] **Temporary bans** (auto-expire after N hours)
- [ ] **IP-based bans** (requires RCON integration)

### Contributing

Interested in implementing dynamic config loading? See [CONTRIBUTING.md](../CONTRIBUTING.md).

**Suggested approach:**
1. Add YAML loader in `security_monitor.py`
2. Override `MALICIOUS_PATTERNS` if `config/secmon.yml` exists
3. Override `self.rate_limits` with user-defined values
4. Add schema validation for safety

---

## Best Practices

### Docker Security

```yaml
volumes:
  - ./config:/app/config  # Read-write for infractions.jsonl and server-banlist.json
  - ./patterns:/app/patterns:ro
  - /factorio/logs:/factorio:ro

secrets:
  DISCORD_BOT_TOKEN:
    file: .secrets/DISCORD_BOT_TOKEN.txt
  RCON_PASSWORD:
    file: .secrets/RCON_PASSWORD
```

### Monitoring

```bash
# Watch for security events
docker logs factorio-isr | grep malicious_pattern_detected

# Tail infractions log
tail -f config/infractions.jsonl

# View banned players
cat config/server-banlist.json | jq '.banned_players'
```

---

## Next Steps

- ✅ [Threat Model](ARCHITECTURE.md#security) – Security architecture overview
- ✅ [Configuration](configuration.md) – Environment variables
- ✅ [Deployment](DEPLOYMENT.md) – Production hardening checklist

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](../LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)