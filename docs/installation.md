---
layout: default
title: Installation Guide
---


# 💾 Installation Guide

Quick setup guide for getting Factorio ISR running locally or with Docker.

## Prerequisites

- Docker and Docker Compose (recommended), OR
- Python 3.11+ for local development
- A running Factorio server with console logging enabled
- A Discord bot token and channel ID

---

## Docker CLI Installation

### Create Secrets Directory

```bash
mkdir -p .secrets
echo "your-discord-bot-token" > .secrets/DISCORD_BOT_TOKEN.txt
```

### Run with Docker

```bash
docker run -d \
  --name factorio-isr \
  -v /path/to/factorio/log:/factorio/log:ro \
  -v $(pwd)/.secrets/DISCORD_BOT_TOKEN.txt:/run/secrets/DISCORD_BOT_TOKEN:ro \
  -e FACTORIO_LOG_PATH=/factorio/log/console.log \
  -e DISCORD_EVENT_CHANNEL_ID=123456789012345678 \
  -e LOG_LEVEL=info \
  -p 8080:8080 \
  slautomaton/factorio-isr:latest
```

---

## Docker Compose Installation (Recommended)

### Create docker-compose.yml

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
      - ./patterns:/app/patterns:ro
    secrets:
      - discord_bot_token
    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - DISCORD_EVENT_CHANNEL_ID=123456789012345678
      - LOG_LEVEL=info
      - BOT_NAME=Factorio Server Bot
    ports:
      - "8080:8080"

volumes:
  factorio-data:

secrets:
  discord_bot_token:
    file: ./.secrets/DISCORD_BOT_TOKEN.txt
```

### Start Services

```bash
docker compose up -d
```

### Check Logs

```bash
docker compose logs -f factorio-isr
```

---

## Local Development Installation

### Clone Repository

```bash
git clone https://github.com/stephenclau/factorio-isr.git
cd factorio-isr
```

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Create Environment File

```bash
cat > .env << EOF
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_EVENT_CHANNEL_ID=123456789012345678
FACTORIO_LOG_PATH=/path/to/factorio/console.log
LOG_LEVEL=debug
LOG_FORMAT=console
HEALTH_CHECK_PORT=8080
BOT_NAME=Factorio Dev Bot
EOF
```

### Run Application

```bash
python -m src.main
```

---

## Verify Installation

### Health Check

```bash
curl http://localhost:8080/health
```

Expected response:

```json
{
  "status": "healthy",
  "uptime_seconds": 123,
  "version": "2.0.0"
}
```

### Verify Discord Connection

Check bot is online in Discord and responding to events. You should see bot status update to show server info.

---

## Next Steps

- **Configure:** [Configuration Guide](configuration.md) – Environment variables, RCON, patterns
- **Production:** [Deployment Guide](DEPLOYMENT.md) – Systemd, Docker Compose, monitoring
- **Development:** [Development Guide](development.md) – Running tests, adding features
