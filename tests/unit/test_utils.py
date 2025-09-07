import os

from utils import fs, dates


def test_fs_write_and_read(tmp_path):
    f = tmp_path / "demo.txt"
    fs.write_text(str(f), "hello")
    assert f.exists()
    content = f.read_text()
    assert content == "hello"


def test_safe_filename():
    unsafe = "Мой файл:версия?.pdf"
    safe = fs.safe_filename(unsafe)
    assert ":" not in safe and "?" not in safe


def test_quarter_to_date():
    assert dates.parse_quarter("1кв-2025") == "2025-03-31"
    assert dates.parse_quarter("3 квартал 2024") == "2024-09-30"


def test_to_iso_date():
    assert dates.to_iso_date("12.05.2024") == "2024-05-12"
    assert dates.to_iso_date("сейчас") == "сейчас"
