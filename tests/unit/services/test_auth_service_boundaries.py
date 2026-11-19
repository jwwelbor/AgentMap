"""Runtime configuration boundary tests for AuthService."""

from unittest.mock import Mock

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
