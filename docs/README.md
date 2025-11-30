# Factorio ISR (Incident Stream Relay)

[![Docker Hub](https://img.shields.io/docker/v/slautomaton/factorio-isr?style=plastic&label=Docker%20Hub&logo=docker)](https://hub.docker.com/r/slautomaton/factorio-isr)
![Docker Image Version](https://img.shields.io/docker/v/slautomaton/factorio-isr?arch=amd64&style=plastic&logo=docker&label=Image%20Version)
![Docker Image Size](https://img.shields.io/docker/image-size/slautomaton/factorio-isr?arch=amd64&style=plastic&logo=docker&label=Image%20Size)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg?style=plastic)](https://www.python.org/downloads/) 
![GitHub Release](https://img.shields.io/github/v/release/stephenclau/factorio-isr?sort=semver&display_name=release&style=plastic&logo=github) \
![GitHub last commit](https://img.shields.io/github/last-commit/stephenclau/factorio-isr?style=plastic&logo=github&label=Last%20Commit) 
![Codecov](https://img.shields.io/codecov/c/github/stephenclau/factorio-isr?stupid=0?style=plastic&logo=codecov&label=Coverage&color=orange&link=(https%3A%2F%2Fcodecov.io%2Fgh%2Fstephenclau%2Ffactorio-isr)) 
![GitHub License](https://img.shields.io/github/license/stephenclau/factorio-isr?style=plastic&logo=github&label=License&link=https%3A%2F%2Fgithub.com%2Fstephenclau%2Ffactorio-isr%2Fblob%2Fmain%2FLICENSE) \
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/01.yml?style=plastic&logo=github&label=Build) 
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/02.yml?style=plastic&logo=google&label=OSV%20Scan%20Check)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stephenclau/factorio-isr/03.yml?style=plastic&logo=trivy&label=Trivy%20CVE)



Real-time Factorio server event monitoring with Discord integration. Stream JOIN/LEAVE/CHAT events and mod activities directly to your Discord channel.

<!-- ![Factorio ISR Demo](https://via.placeholder.com/800x400?text=Factorio+ISR+Demo) -->

## ✨ Features

### Current Offering
- 🔄 **Real-time log tailing** - Monitors Factorio console.log with file rotation support
- 💬 **Core event parsing** - JOIN, LEAVE, CHAT, and SERVER messages
- 🎮 **Extra support** - MILESTONE, TASK/TODO, RESEARCH, and DEATH events
- 🔗 **Discord webhook integration** - Formatted messages with emojis
- ⚡ **Rate limiting** - Automatic retry logic and exponential backoff
- 🏥 **Health check endpoint** - HTTP health monitoring for container orchestration
- 🐳 **Docker ready** - Production-ready container with non-root user
- 🔐 **Docker secrets support** - Secure credential management
- 📊 **Structured logging** - JSON and console output formats
- ✅ **Comprehensive tests** - Full test coverage with pytest

### Coming Soon
- 📡 **RCON integration** - Read server stats (player count, uptime)
- 🤖 **Discord bot upgrade** - Slash commands for interactive queries
- ⚙️ **Configurable filters** - YAML-based event filtering
- 🎛️ **Admin commands** - Send broadcasts and manage server via Discord

## 🚀 Quick Start

### Docker CLI
Create secrets directory
```bash
mkdir -p .secrets
echo "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN" > .secrets/DISCORD_WEBHOOK_URL.txt
```
Run with Docker
```bash
docker run -d
--name factorio-isr
-v /path/to/factorio/log:/factorio/log:ro
-v $(pwd)/.secrets/DISCORD_WEBHOOK_URL.txt:/run/secrets/DISCORD_WEBHOOK_URL:ro
-e FACTORIO_LOG_PATH=/factorio/log/console.log
-e LOG_LEVEL=info
-p 8080:8080
slautomaton/factorio-isr:latest
```

### Docker Compose (Sidecar with a Factorio container)(Recommended)
```yaml
services:
factorio:
image: factoriotools/factorio:stable
ports:
- "34197:34197/udp"
volumes:
- factorio-data:/factorio
# ... your Factorio config

factorio-isr:
image: slautomaton/factorio-isr:latest
depends_on:
- factorio
volumes:
- factorio-data:/factorio:ro
secrets:
- DISCORD_WEBHOOK_URL
environment:
- FACTORIO_LOG_PATH=/factorio/console.log
- LOG_LEVEL=info
- BOT_NAME=Factorio Server Bot
ports:
- "8080:8080"

volumes:
factorio-data:

secrets:
DISCORD_WEBHOOK_URL:
file: ./.secrets/DISCORD_WEBHOOK_URL.txt
```
### Local Development

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
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN
FACTORIO_LOG_PATH=/path/to/factorio/console.log
LOG_LEVEL=debug
LOG_FORMAT=console
HEALTH_CHECK_PORT=8080
BOT_NAME=Factorio Dev Bot
EOF
```
Run the application
```bash
python -m src.main
```
## 🎮 Supported Events

### Core Events
- ✅ **Player Join** - `PlayerName joined the game`
- ❌ **Player Leave** - `PlayerName left the game`
- 💬 **Chat Messages** - `PlayerName: Hello everyone!`
- 🖥️ **Server Messages** - `[CHAT] <server>: Server restarting...`

### Mod Events
- 🏆 **Milestones** - `[MILESTONE] PlayerName completed: First automation`
- ✔️ **Tasks** - `[TODO] PlayerName finished task: Build solar farm`
- 🔬 **Research** - `Automation technology has been researched`
- 💀 **Deaths** - `PlayerName was killed by a biter`

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
- [ ] Use Docker secrets for `DISCORD_WEBHOOK_URL`
- [ ] Mount Factorio logs as read-only (`:ro`)
- [ ] Configure health check monitoring
- [ ] Set appropriate `UID`/`GID` for file permissions
- [ ] Configure container restart policy
- [ ] Set up log rotation if needed
- [ ] Monitor container resource usage

### Example systemd Service
```bash
[Unit]
Description=Factorio ISR
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStart=/usr/bin/docker run --rm
--name factorio-isr
-v /home/factorio/log:/factorio/log:ro
-v /home/factorio/.secrets/discord_webhook.txt:/run/secrets/DISCORD_WEBHOOK_URL:ro
-e FACTORIO_LOG_PATH=/factorio/log/console.log
slautomaton/factorio-isr:latest
ExecStop=/usr/bin/docker stop factorio-isr

[Install]
WantedBy=multi-user.target
```

## 📄 License

MIT

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Setup

Clone your fork
```bash
git clone https://github.com/YOUR_USERNAME/factorio-isr.git
cd factorio-isr
```
Create virtual environment
```bash
python -m venv venv
source venv/bin/activate
```
Install in development mode
```bash
pip install -e .
pip install -r requirements-dev.txt
```
Run tests
```bash
pytest
```

## 📚 Documentation

- **[Installation Guide](docs/installation.md)** - Detailed setup instructions
- **[Configuration](docs/configuration.md)** - Environment variables and settings
- **[Docker Deployment](docs/docker-deployment.md)** - Production deployment guide
- **[Development](docs/development.md)** - Contributing and local development
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Architecture](docs/architecture.md)** - System design and components
- **[Roadmap](docs/roadmap.md)** - Future features and timeline

## 🙏 Acknowledgments

- [Factorio](https://www.factorio.com/) - The amazing game this tool supports
- [factoriotools/factorio-docker](https://github.com/factoriotools/factorio-docker) - Inspiration for Docker patterns
- [Discord Webhooks](https://discord.com/developers/docs/resources/webhook) - Simple integration API

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/stephenclau/factorio-isr/discussions)
- 📧 **Email**: stephen.c.lau@gmail.com



---

**Made with ❤️ for the Factorio community**

*The factory telemetry must grow!* 🏭
