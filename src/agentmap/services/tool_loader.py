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
    pass


def load_tools_from_module(module_path: str) -> List[Any]:
    """
    Load all @tool decorated functions from a Python module or directory.

    If `module_path` points to a `.py` file, loads tools from that single file.
    If `module_path` points to a directory, loads tools from every `.py` file
    in the top level of that directory (non-recursive).

    Args:
        module_path: Path to a Python `.py` file or a directory of `.py` files.
            Can be relative or absolute.

    Returns:
        List of LangChain Tool objects discovered.

    Raises:
        ImportError: If the path does not exist, or any module cannot be imported.
        ValueError: If no tools are found.

    Performance:
        Single-module loading typically completes in <10ms.

    Example:
        >>> tools = load_tools_from_module("weather_tools.py")
        >>> print([tool.name for tool in tools])
        ['get_weather', 'get_forecast', 'get_location']

        >>> tools = load_tools_from_module("examples/tools/")
        >>> print([tool.name for tool in tools])
        ['add', 'multiply', 'upper', 'lower']
    """
    # Validate path exists
    path = Path(module_path)
    if not path.exists():
        raise ImportError(
            f"Tool module not found: {module_path}\n"
            f"Suggestions:\n"
            f"  • Check the ToolSource column in your CSV\n"
            f"  • Verify the file exists in the specified location\n"
            f"  • Use absolute or relative path from workflow directory"
        )

    # Directory: load tools from every top-level .py file
    if path.is_dir():
        tools: List[Any] = []
        py_files = sorted(p for p in path.glob("*.py") if p.is_file())
        for py_file in py_files:
            # Files without @tool functions are silently skipped in directory mode
            tools.extend(_load_tools_from_file(str(py_file), allow_empty=True))

        if not tools:
            raise ValueError(
                f"No @tool decorated functions found in: {module_path}\n"
                f"Suggestions:\n"
                f"  • Ensure functions are decorated with @tool\n"
                f"  • Import the @tool decorator: from langchain_core.tools import tool\n"
                f"  • Verify the directory contains .py files with tool functions"
            )
        return tools

    # Single file
    return _load_tools_from_file(module_path)


def _load_tools_from_file(module_path: str, allow_empty: bool = False) -> List[Any]:
    """Load @tool decorated functions from a single .py file.

    Args:
        module_path: Path to the .py file.
        allow_empty: If True, return [] when no tools are found instead of raising.
            Used when scanning a directory where some files may not contain tools.
    """
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
        # In langchain_core, @tool creates StructuredTool objects which have invoke/run methods
        # but callable() returns False, so we check for the tool signature instead
        if (
            hasattr(obj, "name")
            and hasattr(obj, "description")
            and (hasattr(obj, "invoke") or hasattr(obj, "run"))
        ):
            tools.append(obj)

    # Fail fast if no tools found (unless caller is scanning a directory)
    if not tools and not allow_empty:
        raise ValueError(
            f"No @tool decorated functions found in: {module_path}\n"
            f"Suggestions:\n"
            f"  • Ensure functions are decorated with @tool\n"
            f"  • Import the @tool decorator: from langchain_core.tools import tool\n"
            f"  • Verify the module contains callable tool functions"
        )

    return tools
