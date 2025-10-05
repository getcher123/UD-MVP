from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP_MS_ROOT = Path(__file__).resolve().parents[2]
if str(APP_MS_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MS_ROOT))

from services.docx_to_md import docx_to_md_text


def test_docx_to_md_text(tmp_path):
    tmp_dir = Path(tmp_path)
    source_md = tmp_dir / "source.md"
    source_md.write_text("Hello world\n\n- bullet", encoding="utf-8")

    docx_path = tmp_dir / "generated.docx"
    subprocess.run(["pandoc", str(source_md), "-o", str(docx_path)], check=True)

    md_text = docx_to_md_text(docx_path)

    assert "Hello world" in md_text
    assert "bullet" in md_text
