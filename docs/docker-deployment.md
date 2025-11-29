# 🚢 Docker Deployment Guide

This guide covers production deployment best practices for Factorio ISR.

## Production Checklist

Before deploying to production, ensure you've completed these steps:

- [ ] Set `LOG_LEVEL=info` or `warning` (not debug)
- [ ] Set `LOG_FORMAT=json` for log aggregation
- [ ] Use Docker secrets for `DISCORD_WEBHOOK_URL`
- [ ] Mount Factorio logs as read-only (`:ro`)
- [ ] Configure health check monitoring
- [ ] Set appropriate `UID`/`GID` for file permissions
- [ ] Configure container restart policy
- [ ] Set up log rotation if needed
- [ ] Monitor container resource usage
- [ ] Test failover and recovery scenarios

## Building the Docker Image

### Build Locally

```bash
docker build -t factorio-isr:latest .
```

### Build with Custom UID/GID

For systems where the Factorio log files are owned by a specific user:

```bash
docker build \
  --build-arg UID=1000 \
  --build-arg GID=1000 \
  -t factorio-isr:custom .
```

### Multi-Platform Build

Requires Docker Buildx:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t slautomaton/factorio-isr:latest \
  --push .
```

## Docker Compose Production Setup

### Full Production Configuration

```yaml
version: '3.8'

services:
  factorio:
    image: factoriotools/factorio:stable
    container_name: factorio-server
    restart: unless-stopped
    ports:
      - "34197:34197/udp"
    volumes:
      - factorio-data:/factorio
      - ./config:/factorio/config
    environment:
      - UPDATE_ON_START=true
    networks:
      - factorio-net

  factorio-isr:
    image: slautomaton/factorio-isr:latest
    container_name: factorio-isr
    restart: unless-stopped
    depends_on:
      - factorio
    volumes:
      - factorio-data:/factorio:ro
    secrets:
      - DISCORD_WEBHOOK_URL
    environment:
      - FACTORIO_LOG_PATH=/factorio/console.log
      - LOG_LEVEL=info
      - LOG_FORMAT=json
      - HEALTH_CHECK_HOST=0.0.0.0
      - HEALTH_CHECK_PORT=8080
      - BOT_NAME=Factorio Production Server
    ports:
      - "8080:8080"
    networks:
      - factorio-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

volumes:
  factorio-data:
    driver: local

networks:
  factorio-net:
    driver: bridge

secrets:
  DISCORD_WEBHOOK_URL:
    file: ./.secrets/DISCORD_WEBHOOK_URL.txt
```

### Deployment Commands

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f factorio-isr

# Restart a specific service
docker compose restart factorio-isr

# Stop all services
docker compose down

# Update to latest image
docker compose pull
docker compose up -d
```

## systemd Service Integration

### Create Service File

Create `/etc/systemd/system/factorio-isr.service`:

```ini
[Unit]
Description=Factorio ISR
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=10
WorkingDirectory=/home/factorio/factorio-isr
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable factorio-isr

# Start the service
sudo systemctl start factorio-isr

# Check status
sudo systemctl status factorio-isr

# View logs
sudo journalctl -u factorio-isr -f
```

## Docker Swarm Deployment

### Stack Configuration

```yaml
version: '3.8'

services:
  factorio-isr:
    image: slautomaton/factorio-isr:latest
    deploy:
      replicas: 1
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M
    volumes:
      - type: bind
        source: /mnt/factorio/logs
        target: /factorio/log
        read_only: true
    secrets:
      - DISCORD_WEBHOOK_URL
    environment:
      - FACTORIO_LOG_PATH=/factorio/log/console.log
      - LOG_LEVEL=info
      - LOG_FORMAT=json
    ports:
      - "8080:8080"
    networks:
      - factorio-net

networks:
  factorio-net:
    driver: overlay

secrets:
  DISCORD_WEBHOOK_URL:
    external: true
```

### Deploy Stack

```bash
# Create secret
echo "https://discord.com/api/webhooks/..." | \
  docker secret create discord_webhook -

# Deploy stack
docker stack deploy -c docker-stack.yml factorio

# Check services
docker stack services factorio

# View logs
docker service logs -f factorio_factorio-isr
```

## Monitoring and Observability

### Prometheus Metrics (Coming Soon)

The health endpoint can be scraped by Prometheus:

```yaml
scrape_configs:
  - job_name: 'factorio-isr'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/health'
    scrape_interval: 30s
```

### Log Aggregation

With `LOG_FORMAT=json`, logs can be ingested by:

- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Loki** (Grafana Loki)
- **Splunk**
- **CloudWatch Logs**

Example Loki configuration:

```yaml
scrape_configs:
  - job_name: factorio-isr
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
```

## Resource Management

### CPU and Memory Limits

```yaml
services:
  factorio-isr:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M
```

### Disk Usage

Monitor log file growth and set up rotation:

```bash
# Check disk usage
du -sh /var/lib/docker/volumes/factorio-data/_data/

# Set up logrotate
cat > /etc/logrotate.d/factorio << EOF
/var/lib/docker/volumes/factorio-data/_data/console.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 factorio factorio
}
EOF
```

## Security Best Practices

### Non-Root User

The Docker image runs as a non-root user by default (UID 1000, GID 1000).

### Read-Only Mounts

Always mount Factorio logs as read-only:

```yaml
volumes:
  - factorio-data:/factorio:ro
```

### Secret Management

Never commit secrets to version control:

```bash
# Add to .gitignore
echo ".secrets/" >> .gitignore
echo ".env" >> .gitignore
```

### Network Isolation

Use Docker networks to isolate services:

```yaml
networks:
  factorio-net:
    internal: true  # No external access
```

## Backup and Recovery

### Backup Configuration

```bash
# Backup secrets
tar czf factorio-isr-backup.tar.gz .secrets/ docker-compose.yml

# Backup to remote location
rsync -avz factorio-isr-backup.tar.gz user@backup-server:/backups/
```

### Disaster Recovery

```bash
# Restore from backup
tar xzf factorio-isr-backup.tar.gz

# Restart services
docker compose up -d
```

## Troubleshooting Deployment Issues

### Container Won't Start

```bash
# Check container logs
docker compose logs factorio-isr

# Inspect container
docker inspect factorio-isr

# Check file permissions
docker exec factorio-isr ls -la /factorio/log/
```

### Health Check Failing

```bash
# Test health endpoint from host
curl http://localhost:8080/health

# Test from inside container
docker exec factorio-isr curl http://localhost:8080/health
```

### High Resource Usage

```bash
# Monitor resource usage
docker stats factorio-isr

# Check for log file issues
docker exec factorio-isr tail -f /factorio/log/console.log
```

## Next Steps

- Configure monitoring: [Architecture Guide](architecture.md)
- Debug issues: [Troubleshooting Guide](troubleshooting.md)
- Contribute improvements: [Development Guide](development.md)
