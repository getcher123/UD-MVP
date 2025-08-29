from __future__ import annotations

import re
import unicodedata


_SAFE_CHARS_RE = re.compile(r"[^a-z0-9._-]+")


def safe_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"\s+", "_", s)
    s = _SAFE_CHARS_RE.sub("", s)
    s = s.lstrip(".")
    return s or "file"

