# UD-MVP Microservice (app-ms)

Сервис принимает документы, прогоняет их через AgentQL и формирует нормализованный листинг в Excel/JSON. Файл запускается как HTTP API (FastAPI + Uvicorn) и хранит результаты в `data/results`.

## Возможности
- Документы (PDF/DOC/PPT/PPTX/TXT/JPG/PNG) приводятся к PDF и проходят через AgentQL;
- PDF дополнительно обрабатываются через vision-пайплайн: страницы рендерятся в PNG, распознаются GPT-vision с функцией `emit_page`, затем результат нормализуется и агрегируется;
- DOCX конвертируется в Markdown и разбирается ChatGPT по той же инструкции, что и для аудио;
- Excel (XLS/XLSX/XLSM) конвертируется в CSV и разбирается ChatGPT по той же инструкции, что и для аудио;
- Аудио (WAV/MP3/M4A/OGG/AAC) обрабатывается сервисом app-audio (`/v1/transcribe`), затем ChatGPT извлекает структуру из SRT;
- После извлечения выполняется нормализация, агрегирование и экспорт listings в Excel/JSON внутри `data/results`.


## Быстрый старт
```bash
cd app-ms
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --env-file ./.env
```
> Для аудио требуется развернутый сервис `app-audio` (см. отдельный README).

### Pandoc
- Для конвертации DOCX→Markdown требуется установленный [Pandoc](https://pandoc.org/installing.html).
- После установки убедитесь, что команда `pandoc --version` работает в терминале (путь к исполняемому файлу должен быть в переменной `PATH`).
- Если установили Pandoc впервые, перезапустите терминал перед запуском микросервиса.

Smoke-проверка:
```bash
curl -X POST -F "file=@examples/demo.pdf" http://localhost:8000/process_file -o listings.xlsx
```

## REST API
| Метод | Маршрут | Назначение |
|-------|---------|------------|
| GET   | `/healthz` | Проверка живости |
| GET   | `/version` | Текущая версия сервиса |
| POST  | `/process_file` | Обработка документа или аудио |

`POST /process_file`
- form-data поля: `file` (обязателен), `output` (`excel`, `json`, `both`, по умолчанию `excel`), `request_id`, `return_sheet_url`.
- ответ `excel`: файл. Для `json`/`both` возвращается объект:
```json
{
  "request_id": "...",
  "items_count": 42,
  "excel_url": "https://<BASE_URL>/results/<request_id>/listings.xlsx",
  "pending_questions": [],
  "meta": {
    "source_file": "input.pdf",
    "timing_ms": 4312,
    "listings_total": 42
  }
}
```

## Конфигурация
| Переменная | Описание |
|------------|----------|
| `AGENTQL_API_KEY` | токен AgentQL |
| `DEFAULT_QUERY_PATH` | путь к запросу AgentQL (по умолчанию `app-ms/queries/default_query.txt`) |
| `RESULTS_DIR` | каталог для результатов (`data/results`) |
| `BASE_URL` | базовый URL для генерации ссылок |
| `MAX_FILE_MB`, `ALLOW_TYPES` и др. | см. `core/config.py` |
| Настройки `app-audio` | `APP_AUDIO_URL`, `APP_AUDIO_TIMEOUT`, `APP_AUDIO_LANGUAGE`, `APP_AUDIO_MODEL` |
| DOCX -> ChatGPT | `DOCX_TYPES` - список расширений DOCX, которые обрабатываются через Markdown + ChatGPT |
| Excel -> ChatGPT | `EXCEL_TYPES` - список расширений для Excel, которые обрабатываются через CSV + ChatGPT |
| Vision для PDF | `PDF_VISION_PROMPT_PATH`, `PDF_VISION_SCHEMA_PATH`, `OPENAI_VISION_MODEL` |
| Поппер | `POPPLER_PATH` — путь к bin-каталогу Poppler для `pdf2image` |

### Дополнительно: Poppler
- Для rasterизации PDF до PNG используется `pdf2image`, которому нужен установленный [Poppler](https://github.com/oschwartz10612/poppler-windows/releases).
- На Windows укажите путь к `poppler\Library\bin` в `POPPLER_PATH` (через `.env` или переменные среды) перед запуском сервиса.

## Нормализация данных
Правила описаны в `app-ms/config/defaults.yml` (версия 3) и автоматически подхватываются при старте сервиса.

### Общие числовые правила
- `numbers.strip_currency = true` — удаляем символы валют перед разбором чисел.
- `numbers.decimal_comma_to_dot = true` — запятая в числах приводится к точке.

### Площади (area)
- `area.unit = "sqm"` — площади сохраняются в квадратных метрах.

### Этажи (floor)
- Игнорируем служебные маркеры: `этаж`, `эт`, `э.`.
- Спецзначения: `подвал → basement`, `цоколь → socle`, `мезонин → mezzanine`.
- Множественные значения включены (`multi.enabled = true`):
  - разделители: `,`, `;`, `/`, ` и `, `&`;
  - диапазоны: `-`, `–`;
  - финальный вывод собирается через `; `, для диапазонов используется `–`;
  - числовые этажи сортируются первыми, дубликаты убираются (`sort_numeric_first = true`, `uniq = true`).

### Тип использования (use_type)
| Каноническое значение | Синонимы |
|-----------------------|----------|
| `офис` | `office`, `open space`, `офис open space`, `open-space`, `кабинетная`, `офисный`, `студия`, `смешанная` |
| `ритейл` | `retail`, `street-retail`, `street retail`, `стрит-ритейл`, `торговая` |
| `псн` | `свободного назначения` |
| `склад` | `storage`, `warehouse`, `складское` |

### Состояние отделки (fitout_condition)
| Каноническое значение | Синонимы |
|-----------------------|----------|
| `с отделкой` | `готово к въезду`, `с мебелью`, `есть отделка`, `Выполнен ремонт`, `Полностью готово к`, `гипсовые перегородки` |
| `под отделку` | `white box`, `готово к отделке` |

### НДС (vat)
- Ставка по умолчанию: `default_rate = 0.20`.

| Каноническое значение | Синонимы |
|-----------------------|----------|
| `включен` | `включая НДС`, `с НДС`, `НДС включен`, `ставка с НДС`, `вкл. НДС`, `с учетом НДС` |
| `не включен` | `без НДС`, `без НДС.`, `без учета НДС`, `НДС не включен`, `не включая НДС` |
| `не применяется` | `УСН`, `освобождено`, `не облагается НДС`, `НДС 5%`, `без НДС (УСН)` |

Синонимы проверяются не только на полное совпадение, но и по частичным вхождениям, указанным в `fallbacks.vat_partial_synonyms`. Это позволяет распознавать фразы вроде «начисляется НДС» даже в составе более длинного предложения.

### OPEX
| Каноническое значение | Синонимы |
|-----------------------|----------|
| `включен` | `включая эксплуатационные услуги`, `opex включен`, `включены`, `коммунальные платежи` |
| `не включен` | `opex не включен`, `отдельно` |

- По умолчанию OPEX не включён (`opex.default_included = false`), значение `default_year_per_sqm` не задано.

### Даты (dates)
| Месяц | Код |
|-------|-----|
| `январь` | `01` |
| `февраль` | `02` |
| `март` | `03` |
| `апрель` | `04` |
| `май` | `05` |
| `июнь` | `06` |
| `июль` | `07` |
| `август` | `08` |
| `сентябрь` | `09` |
| `октябрь` | `10` |
| `ноябрь` | `11` |
| `декабрь` | `12` |

- Кварталы приводятся к последним дням периода: `Q1 → 03-31`, `Q2 → 06-30`, `Q3 → 09-30`, `Q4 → 12-31`.
- Маркеры актуальности: `сейчас`, `свободно`, `готово к въезду`, `сегодня`.

### Сопоставление (matching)
- Допуск по площади: `abs_sqm = 2`, `rel_pct = 2.0`.
- `join_key_listing` строится из `object_id`, `building_token`, `use_type_norm`, `floors_norm`, `area_1dp`.

### Производные значения (derivation)
- `rent_rate_year_sqm_base.priority = ["direct", "reconstruct_from_month"]`.
- При реконструкции из месячной ставки учитываются НДС и OPEX (`respect_vat = true`, `respect_opex = true`), используется `vat_fallback = 0.20`, результат округляется до двух знаков (`round_decimals = 2`).
- `gross_month_total.round_decimals = 2`.

### Контроль качества (quality)
- `rent_rate_year_sqm_base` помечается как выброс при значениях `< 1000` или `> 200000`.

### Фоллбеки (fallbacks)
- `rent_vat_norm`: сначала используется НДС из листинга (`use_listing_vat = true`), затем из объекта (`use_object_rent_vat = true`).
- `use_type_norm` по умолчанию = `офис`.
- `market_type`: `с отделкой → ранее арендованное`, `под отделку → новое`.
- `divisible_from_sqm` копирует значение из `area_sqm`.
- `opex_included.set_when_year_per_sqm_present = "не включен"` — если задана годовая ставка OPEX, но флаг пуст, он проставляется автоматически.
- `vat_partial_synonyms` помогает ловить фразы вроде «начисляется НДС», даже если поле `rent_vat` пустое.

### Вопросы для уточнения (questions)
- `fitout_condition`: «Уточните отделку: «с отделкой» или «под отделку»?»
- `delivery_date`: «Уточните дату передачи (ISO YYYY-MM-DD) или «сейчас».»
- `rent_rate`: «Подтвердите НДС (включен/не применяется) и OPEX (включён/отдельно, руб/м²/год).»
- `use_type`: «Уточните тип использования: офис, торговое, псн или склад.»

### Именование (naming)
- `building.name_compose = "{object_name}{suffix}"`, где `suffix = ", {building_token}"` при наличии токена. Если исходное `building_name` уже содержит `object_name` (или наоборот объект уже содержит токен), суффикс не добавляется.
- `building.id_compose = "{object_id}__{building_token_slug}"`; если токена нет, используется только `object_id`.

### Идентификаторы (identifier)
- `listing_id.compose_parts = ["object_id", "building_token_slug", "use_type_norm_slug", "floors_norm_slug", "area_1dp"]`.
- Добавляется хэш по `source_file_basename` (`hash_part = ["source_file_basename"]`, `hash_len = 8`), элементы соединяются через `__`.



### Настройки пайплайна (pipeline)
- Блок `pipeline` в `defaults.yml` делит обработку по типам входа (`doc`, `excel`, `ppt`, `pdf`, `image`, `audio`, `txt`) и позволяет отключать/настраивать этапы без правки кода.
- `common.pdf_conversion` и `common.agentql` задают значения по умолчанию: движок (`engine: libreoffice`), режим AgentQL (`mode: standard`) и тайм-аут (`timeout_sec`). Значения можно переопределить на уровне конкретного формата.
- `excel.uno_borders` управляет запуском скрипта `scripts/uno_set_borders.py`; толщина линий берётся из `width_pt` (по умолчанию 1.0 pt).
- `audio.transcription` и `audio.chatgpt_structured` отвечают за распознавание речи и структурирование расшифровки. Если транскрибация отключена, сервис вернёт 503.
- Для `xls`/`txt` и изображений блок `pdf_conversion` решает, выполнять ли конвертацию и каким движком (`img2pdf` для ветки `image`).
- Для `doc`/`docx` документ преобразуется в Markdown (`doc_to_md`/`docx_to_md`), после чего запускается `chatgpt_structured`.
- Для `ppt`/`pptx` используется этап `ppt_to_md`, который вытягивает текст (включая простые таблицы) в Markdown перед вызовом `chatgpt_structured`.
- `postprocess.excel_export.enabled` позволяет отключить генерацию Excel; при запросе `output=excel` при выключенном блоке возвращается ошибка 503.
- Для `pdf` доступны новые стадии `pdf_to_images` (рендер страниц в PNG через Poppler) и `vision_per_page` (распознавание GPT-vision по промпту и схеме), после чего результат передаётся в `pdf.chatgpt_structured`.

## Формирование Excel
Каждое помещение выгружается отдельной строкой. Порядок и заголовки колонок соответствуют `output.listing_columns`:

| Поле | Заголовок |
|------|-----------|
| `object_name` | `Объект` |
| `building_name` | `Здание` |
| `use_type_norm` | `Тип использования` |
| `area_sqm` | `Площадь, кв.м.` |
| `divisible_from_sqm` | `Делится от, кв.м.` |
| `floors_norm` | `Этаж` |
| `market_type` | `Новый / Вторичка` |
| `fitout_condition_norm` | `Состояние помещения` |
| `delivery_date_norm` | `Дата передачи` |
| `rent_rate_year_sqm_base` | `Ставка аренды в год за кв.м., руб.` |
| `rent_vat_norm` | `НДС (ставка аренды)` |
| `opex_year_per_sqm` | `OPEX в год за кв.м., руб.` |
| `opex_included` | `OPEX включен` |
| `rent_month_total_gross` | `Ставка аренды в месяц, руб.` |
| `sale_price_per_sqm` | `Цена продажи за кв.м., руб.` |
| `sale_vat_norm` | `НДС (цена продажи)` |
| `source_file` | `Исходный файл` |
| `request_id` | `Идентификатор запроса` |
| `quality_flags` | `Флаги качества` |

Идентификаторы (`listing_id`, `building_id`) формируются по правилам `identifier` из `defaults.yml`.

## Конвертация Excel в PDF
- Excel-файлы перед выгрузкой проходят через LibreOffice; для `.xlsx` дополнительно запускается UNO-скрипт `app-ms/scripts/uno_set_borders.py`, который задаёт границы по всей используемой области толщиной 1 pt.
- По умолчанию сервис пытается найти `soffice` и `python` LibreOffice автоматически; путь можно переопределить переменной `SOFFICE_PATH`.

## Docker
```powershell
docker build -t ud-ms:latest -f app-ms/Dockerfile .
New-Item -ItemType Directory -Force .\data | Out-Null
docker run --rm -p 8000:8000 -v "${PWD}\data:/data" --env-file .env ud-ms:latest
```

## Полезное
- Тесты см. в `app-ms/tests` (юнит + интеграционные сценарии).
- Для пересоздания Excel вне сервиса используйте `python app-ms/scripts/json_to_listings_excel.py <json> --request-id <id>`.
