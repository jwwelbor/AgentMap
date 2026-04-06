"""
Unit tests for GraphToolLoadingService.

Covers the merged tool-loading pipeline:
- Single-file loading via load_tools_from_module()
- Directory aggregation (top-level only, non-recursive)
- Silent skip of helper-only files
- Re-export deduplication vs distinct-name collision detection
- Path security via injected FilePathService
"""

import logging
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from agentmap.services.file_path_service import FilePathService
from agentmap.services.graph.graph_tool_loading_service import (
    GraphToolLoadingService,
)


class _StubLoggingService:
    """Minimal logging-service stub for unit tests."""

    def get_class_logger(self, _instance):
        logger = logging.getLogger(f"test.{id(_instance)}")
        logger.addHandler(logging.NullHandler())
        return logger


def _make_service(file_path_service=None) -> GraphToolLoadingService:
    """Construct a GraphToolLoadingService with stub logging."""
    return GraphToolLoadingService(
        _StubLoggingService(), file_path_service=file_path_service
    )


def _make_real_file_path_service() -> FilePathService:
    """
    Build a real FilePathService for path-security tests.

    FilePathService stores app_config_service but only consults it from
    get_bundle_path(), which we never call here. Passing None is safe.
    """
    return FilePathService(
        app_config_service=None, logging_service=_StubLoggingService()
    )


# ----------------------------------------------------------------------
# Single-file mode
# ----------------------------------------------------------------------


class TestLoadToolsFromModuleFile(unittest.TestCase):
    """load_tools_from_module() with single .py file inputs."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_module_path = Path(self.test_dir) / "test_tools.py"
        self.service = _make_service()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_test_module(self, content: str) -> Path:
        self.test_module_path.write_text(content)
        return self.test_module_path

    def test_load_tools_with_valid_module(self):
        module_content = '''
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Weather for {location}"

@tool
def get_forecast(location: str, days: int) -> str:
    """Get weather forecast."""
    return f"Forecast for {location} for {days} days"
'''
        module_path = self._create_test_module(module_content)
        tools = self.service.load_tools_from_module(str(module_path))

        self.assertEqual(len(tools), 2)
        tool_names = [t.name for t in tools]
        self.assertIn("get_weather", tool_names)
        self.assertIn("get_forecast", tool_names)

        for t in tools:
            self.assertTrue(hasattr(t, "name"))
            self.assertTrue(hasattr(t, "description"))
            self.assertTrue(hasattr(t, "invoke") or hasattr(t, "run"))

    def test_load_tools_import_error_missing_file(self):
        missing_path = "/nonexistent/path/to/tools.py"
        with self.assertRaises(ImportError) as context:
            self.service.load_tools_from_module(missing_path)

        self.assertIn("Tool module not found", str(context.exception))
        self.assertIn(missing_path, str(context.exception))
        self.assertIn("Check the ToolSource column", str(context.exception))

    def test_load_tools_import_error_syntax_error(self):
        module_content = """
from langchain_core.tools import tool

@tool
def bad_syntax(  # Missing closing parenthesis
    return "broken"
"""
        module_path = self._create_test_module(module_content)
        with self.assertRaises(ImportError) as context:
            self.service.load_tools_from_module(str(module_path))

        self.assertIn("Failed to import tool module", str(context.exception))
        self.assertIn("syntax errors", str(context.exception))

    def test_load_tools_import_error_missing_dependency(self):
        module_content = '''
from nonexistent_module import some_function
from langchain_core.tools import tool

@tool
def my_tool() -> str:
    """A tool."""
    return "result"
'''
        module_path = self._create_test_module(module_content)
        with self.assertRaises(ImportError) as context:
            self.service.load_tools_from_module(str(module_path))

        self.assertIn("Failed to import tool module", str(context.exception))
        self.assertIn("dependencies are installed", str(context.exception))

    def test_load_tools_value_error_no_tools_found(self):
        module_content = '''
def regular_function():
    """Not a tool."""
    return "not a tool"

class SomeClass:
    """Not a tool."""
    pass
'''
        module_path = self._create_test_module(module_content)
        with self.assertRaises(ValueError) as context:
            self.service.load_tools_from_module(str(module_path))

        self.assertIn("No @tool decorated functions found", str(context.exception))
        self.assertIn("decorated with @tool", str(context.exception))

    def test_load_tools_signature_validation(self):
        module_content = '''
from langchain_core.tools import tool

@tool
def calculate(a: int, b: int) -> int:
    """Calculate sum of two numbers."""
    return a + b
'''
        module_path = self._create_test_module(module_content)
        tools = self.service.load_tools_from_module(str(module_path))

        self.assertEqual(len(tools), 1)
        t = tools[0]
        self.assertIsInstance(t.name, str)
        self.assertIsInstance(t.description, str)
        self.assertEqual(t.name, "calculate")
        self.assertIn("sum", t.description.lower())

    def test_load_tools_performance(self):
        module_content = '''
from langchain_core.tools import tool

@tool
def quick_tool() -> str:
    """Quick tool."""
    return "fast"
'''
        module_path = self._create_test_module(module_content)

        start_time = time.perf_counter()
        tools = self.service.load_tools_from_module(str(module_path))
        end_time = time.perf_counter()

        duration_ms = (end_time - start_time) * 1000
        self.assertLess(
            duration_ms, 10, f"Loading took {duration_ms:.2f}ms, expected <10ms"
        )
        self.assertEqual(len(tools), 1)

    def test_load_tools_multiple_tools_same_module(self):
        module_content = '''
from langchain_core.tools import tool

@tool
def tool_one() -> str:
    """First tool."""
    return "one"

@tool
def tool_two() -> str:
    """Second tool."""
    return "two"

@tool
def tool_three() -> str:
    """Third tool."""
    return "three"

def not_a_tool():
    """Regular function."""
    pass
'''
        module_path = self._create_test_module(module_content)
        tools = self.service.load_tools_from_module(str(module_path))

        self.assertEqual(len(tools), 3)
        tool_names = sorted([t.name for t in tools])
        self.assertEqual(tool_names, ["tool_one", "tool_three", "tool_two"])

    def test_load_tools_with_complex_signatures(self):
        module_content = '''
from langchain_core.tools import tool
from typing import List, Dict, Optional

@tool
def complex_tool(
    query: str,
    filters: Optional[Dict[str, str]] = None,
    limit: int = 10
) -> List[str]:
    """Tool with complex signature."""
    return ["result"]
'''
        module_path = self._create_test_module(module_content)
        tools = self.service.load_tools_from_module(str(module_path))

        self.assertEqual(len(tools), 1)
        t = tools[0]
        self.assertEqual(t.name, "complex_tool")
        self.assertIn("complex signature", t.description.lower())


# ----------------------------------------------------------------------
# Directory mode
# ----------------------------------------------------------------------


class TestLoadToolsFromModuleDirectory(unittest.TestCase):
    """load_tools_from_module() with directory inputs."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.service = _make_service()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _write_module(self, filename: str, content: str) -> Path:
        path = Path(self.test_dir) / filename
        path.write_text(content)
        return path

    def test_directory_aggregates_all_py_files(self):
        self._write_module(
            "math_tools.py",
            '''
from langchain_core.tools import tool

@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
''',
        )
        self._write_module(
            "string_tools.py",
            '''
from langchain_core.tools import tool

@tool
def upper(text: str) -> str:
    """Uppercase a string."""
    return text.upper()
''',
        )

        tools = self.service.load_tools_from_module(self.test_dir)
        tool_names = sorted(t.name for t in tools)
        self.assertEqual(tool_names, ["add", "upper"])

    def test_directory_multiple_tools_per_file(self):
        self._write_module(
            "file_a.py",
            '''
from langchain_core.tools import tool

@tool
def alpha() -> str:
    """Alpha tool."""
    return "a"

@tool
def beta() -> str:
    """Beta tool."""
    return "b"
''',
        )
        self._write_module(
            "file_b.py",
            '''
from langchain_core.tools import tool

@tool
def gamma() -> str:
    """Gamma tool."""
    return "g"
''',
        )

        tools = self.service.load_tools_from_module(self.test_dir)
        self.assertEqual(len(tools), 3)
        self.assertEqual(sorted(t.name for t in tools), ["alpha", "beta", "gamma"])

    def test_directory_skips_files_without_tools(self):
        self._write_module(
            "real_tools.py",
            '''
from langchain_core.tools import tool

@tool
def my_tool() -> str:
    """A tool."""
    return "x"
''',
        )
        self._write_module(
            "helpers.py",
            '''
def helper():
    """Just a helper, not a tool."""
    return 1
''',
        )

        tools = self.service.load_tools_from_module(self.test_dir)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "my_tool")

    def test_directory_empty_directory_raises(self):
        with self.assertRaises(ValueError) as context:
            self.service.load_tools_from_module(self.test_dir)
        self.assertIn("No @tool decorated functions found", str(context.exception))

    def test_directory_no_tools_anywhere_raises(self):
        self._write_module(
            "a.py",
            """
def not_a_tool():
    return 1
""",
        )
        self._write_module(
            "b.py",
            """
class Helper:
    pass
""",
        )

        with self.assertRaises(ValueError) as context:
            self.service.load_tools_from_module(self.test_dir)
        self.assertIn("No @tool decorated functions found", str(context.exception))

    def test_directory_does_not_recurse_into_subdirs(self):
        self._write_module(
            "top.py",
            '''
from langchain_core.tools import tool

@tool
def top_tool() -> str:
    """Top level tool."""
    return "top"
''',
        )
        sub = Path(self.test_dir) / "nested"
        sub.mkdir()
        (sub / "nested_tools.py").write_text(
            '''
from langchain_core.tools import tool

@tool
def nested_tool() -> str:
    """Nested tool."""
    return "nested"
'''
        )

        tools = self.service.load_tools_from_module(self.test_dir)
        tool_names = [t.name for t in tools]
        self.assertEqual(tool_names, ["top_tool"])
        self.assertNotIn("nested_tool", tool_names)

    def test_directory_propagates_import_errors(self):
        self._write_module(
            "good.py",
            '''
from langchain_core.tools import tool

@tool
def good_tool() -> str:
    """Good tool."""
    return "ok"
''',
        )
        self._write_module(
            "broken.py",
            "def broken(  # syntax error\n",
        )

        with self.assertRaises(ImportError) as context:
            self.service.load_tools_from_module(self.test_dir)
        self.assertIn("broken.py", str(context.exception))


# ----------------------------------------------------------------------
# Collision detection (new behavior)
# ----------------------------------------------------------------------


class TestCollisionDetection(unittest.TestCase):
    """Distinct tools sharing a name across files must raise, not silently drop."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.service = _make_service()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _write(self, filename: str, content: str) -> Path:
        path = Path(self.test_dir) / filename
        path.write_text(content)
        return path

    def test_distinct_tools_same_name_raises_with_both_sources(self):
        """Two different @tool functions named `process` in two files → ValueError.

        Without this check, sorted-filename order would silently keep file_a's
        `process` and discard file_b's `process`, so users would invoke a tool
        other than the one they intended.
        """
        self._write(
            "file_a.py",
            '''
from langchain_core.tools import tool

@tool
def process(x: str) -> str:
    """Process from file_a."""
    return f"a:{x}"
''',
        )
        self._write(
            "file_b.py",
            '''
from langchain_core.tools import tool

@tool
def process(x: str) -> str:
    """Process from file_b — distinct implementation."""
    return f"b:{x}"
''',
        )

        with self.assertRaises(ValueError) as context:
            self.service.load_tools_from_module(self.test_dir)

        msg = str(context.exception)
        self.assertIn("Tool name collision", msg)
        self.assertIn("'process'", msg)
        self.assertIn("file_a.py", msg)
        self.assertIn("file_b.py", msg)


# ----------------------------------------------------------------------
# Path security
# ----------------------------------------------------------------------


class TestPathSecurity(unittest.TestCase):
    """When a FilePathService is injected, dangerous tool sources are rejected."""

    def setUp(self):
        self.service = _make_service(file_path_service=_make_real_file_path_service())

    def test_system_path_rejected(self):
        """A tool source pointing inside /etc must be rejected before any I/O."""
        with self.assertRaises(ImportError) as context:
            self.service.load_tools_from_module("/etc/passwd")

        msg = str(context.exception)
        self.assertIn("rejected by path security", msg)
        # The original input must appear in the error so the user can find it
        self.assertIn("/etc/passwd", msg)

    def test_path_traversal_rejected(self):
        """A tool source containing `..` segments must be rejected."""
        with self.assertRaises(ImportError) as context:
            self.service.load_tools_from_module("../../etc/passwd")

        msg = str(context.exception)
        self.assertIn("rejected by path security", msg)

    def test_safe_path_passes_validation(self):
        """The real examples/tools/ directory must pass path security."""
        # This must NOT raise
        tools = self.service.load_tools_from_module("examples/tools/")
        self.assertGreater(len(tools), 0)

    def test_no_file_path_service_means_no_security_checks(self):
        """When no FilePathService is injected, validation is skipped (e.g. unit tests)."""
        svc = _make_service()  # no file_path_service
        # /etc/passwd doesn't exist as a Python module so this still fails,
        # but with the loader's ImportError, NOT the security ImportError.
        with self.assertRaises(ImportError) as context:
            svc.load_tools_from_module("/etc/passwd")
        # If security ran, the message would say "rejected by path security".
        # Without security, the loader hits "Failed to import tool module" instead.
        self.assertNotIn("rejected by path security", str(context.exception))


if __name__ == "__main__":
    unittest.main()
