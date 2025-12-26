---
layout: default
title: Mentions Guide
---

# 💬 Mentions Configuration Reference

Complete guide to mapping in-game @tokens to Discord mentions using `config/mentions.yml`.

## Table of Contents
- [Overview](#overview)
- [Implementation Status](#implementation-status)
- [File Format](#file-format)
- [Structure](#structure)
- [Field Reference](#field-reference)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Testing](#testing)
- [Next Steps](#next-steps)

---

## Overview

Mentions map simple in-game tokens like `@board` or `@ops` to actual Discord mentions for roles or users during Discord message rendering.

This document describes how to define mention aliases in `config/mentions.yml` and how the bot resolves them at send time.

**Optional Feature:** `mentions.yml` is **optional**. If not provided, @mentions in Factorio chat will appear as plain text in Discord.

---

## Implementation Status

**✅ IMPLEMENTED:** Mention resolution is active in `src/bot/event_handler.py`.

- ✅ User mentions (`@alice` → `<@123456>`)
- ✅ Role mentions (`@admins` → `<@&987654>`)
- ✅ Alias resolution (`@ops` → "operations" role)
- ✅ Multiple aliases per user/role
- ✅ Case-insensitive matching

**How it works:**
1. User types `@ops` in Factorio chat
2. Event parser detects chat message
3. Event handler checks `mentions.yml` for `ops` alias
4. Resolves to Discord role ID and formats as `<@&ROLE_ID>`
5. Discord pings the role when message is sent

---

## File Format

Mentions are defined in YAML under a top-level `mentions` section.

Place the file at `./config/mentions.yml`.

```yaml
# config/mentions.yml
mentions:
  alice:
    type: user
    discord_id: 123456789012345678
    aliases:
      - alice
      - Alice
      - alicesmith

  bob:
    type: user
    discord_id: 234567890123456789
    aliases:
      - bob
      - Bob
      - bobby

  admins:
    type: role
    discord_id: 987654321098765432
    aliases:
      - admins
      - admin
      - moderators
      - mods

  board_of_directors:
    type: role
    discord_id: 111222333444555666
    aliases:
      - board
      - board-of-directors
      - directors
```

---

## Structure

- **`mentions`**: Root key for all mention configuration
- **Mention key** (e.g., `alice`, `admins`): Internal identifier (can be anything)
- **`type`**: Either `user` or `role`
- **`discord_id`**: Discord user ID or role ID (snowflake)
- **`aliases`**: List of in-game tokens that map to this mention

---

## Field Reference

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|----------|
| `type` | `user` or `role` | Type of mention | `user` |
| `discord_id` | Integer (snowflake) | Discord user/role ID | `123456789012345678` |
| `aliases` | List of strings | In-game tokens | `["alice", "Alice"]` |

### Getting Discord IDs

**For Users:**
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click user → Copy ID

**For Roles:**
1. Enable Developer Mode
2. Server Settings → Roles → Right-click role → Copy ID

---

## Examples

### Example 1: User Mentions

**Config:**
```yaml
mentions:
  alice:
    type: user
    discord_id: 123456789012345678
    aliases: ["alice", "Alice"]
```

**Factorio Chat:**
```
[CHAT] Bob: Hey @alice, check the oil refinery!
```

**Discord Output:**
```
[vanilla] 💬 Bob: Hey <@123456789012345678>, check the oil refinery!
```

**Result:** Alice gets pinged in Discord.

---

### Example 2: Role Mentions

**Config:**
```yaml
mentions:
  admins:
    type: role
    discord_id: 987654321098765432
    aliases: ["admins", "admin", "mods"]
```

**Factorio Chat:**
```
[CHAT] Charlie: @admins there's a griefer on the server!
```

**Discord Output:**
```
[vanilla] 💬 Charlie: <@&987654321098765432> there's a griefer on the server!
```

**Result:** Everyone with the "admins" role gets pinged.

---

### Example 3: Multiple Aliases

**Config:**
```yaml
mentions:
  operations:
    type: role
    discord_id: 111222333444555666
    aliases:
      - ops
      - operations
      - operations-team
```

**Factorio Chat:**
```
[CHAT] Dana: @ops need help at the uranium patch
```

**Discord Output:**
```
[modded] 💬 Dana: <@&111222333444555666> need help at the uranium patch
```

**Result:** `@ops`, `@operations`, and `@operations-team` all resolve to the same role.

---

## Best Practices

1. **Short, memorable aliases**: Use `ops`, `board`, `chiefs` instead of long names
2. **Include case variants**: Add both `alice` and `Alice` for case-insensitive matching
3. **Avoid conflicts**: Don't use the same alias for multiple users/roles
4. **Test before deploying**: Use a test Discord server to verify mentions work
5. **Document for players**: Tell players what aliases are available (e.g., "Use @ops for operations team")

---

## Testing

### Manual Testing

1. **Type in Factorio chat:**
   ```
   @ops help at oil refinery
   ```

2. **Check Discord for:**
   - Message appears with `<@&ROLE_ID>` mention
   - Role members get pinged

3. **Check logs for:**
   ```
   mentions_detected: ["ops"]
   mention_resolved_to_role: ops -> 111222333444555666
   ```

### Troubleshooting

**Mentions not working?**
1. Verify `mentions.yml` exists in `config/`
2. Check YAML syntax: `python -c "import yaml; yaml.safe_load(open('config/mentions.yml'))"`
3. Verify Discord IDs are correct (18-digit snowflakes)
4. Check bot has "Mention Everyone" permission (for role mentions)
5. Enable debug logging: `LOG_LEVEL=debug`

---

## Next Steps

- See [Configuration Guide](configuration.md) for all `mentions.yml` options
- See [Patterns](PATTERNS.md) for how chat events are parsed
- See [Troubleshooting](TROUBLESHOOTING.md) for diagnosing mention issues

---

> **📄 Licensing Information**
> 
> This project is open licensed:
> - **[MIT](../LICENSE)** – Open source use (free)