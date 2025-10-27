"""Client helpers for microservice interactions."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Ensure local `.env` variables are available even if config hasn't been imported yet.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

_DEFAULT_CONNECT_TIMEOUT = 60.0
_DEFAULT_READ_TIMEOUT = 300.0


def _parse_timeout(raw: str | None, fallback: float) -> float:
    if not raw:
        return fallback
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return fallback
    if value <= 0:
        return fallback
    return value


def _build_timeout() -> httpx.Timeout:
    connect = _parse_timeout(os.getenv("MICROSERVICE_CONNECT_TIMEOUT"), _DEFAULT_CONNECT_TIMEOUT)
    read = _parse_timeout(os.getenv("MICROSERVICE_READ_TIMEOUT"), _DEFAULT_READ_TIMEOUT)
    # Apply the same value to write timeout to avoid half-open uploads on slow links.
    return httpx.Timeout(timeout=None, connect=connect, read=read, write=read)


async def process_file(file_path: Path, chat_id: str) -> tuple[bytes, str, list[dict[str, Any]]]:
    """Send file to microservice and return resulting XLSX bytes, filename, and status messages."""

    base_url = os.getenv("MICROSERVICE_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("MICROSERVICE_BASE_URL is not set")

    url = f"{base_url}/process_file"

    timeout = _build_timeout()
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            data = {"chat_id": chat_id}
            resp = await client.post(url, data=data, files=files)
            resp.raise_for_status()

            content = resp.content
            cd = resp.headers.get("Content-Disposition") or resp.headers.get("content-disposition") or ""
            filename = _filename_from_content_disposition(cd) or "result.xlsx"

            status_messages: list[dict[str, Any]] = []
            header_val = resp.headers.get("X-UD-Status") or resp.headers.get("x-ud-status")
            if header_val:
                try:
                    decoded = base64.b64decode(header_val)
                    data_obj = json.loads(decoded.decode("utf-8"))
                    if isinstance(data_obj, list):
                        status_messages = [entry for entry in data_obj if isinstance(entry, dict)]
                    elif isinstance(data_obj, dict):
                        inner = data_obj.get("status_messages")
                        if isinstance(inner, list):
                            status_messages = [entry for entry in inner if isinstance(entry, dict)]
                        else:
                            status_messages = [data_obj]
                    else:
                        status_messages = [{"message": str(data_obj)}]
                except Exception:
                    status_messages = [{"message": str(header_val)}]

            return content, filename, status_messages


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


async def get_health() -> dict[str, Any]:
    """Fetch health status from the microservice."""

    base_url = os.getenv("MICROSERVICE_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("MICROSERVICE_BASE_URL is not set")

    url = f"{base_url}/healthz"
    timeout = _build_timeout()
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        try:
            return resp.json()
        except json.JSONDecodeError:
            return {"ok": False, "raw": resp.text}
