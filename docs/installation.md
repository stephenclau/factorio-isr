# 💾 Installation Guide

This guide covers multiple ways to install and run Factorio ISR.

## Prerequisites

- Docker and Docker Compose (recommended)
- OR Python 3.13+ for local development
- A running Factorio server with console logging enabled
- A Discord webhook URL

## Docker CLI Installation

### Create Secrets Directory

```bash
mkdir -p .secrets
echo "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN" > .secrets/DISCORD_WEBHOOK_URL.txt
```

### Run with Docker

```bash
docker run -d \
  --name factorio-isr \
  -v /path/to/factorio/log:/factorio/log:ro \
  -v $(pwd)/.secrets/DISCORD_WEBHOOK_URL.txt:/run/secrets/DISCORD_WEBHOOK_URL:ro \
  -e FACTORIO_LOG_PATH=/factorio/log/console.log \
  -e LOG_LEVEL=info \
  -p 8080:8080 \
  slautomaton/factorio-isr:latest
```

## Docker Compose Installation (Recommended)

### As a Sidecar Container

Create a `docker-compose.yml` file:

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

### Start the Services

```bash
docker compose up -d
```

### Check Logs

```bash
docker compose logs -f factorio-isr
```

## Local Development Installation

### Clone the Repository

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
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN
FACTORIO_LOG_PATH=/path/to/factorio/console.log
LOG_LEVEL=debug
LOG_FORMAT=console
HEALTH_CHECK_PORT=8080
BOT_NAME=Factorio Dev Bot
EOF
```

### Run the Application

```bash
python -m src.main
```

## Verifying Installation

### Check Health Endpoint

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "factorio-isr"
}
```

### Test Discord Integration

Send a test message to verify your webhook works:

```bash
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test message from Factorio ISR"}'
```

## Next Steps

- Configure environment variables: [Configuration Guide](configuration.md)
- Set up for production: [Docker Deployment Guide](docker-deployment.md)
- Start developing: [Development Guide](development.md)
