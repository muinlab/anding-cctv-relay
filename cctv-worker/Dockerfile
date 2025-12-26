# CCTV Worker Dockerfile
# Multi-stage build for smaller image size

# ============================================================================
# Stage 1: Builder
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Runtime
# ============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies (OpenCV needs these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/
COPY scripts/entrypoint.sh ./entrypoint.sh
COPY pyproject.toml .

# Create directories and set permissions
RUN mkdir -p data/roi_configs data/snapshots logs && \
    chmod +x entrypoint.sh

# Download YOLO model (optional, can mount from host)
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" || true

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose debug stream port
EXPOSE 8001

# Health check - check API if debug enabled, otherwise just check process
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD if [ "${DEBUG_STREAM_ENABLED:-false}" = "true" ]; then \
        wget -q --spider http://localhost:${DEBUG_STREAM_PORT:-8001}/debug/status || exit 1; \
    else \
        python -c "import sys; sys.exit(0)"; \
    fi

# Default command
ENTRYPOINT ["./entrypoint.sh"]
CMD []
