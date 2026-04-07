"""
GraphToolLoadingService for AgentMap.

Service responsible for loading and resolving tools from modules for agent nodes.
Owns the full tool-loading pipeline: path security validation, file/directory
scanning, @tool function discovery, name-collision detection, and per-node
filtering by ``available_tools``.
"""

import importlib.util
import inspect
from pathlib import Path
from typing import Any, List, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.file_path_service import FilePathService
from agentmap.services.logging_service import LoggingService


class GraphToolLoadingService:
    """
    Service for loading tools from modules for agent nodes.

    This service handles the tool resolution phase where ``tool_source`` fields
    in node definitions are resolved to actual tool instances. It supports both
    single ``.py`` files and directories of ``.py`` files (top-level only,
    non-recursive). Files in a directory that contain no ``@tool`` functions are
    silently skipped so helper modules can live alongside tool modules.

    Path security: when a ``FilePathService`` is injected, every ``tool_source``
    is validated before loading. Paths inside dangerous system locations
    (``/etc``, ``/bin``, ``/usr/lib``, ``/proc``, Windows system folders, etc.)
    and paths containing traversal segments (``..``) are rejected.
    """

    def __init__(
        self,
        logging_service: LoggingService,
        file_path_service: Optional[FilePathService] = None,
    ):
        """
        Initialize with logging and (optional) path security services.

        Args:
            logging_service: Service for logging
            file_path_service: Optional path validation service. When provided,
                every tool_source is checked against dangerous system paths and
                traversal attempts before any module is imported. When None
                (e.g. in unit tests), no path security checks are performed.
        """
        self.logger = logging_service.get_class_logger(self)
        self._file_path_service = file_path_service
        self.logger.debug(
            "[GraphToolLoadingService] Initialized "
            f"(path_security={'enabled' if file_path_service else 'disabled'})"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_tools_for_nodes(self, bundle: GraphBundle) -> None:
        """
        Load tools from modules for all nodes that specify tool sources.

        This method processes each node's ``tool_source`` field and loads the
        specified tools into ``bundle.tools[node_name]`` for later binding
        during agent instantiation.

        Args:
            bundle: GraphBundle with nodes that may require tools

        Raises:
            ImportError: If a tool module cannot be imported
            ValueError: If specified tools are not found in the module, or if
                two distinct tools share a name across files in a directory
        """
        if not bundle.nodes:
            return

        loaded_count = 0
        for node_name, node in bundle.nodes.items():
            # Skip nodes without tool_source or with "toolnode" (special case)
            tool_source = getattr(node, "tool_source", None)
            if not tool_source or tool_source.lower() == "toolnode":
                continue

            try:
                tools = self._load_tools_for_single_node(node_name, node, tool_source)

                # Store in bundle
                bundle.tools[node_name] = tools
                loaded_count += 1

            except (ImportError, ValueError):
                # Re-raise these specific exceptions as they have good context
                raise
            except Exception as e:
                error_msg = (
                    f"Unexpected error loading tools for node {node_name}: {str(e)}\n"
                    f"Tool source: {tool_source}"
                )
                self.logger.error(f"[GraphToolLoadingService] {error_msg}")
                raise RuntimeError(error_msg) from e

        if loaded_count > 0:
            self.logger.info(
                f"[GraphToolLoadingService] Tool loading complete: "
                f"{loaded_count} nodes configured with tools"
            )

    def load_tools_from_module(self, module_path: str) -> List[Any]:
        """
        Load all ``@tool`` decorated functions from a Python module or directory.

        If ``module_path`` points to a ``.py`` file, loads tools from that single
        file. If it points to a directory, loads tools from every ``.py`` file
        in the top level of that directory (non-recursive).

        Args:
            module_path: Path to a Python ``.py`` file or a directory of ``.py``
                files. Can be relative or absolute.

        Returns:
            List of LangChain Tool objects discovered.

        Raises:
            ImportError: If the path does not exist, fails path-security
                validation, or any module cannot be imported.
            ValueError: If no tools are found, or if two distinct tools share
                the same name across different files in a directory.
        """
        # Path security validation. Done first so dangerous paths are rejected
        # before any I/O or module imports.
        self._validate_tool_source_security(module_path)

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
        if path.is_dir():
            return self._load_tools_from_directory(path, module_path)

        # Single file
        tools = self._load_tools_from_file(module_path)
        if not tools:
            raise self._no_tools_found_error(
                module_path, "Verify the module contains callable tool functions"
            )
        return tools

    # ------------------------------------------------------------------
    # Per-node orchestration
    # ------------------------------------------------------------------

    def _load_tools_for_single_node(
        self, node_name: str, node: Any, tool_source: str
    ) -> list:
        """
        Load tools for a single node from its tool source.

        Args:
            node_name: Name of the node
            node: Node object with tool configuration
            tool_source: Module path to load tools from

        Returns:
            List of loaded tool instances

        Raises:
            ImportError: If tool module cannot be imported or fails security
                validation
            ValueError: If specified tools not found in module
        """
        try:
            # Load all tools from the module
            self.logger.debug(
                f"[GraphToolLoadingService] Loading tools from: {tool_source}"
            )
            all_tools = self.load_tools_from_module(tool_source)

            # Filter to available_tools if specified
            available_tools = getattr(node, "available_tools", None)
            if available_tools:
                tools = self._filter_tools_by_availability(
                    all_tools, available_tools, tool_source, node_name
                )
            else:
                # Use all tools from module
                tools = all_tools

            tool_names = [t.name for t in tools]
            self.logger.info(
                f"[GraphToolLoadingService] Loaded {len(tools)} tools for "
                f"{node_name}: {', '.join(tool_names)}"
            )

            return tools

        except ImportError as e:
            error_msg = (
                f"Failed to load tools for node {node_name}: {str(e)}\n"
                f"Tool source: {tool_source}\n"
                f"Suggestions:\n"
                f"  - Check ToolSource column in CSV\n"
                f"  - Verify the file path is correct\n"
                f"  - Ensure the module exists and is accessible"
            )
            self.logger.error(f"[GraphToolLoadingService] {error_msg}")
            raise ImportError(error_msg) from e

    def _filter_tools_by_availability(
        self, all_tools: list, available_tools: list, tool_source: str, node_name: str
    ) -> list:
        """
        Filter tools by the available_tools specification.

        Args:
            all_tools: All tools loaded from module
            available_tools: List of tool names to include
            tool_source: Source module path for error messages
            node_name: Node name for error messages

        Returns:
            Filtered list of tools

        Raises:
            ValueError: If requested tools not found in module
        """
        # Filter tools by name
        tools = [t for t in all_tools if t.name in available_tools]

        # Validate all requested tools were found
        found_names = {t.name for t in tools}
        requested_names = set(available_tools)
        missing = requested_names - found_names

        if missing:
            available_names = [t.name for t in all_tools]
            error_msg = (
                f"Tools not found in {tool_source}: {sorted(missing)}\n"
                f"Available tools: {sorted(available_names)}\n"
                f"Suggestions:\n"
                f"  - Check spelling in AvailableTools column\n"
                f"  - Verify @tool decorated functions exist in module"
            )
            self.logger.error(
                f"[GraphToolLoadingService] Tool validation failed for "
                f"{node_name}: {error_msg}"
            )
            raise ValueError(error_msg)

        return tools

    # ------------------------------------------------------------------
    # Path security
    # ------------------------------------------------------------------

    def _validate_tool_source_security(self, module_path: str) -> None:
        """
        Reject tool sources that point to dangerous system locations or contain
        path traversal segments.

        No-op if no FilePathService was injected (e.g. in unit tests).

        Raises:
            ImportError: If validation fails. We re-raise as ImportError so the
                caller's existing error-handling for "module cannot be loaded"
                still applies.
        """
        if self._file_path_service is None:
            return

        try:
            self._file_path_service.validate_safe_path(module_path)
        except Exception as e:
            self.logger.error(
                f"[GraphToolLoadingService] Tool source rejected by path "
                f"security: {module_path}: {e}"
            )
            raise ImportError(
                f"Tool source rejected by path security: {module_path}\n"
                f"Reason: {e}\n"
                f"Suggestions:\n"
                f"  • Tool sources must not point to system directories "
                f"(/etc, /bin, /usr/lib, etc.)\n"
                f"  • Tool sources must not contain path traversal segments "
                f"('..')"
            ) from e

    # ------------------------------------------------------------------
    # Filesystem scanning
    # ------------------------------------------------------------------

    def _load_tools_from_directory(self, path: Path, original_path: str) -> List[Any]:
        """
        Load and aggregate tools from every top-level ``.py`` file in a
        directory. Non-recursive.

        Tool-name collisions across files raise ``ValueError`` listing both
        source files. Silent first-load-wins would let users get a tool other
        than the one they intended, and LangGraph's ToolNode rejects duplicate
        names anyway. If you genuinely need the same tool exposed from multiple
        files, import it from a single source.

        Args:
            path: Resolved Path to the directory
            original_path: Original user-supplied string, for error messages

        Returns:
            Aggregated list of unique tools

        Raises:
            ValueError: On name collisions, or if no tools are found.
            ImportError: If any .py file in the directory fails to import.
        """
        tools_by_name: dict = {}
        sources_by_name: dict = {}
        py_files = sorted(p for p in path.glob("*.py") if p.is_file())

        for py_file in py_files:
            file_str = str(py_file)
            for tool in self._load_tools_from_file(file_str):
                if tool.name in tools_by_name:
                    raise ValueError(
                        f"Tool name collision in directory {original_path}: "
                        f"'{tool.name}' is defined by two different files\n"
                        f"  • {sources_by_name[tool.name]}\n"
                        f"  • {file_str}\n"
                        f"Suggestions:\n"
                        f"  • Rename one of the conflicting tools\n"
                        f"  • Move one tool to a separate directory\n"
                        f"  • If both files re-export the same tool, import it "
                        f"from a single source"
                    )
                tools_by_name[tool.name] = tool
                sources_by_name[tool.name] = file_str

        if not tools_by_name:
            raise self._no_tools_found_error(
                original_path,
                "Verify the directory contains .py files with tool functions",
            )
        return list(tools_by_name.values())

    def _load_tools_from_file(self, module_path: str) -> List[Any]:
        """
        Import a .py file and return all ``@tool`` decorated functions found.

        Returns an empty list if the file imports cleanly but defines no tools;
        callers decide whether an empty result is an error. Raises
        ``ImportError`` if the file cannot be imported at all.
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

        # Discover @tool decorated functions. LangChain tools have `name` and
        # `description` attributes. In langchain_core, @tool creates
        # StructuredTool objects which have invoke/run methods but callable()
        # returns False, so we check for the tool signature instead.
        tools = []
        for _name, obj in inspect.getmembers(module):
            if (
                hasattr(obj, "name")
                and hasattr(obj, "description")
                and (hasattr(obj, "invoke") or hasattr(obj, "run"))
            ):
                tools.append(obj)

        return tools

    @staticmethod
    def _no_tools_found_error(source: str, hint: str) -> ValueError:
        """Build the standard 'no tools found' error with a source-specific hint."""
        return ValueError(
            f"No @tool decorated functions found in: {source}\n"
            f"Suggestions:\n"
            f"  • Ensure functions are decorated with @tool\n"
            f"  • Import the @tool decorator: from langchain_core.tools import tool\n"
            f"  • {hint}"
        )
