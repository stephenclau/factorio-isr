---
layout: default
title: Troubleshooting
---

# 🔧 Troubleshooting Guide

Common issues and solutions for Factorio ISR with bot integration, multi-server support, and advanced features.

## Table of Contents

- [Startup Issues](#startup-issues)
- [Discord Bot Issues](#discord-bot-issues)
- [RCON Problems](#rcon-problems)
- [Multi-Server Issues](#multi-server-issues)
- [Slash Commands](#slash-commands)
- [Mentions Feature](#mentions-feature)
- [Log Tailing Issues](#log-tailing-issues)
- [Pattern Matching](#pattern-matching)
- [Docker Issues](#docker-issues)
- [Performance Issues](#performance-issues)

---

## Startup Issues

### Application Won't Start

**Error:** `ModuleNotFoundError: No module named 'X'`

**Solution:**

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "discord.py|structlog|pyyaml|dotenv"
```

---

**Error:** `ValueError: DISCORD_BOT_TOKEN is required`

**Solution:**

```bash
# Check .env file
cat .env | grep DISCORD_BOT_TOKEN

# Or check secrets
cat .secrets/DISCORD_BOT_TOKEN.txt

# Verify in container
docker exec factorio-isr ls -la /run/secrets/DISCORD_BOT_TOKEN
```

---

**Error:** `ValueError: servers.yml not found or empty`

**Solution:**

```bash
# Verify servers.yml exists
ls -la config/servers.yml

# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config/servers.yml'))"

# Minimal config
cat > config/servers.yml << EOF
servers:
  default:
    log_path: /factorio/console.log
    discord:
      event_channel_id: 123456789012345678
EOF
```

---

### Config Validation Fails

**Error:** `ValueError: Invalid server configuration for 'SERVER_NAME'`

**Solution:**

```bash
# Check servers.yml structure
cat config/servers.yml

# Ensure all required fields present
servers:
  my_server:
    log_path: /factorio/console.log  # Required
    discord:
      event_channel_id: 123...       # Required

# Validate YAML syntax
python -m yaml.tool config/servers.yml
```

---

**Error:** `ValueError: LOG_LEVEL must be one of [...]`

**Solution:**

```bash
# Valid log levels: debug, info, warning, error, critical
# Edit .env
LOG_LEVEL=info
```

---

## Discord Bot Issues

### Bot Not Coming Online

**Symptom:** Bot shows as offline in Discord

**Troubleshooting Steps:**

1. **Verify bot token is valid:**
   - Discord Developer Portal → Bot → Reset Token
   - Update `.secrets/DISCORD_BOT_TOKEN.txt`

2. **Check bot is invited to server:**
   - Required scopes: `bot`, `applications.commands`
   - Required permissions: Send Messages, Embed Links, Use Slash Commands

3. **Verify intents enabled:**
   - Discord Developer Portal → Bot → Privileged Gateway Intents
   - Enable: Server Members Intent, Message Content Intent (if reading chat)

4. **Check application logs for errors:**
   ```bash
   docker-compose logs factorio-isr | head -50
   ```

---

### Messages Not Sending

**Symptom:** Bot online but events not appearing in Discord

**Troubleshooting Steps:**

1. **Verify channel ID is correct:**
   ```bash
   # Enable Developer Mode in Discord
   # Right-click channel → Copy ID
   grep event_channel_id config/servers.yml
   ```

2. **Check bot has permissions in channel:**
   - View Channel
   - Send Messages
   - Embed Links
   - Attach Files (for stats embeds)

3. **Verify per-server channel configuration:**
   ```yaml
   servers:
     my_server:
       discord:
         event_channel_id: 123456789012345678  # Must exist and bot has access
   ```

---

### Slash Commands Not Appearing

**Symptom:** `/stats`, `/players`, etc. not showing in Discord

**Troubleshooting Steps:**

1. **Re-invite bot with correct scopes:**
   - Discord Developer Portal → OAuth2 → URL Generator
   - Select: `bot`, `applications.commands`
   - Bot Permissions: Send Messages, Embed Links, Use Slash Commands

2. **Wait for command sync:**
   - Commands can take up to 1 hour to appear globally

3. **Check guild commands:**
   - Bot registers commands per-guild when it joins
   - Kick and re-invite bot to force re-sync

---

### Slash Commands Fail

**Error:** `/stats` → "This interaction failed"

**Troubleshooting Steps:**

1. **RCON not configured for that server:**
   ```yaml
   servers:
     my_server:
       rcon:  # Must be present
         host: localhost
         port: 27015
         password_file: .secrets/rcon_myserver.txt
   ```

2. **Server name typo:**
   ```bash
   # Server name in command must match servers.yml exactly
   /stats server:my_server  # Case-sensitive!
   ```

3. **Check application logs:**
   ```bash
   docker-compose logs factorio-isr | grep -i error
   ```

---

### `/save` Command Fails

**Error:** "Could not save game for server X"

**Troubleshooting Steps:**

1. **RCON permissions:**
   - Factorio server must allow `/save` command via RCON
   - Check `server-adminlist.json` if admin-only

2. **RCON connection issue:**
   ```bash
   # Test RCON manually
   python -c "
   from rcon.source import Client
   with open('.secrets/rcon_myserver.txt') as f:
       pw = f.read().strip()
   with Client('localhost', 27015, passwd=pw) as c:
       print(c.run('/save'))
   "
   ```

---

## RCON Problems

### RCON Not Connecting

**Symptom:** RCON connection failing

**Troubleshooting Steps:**

1. **Check servers.yml RCON config:**
   ```bash
   grep -A 5 "rcon:" config/servers.yml
   ```

2. **Verify password file exists and is readable:**
   ```bash
   cat .secrets/rcon_myserver.txt
   ls -la .secrets/rcon_myserver.txt
   chmod 600 .secrets/rcon_myserver.txt
   ```

3. **Verify RCON section in servers.yml:**
   ```yaml
   servers:
     my_server:
       rcon:
         host: localhost
         port: 27015
         password_file: .secrets/rcon_myserver.txt
   ```

4. **Check Factorio RCON is enabled:**
   ```bash
   grep rcon-port /path/to/factorio/server-settings.json
   ```

---

### Stats Not Posting

**Symptom:** RCON connected but no stats in Discord

**Troubleshooting Steps:**

1. **Check stats interval is configured:**
   ```bash
   grep stats_interval config/servers.yml
   ```

2. **Verify stats interval is set (default 300 = 5 min):**
   ```yaml
   servers:
     my_server:
       rcon:
         stats_interval: 300
   ```

3. **Ensure bot has permission to post embeds:**
   - Discord → Channel Settings → Permissions → Embed Links

---

## Multi-Server Issues

### Wrong Server's Events Appearing

**Symptom:** Events from server A appearing in server B's channel

**Solution:**

```yaml
# Ensure each server has unique channel ID
servers:
  server_a:
    discord:
      event_channel_id: 111111111111111111  # Server A channel

  server_b:
    discord:
      event_channel_id: 222222222222222222  # Server B channel (different!)
```

---

### Some Servers Not Monitored

**Symptom:** Only some servers posting events

**Troubleshooting Steps:**

```bash
# Verify all log paths in servers.yml exist
for server in $(grep "log_path:" config/servers.yml | awk '{print $2}'); do
    ls -la "$server" || echo "Missing: $server"
done

# Ensure all servers have valid config
python -c "
import yaml
with open('config/servers.yml') as f:
    config = yaml.safe_load(f)
    for name, cfg in config['servers'].items():
        assert 'log_path' in cfg, f'{name}: missing log_path'
        assert 'discord' in cfg, f'{name}: missing discord section'
        print(f'✅ {name}')
"
```

---

## Slash Commands

### `/stats` Not Working

**Error:** "Could not retrieve stats for server X"

**Troubleshooting Steps:**

1. **RCON not configured for that server:**
   ```yaml
   servers:
     my_server:
       rcon:  # Must be present
         host: localhost
         port: 27015
         password_file: .secrets/rcon_myserver.txt
   ```

2. **Server name typo:**
   ```bash
   # Server name in command must match servers.yml exactly
   /stats server:my_server  # Case-sensitive!
   ```

---

### `/players` Shows No Players

**Symptom:** Command runs but says "No players online" when players are present

**Troubleshooting Steps:**

1. Verify RCON is connected
2. Check server permissions
3. Verify RCON connection is active

---

## Mentions Feature

### @mentions Not Working

**Symptom:** `@username` in Factorio chat not pinging Discord user

**Troubleshooting Steps:**

1. **Verify mentions.yml exists:**
   ```bash
   ls -la config/mentions.yml
   ```

2. **Create mentions.yml if missing:**
   ```yaml
   # config/mentions.yml
   mentions:
     alice:
       type: user
       discord_id: 123456789012345678
       aliases:
         - alice
         - Alice
   ```

3. **Verify Discord IDs:**
   - Enable Developer Mode in Discord
   - Right-click user/role → Copy ID
   - Use that ID in mentions.yml

4. **Check bot permissions:**
   - Bot needs "Mention Everyone" permission for role mentions

---

## Log Tailing Issues

### Log File Not Found

**Error:** `waiting_for_log_file` in logs

**Troubleshooting Steps:**

1. **Verify log path in servers.yml:**
   ```bash
   grep log_path config/servers.yml
   ```

2. **Verify files exist:**
   ```bash
   ls -la /path/to/factorio/console.log
   ```

3. **For Docker, verify mount:**
   - docker-compose.yml
   - volumes section should include log directory

4. **Check permissions:**
   ```bash
   chmod 644 /path/to/factorio/console.log
   ```

---

### No Events Detected

**Symptom:** Application running but no Discord messages

**Troubleshooting Steps:**

1. **Verify log file is being written to:**
   ```bash
   tail -f /path/to/factorio/console.log
   ```

2. **Check patterns loaded:**
   ```bash
   ls -la patterns/
   ```

3. **Verify YAML syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('patterns/vanilla.yml'))"
   ```

---

## Pattern Matching

### Pattern Not Matching

**Symptom:** Expected events not appearing in Discord

**Troubleshooting Steps:**

1. **Check pattern syntax:**
   ```yaml
   patterns:
     player_join:
       pattern: '\[JOIN\] (.+)'  # Escaped brackets
       type: join
       emoji: "👋"
   ```

2. **Test regex with real log line:**
   ```bash
   tail -1 /path/to/factorio/console.log
   # Copy line and test pattern
   ```

3. **Check priority:**
   ```yaml
   # Higher priority = checked first
   patterns:
     specific:
       pattern: '\[JOIN\] (Admin|Mod)'
       priority: 100  # Checked before regular

     generic:
       pattern: '\[JOIN\] (.+)'
       priority: 50
   ```

---

## Docker Issues

### Container Exits Immediately

**Troubleshooting Steps:**

```bash
# Check exit code
docker-compose ps

# View logs
docker-compose logs factorio-isr | tail -50

# Check config
docker-compose config
```

**Solutions:**

```bash
# Look for startup errors
docker-compose logs factorio-isr | head -50

# Test interactively
docker-compose run --rm factorio-isr /bin/bash
```

---

### Volume Mount Issues

**Error:** `stat /factorio/console.log: no such file or directory`

**Solutions:**

```bash
# Verify host path exists
ls -la /path/to/factorio/console.log

# Check docker-compose.yml
volumes:
  - /path/to/factorio/logs:/factorio:ro  # ✅ Directory mount
```

---

## Performance Issues

### High CPU Usage

**Troubleshooting Steps:**

```bash
# Check CPU
docker stats factorio-isr

# Check application logs
docker-compose logs factorio-isr | head -50
```

**Solutions:**

```bash
# Reduce log level
LOG_LEVEL=info  # Not debug
```

---

### High Memory Usage

**Troubleshooting Steps:**

```bash
# Check memory
docker stats factorio-isr
```

**Solutions:**

```bash
# Set memory limit in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 512M

# Restart if needed
docker-compose restart factorio-isr
```

---

## Getting Help

### Collect Diagnostic Information

```bash
# System info
uname -a
docker --version
python --version

# Application logs
docker-compose logs --tail=200 factorio-isr

# Config (redact secrets)
cat config/servers.yml
ls -la config/
ls -la patterns/

# Health check
curl http://localhost:8080/health
```

---

### Enable Debug Logging

```bash
# .env
LOG_LEVEL=debug
LOG_FORMAT=console

# Restart and watch
docker-compose restart factorio-isr
docker-compose logs -f factorio-isr
```

---

### Report Issues

When reporting issues, please include:

1. **Error message** - Full text of error
2. **Steps to reproduce** - How to trigger the issue
3. **Configuration** - `servers.yml` and patterns (redact secrets)
4. **Environment** - OS, Docker version, Python version
5. **Logs** - Last 50-100 lines from application

---

## Next Steps

- [RCON Setup](RCON_SETUP.md) - Configure RCON per server
- [Configuration](configuration.md) - All environment variables
- [Examples](EXAMPLES.md) - Common configurations
- [Patterns](PATTERNS.md) - Pattern syntax

---

**Still stuck?** Open an issue on [GitHub](https://github.com/stephenclau/factorio-isr/issues) with diagnostic info or contact [licensing@laudiversified.com](mailto:licensing@laudiversified.com) for support.

---

> **📄 Licensing Information**
> 
> This project is open licensed:
> - **[MIT](../LICENSE)** – Open source use (free)