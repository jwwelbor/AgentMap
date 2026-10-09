"""Cleanup must preserve its operation's failure, not a caller's handled error."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
AMBIENT_LOOKUPS = {"exception", "exc_info"}


def _sys_module_names(tree):
    return {"sys"} | {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "sys"
    }


def _direct_lookup_names(tree):
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "sys"
        for alias in node.names
        if alias.name in AMBIENT_LOOKUPS
    }


def _reads_ambient_exception(function, modules, lookups):
    if isinstance(function, ast.Name):
        return function.id in lookups
    return (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id in modules
        and function.attr in AMBIENT_LOOKUPS
    )


def _ambient_exception_reads(source):
    tree = ast.parse(source)
    modules, lookups = _sys_module_names(tree), _direct_lookup_names(tree)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _reads_ambient_exception(node.func, modules, lookups)
    ]


@pytest.mark.parametrize(
    "path",
    [
        "src/agentmap/services/llm/ordinary_lifecycle.py",
        "src/agentmap/services/storage/gcp_storage_connector.py",
    ],
)
def test_cleanup_primary_is_captured_from_its_owned_operation(path):
    assert not _ambient_exception_reads((ROOT / path).read_text()), path


@pytest.mark.parametrize(
    "source",
    [
        "import sys\nprimary = sys.exception()",
        "import sys as runtime\nprimary = runtime.exc_info()[1]",
        "from sys import exception as current\nprimary = current()",
        "def build():\n    import sys as runtime\n    return runtime.exception()",
        "def build():\n    from sys import exception as current\n    return current()",
    ],
)
def test_primary_scope_guard_detects_ambient_lookup_aliases(source):
    assert _ambient_exception_reads(source)


def test_primary_scope_guard_allows_operation_capture_and_task_errors():
    source = "try:\n    build()\nexcept BaseException as primary:\n    raise\n"
    assert not _ambient_exception_reads(source)
    assert not _ambient_exception_reads("cleanup = task.exception()")
