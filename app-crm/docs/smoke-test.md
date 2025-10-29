# Смоук‑тест CRM сервиса

Документ описывает базовый сценарий проверки работоспособности CRM сервиса после деплоя или локальных изменений. Смоук‑тест закрывает основные цепочки: чтение конфигурации, обновление существующих строк и добавление новых записей в Google Sheets, а также проверку идемпотентности REST API.

## 1. Предварительные условия

- **Google Service Account**: файл `app-crm/config/service_account.json` с рабочим ключом сервисного аккаунта, имеющего роль *Editor* на таблицу CRM.
- **Конфигурация листа**: заполненный `app-crm/config/sheets.local.yml` (см. пример `sheets.example.yml`) с корректным `spreadsheet_id`, именем листа (`V1`) и номером строки заголовка.
- **Зависимости**: активированное виртуальное окружение и установленные пакеты
  ```powershell
  python -m venv .venv_crm
  .\.venv_crm\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  python -m pip install -r app-crm/requirements.txt
  ```
- **Работающий CRM сервис**: поднять API согласно README (например, `uvicorn app.main:app --reload --port 8010`). Все запросы выполняются по HTTPS/HTTP с отключённой авторизацией.

## 2. Подготовка тестовых данных в Google Sheets

1. Очистить лист и заполнить его стабильной выборкой:
   ```powershell
   python app-crm/scripts/seed_sheet.py `
     --truncate `
     --samples 5
   ```
   Скрипт оставляет заголовок и создаёт 5 строк вида:

| # | building_name            | area_sqm | divisible_from_sqm | fitout_condition_norm | rent_rate_year_sqm_base | rent_vat_norm | opex_year_per_sqm | opex_included | sale_price_per_sqm | sale_vat_norm |
|---|--------------------------|---------:|--------------------:|-----------------------|-------------------------:|---------------|------------------:|---------------|--------------------:|---------------|
| 1 | CRM Core XP Tower 1      | 225      | 145                 | С отделкой            | 21 500                   | С НДС         | 2 620             | Да            | 185 000             | С НДС         |
| 2 | CRM Core XP Tower 2      | 250      | 170                 | Без отделки           | 23 000                   | С НДС         | 2 740             | Да            | 190 000             | Без НДС       |
| 3 | CRM Core XP Tower 3      | 275      | 195                 | С отделкой            | 24 500                   | С НДС         | 2 860             | Да            | 195 000             | С НДС         |
| 4 | CRM Core XP Tower 4      | 300      | 220                 | Без отделки           | 26 000                   | С НДС         | 2 980             | Да            | 200 000             | Без НДС       |
| 5 | CRM Core XP Tower 5      | 325      | 245                 | С отделкой            | 27 500                   | С НДС         | 3 100             | Да            | 205 000             | С НДС         |

   > `request_id` и `updated_at` генерируются динамически при каждом запуске.

2. Убедиться, что лист `request_log` (если используется) очищен либо содержит тестовый лист для логирования.

## 3. Тестовый запрос к CRM

Подготовленный payload лежит в `app-crm/docs/smoke_payload.json`. Он проверяет:
- обновление существующих строк для `CRM Core XP Tower 1` и `CRM Core XP Tower 3`;
- добавление новой строки `CRM Core XP Tower 9`.

Отправка запроса:

```powershell
curl -X POST http://localhost:8010/v1/import/listings `
  -H "Content-Type: application/json" `
  --data-binary "@app-crm/docs/smoke_payload.json"
```

Ожидаемый ответ (200 OK):

```json
{
  "request_id": "smoke-req-2025-10-31-01",
  "summary": {
    "updated": 2,
    "inserted": 1,
    "skipped": 0
  },
  "duplicates": []
}
```

## 4. Проверка обновлений в таблице

### 4.1. Строки, которые должны измениться

| building_name       | Поля для сверки                                                                                   |
|---------------------|----------------------------------------------------------------------------------------------------|
| CRM Core XP Tower 1 | `divisible_from_sqm = 130`, `rent_rate_year_sqm_base = 22 200`, `rent_month_total_gross = 467 812,50`, `sale_price_per_sqm = 185 000`, `sale_vat_norm = "С НДС"` |
| CRM Core XP Tower 3 | `fitout_condition_norm = "Без отделки"`, `rent_rate_year_sqm_base = 25 500`, `rent_month_total_gross = 653 125,00`, `sale_price_per_sqm = 195 000`, `sale_vat_norm = "С НДС"` |

Обе строки должны содержать `source_file = smoke_manual.xlsx` и `request_id = smoke-req-2025-10-31-01`, а `updated_at` должен обновиться на серверное значение.

### 4.2. Новая строка

| building_name       | area_sqm | rent_rate_year_sqm_base | rent_month_total_gross | sale_price_per_sqm | sale_vat_norm |
|---------------------|---------:|-------------------------:|-----------------------:|-------------------:|---------------|
| CRM Core XP Tower 9 | 360      | 21 000                   | 705 000,00             | 178 000            | С НДС         |

Дополнительно убедиться, что `opex_included = "Да"` и `rent_vat_norm = "С НДС"` для всех строк смоук-запроса.

Строка должна появиться внизу листа, все типовые поля заполнены согласно payload.

### 4.3. Лист request_log

Если в конфигурации активирован лог (`request_log`), убедиться, что:
- добавлена запись с `request_id = smoke-req-2025-10-31-01`;
- поля времени и счётчики (`updated = 2`, `inserted = 1`, `skipped = 0`) отражают результат.

## 5. Проверка идемпотентности

Повторно отправить тот же payload:

```powershell
curl -X POST http://localhost:8010/v1/import/listings `
  -H "Content-Type: application/json" `
  --data-binary "@app-crm/docs/smoke_payload.json"
```

Ожидаемый ответ:

```json
{
  "summary": {
    "updated": 0,
    "inserted": 0,
    "skipped": 0
  },
  "duplicates": []
}
```

В таблице не должно появиться новых строк, значения остаются неизменными.

## 6. Дополнительные проверки (по необходимости)

- **Duplicate detection**: изменить в payload название здания так, чтобы сервис вернул `duplicates`, и проверить статус обработки.
- **Ошибка схемы**: удалить обязательное поле (`building_name`) и убедиться, что сервис возвращает `400 Bad Request`.
- **Отказоустойчивость**: временно закрыть доступ сервисному аккаунту и убедиться, что сервис корректно логирует ошибку Google API (5xx).

## 7. Сброс после теста

- Для очистки таблицы повторно выполнить `seed_sheet.py --truncate --samples 5`.
- Деактивировать виртуальное окружение (`deactivate`).
- При необходимости удалить тестовую строку `CRM Core XP Tower 9`, если требуется «чистый» лист.

---

После прохождения смоук‑теста зафиксировать результаты в системе отслеживания (прошёл/не прошёл, дата, ответственный). Документ можно дополнять по мере расширения функциональности CRM сервиса.***
