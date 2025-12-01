# 📋 Configuration Guide

Complete configuration reference for Factorio ISR (Phase 1-3).

## Table of Contents

- [Environment Variables](#environment-variables)
- [Docker Secrets](#docker-secrets-recommended-for-production)
- [RCON Configuration](#rcon-configuration-phase-3)
- [Multi-Channel Routing](#multi-channel-routing-phase-2)
- [Pattern Configuration](#pattern-configuration-phase-2)
- [Discord Webhook Setup](#getting-a-discord-webhook)
- [Supported Events](#supported-events)
- [Log Configuration](#log-levels)
- [Health Monitoring](#health-monitoring)
- [Example Configurations](#example-configurations)

---

## Environment Variables

### Core Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | ✅ Yes | - | Discord webhook URL for posting events (can use secret file) |
| `FACTORIO_LOG_PATH` | ✅ Yes | - | Path to Factorio console.log file |
| `BOT_NAME` | No | `Factorio ISR` | Display name for Discord webhook |
| `BOT_AVATAR_URL` | No | - | Avatar URL for Discord webhook |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `info` | Logging level: `debug`, `info`, `warning`, `error`, `critical` |
| `LOG_FORMAT` | No | `console` | Log output format: `json` (production) or `console` (development) |

### Health Check

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HEALTH_CHECK_HOST` | No | `0.0.0.0` | Health check server bind address |
| `HEALTH_CHECK_PORT` | No | `8080` | Health check server port |

### Pattern Configuration (Phase 2)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PATTERNS_DIR` | No | `patterns` | Directory containing pattern YAML files |
| `PATTERN_FILES` | No | All `.yml` files | JSON array of specific pattern files to load |

### Multi-Channel Routing (Phase 2)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEBHOOK_CHANNELS` | No | `{}` | JSON object mapping channel names to webhook URLs |

**Example:**
```bash
WEBHOOK_CHANNELS={"chat":"https://discord.com/webhooks/...","admin":"https://discord.com/webhooks/..."}
```

### RCON Configuration (Phase 3) ✨

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RCON_ENABLED` | No | `false` | Enable RCON integration for real-time stats |
| `RCON_HOST` | No | `localhost` | Factorio server hostname or IP address |
| `RCON_PORT` | No | `27015` | RCON port (must match Factorio server config) |
| `RCON_PASSWORD` | Conditional* | - | RCON password (required if `RCON_ENABLED=true`) |
| `STATS_INTERVAL` | No | `300` | Stats collection interval in seconds (5 minutes) |

*Required when `RCON_ENABLED=true`

**📖 See [RCON Setup Guide](docs/RCON_SETUP.md) for detailed configuration instructions**

---

## Docker Secrets (Recommended for Production)

For production deployments, use Docker secrets or local `.secrets/` folder for sensitive data.

### Local Development (`.secrets/` folder)

```bash
# Create secrets directory
mkdir -p .secrets

# Add Discord webhook
echo "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" > .secrets/DISCORD_WEBHOOK_URL.txt

# Add RCON password (Phase 3)
echo "your-rcon-password" > .secrets/RCON_PASSWORD.txt

# Secure files
chmod 700 .secrets
chmod 600 .secrets/*

# Add to .gitignore
echo ".secrets/" >> .gitignore
```

The application automatically checks:
1. `.secrets/SECRET_NAME.txt` (local development)
2. `/run/secrets/SECRET_NAME` (Docker secrets)
3. Environment variable `$SECRET_NAME` (fallback)

---

### Docker Compose Secrets

```yaml
services:
  factorio-isr:
    secrets:
      - discord_webhook_url
      - rcon_password
    environment:
      - RCON_ENABLED=true
      - RCON_HOST=factorio-server

secrets:
  discord_webhook_url:
    file: .secrets/DISCORD_WEBHOOK_URL.txt
  rcon_password:
    file: .secrets/RCON_PASSWORD.txt
```

---

### Docker Swarm Secrets

```bash
# Create secrets
docker secret create discord_webhook .secrets/DISCORD_WEBHOOK_URL.txt
docker secret create rcon_password .secrets/RCON_PASSWORD.txt

# Deploy service
docker service create \
  --name factorio-isr \
  --secret discord_webhook \
  --secret rcon_password \
  -e RCON_ENABLED=true \
  yourusername/factorio-isr:latest
```

---

## RCON Configuration (Phase 3)

### Enable RCON

```bash
# .env
RCON_ENABLED=true
RCON_HOST=localhost
RCON_PORT=27015
STATS_INTERVAL=300
```

```bash
# Store password securely
echo "your-rcon-password" > .secrets/RCON_PASSWORD.txt
chmod 600 .secrets/RCON_PASSWORD.txt
```

### What RCON Provides

When enabled, RCON integration provides:
- 📊 **Real-time player count** posted to Discord every 5 minutes (configurable)
- 👥 **Online player list** with player names
- ⏰ **Server game time** (day/time in-game)
- 🔄 **Automatic reconnection** if connection is lost

### Discord Stats Format

```
📊 **Server Status**
👥 Players Online: 3
📝 Alice, Bob, Charlie
⏰ Game Time: Day 42, 13:45
```

Stats are posted every `STATS_INTERVAL` seconds (default: 300 = 5 minutes).

### RCON Requirements

- ✅ Factorio server with RCON enabled
- ✅ RCON password configured on Factorio server
- ✅ Network connectivity to RCON port
- ✅ `rcon` Python package installed (included in requirements.txt)

**📖 Complete guide:** [RCON Setup Guide](docs/RCON_SETUP.md)

---

## Multi-Channel Routing (Phase 2)

Route different event types to different Discord channels.

### Basic Setup

```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/webhooks/MAIN_WEBHOOK
WEBHOOK_CHANNELS={"chat":"https://discord.com/webhooks/CHAT","events":"https://discord.com/webhooks/EVENTS"}
```

### Pattern Channel Assignment

```yaml
# patterns/routing.yml
patterns:
  - name: chat_message
    regex: '\[CHAT\] (.+?): (.+)'
    event_type: chat
    discord:
      channel: chat  # Routes to chat webhook
      emoji: "💬"

  - name: player_death
    regex: '(.+) was killed'
    event_type: death
    discord:
      channel: events  # Routes to events webhook
      emoji: "💀"
```

### Common Channel Setups

**Simple (2 channels):**
```bash
WEBHOOK_CHANNELS={"chat":"URL1","events":"URL2"}
```

**Medium (4 channels):**
```bash
WEBHOOK_CHANNELS={"chat":"URL1","events":"URL2","milestones":"URL3","admin":"URL4"}
```

**Advanced (6+ channels):**
```bash
WEBHOOK_CHANNELS={"chat":"URL1","joins":"URL2","deaths":"URL3","achievements":"URL4","research":"URL5","milestones":"URL6"}
```

**📖 Complete guide:** [Multi-Channel Routing Guide](docs/MULTI_CHANNEL.md)

---

## Pattern Configuration (Phase 2)

Customize event detection and Discord formatting with YAML patterns.

### Default Patterns

Included patterns in `patterns/vanilla.yml`:
- Player join/leave
- Chat messages
- Deaths
- Achievements
- Research completion
- Rocket launches

### Custom Patterns

Create custom pattern files in `patterns/` directory:

```yaml
# patterns/custom.yml
patterns:
  - name: custom_event
    regex: 'Your regex pattern here'
    event_type: custom
    priority: 50
    fields:
      field_name: 1
    discord:
      channel: general
      emoji: "🎮"
      color: 0x00FF00
      title: "Event Title"
      description: "{field_name} did something"
```

### Load Specific Patterns

```bash
# Load only specific files
PATTERN_FILES=["vanilla.yml","krastorio2.yml","space-exploration.yml"]
```

**📖 Complete syntax reference:** [Pattern Guide](docs/PATTERNS.md)

---

## Getting a Discord Webhook

### Step-by-Step Instructions

1. **Open Discord** → Go to your server
2. **Right-click channel** → Edit Channel
3. **Navigate to Integrations** → Webhooks
4. **Click New Webhook**
5. **Customize:**
   - Name: "Factorio Server", "Factorio Chat", etc.
   - Avatar: Optional custom icon
6. **Copy Webhook URL**
7. **Add to configuration:**
   - `.env`: `DISCORD_WEBHOOK_URL=...`
   - Or `.secrets/DISCORD_WEBHOOK_URL.txt`

### Webhook URL Format

```
https://discord.com/api/webhooks/{WEBHOOK_ID}/{WEBHOOK_TOKEN}
```

### Multiple Webhooks

For multi-channel routing, create separate webhooks for each channel:
- One webhook for chat messages
- One webhook for game events
- One webhook for admin notifications
- etc.

---

## Supported Events

### Phase 1: Core Events

- ✅ **Player Join** - Player connected to server
- 👋 **Player Leave** - Player disconnected
- 💬 **Chat Messages** - Player chat
- 🖥️ **Server Messages** - Server announcements
- 💀 **Deaths** - Player deaths with cause
- 🏆 **Achievements** - Achievement unlocks
- 🔬 **Research** - Technology research completion
- 🚀 **Rocket Launches** - Rocket launch celebrations

### Phase 2: Enhanced Events

- 📋 **Custom Patterns** - Define your own event types
- 🎯 **Priority Routing** - Route by event importance
- 📨 **Multi-Channel** - Different events to different channels
- 🎨 **Custom Formatting** - Full Discord embed customization
- 🧩 **Mod Support** - Patterns for popular mods

### Phase 3: RCON Statistics ✨

- 📊 **Server Stats** - Automated status reports
- 👥 **Player Count** - Real-time player tracking
- 📝 **Player List** - Who's online
- ⏰ **Game Time** - Current in-game time

**📖 See examples:** [Usage Examples](docs/EXAMPLES.md)

---

## Log Levels

### Available Levels

| Level | Use Case | Output |
|-------|----------|--------|
| `debug` | Development, troubleshooting | Very verbose, all events |
| `info` | Production (recommended) | Standard operational logs |
| `warning` | Production | Warnings and errors only |
| `error` | Production | Errors only |
| `critical` | Production | Critical failures only |

### Development Configuration

```bash
LOG_LEVEL=debug
LOG_FORMAT=console  # Easier to read
```

### Production Configuration

```bash
LOG_LEVEL=info
LOG_FORMAT=json  # Structured logging
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
  "uptime": 12345,
  "version": "1.0.0"
}
```

### Configuration

```bash
HEALTH_CHECK_HOST=0.0.0.0  # Listen on all interfaces
HEALTH_CHECK_PORT=8080     # Default port
```

### Docker Health Check

Built-in health check runs every 30 seconds:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

### Monitoring

```bash
# Docker
docker-compose ps
docker inspect --format='{{.State.Health.Status}}' factorio-isr

# Systemd
systemctl status factorio-isr
```

---

## Example Configurations

### Minimal (Phase 1)

```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/webhooks/...
FACTORIO_LOG_PATH=/factorio/console.log
```

### Development

```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/webhooks/...
FACTORIO_LOG_PATH=/path/to/factorio/console.log
LOG_LEVEL=debug
LOG_FORMAT=console
BOT_NAME=Factorio Dev Bot
```

### Production with RCON (Phase 3)

```bash
# .env
# Use secret files for sensitive data
FACTORIO_LOG_PATH=/factorio/console.log
LOG_LEVEL=info
LOG_FORMAT=json
HEALTH_CHECK_HOST=0.0.0.0
HEALTH_CHECK_PORT=8080
BOT_NAME=Factorio Production Server

# RCON enabled
RCON_ENABLED=true
RCON_HOST=localhost
RCON_PORT=27015
STATS_INTERVAL=300
```

```bash
# .secrets/DISCORD_WEBHOOK_URL.txt
https://discord.com/webhooks/...

# .secrets/RCON_PASSWORD.txt
your-secure-rcon-password
```

### Production with Multi-Channel (Phase 2 + 3)

```bash
# .env
FACTORIO_LOG_PATH=/factorio/console.log
LOG_LEVEL=info
LOG_FORMAT=json
BOT_NAME=Factorio Server

# Multi-channel routing
WEBHOOK_CHANNELS={"chat":"https://discord.com/webhooks/CHAT","events":"https://discord.com/webhooks/EVENTS","milestones":"https://discord.com/webhooks/MILESTONES","admin":"https://discord.com/webhooks/ADMIN"}

# Custom patterns
PATTERNS_DIR=patterns
PATTERN_FILES=["vanilla.yml","custom.yml","krastorio2.yml"]

# RCON enabled
RCON_ENABLED=true
RCON_HOST=factorio-server
RCON_PORT=27015
STATS_INTERVAL=300
```

---

## Phase Implementation Status

| Phase | Status | Features |
|-------|--------|----------|
| **Phase 1** | ✅ Complete | Core log monitoring, Discord integration, health checks |
| **Phase 2** | ✅ Complete | YAML patterns, multi-channel routing, custom events |
| **Phase 3** | ✅ Complete | RCON integration, server statistics, player tracking |

**All phases production-ready with 95%+ test coverage!**

---

## Documentation

### Complete Guides

- **[RCON Setup Guide](docs/RCON_SETUP.md)** ⭐ - Configure Phase 3 server statistics
- **[Usage Examples](docs/EXAMPLES.md)** - Common configuration scenarios
- **[Multi-Channel Guide](docs/MULTI_CHANNEL.md)** - Route events to different channels
- **[Pattern Syntax](docs/PATTERNS.md)** - Complete pattern reference
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Quick Links

- **Getting Started:** [README.md](../README.md)
- **Docker Deployment:** [Deployment Guide](docs/DEPLOYMENT.md)
- **Pattern Examples:** [Examples](docs/EXAMPLES.md)
- **Common Issues:** [Troubleshooting](docs/TROUBLESHOOTING.md)

---

## Next Steps

1. **Basic Setup:**
   - [Get Discord webhook](#getting-a-discord-webhook)
   - [Configure environment variables](#environment-variables)
   - [Start the application](../README.md#quick-start)

2. **Enable RCON (Phase 3):**
   - [RCON Setup Guide](docs/RCON_SETUP.md)
   - Configure Factorio server RCON
   - Enable stats collection

3. **Advanced Features:**
   - [Multi-channel routing](docs/MULTI_CHANNEL.md)
   - [Custom patterns](docs/PATTERNS.md)
   - [Mod-specific events](docs/EXAMPLES.md#custom-mod-events)

4. **Deploy to Production:**
   - [Deployment Guide](docs/DEPLOYMENT.md)
   - Set up monitoring
   - Configure backups

---

**Need help?** Check the [Troubleshooting Guide](docs/TROUBLESHOOTING.md) or open an issue on GitHub.
