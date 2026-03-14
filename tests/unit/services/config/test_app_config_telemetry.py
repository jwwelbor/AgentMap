"""Tests for AppConfigService telemetry config integration.

Verifies get_telemetry_config() delegates to TelemetryConfigManager
and TelemetryConfigManager is registered in _managers list.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.config.config_managers.telemetry_config_manager import (
    TelemetryConfigManager,
)
from agentmap.services.config.config_service import ConfigService


@pytest.fixture
def mock_config_service():
    """Create a mock ConfigService that returns empty config data."""
    mock_cs = create_autospec(ConfigService, instance=True)
    mock_cs.load_config.return_value = {}
    mock_cs.get_value_from_config.return_value = {}
    return mock_cs


@pytest.fixture
def app_config_service(mock_config_service):
    """Create AppConfigService instance with mocked dependencies."""
    return AppConfigService(mock_config_service)


class TestAppConfigTelemetryIntegration:
    """Verify telemetry config manager is properly integrated."""

    def test_telemetry_manager_exists(self, app_config_service) -> None:
        """AppConfigService has a _telemetry_manager attribute."""
        assert hasattr(app_config_service, "_telemetry_manager")
        assert isinstance(app_config_service._telemetry_manager, TelemetryConfigManager)

    def test_telemetry_manager_in_managers_list(self, app_config_service) -> None:
        """TelemetryConfigManager is registered in _managers list."""
        assert app_config_service._telemetry_manager in app_config_service._managers

    def test_get_telemetry_config_returns_dict(self, app_config_service) -> None:
        """get_telemetry_config() returns a well-formed dict."""
        config = app_config_service.get_telemetry_config()
        assert isinstance(config, dict)
        assert "enabled" in config
        assert "exporter" in config
        assert "endpoint" in config
        assert "protocol" in config
        assert "traces" in config
        assert "resource" in config

    def test_get_telemetry_config_defaults(self, app_config_service) -> None:
        """get_telemetry_config() returns safe defaults when no config present."""
        config = app_config_service.get_telemetry_config()
        assert config["enabled"] is False
        assert config["exporter"] == "none"
        assert config["traces"]["agent_inputs"] is False
        assert config["traces"]["agent_outputs"] is False
        assert config["traces"]["llm_prompts"] is False
        assert config["traces"]["llm_responses"] is False

    def test_logger_replacement_propagates(self, app_config_service) -> None:
        """Logger replacement propagates to _telemetry_manager."""
        new_logger = MagicMock()
        app_config_service.replace_logger(new_logger)
        assert app_config_service._telemetry_manager._logger is new_logger
