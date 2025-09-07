"""Client helpers for microservice interactions."""

from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path
from typing import Tuple

import httpx


async def process_file(file_path: Path, chat_id: str) -> tuple[bytes, str]:
    """Send file to microservice and return resulting XLSX bytes and filename.

    POST {MICROSERVICE_BASE_URL}/process_file with multipart/form-data (file, chat_id).
    Timeouts: connect 60s, read 120s.
    On success: return (xlsx_bytes, filename) where filename is taken from
    Content-Disposition header if present, otherwise "result.xlsx".
    """

    base_url = os.getenv("MICROSERVICE_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("MICROSERVICE_BASE_URL is not set")

    url = f"{base_url}/process_file"

    timeout = httpx.Timeout(120.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            data = {"chat_id": chat_id}
            resp = await client.post(url, data=data, files=files)
            resp.raise_for_status()

            content = resp.content
            cd = resp.headers.get("Content-Disposition") or resp.headers.get("content-disposition") or ""
            filename = _filename_from_content_disposition(cd) or "result.xlsx"
            return content, filename


_FILENAME_STAR_RE = re.compile(r"filename\*=(?:UTF-8'')?([^;]+)", flags=re.IGNORECASE)
_FILENAME_RE = re.compile(r"filename=\"?([^\";]+)\"?", flags=re.IGNORECASE)


def _filename_from_content_disposition(value: str) -> str | None:
    if not value:
        return None
    m = _FILENAME_STAR_RE.search(value)
    if m:
        raw = m.group(1)
        try:
            return urllib.parse.unquote(raw)
        except Exception:
            return raw
    m = _FILENAME_RE.search(value)
    if m:
        return m.group(1)
    return None
