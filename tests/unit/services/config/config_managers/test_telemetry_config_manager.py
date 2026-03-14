"""Unit tests for TelemetryConfigManager.

Covers TC-430 through TC-472 from the E02-F04 test plan:
- Default values (TC-430 to TC-433, TC-470, TC-471)
- Config merging (TC-472)
- Validation (TC-460, TC-461, TC-462)
- Typed accessors (TC-430 to TC-445)
"""

from unittest.mock import MagicMock

import pytest

from agentmap.exceptions.base_exceptions import ConfigurationException
from agentmap.services.config.config_managers.telemetry_config_manager import (
    TelemetryConfigManager,
)


@pytest.fixture
def make_manager():
    """Factory fixture to create TelemetryConfigManager with given config data."""

    def _make(config_data: dict):
        mock_config_service = MagicMock()
        # Wire up get_value_from_config to navigate dot-notation paths

        def get_value_from_config(data, path, default=None):
            keys = path.split(".")
            current = data
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current

        mock_config_service.get_value_from_config = get_value_from_config
        mock_logger = MagicMock()
        return TelemetryConfigManager(mock_config_service, config_data, mock_logger)

    return _make


# ============================================================================
# TC-470, TC-471: Missing telemetry section returns safe defaults
# ============================================================================


class TestDefaultValues:
    """Test that missing or empty telemetry section returns correct defaults."""

    def test_missing_section_returns_defaults(self, make_manager):
        """TC-470: Missing telemetry section returns safe defaults."""
        manager = make_manager({})
        config = manager.get_telemetry_config()

        assert config["enabled"] is False
        assert config["exporter"] == "none"
        assert config["endpoint"] == "http://localhost:4317"
        assert config["protocol"] == "grpc"

    def test_missing_section_no_error_no_warning(self, make_manager):
        """TC-471: No error or warning on missing section."""
        manager = make_manager({})
        # Should not raise
        config = manager.get_telemetry_config()
        assert config["enabled"] is False

    def test_empty_section_returns_defaults(self, make_manager):
        """Empty telemetry section returns all defaults."""
        manager = make_manager({"telemetry": {}})
        config = manager.get_telemetry_config()

        assert config["enabled"] is False
        assert config["exporter"] == "none"

    def test_agent_inputs_defaults_false(self, make_manager):
        """TC-430: agent_inputs flag defaults to false."""
        manager = make_manager({})
        flags = manager.get_content_capture_flags()
        assert flags["agent_inputs"] is False

    def test_agent_outputs_defaults_false(self, make_manager):
        """TC-431: agent_outputs flag defaults to false."""
        manager = make_manager({})
        flags = manager.get_content_capture_flags()
        assert flags["agent_outputs"] is False

    def test_llm_prompts_defaults_false(self, make_manager):
        """TC-432: llm_prompts flag defaults to false."""
        manager = make_manager({})
        flags = manager.get_content_capture_flags()
        assert flags["llm_prompts"] is False

    def test_llm_responses_defaults_false(self, make_manager):
        """TC-433: llm_responses flag defaults to false."""
        manager = make_manager({})
        flags = manager.get_content_capture_flags()
        assert flags["llm_responses"] is False

    def test_resource_attributes_default_service_name(self, make_manager):
        """service.name defaults to 'agentmap'."""
        manager = make_manager({})
        attrs = manager.get_resource_attributes()
        assert attrs["service.name"] == "agentmap"


# ============================================================================
# TC-472: Config merging
# ============================================================================


class TestConfigMerging:
    """Test that partial config merges correctly with defaults."""

    def test_partial_config_merges_with_defaults(self, make_manager):
        """TC-472: Partial config merges with defaults."""
        manager = make_manager(
            {
                "telemetry": {
                    "enabled": True,
                    "exporter": "otlp",
                }
            }
        )
        config = manager.get_telemetry_config()

        assert config["enabled"] is True
        assert config["exporter"] == "otlp"
        # Defaults filled in
        assert config["endpoint"] == "http://localhost:4317"
        assert config["protocol"] == "grpc"

    def test_nested_traces_merge(self, make_manager):
        """Nested traces dict merges correctly -- user overrides one flag, others default."""
        manager = make_manager(
            {
                "telemetry": {
                    "traces": {
                        "agent_inputs": True,
                    }
                }
            }
        )
        config = manager.get_telemetry_config()

        assert config["traces"]["agent_inputs"] is True
        assert config["traces"]["agent_outputs"] is False
        assert config["traces"]["llm_prompts"] is False
        assert config["traces"]["llm_responses"] is False

    def test_resource_merge_with_service_name_default(self, make_manager):
        """Resource dict merges, keeping service.name default when not overridden."""
        manager = make_manager(
            {
                "telemetry": {
                    "resource": {
                        "deployment.environment": "staging",
                    }
                }
            }
        )
        attrs = manager.get_resource_attributes()
        assert attrs["service.name"] == "agentmap"
        assert attrs["deployment.environment"] == "staging"

    def test_resource_service_name_override(self, make_manager):
        """User can override service.name."""
        manager = make_manager(
            {
                "telemetry": {
                    "resource": {
                        "service.name": "my-app",
                    }
                }
            }
        )
        attrs = manager.get_resource_attributes()
        assert attrs["service.name"] == "my-app"

    def test_unknown_keys_ignored(self, make_manager):
        """Extra unknown keys in telemetry section are preserved but don't cause errors."""
        manager = make_manager(
            {
                "telemetry": {
                    "sampling_rate": 0.5,
                }
            }
        )
        config = manager.get_telemetry_config()
        assert config["sampling_rate"] == 0.5
        assert config["enabled"] is False


# ============================================================================
# TC-460, TC-461, TC-462: Validation
# ============================================================================


class TestValidation:
    """Test that invalid config values raise ConfigurationException."""

    def test_invalid_exporter_raises(self, make_manager):
        """TC-460: Invalid exporter raises ConfigurationException."""
        manager = make_manager(
            {
                "telemetry": {
                    "exporter": "kafka",
                }
            }
        )
        with pytest.raises(ConfigurationException, match="Invalid telemetry exporter"):
            manager.get_telemetry_config()

    def test_invalid_exporter_lists_valid_options(self, make_manager):
        """TC-460: Error message lists valid exporter options."""
        manager = make_manager(
            {
                "telemetry": {
                    "exporter": "datadog",
                }
            }
        )
        with pytest.raises(ConfigurationException, match="otlp.*console.*none"):
            manager.get_telemetry_config()

    def test_invalid_protocol_raises(self, make_manager):
        """TC-461: Invalid protocol raises ConfigurationException."""
        manager = make_manager(
            {
                "telemetry": {
                    "protocol": "websocket",
                }
            }
        )
        with pytest.raises(ConfigurationException, match="Invalid telemetry protocol"):
            manager.get_telemetry_config()

    def test_invalid_protocol_lists_valid_options(self, make_manager):
        """TC-461: Error message lists valid protocol options."""
        manager = make_manager(
            {
                "telemetry": {
                    "protocol": "tcp",
                }
            }
        )
        with pytest.raises(ConfigurationException, match="grpc.*http/protobuf"):
            manager.get_telemetry_config()

    def test_empty_string_exporter_raises(self, make_manager):
        """Empty string exporter raises ConfigurationException."""
        manager = make_manager(
            {
                "telemetry": {
                    "exporter": "",
                }
            }
        )
        with pytest.raises(ConfigurationException, match="Invalid telemetry exporter"):
            manager.get_telemetry_config()

    def test_numeric_exporter_raises(self, make_manager):
        """Numeric exporter raises ConfigurationException."""
        manager = make_manager(
            {
                "telemetry": {
                    "exporter": 123,
                }
            }
        )
        with pytest.raises(ConfigurationException, match="Invalid telemetry exporter"):
            manager.get_telemetry_config()

    def test_valid_exporters_pass(self, make_manager):
        """Valid exporter values do not raise."""
        for exporter in ["otlp", "console", "none"]:
            manager = make_manager(
                {
                    "telemetry": {
                        "exporter": exporter,
                    }
                }
            )
            config = manager.get_telemetry_config()
            assert config["exporter"] == exporter

    def test_valid_protocols_pass(self, make_manager):
        """Valid protocol values do not raise."""
        for protocol in ["grpc", "http/protobuf"]:
            manager = make_manager(
                {
                    "telemetry": {
                        "protocol": protocol,
                    }
                }
            )
            config = manager.get_telemetry_config()
            assert config["protocol"] == protocol

    def test_non_boolean_enabled_raises(self, make_manager):
        """Non-boolean enabled raises ConfigurationException."""
        manager = make_manager(
            {
                "telemetry": {
                    "enabled": "true",
                }
            }
        )
        with pytest.raises(ConfigurationException, match="enabled"):
            manager.get_telemetry_config()

    def test_non_boolean_traces_flag_raises(self, make_manager):
        """Non-boolean traces flag raises ConfigurationException."""
        manager = make_manager(
            {
                "telemetry": {
                    "traces": {
                        "agent_inputs": "yes",
                    }
                }
            }
        )
        with pytest.raises(ConfigurationException, match="traces"):
            manager.get_telemetry_config()

    def test_non_string_resource_value_raises(self, make_manager):
        """Non-string resource attribute values raise ConfigurationException."""
        manager = make_manager(
            {
                "telemetry": {
                    "resource": {
                        "count": 42,
                    }
                }
            }
        )
        with pytest.raises(ConfigurationException, match="resource"):
            manager.get_telemetry_config()


# ============================================================================
# Typed accessors
# ============================================================================


class TestTypedAccessors:
    """Test typed accessor methods return correct types and values."""

    def test_is_enabled_returns_bool_false(self, make_manager):
        """is_enabled() returns False by default."""
        manager = make_manager({})
        result = manager.is_enabled()
        assert result is False
        assert isinstance(result, bool)

    def test_is_enabled_returns_bool_true(self, make_manager):
        """is_enabled() returns True when configured."""
        manager = make_manager({"telemetry": {"enabled": True}})
        result = manager.is_enabled()
        assert result is True
        assert isinstance(result, bool)

    def test_get_exporter_config_returns_dict(self, make_manager):
        """get_exporter_config() returns dict with exporter, endpoint, protocol."""
        manager = make_manager({})
        config = manager.get_exporter_config()
        assert isinstance(config, dict)
        assert "exporter" in config
        assert "endpoint" in config
        assert "protocol" in config
        assert config["exporter"] == "none"
        assert config["endpoint"] == "http://localhost:4317"
        assert config["protocol"] == "grpc"

    def test_get_exporter_config_with_custom_values(self, make_manager):
        """get_exporter_config() returns custom values when configured."""
        manager = make_manager(
            {
                "telemetry": {
                    "exporter": "otlp",
                    "endpoint": "http://collector:4317",
                    "protocol": "http/protobuf",
                }
            }
        )
        config = manager.get_exporter_config()
        assert config["exporter"] == "otlp"
        assert config["endpoint"] == "http://collector:4317"
        assert config["protocol"] == "http/protobuf"

    def test_get_content_capture_flags_returns_four_bools(self, make_manager):
        """get_content_capture_flags() returns dict with four boolean keys."""
        manager = make_manager({})
        flags = manager.get_content_capture_flags()
        assert isinstance(flags, dict)
        assert len(flags) == 4
        assert all(isinstance(v, bool) for v in flags.values())
        expected_keys = {
            "agent_inputs",
            "agent_outputs",
            "llm_prompts",
            "llm_responses",
        }
        assert set(flags.keys()) == expected_keys

    def test_get_content_capture_flags_with_enabled(self, make_manager):
        """get_content_capture_flags() reflects config when flags enabled."""
        manager = make_manager(
            {
                "telemetry": {
                    "traces": {
                        "agent_inputs": True,
                        "llm_prompts": True,
                    }
                }
            }
        )
        flags = manager.get_content_capture_flags()
        assert flags["agent_inputs"] is True
        assert flags["agent_outputs"] is False
        assert flags["llm_prompts"] is True
        assert flags["llm_responses"] is False

    def test_get_resource_attributes_returns_dict(self, make_manager):
        """get_resource_attributes() returns dict with service.name defaulted."""
        manager = make_manager({})
        attrs = manager.get_resource_attributes()
        assert isinstance(attrs, dict)
        assert attrs["service.name"] == "agentmap"

    def test_get_resource_attributes_with_custom(self, make_manager):
        """get_resource_attributes() includes custom attributes."""
        manager = make_manager(
            {
                "telemetry": {
                    "resource": {
                        "service.name": "my-service",
                        "deployment.environment": "production",
                    }
                }
            }
        )
        attrs = manager.get_resource_attributes()
        assert attrs["service.name"] == "my-service"
        assert attrs["deployment.environment"] == "production"

    def test_get_telemetry_config_returns_complete_structure(self, make_manager):
        """get_telemetry_config() returns complete config with all expected keys."""
        manager = make_manager({})
        config = manager.get_telemetry_config()

        assert "enabled" in config
        assert "exporter" in config
        assert "endpoint" in config
        assert "protocol" in config
        assert "traces" in config
        assert "resource" in config
