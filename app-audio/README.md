# Audio Transcription Service

FastAPI сервис, который принимает аудио в base64 и возвращает текст, распознанный Whisper.

## Требования
- Python 3.10+
- Установленный ffmpeg в системе (для декодирования аудио)
- (Опционально) GPU и CUDA для ускорения torch

## Установка
1. Создать окружение: `python -m venv .venv_audio`
2. Активировать окружение и установить зависимости: `pip install -r app-audio/requirements.txt`
3. (Опционально) Задать переменную `TORCH_DEVICE` для выбора устройства (`cpu` или `cuda`).

## Запуск
- `uvicorn app-audio.main:app --host 0.0.0.0 --port 8001`

## Пример запроса
```bash
curl -X POST http://localhost:8001/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
        "audio_base64": "<base64-строка файла>",
        "filename": "sample.wav",
        "settings": {
          "language": "ru",
          "whisper_model": "large-v3"
        }
      }'
```

### Подготовка аудио в base64
```bash
python - <<'PY'
import base64, sys
with open("sample.wav", "rb") as f:
    print(base64.b64encode(f.read()).decode())
PY
```

Ответ содержит текст `text`, язык `language` и детали по сегментам `segments`.
