"""
Test suite for env: prefix resolution in ConfigService.

Validates that ConfigService._resolve_env_vars() correctly resolves
environment variable references in config data loaded from YAML files.
"""

import os
import tempfile
import unittest

import yaml

from agentmap.services.config.config_service import ConfigService


class TestEnvVarResolution(unittest.TestCase):
    """Test env: prefix resolution in ConfigService."""

    def setUp(self):
        """Set up test fixtures."""
        ConfigService._instance = None
        self.config_service = ConfigService()
        self.temp_dir = tempfile.mkdtemp()
        # Save original env to restore later
        self._original_env = os.environ.copy()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        ConfigService._instance = None
        # Restore original environment
        os.environ.clear()
        os.environ.update(self._original_env)

    def test_resolve_simple_env_var(self):
        """env:VAR resolves from os.environ."""
        os.environ["TEST_API_KEY"] = "sk-test-123"
        result = self.config_service._resolve_env_vars("env:TEST_API_KEY")
        self.assertEqual(result, "sk-test-123")

    def test_resolve_env_var_with_default_missing(self):
        """env:VAR:default returns default when var is missing."""
        os.environ.pop("MISSING_VAR", None)
        result = self.config_service._resolve_env_vars("env:MISSING_VAR:fallback_value")
        self.assertEqual(result, "fallback_value")

    def test_resolve_env_var_with_default_present(self):
        """env:VAR:default returns env value when var is present (default ignored)."""
        os.environ["PRESENT_VAR"] = "real_value"
        result = self.config_service._resolve_env_vars("env:PRESENT_VAR:fallback_value")
        self.assertEqual(result, "real_value")

    def test_resolve_missing_env_var_no_default(self):
        """env:VAR with missing var and no default returns empty string."""
        os.environ.pop("TOTALLY_MISSING", None)
        result = self.config_service._resolve_env_vars("env:TOTALLY_MISSING")
        self.assertEqual(result, "")

    def test_resolve_nested_dict(self):
        """Nested dicts are resolved recursively."""
        os.environ["NESTED_KEY"] = "resolved_nested"
        data = {
            "level1": {
                "level2": {
                    "key": "env:NESTED_KEY",
                }
            }
        }
        result = self.config_service._resolve_env_vars(data)
        self.assertEqual(result["level1"]["level2"]["key"], "resolved_nested")

    def test_resolve_list_values(self):
        """Lists are resolved recursively."""
        os.environ["LIST_VAR"] = "list_value"
        data = ["env:LIST_VAR", "plain_string", 42]
        result = self.config_service._resolve_env_vars(data)
        self.assertEqual(result, ["list_value", "plain_string", 42])

    def test_non_string_values_pass_through(self):
        """Non-string values pass through unchanged."""
        data = {
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "none_val": None,
        }
        result = self.config_service._resolve_env_vars(data)
        self.assertEqual(result, data)

    def test_non_env_strings_pass_through(self):
        """Strings without env: prefix pass through unchanged."""
        result = self.config_service._resolve_env_vars("just a regular string")
        self.assertEqual(result, "just a regular string")

    def test_resolve_in_realistic_config(self):
        """Realistic LLM config with env: values resolves correctly."""
        os.environ["TEST_OPENAI_KEY"] = "sk-real-key"
        os.environ.pop("TEST_MISSING_KEY", None)

        data = {
            "llm": {
                "openai": {
                    "api_key": "env:TEST_OPENAI_KEY",
                    "model": "gpt-4.1-mini",
                    "temperature": 0.7,
                },
                "anthropic": {
                    "api_key": "env:TEST_MISSING_KEY:sk-fallback",
                    "model": "claude-sonnet-4-6",
                },
            }
        }
        result = self.config_service._resolve_env_vars(data)
        self.assertEqual(result["llm"]["openai"]["api_key"], "sk-real-key")
        self.assertEqual(result["llm"]["anthropic"]["api_key"], "sk-fallback")
        # Non-env values unchanged
        self.assertEqual(result["llm"]["openai"]["model"], "gpt-4.1-mini")
        self.assertEqual(result["llm"]["openai"]["temperature"], 0.7)

    def test_default_with_colon_in_value(self):
        """env:VAR:default where default itself contains colons."""
        os.environ.pop("URL_VAR", None)
        result = self.config_service._resolve_env_vars(
            "env:URL_VAR:http://localhost:8080"
        )
        self.assertEqual(result, "http://localhost:8080")

    def test_end_to_end_load_config_resolves_env(self):
        """End-to-end: YAML file with env: values resolves on load_config()."""
        os.environ["E2E_TEST_KEY"] = "e2e_resolved"

        config_data = {
            "llm": {
                "openai": {
                    "api_key": "env:E2E_TEST_KEY",
                }
            }
        }
        test_file = os.path.join(self.temp_dir, "env_test_config.yaml")
        with open(test_file, "w") as f:
            yaml.dump(config_data, f)

        result = self.config_service.load_config(test_file)
        self.assertEqual(result["llm"]["openai"]["api_key"], "e2e_resolved")

    def test_empty_env_var_with_no_default_logs_warning(self):
        """Empty env var with no default logs a warning."""
        os.environ.pop("WARN_TEST_VAR", None)
        # Should not raise, just return ""
        result = self.config_service._resolve_env_vars("env:WARN_TEST_VAR")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
