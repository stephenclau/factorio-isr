# Deployment Topology & Operations

This guide covers deployment patterns for Factorio ISR across different scales and architectures.

## Topology Overview

Factorio ISR is designed to monitor **1 to N Factorio servers** from a **single ISR instance**.

### Key Principles

- **Per-instance isolation:** Each ISR instance manages its own set of servers
- **Stateless by design:** All state in RAM (no external DB required for small deployments)
- **Horizontal scaling:** Multiple ISR instances for HA/geo-distribution
- **Network transparency:** Works across local networks, Docker containers, Kubernetes

---

## Topology 1: Single Server, Single ISR (Simplest)

```
┌───────────────────────────┐
│  Factorio Server (production)     │
│  - console.log                    │
└────────┬──────────────────┘
           │
           │ Read logs / RCON
           ↓
┌───────────────────────────┐
│  ISR Container                    │
│  - EventParser                    │
│  - ServerManager (1 server)       │
│  - Discord Bot                    │
└────────┬──────────────────┘
           │
           │ POST events
           ↓
      ┌────────┐
      │ Discord    │
      │ Channels   │
      └────────┘
```

**Use case:** Community servers, small hosting providers  
**servers.yml:**
```yaml
servers:
  default:
    name: "Community Server"
    log_path: /factorio/console.log
    rcon_host: localhost
    rcon_port: 27015
```

**Docker Compose Example:**
```yaml
version: "3.8"
services:
  factorio:
    image: factoriotools/factorio:latest
    ports:
      - "27015:27015/tcp"
    volumes:
      - ./factorio:/factorio

  isr:
    image: slautomaton/factorio-isr:latest
    environment:
      - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
    volumes:
      - ./config/servers.yml:/app/config/servers.yml:ro
      - ./patterns:/app/patterns:ro
      - ./factorio:/factorio:ro  # Share logs
    depends_on:
      - factorio
```

---

## Topology 2: Multi-Server, Single ISR (Typical)

```
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ Server 1 (prod)    │  │ Server 2 (staging) │  │ Server N (test)    │
│ console.log        │  │ console.log        │  │ console.log        │
└────┬───────┘  └────┬───────┘  └────┬───────┘
          │                       │                       │
          └─────────────────┴────────────────────┴─────────────────┘
                                   │
                                   ↓
                        ┌───────────────────────────┐
                        │  ISR Container                        │
                        │  ServerManager                        │
                        │  ├─ prod:  RCONClient, Collector, Alert   │
                        │  ├─ staging: RCONClient, Collector, Alert │
                        │  └─ test:   RCONClient, Collector, Alert  │
                        │  Discord Bot (multi-channel)           │
                        └───────────────────────────┘
                                   │
                        ┌────────┴─────────┐
                        ↓              ↓
                  ┌────────┐   ┌────────┐
                  │ Discord      │   │ Discord      │
                  │ #prod-events │   │ #alerts      │
                  └────────┘   └────────┘
```

**Use case:** Hosting providers, multi-tenant setups  
**servers.yml:**
```yaml
servers:
  prod:
    name: "Production"
    log_path: /data/prod/console.log
    rcon_host: prod-server.internal
    rcon_port: 27015
    alert_channel_id: 1234567890

  staging:
    name: "Staging"
    log_path: /data/staging/console.log
    rcon_host: staging-server.internal
    rcon_port: 27015
    alert_channel_id: 1234567891

  test:
    name: "Testing"
    log_path: /data/test/console.log
    rcon_host: test-server.internal
    rcon_port: 27015
    alert_channel_id: 1234567892
```

**Docker Compose Example:**
```yaml
version: "3.8"
services:
  isr:
    image: slautomaton/factorio-isr:latest
    environment:
      - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
      - LOG_LEVEL=info
    volumes:
      - ./servers.yml:/app/config/servers.yml:ro
      - ./patterns:/app/patterns:ro
      - /data:/data:ro  # Mount all server data
    ports:
      - "8080:8080"  # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Topology 3: Distributed, High-Availability

```
┌────────────────────────────────────────┐
│                  SERVERS                                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ prod (US)  │   │ eu-prod    │   │ asia-prod  │  │
│  └────┬────┘   └────┬────┘   └────┬────┘  │
└───────────────────┬─────────────┴─────────────┘
           │                   │                   │
┌────────────────┴─────────────┴───────────────────┐
│                        ISR INSTANCES                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ ISR-US    │  │ ISR-EU    │  │ ISR-ASIA  │  │
│  │ (prod, local)│  │ (eu-prod) │  │ (asia)    │  │
│  └────┬──────┘  └────┬──────┘  └────┬──────┘  │
└─────────────┴─────────────┴─────────────┴─────────────┘
           │            │            │
           └────────────┴────────────┴────────────┘
                          │
                  ┌─────┴─────┐
                  ↓              ↓
            ┌──────────┐  ┌──────────┐
            │ Discord      │  │ Discord      │
            │ (single bot) │  │ (backup)     │
            └──────────┘  └──────────┘
```

**Use case:** Enterprise, SaaS providers  
**Architecture:**
- Each region has 1-2 ISR instances
- Each ISR monitors local servers only
- All instances post to shared Discord bot
- Load balancer / DNS geo-routing (optional)

**Benefits:**
- Lower latency (ISR runs in same region as servers)
- Fault isolation (one region's ISR down doesn't affect others)
- Independent scaling per region

---

## Topology 4: Kubernetes Deployment (High-Scale)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: factorio-isr
spec:
  replicas: 3  # HA across nodes
  selector:
    matchLabels:
      app: factorio-isr
  template:
    metadata:
      labels:
        app: factorio-isr
    spec:
      containers:
      - name: isr
        image: slautomaton/factorio-isr:latest
        env:
        - name: DISCORD_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: discord-secrets
              key: bot-token
        - name: LOG_FORMAT
          value: "json"
        ports:
        - containerPort: 8080
          name: health
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
        - name: patterns
          mountPath: /app/patterns
          readOnly: true
        - name: server-logs
          mountPath: /servers
          readOnly: true
      volumes:
      - name: config
        configMap:
          name: isr-config
      - name: patterns
        configMap:
          name: isr-patterns
      - name: server-logs
        nfs:
          server: nfs.internal
          path: "/factorio"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: isr-config
data:
  servers.yml: |
    servers:
      prod:
        name: "Production"
        log_path: /servers/prod/console.log
        rcon_host: prod-rcon.internal
        rcon_port: 27015
```

**Benefits:**
- Automatic failover
- Resource scaling
- Rolling updates
- Centralized logging (ELK, Datadog)

---

## Operational Considerations

### Log File Accessibility

**Local (same host):**
- Direct filesystem mount
- Lowest latency

**Network (different host):**
- NFS mount (shared filesystem)
- SMB/CIFS (Windows file sharing)
- SSH with sftp (read-only)

### RCON Network Access

**Local network (recommended):**
- Direct TCP connection within LAN
- No firewall complexity

**Across networks:**
- Expose RCON port (secure with firewall rules)
- VPN tunnel between ISR and server
- SSH port forwarding (if needed)

### Configuration Management

**Development:**
```bash
# Local servers.yml
DISCORD_BOT_TOKEN=xyz docker-compose up
```

**Production:**
```bash
# Docker secrets
docker secret create discord_token /path/to/token
docker secret create rcon_password /path/to/password
# Use in docker-compose.yml via ${DISCORD_BOT_TOKEN}
```

**Kubernetes:**
```bash
kubectl create secret generic discord-secrets \
  --from-literal=bot-token=${DISCORD_BOT_TOKEN}
kubectl create configmap isr-config \
  --from-file=servers.yml=config/servers.yml
```

### Health Checking

ISR exposes `/health` endpoint for orchestration:
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

**Kubernetes:** See example above (livenessProbe + readinessProbe)

---

## Scaling Guidelines

| Scale | Servers per Instance | Storage | CPU | Memory | Approach |
|-------|----------------------|---------|-----|--------|----------|
| Small | 1-5 | Minimal | 0.5 core | 512MB | Single container |
| Medium | 5-10 | Standard | 1 core | 1GB | Single instance |
| Large | 10-20 | 10GB+ | 2 cores | 2GB | Single instance + optimization |
| XL | 20+ | 10GB+ | 4+ cores | 4GB+ | Multiple instances (geo-split) |

**Optimization for higher density:**
- Increase log poll interval (0.1s → 0.5s)
- Decrease RCON stats interval (30s → 60s)
- Batch pattern compilation

---

## Upgrades & Rollbacks

### Docker Compose
```bash
# Pull new version
docker pull slautomaton/factorio-isr:latest

# Restart (zero-downtime if health check OK)
docker-compose down
docker-compose up -d
```

### Kubernetes
```bash
# Rolling update (new pods replace old)
kubectl set image deployment/factorio-isr \
  isr=slautomaton/factorio-isr:v0.3.0

# Monitor rollout
kubectl rollout status deployment/factorio-isr

# Rollback if needed
kubectl rollout undo deployment/factorio-isr
```

---

**Last updated:** December 14, 2025  
**For support:** See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
