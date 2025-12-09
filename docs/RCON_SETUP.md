---
layout: default
title: RCON Setup
---

# 📡 RCON Configuration Guide

Complete guide to setting up RCON (Remote Console) integration for real-time server statistics via the multi-server architecture.

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

**Stats are posted every 5 minutes by default per server.**

### Why servers.yml?

Factorio ISR now uses a **centralized multi-server architecture**. Instead of environment variables for individual RCON settings, all server configurations—including RCON—are stored in `config/servers.yml`. This approach:

✅ Manages multiple servers with a single ISR instance  
✅ Keeps all server settings in one file  
✅ Supports per-server RCON passwords and intervals  
✅ Enables per-server Discord channels  
✅ Scales efficiently without multiple containers  

---

## Prerequisites

- Factorio server(s) with RCON enabled
- RCON password(s) configured on each Factorio server
- Network connectivity between Factorio ISR and all Factorio servers
- `rcon` Python package installed
- `config/servers.yml` file configured

---

## Factorio Server Setup

### Method 1: server-settings.json

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

After configuration, restart your Factorio server for changes to take effect.

---

## Multi-Server Configuration

### Single Server Setup

Create `config/servers.yml`:

```yaml
servers:
  los_hermanos:
    log_path: /factorio/logs/console.log
    rcon:
      host: localhost
      port: 27015
      password_file: .secrets/rcon_los_hermanos.txt
      stats_interval: 300
    discord:
      event_channel_id: 123456789012345678
```

### Multiple Servers Setup

Manage several Factorio servers with a single ISR instance:

```yaml
servers:
  production_server:
    log_path: /factorio/production/console.log
    rcon:
      host: factorio-prod.internal
      port: 27015
      password_file: .secrets/rcon_production.txt
      stats_interval: 300
    discord:
      event_channel_id: 111111111111111111

  testing_server:
    log_path: /factorio/testing/console.log
    rcon:
      host: factorio-test.internal
      port: 27015
      password_file: .secrets/rcon_testing.txt
      stats_interval: 600
    discord:
      event_channel_id: 222222222222222222

  space_age_modpack:
    log_path: /factorio/space-age/console.log
    rcon:
      host: 192.168.1.50
      port: 27015
      password_file: .secrets/rcon_space_age.txt
      stats_interval: 300
    discord:
      event_channel_id: 333333333333333333
```

---

## servers.yml Structure

### Complete Reference

```yaml
servers:
  SERVER_NAME:              # Unique identifier for this server
    log_path: STRING        # Path to Factorio console.log
    
    rcon:                   # RCON configuration (optional)
      enabled: BOOLEAN      # Enable RCON (default: true if section exists)
      host: STRING          # Factorio server hostname/IP
      port: INTEGER         # RCON port (default: 27015)
      password_file: STRING # Path to file containing RCON password
      stats_interval: INTEGER # Stats post interval in seconds (default: 300)
    
    discord:                # Discord output settings
      event_channel_id: INTEGER # Channel ID for events from this server
```

### Minimal Configuration

Bare minimum for one server:

```yaml
servers:
  my_server:
    log_path: /factorio/console.log
    rcon:
      host: localhost
      port: 27015
      password_file: .secrets/rcon_password.txt
    discord:
      event_channel_id: 123456789012345678
```

### Advanced Configuration

With custom stats interval and explicit enable flag:

```yaml
servers:
  vanilla:
    log_path: /data/vanilla/console.log
    rcon:
      enabled: true
      host: vanilla.game.local
      port: 27015
      password_file: .secrets/vanilla_rcon.txt
      stats_interval: 600  # Post every 10 minutes
    discord:
      event_channel_id: 123456789012345678

  mods_only:
    log_path: /data/mods/console.log
    rcon:
      enabled: false  # Disable RCON, log-only mode
    discord:
      event_channel_id: 987654321098765432
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
echo "prod-secure-password-123" > .secrets/rcon_production.txt

# Testing server
echo "test-secure-password-456" > .secrets/rcon_testing.txt

# Space Age modpack
echo "space-secure-password-789" > .secrets/rcon_space_age.txt

# Secure all password files
chmod 600 .secrets/rcon_*.txt
```

### Reference in servers.yml

Point to each password file in your configuration:

```yaml
servers:
  production_server:
    rcon:
      password_file: .secrets/rcon_production.txt

  testing_server:
    rcon:
      password_file: .secrets/rcon_testing.txt
```

---

## Testing RCON Connection

### Test from Command Line

```bash
# Install rcon package
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
{"event": "server_initialized", "server": "los_hermanos", ...}
{"event": "rcon_connected", "server": "los_hermanos", "host": "localhost", "port": 27015, ...}
{"event": "stats_collector_started", "server": "los_hermanos", "interval": 300, ...}
```

### Verify Stats Posting

Check your Discord channels - you should see stats like:

```
📊 **Server Status** (los_hermanos)
👥 Players Online: 3
📝 Alice, Bob, Charlie
⏰ Game Time: Day 42, 13:45
📈 UPS: 59.8/60 ✅
🧬 Evolution: 45.2%
```

---

## Discord Stats Format

### With Players Online

```
📊 **Server Status** (production_server)
👥 Players Online: 5
📝 Alice, Bob, Charlie, Dave, Eve
⏰ Game Time: Day 108, 08:30
📈 UPS: 59.8/60 ✅
🧬 Evolution: 45.2%
```

### No Players Online

```
📊 **Server Status** (testing_server)
👥 Players Online: 0
⏰ Game Time: Day 108, 08:35
📈 UPS: 60.0/60 ✅
🧬 Evolution: 0%
```

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
   openssl rand -base64 32 > .secrets/rcon_myserver.txt
   ```

3. **Restrict file permissions**
   ```bash
   chmod 600 .secrets/rcon_*.txt
   chmod 600 config/servers.yml
   ```

4. **Use Docker secrets in production**
   ```yaml
   services:
     factorio-isr:
       secrets:
         - rcon_production_password
         - rcon_testing_password
   
   secrets:
     rcon_production_password:
       file: .secrets/rcon_production.txt
     rcon_testing_password:
       file: .secrets/rcon_testing.txt
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
- **Docker:** Use service names (e.g., `factorio-prod` if using docker-compose)

---

## Troubleshooting

### RCON Not Connecting

**Symptom:** `{"event": "rcon_connection_failed", "server": "production_server", ...}` in logs

**Solutions:**

1. **Verify servers.yml RCON section exists**
   ```bash
   grep -A 5 "rcon:" config/servers.yml
   ```

2. **Check password file is readable**
   ```bash
   cat .secrets/rcon_production.txt
   ls -la .secrets/rcon_*.txt
   ```

3. **Verify Factorio RCON is running**
   ```bash
   telnet factorio-prod.internal 27015
   # Should connect (Ctrl+C to exit)
   ```

4. **Test connection manually**
   ```bash
   python -c "
   from rcon.source import Client
   with open('.secrets/rcon_production.txt') as f:
       password = f.read().strip()
   try:
       with Client('factorio-prod.internal', 27015, passwd=password) as c:
           print('✅ Connected')
   except Exception as e:
       print(f'❌ Error: {e}')
   "
   ```

5. **Check server names match**
   ```bash
   # servers.yml must use the same name for log_path and rcon settings
   grep "servers:" config/servers.yml -A 50
   ```

---

### Connection Refused

**Error:** `ConnectionRefusedError: [Errno 111] Connection refused`

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
   ```

3. **Verify correct host and port in servers.yml**
   ```bash
   grep -A 3 "rcon:" config/servers.yml
   ```

4. **Check firewall**
   ```bash
   sudo ufw status
   sudo iptables -L -n | grep 27015
   ```

---

### Authentication Failed

**Error:** `Authentication failed` or `Invalid password`

**Solutions:**

1. **Verify password file contains correct password**
   ```bash
   cat .secrets/rcon_production.txt
   # Compare with Factorio server-settings.json
   grep rcon-password /path/to/factorio/data/server-settings.json
   ```

2. **Check for extra whitespace or newlines**
   ```bash
   # Show file with hidden characters
   od -c .secrets/rcon_production.txt
   ```

3. **Recreate password file without trailing newline**
   ```bash
   echo -n "your-password" > .secrets/rcon_production.txt
   ```

4. **Verify password_file path in servers.yml**
   ```bash
   grep password_file config/servers.yml
   # Path should be correct and file should exist
   ```

---

### Stats Not Posting

**Symptom:** RCON connected but no stats in Discord

**Solutions:**

1. **Check stats interval is reasonable**
   ```bash
   grep stats_interval config/servers.yml
   # Default is 300 (5 minutes), minimum 60
   ```

2. **Wait for stats interval to elapse**
   ```bash
   # Stats are posted on a schedule, may need to wait
   # Check logs for: stats_posted event
   ```

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
   - Bot must have "Send Messages" permission in the channel
   - Check Discord bot permissions

---

### RCON Library Not Available

**Error:** `RCON_AVAILABLE: False` or `rcon package not installed`

**Solution:**

```bash
pip install rcon

# Verify installation
python -c "import rcon; print('✅ rcon installed')"
```

---

### Wrong Server Name in logs

**Error:** Stats posting to wrong channel, wrong server appearing in events

**Solution:**

Ensure server names in `servers.yml` are used consistently:

```yaml
servers:
  production_server:     # This is the server name
    log_path: /factorio/prod/console.log
    rcon:
      host: prod.example.com
      password_file: .secrets/rcon_production.txt
    discord:
      event_channel_id: 123456789012345678
```

Each server name must be unique and consistent. It appears in:
- Discord stats header: `📊 Server Status (production_server)`
- Log output
- Health checks and monitoring

---

## Advanced Configuration

### Custom Stats Interval Per Server

```yaml
servers:
  busy_server:
    rcon:
      stats_interval: 600  # Post every 10 minutes

  quiet_server:
    rcon:
      stats_interval: 3600  # Post every hour

  dev_server:
    rcon:
      stats_interval: 60  # Post every minute (dev only!)
```

### Disable RCON Per Server

```yaml
servers:
  log_only:
    log_path: /factorio/logs/console.log
    rcon:
      enabled: false  # Fall back to log-only mode
    discord:
      event_channel_id: 123456789012345678
```

---

## Performance Considerations

### Resource Usage

RCON integration per server adds minimal overhead:
- **Memory:** ~5MB per active RCON connection
- **CPU:** <1% per server during stats collection
- **Network:** ~1KB per stats query per server

### Scaling

- ✅ Single server: No issues
- ✅ 2-5 servers: Excellent, ideal use case
- ⚠️ 10+ servers: Monitor resource usage
- ⚠️ 100+ players per server: Consider increasing stats interval

---

## Monitoring RCON Health

### Check All Servers' RCON Status

```bash
# View RCON logs for all servers
docker-compose logs factorio-isr | grep rcon

# Check last stats post per server
docker-compose logs factorio-isr | grep stats_posted | tail -5
```

### Automated Health Check Script

```bash
#!/bin/bash
# Check if stats are being posted for all configured servers

SERVERS=$(grep "^  [a-z_]*:" config/servers.yml | sed 's/://g' | tr -d ' ')

for server in $SERVERS; do
    LAST_STAT=$(docker-compose logs factorio-isr | grep "stats_posted" | grep "$server" | tail -1)
    
    if [ -z "$LAST_STAT" ]; then
        echo "⚠️ [$server] No recent stats - may be down"
    else
        echo "✅ [$server] Last stats posted: $LAST_STAT"
    fi
done
```

---

## Migrating from Old Architecture

If upgrading from single-server RCON env variables to multi-server `servers.yml`:

### Old .env (Deprecated)
```bash
RCON_ENABLED=true
RCON_HOST=localhost
RCON_PORT=27015
STATS_INTERVAL=300
```

### New servers.yml (Current)
```yaml
servers:
  default:
    log_path: /factorio/console.log
    rcon:
      host: localhost
      port: 27015
      password_file: .secrets/rcon_password.txt
      stats_interval: 300
    discord:
      event_channel_id: 123456789012345678
```

**Benefits of migration:**
- Support multiple servers simultaneously
- Per-server RCON configuration
- Per-server Discord channels
- Single ISR instance manages all servers
- Easier to maintain and scale

---

## Next Steps

- ✅ [Pattern Customization](PATTERNS.md) – Custom events and regex
- ✅ [Examples](EXAMPLES.md) – Configuration examples
- ✅ [Configuration Guide](configuration.md) – All environment variables
- ✅ [Deployment Guide](DEPLOYMENT.md) – Production setup

---

## Support

- **Issues:** [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- **Documentation:** [Full Documentation](README.md)


> **📄 Licensing Information**
> 
> This project is dual-licensed:
> - **[AGPL-3.0](LICENSE)** – Open source use (free)
> - **[Commercial License](LICENSE-COMMERCIAL.md)** – Proprietary use
>
> Questions? See our [Licensing Guide](LICENSING.md) or email [licensing@laudiversified.com](mailto:licensing@laudiversified.com)