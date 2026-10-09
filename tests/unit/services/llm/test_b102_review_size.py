"""Guard functions that crossed AgentMap's 50-line limit in B102."""

import ast
import tomllib

import pytest

from tests.unit.services.llm.test_b102_review_inventory import (
    B102_TEST_MODULES,
    ROOT,
    _class_definitions,
    _duplicate_definitions,
    _imported_names,
    _public_names,
)

B102_SOURCE_MODULES = (
    "src/agentmap/runtime/runtime_manager.py",
    "src/agentmap/runtime/cleanup_mixin.py",
    "src/agentmap/runtime/lifespan_mixin.py",
    "src/agentmap/services/llm/client_lifecycle.py",
    "src/agentmap/services/llm/ordinary_lifecycle.py",
    "src/agentmap/services/llm/invocation_lease.py",
    "src/agentmap/services/llm/response_observer.py",
    "src/agentmap/services/llm/observed_transports.py",
    "src/agentmap/services/llm/observed_clients.py",
    "src/agentmap/services/llm/stream_lifecycle.py",
    "src/agentmap/services/llm/attempt_lifecycle.py",
    "src/agentmap/services/llm/batch_lifecycle.py",
    "src/agentmap/services/llm/governed_accounting.py",
    "src/agentmap/services/llm/telemetry_lifecycle.py",
    "src/agentmap/async_lifecycle.py",
    "src/agentmap/deployment/http/api/sse.py",
    "src/agentmap/deployment/http/api/sse_lifecycle.py",
)


def _top_level_functions(tree):
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _named_call_owners(tree, call_name):
    return [
        function.name
        for function in _top_level_functions(tree)
        for call in ast.walk(function)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == call_name
    ]


def _attribute_call_owners(tree, attribute_name):
    return [
        function.name
        for function in _top_level_functions(tree)
        for call in ast.walk(function)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == attribute_name
    ]


def _find_function(tree, name):
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _assignment_lines_with_attribute(node, attribute_name):
    lines = []
    for statement in ast.walk(node):
        if not isinstance(statement, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Attribute) and target.attr == attribute_name
            for target in statement.targets
        ):
            lines.append(statement.lineno)
    return lines


def _call_lines_named(node, call_name):
    return [
        call.lineno
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == call_name
    ]


def _reads_attribute(node, owner_name, attribute_name):
    return any(
        isinstance(access, ast.Attribute)
        and isinstance(access.value, ast.Name)
        and access.value.id == owner_name
        and access.attr == attribute_name
        for access in ast.walk(node)
    )


def test_b102_structural_inventory_retains_both_test_roots():
    roots = {path.parts[:2] for path in B102_TEST_MODULES}
    assert ("tests", "unit") in roots
    assert ("tests", "fresh_suite") in roots


def test_shared_usage_functions_have_at_most_nine_decision_points__b102():
    """Keep evidence decoding and pricing decisions independently inspectable."""
    tree = ast.parse((ROOT / "src/agentmap/services/llm/usage_presence.py").read_text())
    branching = (
        ast.If,
        ast.IfExp,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.ExceptHandler,
        ast.comprehension,
    )
    for function in tree.body:
        if isinstance(function, ast.FunctionDef):
            decisions = sum(isinstance(node, branching) for node in ast.walk(function))
            decisions += sum(
                len(node.values) - 1
                for node in ast.walk(function)
                if isinstance(node, ast.BoolOp)
            )
            assert decisions <= 9, f"{function.name} has {decisions} decision points"


def test_one_finalizer_owns_the_only_completion_call_site__b102():
    tree = ast.parse(
        (ROOT / "src/agentmap/services/llm/attempt_lifecycle.py").read_text()
    )
    assert _named_call_owners(tree, "finish_attempt") == ["finalize_attempt"]
    assert _attribute_call_owners(tree, "after_attempt") == ["finish_attempt"]
    assert _named_call_owners(tree, "finalize_attempt") == ["invoke_governed_attempt"]


def test_b102_shared_exceptions_keep_the_canonical_package_owner():
    names = {"AttemptLifecycleRefusal", "ResponseCaptureFailure"}
    exceptions_root = ROOT / "src/agentmap/exceptions"
    canonical_tree = ast.parse((exceptions_root / "service_exceptions.py").read_text())
    assert _class_definitions(canonical_tree, names) == names
    package_tree = ast.parse((exceptions_root / "__init__.py").read_text())
    assert names <= _imported_names(
        package_tree, "agentmap.exceptions.service_exceptions"
    )
    assert names <= _public_names(package_tree)
    duplicates = _duplicate_definitions(ROOT / "src/agentmap/services", ROOT, names)
    assert not duplicates, duplicates


def test_qualified_provider_versions_are_pinned_in_install_extras__b102():
    observed = ast.parse(
        (ROOT / "src/agentmap/services/llm/observed_clients.py").read_text()
    )
    assignment = next(
        node
        for node in observed.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "QUALIFIED_VERSIONS"
            for target in node.targets
        )
    )
    required = {
        f"{package}=={version}"
        for provider in ast.literal_eval(assignment.value).values()
        for package, version in provider.items()
    }
    extras = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    for extra in ("llm", "all"):
        assert required <= set(extras[extra]), f"{extra} misses qualified packages"


_B102_FUNCTION_LIMITS = {
    "src/agentmap/async_lifecycle.py": """
        _cancellation_count raise_cleanup_error_or_note create_task_or_close
        create_cleanup_task_or_close await_terminal_task raise_initialization_outcome result
    """.split(),
    "src/agentmap/deployment/http/api/sse_lifecycle.py": """
        _merge_cleanup_error _finish_sse_cleanup _close_upstream
        _release_semaphore_slot _close_upstream_and_release_slot aclose_upstream_and_release
    """.split(),
    "src/agentmap/services/llm/attempt_lifecycle.py": """
        invoke_governed_attempt evaluate_attempt_response terminal_outcome
        propagate_finalized_failure finalize_attempt run_governed_invocation
        get_async_client invoke_timed_provider
    """.split(),
    "src/agentmap/services/llm/batch_lifecycle.py": """
        reject_batch_lifecycle_options
    """.split(),
    "src/agentmap/services/llm/governed_accounting.py": """
        governed_accounting_callbacks invoke_accounted_attempt
    """.split(),
    "src/agentmap/services/llm/invocation_lease.py": """
        dispatch_plain_sync_call invoke_provider_async
    """.split(),
    "src/agentmap/services/llm/response_observer.py": """
        observe_successful_receipt
    """.split(),
    "src/agentmap/services/llm/stream_lifecycle.py": """
        close_async_stream_preserving_primary _raise_stream_close_outcome
        _raise_stream_close_error isolated_llm_stream create_llm_stream_async
    """.split(),
    "src/agentmap/services/llm/telemetry_lifecycle.py": """
        span_preserving_primary close_span_preserving_primary
        call_with_telemetry call_with_telemetry_async
    """.split(),
    "src/agentmap/services/llm/cost_calculator.py": "calculate".split(),
    "src/agentmap/services/llm/usage_presence.py": """
        provider_usage_presence validate_usage_presence capture_measurements
    """.split(),
    "src/agentmap/services/llm_client_factory.py": """
        get_or_create_client _create_langchain_client _create_openai_client
        _create_anthropic_client _create_google_client
    """.split(),
    "src/agentmap/services/llm_service.py": """
        _build_success_llm_response _observe_successful_receipt _run_resilient_retry_loop
        call_llm call_llm_async _call_llm_async_with_telemetry
        _call_llm_with_telemetry call_llm_stream_async
        _close_async_stream_preserving_primary _invoke_provider_async
    """.split(),
    "tests/fresh_suite/unit/services/llm/test_response_evidence_security.py": """
        mark_sdk_error_repr provider_error_markers marked_error_transport
        assert_error_markers_confined test_provider_error_secrets_reach_only_response_evidence__b102
    """.split(),
}


@pytest.mark.parametrize(
    "path,name",
    [(path, name) for path, names in _B102_FUNCTION_LIMITS.items() for name in names],
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


@pytest.mark.parametrize("path", B102_TEST_MODULES)
def test_b102_owned_modules_stay_within_file_limit(path):
    lines = (ROOT / path).read_text().splitlines()
    assert len(lines) <= 350, f"{path} has {len(lines)} lines; limit is 350"


@pytest.mark.parametrize("path", B102_SOURCE_MODULES)
def test_b102_owned_source_modules_stay_within_file_limit(path):
    lines = (ROOT / path).read_text().splitlines()
    assert len(lines) <= 350, f"{path} has {len(lines)} lines; limit is 350"


def test_observed_resource_close_coordinator_stays_within_method_limit():
    tree = ast.parse(
        (ROOT / "src/agentmap/services/llm/observed_clients.py").read_text()
    )
    close_all = _find_function(tree, "_close_all")
    size = close_all.end_lineno - close_all.lineno + 1
    assert size <= 50, f"ObservedResources._close_all has {size} lines; limit is 50"


@pytest.mark.parametrize("path", B102_TEST_MODULES)
def test_every_b102_owned_test_function_stays_within_limit(path):
    tree = ast.parse((ROOT / path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            size = node.end_lineno - node.lineno + 1
            assert size <= 50, f"{path}:{node.name} has {size} lines; limit is 50"


def test_measurement_publication_precedes_pricing_and_uses_shared_finalizer():
    usage_tree = ast.parse(
        (ROOT / "src/agentmap/services/llm/usage_presence.py").read_text()
    )
    pure = {
        node.name: node for node in usage_tree.body if isinstance(node, ast.FunctionDef)
    }
    for name in ("validate_usage_presence", "capture_measurements"):
        identifiers = {
            node.id for node in ast.walk(pure[name]) if isinstance(node, ast.Name)
        }
        assert not identifiers & {"calculator", "rates", "model"}
        assert not any(
            isinstance(node, ast.Attribute) and node.attr in {"calculate", "get_rates"}
            for node in ast.walk(pure[name])
        )


def test_published_accumulator_is_read_after_downstream_failure__b102():
    accounting_tree = ast.parse(
        (ROOT / "src/agentmap/services/llm/governed_accounting.py").read_text()
    )
    reader = _find_function(accounting_tree, "read_evidence")
    publish = _assignment_lines_with_attribute(reader, "outcome")[0]
    collect = _call_lines_named(reader, "collect_evidence")[0]
    assert publish < collect
    lifecycle_tree = ast.parse(
        (ROOT / "src/agentmap/services/llm/attempt_lifecycle.py").read_text()
    )
    evaluator = _find_function(lifecycle_tree, "evaluate_attempt_response")
    assert _reads_attribute(evaluator, "accumulator", "outcome")
