---
layout: default
title: Roadmap
---


## 🗺️ Roadmap

### Phase 1 - Minimum Viable Product (MVP) ✅
- [x] Real-time log monitoring
- [x] Discord webhook integration
- [x] Core event parsing
- [x] Docker deployment
- [x] Health checks
- [x] Comprehensive tests

### Phase 2 - RCON Integration ✅
- [x] Read-only RCON commands
- [x] Server statistics (players, uptime)
- [x] Scheduled status updates (set intervals)

### Phase 3 - Enhanced Parsing ✅
- [x] YAML-based pattern configuration
- [x] Custom event filters
- [x] Multiple Discord channels
- [x] Event statistics and aggregation

### Phase 4 - Discord Bot ✅
- [x] Replace webhook with Discord bot (1 bot to 1 RCON/server arch)
- [x] Slash commands
- [x] Interactive queries

### Phase 5 - Interactive Features Baseline ✅
- [x] Admin commands from Discord
- [x] RCON write operations
- [x] Multi-server support (1 bot supporting n number of RCON/server connections)

### Phase 6 - More Interactions and House Cleaning ✅
- [x] Default use of embeds over plain text for bot responses
- [x] Console to Discord @mention support
- [x] Input sanitization + memory and threadsafe performance optimization 

### Future 
- [ ] Full webhook deprecation and removal from codebase
- [ ] Permission system
- [X] Milestone/Todo mod event support (only works if/when those mods write to console log)
- [ ] Open Telemetry/Prometheus 
- [ ] Hot loadable configs
