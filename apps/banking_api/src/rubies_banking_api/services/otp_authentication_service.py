"""Phone-number and OTP authentication for customer sessions."""

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
from rubies_banking_api.models.customer import Customer
from rubies_security.authentication import TokenSettings


class OTPAuthenticationError(Exception):
    """Raised when phone verification or OTP authentication fails."""


@dataclass(frozen=True, slots=True)
class OTPChallenge:
    """A short-lived OTP challenge for a registered customer."""

    customer_reference: str
    otp: str
    expires_at: float
    attempts_remaining: int


class OTPAuthenticationService:
    """Authenticate customers using registered phone numbers and one-time codes.

    OTP challenges are stored in memory for the demo. They are lost when the
    application restarts and are not suitable for a multi-worker production
    deployment.
    """

    OTP_TTL_SECONDS = 300
    MAX_ATTEMPTS = 5

    def __init__(self) -> None:
        self._challenges: dict[str, OTPChallenge] = {}
        self._lock = Lock()

    def request_otp(self, db: Session, phone_number: str) -> str:
        """Create an OTP challenge for an active customer.

        The returned code is intended for development/demo delivery only.
        Production delivery should use a trusted SMS provider.
        """
        normalized_phone = phone_number.strip()
        if not normalized_phone:
            raise OTPAuthenticationError("Phone number is required.")

        customer = db.scalar(
            select(Customer).where(
                Customer.phone_number == normalized_phone,
                Customer.is_active.is_(True),
            )
        )
        if customer is None:
            # Avoid revealing whether a phone number is registered.
            raise OTPAuthenticationError(
                "Unable to start verification for the supplied phone number."
            )

        code = f"{secrets.randbelow(1_000_000):06d}"
        challenge = OTPChallenge(
            customer_reference=customer.customer_reference,
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
        """Verify an OTP and issue a short-lived access token."""
        normalized_phone = phone_number.strip()

        with self._lock:
            challenge = self._challenges.get(normalized_phone)

            if challenge is None:
                raise OTPAuthenticationError(
                    "Verification code is invalid or has expired."
                )

            if time.time() >= challenge.expires_at:
                self._challenges.pop(normalized_phone, None)
                raise OTPAuthenticationError(
                    "Verification code is invalid or has expired."
                )

            if challenge.attempts_remaining <= 0:
                self._challenges.pop(normalized_phone, None)
                raise OTPAuthenticationError(
                    "Too many incorrect attempts. Request a new code."
                )

            if not secrets.compare_digest(challenge.otp, otp.strip()):
                remaining = challenge.attempts_remaining - 1
                if remaining <= 0:
                    self._challenges.pop(normalized_phone, None)
                else:
                    self._challenges[normalized_phone] = OTPChallenge(
                        customer_reference=challenge.customer_reference,
                        otp=challenge.otp,
                        expires_at=challenge.expires_at,
                        attempts_remaining=remaining,
                    )
                raise OTPAuthenticationError("Verification code is incorrect.")

            self._challenges.pop(normalized_phone, None)

        customer = db.scalar(
            select(Customer).where(
                Customer.customer_reference == challenge.customer_reference,
                Customer.phone_number == normalized_phone,
                Customer.is_active.is_(True),
            )
        )
        if customer is None:
            raise OTPAuthenticationError(
                "Unable to verify this customer. Request a new code."
            )

        settings = get_settings()
        settings.validate_jwt_configuration()

        token_settings = TokenSettings(
            secret_key=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )

        now = int(time.time())
        session_id = str(uuid4())
        access_token = jwt.encode(
            {
                "sub": customer.customer_reference,
                "sid": session_id,
                "verified": True,
                "iat": now,
                "exp": now + 900,
                "iss": token_settings.issuer,
                "aud": token_settings.audience,
            },
            token_settings.secret_key,
            algorithm=token_settings.algorithm,
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 900,
        }