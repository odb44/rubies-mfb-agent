
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.config import get_settings
from rubies_banking_api.db.database import get_db
from rubies_banking_api.models.support_staff import SupportStaff

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class SupportStaffIdentity:
    staff_number: str
    session_id: str


def get_support_staff_identity(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> SupportStaffIdentity:
    """Authenticate a support staff token and verify the staff account is active."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated support staff identity is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()

    try:
        settings.validate_jwt_configuration()

        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience="rubies-mfb-support-desk",
            options={
                "require": [
                    "sub",
                    "sid",
                    "verified",
                    "token_use",
                    "iat",
                    "exp",
                    "iss",
                    "aud",
                ]
            },
        )

        if (
            payload.get("verified") is not True
            or payload.get("token_use") != "support_staff"
        ):
            raise InvalidTokenError("Invalid support staff token.")

        staff_number = payload["sub"]
        session_id = payload["sid"]

    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The support staff access token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    staff = db.scalar(
        select(SupportStaff).where(
            SupportStaff.staff_number == staff_number,
            SupportStaff.is_active.is_(True),
        )
    )

    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The support staff account is inactive or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return SupportStaffIdentity(
        staff_number=staff.staff_number,
        session_id=session_id,
    )

