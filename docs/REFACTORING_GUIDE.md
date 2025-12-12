# Discord Bot Refactoring Guide

**Branch:** `refactor/discord-bot-modular`

**Status:** Phase 1-5 Complete (Structure and Core Modules) | Phase 6 In Progress (Command Implementation)

---

## Overview

This refactoring breaks down the monolithic `discord_bot.py` (1,715 lines) into a **modular architecture** that:

✅ **Maintains 100% API compatibility** - No changes required to `main.py` or `config.py`
✅ **Respects Discord's 25 subcommand limit** - Single `/factorio` command file
✅ **Improves maintainability** - Clear separation of concerns
✅ **Enables better testing** - Isolated, mockable components
✅ **Scales elegantly** - Easy to add new features

---

## Architecture

### Directory Structure

```
src/
├── discord_bot.py (ORIGINAL - untouched for now)
├── discord_bot_refactored.py (NEW - ~300 lines, delegating coordinator)
│
└── bot/  (NEW DIRECTORY)
    ├── __init__.py
    ├── user_context.py     (100 lines) - Per-user server context
    ├── helpers.py          (150 lines) - Utilities & presence
    ├── event_handler.py    (300 lines) - Event sending & mentions
    ├── rcon_monitor.py     (400 lines) - RCON status monitoring
    │
    └── commands/
        ├── __init__.py
        └── factorio.py     (850 lines) - ALL /factorio subcommands (17/25)
```

### Component Responsibilities

| Module | Responsibility | Lines |
|--------|---|---|
| `user_context.py` | Per-user server context tracking, RCON client routing | 100 |
| `helpers.py` | Presence management, uptime formatting, channel utilities | 150 |
| `event_handler.py` | Event delivery, mention resolution, channel routing | 300 |
| `rcon_monitor.py` | Connection status monitoring, notifications, breakdown embeds | 400 |
| `commands/factorio.py` | All /factorio slash commands (17/25 available) | 850 |
| `discord_bot_refactored.py` | Bot lifecycle, coordination, public API | 300 |
| **TOTAL** | | **2,100 lines** (+5% for documentation/structure) |

---

## Key Design Decisions

### 1. Single Command File (`bot/commands/factorio.py`)

**Why not 6 separate files?**

Discord enforces a **25 subcommand-per-group maximum**. We currently have 17 commands:
- Multi-Server: 2 (servers, connect)
- Server Information: 7 (status, players, version, seed, evolution, admins, health)
- Player Management: 7 (kick, ban, unban, mute, unmute, promote, demote)
- Server Management: 4 (save, broadcast, whisper, whitelist)
- Game Control: 3 (time, speed, research)
- Advanced: 2 (rcon, help)

**Benefits:**
- All commands register under one `app_commands.Group`
- Single source of truth for capacity tracking (17/25)
- Organized with section headers (Multi-Server, Player Management, etc.)
- Easy to see at a glance what's at capacity
- No artificial file boundaries

### 2. Modular Components (Composition over Inheritance)

```python
class DiscordBot(discord.Client):
    def __init__(self, ...):
        self.user_context = UserContextManager(bot=self)
        self.presence_manager = PresenceManager(bot=self)
        self.event_handler = EventHandler(bot=self)
        self.rcon_monitor = RconMonitor(bot=self)
```

**Benefits:**
- Each component has a single responsibility
- Easy to test components independently
- Clear interfaces between components
- Future-proof for dependency injection

### 3. Zero Breaking Changes

The refactored `DiscordBot` class:
- ✅ Same `__init__` signature
- ✅ Same public methods (`send_event`, `set_server_manager`, `set_event_channel`)
- ✅ Same attributes (`user_context` added, but old inline methods removed)
- ✅ Same integration points with `main.py`

**Migration path:** Simply swap `from discord_bot_refactored import DiscordBot`

---

## Implementation Phases

### Phase 1 ✅ (Complete) - Directory Structure
- Create `src/bot/` directory
- Create `src/bot/commands/` directory
- Add `__init__.py` files

### Phase 2 ✅ (Complete) - Extract Helpers
- Move utility functions to `bot/helpers.py`
- Create `PresenceManager` class
- Update imports in refactored bot

### Phase 3 ✅ (Complete) - Extract User Context
- Create `UserContextManager` class in `bot/user_context.py`
- Methods: `get_user_server()`, `set_user_server()`, `get_rcon_for_user()`, `get_server_display_name()`
- Test multi-server context switching

### Phase 4 ✅ (Complete) - Extract Event Handler
- Create `EventHandler` class in `bot/event_handler.py`
- Methods: `send_event()`, mention resolution, channel routing
- Load mention config from `config/mentions.yml`

### Phase 5 ✅ (Complete) - Extract RCON Monitor
- Create `RconMonitor` class in `bot/rcon_monitor.py`
- Methods: `start()`, `stop()`, monitoring loop, status tracking
- Per-server state management and notifications
- Breakdown embed generation

### Phase 6 🚧 (In Progress) - Extract Commands

**Current Status:** Template structure with 4/17 commands implemented
- ✅ `/factorio servers` - List available servers
- ✅ `/factorio connect` - Switch to a server
- ✅ `/factorio status` - Show server status (template)
- ✅ `/factorio help` - Show help message

**Remaining (Outlined):**
- `/factorio players` - List online players
- `/factorio version` - Show Factorio version
- `/factorio seed` - Show map seed
- `/factorio evolution` - Show biter evolution
- `/factorio admins` - List admins
- `/factorio health` - Check health status
- Player management commands (kick, ban, unban, mute, unmute, promote, demote)
- Server management commands (save, broadcast, whisper, whitelist)
- Game control commands (time, speed, research)
- Advanced commands (rcon)

**Pattern:** Each command in `factorio.py` follows:
```python
@factorio_group.command(name="...", description="...")
@app_commands.describe(param1="...", param2="...")
async def command_name(interaction: discord.Interaction, param1: str, ...) -> None:
    """Implementation."""
    ...
```

### Phase 7 🔜 (Not Started) - Cleanup & Validation
- Remove old inline code from `discord_bot.py`
- Run full integration test suite
- Verify all tests pass with 91%+ coverage
- Commit final refactored version

---

## Integration Points

### `main.py` (NO CHANGES)

```python
from discord_interface import DiscordInterfaceFactory

self.discord = DiscordInterfaceFactory.create_interface(self.config)
await self.discord.connect()
```

Still works exactly the same. `DiscordInterfaceFactory` returns `BotDiscordInterface` which wraps the refactored `DiscordBot`.

### `config.py` (NO CHANGES)

```python
from config import ServerConfig, load_config, validate_config
```

Server configuration unchanged. Per-server breakdown settings still loaded from `servers.yml`.

### `discord_interface.py` (MINIMAL CHANGES)

The `BotDiscordInterface` class may need to be updated to use:
```python
self.bot = DiscordBotFactory.create_bot(token)
```

Instead of the old import. Full backward compatibility is maintained.

---

## Command Implementation Pattern

Each command in `bot/commands/factorio.py` follows this pattern:

### Example: `/factorio status`

```python
@factorio_group.command(name="status", description="Show Factorio server status")
async def status_command(interaction: discord.Interaction) -> None:
    """Get comprehensive server status with rich embed."""
    # 1. Check rate limit
    is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
    if is_limited:
        embed = EmbedBuilder.cooldown_embed(retry)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # 2. Defer response (defer allows up to 15 minute timeout)
    await interaction.response.defer()

    # 3. Get user's server context
    server_tag = bot.user_context.get_user_server(interaction.user.id)
    server_name = bot.user_context.get_server_display_name(interaction.user.id)

    # 4. Get user's RCON client
    rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)
    if rcon_client is None or not rcon_client.is_connected:
        embed = EmbedBuilder.error_embed(f"RCON not available for {server_name}.")
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # 5. Execute RCON queries
    try:
        players = await rcon_client.get_players()
        uptime = await get_game_uptime(rcon_client)
        # ... build embed ...
        await interaction.followup.send(embed=embed)
        logger.info("status_command_executed", user=interaction.user.name)
    except Exception as e:
        embed = EmbedBuilder.error_embed(f"Failed to get status: {str(e)}")
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error("status_command_failed", error=str(e))
```

**Key elements:**
- Cooldown check (QUERY_COOLDOWN, ADMIN_COOLDOWN, or DANGER_COOLDOWN)
- Deferred response (allows long-running RCON queries)
- User context lookup via `bot.user_context`
- RCON client retrieval via `bot.user_context.get_rcon_for_user()`
- Error handling and logging
- Rich embeds via `EmbedBuilder`

---

## Testing Strategy

### Unit Tests

Each module has a clear testing boundary:

```python
# test_user_context.py
from bot.user_context import UserContextManager

def test_user_context_defaults_to_first_server():
    bot = MockBot(servers=["prod", "staging"])
    mgr = UserContextManager(bot)
    assert mgr.get_user_server(123) == "prod"

# test_helpers.py
from bot.helpers import format_uptime
from datetime import timedelta

def test_format_uptime():
    assert format_uptime(timedelta(seconds=45)) == "< 1m"
    assert format_uptime(timedelta(seconds=90)) == "1m"
    assert format_uptime(timedelta(hours=2, minutes=15)) == "2h 15m"

# test_event_handler.py
from bot.event_handler import EventHandler

async def test_send_event_routes_to_correct_channel():
    bot = MockBot(server_manager=MockManager())
    handler = EventHandler(bot)
    event = FactorioEvent(server_tag="prod", ...)
    result = await handler.send_event(event)
    assert result is True

# test_rcon_monitor.py
from bot.rcon_monitor import RconMonitor

async def test_rcon_monitor_detects_disconnection():
    bot = MockBot(server_manager=MockManager())
    monitor = RconMonitor(bot)
    # ... simulate status change ...
    assert len(bot.notifications) == 1
    assert "Disconnected" in bot.notifications[0]
```

### Integration Tests

```python
# test_discord_bot_refactored.py
from discord_bot_refactored import DiscordBot, DiscordBotFactory

async def test_bot_lifecycle():
    """Test bot connect, ready, disconnect cycle."""
    bot = DiscordBotFactory.create_bot(token="test")
    assert bot.user_context is not None
    assert bot.event_handler is not None
    assert bot.rcon_monitor is not None

async def test_command_registration():
    """Test that all /factorio commands register."""
    bot = DiscordBotFactory.create_bot(token="test")
    await bot.setup_hook()
    
    # Get /factorio group
    factorio_cmd = bot.tree.get_commands()[0]
    assert factorio_cmd.name == "factorio"
    assert len(factorio_cmd.commands) == 17  # Current count
```

### Coverage Target

- **Current:** 91%+ (existing tests)
- **After refactor:** Maintain or improve
- **Method:** Isolated unit tests + integration tests

---

## Migration Checklist

### Before Merging

- [ ] All Phase 1-5 modules created and committed
- [ ] Phase 6 commands template complete with 4+ commands implemented
- [ ] Import paths verified (both package and flat layouts)
- [ ] Type hints applied to all new code
- [ ] Docstrings added to all public methods
- [ ] Logging calls match original patterns
- [ ] New modules tested independently
- [ ] Integration tests pass
- [ ] Code coverage ≥ 91%
- [ ] Linting passes (mypy, black, pylint)

### During Phase 7 (Final Cleanup)

- [ ] Verify `discord_bot_refactored.py` works as drop-in replacement
- [ ] Update `discord_interface.py` to import from refactored version
- [ ] Remove old inline code from `discord_bot.py` OR rename to backup
- [ ] Run full application test suite
- [ ] Test with actual Discord bot in staging
- [ ] Verify all 17 commands work end-to-end
- [ ] Create PR with detailed description
- [ ] Code review and approval
- [ ] Merge to main

---

## Benefits Summary

### For Developers
- 🎯 **Clear ownership** - Each module handles one concern
- 🧪 **Easy testing** - Isolated components, minimal mocking
- 🔄 **Easy refactoring** - Change one module without affecting others
- 📚 **Better documentation** - Clear file structure, section headers

### For Maintainers
- 🚀 **Faster feature addition** - Add commands to `factorio.py` without touching lifecycle code
- 🐛 **Easier debugging** - Issues localized to specific modules
- 📊 **Better metrics** - Lines per file stay reasonable (~300-900)
- ⚙️ **Scalability** - Can grow to 25 commands without file explosion

### For Operations
- 🔍 **Clearer logs** - Module-specific logging context
- 📈 **Better monitoring** - Separate concerns mean separate metrics
- 🛡️ **Safer deployments** - Smaller, focused changes per PR

---

## References

- **Original discord_bot.py:** `src/discord_bot.py` (1,715 lines)
- **Refactored version:** `src/discord_bot_refactored.py` (300 lines)
- **Module structure:** `src/bot/` directory
- **Command registry:** `src/bot/commands/factorio.py` (850 lines)
- **Discord.py API:** https://discordpy.readthedocs.io/
- **Discord slash commands:** https://discordpy.readthedocs.io/en/stable/interactions/api.html

---

## Questions?

Refer to the inline documentation in each module:
- `bot/__init__.py` - Package overview
- `bot/user_context.py` - User context management
- `bot/helpers.py` - Utilities
- `bot/event_handler.py` - Event delivery
- `bot/rcon_monitor.py` - Monitoring
- `bot/commands/factorio.py` - Command structure (17/25)

Each file has detailed docstrings and type hints for quick reference.
