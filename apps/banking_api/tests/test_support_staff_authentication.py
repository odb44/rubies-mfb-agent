
"""Tests for support staff OTP authentication."""

from unittest.mock import MagicMock, patch

import jwt
import pytest
from rubies_banking_api.models.support_staff import SupportStaff
from rubies_banking_api.services.support_staff_authentication_service import (
    SupportStaffAuthenticationError,
    SupportStaffAuthenticationService,
)

TEST_SECRET_KEY = "test-secret-key-for-rubies-mfb-agent"
TEST_JWT_ISSUER = "rubies-mfb-test"
TEST_PHONE_NUMBER = "+2348012345678"


@pytest.fixture
def service():
    return SupportStaffAuthenticationService()


@pytest.fixture
def active_staff():
    return SupportStaff(
        id=1,
        staff_number="STF-000001",
        phone_number=TEST_PHONE_NUMBER,
        full_name="Test Support Staff",
        is_active=True,
    )


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.jwt_secret_key = TEST_SECRET_KEY
    settings.jwt_issuer = TEST_JWT_ISSUER
    settings.validate_jwt_configuration.return_value = None

    with patch(
        "rubies_banking_api.services.support_staff_authentication_service.get_settings",
        return_value=settings,
    ):
        yield settings


def test_request_otp_generates_six_digit_code(
    service,
    active_staff,
):
    """An active staff account receives a six-digit OTP challenge."""
    db = MagicMock()
    db.scalar.return_value = active_staff

    with patch(
        "rubies_banking_api.services.support_staff_authentication_service.secrets.randbelow",
        return_value=123456,
    ):
        otp = service.request_otp(db, TEST_PHONE_NUMBER)

    assert otp == "123456"
    assert len(otp) == 6

    challenge = service._challenges[TEST_PHONE_NUMBER]

    assert challenge.staff_id == active_staff.id
    assert challenge.staff_number == active_staff.staff_number
    assert challenge.otp == otp
    assert challenge.attempts_remaining == service.MAX_ATTEMPTS
    assert challenge.expires_at > 0


def test_request_otp_rejects_unknown_staff(service):
    """Unknown staff phone numbers cannot start authentication."""
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(SupportStaffAuthenticationError):
        service.request_otp(db, TEST_PHONE_NUMBER)

    assert TEST_PHONE_NUMBER not in service._challenges


def test_request_otp_rejects_inactive_staff(
    service,
    active_staff,
):
    """Inactive staff accounts cannot request an OTP."""
    active_staff.is_active = False

    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(SupportStaffAuthenticationError):
        service.request_otp(db, TEST_PHONE_NUMBER)

    assert TEST_PHONE_NUMBER not in service._challenges


def test_verify_otp_issues_staff_jwt(
    service,
    active_staff,
    mock_settings,
):
    """A valid OTP produces a staff-scoped JWT."""
    db = MagicMock()
    db.scalar.side_effect = [active_staff, active_staff]

    with patch(
        "rubies_banking_api.services.support_staff_authentication_service.secrets.randbelow",
        return_value=123456,
    ):
        service.request_otp(db, TEST_PHONE_NUMBER)

    result = service.verify_otp(
        db,
        TEST_PHONE_NUMBER,
        "123456",
    )

    assert result["token_type"] == "bearer"
    assert result["expires_in"] == service.TOKEN_TTL_SECONDS

    payload = jwt.decode(
        result["access_token"],
        TEST_SECRET_KEY,
        algorithms=["HS256"],
        issuer=TEST_JWT_ISSUER,
        audience=service.TOKEN_AUDIENCE,
    )

    assert payload["sub"] == active_staff.staff_number
    assert payload["verified"] is True
    assert payload["token_use"] == "support_staff"
    assert payload["aud"] == service.TOKEN_AUDIENCE
    assert payload["sid"]


def test_incorrect_otp_reduces_attempts(service, active_staff):
    """Incorrect OTP submissions reduce the remaining attempts."""
    db = MagicMock()
    db.scalar.return_value = active_staff

    with patch(
        "rubies_banking_api.services.support_staff_authentication_service.secrets.randbelow",
        return_value=123456,
    ):
        service.request_otp(db, TEST_PHONE_NUMBER)

    with pytest.raises(SupportStaffAuthenticationError):
        service.verify_otp(
            db,
            TEST_PHONE_NUMBER,
            "000000",
        )

    challenge = service._challenges[TEST_PHONE_NUMBER]

    assert challenge.attempts_remaining == service.MAX_ATTEMPTS - 1


def test_fifth_incorrect_attempt_invalidates_challenge(
    service,
    active_staff,
):
    """The fifth incorrect OTP attempt invalidates the challenge."""
    db = MagicMock()
    db.scalar.return_value = active_staff

    with patch(
        "rubies_banking_api.services.support_staff_authentication_service.secrets.randbelow",
        return_value=123456,
    ):
        service.request_otp(db, TEST_PHONE_NUMBER)

    for _ in range(service.MAX_ATTEMPTS):
        with pytest.raises(SupportStaffAuthenticationError):
            service.verify_otp(
                db,
                TEST_PHONE_NUMBER,
                "000000",
            )

    assert TEST_PHONE_NUMBER not in service._challenges


def test_expired_otp_is_rejected(service, active_staff):
    """Expired OTP challenges cannot be used."""
    db = MagicMock()
    db.scalar.return_value = active_staff

    with patch(
        "rubies_banking_api.services.support_staff_authentication_service.secrets.randbelow",
        return_value=123456,
    ):
        service.request_otp(db, TEST_PHONE_NUMBER)

    service._challenges[TEST_PHONE_NUMBER] = (
        service._challenges[TEST_PHONE_NUMBER].__class__(
            staff_id=active_staff.id,
            staff_number=active_staff.staff_number,
            otp="123456",
            expires_at=0,
            attempts_remaining=service.MAX_ATTEMPTS,
        )
    )

    with pytest.raises(SupportStaffAuthenticationError):
        service.verify_otp(
            db,
            TEST_PHONE_NUMBER,
            "123456",
        )

    assert TEST_PHONE_NUMBER not in service._challenges


def test_otp_can_only_be_used_once(
    service,
    active_staff,
    mock_settings,
):
    """A successfully verified OTP cannot be reused."""
    db = MagicMock()
    db.scalar.side_effect = [active_staff, active_staff]

    with patch(
        "rubies_banking_api.services.support_staff_authentication_service.secrets.randbelow",
        return_value=123456,
    ):
        service.request_otp(db, TEST_PHONE_NUMBER)

    result = service.verify_otp(
        db,
        TEST_PHONE_NUMBER,
        "123456",
    )

    assert result["access_token"]

    with pytest.raises(SupportStaffAuthenticationError):
        service.verify_otp(
            db,
            TEST_PHONE_NUMBER,
            "123456",
        )


def test_inactive_staff_cannot_receive_token(
    service,
    active_staff,
    mock_settings,
):
    """Staff deactivated after OTP issuance cannot receive a token."""
    db = MagicMock()
    db.scalar.side_effect = [active_staff, None]

    with patch(
        "rubies_banking_api.services.support_staff_authentication_service.secrets.randbelow",
        return_value=123456,
    ):
        service.request_otp(db, TEST_PHONE_NUMBER)

    with pytest.raises(SupportStaffAuthenticationError):
        service.verify_otp(
            db,
            TEST_PHONE_NUMBER,
            "123456",
        )
