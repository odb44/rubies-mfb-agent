"""Application entry point for the Rubies MFB Banking API."""

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request

from rubies_observability import (
    configure_logging,
    correlation_context,
    log_event,
)

from rubies_banking_api.api.cards import router as cards_router
from rubies_banking_api.api.disputes import router as disputes_router
from rubies_banking_api.api.transactions import router as transactions_router
from rubies_banking_api.api.support_handoffs import (
    router as support_handoffs_router,
)
from rubies_banking_api.api.loans import router as loans_router
from rubies_banking_api.config import get_settings


settings = get_settings()

logger = configure_logging(
    level="INFO",
    logger_name="rubies.banking_api",
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(cards_router)
app.include_router(disputes_router)
app.include_router(transactions_router)
app.include_router(loans_router)
app.include_router(support_handoffs_router)


CORRELATION_ID_HEADER = "X-Correlation-ID"
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _get_correlation_id(request: Request) -> str:
    """Accept a safe incoming correlation ID or generate a new one."""
    incoming_id = request.headers.get(CORRELATION_ID_HEADER, "").strip()

    if CORRELATION_ID_PATTERN.fullmatch(incoming_id):
        return incoming_id

    return uuid.uuid4().hex


@app.middleware("http")
async def observe_requests(
    request: Request,
    call_next,
):
    """Log request outcomes and return the correlation ID to the caller."""
    correlation_id = _get_correlation_id(request)
    start = time.perf_counter()

    with correlation_context(correlation_id):
        try:
            response = await call_next(request)

        except Exception as exc:
            log_event(
                logger,
                component="banking_api",
                event="http.request.failed",
                outcome="error",
                level=logging.ERROR,
                metadata={
                    "method": request.method,
                    "route": request.scope.get("route").path
                    if request.scope.get("route")
                    else "unmatched",
                },
                duration_ms=(time.perf_counter() - start) * 1000,
                exception_type=type(exc).__name__,
            )
            raise

        response.headers[CORRELATION_ID_HEADER] = correlation_id

        route = request.scope.get("route")
        route_template = getattr(route, "path", "unmatched")

        log_event(
            logger,
            component="banking_api",
            event="http.request.completed",
            outcome=(
                "success"
                if response.status_code < 400
                else "error"
            ),
            level=(
                logging.ERROR
                if response.status_code >= 500
                else logging.WARNING
                if response.status_code >= 400
                else logging.INFO
            ),
            metadata={
                "method": request.method,
                "route": route_template,
                "status_code": response.status_code,
            },
            duration_ms=(time.perf_counter() - start) * 1000,
        )

        return response


@app.get("/", tags=["General"])
def root() -> dict[str, str]:
    """Return basic API information."""
    return {
        "service": "Rubies MFB Banking API",
        "message": "Welcome to the Rubies MFB Banking API.",
        "health": "/health",
        "documentation": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Report the Banking API health status."""
    return {
        "status": "ok",
        "service": "banking-api",
        "environment": settings.environment,
    }
