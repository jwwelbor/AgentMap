"""
Integration tests for PromptManagerService yaml: prefix resolution.

These tests use real YAML files on disk (not mocked) to verify that the yaml:
prefix resolves prompts from arbitrary YAML files that are separate from the
registry file configured in agentmap_config.yaml.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService


class TestPromptManagerYamlIntegration(unittest.TestCase):
    """Integration tests for yaml: prefix with real files on disk."""

    def setUp(self):
        """Create a temporary prompts directory with real YAML files."""
        self.temp_dir = tempfile.mkdtemp()
        self.prompts_dir = Path(self.temp_dir) / "prompts"
        self.prompts_dir.mkdir()

        # --- registry.yaml (the configured registry file) ---
        self.registry_path = self.prompts_dir / "registry.yaml"
        self.registry_path.write_text(
            yaml.dump({"greeting": "Hello from the registry!"})
        )

        # --- A completely separate YAML file (NOT the registry) ---
        self.support_dir = self.prompts_dir / "workflows" / "support"
        self.support_dir.mkdir(parents=True)

        support_prompts = {
            "responses": {
                "resolved": "Hi {customer_name}, ticket {ticket_id} is resolved.",
                "escalated": "Ticket {ticket_id} escalated to tier 2.",
            },
            "internal": {
                "handoff": {"notes": "Handoff from {previous_agent} to {new_agent}."}
            },
        }
        support_file = self.support_dir / "resolution_template.yaml"
        with open(support_file, "w") as f:
            yaml.dump(support_prompts, f, default_flow_style=False)

        # --- A second separate YAML file to prove multi-file works ---
        onboarding_prompts = {
            "steps": {
                "welcome": "Welcome aboard, {username}!",
                "training": "Please complete module {module_id}.",
            }
        }
        onboarding_dir = self.prompts_dir / "workflows" / "onboarding"
        onboarding_dir.mkdir(parents=True)
        onboarding_file = onboarding_dir / "steps.yaml"
        with open(onboarding_file, "w") as f:
            yaml.dump(onboarding_prompts, f, default_flow_style=False)

        # --- Build real service with real config pointing at temp dir ---
        mock_config = self._build_config_service()
        mock_logging = self._build_logging_service()
        self.service = PromptManagerService(mock_config, mock_logging)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _build_config_service(self):
        """Build a minimal AppConfigService-compatible object with real paths."""
        from unittest.mock import MagicMock

        config = MagicMock(spec=AppConfigService)
        config.get_prompts_config.return_value = {
            "directory": str(self.prompts_dir),
            "registry_file": str(self.registry_path),
            "enable_cache": False,
        }
        return config

    def _build_logging_service(self):
        """Build a real-ish logging service."""
        import logging
        from unittest.mock import MagicMock

        svc = MagicMock(spec=LoggingService)
        svc.get_class_logger.return_value = logging.getLogger(
            "test.prompt_manager_yaml"
        )
        return svc

    # -------------------------------------------------------------------------
    # yaml: resolution from a file that is NOT the registry
    # -------------------------------------------------------------------------

    def test_yaml_resolve_simple_key(self):
        """yaml: prefix resolves a top-level nested key from a non-registry file."""
        result = self.service.resolve_prompt(
            "yaml:workflows/support/resolution_template.yaml#responses.resolved"
        )
        self.assertEqual(result, "Hi {customer_name}, ticket {ticket_id} is resolved.")

    def test_yaml_resolve_sibling_key(self):
        """yaml: prefix resolves a different key from the same file."""
        result = self.service.resolve_prompt(
            "yaml:workflows/support/resolution_template.yaml#responses.escalated"
        )
        self.assertEqual(result, "Ticket {ticket_id} escalated to tier 2.")

    def test_yaml_resolve_deeply_nested_key(self):
        """yaml: prefix navigates 3+ levels of nesting."""
        result = self.service.resolve_prompt(
            "yaml:workflows/support/resolution_template.yaml#internal.handoff.notes"
        )
        self.assertEqual(result, "Handoff from {previous_agent} to {new_agent}.")

    def test_yaml_resolve_from_second_file(self):
        """yaml: prefix resolves from a completely different YAML file."""
        result = self.service.resolve_prompt(
            "yaml:workflows/onboarding/steps.yaml#steps.welcome"
        )
        self.assertEqual(result, "Welcome aboard, {username}!")

    def test_yaml_resolve_second_file_different_key(self):
        """yaml: prefix resolves another key from the second file."""
        result = self.service.resolve_prompt(
            "yaml:workflows/onboarding/steps.yaml#steps.training"
        )
        self.assertEqual(result, "Please complete module {module_id}.")

    # -------------------------------------------------------------------------
    # yaml: with format_prompt (variable substitution)
    # -------------------------------------------------------------------------

    def test_yaml_format_prompt_substitutes_variables(self):
        """format_prompt resolves yaml: reference then substitutes variables."""
        result = self.service.format_prompt(
            "yaml:workflows/support/resolution_template.yaml#responses.resolved",
            {"customer_name": "Alice", "ticket_id": "T-42"},
        )
        self.assertEqual(result, "Hi Alice, ticket T-42 is resolved.")

    def test_yaml_format_prompt_second_file(self):
        """format_prompt works with yaml: references to a different file."""
        result = self.service.format_prompt(
            "yaml:workflows/onboarding/steps.yaml#steps.welcome",
            {"username": "Bob"},
        )
        self.assertEqual(result, "Welcome aboard, Bob!")

    # -------------------------------------------------------------------------
    # Error cases (real files, real errors)
    # -------------------------------------------------------------------------

    def test_yaml_missing_file_returns_error(self):
        """yaml: prefix returns descriptive error for nonexistent file."""
        result = self.service.resolve_prompt("yaml:does_not_exist.yaml#some.key")
        self.assertIn("not found", result.lower())

    def test_yaml_missing_key_returns_error(self):
        """yaml: prefix returns error when key path doesn't exist in file."""
        result = self.service.resolve_prompt(
            "yaml:workflows/support/resolution_template.yaml#responses.nonexistent"
        )
        self.assertIn("not found", result.lower())

    def test_yaml_missing_hash_returns_error(self):
        """yaml: prefix returns error when # separator is missing."""
        result = self.service.resolve_prompt(
            "yaml:workflows/support/resolution_template.yaml"
        )
        self.assertIn("missing #key", result.lower())

    # -------------------------------------------------------------------------
    # Confirm registry still works alongside yaml:
    # -------------------------------------------------------------------------

    def test_registry_still_works(self):
        """prompt: prefix still resolves from the registry file."""
        result = self.service.resolve_prompt("prompt:greeting")
        self.assertEqual(result, "Hello from the registry!")

    def test_plain_text_passthrough(self):
        """Plain text without prefix passes through unchanged."""
        text = "You are a helpful assistant."
        result = self.service.resolve_prompt(text)
        self.assertEqual(result, text)


if __name__ == "__main__":
    unittest.main()
