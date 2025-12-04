# RCON Configuration Guide

This guide covers setting up RCON (Remote Console) integration for real-time server statistics.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Factorio Server Setup](#factorio-server-setup)
- [Factorio ISR Configuration](#factorio-isr-configuration)
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

**Stats are posted every 5 minutes by default.**

---

## Prerequisites

- Factorio server with RCON enabled
- RCON password configured on Factorio server
- Network connectivity between Factorio ISR and Factorio server
- `rcon` Python package installed

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

## Factorio ISR Configuration

### Option 1: Environment Variables

Edit your `.env` file:

```bash
# Enable RCON
RCON_ENABLED=true

# Server connection
RCON_HOST=localhost        # Use localhost if on same machine
RCON_PORT=27015           # Must match Factorio RCON port

# Stats collection interval (seconds)
STATS_INTERVAL=300        # Post stats every 5 minutes
```

### Option 2: Docker Secrets (Recommended for Production)

Store password in `.secrets/RCON_PASSWORD.txt`:

```bash
# Create secrets directory
mkdir -p .secrets

# Add RCON password
echo "your-secure-password-here" > .secrets/RCON_PASSWORD.txt

# Secure the file
chmod 600 .secrets/RCON_PASSWORD.txt
```

Update `.env`:

```bash
RCON_ENABLED=true
RCON_HOST=172.20.48.220   # Your Factorio server IP
RCON_PORT=27015
STATS_INTERVAL=300
```

### Option 3: Docker Compose Secrets

In `docker-compose.yml`:

```yaml
services:
  factorio-isr:
    environment:
      - RCON_ENABLED=true
      - RCON_HOST=factorio-server
      - RCON_PORT=27015
      - STATS_INTERVAL=300
    secrets:
      - rcon_password

secrets:
  rcon_password:
    file: .secrets/RCON_PASSWORD.txt
```

---

## Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RCON_ENABLED` | Yes | `false` | Enable RCON integration |
| `RCON_HOST` | Yes | `localhost` | Factorio server hostname/IP |
| `RCON_PORT` | Yes | `27015` | RCON port (must match server) |
| `RCON_PASSWORD` | Yes | - | RCON password |
| `STATS_INTERVAL` | No | `300` | Stats post interval (seconds) |

---

## Testing RCON Connection

### Test from Command Line

```bash
# Install rcon package
pip install rcon

# Test connection
python -c "
from rcon.source import Client
with Client('localhost', 27015, passwd='your-password') as client:
    response = client.run('/time')
    print(f'✅ RCON Connected! Server time: {response}')
"
```

### Test via Factorio ISR

```bash
# Run with debug logging
LOG_LEVEL=debug python -m src.main
```

Look for these log entries:

```json
{"event": "rcon_connected", "host": "localhost", "port": 27015, ...}
{"event": "stats_collector_started", "interval": 300, ...}
```

### Verify Stats Posting

Check your Discord channel - you should see:

```
📊 **Server Status**
👥 Players Online: 3
📝 Alice, Bob, Charlie
⏰ Game Time: Day 42, 13:45
```

---

## Discord Stats Format

### With Players Online

```
📊 **Server Status**
👥 Players Online: 5
📝 Alice, Bob, Charlie, Dave, Eve
⏰ Game Time: Day 108, 08:30
```

### No Players Online

```
📊 **Server Status**
👥 Players Online: 0
⏰ Game Time: Day 108, 08:35
```

---

## Security Best Practices

### 🔒 Secure Your RCON Password

1. **Never commit passwords to Git**
   ```bash
   echo ".secrets/" >> .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use strong passwords**
   ```bash
   # Generate secure password
   openssl rand -base64 32
   ```

3. **Restrict file permissions**
   ```bash
   chmod 600 .secrets/RCON_PASSWORD.txt
   chmod 600 .env
   ```

4. **Use Docker secrets in production**
   - Don't put passwords in environment variables
   - Use secrets mounting instead

### 🔥 Firewall Configuration

If Factorio and ISR are on different machines:

```bash
# On Factorio server - allow RCON port from ISR IP only
sudo ufw allow from 192.168.1.100 to any port 27015 proto tcp
```

### 🌐 Network Considerations

- **Same machine:** Use `localhost` or `127.0.0.1`
- **Local network:** Use private IP (e.g., `192.168.1.50`)
- **Remote server:** Consider VPN or SSH tunnel for security

---

## Troubleshooting

### RCON Not Connecting

**Symptom:** `{"event": "rcon_disabled", ...}` in logs

**Solutions:**

1. **Check RCON is enabled in config**
   ```bash
   grep RCON_ENABLED .env
   # Should show: RCON_ENABLED=true
   ```

2. **Verify Factorio RCON is running**
   ```bash
   telnet localhost 27015
   # Should connect (Ctrl+C to exit)
   ```

3. **Check password is set**
   ```bash
   ls -la .secrets/RCON_PASSWORD.txt
   cat .secrets/RCON_PASSWORD.txt  # Verify content
   ```

4. **Test connection manually**
   ```bash
   python -c "
   from rcon.source import Client
   try:
       with Client('localhost', 27015, passwd='your-password') as c:
           print('✅ Connected')
   except Exception as e:
       print(f'❌ Error: {e}')
   "
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

3. **Verify correct port**
   ```bash
   grep rcon-port /path/to/factorio/data/server-settings.json
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

1. **Verify password matches Factorio config**
   ```bash
   # Compare both passwords
   cat .secrets/RCON_PASSWORD.txt
   grep rcon-password /path/to/factorio/data/server-settings.json
   ```

2. **Check for extra whitespace**
   ```bash
   # Show hidden characters
   od -c .secrets/RCON_PASSWORD.txt
   ```

3. **Recreate password file**
   ```bash
   echo -n "your-password" > .secrets/RCON_PASSWORD.txt
   ```

---

### Stats Not Posting

**Symptom:** RCON connected but no stats in Discord

**Solutions:**

1. **Check stats collector started**
   ```bash
   # Look for this in logs
   grep "stats_collector_started" logs/*.log
   ```

2. **Verify stats interval**
   ```bash
   grep STATS_INTERVAL .env
   # Default is 300 seconds (5 minutes)
   ```

3. **Check for errors**
   ```bash
   grep -i "stats\|rcon" logs/*.log | grep -i error
   ```

4. **Test Discord webhook**
   ```bash
   curl -X POST "$(cat .secrets/DISCORD_WEBHOOK_URL.txt)" \
     -H "Content-Type: application/json" \
     -d '{"content":"Test stats message"}'
   ```

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

## Advanced Configuration

### Custom Stats Interval

Post stats more or less frequently:

```bash
# Every minute (not recommended - spam)
STATS_INTERVAL=60

# Every 10 minutes
STATS_INTERVAL=600

# Every hour
STATS_INTERVAL=3600
```

### Multiple Factorio Servers

Run separate ISR instances for each server:

```yaml
# docker-compose.yml
services:
  factorio-isr-server1:
    build: .
    environment:
      - RCON_HOST=server1.example.com
      - RCON_PORT=27015
    secrets:
      - rcon_password_server1

  factorio-isr-server2:
    build: .
    environment:
      - RCON_HOST=server2.example.com
      - RCON_PORT=27015
    secrets:
      - rcon_password_server2
```

---

## Performance Considerations

### Resource Usage

RCON integration adds minimal overhead:
- **Memory:** ~5MB additional
- **CPU:** <1% during stats collection
- **Network:** ~1KB per stats query

### Scaling

- ✅ Single server: No issues
- ✅ Multiple servers: Run separate instances
- ⚠️ High player count (100+): Consider increasing interval

---

## Monitoring RCON Health

### Check RCON Status

```bash
# View RCON logs
docker-compose logs factorio-isr | grep rcon

# Check last stats post
docker-compose logs factorio-isr | grep stats_posted | tail -1
```

### Automated Health Check

Add to your monitoring script:

```bash
#!/bin/bash
# Check if stats are being posted

LAST_STAT=$(docker-compose logs factorio-isr | grep stats_posted | tail -1)

if [ -z "$LAST_STAT" ]; then
    echo "⚠️ No stats found - RCON may be down"
    # Send alert
fi
```

---

## Disabling RCON

To disable RCON and fall back to log-only mode:

```bash
# Edit .env
RCON_ENABLED=false

# Restart
docker-compose restart factorio-isr
```

The application will continue monitoring logs without stats collection.

---

## Next Steps

- ✅ [Multi-Channel Configuration](MULTI_CHANNEL.md)
- ✅ [Pattern Customization](PATTERNS.md)
- ✅ [Deployment Guide](DEPLOYMENT.md)

---

## Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/factorio-isr/issues)
- **Discord:** [Join our Discord](https://discord.gg/your-server)
- **Documentation:** [Full Documentation](../README.md)
