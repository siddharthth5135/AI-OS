import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger("ai_os.middleware")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log requests and responses.
    Assigns a unique X-Request-ID to each request.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Assign Request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Bind request context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        # Log request start
        logger.info("http_request_start")

        start_time = time.perf_counter()
        
        try:
            response: Response = await call_next(request)
            
            duration_s = time.perf_counter() - start_time
            duration_ms = duration_s * 1000
            status_code = response.status_code

            # Log request completion with appropriate level
            log_data = {
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
            }

            if 200 <= status_code < 400:
                logger.info("http_request_complete", **log_data)
            elif 400 <= status_code < 500:
                logger.warning("http_request_complete", **log_data)
            else:
                logger.error("http_request_complete", **log_data)

            # Record request metrics
            try:
                from app.core.observability.metrics import record_request
                record_request(request.method, request.url.path, status_code, duration_s)
            except Exception:
                pass

            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            duration_s = time.perf_counter() - start_time
            duration_ms = duration_s * 1000
            logger.error(
                "http_request_failed",
                exception=str(e),
                duration_ms=round(duration_ms, 2),
                status_code=500,
            )
            # Record request metrics
            try:
                from app.core.observability.metrics import record_request
                record_request(request.method, request.url.path, 500, duration_s)
            except Exception:
                pass
            raise
        finally:
            structlog.contextvars.clear_contextvars()
