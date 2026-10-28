"""Customer phone and OTP authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rubies_banking_api.config import get_settings

from rubies_banking_api.db.database import get_db
from rubies_banking_api.services.otp_authentication_service import (
    OTPAuthenticationError,
    OTPAuthenticationService,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

otp_authentication_service = OTPAuthenticationService()


class OTPRequest(BaseModel):
    """Request an OTP for a registered customer phone number."""

    phone_number: str = Field(min_length=7, max_length=20)


class OTPVerification(BaseModel):
    """Verify a previously requested OTP."""

    phone_number: str = Field(min_length=7, max_length=20)
    otp: str = Field(pattern=r"^\d{6}$")


class OTPRequestResponse(BaseModel):
    """Response confirming that an OTP challenge was created."""

    message: str
    development_otp: str | None = None


class TokenResponse(BaseModel):
    """Short-lived authenticated customer session."""

    access_token: str
    token_type: str
    expires_in: int


@router.post("/request-otp", response_model=OTPRequestResponse)
def request_otp(
    request: OTPRequest,
    db: Annotated[Session, Depends(get_db)],
) -> OTPRequestResponse:
    """Create an OTP challenge without exposing customer registration status."""
    settings = get_settings()
    development_otp = None

    try:
        otp = otp_authentication_service.request_otp(
            db,
            request.phone_number,
        )
        if settings.environment.lower() == "development":
            development_otp = otp
    except OTPAuthenticationError:
        # Avoid disclosing whether a phone number belongs to a customer.
        pass

    return OTPRequestResponse(
        message="If the phone number is registered, a verification code will be sent.",
        development_otp=development_otp,
    )

@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(
    request: OTPVerification,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Verify the OTP and issue a customer access token."""
    try:
        result = otp_authentication_service.verify_otp(
            db,
            request.phone_number,
            request.otp,
        )
    except OTPAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
        ) from exc

    return TokenResponse(**result)
