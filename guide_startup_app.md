# Guide: подключение к VM и развёртывание UD-MVP (бот + микросервисы)

## 1. Подключение к VPN (если требуется внутренняя сеть)

> Шаги из исходного onboarding: применимо, если GitLab/стенд видны только через L2TP.

- В админском PowerShell (локальная машина Windows):
  ```powershell
  powershell -ExecutionPolicy Bypass -File "C:\BI core XP\vpn1.ps1"
  ```
  Создаст профиль `CORE-XP L2TP VPN` для всех пользователей.
- Проверить профиль/статус:
  ```powershell
  Get-VpnConnection -Name "CORE-XP L2TP VPN" -AllUserConnection | Format-List Name,ConnectionStatus,ServerAddress
  ```
- Подключение (вводить пароль вручную):
  ```powershell
  rasdial "CORE-XP L2TP VPN" Vendor_SRiabova "<пароль>"
  # или
  rasdial "CORE-XP L2TP VPN" Vendor_VKrupiy "<пароль>"
  ```
  Без сохранения пароля в истории:
  ```powershell
  $cred = Get-Credential -UserName Vendor_SRiabova
  rasdial "CORE-XP L2TP VPN" $cred.UserName $cred.GetNetworkCredential().Password
  ```
- Проверить доступность: `rasdial`, далее `ping moskrgit01.core-xp.net` и `curl -k -I https://moskrgit01.core-xp.net/` (фолбэк IP `10.6.97.50`).
- Отключить или пересоздать профиль при сбоях:
  ```powershell
  rasdial "CORE-XP L2TP VPN" /disconnect
  Remove-VpnConnection -Name "CORE-XP L2TP VPN" -AllUserConnection -Force
  ```

## 2. SSH-доступ

- Хост (старый): `10.6.97.25`, пользователь: `cyberdb_admin`, пароль: `xR^83` (первый вход — вручную).
- Хост (новый, NL, без VPN): `185.216.87.237`, пользователь: `cyberdb_user` (доступ по паролю/ключу).

---

- Вход старый: `ssh cyberdb_admin@10.6.97.25`
- Вход новый: `ssh cyberdb_user@185.216.87.237`
- После входа (опционально) сменить пароль: `passwd`
- Проверить группы: `whoami && groups` (должны быть `sudo` и `docker`).

## 3. Базовая подготовка (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential git curl ffmpeg pandoc libreoffice-common poppler-utils tmux
# docker (если нет): sudo apt install -y docker.io docker-compose-plugin
```

## 4. Перенос кода и репозитория на новый сервер (NL, без прямого доступа к GitLab)

### Быстрый перенос архивами (старый → новый)

- На старом (`cyberdb_admin@10.6.97.25`):
  ```bash
  cd /opt/ud-mvp
  tar czf /tmp/ud-mvp.tar.gz \
    --exclude '.git' \
    --exclude '.venv*' \
    --exclude 'app-audio/whisper-diarization/.git' \
    .
  cp /opt/ud-mvp/.env /tmp/.env
  cp /opt/ud-mvp/app-crm/config/service_account.json /tmp/service_account.json 2>/dev/null
  cp /opt/ud-mvp/app-crm/config/sheets.local.yml /tmp/sheets.local.yml 2>/dev/null
  scp /tmp/ud-mvp.tar.gz cyberdb_user@185.216.87.237:/tmp/
  scp /tmp/.env cyberdb_user@185.216.87.237:/tmp/.env
  scp /tmp/service_account.json cyberdb_user@185.216.87.237:/tmp/ 2>/dev/null
  scp /tmp/sheets.local.yml cyberdb_user@185.216.87.237:/tmp/ 2>/dev/null
  ```
- На новом (`cyberdb_user@185.216.87.237`):
  ```bash
  sudo mkdir -p /opt/ud-mvp && sudo chown "$USER":"$USER" /opt/ud-mvp
  tar xzf /tmp/ud-mvp.tar.gz -C /opt/ud-mvp
  [ -f /tmp/.env ] && mv /tmp/.env /opt/ud-mvp/.env
  [ -f /tmp/service_account.json ] && mkdir -p /opt/ud-mvp/app-crm/config && mv /tmp/service_account.json /opt/ud-mvp/app-crm/config/
  [ -f /tmp/sheets.local.yml ] && mkdir -p /opt/ud-mvp/app-crm/config && mv /tmp/sheets.local.yml /opt/ud-mvp/app-crm/config/
  ```

### Копирование секретов/артефактов

- На старом сервере:
  ```bash
  cd /opt/ud-mvp
  tar czf /tmp/ud-secrets.tar.gz \
    .env \
    app-crm/config/service_account.json \
    app-crm/config/sheets.local.yml \
    data/results \
    data/uploads
  scp /tmp/ud-secrets.tar.gz cyberdb_user@185.216.87.237:/tmp/
  ```
- На новом сервере:
  ```bash
  sudo mkdir -p /opt/ud-mvp && sudo chown "$USER":"$USER" /opt/ud-mvp
  tar xzf /tmp/ud-secrets.tar.gz -C /opt/ud-mvp
  ```

### Git-туннель (если нужен прямой pull/push из GitLab)

- Требования: на новом сервере добавлен SSH-ключ в GitLab (проверка: `ssh -p 2222 git@localhost` должно сказать Welcome, когда туннель активен).
- Если ключа нет, на старом сервере:
  ```bash
  ssh-keygen -t ed25519 -C "vendor_vkrupiy@core-xp.net" -f ~/.ssh/id_ed25519
  ssh-copy-id -i ~/.ssh/id_ed25519.pub cyberdb_user@185.216.87.237   # добавит ключ на новый сервер
  ```
- Запускается на старом сервере (или любом узле с доступом к GitLab) в tmux, пример с портом 2223 и keepalive:
  ```bash
  tmux new -s gitlab-tunnel 'ssh -i ~/.ssh/id_ed25519 -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o TCPKeepAlive=yes -R 2223:moskrgit01.core-xp.net:22 cyberdb_user@185.216.87.237'
  ```
- На новом сервере проверить, что порт слушает, и тест SSH:
  ```bash
  ss -tnlp | grep 2223
  ssh -p 2223 git@localhost   # Welcome... без пароля
  ```
- На новом сервере использовать tunneled origin:

  ```bash
  # чистый клон через туннель (при необходимости)
  # sudo rm -rf /opt/ud-mvp && sudo mkdir -p /opt/ud-mvp && sudo chown "$USER":"$USER" /opt/ud-mvp
  # GIT_SSH_COMMAND='ssh -p 2223' git clone ssh://git@localhost:2223/Vendor_VKrupiy/ud.git /opt/ud-mvp

  cd /opt/ud-mvp
  git remote set-url origin ssh://git@localhost:2223/Vendor_VKrupiy/ud.git
  GIT_SSH_COMMAND='ssh -p 2223' git fetch
  GIT_SSH_COMMAND='ssh -p 2223' git pull
  ```

- Когда появится прямой доступ к GitLab, вернуть обычный origin:
  ```bash
  git remote set-url origin git@moskrgit01.core-xp.net:Vendor_VKrupiy/ud.git
  ```

### Копирование с сохранением истории (без доступа к GitLab)

- На старом сервере:
  ```bash
  cd /opt/ud-mvp
  git fetch --all
  git bundle create /tmp/ud.bundle --all
  scp /tmp/ud.bundle cyberdb_user@185.216.87.237:/tmp/
  ```
- На новом сервере:
  ```bash
  sudo mkdir -p /opt/ud-mvp && sudo chown "$USER":"$USER" /opt/ud-mvp
  cd /opt/ud-mvp
  git clone /tmp/ud.bundle .
  git remote remove origin 2>/dev/null
  # при желании можно добавить origin на туннель/прямой GitLab позже
  ```
  Для обновлений повторяйте `git bundle` → `scp` → `git pull /tmp/ud.bundle` до появления прямого доступа.

### Туннель для OpenAI API (если прямой доступ недоступен)

- Запускается на узле с доступом к api.openai.com (например, старый сервер) в tmux, пример на порту 8443:
  ```bash
  tmux new -s oai-tunnel 'ssh -i ~/.ssh/id_ed25519 -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o TCPKeepAlive=yes -L 127.0.0.1:8443:api.openai.com:443 cyberdb_user@185.216.87.237'
  ```
- На сервере, откуда идут запросы (старый), включить редирект в iptables (без /etc/hosts):
  ```bash
  sudo iptables -t nat -A OUTPUT -p tcp -d api.openai.com --dport 443 -j REDIRECT --to-ports 8443
  ```
  Если ранее добавляли строку в `/etc/hosts`, удалите её (иначе редирект не сработает):
  ```bash
  sudo sed -i '/api\.openai\.com/d' /etc/hosts
  ```
  Теперь обращения к стандартному `https://api.openai.com` пойдут через туннель. Чтобы отменить редирект:
  ```bash
  sudo iptables -t nat -D OUTPUT -p tcp -d api.openai.com --dport 443 -j REDIRECT --to-ports 8443
  ```

Если `docker-compose-plugin` недоступен в стандартных репозиториях, ставим из Docker CE:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Проверка: `docker --version` и `docker compose version`.

## 5. Рабочая директория и код

> По умолчанию `git clone` создаёт подкаталог с именем репозитория. Чтобы сразу клонировать в `/opt/ud-mvp`, укажите путь назначения. Если уже клонировали в подкаталог, перенесите содержимое и удалите вложенную папку.

```bash
sudo mkdir -p /opt/ud-mvp && sudo chown "$USER":"$USER" /opt/ud-mvp
cd /opt/ud-mvp
git clone <repo_url> /opt/ud-mvp   # клонировать прямо в рабочую директорию
```

Если уже склонировали в подкаталог (например, `/opt/ud-mvp/UD-MVP`), можно переложить содержимое в `/opt/ud-mvp`:

```bash
cd /opt/ud-mvp
shopt -s dotglob && mv UD-MVP/* . && rmdir UD-MVP
```

После размещения кода создайте каталоги данных:

```bash
mkdir -p data/results data/uploads
```

## 6. Локальный запуск (Windows 11 + WSL2)

- Рабочая папка: `C:\ud-mvp2` (в WSL: `/mnt/c/ud-mvp2`).
- Команды выполняйте в WSL (Ubuntu). PowerShell — только для копирования файлов и проверок.
- Попплер в WSL ставится через `poppler-utils` (бинарники в `/usr/bin`).
- Для WSL используйте в `.env`:
  ```
  POPPLER_PATH=/usr/bin
  SOFFICE_PATH=/usr/bin/soffice
  ```
- Быстрый запуск всех сервисов (tmux-сессии):
  ```bash
  cd /mnt/c/ud-mvp2
  bash ./start_all.sh
  ```
- Проверка из PowerShell (localhost или IP WSL):
  ```powershell
  Invoke-RestMethod -Uri "http://localhost:8001/health"
  Invoke-RestMethod -Uri "http://localhost:8010/healthz"
  Invoke-RestMethod -Uri "http://localhost:8000/healthz"
  # если localhost не отвечает:
  $wslIp = (wsl hostname -I).Split()[0]
  Invoke-RestMethod -Uri "http://$wslIp:8001/health"
  Invoke-RestMethod -Uri "http://$wslIp:8010/healthz"
  Invoke-RestMethod -Uri "http://$wslIp:8000/healthz"
  ```

## 7. Установка зависимостей (раздельные окружения)

```bash
cd /opt/ud-mvp
python3 -m venv .venv_audio && source .venv_audio/bin/activate && pip install --upgrade pip && pip install -r app-audio/requirements.txt && deactivate
python3 -m venv .venv_crm && source .venv_crm/bin/activate && pip install --upgrade pip && pip install -r app-crm/requirements.txt && deactivate
python3 -m venv .venv_ms && source .venv_ms/bin/activate && pip install --upgrade pip && pip install -r app-ms/requirements.txt && deactivate
python3 -m venv .venv_bot && source .venv_bot/bin/activate && pip install --upgrade pip && pip install -r requirements.txt && deactivate
```

Для app-audio при отсутствии GPU можно принудительно поставить CPU Torch:

```bash
source /opt/ud-mvp/.venv_audio/bin/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.2.2
deactivate
```

## 8. Переменные окружения и секреты

- Общий `.env` в корне `/opt/ud-mvp/.env` (используют бот и microservices):

  ```
  BOT_TOKEN=...
  MICROSERVICE_BASE_URL=http://127.0.0.1:8000
  WEBHOOK_URL=https://your.domain/webhook   # если нужен вебхук
  MAX_FILE_MB=20

  AGENTQL_API_KEY=...          # или OPENAI_* токены для app-ms
  OPENAI_API_KEY=...
  OPENAI_MODEL=gpt-5
  OPENAI_VISION_MODEL=gpt-5.2
  BASE_URL=http://localhost:8000
  RESULTS_DIR=/opt/ud-mvp/data/results
  APP_AUDIO_URL=http://127.0.0.1:8001/v1/transcribe
  APP_CRM_URL=http://127.0.0.1:8010/v1/import/listings
  APP_AUDIO_LANGUAGE=ru
  APP_AUDIO_MODEL=medium
  ```

  По необходимости добавьте `POPPLER_PATH`, `SOFFICE_PATH`.

- app-crm:
  - Файл `app-crm/config/service_account.json` (ключ сервисного аккаунта, в git не хранится).
  - Настроить `app-crm/config/sheets.local.yml` по образцу `sheets.example.yml`
    или задать переменные: `CRM_GOOGLE_SERVICE_ACCOUNT_JSON`, `CRM_SHEET_ID`, `CRM_SHEET_NAME`, `CRM_CACHE_URL`.
    Если `sheets.local.yml` отсутствует, CRM возьмёт ID/лист из переменных `.env` (`CRM_SHEET_ID`, `CRM_SHEET_NAME`, опционально `CRM_SERVICE_ACCOUNT_FILE`/`CRM_GOOGLE_SERVICE_ACCOUNT_JSON`).
  - Заливка ключа на сервер (пример из Windows с кавычками в пути):  
    PowerShell/Git Bash: `scp "C:\Users\<you>\Downloads\cred.json" cyberdb_admin@10.6.97.25:/opt/ud-mvp/app-crm/config/service_account.json`  
    WSL: `scp /mnt/c/Users/<you>/Downloads/cred.json cyberdb_admin@10.6.97.25:/opt/ud-mvp/app-crm/config/service_account.json`  
    После копирования: `sudo chown cyberdb_admin:cyberdb_admin /opt/ud-mvp/app-crm/config/service_account.json`.
  - Прописать значения в `.env` (если не используете `sheets.local.yml`):
    ```bash
    python3 - <<'PY'
    from pathlib import Path
    env_path = Path("/opt/ud-mvp/.env")
    updates = {
        "CRM_GOOGLE_SERVICE_ACCOUNT_JSON": "/opt/ud-mvp/app-crm/config/service_account.json",
        "CRM_SHEET_ID": "<your_sheet_id>",
        "CRM_SHEET_NAME": "<sheet_name>",
    }
    lines = env_path.read_text().splitlines()
    out, seen = [], set()
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else None
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    env_path.write_text("\n".join(out) + "\n")
    PY
    ```
  - Готовый патч для `.env` (добавит/обновит переменные CRM, остальные строки не тронет):
    ```bash
    python3 - <<'PY'
    from pathlib import Path
    env_path = Path("/opt/ud-mvp/.env")
    updates = {
        "CRM_GOOGLE_SERVICE_ACCOUNT_JSON": "/opt/ud-mvp/app-crm/config/service_account.json",
        "CRM_SHEET_ID": "1EsTUY7LxJ3T_20Kqr25I-qruawxV6oo0upc01eLUmrk",
        "CRM_SHEET_NAME": "V1",
    }
    lines = env_path.read_text().splitlines()
    out, seen = [], set()
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else None
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    env_path.write_text("\n".join(out) + "\n")
    PY
    ```
- app-audio: переменные берутся из корневого `.env` (путь `/opt/ud-mvp/.env`). Формат для TORCH и модели:
  ```
  TORCH_DEVICE=cpu    # или cuda если есть GPU
  APP_AUDIO_MODEL=medium   # при необходимости
  ```
  CPU по умолчанию (Torch 2.2.2). Для GPU подберите пакет под CUDA (см. https://pytorch.org/get-started/locally/).
  Убедитесь, что есть зависимый репозиторий `app-audio/whisper-diarization` (если нет — `git clone --depth 1 https://github.com/MahmoudAshraf97/whisper-diarization.git app-audio/whisper-diarization`).
  Системные пакеты для PyAV: `sudo apt-get install -y pkg-config ffmpeg libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libavfilter-dev`.
  Единый патч `.env` (замени плейсхолдеры, остальные строки не тронет):
  ```bash
  python - <<'PY'
  from pathlib import Path
  env_path = Path("/opt/ud-mvp/.env")
  updates = {
      "BOT_TOKEN": "<your_bot_token>",
      "MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
      "WEBHOOK_URL": "https://your.domain/webhook",
      "MAX_FILE_MB": "20",
      "AGENTQL_API_KEY": "<your_agentql_or_openai_key>",
      "BASE_URL": "http://localhost:8000",
      "RESULTS_DIR": "/opt/ud-mvp/data/results",
      "OPENAI_API_KEY": "<your_openai_key>",
      "OPENAI_MODEL": "gpt-5",
      "OPENAI_VISION_MODEL": "gpt-5.2",
      "APP_AUDIO_URL": "http://127.0.0.1:8001/v1/transcribe",
      "APP_CRM_URL": "http://127.0.0.1:8010/v1/import/listings",
      "APP_AUDIO_LANGUAGE": "ru",
      "APP_AUDIO_MODEL": "medium",
      "POPPLER_PATH": "/usr/bin",
      "SOFFICE_PATH": "/usr/bin/soffice",
      "CRM_GOOGLE_SERVICE_ACCOUNT_JSON": "/opt/ud-mvp/app-crm/config/service_account.json",
      "CRM_SHEET_ID": "<your_sheet_id>",
      "CRM_SHEET_NAME": "V1",
  }
  lines = env_path.read_text().splitlines()
  out, seen = [], set()
  for line in lines:
      key = line.split("=", 1)[0] if "=" in line else None
      if key in updates:
          out.append(f"{key}={updates[key]}")
          seen.add(key)
      else:
          out.append(line)
  for k, v in updates.items():
      if k not in seen:
          out.append(f"{k}={v}")
  env_path.write_text("\n".join(out) + "\n")
  PY
  ```

## 9. Запуск сервисов (рекомендуется tmux, чтобы не блокировать терминал)

Создайте venv и установите зависимости (один раз), затем поднимайте сервисы в отдельных tmux-сессиях `-d` (в фоне). Логи можно смотреть `tmux attach -t <name>` и выходить `Ctrl+b d`.

### app-audio (порт 8001)

```bash
cd /opt/ud-mvp
python3 -m venv .venv_audio && source .venv_audio/bin/activate
pip install -r app-audio/requirements.txt
# зависимости whisper-diarization
cd app-audio/whisper-diarization && pip install -r requirements.txt -c constraints.txt && cd /opt/ud-mvp
tmux new -s audio -d 'cd /opt/ud-mvp && source .venv_audio/bin/activate && uvicorn app-audio.main:app --host 0.0.0.0 --port 8001 --env-file /opt/ud-mvp/.env'
```

### app-crm (порт 8010)

```bash
cd /opt/ud-mvp
python3 -m venv .venv_crm && source .venv_crm/bin/activate
pip install -r app-crm/requirements.txt
export PYTHONPATH="$PWD/app-crm"
# Важно подхватить .env перед стартом
tmux new -s crm -d 'cd /opt/ud-mvp && set -a && source /opt/ud-mvp/.env && set +a && export PYTHONPATH=/opt/ud-mvp/app-crm && source /opt/ud-mvp/.venv_crm/bin/activate && uvicorn app_crm.api:create_app --factory --host 0.0.0.0 --port 8010'
```

Проверка: `curl http://localhost:8010/healthz`

### app-ms (порт 8000)

```bash
cd /opt/ud-mvp/app-ms
python3 -m venv ../.venv_ms && source ../.venv_ms/bin/activate
pip install -r requirements.txt
tmux new -s ms -d 'cd /opt/ud-mvp/app-ms && source /opt/ud-mvp/.venv_ms/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --env-file /opt/ud-mvp/.env'
```

Smoke: `curl -X POST -F "file=@app-ms/examples/demo.pdf" http://localhost:8000/process_file -o listings.xlsx`

### Telegram-бот (polling или webhook, порт 8080 при вебхуке)

```bash
cd /opt/ud-mvp
python3 -m venv .venv_bot && source .venv_bot/bin/activate
pip install -r requirements.txt
tmux new -s bot -d 'cd /opt/ud-mvp && source .venv_bot/bin/activate && BOT_TOKEN=... MICROSERVICE_BASE_URL=http://127.0.0.1:8000 python -m app.polling_runner'
# webhook-вариант:
# tmux new -s bot -d 'cd /opt/ud-mvp && source .venv_bot/bin/activate && BOT_TOKEN=... MICROSERVICE_BASE_URL=http://127.0.0.1:8000 WEBHOOK_URL=https://your.domain/webhook python -m app.main'
```

## 10. Порядок старта и чек-лист

1. app-audio → 2) app-crm (если нужен) → 3) app-ms → 4) бот.  
   Health: `curl http://localhost:8001/health` (audio), `curl http://localhost:8010/healthz`, `curl http://localhost:8000/healthz`.  
   Убедиться, что бот стучится в `MICROSERVICE_BASE_URL=http://127.0.0.1:8000`.

### Быстрый старт всех сервисов + туннель OpenAI (старый сервер)

```bash
# туннель OpenAI (порт 8443 -> api.openai.com:443 через новый сервер)
tmux kill-session -t oai-tunnel 2>/dev/null || true
tmux new -s oai-tunnel -d 'ssh -i ~/.ssh/id_ed25519 -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o TCPKeepAlive=yes -L 127.0.0.1:8443:api.openai.com:443 cyberdb_user@185.216.87.237'

# перезапуск микросервисов и бота
for s in audio crm ms bot; do tmux kill-session -t "$s" 2>/dev/null || true; done
tmux new -s audio -d 'cd /opt/ud-mvp && source /opt/ud-mvp/.venv_audio/bin/activate && uvicorn app-audio.main:app --host 0.0.0.0 --port 8001 --env-file /opt/ud-mvp/.env'
tmux new -s crm   -d 'cd /opt/ud-mvp && set -a && source /opt/ud-mvp/.env && set +a && export PYTHONPATH=/opt/ud-mvp/app-crm && source /opt/ud-mvp/.venv_crm/bin/activate && uvicorn app_crm.api:create_app --factory --host 0.0.0.0 --port 8010'
tmux new -s ms    -d 'cd /opt/ud-mvp/app-ms && source /opt/ud-mvp/.venv_ms/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --env-file /opt/ud-mvp/.env'
tmux new -s bot   -d 'cd /opt/ud-mvp && source /opt/ud-mvp/.venv_bot/bin/activate && python -m app.polling_runner'
```

### Проверка сервисов и OpenAI

```bash
# сервисы
curl http://localhost:8001/health
curl http://localhost:8010/healthz
curl http://localhost:8000/healthz

# OpenAI через туннель 8443
curl --connect-to api.openai.com:443:127.0.0.1:8443 https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -n 5
```

## 11. Прод-режим/демоны

- Можно держать процессы в `tmux`/`screen`.
- Для systemd: `ExecStart=/opt/ud-mvp/.venv_ms/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --env-file /opt/ud-mvp/.env`, `WorkingDirectory=/opt/ud-mvp/app-ms`. Аналогично для app-audio, app-crm, бота.
- Открыть/проксировать порты 8000/8001/8010/8080 по необходимости; при вебхуке — закрыть всё, публиковать только HTTP(S) фронт (через Nginx) и Telegram webhook.

## 12. Фактическая установка на новом сервере (декабрь 2025)

На NL-сервере `cyberdb_user@185.216.87.237` были ограничения: системный `python3.12` без `ensurepip`/`pip`, нет прав на `apt install build-essential`, отсутствуют gcc/g++ и poppler, поэтому сборка `whisper-diarization` и pdf2image ломалась. Выбрали Miniconda — позволила без sudo получить компилятор и poppler, собрать C++-модули и не трогать системный питон.

### 12.1. Miniconda и тулчейн

```bash
cd /opt/ud-mvp
curl -sSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p /opt/ud-mvp/miniconda3
/opt/ud-mvp/miniconda3/bin/conda create -y -p /opt/ud-mvp/conda-audio python=3.12 pip
/opt/ud-mvp/miniconda3/bin/conda install -y -c conda-forge gxx_linux-64=13.2.0
/opt/ud-mvp/miniconda3/bin/conda install -y -p /opt/ud-mvp/conda-audio -c conda-forge gxx_linux-64=13.2.0 poppler=24.09.0
ln -sf /opt/ud-mvp/conda-audio/bin/x86_64-conda-linux-gnu-gcc /opt/ud-mvp/conda-audio/bin/gcc
ln -sf /opt/ud-mvp/conda-audio/bin/x86_64-conda-linux-gnu-g++ /opt/ud-mvp/conda-audio/bin/g++
```

### 12.2. App-audio (CPU) в conda

```bash
# .env дополнен: TORCH_DEVICE=cpu, POPPLER_PATH=/opt/ud-mvp/conda-audio/bin
/opt/ud-mvp/conda-audio/bin/pip install -r /opt/ud-mvp/app-audio/requirements.txt
CC=/opt/ud-mvp/conda-audio/bin/gcc CXX=/opt/ud-mvp/conda-audio/bin/g++ \
PATH="/opt/ud-mvp/conda-audio/bin:$PATH" \
/opt/ud-mvp/conda-audio/bin/pip install --no-cache-dir \
  -r /opt/ud-mvp/app-audio/whisper-diarization/requirements.txt \
  -c /opt/ud-mvp/app-audio/whisper-diarization/constraints.txt
```

### 12.3. CRM / MS / бот (venv без sudo)

```bash
python3 -m venv --without-pip .venv_crm && ./.venv_crm/bin/python /tmp/get-pip.py && ./.venv_crm/bin/pip install -r app-crm/requirements.txt
python3 -m venv --without-pip .venv_ms  && ./.venv_ms/bin/python  /tmp/get-pip.py && ./.venv_ms/bin/pip  install -r app-ms/requirements.txt
python3 -m venv --without-pip .venv_bot && ./.venv_bot/bin/python /tmp/get-pip.py && ./.venv_bot/bin/pip install -r requirements.txt
```

### 12.4. Ключевые правки .env

```env
TORCH_DEVICE=cpu
POPPLER_PATH=/opt/ud-mvp/conda-audio/bin
APP_AUDIO_URL=http://127.0.0.1:8001/v1/transcribe
APP_AUDIO_LANGUAGE=ru
APP_AUDIO_MODEL=medium
CRM_SHEET_ID=1EsTUY7LxJ3T_20Kqr25I-qruawxV6oo0upc01eLUmrk
CRM_SHEET_NAME=V1
```

### 12.5. Реальные команды запуска (tmux)

```bash
tmux new -s audio -d '/opt/ud-mvp/conda-audio/bin/python -m uvicorn app-audio.main:app --host 0.0.0.0 --port 8001 --env-file /opt/ud-mvp/.env'
tmux new -s crm   -d 'cd /opt/ud-mvp && export PYTHONPATH=/opt/ud-mvp/app-crm && source .venv_crm/bin/activate && uvicorn app_crm.api:create_app --factory --host 0.0.0.0 --port 8010 --env-file /opt/ud-mvp/.env'
tmux new -s ms    -d 'cd /opt/ud-mvp/app-ms && source ../.venv_ms/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --env-file /opt/ud-mvp/.env'
tmux new -s bot   -d 'cd /opt/ud-mvp && source .venv_bot/bin/activate && python -m app.polling_runner'
```

Проверки: `curl http://localhost:8001/health`, `curl http://localhost:8010/healthz`, `curl http://localhost:8000/healthz`.

### 12.6. Что ломалось и как починили

- Нет `ensurepip`/`pip` в системном python → ставили pip через `get-pip.py` внутри venv.
- Отсутствие gcc/g++ → conda `gxx_linux-64`.
- pdf2image жаловался на Poppler → conda `poppler` и `POPPLER_PATH` в `.env`.
- whisper-diarization не собирался без компилятора → сборка в conda-окружении с явным `CC/CXX`.
- На старом сервере не было прямого доступа к `api.openai.com:443` и `api.telegram.org:443` → подняли SSH-туннели на новый сервер и пустили трафик через него.
- Туннель `oai-tunnel` не поднимался и просил пароль → публичный ключ старого сервера добавили в `~/.ssh/authorized_keys` пользователя `cyberdb_user` на новом сервере.
- Бот не реагировал, хотя процесс был жив → в логах `aiogram` было `Cannot connect to host api.telegram.org:443`, после поднятия `tg-tunnel` связь восстановилась.
- В `.env` была строка `WEBHOOK_URL= https://...` с пробелом после `=` → `source .env` пытался исполнить URL как команду, строку исправили на `WEBHOOK_URL=https://...`.
- После восстановления сети бот всё ещё ловил `TelegramConflictError` → оказался запущен второй polling-бот на другом узле, лишний экземпляр остановили.
- `make start` на сервере мог падать с `Permission denied` на `./start_all.sh` → безопаснее запускать `bash ./start_all.sh`, либо дать файлу `chmod +x`.

### 12.7. Прод: восстановление OpenAI и Telegram через новый сервер

1. Проверить, что старый сервер ходит на новый по ключу:

```bash
ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 cyberdb_user@185.216.87.237 'echo ok-from-new'
```

2. Поднять туннель OpenAI:

```bash
tmux kill-session -t oai-tunnel 2>/dev/null || true
tmux new -s oai-tunnel -d 'while true; do ssh -i ~/.ssh/id_ed25519 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o TCPKeepAlive=yes -N -L 127.0.0.1:8443:api.openai.com:443 cyberdb_user@185.216.87.237; sleep 5; done'
ss -tnlp | grep 8443
```

3. Поднять туннель Telegram:

```bash
tmux kill-session -t tg-tunnel 2>/dev/null || true
tmux new -s tg-tunnel -d 'while true; do ssh -i ~/.ssh/id_ed25519 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o TCPKeepAlive=yes -N -L 127.0.0.1:8445:api.telegram.org:443 cyberdb_user@185.216.87.237; sleep 5; done'
ss -tnlp | grep 8445
```

4. Проверить туннели напрямую, в обход стандартного `443`:

```bash
cd /opt/ud-mvp
set -a && source /opt/ud-mvp/.env && set +a

curl --connect-to api.openai.com:443:127.0.0.1:8443 https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head

curl --connect-to api.telegram.org:443:127.0.0.1:8445 "https://api.telegram.org/bot$BOT_TOKEN/getMe"
```

5. Если нужно, включить редирект на стандартные endpoint'ы через `iptables`.
   Важно: IP у Telegram/OpenAI могут меняться, перед добавлением правил лучше проверить актуальный резолв:

```bash
getent ahostsv4 api.openai.com
getent ahostsv4 api.telegram.org
```

Пример рабочих правил:

```bash
sudo iptables -t nat -A OUTPUT -p tcp -d 172.66.0.243 --dport 443 -j REDIRECT --to-ports 8443
sudo iptables -t nat -A OUTPUT -p tcp -d 162.159.140.245 --dport 443 -j REDIRECT --to-ports 8443
sudo iptables -t nat -A OUTPUT -p tcp -d 149.154.166.110 --dport 443 -j REDIRECT --to-ports 8445
```

6. Проверить уже стандартные endpoint'ы:

```bash
cd /opt/ud-mvp
set -a && source /opt/ud-mvp/.env && set +a

curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" | head
curl "https://api.telegram.org/bot$BOT_TOKEN/getMe"
```

Если OpenAI отвечает JSON с `invalid_api_key` и пустым ключом, сеть уже работает, проблема только в том, что в текущую shell не загружен `.env`.

### 12.8. Диагностика бота

- Проверить tmux-сессию и хвост лога:

```bash
tmux ls
tmux capture-pane -pt bot -S -120
```

- Если в логе `Cannot connect to host api.telegram.org:443`:
  - проверить `tg-tunnel`;
  - проверить `curl --connect-to api.telegram.org:443:127.0.0.1:8445 "https://api.telegram.org/bot$BOT_TOKEN/getMe"`;
  - проверить `iptables`-редирект на актуальный IP `api.telegram.org`.

- Если в логе `TelegramConflictError: terminated by other getUpdates request`:
  - найти и остановить второй polling-экземпляр с тем же `BOT_TOKEN`;
  - проверить локальный WSL, старый сервер, новый сервер и другие рабочие узлы;
  - после этого перезапустить один bot:

```bash
tmux kill-session -t bot 2>/dev/null || true
tmux new -s bot -d 'cd /opt/ud-mvp && source /opt/ud-mvp/.venv_bot/bin/activate && MICROSERVICE_BASE_URL=http://127.0.0.1:8000 python -m app.polling_runner'
```

- Если `tmux new -s bot ...` сразу завершается:
  - проверить, что используется правильное окружение `.venv_bot`, а не `.venv`;
  - посмотреть ручной запуск:

```bash
cd /opt/ud-mvp
set -a && source /opt/ud-mvp/.env && set +a
source /opt/ud-mvp/.venv_bot/bin/activate
MICROSERVICE_BASE_URL=http://127.0.0.1:8000 python -m app.polling_runner
```

### 12.9. Быстрые smoke-checks прод-сервера

```bash
cd /opt/ud-mvp
set -a && source /opt/ud-mvp/.env && set +a

curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:8010/healthz
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" >/dev/null && echo openai-ok
curl -fsS "https://api.telegram.org/bot$BOT_TOKEN/getMe" >/dev/null && echo telegram-ok
tmux ls
```
