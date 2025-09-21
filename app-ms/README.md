# UD-MVP Microservice (app-ms)

Сервис принимает документы, прогоняет их через AgentQL и формирует нормализованный листинг в Excel/JSON. Файл запускается как HTTP API (FastAPI + Uvicorn) и хранит результаты в `data/results`.

## Возможности
- авто-конвертация входных документов (PDF/DOCX/PPTX/XLSX/JPG/PNG) в PDF;
- обработка аудио через внешний `app-audio` (WAV/MP3/M4A/OGG/AAC);
- запуск AgentQL-запроса (`app-ms/queries/default_query.txt`) и нормализация данных по правилам `config/defaults.yml`;
- экспорт в Excel со строгим набором колонок и расчётом вспомогательных полей.

## Быстрый старт
```bash
cd app-ms
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --env-file ./.env
```
> Для аудио требуется развернутый сервис `app-audio` (см. отдельный README).

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

## Нормализация данных
Правила описаны в `app-ms/config/defaults.yml` и автоматически подхватываются при старте.

### Тип использования (use_type)
| Каноническое значение | Синонимы |
|-----------------------|----------|
| `офис` | `office`, `open space`, `офис open space`, `офис open-space`, `офис open space` |
| `ритейл` | `retail`, `street-retail`, `стрит-ритейл`, `street retail` |
| `псн` | `psn`, `псн`, `vip`, `помещение свободного назначения` |
| `склад` | `storage`, `warehouse`, `складское помещение` |

### Состояние отделки (fitout_condition)
| Каноническое значение | Синонимы |
|-----------------------|----------|
| `с отделкой` | `готово к въезду`, `с мебелью`, `есть отделка` |
| `под отделку` | `white box`, `готово к отделке` |

### НДС (rent_vat / sale_vat)
| Каноническое значение | Синонимы |
|-----------------------|----------|
| `включен` | `включая ндс`, `с ндс`, `ндс включен`, `ставка с ндс` |
| `не включен` | `без ндс`, `без ндс.`, `без НДС`, `без НДС.`, `ндс не включен`, `не включая ндс`, `без ндс (усн)` |
| `не применяется` | `усн`, `освобождено`, `освобождение от ндс`, `не облагается ндс`, `0%`, `ставка 0%`, `ндс 5%` |

### Дополнительные правила
- Площади (`area_sqm`, `divisible_from_sqm`) округляются до целого.
- Денежные поля (`rent_rate_year_sqm_base`, `rent_month_total_gross`, `sale_price_per_sqm`, `opex_year_per_sqm`) округляются до целого.
- Формат даты поставки (`delivery_date_norm`) — ISO `YYYY-MM-DD`; для «Февраль 2025» берётся первое число месяца, для кварталов — последняя дата квартала.

## Формирование Excel
Столбцы и порядок: `object_name`, `building_name`, `use_type_norm`, `area_sqm`, `divisible_from_sqm`, `floors_norm`, `market_type`, `fitout_condition_norm`, `delivery_date_norm`, `rent_rate_year_sqm_base`, `rent_vat_norm`, `opex_year_per_sqm`, `opex_included`, `rent_month_total_gross`, `sale_price_per_sqm`, `sale_vat_norm`, `source_file`, `request_id`, `quality_flags`.

Идентификаторы (`listing_id`, `building_id`) формируются по правилам `identifier` из `defaults.yml`.

## Docker
```powershell
docker build -t ud-ms:latest -f app-ms/Dockerfile .
New-Item -ItemType Directory -Force .\data | Out-Null
docker run --rm -p 8000:8000 -v "${PWD}\data:/data" --env-file .env ud-ms:latest
```

## Полезное
- Тесты см. в `app-ms/tests` (юнит + интеграционные сценарии).
- Для пересоздания Excel вне сервиса используйте `python app-ms/scripts/json_to_listings_excel.py <json> --request-id <id>`.

