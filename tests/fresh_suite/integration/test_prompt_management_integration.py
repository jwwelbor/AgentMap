"""
Integration tests for PromptManagerService.

Exercises all three resolution backends (registry, file, yaml),
subfolder paths, variable substitution, caching, the fallback chain,
and service diagnostics using real prompt files on disk.

Prompt fixtures live in examples/prompt_management/prompts/.
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.config.config_service import ConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROMPTS_DIR = (
    Path(__file__).resolve().parents[3] / "examples" / "prompt_management" / "prompts"
)


def _build_service(*, enable_cache: bool = False) -> PromptManagerService:
    """Build a PromptManagerService pointing at the example prompts directory."""
    config_svc = ConfigService()
    app_config = AppConfigService(config_svc, config_path=None)

    app_config.get_prompts_config = lambda: {
        "directory": str(PROMPTS_DIR),
        "registry_file": str(PROMPTS_DIR / "registry.yaml"),
        "enable_cache": enable_cache,
    }

    logging_config = app_config.get_logging_config()
    logging_svc = LoggingService(logging_config)
    logging_svc.initialize()

    return PromptManagerService(app_config, logging_svc)


@pytest.fixture
def svc():
    """PromptManagerService with caching disabled."""
    return _build_service(enable_cache=False)


@pytest.fixture
def svc_cached():
    """PromptManagerService with caching enabled."""
    return _build_service(enable_cache=True)


# ---------------------------------------------------------------------------
# Registry resolution (prompt: prefix)
# ---------------------------------------------------------------------------


class TestRegistryResolution:

    def test_simple_key(self, svc):
        result = svc.resolve_prompt("prompt:welcome")
        assert "{username}" in result
        assert "{workflow_name}" in result

    def test_multiline_key(self, svc):
        result = svc.resolve_prompt("prompt:classify_goal")
        assert "classification expert" in result
        assert "{goal}" in result

    def test_missing_key(self, svc):
        result = svc.resolve_prompt("prompt:does_not_exist")
        assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# File resolution (file: prefix)
# ---------------------------------------------------------------------------


class TestFileResolution:

    def test_nested_subfolder(self, svc):
        result = svc.resolve_prompt("file:agents/llm/code_reviewer.txt")
        assert "code reviewer" in result.lower()
        assert "{language}" in result

    def test_different_subfolder(self, svc):
        result = svc.resolve_prompt("file:agents/summary/executive_brief.txt")
        assert "executive brief" in result.lower()
        assert "{topic}" in result

    def test_workflow_subfolder(self, svc):
        result = svc.resolve_prompt("file:workflows/onboarding/step1_welcome.txt")
        assert "{employee_name}" in result
        assert "{buddy_name}" in result

    def test_support_workflow(self, svc):
        result = svc.resolve_prompt("file:workflows/support/triage.txt")
        assert "{ticket_id}" in result
        assert "JSON" in result

    def test_missing_file(self, svc):
        result = svc.resolve_prompt("file:does/not/exist.txt")
        assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# YAML resolution (yaml: prefix)
# ---------------------------------------------------------------------------


class TestYamlResolution:

    _base = "workflows/support/resolution_template.yaml"

    def test_resolved_response(self, svc):
        result = svc.resolve_prompt(f"yaml:{self._base}#responses.resolved")
        assert "{customer_name}" in result
        assert "{resolution_summary}" in result

    def test_escalated_response(self, svc):
        result = svc.resolve_prompt(f"yaml:{self._base}#responses.escalated")
        assert "{escalation_reason}" in result
        assert "{sla_hours}" in result

    def test_nested_section(self, svc):
        result = svc.resolve_prompt(f"yaml:{self._base}#internal.handoff_notes")
        assert "INTERNAL" in result
        assert "{previous_agent}" in result

    def test_missing_key_path(self, svc):
        result = svc.resolve_prompt(f"yaml:{self._base}#responses.nonexistent")
        assert "not found" in result.lower()

    def test_missing_hash_separator(self, svc):
        result = svc.resolve_prompt(f"yaml:{self._base}")
        assert "missing #key" in result.lower() or "invalid" in result.lower()


# ---------------------------------------------------------------------------
# Plain text passthrough
# ---------------------------------------------------------------------------


class TestPlainTextPassthrough:

    def test_plain_text(self, svc):
        plain = "You are a helpful assistant. Answer the user's question."
        assert svc.resolve_prompt(plain) == plain

    def test_empty_string(self, svc):
        assert svc.resolve_prompt("") == ""

    def test_none(self, svc):
        assert svc.resolve_prompt(None) is None


# ---------------------------------------------------------------------------
# format_prompt (resolve + substitute)
# ---------------------------------------------------------------------------


class TestFormatPrompt:

    def test_registry_prompt(self, svc):
        result = svc.format_prompt(
            "prompt:welcome",
            {"username": "Alice", "workflow_name": "OnboardingFlow"},
        )
        assert "Alice" in result
        assert "OnboardingFlow" in result

    def test_file_prompt(self, svc):
        result = svc.format_prompt(
            "file:workflows/onboarding/step1_welcome.txt",
            {
                "employee_name": "Bob",
                "department": "Engineering",
                "role": "Backend Developer",
                "start_date": "2026-03-01",
                "buddy_name": "Carol",
            },
        )
        assert "Bob" in result
        assert "Engineering" in result
        assert "Carol" in result
        assert "{employee_name}" not in result

    def test_yaml_prompt(self, svc):
        result = svc.format_prompt(
            "yaml:workflows/support/resolution_template.yaml#responses.resolved",
            {
                "customer_name": "Dave",
                "ticket_id": "TKT-42",
                "resolution_summary": "Reset the widget cache",
                "agent_name": "SupportBot",
            },
        )
        assert "Dave" in result
        assert "TKT-42" in result
        assert "Reset the widget cache" in result
        assert "{customer_name}" not in result

    def test_plain_text(self, svc):
        result = svc.format_prompt(
            "Hello {name}, your order #{order_id} is ready.",
            {"name": "Eve", "order_id": "9001"},
        )
        assert "Eve" in result
        assert "9001" in result


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


class TestCaching:

    def test_cache_enabled(self, svc_cached):
        assert svc_cached.enable_cache is True

    def test_cache_populated(self, svc_cached):
        svc_cached.resolve_prompt("prompt:farewell")
        assert "prompt:farewell" in svc_cached._cache

    def test_cached_result_matches(self, svc_cached):
        result1 = svc_cached.resolve_prompt("prompt:farewell")
        result2 = svc_cached.resolve_prompt("prompt:farewell")
        assert result1 == result2

    def test_clear_cache(self, svc_cached):
        svc_cached.resolve_prompt("prompt:farewell")
        svc_cached.clear_cache()
        assert len(svc_cached._cache) == 0


# ---------------------------------------------------------------------------
# get_registry
# ---------------------------------------------------------------------------


class TestGetRegistry:

    def test_returns_dict(self, svc):
        assert isinstance(svc.get_registry(), dict)

    def test_contains_expected_keys(self, svc):
        registry = svc.get_registry()
        assert "welcome" in registry
        assert "classify_goal" in registry
        assert "support_escalation" in registry

    def test_mutation_safety(self, svc):
        registry = svc.get_registry()
        registry["injected_key"] = "should not appear"
        assert "injected_key" not in svc.get_registry()


# ---------------------------------------------------------------------------
# get_service_info
# ---------------------------------------------------------------------------


class TestServiceInfo:

    def test_service_name(self, svc):
        info = svc.get_service_info()
        assert info["service"] == "PromptManagerService"

    def test_config_available(self, svc):
        assert svc.get_service_info()["config_available"] is True

    def test_prompts_dir(self, svc):
        assert str(PROMPTS_DIR) in svc.get_service_info()["prompts_dir"]

    def test_registry_size(self, svc):
        assert svc.get_service_info()["registry_size"] > 0

    def test_supported_prefixes(self, svc):
        prefixes = set(svc.get_service_info()["supported_prefixes"])
        assert prefixes == {"prompt:", "file:", "yaml:"}


# ---------------------------------------------------------------------------
# get_formatted_prompt fallback chain
# ---------------------------------------------------------------------------


class TestGetFormattedPromptFallback:

    def test_primary_prompt_used(self):
        from agentmap.services.prompt_manager_service import get_formatted_prompt

        with patch(
            "agentmap.services.prompt_manager_service._prompt_manager", _build_service()
        ):
            result = get_formatted_prompt(
                primary_prompt="prompt:welcome",
                template_file="file:agents/llm/code_reviewer.txt",
                default_template="Fallback: {username}",
                values={"username": "Zara", "workflow_name": "Test"},
                logger=logging.getLogger("test_fallback"),
            )
        assert "Zara" in result
        assert "Test" in result

    def test_falls_through_to_file(self):
        from agentmap.services.prompt_manager_service import get_formatted_prompt

        with patch(
            "agentmap.services.prompt_manager_service._prompt_manager", _build_service()
        ):
            result = get_formatted_prompt(
                primary_prompt=None,
                template_file="file:workflows/support/triage.txt",
                default_template="Default fallback",
                values={
                    "ticket_id": "T-1",
                    "customer_name": "Yan",
                    "issue_description": "broken",
                },
                logger=logging.getLogger("test_fallback"),
            )
        assert "T-1" in result
        assert "Yan" in result

    def test_falls_through_to_default(self):
        from agentmap.services.prompt_manager_service import get_formatted_prompt

        with patch(
            "agentmap.services.prompt_manager_service._prompt_manager", _build_service()
        ):
            result = get_formatted_prompt(
                primary_prompt=None,
                template_file=None,
                default_template="Default for {who}",
                values={"who": "Xavier"},
                logger=logging.getLogger("test_fallback"),
            )
        assert "Xavier" in result
