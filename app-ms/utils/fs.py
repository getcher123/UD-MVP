from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Optional


def ensure_dir(path: str | Path) -> Path:
    """
    Создаёт директорию (и родителей) при необходимости.
    Возвращает Path на директорию.

    >>> p = ensure_dir("tmp/test_fs_utils")
    >>> p.is_dir()
    True
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


_SAFE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def _sanitize_base(base: str) -> str:
    """Sanitize only the base name (without suffix).

    - Allowed: latin letters, digits, '_', '-', '.'
    - Any other run of characters is replaced by '_' (length 1-2) or '___' (length >=3)
    - Collapse underscore runs so that:
      - 3 or more → exactly '___'
      - 2 → '_'
      - 1 → '_'
    """
    out: list[str] = []
    run_len = 0
    for ch in base:
        if ch in _SAFE_CHARS:
            if run_len:
                out.append("___" if run_len >= 3 else "_")
                run_len = 0
            out.append(ch)
        else:
            run_len += 1
    if run_len:
        out.append("___" if run_len >= 3 else "_")

    s = "".join(out)
    # normalize underscores: 4+ -> 3, 2 -> 1
    s = re.sub(r"_{3,}", "___", s)
    s = re.sub(r"__", "_", s)
    return s or "_"


def safe_filename(name: str, max_len: int = 100) -> str:
    """
    Делает имя файла безопасным: только латинские буквы, цифры, _, -, .
    Русские и прочие символы заменяются на '_'. Сжимает повторяющиеся '_'.
    Ограничивает длину (без расширения).

    >>> safe_filename("Отчёт 12.07.2025 (финал).pdf")
    '___12.07.2025___.pdf'
    >>> safe_filename("my file?.txt")
    'my_file_.txt'
    """
    p = Path(name)
    base = p.stem
    suffix = p.suffix  # keep original casing

    base_sanitized = _sanitize_base(base)
    if len(base_sanitized) > max_len:
        base_sanitized = base_sanitized[:max_len]

    # sanitize suffix to keep only ASCII letters/digits and '.'; keep leading dot
    if suffix:
        root, ext = os.path.splitext(p.name)
        # ext includes leading dot
        safe_ext = "." + re.sub(r"[^A-Za-z0-9.]+", "", ext.lstrip(".")) if ext else ""
    else:
        safe_ext = ""

    return f"{base_sanitized}{safe_ext}" if safe_ext else base_sanitized


def safe_name(name: str, max_len: Optional[int] = None) -> str:
    """Безопасная версия для основы имени (без расширения).

    Это вспомогательная функция для совместимости со старым кодом.
    """
    s = _sanitize_base(name)
    if max_len is not None and len(s) > max_len:
        s = s[: max_len]
    return s


def file_ext(path: str | Path) -> str:
    """
    Расширение файла в нижнем регистре без точки. Если нет — пустая строка.

    >>> file_ext("a/b/C.DOCX")
    'docx'
    >>> file_ext("noext")
    ''
    """
    s = str(path)
    _, ext = os.path.splitext(s)
    return ext.lstrip(".").lower()


def file_size_mb(path: str | Path) -> float:
    """
    Размер файла в мегабайтах (MiB = bytes / 1024**2).

    >>> import tempfile, os
    >>> with tempfile.NamedTemporaryFile(delete=False) as f:
    ...     _ = f.write(b"x"*1048576)  # 1 MiB
    ...     tmp = f.name
    >>> 0.99 < file_size_mb(tmp) < 1.01
    True
    """
    size = os.path.getsize(path)
    return size / float(1024 ** 2)


def enforce_size_limit(path: str | Path, max_mb: int) -> None:
    """
    Бросает ValueError, если размер файла > max_mb.
    """
    mb = file_size_mb(path)
    if mb > float(max_mb):
        raise ValueError(f"File too large: {mb:.2f} MiB > {max_mb} MiB")


def is_allowed_type(path: str | Path, allow: list[str]) -> bool:
    """
    True, если расширение файла (без точки, lower) входит в allow.

    >>> is_allowed_type("x.PDF", ["pdf","docx"])
    True
    """
    ext = file_ext(path)
    allow_l = {a.lower() for a in allow}
    return ext in allow_l


def write_bytes(path: str | Path, data: bytes, makedirs: bool = True) -> Path:
    """
    Записывает байты, создаёт родительские директории при необходимости.
    Возвращает Path на файл.
    """
    p = Path(path)
    if makedirs:
        ensure_dir(p.parent)
    p.write_bytes(data)
    return p


def write_text(path: str | Path, text: str, encoding: str = "utf-8", makedirs: bool = True) -> Path:
    """Аналог write_bytes для текста."""
    p = Path(path)
    if makedirs:
        ensure_dir(p.parent)
    p.write_text(text, encoding=encoding)
    return p


def read_text(path: str | Path, encoding: str = "utf-8") -> str:
    """Читает текст из файла."""
    return Path(path).read_text(encoding=encoding)


def sha256_file(path: str | Path, chunk: int = 1 << 16) -> str:
    """
    Хэш файла hex-строкой (sha256).

    >>> import tempfile
    >>> t = tempfile.NamedTemporaryFile(delete=False)
    >>> _ = t.write(b"abc"); t.close()
    >>> sha256_file(t.name) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    True
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def unique_path(dir_: str | Path, stem: str, suffix: str) -> Path:
    """
    Возвращает путь dir_/ <stem>_<uuid4><suffix>, не существующий на диске.

    >>> p = unique_path("tmp", "report", ".xlsx")
    >>> p.parent.name == "tmp" and p.suffix == ".xlsx"
    True
    """
    d = Path(dir_)
    while True:
        candidate = d / f"{stem}_{uuid.uuid4().hex}{suffix}"
        if not candidate.exists():
            return candidate


def build_result_path(request_id: str, name: str, base_dir: Optional[str | Path] = None) -> Path:
    """
    Возвращает путь для сохранения результата:
    <base_dir or "data/results">/<request_id>/<safe_filename(name)>
    Гарантирует существование директории.

    >>> p = build_result_path("abcd1234", "export.xlsx", base_dir="tmp/results")
    >>> str(p).endswith("tmp/results/abcd1234/export.xlsx")
    True
    """
    base = Path(base_dir) if base_dir is not None else Path("data/results")
    target_dir = ensure_dir(base / request_id)
    return target_dir / safe_filename(name)


__all__ = [
    "ensure_dir",
    "safe_filename",
    "safe_name",
    "file_ext",
    "file_size_mb",
    "enforce_size_limit",
    "is_allowed_type",
    "write_bytes",
    "write_text",
    "read_text",
    "sha256_file",
    "unique_path",
    "build_result_path",
]
