from __future__ import annotations

from fastapi import APIRouter

from core.config import get_settings


router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@router.get("/version")
async def version() -> dict:
    return {"version": settings.MICROSERVICE_VERSION}

