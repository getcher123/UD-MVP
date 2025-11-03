from __future__ import annotations

from typing import Optional

import gspread
from fastapi import Depends, FastAPI, HTTPException, Request, status
from google.oauth2.service_account import Credentials

from .config import AppSettings, load_settings
from .schemas import ImportListingsRequest, ImportListingsResponse
from .service import CRMProcessor
from .sheet_gateway import GspreadSheetGateway

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def create_app(settings: Optional[AppSettings] = None, processor: Optional[CRMProcessor] = None) -> FastAPI:
    app = FastAPI(title="CRM Sync Service", version="1.0.0")

    @app.on_event("startup")
    async def startup() -> None:
        app.state.settings = settings or load_settings()
        app.state.processor = processor or _build_processor(app.state.settings)

    @app.post(
        "/v1/import/listings",
        response_model=ImportListingsResponse,
        status_code=status.HTTP_200_OK,
    )
    async def import_listings(payload: ImportListingsRequest, processor: CRMProcessor = Depends(_get_processor)) -> ImportListingsResponse:
        try:
            return processor.process(payload)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _get_processor(request: Request) -> CRMProcessor:
    processor = getattr(request.app.state, "processor", None)
    if processor is None:  # pragma: no cover - startup not run
        raise HTTPException(status_code=503, detail="Service not initialised")
    return processor


def _build_processor(settings: AppSettings) -> CRMProcessor:
    credentials = Credentials.from_service_account_file(str(settings.service_account_file), scopes=SCOPES)
    client = gspread.authorize(credentials)
    gateway = GspreadSheetGateway(client, settings.sheet)
    return CRMProcessor(settings.sheet, gateway)
