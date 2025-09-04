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
from typing import Dict, List, Optional, Union

from agentmap.models.graph import Graph
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.logging_service import LoggingService

try:
    pass

    HAS_DILL = True
except ImportError:
    HAS_DILL = False

IMPORT_HEADER = """from langgraph.graph import StateGraph
from agentmap.agents.builtins.openai_agent import OpenAIAgent
from agentmap.agents.builtins.anthropic_agent import AnthropicAgent
from agentmap.agents.builtins.google_agent import GoogleAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.branching_agent import BranchingAgent
from agentmap.agents.builtins.success_agent import SuccessAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
"""


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
            f"[GraphOutputService] Exporting graph '{graph_name}' to format '{export_format}'"
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
        lines = self._generate_python_code(graph_name, graph_def, state_schema)
        path = self._get_output_path(graph_name, output_path, "py")

        with open(path, "w") as f:
            f.write("\n".join(lines))

        self.logger.info(f"[GraphOutputService] ✅ Exported {graph_name} to {path}")
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
        lines = (
            [f"builder = StateGraph({state_schema})"]
            if state_schema != "dict"
            else ["builder = StateGraph(dict)"]
        )

        for node in graph_def.values():
            agent_class_obj = self.agent_registry.get_agent_class(node.agent_type)
            agent_class = (
                agent_class_obj.__name__ if agent_class_obj else "DefaultAgent"
            )
            lines.append(f'builder.add_node("{node.name}", {agent_class}())')

        entry = next(iter(graph_def))
        lines.append(f'builder.set_entry_point("{entry}")')
        lines.append("graph = builder.compile()")

        path = self._get_output_path(graph_name, output_path, "src")
        with open(path, "w") as f:
            f.write("\n".join(lines))

        self.logger.info(
            f"[GraphOutputService] ✅ Exported {graph_name} source to {path}"
        )
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

        lines = [
            f"# Debug Export for Graph: {graph_name}",
            f"# State Schema: {state_schema}",
            f"# Generated by GraphOutputService",
            "",
            "# === GRAPH STRUCTURE ===",
        ]

        for node_name, node in graph_def.items():
            lines.extend(
                [
                    f"",
                    f"# Node: {node_name}",
                    f"#   Agent Type: {node.agent_type}",
                    f"#   Inputs: {node.inputs}",
                    f"#   Output: {node.output}",
                    (
                        f"#   Prompt: {node.prompt[:100]}..."
                        if len(node.prompt or "") > 100
                        else f"#   Prompt: {node.prompt}"
                    ),
                    f"#   Edges: {node.edges}",
                ]
            )

        lines.extend(
            [
                "",
                "# === EXECUTABLE CODE ===",
                "",
            ]
        )

        # Add the actual executable code
        python_lines = self._generate_python_code(graph_name, graph_def, state_schema)
        lines.extend(python_lines)

        path = self._get_output_path(graph_name, output_path, "debug")
        with open(path, "w") as f:
            f.write("\n".join(lines))

        self.logger.info(
            f"[GraphOutputService] ✅ Exported {graph_name} debug info to {path}"
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
        lines = ""
        if export_format == "markdown":
            lines = self._generate_markdown_docs(graph_name, graph_def)
        elif export_format == "html":
            lines = self._generate_html_docs(graph_name, graph_def)

        path = self._get_output_path(graph_name, output_path, ext)
        with open(path, "w") as f:
            f.write("\n".join(lines))

        self.logger.info(
            f"[GraphOutputService] ✅ Generated {export_format} documentation for {graph_name}: {path}"
        )
        return path

    def _get_graph_definition(self, graph_name: str):
        """
        Get graph definition using CompilationService.

        Args:
            graph_name: Name of the graph to retrieve

        Returns:
            Graph definition dict in old format (for compatibility with existing export methods)

        Raises:
            ValueError: If graph not found or compilation dependencies unavailable
        """

        try:
            # TODO: get the graph definition from the graph bundle

            return None

        except Exception as e:
            self.logger.error(
                f"[GraphOutputService] Failed to get graph definition for export '{graph_name}': {e}"
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
        Convert Graph domain model to old format for compatibility with export methods.

        Args:
            graph: Graph domain model

        Returns:
            Dictionary in old GraphBuilder format
        """
        old_format = {}

        for node_name, node in graph.nodes.items():
            # Convert Node to old format using a simple object with the required attributes
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
                    f"[GraphOutputService] Failed to import '{model_name}', fallback to dict: {e}"
                )
                return dict
        else:
            try:
                module_path, class_name = state_schema.rsplit(".", 1)
                module = __import__(module_path, fromlist=[class_name])
                return getattr(module, class_name)
            except Exception as e:
                self.logger.warning(
                    f"[GraphOutputService] Failed to import custom schema '{state_schema}': {e}"
                )
                return dict

    def _generate_python_code(
        self, graph_name: str, graph_def: Dict, state_schema: str
    ) -> List[str]:
        """
        Generate Python code for graph export.

        Args:
            graph_name: Name of the graph
            graph_def: Graph definition dictionary
            state_schema: State schema to use

        Returns:
            List of code lines
        """
        lines = [IMPORT_HEADER]

        if state_schema.startswith("pydantic:"):
            model_name = state_schema.split(":", 1)[1]
            lines.append(
                f"from agentmap.schemas.{model_name.lower()} import {model_name}"
            )

        for node in graph_def.values():
            for target in node.edges.values():
                func = self.function_resolution.extract_func_ref(target)
                if func:
                    lines.append(f"from agentmap.functions.{func} import {func}")

        lines.extend(
            [
                "",
                f"# Graph: {graph_name}",
                f"builder = StateGraph({state_schema if state_schema != 'dict' else 'dict'})",
            ]
        )

        for node in graph_def.values():
            agent_class_obj = self.agent_registry.get_agent_class(node.agent_type)
            agent_class = (
                agent_class_obj.__name__ if agent_class_obj else "DefaultAgent"
            )
            context = (
                f'{{"input_fields": {node.inputs}, "output_field": "{node.output}"}}'
            )
            prompt_text = node.prompt or ""
            lines.append(
                f'builder.add_node("{node.name}", {agent_class}(name="{node.name}", prompt="{prompt_text}", context={context}))'
            )

        entry = next(iter(graph_def))
        lines.extend(
            [f'builder.set_entry_point("{entry}")', "graph = builder.compile()"]
        )

        return lines

    @staticmethod
    def _generate_markdown_docs(graph_name: str, graph_def: Dict) -> List[str]:
        """Generate markdown documentation for graph."""
        lines = [
            f"# Graph: {graph_name}",
            "",
            "## Overview",
            f"This document describes the structure and flow of the `{graph_name}` graph.",
            "",
            "## Nodes",
            "",
        ]

        for node_name, node in graph_def.items():
            lines.extend(
                [
                    f"### {node_name}",
                    f"- **Agent Type**: {node.agent_type}",
                    f"- **Inputs**: {', '.join(node.inputs) if node.inputs else 'None'}",
                    f"- **Output**: {node.output or 'None'}",
                    f"- **Description**: {node.description or 'No description'}",
                    "",
                ]
            )

            if node.prompt:
                lines.extend(["**Prompt:**", "```", node.prompt, "```", ""])

            if node.edges:
                lines.extend(["**Edges:**", ""])
                for edge_type, target in node.edges.items():
                    lines.append(f"- `{edge_type}` → `{target}`")
                lines.append("")

        return lines

    @staticmethod
    def _generate_html_docs(graph_name: str, graph_def: Dict) -> List[str]:
        """Generate HTML documentation for graph."""
        lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"    <title>Graph: {graph_name}</title>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 2em; }",
            "        .node { margin: 1em 0; padding: 1em; border: 1px solid #ccc; }",
            "        .prompt { background: #f5f5f5; padding: 1em; }",
            "    </style>",
            "</head>",
            "<body>",
            f"    <h1>Graph: {graph_name}</h1>",
            "    <h2>Nodes</h2>",
        ]

        for node_name, node in graph_def.items():
            lines.extend(
                [
                    f'    <div class="node">',
                    f"        <h3>{node_name}</h3>",
                    f"        <p><strong>Agent Type:</strong> {node.agent_type}</p>",
                    f'        <p><strong>Inputs:</strong> {", ".join(node.inputs) if node.inputs else "None"}</p>',
                    f'        <p><strong>Output:</strong> {node.output or "None"}</p>',
                    f'        <p><strong>Description:</strong> {node.description or "No description"}</p>',
                ]
            )

            if node.prompt:
                lines.extend(
                    [
                        f'        <div class="prompt">',
                        f"            <strong>Prompt:</strong><br>",
                        f"            <pre>{node.prompt}</pre>",
                        f"        </div>",
                    ]
                )

            lines.append("    </div>")

        lines.extend(["</body>", "</html>"])

        return lines

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
