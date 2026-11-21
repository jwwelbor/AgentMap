from unittest.mock import Mock

from agentmap.models.config_models import ConfigModel
from agentmap.services.config.config_managers.llm_config_manager import (
    LLMConfigManager,
)


def _manager(config):
    config_service = Mock()
    config_service.get_value_from_config.side_effect = (
        lambda data, _path, default: data.get("llm", {}).get("call_log", default)
    )
    return LLMConfigManager(config_service, config)


def test_call_log_is_disabled_by_default():
    manager = _manager({})

    assert manager.get_call_log_config() == {
        "enabled": False,
        "directory": "agentmap/llm_call_logs",
    }


def test_call_log_config_preserves_enabled_and_custom_directory():
    manager = _manager(
        {"llm": {"call_log": {"enabled": True, "directory": "/tmp/calls"}}}
    )

    assert manager.get_call_log_config() == {
        "enabled": True,
        "directory": "/tmp/calls",
    }


def test_call_log_config_survives_application_config_validation():
    config = ConfigModel.model_validate(
        {"llm": {"call_log": {"enabled": True, "directory": "/tmp/calls"}}}
    )

    assert config.llm.call_log.enabled is True
    assert config.llm.call_log.directory == "/tmp/calls"
