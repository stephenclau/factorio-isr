---
layout: default
title: Home
---

# Factorio ISR Documentation

[![Release](https://img.shields.io/github/v/release/stephenclau/factorio-isr?style=flat-square&logo=github)](https://github.com/stephenclau/factorio-isr/releases)
[![License](https://img.shields.io/github/license/stephenclau/factorio-isr?style=flat-square)](https://github.com/stephenclau/factorio-isr/blob/main/LICENSE)

**Real-time Factorio server monitoring with Discord integration**

Monitor your Factorio server activity in real-time and relay events directly to Discord channels. Get instant notifications for player joins/leaves, chat messages, achievements, deaths, and more—all without touching a single line of code.

---

## Why Factorio ISR?

Running a Factorio server is great. Knowing what's happening on it without logging in? Even better.

- **Stay Connected** - Know when players join or leave, even when you're away
- **Community Engagement** - Bridge in-game chat to Discord for seamless communication
- **Server Insights** - Track achievements, research, deaths, and custom mod events
- **Admin Tools** - Send broadcasts and check server stats via Discord commands
- **Zero Hassle** - Docker-ready with one-command deployment

---

## Features

### 🔄 Real-Time Monitoring
Monitor Factorio `console.log` continuously with automatic rotation support. Never miss an event.

### 💬 Rich Event Parsing
Capture player joins/leaves, chat messages, deaths, achievements, research, and mod-specific events using flexible YAML patterns.

### 🤖 Discord Bot Integration
Native Discord bot with slash commands for server status, player lists, admin actions, and performance metrics.

### 📡 RCON Support
Query live server statistics: player count, uptime, evolution factor, UPS, and more. Schedule automated status reports.

### 🔀 Multi-Channel Routing
Route different event types to different Discord channels—keep chat in one place and admin alerts in another.

### 🏛️ Admin Commands
Send in-game broadcasts, check server health, and monitor performance directly from Discord.

### 🐳 Production Ready
Ships with Docker support, health checks, structured logging, and 95%+ test coverage.

---

## Quick Start

Get up and running in under 5 minutes.

### 1. Get the Code

```bash
git clone https://github.com/stephenclau/factorio-isr.git
cd factorio-isr
```

### 2. Configure Environment

```bash
# Create secrets directory
mkdir -p .secrets

# Add your Discord bot token
echo "YOUR_DISCORD_BOT_TOKEN" > .secrets/DISCORD_BOT_TOKEN.txt

# Add your Discord channel ID (right-click channel → Copy ID)
echo "DISCORD_EVENT_CHANNEL_ID=123456789012345678" >> .env
```

### 3. Deploy

```bash
# Update docker-compose.yml.example with your paths
docker compose up -d
```

**That's it!** Events will start flowing to Discord immediately.

📖 **Need more details?** See the [Installation Guide](installation.md)

---

## What Can It Do?

### Supported Events

#### Core Events
- ✅ **Player Join/Leave** - Track server population changes
- 💬 **Chat Messages** - Bridge in-game chat to Discord
- 🖥️ **Server Messages** - Relay server announcements
- 💀 **Deaths** - See who got eaten by biters

#### Advanced Events
- 🏆 **Achievements** - Celebrate player milestones
- 🔬 **Research** - Track technology progress
- 🚀 **Rocket Launches** - Never miss a launch celebration
- 🧩 **Mod Support** - Custom patterns for popular mods

📖 **See examples:** [Usage Examples](EXAMPLES.md)

---

## Documentation

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0;">

### 🚀 Getting Started
**New to Factorio ISR?**
- [Installation Guide](installation.md) - Step-by-step setup
- [Configuration](configuration.md) - Environment variables & settings
- [Quick Examples](EXAMPLES.md) - Common scenarios

### 🔧 Configuration
**Customize your setup**
- [Pattern Syntax](PATTERNS.md) - Event matching rules
- [RCON Setup](RCON_SETUP.md) - Enable server statistics

### 📚 Reference
**Deep dive documentation**
- [Deployment Guide](DEPLOYMENT.md) - Production setup
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues

### 🛠️ Development
**Contributing to the project**
- [Development Guide](development.md) - Local setup & testing
- [Roadmap](roadmap.md) - Future features
- [GitHub Repository](https://github.com/stephenclau/factorio-isr) - Source code

</div>

---

## Common Use Cases

### Single Server Monitoring
Perfect for hobby servers or small communities. Monitor one Factorio server with all events in a single Discord channel.

📖 [View Setup Guide](EXAMPLES.md#single-server-setup)

### Multi-Server Setup
Run multiple Factorio servers (vanilla, modded, testing) with separate Discord channels for each.

📖 [View Multi-Server Guide](EXAMPLES.md#multiple-servers)

### Admin-Only Alerts
Route player activity to a public channel while keeping admin alerts (low UPS, crashes) in a private channel.

📖 [View Pattern Guide](PATTERNS.md)

### Mod-Specific Events
Parse custom events from popular mods like Krastorio 2, Space Exploration, or Factorissimo.

📖 [View Mod Patterns](PATTERNS.md#mod-support)

---

## Need Help?

### 🐛 Found a Bug?
[Open an Issue](https://github.com/stephenclau/factorio-isr/issues) on GitHub

### 💬 Have Questions?
Check [Troubleshooting](TROUBLESHOOTING.md) or start a [Discussion](https://github.com/stephenclau/factorio-isr/discussions)

### 🤝 Want to Contribute?
See the [Development Guide](development.md)

---

## System Requirements

- **Factorio Server** - Any version (headless or GUI)
- **Docker** - Version 20.10+ (recommended) or Python 3.13+
- **Discord** - Bot token with appropriate permissions

---

## License

Factorio ISR is open source under the [MIT License](https://github.com/stephenclau/factorio-isr/blob/main/LICENSE).

---

**Made with ❤️ for the Factorio community**

[⬆ Back to Top](#factorio-isr-documentation)
