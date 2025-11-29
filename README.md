# Factorio ISR (Incident Stream Relay)

[![Docker Hub](https://img.shields.io/docker/v/slautomaton/factorio-isr?style=plastic&label=Docker%20Hub&logo=docker)](https://hub.docker.com/r/slautomaton/factorio-isr)
![Docker Image Version](https://img.shields.io/docker/v/slautomaton/factorio-isr?arch=amd64&style=plastic&logo=docker&label=Image%20Version)
![Docker Image Size](https://img.shields.io/docker/image-size/slautomaton/factorio-isr?arch=amd64&style=plastic&logo=docker&label=Image%20Size)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg?style=plastic)](https://www.python.org/downloads/) 
![GitHub Release](https://img.shields.io/github/v/release/stephenclau/factorio-isr?sort=semver&display_name=release&style=plastic&logo=github) \
![GitHub last commit](https://img.shields.io/github/last-commit/stephenclau/factorio-isr?style=plastic&logo=github&label=Last%20Commit) 
![Codecov](https://img.shields.io/codecov/c/github/stephenclau/factorio-isr?style=plastic&logo=codecov&label=Coverage&color=orange&link=(https%3A%2F%2Fcodecov.io%2Fgh%2Fstephenclau%2Ffactorio-isr)) 
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

### Docker Compose (Recommended)

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

## 📚 Documentation

- **[Installation Guide](docs/installation.md)** - Detailed setup instructions
- **[Configuration](docs/configuration.md)** - Environment variables and settings
- **[Docker Deployment](docs/docker-deployment.md)** - Production deployment guide
- **[Development](docs/development.md)** - Contributing and local development
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Architecture](docs/architecture.md)** - System design and components
- **[Roadmap](docs/roadmap.md)** - Future features and timeline

## 🤝 Contributing

Contributions welcome! Please see our [Development Guide](docs/development.md) for details on:
- Setting up your development environment
- Code style and testing requirements
- Submitting pull requests

## 📄 License

TBD

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/stephenclau/factorio-isr/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/stephenclau/factorio-isr/discussions)
- 📧 **Email**: stephen.c.lau@gmail.com

---

**Made with ❤️ for the Factorio community**

*The factory telemetry must grow!* 🏭
