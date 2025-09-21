from pathlib import Path
path = Path('app-ms/config/defaults.yml')
text = path.read_text(encoding='utf-8')
old = '  vat:\n    treat_not_applied: ["���", "���������", "��� 5%"]\n    default_rate: 0.20\n'
new = '  vat:\n    canon: ["включен", "не включен", "не применяется"]\n    synonyms:\n      "включен": ["включая ндс", "с ндс", "ндс включен"]\n      "не включен": ["без ндс", "без ндс.", "ндс не включен", "не включая ндс"]\n      "не применяется": ["усн", "освобождено", "не облагается ндс"]\n    treat_not_applied: ["не применяется", "ставка 0%", "ндс 5%"]\n    default_rate: 0.20\n'
if old not in text:
    raise SystemExit('expected vat block not found')
path.write_text(text.replace(old, new), encoding='utf-8')
