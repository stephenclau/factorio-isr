---
layout: default
title: Configuration
---

# 📋 Configuration Guide

Complete configuration reference for Factorio ISR.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Docker Secrets](#docker-secrets-recommended-for-production)
- [File Layout](#file-layout)
- [Server Configuration (servers.yml)](#server-configuration-serversyml)
- [Discord Bot Setup](#discord-bot-setup)
- [Pattern Configuration](#pattern-configuration)
- [Log Levels](#log-levels)
- [Health Monitoring](#health-monitoring)

---

## Environment Variables

### Core Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ Yes | - | Discord bot token (can use secret file) |
| `DISCORD_EVENT_CHANNEL_ID` | No | - | **Deprecated**: Use `servers.yml` for channel mapping. |

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

---

## File Layout

The application uses a strict directory structure (hardcoded for reliability in Docker).

| Path | Description |
|------|-------------|
| `/app/config/` | **Configuration Directory**. Must contain `servers.yml` and `mentions.yml`. |
| `/app/patterns/` | **Patterns Directory**. Must contain YAML pattern files (e.g., `vanilla.yml`). |
| `/app/logs/` | **Logs Directory**. Application logs are written here. |
| `.secrets/` | **Secrets Directory**. Local development secrets. |

**Note**: `CONFIG_DIR` and `PATTERNS_DIR` environment variables are no longer supported. You must mount volumes to `/app/config` and `/app/patterns`.

---

## Server Configuration (`servers.yml`)

The `servers.yml` file in your config directory is the single source of truth for all server instances.

```yaml
servers:
  # Unique server identifier (snake_case recommended)
  los_hermanos:
    # Path to the Factorio console.log (inside the container)
    log_path: /factorio/los_hermanos/console.log
    
    # RCON Connection Details
    rcon_host: factorio-1.internal
    rcon_port: 27015
    rcon_password: "secure_password_here"  # Or use secrets mapping
    
    # Discord Channel ID for this server's events
    discord_channel_id: 123456789012345678
    
    # RCON Polling Interval (seconds)
    stats_interval: 300
    
  space_age:
    log_path: /factorio/space_age/console.log
    rcon_host: factorio-2.internal
    rcon_port: 27015
    rcon_password: "another_password"
    discord_channel_id: 987654321098765432
    stats_interval: 300
```

---

## Docker Secrets (Recommended for Production)

For production deployments, use Docker secrets or local `.secrets/` folder for sensitive data.

### Local Development (`.secrets/` folder)

```bash
# Create secrets directory
mkdir -p .secrets

# Add Discord bot token
echo "your-discord-bot-token" > .secrets/DISCORD_BOT_TOKEN.txt

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

---

## Pattern Configuration

Customize event detection and Discord formatting with YAML patterns in `/app/patterns`.

### Loading Patterns

By default, all `.yml` files in `/app/patterns` are loaded. To restrict this, you can use the `PATTERN_FILES` environment variable (JSON array).

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
    channel: milestones
```

**📖 Complete syntax reference:** [Pattern Guide](PATTERNS.md)

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
  "version": "2.1.0"
}
```

### Docker Health Check

Built-in health check runs every 30 seconds:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)
