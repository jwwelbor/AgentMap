# agentmap/services/graph_export_service.py

import pickle
from pathlib import Path
from typing import Optional, Union, Dict

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.compilation_service import CompilationService, CompilationOptions
from agentmap.services.graph_bundle_service import GraphBundleService
from agentmap.models.graph import Graph

from agentmap.agents import get_agent_class

from langgraph.graph import StateGraph

try:
    import dill
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

class GraphExportService:
    """
    Service for exporting Graph domain models to various formats.
    
    This service handles format-specific output operations for graphs,
    including Python code generation, pickle serialization, and source
    code export. It focuses specifically on export operations and
    coordinates with CompilationService for graph building.
    """
    
    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        function_resolution_service: FunctionResolutionService,
        graph_bundle_service: GraphBundleService,
        compilation_service: Optional[CompilationService] = None
    ):
        """Initialize export service with dependency injection."""
        self.compiled_graphs_path = app_config_service.get_compiled_graphs_path()
        self.csv_path = app_config_service.get_csv_path()
        self.custom_agents_path = app_config_service.get_custom_agents_path()
        self.functions_path = app_config_service.get_functions_path()
        self.logger = logging_service.get_class_logger(self)
        self.function_resolution = function_resolution_service
        self.compilation_service = compilation_service
        self.graph_bundle_service = graph_bundle_service
        self.logger.info("[GraphExportService] Initialized")

    def export_graph(self, 
                     graph_name: str, 
                     format: str = "python", 
                     output_path: Optional[str] = None,
                     state_schema: str = "dict"):
        """
        Export graph to specified format.
        
        Args:
            graph_name: Name of the graph to export
            format: Export format ('python', 'pickle', 'pkl', 'source', 'src')
            output_path: Optional output path override
            state_schema: State schema to use for export
            
        Returns:
            Path to the exported file
            
        Raises:
            ValueError: If export format is not supported
        """
        self.logger.info(f"[GraphExportService] Exporting graph '{graph_name}' to format '{format}'")
        
        if format == "python":
            return self._export_as_python(graph_name, output_path, state_schema)
        elif format in ("pickle", "pkl"):
            return self._export_as_pickle(graph_name, output_path, state_schema)
        elif format in ("source", "src"):
            return self._export_as_source(graph_name, output_path, state_schema)
        else:
            raise ValueError(f"Unsupported export format: {format}. Supported formats: python, pickle, pkl, source, src")

    def _get_graph_definition(self, graph_name: str):
        """
        Get graph definition using CompilationService.
        
        Args:
            graph_name: Name of the graph to retrieve
            
        Returns:
            Graph definition dict in old format (for compatibility with existing export methods)
            
        Raises:
            ValueError: If graph not found or export dependencies unavailable
        """
        if self.compilation_service is None:
            raise ValueError(
                "CompilationService not available - cannot export graph. "
                "Graph export requires CompilationService to be properly registered."
            )
            
        try:
            # Use CompilationService to compile the graph, which internally uses GraphDefinitionService
            compilation_result = self.compilation_service.compile_graph(
                graph_name, 
                CompilationOptions(csv_path=self.csv_path, include_source=False)
            )
            
            if not compilation_result.success:
                raise ValueError(f"Failed to compile graph for export '{graph_name}': {compilation_result.error}")
            
            # Get the Graph domain model through GraphDefinitionService (via CompilationService)
            # We need to get the raw Graph object to convert to old format
            graph_domain_model = self.compilation_service.graph_definition.build_from_csv(self.csv_path, graph_name)
            
            # Convert Graph domain model to old format for compatibility
            graph_def = self._convert_graph_to_old_format(graph_domain_model)
            
            return graph_def
            
        except Exception as e:
            self.logger.error(f"[GraphExportService] Failed to get graph definition for export '{graph_name}': {e}")
            raise

    def _get_output_path(self, graph_name: str, output_path: Optional[str], ext: str):
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
            output_path = self.compiled_graphs_path / f"{graph_name}.{ext}"
        else:
            output_path = Path(output_path)
            if output_path.is_dir():
                output_path = output_path / f"{graph_name}.{ext}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    def _export_as_python(self, graph_name: str, output_path: Optional[str], state_schema: str):
        """
        Export graph as Python code.
        
        Args:
            graph_name: Name of the graph to export
            output_path: Optional output path override
            state_schema: State schema to use
            
        Returns:
            Path to the exported Python file
        """
        self.logger.debug(f"[GraphExportService] Exporting '{graph_name}' as Python code")
        
        graph_def = self._get_graph_definition(graph_name)
        lines = self._generate_python_code(graph_name, graph_def, state_schema)
        path = self._get_output_path(graph_name, output_path, "py")
        
        with open(path, "w") as f:
            f.write("\n".join(lines))
        
        self.logger.info(f"[GraphExportService] ✅ Exported {graph_name} to {path}")
        return path

    def _export_as_pickle(self, graph_name: str, output_path: Optional[str], state_schema: str):
        """
        Export graph as pickle file using clean architecture services.
        
        Args:
            graph_name: Name of the graph to export
            output_path: Optional output path override
            state_schema: State schema to use
            
        Returns:
            Path to the exported pickle file
        """
        self.logger.debug(f"[GraphExportService] Exporting '{graph_name}' as pickle")
        
        if self.compilation_service is None:
            self.logger.warning("[GraphExportService] CompilationService not available - falling back to Python export")
            return self._export_as_python(graph_name, output_path, state_schema)
            
        try:
            # Use CompilationService to compile the graph with proper schema
            compilation_options = CompilationOptions(
                csv_path=self.csv_path,
                state_schema=state_schema,
                include_source=False
            )
            
            compilation_result = self.compilation_service.compile_graph(graph_name, compilation_options)
            
            if not compilation_result.success:
                self.logger.error(f"[GraphExportService] Failed to compile graph for export: {compilation_result.error}")
                # Fallback to python export if compilation fails
                return self._export_as_python(graph_name, output_path, state_schema)
            
            # Get the target output path
            target_path = self._get_output_path(graph_name, output_path, "pkl")
            
            # If compilation result path is different from target, copy/move the file
            if compilation_result.output_path != target_path:
                import shutil
                shutil.copy2(compilation_result.output_path, target_path)
                self.logger.debug(f"[GraphExportService] Copied compiled graph from {compilation_result.output_path} to {target_path}")
            
            self.logger.info(f"[GraphExportService] ✅ Exported {graph_name} to {target_path}")
            return target_path
            
        except Exception as e:
            self.logger.error(f"[GraphExportService] Failed to export graph as pickle: {e}")
            # Fallback to python export
            self.logger.info("[GraphExportService] Falling back to Python export")
            return self._export_as_python(graph_name, output_path, state_schema)

    def _export_as_source(self, graph_name: str, output_path: Optional[str], state_schema: str):
        """
        Export graph as source code.
        
        Args:
            graph_name: Name of the graph to export
            output_path: Optional output path override
            state_schema: State schema to use
            
        Returns:
            Path to the exported source file
        """
        self.logger.debug(f"[GraphExportService] Exporting '{graph_name}' as source code")
        
        graph_def = self._get_graph_definition(graph_name)
        lines = [f"builder = StateGraph({state_schema})"] if state_schema != "dict" else ["builder = StateGraph(dict)"]
        
        for node in graph_def.values():
            agent_class = get_agent_class(node.agent_type).__name__ if get_agent_class(node.agent_type) else "DefaultAgent"
            lines.append(f'builder.add_node("{node.name}", {agent_class}())')
        
        entry = next(iter(graph_def))
        lines.append(f'builder.set_entry_point("{entry}")')
        
        path = self._get_output_path(graph_name, output_path, "src")
        with open(path, "w") as f:
            f.write("\n".join(lines))
        
        self.logger.info(f"[GraphExportService] ✅ Exported {graph_name} source to {path}")
        return path
    
    def _convert_graph_to_old_format(self, graph: Graph) -> Dict:
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
            old_format[node_name] = type('Node', (), {
                'name': node.name,
                'context': node.context,
                'agent_type': node.agent_type,
                'inputs': node.inputs,
                'output': node.output,
                'prompt': node.prompt,
                'description': node.description,
                'edges': node.edges
            })()
        
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
                module = __import__(f"agentmap.schemas.{model_name.lower()}", fromlist=[model_name])
                return getattr(module, model_name)
            except (ImportError, AttributeError) as e:
                self.logger.warning(f"[GraphExportService] Failed to import '{model_name}', fallback to dict: {e}")
                return dict
        else:
            try:
                module_path, class_name = state_schema.rsplit(".", 1)
                module = __import__(module_path, fromlist=[class_name])
                return getattr(module, class_name)
            except Exception as e:
                self.logger.warning(f"[GraphExportService] Failed to import custom schema '{state_schema}': {e}")
                return dict

    def _generate_python_code(self, graph_name, graph_def, state_schema):
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
            lines.append(f"from agentmap.schemas.{model_name.lower()} import {model_name}")
        
        for node in graph_def.values():
            for target in node.edges.values():
                func = self.function_resolution.extract_func_ref(target)
                if func:
                    lines.append(f"from agentmap.functions.{func} import {func}")
        
        lines.append("")
        lines.append(f"# Graph: {graph_name}")
        lines.append(f"builder = StateGraph({state_schema if state_schema != 'dict' else 'dict'})")
        
        for node in graph_def.values():
            agent_class = get_agent_class(node.agent_type).__name__ if get_agent_class(node.agent_type) else "DefaultAgent"
            context = f'{{"input_fields": {node.inputs}, "output_field": "{node.output}"}}'
            lines.append(f'builder.add_node("{node.name}", {agent_class}(name="{node.name}", prompt="{node.prompt or ''}", context={context}))')
        
        entry = next(iter(graph_def))
        lines.append(f'builder.set_entry_point("{entry}")')
        lines.append("graph = builder.compile()")
        
        return lines
    
    def get_service_info(self) -> Dict[str, Union[str, bool]]:
        """
        Get information about the export service for debugging.
        
        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphExportService",
            "compilation_service_available": self.compilation_service is not None,
            "graph_bundle_service_available": self.graph_bundle_service is not None,
            "function_resolution_available": self.function_resolution is not None,
            "compiled_graphs_path": str(self.compiled_graphs_path),
            "csv_path": str(self.csv_path),
            "functions_path": str(self.functions_path),
            "supported_formats": ["python", "pickle", "pkl", "source", "src"],
            "dill_available": HAS_DILL
        }
