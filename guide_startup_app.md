# Guide: подключение к VM и развёртывание UD-MVP (бот + микросервисы)

## 1. SSH-доступ
- Хост: `10.6.97.25`
- Пользователь: `cyberdb_admin`
- Пароль: `xR^83` (первый вход — вводить вручную, без copy-paste).
---
- Команда входа: `ssh cyberdb_admin@10.6.97.25`
- После входа (опционально) сменить пароль: `passwd`
- Проверить группы: `whoami && groups` (должны быть `sudo` и `docker`).

## 2. Подключение к VPN (если требуется внутренняя сеть)
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

## 2. Базовая подготовка (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential git curl ffmpeg pandoc libreoffice-common poppler-utils tmux
# docker (если нет): sudo apt install -y docker.io docker-compose-plugin
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

## 3. Рабочая директория и код
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

## 4. Установка зависимостей (раздельные окружения)
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

## 5. Переменные окружения и секреты
- Общий `.env` в корне `/opt/ud-mvp/.env` (используют бот и microservices):
  ```
  BOT_TOKEN=...
  MICROSERVICE_BASE_URL=http://127.0.0.1:8000
  WEBHOOK_URL=https://your.domain/webhook   # если нужен вебхук
  MAX_FILE_MB=20

  AGENTQL_API_KEY=...          # или OPENAI_* токены для app-ms
  BASE_URL=http://localhost:8000
  RESULTS_DIR=/opt/ud-mvp/data/results
  APP_AUDIO_URL=http://127.0.0.1:8001
  APP_CRM_URL=http://127.0.0.1:8010      # если используем CRM
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
    python - <<'PY'
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
    python - <<'PY'
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
  APP_AUDIO_DEFAULT_MODEL=medium   # при необходимости
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
      "APP_AUDIO_URL": "http://127.0.0.1:8001",
      "APP_CRM_URL": "http://127.0.0.1:8010",
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

## 6. Запуск сервисов (рекомендуется tmux, чтобы не блокировать терминал)
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
tmux new -s crm -d 'cd /opt/ud-mvp && export PYTHONPATH=/opt/ud-mvp/app-crm && source .venv_crm/bin/activate && uvicorn app_crm.api:create_app --factory --host 0.0.0.0 --port 8010'
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

## 7. Порядок старта и чек-лист
1) app-audio → 2) app-crm (если нужен) → 3) app-ms → 4) бот.  
Health: `curl http://localhost:8001/health` (audio), `curl http://localhost:8010/healthz`, `curl http://localhost:8000/healthz`.  
Убедиться, что бот стучится в `MICROSERVICE_BASE_URL=http://127.0.0.1:8000`.

## 8. Прод-режим/демоны
- Можно держать процессы в `tmux`/`screen`.
- Для systemd: `ExecStart=/opt/ud-mvp/.venv_ms/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --env-file /opt/ud-mvp/.env`, `WorkingDirectory=/opt/ud-mvp/app-ms`. Аналогично для app-audio, app-crm, бота.
- Открыть/проксировать порты 8000/8001/8010/8080 по необходимости; при вебхуке — закрыть всё, публиковать только HTTP(S) фронт (через Nginx) и Telegram webhook.

## 9. Безопасный WireGuard-туннель (чтобы не потерять SSH)
- Не ставьте дефолтный маршрут через WG, пока не увидите рукопожатие (`received > 0` в `wg show`).
- Конфиг с split-трафиком (пример, подставьте свои ключи/endpoint/DNS):  
  ```
  [Interface]
  PrivateKey = <your_private_key>
  Address = 10.x.x.x/32
  DNS = 10.64.0.1
  Table = off
  PostUp = ip route replace 10.6.0.0/16 dev ens160; for ip in $(dig +short A api.openai.com @10.6.97.50 | grep -E '^[0-9.]+$'); do ip route replace ${ip}/32 dev wg0; done
  PostDown = ip route del 10.6.0.0/16 2>/dev/null; for ip in $(dig +short A api.openai.com @10.6.97.50 | grep -E '^[0-9.]+$'); do ip route del ${ip}/32 2>/dev/null; done

  [Peer]
  PublicKey = <server_public_key>
  AllowedIPs = 0.0.0.0/0, ::/0    # оставляем, но Table=off + PostUp не перехватит SSH
  Endpoint = <server_ip>:<port>
  PersistentKeepalive = 25
  ```
- Поднимаем только в `tmux`: `sudo wg-quick up wg0`, проверяем `sudo wg show` (должен появиться recv > 0), затем `ip route get <ip api.openai.com>` — должно идти через wg0, SSH остаётся через ens160.
- Отключить туннель: `sudo wg-quick down wg0`. Не включайте `systemctl enable wg-quick@wg0`, пока не убедились в стабильности.
- Если что-то пошло не так и есть консоль/OOB: `sudo wg-quick down wg0 && sudo ip route replace default via 10.6.97.1 dev ens160 && sudo ip route flush table 51820 && sudo ip rule del table 51820`.

## 10. Контроль после входа на VM
```bash
whoami && hostname && uname -a
df -h
free -h
```
Проверить docker (по требованию): `docker ps` или `docker compose version`.

## Утилиты для VPN-туннелей (WireGuard)
- Установка (Ubuntu/Debian):  
  ```bash
  sudo apt update
  sudo apt install -y wireguard-tools dnsutils
  sudo mkdir -p /etc/wireguard && sudo chmod 755 /etc/wireguard
  ```
- Работа с туннелем:  
  ```bash
  sudo wg-quick up wg0
  sudo wg-quick down wg0
  sudo wg show
  ```
- Автозапуск после проверки: `sudo systemctl enable wg-quick@wg0`; отключить: `sudo systemctl disable wg-quick@wg0`.
- Примеры создания конфигов:
  - Базовый (весь трафик, сначала проверяйте handshake, чтобы не потерять SSH):
    ```bash
    sudo tee /etc/wireguard/wg0.conf >/dev/null <<'EOF'
    [Interface]
    PrivateKey = <your_private_key>
    Address = 10.0.0.2/32
    DNS = 1.1.1.1
    Table = off

    [Peer]
    PublicKey = <server_public_key>
    AllowedIPs = 0.0.0.0/0, ::/0
    Endpoint = <server_ip>:<port>
    PersistentKeepalive = 25
    EOF
    sudo chmod 600 /etc/wireguard/wg0.conf
    ```
  - Split-трафик (пример с исключением локальной сети и маршрутами только к api.openai.com):
    ```bash
    sudo tee /etc/wireguard/wg0.conf >/dev/null <<'EOF'
    [Interface]
    PrivateKey = <your_private_key>
    Address = 10.x.x.x/32
    DNS = 10.64.0.1
    Table = off
    PostUp = ip route replace 10.6.0.0/16 dev ens160; for ip in $(dig +short A api.openai.com @10.6.97.50 | grep -E '^[0-9.]+$'); do ip route replace ${ip}/32 dev wg0; done
    PostDown = ip route del 10.6.0.0/16 2>/dev/null; for ip in $(dig +short A api.openai.com @10.6.97.50 | grep -E '^[0-9.]+$'); do ip route del ${ip}/32 2>/dev/null; done

    [Peer]
    PublicKey = <server_public_key>
    AllowedIPs = 0.0.0.0/0, ::/0
    Endpoint = <server_ip>:<port>
    PersistentKeepalive = 25
    EOF
    sudo chmod 600 /etc/wireguard/wg0.conf
    ```
  - Резервная копия и смена порта/endpoint:
    ```bash
    sudo cp /etc/wireguard/wg0.conf /etc/wireguard/wg0.conf.bak
    sudo sed -i 's/^Endpoint = .*/Endpoint = <new_ip>:<new_port>/' /etc/wireguard/wg0.conf
    ```
