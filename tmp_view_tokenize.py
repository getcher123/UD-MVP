from pathlib import Path
text = Path('app-ms/services/normalizers.py').read_text(encoding='utf-8').splitlines()
start = next(i for i,l in enumerate(text) if l.strip().startswith('def _tokenize'))
for line in text[start:start+100]:
    print(line)
