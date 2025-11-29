# Factorio Discord Bridge

Real-time Factorio server event monitoring with Discord integration.

## Features

- 🔄 Real-time log tailing
- 📊 Structured event parsing
- 💬 Discord webhook integration
- 🔐 Docker secrets support
- 🏥 Health check endpoint
- 🎯 Extensible pattern matching

## Quick Start

1. **Setup environment:** cp .env.example .env
2. **Build and run:** docker compose up -d --build
3. **Check health:** curl http://localhost:8080/health

## Setting User/Permission 

The bridge container runs with a configurable UID/GID set at runtime via the `user:` directive in `docker-compose.yml`.

### Default Configuration (Standalone)
user: "1000:1000" # Different from Factorio's 1001

### Matching Factorio's UID (Shared Permissions for Sidecar)
If your Factorio server runs as UID 1001:
user: "1001:1001" # Same as Factorio

### Custom UID/GID
user: "5000:5000" # Any UID:GID you need

### No Rebuild Required
Change the `user:` value in `docker-compose.yml` and restart:
docker compose up -d

### Verify Running User
docker exec factorio-isr id

### Permission Requirements
The ISR user needs **read permission** on Factorio logs: Make logs readable by all
chmod 644 /path/to/factorio/log/console.log


## Configuration

### Discord Webhook

Create a webhook in your Discord channel:
1. Channel Settings → Integrations → Webhooks → New Webhook
2. Copy webhook URL to `.env`

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | Yes | - | Discord webhook URL |
| `FACTORIO_LOG_PATH` | Yes | `/logs/console.log` | Path to console log |
| `LOG_LEVEL` | No | `info` | Logging level |
| `HEALTH_CHECK_PORT` | No | `8080` | Health check port |

## Development
Install dependencies
pip install -r requirements.txt

Run tests
pytest

Format code
black src/ tests/

Lint
ruff check src/ tests/

## Architecture
Log File → Tailer → Parser → Discord Client
↓
Health Check


## License

Not Sure Yet
