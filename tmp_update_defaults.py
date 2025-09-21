from pathlib import Path
path = Path('app-ms/config/defaults.yml')
text = path.read_text(encoding='utf-8')
if 'normalization:\n  vat:' not in text:
    raise SystemExit('vat section not found')

text = text.replace('  vat:\n    treat_not_applied: ["не применяется", "ставка 0%", "ндс 5%"]\n    default_rate: 0.20\n',
'  vat:\n    canon: ["включен", "не включен", "не применяется"]\n    synonyms:\n      "включен": ["включая ндс", "с ндс", "ндс включен"]\n      "не включен": ["без ндс", "без ндс.", "ндс не включен", "не включая ндс"]\n      "не применяется": ["усн", "освобождено", "не облагается ндс"]\n    treat_not_applied: ["не применяется", "ндс 5%", "ставка 0%"]\n    default_rate: 0.20\n')

path.write_text(text, encoding='utf-8')
