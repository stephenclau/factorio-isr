# 🗼Architecture Guide

Overview of Factorio ISR system design and extensibility.

## System Components

- **Log Tailer**: Monitors Factorio server log file and emits new events line-by-line.
- **Event Parser**: Uses regex patterns to extract JOIN/LEAVE/CHAT, mod events, tasks, deaths, research.
- **Discord Client**: Formats events and sends messages via webhook (future: full Discord bot).
- **Health Monitor**: HTTP endpoint for container orchestration (e.g., Docker health checks).
- **Configuration Loader**: Reads config from env/Docker secrets/YAML.

## Event Flow Diagram

```text
[Factorio Console Log] → [Log Tailer] → [Event Parser] → [Discord Client] → [Discord Channel]
```

## Design Decisions

- **Containerized**: Everything runs as a non-root user for security.
- **Stateless**: No database; all state is sourced from logs.
- **Extensible**: Patterns via YAML and regex; can support new mods/events.
- **Pluggable**: Future phases allow RCON client and admin commands.

## Extension Points

- Add new event patterns in the event parser.
- Extend health monitor for Prometheus.
- Replace webhook with Discord bot for advanced features.

## Phase Roadmap

| Phase | Description |
|-------|-------------|
| 1     | Passive log watcher MVP (JOIN, LEAVE, CHAT, mod tasks) |
| 2     | Enhanced parsing (custom YAML, filters) |
| 3     | Add RCON client (read only) |
| 4     | Discord bot, slash commands |
| 5     | Write commands/admin features |

See [Roadmap](roadmap.md) for more.