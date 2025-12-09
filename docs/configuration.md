# 📋 Configuration Guide

Complete configuration reference for Factorio ISR.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Docker Secrets](#docker-secrets-recommended-for-production)
- [Discord Bot Setup](#discord-bot-setup)
- [RCON Configuration](#rcon-configuration)
- [Multi-Server Support](#multi-server-support)
- [Pattern Configuration](#pattern-configuration)
- [Supported Events](#supported-events)
- [Log Levels](#log-levels)
- [Health Monitoring](#health-monitoring)
- [Example Configurations](#example-configurations)

---

## Environment Variables

### Core Configuration (Discord Bot)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ Yes | - | Discord bot token (can use secret file) |
| `DISCORD_EVENT_CHANNEL_ID` | ✅ Yes | - | Discord channel ID for event notifications |
| `FACTORIO_LOG_PATH` | ✅ Yes | - | Path to Factorio console.log file |
| `BOT_NAME` | No | `Factorio ISR` | Display name for Discord bot |
| `BOT_AVATAR_URL` | No | - | Avatar URL for Discord bot |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `info` | Logging level: `debug`, `info`, `warning`, `error`, `critical` |
| `LOG_FORMAT` | No | `json` | Log output format: `json` (production) or `console` (development) |

### Health Check

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HEALTH_CHECK_HOST` | No | `0.0.0.0` | Health check server bind address |
| `HEALTH_CHECK_PORT` | No | `8080` | Health check server port |

### Pattern Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PATTERNS_DIR` | No | `patterns` | Directory containing pattern YAML files |
| `PATTERN_FILES` | No | All `.yml` files | JSON array of specific pattern files to load |

### RCON Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RCON_ENABLED` | No | `false` | Enable RCON integration for real-time stats |
| `RCON_HOST` | No | `localhost` | Factorio server hostname or IP address |
| `RCON_PORT` | No | `27015` | RCON port (must match Factorio server config) |
| `RCON_PASSWORD` | Conditional* | - | RCON password (required if `RCON_ENABLED=true`) |
| `STATS_INTERVAL` | No | `300` | Stats collection interval in seconds (5 minutes) |

*Required when `RCON_ENABLED=true`

### Multi-Server Support

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SERVERS_CONFIG` | No | `config/servers.yml` | Path to servers.yml configuration file |

**📖 See [RCON Setup Guide](RCON_SETUP.md) for detailed configuration instructions**

---

## Docker Secrets (Recommended for Production)

For production deployments, use Docker secrets or local `.secrets/` folder for sensitive data.

### Local Development (`.secrets/` folder)

```bash
# Create secrets directory
mkdir -p .secrets

# Add Discord bot token
echo "your-discord-bot-token" > .secrets/DISCORD_BOT_TOKEN.txt

# Add RCON password (optional)
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

### Docker Compose Secrets

```yaml
services:
  factorio-isr:
    secrets:
      - discord_bot_token
      - rcon_password
    environment:
      - DISCORD_EVENT_CHANNEL_ID=123456789012345678
      - RCON_ENABLED=true
      - RCON_HOST=factorio-server

secrets:
  discord_bot_token:
    file: .secrets/DISCORD_BOT_TOKEN.txt
  rcon_password:
    file: .secrets/RCON_PASSWORD.txt
```

### Docker Swarm Secrets

```bash
# Create secrets
docker secret create discord_bot_token .secrets/DISCORD_BOT_TOKEN.txt
docker secret create rcon_password .secrets/RCON_PASSWORD.txt

# Deploy service
docker service create \
  --name factorio-isr \
  --secret discord_bot_token \
  --secret rcon_password \
  -e DISCORD_EVENT_CHANNEL_ID=123456789012345678 \
  -e RCON_ENABLED=true \
  yourusername/factorio-isr:latest
```

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
   - Under "Bot" → "Intents", enable:
     - `Message Content Intent` (required to read messages)
     - `Server Members Intent` (optional, for advanced features)

4. **Generate Invite URL**
   - Go to "OAuth2" → "URL Generator"
   - Under "SCOPES", select:
     - `bot`
     - `applications.commands` (for slash commands)
   - Under "BOT PERMISSIONS", select:
     - `Send Messages`
     - `Embed Links`
     - `Read Message History`
     - `Use Slash Commands`
   - Copy the generated URL and open it in your browser
   - Select your Discord server and authorize

5. **Get Event Channel ID**
   - In Discord, enable Developer Mode: User Settings → Advanced → Developer Mode
   - Right-click the channel where events should be posted
   - Click "Copy Channel ID"
   - Set `DISCORD_EVENT_CHANNEL_ID=YOUR_ID` in `.env`

### Verify Bot Setup

```bash
# Test bot connection
curl -X GET https://discord.com/api/v10/users/@me \
  -H "Authorization: Bot YOUR_BOT_TOKEN"

# Should return bot user info
```

---

## RCON Configuration

### Enable RCON

```bash
# .env
RCON_ENABLED=true
RCON_HOST=localhost
RCON_PORT=27015
STATS_INTERVAL=300
```

Store password securely:

```bash
echo "your-rcon-password" > .secrets/RCON_PASSWORD.txt
chmod 600 .secrets/RCON_PASSWORD.txt
```

### What RCON Provides

When enabled, RCON integration provides:
- 📊 **Real-time player count** posted to Discord every 5 minutes (configurable)
- 👥 **Online player list** with player names
- ⏰ **Server game time** (day/time in-game)
- 📈 **UPS monitoring** with low-UPS alerts
- 🧬 **Evolution factor** tracking per surface
- 🔄 **Automatic reconnection** if connection is lost

### Discord Stats Format

```
📊 **Server Status**
👥 Players Online: 3
📝 Alice, Bob, Charlie
⏰ Game Time: Day 42, 13:45
📈 UPS: 59.8/60 ✅
🧬 Evolution: 45.2%
```

Stats are posted every `STATS_INTERVAL` seconds (default: 300 = 5 minutes).

### RCON Requirements

- ✅ Factorio server with RCON enabled
- ✅ RCON password configured on Factorio server
- ✅ Network connectivity to RCON port
- ✅ `rcon` Python package installed (included in requirements.txt)

**📖 Complete guide:** [RCON Setup Guide](RCON_SETUP.md)

---

## Multi-Server Support

Configure multiple Factorio servers via `config/servers.yml`:

```yaml
servers:
  los_hermanos:
    log_path: /factorio/los_hermanos/console.log
    rcon_host: factorio-1.internal
    rcon_port: 27015
    rcon_password: password1
    discord_channel_id: 123456789012345678
    stats_interval: 300
    
  space_age:
    log_path: /factorio/space_age/console.log
    rcon_host: factorio-2.internal
    rcon_port: 27015
    rcon_password: password2
    discord_channel_id: 987654321098765432
    stats_interval: 300
```

Set in environment:

```bash
SERVERS_CONFIG=config/servers.yml
```

The bot will coordinate events and stats across all configured servers.

---

## Pattern Configuration

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
events:
  rocket_launch:
    pattern: 'rocket.*launched'
    type: milestone
    emoji: "🚀"
    message: "Rocket launched by {player}!"
    enabled: true
    priority: 5
    channel: milestones
```

### Load Specific Patterns

```bash
# Load only specific files
PATTERN_FILES=["vanilla.yml","krastorio2.yml","space-exploration.yml"]
```

**📖 Complete syntax reference:** [Pattern Guide](PATTERNS.md)

---

## Supported Events

### Core Events (Phase 1-2)

- ✅ **Player Join** – Player connected to server
- 👋 **Player Leave** – Player disconnected
- 💬 **Chat Messages** – Player chat
- 🖥️ **Server Messages** – Server announcements
- 💀 **Deaths** – Player deaths with cause
- 🏆 **Achievements** – Achievement unlocks
- 🔬 **Research** – Technology research completion
- 🚀 **Rocket Launches** – Rocket launch celebrations

### Advanced Events (Phase 2+)

- 📋 **Custom Patterns** – Define your own event types
- 🎯 **Priority Routing** – Route by event importance
- 📨 **Multi-Channel** – Different events to different channels
- 🎨 **Custom Formatting** – Full Discord formatting
- 🧩 **Mod Support** – Patterns for popular mods

### Metrics & Alerts (Phase 6)

- 📊 **Server Stats** – Automated status reports
- 👥 **Player Count** – Real-time player tracking
- 📝 **Player List** – Who's online
- ⏰ **Game Time** – Current in-game time
- 📈 **UPS Monitoring** – Low-UPS alerts with thresholds
- 🧬 **Evolution Tracking** – Biters evolution per surface

**📖 See examples:** [Usage Examples](EXAMPLES.md)

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
LOG_FORMAT=json  # Structured logging for aggregation
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
  "version": "2.0.0"
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

### Minimal (Log Tailing + Bot)

```bash
# .env
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_EVENT_CHANNEL_ID=123456789012345678
FACTORIO_LOG_PATH=/factorio/console.log
LOG_LEVEL=info
LOG_FORMAT=json
```

### Development (with Debug Logging)

```bash
# .env
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_EVENT_CHANNEL_ID=123456789012345678
FACTORIO_LOG_PATH=/path/to/factorio/console.log
LOG_LEVEL=debug
LOG_FORMAT=console
BOT_NAME=Factorio Dev Bot
HEALTH_CHECK_PORT=8080
```

### Production with RCON

```bash
# .env
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
# .secrets/DISCORD_BOT_TOKEN.txt
your-discord-bot-token

# .secrets/RCON_PASSWORD.txt
your-secure-rcon-password
```

### Production Multi-Server

```bash
# .env
FACTORIO_LOG_PATH=/factorio/console.log
LOG_LEVEL=info
LOG_FORMAT=json
BOT_NAME=Factorio Multi-Server Bot

# Patterns
PATTERNS_DIR=patterns
PATTERN_FILES=["vanilla.yml","research.yml","achievements.yml"]

# Multi-server
SERVERS_CONFIG=config/servers.yml

# RCON enabled
RCON_ENABLED=true
```

```yaml
# config/servers.yml
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

---

## Phase Implementation Status

| Phase | Status | Features |
|-------|--------|----------|
| **Phase 1** | ✅ Complete | Core log monitoring, Discord bot integration, health checks |
| **Phase 2** | ✅ Complete | YAML patterns, multi-server support, custom events |
| **Phase 3** | ✅ Complete | RCON integration, server statistics, player tracking |
| **Phase 4** | ✅ Complete | Discord bot with slash commands, permission system |
| **Phase 5** | ✅ Complete | Admin commands, RCON write operations, multi-server |
| **Phase 6** | ✅ In use | Metrics polling, UPS alerts, hardened regex/config |

**All phases production-ready with high test coverage!**

---

## Documentation

### Complete Guides

- **[Discord Bot Setup](#discord-bot-setup)** – Create and configure your bot
- **[RCON Setup Guide](RCON_SETUP.md)** ⭐ – Configure server statistics
- **[Usage Examples](EXAMPLES.md)** – Common configuration scenarios
- **[Pattern Syntax](PATTERNS.md)** – Complete pattern reference
- **[Deployment Guide](DEPLOYMENT.md)** – Production deployment
- **[Troubleshooting](TROUBLESHOOTING.md)** – Common issues and solutions
- **[Mentions Guide](mentions.md)** – @mention role vocabulary
- **[Security Guide](secmon.md)** – Security monitoring and rate limiting

### Quick Links

- **Getting Started:** [README.md](../README.md)
- **Docker Deployment:** [Deployment Guide](DEPLOYMENT.md)
- **Pattern Examples:** [Examples](EXAMPLES.md)
- **Common Issues:** [Troubleshooting](TROUBLESHOOTING.md)

---

## Next Steps

1. **Basic Setup:**
   - [Create Discord bot](#discord-bot-setup)
   - [Configure environment variables](#environment-variables)
   - [Start the application](../README.md#quick-start)

2. **Enable RCON (optional):**
   - [RCON Setup Guide](RCON_SETUP.md)
   - Configure Factorio server RCON
   - Enable stats collection

3. **Advanced Features:**
   - [Custom patterns](PATTERNS.md)
   - [Multi-server configuration](configuration.md#multi-server-support)
   - [Mod-specific events](EXAMPLES.md)
   - [Mention role vocabulary](mentions.md)

4. **Deploy to Production:**
   - [Deployment Guide](DEPLOYMENT.md)
   - Set up monitoring
   - Configure log rotation

---

**Need help?** Check the [Troubleshooting Guide](TROUBLESHOOTING.md) or open an issue on GitHub.
