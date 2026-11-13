
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rubies_banking_api.config import get_settings
from rubies_banking_api.db.database import get_db
from rubies_banking_api.services.support_staff_authentication_service import (
    SupportStaffAuthenticationError,
    support_staff_authentication_service,
)

router = APIRouter(
    prefix="/api/support-staff/auth",
    tags=["Support Staff Authentication"],
)


class OTPRequest(BaseModel):
    phone_number: str = Field(min_length=7, max_length=20)


class OTPVerification(BaseModel):
    phone_number: str = Field(min_length=7, max_length=20)
    otp: str = Field(pattern=r"^\d{6}$")


class OTPRequestResponse(BaseModel):
    message: str
    development_otp: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


@router.post("/request-otp", response_model=OTPRequestResponse)
def request_staff_otp(
    request: OTPRequest,
    db: Annotated[Session, Depends(get_db)],
) -> OTPRequestResponse:
    settings = get_settings()
    development_otp = None

    try:
        otp = support_staff_authentication_service.request_otp(
            db,
            request.phone_number,
        )

        if settings.environment.lower() == "development":
            development_otp = otp

    except SupportStaffAuthenticationError:
        pass

    return OTPRequestResponse(
        message="If the staff account is registered, a verification code will be sent.",
        development_otp=development_otp,
    )


@router.post("/verify-otp", response_model=TokenResponse)
def verify_staff_otp(
    request: OTPVerification,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    try:
        result = support_staff_authentication_service.verify_otp(
            db,
            request.phone_number,
            request.otp,
        )
    except SupportStaffAuthenticationError as exc:
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
