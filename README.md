# Factorio ISR (Incident Stream Relay)

[![Docker Hub](https://img.shields.io/docker/v/slautomaton/factorio-isr?style=plastic&label=Docker%20Hub&logo=docker)](https://hub.docker.com/r/slautomaton/factorio-isr)
![Docker Image Version](https://img.shields.io/docker/v/slautomaton/factorio-isr?arch=amd64&style=plastic&logo=docker&label=Image%20Version)
![Docker Image Size](https://img.shields.io/docker/image-size/slautomaton/factorio-isr?arch=amd64&style=plastic&logo=docker&label=Image%20Size)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg?style=plastic&Lable=Release)](https://www.python.org/downloads/) 
![GitHub Release](https://img.shields.io/github/v/release/stephenclau/factorio-isr?include_prereleases&sort=semver&display_name=tag&style=plastic&logo=github&label=Release&cacheSeconds=1200&link=https%3A%2F%2Fgithub.com%2Fstephenclau%2Ffactorio-isr%2Freleases%2Ftag%2Fv0.2.1) 
![GitHub last commit](https://img.shields.io/github/last-commit/stephenclau/factorio-isr?style=plastic&logo=github&label=Last%20Commit) 
![Codecov](https://img.shields.io/codecov/c/github/stephenclau/factorio-isr?style=plastic&label=CodeCov&color=orange&link=https%3A%2F%2Fapp.codecov.io%2Fgh%2Fstephenclau%2Ffactorio-isr)
![GitHub License](https://img.shields.io/github/license/stephenclau/factorio-isr?style=plastic&logo=github&label=License&link=https%3A%2F%2Fgithub.com%2Fstephenclau%2Ffactorio-isr%2Fblob%2Fmain%2FLICENSE) 
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/01.yml?style=plastic&logo=github&label=Build) 
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/02.yml?style=plastic&logo=google&label=OSV%20Scan%20Check)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/03.yml?style=plastic&logo=trivy&label=Trivy%20CVE)

**Enterprise-grade multi-server Discord integration for Factorio.** Real-time event streaming, UPS monitoring, RCON control, and 91%+ test coverage. Deploy on Docker, Kubernetes, or self-host.

---

## 🎯 What is Factorio ISR?

Factorio ISR is a **production-ready system** that bridges Factorio servers and Discord:

- **🔄 Event Streaming** – Real-time JOIN/LEAVE/CHAT/DEATH events to Discord
- **📊 Server Metrics** – UPS, evolution, player count, uptime monitoring
- **⚠️ Intelligent Alerts** – Low-UPS warnings with configurable thresholds and cooldowns
- **🎮 Discord Commands** – 25+ slash commands for server management & info
- **🖥️ Multi-Server** – Single ISR monitors 1–N Factorio servers
- **🔐 Enterprise Security** – AGPL-3.0 dual licensing, regex ReDoS protection, input sanitization
- **✅ Proven Quality** – 1000+ tests, 91%+ coverage, production deployments

---

## ✨ Features at a Glance

### Core Capabilities

| Feature | Availability | Self-Host (AGPL) | Commercial License |
|---------|--------------|------------------|-------------------|
| **Real-time log tailing** | ✅ Stable | Free | Included |
| **Event pattern matching** (20+ patterns) | ✅ Stable | Free | Included |
| **Multi-channel routing** | ✅ Stable | Free | Included |
| **Discord bot mode** | ✅ Stable | Free | Included |
| **25+ slash commands** | ✅ Stable | Free | Included |
| **RCON client** | ✅ Stable | Free | Included |
| **UPS/evolution metrics** | ✅ Stable | Free | Included |
| **Alert monitoring** | ✅ Stable | Free | Included |
| **Health check endpoint** | ✅ Stable | Free | Included |
| **Structured logging (JSON)** | ✅ Stable | Free | Included |
| **Docker support** | ✅ Production | Free | Included |
| **Kubernetes ready** | ✅ Production | Free | Included |
| **High test coverage (91%+)** | ✅ Stable | Free | Included |

### Event Types Supported

- ✅ **Player Join/Leave** – `PlayerName joined/left the game`
- ✅ **Chat Messages** – `PlayerName: Hello everyone!`
- ✅ **Server Messages** – `[CHAT] <server>: Message`
- ✅ **Deaths** – `PlayerName was killed by a biter`
- ✅ **Milestones** – Custom mod events via regex patterns
- ✅ **Tasks/Research** – Custom mod events via regex patterns
- ✅ **Custom Events** – Define your own via YAML patterns

---

## 🏗️ Architecture Overview

Factorio ISR uses **six-layer modular architecture** for clean separation of concerns:

```
Factorio Servers (console.log + RCON)
         ↓
  [Input & Configuration Layer]
         ↓
  [Log Ingestion & Processing Layer]
         ↓
  [Discord Integration Layer]
         ↓
  [Server Control & Monitoring Layer]
         ↓
  [Bot Commands & Context Layer]
         ↓
  [Observability & Health Layer]
         ↓
Discord Channels + HTTP Health Endpoint
```

**Key components:**
- **ServerManager** – Orchestrates RCON, metrics, alerts per server
- **EventParser** – Pattern matching with ReDoS protection
- **DiscordBot** – Slash commands, event routing, login lifecycle
- **RconStatsCollector** – Periodic UPS/evolution snapshots
- **RconAlertMonitor** – Threshold-based alerting with cooldowns

**For detailed architecture:** See [**docs/ARCHITECTURE.md**](docs/ARCHITECTURE.md)

---

## 🚀 Getting Started

### Multi-Step Setup Process

Factorio ISR requires configuration before launch. The setup involves:

1. **Create working directory** → `~/factorio-isr` with subdirectories (`config/`, `patterns/`, `.secrets/`)
2. **Create config files** → `servers.yml` (RCON + Discord channels), `mentions.yml` (optional)
3. **Populate pattern files** → `vanilla.yml` (core events), `custom.yml` (your patterns)
4. **Create secrets** → `.env` file (Discord token, RCON password)
5. **Customize docker-compose.yml** → Mount your Factorio console.log path
6. **Create Discord bot token** → Discord Developer Portal
7. **Launch and verify** → `docker compose up -d`, test events

### 📖 Installation Guide (15-30 minutes)

**🌟 START HERE:** [**docs/installation.md**](docs/installation.md)

Complete step-by-step guide covering:
- Creating directory structure
- Writing servers.yml, mentions.yml, patterns
- Setting up .env secrets (Discord token, RCON password)
- Configuring docker-compose.yml (volume mounts)
- Creating Discord bot and authorizing
- Launching ISR and verifying connectivity
- Testing event streaming
- Troubleshooting common issues

**Setup Time:** 15–30 minutes  
**Difficulty:** Intermediate (Docker, YAML, Discord setup)

---

## 📊 Supported Deployments

| Deployment | Best For | Setup Complexity | Documentation |
|----------|----------|------------------|---------------|
| **Docker Compose** | Small to medium setups | ⭐⭐ Low | [TOPOLOGY.md §1-2](docs/TOPOLOGY.md) |
| **Multi-server Docker** | Hosting providers | ⭐⭐ Low | [TOPOLOGY.md §2](docs/TOPOLOGY.md) |
| **Distributed (geo-split)** | Global hosting | ⭐⭐⭐ Medium | [TOPOLOGY.md §3](docs/TOPOLOGY.md) |
| **Kubernetes** | Enterprise/SaaS | ⭐⭐⭐ Medium | [TOPOLOGY.md §4](docs/TOPOLOGY.md) |

**For detailed deployment patterns:** See [**docs/TOPOLOGY.md**](docs/TOPOLOGY.md)

---

## 🏥 Health Monitoring

ISR exposes HTTP `/health` endpoint for orchestration:

```bash
curl http://localhost:8080/health
{"status": "healthy", "service": "factorio-isr"}
```

**Docker Compose:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**Kubernetes:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
```

---

## 🧪 Testing & Quality

**Test Coverage:** 91%+ across 1000+ tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific suite
pytest tests/test_event_parser.py -v

# Watch mode
pytest-watch
```

**Test Organization:**
- `test_MODULE.py` – Core logic (happy + error paths)
- `test_MODULE_hardened.py` – Security-focused tests
- `test_MODULE_intensified.py` – Performance & concurrency
- `test_MODULE_integration.py` – Multi-component flows

---

## 📚 Documentation

| Guide | Purpose |
|-------|----------|
| **[Installation](docs/installation.md)** | 🌟 **START HERE** - Complete setup walkthrough |
| **[Configuration](docs/configuration.md)** | All options and environment variables |
| **[Architecture](docs/ARCHITECTURE.md)** | System design and component layers |
| **[Topology](docs/TOPOLOGY.md)** | Deployment patterns and scaling |
| **[RCON Setup](docs/RCON_SETUP.md)** | Factorio server commands |
| **[Patterns](docs/PATTERNS.md)** | Event pattern syntax |
| **[Examples](docs/EXAMPLES.md)** | Configuration scenarios |
| **[Deployment](docs/DEPLOYMENT.md)** | Production checklist |
| **[Troubleshooting](docs/TROUBLESHOOTING.md)** | Common issues and fixes |

---

## 🛠️ Command Examples

Once ISR is running, use Discord slash commands:

```
/factorio status          → See all connected servers
/factorio players         → List active players
/factorio save            → Save server
/factorio kick player     → Remove player
/factorio ban player      → Ban player
/factorio unban player    → Unban player
/factorio broadcast msg   → Send in-game message
/factorio time            → Get server time
/factorio clock           → Detailed time info
/factorio evolution       → Evolution percentage
/factorio research        → Research progress
/factorio admin           → Admin utilities
```

For full command list: See [**RCON_SETUP.md**](docs/RCON_SETUP.md).

---

## 🛨️ Production Deployment

### Pre-Flight Checklist

- [ ] Set `LOG_LEVEL=info` or `warning`
- [ ] Set `LOG_FORMAT=json` for aggregation
- [ ] Use Docker secrets for sensitive values
- [ ] Mount Factorio logs as read-only
- [ ] Configure health check monitoring
- [ ] Set appropriate `UID`/`GID`
- [ ] Enable container restart policy
- [ ] Monitor resource usage
- [ ] Test graceful shutdown (SIGTERM)

**For full deployment guide:** See [**docs/DEPLOYMENT.md**](docs/DEPLOYMENT.md).

---

## 🔐 Security & Licensing

### AGPL-3.0 (Open Source)
✅ **Free for:** Self-hosting, learning, open-source projects
- Must share modifications with users
- See [LICENSE](LICENSE) for full terms

### Commercial License
✅ **For:** Proprietary software, SaaS offerings, private modifications
- No AGPL obligations
- Enterprise support available
- Contact: `licensing@laudiversified.com`

**See also:** [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md)

---

## 🙏 Acknowledgments

- [Factorio](https://www.factorio.com/) – The amazing game this tool supports
- Discord.py – Python Discord API wrapper
- pytest – Test framework
- structlog – Structured logging

## 📞 Support

- 🐛 **Issues:** [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/stephenclau/factorio-isr/discussions)
- 📧 **Commercial:** [licensing@laudiversified.com](mailto:licensing@laudiversified.com)

---

**Made with ❤️ for the Factorio community**
