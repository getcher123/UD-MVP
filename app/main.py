"""Webhook-based application entry point using FastAPI."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request, Response
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from .config import settings
from .handlers.common import router as common_router
from .handlers.documents import router as documents_router


# --- Bot & Dispatcher setup ---
bot = Bot(settings.bot_token)
dp = Dispatcher()

# Include routers with commands and other handlers
dp.include_router(common_router)
dp.include_router(documents_router)


# --- FastAPI app ---
app = FastAPI()


@app.on_event("startup")
async def on_startup() -> None:
    """Set webhook on startup if WEBHOOK_URL provided."""
    webhook_url = getattr(settings, "webhook_url", "")
    if webhook_url:
        await bot.set_webhook(webhook_url)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Remove webhook and close bot session on shutdown."""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    finally:
        await bot.session.close()


@app.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Receive Telegram updates and dispatch them to aiogram."""
    body = await request.body()
    try:
        update = Update.model_validate_json(body)
    except Exception:
        # Fallback in case content-type handling differs
        payload: Any = await request.json()
        update = Update.model_validate(payload)

    await dp.feed_update(bot, update)
    return Response(status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=bool(os.getenv("RELOAD", "0") == "1"),
    )
