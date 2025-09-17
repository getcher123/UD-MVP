from __future__ import annotations

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.middleware import install_request_logging
from api.routes_health import router as health_router
from api.routes_process import router as process_router
from core.config import get_settings
from core.ids import make_request_id
from core.errors import ServiceError, ErrorCode
from core.logging import setup_logging


settings = get_settings()
app = FastAPI(title="MS Phase 1 Test")

setup_logging(settings.LOG_LEVEL)
install_request_logging(app)
app.include_router(health_router)
app.include_router(process_router)

# CORS for local debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/error")
def test_error(request_id: str = Depends(make_request_id)):
    raise ServiceError(code="TEST_ERROR", http_status=400, message="This is a test")


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    code = exc.code.value if hasattr(exc.code, "value") else str(exc.code)
    body = {"error": {"code": code, "message": exc.message, "request_id": request_id}}
    return JSONResponse(status_code=exc.http_status, content=body)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    body = {
        "error": {
            "code": ErrorCode.INTERNAL_ERROR.value,
            "message": "Internal server error",
            "request_id": request_id,
        }
    }
    return JSONResponse(status_code=500, content=body)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    body = {
        "error": {
            "code": ErrorCode.VALIDATION_ERROR.value,
            "message": "Validation error",
            "request_id": request_id,
        }
    }
    return JSONResponse(status_code=422, content=body)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    # Run from repository root with: python app-ms/main.py
    # Or: cd app-ms && uvicorn main:app --reload
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
