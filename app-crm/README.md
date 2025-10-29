# app-crm

Сервис синхронизации результатов распознавания listings из `app-ms` с CRM, представленной в виде Google Sheets. Основная задача — получать партии объектов недвижимости, найденных микросервисом, и поддерживать таблицу CRM в консистентном состоянии.

## Быстрый старт

1. **Создай и активируй окружение**

   ```powershell
   python -m venv .venv_crm
   .\.venv_crm\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r app-crm/requirements.txt
   ```

2. **Подготовь конфиги**

   - положи рабочий ключ сервисного аккаунта в `app-crm/config/service_account.json` (файл в `.gitignore`);
   - укажи параметры Google Sheet в `app-crm/config/sheets.local.yml` (см. `sheets.example.yml`).

3. **Запусти сервис**

   ```powershell
   # выполняем из корня репозитория
   $env:PYTHONPATH = "$PWD\app-crm"
   uvicorn app_crm.api:create_app --factory --host 0.0.0.0 --port 8010
   ```

   После старта доступны эндпоинты:
   - `GET /healthz` — проверка живости;
   - `POST /v1/import/listings` — основной импорт.

4. **Смоук-тест**

   - очистить и наполнить лист тестовыми строками: `python app-crm/scripts/seed_sheet.py --truncate --samples 5`;
   - отправить payload `app-crm/docs/smoke_payload.json` (см. `app-crm/docs/smoke-test.md`).

5. **Запуск unit-тестов**

   ```powershell
   pytest tests/app_crm
   ```

## Смоук-тестирование

1. **Сброс таблицы в тестовое состояние**

   ```powershell
   python app-crm/scripts/seed_sheet.py --truncate --samples 5
   ```

   Скрипт очистит лист `V1` ниже заголовка и добавит пять эталонных строк для проверки обновлений и вставок.

2. **Отправка основного payload**

   ```powershell
   $response = Invoke-WebRequest `
     -Uri http://localhost:8010/v1/import/listings `
     -Method POST `
     -ContentType 'application/json' `
     -InFile 'app-crm/docs/smoke_payload.json'
   $response.Content
   ```

   Ожидаемый ответ: `updated = 2`, `inserted = 1`, `duplicates = []`. Повторная отправка должна вернуть тот же summary и тот же `processed_at` (идемпотентность).

3. **Дополнительный точечный кейс**

   Чтобы проверить конкретную строку, можно отправить `app-crm/docs/manual_single.json` (одна запись для `CRM Core XP Tower 4`):

   ```powershell
   $response = Invoke-WebRequest `
     -Uri http://localhost:8010/v1/import/listings `
     -Method POST `
     -ContentType 'application/json' `
     -InFile 'app-crm/docs/manual_single.json'
   $response.Content
   ```

   Запись обновит/добавит строку Tower 4 с площадью 302 м² и новыми значениями аренды/продажи. Проверяйте в Google Sheets, что `rent_month_total_gross`, `sale_price_per_sqm` и `sale_vat_norm` изменились.

4. **Лист request_log**

   В листе `request_log` появляется запись с `request_id`, summary и таймстампом. Если лист отсутствовал, сервис создаст его автоматически при первом запуске.

## Поток данных
- Telegram-бот принимает файл и отправляет его в `app-ms`.
- `app-ms` извлекает listings в табличный вид (Excel/JSON) и по завершении обработки вызывает `app-crm`.
- `app-crm` нормализует данные, находит соответствующие строки в Google Sheets и обновляет их либо добавляет новые записи.

## Протокол взаимодействия с `app-ms`
`app-crm` поднимает REST API (FastAPI/HTTP 1.1). Все вызовы должны идти по HTTPS.

- **Endpoint:** `POST /v1/import/listings`
- **Доступ:** сервис работает внутри приватной сети; дополнительных заголовков авторизации не требуется
- **Idempotency:** `request_id` используется для дедупликации повторных отправок. Повторный вызов с тем же `request_id` возвращает прежний результат без повторного захода в Google Sheets.
- **Обязательные поля в `listings`:** достаточно передать `building_name` и `area_sqm`; остальные атрибуты заполняются по мере наличия. Сервис корректно обрабатывает запросы с неполным набором колонок.
- **`meta`:** опциональный объект с дополнительной информацией о пачке (`listings_total`, идентификаторы, служебные заметки). Сервис его не обрабатывает, но сохраняет в `request_log` для отладки.

### Тело запроса
```json
{
  "request_id": "ce5b2b2d-55b6-4e3e-83ed-7bcf742f9687",
  "source_file": "demo.pdf",
  "received_at": "2025-10-27T17:21:43.512Z",
  "listings": [
    {
      "object_name": "Лофт с отделкой",
      "building_name": "БЦ Омега Плаза",
      "use_type_norm": "Офис",
      "area_sqm": 320.0,
      "divisible_from_sqm": 150.0,
      "floors_norm": "5 этаж",
      "market_type": "Аренда",
      "fitout_condition_norm": "С отделкой",
      "delivery_date_norm": "Готово",
      "rent_rate_year_sqm_base": 22000.0,
      "rent_vat_norm": "С НДС",
      "opex_year_per_sqm": 3000.0,
      "opex_included": "Да",
      "rent_month_total_gross": 586666.7,
      "sale_price_per_sqm": null,
      "sale_vat_norm": null,
      "source_file": "demo.pdf",
      "request_id": "ce5b2b2d-55b6-4e3e-83ed-7bcf742f9687",
      "recognition_summary": "Аренда офиса в БЦ Омега Плаза, площадь 320 кв.м",
      "uncertain_parameters": []
    }
  ],
  "meta": {
    "listings_total": 12,
    "agentql_session": "session-987",
    "pending_questions": []
  }
}
```

Поле `listings` ожидает объекты в том же формате, который описан в `app-ms/README.md` (`output.listing_columns`). Допускается передача пустых значений (`null`/`""`) для отсутствующих данных.

### Ответ сервиса
```json
{
  "request_id": "ce5b2b2d-55b6-4e3e-83ed-7bcf742f9687",
  "processed_at": "2025-10-27T17:21:45.901Z",
  "summary": {
    "updated": 8,
    "inserted": 4,
    "skipped": 0
  },
  "duplicates": [
    {
      "listing_index": 3,
      "reason": "multiple sheet matches (score diff < 0.05)"
    }
  ]
}
```

- **200 OK** — данные синхронизированы; см. `summary`.
- **400 Bad Request** — нарушена схема данных или отсутствуют обязательные поля.
- **409 Conflict** — конфликт с обработкой `request_id` (например, в процессе другого воркера); клиент может повторить запрос позже.
- **5xx** — внутренние ошибки; `app-ms` повторяет попытку с экспоненциальной паузой.

## Работа с Google Sheets
- Таблица CRM копирует структуру Excel, сформированного `app-ms`: каждая строка — одно помещение.
- Базовая конфигурация задаётся переменными окружения:
  - `CRM_GOOGLE_SERVICE_ACCOUNT_JSON` — JSON сервисного аккаунта (строка или путь к файлу).
  - `CRM_SHEET_ID` — идентификатор таблицы.
  - `CRM_SHEET_NAME` — лист внутри таблицы (по умолчанию `Listings`).
  - `CRM_MATCH_AREA_TOLERANCE` — допустимое отклонение площади в м² (по умолчанию `2.0`).
  - `CRM_MATCH_NAME_THRESHOLD` — порог схожести названия здания (0…1, по умолчанию `0.82`).
  - `CRM_BATCH_SIZE` — размер пачки обновлений в одном вызове Google Sheets API (по умолчанию `50`).
- Для ускорения поиска сервис кэширует последние чтения листа в Redis (опционально): `CRM_CACHE_URL`.
- Взаимодействие с Google Sheets повторяет стандартный CRM-поток: чтение `spreadsheets.values.batchGet`, обновление `spreadsheets.values.batchUpdate`, добавление строк через `spreadsheets.values.append`.

## Алгоритм синхронизации
1. **Валидация партии.** Проверить уникальность `request_id`, схему полей и наличие ключевых значений (`building_name`, `area_sqm`).
2. **Загрузка актуальных данных.** Получить диапазон листа (строки + заголовки). Строим внутренний индекс:
   - нормализованное название здания;
   - площадь в м²;
   - позиция строки.
3. **Обработка каждого объекта.**
   1. Подготовить значения: проверить, что `building_name` и `area_sqm` заполнены, обрезать внешние пробелы. Пустая площадь или `0` — запись в `skipped`.
   2. Выполнить поиск строки по названию здания (см. раздел ниже). Алгоритм возвращает одно совпадение, список кандидатов для дублей или `None`.
   3. При найденной строке сформировать массив значений в порядке столбцов листа и выполнить batchUpdate (`updateCells`) с указанием номера строки; обновить служебные поля `updated_at`, `source_file` (если есть).
   4. При отсутствии совпадений вызвать `appendRows`, сохранить индекс добавленной строки в отчёте и очистить связанный кеш.
4. **Постобработка.**
   - Записать в таблицу `request_log` (отдельный лист) `request_id`, тайминги, счётчики и статус.
   - Очистить кэш, связанный с обновлёнными строками.
   - Вернуть сводку клиенту.

### Поиск по названию здания
1. При загрузке листа формируется индекс `exact_index[building_name] -> [RowInfo]` и вспомогательные соответствия из словаря `CRM_NAME_ALIASES`.
2. **Прямое совпадение.** Используем входной `building_name` как есть: данные уже нормализованы в `app-ms` и в таблице, дополнительно выполняется только `strip()`. Сразу отбрасываем строки, где `abs(area_sheet - area_incoming) > CRM_MATCH_AREA_TOLERANCE`.
3. **Алиасы.** Если прямого попадания нет, ищем каноническое название по `CRM_NAME_ALIASES` (словарь общий со стандартным CRM) и повторяем поиск.
4. **Фаззи-сравнение.** Для оставшихся строк считаем `SequenceMatcher.ratio` (или Levenshtein). Совпадение принимается, если `score >= CRM_MATCH_NAME_THRESHOLD`; отклонение площади уменьшает итоговый балл.
5. Если найдено несколько строк с разницей `score < 0.05`, объект помечается как `duplicate`, а кандидаты возвращаются в `duplicates`.
6. При отсутствии кандидатов возвращаем `None`, объект добавляется как новая строка.
7. Дополнительного нормирования не требуется: используем названия из листинга без преобразований, кроме обрезки пробелов.

## Расширения и задачи на будущее
- Поддержка обработки обновлений по Webhook от Google Sheets для актуализации локального кэша.
- Веб-интерфейс для просмотра лога синхронизаций и ручного разрешения `duplicate`-записей.
- Отправка уведомлений (Slack/Telegram) при превышении порога ошибок или при ручном вмешательстве.
