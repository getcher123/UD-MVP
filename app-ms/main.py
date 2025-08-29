from __future__ import annotations

from fastapi import FastAPI

from api.routes_health import router as health_router
from api.routes_process import router as process_router


app = FastAPI(title="UD-MVP Microservice")
app.include_router(health_router)
app.include_router(process_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        reload=True,
    )

