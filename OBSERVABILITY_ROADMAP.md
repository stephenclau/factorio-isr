# Observability Roadmap - Phase 6.0
## Health Check Hardening + Prometheus + OpenTelemetry

**Date:** December 10, 2025  
**Status:** PLANNING  
**Priority:** 🔴 CRITICAL → 🟡 HIGH → 🟢 MEDIUM  

---

## Executive Summary

Your application currently has **no observability** beyond Docker healthchecks.

### What's Broken Right Now

✅ **Logging:** Working (structlog + JSON)  
❌ **Metrics:** Missing (no Prometheus integration)  
❌ **Traces:** Missing (no OpenTelemetry)  
❌ **Health State:** Fake (always returns "healthy" even when degraded)  
❌ **Kubernetes:** Can't tell if app is actually ready to handle traffic  

### What We're Building

✅ **State Tracking:** health.py knows component status  
✅ **Metrics:** `/metrics` endpoint exports Prometheus data  
✅ **Traces:** OpenTelemetry spans for request tracing  
✅ **Correlation:** logs ↔ traces linked by trace_id  
✅ **Dashboards:** Grafana + Jaeger visualization  

---

## Implementation Phases

### 🔴 PHASE 1: Cleanup (CONCURRENT with Phase 1B)
**Status:** Ready to implement  
**Effort:** 90 minutes  
**Dependencies:** None  
**Blocking:** Phase 2+

**Deliverables:**
- [ ] Delete `src/discord_client.py`
- [ ] Remove deprecated Config fields
- [ ] Update `.env.example`
- [ ] Verify no regressions

**Reference:** `docs/DEPRECATION_CLEANUP.md` (from previous analysis)

---

### 🔴 PHASE 1B: Health Check Hardening (CONCURRENT with Phase 1)
**Status:** Ready to implement  
**Effort:** 40 minutes  
**Dependencies:** None  
**Blocking:** Phase 2

**Deliverables:**
- [ ] Add state tracking to `HealthCheckServer`
  - `is_live` / `is_ready` flags
  - `component_status` dict tracking Discord, RCON, LogTailer
  - `error_counts` for debugging

- [ ] Implement readiness vs liveness separation
  - `/healthz` → Kubernetes liveness probe
  - `/ready` → Kubernetes readiness probe
  - `/health` → Legacy endpoint

- [ ] Wire component lifecycle to health checks
  - In `main.py`: Call `health_server.mark_live()`, `mark_component_healthy()`, etc.
  - Mark components as unhealthy on errors
  - Return 503 when not ready

- [ ] Test with Kubernetes probes
  ```bash
  curl http://localhost:8080/healthz  # 200 if alive
  curl http://localhost:8080/ready    # 200 if ready
  ```

**Reference:** `docs/HEALTH_OTEL_REFERENCE.md` (health.py Phase 1 section)

**Impact:** 
- ✅ Kubernetes can now properly orchestrate pods
- ✅ Failing components are detected immediately
- ✅ Foundation for metrics/traces

---

### 🟡 PHASE 2: Prometheus Metrics
**Status:** Design complete, implementation ready  
**Effort:** 90 minutes  
**Dependencies:** Phase 1B complete  
**Blocking:** Phase 3 (optional)

**Deliverables:**
- [ ] Add `prometheus-client` dependency
  ```bash
  pip install prometheus-client>=0.17.0
  ```

- [ ] Implement `/metrics` endpoint in `HealthCheckServer`
  - Prometheus text format (OpenMetrics 0.0.4)
  - Auto-updates on each request

- [ ] Define core metrics
  ```prometheus
  factorio_isr_uptime_seconds
  factorio_isr_component_status{component="discord|rcon|log_tailer"}
  factorio_isr_errors_total{component,error_type}
  factorio_isr_events_processed_total{server,event_type}
  factorio_isr_discord_api_latency_seconds_bucket
  factorio_isr_rcon_command_latency_seconds_bucket{server}
  ```

- [ ] Wire metrics to component events
  - `record_event(server, event_type)` when processing logs
  - `record_discord_latency(seconds)` after API calls
  - `record_rcon_latency(server, seconds)` after RCON commands

- [ ] Create Prometheus scrape config
  ```yaml
  - job_name: 'factorio-isr'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
  ```

- [ ] Test metric collection
  ```bash
  curl http://localhost:8080/metrics | grep factorio_isr
  ```

**Reference:** `docs/HEALTH_OTEL_REFERENCE.md` (health.py Phase 1 & 2 sections)

**Impact:**
- ✅ Production visibility (Grafana dashboards)
- ✅ Historical trend analysis
- ✅ Alerting capability (via Prometheus AlertManager)
- ✅ Capacity planning data

---

### 🟢 PHASE 3: OpenTelemetry Traces (OPTIONAL)
**Status:** Design complete, implementation ready  
**Effort:** 120 minutes  
**Dependencies:** Phase 1B + Phase 2  
**Blocking:** None

**Deliverables:**
- [ ] Add OpenTelemetry dependencies
  ```bash
  pip install \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-jaeger \
    opentelemetry-instrumentation-aiohttp \
    opentelemetry-instrumentation-logging
  ```

- [ ] Configure tracer provider in `HealthCheckServer`
  - Initialize Jaeger exporter
  - Setup span processor
  - Get tracer instance

- [ ] Instrument key operations
  - Discord API calls (measure latency, capture errors)
  - RCON commands (measure latency, track success/failure)
  - Log processing (measure per-line latency)
  - Event parsing (measure regex matching time)

- [ ] Add trace correlation to logs
  - Inject `trace_id` and `span_id` in structured logs
  - Use OpenTelemetry LoggingInstrumentor

- [ ] Configure Jaeger exporter
  ```python
  jaeger_exporter = JaegerExporter(
      agent_host_name="jaeger",
      agent_port=6831
  )
  ```

- [ ] Test trace collection
  ```bash
  # Open Jaeger UI: http://localhost:16686
  # Search for service: factorio-isr
  # View trace spans
  ```

**Reference:** `docs/HEALTH_OTEL_REFERENCE.md` (health.py Phase 3 section)

**Impact:**
- ✅ Distributed tracing for request analysis
- ✅ Critical path analysis (which operations are slow?)
- ✅ Dependency mapping (what calls what?)
- ✅ Error investigation (find root cause fast)
- ✅ Log-to-trace correlation (click trace_id in logs)

---

### 🟢 PHASE 4: Dashboards & Alerting (OPTIONAL)
**Status:** Design complete  
**Effort:** 60 minutes  
**Dependencies:** Phase 2 complete  
**Blocking:** None

**Deliverables:**
- [ ] Create Grafana dashboard
  - Application status (uptime, component health)
  - Event processing (rate, latency percentiles)
  - Discord integration (API latency, reconnections)
  - RCON performance (per-server latency)

- [ ] Setup Prometheus AlertManager
  ```yaml
  groups:
    - name: factorio-isr
      rules:
        - alert: HighDiscordLatency
          expr: factorio_isr_discord_api_latency_seconds{quantile="0.95"} > 2.0
        - alert: ComponentDown
          expr: factorio_isr_component_status == 0
  ```

- [ ] Create Jaeger service map
  - Visualize all components and their interactions

- [ ] Configure log aggregation (optional)
  - Logstash + Elasticsearch + Kibana for centralized logs

**Reference:** `docs/OBSERVABILITY_STRATEGY.md` (Grafana section)

**Impact:**
- ✅ Real-time operational visibility
- ✅ Proactive alerting
- ✅ Historical trend analysis
- ✅ Beautiful dashboards for stakeholders

---

## Timeline

```
Week 1 (This Week)
├─ Phase 1: Cleanup (90 min)
│  ├─ Delete webhook code
│  ├─ Remove deprecated env vars
│  └─ Verify no regressions
│
└─ Phase 1B: Health Hardening (40 min)
   ├─ Add state tracking
   ├─ Implement liveness/readiness
   └─ Wire to main.py

Week 2
└─ Phase 2: Prometheus Metrics (90 min)
   ├─ Add prometheus-client
   ├─ Implement /metrics endpoint
   ├─ Define metrics
   └─ Test collection

Week 3
└─ Phase 3: OpenTelemetry (120 min) [OPTIONAL]
   ├─ Add OTEL dependencies
   ├─ Configure tracer
   ├─ Instrument operations
   └─ Test spans

Week 4
└─ Phase 4: Dashboards (60 min) [OPTIONAL]
   ├─ Create Grafana dashboard
   ├─ Setup AlertManager
   └─ Deploy ELK stack
```

**Total Effort:**
- 🔴 Critical: Phase 1 + 1B = **130 minutes** (~2 hours)
- 🟡 High: Phase 2 = **90 minutes** (~1.5 hours)
- 🟢 Optional: Phase 3 + 4 = **180 minutes** (~3 hours)
- **Total: ~6.5 hours over 4 weeks**

---

## Quick Start (Today)

If you want to see results immediately:

### Step 1: Run Phase 1B (40 min)
```bash
# Update src/health.py with state tracking
cp docs/HEALTH_OTEL_REFERENCE.md docs/HEALTH_OTEL_REFERENCE.md
# (Copy Phase 1 implementation from reference)

# Update src/main.py to wire health checks
# Call health_server.mark_live(), mark_ready(), mark_component_healthy()

# Test
curl http://localhost:8080/healthz
curl http://localhost:8080/ready
```

### Step 2: Run Phase 2 (90 min)
```bash
pip install prometheus-client
# Add /metrics endpoint to health.py
# Wire metrics in main.py

# Test
curl http://localhost:8080/metrics
```

### Step 3 (Optional): Visualize
```bash
# Start Prometheus
docker run -p 9090:9090 -v prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus

# Start Grafana
docker run -p 3000:3000 grafana/grafana

# Open http://localhost:3000 → Create dashboard
```

---

## Architecture Diagram

```
┌─────────────────────────────────────┐
│  Factorio ISR Application                  │
├─────────────────────────────────────┤
│                                            │
│  HealthCheckServer (Phase 1B)              │
│  ├─ /healthz (liveness)                    │
│  ├─ /ready (readiness)                      │
│  ├─ State tracking (is_live, is_ready)      │
│  └─ Component status dict                   │
│                                            │
│  + PrometheusMetrics (Phase 2)             │
│  ├─ /metrics endpoint                       │
│  ├─ Gauges (uptime, component_status)       │
│  ├─ Counters (events, errors)               │
│  └─ Histograms (latency)                    │
│                                            │
│  + OpenTelemetry (Phase 3, optional)       │
│  ├─ Tracer for key operations               │
│  ├─ Span creation (Discord, RCON, parsing)  │
│  └─ Correlation IDs (trace_id in logs)      │
│                                            │
└─────────────────────────────────────┘
                         │
         ┌───────────────────────────┐
         │  Observability Stack              │
         ├───────────────────────────┤
         │                                │
         │  Prometheus (Phase 2)           │
         │  └─ Scrapes /metrics endpoint    │
         │                                │
         │  + Grafana (Phase 4)            │
         │  └─ Visualizes metrics            │
         │                                │
         │  + Jaeger (Phase 3)             │
         │  └─ Visualizes traces            │
         │                                │
         │  + ELK Stack (Phase 4, optional)│
         │  └─ Aggregates logs              │
         │                                │
         └───────────────────────────┘
```

---

## Decision Matrix

### Do I Need Phase 1B (Health Hardening)?
**Answer: YES, REQUIRED**
- Kubernetes can't tell if your app is ready
- Components fail silently (health endpoint always returns 200)
- Foundation for everything else

### Do I Need Phase 2 (Prometheus)?
**Answer: YES, if you care about production visibility**
- See what's actually happening in production
- Alerts when things go wrong
- Required for SLA/SLO tracking

### Do I Need Phase 3 (OpenTelemetry)?
**Answer: OPTIONAL, but nice-to-have**
- Useful for debugging complex issues
- See request flows end-to-end
- Overkill for simple setups
- Add it later if needed

### Do I Need Phase 4 (Dashboards)?
**Answer: OPTIONAL, but recommended**
- Makes metrics actionable
- Beautiful for stakeholders
- Essential for ops teams

---

## Documentation References

1. **DEPRECATION_CLEANUP.md** (from previous analysis)
   - Webhook code removal
   - Config field cleanup
   - Environment variable consolidation

2. **OBSERVABILITY_STRATEGY.md** (NEW)
   - Complete observability architecture
   - Three pillars (metrics, logs, traces)
   - Implementation phases
   - Configuration options
   - Success criteria

3. **HEALTH_OTEL_REFERENCE.md** (NEW)
   - Complete working code examples
   - Phase 1: Health hardening
   - Phase 2: Prometheus metrics
   - Phase 3: OpenTelemetry traces
   - Docker Compose setup
   - Testing instructions

---

## Support & Questions

**Q: Which phase should I do first?**  
A: Phase 1 (cleanup) + Phase 1B (health hardening) = MUST DO. They're prerequisites and take ~2 hours total.

**Q: Can I skip Phase 2?**  
A: No, if you're deploying to production. Metrics are essential for observability.

**Q: Can I skip Phase 3?**  
A: Yes, traces are optional. Start with Phase 2, add Phase 3 later if needed.

**Q: How long does each phase take?**  
- Phase 1 (cleanup): 90 min
- Phase 1B (health hardening): 40 min
- Phase 2 (Prometheus): 90 min
- Phase 3 (OpenTelemetry): 120 min
- Phase 4 (Dashboards): 60 min

**Q: Do I need to change my application code?**  
A: Yes, minimal changes to `main.py` to wire health checks. See Phase 1B reference.

**Q: What if I'm using Docker Compose locally?**  
A: See docker-compose example in HEALTH_OTEL_REFERENCE.md

---

## Checklist

### Pre-Implementation
- [ ] Review this roadmap
- [ ] Read OBSERVABILITY_STRATEGY.md
- [ ] Skim HEALTH_OTEL_REFERENCE.md
- [ ] Team agrees on scope
- [ ] Decide which phases to implement

### Phase 1 (Cleanup)
- [ ] Delete discord_client.py
- [ ] Remove deprecated Config fields
- [ ] Update .env.example
- [ ] Verify no regressions
- [ ] Create PR, merge

### Phase 1B (Health Hardening)
- [ ] Update health.py with state tracking
- [ ] Implement liveness/readiness
- [ ] Update main.py to wire health
- [ ] Test /healthz and /ready
- [ ] Create PR, merge

### Phase 2 (Prometheus)
- [ ] Add prometheus-client dependency
- [ ] Implement /metrics endpoint
- [ ] Wire metrics in application
- [ ] Test metric collection
- [ ] Create Prometheus scrape config
- [ ] Create PR, merge

### Phase 3 (OpenTelemetry) [Optional]
- [ ] Add OTEL dependencies
- [ ] Configure tracer
- [ ] Instrument operations
- [ ] Add trace correlation to logs
- [ ] Test trace collection
- [ ] Create PR, merge

### Phase 4 (Dashboards) [Optional]
- [ ] Create Grafana dashboard
- [ ] Setup AlertManager
- [ ] Deploy visualization stack
- [ ] Create runbooks

---

**Start with Phase 1B today. You'll have working health checks in 40 minutes.**

Good luck! 🚀
