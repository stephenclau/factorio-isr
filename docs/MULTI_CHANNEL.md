# Multi-Channel Routing Guide

Configure Factorio ISR to route different event types to different Discord channels.

## Table of Contents

- [Overview](#overview)
- [Basic Configuration](#basic-configuration)
- [Channel Definitions](#channel-definitions)
- [Pattern Routing](#pattern-routing)
- [Common Scenarios](#common-scenarios)
- [Advanced Routing](#advanced-routing)
- [Troubleshooting](#troubleshooting)

---

## Overview

Multi-channel routing allows you to:
- **Separate chat from events** - Keep conversations separate from game notifications
- **Create admin channels** - Route sensitive events to private channels
- **Organize by priority** - Send milestones to dedicated channels
- **Reduce noise** - Filter events by importance per channel

### Benefits

- ✅ **Better organization** - Each channel has a specific purpose
- ✅ **Reduced spam** - Users can mute channels they don't want
- ✅ **Improved readability** - Related events stay together
- ✅ **Flexible notifications** - Different Discord notification settings per channel

---

## Basic Configuration

### Single Default Channel

Without multi-channel routing, all events go to one webhook:

```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK
```

All events → Single channel

---

### Enable Multi-Channel

Add channel definitions to `.env`:

```bash
# .env
# Main webhook (fallback for unrouted events)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/MAIN_WEBHOOK

# Additional channels (JSON format)
WEBHOOK_CHANNELS={"chat":"https://discord.com/webhooks/CHAT","events":"https://discord.com/webhooks/EVENTS"}
```

Now you can route different patterns to different channels!

---

## Channel Definitions

### Format

The `WEBHOOK_CHANNELS` variable uses JSON format:

```bash
WEBHOOK_CHANNELS={"channel_name":"webhook_url","another_channel":"webhook_url"}
```

**Important:**
- Must be valid JSON (use double quotes)
- Channel names are case-sensitive
- No spaces in JSON (except in URLs)

---

### Common Channel Setup

```bash
# .env
WEBHOOK_CHANNELS={"general":"https://discord.com/webhooks/GENERAL","chat":"https://discord.com/webhooks/CHAT","events":"https://discord.com/webhooks/EVENTS","milestones":"https://discord.com/webhooks/MILESTONES","admin":"https://discord.com/webhooks/ADMIN"}
```

This creates 5 channels:
- `general` - Fallback/misc events
- `chat` - Player chat messages
- `events` - Game events (deaths, joins, etc.)
- `milestones` - Important achievements
- `admin` - Administrative events

---

### Discord Setup

Create webhooks in Discord:

1. **Open Discord** → Go to Server Settings
2. **Integrations** → Webhooks
3. **New Webhook** for each channel
4. **Customize:**
   - Name: "Factorio Chat", "Factorio Events", etc.
   - Channel: Select target channel
   - Avatar: Optional custom icon
5. **Copy Webhook URL** → Use in `.env`

---

## Pattern Routing

### Specify Channel in Patterns

Add `channel` to the `discord` section:

```yaml
# patterns/routing.yml
patterns:
  - name: chat_message
    regex: '\[CHAT\] (.+?): (.+)'
    event_type: chat
    discord:
      channel: chat  # ← Routes to "chat" webhook
      emoji: "💬"
```

### Fallback Behavior

If no channel is specified or channel doesn't exist:
- Falls back to `DISCORD_WEBHOOK_URL` (main webhook)
- Event is still sent, just to default channel

---

## Common Scenarios

### Scenario 1: Separate Chat from Events

**Goal:** Chat in one channel, everything else in another

```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/webhooks/EVENTS
WEBHOOK_CHANNELS={"chat":"https://discord.com/webhooks/CHAT"}
```

```yaml
# patterns/chat.yml
patterns:
  - name: chat_message
    regex: '\[CHAT\] (.+?): (.+)'
    event_type: chat
    discord:
      channel: chat  # ← Chat goes here
      emoji: "💬"
      title: "{1}"
      description: "{2}"
```

All other events → Default webhook (events)  
Chat messages → Chat webhook

---

### Scenario 2: Admin Notifications

**Goal:** Sensitive events in private admin channel

```bash
# .env
WEBHOOK_CHANNELS={"general":"https://discord.com/webhooks/GENERAL","admin":"https://discord.com/webhooks/ADMIN"}
```

```yaml
# patterns/admin.yml
patterns:
  - name: admin_join
    regex: '\[JOIN\] (Admin|Moderator).+'
    event_type: admin
    discord:
      channel: admin
      emoji: "🛡️"
      color: 0xFF0000
      title: "Admin Online"

  - name: server_command
    regex: 'Server command executed: (.+)'
    event_type: admin
    discord:
      channel: admin
      emoji: "⚙️"
      title: "Server Command"
      description: "{1}"
```

---

### Scenario 3: Milestone Celebrations

**Goal:** Major achievements in dedicated channel

```bash
# .env
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
      description: "The team has successfully launched a rocket!"

  - name: first_nuclear
    regex: 'Nuclear reactor activated'
    event_type: milestone
    discord:
      channel: milestones
      emoji: "☢️"
      title: "Nuclear Power Online!"

  - name: production_milestone
    regex: 'Production milestone: (.+)'
    event_type: milestone
    discord:
      channel: milestones
      emoji: "📈"
      description: "{1}"
```

---

### Scenario 4: Death Alerts

**Goal:** Track deaths separately

```bash
# .env
WEBHOOK_CHANNELS={"general":"https://discord.com/webhooks/GENERAL","deaths":"https://discord.com/webhooks/DEATHS"}
```

```yaml
# patterns/deaths.yml
patterns:
  - name: player_death
    regex: '(.+) was killed by (.+)'
    event_type: death
    discord:
      channel: deaths
      emoji: "💀"
      color: 0xFF0000
      title: "Player Death"
      description: "{1} was killed by {2}"
```

---

### Scenario 5: Complete Separation

**Goal:** Different channel for every event type

```bash
# .env
WEBHOOK_CHANNELS={"chat":"https://discord.com/webhooks/CHAT","joins":"https://discord.com/webhooks/JOINS","deaths":"https://discord.com/webhooks/DEATHS","achievements":"https://discord.com/webhooks/ACHIEVEMENTS","research":"https://discord.com/webhooks/RESEARCH","milestones":"https://discord.com/webhooks/MILESTONES"}
```

```yaml
# patterns/complete.yml
patterns:
  - name: chat
    regex: '\[CHAT\] (.+?): (.+)'
    event_type: chat
    discord:
      channel: chat

  - name: join
    regex: '\[JOIN\] (.+) joined'
    event_type: join
    discord:
      channel: joins

  - name: death
    regex: '(.+) was killed'
    event_type: death
    discord:
      channel: deaths

  - name: achievement
    regex: '(.+) completed (.+)'
    event_type: achievement
    discord:
      channel: achievements

  - name: research
    regex: 'Technology (.+) researched'
    event_type: research
    discord:
      channel: research

  - name: rocket
    regex: 'Rocket launched'
    event_type: milestone
    discord:
      channel: milestones
```

---

## Advanced Routing

### Conditional Routing by Content

Route based on message content:

```yaml
# patterns/conditional.yml
patterns:
  # Admin deaths → admin channel
  - name: admin_death
    regex: '(Admin|Moderator) was killed'
    event_type: death
    priority: 100
    discord:
      channel: admin
      emoji: "💀"
      color: 0xFF0000
      title: "⚠️ ADMIN DEATH"

  # Regular deaths → deaths channel
  - name: regular_death
    regex: '(.+) was killed'
    event_type: death
    priority: 50
    discord:
      channel: deaths
      emoji: "💀"
```

Priority matters! Higher priority patterns match first.

---

### Priority-Based Routing

Route high-priority events differently:

```yaml
# patterns/priority.yml
patterns:
  # Critical events → admin channel
  - name: server_error
    regex: 'ERROR|CRITICAL|FATAL'
    event_type: error
    priority: 100
    discord:
      channel: admin
      emoji: "🚨"
      color: 0xFF0000

  # High priority → milestones
  - name: rocket
    regex: 'Rocket launched'
    event_type: milestone
    priority: 90
    discord:
      channel: milestones

  # Normal events → general
  - name: achievement
    regex: '(.+) completed (.+)'
    event_type: achievement
    priority: 50
    discord:
      channel: general
```

---

### Multi-Channel Broadcast

Send same event to multiple channels:

```yaml
# patterns/broadcast.yml
patterns:
  - name: rocket_to_general
    regex: 'Rocket launched'
    event_type: milestone
    priority: 100
    discord:
      channel: general
      emoji: "🚀"
      title: "🎉 ROCKET LAUNCHED! 🎉"

  - name: rocket_to_milestones
    regex: 'Rocket launched'
    event_type: milestone
    priority: 99
    discord:
      channel: milestones
      emoji: "🚀"
      title: "🎉 ROCKET LAUNCHED! 🎉"
```

Both patterns match → Both channels receive the event

---

### Dynamic Channel Selection

Use multiple pattern files for different routing:

```bash
# Development
PATTERN_FILES=["vanilla.yml","routing-dev.yml"]

# Production
PATTERN_FILES=["vanilla.yml","routing-prod.yml"]
```

```yaml
# patterns/routing-dev.yml
patterns:
  - name: all_events
    regex: '.*'
    priority: 1
    discord:
      channel: dev-testing
```

```yaml
# patterns/routing-prod.yml
patterns:
  - name: chat
    regex: '\[CHAT\]'
    discord:
      channel: chat

  - name: events
    regex: '.*'
    discord:
      channel: events
```

---

## Channel Architecture

### Small Server (1-10 players)

**2 channels:**
```bash
WEBHOOK_CHANNELS={"chat":"URL1","events":"URL2"}
```

- `chat` - Player conversations
- `events` - Everything else

---

### Medium Server (10-50 players)

**4 channels:**
```bash
WEBHOOK_CHANNELS={"chat":"URL1","events":"URL2","milestones":"URL3","admin":"URL4"}
```

- `chat` - Player conversations
- `events` - Joins, deaths, achievements
- `milestones` - Rockets, major achievements
- `admin` - Admin actions, errors

---

### Large Server (50+ players)

**6+ channels:**
```bash
WEBHOOK_CHANNELS={"chat":"URL1","joins":"URL2","deaths":"URL3","achievements":"URL4","research":"URL5","milestones":"URL6","admin":"URL7"}
```

Fully separated event types for better organization.

---

## Testing Multi-Channel

### Test Individual Channels

```bash
# Test chat channel
curl -X POST "https://discord.com/webhooks/CHAT" \
  -H "Content-Type: application/json" \
  -d '{"content":"🧪 Test chat channel"}'

# Test events channel
curl -X POST "https://discord.com/webhooks/EVENTS" \
  -H "Content-Type: application/json" \
  -d '{"content":"🧪 Test events channel"}'

# Test admin channel
curl -X POST "https://discord.com/webhooks/ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"content":"🧪 Test admin channel"}'
```

---

### Verify Routing

Check logs to see which channel each event uses:

```bash
# View routing decisions
docker-compose logs factorio-isr | grep channel

# Expected output:
# {"event": "discord_message_sent", "channel": "chat", ...}
# {"event": "discord_message_sent", "channel": "events", ...}
```

---

### Simulate Events

```bash
LOG_FILE=/path/to/factorio/console.log

# Should go to chat channel
echo "$(date '+%Y-%m-%d %H:%M:%S') [CHAT] TestUser: Test message" >> $LOG_FILE

# Should go to events channel
echo "$(date '+%Y-%m-%d %H:%M:%S') [JOIN] TestUser joined the game" >> $LOG_FILE

# Should go to milestones channel
echo "$(date '+%Y-%m-%d %H:%M:%S') Rocket launched" >> $LOG_FILE
```

---

## Troubleshooting

### Events Go to Wrong Channel

**Problem:** Event appears in wrong Discord channel

**Solutions:**

1. **Check pattern priority**
   ```yaml
   # Higher priority matches first
   - name: admin_death
     priority: 100  # ← Matches before regular_death

   - name: regular_death
     priority: 50
   ```

2. **Verify channel name matches**
   ```bash
   # .env
   WEBHOOK_CHANNELS={"chat":"..."}

   # Pattern must match exactly
   discord:
     channel: chat  # ← Must be "chat", not "Chat"
   ```

3. **Check pattern regex**
   ```bash
   # Test regex
   python -c "
   import re
   pattern = r'\[CHAT\] (.+?): (.+)'
   log_line = '2024-12-01 12:00:00 [CHAT] Player: Hello'
   match = re.search(pattern, log_line)
   print(f'Match: {match.groups() if match else None}')
   "
   ```

---

### Channel Not Found

**Problem:** `{"event": "channel_not_found", "channel": "xyz"}`

**Solutions:**

1. **Check WEBHOOK_CHANNELS syntax**
   ```bash
   # Validate JSON
   python -c "
   import json
   import os
   channels = os.getenv('WEBHOOK_CHANNELS', '{}')
   print(json.loads(channels))
   "
   ```

2. **Verify channel name**
   ```bash
   # List defined channels
   python -c "
   import json
   import os
   channels = json.loads(os.getenv('WEBHOOK_CHANNELS', '{}'))
   print('Defined channels:', list(channels.keys()))
   "
   ```

3. **Check for typos**
   - Channel names are case-sensitive
   - No extra spaces
   - Exact match required

---

### Webhook Not Working

**Problem:** Webhook URL returns 404 or 401

**Solutions:**

1. **Test webhook directly**
   ```bash
   curl -X POST "YOUR_WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d '{"content":"Test"}'
   ```

2. **Check webhook is valid**
   - Webhook not deleted in Discord
   - Correct permissions in channel
   - Bot still in server

3. **Regenerate webhook**
   - Delete old webhook in Discord
   - Create new webhook
   - Update `.env` with new URL

---

### All Events Go to Default Channel

**Problem:** Multi-channel not working at all

**Solutions:**

1. **Verify WEBHOOK_CHANNELS is set**
   ```bash
   grep WEBHOOK_CHANNELS .env
   ```

2. **Check JSON format**
   ```bash
   # Must be valid JSON with double quotes
   WEBHOOK_CHANNELS={"chat":"url"}  # ✅ Correct
   WEBHOOK_CHANNELS={'chat':'url'}  # ❌ Wrong
   WEBHOOK_CHANNELS={chat:url}      # ❌ Wrong
   ```

3. **Restart application**
   ```bash
   docker-compose restart factorio-isr
   ```

4. **Check logs for errors**
   ```bash
   docker-compose logs factorio-isr | grep -i webhook
   ```

---

## Best Practices

### Channel Organization

- ✅ **Start simple** - Begin with 2-3 channels
- ✅ **Group related events** - Don't over-separate
- ✅ **Consider muting** - Users can mute channels they don't want
- ✅ **Test thoroughly** - Verify routing before production

---

### Naming Conventions

- Use **lowercase** channel names
- Use **descriptive** names (e.g., `admin` not `a`)
- Keep names **short** (easier to type)
- Be **consistent** across patterns

---

### Discord Channel Setup

- Use **topic descriptions** to explain what each channel receives
- Set **permissions** appropriately (e.g., admin channel restricted)
- Configure **notifications** per channel
- Use **channel categories** to group related channels

---

### Performance

- Multi-channel routing adds **minimal overhead**
- Each webhook is sent **concurrently** (non-blocking)
- Failed webhooks **don't block** other channels
- **No limit** on number of channels

---

## Examples

See [EXAMPLES.md](EXAMPLES.md) for complete multi-channel scenarios.

---

## Next Steps

- [RCON Setup](RCON_SETUP.md) - Configure server statistics
- [Pattern Guide](PATTERNS.md) - Pattern syntax reference
- [Examples](EXAMPLES.md) - Common configurations
- [Deployment](DEPLOYMENT.md) - Production deployment

---

**Happy routing! 📨**
