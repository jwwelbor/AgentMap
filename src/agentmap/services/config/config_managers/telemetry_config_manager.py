"""Telemetry configuration manager."""

from typing import Any, Dict

from agentmap.exceptions.base_exceptions import ConfigurationException
from agentmap.services.config.config_managers.base_config_manager import (
    BaseConfigManager,
)

VALID_EXPORTERS = {"otlp", "console", "none"}
VALID_PROTOCOLS = {"grpc", "http/protobuf"}

DEFAULTS = {
    "enabled": False,
    "exporter": "none",
    "endpoint": "http://localhost:4317",
    "protocol": "grpc",
    "traces": {
        "agent_inputs": False,
        "agent_outputs": False,
        "llm_prompts": False,
        "llm_responses": False,
    },
    "resource": {
        "service.name": "agentmap",
    },
}


class TelemetryConfigManager(BaseConfigManager):
    """
    Configuration manager for telemetry settings.

    Handles telemetry configuration with privacy-safe defaults.
    All content capture flags default to false. Validates exporter
    and protocol values at config load time.
    """

    def get_telemetry_config(self) -> Dict[str, Any]:
        """
        Get the telemetry configuration with default values.

        Merges user config with defaults and validates exporter/protocol values.

        Returns:
            Complete telemetry configuration dictionary.

        Raises:
            ConfigurationException: If exporter or protocol values are invalid,
                if enabled or trace flags are non-boolean, or if resource
                attribute values are non-string.
        """
        raw = self.get_section("telemetry", {})
        if raw is None:
            raw = {}
        merged = self._merge_with_defaults(raw, DEFAULTS)

        self._validate(merged)

        return merged

    def is_enabled(self) -> bool:
        """
        Check if telemetry is enabled.

        Returns:
            True if telemetry is enabled, False otherwise.
        """
        raw = self.get_section("telemetry", {})
        if raw is None:
            raw = {}
        merged = self._merge_with_defaults(raw, DEFAULTS)
        return merged["enabled"]

    def get_exporter_config(self) -> Dict[str, str]:
        """
        Get exporter configuration.

        Returns:
            Dict with exporter, endpoint, and protocol keys.
        """
        config = self.get_telemetry_config()
        return {
            "exporter": config["exporter"],
            "endpoint": config["endpoint"],
            "protocol": config["protocol"],
        }

    def get_content_capture_flags(self) -> Dict[str, bool]:
        """
        Get content capture privacy flags.

        Returns:
            Dict with agent_inputs, agent_outputs, llm_prompts,
            and llm_responses boolean flags.
        """
        config = self.get_telemetry_config()
        traces = config.get("traces", {})
        return {
            "agent_inputs": traces.get("agent_inputs", False),
            "agent_outputs": traces.get("agent_outputs", False),
            "llm_prompts": traces.get("llm_prompts", False),
            "llm_responses": traces.get("llm_responses", False),
        }

    def get_resource_attributes(self) -> Dict[str, str]:
        """
        Get resource attributes for TracerProvider.

        Returns:
            Dict of resource attributes with service.name defaulted
            to 'agentmap'.
        """
        config = self.get_telemetry_config()
        return config.get("resource", {"service.name": "agentmap"})

    def _validate(self, config: Dict[str, Any]) -> None:
        """
        Validate telemetry configuration values.

        Args:
            config: Merged telemetry configuration dictionary.

        Raises:
            ConfigurationException: If any values are invalid.
        """
        # Validate enabled is boolean
        if not isinstance(config.get("enabled"), bool):
            raise ConfigurationException(
                f"Invalid telemetry 'enabled' value: '{config.get('enabled')}'. "
                "Must be a boolean (true/false)"
            )

        # Validate exporter
        exporter = config.get("exporter")
        if exporter not in VALID_EXPORTERS:
            raise ConfigurationException(
                f"Invalid telemetry exporter: '{exporter}'. "
                f"Valid options: otlp, console, none"
            )

        # Validate protocol
        protocol = config.get("protocol")
        if protocol not in VALID_PROTOCOLS:
            raise ConfigurationException(
                f"Invalid telemetry protocol: '{protocol}'. "
                f"Valid options: grpc, http/protobuf"
            )

        # Validate traces flags are booleans
        traces = config.get("traces", {})
        if isinstance(traces, dict):
            for key in (
                "agent_inputs",
                "agent_outputs",
                "llm_prompts",
                "llm_responses",
            ):
                if key in traces and not isinstance(traces[key], bool):
                    raise ConfigurationException(
                        f"Invalid telemetry traces.{key} value: "
                        f"'{traces[key]}'. Must be a boolean (true/false)"
                    )

        # Validate resource attributes are strings
        resource = config.get("resource", {})
        if isinstance(resource, dict):
            for key, value in resource.items():
                if not isinstance(value, str):
                    raise ConfigurationException(
                        f"Invalid telemetry resource attribute '{key}': "
                        f"'{value}'. OTEL resource attributes must be strings"
                    )
