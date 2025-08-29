"""Utility helpers for working with files and directories."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path


# Project root dir (three levels up from this file: utils -> app -> repo root)
_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _ROOT_DIR / "data"
_UPLOADS_DIR = _DATA_DIR / "uploads"
_TMP_DIR = _DATA_DIR / "tmp"


def ensure_dirs() -> None:
    """Ensure application data directories exist.

    Creates `<project_root>/data/uploads` and `<project_root>/data/tmp`.
    Safe to call multiple times.
    """

    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    _TMP_DIR.mkdir(parents=True, exist_ok=True)


_SAFE_CHARS_RE = re.compile(r"[^a-z0-9._-]+")
_MULTI_DOTS_RE = re.compile(r"\.{2,}")
_MULTI_UNDERSCORE_RE = re.compile(r"_{2,}")


def _ascii(text: str) -> str:
    # Normalize unicode and drop non-ascii bytes
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def safe_filename(name: str) -> str:
    """Return a filesystem-safe file name (no directories).

    - Keeps only latin letters/digits, dot, dash, underscore
    - Converts spaces to underscores, lowers case
    - Collapses repeated dots/underscores, strips leading dots
    - Preserves last extension if present
    """

    # Remove any directory components
    just_name = Path(name).name

    # Split into stem and (last) suffix
    p = Path(just_name)
    stem = p.stem
    suffix = p.suffix.lower()

    # Transliterate to ascii and lower
    stem_ascii = _ascii(stem).lower()

    # Replace whitespace with underscores
    stem_ascii = re.sub(r"\s+", "_", stem_ascii)

    # Remove unsafe characters
    stem_ascii = _SAFE_CHARS_RE.sub("", stem_ascii)

    # Collapse multiples
    stem_ascii = _MULTI_UNDERSCORE_RE.sub("_", stem_ascii)
    suffix_sanitized = _ascii(suffix).lower()
    suffix_sanitized = _SAFE_CHARS_RE.sub("", suffix_sanitized)
    suffix_sanitized = _MULTI_DOTS_RE.sub(".", suffix_sanitized)

    # Avoid leading dot files (like .env) after sanitization
    safe_stem = stem_ascii.lstrip(".")

    # Fallback if empty
    if not safe_stem:
        safe_stem = "file"

    # Ensure suffix starts with a single dot if present
    if suffix_sanitized and not suffix_sanitized.startswith("."):
        suffix_sanitized = "." + suffix_sanitized

    # Avoid names like "file." (trailing dot)
    if suffix_sanitized == ".":
        suffix_sanitized = ""

    return f"{safe_stem}{suffix_sanitized}"


def max_size_bytes() -> int:
    """Return max upload size in bytes from env `MAX_FILE_MB`.

    Defaults to 20 MB if not set or invalid.
    """

    raw = os.getenv("MAX_FILE_MB", "20")
    try:
        mb = int(raw)
    except (TypeError, ValueError):
        mb = 20
    # Prevent negative or zero
    if mb <= 0:
        mb = 20
    return mb * 1024 * 1024


def save_bytes(path: Path, data: bytes) -> Path:
    """Save binary data to the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
