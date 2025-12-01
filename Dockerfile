# Build stage
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.14-slim

LABEL org.opencontainers.image.title="Factorio ISR"
LABEL org.opencontainers.image.description="Real-time Factorio server event monitoring with Discord integration"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="https://github.com/stephenclau/factorio-isr"
LABEL org.opencontainers.image.source="https://github.com/stephenclau/factorio-isr"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/factorio-isr/.local/bin:${PATH}"

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create user
ARG UID=845
ARG GID=845
RUN groupadd -g ${GID} factorio-isr && \
    useradd -u ${UID} -g ${GID} -m -s /bin/bash factorio-isr

# Copy Python packages from builder
COPY --from=builder --chown=factorio-isr:factorio-isr /root/.local /home/factorio-isr/.local

# Copy application
COPY --chown=factorio-isr:factorio-isr src/ ./src/
COPY --chown=factorio-isr:factorio-isr patterns/ ./patterns/

USER factorio-isr

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

STOPSIGNAL SIGTERM

CMD ["python", "-m", "src.main"]
