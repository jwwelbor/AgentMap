"""
Tool loading utility for discovering @tool decorated functions from Python modules.

This is a simple utility function (not a service) that uses Python's importlib
and inspect modules to discover LangChain @tool decorated functions.
"""

import importlib.util
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


def load_tools_from_module(module_path: str) -> List[Any]:
    """
    Load all @tool decorated functions from a Python module.

    This utility function imports a Python module and discovers all callable
    objects that have the LangChain Tool signature (name and description attributes).

    Args:
        module_path: Path to the Python module (.py file). Can be relative or absolute.

    Returns:
        List of LangChain Tool objects discovered in the module.

    Raises:
        ImportError: If the module cannot be imported or does not exist.
        ValueError: If no tools are found in the module.

    Performance:
        Module loading typically completes in <10ms.

    Example:
        >>> tools = load_tools_from_module("weather_tools.py")
        >>> print([tool.name for tool in tools])
        ['get_weather', 'get_forecast', 'get_location']
    """
    # Validate module path exists
    module_file = Path(module_path)
    if not module_file.exists():
        raise ImportError(
            f"Tool module not found: {module_path}\n"
            f"Suggestions:\n"
            f"  • Check the ToolSource column in your CSV\n"
            f"  • Verify the file exists in the specified location\n"
            f"  • Use absolute or relative path from workflow directory"
        )

    # Import module dynamically
    try:
        spec = importlib.util.spec_from_file_location("tools", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module spec from: {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(
            f"Failed to import tool module: {module_path}\n"
            f"Error: {str(e)}\n"
            f"Suggestions:\n"
            f"  • Check for syntax errors in the module\n"
            f"  • Verify all dependencies are installed\n"
            f"  • Ensure the module contains valid Python code"
        ) from e

    # Discover @tool decorated functions
    tools = []
    for name, obj in inspect.getmembers(module):
        # LangChain tools have 'name' and 'description' attributes
        # Check for callable objects with tool signature (name and description)
        if callable(obj) and hasattr(obj, "name") and hasattr(obj, "description"):
            # Tool objects from @tool decorator
            tools.append(obj)

    # Fail fast if no tools found
    if not tools:
        raise ValueError(
            f"No @tool decorated functions found in: {module_path}\n"
            f"Suggestions:\n"
            f"  • Ensure functions are decorated with @tool\n"
            f"  • Import the @tool decorator: from langchain_core.tools import tool\n"
            f"  • Verify the module contains callable tool functions"
        )

    return tools
