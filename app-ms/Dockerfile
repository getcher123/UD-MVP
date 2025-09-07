# ---------- Base builder image ----------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: LibreOffice, fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-calc libreoffice-impress \
      fonts-dejavu fonts-liberation \
      curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app-ms/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Runtime image ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-calc libreoffice-impress \
      fonts-dejavu fonts-liberation \
      curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash appuser && mkdir -p /data/results /tmp/pdf && chown -R appuser:appuser /data /tmp/pdf
USER appuser

WORKDIR /app

COPY --from=base /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=base /usr/local/bin /usr/local/bin

COPY --chown=appuser:appuser app-ms/ /app/

ENV RESULTS_DIR=/data/results \
    DEFAULT_QUERY_PATH=/app/queries/default_query.txt

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
