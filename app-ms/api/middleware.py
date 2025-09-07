from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from starlette.types import ASGIApp, Receive, Scope, Send


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        # Use application logger; root configured to JSON in setup_logging
        self.logger = logging.getLogger("app.request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        request_id = headers.get("x-request-id", str(uuid.uuid4()))
        # expose request_id to downstream handlers via request.state
        if "state" in scope and scope["state"] is not None:
            try:
                # Starlette's Request.state is a State object supporting attribute assignment
                setattr(scope["state"], "request_id", request_id)  # type: ignore[arg-type]
            except Exception:
                # Fallback if state doesn't support attributes
                try:
                    scope["state"]["request_id"] = request_id  # type: ignore[index]
                except Exception:
                    pass
        else:
            scope["state"] = {"request_id": request_id}

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                # Append X-Request-ID header
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = raw_headers

                elapsed_ms = int((time.perf_counter() - start) * 1000)
                route = getattr(scope.get("route"), "path", None) or scope.get("path")
                method = scope.get("method")
                status_code = message.get("status")
                client = scope.get("client") or (None, None)
                client_ip = client[0] if isinstance(client, (list, tuple)) else None

                self.logger.info(
                    "request",
                    extra={
                        "request_id": request_id,
                        "route": route,
                        "timing_ms": elapsed_ms,
                        "method": method,
                        "status_code": status_code,
                        "path": scope.get("path"),
                        "client_ip": client_ip,
                    },
                )

            await send(message)

        await self.app(scope, receive, send_wrapper)


def install_request_logging(app: ASGIApp) -> None:
    """Convenience helper to install the middleware."""
    app.add_middleware(RequestLoggingMiddleware)  # type: ignore[arg-type]
