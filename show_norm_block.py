from pathlib import Path
text = Path('app-ms/core/config_loader.py').read_text(encoding='utf-8').splitlines()
for i, line in enumerate(text):
    if 'normalization' in line:
        for l in text[i:i+50]:
            print(l)
        break
