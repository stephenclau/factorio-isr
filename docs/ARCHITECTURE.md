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
┌────────────────────┴────────────────────────────────────────┐
│              discord_interface.py                           │
│   - BotDiscordInterface (wraps DiscordBot)                  │
│   - Creates bot instance & connects to Discord              │
│   - Forwards events to bot                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────┴────────────────────────────────────────┐
│                  discord_bot.py (Orchestrator)              │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ DiscordBot(discord.Client)                           │  │
│  │ - Handles Discord lifecycle (on_ready, on_interaction) │  │
│  │ - Registers slash commands                           │  │
│  │ - Delegates all logic to specialized managers        │  │
│  └──┬──────────────────┬───────────────────────────────┘  │
│     │                  │                                    │
│     ▼                  ▼                                    │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │ user_context.py │  │ presence_manager.py             │   │
│  │ UserContextMgr  │  │ PresenceManager                 │   │
│  │                 │  │                                 │   │
│  │• get_user_server│  │• update() - sets bot activity   │   │
│  │• set_user_server│  │  based on server RCON status    │   │
│  │• get_rcon_for_   │  │                                 │   │
│  │  user           │  └─────────────────────────────────┘   │
│  └─────────────────┘                                        │
│           │                                                   │
│           └───────────┐                                       │
│                       ▼                                       │
│  ┌────────────────────┴───────────────────────────────────┐ │
│  │                   server_manager.py                     │ │
│  │ ServerManager                                           │ │
│  │ - Master controller for all Factorio server interactions│ │
│  │ - Initializes, starts, and stops all RCON clients     │ │
│  │ - Aggregates status for presence and health checks      │ │
│  │                                                         │ │
│  │ ┌────────────────────┬───────────────────┬──────────┐ │ │
│  │ │ rcon_client.py     │ rcon_alert_monitor│ rcon_... │ │ │
│  │ │ RconClient         │ .py               │          │ │ │
│  │ │ • Pure protocol    │ • UPS alerts      │          │ │ │
│  │ └────────────────────┴───────────────────┴──────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
┌──────────────────────────────┐   ┌──────────────────────┐
│   bot/commands/factorio.py   │   │  config.py           │
│                              │   │                      │
│  register_factorio_commands()│   │ • ServerConfig       │
│  - All 25 slash commands     │   │ • load_config()      │
│  - Self-contained enclosures │   │                      │
│                              │   │  Servers from:       │
│  Multi-Server (2):           │   │  • servers.yml       │
│  ├─ /factorio servers        │   │  • env vars          │
│  └─ /factorio connect        │   │  • Docker secrets    │
│                              │   │                      │
│  Server Info (7):            │   └──────────────────────┘
│  ├─ /factorio status         │
│  ├─ /factorio players        │   ┌──────────────────────┐
│  ├─ /factorio version        │   │ rcon_modules         │
│  ├─ /factorio seed           │   │                      │
│  ├─ /factorio evolution      │   │ • rcon_client.py     │
│  ├─ /factorio admins         │   │ • rcon_metrics_engine│
│  └─ /factorio health         │   │ • rcon_stats_collector
│                              │   │ • rcon_alert_monitor │
│  Player Mgmt (7):            │   │                      │
│  ├─ /factorio kick           │   └──────────────────────┘
│  ├─ /factorio ban            │
│  ├─ /factorio unban          │
│  ├─ /factorio mute           │
│  ├─ /factorio unmute         │
│  ├─ /factorio promote        │
│  └─ /factorio demote         │
│                              │
│  ...and 8 more...            │
└──────────────────────────────┘
```

## Data Flow Diagrams

### 1. Command Execution Flow (Discrete Enclosure Pattern)

```
Discord User
    │
    │ Types: /factorio status
    ▼
Discord API (Interaction)
    │
    ▼
discord_bot.on_interaction() -> status_command(interaction)
    │
    ├─ 1. Check Rate Limit
    │
    ├─ 2. Defer Response
    │
    ├─ 3. Get User Context (RCON Client)
    │   └─ user_context.get_rcon_for_user(user_id) -> RconClient
    │
    ├─ 4. Execute RCON Command
    │   └─ rcon_client.execute("/players") -> "Players: Alice, Bob"
    │
    ├─ 5. Parse Response (Inline)
    │   └─ Parse player names from string
    │
    ├─ 6. Format Embed
    │   └─ EmbedBuilder.success_embed(...)
    │
    └─ 7. Send Response
        └─ interaction.followup.send(embed=embed)
```

### 2. RCON Monitoring & Alerting Flow

```
ServerManager.start()
    │
    │ For each server in config:
    ├─> 1. Create RconClient instance
    │
    ├─> 2. Start RconAlertMonitor (if enabled)
    │      │
    │      │ Loop every [alert_interval] seconds:
    │      └─> rcon_client.get_ups() -> 25.0
    │          │
    │          │ If UPS < threshold:
    │          └─> discord_interface.send_alert(embed)
    │
    └─> 3. Start RconStatsCollector (if enabled)
           │
           │ Loop every [stats_interval] seconds:
           └─> rcon_metrics_engine.get_all_metrics() -> Stats
               │
               │ Format with format_stats_embed()
               └─> discord_interface.send_stats(embed)
```

## Module Dependencies (Post-Refactor)

```
main.py
 └─ Application
    └─ discord_interface.py (BotDiscordInterface)
       └─ discord_bot.py (DiscordBot)
          ├─ depends on: user_context.py (UserContextManager)
          ├─ depends on: presence_manager.py (PresenceManager)
          │  └─ depends on: server_manager.py
          │
          ├─ depends on: server_manager.py (ServerManager)
          │  └─ depends on: RCON Modules
          │     ├─ rcon_client.py
          │     ├─ rcon_metrics_engine.py
          │     ├─ rcon_stats_collector.py
          │     └─ rcon_alert_monitor.py
          │
          └─ depends on: bot/commands/factorio.py
             └─ depends on: user_context.py, EmbedBuilder
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
    │  ├─ tag, name, log_path
    │  ├─ rcon_host, rcon_port, rcon_password
    │  ├─ discord_channel_id
    │  ├─ enable_stats_collector: bool (NEW)
    │  ├─ enable_ups_stat: bool (NEW)
    │  └─ enable_evolution_stat: bool (NEW)
    │
    └─ ServerManager
       └─ Creates RconClient per server based on config
```

---

## For More Information

- **Implementation details:** See docstrings in `src/rcon/` and `src/bot/`
- **Command patterns:** See `src/bot/commands/factorio.py`
- **Integration:** See `REFACTORING_GUIDE.md`
- **Quick start:** See `REFACTOR_SUMMARY.md`
