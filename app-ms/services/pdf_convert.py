from __future__ import annotations

from typing import Tuple


async def ensure_pdf(input_bytes: bytes, filename: str | None = None) -> Tuple[bytes, str]:
    """Ensure the content is PDF; if not, convert it (stub).

    Returns (pdf_bytes, pdf_name).
    """
    # TODO: Real conversion. For now assume input is PDF or treat as-is.
    name = (filename or "document").rsplit(".", 1)[0] + ".pdf"
    return input_bytes, name

