from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class Object(BaseModel):
    """Generic extracted object placeholder.

    Shape is intentionally flexible to accommodate different schemas
    returned by AgentQL or normalization steps.
    """

    data: Dict[str, Any] = Field(default_factory=dict)


class ProcessFileResponse(BaseModel):
    request_id: str
    items_count: int
    objects: Optional[List[Object]] = None
    excel_url: Optional[str] = None
    pending_questions: Optional[List[Dict[str, Any]]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ClarifyRequest(BaseModel):
    """Placeholder for future clarification flow."""

    request_id: str
    answers: Dict[str, Any] = Field(default_factory=dict)


class ClarifyResponse(BaseModel):
    request_id: str
    pending_questions: Optional[List[Dict[str, Any]]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "HealthResponse",
    "Object",
    "ProcessFileResponse",
    "ClarifyRequest",
    "ClarifyResponse",
]
