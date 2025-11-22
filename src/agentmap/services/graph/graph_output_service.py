"""
GraphOutputService for AgentMap.

Consolidated service for generating human-readable graph outputs including Python code,
source files, and documentation. This service replaces the duplicate GraphExportService
and GraphSerializationService, focusing on export formats while leaving persistence
to GraphBundleService.

Architecture Note: This consolidation eliminates 90%+ code duplication between
GraphExportService and GraphSerializationService while maintaining clear separation
of concerns with GraphBundleService handling persistence.
"""

from pathlib import Path
from typing import Dict, Optional, Union

from agentmap.models.graph import Graph
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.graph.output import (
    DocumentationGenerator,
    PythonCodeGenerator,
    generate_debug_code,
    generate_source_code,
)
from agentmap.services.graph.output.python_generator import IMPORT_HEADER
from agentmap.services.logging_service import LoggingService

try:
    pass

    HAS_DILL = True
except ImportError:
    HAS_DILL = False

__all__ = ["GraphOutputService", "IMPORT_HEADER"]


class GraphOutputService:
    """
    Service for generating human-readable graph outputs.

    This service handles format-specific output operations for graphs,
    including Python code generation and source code export. It focuses
    specifically on human-readable formats while GraphBundleService handles
    persistence.

    Responsibilities:
    - Python code generation for graphs
    - Source code template generation
    - Debug information export
    - Documentation generation

    Does NOT handle:
    - CSV parsing (GraphBuilderService responsibility)
    """

    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        function_resolution_service: FunctionResolutionService,
        agent_registry_service: AgentRegistryService,
    ):
        """Initialize output service with dependency injection."""
        self.csv_path = app_config_service.get_csv_repository_path()
        self.custom_agents_path = app_config_service.get_custom_agents_path()
        self.functions_path = app_config_service.get_functions_path()
        self.logger = logging_service.get_class_logger(self)
        self.function_resolution = function_resolution_service
        self.agent_registry = agent_registry_service

        # Initialize generators
        self._python_generator = PythonCodeGenerator(
            function_resolution_service, agent_registry_service
        )

        self.logger.info("[GraphOutputService] Initialized")

    def export_graph(
        self,
        graph_name: str,
        export_format: str = "python",
        output_path: Optional[str] = None,
        state_schema: str = "dict",
    ) -> Path:
        """
        Export graph to specified human-readable format.

        Args:
            graph_name: Name of the graph to export
            export_format: Export format ('python', 'source', 'src', 'debug')
            output_path: Optional output path override
            state_schema: State schema to use for export

        Returns:
            Path to the exported file

        Raises:
            ValueError: If export format is not supported

        Note:
            This service focuses on human-readable formats only.
        """
        self.logger.info(
            f"[GraphOutputService] Exporting graph '{graph_name}' "
            f"to format '{export_format}'"
        )

        if export_format == "python":
            return self.export_as_python(graph_name, output_path, state_schema)
        elif export_format in ("source", "src"):
            return self.export_as_source(graph_name, output_path, state_schema)
        elif export_format == "debug":
            return self.export_as_debug(graph_name, output_path, state_schema)
        else:
            raise ValueError(
                f"Unsupported export format: {export_format}. "
                f"Supported formats: python, source, src, debug. "
                f"For persistence, use GraphBundleService."
            )

    def export_as_python(
        self,
        graph_name: str,
        output_path: Optional[str] = None,
        state_schema: str = "dict",
    ) -> Path:
        """
        Export graph as executable Python code.

        Args:
            graph_name: Name of the graph to export
            output_path: Optional output path override
            state_schema: State schema to use

        Returns:
            Path to the exported Python file
        """
        self.logger.debug(
            f"[GraphOutputService] Exporting '{graph_name}' as Python code"
        )

        graph_def = self._get_graph_definition(graph_name)
        lines = self._python_generator.generate(graph_name, graph_def, state_schema)
        path = self._get_output_path(graph_name, output_path, "py")

        with open(path, "w") as f:
            f.write("\n".join(lines))

        self.logger.info(f"[GraphOutputService] Exported {graph_name} to {path}")
        return path

    def export_as_source(
        self,
        graph_name: str,
        output_path: Optional[str] = None,
        state_schema: str = "dict",
    ) -> Path:
        """
        Export graph as basic source code template.

        Args:
            graph_name: Name of the graph to export
            output_path: Optional output path override
            state_schema: State schema to use

        Returns:
            Path to the exported source file
        """
        self.logger.debug(
            f"[GraphOutputService] Exporting '{graph_name}' as source code"
        )

        graph_def = self._get_graph_definition(graph_name)
        lines = generate_source_code(graph_def, state_schema, self.agent_registry)

        path = self._get_output_path(graph_name, output_path, "src")
        with open(path, "w") as f:
            f.write("\n".join(lines))

        self.logger.info(f"[GraphOutputService] Exported {graph_name} source to {path}")
        return path

    def export_as_debug(
        self,
        graph_name: str,
        output_path: Optional[str] = None,
        state_schema: str = "dict",
    ) -> Path:
        """
        Export graph with debug information and metadata.

        Args:
            graph_name: Name of the graph to export
            output_path: Optional output path override
            state_schema: State schema to use

        Returns:
            Path to the exported debug file
        """
        self.logger.debug(
            f"[GraphOutputService] Exporting '{graph_name}' with debug information"
        )

        graph_def = self._get_graph_definition(graph_name)
        lines = generate_debug_code(
            graph_name, graph_def, state_schema, self._python_generator
        )

        path = self._get_output_path(graph_name, output_path, "debug")
        with open(path, "w") as f:
            f.write("\n".join(lines))

        self.logger.info(
            f"[GraphOutputService] Exported {graph_name} debug info to {path}"
        )
        return path

    def export_as_documentation(
        self,
        graph_name: str,
        output_path: Optional[str] = None,
        export_format: str = "markdown",
    ) -> Path:
        """
        Export graph as documentation.

        Args:
            graph_name: Name of the graph to export
            output_path: Optional output path override
            export_format: Documentation format ('markdown', 'html')

        Returns:
            Path to the exported documentation file
        """
        self.logger.debug(
            f"[GraphOutputService] Generating documentation for '{graph_name}'"
        )

        # Validate format first before expensive operations
        if export_format == "markdown":
            ext = "md"
        elif export_format == "html":
            ext = "html"
        else:
            raise ValueError(f"Unsupported documentation format: {export_format}")

        graph_def = self._get_graph_definition(graph_name)

        if export_format == "markdown":
            lines = DocumentationGenerator.generate_markdown(graph_name, graph_def)
        else:  # html
            lines = DocumentationGenerator.generate_html(graph_name, graph_def)

        path = self._get_output_path(graph_name, output_path, ext)
        with open(path, "w") as f:
            f.write("\n".join(lines))

        self.logger.info(
            f"[GraphOutputService] Generated {export_format} documentation "
            f"for {graph_name}: {path}"
        )
        return path

    def _get_graph_definition(self, graph_name: str):
        """
        Get graph definition using CompilationService.

        Args:
            graph_name: Name of the graph to retrieve

        Returns:
            Graph definition dict in old format (for compatibility)

        Raises:
            ValueError: If graph not found or compilation dependencies unavailable
        """
        try:
            # TODO: get the graph definition from the graph bundle

            return None

        except Exception as e:
            self.logger.error(
                f"[GraphOutputService] Failed to get graph definition "
                f"for export '{graph_name}': {e}"
            )
            raise

    def _get_output_path(
        self, graph_name: str, output_path: Optional[str], ext: str
    ) -> Path:
        """
        Determine output path for exported graph file.

        Args:
            graph_name: Name of the graph being exported
            output_path: Optional output path override
            ext: File extension for export format

        Returns:
            Path object for the output file
        """
        if not output_path:
            output_path = self.custom_agents_path / f"{graph_name}.{ext}"
        else:
            output_path = Path(output_path)
            if output_path.is_dir():
                output_path = output_path / f"{graph_name}.{ext}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    @staticmethod
    def _convert_graph_to_old_format(graph: Graph) -> Dict:
        """
        Convert Graph domain model to old format for compatibility.

        Args:
            graph: Graph domain model

        Returns:
            Dictionary in old GraphBuilder format
        """
        old_format = {}

        for node_name, node in graph.nodes.items():
            # Convert Node to old format using a simple object
            old_format[node_name] = type(
                "Node",
                (),
                {
                    "name": node.name,
                    "context": node.context,
                    "agent_type": node.agent_type,
                    "inputs": node.inputs,
                    "output": node.output,
                    "prompt": node.prompt,
                    "description": node.description,
                    "edges": node.edges,
                },
            )()

        return old_format

    def _resolve_state_schema_class(self, state_schema: str):
        """
        Resolve state schema class from string specification.

        Args:
            state_schema: State schema specification string

        Returns:
            Resolved class object
        """
        if state_schema == "dict":
            return dict
        elif state_schema.startswith("pydantic:"):
            model_name = state_schema.split(":", 1)[1]
            try:
                module = __import__(
                    f"agentmap.schemas.{model_name.lower()}", fromlist=[model_name]
                )
                return getattr(module, model_name)
            except (ImportError, AttributeError) as e:
                self.logger.warning(
                    f"[GraphOutputService] Failed to import '{model_name}', "
                    f"fallback to dict: {e}"
                )
                return dict
        else:
            try:
                module_path, class_name = state_schema.rsplit(".", 1)
                module = __import__(module_path, fromlist=[class_name])
                return getattr(module, class_name)
            except Exception as e:
                self.logger.warning(
                    f"[GraphOutputService] Failed to import custom schema "
                    f"'{state_schema}': {e}"
                )
                return dict

    def get_service_info(self) -> Dict[str, Union[str, bool]]:
        """
        Get information about the output service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphOutputService",
            "function_resolution_available": self.function_resolution is not None,
            "csv_path": str(self.csv_path),
            "functions_path": str(self.functions_path),
            "supported_formats": ["python", "source", "src", "debug", "documentation"],
            "note": "For graph persistence, use GraphBundleService",
            "dill_available": HAS_DILL,
        }
