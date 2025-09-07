import io
import os
import tempfile
import shutil
from pathlib import Path

import pytest
from services import pdf_convert


def test_pdf_passthrough(tmp_path):
    # создаём пустой PDF
    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%EOF")

    out = pdf_convert.to_pdf(str(pdf_path), str(tmp_path))
    assert out == str(pdf_path)
    assert Path(out).exists()


def test_jpg_to_pdf(tmp_path):
    # создаём "фейковый" JPG (достаточно заголовка)
    jpg_path = tmp_path / "demo.jpg"
    jpg_path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)

    out = pdf_convert.to_pdf(str(jpg_path), str(tmp_path))
    assert out.endswith(".pdf")
    assert Path(out).exists()
    # PDF всегда начинается с "%PDF"
    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_docx_to_pdf_mocks_subprocess(monkeypatch, tmp_path):
    # имитируем DOCX-файл
    docx_path = tmp_path / "demo.docx"
    docx_path.write_text("fake docx")

    # папка для PDF
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # подменяем subprocess.run внутри pdf_convert
    def fake_run(args, **kwargs):
        # создаём PDF в out_dir
        pdf_path = out_dir / "demo.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%EOF")
        return 0

    monkeypatch.setattr(pdf_convert, "subprocess", pdf_convert.subprocess)
    monkeypatch.setattr(pdf_convert.subprocess, "run", fake_run)

    out = pdf_convert.to_pdf(str(docx_path), str(out_dir))
    assert out.endswith(".pdf")
    assert Path(out).exists()
