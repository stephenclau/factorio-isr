---
layout: default
title: Configuration
---

# 📋 Configuration Guide

Complete configuration reference for Factorio ISR with multi-server support, Discord bot integration, and advanced features.

## Table of Contents

- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Docker Secrets](#docker-secrets-recommended-for-production)
- [File Layout](#file-layout)
- [Multi-Server Configuration (servers.yml)](#multi-server-configuration-serversyml)
- [Mentions Configuration (mentions.yml)](#mentions-configuration-mentionsyml)
- [Security Monitor (secmon.yml)](#security-monitor-secmonyml)
- [Discord Bot Setup](#discord-bot-setup)
- [Pattern Configuration](#pattern-configuration)
- [Log Levels](#log-levels)
- [Health Monitoring](#health-monitoring)

---

## Quick Start

**Minimum viable configuration for single server:**

1. Create `.secrets/DISCORD_BOT_TOKEN.txt` with your bot token
2. Create `config/servers.yml`:
   ```yaml
   servers:
     default:
       log_path: /factorio/console.log
       rcon_host: localhost
       rcon_port: 27015
       rcon_password: "${RCON_PASSWORD}"  # or hardcode for dev
       event_channel_id: 123456789012345678
   ```
3. Run: `docker-compose up -d`

**That's it.** Everything else is optional enhancement.

---

## Environment Variables

### Core Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ Yes | - | Discord bot token (can use secret file: `.secrets/DISCORD_BOT_TOKEN.txt`) |
| `LOG_LEVEL` | No | `info` | Logging level: `debug`, `info`, `warning`, `error` |
| `LOG_FORMAT` | No | `console` | Log output format: `json` (production) or `console` (development) |
| `HEALTH_CHECK_HOST` | No | `0.0.0.0` | Health check server bind address |
| `HEALTH_CHECK_PORT` | No | `8080` | Health check server port |

### Deprecated Variables

| Variable | Status | Replacement |
|----------|--------|-------------|
| `DISCORD_EVENT_CHANNEL_ID` | ⚠️ Deprecated | Use `event_channel_id` in `servers.yml` per server |
| `DISCORD_WEBHOOK_URL` | ❌ Removed | Bot-only mode (v2.0+) |
| `CONFIG_DIR` | ❌ Removed | Hardcoded to `config/` (relative to working directory) |
| `PATTERNS_DIR` | ❌ Removed | Hardcoded to `patterns/` (relative to working directory) |
| `RCON_ENABLED`, `RCON_HOST`, `RCON_PORT`, `RCON_PASSWORD` | ⚠️ Legacy | Configure per-server in `servers.yml` |

---

## File Layout

The application uses a strict directory structure (hardcoded for reliability in Docker).

| Path | Description | Required |
|------|-------------|----------|
| `config/` | **Configuration Directory**. Contains `servers.yml` (required), `mentions.yml` (optional), `secmon.yml` (optional). | ✅ Yes |
| `patterns/` | **Patterns Directory**. YAML pattern files (e.g., `vanilla.yml`). | ✅ Yes |
| `logs/` | **Application Logs**. Written by the application. | No |
| `.secrets/` | **Local Development Secrets**. Not mounted in production (use Docker secrets instead). | Dev only |

**⚠️ Important:** Mount these directories as volumes in Docker:
```yaml
volumes:
  - ./config:/app/config:ro        # Read-only
  - ./patterns:/app/patterns:ro    # Read-only
  - /factorio/logs:/factorio:ro    # Factorio log directory
  - ./logs:/app/logs               # Application logs (read-write)
```

---

## Multi-Server Configuration (servers.yml)

The `servers.yml` file in `config/` is the **single source of truth** for all server instances.

### Minimal Single Server

```yaml
servers:
  default:
    log_path: /factorio/console.log
    rcon_host: localhost
    rcon_port: 27015
    rcon_password: "secure-password"
    event_channel_id: 123456789012345678
```

### Multi-Server with RCON

```yaml
servers:
  production:
    name: Production Server
    log_path: /factorio/production/console.log
    rcon_host: factorio-prod.internal
    rcon_port: 27015
    rcon_password: "${RCON_PASSWORD_PROD}"  # Env var expansion supported
    event_channel_id: 111111111111111111
    stats_interval: 300  # Post stats every 5 minutes

  testing:
    name: Testing Server
    log_path: /factorio/testing/console.log
    rcon_host: factorio-test.internal
    rcon_port: 27015
    rcon_password: "${RCON_PASSWORD_TEST}"
    event_channel_id: 222222222222222222
    stats_interval: 600  # Every 10 minutes

  space_age:
    name: Space Age Modpack
    log_path: /factorio/space-age/console.log
    rcon_host: 192.168.1.50
    rcon_port: 27015
    rcon_password: "${RCON_PASSWORD_SA}"
    event_channel_id: 333333333333333333
    enable_stats_collector: false  # Disable periodic stats
```

### Complete Field Reference

```yaml
servers:
  SERVER_TAG:                 # Unique identifier (lowercase, alphanumeric, hyphens/underscores)
    name: STRING              # Display name (optional, defaults to tag)
    log_path: STRING          # Path to Factorio console.log (required)
    
    # RCON configuration (required for slash commands and stats)
    rcon_host: STRING         # Factorio server hostname/IP
    rcon_port: INTEGER        # RCON port (default: 27015)
    rcon_password: STRING     # RCON password (supports ${ENV_VAR} expansion)
    
    # Discord output settings (required)
    event_channel_id: INTEGER # Channel ID for events from this server
    
    # Stats configuration (optional)
    stats_interval: INTEGER   # Stats post interval in seconds (default: 300)
    enable_stats_collector: BOOLEAN  # Enable/disable stats (default: true)
    enable_ups_stat: BOOLEAN  # Include UPS in stats (default: true)
    enable_evolution_stat: BOOLEAN   # Include evolution in stats (default: true)
    
    # Alert configuration (optional)
    enable_alerts: BOOLEAN    # Enable UPS alerts (default: true)
    ups_warning_threshold: FLOAT     # UPS threshold for alert (default: 55.0)
    ups_recovery_threshold: FLOAT    # UPS threshold for recovery (default: 58.0)
    alert_check_interval: INTEGER    # Seconds between checks (default: 60)
    alert_samples_required: INTEGER  # Consecutive bad samples before alert (default: 3)
    alert_cooldown: INTEGER   # Seconds between repeat alerts (default: 300)
    
    # RCON status monitoring (optional)
    rcon_status_alert_mode: STRING   # 'transition' or 'interval' (default: transition)
    rcon_status_alert_interval: INTEGER  # Seconds for interval mode (default: 300)
```

### Server Naming Rules

- **Lowercase + alphanumeric:** `production` ✅, `Production` ❌
- **Hyphens and underscores allowed:** `space-age` ✅, `los_hermanos` ✅
- **Must be valid identifier:** `server!` ❌, `my server` ❌
- **Unique tags:** No duplicates

**Examples:**
- ✅ `production`, `testing`, `space-age`, `krastorio2`, `los_hermanos`
- ❌ `Production`, `Test Server`, `server#1`, `my-very-long-impossible-server-name`

---

## Mentions Configuration (mentions.yml)

Optional file for `@user` and `@role` mentions in Discord when players use `@name` in Factorio chat.

### Location

`config/mentions.yml`

### Example Configuration

```yaml
mentions:
  # Discord user mention
  alice:
    type: user
    discord_id: 123456789012345678
    aliases:
      - alice
      - Alice
      - alicesmith

  # Discord role mention
  admins:
    type: role
    discord_id: 987654321098765432
    aliases:
      - admin
      - admins
      - moderator

  # Another user
  bob:
    type: user
    discord_id: 234567890123456789
    aliases:
      - bob
      - Bob
      - bobby
```

### How It Works

When a player types in Factorio chat:
```
[CHAT] alice: Hey @bob, check the @admins channel!
```

Discord receives:
```
[CHAT] alice: Hey <@234567890123456789>, check the <@&987654321098765432> channel!
```

**Result:** Discord pings the actual users/roles.

### Required Bot Permissions

- **Mention Everyone** permission (for role mentions)
- **Message Content Intent** (to read chat messages)

### Getting Discord IDs

1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click user/role → Copy ID
3. Paste the numeric ID into `discord_id` field

---

## Security Monitor (secmon.yml)

**⚠️ Experimental Feature** - Optional file for security event detection and auto-moderation.

### Location

`config/secmon.yml`

### Example Configuration

```yaml
security_monitor:
  enabled: true
  
  # Auto-kick players who trigger these patterns
  patterns:
    - pattern: 'console commands detected'
      severity: critical
      action: kick
      reason: "Console abuse detected"
    
    - pattern: 'suspicious behavior: (.+)'
      severity: high
      action: warn
      reason: "Suspicious activity"
  
  # Alert channel for security events
  alert_channel_id: 999999999999999999
  
  # Auto-ban on X kicks within Y minutes
  auto_ban:
    enabled: true
    kick_threshold: 3
    time_window_minutes: 10
```

**Status:** Experimental. Requires RCON for kick/ban actions.

**⚠️ Use with caution:** Auto-moderation can have false positives. Test thoroughly in a non-production environment first.

---

## Docker Secrets (Recommended for Production)

For production deployments, use Docker secrets or local `.secrets/` folder for sensitive data.

### Local Development (`.secrets/` folder)

```bash
# Create secrets directory
mkdir -p .secrets

# Add Discord bot token
echo "your-discord-bot-token" > .secrets/DISCORD_BOT_TOKEN.txt

# Add RCON passwords per server
echo "prod-password" > .secrets/RCON_PASSWORD_PROD
echo "test-password" > .secrets/RCON_PASSWORD_TEST

# Secure files
chmod 700 .secrets
chmod 600 .secrets/*

# Add to .gitignore
echo ".secrets/" >> .gitignore
```

### Docker Secrets (Production)

```yaml
# docker-compose.yml
services:
  factorio-isr:
    secrets:
      - DISCORD_BOT_TOKEN
      - RCON_PASSWORD_PROD
      - RCON_PASSWORD_TEST

secrets:
  DISCORD_BOT_TOKEN:
    file: .secrets/DISCORD_BOT_TOKEN.txt
  RCON_PASSWORD_PROD:
    file: .secrets/RCON_PASSWORD_PROD
  RCON_PASSWORD_TEST:
    file: .secrets/RCON_PASSWORD_TEST
```

### Secret Resolution Order

The application checks secrets in this order:

1. Docker secret at `/run/secrets/SECRET_NAME`
2. Environment variable `$SECRET_NAME`
3. Value defined in YAML (for non-sensitive config)

**Example:** For `rcon_password: "${RCON_PASSWORD}"` in `servers.yml`:
1. Checks `/run/secrets/RCON_PASSWORD`
2. Checks environment variable `$RCON_PASSWORD`
3. If both fail, uses empty string (validation will fail)

---

## Discord Bot Setup

### Creating a Discord Bot

1. **Go to Discord Developer Portal**
   - Visit [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application"
   - Name it (e.g., "Factorio ISR")
   - Click "Create"

2. **Add a Bot**
   - In the left sidebar, click "Bot"
   - Click "Add Bot"
   - Copy the token under "TOKEN"
   - Save this token in `.secrets/DISCORD_BOT_TOKEN.txt`

3. **Configure Bot Permissions**
   - Under "Bot" → "Privileged Gateway Intents", enable:
     - ✅ **Message Content Intent** (required to read chat for mentions)
     - ✅ **Server Members Intent** (optional, for advanced features)

4. **Generate Invite URL**
   - Go to "OAuth2" → "URL Generator"
   - Under "SCOPES", select:
     - ✅ `bot`
     - ✅ `applications.commands` (for slash commands)
   - Under "BOT PERMISSIONS", select:
     - ✅ `Send Messages`
     - ✅ `Embed Links`
     - ✅ `Read Message History`
     - ✅ `Use Slash Commands`
     - ✅ `Mention Everyone` (if using mentions.yml for roles)
   - Copy the generated URL and open it in your browser
   - Select your Discord server and authorize

### Slash Commands Available

After bot is online, these commands are available in Discord:

| Command | Description | Requires RCON | Server Parameter |
|---------|-------------|---------------|------------------|
| `/stats [server]` | Show current server stats (UPS, evolution, players) | ✅ Yes | Optional (defaults to first) |
| `/players [server]` | List online players | ✅ Yes | Optional |
| `/time [server]` | Show in-game time | ✅ Yes | Optional |
| `/save [server]` | Trigger server save | ✅ Yes | Optional |
| `/seed [server]` | Show map seed | ✅ Yes | Optional |
| `/version [server]` | Show Factorio version | ✅ Yes | Optional |
| `/research [server]` | Show current research | ✅ Yes | Optional |
| `/evolution [server]` | Show evolution factor | ✅ Yes | Optional |
| `/online [server]` | Alias for `/players` | ✅ Yes | Optional |
| `/uptime [server]` | Show server uptime | ✅ Yes | Optional |

**Note:** Commands require RCON to be configured for the target server. If `[server]` parameter is omitted, the command operates on the first configured server.

---

## Pattern Configuration

Customize event detection and Discord formatting with YAML patterns in `patterns/`.

### Loading Patterns

By default, all `.yml` files in `patterns/` are loaded. To restrict this, you can use the `PATTERN_FILES` environment variable (JSON array).

```bash
# Load only specific files
PATTERN_FILES='["vanilla.yml", "krastorio2.yml"]'
```

### Example Pattern File

```yaml
# patterns/custom.yml
events:
  rocket_launch:
    pattern: 'rocket.*launched'
    type: milestone
    emoji: "🚀"
    message: "Rocket launched by {player}!"
    enabled: true
    priority: 5
```

**📖 Complete syntax reference:** [Pattern Guide](PATTERNS.md)

---

## Log Levels

### Available Levels

| Level | Use Case | Output | Production? |
|-------|----------|--------|-------------|
| `debug` | Development, troubleshooting | Very verbose, all events | ❌ No |
| `info` | Production (recommended) | Standard operational logs | ✅ Yes |
| `warning` | Production (quiet) | Warnings and errors only | ✅ Yes |
| `error` | Production (minimal) | Errors only | ⚠️ Risky |

### Development Configuration

```bash
LOG_LEVEL=debug
LOG_FORMAT=console  # Easier to read
```

### Production Configuration

```bash
LOG_LEVEL=info
LOG_FORMAT=json  # Structured logging for aggregation (Splunk, ELK, etc.)
```

---

## Health Monitoring

### Health Check Endpoint

Available at: `http://localhost:8080/health`

```bash
# Test health
curl http://localhost:8080/health
```

**Response:**

```json
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "version": "2.1.0",
  "servers": {
    "production": "connected",
    "testing": "connected",
    "space_age": "log_only"
  }
}
```

### Docker Health Check

Built-in health check runs every 30 seconds:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

### Monitoring RCON Status

The health endpoint shows per-server RCON status:

- `"connected"` - RCON active and responding
- `"log_only"` - No RCON configured (log tailing only)
- `"error"` - RCON connection failed

---

## Advanced Topics

### Multi-Server Channel Strategy

**Option 1: One channel per server** (recommended)
```yaml
servers:
  prod:
    event_channel_id: 111111111111111111
  test:
    event_channel_id: 222222222222222222
```
**Pros:** Clear separation, easy filtering  
**Cons:** More channels to manage

**Option 2: Shared channel for all servers**
```yaml
servers:
  prod:
    event_channel_id: 123456789012345678  # Same
  test:
    event_channel_id: 123456789012345678  # Same
```
**Pros:** Single feed  
**Cons:** Noisy with multiple active servers

**Recommendation:** Use distinct channels for production servers. Shared channel works well for 2-3 low-activity dev servers.

### Custom Stats Intervals

```yaml
servers:
  high_activity:
    stats_interval: 120  # Every 2 minutes (chatty)

  low_activity:
    stats_interval: 1800  # Every 30 minutes (quiet)
```

**Recommendation:** 300 seconds (5 minutes) for most use cases. Lower values increase Discord API usage.

### Disabling Features Per Server

```yaml
servers:
  log_only_server:
    log_path: /factorio/logs/console.log
    # No rcon_* fields = log-only mode (no stats, no slash commands)
    event_channel_id: 123456789012345678

  stats_disabled:
    rcon_host: localhost
    rcon_port: 27015
    rcon_password: "password"
    event_channel_id: 987654321098765432
    enable_stats_collector: false  # Disable periodic stats
    enable_alerts: false            # Disable UPS alerts
```

---

## Next Steps

- ✅ [Installation Guide](installation.md) – Get up and running
- ✅ [RCON Setup](RCON_SETUP.md) – Configure real-time stats
- ✅ [Pattern Customization](PATTERNS.md) – Custom events and regex
- ✅ [Examples](EXAMPLES.md) – Real-world configurations
- ✅ [Troubleshooting](TROUBLESHOOTING.md) – Fix common issues

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](../LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)