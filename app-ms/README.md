# UD-MVP Microservice (app-ms)

Назначение: **принять файл → привести к PDF → извлечь через AgentQL → нормализовать → вернуть Excel/JSON.**

Микросервис предоставляет простой HTTP API, который принимает загруженный файл, прогоняет его через конвертацию и извлечение данных, нормализует результаты и возвращает структурированный ответ.

* **Вход:** документы (PDF/DOCX/PPTX/XLSX/JPG/PNG) и аудио (WAV/MP3/M4A/OGG/AAC).
* **Подготовка:** документы конвертируются в PDF; аудио отправляется в сервис app-audio (/v1/transcribe) с diar=true.
* **Извлечение:** для документов запускается AgentQL с QUERY, для аудио используется ChatGPT по SRT из app-audio.
* **Нормализация:** очистка и приведение данных к целевой структуре объектов.
* **Выход:** Excel и/или JSON с помещениями (listings) — одна строка = одно помещение.

> Микросервис работает в режимах document и audio; ветка выбирается по типу загруженного файла.

---

## Эндпоинты

* `GET /healthz` — проверка готовности.
* `GET /version` — версия микросервиса.
* `POST /process_file` — загрузка файла и получение результата.

### `POST /process_file`

**Форма:** `multipart/form-data`

Поля:

* `file` — бинарный файл (обязательно)
* `output` — `excel` | `json` | `both` (по умолчанию `excel`)
* `return_sheet_url` — `true|false` (по умолчанию `false`; зарезервировано под интеграцию с Google Sheets)
* `request_id` — строка для идемпотентности (опционально)

**Ответ (пример при `output=excel`):**

```json
{
  "request_id": "b9c7e8f0b2d14c1bbf7c4a0f4e2d9a55",
  "items_count": 42,
  "excel_url": "https://<BASE_URL>/results/b9c7e8f0.../listings.xlsx",
  "pending_questions": [],
  "meta": {
    "source_file": "input.pdf",
    "timing_ms": 4312,
    "listings_total": 42
  }
}
```

**Коды ошибок:** `400` (валидация/тип/размер), `422` (конвертация PDF), `424` (AgentQL), `429` (rate limit), `500` (внутренняя).

---

## Локальный запуск

```bash
cd app-ms
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --env-file ./.env
`
> Для обработки аудио потребуется запущенный сервис app-audio (см. app-audio/README.md).``

**Smoke (curl):**

```bash
curl -X POST \
  -F "file=@examples/demo.pdf" \
  http://localhost:8000/process_file -o listings.xlsx
```

**HTTPie:**

```bash
http --form POST :8000/process_file file@examples/demo.pdf output:=both
```

---

## Переменные окружения

* `AGENTQL_API_KEY` — ключ для AgentQL.
* `DEFAULT_QUERY_PATH` — путь к QUERY (по умолчанию `app-ms/queries/default_query.txt`).
* `RESULTS_DIR` — каталог для результата (по умолчанию `data/results`).
* APP_AUDIO_URL — базовый URL сервиса app-audio (/v1/transcribe).
* APP_AUDIO_TIMEOUT — таймаут запроса к app-audio (секунды).
* APP_AUDIO_LANGUAGE / APP_AUDIO_MODEL — необязательные параметры по умолчанию для распознавания.
* AUDIO_TYPES — список расширений, которые обрабатываются как аудио (по умолчанию WAV/MP3/M4A/OGG/AAC).
* `BASE_URL` — базовый URL для формирования `excel_url` (опционально).
* Прочие — см. `core/config.py`.

---

## Выходной формат (листинги)

**Уровень:** **ЛИСТИНГИ** — **каждая строка** = одно помещение, **без группировки по зданиям**.

**Строгий порядок колонок** задаётся в `config/defaults.yml → output.listing_columns`:

1. `listing_id`
2. `object_id`
3. `object_name`
4. `building_id`
5. `building_name`
6. `use_type_norm`
7. `area_sqm`
8. `divisible_from_sqm`
9. `floors_norm`
10. `market_type`
11. `fitout_condition_norm`
12. `delivery_date_norm`
13. `rent_rate_year_sqm_base`
14. `rent_vat_norm`
15. `opex_year_per_sqm`
16. `opex_included`
17. `rent_month_total_gross`
18. `sale_price_per_sqm`
19. `sale_vat_norm`
20. `source_file`
21. `request_id`
22. `quality_flags`

**Имена/ID:**

* `building_name` = `{object_name}` + `", {token}"` (если извлечён токен: `стр. 1`, `корпус 2`, `литера Б`, `блок C`).
* `building_id` = `{object_id}__{building_token_slug}`; если токена нет — `{object_id}`.
* `listing_id` — конкатенация нормализованных частей (`object_id`, `building_token_slug`, `use_type_norm_slug`, `floors_norm_slug`, `area_1dp`) + короткий хэш `basename` файла-источника (см. `identifier.listing_id` в конфиге).

**Excel:**

* один лист, freeze заголовка (A2), включён автофильтр;
* числовые колонки — без символов валют.

---

## Этажи (мультиэтажность)

Поддерживаются одиночные значения, **списки** и **диапазоны**:

* списки: разделители `,`, `;`, `/`, `и`, `&`
* диапазоны: `-` или `–`
* удаляются служебные слова: `этаж`, `эт`, `э.`
* спец-этажи: `подвал` (−1), `цоколь`, `мезонин`
* **рендер:** численные этажи сортируются, подряд идущие объединяются в диапазоны, спец-строки остаются как есть, итог — соединяется `"; "`.

**Примеры:**

* `"1 и 2"` → `"1–2"`
* `"1,3;5"` → `"1; 3; 5"`
* `"цоколь/1-2"` → `"1–2; цоколь"`

---

## Нормализация и расчёты (основные правила)

* **Числа/валюта:** убрать пробелы/валюту, `,` → `.`, всё хранить как `float`.
* **Тип использования:** в канон `{офис, торговое, псн, склад}` (синонимы — см. конфиг).
* **Отделка:** `{с отделкой, под отделку}` (синонимы — см. конфиг).
* **Даты:** ISO `YYYY-MM-DD` или `"сейчас"`; `Q{1-4} YYYY` → конец квартала.
* **VAT:** `{включен, не применяется}`; при пустом значении на листинге — наследование с уровня объекта.
* **OPEX:** `opex_included` (`True/False`), `opex_year_per_sqm` — `float|None`.
* **Годовая ставка аренды без НДС и OPEX (`rent_rate_year_sqm_base`):**

  1. если есть прямая годовая ставка за м² — взять её;
  2. иначе реконструировать из **месячной суммы**:

     ```
     base_month = rent_cost_month_per_room / (1 + vat_rate_if_included)
     rent_rate_year_sqm_base = (base_month * 12) / area_sqm - (opex_year_per_sqm if not opex_included else 0)
     ```

  * пороги выбросов: см. `quality.outliers` в конфиге.
* **Месячная «грязная» сумма (`rent_month_total_gross`):**

  ```
  gross_month = ((rent_rate_year_sqm_base + (0 if opex_included else opex_year_per_sqm or 0)) * area_sqm) * (1 + vat_rate) / 12
  ```

---

## Конфигурация правил

Все бизнес-правила хранятся в `app-ms/config/defaults.yml` и подгружаются при старте.
Ключевые блоки:

* `normalization` — синонимы, парсинг дат, этажей, VAT/OPEX.
* `identifier.listing_id` — как строится `listing_id`.
* `output.listing_columns` — **строгий порядок** колонок Excel.

Изменение YAML не требует правки кода (при неизменной схеме).

---

## Проверка

**Через API (возврат Excel):**

```bash
curl -X POST \
  -F "file=@service_AQL/input/28.04.2025 -Таблица по свободным площадям.pdf" \
  http://localhost:8000/process_file -o listings.xlsx
```

**Офлайн (если добавлен скрипт преобразования JSON AgentQL → Excel):**

```bash
python app-ms/scripts/json_to_listings_excel.py "service_AQL/input/28.04.2025 -Таблица по свободным площадям.json" --request-id demo_28042025
# Результат: data/results/demo_28042025/listings.xlsx
```

---

## Изменения по сравнению с ранними версиями

* ❗ **Отказ от агрегирования по зданиям.** Теперь **каждый листинг** — отдельная строка с уникальным `listing_id`.
* Обновлены `defaults.yml`, генерация `building_name`/`building_id`, нормализация **мультиэтажности** и формулы дериваций.

---

## Тесты

Рекомендуется прогонять:

* `tests/unit/test_floors.py` — парсинг/рендер этажей;
* `tests/unit/test_ids_helper.py` — генерация `listing_id`/`building_id`/`building_name`;
* `tests/integration/test_flatten_listings.py` — сквозной сценарий: JSON → нормализация → Excel.

---

## Docker

Сборка образа (из корня репозитория):

```powershell
docker build -t ud-ms:latest -f app-ms/Dockerfile .
```

Запуск контейнера с пробросом порта и тома для результатов:

```powershell
New-Item -ItemType Directory -Force .\data | Out-Null
docker run --rm -p 8000:8000 -v "${PWD}\data:/data" --env-file .env ud-ms:latest
```

Проверка здоровья и загрузка файла:

```powershell
Invoke-WebRequest http://localhost:8000/healthz | Select-Object -ExpandProperty Content
curl.exe -F "file=@service_AQL\input\28.04.2025 -Таблица по свободным площадям.pdf" http://localhost:8000/process_file -o listings.xlsx
```

Замечания:

- По умолчанию результаты пишутся в `/data/results` внутри контейнера; за счёт `-v ${PWD}\data:/data` они доступны на хосте в `./data/results`.
- Для Windows PowerShell используйте `curl.exe` (а не алиас `curl`).
- Если используется корпоративный прокси, передавайте его в сборку: `--build-arg HTTP_PROXY=... --build-arg HTTPS_PROXY=...`.
- Для стабильной сборки рекомендуется увеличить память Docker Desktop до 4–6 GB (LibreOffice тянет зависимости).

