# UD-MVP Microservice (app-ms)

Purpose: accept a file → convert to PDF → run through AgentQL → normalize → return Excel/JSON.

This microservice exposes a simple HTTP API that receives an uploaded file, performs a
conversion and extraction pipeline, and returns a structured result. The intended flow is:

- Input: User uploads a document or image (PDF/DOCX/PPTX/XLSX/JPG/PNG, etc.).
- Convert: If not already PDF, convert the file to PDF.
- Extract: Run the PDF through AgentQL using a predefined query to extract tabular data.
- Normalize: Clean and normalize the extracted data for consistent downstream usage.
- Output: Return an Excel workbook (and/or JSON) containing the normalized results.

This repository currently ships with a runnable stub implementation:

- `POST /process_file` accepts `multipart/form-data` with fields `file=@...` and `chat_id`.
- It returns a small example Excel file to demonstrate the I/O contract.
- Replace the placeholder service functions under `services/` with real implementations.

## Endpoints

- `GET /health` — health check.
- `POST /process_file` — accepts a file and returns an Excel file.

## Local Run

```bash
cd app-ms
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

## Environment

Common variables you might add as you implement real logic:

- `AGENTQL_API_KEY` — API key for AgentQL
- `DEFAULT_QUERY_PATH` — path to the default AgentQL query file (defaults to `queries/default_query.txt`)

## Выходной формат

- Уровень: агрегирование до уровня зданий (buildings).
- Колонки (строгий порядок) — см. `config/defaults.yml → output.building_columns`:
  - building_id
  - building_name
  - object_id
  - object_name
  - use_type_set_norm
  - fitout_condition_mode
  - delivery_date_earliest
  - floors_covered_norm
  - area_sqm_total
  - listing_count
  - rent_rate_year_sqm_base_min
  - rent_rate_year_sqm_base_avg
  - rent_rate_year_sqm_base_max
  - rent_vat_norm_mode
  - opex_year_per_sqm_avg
  - rent_month_total_gross_avg
  - sale_price_per_sqm_min
  - sale_price_per_sqm_avg
  - sale_price_per_sqm_max
  - sale_vat_norm_mode
  - source_files
  - request_id
  - quality_flags

- Имена/ID:
  - building_name: формируется по шаблону из `aggregation.building.name.compose`, фактически `{object_name}{suffix}`, где `suffix = ", {token}"` если в `building_name` распознан токен (например, `стр. 1`, `корпус 2`, `литера Б`).
  - building_id: slug от `object_name` и токена здания: `{object_id}__{building_token_slug}`; если токена нет — просто `{object_id}`.

- Excel: один лист, первая строка заморожена (freeze `A2`), включён автофильтр, простые числовые форматы (без валютных символов).

## Этажи

- Поддерживаются одиночные значения, списки и диапазоны с разделителями:
  - множественные: `,`, `;`, `/`, ` и `, `&`
  - диапазон: `-` или `–`
- Удаляются служебные слова: `этаж`, `эт`, `э.`
- Спец-этажи маппятся: `подвал` (−1), `цоколь`, `мезонин`.
- Рендер: численные этажи сортируются, подряд идущие объединяются в диапазоны, спец-строки остаются как есть, итог соединяется `"; "`.

Примеры:
- "1 и 2" → "1–2"
- "1,3;5" → "1; 3; 5"
- "цоколь/1-2" → "1–2; цоколь"

## Проверка

- Быстрый smoke через API (возвращает Excel):
  - `curl -X POST -F "file=@service_AQL/input/28.04.2025 -Таблица по свободным площадям.pdf" -F "chat_id=123" http://localhost:9000/process_file -o export.xlsx`
- Офлайн агрегация JSON от AgentQL в Excel:
  - `python app-ms/scripts/json_to_buildings_excel.py "service_AQL/input/28.04.2025 -Таблица по свободным площадям.json" --request-id demo_28042025`
  - Результат: `data/results/demo_28042025/export.xlsx`

Описание колонок (фрагмент):
- building_id: `obekt__str-1` для "Объект, стр. 1"
- floors_covered_norm: "1–2" для листингов с этажами `1` и `1-2`
- area_sqm_total: сумма площадей по всем листингам здания
- listing_count: количество листингов в здании
