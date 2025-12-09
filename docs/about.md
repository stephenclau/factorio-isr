---
layout: default
title: About
---

# About

The Factorio ISR project is now a pretty sophisticated, multi-phase Factorio–Discord control plane with production-ready monitoring, metrics, and bot UX woven together into one coherent system.

## Core capabilities
***Discord integration is first-class:*** A fully async DiscordBot with proper login/connect lifecycle, robust connectbot/disconnectbot semantics, and a working integration test that proves real-token connectivity to Discord.​

***Unified control surface:*** The bot exposes a single top-level factorio slash command implemented as an appcommands.Group, giving you subcommands like ping, status, players, help, ban, kick, unban, save, and rcon as the canonical entry point into server control.

## Server monitoring & metrics
***UPS-aware stats pipeline:*** The RCON side now includes a RconStatsCollector and UPSCalculator that sample tick deltas to compute accurate UPS, enrich periodic stats snapshots, and push them to Discord with both embed and plaintext fallbacks.​

***Smart performance alerting:*** A RconAlertMonitor runs per server, with configurable intervals, thresholds, consecutive-sample logic, and cooldowns; it raises low-UPS alerts and recovery notifications using structured embeds and sensible throttling.

## Multi‑server & configuration
***ServerManager orchestration:*** ServerManager now manages RCON clients, stats collectors, and alert monitors per server, with helpers like get_alert_states and stop_all to cleanly coordinate shutdown.​

***Richer servers.yml / config:*** ServerConfig has grown into a real tuning panel: per-server flags for collect_ups, collect_evolution, enable_alerts, polling intervals, UPS warning/recovery thresholds, and alert cooldowns, all with backwards-compatible defaults.


## Discord UX and command syncing
Slash commands that feel “native”: The bot uses appcommands.Group("factorio", ...) so users type factorio status, factorio players, factorio help, factorio ban, etc., matching the mental model of “Factorio is the root verb, everything else is an action”.​

Better command visibility & logging: Command sync now logs both global and per‑guild trees, including a true count of leaf subcommands, so logs tell you “one factorio group with N leaves” instead of pretending nothing is registered.

## Test coverage & reliability
***High‑coverage pytest suites:*** There are large, strongly-typed test modules for the Discord bot, RCON client, log tailer, and new polling/alert code, pushing coverage into the 90%+ territory and exercising async paths, error handling, and lifecycle edges.​

***Integration-ready, not just unit‑ready:*** The test harness includes a real-bot integration path (token validity checks, connection timeout diagnostics) so production failures look familiar and debuggable rather than mysterious.