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

    # Directory: load tools from every top-level .py file.
    # Tools are deduplicated by name because a module that re-exports a tool
    # from a sibling (e.g. `from .a import shared`) would otherwise surface
    # the same tool twice, and LangGraph's ToolNode rejects duplicate names.
    if path.is_dir():
        tools_by_name: dict = {}
        py_files = sorted(p for p in path.glob("*.py") if p.is_file())
        for py_file in py_files:
            for tool in _load_tools_from_file(str(py_file)):
                tools_by_name.setdefault(tool.name, tool)

        if not tools_by_name:
            raise _no_tools_found_error(
                module_path,
                "Verify the directory contains .py files with tool functions",
            )
        return list(tools_by_name.values())

    # Single file
    tools = _load_tools_from_file(module_path)
    if not tools:
        raise _no_tools_found_error(
            module_path, "Verify the module contains callable tool functions"
        )
    return tools


def _no_tools_found_error(source: str, hint: str) -> ValueError:
    """Build the standard 'no tools found' error with a source-specific hint."""
    return ValueError(
        f"No @tool decorated functions found in: {source}\n"
        f"Suggestions:\n"
        f"  • Ensure functions are decorated with @tool\n"
        f"  • Import the @tool decorator: from langchain_core.tools import tool\n"
        f"  • {hint}"
    )


def _load_tools_from_file(module_path: str) -> List[Any]:
    """Import a .py file and return all @tool decorated functions found.

    Returns an empty list if the file imports cleanly but defines no tools;
    callers decide whether an empty result is an error. Raises ImportError
    if the file cannot be imported at all.
    """
    # Import module dynamically. Using the file's stem as the synthetic
    # module name keeps each loaded file distinct in sys.modules-style
    # bookkeeping and avoids `__name__` collisions when many files are
    # loaded back-to-back from a directory.
    try:
        module_name = Path(module_path).stem or "tools"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
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

    return tools
