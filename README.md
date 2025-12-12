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


Real-time Factorio server event monitoring with Discord integration. Stream JOIN/LEAVE/CHAT events and mod activities directly to your Discord.

<!-- ![Factorio ISR Demo](https://via.placeholder.com/800x400?text=Factorio+ISR+Demo) -->

## ✨ Features

### Current Offering
- 🔄 **Real-time log tailing** – Monitors Factorio `console.log` with rotation support
- 💬 **Rich event parsing** – JOIN, LEAVE, CHAT, SERVER plus MILESTONE, TASK/TODO, RESEARCH, DEATH, and other mod events
- 🧩 **YAML pattern system** – Configurable regex patterns with priority, channels, and safe templates
- 🔀 **Multi-channel routing** – Route different event types to different Discord channels/webhooks
- 🔗 **Discord integration** - Bot with slash commands (status, players, admin, metrics)
- 📡 **RCON integration** – Live server stats (players, uptime, evolution, UPS) with scheduled posts
- 🎛️ **Admin commands** - Send broadcasts and manage server via Discord
- 🧠 **Metrics & alerts** – UPS/evolution monitoring, low-UPS alerts, and performance snapshots
- 🏥 **Health check endpoint** – HTTP health monitoring for orchestration
- 🐳 **Docker ready** – Production container with non-root user
- 🔐 **Secrets support** – Docker secrets and `.secrets/` for sensitive config
- 📊 **Structured logging** – JSON and console modes
- ✅ **High test coverage** – Extensive pytest suites across core modules

## 🚀 Quick Start
### Use Docker Compose
```bash
# Create nonroot user on your host
sudo useradd -m -s /bin/bash someuser

# Add user to Docker group
sudo usermod -aG docker someuser

# Grab the UID/ID
id someuser

# Clone the repository
git clone https://github.com/stephenclau/factorio-isr.git
cd factorio-isr

# Configure Docker Compose
mv docker-compose.yml.sidecar /path/to/your/working/dir/docker-compose.yml
mv /config/ to /path/to/your/working/dir
mv /patterns/ to /path/to/your/working/dir

# update docker-compose.yml to your needs

# Start the service
docker compose up -d
```

## 🎮 Supported Events

### Core Events
- ✅ **Player Join** - `PlayerName joined the game`
- ❌ **Player Leave** - `PlayerName left the game`
- 💬 **Chat Messages** - `PlayerName: Hello everyone!`
- 🖥️ **Server Messages** - `[CHAT] <server>: Server restarting...`
- 💀 **Deaths** - `PlayerName was killed by a biter`

### Mod Support Ready 
- 🏆 **Milestones** - `[MILESTONE] PlayerName completed: First automation`
- ✔️ **Tasks** - `[TODO] PlayerName finished task: Build solar farm`
- 🔬 **Research** - `Automation technology has been researched`

FYI - milestones and tasklist do not write to console so this doesn't work, but the regex patterns are made in case mod developers make the change.

## 🏥 Health Monitoring

The health check endpoint is available at `http://localhost:8080/health`

Check health
```bash
curl http://localhost:8080/health
```
Response
```bash
{
"status": "healthy",
"service": "factorio-isr"
}
```
Docker health check is built-in and runs every 30 seconds.


## Local Development

Clone the repository
```bash
git clone https://github.com/stephenclau/factorio-isr.git \
cd factorio-isr
```
Create virtual environment
```bash
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate
```

Install dependencies
```bash
pip install -r requirements.txt
```

Create .env file
```bash
cat > .env << EOF
# Required for bot mode: Channel ID where events will be sent
# Get this by enabling Developer Mode in Discord, right-clicking the channel, and copying ID
DISCORD_EVENT_CHANNEL_ID=1443838551019094048
# Patterns directory
PATTERNS_DIR=patterns
# Factorio Log Path
FACTORIO_LOG_PATH=./logs/console.log
# Health Check Configuration
HEALTH_CHECK_HOST=0.0.0.0
HEALTH_CHECK_PORT=8080
# Logging
LOG_LEVEL=info
LOG_FORMAT=json
# Custom bot appearance for discord webhooks only (deprecated). 
#BOT_NAME=Webhook Botter
#BOT_AVATAR_URL=
# RCON Status Alert Configuration
# Mode: "transition" = send on server state changes, "interval" = send periodically
RCON_STATUS_ALERT_MODE=transition
# Interval in seconds (only used when mode=interval)
RCON_STATUS_ALERT_INTERVAL=300
EOF
```
Run the application
```bash
python -m src.main
```

## 🧪 Testing

Install dev dependencies
``bash 
pip install -r requirements.txt
``

Run all tests
``bash
pytest
``
Run with coverage
``bash
pytest --cov=src --cov-report=html
``
Run specific test file
``bash
pytest tests/test_event_parser.py -v
``
Run in watch mode
``bash
pytest-watch
``

## 📦 Deployment

### Production Checklist

- [ ] Set `LOG_LEVEL=info` or `warning`
- [ ] Set `LOG_FORMAT=json` for log aggregation
- [ ] Use Docker secrets for `DISCORD_BOT_TOKEN, RCON_PASSWORD, etc`
- [ ] Mount Factorio logs as read-only (`:ro`)
- [ ] Configure health check monitoring
- [ ] Set appropriate `UID`/`GID` for file permissions
- [ ] Configure container restart policy
- [ ] Set up log rotation if needed
- [ ] Monitor container resource usage

## 📚 Documentation

- **[Installation Guide](docs/installation.md)** - Detailed setup instructions
- **[Configuration](docs/configuration.md)** - Environment variables and settings
- **[Development](docs/development.md)** - Contributing and local development
- **[Architecture](docs/architecture.md)** - System design and components
- **[Roadmap](docs/roadmap.md)** - Future features and timeline
- **[RCON Setup Guide](docs/RCON_SETUP.md)** - Complete server connection reference 
- **[Usage Examples](docs/EXAMPLES.md)** - Common configuration scenarios
- **[Event Pattern Syntax](docs/PATTERNS.md)** - Complete event pattern reference
- **[Mentions Config Syntax](docs/mentions.md)** - Complete mentions reference
- **[Security Monitor Syntax](docs/secmon.md)** - Complete secmon config reference
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## 🙏 Acknowledgments

- [Factorio](https://www.factorio.com/) - The amazing game this tool supports

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/stephenclau/factorio-isr/discussions)
---

**Made with ❤️ for the Factorio community**

## 📄 License

Factorio ISR is **dual-licensed**:

### Option 1: AGPL-3.0 (Open Source)

Free for use, modification, and distribution under the terms of the 
[GNU Affero General Public License v3.0](LICENSE).

**Requirements:**
- Must open-source any modifications
- Must share source code with network users
- Must use AGPL-3.0 for derivative works

✅ **Great for:** Self-hosting, learning, contributing, open-source projects

### Option 2: Commercial License

For organizations that need to use Factorio ISR without AGPL 
obligations.

**Use cases:**
- Integration into proprietary software
- Offering as a managed service without open-sourcing
- Keeping modifications private
- Enterprise compliance requirements

📧 **Contact:** licensing@laudiversified.com
📄 **Details:** See [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md)

---

**Can't decide?** Most self-hosters choose AGPL-3.0. Commercial 
licenses are for companies with specific compliance needs.
