# 📋 Configuration

This guide covers all configuration options for Factorio ISR.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | ✅ Yes | - | Discord webhook URL for posting events |
| `FACTORIO_LOG_PATH` | ✅ Yes | - | Path to Factorio console.log file |
| `LOG_LEVEL` | No | `info` | Logging level: debug, info, warning, error, critical |
| `LOG_FORMAT` | No | `json` | Log output format: json or console |
| `HEALTH_CHECK_HOST` | No | `0.0.0.0` | Health check server bind address |
| `HEALTH_CHECK_PORT` | No | `8080` | Health check server port |
| `BOT_NAME` | No | `Factorio Bridge` | Display name for Discord webhook |
| `BOT_AVATAR_URL` | No | - | Avatar URL for Discord webhook |

## Docker Secrets (Recommended for Production)

For production deployments, use Docker secrets instead of environment variables for sensitive data.

### Create Secret File

```bash
mkdir -p .secrets
echo "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" > .secrets/DISCORD_WEBHOOK_URL.txt
chmod 600 .secrets/DISCORD_WEBHOOK_URL.txt
```

### Mount in docker-compose.yml

```yaml
services:
  factorio-isr:
    secrets:
      - DISCORD_WEBHOOK_URL

secrets:
  DISCORD_WEBHOOK_URL:
    file: ./.secrets/DISCORD_WEBHOOK_URL.txt
```

### Or in Docker CLI

```bash
docker secret create discord_webhook .secrets/DISCORD_WEBHOOK_URL.txt

docker service create \
  --name factorio-isr \
  --secret discord_webhook \
  slautomaton/factorio-isr:latest
```

## Getting a Discord Webhook

### Step-by-Step Instructions

1. Go to your Discord server
2. Right-click a channel → **Edit Channel**
3. Navigate to **Integrations** → **Webhooks**
4. Click **New Webhook**
5. Customize the webhook name and avatar (optional)
6. Click **Copy Webhook URL**
7. Add the URL to your `.env` or `.secrets/DISCORD_WEBHOOK_URL.txt`

### Webhook URL Format

```
https://discord.com/api/webhooks/{WEBHOOK_ID}/{WEBHOOK_TOKEN}
```

## Supported Events

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

## Log Levels

### Available Levels

- `debug` - Detailed debugging information (verbose)
- `info` - General informational messages (recommended for production)
- `warning` - Warning messages for potential issues
- `error` - Error messages for failures
- `critical` - Critical errors that may stop the service

### Example Usage

For development:
```bash
LOG_LEVEL=debug
LOG_FORMAT=console
```

For production:
```bash
LOG_LEVEL=info
LOG_FORMAT=json
```

## Health Monitoring

The health check endpoint is available at `http://localhost:8080/health` by default.

### Configuration

```bash
HEALTH_CHECK_HOST=0.0.0.0  # Listen on all interfaces
HEALTH_CHECK_PORT=8080     # Default port
```

### Docker Health Check

Built into the Docker image and runs every 30 seconds:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

### Response Format

```json
{
  "status": "healthy",
  "service": "factorio-isr"
}
```

## Example Configurations

### Minimal Configuration

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
FACTORIO_LOG_PATH=/factorio/console.log
```

### Development Configuration

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
FACTORIO_LOG_PATH=/path/to/factorio/console.log
LOG_LEVEL=debug
LOG_FORMAT=console
BOT_NAME=Factorio Dev Bot
```

### Production Configuration

```bash
# Use Docker secrets for DISCORD_WEBHOOK_URL
FACTORIO_LOG_PATH=/factorio/console.log
LOG_LEVEL=info
LOG_FORMAT=json
HEALTH_CHECK_HOST=0.0.0.0
HEALTH_CHECK_PORT=8080
BOT_NAME=Factorio Production Server
BOT_AVATAR_URL=https://example.com/avatar.png
```

## Next Steps

- Deploy to production: [Docker Deployment Guide](docker-deployment.md)
- Troubleshoot issues: [Troubleshooting Guide](troubleshooting.md)
