from pathlib import Path
path = Path('app-ms/core/config_loader.py')
text = path.read_text(encoding='utf-8')
old = '            "use_type": {"canon": ["офис", "ритейл", "псн", "склад"], "synonyms": {"офис": ["office", "open space"], "ритейл": ["retail", "street-retail"], "псн": ["psn"], "склад": ["storage", "warehouse"]}},\n'
if old not in text:
    raise SystemExit('expected literal block not found; please adjust replacement manually')
new = '            "use_type": {\n                "canon": ["офис", "ритейл", "псн", "склад"],\n                "synonyms": {\n                    "офис": ["office", "open space", "офис open space", "open-space"],\n                    "ритейл": ["retail", "street-retail", "street retail", "стрит-ритейл"],\n                    "псн": ["psn", "псн", "помещение свободного назначения", "свободного назначения", "нежилое помещение свободного назначения"],\n                    "склад": ["storage", "warehouse", "складское помещение"]\n                }\n            },\n'
path.write_text(text.replace(old, new), encoding='utf-8')
