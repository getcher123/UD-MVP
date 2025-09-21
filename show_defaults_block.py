from pathlib import Path
lines = Path('app-ms/config/defaults.yml').read_text(encoding='utf-8').splitlines()
for i, line in enumerate(lines):
    if 'opex_included' in line:
        for l in lines[i-2:i+6]:
            print(l)
        break
