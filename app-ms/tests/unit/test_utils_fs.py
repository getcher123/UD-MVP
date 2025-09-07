from __future__ import annotations

import sys
import re
from pathlib import Path
import tempfile
import pytest

# Надёжно находим корень проекта, чтобы импортировать 'utils'
root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from utils import fs  # type: ignore


def test_safe_filename_semantic():
    out = fs.safe_filename("Отчёт 12.07.2025 (финал).pdf")
    # 1) правильное расширение
    assert out.lower().endswith(".pdf")
    # 2) ключевая часть имени сохранена
    assert "12.07.2025" in out
    # 3) нет не-ASCII символов/скобок/пробелов
    assert all(ch.isascii() for ch in out)
    # 4) только разрешённые символы
    assert re.fullmatch(r"[A-Za-z0-9_.\-]+\.pdf", out)


def test_file_ext_and_allowed_type():
    assert fs.file_ext("a/b/C.DOCX") == "docx"
    assert fs.file_ext("noext") == ""
    assert fs.is_allowed_type("x.PDF", ["pdf", "docx"]) is True
    assert fs.is_allowed_type("x.bin", ["pdf", "docx"]) is False


def test_file_size_and_enforce_limit(tmp_path: Path):
    p = tmp_path / "bin.bin"
    p.write_bytes(b"x" * (1024 * 1024))  # ~1 MiB
    sz = fs.file_size_mb(p)
    assert 0.99 < sz < 1.01
    with pytest.raises(ValueError):
        fs.enforce_size_limit(p, max_mb=0)


def test_write_read_and_sha256(tmp_path: Path):
    txt = tmp_path / "a.txt"
    fs.write_text(txt, "hello")
    assert fs.read_text(txt) == "hello"

    binf = tmp_path / "b.bin"
    fs.write_bytes(binf, b"abc")
    # sha256("abc")
    assert (
        fs.sha256_file(binf)
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_unique_path_and_build_result_path(tmp_path: Path):
    up = fs.unique_path(tmp_path, "report", ".xlsx")
    assert up.parent == tmp_path and up.suffix == ".xlsx"
    # Гарантируем, что путь не существует до записи
    assert not up.exists()

    out = fs.build_result_path("abcd1234", "export.xlsx", base_dir=tmp_path)
    # .../tmp/<something>/abcd1234/export.xlsx
    assert out.name == "export.xlsx" and out.parent.name == "abcd1234"
    tail = Path(*out.parts[-3:])
    assert list(tail.parts) == [tmp_path.name, "abcd1234", "export.xlsx"]
