from pathlib import Path
text = Path('app-ms/config/defaults.yml').read_text(encoding='utf-8').splitlines()
start = next(i for i, line in enumerate(text) if line.strip().startswith('vat:'))
for line in text[start:start+10]:
    print(line)
