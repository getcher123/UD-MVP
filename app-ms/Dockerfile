# syntax=docker/dockerfile:1.7-labs

# ---------- Base: только Python deps ----------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) Установим только Python-зависимости (с кэшем pip)
COPY app-ms/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    pip install -r requirements.txt

# ---------- Runtime: системные пакеты + скопировать site-packages ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000 \
    DEBIAN_FRONTEND=noninteractive

# 2) LibreOffice и прочие системные зависимости СТАВИМ ОДИН РАЗ (здесь)
#    Добавим ретраи и таймауты для apt (устойчивость к сети)
RUN --mount=type=cache,target=/var/cache/apt \
    set -eux; \
    apt-get update -o Acquire::Retries=5 -o Acquire::http::Timeout=30; \
    apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-calc libreoffice-impress \
      fonts-dejavu fonts-liberation \
      curl ca-certificates; \
    rm -rf /var/lib/apt/lists/*

# 3) Пользователь и каталоги данных
RUN useradd -ms /bin/bash appuser \
 && mkdir -p /data/results /tmp/pdf \
 && chown -R appuser:appuser /data /tmp/pdf
USER appuser

WORKDIR /app

# 4) Переносим Python из base-слоя (установка пакетов уже была)
COPY --from=base /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=base /usr/local/bin /usr/local/bin

# 5) Кладём код
COPY --chown=appuser:appuser app-ms/ /app/

ENV RESULTS_DIR=/data/results \
    DEFAULT_QUERY_PATH=/app/queries/default_query.txt

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]