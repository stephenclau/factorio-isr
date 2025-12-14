# Installation Guide

Complete step-by-step guide for deploying Factorio ISR using Docker Compose.

---

## Prerequisites

- **Docker & Docker Compose** installed on your host
- **A running Factorio server** with console logging enabled
- **Discord bot token** (from Discord Developer Portal)
- **RCON enabled** on your Factorio server (see [RCON_SETUP.md](RCON_SETUP.md))

**Time Estimate:** 15–30 minutes  
**Difficulty:** Intermediate (Docker, YAML, Discord setup)

---

## Critical Path: Docker Compose Installation (Recommended)

### Step 1: Create Working Directory on Host

Create a dedicated directory for ISR configuration and change into it:

```bash
mkdir -p ~/factorio-isr
cd ~/factorio-isr
```

This directory will hold all ISR configuration files that will be mounted into the Docker container.

---

### Step 2: Create Subdirectories for Container Mounts

Create the directory structure that Docker will mount:

```bash
mkdir -p config patterns .secrets
```

**Directory purposes:**
- `config/` → Contains `servers.yml` and `mentions.yml`
- `patterns/` → Contains event pattern YAML files (`vanilla.yml`, custom patterns)
- `.secrets/` → Contains sensitive values (Discord token, RCON passwords)

---

### Step 3: Pre-Populate Configuration Files

#### Create `config/servers.yml`

This file defines your Factorio servers and Discord integration:

```bash
cat > config/servers.yml << 'EOF'
servers:
  default:
    name: "My Factorio Server"
    # Path to console.log inside the ISR container (after mount)
    log_path: /factorio/console.log
    
    # RCON connection details
    rcon_host: localhost  # or your Factorio server hostname
    rcon_port: 27015
    rcon_password: ${RCON_PASSWORD}  # Uses env variable
    
    # Discord channels (get IDs from Discord Developer Mode)
    alert_channel_id: 1234567890123456789  # For UPS alerts
    status_channel_id: 1234567890123456789  # For status updates
    
    # Metrics collection
    enable_stats_collector: true
    enable_ups_stat: true
    enable_evolution_stat: true
    collect_interval_seconds: 30
    
    # Alert thresholds
    enable_alerts: true
    ups_warning_threshold: 30.0
    ups_recovery_threshold: 45.0
    alert_cooldown_seconds: 300
EOF
```

**Important:** Update these values:
- `rcon_host` → Your Factorio server hostname (use `host.docker.internal` if Factorio runs on same host)
- `rcon_port` → Your RCON port (default 27015)
- `alert_channel_id` → Discord channel ID for alerts
- `status_channel_id` → Discord channel ID for status messages

**Multi-Server Setup:**
```yaml
servers:
  prod:
    name: "Production"
    log_path: /factorio/prod/console.log
    rcon_host: prod-server
    rcon_port: 27015
    rcon_password: ${RCON_PROD_PASSWORD}
    alert_channel_id: 1111111111111111111
    
  staging:
    name: "Staging"
    log_path: /factorio/staging/console.log
    rcon_host: staging-server
    rcon_port: 27016
    rcon_password: ${RCON_STAGING_PASSWORD}
    alert_channel_id: 2222222222222222222
```

#### Create `config/mentions.yml` (Optional)

For Discord @mention support from in-game chat:

```bash
cat > config/mentions.yml << 'EOF'
mentions:
  enabled: true
  groups:
    admin:
      discord_role_id: 1234567890123456789
      keywords: ["@admin", "@admins"]
    
    moderator:
      discord_role_id: 9876543210987654321
      keywords: ["@mod", "@mods"]
  
  users:
    JohnDoe:
      discord_user_id: 1111111111111111111
      keywords: ["@john", "@johndoe"]
EOF
```

#### Create Pattern Files

Copy vanilla patterns (baseline event types):

```bash
curl -o patterns/vanilla.yml \
  https://raw.githubusercontent.com/stephenclau/factorio-isr/main/patterns/vanilla.yml
```

**Or manually create vanilla patterns:**

```bash
cat > patterns/vanilla.yml << 'EOF'
patterns:
  - name: player_join
    regex: '(?P<player>\w+) joined the game'
    priority: 10
    enabled: true
    
  - name: player_leave
    regex: '(?P<player>\w+) left the game'
    priority: 10
    enabled: true
    
  - name: player_chat
    regex: '(?P<player>\w+): (?P<message>.+)'
    priority: 5
    enabled: true
    
  - name: player_death
    regex: '(?P<player>\w+) was killed'
    priority: 8
    enabled: true
EOF
```

**Create custom patterns (optional):**

```bash
cat > patterns/custom.yml << 'EOF'
patterns:
  - name: my_custom_event
    regex: '\[CUSTOM\] (?P<message>.+)'
    priority: 5
    enabled: true
EOF
```

---

### Step 4: Create Secrets

Create Discord bot token secret:

```bash
echo "your_discord_bot_token_here" > .secrets/DISCORD_BOT_TOKEN.txt
```

**Optional:** Create RCON password secret (if not using environment variable in `servers.yml`):

```bash
echo "your_rcon_password" > .secrets/RCON_PASSWORD.txt
```

**Security:** Ensure `.secrets/` is not committed to version control:

```bash
echo ".secrets/" >> .gitignore
```

---

### Step 5: Create docker-compose.yml

Create Docker Compose file with proper volume mounts:

```bash
cat > docker-compose.yml << 'EOF'
version: "3.8"

services:
  factorio-isr:
    image: slautomaton/factorio-isr:latest
    container_name: factorio-isr
    restart: unless-stopped
    
    # Volume mounts (read-only for security)
    volumes:
      # ISR configuration
      - ./config:/app/config:ro
      - ./patterns:/app/patterns:ro
      
      # Factorio logs (adjust path to your Factorio installation)
      - /path/to/factorio:/factorio:ro
      
      # Optional: mentions config
      # - ./config/mentions.yml:/app/config/mentions.yml:ro
    
    # Secrets (Docker secrets pattern)
    secrets:
      - discord_bot_token
    
    # Environment variables
    environment:
      # Discord
      - DISCORD_BOT_TOKEN_FILE=/run/secrets/discord_bot_token
      
      # RCON password (if using env instead of secrets)
      - RCON_PASSWORD=your_rcon_password_here
      
      # Logging
      - LOG_LEVEL=info
      - LOG_FORMAT=json
      
      # Health check
      - HEALTH_CHECK_HOST=0.0.0.0
      - HEALTH_CHECK_PORT=8080
    
    # Expose health check port
    ports:
      - "8080:8080"
    
    # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

# Docker secrets definition
secrets:
  discord_bot_token:
    file: ./.secrets/DISCORD_BOT_TOKEN.txt
EOF
```

**Critical:** Update this line with your actual Factorio path:
```yaml
- /path/to/factorio:/factorio:ro
```

**Example paths:**
- Linux: `/opt/factorio:/factorio:ro`
- Docker volume: `factorio-data:/factorio:ro` (if Factorio also runs in Docker)
- NFS mount: `/mnt/factorio-nfs:/factorio:ro`

**Multi-Server Example:**
```yaml
volumes:
  - ./config:/app/config:ro
  - ./patterns:/app/patterns:ro
  - /data/factorio/prod:/factorio/prod:ro
  - /data/factorio/staging:/factorio/staging:ro
```

---

### Step 6: Launch ISR

Start the ISR container:

```bash
docker compose up -d
```

**Verify startup:**

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f factorio-isr

# Check health
curl http://localhost:8080/health
```

**Expected health response:**
```json
{
  "status": "healthy",
  "service": "factorio-isr"
}
```

---

### Step 7: Verify Discord Integration

1. **Check bot online status** in Discord
2. **Trigger an event** (join your Factorio server)
3. **Verify Discord message** appears in configured channel
4. **Test slash commands:**
   ```
   /factorio status
   /factorio players
   ```

---

## Alternative: Docker CLI Installation (Advanced)

For users who prefer raw Docker commands instead of Docker Compose:

```bash
# Create secrets
mkdir -p .secrets
echo "your_discord_bot_token" > .secrets/DISCORD_BOT_TOKEN.txt

# Run ISR container
docker run -d \
  --name factorio-isr \
  --restart unless-stopped \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/patterns:/app/patterns:ro \
  -v /path/to/factorio:/factorio:ro \
  -v $(pwd)/.secrets/DISCORD_BOT_TOKEN.txt:/run/secrets/discord_bot_token:ro \
  -e DISCORD_BOT_TOKEN_FILE=/run/secrets/discord_bot_token \
  -e RCON_PASSWORD=your_rcon_password \
  -e LOG_LEVEL=info \
  -e LOG_FORMAT=json \
  -p 8080:8080 \
  slautomaton/factorio-isr:latest
```

---

## Local Development Installation

For contributors or users who want to run ISR without Docker:

### Clone Repository

```bash
git clone https://github.com/stephenclau/factorio-isr.git
cd factorio-isr
```

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Create .env File

```bash
cat > .env << 'EOF'
# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token

# RCON
RCON_PASSWORD=your_rcon_password

# Paths
FACTORIO_LOG_PATH=/path/to/factorio/console.log
PATTERNS_DIR=./patterns

# Logging
LOG_LEVEL=debug
LOG_FORMAT=console

# Health check
HEALTH_CHECK_HOST=0.0.0.0
HEALTH_CHECK_PORT=8080
EOF
```

### Run Application

```bash
python -m src.main
```

---

## Troubleshooting

### ISR can't connect to Discord

**Symptom:** Logs show `discord.errors.LoginFailure`

**Fix:**
1. Verify Discord bot token in `.secrets/DISCORD_BOT_TOKEN.txt`
2. Check token has no extra whitespace/newlines
3. Verify bot has proper intents enabled (Discord Developer Portal)

### ISR can't connect to RCON

**Symptom:** Logs show `RCON connection failed`

**Fix:**
1. Verify RCON is enabled in Factorio `server-settings.json`
2. Check `rcon_host` in `servers.yml` (use `host.docker.internal` for same-host Docker)
3. Verify `rcon_port` matches Factorio config
4. Test RCON manually: `telnet <host> <port>`

### Events not appearing in Discord

**Symptom:** Bot online, but no event messages

**Fix:**
1. Check `alert_channel_id` and `status_channel_id` are correct
2. Verify bot has permissions to post in those channels
3. Check pattern files loaded: `docker compose logs | grep "Loaded patterns"`
4. Trigger an event manually (join/leave game)

### Health check failing

**Symptom:** `curl http://localhost:8080/health` fails

**Fix:**
1. Check port 8080 is exposed: `docker compose ps`
2. Verify container is running: `docker compose ps`
3. Check logs for startup errors: `docker compose logs`

### File permission errors

**Symptom:** ISR can't read config/log files

**Fix:**
1. Verify volume mounts are `:ro` (read-only)
2. Check file ownership matches container user (UID 1000 by default)
3. On Linux: `sudo chown -R 1000:1000 config/ patterns/`

---

## Next Steps

- **Configure:** [Configuration Guide](configuration.md) – Advanced options, multi-server
- **Patterns:** [Event Patterns](PATTERNS.md) – Customize event detection
- **Commands:** [RCON Setup](RCON_SETUP.md) – Discord slash commands
- **Deploy:** [Deployment Guide](DEPLOYMENT.md) – Production best practices
- **Scale:** [Topology Guide](TOPOLOGY.md) – Multi-server, Kubernetes

---

## Getting Help

- 🐛 **Issues:** [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/stephenclau/factorio-isr/discussions)
- 📧 **Commercial Support:** [licensing@laudiversified.com](mailto:licensing@laudiversified.com)

---

**Last updated:** December 14, 2025  
**Version:** v0.2.1+
