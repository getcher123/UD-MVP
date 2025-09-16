# Whisper Diarization Service

FastAPI-сервис, который оборачивает `diarize.py` из репозитория [MahmoudAshraf97/whisper-diarization](https://github.com/MahmoudAshraf97/whisper-diarization). Повторяет шаги из Colab-скрипта: патчим RNN в torch, запускаем `diarize.py`, читаем `.srt` и возвращаем результат через HTTP.

## Подготовка окружения
```bash
# 1. ffmpeg (пример для Windows)
choco install ffmpeg

# 2. Создать виртуальное окружение и установить зависимости сервиса
echo "python -m venv .venv_audio"
python -m venv .venv_audio
.\.venv_audio\Scripts\activate
pip install -r app-audio/requirements.txt

# 3. Установить CUDA Toolkit 12.1 + cuDNN 9.x (GPU)
#    Скачайте CUDA 12.1 с https://developer.nvidia.com/cuda-downloads и поставьте Toolkit.
#    Из архива cuDNN for CUDA 12.x скопируйте содержимое папок bin/lib/include в каталоги CUDA (v12.1).
#    После установки проверьте `nvcc --version` и `python -c "import torch; print(torch.cuda.is_available())"`.

# 4. Установить MSVC Build Tools (только Windows)
#    Для сборки ctc-forced-aligner и texterrors нужны компиляторы.
#    Скачайте https://aka.ms/vs/17/release/vs_BuildTools.exe и установите
#    рабочую нагрузку "Desktop development with C++" (MSVC + Windows SDK).
#    После установки откройте новое окно PowerShell и активируйте окружение.

# 5. Клонировать репозиторий diarization и поставить его зависимости
cd app-audio
git clone --depth 1 https://github.com/MahmoudAshraf97/whisper-diarization.git
cd whisper-diarization
pip install -r requirements.txt -c constraints.txt
cd ../..
```

При необходимости установите переменную `TORCH_DEVICE` (`cpu` или `cuda`).

## Запуск сервиса
```bash
uvicorn app-audio.main:app --host 0.0.0.0 --port 8001 --env-file .env
```

## Пример запроса
```bash
curl -X POST http://localhost:8001/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
        "audio_base64": "<base64-строка файла>",
        "filename": "dialogue.wav",
        "settings": {
          "language": "ru",
          "whisper_model": "medium"
        }
      }'
```
**Smoke (curl):**

```bash
curl -Method Post http://localhost:8001/v1/transcribe -ContentType "application/json" -Body ('{{"audio_base64":"{0}","filename":"audio_2025-09-16_17-13-23.ogg","settings":{{"language":"ru","whisper_model":"medium"}}}}' -f ([Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\UD-MVP\app-audio\data\audio_2025-09-16_17-13-23.ogg")))) -o app-audio\data\response.json
```

### Формат ответа
```json
{
  "text": "Полный текст диалога",
  "model": "medium",
  "language": "ru",
  "duration_ms": 12345,
  "speakers": [
    {
      "speaker": "speaker1",
      "start": 0.0,
      "end": 5.2,
      "text": "Реплика первого собеседника"
    },
    {
      "speaker": "speaker2",
      "start": 5.2,
      "end": 10.7,
      "text": "Ответ второго собеседника"
    }
  ]
}
```

### Примечания
- `.srt`, `.txt`, `.json`, созданные `diarize.py`, удаляются после обработки.
- Если каталог `app-audio/whisper-diarization` отсутствует, сервис вернёт подсказку.
- Чтобы поменять модель, передайте нужное значение в `settings.whisper_model` (например, `large-v3`).
