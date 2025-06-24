"""
CompilationService for AgentMap.

Service that wraps existing graph compilation functionality providing a clean interface
for compiling graphs while maintaining all existing features including registry injection,
bundling, and source code generation.
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.graph_assembly_service import GraphAssemblyService
from agentmap.services.graph_bundle_service import GraphBundleService
from agentmap.services.graph_definition_service import GraphDefinitionService
from agentmap.services.logging_service import LoggingService
from agentmap.services.node_registry_service import NodeRegistryService


@dataclass
class CompilationOptions:
    """Options for graph compilation."""

    output_dir: Optional[Path] = None
    state_schema: str = "dict"
    force_recompile: bool = False
    include_source: bool = True
    csv_path: Optional[Path] = None


@dataclass
class CompilationResult:
    """Result of graph compilation."""

    graph_name: str
    output_path: Path
    source_path: Optional[Path]
    success: bool
    compilation_time: float
    registry_stats: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CompilationService:
    """
    Service for graph compilation with clean interface.

    Wraps existing compiler functionality while providing enhanced options,
    better error handling, and integration with the new GraphBuilderService.
    """

    def __init__(
        self,
        graph_definition_service: GraphDefinitionService,
        logging_service: LoggingService,
        app_config_service: AppConfigService,
        node_registry_service: NodeRegistryService,
        graph_bundle_service: GraphBundleService,
        assembly_service: GraphAssemblyService,
        function_resolution_service: FunctionResolutionService,
    ):
        """Initialize service with dependency injection."""
        self.graph_definition = graph_definition_service
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service
        self.node_registry = node_registry_service
        self.assembly_service = assembly_service
        self.bundle_service = graph_bundle_service
        self.function_resolution_service = function_resolution_service
        self.logger.info("[CompilationService] Initialized")

    def compile_graph(
        self, graph_name: str, options: Optional[CompilationOptions] = None
    ) -> CompilationResult:
        """
        Compile single graph with options.

        Args:
            graph_name: Name of the graph to compile
            options: Compilation options (uses defaults if None)

        Returns:
            CompilationResult with compilation details
        """
        start_time = time.time()
        # class CompilationOptions:
        #     """Options for graph compilation."""
        #     output_dir: Optional[Path] = None
        #     state_schema: str = "dict"
        #     force_recompile: bool = False
        #     include_source: bool = True
        #     csv_path: Optional[Path] = None

        if options is None:
            options = CompilationOptions()
            options.csv_path = self.config.get_csv_path()
            options.output_dir = self.config.get_compiled_graphs_path()

        self.logger.info(f"[CompilationService] Compiling graph: {graph_name}")

        try:
            # Get CSV path
            csv_path = options.csv_path or self.config.csv_path

            # Check if recompilation needed
            if not options.force_recompile and self._is_compilation_current(
                graph_name, csv_path, options
            ):
                self.logger.info(
                    f"[CompilationService] Graph {graph_name} is up to date, skipping compilation"
                )
                # Return existing compilation result
                output_path = self._get_output_path(graph_name, options.output_dir)
                compilation_time = time.time() - start_time
                return CompilationResult(
                    graph_name=graph_name,
                    output_path=output_path,
                    source_path=(
                        self._get_source_path(graph_name, options.output_dir)
                        if options.include_source
                        else None
                    ),
                    success=True,
                    compilation_time=compilation_time,
                )

            # Build graph using GraphDefinitionService
            graph = self.graph_definition.build_from_csv(csv_path, graph_name)

            # Use Graph domain model directly with GraphAssemblyService

            # Prepare node registry
            node_registry = self.node_registry.prepare_for_assembly(
                graph.nodes, graph_name
            )

            # Create agent instances for each node (CompilationService needs this)
            for node in graph.nodes.values():
                agent_instance = self._create_agent_instance(node, graph_name)
                # Ensure node.context is a dictionary and add the agent instance
                if not hasattr(node, "context") or node.context is None:
                    node.context = {}
                elif not isinstance(node.context, dict):
                    node.context = {"context": node.context}
                node.context["instance"] = agent_instance

            # Create fresh compiled graph with registry injection (avoid LangGraph reuse issues)
            compiled_graph = self.assembly_service.assemble_graph(
                graph=graph,
                node_registry=node_registry,
            )

            # Check if assembly was successful
            if compiled_graph is None:
                raise ValueError(
                    f"Graph assembly failed for '{graph_name}' - assemble_graph returned None"
                )

            # Compile graph
            # Prepare source code
            # Generate source lines for debugging (simplified)
            src_lines = [f"# Generated graph: {graph_name}", "# Compiled with AgentMap"]

            # Prepare output directory
            output_dir = options.output_dir or self.config.compiled_graphs_path
            os.makedirs(output_dir, exist_ok=True)

            # Read CSV content for versioning
            with open(csv_path, "r") as f:
                csv_content = f.read()

            # Create bundle and save
            bundle = self.bundle_service.create_bundle(
                graph=compiled_graph,
                node_registry=node_registry,
                csv_content=csv_content,
            )

            output_path = Path(output_dir) / f"{graph_name}.pkl"
            self.bundle_service.save_bundle(bundle, output_path)

            # Save source file if requested
            source_path = None
            if options.include_source:
                source_path = Path(output_dir) / f"{graph_name}.src"
                with open(source_path, "w") as f:
                    f.write("\n".join(src_lines))

            compilation_time = time.time() - start_time

            # Get registry statistics
            # Note: This is a simplified approach - in full implementation we'd capture these during compilation
            registry_stats = {
                "nodes_processed": len(graph.nodes),
                "registry_size": len(node_registry),
                "compilation_time": compilation_time,
            }

            self.logger.info(
                f"[CompilationService] ✅ Compiled {graph_name} to {output_path} "
                f"in {compilation_time:.2f}s with registry injection"
            )

            return CompilationResult(
                graph_name=graph_name,
                output_path=output_path,
                source_path=source_path,
                success=True,
                compilation_time=compilation_time,
                registry_stats=registry_stats,
            )

        except Exception as e:
            compilation_time = time.time() - start_time
            error_msg = f"Failed to compile graph {graph_name}: {str(e)}"
            self.logger.error(f"[CompilationService] {error_msg}")

            return CompilationResult(
                graph_name=graph_name,
                output_path=Path(""),  # Empty path for failed compilation
                source_path=None,
                success=False,
                compilation_time=compilation_time,
                error=error_msg,
            )

    def compile_all_graphs(
        self, options: Optional[CompilationOptions] = None
    ) -> List[CompilationResult]:
        """
        Compile all graphs found in CSV file.

        Args:
            options: Compilation options (uses defaults if None)

        Returns:
            List of CompilationResult for each graph
        """
        options = options or CompilationOptions()
        csv_path = options.csv_path or self.config.csv_path

        self.logger.info("[CompilationService] Compiling all graphs")

        try:
            # Get all graphs from CSV
            all_graphs = self.graph_definition.build_all_from_csv(csv_path)

            results = []
            for graph_name in all_graphs.keys():
                result = self.compile_graph(graph_name, options)
                results.append(result)

            successful_compilations = [r for r in results if r.success]
            failed_compilations = [r for r in results if not r.success]

            self.logger.info(
                f"[CompilationService] ✅ Compilation complete: "
                f"{len(successful_compilations)} successful, {len(failed_compilations)} failed"
            )

            if failed_compilations:
                for result in failed_compilations:
                    self.logger.error(
                        f"[CompilationService] Failed: {result.graph_name} - {result.error}"
                    )

            return results

        except Exception as e:
            error_msg = f"Failed to compile all graphs: {str(e)}"
            self.logger.error(f"[CompilationService] {error_msg}")

            # Return single failed result representing the batch failure
            return [
                CompilationResult(
                    graph_name="<batch_compilation>",
                    output_path=Path(""),
                    source_path=None,
                    success=False,
                    compilation_time=0.0,
                    error=error_msg,
                )
            ]

    def auto_compile_if_needed(
        self,
        graph_name: str,
        csv_path: Path,
        options: Optional[CompilationOptions] = None,
    ) -> Optional[CompilationResult]:
        """
        Auto-compile if missing or outdated.

        Args:
            graph_name: Name of the graph to compile
            csv_path: Path to CSV file
            options: Compilation options

        Returns:
            CompilationResult if compilation was performed, None if not needed
        """
        options = options or CompilationOptions()
        options.csv_path = csv_path

        if self._is_compilation_current(graph_name, csv_path, options):
            self.logger.debug(
                f"[CompilationService] Graph {graph_name} is current, no compilation needed"
            )
            return None

        self.logger.info(
            f"[CompilationService] Auto-compiling outdated graph: {graph_name}"
        )
        return self.compile_graph(graph_name, options)

    def validate_before_compilation(self, csv_path: Path) -> List[str]:
        """
        Validate CSV before attempting compilation.

        Args:
            csv_path: Path to CSV file to validate

        Returns:
            List of validation errors (empty if valid)
        """
        self.logger.debug(
            f"[CompilationService] Validating CSV before compilation: {csv_path}"
        )
        return self.graph_definition.validate_csv_before_building(csv_path)

    def get_compilation_status(
        self, graph_name: str, csv_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Get compilation status for a graph.

        Args:
            graph_name: Name of the graph
            csv_path: Optional CSV path override

        Returns:
            Dictionary with compilation status information
        """
        csv_path = csv_path or self.config.csv_path
        output_path = self._get_output_path(graph_name)

        status = {
            "graph_name": graph_name,
            "compiled": output_path.exists(),
            "output_path": output_path,
            "current": False,
            "csv_path": csv_path,
        }

        if status["compiled"]:
            status["current"] = self._is_compilation_current(graph_name, csv_path)
            status["compiled_time"] = output_path.stat().st_mtime
            status["csv_modified_time"] = csv_path.stat().st_mtime

        return status

    def _create_agent_instance(self, node, graph_name: str):
        """Create agent instance for compilation."""
        # For compilation, we just need a minimal agent that can be assembled
        # We'll use DefaultAgent with minimal setup
        from agentmap.agents.builtins.default_agent import DefaultAgent
        from agentmap.services.state_adapter_service import StateAdapterService

        # Create context with input/output field information
        context = {
            "input_fields": node.inputs,
            "output_field": node.output,
            "description": node.description or "",
        }

        # For compilation, create a minimal functional agent using existing services
        agent_instance = DefaultAgent(
            name=node.name,
            prompt=node.prompt or "",
            logger=self.logger,
            execution_tracker_service=self._get_execution_tracker(),
            context=context,
            state_adapter_service=StateAdapterService(),
        )

        return agent_instance

    def _get_execution_tracker(self):
        """Get an execution tracker for compilation."""
        # For compilation, create a minimal tracker
        from agentmap.models.execution_tracker import ExecutionTracker

        return ExecutionTracker(
            track_inputs=False, track_outputs=False, minimal_mode=True
        )

    def _is_compilation_current(
        self,
        graph_name: str,
        csv_path: Path,
        options: Optional[CompilationOptions] = None,
    ) -> bool:
        """
        Check if compilation is current (compiled file newer than CSV).

        Args:
            graph_name: Name of the graph
            csv_path: Path to CSV file
            options: Compilation options

        Returns:
            True if compilation is current, False otherwise
        """
        output_path = self._get_output_path(
            graph_name, options.output_dir if options else None
        )

        if not output_path.exists():
            return False

        if not csv_path.exists():
            return True  # Can't compare if CSV doesn't exist

        compiled_time = output_path.stat().st_mtime
        csv_time = csv_path.stat().st_mtime

        return compiled_time > csv_time

    def _get_output_path(
        self, graph_name: str, output_dir: Optional[Path] = None
    ) -> Path:
        """Get output path for compiled graph."""
        output_dir = output_dir or self.config.compiled_graphs_path
        return Path(output_dir) / f"{graph_name}.pkl"

    def _get_source_path(
        self, graph_name: str, output_dir: Optional[Path] = None
    ) -> Path:
        """Get source path for compiled graph."""
        output_dir = output_dir or self.config.compiled_graphs_path
        return Path(output_dir) / f"{graph_name}.src"

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the compilation service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "CompilationService",
            "graph_definition_available": self.graph_definition is not None,
            "config_available": self.config is not None,
            "node_registry_available": self.node_registry is not None,
            "compiled_graphs_path": str(self.config.compiled_graphs_path),
            "csv_path": str(self.config.csv_path),
            "functions_path": str(self.config.functions_path),
        }
