"""Guard functions that crossed AgentMap's 50-line limit in B102."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]


@pytest.mark.parametrize(
    "path,name",
    [
        ("src/agentmap/services/llm/attempt_lifecycle.py", "invoke_governed_attempt"),
        ("src/agentmap/services/llm/attempt_lifecycle.py", "settle_failed_attempt"),
        ("src/agentmap/services/llm/attempt_lifecycle.py", "settle_successful_attempt"),
        ("src/agentmap/services/llm_client_factory.py", "get_or_create_client"),
        ("src/agentmap/services/llm_client_factory.py", "_create_openai_client"),
        ("src/agentmap/services/llm_client_factory.py", "_create_anthropic_client"),
        ("src/agentmap/services/llm_client_factory.py", "_create_google_client"),
        ("src/agentmap/services/llm_service.py", "_run_resilient_retry_loop"),
        (
            "tests/fresh_suite/unit/services/llm/test_response_evidence_security.py",
            "mark_sdk_error_repr",
        ),
        (
            "tests/fresh_suite/unit/services/llm/test_response_evidence_security.py",
            "provider_error_markers",
        ),
        (
            "tests/fresh_suite/unit/services/llm/test_response_evidence_security.py",
            "marked_error_transport",
        ),
        (
            "tests/fresh_suite/unit/services/llm/test_response_evidence_security.py",
            "assert_error_markers_confined",
        ),
        (
            "tests/fresh_suite/unit/services/llm/test_response_evidence_security.py",
            "test_provider_error_secrets_reach_only_response_evidence__b102",
        ),
    ],
)
def test_b102_newly_oversized_functions_stay_within_repository_limit(path, name):
    tree = ast.parse((ROOT / path).read_text())
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    assert len(matches) == 1
    size = matches[0].end_lineno - matches[0].lineno + 1
    assert size <= 50, f"{path}:{name} has {size} lines; limit is 50"


@pytest.mark.parametrize(
    "path",
    [
        "tests/fresh_suite/unit/services/llm/test_response_evidence.py",
        "tests/fresh_suite/unit/services/llm/test_response_evidence_security.py",
    ],
)
def test_b102_response_evidence_modules_stay_within_file_limit(path):
    lines = (ROOT / path).read_text().splitlines()
    assert len(lines) <= 350, f"{path} has {len(lines)} lines; limit is 350"
