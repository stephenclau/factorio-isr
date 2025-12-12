# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-12-12

### Architecture
- **RCON Client Modularization**: Split `rcon_client.py` into focused modules to separate protocol, metrics, stats, and alerting concerns.
  - `rcon_client.py`: Pure RCON protocol and connection management.
  - `rcon_metrics_engine.py`: Unified metrics computation (UPS, evolution, player counts).
  - `rcon_stats_collector.py`: Handling of periodic stats posting to Discord.
  - `rcon_alert_monitor.py`: High-frequency UPS monitoring and alerting logic.
- **Command Pattern Refactor**: Converted all Discord slash commands into discrete, self-contained enclosures. Each command now encapsulates its own RCON execution, parsing, formatting, and error handling, removing cross-command dependencies.

### Features
- **Configurable Stats Collection**: Added `enable_stats_collector` flag to `servers.yml` to toggle RCON stats collection per server.
- **Granular Metrics Toggles**: Added `enable_ups_stat` and `enable_evolution_stat` to fine-tune which metrics are collected.
- **Enhanced `save` Command**: Now supports intelligent save name parsing from RCON responses, handling both full paths and simple filenames.
- **Multi-Surface `evolution`**: Updated `evolution` command to support aggregate (all surfaces) and per-surface queries, automatically filtering platform surfaces.
- **Improved `whitelist`**: Refactored whitelist command for cleaner flow and better action-specific logging.
- **Rich `broadcast`**: Added pink color formatting to in-game broadcasts and improved Discord embed styling.
- **Simplified `time`**: Switched to `daytime` (0-1) for setting time and added human-readable shortcuts (noon, midnight).

### Refactor
- **Config Renaming**:
  - Renamed `enable_stats_gather` to `enable_stats_collector` for clarity.
  - Renamed `collect_ups` to `enable_ups_stat`.
  - Renamed `collect_evolution` to `enable_evolution_stat`.
- **Helpers Cleanup**: Moved `get_version`, `get_seed`, `get_game_uptime` to `helpers.py` to remove god-object anti-patterns in `rcon_client.py`.
- **Formatter Extraction**: Extracted `format_stats_text` and `format_stats_embed` to `bot.helpers` for reuse across modules.

### Documentation
- Updated `servers.yml.example` with new config options and detailed documentation.
- Updated `REFACTORING_STATUS.md` to reflect completion of Discord Bot and RCON modular refactoring.
