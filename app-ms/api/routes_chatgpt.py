from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.ids import new_job_id
from services.chatgpt_structured import extract_structured_objects


router = APIRouter(tags=["chatgpt"])


class ChatGPTRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw transcript text to parse")
    request_id: Optional[str] = Field(default=None, description="Optional external request identifier")


class ChatGPTResponse(BaseModel):
    request_id: str
    result: Dict[str, Any]
    timing_ms: int


@router.post("/chatgpt/parse", response_model=ChatGPTResponse)
async def parse_with_chatgpt(payload: ChatGPTRequest) -> ChatGPTResponse:
    start = time.perf_counter()
    req_id = payload.request_id or new_job_id()
    result = extract_structured_objects(payload.text)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return ChatGPTResponse(request_id=req_id, result=result, timing_ms=elapsed_ms)
