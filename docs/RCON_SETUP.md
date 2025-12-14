---
layout: default
title: RCON Setup
---

# 📡 RCON Configuration Guide

Complete guide to setting up RCON (Remote Console) integration for real-time server statistics and slash commands via the multi-server architecture.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Factorio Server Setup](#factorio-server-setup)
- [Multi-Server Configuration](#multi-server-configuration)
- [servers.yml Structure](#serversyml-structure)
- [Testing RCON Connection](#testing-rcon-connection)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

RCON integration enables Factorio ISR to:
- Query player count in real-time
- Get list of online players
- Retrieve server time and game state
- Post periodic server statistics to Discord
- Execute server commands (save, seed, research status, etc.)
- Provide 25+ slash commands in Discord

**Default stats interval:** 300 seconds (5 minutes) per server

### Why Multi-Server?

Factorio ISR uses a **centralized multi-server architecture**. Instead of environment variables for individual RCON settings, all server configurations live in `config/servers.yml`. This approach:

✅ Manages multiple servers with a single ISR instance  
✅ Keeps all server settings in one file  
✅ Supports per-server RCON passwords and intervals  
✅ Enables per-server Discord channels  
✅ Scales efficiently without multiple containers  

### Real Talk: Performance

RCON integration per server adds:
- **Memory:** ~5MB per active RCON connection
- **CPU:** <1% per server during stats collection
- **Network:** ~1KB per stats query per server

**Scaling reality:**
- ✅ **1-5 servers:** Ideal use case, no issues
- ⚠️ **10+ servers:** Monitor resource usage, consider increasing stats intervals
- ⚠️ **100+ players per server:** Can impact query response time, test thoroughly

---

## Prerequisites

- Factorio server(s) with RCON enabled
- RCON password(s) configured on each Factorio server
- Network connectivity between Factorio ISR and all Factorio servers
- `rcon` Python package installed (included in `requirements.txt`)
- `config/servers.yml` file configured (**mandatory**)

---

## Factorio Server Setup

### Method 1: server-settings.json (Recommended)

Edit your Factorio `server-settings.json`:

```json
{
  "name": "My Factorio Server",
  "description": "A great server",

  "rcon-port": 27015,
  "rcon-password": "your-secure-password-here"
}
```

### Method 2: config.ini

Alternatively, edit `config/config.ini`:

```ini
[rcon]
port=27015
password=your-secure-password-here
```

### Method 3: Command Line

Start Factorio with RCON arguments:

```bash
./factorio --start-server savefile.zip \
  --rcon-port 27015 \
  --rcon-password "your-secure-password-here"
```

### Restart Factorio Server

After configuration, **restart your Factorio server** for changes to take effect. RCON cannot be enabled on a running server.

---

## Multi-Server Configuration

### Single Server Setup

Create `config/servers.yml`:

```yaml
servers:
  default:
    name: My Factorio Server
    log_path: /factorio/console.log
    rcon_host: localhost
    rcon_port: 27015
    rcon_password: "${RCON_PASSWORD}"  # or hardcode for dev
    event_channel_id: 123456789012345678
    stats_interval: 300
```

### Multiple Servers Setup

Manage several Factorio servers with a single ISR instance:

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

---

## servers.yml Structure

### Complete Reference

```yaml
servers:
  SERVER_TAG:               # Unique identifier for this server
    name: STRING            # Display name (optional, defaults to tag)
    log_path: STRING        # Path to Factorio console.log
    
    # RCON configuration (required for slash commands and stats)
    rcon_host: STRING       # Factorio server hostname/IP
    rcon_port: INTEGER      # RCON port (default: 27015)
    rcon_password: STRING   # RCON password (supports ${ENV_VAR} expansion)
    
    # Discord output settings
    event_channel_id: INTEGER # Channel ID for events from this server
    
    # Stats configuration (optional)
    stats_interval: INTEGER # Stats post interval in seconds (default: 300)
```

### Minimal Configuration

Bare minimum for one server:

```yaml
servers:
  default:
    log_path: /factorio/console.log
    rcon_host: localhost
    rcon_port: 27015
    rcon_password: "password123"
    event_channel_id: 123456789012345678
```

---

## Setting Up RCON Passwords

### Create Secrets Directory

```bash
mkdir -p .secrets
```

### Store Individual Server Passwords

```bash
# Production server
echo "prod-secure-password-123" > .secrets/RCON_PASSWORD_PROD

# Testing server
echo "test-secure-password-456" > .secrets/RCON_PASSWORD_TEST

# Space Age modpack
echo "space-secure-password-789" > .secrets/RCON_PASSWORD_SA

# Secure all password files
chmod 600 .secrets/RCON_PASSWORD_*
```

### Reference in servers.yml

Point to each password via environment variable expansion:

```yaml
servers:
  production:
    rcon_password: "${RCON_PASSWORD_PROD}"

  testing:
    rcon_password: "${RCON_PASSWORD_TEST}"
```

The application will:
1. Check `/run/secrets/RCON_PASSWORD_PROD` (Docker secrets)
2. Check environment variable `$RCON_PASSWORD_PROD`
3. If both fail, use empty string (validation will fail at startup)

---

## Testing RCON Connection

### Test from Command Line

```bash
# Install rcon package (if not already installed)
pip install rcon

# Test connection to specific server
python -c "
from rcon.source import Client

host = 'localhost'
port = 27015
password = 'your-password'

try:
    with Client(host, port, passwd=password) as client:
        response = client.run('/time')
        print(f'✅ RCON Connected! Server time: {response}')
except Exception as e:
    print(f'❌ Connection failed: {e}')
"
```

### Test via Factorio ISR

```bash
# Run with debug logging
LOG_LEVEL=debug python -m src.main
```

Look for these log entries:

```json
{"event": "server_initialized", "server": "default", ...}
{"event": "rcon_connected", "server": "default", "host": "localhost", "port": 27015, ...}
{"event": "stats_collector_started", "server": "default", "interval": 300, ...}
```

### Verify Stats Posting

Check your Discord channels - you should see stats like:

```
📊 **Server Status** (default)
👥 Players Online: 3
📏 Alice, Bob, Charlie
⏰ Game Time: Day 42, 13:45
📈 UPS: 59.8/60 ✅
🧬 Evolution: 45.2%
```

**First stats post:** Within 5 minutes of startup (default interval)

---

## Discord Stats Format

### With Players Online

```
📊 **Server Status** (production)
👥 Players Online: 5
📏 Alice, Bob, Charlie, Dave, Eve
⏰ Game Time: Day 108, 08:30
📈 UPS: 59.8/60 ✅
🧬 Evolution: 45.2%
```

### No Players Online

```
📊 **Server Status** (testing)
👥 Players Online: 0
⏰ Game Time: Day 108, 08:35
📈 UPS: 60.0/60 ✅
🧬 Evolution: 0%
```

---

## Slash Commands Available

Once RCON is configured, these Discord slash commands become available:

| Command | Description | Example |
|---------|-------------|----------|
| `/stats [server]` | Current server stats (UPS, players, time, evolution) | `/stats server:production` |
| `/players [server]` | List online players | `/players` |
| `/time [server]` | Show in-game time | `/time server:testing` |
| `/save [server]` | Trigger server save | `/save` |
| `/seed [server]` | Show map seed | `/seed` |
| `/version [server]` | Show Factorio version | `/version` |
| `/research [server]` | Show current research | `/research` |
| `/evolution [server]` | Show evolution factor | `/evolution` |

**Note:** Bot supports 25+ commands total. This table shows the most commonly used. The `[server]` parameter is optional and defaults to the first configured server.

---

## Security Best Practices

### 🔒 Secure Your RCON Passwords

1. **Never commit passwords to Git**
   ```bash
   echo ".secrets/" >> .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use strong passwords**
   ```bash
   # Generate secure password for each server
   openssl rand -base64 32 > .secrets/RCON_PASSWORD_PROD
   ```

3. **Restrict file permissions**
   ```bash
   chmod 600 .secrets/RCON_PASSWORD_*
   chmod 600 config/servers.yml
   ```

4. **Use Docker secrets in production**
   ```yaml
   services:
     factorio-isr:
       secrets:
         - RCON_PASSWORD_PROD
         - RCON_PASSWORD_TEST
   
   secrets:
     RCON_PASSWORD_PROD:
       file: .secrets/RCON_PASSWORD_PROD
     RCON_PASSWORD_TEST:
       file: .secrets/RCON_PASSWORD_TEST
   ```

### 🔥 Firewall Configuration

If Factorio and ISR are on different machines:

```bash
# On each Factorio server - allow RCON port from ISR IP only
sudo ufw allow from 192.168.1.100 to any port 27015 proto tcp
```

### 🌐 Network Considerations

- **Same machine:** Use `localhost` or `127.0.0.1`
- **Local network:** Use private IP (e.g., `192.168.1.50`)
- **Remote server:** Consider VPN or SSH tunnel for security
- **Docker:** Use service names (e.g., `factorio-prod` if using docker-compose networks)

---

## Troubleshooting

### RCON Not Connecting

**Symptom:** `{"event": "rcon_connection_failed", "server": "production", ...}` in logs

**What's actually happening:** Python RCON client cannot establish TCP connection to Factorio server on port 27015.

**Solutions (try in order):**

1. **Verify servers.yml RCON section exists**
   ```bash
   grep -A 5 "rcon_" config/servers.yml
   ```

2. **Check password file is readable**
   ```bash
   cat .secrets/RCON_PASSWORD_PROD
   ls -la .secrets/RCON_PASSWORD_*
   ```

3. **Verify Factorio RCON is running**
   ```bash
   telnet factorio-prod.internal 27015
   # Should connect (Ctrl+C to exit)
   # If "Connection refused" = Factorio RCON not enabled
   ```

4. **Test connection manually**
   ```bash
   python -c "
   from rcon.source import Client
   with open('.secrets/RCON_PASSWORD_PROD') as f:
       password = f.read().strip()
   try:
       with Client('factorio-prod.internal', 27015, passwd=password) as c:
           print('✅ Connected')
   except Exception as e:
       print(f'❌ Error: {e}')
   "
   ```

**Timeline:** Diagnosis typically takes 5-10 minutes if you follow these steps.

---

### Connection Refused

**Error:** `ConnectionRefusedError: [Errno 111] Connection refused`

**What's actually happening:** The TCP connection to port 27015 is being rejected. Either Factorio isn't running, RCON isn't enabled, or firewall is blocking.

**Solutions:**

1. **Verify Factorio server is running**
   ```bash
   ps aux | grep factorio
   ```

2. **Check RCON port is listening**
   ```bash
   netstat -tlnp | grep 27015
   # or
   ss -tlnp | grep 27015
   # Should show: LISTEN on port 27015
   ```

3. **Verify correct host and port in servers.yml**
   ```bash
   grep -A 3 "rcon_" config/servers.yml
   ```

4. **Check firewall**
   ```bash
   sudo ufw status
   sudo iptables -L -n | grep 27015
   ```

---

### Authentication Failed

**Error:** `Authentication failed` or `Invalid password`

**What's actually happening:** RCON connected successfully, but password is wrong.

**Solutions:**

1. **Verify password file contains correct password**
   ```bash
   cat .secrets/RCON_PASSWORD_PROD
   # Compare with Factorio server-settings.json
   grep rcon-password /path/to/factorio/data/server-settings.json
   ```

2. **Check for extra whitespace or newlines**
   ```bash
   # Show file with hidden characters
   od -c .secrets/RCON_PASSWORD_PROD
   # Should not have trailing \n
   ```

3. **Recreate password file without trailing newline**
   ```bash
   echo -n "your-password" > .secrets/RCON_PASSWORD_PROD
   ```

4. **Verify password_file path in servers.yml**
   ```bash
   grep password config/servers.yml
   # Path should use ${ENV_VAR} or be absolute
   ```

---

### Stats Not Posting

**Symptom:** RCON connected but no stats in Discord

**What's actually happening:** Stats collector is disabled, interval hasn't elapsed, or Discord permissions missing.

**Solutions:**

1. **Check stats interval is configured**
   ```bash
   grep stats_interval config/servers.yml
   # Default: 300 seconds (5 minutes)
   ```

2. **Wait for stats interval to elapse**
   - First stats post happens 5 minutes after startup (default)
   - Check logs for: `{"event": "stats_posted", ...}`

3. **Verify Discord channel is correct**
   ```bash
   grep event_channel_id config/servers.yml
   # ID should be a valid Discord channel the bot has access to
   ```

4. **Check for errors in logs**
   ```bash
   docker-compose logs factorio-isr | grep -i "stats\|rcon\|error"
   ```

5. **Ensure bot has permission to post**
   - Bot must be in the server
   - Bot must have "Send Messages" + "Embed Links" permission in the channel

---

### RCON Library Not Available

**Error:** `RCON_AVAILABLE: False` or `rcon package not installed`

**What's actually happening:** Python `rcon` package is not installed in the environment.

**Solution:**

```bash
pip install rcon

# Verify installation
python -c "import rcon; print('✅ rcon installed')"
```

**For Docker:** This should never happen if using the official image. If it does, rebuild:
```bash
docker-compose build --no-cache
```

---

## Advanced Configuration

### Custom Stats Interval Per Server

```yaml
servers:
  busy_server:
    stats_interval: 600  # Post every 10 minutes

  quiet_server:
    stats_interval: 3600  # Post every hour

  dev_server:
    stats_interval: 60  # Post every minute (dev only!)
```

**Recommendation:** 300 seconds (5 minutes) for most use cases. Lower values increase Discord API usage and can hit rate limits with many servers.

### Disable Stats Per Server

```yaml
servers:
  log_only:
    log_path: /factorio/logs/console.log
    # No rcon_* fields = log-only mode
    event_channel_id: 123456789012345678

  stats_disabled:
    rcon_host: localhost
    rcon_port: 27015
    rcon_password: "password"
    event_channel_id: 987654321098765432
    enable_stats_collector: false  # Explicit disable
```

---

## Monitoring RCON Health

### Check All Servers' RCON Status

```bash
# View RCON logs for all servers
docker-compose logs factorio-isr | grep rcon

# Check last stats post per server
docker-compose logs factorio-isr | grep stats_posted | tail -5
```

### Health Check Endpoint

```bash
curl http://localhost:8080/health
```

**Response includes per-server RCON status:**

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

---

## Next Steps

- ✅ [Pattern Customization](PATTERNS.md) – Custom events and regex
- ✅ [Examples](EXAMPLES.md) – Configuration examples
- ✅ [Configuration Guide](configuration.md) – All environment variables
- ✅ [Deployment Guide](DEPLOYMENT.md) – Production setup

---

## Support

- **Issues:** [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- **Documentation:** [Full Documentation](../README.md)

---

> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](../LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)