# Factorio ISR (Incident Stream Relay)

[![Docker Hub](https://img.shields.io/docker/v/slautomaton/factorio-isr?style=plastic&label=Docker%20Hub&logo=docker)](https://hub.docker.com/r/slautomaton/factorio-isr)
![Docker Image Version](https://img.shields.io/docker/v/slautomaton/factorio-isr?arch=amd64&style=plastic&logo=docker&label=Image%20Version)
![Docker Image Size](https://img.shields.io/docker/image-size/slautomaton/factorio-isr?arch=amd64&style=plastic&logo=docker&label=Image%20Size)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg?style=plastic&Lable=Release)](https://www.python.org/downloads/) 
![GitHub Release](https://img.shields.io/github/v/release/stephenclau/factorio-isr?include_prereleases&sort=semver&display_name=tag&style=plastic&logo=github&label=Release&cacheSeconds=1200&link=https%3A%2F%2Fgithub.com%2Fstephenclau%2Ffactorio-isr%2Freleases%2Ftag%2Fv0.2.1) \
![GitHub last commit](https://img.shields.io/github/last-commit/stephenclau/factorio-isr?style=plastic&logo=github&label=Last%20Commit) 
![Codecov](https://img.shields.io/codecov/c/github/stephenclau/factorio-isr?style=plastic&label=CodeCov&color=orange&link=https%3A%2F%2Fapp.codecov.io%2Fgh%2Fstephenclau%2Ffactorio-isr)
![GitHub License](https://img.shields.io/github/license/stephenclau/factorio-isr?style=plastic&logo=github&label=License&link=https%3A%2F%2Fgithub.com%2Fstephenclau%2Ffactorio-isr%2Fblob%2Fmain%2FLICENSE) \
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/01.yml?style=plastic&logo=github&label=Build) 
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/02.yml?style=plastic&logo=google&label=OSV%20Scan%20Check)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/03.yml?style=plastic&logo=trivy&label=Trivy%20CVE)

Real-time Factorio server event monitoring with Discord bot integration. Stream game events, manage multiple servers, and control your Factorio infrastructure directly from Discord.

---

## ✨ Features

### Core Capabilities
- 🔄 **Real-time log tailing** – Monitors Factorio `console.log` with automatic rotation support
- 🖥️ **Multi-server support** – Monitor multiple Factorio servers with a single ISR instance
- 💬 **Richer event parsing** – JOIN, LEAVE, CHAT, SERVER, MILESTONE, RESEARCH, DEATH, and custom mod events
- 🧩 **YAML pattern system** – Configurable regex patterns with priority, channels, and safe templates
- 🤖 **Discord bot integration** – Native Discord bot with slash commands and rich embeds

### Discord Features
- 📡 **Slash commands** – `/status`, `/players`, `/save`, `/broadcast`, `/servers`
- 🔔 **@Mentions** – Tag Discord users/roles from Factorio chat (`@username` in-game)
- 🎛️ **Admin commands** – Send broadcasts and manage servers via Discord
- 🎨 **Per-server channels** – Route each server's events to dedicated Discord channels

### Monitoring & Performance
- 📊 **RCON integration** – Live server stats (players, uptime, evolution, UPS)
- 🧠 **Metrics & alerts** – UPS/evolution monitoring, low-UPS alerts, performance snapshots
- 🔒 **Security monitoring** – Alert admins on sensitive console commands via `secmon.yml`
- 🏥 **Health check endpoint** – HTTP health monitoring for orchestration

### Operations
- 🐳 **Docker ready** – Production container with non-root user and secrets support
- 🔐 **Secrets management** – Docker secrets and `.secrets/` directory support
- 📊 **Structured logging** – JSON and console modes with configurable levels
- ✅ **High test coverage** – Extensive pytest suites across core modules

---

## 💡 Use Cases

- **Community Servers** - Keep Discord community engaged with real-time game events
- **Admin Monitoring** - Get alerts when players join, die, or trigger sensitive commands
- **Multi-Server Networks** - Centralize monitoring for multiple Factorio servers from one bot
- **Performance Tracking** - Monitor UPS and evolution metrics over time with alerts
- **Cross-Platform Chat** - Bridge Factorio in-game chat to Discord channels
- **Remote Management** - Execute admin commands without connecting to Factorio

---

## 🚀 Quick Start

### Prerequisites

- **Discord bot token** – [Create one here](https://discord.com/developers/applications)
  - Required scopes: `bot`, `applications.commands`
  - Required permissions: Send Messages, Embed Links, Use Slash Commands, Mention Everyone
- **Discord channel IDs** – Enable Developer Mode in Discord → Right-click channel → Copy ID
- **Factorio server** – With console logging enabled

### Docker Compose (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/stephenclau/factorio-isr.git
   cd factorio-isr
   ```

2. **Create secrets:**
   ```bash
   mkdir -p .secrets
   echo "your-discord-bot-token" > .secrets/DISCORD_BOT_TOKEN.txt
   chmod 600 .secrets/DISCORD_BOT_TOKEN.txt
   ```

3. **Configure servers** (`config/servers.yml`):
   ```yaml
   servers:
     my_server:
       log_path: /factorio/console.log
       discord:
         event_channel_id: 123456789012345678
       rcon:
         host: localhost
         port: 27015
         password_file: .secrets/rcon_password.txt
         stats_interval: 300
   ```

4. **Update `docker-compose.yml`:**
   ```bash
   cp docker-compose.yml.example docker-compose.yml
   # Edit to match your setup
   ```

5. **Start:**
   ```bash
   docker compose up -d
   ```

6. **Verify:**
   ```bash
   # Check health
   curl http://localhost:8080/health
   
   # View logs
   docker compose logs -f factorio-isr
   
   # Check bot is online in Discord
   ```

---

## 🤖 Discord Bot Commands

- `/stats [server]` - View server statistics (players, uptime, UPS, evolution)
- `/players [server]` - List online players
- `/save [server]` - Trigger server save
- `/broadcast <message> [server]` - Send message to all players
- `/servers` - List all configured servers and their status

> **Note:** Commands require RCON to be configured for the target server.

---

## ⚙️ Multi-Server Configuration

Manage multiple servers with a single ISR instance via `config/servers.yml`:

```yaml
servers:
  vanilla:
    log_path: /factorio/vanilla/console.log
    rcon:
      host: localhost
      port: 27015
      password_file: .secrets/rcon_vanilla.txt
      stats_interval: 300
    discord:
      event_channel_id: 123456789012345678

  modded:
    log_path: /factorio/modded/console.log
    rcon:
      host: localhost
      port: 27016
      password_file: .secrets/rcon_modded.txt
      stats_interval: 600
    discord:
      event_channel_id: 987654321098765432
```

Each server gets:
- Independent log monitoring
- Dedicated Discord channel
- Per-server RCON configuration
- Separate stats posting intervals

See **[Configuration Guide](docs/configuration.md)** for full reference.

---

## 🎮 Supported Events

### Core Events
- ✅ **Player Join** - `PlayerName joined the game`
- ❌ **Player Leave** - `PlayerName left the game`
- 💬 **Chat Messages** - `PlayerName: Hello everyone!`
- 🖥️ **Server Messages** - `[CHAT] <server>: Server restarting...`
- 💀 **Deaths** - `PlayerName was killed by a biter`

### Mod Support
- 🏆 **Milestones** - `[MILESTONE] PlayerName completed: First automation`
- ✔️ **Tasks** - `[TODO] PlayerName finished task: Build solar farm`
- 🔬 **Research** - `Automation technology has been researched`

> **Note:** Milestones and tasks require mod support for console logging.

### Custom Events
Add your own patterns in `patterns/*.yml` - see **[Pattern Syntax](docs/PATTERNS.md)** for details.

---

## 🔒 Security

- **Pattern validation** – YAML patterns validated at load time
- **ReDoS protection** – Regex timeout limits prevent denial-of-service
- **Secrets management** – Support for Docker secrets and `.secrets/` directory
- **Security monitoring** – Alert on sensitive console commands via `config/secmon.yml`
- **Read-only mounts** – Log files mounted read-only in containers
- **Non-root container** – Docker image runs as non-privileged user

---

## 🏥 Health Monitoring

Health check endpoint at `http://localhost:8080/health`

```bash
curl http://localhost:8080/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "factorio-isr",
  "uptime_seconds": 3600
}
```

Docker health check runs automatically every 30 seconds.

---

## 🧪 Testing

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_event_parser.py -v

# Watch mode
pytest-watch
```

---

## 📦 Deployment

### Production Checklist

- [ ] Set `LOG_LEVEL=info` or `warning`
- [ ] Set `LOG_FORMAT=json` for log aggregation
- [ ] Use Docker secrets for `DISCORD_BOT_TOKEN`, `RCON_PASSWORD`
- [ ] Mount Factorio logs as read-only (`:ro`)
- [ ] Configure `config/servers.yml` with all servers
- [ ] Configure health check monitoring
- [ ] Set appropriate container restart policy
- [ ] Set up log rotation if needed
- [ ] Monitor container resource usage

See **[Deployment Guide](docs/DEPLOYMENT.md)** for detailed instructions.

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

See **[Development Guide](docs/development.md)** for local setup and contribution guidelines.

---

## 📚 Documentation

- **[Installation Guide](docs/installation.md)** – Detailed setup instructions
- **[Configuration](docs/configuration.md)** – Environment variables and settings
- **[RCON Setup Guide](docs/RCON_SETUP.md)** – Configure server statistics
- **[Usage Examples](docs/EXAMPLES.md)** – Common configuration scenarios
- **[Pattern Syntax](docs/PATTERNS.md)** – Complete pattern reference
- **[Deployment Guide](docs/DEPLOYMENT.md)** – Production deployment
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** – Common issues and solutions
- **[Development](docs/development.md)** – Contributing and local development
- **[Architecture](docs/architecture.md)** – System design and components
- **[Roadmap](docs/roadmap.md)** – Future features and timeline

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Factorio](https://www.factorio.com/) – The amazing game this tool supports
- [factoriotools/factorio-docker](https://github.com/factoriotools/factorio-docker) – Inspiration for Docker patterns
- [discord.py](https://github.com/Rapptz/discord.py) – Excellent Discord API wrapper

---

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/stephenclau/factorio-isr/discussions)

---

**Made with ❤️ for the Factorio community**
