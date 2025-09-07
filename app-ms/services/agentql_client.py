from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx

from core.errors import ErrorCode, ServiceError


logger = logging.getLogger("service.agentql")


def run_agentql(pdf_path: str, query: str, mode: str = "standard", timeout_sec: float = 600.0) -> Dict[str, Any]:
    """
    Execute AgentQL against a PDF document via REST API.

    - Reads API key from ENV `AGENTQL_API_KEY`.
    - Retries up to 3 attempts with exponential backoff and jitter.
    - Logs timing_ms and pages if available.
    """
    api_key = os.getenv("AGENTQL_API_KEY")
    if not api_key:
        raise ServiceError(ErrorCode.AGENTQL_ERROR, 424, "AgentQL API key is not configured")

    p = Path(pdf_path)
    if not p.exists() or not p.is_file():
        raise ServiceError(ErrorCode.AGENTQL_ERROR, 424, f"PDF not found: {pdf_path}")

    # Allow overriding timeout via env for debugging (seconds)
    try:
        timeout_env = float(os.getenv("AGENTQL_TIMEOUT", "0") or 0)
        if timeout_env > 0:
            timeout_sec = timeout_env
    except ValueError:
        pass

    url = "https://api.agentql.com/v1/query-document"
    headers = {"X-API-Key": api_key}

    body = {"query": query, "params": {"mode": mode}}

    attempts = 3
    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        start = time.perf_counter()
        try:
            logger.info("agentql_call_start", extra={"file": str(p), "mode": mode, "timeout_sec": timeout_sec})
            with p.open("rb") as f:
                files = {
                    "file": (p.name, f, "application/pdf"),
                    "body": (None, json.dumps(body, ensure_ascii=False), "application/json"),
                }
                with httpx.Client(timeout=timeout_sec) as client:
                    resp = client.post(url, headers=headers, files=files)
                    resp.raise_for_status()
                    data = resp.json()

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            pages = None
            if isinstance(data, dict):
                pages = data.get("pages") or data.get("pdf_pages") or data.get("meta", {}).get("pages")
            logger.info("agentql_ok", extra={"timing_ms": elapsed_ms, "pages": pages, "mode": mode})
            return data
        except Exception as e:  # noqa: BLE001
            last_err = e
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "agentql_attempt_failed",
                extra={"attempt": i, "timing_ms": elapsed_ms, "error": str(e)},
            )
            if i < attempts:
                base = 0.4 * (2 ** (i - 1))
                time.sleep(base + random.uniform(0.2, 0.8))

    raise ServiceError(ErrorCode.AGENTQL_ERROR, 424, f"AgentQL call failed: {last_err}")


class AgentQLClient:
    """Light wrapper kept for future async usage."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("AGENTQL_API_KEY")

    async def run_query(self, pdf_bytes: bytes, query: str) -> List[Dict[str, Any]]:  # pragma: no cover - legacy stub
        # In a future version, support in-memory upload. For now, encourage path-based API.
        raise NotImplementedError("Use run_agentql(pdf_path, query) for now")

