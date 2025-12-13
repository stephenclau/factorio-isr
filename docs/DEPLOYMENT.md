---
layout: default
title: Deployment
---

# Production Deployment Guide

Complete guide for deploying Factorio ISR to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Preparation](#preparation)
- [Docker Deployment](#docker-deployment)
- [Systemd Deployment](#systemd-deployment)
- [Monitoring](#monitoring)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **OS:** Linux (recommended), macOS, Windows
- **Python:** 3.11 or higher
- **Docker:** 20.10+ (for Docker deployment)
- **Memory:** 256MB minimum, 512MB recommended
- **CPU:** 1 core minimum
- **Disk:** 100MB application + logs

---

### Required Information

Before deploying, gather:

- ✅ Discord **bot token**
- ✅ Discord **event channel ID**
- ✅ Factorio log file path
- ✅ RCON password (if using RCON)
- ✅ Server IP/hostname
- ✅ Network access to Factorio server

---

## Preparation

### Step 1: Clone Repository

```bash
# Production server
cd /opt
sudo git clone https://github.com/yourusername/factorio-isr.git
cd factorio-isr

# Or download release
wget https://github.com/yourusername/factorio-isr/archive/v2.0.0.tar.gz
tar -xzf v2.0.0.tar.gz
cd factorio-isr-2.0.0
```

---

### Step 2: Create Secrets

```bash
# Create secrets directory
mkdir -p .secrets

# Add Discord bot token
echo "your-discord-bot-token" > .secrets/DISCORD_BOT_TOKEN.txt

# Add RCON password
echo "your-rcon-password" > .secrets/RCON_PASSWORD.txt

# Secure secrets
chmod 700 .secrets
chmod 600 .secrets/*
```

---

### Step 3: Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit configuration
nano .env
```

**Minimum production .env (bot mode only):**

```bash
# Discord Bot
DISCORD_BOT_TOKEN=   # Will use secret file if empty
DISCORD_EVENT_CHANNEL_ID=123456789012345678

# Factorio
FACTORIO_LOG_PATH=/path/to/factorio/console.log

# Bot
BOT_NAME=Production Factorio Server

# Logging
LOG_LEVEL=info
LOG_FORMAT=json

# Health Check
HEALTH_CHECK_HOST=0.0.0.0
HEALTH_CHECK_PORT=8080

# RCON (optional)
RCON_ENABLED=true
RCON_HOST=localhost
RCON_PORT=27015
STATS_INTERVAL=300
```

> Bot token resolution order: `.secrets/DISCORD_BOT_TOKEN.txt` → `/run/secrets/DISCORD_BOT_TOKEN` → `DISCORD_BOT_TOKEN` env.

---

### Step 4: Create Patterns

```bash
# Verify patterns directory
ls -la patterns/

# Should contain:
# - vanilla.yml (included)
# - research.yml / achievements.yml (optional)
# - custom patterns (add as needed)
```

---

### Step 5: Security Checklist

```bash
# Verify secrets not in git
grep -r "DISCORD_BOT_TOKEN" .git/ || echo "✅ No bot tokens in git"

grep -r "discord.com/api" .git/ || echo "✅ No raw Discord URLs in git"

# Check .gitignore
grep ".secrets" .gitignore || echo ".secrets/" >> .gitignore
grep ".env" .gitignore || echo ".env" >> .gitignore

# Verify file permissions
ls -la .secrets/
# Should show: drwx------ (700) for directory
# Should show: -rw------- (600) for files
```

---

## Docker Deployment

### Method 1: Docker Compose (Recommended)

#### Step 1: Prepare docker-compose.yml

Configure `docker-compose.yml` with your environment settings:

```yaml
version: '3.8'

services:
  factorio-isr:
    build: .
    container_name: factorio-isr
    restart: unless-stopped

    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - LOG_LEVEL=info
      - LOG_FORMAT=json
      - HEALTH_CHECK_HOST=0.0.0.0
      - HEALTH_CHECK_PORT=8080
      - RCON_ENABLED=true
      - RCON_HOST=factorio-server
      - RCON_PORT=27015
      - STATS_INTERVAL=300
      - DISCORD_EVENT_CHANNEL_ID=123456789012345678

    secrets:
      - discord_bot_token
      - rcon_password

    volumes:
      - /path/to/factorio/logs:/factorio:ro
      - ./patterns:/app/patterns:ro
      - ./config:/app/config:ro
      - ./logs:/app/logs

    ports:
      - "8080:8080"

    networks:
      - factorio

    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

secrets:
  discord_bot_token:
    file: .secrets/DISCORD_BOT_TOKEN.txt
  rcon_password:
    file: .secrets/RCON_PASSWORD.txt

networks:
  factorio:
    driver: bridge
```

#### Step 2: Deploy

```bash
# Build image
docker-compose build

# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

#### Step 3: Verify

```bash
# Check health endpoint
curl http://localhost:8080/health

# Expected: {"status": "healthy", ...}

# View logs
docker-compose logs --tail=50 factorio-isr

# Check container is running
docker ps | grep factorio-isr
```

---

### Method 2: Docker Run

Without docker-compose:

```bash
# Build image
docker build -t factorio-isr:latest .

# Run container
docker run -d \
  --name factorio-isr \
  --restart unless-stopped \
  -e FACTORIO_LOG_PATH=/factorio/console.log \
  -e DISCORD_EVENT_CHANNEL_ID=123456789012345678 \
  -e BOT_NAME="Production Server" \
  -e LOG_LEVEL=info \
  -e LOG_FORMAT=json \
  -e RCON_ENABLED=true \
  -e RCON_HOST=localhost \
  -e RCON_PORT=27015 \
  -v /path/to/factorio/logs:/factorio:ro \
  -v $(pwd)/.secrets/DISCORD_BOT_TOKEN.txt:/run/secrets/DISCORD_BOT_TOKEN:ro \
  -v $(pwd)/.secrets/RCON_PASSWORD.txt:/run/secrets/RCON_PASSWORD:ro \
  -v $(pwd)/patterns:/app/patterns:ro \
  -v $(pwd)/config:/app/config:ro \
  -p 8080:8080 \
  factorio-isr:latest

# View logs
docker logs -f factorio-isr
```

---

## Systemd Deployment

For deployments without Docker, follow your organization's standard systemd service deployment patterns.

### Requirements

- Python 3.11+ virtual environment
- Service start command: `python -m src.main`
- Working directory: `/opt/factorio-isr`
- Environment file: `.env` with required variables
- Restart policy: `always`

### Basic Service Structure

```ini
[Unit]
Description=Factorio ISR Discord Integration
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=factorio
Group=factorio
WorkingDirectory=/opt/factorio-isr
EnvironmentFile=/opt/factorio-isr/.env
ExecStart=/opt/factorio-isr/venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

For production hardening guidance, contact [licensing@laudiversified.com](mailto:licensing@laudiversified.com).

---

## Monitoring

### Health Check

```bash
curl http://localhost:8080/health
```

Expected response:

```json
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "version": "2.0.0"
}
```

### Logs

- **Docker:**
  ```bash
  docker-compose logs -f factorio-isr
  ```

- **Systemd:**
  ```bash
  journalctl -u factorio-isr -f
  ```

---

## Maintenance

### Updating the Application

```bash
# Pull latest changes
cd /opt/factorio-isr
git pull origin main

# Rebuild Docker image (if using Docker)
docker-compose build
docker-compose up -d

# Or restart systemd service
sudo systemctl restart factorio-isr
```

### Rotating Logs

- Configure external log rotation for `/app/logs` or Docker json-file logs
- Use `max-size` and `max-file` options (see docker-compose example)

### Backups

- Backup:
  - `patterns/`
  - `config/` (servers.yml, mentions.yml, secmon.yml)
  - `.env`
  - `.secrets/` (or Docker/Swarm secrets definitions)

---

## Troubleshooting

- **Bot not online in Discord:**
  - Check `DISCORD_BOT_TOKEN` is valid
  - Verify bot is invited to the server
  - Check `DISCORD_EVENT_CHANNEL_ID` exists and bot has permissions

- **No events in Discord:**
  - Verify `FACTORIO_LOG_PATH` is correct and readable
  - Confirm Factorio is writing to `console.log`
  - Run with `LOG_LEVEL=debug`

- **RCON stats not updating:**
  - Verify `RCON_ENABLED=true`
  - Check RCON host/port/password
  - Confirm RCON is enabled in Factorio server config

- **Health check failing:**
  - Check logs for errors
  - Ensure `HEALTH_CHECK_PORT` not in use

For more details, see:
- [Configuration Guide](configuration.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)
