
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.config import get_settings
from rubies_banking_api.models.support_staff import SupportStaff


class SupportStaffAuthenticationError(Exception):
    """Raised when support staff OTP authentication fails."""


@dataclass(frozen=True, slots=True)
class StaffOTPChallenge:
    staff_id: int
    staff_number: str
    otp: str
    expires_at: float
    attempts_remaining: int


class SupportStaffAuthenticationService:
    OTP_TTL_SECONDS = 300
    MAX_ATTEMPTS = 5
    TOKEN_TTL_SECONDS = 900
    TOKEN_AUDIENCE = "rubies-mfb-support-desk"

    def __init__(self) -> None:
        self._challenges: dict[str, StaffOTPChallenge] = {}
        self._lock = Lock()

    def request_otp(self, db: Session, phone_number: str) -> str:
        normalized_phone = phone_number.strip()

        staff = db.scalar(
            select(SupportStaff).where(
                SupportStaff.phone_number == normalized_phone,
                SupportStaff.is_active.is_(True),
            )
        )

        if staff is None:
            raise SupportStaffAuthenticationError(
                "Unable to start verification for the supplied phone number."
            )

        code = f"{secrets.randbelow(1_000_000):06d}"

        challenge = StaffOTPChallenge(
            staff_id=staff.id,
            staff_number=staff.staff_number,
            otp=code,
            expires_at=time.time() + self.OTP_TTL_SECONDS,
            attempts_remaining=self.MAX_ATTEMPTS,
        )

        with self._lock:
            self._challenges[normalized_phone] = challenge

        return code

    def verify_otp(
        self,
        db: Session,
        phone_number: str,
        otp: str,
    ) -> dict[str, str | int]:
        normalized_phone = phone_number.strip()

        with self._lock:
            challenge = self._challenges.get(normalized_phone)

            if challenge is None or time.time() >= challenge.expires_at:
                self._challenges.pop(normalized_phone, None)
                raise SupportStaffAuthenticationError(
                    "Verification code is invalid or has expired."
                )

            if challenge.attempts_remaining <= 0:
                self._challenges.pop(normalized_phone, None)
                raise SupportStaffAuthenticationError(
                    "Too many incorrect attempts. Request a new code."
                )

            if not secrets.compare_digest(challenge.otp, otp.strip()):
                remaining = challenge.attempts_remaining - 1

                if remaining == 0:
                    self._challenges.pop(normalized_phone, None)
                else:
                    self._challenges[normalized_phone] = StaffOTPChallenge(
                        staff_id=challenge.staff_id,
                        staff_number=challenge.staff_number,
                        otp=challenge.otp,
                        expires_at=challenge.expires_at,
                        attempts_remaining=remaining,
                    )

                raise SupportStaffAuthenticationError(
                    "Verification code is incorrect."
                )

            self._challenges.pop(normalized_phone, None)

        staff = db.scalar(
            select(SupportStaff).where(
                SupportStaff.id == challenge.staff_id,
                SupportStaff.phone_number == normalized_phone,
                SupportStaff.is_active.is_(True),
            )
        )

        if staff is None:
            raise SupportStaffAuthenticationError(
                "Staff account is inactive or unavailable."
            )

        settings = get_settings()
        settings.validate_jwt_configuration()

        now = int(time.time())
        session_id = str(uuid4())

        access_token = jwt.encode(
            {
                "sub": staff.staff_number,
                "sid": session_id,
                "verified": True,
                "token_use": "support_staff",
                "iat": now,
                "exp": now + self.TOKEN_TTL_SECONDS,
                "iss": settings.jwt_issuer,
                "aud": self.TOKEN_AUDIENCE,
            },
            settings.jwt_secret_key,
            algorithm="HS256",
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": self.TOKEN_TTL_SECONDS,
        }


support_staff_authentication_service = SupportStaffAuthenticationService()
