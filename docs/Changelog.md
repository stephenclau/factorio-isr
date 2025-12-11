# Changelog

All notable changes to the **Factorio ISR** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-12-11

### Added
- **Observability**: Added `OBSERVABILITY_ROADMAP.md` outlining phases for metrics, tracing, and logging.
- **Observability**: Added `HEALTH_OTEL_REFERENCE.md` with OpenTelemetry reference implementation for health checks.
- **Security**: Comprehensive Discord Security Guide covering ReDoS mitigation, strict YAML validation, and console input sanitization.
- **Testing**: Enhanced test suites for `ServerManager`, `DiscordInterface`, `EventParser`, and `Application` targeting 93%+ coverage.
- **RCON**: Multi-server RCON monitoring support with per-server status tracking and breakdown notifications.

### Changed
- **Architecture**: `DiscordBot` initialization aligned with multi-server architecture; breakdown settings now loaded via `server_manager`.
- **Refactor**: Renamed `discord_client` module and parameters to `discord_interface` for consistency across `RconStatsCollector` and `RconAlertMonitor`.
- **Configuration**: Hardcoded `config` and `patterns` directories to relative paths (`/app/config`, `/app/patterns`) to standardize Docker and local dev environments.
- **Configuration**: `servers.yml` is now the single source of truth for server configurations, residing in `/app/config`.

### Removed
- **Configuration**: Removed support for `CONFIG_DIR` and `PATTERNS_DIR` environment variables.
- **Configuration**: Removed deprecated `factorio_log_path` from `Config` (replaced by per-server `log_path` in `servers.yml`).
- **Configuration**: Removed deprecated `bot_name` and `bot_avatar_url` fields (webhook-era legacy).
- **Code**: Removed dead webhook-related code and legacy `discord_client.py`.

### Fixed
- **Docs**: split large README into modular files in `/docs` for better navigation.
- **Docs**: Clarified `servers.yml` relocation instructions.
