FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies before source, so a code change doesn't invalidate the slow install layer.
COPY requirements.txt .
RUN pip install -r requirements.txt

# The trained artifacts ship inside app/ml/artifacts. ml/ and data/ are included
# so the demo generator works and the model can be retrained inside the container.
COPY app ./app
COPY ml ./ml
COPY scripts ./scripts
COPY data ./data

# Unprivileged user. /data holds the SQLite file and should be mounted as a volume.
RUN useradd --create-home --uid 10001 triage && mkdir -p /data && chown triage /data
USER triage

ENV DATABASE_URL=sqlite+aiosqlite:////data/triageai.db \
    ENVIRONMENT=production \
    PORT=8000 \
    SEED_TICKETS=80

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=4)"

# A single uvicorn worker on purpose: the WebSocket hub is in-process, so a second
# worker would never see events published on the first (see app/core/events.py).
# An empty database is seeded once so a fresh deploy has something to show.
CMD ["sh", "-c", "python -m scripts.seed --if-empty --n \"$SEED_TICKETS\" && exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips='*'"]
