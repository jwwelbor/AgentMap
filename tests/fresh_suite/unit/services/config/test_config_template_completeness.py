"""
Test suite for config template completeness.

Validates that the scaffolding template (agentmap_config.yaml.template) stays
in sync with the sections and keys that AppConfigService and other services
actually depend on.  When a new config section is added to the service layer
but the template is not updated, these tests will fail — that's the point.
"""

import unittest
from pathlib import Path

import yaml


# Path to the canonical template shipped with the package
_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[5]
    / "src"
    / "agentmap"
    / "templates"
    / "config"
    / "agentmap_config.yaml.template"
)


class TestConfigTemplateCompleteness(unittest.TestCase):
    """Ensure the config template covers every section the app requires."""

    def setUp(self):
        """Load and parse the template file once per test."""
        self.assertTrue(
            _TEMPLATE_PATH.exists(),
            f"Template file not found at {_TEMPLATE_PATH}",
        )
        with open(_TEMPLATE_PATH) as f:
            self.raw = f.read()
        self.config = yaml.safe_load(self.raw)

    # ------------------------------------------------------------------
    # Basic validity
    # ------------------------------------------------------------------

    def test_template_is_valid_yaml(self):
        """Template must parse without error and produce a dict."""
        self.assertIsInstance(self.config, dict, "Template did not parse to a dict")

    # ------------------------------------------------------------------
    # Top-level sections
    # ------------------------------------------------------------------

    # Sections that MUST appear in the template.
    # Update this set when adding a new section to the service layer.
    REQUIRED_TOP_LEVEL_SECTIONS = {
        "logging",
        "llm",
        "prompts",
        "execution",
        "paths",
        "memory",
        "routing",
        "messaging",
    }

    def test_template_has_required_top_level_sections(self):
        """Every section the application depends on must be in the template."""
        present = set(self.config.keys())
        missing = self.REQUIRED_TOP_LEVEL_SECTIONS - present
        self.assertFalse(
            missing,
            f"Template is missing required top-level sections: {sorted(missing)}",
        )

    def test_template_sections_cover_validate_config_requirements(self):
        """AppConfigService.validate_config() requires these four sections.

        If someone adds to that list without updating the template the test
        should break.
        """
        validate_config_required = {"logging", "llm", "prompts", "execution"}
        present = set(self.config.keys())
        missing = validate_config_required - present
        self.assertFalse(
            missing,
            f"Template missing sections required by validate_config(): {sorted(missing)}",
        )

    # ------------------------------------------------------------------
    # Sub-key checks for critical sections
    # ------------------------------------------------------------------

    def test_prompts_section_has_required_keys(self):
        """prompts: must define directory, registry_file, enable_cache."""
        prompts = self.config.get("prompts")
        self.assertIsInstance(prompts, dict, "prompts section is not a dict")
        for key in ("directory", "registry_file", "enable_cache"):
            self.assertIn(key, prompts, f"prompts section missing key '{key}'")

    def test_paths_section_has_required_keys(self):
        """paths: must define custom_agents, functions, csv_repository."""
        paths = self.config.get("paths")
        self.assertIsInstance(paths, dict, "paths section is not a dict")
        for key in ("custom_agents", "functions", "csv_repository"):
            self.assertIn(key, paths, f"paths section missing key '{key}'")

    def test_execution_section_has_required_keys(self):
        """execution: must contain a tracking sub-section."""
        execution = self.config.get("execution")
        self.assertIsInstance(execution, dict, "execution section is not a dict")
        self.assertIn("tracking", execution, "execution section missing 'tracking'")

    def test_logging_section_has_required_keys(self):
        """logging: must have version and handlers."""
        logging_cfg = self.config.get("logging")
        self.assertIsInstance(logging_cfg, dict, "logging section is not a dict")
        for key in ("version", "handlers"):
            self.assertIn(key, logging_cfg, f"logging section missing key '{key}'")

    def test_llm_section_has_at_least_one_provider(self):
        """llm: must define at least one provider block."""
        llm = self.config.get("llm")
        self.assertIsInstance(llm, dict, "llm section is not a dict")
        self.assertTrue(len(llm) >= 1, "llm section must have at least one provider")

    def test_routing_section_exists(self):
        """routing: must be present as a dict."""
        routing = self.config.get("routing")
        self.assertIsInstance(routing, dict, "routing section is not a dict")


if __name__ == "__main__":
    unittest.main()
