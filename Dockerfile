# Multi-stage build for SOCIALMEDIAAUTOMATION

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /root/.local /root/.local
COPY SOCIALMEDIAAUTOMATION.py .

# Set environment variables
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.getenv('PORT', '8000'))"

# Expose the local default. Railway injects PORT at runtime.
EXPOSE 8000

# Run the application on the hosting-assigned port.
CMD ["sh", "-c", "uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port ${PORT:-8000}"]
