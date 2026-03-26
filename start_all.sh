#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo ".env not found at $ENV_FILE" >&2
  exit 1
fi

mkdir -p "$ROOT/data/results" "$ROOT/data/uploads"

start_tmux() {
  local name="$1"; shift
  tmux kill-session -t "$name" 2>/dev/null || true
  tmux new -s "$name" -d "$*"
}

check_health() {
  local url="$1" name="$2"
  curl -fsS "$url" >/dev/null && echo "[ok] $name: $url" || echo "[fail] $name: $url"
}

# audio (8001)
start_tmux audio "cd \"$ROOT\" && source \"$ROOT/.venv_audio/bin/activate\" && uvicorn app-audio.main:app --host 0.0.0.0 --port 8001 --env-file \"$ENV_FILE\""

# crm (8010)
start_tmux crm "cd \"$ROOT\" && set -a && source \"$ENV_FILE\" && set +a && export PYTHONPATH=\"$ROOT/app-crm\" && source \"$ROOT/.venv_crm/bin/activate\" && uvicorn app_crm.api:create_app --factory --host 0.0.0.0 --port 8010"

# ms (8000)
# локальные бинари без sudo
POPPLER_BIN="$ROOT/app-ms/.poppler_local/usr/bin"
POPPLER_LIB="$ROOT/app-ms/.poppler_local/usr/lib/x86_64-linux-gnu"
PANDOC_BIN="$ROOT/app-ms/.pandoc_local/bin/pandoc"
SOFFICE_BIN="/mnt/c/Program Files/LibreOffice/program/soffice.exe"
start_tmux ms "cd \"$ROOT/app-ms\" && export POPPLER_PATH=\"$POPPLER_BIN\" && export LD_LIBRARY_PATH=\"$POPPLER_LIB:\${LD_LIBRARY_PATH:-}\" && export PANDOC_PATH=\"$PANDOC_BIN\" && export PATH=\"$ROOT/app-ms/.pandoc_local/bin:\$PATH\" && export SOFFICE_PATH=\"$SOFFICE_BIN\" && source \"$ROOT/.venv_ms/bin/activate\" && uvicorn main:app --host 0.0.0.0 --port 8000 --env-file \"$ENV_FILE\""

# bot (polling)
start_tmux bot "cd \"$ROOT\" && source \"$ROOT/.venv_bot/bin/activate\" && MICROSERVICE_BASE_URL=http://127.0.0.1:8000 python -m app.polling_runner"

echo "tmux sessions started: audio, crm, ms, bot"
sleep 2
check_health "http://127.0.0.1:8001/healthz" "audio"
check_health "http://127.0.0.1:8010/healthz" "crm"
check_health "http://127.0.0.1:8000/healthz" "ms"
