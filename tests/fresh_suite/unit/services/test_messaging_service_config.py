from unittest.mock import Mock

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.config.availability_cache_service import (
    AvailabilityCacheService,
)
from agentmap.services.logging_service import LoggingService
from agentmap.services.messaging.messaging_service import MessagingService


def test_load_messaging_config_reads_messaging_section() -> None:
    expected_config = {
        "default_provider": "local",
        "providers": {},
        "message_templates": {"notice": {"body": "hello"}},
    }
    config_service = Mock(spec=AppConfigService)
    config_service.get_section.return_value = expected_config
    logging_service = Mock(spec=LoggingService)
    logging_service.get_class_logger.return_value = Mock()
    availability_cache = Mock(spec=AvailabilityCacheService)

    service = MessagingService(config_service, logging_service, availability_cache)

    config_service.get_section.assert_called_once_with("messaging", {})
    assert service.messaging_config == expected_config
