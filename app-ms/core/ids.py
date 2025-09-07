from __future__ import annotations

import uuid
from fastapi import Request


def new_job_id() -> str:
    return uuid.uuid4().hex


def make_request_id(request: Request) -> str:
    # Prefer ID from middleware/state, then header, else generate
    rid = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    return rid or uuid.uuid4().hex
