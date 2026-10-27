"""Tests for banking API configuration and JWT settings."""

import pytest
from rubies_banking_api.config import Settings


def test_default_settings_have_expected_application_metadata() -> None:
    settings = Settings()

    assert settings.app_name == "Rubies MFB Banking API"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"


def test_jwt_configuration_accepts_valid_values() -> None:
    settings = Settings(
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters-long",
        jwt_issuer="rubies-mfb",
        jwt_audience="rubies-mfb-api",
    )

    settings.validate_jwt_configuration()


@pytest.mark.parametrize(
    "secret_key",
    [
        "",
        "too-short",
    ],
)
def test_jwt_configuration_rejects_short_secret(secret_key: str) -> None:
    settings = Settings(
        jwt_secret_key=secret_key,
        jwt_issuer="rubies-mfb",
        jwt_audience="rubies-mfb-api",
    )

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        settings.validate_jwt_configuration()


@pytest.mark.parametrize(
    ("issuer", "audience"),
    [
        ("", "rubies-mfb-api"),
        ("   ", "rubies-mfb-api"),
        ("rubies-mfb", ""),
        ("rubies-mfb", "   "),
    ],
)
def test_jwt_configuration_rejects_blank_issuer_or_audience(
    issuer: str,
    audience: str,
) -> None:
    settings = Settings(
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters-long",
        jwt_issuer=issuer,
        jwt_audience=audience,
    )

    with pytest.raises(ValueError):
        settings.validate_jwt_configuration()