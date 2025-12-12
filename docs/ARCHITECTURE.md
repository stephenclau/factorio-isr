# Discord Bot Architecture - Visual Guide

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     main.py (Application)                   │
│   - Loads config                                            │
│   - Initializes Application                                 │
│   - Manages lifecycle                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              discord_interface.py                           │
│   BotDiscordInterface (wraps DiscordBot)                    │
│   - Creates bot instance                                    │
│   - Connects to Discord                                     │
│   - Forwards events to bot                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          discord_bot_refactored.py                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ DiscordBot(discord.Client)                           │  │
│  │ - Coordinates modular components                     │  │
│  │ - Handles lifecycle (connect, disconnect, ready)     │  │
│  │ - Delegates concerns to specialized modules          │  │
│  └──┬────────────────────────────────────────────────┬──┘  │
│     │                                                │      │
│     ▼                                                ▼      │
│  ┌─────────────────┐    ┌─────────────────────────────┐   │
│  │ user_context:   │    │ presence_manager:          │   │
│  │ UserContextMgr  │    │ PresenceManager            │   │
│  │                 │    │                            │   │
│  │ • get_user_     │    │ • update() - updates bot   │   │
│  │   server()      │    │   presence based on RCON   │   │
│  │ • set_user_     │    │   connection status        │   │
│  │   server()      │    └─────────────────────────────┘   │
│  │ • get_rcon_for_ │                                      │
│  │   user()        │                                      │
│  │ • get_server_   │                                      │
│  │   display_name()│                                      │
│  └─────────────────┘                                      │
│     │                                                      │
│     ├──────────────────────────────────────────────────┐  │
│     │                                                  │  │
│     ▼                                                  ▼  │
│  ┌──────────────────────┐       ┌──────────────────────┐ │
│  │ event_handler:       │       │ rcon_monitor:        │ │
│  │ EventHandler         │       │ RconMonitor          │ │
│  │                      │       │                      │ │
│  │ • send_event() -     │       │ • start() - starts   │ │
│  │   routes to channel  │       │   monitoring loop    │ │
│  │ • mention resolution │       │ • stop() - stops     │ │
│  │   (users, roles)     │       │   monitoring loop    │ │
│  │ • config loading     │       │ • per-server state   │ │
│  │   from mentions.yml  │       │   tracking           │ │
│  │                      │       │ • status change      │ │
│  │                      │       │   handlers           │ │
│  │                      │       │ • breakdown embeds   │ │
│  └──────────────────────┘       └──────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
┌──────────────────────────────┐   ┌──────────────────────┐
│   bot/commands/factorio.py   │   │  config.py           │
│                              │   │                      │
│  register_factorio_commands()│   │ • ServerConfig       │
│  - Registers /factorio group │   │ • load_config()      │
│  - 17/25 subcommands        │   │ • validate_config()  │
│                              │   │                      │
│  Multi-Server (2):           │   │  Servers from:       │
│  ├─ /factorio servers        │   │  • servers.yml       │
│  └─ /factorio connect        │   │  • env vars          │
│                              │   │  • Docker secrets    │
│  Server Info (7):            │   │                      │
│  ├─ /factorio status         │   └──────────────────────┘
│  ├─ /factorio players        │
│  ├─ /factorio version        │   ┌──────────────────────┐
│  ├─ /factorio seed           │   │ server_manager.py    │
│  ├─ /factorio evolution      │   │                      │
│  ├─ /factorio admins         │   │ • ServerManager      │
│  └─ /factorio health         │   │ • multi-server RCON  │
│                              │   │ • status tracking    │
│  Player Mgmt (7):            │   │ • stats collection   │
│  ├─ /factorio kick           │   │                      │
│  ├─ /factorio ban            │   └──────────────────────┘
│  ├─ /factorio unban          │
│  ├─ /factorio mute           │   ┌──────────────────────┐
│  ├─ /factorio unmute         │   │ Discord             │
│  ├─ /factorio promote        │   │                      │
│  └─ /factorio demote         │   │ • Text channels      │
│                              │   │ • Guild roles        │
│  Server Mgmt (4):            │   │ • Members           │
│  ├─ /factorio save           │   │                      │
│  ├─ /factorio broadcast      │   └──────────────────────┘
│  ├─ /factorio whisper        │
│  └─ /factorio whitelist      │   ┌──────────────────────┐
│                              │   │ Factorio Servers    │
│  Game Control (3):           │   │                      │
│  ├─ /factorio time           │   │ • Log files          │
│  ├─ /factorio speed          │   │ • RCON sockets       │
│  └─ /factorio research       │   │ • Game state         │
│                              │   │                      │
│  Advanced (2):               │   └──────────────────────┘
│  ├─ /factorio rcon           │
│  └─ /factorio help           │
│                              │
└──────────────────────────────┘
```

## Data Flow Diagrams

### 1. Command Execution Flow

```
Discord User
    │
    │ Types: /factorio status
    ▼
Discord API
    │
    │ Slash command interaction
    ▼
DiscordBot.on_interaction()
    │
    │ Routes to /factorio group
    ▼
statatus_command(interaction)
    │
    ├─ Check rate limit
    │
    ├─ Get user's server context
    │   └─ user_context.get_user_server(user_id) -> "prod"
    │
    ├─ Get user's RCON client
    │   └─ user_context.get_rcon_for_user(user_id) -> RconClient
    │
    ├─ Query RCON
    │   ├─ rcon_client.get_players() -> ["Alice", "Bob"]
    │   └─ helpers.get_game_uptime(rcon_client) -> "2h 15m"
    │
    ├─ Build embed
    │   └─ EmbedBuilder.create_base_embed(...)
    │
    └─ Send response
        └─ interaction.followup.send(embed=embed)
```

### 2. Event Delivery Flow

```
Factorio Log Entry
    │
    │ "[0.123] Alice joined the game"
    ▼
log_tailer.handle_log_line(line, server_tag="prod")
    │
    ▼
EventParser.parse_line(line, server_tag="prod")
    │
    ├─ Match against patterns
    ├─ Extract metadata
    └─ Return FactorioEvent or None
        │
        ▼
    FactorioEvent(event_type=JOIN, player_name="Alice", server_tag="prod")
        │
        ▼
DiscordBot.send_event(event)
    │
    ├─ Delegate to event_handler
    │
    ▼
EventHandler.send_event(event)
    │
    ├─ Get target channel
    │   └─ _get_channel_for_event(event) -> ServerConfig.event_channel_id
    │
    ├─ Format message
    │   └─ FactorioEventFormatter.format_for_discord(event) -> markdown string
    │
    ├─ Resolve mentions
    │   └─ _resolve_mentions(guild, ["@admins"]) -> ["@Role:Admins"]
    │
    └─ Send to Discord
        └─ channel.send(message + mentions)
```

### 3. RCON Monitoring Flow

```
RconMonitor._monitor_rcon_status()
    │
    │ Loop every 5 seconds
    ▼
server_manager.get_status_summary() -> {"prod": True, "staging": False}
    │
    ├─ For each server:
    │   └─ Handle status change
    │       ├─ Detect transition (connected -> disconnected)
    │       └─ If changed:
    │           ├─ Send disconnect notification
    │           │   └─ _notify_rcon_disconnected("prod")
    │           │       └─ channel.send(embed with warning)
    │           │
    │           └─ Send reconnect notification
    │               └─ _notify_rcon_reconnected("prod")
    │                   └─ channel.send(embed with success + downtime)
    │
    ├─ Check breakdown schedule
    │   ├─ Mode = "transition" -> send on status change
    │   └─ Mode = "interval" -> send every N seconds
    │       └─ _send_breakdown_embeds()
    │           ├─ Build embed with all server statuses
    │           └─ Send to global + per-server channels
    │
    ├─ Update presence
    │   └─ presence_manager.update()
    │       ├─ Calculate connected/total count
    │       └─ Update bot activity ("🟢 RCON (2/3) | /factorio help")
    │
    └─ Repeat
```

## Module Dependencies

```
DiscordBot
    ├─ depends on: UserContextManager
    │  └─ provides: get_user_server(), set_user_server(), get_rcon_for_user()
    │
    ├─ depends on: PresenceManager
    │  └─ provides: update()
    │
    ├─ depends on: EventHandler
    │  └─ provides: send_event()
    │  └─ depends on: ServerManager, EmbedBuilder, FactorioEventFormatter
    │
    ├─ depends on: RconMonitor
    │  └─ provides: start(), stop()
    │  └─ depends on: ServerManager, EmbedBuilder
    │
    └─ depends on: register_factorio_commands()
       └─ provides: /factorio slash command group
       └─ depends on: UserContextManager, RCON clients, EmbedBuilder
```

## Type Safety

### Key Type Hints

```python
# User context
def get_user_server(self, user_id: int) -> str:
    ...

def get_rcon_for_user(self, user_id: int) -> Optional[Any]:
    ...

# Event handling
async def send_event(self, event: FactorioEvent) -> bool:
    ...

# RCON monitoring
async def _handle_server_status_change(self, server_tag: str, current_status: bool) -> bool:
    ...

# Presence
class PresenceManager:
    async def update(self) -> None:
        ...
```

## Configuration Flow

```
config.py
    │
    ├─ load_config() -> Config
    │  └─ Reads from:
    │     ├─ config/servers.yml (ServerConfig[])
    │     ├─ Environment variables
    │     ├─ Docker secrets (/run/secrets/*)
    │     └─ Defaults
    │
    ├─ ServerConfig (per-server)
    │  ├─ tag: str ("prod", "staging")
    │  ├─ name: str ("Production", "Staging")
    │  ├─ rcon_host: str ("localhost")
    │  ├─ rcon_port: int (27015)
    │  ├─ rcon_password: str (loaded from secrets)
    │  ├─ event_channel_id: int (Discord channel)
    │  ├─ rcon_breakdown_mode: str ("transition" | "interval")
    │  └─ rcon_breakdown_interval: int (seconds)
    │
    └─ ServerManager
       └─ Creates RconClient per server
```

## Execution Context

### Single Async Event Loop

```
DiscordBot
    ├─ connect_bot() - async
    │  ├─ login() to Discord
    │  └─ start monitoring tasks
    │
    ├─ _monitor_rcon_status() - background task (asyncio.create_task)
    │  └─ Runs loop every 5 seconds while _connected
    │
    ├─ on_ready() - event handler
    │  └─ Called when bot ready
    │
    ├─ on_interaction() - event handler
    │  └─ Routes slash commands
    │
    └─ disconnect_bot() - async cleanup
       ├─ Cancel monitoring task
       └─ Close connection to Discord
```

## Error Handling Strategy

```
All async operations:
    ├─ Try/Except block
    ├─ Log error with context
    ├─ Return error embed to user
    └─ Never crash the bot

RCON operations:
    ├─ Timeout protection
    ├─ Connection validation
    ├─ Response parsing validation
    └─ Graceful degradation

Discord operations:
    ├─ Handle Forbidden (no permissions)
    ├─ Handle HTTPException (network)
    ├─ Handle NotFound (channel/user deleted)
    └─ Log all failures for debugging
```

---

## For More Information

- **Implementation details:** See docstrings in `src/bot/*.py`
- **Command patterns:** See `src/bot/commands/factorio.py`
- **Integration:** See `REFACTORING_GUIDE.md`
- **Quick start:** See `REFACTOR_SUMMARY.md`
