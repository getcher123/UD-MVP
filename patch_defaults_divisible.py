from pathlib import Path
path = Path("app-ms/config/defaults.yml")
lines = path.read_text(encoding='utf-8').splitlines()
for idx, line in enumerate(lines):
    if 'под отделку: новое' in line:
        insert_idx = idx + 1
        break
else:
    raise SystemExit('target line not found')
lines.insert(insert_idx, '    divisible_from_sqm:')
lines.insert(insert_idx + 1, '      copy_from: area_sqm')
path.write_text("\n".join(lines) + "\n", encoding='utf-8')
