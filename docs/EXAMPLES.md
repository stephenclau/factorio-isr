# 📖 Usage Examples

Common configuration scenarios and use cases for Factorio ISR.

## Table of Contents

- [Basic Setup](#basic-setup)
- [RCON Statistics](#rcon-statistics)
- [Custom Mod Events](#custom-mod-events)
- [Docker Deployment](#docker-deployment)
- [Multiple Servers](#multiple-servers)
- [Advanced Patterns](#advanced-patterns)

---

## Basic Setup

### Minimal Configuration

Monitor Factorio logs and send events to Discord via bot:

```bash
# .env
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_EVENT_CHANNEL_ID=123456789012345678
FACTORIO_LOG_PATH=/factorio/console.log
BOT_NAME=My Factorio Server
```

```bash
python -m src.main
```

**Expected Output:**
- Player joins/leaves
- Chat messages
- Deaths and achievements
- Research completions
- Rocket launches

---

## RCON Statistics

### Enable Server Stats

Post player count and server time every 5 minutes:

```bash
# .env
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_EVENT_CHANNEL_ID=123456789012345678
FACTORIO_LOG_PATH=/factorio/console.log

# Enable RCON
RCON_ENABLED=true
RCON_HOST=localhost
RCON_PORT=27015
STATS_INTERVAL=300
```

```bash
# Store password securely
echo "your-rcon-password" > .secrets/RCON_PASSWORD.txt
chmod 600 .secrets/RCON_PASSWORD.txt

# Run
python -m src.main
```

**Discord Output (every 5 minutes):**

```
📊 **Server Status**
👥 Players Online: 3
📝 Alice, Bob, Charlie
⏰ Game Time: Day 42, 13:45
📈 UPS: 59.8/60 ✅
🧬 Evolution: 45.2%
```

### Custom Stats Interval

**Every 10 Minutes**

```bash
STATS_INTERVAL=600
```

**Every Hour**

```bash
STATS_INTERVAL=3600
```

**Every Minute (Testing Only)**

```bash
STATS_INTERVAL=60  # Not recommended for production
```

---

## Custom Mod Events

### AAI Vehicles

Track vehicle deployment and destruction:

```yaml
# patterns/aai-vehicles.yml
events:
  vehicle_deployed:
    pattern: '(.+) deployed a (.+)'
    type: vehicle
    emoji: "🚗"
    message: "{player} deployed a {vehicle}"
    enabled: true
    priority: 80
    channel: events

  vehicle_destroyed:
    pattern: 'Vehicle (.+) was destroyed by (.+)'
    type: death
    emoji: "💥"
    message: "{vehicle} was destroyed by {cause}!"
    enabled: true
    priority: 85
    channel: milestones

  vehicle_abandoned:
    pattern: '(.+) abandoned (.+)'
    type: vehicle
    emoji: "🚙"
    message: "{player} abandoned {vehicle}"
    enabled: true
    priority: 5
    channel: events
```

---

### Krastorio 2

Track Krastorio 2 specific events:

```yaml
# patterns/krastorio2.yml
events:
  matter_stabilizer:
    pattern: 'Matter stabilizer (activated|deactivated)'
    type: achievement
    emoji: "⚗️"
    message: "Matter stabilizer {state}"
    enabled: true
    priority: 50
    channel: events

  intergalactic_transceiver:
    pattern: 'Intergalactic transceiver built'
    type: milestone
    emoji: "📡"
    message: "🌌 Intergalactic Communication Enabled!"
    enabled: true
    priority: 100
    channel: milestones

  matter_conversion:
    pattern: 'Matter converted: (.+) units'
    type: resource
    emoji: "⚗️"
    message: "Converted {amount} units of matter"
    enabled: true
    priority: 20
    channel: events
```

---

### Space Exploration

Track space-related events:

```yaml
# patterns/space-exploration.yml
events:
  satellite_launched:
    pattern: '(.+) launched satellite to (.+)'
    type: milestone
    emoji: "🛰️"
    message: "{player} launched satellite to {destination}"
    enabled: true
    priority: 95
    channel: milestones

  planet_discovered:
    pattern: 'Planet discovered: (.+)'
    type: milestone
    emoji: "🌎"
    message: "🌟 New Planet Discovered: {planet}!"
    enabled: true
    priority: 100
    channel: milestones

  space_death:
    pattern: '(.+) died in space'
    type: death
    emoji: "💀"
    message: "{player} died in the cold void of space"
    enabled: true
    priority: 90
    channel: events

  cargo_rocket:
    pattern: 'Cargo rocket launched to (.+)'
    type: logistics
    emoji: "📦"
    message: "Cargo rocket launched to {destination}"
    enabled: true
    priority: 30
    channel: events
```

---

### Factorissimo

Track factory building events:

```yaml
# patterns/factorissimo.yml
events:
  factory_built:
    pattern: 'Factory building constructed'
    type: milestone
    emoji: "🏭"
    message: "New factory building constructed!"
    enabled: true
    priority: 40
    channel: events

  factory_upgraded:
    pattern: '(.+) upgraded factory to level (.+)'
    type: milestone
    emoji: "⬆️"
    message: "{player} upgraded factory to level {level}"
    enabled: true
    priority: 50
    channel: events
```

---

## Docker Deployment

### Basic Docker

```bash
# Create secrets
mkdir -p .secrets
echo "your-discord-bot-token" > .secrets/DISCORD_BOT_TOKEN.txt

# Run container
docker run -d \
  --name factorio-isr \
  -e DISCORD_BOT_TOKEN="" \
  -e DISCORD_EVENT_CHANNEL_ID=123456789012345678 \
  -e FACTORIO_LOG_PATH=/factorio/console.log \
  -e LOG_LEVEL=info \
  -v /path/to/factorio/logs:/factorio:ro \
  -v $(pwd)/.secrets/DISCORD_BOT_TOKEN.txt:/run/secrets/DISCORD_BOT_TOKEN:ro \
  -p 8080:8080 \
  slautomaton/factorio-isr:latest
```

### Docker Compose with RCON

```yaml
version: '3.8'

services:
  factorio-isr:
    image: slautomaton/factorio-isr:latest
    container_name: factorio-isr
    restart: unless-stopped

    environment:
      - DISCORD_EVENT_CHANNEL_ID=123456789012345678
      - FACTORIO_LOG_PATH=/factorio/console.log
      - LOG_LEVEL=info
      - LOG_FORMAT=json
      - RCON_ENABLED=true
      - RCON_HOST=factorio-server
      - RCON_PORT=27015
      - STATS_INTERVAL=300

    secrets:
      - discord_bot_token
      - rcon_password

    volumes:
      - /path/to/factorio/logs:/factorio:ro
      - ./patterns:/app/patterns:ro
      - ./config:/app/config:ro

    ports:
      - "8080:8080"

    networks:
      - factorio

secrets:
  discord_bot_token:
    file: ./.secrets/DISCORD_BOT_TOKEN.txt
  rcon_password:
    file: ./.secrets/RCON_PASSWORD.txt

networks:
  factorio:
    driver: bridge
```

---

## Multiple Servers

### Configuration (servers.yml)

```yaml
servers:
  los_hermanos:
    log_path: /factorio/los_hermanos/console.log
    rcon_host: factorio-1.internal
    rcon_port: 27015
    discord_channel_id: 123456789012345678
    stats_interval: 300

  space_age:
    log_path: /factorio/space_age/console.log
    rcon_host: factorio-2.internal
    rcon_port: 27015
    discord_channel_id: 987654321098765432
    stats_interval: 300
```

### Environment

```bash
# .env
SERVERS_CONFIG=config/servers.yml
RCON_ENABLED=true
LOG_LEVEL=info
```

The bot will coordinate events across both servers and show presence like:

```
Watching 2/2 servers online
```

---

## Advanced Patterns

### Pattern with Extracted Fields

```yaml
events:
  research_complete:
    pattern: '(.+) research completed: (.+) \(level (\d+)\)'
    type: research
    emoji: "🔬"
    message: "{player} completed {technology} research (level {level})"
    enabled: true
    priority: 30
    channel: events
```

**Log Input:**

```
Alice research completed: Automation 3 (level 3)
```

**Discord Output:**

```
🔬 Alice completed Automation 3 research (level 3)
```

### Conditional Patterns (High Priority)

```yaml
events:
  boss_spawn:
    pattern: 'Enemy spawned: .*behemoth'
    type: danger
    emoji: "👹"
    message: "⚠️ BEHEMOTH SPOTTED!"
    enabled: true
    priority: 100  # High priority = sent first
    channel: alerts

  death_important:
    pattern: '(Owner|Admin).*was killed'
    type: death
    emoji: "💀"
    message: "Critical: {player} was killed!"
    enabled: true
    priority: 99
    channel: alerts
```

### Disabled Patterns (Optional)

```yaml
events:
  verbose_log:
    pattern: 'verbose log message'
    type: debug
    emoji: "📝"
    message: "{text}"
    enabled: false  # Disabled, not parsed
    priority: 1
    channel: debug
```

---

## Common Issues

**No events appearing?**
- Check `FACTORIO_LOG_PATH` is readable
- Verify Factorio is writing logs
- Enable `LOG_LEVEL=debug` to see parsing details

**Bot offline?**
- Verify `DISCORD_BOT_TOKEN` is valid
- Check bot is invited to server
- Verify `DISCORD_EVENT_CHANNEL_ID` is correct

**RCON stats not updating?**
- Check `RCON_ENABLED=true`
- Verify host/port/password
- Confirm RCON is enabled in Factorio server

---

**See also:**
- [Pattern Syntax](PATTERNS.md) – Full pattern reference
- [Configuration Guide](configuration.md) – All environment variables
- [RCON Setup](RCON_SETUP.md) – Detailed RCON configuration
