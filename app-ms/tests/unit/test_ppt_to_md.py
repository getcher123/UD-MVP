from __future__ import annotations

from pathlib import Path
import sys

APP_MS_ROOT = Path(__file__).resolve().parents[2]
if str(APP_MS_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MS_ROOT))

from services.ppt_to_md import ppt_to_md_text


def test_ppt_to_md_text_produces_markdown():
    ppt_path = APP_MS_ROOT / "data" / "ppt-test.pptx"
    md_text = ppt_to_md_text(ppt_path)

    assert md_text.startswith("# ")
    assert "Slide 1" in md_text
    assert "- " in md_text
