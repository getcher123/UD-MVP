from pathlib import Path
path = Path('app-ms/config/defaults.yml')
lines = path.read_text(encoding='utf-8').splitlines()
start = None
for i, line in enumerate(lines):
    if line.lstrip().startswith('vat:'):
        start = i
        break
if start is None:
    raise SystemExit('vat block not found')
end = start + 1
while end < len(lines) and (lines[end].startswith('  ') or not lines[end].strip()):
    if not lines[end].strip() and end > start + 1:
        break
    end += 1
new_block = [
    '  vat:',
    '    canon: ["включен", "не включен", "не применяется"]',
    '    synonyms:',
    '      "включен": ["включая НДС", "с НДС", "НДС включен", "ставка с НДС"]',
    '      "не включен": ["без НДС", "без НДС.", "НДС не включен", "не включая НДС", "без НДС (УСН)"]',
    '      "не применяется": ["УСН", "освобождено", "не облагается НДС", "0%", "ставка 0%", "НДС 5%"]',
    '    default_rate: 0.20',
]
lines = lines[:start] + new_block + lines[end:]
path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
