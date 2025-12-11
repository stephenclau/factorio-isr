# Health Check + OpenTelemetry Reference Implementation
## Enhanced health.py with Observability

---

## Quick Start

### Minimal Setup (Metrics Only)

```python
# requirements.txt
prometheus-client>=0.17.0
structlog>=22.0.0
aiohttp>=3.8.0
```

```python
# src/health.py - PHASE 1 & 2
import time
import asyncio
from typing import Optional, Dict
from aiohttp import web
import structlog

try:
    from prometheus_client import Gauge, Counter, Histogram, REGISTRY, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = structlog.get_logger()


class HealthCheckServer:
    """Health check server with optional Prometheus metrics."""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        enable_metrics: bool = True
    ):
        """
        Initialize health check server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            enable_metrics: Enable Prometheus /metrics endpoint
        """
        self.host = host
        self.port = port
        self.enable_metrics = enable_metrics and PROMETHEUS_AVAILABLE
        
        # Server lifecycle
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
        # Application state
        self.start_time = time.time()
        self.is_live = False
        self.is_ready = False
        self.component_status: Dict[str, str] = {}
        self.error_counts: Dict[str, int] = {}
        
        # Setup routes and metrics
        self._setup_routes()
        if self.enable_metrics:
            self._setup_prometheus_metrics()
    
    def _setup_routes(self) -> None:
        """Configure HTTP routes."""
        self.app.router.add_get("/healthz", self.liveness_handler)
        self.app.router.add_get("/ready", self.readiness_handler)
        self.app.router.add_get("/health", self.health_handler)  # Legacy
        self.app.router.add_get("/", self.root_handler)
        
        if self.enable_metrics:
            self.app.router.add_get("/metrics", self.metrics_handler)
    
    def _setup_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        if not self.enable_metrics:
            return
        
        # Uptime gauge
        self.uptime_gauge = Gauge(
            'factorio_isr_uptime_seconds',
            'Application uptime in seconds'
        )
        
        # Component status gauge (1=healthy, 0=failed)
        self.component_status_gauge = Gauge(
            'factorio_isr_component_status',
            'Component status (1=healthy, 0=failed)',
            ['component']
        )
        
        # Error counter
        self.errors_counter = Counter(
            'factorio_isr_errors_total',
            'Total errors by component',
            ['component', 'error_type']
        )
        
        # Event counter
        self.events_processed = Counter(
            'factorio_isr_events_processed_total',
            'Total events processed',
            ['server', 'event_type']
        )
        
        # Latency histograms
        self.discord_latency = Histogram(
            'factorio_isr_discord_api_latency_seconds',
            'Discord API latency',
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
        )
        
        self.rcon_latency = Histogram(
            'factorio_isr_rcon_command_latency_seconds',
            'RCON command latency',
            ['server'],
            buckets=(0.01, 0.1, 0.5, 1.0, 5.0, 10.0)
        )
    
    async def liveness_handler(self, request: web.Request) -> web.Response:
        """
        Kubernetes liveness probe: Is the app running?
        
        Returns:
            200 OK if app is alive, 503 if dead
        """
        uptime = time.time() - self.start_time
        is_alive = self.is_live or uptime > 5  # Grace period
        status_code = 200 if is_alive else 503
        
        logger.info(
            "health_liveness_check",
            is_alive=is_alive,
            uptime_seconds=uptime
        )
        
        return web.json_response(
            {
                "status": "alive" if is_alive else "dead",
                "uptime_seconds": uptime,
                "timestamp": time.time()
            },
            status=status_code
        )
    
    async def readiness_handler(self, request: web.Request) -> web.Response:
        """
        Kubernetes readiness probe: Can it handle traffic?
        
        Returns:
            200 OK if ready, 503 if not ready
        """
        is_ready = (
            self.is_ready and
            self.component_status.get("discord") == "healthy" and
            self.component_status.get("log_tailer") == "healthy"
        )
        status_code = 200 if is_ready else 503
        
        # Collect failure reasons
        reasons = []
        if not self.is_ready:
            reasons.append("app_not_initialized")
        if self.component_status.get("discord") != "healthy":
            reasons.append("discord_unhealthy")
        if self.component_status.get("log_tailer") != "healthy":
            reasons.append("log_tailer_unhealthy")
        if self.component_status.get("rcon") != "healthy":
            reasons.append("rcon_unhealthy")
        
        logger.info(
            "health_readiness_check",
            is_ready=is_ready,
            reasons=reasons,
            components=self.component_status
        )
        
        return web.json_response(
            {
                "ready": is_ready,
                "reasons": reasons,
                "components": self.component_status,
                "timestamp": time.time()
            },
            status=status_code
        )
    
    async def health_handler(self, request: web.Request) -> web.Response:
        """
        Legacy /health endpoint. Use /healthz or /ready instead.
        
        Returns:
            200 OK with status info
        """
        return web.json_response({
            "status": "healthy",
            "service": "factorio-isr",
            "uptime_seconds": time.time() - self.start_time,
            "endpoints": {
                "liveness": "/healthz",
                "readiness": "/ready",
                "metrics": "/metrics" if self.enable_metrics else None
            }
        })
    
    async def root_handler(self, request: web.Request) -> web.Response:
        """
        Root endpoint with service info.
        
        Returns:
            200 OK with service info
        """
        return web.json_response({
            "service": "factorio-isr",
            "endpoints": {
                "liveness": "/healthz",
                "readiness": "/ready",
                "health": "/health",
                "metrics": "/metrics" if self.enable_metrics else None
            }
        })
    
    async def metrics_handler(self, request: web.Request) -> web.Response:
        """
        Prometheus metrics endpoint.
        
        Returns:
            Prometheus text format metrics
        """
        if not self.enable_metrics:
            return web.Response(status=404)
        
        # Update gauges
        self.uptime_gauge.set(time.time() - self.start_time)
        
        for component, status in self.component_status.items():
            self.component_status_gauge.labels(component=component).set(
                1 if status == "healthy" else 0
            )
        
        logger.debug("metrics_endpoint_accessed")
        
        # Generate Prometheus output
        metrics_output = generate_latest(REGISTRY).decode('utf-8')
        
        return web.Response(
            text=metrics_output,
            content_type='text/plain; version=0.0.4; charset=utf-8'
        )
    
    # State management methods
    
    async def mark_initializing(self) -> None:
        """Mark app as initializing."""
        self.is_live = False
        self.is_ready = False
        logger.info("health_state_change", state="initializing")
    
    async def mark_live(self) -> None:
        """Mark app as live (running)."""
        self.is_live = True
        logger.info("health_state_change", state="live")
    
    async def mark_ready(self) -> None:
        """Mark app as ready (can handle traffic)."""
        self.is_ready = True
        logger.info("health_state_change", state="ready")
    
    async def mark_component_healthy(self, component: str) -> None:
        """Mark a component as healthy."""
        self.component_status[component] = "healthy"
        self.error_counts[component] = 0
        logger.info(
            "component_status_change",
            component=component,
            status="healthy"
        )
    
    async def mark_component_unhealthy(self, component: str, reason: str) -> None:
        """Mark a component as unhealthy."""
        self.component_status[component] = "unhealthy"
        self.error_counts[component] = self.error_counts.get(component, 0) + 1
        
        # Mark app as not ready
        self.is_ready = False
        
        logger.warning(
            "component_status_change",
            component=component,
            status="unhealthy",
            reason=reason,
            error_count=self.error_counts[component]
        )
        
        if self.enable_metrics:
            self.errors_counter.labels(
                component=component,
                error_type=reason
            ).inc()
    
    def record_event(self, server: str, event_type: str) -> None:
        """Record event processing for metrics."""
        if self.enable_metrics:
            self.events_processed.labels(server=server, event_type=event_type).inc()
    
    def record_discord_latency(self, latency_seconds: float) -> None:
        """Record Discord API latency."""
        if self.enable_metrics:
            self.discord_latency.observe(latency_seconds)
    
    def record_rcon_latency(self, server: str, latency_seconds: float) -> None:
        """Record RCON command latency."""
        if self.enable_metrics:
            self.rcon_latency.labels(server=server).observe(latency_seconds)
    
    # Server lifecycle
    
    async def start(self) -> None:
        """Start the health check server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(
            self.runner,
            self.host,
            self.port
        )
        await self.site.start()
        
        logger.info(
            "health_server_started",
            host=self.host,
            port=self.port,
            metrics_enabled=self.enable_metrics
        )
    
    async def stop(self) -> None:
        """Stop the health check server."""
        if self.site is not None:
            await self.site.stop()
        
        if self.runner is not None:
            await self.runner.cleanup()
        
        logger.info("health_server_stopped")
```

---

## Full Stack (With OpenTelemetry)

### Requirements

```bash
pip install \
  prometheus-client>=0.17.0 \
  opentelemetry-api>=1.19.0 \
  opentelemetry-sdk>=1.19.0 \
  opentelemetry-exporter-prometheus>=0.40b0 \
  opentelemetry-exporter-jaeger>=1.19.0 \
  opentelemetry-instrumentation-aiohttp>=0.40b0 \
  opentelemetry-instrumentation-logging>=0.40b0
```

### Extended health.py with OpenTelemetry

```python
# src/health.py - PHASE 1, 2, & 3

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader


class HealthCheckServer:
    """Enhanced with OpenTelemetry support."""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        enable_metrics: bool = True,
        enable_traces: bool = False,
        jaeger_host: str = "localhost",
        jaeger_port: int = 6831
    ):
        # ... previous __init__ code ...
        
        self.enable_traces = enable_traces
        if enable_traces:
            self._setup_otel_tracing(jaeger_host, jaeger_port)
    
    def _setup_otel_tracing(self, jaeger_host: str, jaeger_port: int) -> None:
        """Initialize OpenTelemetry tracing."""
        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
        )
        
        # Setup tracer provider
        trace_provider = TracerProvider()
        trace_provider.add_span_processor(
            BatchSpanProcessor(jaeger_exporter)
        )
        trace.set_tracer_provider(trace_provider)
        
        # Get tracer
        self.tracer = trace.get_tracer(__name__)
        
        logger.info(
            "otel_tracing_enabled",
            jaeger_host=jaeger_host,
            jaeger_port=jaeger_port
        )
    
    async def liveness_handler(self, request: web.Request) -> web.Response:
        """Enhanced with tracing."""
        if self.enable_traces:
            with self.tracer.start_as_current_span("health_liveness_check") as span:
                span.set_attribute("uptime_seconds", time.time() - self.start_time)
                # ... handler logic ...
        else:
            # ... handler logic without tracing ...
    
    async def readiness_handler(self, request: web.Request) -> web.Response:
        """Enhanced with tracing."""
        if self.enable_traces:
            with self.tracer.start_as_current_span("health_readiness_check") as span:
                span.set_attribute("is_ready", self.is_ready)
                for component, status in self.component_status.items():
                    span.set_attribute(f"component.{component}", status)
                # ... handler logic ...
        else:
            # ... handler logic without tracing ...
```

---

## Integration with Application

### In main.py

```python
async def setup(self) -> None:
    # ... existing setup code ...
    
    # Initialize health check server
    self.health_server = HealthCheckServer(
        host=self.config.health_check_host,
        port=self.config.health_check_port,
        enable_metrics=True,
        enable_traces=getenv("TRACES_ENABLED", "false").lower() == "true"
    )

async def start(self) -> None:
    # ... existing start code ...
    
    await self.health_server.start()
    await self.health_server.mark_live()
    
    # Start components with health tracking
    try:
        self.discord = DiscordInterfaceFactory.create_interface(self.config)
        await self.discord.connect()
        await self.health_server.mark_component_healthy("discord")
    except Exception as e:
        await self.health_server.mark_component_unhealthy("discord", str(e))
        raise
    
    try:
        self.server_manager = ServerManager(...)
        await self.server_manager.add_server(...)
        await self.health_server.mark_component_healthy("rcon")
    except Exception as e:
        await self.health_server.mark_component_unhealthy("rcon", str(e))
        raise
    
    try:
        self.logtailer = MultiServerLogTailer(...)
        await self.logtailer.start()
        await self.health_server.mark_component_healthy("log_tailer")
    except Exception as e:
        await self.health_server.mark_component_unhealthy("log_tailer", str(e))
        raise
    
    # Mark as ready
    await self.health_server.mark_ready()

async def handle_log_line(self, line: str, server_tag: str) -> None:
    # ... existing handler code ...
    
    # Record metrics
    if event is not None:
        self.health_server.record_event(server_tag, event.event_type.value)
```

---

## Testing

### Test Endpoints

```bash
# Liveness
curl http://localhost:8080/healthz
# {"status": "alive", "uptime_seconds": 45.2, "timestamp": 1702315435.123}

# Readiness
curl http://localhost:8080/ready
# {"ready": true, "reasons": [], "components": {...}, "timestamp": 1702315435.456}

# Metrics
curl http://localhost:8080/metrics | grep factorio_isr
# factorio_isr_uptime_seconds 45.6
# factorio_isr_component_status{component="discord"} 1
# factorio_isr_component_status{component="log_tailer"} 1
# factorio_isr_events_processed_total{server="primary",event_type="player_join"} 42
```

### Simulating Component Failures

```python
# Test unhealthy state
await health_server.mark_component_unhealthy("discord", "connection_timeout")

# Should return 503
curl http://localhost:8080/ready
# {"ready": false, "reasons": ["discord_unhealthy"], ...}
```

---

## Docker Compose Example

```yaml
version: '3.8'

services:
  factorio-isr:
    build: .
    environment:
      HEALTH_CHECK_HOST: "0.0.0.0"
      HEALTH_CHECK_PORT: "8080"
      METRICS_ENABLED: "true"
      TRACES_ENABLED: "true"
      JAEGER_AGENT_HOST: "jaeger"
      JAEGER_AGENT_PORT: "6831"
    ports:
      - "8080:8080"  # Health + metrics
    depends_on:
      - jaeger
  
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
  
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "6831:6831/udp"  # Agent
      - "16686:16686"     # UI
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
```

### prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'factorio-isr'
    static_configs:
      - targets: ['factorio-isr:8080']
    metrics_path: '/metrics'
```

---

**See OBSERVABILITY_STRATEGY.md for full implementation roadmap.**
