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
pip list | grep -E "discord.py|structlog|rcon|pyyaml|dotenv"
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

**Diagnosis:**

```bash
# Check token
cat .secrets/DISCORD_BOT_TOKEN.txt

# Verify bot invited to server
# Discord Developer Portal → Your App → OAuth2 → Bot

# Check logs
docker-compose logs factorio-isr | grep -i "bot\|discord\|login"
```

**Solutions:**

1. **Verify bot token is valid:**
   - Discord Developer Portal → Bot → Reset Token
   - Update `.secrets/DISCORD_BOT_TOKEN.txt`

2. **Check bot is invited to server:**
   - Required scopes: `bot`, `applications.commands`
   - Required permissions: Send Messages, Embed Links, Use Slash Commands

3. **Verify intents enabled:**
   - Discord Developer Portal → Bot → Privileged Gateway Intents
   - Enable: Server Members Intent, Message Content Intent (if reading chat)

4. **Check for startup errors:**
   ```bash
   docker-compose logs factorio-isr | grep -i error
   ```

---

### Messages Not Sending

**Symptom:** Bot online but events not appearing in Discord

**Diagnosis:**

```bash
# Check channel ID
grep event_channel_id config/servers.yml

# Check bot permissions
# Discord → Channel Settings → Permissions → Your Bot

# Check logs for permission errors
docker-compose logs factorio-isr | grep -i "permission\|forbidden"
```

**Solutions:**

1. **Verify channel ID is correct:**
   ```bash
   # Get channel ID: Enable Developer Mode in Discord
   # Right-click channel → Copy ID
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

**Diagnosis:**

```bash
# Check bot invited with applications.commands scope
# Check logs for command sync
docker-compose logs factorio-isr | grep -i "command\|slash"
```

**Solutions:**

1. **Re-invite bot with correct scopes:**
   - Discord Developer Portal → OAuth2 → URL Generator
   - Select: `bot`, `applications.commands`
   - Bot Permissions: Send Messages, Embed Links, Use Slash Commands

2. **Wait for command sync:**
   - Commands can take up to 1 hour to appear globally
   - Check logs for: `synced_slash_commands`

3. **Check guild commands:**
   ```bash
   # Bot registers commands per-guild when it joins
   # Kick and re-invite bot to force re-sync
   ```

---

### Slash Commands Fail

**Error:** `/stats` → "This interaction failed"

**Diagnosis:**

```bash
# Check logs when running command
docker-compose logs factorio-isr -f

# Look for specific error
docker-compose logs factorio-isr | grep -i "stats\|command\|error"
```

**Solutions:**

1. **RCON not configured:**
   ```yaml
   # servers.yml - RCON required for /stats, /players
   servers:
     my_server:
       rcon:
         host: localhost
         port: 27015
         password_file: .secrets/rcon_myserver.txt
   ```

2. **Wrong server name:**
   ```bash
   # Server name in command must match servers.yml
   /stats server:my_server  # Must match "my_server:" in YAML
   ```

3. **Bot missing permissions:**
   - Ensure bot can send messages in the channel where command was used

---

## RCON Problems

### RCON Not Connecting

**Symptom:** `{"event": "rcon_connection_failed", "server": "...", ...}` in logs

**Diagnosis:**

```bash
# Check servers.yml RCON config
grep -A 5 "rcon:" config/servers.yml

# Check password file
cat .secrets/rcon_myserver.txt

# Test RCON manually
python -c "
from rcon.source import Client
with open('.secrets/rcon_myserver.txt') as f:
    pw = f.read().strip()
with Client('localhost', 27015, passwd=pw) as c:
    print(c.run('/time'))
"
```

**Solutions:**

```bash
# Verify RCON section in servers.yml
servers:
  my_server:
    rcon:
      host: localhost
      port: 27015
      password_file: .secrets/rcon_myserver.txt

# Ensure password file exists and readable
ls -la .secrets/rcon_myserver.txt
chmod 600 .secrets/rcon_myserver.txt

# Check Factorio RCON is enabled
grep rcon-port /path/to/factorio/server-settings.json
```

---

### Stats Not Posting

**Symptom:** RCON connected but no stats in Discord

**Diagnosis:**

```bash
# Check stats interval
grep stats_interval config/servers.yml

# Check collector started
docker-compose logs factorio-isr | grep "stats_collector_started"

# Check for errors
docker-compose logs factorio-isr | grep -i "stats" | grep -i error
```

**Solutions:**

```bash
# Verify stats interval is set (default 300 = 5 min)
servers:
  my_server:
    rcon:
      stats_interval: 300

# Wait for interval to elapse
# Check logs for stats_posted event

# Ensure bot has permission to post embeds
# Discord → Channel Settings → Permissions → Embed Links
```

---

### UPS/Evolution Monitoring Not Working

**Symptom:** Stats posted but missing UPS or evolution data

**Diagnosis:**

```bash
# Check RCON commands work
python -c "
from rcon.source import Client
with open('.secrets/rcon_myserver.txt') as f:
    pw = f.read().strip()
with Client('localhost', 27015, passwd=pw) as c:
    print('UPS:', c.run('/measured-command game.speed'))
    print('Evolution:', c.run('/c game.print(game.forces[\"enemy\"].evolution_factor)'))
"
```

**Solutions:**

- UPS monitoring requires RCON access
- Evolution factor requires Lua access via RCON
- Ensure Factorio version supports commands used

---

## Multi-Server Issues

### Wrong Server's Events Appearing

**Symptom:** Events from server A appearing in server B's channel

**Diagnosis:**

```bash
# Check servers.yml channel IDs
grep -A 3 "discord:" config/servers.yml

# Check logs for server name in events
docker-compose logs factorio-isr | grep "event_sent"
```

**Solutions:**

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

**Diagnosis:**

```bash
# Check logs for each server initialization
docker-compose logs factorio-isr | grep "server_initialized"

# Check log files exist
ls -la /path/to/factorio/*/console.log
```

**Solutions:**

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

### Bot Presence Shows Wrong Server Count

**Symptom:** Bot status shows "Watching 1/3 servers" incorrectly

**Diagnosis:**

```bash
# Check RCON status for all servers
docker-compose logs factorio-isr | grep "rcon_connection"

# Look for connection failures
docker-compose logs factorio-isr | grep "rcon_connection_failed"
```

**Solutions:**

- Presence updates based on active RCON connections
- If a server's RCON is down, it won't count as "online"
- Fix RCON issues for missing servers (see RCON section)

---

## Slash Commands

### `/stats` Not Working

**Error:** "Could not retrieve stats for server X"

**Solutions:**

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

3. **RCON connection down:**
   ```bash
   # Check logs
   docker-compose logs factorio-isr | grep "my_server" | grep "rcon"
   ```

---

### `/players` Shows No Players

**Symptom:** Command runs but says "No players online" when players are present

**Solutions:**

- Verify RCON connected and returning player list
- Test manually:
  ```bash
  python -c "
  from rcon.source import Client
  with open('.secrets/rcon_myserver.txt') as f:
      pw = f.read().strip()
  with Client('localhost', 27015, passwd=pw) as c:
      print(c.run('/players'))
  "
  ```

---

### `/save` Command Fails

**Error:** "Could not save game for server X"

**Solutions:**

1. **RCON permissions:**
   - Factorio server must allow `/save` command via RCON
   - Check `server-adminlist.json` if admin-only

2. **RCON connection issue:**
   ```bash
   # Test save manually
   python -c "
   from rcon.source import Client
   with open('.secrets/rcon_myserver.txt') as f:
       pw = f.read().strip()
   with Client('localhost', 27015, passwd=pw) as c:
       print(c.run('/save'))
   "
   ```

---

## Mentions Feature

### @mentions Not Working

**Symptom:** `@username` in Factorio chat not pinging Discord user

**Diagnosis:**

```bash
# Check mentions.yml exists
ls -la config/mentions.yml

# Check format
cat config/mentions.yml

# Check logs for mention parsing
LOG_LEVEL=debug docker-compose up | grep -i mention
```

**Solutions:**

1. **Create mentions.yml:**
   ```yaml
   # config/mentions.yml
   mentions:
     alice:
       type: user
       discord_id: 123456789012345678
       aliases:
         - alice
         - Alice
         - ALICE

     moderators:
       type: role
       discord_id: 987654321098765432
       aliases:
         - mods
         - moderators
   ```

2. **Verify Discord IDs:**
   - Enable Developer Mode in Discord
   - Right-click user/role → Copy ID
   - Use that ID in mentions.yml

3. **Check bot permissions:**
   - Bot needs "Mention Everyone" permission to @role mentions
   - Ensure bot can see the user/role

---

### Role Mentions Not Working

**Error:** `@moderators` shows as plain text, doesn't ping

**Solutions:**

```yaml
# Ensure type: role
mentions:
  moderators:
    type: role  # Not user
    discord_id: 987654321098765432

# Check bot has "Mention Everyone" permission
# Discord → Server Settings → Roles → Your Bot → Mention Everyone
```

---

### Security Monitor Mentions

**Symptom:** Security events not triggering @admin ping

**Diagnosis:**

```bash
# Check secmon.yml exists
ls -la config/secmon.yml

# Check format
cat config/secmon.yml
```

**Solutions:**

```yaml
# config/secmon.yml
security:
  sensitive_commands:
    enabled: true
    mention_group: admins  # Must match mentions.yml entry
    patterns:
      - '/c '
      - '/command'
      - 'script.raise_event'

# config/mentions.yml
mentions:
  admins:  # Matches mention_group above
    type: role
    discord_id: 123456789012345678
```

---

## Log Tailing Issues

### Log File Not Found

**Error:** `waiting_for_log_file` in logs

**Diagnosis:**

```bash
# Check log path in servers.yml
grep log_path config/servers.yml

# Verify files exist
ls -la /path/to/factorio/console.log

# Check Docker mount
docker exec factorio-isr ls -la /factorio/console.log
```

**Solutions:**

```bash
# Fix path in servers.yml
servers:
  my_server:
    log_path: /factorio/console.log  # Correct path

# For Docker, verify mount
# docker-compose.yml
volumes:
  - /host/path/to/factorio/logs:/factorio:ro

# Check permissions
chmod 644 /path/to/factorio/console.log
```

---

### No Events Detected

**Symptom:** Application running but no Discord messages

**Diagnosis:**

```bash
# Check log is being read
docker-compose logs factorio-isr | grep "log_file_opened"

# Verify log has content
tail -f /path/to/factorio/console.log

# Check pattern matching
LOG_LEVEL=debug docker-compose up | grep "event_parsed"
```

**Solutions:**

1. **Verify log file is active:**
   ```bash
   # Test entry
   echo "$(date '+%Y-%m-%d %H:%M:%S') [CHAT] TestUser: Test!" >> /path/to/factorio/console.log
   ```

2. **Check patterns loaded:**
   ```bash
   docker-compose logs factorio-isr | grep "patterns_loaded"
   ls -la patterns/
   ```

3. **Verify YAML syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('patterns/vanilla.yml'))"
   ```

---

### Log Rotation Not Detected

**Symptom:** Old events repeating after log rotation

**Solution:**

Application handles rotation automatically via inode tracking. If issues persist:

```bash
# Restart after rotation
docker-compose restart factorio-isr
```

---

## Pattern Matching

### Pattern Not Matching

**Symptom:** Expected events not appearing in Discord

**Diagnosis:**

```bash
# Enable debug logging
LOG_LEVEL=debug docker-compose up | grep "pattern_matched\|no_match"

# Test regex manually
python -c "
import re
pattern = r'YOUR_PATTERN'
line = 'YOUR_LOG_LINE'
match = re.search(pattern, line)
print(f'Match: {match.groups() if match else None}')
"
```

**Solutions:**

1. **Check pattern syntax:**
   ```yaml
   events:
     player_join:
       pattern: '\[JOIN\] (.+)'  # Escaped brackets
       type: join
       emoji: "👋"
       message: "{player} joined"
   ```

2. **Test with real log line:**
   ```bash
   tail -1 /path/to/factorio/console.log
   # Copy line and test in Python
   ```

3. **Check priority:**
   ```yaml
   # Higher priority = checked first
   events:
     admin_join:
       pattern: '\[JOIN\] (Admin|Mod) .+'
       priority: 100  # Checked before regular join

     regular_join:
       pattern: '\[JOIN\] (.+)'
       priority: 50
   ```

---

### Wrong Pattern Matching

**Symptom:** Generic pattern matching instead of specific

**Solution:**

```yaml
# Use higher priority for specific patterns
events:
  death_by_train:
    pattern: '(.+) was killed by locomotive'
    priority: 90  # Higher

  death_generic:
    pattern: '(.+) was killed'
    priority: 50  # Lower
```

---

## Docker Issues

### Container Exits Immediately

**Diagnosis:**

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
docker-compose logs factorio-isr | grep -i error

# Verify secrets mounted
docker exec factorio-isr ls -la /run/secrets/

# Test interactively
docker-compose run --rm factorio-isr /bin/bash
python -m src.main
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

# Don't mount individual file
# - /path/to/console.log:/factorio:ro  # ❌ File mount
```

---

## Performance Issues

### High CPU Usage

**Diagnosis:**

```bash
# Check CPU
docker stats factorio-isr

# Check log polling
docker-compose logs factorio-isr | grep "poll"
```

**Solutions:**

```bash
# Reduce log level
LOG_LEVEL=info  # Not debug

# Check for log spam
# Filter verbose patterns with priority=1
```

---

### High Memory Usage

**Diagnosis:**

```bash
# Check memory
docker stats factorio-isr

# Look for leaks
docker-compose logs factorio-isr | wc -l
```

**Solutions:**

```bash
# Set memory limit
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 512M

# Restart if needed
docker-compose restart factorio-isr
```

---

### Rate Limiting

**Symptom:** Discord events delayed or "Rate Limited" in logs

**Solutions:**

- Discord bot rate limits: ~50 messages per second per channel
- Use multiple channels if needed
- Filter low-priority events with `priority: 1` in patterns

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

Include:

1. **Error message** - Full text
2. **Logs** - Last 50-100 lines
3. **Configuration** - `servers.yml`, patterns (redact secrets)
4. **Environment** - OS, Docker version, Python version
5. **Steps to reproduce**

---

## Next Steps

- [RCON Setup](RCON_SETUP.md) - Configure RCON per server
- [Configuration](configuration.md) - All environment variables
- [Examples](EXAMPLES.md) - Common configurations
- [Patterns](PATTERNS.md) - Pattern syntax

---

**Still stuck?** Open an issue on [GitHub](https://github.com/stephenclau/factorio-isr/issues) with diagnostic info.
