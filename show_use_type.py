from pathlib import Path
text = Path('app-ms/core/config_loader.py').read_text(encoding='utf-8').splitlines()
for i, line in enumerate(text):
    if 'use_type' in line:
        print(i, line)
        for extra in text[i+1:i+10]:
            print('   ', extra)
        break
