#!/usr/bin/env python3
"""
Prompt Management Integration Test

Exercises the PromptManagerService as a host application would:
real files on disk, all three resolution backends (registry, file, yaml),
subfolder paths, variable substitution, caching, and the fallback chain.

Run from the repo root:
    uv run python examples/prompt_management/test_prompt_management.py
"""

import sys
from pathlib import Path
from typing import Any, Dict

# --- bootstrap: make the library importable from a source checkout ----------
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.config.config_service import ConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_pass = 0
_fail = 0


def ok(label: str):
    global _pass
    _pass += 1
    print(f"  PASS  {label}")


def fail(label: str, detail: str = ""):
    global _fail
    _fail += 1
    msg = f"  FAIL  {label}"
    if detail:
        msg += f"  -- {detail}"
    print(msg)


def check(condition: bool, label: str, detail: str = ""):
    if condition:
        ok(label)
    else:
        fail(label, detail)


def build_service(*, enable_cache: bool = False) -> PromptManagerService:
    """Build a PromptManagerService pointing at our sample prompts directory."""
    config_svc = ConfigService()
    # Minimal app config -- only the prompts section matters
    app_config = AppConfigService(config_svc, config_path=None)

    # Override the prompts section that the service reads at init
    app_config.get_prompts_config = lambda: {
        "directory": str(PROMPTS_DIR),
        "registry_file": str(PROMPTS_DIR / "registry.yaml"),
        "enable_cache": enable_cache,
    }

    logging_config = app_config.get_logging_config()
    logging_svc = LoggingService(logging_config)
    logging_svc.initialize()

    return PromptManagerService(app_config, logging_svc)


# ---------------------------------------------------------------------------
# Test groups
# ---------------------------------------------------------------------------

def test_registry_resolution(svc: PromptManagerService):
    """prompt: prefix -- keys looked up in registry.yaml"""
    print("\n[1] Registry resolution (prompt: prefix)")

    # Simple key
    result = svc.resolve_prompt("prompt:welcome")
    check(
        "{username}" in result and "{workflow_name}" in result,
        "prompt:welcome resolves with placeholders",
        f"got: {result!r:.80}",
    )

    # Multi-line key
    result = svc.resolve_prompt("prompt:classify_goal")
    check(
        "classification expert" in result and "{goal}" in result,
        "prompt:classify_goal resolves multi-line YAML block",
    )

    # Missing key
    result = svc.resolve_prompt("prompt:does_not_exist")
    check(
        "not found" in result.lower(),
        "missing registry key returns descriptive error",
        f"got: {result!r:.80}",
    )


def test_file_resolution(svc: PromptManagerService):
    """file: prefix -- text files in the prompts directory tree"""
    print("\n[2] File resolution (file: prefix)")

    # Top-level subfolder
    result = svc.resolve_prompt("file:agents/llm/code_reviewer.txt")
    check(
        "code reviewer" in result.lower() and "{language}" in result,
        "file:agents/llm/code_reviewer.txt (2 levels deep)",
    )

    result = svc.resolve_prompt("file:agents/summary/executive_brief.txt")
    check(
        "executive brief" in result.lower() and "{topic}" in result,
        "file:agents/summary/executive_brief.txt (different subfolder)",
    )

    # Workflow subfolders
    result = svc.resolve_prompt("file:workflows/onboarding/step1_welcome.txt")
    check(
        "{employee_name}" in result and "{buddy_name}" in result,
        "file:workflows/onboarding/step1_welcome.txt",
    )

    result = svc.resolve_prompt("file:workflows/support/triage.txt")
    check(
        "{ticket_id}" in result and "JSON" in result,
        "file:workflows/support/triage.txt",
    )

    # Missing file
    result = svc.resolve_prompt("file:does/not/exist.txt")
    check(
        "not found" in result.lower(),
        "missing file returns descriptive error",
        f"got: {result!r:.80}",
    )


def test_yaml_resolution(svc: PromptManagerService):
    """yaml: prefix -- values inside YAML files via dot-notation key paths"""
    print("\n[3] YAML resolution (yaml: prefix)")

    base = "workflows/support/resolution_template.yaml"

    result = svc.resolve_prompt(f"yaml:{base}#responses.resolved")
    check(
        "{customer_name}" in result and "{resolution_summary}" in result,
        "yaml:...#responses.resolved",
    )

    result = svc.resolve_prompt(f"yaml:{base}#responses.escalated")
    check(
        "{escalation_reason}" in result and "{sla_hours}" in result,
        "yaml:...#responses.escalated",
    )

    result = svc.resolve_prompt(f"yaml:{base}#internal.handoff_notes")
    check(
        "INTERNAL" in result and "{previous_agent}" in result,
        "yaml:...#internal.handoff_notes (nested section)",
    )

    # Missing key path
    result = svc.resolve_prompt(f"yaml:{base}#responses.nonexistent")
    check(
        "not found" in result.lower(),
        "missing YAML key returns descriptive error",
        f"got: {result!r:.80}",
    )

    # Missing hash separator
    result = svc.resolve_prompt(f"yaml:{base}")
    check(
        "missing #key" in result.lower() or "invalid" in result.lower(),
        "yaml ref without # returns descriptive error",
        f"got: {result!r:.80}",
    )


def test_plain_text_passthrough(svc: PromptManagerService):
    """Strings without a recognized prefix pass through unchanged."""
    print("\n[4] Plain text passthrough")

    plain = "You are a helpful assistant. Answer the user's question."
    result = svc.resolve_prompt(plain)
    check(result == plain, "plain text returned unchanged")

    check(svc.resolve_prompt("") == "", "empty string passes through")
    check(svc.resolve_prompt(None) is None, "None passes through")


def test_format_prompt(svc: PromptManagerService):
    """format_prompt: resolve + variable substitution in one call."""
    print("\n[5] format_prompt (resolve + substitute)")

    # Registry prompt with variables
    result = svc.format_prompt(
        "prompt:welcome",
        {"username": "Alice", "workflow_name": "OnboardingFlow"},
    )
    check(
        "Alice" in result and "OnboardingFlow" in result,
        "registry prompt formatted with variables",
    )

    # File prompt with variables
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
    check(
        "Bob" in result
        and "Engineering" in result
        and "Carol" in result
        and "{employee_name}" not in result,
        "file prompt formatted with all 5 variables",
    )

    # YAML prompt with variables
    result = svc.format_prompt(
        "yaml:workflows/support/resolution_template.yaml#responses.resolved",
        {
            "customer_name": "Dave",
            "ticket_id": "TKT-42",
            "resolution_summary": "Reset the widget cache",
            "agent_name": "SupportBot",
        },
    )
    check(
        "Dave" in result
        and "TKT-42" in result
        and "Reset the widget cache" in result
        and "{customer_name}" not in result,
        "YAML prompt formatted with variables",
    )

    # Plain text with variables
    result = svc.format_prompt(
        "Hello {name}, your order #{order_id} is ready.",
        {"name": "Eve", "order_id": "9001"},
    )
    check(
        "Eve" in result and "9001" in result,
        "plain text formatted with variables",
    )


def test_caching(svc_cached: PromptManagerService):
    """With caching enabled, repeat resolutions hit the cache."""
    print("\n[6] Caching behaviour")

    check(svc_cached.enable_cache is True, "cache is enabled")

    # First call populates cache
    result1 = svc_cached.resolve_prompt("prompt:farewell")
    check("prompt:farewell" in svc_cached._cache, "cache populated after first call")

    # Second call returns same value
    result2 = svc_cached.resolve_prompt("prompt:farewell")
    check(result1 == result2, "cached result matches original")

    # Clear cache
    svc_cached.clear_cache()
    check(len(svc_cached._cache) == 0, "clear_cache empties the cache")


def test_get_registry(svc: PromptManagerService):
    """get_registry returns a safe copy of the loaded registry."""
    print("\n[7] get_registry")

    registry = svc.get_registry()
    check(isinstance(registry, dict), "returns a dict")
    check("welcome" in registry, "contains 'welcome' key")
    check("classify_goal" in registry, "contains 'classify_goal' key")
    check("support_escalation" in registry, "contains 'support_escalation' key")

    # Mutation safety
    registry["injected_key"] = "should not appear"
    check(
        "injected_key" not in svc.get_registry(),
        "mutations to returned dict don't affect service",
    )


def test_service_info(svc: PromptManagerService):
    """get_service_info returns diagnostic metadata."""
    print("\n[8] get_service_info")

    info = svc.get_service_info()
    check(info["service"] == "PromptManagerService", "service name present")
    check(info["config_available"] is True, "config available")
    check(str(PROMPTS_DIR) in info["prompts_dir"], "prompts_dir matches")
    check(info["registry_size"] > 0, f"registry_size = {info['registry_size']}")
    check(
        set(info["supported_prefixes"]) == {"prompt:", "file:", "yaml:"},
        "supported_prefixes correct",
    )


def test_get_formatted_prompt_fallback():
    """get_formatted_prompt tries primary -> file -> default in order."""
    print("\n[9] get_formatted_prompt fallback chain")

    import logging
    from agentmap.services.prompt_manager_service import get_formatted_prompt

    # We need the global singleton to be our service
    import agentmap.services.prompt_manager_service as pms

    original = pms._prompt_manager
    pms._prompt_manager = build_service()

    logger = logging.getLogger("test_fallback")

    try:
        # Primary succeeds
        result = get_formatted_prompt(
            primary_prompt="prompt:welcome",
            template_file="file:agents/llm/code_reviewer.txt",
            default_template="Fallback: {username}",
            values={"username": "Zara", "workflow_name": "Test"},
            logger=logger,
        )
        check(
            "Zara" in result and "Test" in result,
            "primary prompt used when available",
        )

        # Primary is None, falls through to file
        result = get_formatted_prompt(
            primary_prompt=None,
            template_file="file:workflows/support/triage.txt",
            default_template="Default fallback",
            values={
                "ticket_id": "T-1",
                "customer_name": "Yan",
                "issue_description": "broken",
            },
            logger=logger,
        )
        check(
            "T-1" in result and "Yan" in result,
            "file template used when primary is None",
        )

        # Both None, falls through to default
        result = get_formatted_prompt(
            primary_prompt=None,
            template_file=None,
            default_template="Default for {who}",
            values={"who": "Xavier"},
            logger=logger,
        )
        check("Xavier" in result, "default template used as last resort")

    finally:
        pms._prompt_manager = original


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 64)
    print("  AgentMap Prompt Management - Integration Test")
    print(f"  Prompts directory: {PROMPTS_DIR}")
    print("=" * 64)

    # Verify prompts directory exists
    if not PROMPTS_DIR.exists():
        print(f"\nERROR: Prompts directory not found: {PROMPTS_DIR}")
        return 1

    svc = build_service(enable_cache=False)
    svc_cached = build_service(enable_cache=True)

    test_registry_resolution(svc)
    test_file_resolution(svc)
    test_yaml_resolution(svc)
    test_plain_text_passthrough(svc)
    test_format_prompt(svc)
    test_caching(svc_cached)
    test_get_registry(svc)
    test_service_info(svc)
    test_get_formatted_prompt_fallback()

    print("\n" + "=" * 64)
    total = _pass + _fail
    print(f"  Results: {_pass} passed, {_fail} failed  ({total} total)")
    print("=" * 64)

    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
