# Multi‑stage Dockerfile for the realtime collaboration WebSocket server

# ---------- Builder stage ----------
FROM python:3.14-slim AS builder
WORKDIR /app

# Install build‑time dependencies needed for compiled extensions (y‑py, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY services/command_center/realtime_collab ./services/command_center/realtime_collab
COPY scripts ./scripts

# Run tests to verify the build (optional but ensures image quality)
RUN pytest -q

# ---------- Runtime stage ----------
FROM python:3.14-slim AS runtime
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY services/command_center/realtime_collab ./services/command_center/realtime_collab
COPY scripts ./scripts

# Expose the default WS port
EXPOSE 8000

# Default command runs the server (TLS optional via flags)
CMD ["python", "-m", "services.command_center.realtime_collab.server"]