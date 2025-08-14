"""
GraphRunnerService for AgentMap.

Simplified facade service that coordinates graph execution by delegating to specialized services.
Pure orchestration with minimal internal logic.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.models.execution_result import ExecutionResult
from agentmap.services.agent_factory_service import AgentFactoryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph_execution_service import GraphExecutionService
from agentmap.services.graph_resolution_service import GraphResolutionService
from agentmap.services.host_protocol_configuration_service import HostProtocolConfigurationService
from agentmap.services.logging_service import LoggingService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.agent_service_injection_service import AgentServiceInjectionService


@dataclass
class RunOptions:
    """Options for graph execution."""
    config_file: Optional[Path] = None
    initial_state: Optional[Any] = None
    csv_path: Optional[Path] = None
    validate_before_run: bool = False
    track_execution: bool = True
    execution_mode: str = "standard"


class GraphRunnerService:
    """
    Simplified facade service for graph execution orchestration.
    
    Pure delegation to specialized services with minimal internal logic.
    Maintains all existing public APIs while dramatically reducing complexity.
    """

    def __init__(
        self,
        graph_execution_service: GraphExecutionService,
        graph_resolution_service: GraphResolutionService,
        graph_preparation_service: Any,  # GraphPreparationService
        agent_factory_service: AgentFactoryService,
        agent_service_injection_service: AgentServiceInjectionService,
        logging_service: LoggingService,
        app_config_service: AppConfigService,
        execution_tracking_service: ExecutionTrackingService,
        state_adapter_service: StateAdapterService,
        host_protocol_configuration_service: HostProtocolConfigurationService = None,
        prompt_manager_service: Any = None,  # PromptManagerService - optional
    ):
        """Initialize facade service with core dependencies only."""
        # Core orchestration services
        self.graph_execution = graph_execution_service
        self.graph_resolution = graph_resolution_service
        self.graph_preparation = graph_preparation_service
        self.agent_factory = agent_factory_service
        self.agent_service_injection = agent_service_injection_service
        
        # Infrastructure
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service
        
        # Services for agent creation delegation
        self.execution_tracking_service = execution_tracking_service
        self.state_adapter_service = state_adapter_service
        self.prompt_manager_service = prompt_manager_service
        
        # Optional host services
        self.host_protocol_configuration = host_protocol_configuration_service
        self._host_services_available = host_protocol_configuration_service is not None
        
        self.logger.info("[GraphRunnerService] Initialized as pure delegation facade")

    def get_default_options(self) -> RunOptions:
        """Get default run options from configuration."""
        options = RunOptions()
        options.initial_state = None
        options.csv_path = self.config.get_csv_path()
        options.validate_before_run = False
        options.track_execution = self.config.get_execution_config().get("track_execution", True)
        options.execution_mode = "standard"
        return options

    def run_graph(self, graph_name: str, options: Optional[RunOptions] = None) -> ExecutionResult:
        """
        Main graph execution method - pure facade implementation.
        
        Delegates resolution to GraphResolutionService and execution to GraphExecutionService.
        """
        if options is None:
            options = self.get_default_options()
            
        state = options.initial_state or {}
        
        self.logger.info(f"⭐ STARTING GRAPH: '{graph_name}'")
        
        try:
            # Step 1: Resolve graph using GraphResolutionService
            resolved_execution = self.graph_resolution.resolve_graph_for_execution(
                graph_name, options.csv_path
            )
            
            # Step 2: Delegate execution based on resolution type
            if resolved_execution["type"] == "bundle":
                return self.graph_execution.execute_with_bundle(
                    bundle=resolved_execution["bundle"], state=state
                )
            elif resolved_execution["type"] == "definition":
                # Prepare and inject agents
                prepared_graph_def = self.graph_preparation.prepare_graph_definition(
                    resolved_execution["graph_def"], graph_name
                )
                self._inject_agent_instances(prepared_graph_def, graph_name)
                
                return self.graph_execution.execute_from_definition(
                    graph_def=prepared_graph_def, state=state, graph_name=graph_name
                )
            else:
                raise ValueError(f"Unknown resolution type: {resolved_execution['type']}")
                
        except Exception as e:
            self.logger.error(f"❌ GRAPH EXECUTION FAILED: '{graph_name}' - {str(e)}")
            return ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,
                execution_summary=None,
                total_duration=0.0,
                compiled_from=None,
                error=str(e),
            )

    def run_from_csv_direct(
        self, csv_path: Path, graph_name: str, options: Optional[RunOptions] = None
    ) -> ExecutionResult:
        """
        Run graph directly from CSV - pure delegation implementation.
        
        Delegates loading to GraphPreparationService and execution to GraphExecutionService.
        """
        if options is None:
            options = self.get_default_options()
            
        options.csv_path = csv_path
        state = options.initial_state or {}
        
        self.logger.info(f"[GraphRunnerService] Running from CSV: {csv_path}, graph: {graph_name}")
        
        try:
            # Delegate loading and preparation to GraphPreparationService
            graph_def, resolved_graph_name = self.graph_preparation.load_graph_definition_for_execution(
                csv_path, graph_name
            )
            
            # Delegate execution to GraphExecutionService
            return self.graph_execution.execute_from_definition(
                graph_def=graph_def, state=state, graph_name=resolved_graph_name
            )
            
        except Exception as e:
            self.logger.error(f"❌ CSV EXECUTION FAILED: '{graph_name}' - {str(e)}")
            return ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,
                execution_summary=None,
                total_duration=0.0,
                compiled_from="memory",
                error=str(e),
            )

    def _inject_agent_instances(self, graph_nodes: Dict[str, Any], graph_name: str) -> None:
        """
        Create and inject agent instances using AgentFactoryService delegation.
        """
        self.logger.debug(f"[GraphRunnerService] Injecting agents for: {graph_name}")
        
        # Get node registry from GraphPreparationService
        node_registry = self.graph_preparation.get_last_prepared_node_registry()
        
        # Create and configure agents for each node
        for node_name, node in graph_nodes.items():
            # Delegate agent creation to AgentFactoryService
            agent_instance = self.agent_factory.create_agent_instance(
                node=node,
                graph_name=graph_name,
                execution_tracking_service=self.execution_tracking_service,
                state_adapter_service=self.state_adapter_service,
                prompt_manager_service=self.prompt_manager_service,
                node_registry=node_registry
            )
            
            # Delegate service configuration to AgentServiceInjectionService
            self._configure_agent_services(agent_instance)
            
            # Store in node context
            if not node.context:
                node.context = {}
            node.context["instance"] = agent_instance
        
        self.logger.debug(f"[GraphRunnerService] ✅ Agents injected for: {graph_name}")

    def _configure_agent_services(self, agent: Any) -> None:
        """
        Configure services by delegating to AgentServiceInjectionService.
        """
        if self.agent_service_injection:
            # Delegate to centralized service injection
            summary = self.agent_service_injection.configure_all_services(agent)
            core_count = summary['total_services_configured']
            
            # Configure host services after core services
            host_count = self._configure_host_services(agent)
            
            total = core_count + host_count
            if total > 0:
                self.logger.info(
                    f"[GraphRunnerService] Configured {total} services for {agent.name} "
                    f"(core: {core_count}, host: {host_count})"
                )
            else:
                self.logger.debug(f"[GraphRunnerService] No services for {agent.name}")
        else:
            self.logger.warning(f"[GraphRunnerService] No service injection available for {agent.name}")

    def _configure_host_services(self, agent: Any) -> int:
        """
        Configure host services using HostProtocolConfigurationService delegation.
        """
        if not self._host_services_available or not self.config.is_host_application_enabled():
            return 0
            
        try:
            return self.host_protocol_configuration.configure_host_protocols(agent)
        except Exception as e:
            self.logger.error(f"[GraphRunnerService] Host service config failed for {agent.name}: {e}")
            return 0

    def get_service_info(self) -> Dict[str, Any]:
        """Get basic service status information."""
        return {
            "service": "GraphRunnerService",
            "architecture": "pure_delegation_facade",
            "dependencies_ready": all([
                self.graph_execution is not None,
                self.graph_resolution is not None,
                self.graph_preparation is not None,
                self.agent_factory is not None,
                self.agent_service_injection is not None,
            ]),
            "host_services": self._host_services_available,
        }

    def get_host_service_status(self, agent: Any) -> Dict[str, Any]:
        """Get host service status for debugging."""
        status = {
            "agent_name": getattr(agent, "name", "unknown"),
            "host_services_available": self._host_services_available,
            "host_application_enabled": self.config.is_host_application_enabled() if self.config else False,
            "error": None,
        }
        
        if not self._host_services_available:
            status["error"] = "HostProtocolConfigurationService not available"
            return status
            
        if not self.config.is_host_application_enabled():
            status["error"] = "Host application support disabled"
            return status
            
        try:
            config_status = self.host_protocol_configuration.get_configuration_status(agent)
            status.update({
                "protocols_implemented": config_status.get("configuration_potential", []),
                "services_configured": config_status.get("summary", {}).get("configuration_ready", 0),
            })
        except Exception as e:
            status["error"] = str(e)
            
        return status
