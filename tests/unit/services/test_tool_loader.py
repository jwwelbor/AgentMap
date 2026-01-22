"""
Unit tests for tool_loader utility function.

Tests the load_tools_from_module() function for discovering and loading
LangChain @tool decorated functions from Python modules.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class TestLoadToolsFromModule(unittest.TestCase):
    """Test load_tools_from_module utility function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_module_path = Path(self.test_dir) / "test_tools.py"

    def tearDown(self):
        """Clean up test files."""
        import shutil

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_test_module(self, content: str) -> Path:
        """Create a temporary Python module file."""
        self.test_module_path.write_text(content)
        return self.test_module_path

    def test_load_tools_with_valid_module(self):
        """Test loading tools from a module with @tool decorated functions."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange: Create module with tool functions
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

        # Act
        tools = load_tools_from_module(str(module_path))

        # Assert
        self.assertEqual(len(tools), 2)
        tool_names = [tool.name for tool in tools]
        self.assertIn("get_weather", tool_names)
        self.assertIn("get_forecast", tool_names)

        # Verify tools have required attributes
        for tool in tools:
            self.assertTrue(hasattr(tool, "name"))
            self.assertTrue(hasattr(tool, "description"))
            self.assertTrue(callable(tool))

    def test_load_tools_import_error_missing_file(self):
        """Test ImportError when module file does not exist."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange
        missing_path = "/nonexistent/path/to/tools.py"

        # Act & Assert
        with self.assertRaises(ImportError) as context:
            load_tools_from_module(missing_path)

        self.assertIn("Tool module not found", str(context.exception))
        self.assertIn(missing_path, str(context.exception))
        self.assertIn("Check the ToolSource column", str(context.exception))

    def test_load_tools_import_error_syntax_error(self):
        """Test ImportError when module has syntax errors."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange: Create module with syntax error
        module_content = """
from langchain_core.tools import tool

@tool
def bad_syntax(  # Missing closing parenthesis
    return "broken"
"""
        module_path = self._create_test_module(module_content)

        # Act & Assert
        with self.assertRaises(ImportError) as context:
            load_tools_from_module(str(module_path))

        self.assertIn("Failed to import tool module", str(context.exception))
        self.assertIn("syntax errors", str(context.exception))

    def test_load_tools_import_error_missing_dependency(self):
        """Test ImportError when module has missing dependencies."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange: Create module with missing import
        module_content = '''
from nonexistent_module import some_function
from langchain_core.tools import tool

@tool
def my_tool() -> str:
    """A tool."""
    return "result"
'''
        module_path = self._create_test_module(module_content)

        # Act & Assert
        with self.assertRaises(ImportError) as context:
            load_tools_from_module(str(module_path))

        self.assertIn("Failed to import tool module", str(context.exception))
        self.assertIn("dependencies are installed", str(context.exception))

    def test_load_tools_value_error_no_tools_found(self):
        """Test ValueError when module has no @tool decorated functions."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange: Create module without tools
        module_content = '''
def regular_function():
    """Not a tool."""
    return "not a tool"

class SomeClass:
    """Not a tool."""
    pass
'''
        module_path = self._create_test_module(module_content)

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            load_tools_from_module(str(module_path))

        self.assertIn("No @tool decorated functions found", str(context.exception))
        self.assertIn("decorated with @tool", str(context.exception))

    def test_load_tools_signature_validation(self):
        """Test that loaded tools have correct LangChain Tool signature."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange
        module_content = '''
from langchain_core.tools import tool

@tool
def calculate(a: int, b: int) -> int:
    """Calculate sum of two numbers."""
    return a + b
'''
        module_path = self._create_test_module(module_content)

        # Act
        tools = load_tools_from_module(str(module_path))

        # Assert - Verify tool signature attributes
        self.assertEqual(len(tools), 1)
        tool = tools[0]

        self.assertTrue(hasattr(tool, "name"))
        self.assertTrue(hasattr(tool, "description"))
        self.assertTrue(callable(tool))

        # Verify attributes have correct types
        self.assertIsInstance(tool.name, str)
        self.assertIsInstance(tool.description, str)
        self.assertEqual(tool.name, "calculate")
        self.assertIn("sum", tool.description.lower())

    def test_load_tools_performance(self):
        """Test that module loading completes in <10ms."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange
        module_content = '''
from langchain_core.tools import tool

@tool
def quick_tool() -> str:
    """Quick tool."""
    return "fast"
'''
        module_path = self._create_test_module(module_content)

        # Act - Measure loading time
        start_time = time.perf_counter()
        tools = load_tools_from_module(str(module_path))
        end_time = time.perf_counter()

        duration_ms = (end_time - start_time) * 1000

        # Assert
        self.assertLess(
            duration_ms, 10, f"Loading took {duration_ms:.2f}ms, expected <10ms"
        )
        self.assertEqual(len(tools), 1)

    def test_load_tools_multiple_tools_same_module(self):
        """Test loading multiple tools from the same module."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange
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

        # Act
        tools = load_tools_from_module(str(module_path))

        # Assert
        self.assertEqual(len(tools), 3)
        tool_names = sorted([tool.name for tool in tools])
        self.assertEqual(tool_names, ["tool_one", "tool_three", "tool_two"])

    def test_load_tools_with_complex_signatures(self):
        """Test loading tools with complex function signatures."""
        from agentmap.services.tool_loader import load_tools_from_module

        # Arrange
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

        # Act
        tools = load_tools_from_module(str(module_path))

        # Assert
        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool.name, "complex_tool")
        self.assertIn("complex signature", tool.description.lower())


if __name__ == "__main__":
    unittest.main()
