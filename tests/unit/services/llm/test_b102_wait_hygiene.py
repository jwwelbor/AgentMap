"""Keep broken B102 synchronization from hanging the pytest process."""

import ast
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEST_DIRS = (ROOT / "tests/unit", ROOT / "tests/fresh_suite/unit")


def _b102_modules():
    return sorted(
        path
        for test_dir in TEST_DIRS
        for path in test_dir.rglob("test_*.py")
        if path.name.startswith("test_b102_")
        or "__b102" in path.read_text()
        or path.name == "test_cost_calculator.py"
    )


def _assignment_names(target, value):
    if isinstance(target, ast.Name):
        return {target.id: value}
    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(
        value, (ast.Tuple, ast.List)
    ):
        return {
            name.id: item
            for name, item in zip(target.elts, value.elts)
            if isinstance(name, ast.Name)
        }
    return {}


def _module_numeric_names(tree):
    names = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            names.update(_assignment_names(statement.targets[0], statement.value))
        elif isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            names[statement.target.id] = statement.value
    return names


def _parameter_defaults(scope):
    positional = list(scope.args.posonlyargs) + list(scope.args.args)
    defaults = [None] * (len(positional) - len(scope.args.defaults))
    defaults.extend(scope.args.defaults)
    return dict(zip((arg.arg for arg in positional), defaults)) | dict(
        zip((arg.arg for arg in scope.args.kwonlyargs), scope.args.kw_defaults)
    )


def _finite_number(expression, names, scopes, visited=None):
    if isinstance(expression, ast.Constant):
        return isinstance(expression.value, (int, float)) and math.isfinite(
            expression.value
        )
    if not isinstance(expression, ast.Name):
        return False
    visited = visited or set()
    if expression.id in visited:
        return False
    visited.add(expression.id)
    for scope in scopes:
        defaults = _parameter_defaults(scope)
        if expression.id in defaults:
            return _finite_number(defaults[expression.id], names, scopes, visited)
    if expression.id in names:
        return _finite_number(names[expression.id], names, scopes, visited)
    return False


def _has_finite_timeout(call, positional_index, names, scopes):
    timeout = next(
        (keyword.value for keyword in call.keywords if keyword.arg == "timeout"),
        None,
    )
    if timeout is None and len(call.args) > positional_index:
        timeout = call.args[positional_index]
    return timeout is not None and _finite_number(timeout, names, scopes)


def _attribute_call(node, name):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    )


def _timeout_wrappers(node):
    if _attribute_call(node, "wait_for"):
        return [(node, 1)]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [
            (item.context_expr, 0)
            for item in node.items
            if _attribute_call(item.context_expr, "timeout")
        ]
    return []


def _wait_timeout_context(call, parents):
    node = call
    scopes, wrappers = [], []
    while node in parents:
        node = parents[node]
        wrappers.extend(_timeout_wrappers(node))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append(node)
    return (scopes[0] if scopes else None), scopes, wrappers


def _wait_is_bounded(call, parents, names):
    positional_index = int(
        isinstance(call.func.value, ast.Name) and call.func.value.id == "asyncio"
    )
    owner, scopes, wrappers = _wait_timeout_context(call, parents)
    bounded = _has_finite_timeout(call, positional_index, names, scopes) or any(
        _has_finite_timeout(wrapper, index, names, scopes)
        for wrapper, index in wrappers
    )
    return owner, bounded


def _diagnostic(path, call, owner):
    try:
        relative_path = path.relative_to(ROOT)
    except ValueError:
        relative_path = path.name
    owner_name = owner.name if owner is not None else "<module>"
    return f"{relative_path}:{call.lineno}:{owner_name}"


def _unbounded_waits(path):
    tree = ast.parse(path.read_text())
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    names = _module_numeric_names(tree)
    failures = []
    for call in ast.walk(tree):
        if not _attribute_call(call, "wait"):
            continue
        owner, bounded = _wait_is_bounded(call, parents, names)
        if not bounded:
            failures.append(_diagnostic(path, call, owner))
    return failures


def _scope_nodes(scope):
    stack = list(scope.body)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _failure_safe_finally(call, owner, parents):
    child = call
    while child in parents:
        parent = parents[child]
        if parent is owner:
            break
        if isinstance(parent, ast.Try) and child in parent.body and parent.finalbody:
            return True
        child = parent
    return False


def _wait_belongs_to_created_task(call, owner, parents):
    child = call
    while child in parents:
        parent = parents[child]
        if parent is owner:
            return False
        if (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Attribute)
            and parent.func.attr
            in {"create_task", "ensure_future", "create_task_or_close"}
        ):
            return True
        child = parent
    return False


def _wait_is_in_cleanup_finally(call, owner, parents):
    child = call
    while child in parents:
        parent = parents[child]
        if parent is owner:
            return False
        if isinstance(parent, ast.Try) and child in parent.finalbody:
            return True
        child = parent
    return False


def _is_wait_operation(call, parents):
    called_wait = (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "wait"
    )
    threaded_wait = (
        isinstance(call, ast.Attribute)
        and call.attr == "wait"
        and isinstance(parents.get(call), ast.Call)
        and isinstance(parents[call].func, ast.Attribute)
        and parents[call].func.attr in {"to_thread", "run_in_executor"}
    )
    return called_wait or threaded_wait


def _creates_task(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"create_task", "ensure_future", "create_task_or_close"}
    )


def _readiness_test_nodes(tree):
    for owner in ast.walk(tree):
        if not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not owner.name.startswith("test_"):
            continue
        nodes = list(_scope_nodes(owner))
        if any(_creates_task(node) for node in nodes):
            yield owner, nodes


def _unsafe_readiness_wait(call, owner, parents):
    return (
        _is_wait_operation(call, parents)
        and not _wait_belongs_to_created_task(call, owner, parents)
        and not _wait_is_in_cleanup_finally(call, owner, parents)
        and not _failure_safe_finally(call, owner, parents)
    )


def _readiness_waits_without_cleanup(path):
    tree = ast.parse(path.read_text())
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    return [
        _diagnostic(path, call, owner)
        for owner, nodes in _readiness_test_nodes(tree)
        for call in nodes
        if _unsafe_readiness_wait(call, owner, parents)
    ]


def test_b102_all_event_waits_are_bounded__b102():
    retiring_scope_test = (
        ROOT / "tests/unit/deployment/http/api/test_b102_retiring_scope_cleanup.py"
    )
    assert retiring_scope_test in _b102_modules()
    unbounded = [
        failure for path in _b102_modules() for failure in _unbounded_waits(path)
    ]
    assert not unbounded, "Unbounded B102 waits:\n" + "\n".join(unbounded)


def test_b102_readiness_waits_have_failure_safe_cleanup__b102():
    unsafe = [
        failure
        for path in _b102_modules()
        for failure in _readiness_waits_without_cleanup(path)
    ]
    assert not unsafe, "Readiness waits without failure-safe cleanup:\n" + "\n".join(
        unsafe
    )


def test_b102_wait_scanner_checks_timeout_semantics__b102(tmp_path):
    cases = {
        "event.wait()": True,
        "event.wait(timeout=None)": True,
        "event.wait(timeout=5)": False,
        "event.wait(5)": False,
        "asyncio.wait(tasks)": True,
        "asyncio.wait(tasks, timeout=None)": True,
        "asyncio.wait(tasks, timeout=5)": False,
        "asyncio.wait_for(event.wait(), timeout=None)": True,
        "asyncio.wait_for(event.wait(), timeout=5)": False,
        "event.wait(timeout=float('inf'))": True,
        "event.wait(timeout='5')": True,
    }
    for index, (expression, should_fail) in enumerate(cases.items()):
        path = tmp_path / f"wait_case_{index}.py"
        path.write_text(f"async def probe():\n    {expression}\n")

        assert bool(_unbounded_waits(path)) is should_fail, expression

    declarations = {
        "LIMIT = 5": False,
        "LIMIT: float = 5": False,
        "LIMIT, OTHER = 5, 6": False,
        "LIMIT = OTHER\nOTHER = 5": False,
        "LIMIT = OTHER\nOTHER = LIMIT": True,
    }
    for declaration, should_fail in declarations.items():
        path = tmp_path / "wait_named_timeout.py"
        path.write_text(
            f"{declaration}\nasync def probe():\n    event.wait(timeout=LIMIT)\n"
        )
        assert bool(_unbounded_waits(path)) is should_fail, declaration


def test_b102_wait_scanner_preserves_default_shadowing_and_timeout_context(tmp_path):
    cases = {
        "async def probe(timeout=5):\n    event.wait(timeout=timeout)": False,
        "async def probe(*, timeout=5):\n    event.wait(timeout=timeout)": False,
        "LIMIT = 5\nasync def probe(LIMIT):\n    event.wait(timeout=LIMIT)": True,
        "async def probe():\n    async with asyncio.timeout(5):\n        event.wait()": False,
        "async def probe():\n    async with asyncio.timeout(None):\n        event.wait()": True,
    }
    for source, should_fail in cases.items():
        path = tmp_path / "scoped_wait.py"
        path.write_text(source)
        assert bool(_unbounded_waits(path)) is should_fail, source
