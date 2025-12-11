# Observability Strategy: Prometheus + OpenTelemetry
## Factorio ISR Phase 6.0

**Date:** December 10, 2025  
**Scope:** Unified observability with Prometheus metrics, Logstash logs, and OpenTelemetry traces

---

## 🎯 OBSERVABILITY ARCHITECTURE

### Three Pillars (OpenTelemetry Standard)

```
┌─────────────────────────────────────────────────────────┐
│         Unified Observability (OpenTelemetry)           │
├─────────────────────────────────────────────────────────┤
│  Metrics (Prometheus)  │  Logs (Logstash/ELK)  │ Traces │
├────────────────────────┼────────────────────────┼────────┤
│ • Counters             │ • Application logs     │ • Spans│
│ • Gauges               │ • Error stack traces   │ • Ctx  │
│ • Histograms           │ • Structured JSON      │ • Link │
│ • Component status     │ • Time-series events   │        │
└────────────────────────┴────────────────────────┴────────┘
```

---

## 📊 IMPLEMENTATION LAYERS

### Layer 1: Metrics (Prometheus)

**Endpoint:** `/metrics` (OpenMetrics text format)

**Built-in Metrics:**
```python
# Gauges (point-in-time values)
factorio_isr_uptime_seconds              # App uptime
factorio_isr_component_status{component} # 0=failed, 1=healthy
factorio_isr_discord_latency_ms          # API response time
factorio_isr_rcon_connected{server}      # Connection status

# Counters (cumulative)
factorio_isr_events_processed_total{server,event_type}
factorio_isr_errors_total{component,error_type}
factorio_isr_discord_reconnects_total

# Histograms (distributions)
factorio_isr_log_processing_seconds_bucket
factorio_isr_discord_api_latency_seconds_bucket
factorio_isr_rcon_command_latency_seconds_bucket
```

### Layer 2: Logs (Structured JSON for Logstash/ELK)

**Already Implemented:** ✅ Using `structlog`

**Format:**
```json
{
  "timestamp": "2025-12-10T21:23:00.000Z",
  "level": "info",
  "event": "health_check_request",
  "component_status": {"discord": "connected", "rcon": "ok"},
  "uptime_seconds": 3600,
  "trace_id": "abc123def456"  // OpenTelemetry correlation
}
```

### Layer 3: Traces (OpenTelemetry Spans)

**Span Context:**
```python
# Automatic span creation for:
# - Discord API calls (latency tracking)
# - RCON commands (duration, success/failure)
# - Log processing (lines per batch)
# - Event parsing (regex matching duration)

# Attributes:
{
  "trace_id": "abc123",
  "span_id": "def456",
  "parent_span_id": "ghi789",
  "server": "primary",
  "operation": "process_log_line",
  "duration_ms": 42
}
```

---

## 🔧 HEALTH CHECK HARDENING + OBSERVABILITY

### Current Issues

❌ No state tracking (always returns "healthy")  
❌ No Prometheus endpoint  
❌ No OpenTelemetry context propagation  
❌ No trace correlation with logs  

### Solution: Enhanced HealthCheckServer

```python
class HealthCheckServer:
    """Enhanced health checks with observability hooks."""
    
    def __init__(self, host: str, port: int, 
                 enable_metrics: bool = True,
                 enable_traces: bool = False):
        self.enable_metrics = enable_metrics
        self.enable_traces = enable_traces
        
        # State tracking
        self.start_time = time.time()
        self.is_live = False
        self.is_ready = False
        self.component_status = {}
        self.error_counts = {}
        
        # Prometheus metrics
        if enable_metrics:
            self._setup_prometheus_metrics()
        
        # OpenTelemetry tracer
        if enable_traces:
            self._setup_otel_tracer()
    
    def _setup_prometheus_metrics(self):
        """Initialize prometheus_client metrics."""
        from prometheus_client import Gauge, Counter, Histogram
        
        self.uptime_gauge = Gauge(
            'factorio_isr_uptime_seconds',
            'Application uptime in seconds'
        )
        self.component_status_gauge = Gauge(
            'factorio_isr_component_status',
            'Component status (1=healthy, 0=failed)',
            ['component']
        )
        self.errors_counter = Counter(
            'factorio_isr_errors_total',
            'Total errors by component',
            ['component', 'error_type']
        )
    
    def _setup_otel_tracer(self):
        """Initialize OpenTelemetry tracer."""
        from opentelemetry import trace
        self.tracer = trace.get_tracer(__name__)
    
    async def metrics_handler(self, request):
        """Prometheus metrics endpoint."""
        # Update gauges
        if hasattr(self, 'uptime_gauge'):
            self.uptime_gauge.set(time.time() - self.start_time)
            for component, status in self.component_status.items():
                self.component_status_gauge.labels(component=component).set(
                    1 if status == 'healthy' else 0
                )
        
        # Generate Prometheus text format
        from prometheus_client import generate_latest, REGISTRY
        metrics_output = generate_latest(REGISTRY).decode('utf-8')
        
        return web.Response(
            text=metrics_output,
            content_type='text/plain; version=0.0.4'
        )
    
    async def liveness_handler(self, request):
        """Kubernetes liveness probe: Is the app running?"""
        with self.tracer.start_as_current_span("health_liveness_check"):
            is_alive = self.is_live
            status = 200 if is_alive else 503
            
            return web.json_response(
                {
                    "status": "alive" if is_alive else "dead",
                    "uptime_seconds": time.time() - self.start_time
                },
                status=status
            )
    
    async def readiness_handler(self, request):
        """Kubernetes readiness probe: Can it handle traffic?"""
        with self.tracer.start_as_current_span("health_readiness_check"):
            is_ready = (
                self.is_ready and
                self.component_status.get("discord") == "healthy" and
                self.component_status.get("log_tailer") == "healthy"
            )
            status = 200 if is_ready else 503
            
            reasons = []
            if not self.is_ready:
                reasons.append("app_initializing")
            if self.component_status.get("discord") != "healthy":
                reasons.append("discord_unavailable")
            if self.component_status.get("log_tailer") != "healthy":
                reasons.append("log_tailer_unavailable")
            
            return web.json_response(
                {
                    "ready": is_ready,
                    "reasons": reasons,
                    "components": self.component_status
                },
                status=status
            )
```

---

## 📦 DEPENDENCIES

### Minimal (Metrics Only)
```bash
pip install prometheus-client structlog
```

### Full Stack (Metrics + Traces)
```bash
pip install \
  prometheus-client \
  opentelemetry-api \
  opentelemetry-sdk \
  opentelemetry-exporter-prometheus \
  opentelemetry-exporter-jaeger \
  opentelemetry-instrumentation-aiohttp \
  opentelemetry-instrumentation-logging
```

### Optional (Logstash)
```bash
# Configure docker-compose with ELK stack:
# - Logstash (log ingestion)
# - Elasticsearch (log storage)
# - Kibana (log visualization)
```

---

## 🚀 IMPLEMENTATION PHASES

### Phase 1: Hardening Health Checks (40 min)
**Status:** CRITICAL - Do Now

- [x] Add state tracking (is_live, is_ready, component_status)
- [x] Implement readiness vs liveness separation
- [x] Wire component lifecycle to health checks
- [ ] Update main.py to call health methods
- [ ] Test with Kubernetes probes

**Outcome:** App properly reports its state to orchestrators

### Phase 2: Prometheus Metrics (90 min)
**Status:** HIGH - Next Sprint

- [ ] Add prometheus-client dependency
- [ ] Implement `/metrics` endpoint
- [ ] Create metric definitions (gauges, counters, histograms)
- [ ] Wire metrics to component events
- [ ] Test with `curl http://localhost:8080/metrics`
- [ ] Create Grafana dashboard

**Outcome:** Production-grade metrics visibility

### Phase 3: OpenTelemetry Traces (120 min)
**Status:** MEDIUM - Following Sprint

- [ ] Add OpenTelemetry dependencies
- [ ] Configure tracer provider
- [ ] Add span creation for key operations
- [ ] Wire traces to logs (correlation IDs)
- [ ] Configure Jaeger exporter (optional)
- [ ] Create trace visualization

**Outcome:** Distributed tracing across components

### Phase 4: Logstash Integration (60 min)
**Status:** MEDIUM - Following Sprint

- [ ] Add Logstash config (optional)
- [ ] Configure ELK stack (docker-compose)
- [ ] Verify structured logs ingest to Elasticsearch
- [ ] Create Kibana dashboards
- [ ] Add trace_id to all logs for correlation

**Outcome:** Centralized log storage and visualization

---

## 📋 CONFIGURATION OPTIONS

### Environment Variables

```env
# ===== OBSERVABILITY =====

# Metrics (Prometheus)
METRICS_ENABLED=true                    # Enable /metrics endpoint
METRICS_PORT=8081                       # Optional: separate metrics port

# Traces (OpenTelemetry)
TRACES_ENABLED=false                    # Enable OpenTelemetry
TRACES_EXPORTER=jaeger                  # jaeger, otlp, or none
TRACES_SAMPLE_RATE=0.1                  # % of traces to send (0.0-1.0)

# Jaeger (if using traces)
JAEGER_AGENT_HOST=localhost              # Jaeger agent
JAEGER_AGENT_PORT=6831                   # Jaeger agent port

# Service metadata
SERVICE_NAME=factorio-isr                # Service name in traces
SERVICE_VERSION=6.0.0                    # App version
SERVICE_ENVIRONMENT=production           # Environment label
```

### servers.yml (Per-Server Observability)

```yaml
servers:
  primary:
    tag: primary
    name: Production
    
    # Observability settings
    enable_metrics: true
    metrics_namespace: "factorio_isr_primary"
    trace_enabled: true
    trace_sample_rate: 0.5  # Trace 50% of events
    
    # Alert thresholds (for metrics)
    alerts:
      ups_warning_threshold: 55.0
      rcon_latency_threshold_ms: 1000
      discord_latency_threshold_ms: 2000
```

---

## 🔗 TRACE CORRELATION EXAMPLE

### Log Entry with Trace Context

```json
{
  "timestamp": "2025-12-10T21:24:35.123Z",
  "level": "info",
  "event": "log_line_processed",
  "server": "primary",
  "trace_id": "a1b2c3d4e5f6g7h8",  // ← Trace correlation
  "span_id": "x9y8z7w6v5u4t3s2",
  "line_content": "Player 'Alice' joined",
  "event_type": "player_join",
  "duration_ms": 2.5
}
```

### Jaeger UI Shows

```
Trace: a1b2c3d4e5f6g7h8
├─ span: log_line_received (duration: 0.5ms)
├─ span: parse_log_line (duration: 1.2ms)
├─ span: match_patterns (duration: 0.3ms)
├─ span: discord_send_event (duration: 15.2ms)
└─ span: rcon_command (duration: 450.0ms)
```

---

## 📈 METRICS EXAMPLES

### Dashboard Query (Prometheus/Grafana)

```promql
# Application uptime
factorio_isr_uptime_seconds

# Component health status
factorio_isr_component_status{component="discord"}
factorio_isr_component_status{component="log_tailer"}
factorio_isr_component_status{component="rcon", server="primary"}

# Event processing rate
rate(factorio_isr_events_processed_total[5m])

# Error rate
rate(factorio_isr_errors_total[5m])

# Discord API latency (P95)
histogram_quantile(0.95, factorio_isr_discord_api_latency_seconds_bucket)

# RCON command latency (P99)
histogram_quantile(0.99, factorio_isr_rcon_command_latency_seconds_bucket{server="primary"})
```

---

## 🎨 GRAFANA DASHBOARD PANELS

### Recommended Panels

1. **Application Status**
   - Uptime gauge
   - Component status indicators
   - Last healthcheck time

2. **Event Processing**
   - Events/second (by type)
   - Error rate
   - Processing latency (P50, P95, P99)

3. **Discord Integration**
   - Connected/disconnected status
   - API latency trend
   - Reconnection count
   - Message success rate

4. **RCON Performance**
   - Command latency (by server)
   - Command success rate
   - Connection uptime

5. **System Health**
   - Memory usage
   - CPU usage
   - Network I/O

---

## 🔍 LOGGING + TRACES = OBSERVABILITY

### Without Correlation (Current)

```
Log: "error sending event to discord"
     └─ No way to find related trace spans

Trace: a1b2c3d4e5f6g7h8
       └─ No way to find related logs
```

### With Correlation (After Implementation)

```
Log: "error sending event to discord" (trace_id: a1b2c3d4e5f6g7h8)
     └─ Click trace_id → View entire request trace in Jaeger
        ├─ Which API endpoint?
        ├─ How long did it take?
        └─ Where did it fail?

Trace: a1b2c3d4e5f6g7h8
       └─ Click span → View all logs from that span
          ├─ debug logs during parsing
          ├─ info logs about event processing
          └─ error logs about discord failure
```

---

## ✅ IMPLEMENTATION CHECKLIST

### Before Phase 1: Cleanup (from DEPRECATION analysis)
- [ ] Delete `src/discord_client.py`
- [ ] Remove deprecated Config fields
- [ ] Update `.env.example`
- [ ] Verify no regressions

### Phase 1: Health Check Hardening
- [ ] Add state tracking to HealthCheckServer
- [ ] Implement liveness/readiness separation
- [ ] Update main.py Application class
- [ ] Wire component lifecycle events
- [ ] Test with Kubernetes probes

### Phase 2: Prometheus Metrics
- [ ] Add prometheus-client to requirements
- [ ] Implement `/metrics` endpoint
- [ ] Create metric definitions
- [ ] Wire metrics to component events
- [ ] Create Grafana dashboard
- [ ] Verify metrics export

### Phase 3: OpenTelemetry Traces
- [ ] Add OpenTelemetry dependencies
- [ ] Configure tracer provider
- [ ] Instrument key operations (Discord, RCON, log parsing)
- [ ] Add trace_id to structured logs
- [ ] Configure Jaeger/OTLP exporter
- [ ] Create trace visualizations

### Phase 4: Logstash/ELK (Optional)
- [ ] Add Logstash config
- [ ] Create docker-compose for ELK
- [ ] Verify log ingestion
- [ ] Create Kibana dashboards
- [ ] Add log-to-trace correlation

---

## 🎯 SUCCESS CRITERIA

✅ **Health Checks**
- Kubernetes correctly identifies pod state changes
- `/healthz` returns 503 when components fail
- `/ready` returns 503 when not ready to receive traffic

✅ **Metrics**
- Prometheus scrapes `/metrics` endpoint successfully
- Grafana dashboard displays uptime, component status, latency
- Historical metrics retained for 15+ days

✅ **Traces**
- Key operations create spans (Discord, RCON, log processing)
- Trace IDs appear in structured logs
- Jaeger UI shows request flows end-to-end

✅ **Logs**
- Structured JSON logs ingested to ELK
- Logs searchable by trace_id
- Error logs correlate with trace spans

---

## 📚 RECOMMENDED READING

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/instrumentation/)
- [Jaeger Tracing](https://www.jaegertracing.io/)
- [Kubernetes Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

---

## 📝 NEXT STEPS

1. **Immediate (Today):** Review this document with team
2. **This Week:** Implement Phase 1 (health check hardening)
3. **Next Week:** Implement Phase 2 (Prometheus metrics)
4. **Following Week:** Implement Phase 3 (OpenTelemetry traces)
5. **Optional:** Implement Phase 4 (Logstash/ELK)

---

**Document Status:** DRAFT  
**Last Updated:** December 10, 2025, 9:23 PM PST  
**Owner:** Stephen Clau
