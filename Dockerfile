# Multi-stage build for SOCIALMEDIAAUTOMATION
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY SOCIALMEDIAAUTOMATION.py .
COPY scheduler_daemon.py .
COPY editorial.py studio.html ./
COPY content/demo-privacy-en.jpg ./content/demo-privacy-en.jpg

RUN mkdir -p /data

ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.getenv('PORT', '8000'))"

EXPOSE 8000

# FastAPI lifespan owns the scheduler companion; Uvicorn stays PID 1.
CMD ["sh", "-c", "exec uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port ${PORT:-8000}"]
