"""Runtime configuration boundary tests for AuthService."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from agentmap.services.auth_service import AuthService


def test_malformed_nested_auth_sections_do_not_crash_or_create_keys():
    logging_service = Mock()
    logging_service.get_class_logger.return_value = Mock()

    service = AuthService(
        {
            "api_keys": ["not-a-mapping"],
            "jwt": ["not-a-mapping"],
            "supabase": "not-a-mapping",
        },
        logging_service,
    )

    assert service._api_keys == {}
    assert service.jwt_secret is None
    assert service.jwt_algorithm == "HS256"
    assert service.supabase_url is None
    assert service.supabase_key is None


@pytest.mark.parametrize("enabled", [0, 1, [], None, "false"])
def test_non_boolean_enabled_value_keeps_authentication_enabled(enabled):
    logging_service = Mock()
    logging_service.get_class_logger.return_value = Mock()

    service = AuthService({"enabled": enabled}, logging_service)

    assert service.is_authentication_enabled() is True


def test_boolean_false_still_disables_authentication():
    logging_service = Mock()
    logging_service.get_class_logger.return_value = Mock()

    service = AuthService({"enabled": False}, logging_service)

    assert service.is_authentication_enabled() is False


@pytest.mark.parametrize("expires_at", ["not-a-date", 123, [], False])
def test_invalid_api_key_expiration_does_not_create_non_expiring_key(
    expires_at, monkeypatch
):
    for env_var in list(os.environ):
        if env_var.startswith("AGENTMAP_API_KEY_"):
            monkeypatch.delenv(env_var)

    logging_service = Mock()
    logging_service.get_class_logger.return_value = Mock()
    api_key = "invalid-expiration-key"
    service = AuthService(
        {"api_keys": {"invalid": {"key": api_key, "expires_at": expires_at}}},
        logging_service,
    )

    assert service._hash_api_key(api_key) not in service._api_keys
    assert service.validate_api_key(api_key).authenticated is False
    assert service.get_auth_stats()["total_api_keys"] == 0
    assert service.get_auth_stats()["active_api_keys"] == 0


@pytest.mark.parametrize(
    ("days_from_now", "authenticated", "active_keys"),
    [(-1, False, 0), (1, True, 1)],
)
def test_timezone_aware_api_key_expiration_is_validated_and_counted(
    days_from_now, authenticated, active_keys, monkeypatch
):
    for env_var in list(os.environ):
        if env_var.startswith("AGENTMAP_API_KEY_"):
            monkeypatch.delenv(env_var)

    logging_service = Mock()
    logging_service.get_class_logger.return_value = Mock()
    api_key = "timezone-expiration-key"
    expiration = (
        datetime.now(timezone.utc) + timedelta(days=days_from_now)
    ).isoformat()
    expiration = expiration.replace("+00:00", "Z")
    service = AuthService(
        {"api_keys": {"timezone": {"key": api_key, "expires_at": expiration}}},
        logging_service,
    )

    context = service.validate_api_key(api_key)

    assert context.authenticated is authenticated
    if authenticated:
        assert context.expires_at == datetime.fromisoformat(expiration)
    else:
        assert context.expires_at is None
    assert service.get_auth_stats()["active_api_keys"] == active_keys


def test_missing_api_key_expiration_remains_non_expiring(monkeypatch):
    for env_var in list(os.environ):
        if env_var.startswith("AGENTMAP_API_KEY_"):
            monkeypatch.delenv(env_var)

    logging_service = Mock()
    logging_service.get_class_logger.return_value = Mock()
    service = AuthService(
        {"api_keys": {"no-expiry": {"key": "no-expiration-key"}}},
        logging_service,
    )

    context = service.validate_api_key("no-expiration-key")

    assert context.authenticated is True
    assert context.expires_at is None
    assert service.get_auth_stats()["active_api_keys"] == 1
