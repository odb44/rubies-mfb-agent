"""Application entry point for the Rubies MFB Banking API."""

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from rubies_observability import (
    configure_logging,
    correlation_context,
    log_event,
    record_metric,
)

from rubies_banking_api.api.authentication import router as authentication_router
from rubies_banking_api.api.cards import router as cards_router
from rubies_banking_api.api.chats import router as chats_router
from rubies_banking_api.api.confirmations import (
    router as confirmations_router,
)
from rubies_banking_api.api.disputes import router as disputes_router
from rubies_banking_api.api.loan_eligibility import (
    router as loan_eligibility_router,
)
from rubies_banking_api.api.loans import router as loans_router
from rubies_banking_api.api.support_desk import router as support_desk_router
from rubies_banking_api.api.support_handoffs import (
    router as support_handoffs_router,
)
from rubies_banking_api.api.support_staff_authentication import (
    router as support_staff_authentication_router,
)
from rubies_banking_api.api.transactions import router as transactions_router
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://fulfilling-emotion-production.up.railway.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(confirmations_router)
app.include_router(cards_router)
app.include_router(chats_router)
app.include_router(disputes_router)
app.include_router(transactions_router)
app.include_router(loans_router)
app.include_router(support_handoffs_router)
app.include_router(authentication_router)
app.include_router(support_staff_authentication_router)
app.include_router(support_desk_router)
app.include_router(loan_eligibility_router)


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
    """Log and measure request outcomes and return the correlation ID."""
    correlation_id = _get_correlation_id(request)
    start = time.perf_counter()

    with correlation_context(correlation_id):
        try:
            response = await call_next(request)

        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000

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
                duration_ms=duration_ms,
                exception_type=type(exc).__name__,
            )

            record_metric(
                component="banking_api",
                operation="http_request",
                outcome="error",
                duration_ms=duration_ms,
            )

            raise

        response.headers[CORRELATION_ID_HEADER] = correlation_id

        route = request.scope.get("route")
        route_template = getattr(route, "path", "unmatched")
        duration_ms = (time.perf_counter() - start) * 1000

        if response.status_code < 400:
            outcome = "success"
            log_level = logging.INFO
        elif response.status_code < 500:
            outcome = "failure"
            log_level = logging.WARNING
        else:
            outcome = "error"
            log_level = logging.ERROR

        log_event(
            logger,
            component="banking_api",
            event="http.request.completed",
            outcome=outcome,
            level=log_level,
            metadata={
                "method": request.method,
                "route": route_template,
                "status_code": response.status_code,
            },
            duration_ms=duration_ms,
        )

        record_metric(
            component="banking_api",
            operation="http_request",
            outcome=outcome,
            duration_ms=duration_ms,
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
