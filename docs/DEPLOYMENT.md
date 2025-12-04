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

- ✅ Discord webhook URL(s)
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
wget https://github.com/yourusername/factorio-isr/archive/v1.0.0.tar.gz
tar -xzf v1.0.0.tar.gz
cd factorio-isr-1.0.0
```

---

### Step 2: Create Secrets

```bash
# Create secrets directory
mkdir -p .secrets

# Add Discord webhook
echo "https://discord.com/webhooks/YOUR_WEBHOOK" > .secrets/DISCORD_WEBHOOK_URL.txt

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

**Minimum production .env:**

```bash
# Discord
DISCORD_WEBHOOK_URL=  # Will use secret file

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

---

### Step 4: Create Patterns

```bash
# Verify patterns directory
ls -la patterns/

# Should contain:
# - vanilla.yml (included)
# - custom patterns (add as needed)
```

---

### Step 5: Security Checklist

```bash
# Verify secrets not in git
grep -r "discord.com/api/webhooks" .git/ || echo "✅ No webhooks in git"

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

#### Step 1: Create Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY patterns/ ./patterns/

# Create non-root user
RUN useradd -m -u 1000 factorio-isr && \
    chown -R factorio-isr:factorio-isr /app
USER factorio-isr

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "src.main"]
```

---

#### Step 2: Create docker-compose.yml

```yaml
version: '3.8'

services:
  factorio-isr:
    build: .
    container_name: factorio-isr
    restart: unless-stopped

    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - BOT_NAME=Production Factorio Server
      - LOG_LEVEL=info
      - LOG_FORMAT=json
      - HEALTH_CHECK_HOST=0.0.0.0
      - HEALTH_CHECK_PORT=8080
      - RCON_ENABLED=true
      - RCON_HOST=factorio-server
      - RCON_PORT=27015
      - STATS_INTERVAL=300

    secrets:
      - discord_webhook_url
      - rcon_password

    volumes:
      # Mount Factorio logs (read-only)
      - /path/to/factorio/logs:/factorio:ro
      # Mount patterns
      - ./patterns:/app/patterns:ro
      # Application logs
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
  discord_webhook_url:
    file: .secrets/DISCORD_WEBHOOK_URL.txt
  rcon_password:
    file: .secrets/RCON_PASSWORD.txt

networks:
  factorio:
    driver: bridge
```

---

#### Step 3: Deploy

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

---

#### Step 4: Verify

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
  -e BOT_NAME="Production Server" \
  -e LOG_LEVEL=info \
  -e LOG_FORMAT=json \
  -e RCON_ENABLED=true \
  -e RCON_HOST=localhost \
  -e RCON_PORT=27015 \
  -v /path/to/factorio/logs:/factorio:ro \
  -v $(pwd)/.secrets/DISCORD_WEBHOOK_URL.txt:/run/secrets/DISCORD_WEBHOOK_URL:ro \
  -v $(pwd)/.secrets/RCON_PASSWORD.txt:/run/secrets/RCON_PASSWORD:ro \
  -v $(pwd)/patterns:/app/patterns:ro \
  -p 8080:8080 \
  factorio-isr:latest

# View logs
docker logs -f factorio-isr
```

---

## Systemd Deployment

For deployments without Docker:

### Step 1: Install Dependencies

```bash
# Create virtual environment
cd /opt/factorio-isr
python3.11 -m venv venv

# Activate and install
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

---

### Step 2: Create Service File

```bash
sudo nano /etc/systemd/system/factorio-isr.service
```

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

# Set environment
Environment="PATH=/opt/factorio-isr/venv/bin"
EnvironmentFile=/opt/factorio-isr/.env

# Start command
ExecStart=/opt/factorio-isr/venv/bin/python -m src.main

# Restart policy
Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=300

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/factorio-isr/logs

# Resource limits
MemoryLimit=512M
CPUQuota=50%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=factorio-isr

[Install]
WantedBy=multi-user.target
```

---

### Step 3: Create User

```bash
# Create service user
sudo useradd -r -s /bin/false factorio

# Set ownership
sudo chown -R factorio:factorio /opt/factorio-isr

# Verify permissions
ls -la /opt/factorio-isr
```

---

### Step 4: Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable factorio-isr

# Start service
sudo systemctl start factorio-isr

# Check status
sudo systemctl status factorio-isr

# View logs
sudo journalctl -u factorio-isr -f
```

---

## Monitoring

### Health Checks

#### Manual Check

```bash
curl http://localhost:8080/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "uptime": 12345,
  "version": "1.0.0"
}
```

---

#### Automated Monitoring

**Cron:**

```bash
# /etc/cron.d/factorio-isr-health
*/5 * * * * root /usr/local/bin/factorio-isr-health-check.sh
```

**Health Check Script:**

```bash
#!/bin/bash
# /usr/local/bin/factorio-isr-health-check.sh

HEALTH_URL="http://localhost:8080/health"
ALERT_WEBHOOK="https://discord.com/webhooks/ALERT_WEBHOOK"

response=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")

if [ "$response" != "200" ]; then
    echo "❌ Health check failed: HTTP $response"

    # Send alert
    curl -X POST "$ALERT_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{"content":"🚨 Factorio ISR health check failed! HTTP $response"}"

    exit 1
fi

exit 0
```

---

### Log Monitoring

#### Docker Logs

```bash
# Follow logs
docker-compose logs -f factorio-isr

# Last 100 lines
docker-compose logs --tail=100 factorio-isr

# Filter errors
docker-compose logs factorio-isr | grep -i error

# Since timestamp
docker-compose logs --since="2024-12-01T12:00:00" factorio-isr
```

---

#### Systemd Logs

```bash
# Follow logs
sudo journalctl -u factorio-isr -f

# Last 100 lines
sudo journalctl -u factorio-isr -n 100

# Filter errors
sudo journalctl -u factorio-isr | grep -i error

# Since timestamp
sudo journalctl -u factorio-isr --since "2024-12-01 12:00:00"
```

---

### Metrics (Optional)

Add Prometheus metrics for advanced monitoring:

```python
# src/metrics.py (future enhancement)
from prometheus_client import Counter, Gauge, start_http_server

events_processed = Counter('factorio_events_total', 'Total events processed')
discord_messages_sent = Counter('factorio_discord_messages_total', 'Discord messages sent')
players_online = Gauge('factorio_players_online', 'Current players online')

# Start metrics server on port 9090
start_http_server(9090)
```

---

## Maintenance

### Updates

#### Docker Update

```bash
# Pull latest code
cd /opt/factorio-isr
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d

# Verify
docker-compose logs --tail=50 factorio-isr
curl http://localhost:8080/health
```

---

#### Systemd Update

```bash
# Stop service
sudo systemctl stop factorio-isr

# Update code
cd /opt/factorio-isr
git pull

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Restart service
sudo systemctl start factorio-isr

# Verify
sudo systemctl status factorio-isr
```

---

### Backups

#### Backup Script

```bash
#!/bin/bash
# /usr/local/bin/factorio-isr-backup.sh

BACKUP_DIR="/backup/factorio-isr"
DATE=$(date +%Y%m%d-%H%M%S)
SOURCE="/opt/factorio-isr"

mkdir -p "$BACKUP_DIR"

# Backup configuration and patterns
tar -czf "$BACKUP_DIR/factorio-isr-$DATE.tar.gz" \
    -C "$SOURCE" \
    .env \
    .secrets/ \
    patterns/ \
    docker-compose.yml \
    Dockerfile

# Keep last 7 backups
find "$BACKUP_DIR" -name "factorio-isr-*.tar.gz" -mtime +7 -delete

echo "Backup created: $BACKUP_DIR/factorio-isr-$DATE.tar.gz"
```

```bash
# Make executable
sudo chmod +x /usr/local/bin/factorio-isr-backup.sh

# Add to cron (daily at 3 AM)
sudo crontab -e
# Add: 0 3 * * * /usr/local/bin/factorio-isr-backup.sh
```

---

### Log Rotation

#### Docker Log Rotation

Already configured in docker-compose.yml:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

---

#### Systemd Log Rotation

Configure logrotate:

```bash
sudo nano /etc/logrotate.d/factorio-isr
```

```
/opt/factorio-isr/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 factorio factorio
    postrotate
        systemctl reload factorio-isr
    endscript
}
```

---

## Troubleshooting

### Container Won't Start

**Docker:**

```bash
# Check logs
docker-compose logs factorio-isr

# Inspect container
docker inspect factorio-isr

# Check if port is in use
netstat -tlnp | grep 8080

# Verify secrets are mounted
docker exec factorio-isr ls -la /run/secrets/
```

---

### Service Won't Start

**Systemd:**

```bash
# Check status
sudo systemctl status factorio-isr

# View logs
sudo journalctl -u factorio-isr -n 50

# Test manually
cd /opt/factorio-isr
source venv/bin/activate
python -m src.main
```

---

### Health Check Fails

```bash
# Test health endpoint
curl -v http://localhost:8080/health

# Check if application is running
docker ps | grep factorio-isr
# or
sudo systemctl status factorio-isr

# Check logs for errors
docker-compose logs factorio-isr | grep -i error
# or
sudo journalctl -u factorio-isr | grep -i error
```

---

### RCON Connection Issues

```bash
# Test RCON manually
python -c "
from rcon.source import Client
with Client('localhost', 27015, passwd='YOUR_PASSWORD') as c:
    print(c.run('/time'))
"

# Check network connectivity
telnet localhost 27015

# Verify RCON password
cat .secrets/RCON_PASSWORD.txt

# Check Factorio RCON is enabled
grep rcon /path/to/factorio/server-settings.json
```

---

### Discord Messages Not Sending

```bash
# Test webhook
curl -X POST "$(cat .secrets/DISCORD_WEBHOOK_URL.txt)" \
    -H "Content-Type: application/json" \
    -d '{"content":"Test from production"}'

# Check logs for webhook errors
docker-compose logs factorio-isr | grep discord
```

---

### High Memory Usage

```bash
# Check memory usage
docker stats factorio-isr

# Check for memory leaks in logs
docker-compose logs factorio-isr | grep -i memory

# Restart if needed
docker-compose restart factorio-isr
```

---

## Security Hardening

### Firewall Configuration

```bash
# Allow health check port (if needed externally)
sudo ufw allow 8080/tcp

# Or restrict to specific monitoring server
sudo ufw allow from 192.168.1.100 to any port 8080

# Verify rules
sudo ufw status
```

---

### Secret Management

- ✅ Use `.secrets/` directory for local secrets
- ✅ Use Docker secrets for containers
- ✅ Never commit secrets to git
- ✅ Rotate secrets periodically
- ✅ Use strong passwords (32+ characters)

---

### Container Security

- ✅ Run as non-root user
- ✅ Read-only filesystems where possible
- ✅ Limit resources (memory, CPU)
- ✅ Use health checks
- ✅ Keep base image updated

---

## Performance Tuning

### Resource Limits

**Docker:**

```yaml
services:
  factorio-isr:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

**Systemd:**

```ini
[Service]
MemoryLimit=512M
CPUQuota=50%
```

---

### Optimization

- ✅ Use JSON logging in production
- ✅ Set appropriate stats interval
- ✅ Filter low-priority events
- ✅ Monitor resource usage
- ✅ Rotate logs regularly

---

## Production Checklist

Before going live:

- [ ] All tests passing
- [ ] Secrets configured and secured
- [ ] `.env` file configured
- [ ] Patterns loaded and tested
- [ ] Health endpoint responding
- [ ] Test Discord message sent
- [ ] RCON connection verified (if enabled)
- [ ] Monitoring configured
- [ ] Backups configured
- [ ] Log rotation configured
- [ ] Firewall rules applied
- [ ] Documentation updated

---

## Next Steps

- [RCON Setup](RCON_SETUP.md) - Configure statistics
- [Multi-Channel](MULTI_CHANNEL.md) - Route events
- [Patterns](PATTERNS.md) - Custom patterns
- [Examples](EXAMPLES.md) - Common scenarios

---

**Happy deploying! 🚀**
