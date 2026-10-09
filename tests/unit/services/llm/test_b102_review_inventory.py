"""Keep B102 structural ownership and helper inventories complete."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
TEST_DIRS = (ROOT / "tests/unit", ROOT / "tests/fresh_suite/unit")
B102_TEST_MODULES = sorted(
    {
        path.relative_to(ROOT)
        for test_dir in TEST_DIRS
        for path in test_dir.rglob("test_*.py")
        if path.name.startswith("test_b102")
        or "__b102" in path.read_text()
        or path.name == "test_cost_calculator.py"
    }
)
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
BRANCHES = (
    ast.If,
    ast.IfExp,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.comprehension,
)


def _class_definitions(tree, names):
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in names
    }


def _imported_names(tree, module):
    return {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


def _public_names(tree):
    value = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    )
    return set(ast.literal_eval(value))


def _duplicate_definitions(directory, root, names):
    return [
        f"{path.relative_to(root)}:{node.lineno}:{node.name}"
        for path in directory.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ClassDef) and node.name in names
    ]


def _own_logic_nodes(function):
    """Assertions and nested callable bodies do not belong to this owner."""
    stack = list(function.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.Assert, *FUNCTIONS, ast.ClassDef)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _decision_points(function):
    decisions = 0
    for node in _own_logic_nodes(function):
        decisions += isinstance(node, BRANCHES)
        if isinstance(node, ast.BoolOp):
            decisions += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            decisions += len(node.ifs)
        elif isinstance(node, (ast.Try, ast.TryStar)):
            decisions += bool(node.orelse)
    return decisions


def _helper_inventory():
    return sorted(
        set(B102_TEST_MODULES)
        | {
            "tests/runtime_manager_test_support.py",
            "tests/llm_lifecycle_test_support.py",
        },
        key=str,
    )


def test_b102_structural_inventory_covers_b102_named_modules():
    named_modules = {
        path.relative_to(ROOT)
        for test_dir in TEST_DIRS
        for path in test_dir.rglob("test_b102*.py")
    }
    assert named_modules <= set(B102_TEST_MODULES)


@pytest.mark.parametrize("path", _helper_inventory())
def test_b102_helpers_have_at_most_nine_decision_points(path):
    source = (ROOT / path).read_text()
    assert len(source.splitlines()) <= 350, f"{path} exceeds 350 lines"
    tree = ast.parse(source)
    for function in ast.walk(tree):
        if isinstance(function, FUNCTIONS) and not function.name.startswith("test_"):
            size = function.end_lineno - function.lineno + 1
            assert size <= 50, f"{path}:{function.name} has {size} lines"
            decisions = _decision_points(function)
            assert (
                decisions <= 9
            ), f"{path}:{function.lineno}:{function.name} has {decisions} decision points"


def test_helper_decisions_exclude_assertions_and_nested_test_setup():
    tree = ast.parse("""
def test_setup():
    if setup:
        pass
    def helper():
        assert a and b and c
        def nested():
            if first:
                pass
            if second:
                pass
        if actual_branch:
            pass
""")
    helpers = {
        node.name: node for node in ast.walk(tree) if isinstance(node, FUNCTIONS)
    }
    assert _decision_points(helpers["helper"]) == 1
    assert _decision_points(helpers["nested"]) == 2


def test_helper_decisions_count_boolean_and_comprehension_branches():
    tree = ast.parse("""
def helper():
    return [x for x in values if x and accepted] if ready else []
""")
    assert _decision_points(tree.body[0]) == 4


def test_readiness_scanner_preserves_task_and_cleanup_ownership(tmp_path):
    from tests.unit.services.llm.test_b102_wait_hygiene import (
        _readiness_waits_without_cleanup,
    )

    cases = {
        "task = asyncio.create_task(work())\n    await event.wait()": True,
        "task = asyncio.create_task(work())\n    try:\n        await event.wait()\n    finally:\n        release()": False,
        "task = asyncio.create_task(event.wait())": False,
        "task = asyncio.create_task(work())\n    try:\n        work()\n    finally:\n        await event.wait()": False,
        "def nested():\n        asyncio.create_task(work())\n    await event.wait()": False,
        "task = asyncio.create_task(work())\n    await asyncio.to_thread(event.wait)": True,
    }
    for body, should_fail in cases.items():
        path = tmp_path / "readiness.py"
        path.write_text(f"async def test_probe():\n    {body}\n")
        assert bool(_readiness_waits_without_cleanup(path)) is should_fail, body


def _call_name(call):
    if not isinstance(call, ast.Call):
        return None
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _native_async_facades(tree):
    return {
        function.name
        for function in tree.body
        if isinstance(function, ast.AsyncFunctionDef)
        and any(
            isinstance(node, ast.Await)
            and _call_name(node.value) == "ensure_initialized_async"
            for node in _own_logic_nodes(function)
        )
    }


def _uses_native_async_facade(nodes, facades):
    return any(_call_name(node) in facades for node in nodes)


def _patches_sync_workflow_initializer(nodes):
    target = "agentmap.runtime.workflow_ops.ensure_initialized"
    return any(
        _call_name(node) == "patch"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == target
        for node in nodes
    )


def _async_facade_sync_initializer_patches(tree, facades):
    failures = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.AsyncFunctionDef):
            continue
        nodes = list(_own_logic_nodes(function))
        if not _uses_native_async_facade(nodes, facades):
            continue
        decorators = [
            node
            for decorator in function.decorator_list
            for node in ast.walk(decorator)
        ]
        if _patches_sync_workflow_initializer(nodes + decorators):
            failures.append(f"{function.lineno}:{function.name}")
    return failures


def test_async_facade_tests_patch_the_initializer_they_await():
    path = ROOT / "tests/integration/test_runtime_api.py"
    source = ast.parse((ROOT / "src/agentmap/runtime/workflow_ops.py").read_text())
    facades = _native_async_facades(source)
    assert facades == {
        "run_workflow_async",
        "resume_workflow_async",
        "run_workflow_stream_async",
    }
    failures = _async_facade_sync_initializer_patches(
        ast.parse(path.read_text()), facades
    )
    assert not failures, "Async facade tests patch synchronous startup: " + ", ".join(
        failures
    )


def test_async_initializer_guard_covers_decorators_and_context_patches():
    tree = ast.parse("""
@patch("agentmap.runtime.workflow_ops.ensure_initialized")
async def wrong_decorator():
    await run_workflow_async()
async def wrong_context():
    with patch("agentmap.runtime.workflow_ops.ensure_initialized"):
        await resume_workflow_async()
@patch("agentmap.runtime.workflow_ops.ensure_initialized_async")
async def correct_async():
    await resume_workflow_async()
@patch("agentmap.runtime.workflow_ops.ensure_initialized")
async def correct_thread_wrapper():
    await list_graphs_async()
@patch("agentmap.runtime.workflow_ops.ensure_initialized")
def correct_sync():
    run_workflow()
""")
    failures = _async_facade_sync_initializer_patches(
        tree,
        {"run_workflow_async", "resume_workflow_async", "run_workflow_stream_async"},
    )
    assert [failure.split(":")[1] for failure in failures] == [
        "wrong_decorator",
        "wrong_context",
    ]
