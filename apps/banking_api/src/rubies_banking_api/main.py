from fastapi import FastAPI

from rubies_banking_api.api.cards import router as cards_router
from rubies_banking_api.api.disputes import router as disputes_router
from rubies_banking_api.api.transactions import router as transactions_router
from rubies_banking_api.config import get_settings
from rubies_banking_api.api.loans import router as loans_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(cards_router)
app.include_router(disputes_router)
app.include_router(transactions_router)
app.include_router(loans_router)

@app.get("/", tags=["General"])
def root() -> dict[str, str]:
    return {
        "service": "Rubies MFB Banking API",
        "message": "Welcome to the Rubies MFB Banking API.",
        "health": "/health",
        "documentation": "/docs",
    }

@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "banking-api",
        "environment": settings.environment,
    }