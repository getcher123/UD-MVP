from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Union

from core.config import get_settings


_SAFE_CHARS_RE = re.compile(r"[^a-z0-9._-]+")


def ensure_dir(path: Union[str, Path]) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"\s+", "_", s)
    s = _SAFE_CHARS_RE.sub("", s)
    s = s.lstrip(".")
    return s or "file"


def safe_filename(name: str) -> str:
    p = Path(name)
    base = safe_name(p.stem or "file")
    ext = p.suffix.lower().lstrip(".")
    ext = re.sub(r"[^a-z0-9]+", "", ext)
    return f"{base}.{ext}" if ext else base


def write_bytes(path: Union[str, Path], data: bytes) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_bytes(data)
    return p


def write_text(path: Union[str, Path], data: str, encoding: str = "utf-8") -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(data, encoding=encoding)
    return p


def build_result_path(request_id: str, name: str) -> Path:
    settings = get_settings()
    base = ensure_dir(Path(settings.RESULTS_DIR) / request_id)
    return base / safe_filename(name)


__all__ = [
    "ensure_dir",
    "safe_name",
    "safe_filename",
    "write_bytes",
    "write_text",
    "build_result_path",
]
