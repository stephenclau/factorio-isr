# Usage Examples

Common configuration scenarios and use cases for Factorio ISR.

## Table of Contents

- [Basic Setup](#basic-setup)
- [RCON Statistics](#rcon-statistics)
- [Multi-Channel Routing](#multi-channel-routing)
- [Custom Mod Events](#custom-mod-events)
- [Docker Deployment](#docker-deployment)
- [Multiple Servers](#multiple-servers)
- [Advanced Patterns](#advanced-patterns)

---

## Basic Setup

### Minimal Configuration

Monitor Factorio logs and send events to single Discord channel:

```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK
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
DISCORD_WEBHOOK_URL=https://discord.com/webhooks/YOUR_WEBHOOK
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
```

---

### Custom Stats Interval

#### Every 10 Minutes
```bash
STATS_INTERVAL=600
```

#### Every Hour
```bash
STATS_INTERVAL=3600
```

#### Every Minute (Testing Only)
```bash
STATS_INTERVAL=60  # Not recommended for production
```

---

## Multi-Channel Routing

### Separate Chat and Events

Route chat messages to one channel, game events to another:

```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/webhooks/MAIN_WEBHOOK
WEBHOOK_CHANNELS={"chat":"https://discord.com/webhooks/CHAT_WEBHOOK","events":"https://discord.com/webhooks/EVENTS_WEBHOOK"}
```

```yaml
# patterns/routing.yml
patterns:
  - name: chat_message
    regex: '\[CHAT\] (.+?): (.+)'
    event_type: chat
    fields:
      player: 1
      message: 2
    discord:
      channel: chat
      emoji: "💬"
      title: "{player}"
      description: "{message}"

  - name: player_death
    regex: '(.+) was killed by (.+)'
    event_type: death
    fields:
      player: 1
      killer: 2
    discord:
      channel: events
      emoji: "💀"
      color: 0xFF0000
      title: "Player Death"
      description: "{player} was killed by {killer}"
```

---

### Admin Notifications

Send admin events to a private channel:

```bash
# .env
WEBHOOK_CHANNELS={"general":"https://discord.com/webhooks/GENERAL","admin":"https://discord.com/webhooks/ADMIN"}
```

```yaml
# patterns/admin.yml
patterns:
  - name: admin_join
    regex: '\[JOIN\] (Admin|Moderator|Owner).+'
    event_type: admin
    priority: 100
    discord:
      channel: admin
      emoji: "🛡️"
      color: 0xFF0000
      title: "Admin Online"

  - name: admin_command
    regex: '(.+) used admin command: (.+)'
    event_type: admin
    fields:
      player: 1
      command: 2
    discord:
      channel: admin
      emoji: "⚙️"
      color: 0xFFAA00
      title: "Admin Command"
      description: "{player} executed: {command}"
```

---

### Milestone Channel

Route major achievements to a dedicated milestones channel:

```bash
WEBHOOK_CHANNELS={"general":"https://discord.com/webhooks/GENERAL","milestones":"https://discord.com/webhooks/MILESTONES"}
```

```yaml
# patterns/milestones.yml
patterns:
  - name: rocket_launch
    regex: 'Rocket launched'
    event_type: milestone
    priority: 100
    discord:
      channel: milestones
      emoji: "🚀"
      color: 0x00FF00
      title: "🎉 ROCKET LAUNCHED! 🎉"
      description: "The team has launched a rocket!"

  - name: first_oil
    regex: 'First oil processing'
    event_type: milestone
    discord:
      channel: milestones
      emoji: "🛢️"
      title: "Oil Processing Unlocked"

  - name: nuclear_power
    regex: 'Nuclear power plant activated'
    event_type: milestone
    discord:
      channel: milestones
      emoji: "☢️"
      color: 0x00FF00
      title: "Nuclear Power Online!"
```

---

## Custom Mod Events

### AAI Vehicles

Track vehicle deployment and destruction:

```yaml
# patterns/aai-vehicles.yml
patterns:
  - name: vehicle_deployed
    regex: '(.+) deployed a (.+)'
    event_type: vehicle
    priority: 80
    fields:
      player: 1
      vehicle: 2
    discord:
      emoji: "🚗"
      color: 0x00AAFF
      title: "Vehicle Deployed"
      description: "{player} deployed a {vehicle}"

  - name: vehicle_destroyed
    regex: 'Vehicle (.+) was destroyed by (.+)'
    event_type: death
    fields:
      vehicle: 1
      cause: 2
    discord:
      emoji: "💥"
      color: 0xFF0000
      title: "Vehicle Destroyed"
      description: "{vehicle} was destroyed by {cause}!"

  - name: vehicle_abandoned
    regex: '(.+) abandoned (.+)'
    event_type: vehicle
    fields:
      player: 1
      vehicle: 2
    discord:
      emoji: "🚙"
      color: 0xFFAA00
      description: "{player} abandoned {vehicle}"
```

---

### Krastorio 2

Track Krastorio 2 specific events:

```yaml
# patterns/krastorio2.yml
patterns:
  - name: matter_stabilizer
    regex: 'Matter stabilizer (activated|deactivated)'
    event_type: achievement
    fields:
      state: 1
    discord:
      emoji: "⚗️"
      color: 0x9B59B6
      title: "Matter Stabilizer {state}"

  - name: intergalactic_transceiver
    regex: 'Intergalactic transceiver built'
    event_type: milestone
    priority: 100
    discord:
      emoji: "📡"
      color: 0x3498DB
      title: "🌌 Intergalactic Communication!"
      description: "The Intergalactic Transceiver is operational!"

  - name: matter_conversion
    regex: 'Matter converted: (.+) units'
    event_type: resource
    fields:
      amount: 1
    discord:
      emoji: "⚗️"
      description: "Converted {amount} units of matter"
```

---

### Space Exploration

Track space-related events:

```yaml
# patterns/space-exploration.yml
patterns:
  - name: satellite_launched
    regex: '(.+) launched satellite to (.+)'
    event_type: milestone
    priority: 95
    fields:
      player: 1
      destination: 2
    discord:
      emoji: "🛰️"
      color: 0x3498DB
      title: "Satellite Launched"
      description: "{player} launched satellite to {destination}"

  - name: planet_discovered
    regex: 'Planet discovered: (.+)'
    event_type: milestone
    priority: 100
    fields:
      planet: 1
    discord:
      emoji: "🌎"
      color: 0x27AE60
      title: "🌟 New Planet Discovered!"
      description: "Planet {planet} has been discovered!"

  - name: space_death
    regex: '(.+) died in space'
    event_type: death
    priority: 90
    fields:
      player: 1
    discord:
      emoji: "💀"
      color: 0xFF0000
      title: "Death in Space"
      description: "{player} died in the cold void of space"

  - name: cargo_rocket
    regex: 'Cargo rocket launched to (.+)'
    event_type: logistics
    fields:
      destination: 1
    discord:
      emoji: "📦"
      description: "Cargo rocket launched to {destination}"
```

---

### Factorissimo

Track factory building events:

```yaml
# patterns/factorissimo.yml
patterns:
  - name: factory_built
    regex: '(.+) built a (.+) factory building'
    event_type: achievement
    fields:
      player: 1
      size: 2
    discord:
      emoji: "🏭"
      color: 0x95A5A6
      description: "{player} built a {size} factory building"

  - name: recursive_factory
    regex: 'Factory building placed inside factory building'
    event_type: achievement
    priority: 90
    discord:
      emoji: "🏭"
      color: 0xE74C3C
      title: "Recursive Factory!"
      description: "Inception level: Factory building inside factory building"
```

---

## Docker Deployment

### Single Server Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  factorio-isr:
    build: .
    container_name: factorio-isr
    restart: unless-stopped

    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - BOT_NAME=My Factorio Server
      - LOG_LEVEL=info
      - LOG_FORMAT=json
      - RCON_ENABLED=true
      - RCON_HOST=factorio-server
      - RCON_PORT=27015
      - STATS_INTERVAL=300

    secrets:
      - discord_webhook_url
      - rcon_password

    volumes:
      - /srv/factorio/logs:/factorio:ro
      - ./patterns:/app/patterns:ro

    ports:
      - "8080:8080"

    networks:
      - factorio

secrets:
  discord_webhook_url:
    file: .secrets/DISCORD_WEBHOOK_URL.txt
  rcon_password:
    file: .secrets/RCON_PASSWORD.txt

networks:
  factorio:
    external: true
```

**Deploy:**
```bash
docker-compose up -d
docker-compose logs -f
```

---

### With Factorio Server

Run ISR alongside Factorio server:

```yaml
# docker-compose.yml
version: '3.8'

services:
  factorio:
    image: factoriotools/factorio:stable
    container_name: factorio-server
    restart: unless-stopped
    ports:
      - "34197:34197/udp"
      - "27015:27015/tcp"
    volumes:
      - ./factorio:/factorio
    environment:
      - RCON_PORT=27015
      - RCON_PASSWORD_FILE=/run/secrets/rcon_password
    secrets:
      - rcon_password
    networks:
      - factorio

  factorio-isr:
    build: ./factorio-isr
    container_name: factorio-isr
    restart: unless-stopped
    depends_on:
      - factorio
    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - BOT_NAME=Factorio Server
      - RCON_ENABLED=true
      - RCON_HOST=factorio
      - RCON_PORT=27015
    secrets:
      - discord_webhook_url
      - rcon_password
    volumes:
      - ./factorio:/factorio:ro
    ports:
      - "8080:8080"
    networks:
      - factorio

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

## Multiple Servers

### Separate ISR Instances

Run one ISR instance per Factorio server:

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Vanilla Server
  factorio-isr-vanilla:
    build: .
    container_name: factorio-isr-vanilla
    restart: unless-stopped
    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - BOT_NAME=Vanilla Server
      - RCON_ENABLED=true
      - RCON_HOST=factorio-vanilla
      - RCON_PORT=27015
    secrets:
      - discord_webhook_vanilla
      - rcon_password_vanilla
    volumes:
      - /srv/factorio-vanilla/logs:/factorio:ro
    ports:
      - "8081:8080"

  # Modded Server
  factorio-isr-modded:
    build: .
    container_name: factorio-isr-modded
    restart: unless-stopped
    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - BOT_NAME=Modded Server (K2+SE)
      - RCON_ENABLED=true
      - RCON_HOST=factorio-modded
      - RCON_PORT=27015
      - PATTERNS_DIR=patterns-modded
    secrets:
      - discord_webhook_modded
      - rcon_password_modded
    volumes:
      - /srv/factorio-modded/logs:/factorio:ro
      - ./patterns-modded:/app/patterns-modded:ro
    ports:
      - "8082:8080"

  # Testing Server
  factorio-isr-testing:
    build: .
    container_name: factorio-isr-testing
    restart: unless-stopped
    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - BOT_NAME=Testing Server
      - RCON_ENABLED=false
      - LOG_LEVEL=debug
    secrets:
      - discord_webhook_testing
    volumes:
      - /srv/factorio-testing/logs:/factorio:ro
    ports:
      - "8083:8080"

secrets:
  discord_webhook_vanilla:
    file: .secrets/DISCORD_WEBHOOK_VANILLA.txt
  rcon_password_vanilla:
    file: .secrets/RCON_PASSWORD_VANILLA.txt
  discord_webhook_modded:
    file: .secrets/DISCORD_WEBHOOK_MODDED.txt
  rcon_password_modded:
    file: .secrets/RCON_PASSWORD_MODDED.txt
  discord_webhook_testing:
    file: .secrets/DISCORD_WEBHOOK_TESTING.txt
```

---

## Advanced Patterns

### Conditional Routing by Player

Route admin actions differently:

```yaml
# patterns/conditional.yml
patterns:
  - name: admin_death
    regex: '(Admin|Moderator|Owner) was killed'
    event_type: death
    priority: 110
    discord:
      channel: admin
      emoji: "💀"
      color: 0xFF0000
      title: "⚠️ Admin Death Alert!"

  - name: regular_death
    regex: '(.+) was killed'
    event_type: death
    priority: 50
    discord:
      emoji: "💀"
      description: "{0} was killed"
```

---

### Rate Limiting Common Events

Reduce noise from frequent events:

```yaml
# patterns/filtered.yml
patterns:
  - name: tree_mined
    regex: '(.+) mined a tree'
    event_type: resource
    priority: 1  # Very low priority
    # Don't send to Discord - too spammy

  - name: ore_mined
    regex: '(.+) mined (.+) ore'
    event_type: resource
    priority: 5
    # Also skip Discord

  - name: rocket_launch
    regex: 'Rocket launched'
    event_type: milestone
    priority: 100  # High priority - always send
    discord:
      emoji: "🚀"
      title: "🎉 ROCKET LAUNCHED! 🎉"
```

---

### Complex Regex Patterns

Match complex log formats:

```yaml
# patterns/complex.yml
patterns:
  - name: combat_stats
    regex: '(.+) killed: (\d+) biters, (\d+) spitters, (\d+) worms'
    event_type: achievement
    fields:
      player: 1
      biters: 2
      spitters: 3
      worms: 4
    discord:
      emoji: "⚔️"
      color: 0xFF0000
      title: "Combat Statistics"
      description: "{player}: {biters} biters, {spitters} spitters, {worms} worms"

  - name: production_milestone
    regex: 'Production: (.+) reached (\d+(?:,\d+)*) items/minute'
    event_type: milestone
    fields:
      item: 1
      rate: 2
    discord:
      emoji: "📈"
      color: 0x00FF00
      title: "Production Milestone"
      description: "{item}: {rate} items/minute"
```

---

## Testing Configuration

### Test Discord Webhook

```bash
curl -X POST "$(cat .secrets/DISCORD_WEBHOOK_URL.txt)" \
  -H "Content-Type: application/json" \
  -d '{"content":"🧪 Test message from Factorio ISR setup"}'
```

---

### Test RCON Connection

```bash
python -c "
from rcon.source import Client
with Client('localhost', 27015, passwd='$(cat .secrets/RCON_PASSWORD.txt)') as c:
    print(f'Server time: {c.run("/time")}')
    print(f'Players: {c.run("/players")}')
"
```

---

### Simulate Log Events

```bash
# Add test events to log file
LOG_FILE=/path/to/factorio/console.log

echo "$(date '+%Y-%m-%d %H:%M:%S') [CHAT] TestUser: Hello world!" >> $LOG_FILE
echo "$(date '+%Y-%m-%d %H:%M:%S') [JOIN] TestUser joined the game" >> $LOG_FILE
echo "$(date '+%Y-%m-%d %H:%M:%S') TestUser was killed by a small-biter" >> $LOG_FILE
echo "$(date '+%Y-%m-%d %H:%M:%S') [LEAVE] TestUser left the game" >> $LOG_FILE
```

---

### Dry Run Mode

Test patterns without sending to Discord:

```bash
# Temporarily disable webhook
export DISCORD_WEBHOOK_URL=""

# Run with debug logging
LOG_LEVEL=debug python -m src.main
```

---

## Production Best Practices

### Logging Configuration

```bash
# Production
LOG_LEVEL=info
LOG_FORMAT=json

# Development
LOG_LEVEL=debug
LOG_FORMAT=console

# Troubleshooting
LOG_LEVEL=debug
LOG_FORMAT=json
```

---

### Health Monitoring

```bash
# Automated health check
*/5 * * * * curl -f http://localhost:8080/health || /usr/local/bin/alert.sh
```

---

### Log Rotation

```bash
# /etc/logrotate.d/factorio-isr
/opt/factorio-isr/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 factorio factorio
    postrotate
        docker-compose -f /opt/factorio-isr/docker-compose.yml restart factorio-isr
    endscript
}
```

---

## Next Steps

- [RCON Setup Guide](RCON_SETUP.md) - Configure server statistics
- [Multi-Channel Guide](MULTI_CHANNEL.md) - Route events to different channels
- [Pattern Syntax](PATTERNS.md) - Complete pattern reference
- [Deployment Guide](DEPLOYMENT.md) - Production deployment

---

**Happy monitoring! 🏭🚂**
