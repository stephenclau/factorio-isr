---
layout: default
title: Patterns Guide
---


# Pattern Syntax Reference

Complete guide to creating custom event patterns for Factorio ISR.

## Table of Contents

- [Overview](#overview)
- [Pattern Structure](#pattern-structure)
- [Field Reference](#field-reference)
- [Regex Patterns](#regex-patterns)
- [Discord Configuration](#discord-configuration)
- [Priority System](#priority-system)
- [Examples](#examples)
- [Best Practices](#best-practices)

---

## Overview

Patterns define how Factorio ISR:
- **Matches** log lines using regex
- **Extracts** data from matched lines
- **Formats** Discord messages
- **Routes** events to channels

### Pattern File Format

Patterns are defined in YAML files in the `patterns/` directory.

```yaml
# patterns/example.yml
patterns:
  - name: pattern_name
    regex: 'regex pattern'
    event_type: type
    priority: 100
    fields:
      field_name: capture_group
    discord:
      channel: channel_name
      emoji: "🎮"
      color: 0x00FF00
      title: "Title"
      description: "Description"
```

---

## Pattern Structure

### Minimum Required Fields

```yaml
patterns:
  - name: player_join
    regex: '\[JOIN\] (.+) joined'
    event_type: join
```

**Required:**
- `name` - Unique identifier for the pattern
- `regex` - Regular expression to match log lines
- `event_type` - Category of event

---

### Complete Pattern Example

```yaml
patterns:
  - name: player_death
    regex: '(.+) was killed by (.+)'
    event_type: death
    priority: 80
    fields:
      player: 1
      killer: 2
    discord:
      channel: deaths
      emoji: "💀"
      color: 0xFF0000
      title: "Player Death"
      description: "{player} was killed by {killer}"
```

---

## Field Reference

### name

**Type:** String  
**Required:** Yes  
**Description:** Unique identifier for this pattern

```yaml
name: player_death
```

**Rules:**
- Must be unique within all loaded patterns
- Use snake_case naming convention
- Be descriptive

---

### regex

**Type:** String (Python regex)  
**Required:** Yes  
**Description:** Regular expression to match log lines

```yaml
regex: '\[CHAT\] (.+?): (.+)'
```

**Tips:**
- Use raw strings to avoid escaping issues
- Capture groups with `( )`
- Non-capturing groups with `(?: )`
- Test regex before deploying

**Testing:**
```python
import re
pattern = r'\[CHAT\] (.+?): (.+)'
log_line = '2024-12-01 12:00:00 [CHAT] Player: Hello'
match = re.search(pattern, log_line)
if match:
    print(f'Groups: {match.groups()}')
```

---

### event_type

**Type:** String  
**Required:** Yes  
**Description:** Category of event for grouping and filtering

**Common Types:**
- `chat` - Chat messages
- `join` - Player joins
- `leave` - Player leaves
- `death` - Player deaths
- `achievement` - Achievements unlocked
- `research` - Technology researched
- `milestone` - Major events (rockets, etc.)
- `admin` - Administrative events
- `error` - Errors or warnings

```yaml
event_type: achievement
```

**Custom Types:**

You can define your own:
```yaml
event_type: vehicle  # Custom for vehicle events
event_type: combat   # Custom for combat events
```

---

### priority

**Type:** Integer (0-100)  
**Required:** No  
**Default:** 50  
**Description:** Match priority (higher = matches first)

```yaml
priority: 90
```

**Priority Ranges:**
- `100` - Critical/Must match first
- `80-99` - High priority
- `50-79` - Normal priority
- `20-49` - Low priority
- `1-19` - Very low/catch-all

**Use Cases:**
- Prevent more specific patterns from being overridden
- Create catch-all patterns with low priority
- Route admin events before regular events

**Example:**
```yaml
patterns:
  # Matches first (priority 100)
  - name: admin_death
    regex: '(Admin|Moderator) was killed'
    priority: 100
    discord:
      channel: admin

  # Matches if above doesn't (priority 50)
  - name: regular_death
    regex: '(.+) was killed'
    priority: 50
    discord:
      channel: deaths
```

---

### fields

**Type:** Dictionary  
**Required:** No  
**Description:** Map field names to regex capture groups

```yaml
fields:
  player: 1      # First capture group
  killer: 2      # Second capture group
  location: 3    # Third capture group
```

**Usage in Discord:**
```yaml
discord:
  description: "{player} was killed by {killer} at {location}"
```

**Numbering:**
- Capture groups start at 1 (not 0)
- Group 0 is the entire match
- Use group numbers or field names

---

### discord

**Type:** Dictionary  
**Required:** No  
**Description:** Discord message configuration

```yaml
discord:
  channel: channel_name
  emoji: "🎮"
  color: 0x00FF00
  title: "Message Title"
  description: "Message body"
```

**If omitted:** Event is matched but not sent to Discord

---

## Discord Configuration

### channel

**Type:** String  
**Required:** No  
**Description:** Which Discord channel to send to

```yaml
discord:
  channel: chat
```

**Behavior:**
- Must match key in `WEBHOOK_CHANNELS`
- Falls back to default webhook if not found
- Case-sensitive

---

### emoji

**Type:** String  
**Required:** No  
**Description:** Emoji prepended to message title

```yaml
discord:
  emoji: "🚀"
```

**Tips:**
- Use actual emoji characters
- Can use multiple emojis: "🎉🎊"
- Leave empty for no emoji

**Common Emojis:**
```yaml
chat: "💬"
join: "🎮"
leave: "👋"
death: "💀"
achievement: "🏆"
research: "🔬"
rocket: "🚀"
admin: "🛡️"
error: "🚨"
```

---

### color

**Type:** Integer (hex color)  
**Required:** No  
**Default:** Discord default  
**Description:** Color of Discord embed sidebar

```yaml
discord:
  color: 0xFF0000  # Red
```

**Common Colors:**
```yaml
red: 0xFF0000      # Errors, deaths
green: 0x00FF00    # Success, achievements
blue: 0x0000FF     # Info, research
yellow: 0xFFFF00   # Warnings
orange: 0xFF6600   # Moderate alerts
purple: 0x9B59B6   # Special events
gray: 0x95A5A6     # Misc
```

**Color Picker:** Use https://www.color-hex.com/

---

### title

**Type:** String  
**Required:** No  
**Description:** Bold title of Discord message

```yaml
discord:
  title: "Player Death"
```

**Field Substitution:**
```yaml
discord:
  title: "{player} Achievement"  # Uses 'player' field
```

**Dynamic Titles:**
```yaml
fields:
  player: 1
  achievement: 2
discord:
  title: "{player} unlocked {achievement}"
```

---

### description

**Type:** String  
**Required:** No  
**Description:** Main message body

```yaml
discord:
  description: "A player has joined the server"
```

**Field Substitution:**
```yaml
fields:
  player: 1
  killer: 2
discord:
  description: "{player} was killed by {killer}"
```

**Multi-line:**
```yaml
discord:
  description: |
    {player} completed {achievement}
    Time: {time}
    Location: {location}
```

---

## Regex Patterns

### Basic Matching

#### Literal Text
```yaml
regex: 'Rocket launched'
```
Matches: `"Rocket launched"`

---

#### Simple Capture
```yaml
regex: '(.+) joined the game'
```
Matches: `"PlayerName joined the game"`  
Captures: `["PlayerName"]`

---

### Character Classes

#### Any Character
```yaml
regex: 'Server .+ started'
```
Matches: `"Server v1.0 started"`, `"Server ABC started"`

---

#### Specific Characters
```yaml
regex: '[0-9]+ players online'
```
Matches: `"5 players online"`, `"42 players online"`

---

#### Word Characters
```yaml
regex: '\w+ completed \w+'
```
Matches: `"Player completed Achievement"`

---

### Groups

#### Capturing Group
```yaml
regex: '(.+) was killed by (.+)'
fields:
  player: 1
  killer: 2
```

---

#### Non-capturing Group
```yaml
regex: '(?:Player|Admin) (.+) joined'
fields:
  name: 1
```
Groups `(?:...)` don't create captures

---

#### Named Groups
```yaml
regex: '(?P<player>.+) completed (?P<achievement>.+)'
```
Can reference by name in some contexts

---

### Anchors

#### Start of Line
```yaml
regex: '^\[CHAT\]'
```
Only matches if at start of line

---

#### End of Line
```yaml
regex: 'game$'
```
Only matches if at end of line

---

#### Word Boundary
```yaml
regex: '\bAdmin\b'
```
Matches "Admin" but not "Administrator"

---

### Quantifiers

#### Zero or More
```yaml
regex: 'Player.*joined'
```
Matches: `"Player joined"`, `"Player ABC joined"`

---

#### One or More
```yaml
regex: '[0-9]+'
```
Matches: `"5"`, `"42"`, `"1000"`

---

#### Optional
```yaml
regex: 'Players?'
```
Matches: `"Player"` or `"Players"`

---

#### Exact Count
```yaml
regex: '[0-9]{4}'
```
Matches exactly 4 digits

---

#### Range
```yaml
regex: '[0-9]{2,4}'
```
Matches 2-4 digits

---

### Special Cases

#### Escape Special Characters
```yaml
regex: '\[CHAT\]'  # Matches "[CHAT]"
regex: '\$100'      # Matches "$100"
regex: '\.'         # Matches "."
```

Special characters to escape: `. ^ $ * + ? { } [ ] \ | ( )`

---

#### Multiple Options
```yaml
regex: '(Admin|Moderator|Owner) joined'
```
Matches any of the three options

---

#### Case Insensitive
```yaml
regex: '(?i)admin'
```
Matches: `"Admin"`, `"ADMIN"`, `"admin"`

---

## Priority System

### How Priority Works

1. **Higher priority patterns checked first**
2. **First match wins** (processing stops)
3. **Multiple patterns** can match same line if priorities differ

---

### Priority Examples

#### Admin Events (High Priority)

```yaml
patterns:
  - name: admin_death
    regex: '(Admin|Moderator) was killed'
    priority: 100
    discord:
      channel: admin
      emoji: "🛡️"
      color: 0xFF0000

  - name: regular_death
    regex: '(.+) was killed'
    priority: 50
    discord:
      channel: deaths
      emoji: "💀"
```

`"Admin was killed"` → Matches `admin_death` (priority 100)  
`"Player was killed"` → Matches `regular_death` (priority 50)

---

#### Catch-All Pattern

```yaml
patterns:
  - name: rocket_launch
    regex: 'Rocket launched'
    priority: 90
    discord:
      emoji: "🚀"
      title: "Rocket Launched!"

  - name: generic_event
    regex: '.*'
    priority: 1
    # No discord section - just logs it
```

---

## Examples

### Chat Message

```yaml
patterns:
  - name: chat_message
    regex: '\[CHAT\] (.+?): (.+)'
    event_type: chat
    priority: 50
    fields:
      player: 1
      message: 2
    discord:
      channel: chat
      emoji: "💬"
      title: "{player}"
      description: "{message}"
```

**Matches:**
```
2024-12-01 12:00:00 [CHAT] Alice: Hello everyone!
```

**Discord Output:**
```
💬 **Alice**
Hello everyone!
```

---

### Player Join

```yaml
patterns:
  - name: player_join
    regex: '\[JOIN\] (.+) joined the game'
    event_type: join
    fields:
      player: 1
    discord:
      emoji: "🎮"
      color: 0x00FF00
      description: "{player} joined the game"
```

---

### Player Death

```yaml
patterns:
  - name: player_death
    regex: '(.+) was killed by (.+)'
    event_type: death
    priority: 80
    fields:
      player: 1
      killer: 2
    discord:
      channel: deaths
      emoji: "💀"
      color: 0xFF0000
      title: "Player Death"
      description: "{player} was killed by {killer}"
```

---

### Achievement

```yaml
patterns:
  - name: achievement_unlocked
    regex: '(.+) unlocked achievement (.+)'
    event_type: achievement
    fields:
      player: 1
      achievement: 2
    discord:
      emoji: "🏆"
      color: 0xFFD700
      title: "Achievement Unlocked!"
      description: "{player} unlocked **{achievement}**"
```

---

### Research Complete

```yaml
patterns:
  - name: research_complete
    regex: 'Technology (.+) has been researched'
    event_type: research
    fields:
      technology: 1
    discord:
      emoji: "🔬"
      color: 0x3498DB
      title: "Research Complete"
      description: "Technology **{technology}** has been researched"
```

---

### Rocket Launch

```yaml
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
```

---

### Complex Pattern (Combat Stats)

```yaml
patterns:
  - name: combat_stats
    regex: '(.+) killed: (\d+) biters, (\d+) spitters'
    event_type: achievement
    fields:
      player: 1
      biters: 2
      spitters: 3
    discord:
      emoji: "⚔️"
      color: 0xFF0000
      title: "Combat Statistics"
      description: |
        {player} eliminated:
        • {biters} biters
        • {spitters} spitters
```

---

## Best Practices

### Pattern Design

- ✅ **Be specific** - Match exactly what you need
- ✅ **Use priorities** - Prevent unintended matches
- ✅ **Test regex** - Verify patterns before deploying
- ✅ **Name clearly** - Descriptive pattern names
- ✅ **Document complex patterns** - Add comments

---

### Regex Tips

- ✅ **Escape brackets** - `\[CHAT\]` not `[CHAT]`
- ✅ **Use non-greedy** - `(.+?)` instead of `(.+)` when needed
- ✅ **Anchor when possible** - `^pattern` or `pattern$`
- ✅ **Test edge cases** - Empty strings, special characters
- ✅ **Keep it simple** - Complex regex = maintenance nightmare

---

### Field Naming

- ✅ **Use snake_case** - `player_name` not `PlayerName`
- ✅ **Be descriptive** - `killer` not `k`
- ✅ **Be consistent** - Same names across patterns
- ✅ **Match log format** - Use names that make sense

---

### Discord Formatting

- ✅ **Use emojis** - Visual clarity
- ✅ **Choose colors wisely** - Red for danger, green for success
- ✅ **Keep titles short** - 1-3 words
- ✅ **Descriptions clear** - Easy to read
- ✅ **Use markdown** - `**bold**`, `*italic*`, `` `code` ``

---

### Organization

- ✅ **One file per mod** - `vanilla.yml`, `krastorio2.yml`
- ✅ **Group related patterns** - All vehicle events together
- ✅ **Use comments** - Explain complex patterns
- ✅ **Version control** - Track pattern changes

---

### Testing

```bash
# Test regex
python -c "
import re
pattern = r'YOUR_PATTERN'
test_line = 'YOUR_TEST_LINE'
match = re.search(pattern, test_line)
print('Match:', match.groups() if match else None)
"

# Test pattern file syntax
python -m yaml patterns/your-pattern.yml

# Test with actual application
LOG_LEVEL=debug python -m src.main
```

---

## Pattern Files

### Loading Patterns

**Default:** All `.yml` files in `patterns/` directory

**Custom:**
```bash
# .env
PATTERNS_DIR=my-patterns
```

**Specific files:**
```bash
# .env
PATTERN_FILES=["vanilla.yml","my-mod.yml"]
```

---

### Pattern File Structure

```yaml
# patterns/example.yml

# Comments are allowed
patterns:
  # Pattern 1
  - name: first_pattern
    regex: 'pattern1'
    event_type: type1
    discord:
      emoji: "🎮"

  # Pattern 2
  - name: second_pattern
    regex: 'pattern2'
    event_type: type2
    discord:
      emoji: "🚀"
```

---

## Next Steps

- [Examples](EXAMPLES.md) - Common pattern scenarios
- [Multi-Channel](MULTI_CHANNEL.md) - Channel routing
- [RCON Setup](RCON_SETUP.md) - Server statistics
- [Deployment](DEPLOYMENT.md) - Production deployment

---

**Happy pattern crafting! 🎨**


> **📄 Licensing Information**
> 
> This project is open licensed:
> - **[MIT](../LICENSE)** – Open source use (free)