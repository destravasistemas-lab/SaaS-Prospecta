# ============================================================
# STAGE 1: Build - Image base para instalar dependências
# ============================================================
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt

# ============================================================
# STAGE 2: Runtime - Image final enxuta
# ============================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_PORT=8000 \
    APP_HOST=0.0.0.0 \
    UVICORN_WORKERS=4

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --ingroup appuser --no-create-home appuser

WORKDIR /app

COPY --from=builder /root/.local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /root/.local/bin /usr/local/bin

COPY . .

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE $APP_PORT

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:$APP_PORT/health')" || exit 1

CMD uvicorn app.main:app \
    --host $APP_HOST \
    --port $APP_PORT \
    --workers $UVICORN_WORKERS \
    --proxy-headers \
    --forwarded-allow-ips '*'
