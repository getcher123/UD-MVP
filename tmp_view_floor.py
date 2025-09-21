from pathlib import Path
text = Path('app-ms/services/normalizers.py').read_text(encoding='utf-8').splitlines()
start = next(i for i,l in enumerate(text) if l.strip().startswith('def parse_floors'))
for line in text[start:start+160]:
    print(line)
