from pathlib import Path

entries = [
    ("object_name", "\u041e\u0431\u044a\u0435\u043a\u0442"),
    ("building_name", "\u0417\u0434\u0430\u043d\u0438\u0435"),
    ("use_type_norm", "\u0422\u0438\u043f \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u044f"),
    ("area_sqm", "\u041f\u043b\u043e\u0449\u0430\u0434\u044c, \u043a\u0432.\u043c."),
    ("divisible_from_sqm", "\u0414\u0435\u043b\u0438\u0442\u0441\u044f \u043e\u0442, \u043a\u0432.\u043c."),
    ("floors_norm", "\u042d\u0442\u0430\u0436"),
    ("market_type", "\u041d\u043e\u0432\u044b\u0439 / \u0412\u0442\u043e\u0440\u0438\u0447\u043a\u0430"),
    ("fitout_condition_norm", "\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435 \u043f\u043e\u043c\u0435\u0449\u0435\u043d\u0438\u044f"),
    ("delivery_date_norm", "\u0414\u0430\u0442\u0430 \u043f\u0435\u0440\u0435\u0434\u0430\u0447\u0438"),
    ("rent_rate_year_sqm_base", "\u0421\u0442\u0430\u0432\u043a\u0430 \u0430\u0440\u0435\u043d\u0434\u044b \u0432 \u0433\u043e\u0434 \u0437\u0430 \u043a\u0432.\u043c., \u0440\u0443\u0431."),
    ("rent_vat_norm", "\u041d\u0414\u0421 (\u0441\u0442\u0430\u0432\u043a\u0430 \u0430\u0440\u0435\u043d\u0434\u044b)"),
    ("opex_year_per_sqm", "OPEX \u0432 \u0433\u043e\u0434 \u0437\u0430 \u043a\u0432.\u043c., \u0440\u0443\u0431."),
    ("opex_included", "OPEX \u0432\u043a\u043b\u044e\u0447\u0435\u043d"),
    ("rent_month_total_gross", "\u0421\u0442\u0430\u0432\u043a\u0430 \u0430\u0440\u0435\u043d\u0434\u044b \u0432 \u043c\u0435\u0441\u044f\u0446, \u0440\u0443\u0431."),
    ("sale_price_per_sqm", "\u0426\u0435\u043d\u0430 \u043f\u0440\u043e\u0434\u0430\u0436\u0438 \u0437\u0430 \u043a\u0432.\u043c., \u0440\u0443\u0431."),
    ("sale_vat_norm", "\u041d\u0414\u0421 (\u0446\u0435\u043d\u0430 \u043f\u0440\u043e\u0434\u0430\u0436\u0438)"),
    ("source_file", "\u0418\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u0444\u0430\u0439\u043b"),
    ("request_id", "\u0418\u0434\u0435\u043d\u0442\u0438\u0444\u0438\u043a\u0430\u0442\u043e\u0440 \u0437\u0430\u043f\u0440\u043e\u0441\u0430"),
    ("quality_flags", "\u0424\u043b\u0430\u0433\u0438 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u0430"),
]

print('Samples:', [repr(header) for _, header in entries[:3]])
path = Path('app-ms/config/defaults.yml')
lines = path.read_text(encoding='utf-8').splitlines()
start = None
for idx, line in enumerate(lines):
    if line.strip() == 'listing_columns:':
        start = idx
        break
if start is None:
    raise SystemExit('listing_columns not found')
end = start + 1
while end < len(lines) and lines[end].startswith('    - '):
    end += 1
new_lines = ['  listing_columns:'] + [f"    - {key}|{header}" for key, header in entries]
print('New lines preview:', [repr(line) for line in new_lines[:3]])
lines = lines[:start] + new_lines + lines[end:]
path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
