# Как запустить сервисы в WSL (локальные poppler/pandoc/libreoffice)

1) Подготовка
- Установи зависимости в виртуалки: `.venv_ms`, `.venv_audio`, `.venv_crm`, `.venv_bot`.
- Скачай локальный Poppler и Pandoc (уже лежат в `app-ms/.poppler_local` и `app-ms/.pandoc_local`), LibreOffice — `C:\Program Files\LibreOffice\program\soffice.exe`.
- Проверь `.env` в корне (`/mnt/c/UD-MVP/.env`).

2) Запуск всех сервисов
- Открой WSL в `/mnt/c/UD-MVP`.
- Выполни: `bash start_all.sh`.
- Скрипт сам проставит:
  - `POPPLER_PATH` → `app-ms/.poppler_local/usr/bin`
  - `LD_LIBRARY_PATH` → `app-ms/.poppler_local/usr/lib/x86_64-linux-gnu`
  - `PANDOC_PATH` + `PATH` → `app-ms/.pandoc_local/bin`
  - `SOFFICE_PATH` → `/mnt/c/Program Files/LibreOffice/program/soffice.exe`
- Сервисы стартуют в tmux сессиях: `audio` (8001), `crm` (8010), `ms` (8000), `bot`.
- Скрипт проверит здоровье: `http://127.0.0.1:{8001,8010,8000}/healthz` и выведет ok/fail.

3) Управление
- Посмотреть сессии: `tmux ls`.
- Присоединиться: `tmux attach -t ms` (или `audio`/`crm`/`bot`).
- Остановить: `tmux kill-session -t ms` (или нужная сессия).

4) Запуск только ms (если нужно)
```bash
cd /mnt/c/UD-MVP/app-ms
source ../.venv_ms/bin/activate
export POPPLER_PATH=/mnt/c/UD-MVP/app-ms/.poppler_local/usr/bin
export LD_LIBRARY_PATH=/mnt/c/UD-MVP/app-ms/.poppler_local/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}
export PANDOC_PATH=/mnt/c/UD-MVP/app-ms/.pandoc_local/bin/pandoc
export PATH=/mnt/c/UD-MVP/app-ms/.pandoc_local/bin:$PATH
export SOFFICE_PATH="/mnt/c/Program Files/LibreOffice/program/soffice.exe"
uvicorn main:app --host 0.0.0.0 --port 8000 --env-file ../.env
```

Примечания:
- Если здоровье вернуло `fail`, проверь логи в tmux-сессиях.
- Проект лежит на `/mnt/c`, на больших нагрузках быстрее работать из ext4, но с локальными бинари без sudo это допустимо.
