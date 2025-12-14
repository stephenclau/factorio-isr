---
layout: default
title: Deployment
---

# Production Deployment Guide

Complete guide for deploying Factorio ISR to production with multi-server support.

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

**Realistic resource requirements per deployment:**

| Servers Managed | Memory (RAM) | CPU | Disk Space | Network |
|----------------|--------------|-----|------------|----------|
| 1 server | 256MB | 0.5 core | 100MB | Minimal |
| 5 servers | 512MB | 1 core | 150MB | Low |
| 10 servers | 1GB | 1-2 cores | 200MB | Moderate |
| 20+ servers | 2GB+ | 2+ cores | 300MB+ | Monitor carefully |

**Supported platforms:**
- **Linux:** Ubuntu 22.04+, Debian 11+, RHEL 8+ (recommended)
- **macOS:** 12+ (development only)
- **Windows:** WSL2 or Docker Desktop (development only)

**Required software:**
- **Python:** 3.11+ (for non-Docker deployments)
- **Docker:** 20.10+ (for Docker deployments)
- **Network:** Outbound HTTPS to Discord API, TCP to Factorio RCON ports

### Timeline Expectations

- **First-time setup:** 30-60 minutes
- **Repeat deployment:** 10-15 minutes
- **Adding new server:** 5 minutes
- **Troubleshooting issues:** 15-45 minutes

---

### Required Information

Before deploying, gather:

- ✅ Discord **bot token** (`.secrets/DISCORD_BOT_TOKEN.txt`)
- ✅ Discord **channel IDs** for each server (enable Developer Mode, right-click channel, Copy ID)
- ✅ Factorio **log file paths** for each server
- ✅ **RCON passwords** for each server (if using RCON/stats)
- ✅ **Server IPs/hostnames** for each Factorio instance
- ✅ Network access from ISR to all Factorio RCON ports

---

## Preparation

### Step 1: Clone Repository

```bash
# Production server
cd /opt
sudo git clone https://github.com/stephenclau/factorio-isr.git
cd factorio-isr

# Or download specific release
wget https://github.com/stephenclau/factorio-isr/archive/v2.1.0.tar.gz
tar -xzf v2.1.0.tar.gz
cd factorio-isr-2.1.0
```

---

### Step 2: Create Secrets

```bash
# Create secrets directory
mkdir -p .secrets

# Add Discord bot token
echo "your-discord-bot-token" > .secrets/DISCORD_BOT_TOKEN.txt

# Add RCON passwords per server
echo "prod-password-123" > .secrets/RCON_PASSWORD_PROD
echo "test-password-456" > .secrets/RCON_PASSWORD_TEST

# Secure secrets
chmod 700 .secrets
chmod 600 .secrets/*

# Verify secrets are NOT in git
grep ".secrets" .gitignore || echo ".secrets/" >> .gitignore
```

---

### Step 3: Configure Multi-Server Setup

**Create `config/servers.yml`** (mandatory):

```yaml
servers:
  production:
    name: Production Server
    log_path: /factorio/production/console.log
    rcon_host: factorio-prod.internal
    rcon_port: 27015
    rcon_password: "${RCON_PASSWORD_PROD}"
    event_channel_id: 111111111111111111
    stats_interval: 300

  testing:
    name: Testing Server
    log_path: /factorio/testing/console.log
    rcon_host: factorio-test.internal
    rcon_port: 27015
    rcon_password: "${RCON_PASSWORD_TEST}"
    event_channel_id: 222222222222222222
    stats_interval: 600
```

**Note:** Single-server environment variables (`RCON_ENABLED`, `RCON_HOST`, etc.) are **deprecated**. Use `servers.yml` for all deployments.

---

### Step 4: Configure Environment (Optional)

Create `.env` for non-Docker deployments:

```bash
# Logging
LOG_LEVEL=info
LOG_FORMAT=json

# Health Check
HEALTH_CHECK_HOST=0.0.0.0
HEALTH_CHECK_PORT=8080
```

**What's NOT needed in .env:**
- ❌ `DISCORD_BOT_TOKEN` (use `.secrets/DISCORD_BOT_TOKEN.txt`)
- ❌ `RCON_*` variables (use `servers.yml` per-server)
- ❌ `DISCORD_EVENT_CHANNEL_ID` (use `servers.yml` per-server)

---

### Step 5: Verify Patterns

```bash
# Verify patterns directory
ls -la patterns/

# Should contain:
# - vanilla.yml (included)
# - custom patterns (add as needed)

# Test YAML syntax
python -c "import yaml; yaml.safe_load(open('patterns/vanilla.yml'))"
```

---

### Step 6: Security Checklist

```bash
# Verify secrets not in git
grep -r "discord.com/api" .git/ || echo "✅ No Discord URLs in git"
grep -r "DISCORD_BOT_TOKEN" .git/ || echo "✅ No bot tokens in git"

# Check .gitignore
grep ".secrets" .gitignore || echo ".secrets/" >> .gitignore
grep ".env" .gitignore || echo ".env" >> .gitignore

# Verify file permissions
ls -la .secrets/
# Expected: drwx------ (700) for directory
# Expected: -rw------- (600) for files

ls -la config/servers.yml
# Expected: -rw-r--r-- (644) or -rw------- (600)
```

---

## Docker Deployment

### Method 1: Docker Compose (Recommended)

#### Multi-Server Docker Compose Configuration

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  factorio-isr:
    image: slautomaton/factorio-isr:latest
    # Or build locally:
    # build: .
    container_name: factorio-isr
    restart: unless-stopped

    environment:
      - LOG_LEVEL=info
      - LOG_FORMAT=json
      - HEALTH_CHECK_HOST=0.0.0.0
      - HEALTH_CHECK_PORT=8080

    secrets:
      - DISCORD_BOT_TOKEN
      - RCON_PASSWORD_PROD
      - RCON_PASSWORD_TEST

    volumes:
      # Factorio log directories (read-only)
      - /factorio/production/logs:/factorio/production:ro
      - /factorio/testing/logs:/factorio/testing:ro
      
      # Configuration files (read-only)
      - ./config:/app/config:ro
      - ./patterns:/app/patterns:ro
      
      # Application logs (read-write)
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

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s

secrets:
  DISCORD_BOT_TOKEN:
    file: .secrets/DISCORD_BOT_TOKEN.txt
  RCON_PASSWORD_PROD:
    file: .secrets/RCON_PASSWORD_PROD
  RCON_PASSWORD_TEST:
    file: .secrets/RCON_PASSWORD_TEST

networks:
  factorio:
    driver: bridge
```

#### Deploy

```bash
# Build image (if building locally)
docker-compose build

# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

**Expected startup time:** 10-30 seconds

#### Verify Deployment

```bash
# Check health endpoint
curl http://localhost:8080/health

# Expected response:
{
  "status": "healthy",
  "uptime_seconds": 60,
  "version": "2.1.0",
  "servers": {
    "production": "connected",
    "testing": "connected"
  }
}

# View logs
docker-compose logs --tail=50 factorio-isr

# Check container is running
docker ps | grep factorio-isr
```

---

### Method 2: Docker Run (Single Command)

Without docker-compose:

```bash
# Build image
docker build -t factorio-isr:latest .

# Run container
docker run -d \
  --name factorio-isr \
  --restart unless-stopped \
  -e LOG_LEVEL=info \
  -e LOG_FORMAT=json \
  -v /factorio/production/logs:/factorio/production:ro \
  -v /factorio/testing/logs:/factorio/testing:ro \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/patterns:/app/patterns:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.secrets/DISCORD_BOT_TOKEN.txt:/run/secrets/DISCORD_BOT_TOKEN:ro \
  -v $(pwd)/.secrets/RCON_PASSWORD_PROD:/run/secrets/RCON_PASSWORD_PROD:ro \
  -v $(pwd)/.secrets/RCON_PASSWORD_TEST:/run/secrets/RCON_PASSWORD_TEST:ro \
  -p 8080:8080 \
  factorio-isr:latest

# View logs
docker logs -f factorio-isr
```

---

## Systemd Deployment

For deployments without Docker, use systemd with a Python virtual environment.

### Requirements

- Python 3.11+ installed
- Virtual environment created: `python -m venv venv`
- Dependencies installed: `pip install -r requirements.txt`
- Service runs as non-root user

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

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/factorio-isr/logs

[Install]
WantedBy=multi-user.target
```

**Note:** For production hardening guidance (AppArmor, SELinux, resource limits), contact [licensing@laudiversified.com](mailto:licensing@laudiversified.com) for commercial support.

### Install and Start Service

```bash
# Copy service file
sudo cp factorio-isr.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable factorio-isr

# Start service
sudo systemctl start factorio-isr

# Check status
sudo systemctl status factorio-isr

# View logs
sudo journalctl -u factorio-isr -f
```

**Expected startup time:** 5-15 seconds

---

## Monitoring

### Health Check

```bash
curl http://localhost:8080/health
```

**Expected response:**

```json
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "version": "2.1.0",
  "servers": {
    "production": "connected",
    "testing": "log_only"
  }
}
```

**Server status values:**
- `"connected"` - RCON active and responding
- `"log_only"` - No RCON configured (log tailing only)
- `"error"` - RCON connection failed

### Logs

**Docker:**
```bash
# Live logs
docker-compose logs -f factorio-isr

# Last 100 lines
docker-compose logs --tail=100 factorio-isr

# Search for errors
docker-compose logs factorio-isr | grep -i error
```

**Systemd:**
```bash
# Live logs
sudo journalctl -u factorio-isr -f

# Last 100 lines
sudo journalctl -u factorio-isr -n 100

# Search for errors
sudo journalctl -u factorio-isr | grep -i error
```

### Resource Monitoring

```bash
# Docker resource usage
docker stats factorio-isr

# Expected usage:
# - 100-200MB RAM baseline
# - +5-10MB per server
# - <5% CPU (idle)
# - <10% CPU (stats collection)
```

---

## Maintenance

### Updating the Application

**Docker Compose:**
```bash
# Pull latest changes
cd /opt/factorio-isr
git pull origin main

# Rebuild and restart
docker-compose build
docker-compose up -d

# Verify
docker-compose logs --tail=50 factorio-isr
curl http://localhost:8080/health
```

**Systemd:**
```bash
# Pull latest changes
cd /opt/factorio-isr
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart factorio-isr

# Verify
sudo systemctl status factorio-isr
curl http://localhost:8080/health
```

**Downtime:** 10-30 seconds during restart

### Rotating Logs

**Docker (automatic with json-file driver):**
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"  # Max file size
    max-file: "3"    # Keep 3 files
```

**Systemd (use logrotate):**
```bash
# /etc/logrotate.d/factorio-isr
/opt/factorio-isr/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### Backups

**What to back up:**
```bash
# Configuration
tar -czf factorio-isr-config-$(date +%Y%m%d).tar.gz \
  config/ patterns/ .env

# Secrets (encrypted backup recommended)
tar -czf factorio-isr-secrets-$(date +%Y%m%d).tar.gz .secrets/
# Then encrypt:
# gpg -c factorio-isr-secrets-*.tar.gz
```

**What NOT to back up:**
- `logs/` (ephemeral)
- `venv/` (rebuilt from requirements.txt)
- `.git/` (clone from GitHub)

**Backup frequency:** Weekly or after configuration changes

---

## Troubleshooting

### Bot Not Online in Discord

**What's actually happening:** Bot token invalid, expired, or bot lacks intents.

**Solutions:**
1. Check `DISCORD_BOT_TOKEN` is valid (`.secrets/DISCORD_BOT_TOKEN.txt`)
2. Verify bot is invited to the server with correct scopes (`bot`, `applications.commands`)
3. Enable required intents in Discord Developer Portal

**Timeline:** 5-10 minutes to diagnose and fix

---

### No Events in Discord

**What's actually happening:** Log files not readable, or channel permissions missing.

**Solutions:**
1. Verify `log_path` in `servers.yml` is correct and readable
2. Confirm Factorio is writing to `console.log`
3. Check bot has "Send Messages" and "Embed Links" permissions in channel
4. Run with `LOG_LEVEL=debug` to see parsing activity

**Timeline:** 10-15 minutes to diagnose

---

### RCON Stats Not Updating

**What's actually happening:** RCON connection failed, or stats disabled.

**Solutions:**
1. Verify RCON fields in `servers.yml`
2. Check RCON host/port/password
3. Confirm RCON is enabled in Factorio `server-settings.json`
4. Test RCON manually: `telnet factorio-host 27015`

**Timeline:** 10-20 minutes for RCON troubleshooting

---

### Health Check Failing

**What's actually happening:** Application crashed, or port 8080 in use.

**Solutions:**
1. Check logs for errors: `docker-compose logs factorio-isr | tail -50`
2. Ensure `HEALTH_CHECK_PORT` not in use: `netstat -tlnp | grep 8080`
3. Verify `servers.yml` syntax: `python -c "import yaml; yaml.safe_load(open('config/servers.yml'))"`

**Timeline:** 5-10 minutes

---

### High CPU/Memory Usage

**What's actually happening:** Too many servers with low intervals, or debug logging enabled.

**Solutions:**
1. Increase `stats_interval` per server (600+ for 10+ servers)
2. Disable debug logging: `LOG_LEVEL=info`
3. Disable stats for unused servers: `enable_stats_collector: false`
4. Monitor resource usage: `docker stats factorio-isr`

**Timeline:** 5 minutes to adjust config, 10 minutes to verify improvement

---

## Next Steps

- ✅ [TOPOLOGY.md](TOPOLOGY.md) – Deployment architecture patterns
- ✅ [Configuration Guide](configuration.md) – All environment variables
- ✅ [RCON Setup](RCON_SETUP.md) – Configure real-time stats
- ✅ [Troubleshooting Guide](TROUBLESHOOTING.md) – Fix common issues

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](../LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)