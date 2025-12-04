# Troubleshooting Guide

Common issues and solutions for Factorio ISR.

## Table of Contents

- [Startup Issues](#startup-issues)
- [RCON Problems](#rcon-problems)
- [Discord Issues](#discord-issues)
- [Log Tailing Issues](#log-tailing-issues)
- [Pattern Matching](#pattern-matching)
- [Docker Issues](#docker-issues)
- [Performance Issues](#performance-issues)
- [Configuration Issues](#configuration-issues)

---

## Startup Issues

### Application Won't Start

**Error:** `ModuleNotFoundError: No module named 'X'`

**Solution:**

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "aiohttp|structlog|rcon|pyyaml|dotenv"
```

---

**Error:** `ValueError: DISCORD_WEBHOOK_URL is required`

**Solution:**

```bash
# Check .env file
cat .env | grep DISCORD_WEBHOOK_URL

# Or check secrets
cat .secrets/DISCORD_WEBHOOK_URL.txt

# Verify it's set
python -c "
import sys
sys.path.insert(0, 'src')
from config import load_config
config = load_config()
print(f'Webhook: {config.discord_webhook_url[:50]}...')
"
```

---

**Error:** `ValueError: FACTORIO_LOG_PATH is required`

**Solution:**

```bash
# Set in .env
echo "FACTORIO_LOG_PATH=/path/to/factorio/console.log" >> .env

# Verify file exists
ls -la /path/to/factorio/console.log
```

---

### Config Validation Fails

**Error:** `ValueError: RCON_PASSWORD is required when RCON_ENABLED is true`

**Solution:**

```bash
# Option 1: Set RCON password
echo "your-password" > .secrets/RCON_PASSWORD.txt
chmod 600 .secrets/RCON_PASSWORD.txt

# Option 2: Disable RCON
# Edit .env
RCON_ENABLED=false
```

---

**Error:** `ValueError: LOG_LEVEL must be one of [....]`

**Solution:**

```bash
# Valid log levels: debug, info, warning, error, critical
# Edit .env
LOG_LEVEL=info
```

---

## RCON Problems

### RCON Not Connecting

**Symptom:** `{"event": "rcon_disabled", ...}` in logs

**Diagnosis:**

```bash
# 1. Check RCON enabled
grep RCON_ENABLED .env

# 2. Check password set
ls -la .secrets/RCON_PASSWORD.txt
cat .secrets/RCON_PASSWORD.txt

# 3. Check rcon library installed
python -c "import rcon; print('✅ Installed')"
```

**Solutions:**

```bash
# Install rcon library
pip install rcon

# Set RCON password
echo "your-password" > .secrets/RCON_PASSWORD.txt

# Enable RCON
# Edit .env:
RCON_ENABLED=true
RCON_HOST=localhost
RCON_PORT=27015
```

---

### Connection Refused

**Error:** `ConnectionRefusedError: [Errno 111] Connection refused`

**Diagnosis:**

```bash
# Check Factorio server is running
ps aux | grep factorio

# Check RCON port is listening
netstat -tlnp | grep 27015
# or
ss -tlnp | grep 27015

# Test connection
telnet localhost 27015
```

**Solutions:**

1. **Start Factorio server**

2. **Enable RCON in Factorio:**
   ```json
   // server-settings.json
   {
     "rcon-port": 27015,
     "rcon-password": "your-password"
   }
   ```

3. **Check firewall:**
   ```bash
   sudo ufw status
   sudo ufw allow 27015/tcp
   ```

4. **Verify correct host:**
   ```bash
   # Same machine
   RCON_HOST=localhost

   # Different machine
   RCON_HOST=192.168.1.50
   ```

---

### Authentication Failed

**Error:** `Authentication failed` or `Invalid password`

**Diagnosis:**

```bash
# Compare passwords
cat .secrets/RCON_PASSWORD.txt
grep rcon-password /path/to/factorio/server-settings.json
```

**Solutions:**

```bash
# Ensure passwords match exactly
# No extra whitespace
echo -n "your-password" > .secrets/RCON_PASSWORD.txt

# Check for hidden characters
od -c .secrets/RCON_PASSWORD.txt

# Test manually
python -c "
from rcon.source import Client
with Client('localhost', 27015, passwd='your-password') as c:
    print(c.run('/time'))
"
```

---

### Stats Not Posting

**Symptom:** RCON connected but no stats in Discord

**Diagnosis:**

```bash
# Check stats collector started
docker-compose logs factorio-isr | grep stats_collector_started

# Check stats interval
grep STATS_INTERVAL .env

# Check for errors
docker-compose logs factorio-isr | grep -i "stats\|rcon" | grep -i error
```

**Solutions:**

```bash
# Verify stats interval (seconds)
STATS_INTERVAL=300  # 5 minutes

# Test Discord webhook
curl -X POST "$(cat .secrets/DISCORD_WEBHOOK_URL.txt)" \
    -H "Content-Type: application/json" \
    -d '{"content":"Test stats"}'

# Check RCON queries work
python -c "
from rcon.source import Client
with Client('localhost', 27015, passwd='$(cat .secrets/RCON_PASSWORD.txt)') as c:
    print('Players:', c.run('/players'))
    print('Time:', c.run('/time'))
"

# Restart application
docker-compose restart factorio-isr
```

---

## Discord Issues

### Messages Not Sending

**Symptom:** Events logged but not appearing in Discord

**Diagnosis:**

```bash
# Check webhook URL
cat .secrets/DISCORD_WEBHOOK_URL.txt

# Test webhook
curl -X POST "$(cat .secrets/DISCORD_WEBHOOK_URL.txt)" \
    -H "Content-Type: application/json" \
    -d '{"content":"Test message"}'

# Check logs for webhook errors
docker-compose logs factorio-isr | grep -i webhook | grep -i error
```

**Solutions:**

1. **Verify webhook URL is correct:**
   ```bash
   # Should start with: https://discord.com/api/webhooks/
   cat .secrets/DISCORD_WEBHOOK_URL.txt
   ```

2. **Check webhook exists in Discord:**
   - Server Settings → Integrations → Webhooks
   - Verify webhook is not deleted

3. **Test webhook manually:**
   ```bash
   curl -X POST "YOUR_WEBHOOK_URL" \
       -H "Content-Type: application/json" \
       -d '{"content":"Manual test"}'
   ```

4. **Check rate limiting:**
   - Discord limits: 30 requests per 60 seconds per webhook
   - Reduce event frequency if needed

---

### Wrong Channel

**Symptom:** Events appear in wrong Discord channel

**Diagnosis:**

```bash
# Check WEBHOOK_CHANNELS configuration
grep WEBHOOK_CHANNELS .env

# Verify channel names in patterns
grep "channel:" patterns/*.yml
```

**Solutions:**

1. **Check channel name matches:**
   ```bash
   # .env
   WEBHOOK_CHANNELS={"chat":"URL1","events":"URL2"}

   # Pattern must match exactly (case-sensitive)
   discord:
     channel: chat  # ← Must be "chat" not "Chat"
   ```

2. **Verify webhook URLs:**
   ```bash
   # Test each channel
   curl -X POST "CHAT_WEBHOOK_URL" \
       -d '{"content":"Test chat channel"}'

   curl -X POST "EVENTS_WEBHOOK_URL" \
       -d '{"content":"Test events channel"}'
   ```

3. **Check pattern priority:**
   ```yaml
   # Higher priority matches first
   - name: admin_death
     priority: 100
     discord:
       channel: admin

   - name: regular_death
     priority: 50
     discord:
       channel: deaths
   ```

---

### Messages Malformed

**Symptom:** Discord messages look wrong or incomplete

**Diagnosis:**

```bash
# Check logs for formatting errors
docker-compose logs factorio-isr | grep -i discord | grep -i error

# View raw message data
LOG_LEVEL=debug docker-compose up
```

**Solutions:**

1. **Check field substitution:**
   ```yaml
   fields:
     player: 1
     killer: 2
   discord:
     description: "{player} killed by {killer}"  # ✅
     # Not: "{1} killed by {2}"  # ❌
   ```

2. **Verify regex captures:**
   ```python
   import re
   pattern = r'(.+) was killed by (.+)'
   line = 'Player was killed by biter'
   match = re.search(pattern, line)
   print(match.groups())  # Should print: ('Player', 'biter')
   ```

3. **Check emoji encoding:**
   ```yaml
   discord:
     emoji: "💀"  # ✅ Actual emoji
     # Not: ":skull:"  # ❌ Discord shortcode
   ```

---

## Log Tailing Issues

### Log File Not Found

**Error:** `waiting_for_log_file` in logs

**Diagnosis:**

```bash
# Check log path
grep FACTORIO_LOG_PATH .env

# Verify file exists
ls -la /path/to/factorio/console.log

# Check permissions
ls -la /path/to/factorio/
```

**Solutions:**

```bash
# Correct path in .env
FACTORIO_LOG_PATH=/correct/path/to/console.log

# Fix permissions
sudo chmod 644 /path/to/factorio/console.log

# For Docker, verify mount
docker exec factorio-isr ls -la /factorio/console.log
```

---

### No Events Detected

**Symptom:** Application running but no Discord messages

**Diagnosis:**

```bash
# Check if log is being read
docker-compose logs factorio-isr | grep "log_file_opened"

# Verify log has content
tail -f /path/to/factorio/console.log

# Check pattern matching
LOG_LEVEL=debug docker-compose up
```

**Solutions:**

1. **Verify log file is active:**
   ```bash
   # Add test entry
   echo "$(date '+%Y-%m-%d %H:%M:%S') [CHAT] TestUser: Test!" >> /path/to/factorio/console.log
   ```

2. **Check patterns are loaded:**
   ```bash
   docker-compose logs factorio-isr | grep "patterns_loaded"
   ```

3. **Test pattern matching:**
   ```bash
   # View pattern files
   ls -la patterns/

   # Verify YAML syntax
   python -m yaml patterns/vanilla.yml
   ```

---

### Log Rotation Not Detected

**Symptom:** Old events repeating after log rotation

**Diagnosis:**

```bash
# Check inode tracking
docker-compose logs factorio-isr | grep "rotation_detected"

# Verify rotation method
ls -li /path/to/factorio/console.log*
```

**Solutions:**

Application handles rotation automatically. If issues persist:

```bash
# Restart application after rotation
docker-compose restart factorio-isr

# Or use logrotate postrotate script
# /etc/logrotate.d/factorio
postrotate
    docker-compose -f /path/to/docker-compose.yml restart factorio-isr
endscript
```

---

## Pattern Matching

### Pattern Not Matching

**Symptom:** Expected events not appearing in Discord

**Diagnosis:**

```bash
# Enable debug logging
LOG_LEVEL=debug docker-compose up

# Test regex manually
python -c "
import re
pattern = r'YOUR_PATTERN'
test_line = 'YOUR_LOG_LINE'
match = re.search(pattern, test_line)
print(f'Match: {match.groups() if match else None}')
"
```

**Solutions:**

1. **Check regex escaping:**
   ```yaml
   regex: '\[CHAT\]'  # ✅ Escaped brackets
   regex: '[CHAT]'      # ❌ Character class
   ```

2. **Test with actual log lines:**
   ```bash
   # Get real log line
   tail -1 /path/to/factorio/console.log

   # Test pattern
   python -c "
   import re
   pattern = r'YOUR_PATTERN'
   line = 'PASTE_REAL_LOG_LINE'
   print('Match:', re.search(pattern, line))
   "
   ```

3. **Check pattern priority:**
   ```yaml
   # Higher priority patterns match first
   - name: specific_pattern
     priority: 90

   - name: generic_pattern
     priority: 50
   ```

---

### Wrong Pattern Matching

**Symptom:** Wrong pattern matches log line

**Solution:**

```yaml
# Use higher priority for specific patterns
patterns:
  - name: admin_join
    regex: '\[JOIN\] (Admin|Moderator).+'
    priority: 100  # ← Higher priority

  - name: regular_join
    regex: '\[JOIN\] (.+)'
    priority: 50   # ← Lower priority
```

---

### Pattern Syntax Error

**Error:** `yaml.scanner.ScannerError`

**Diagnosis:**

```bash
# Validate YAML syntax
python -m yaml patterns/your-pattern.yml
```

**Solutions:**

1. **Check indentation (2 spaces):**
   ```yaml
   patterns:
     - name: example  # 2 spaces
       regex: 'pattern'  # 4 spaces
       discord:  # 4 spaces
         emoji: "🎮"  # 6 spaces
   ```

2. **Quote strings with special characters:**
   ```yaml
   regex: 'Pattern with "quotes"'  # ✅
   regex: Pattern with "quotes"    # ❌
   ```

3. **Escape backslashes:**
   ```yaml
   regex: '\[CHAT\]'  # ✅
   regex: '\[CHAT\]'    # ❌ (might work but inconsistent)
   ```

---

## Docker Issues

### Container Exits Immediately

**Diagnosis:**

```bash
# Check exit code
docker-compose ps

# View logs
docker-compose logs factorio-isr

# Inspect container
docker inspect factorio-isr
```

**Solutions:**

```bash
# Check for config errors
docker-compose logs factorio-isr | grep -i error

# Test configuration
docker-compose config

# Verify secrets mounted
docker exec factorio-isr ls -la /run/secrets/

# Run interactively for debugging
docker-compose run --rm factorio-isr /bin/bash
```

---

### Port Already in Use

**Error:** `Bind for 0.0.0.0:8080 failed: port is already allocated`

**Solutions:**

```bash
# Find what's using the port
sudo netstat -tlnp | grep 8080
# or
sudo ss -tlnp | grep 8080

# Kill the process or change port
# docker-compose.yml:
ports:
  - "8081:8080"  # Use different external port
```

---

### Volume Mount Issues

**Error:** `stat /factorio/console.log: no such file or directory`

**Solutions:**

```bash
# Verify host path exists
ls -la /path/to/factorio/console.log

# Check docker-compose.yml mount
volumes:
  - /path/to/factorio/logs:/factorio:ro  # ✅ Directory
  # Not: /path/to/console.log:/factorio:ro  # ❌ File

# Verify permissions
ls -la /path/to/factorio/
```

---

## Performance Issues

### High CPU Usage

**Diagnosis:**

```bash
# Check CPU usage
docker stats factorio-isr

# Check for excessive polling
docker-compose logs factorio-isr | grep "poll_interval"
```

**Solutions:**

```bash
# Increase poll interval (default: 0.1 seconds)
# In src/log_tailer.py:
poll_interval=0.5  # Check every 500ms instead

# Reduce log level
LOG_LEVEL=info  # Not debug

# Filter low-priority events
# Use lower priority in patterns
```

---

### High Memory Usage

**Diagnosis:**

```bash
# Check memory usage
docker stats factorio-isr

# Look for memory leaks
docker-compose logs factorio-isr | grep -i memory
```

**Solutions:**

```bash
# Set memory limits
# docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 512M

# Restart periodically if memory leak suspected
# Add to cron:
0 3 * * * docker-compose restart factorio-isr

# Enable log rotation
# Prevent log files from growing too large
```

---

### Slow Discord Posting

**Symptom:** Long delay between event and Discord message

**Diagnosis:**

```bash
# Check for rate limiting
docker-compose logs factorio-isr | grep -i "rate"

# Check network latency
ping discord.com

# Check webhook response times
time curl -X POST "$(cat .secrets/DISCORD_WEBHOOK_URL.txt)" \
    -d '{"content":"Test"}'
```

**Solutions:**

```bash
# Reduce event frequency
# Use pattern priorities to filter noise

# Check rate limiting (30 req/60s per webhook)
# Use multiple webhooks if needed

# Verify network connectivity
traceroute discord.com
```

---

## Configuration Issues

### Environment Variables Not Loaded

**Diagnosis:**

```bash
# Check .env file exists
ls -la .env

# Verify format
cat .env

# Test loading
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('Webhook:', os.getenv('DISCORD_WEBHOOK_URL', 'NOT SET'))
"
```

**Solutions:**

```bash
# Ensure .env in correct location
ls -la .env

# Check format (no spaces around =)
KEY=value  # ✅
KEY = value  # ❌

# Restart to pick up changes
docker-compose restart factorio-isr
```

---

### Secrets Not Found

**Error:** `Secret file not found: /run/secrets/...`

**Solutions:**

```bash
# Check secrets exist
ls -la .secrets/

# Verify docker-compose.yml secrets section
secrets:
  discord_webhook_url:
    file: .secrets/DISCORD_WEBHOOK_URL.txt  # ✅ Correct path

# Check inside container
docker exec factorio-isr ls -la /run/secrets/
```

---

### JSON Parsing Error

**Error:** `json.JSONDecodeError: Expecting property name`

**Diagnosis:**

```bash
# Check WEBHOOK_CHANNELS format
grep WEBHOOK_CHANNELS .env

# Validate JSON
python -c "
import json
channels = 'YOUR_JSON_HERE'
print(json.loads(channels))
"
```

**Solutions:**

```bash
# Use double quotes (not single)
WEBHOOK_CHANNELS={"chat":"url"}  # ✅
WEBHOOK_CHANNELS={'chat':'url'}  # ❌

# No trailing commas
WEBHOOK_CHANNELS={"a":"url1","b":"url2"}  # ✅
WEBHOOK_CHANNELS={"a":"url1","b":"url2",}  # ❌
```

---

## Getting Help

### Collect Diagnostic Information

```bash
# System info
uname -a
docker --version
python --version

# Application info
docker-compose logs --tail=100 factorio-isr
docker-compose ps
docker stats factorio-isr --no-stream

# Configuration
cat .env | grep -v PASSWORD
ls -la .secrets/
ls -la patterns/

# Test health
curl http://localhost:8080/health
```

---

### Enable Debug Logging

```bash
# .env
LOG_LEVEL=debug
LOG_FORMAT=console  # Easier to read

# Restart
docker-compose restart factorio-isr

# View debug logs
docker-compose logs -f factorio-isr
```

---

### Report Issues

When reporting issues, include:

1. **Error message** - Full error text
2. **Logs** - Recent application logs
3. **Configuration** - .env (redact secrets)
4. **Environment** - OS, Docker version, Python version
5. **Steps to reproduce** - How to trigger the issue

---

## Next Steps

- [RCON Setup](RCON_SETUP.md) - RCON configuration
- [Deployment](DEPLOYMENT.md) - Production deployment
- [Examples](EXAMPLES.md) - Common configurations
- [Patterns](PATTERNS.md) - Pattern syntax

---

**Still having issues?** Open an issue on [GitHub](https://github.com/yourusername/factorio-isr/issues) with diagnostic information above.
