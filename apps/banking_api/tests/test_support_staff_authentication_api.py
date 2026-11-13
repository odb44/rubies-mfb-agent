
"""Tests for support staff authentication API endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from rubies_banking_api.db.database import get_db
from rubies_banking_api.main import app
from rubies_banking_api.services.support_staff_authentication_service import (
    SupportStaffAuthenticationError,
)

BASE_URL = "/api/support-staff/auth"
PHONE_NUMBER = "+2348012345678"
DEVELOPMENT_OTP = "123456"
SUCCESS_MESSAGE = (
    "If the staff account is registered, "
    "a verification code will be sent."
)


def setup_database_override():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: MagicMock()


def teardown_database_override():
    app.dependency_overrides.clear()


def test_request_otp_returns_development_otp():
    """Development environment exposes the OTP for local testing."""
    setup_database_override()

    try:
        with (
            patch(
                "rubies_banking_api.api.support_staff_authentication.get_settings"
            ) as settings_mock,
            patch(
                "rubies_banking_api.api.support_staff_authentication.support_staff_authentication_service"
            ) as service_mock,
        ):
            settings_mock.return_value.environment = "development"
            service_mock.request_otp.return_value = DEVELOPMENT_OTP

            with TestClient(app) as client:
                response = client.post(
                    f"{BASE_URL}/request-otp",
                    json={"phone_number": PHONE_NUMBER},
                )

            service_mock.request_otp.assert_called_once()

        assert response.status_code == 200
        assert response.json() == {
            "message": SUCCESS_MESSAGE,
            "development_otp": DEVELOPMENT_OTP,
        }

    finally:
        teardown_database_override()


def test_request_otp_does_not_expose_otp_in_production():
    """Production responses must never expose the OTP."""
    setup_database_override()

    try:
        with (
            patch(
                "rubies_banking_api.api.support_staff_authentication.get_settings"
            ) as settings_mock,
            patch(
                "rubies_banking_api.api.support_staff_authentication.support_staff_authentication_service"
            ) as service_mock,
        ):
            settings_mock.return_value.environment = "production"
            service_mock.request_otp.return_value = DEVELOPMENT_OTP

            with TestClient(app) as client:
                response = client.post(
                    f"{BASE_URL}/request-otp",
                    json={"phone_number": PHONE_NUMBER},
                )

        assert response.status_code == 200
        assert response.json() == {
            "message": SUCCESS_MESSAGE,
            "development_otp": None,
        }

    finally:
        teardown_database_override()


def test_request_otp_does_not_reveal_unknown_staff():
    """Unknown staff phone numbers receive the same generic response."""
    setup_database_override()

    try:
        with (
            patch(
                "rubies_banking_api.api.support_staff_authentication.get_settings"
            ) as settings_mock,
            patch(
                "rubies_banking_api.api.support_staff_authentication.support_staff_authentication_service"
            ) as service_mock,
        ):
            settings_mock.return_value.environment = "development"
            service_mock.request_otp.side_effect = (
                SupportStaffAuthenticationError(
                    "Unable to start verification for the supplied phone number."
                )
            )

            with TestClient(app) as client:
                response = client.post(
                    f"{BASE_URL}/request-otp",
                    json={"phone_number": PHONE_NUMBER},
                )

        assert response.status_code == 200
        assert response.json() == {
            "message": SUCCESS_MESSAGE,
            "development_otp": None,
        }

    finally:
        teardown_database_override()


def test_request_otp_rejects_invalid_phone_number():
    """Phone numbers outside the accepted length are rejected."""
    setup_database_override()

    try:
        with TestClient(app) as client:
            response = client.post(
                f"{BASE_URL}/request-otp",
                json={"phone_number": "123"},
            )

        assert response.status_code == 422

    finally:
        teardown_database_override()


def test_verify_otp_returns_access_token():
    """Successful OTP verification returns the staff access token."""
    setup_database_override()

    expected_response = {
        "access_token": "test-staff-access-token",
        "token_type": "bearer",
        "expires_in": 900,
    }

    try:
        with patch(
            "rubies_banking_api.api.support_staff_authentication.support_staff_authentication_service"
        ) as service_mock:
            service_mock.verify_otp.return_value = expected_response

            with TestClient(app) as client:
                response = client.post(
                    f"{BASE_URL}/verify-otp",
                    json={
                        "phone_number": PHONE_NUMBER,
                        "otp": DEVELOPMENT_OTP,
                    },
                )

            service_mock.verify_otp.assert_called_once()

        assert response.status_code == 200
        assert response.json() == expected_response

    finally:
        teardown_database_override()


def test_verify_otp_rejects_incorrect_code():
    """Incorrect OTP verification returns HTTP 401."""
    setup_database_override()

    try:
        with patch(
            "rubies_banking_api.api.support_staff_authentication.support_staff_authentication_service"
        ) as service_mock:
            service_mock.verify_otp.side_effect = (
                SupportStaffAuthenticationError(
                    "Verification code is incorrect."
                )
            )

            with TestClient(app) as client:
                response = client.post(
                    f"{BASE_URL}/verify-otp",
                    json={
                        "phone_number": PHONE_NUMBER,
                        "otp": "000000",
                    },
                )

        assert response.status_code == 401
        assert response.json()["detail"] == (
            "Verification code is incorrect."
        )

    finally:
        teardown_database_override()


def test_verify_otp_rejects_expired_code():
    """Expired OTP verification returns HTTP 401."""
    setup_database_override()

    try:
        with patch(
            "rubies_banking_api.api.support_staff_authentication.support_staff_authentication_service"
        ) as service_mock:
            service_mock.verify_otp.side_effect = (
                SupportStaffAuthenticationError(
                    "Verification code is invalid or has expired."
                )
            )

            with TestClient(app) as client:
                response = client.post(
                    f"{BASE_URL}/verify-otp",
                    json={
                        "phone_number": PHONE_NUMBER,
                        "otp": DEVELOPMENT_OTP,
                    },
                )

        assert response.status_code == 401
        assert response.json()["detail"] == (
            "Verification code is invalid or has expired."
        )

    finally:
        teardown_database_override()


def test_verify_otp_rejects_invalid_otp_format():
    """OTP values must contain exactly six digits."""
    setup_database_override()

    try:
        with TestClient(app) as client:
            response = client.post(
                f"{BASE_URL}/verify-otp",
                json={
                    "phone_number": PHONE_NUMBER,
                    "otp": "12345",
                },
            )

        assert response.status_code == 422

    finally:
        teardown_database_override()


def test_verify_otp_returns_service_unavailable_on_configuration_error():
    """Configuration failures return HTTP 503."""
    setup_database_override()

    try:
        with patch(
            "rubies_banking_api.api.support_staff_authentication.support_staff_authentication_service"
        ) as service_mock:
            service_mock.verify_otp.side_effect = ValueError(
                "JWT configuration is invalid."
            )

            with TestClient(app) as client:
                response = client.post(
                    f"{BASE_URL}/verify-otp",
                    json={
                        "phone_number": PHONE_NUMBER,
                        "otp": DEVELOPMENT_OTP,
                    },
                )

        assert response.status_code == 503
        assert response.json()["detail"] == (
            "Authentication is temporarily unavailable."
        )

    finally:
        teardown_database_override()

