"""
GraphRunnerService for AgentMap.

Simplified facade service that coordinates graph execution by delegating to specialized services.
Pure orchestration with minimal internal logic.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, List

from agentmap.models.execution_result import ExecutionResult
from agentmap.services.agent_factory_service import AgentFactoryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph.graph_execution_service import GraphExecutionService
from agentmap.services.host_protocol_configuration_service import HostProtocolConfigurationService
from agentmap.services.logging_service import LoggingService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.agent_service_injection_service import AgentServiceInjectionService
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.csv_graph_parser_service import CSVGraphParserService


@dataclass
class RunOptions:
    """Options for graph execution."""
    config_file: Optional[Path] = None
    initial_state: Optional[Any] = None
    csv_path: Optional[Path] = None
    validate_before_run: bool = False
    track_execution: bool = True
    execution_mode: str = "standard"

from agentmap.services.graph.graph_registry_service import GraphRegistryService

class GraphRunnerService:
    """
    Simplified facade service for graph execution orchestration.
    """
    
    def __init__(
        self,
        logging_service: LoggingService,
        app_config_service: AppConfigService,
        execution_tracking_service: ExecutionTrackingService,
        state_adapter_service: StateAdapterService,
        graph_execution_service: GraphExecutionService,
        graph_bundle_service: GraphBundleService,
        agent_factory_service: AgentFactoryService,
        csv_parser: CSVGraphParserService,
        graph_registry_service: GraphRegistryService,
        graph_bootstrap_service = None,  # NEW: GraphBootstrapService for optimized loading
        host_protocol_configuration_service: HostProtocolConfigurationService = None,
    ):
        """Initialize facade service with core dependencies only."""
        # Core orchestration services
        self.graph_execution = graph_execution_service
        self.graph_bundle_service = graph_bundle_service
        self.graph_registry = graph_registry_service  
        self.graph_bootstrap = graph_bootstrap_service  # NEW: For selective agent/service loading
        self.csv_parser = csv_parser
        self.agent_factory = agent_factory_service
        
        # Infrastructure
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service
        
        # Services for agent creation delegation
        self.execution_tracking_service = execution_tracking_service
        self.state_adapter_service = state_adapter_service
        
        # Optional host services
        self.host_protocol_configuration = host_protocol_configuration_service
        self._host_services_available = host_protocol_configuration_service is not None
        
        self.logger.info(
            f"[GraphRunnerService] Initialized with graph registry and "
            f"bootstrap service support (bootstrap available: {graph_bootstrap_service is not None})"
        )
    
    def run_graph(self, graph_name: str, options: Optional[RunOptions] = None) -> ExecutionResult:
        """
        Run a graph with optimized bundle loading via registry.
        
        Args:
            graph_name: Name of the graph to run
            options: Optional run configuration
            
        Returns:
            ExecutionResult with graph execution outcome
        """
        options = options or RunOptions()
        
        # Phase 1: Determine CSV path and compute hash
        csv_path = self._resolve_csv_path(graph_name, options)
        
        self.logger.info(f"Running graph '{graph_name}' from CSV: {csv_path}")
        
        # Compute CSV hash for registry lookup
        csv_hash = self.graph_registry.compute_hash(csv_path)
        
        self.logger.debug(f"CSV hash: {csv_hash[:8]}...")
        
        # Phase 2: Registry Check (FAST path)
        bundle_path = self.graph_registry.find_bundle(csv_hash)
        
        if bundle_path:
            # FAST PATH: Bundle exists, load it directly
            self.logger.info(f"Found existing bundle for '{graph_name}' at {bundle_path}")
            
            # Load bundle from disk (already parsed and optimized)
            bundle = self.graph_bundle_service.load_bundle(bundle_path)
            
            # Registry automatically updates access tracking
            
        else:
            # SLOW PATH: First time seeing this graph, need to parse and create bundle
            self.logger.info(f"No bundle found for '{graph_name}', creating new bundle")
            
            # Parse CSV (ONE-TIME operation per unique graph)
            graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)
            for (graph_name, node_specs) in graph_spec.graphs.items():
                nodes = self.csv_parser._convert_node_specs_to_nodes(node_specs)
            
                self.logger.debug(f"Parsed {len(nodes)} nodes from CSV")
            
                # Create optimized bundle with all metadata
                bundle = self.graph_bundle_service.create_metadata_bundle_from_nodes(
                    nodes=nodes,
                    graph_name=graph_name,
                    csv_hash=csv_hash,
                    # entry_point=no
                )
                
                # Save bundle to disk
                bundle_path = self._get_bundle_path(graph_name, csv_hash)
                self.graph_bundle_service.save_bundle(bundle, bundle_path)
            
                self.logger.info(f"Saved new bundle to {bundle_path}")
            
                # Register in registry for future fast lookups
                self.graph_registry.register(
                    csv_hash=csv_hash,
                    graph_name=graph_name,
                    bundle_path=bundle_path,
                    csv_path=csv_path,
                    node_count=len(nodes)
                )
                
                self.logger.info(f"Registered bundle in graph registry")
        
        # Phase 3: Optimized Bootstrap (only load what's needed)
        if self.graph_bootstrap:
            # Use GraphBootstrapService for selective loading
            self.logger.debug(f"Using GraphBootstrapService for optimized loading")
            
            # Bootstrap only required agents and services from bundle
            bootstrap_result = self.graph_bootstrap.bootstrap_from_bundle(bundle)
            
            self.logger.info(
                f"Bootstrap completed: {bootstrap_result.get('loaded_agents', 0)} agents, "
                f"{bootstrap_result.get('actual_services', 0)} services loaded"
            )
        else:
            # Fallback: Assume ApplicationBootstrapService has already loaded everything
            self.logger.debug(f"GraphBootstrapService not available, using pre-loaded agents/services")
        
        # Phase 4: Execute the graph using the bundle
        self.logger.info(f"Executing graph '{graph_name}' from bundle")
        
        # The graph_execution_service handles assembly and execution from bundle
        result = self.graph_execution.execute_from_bundle(
            bundle=bundle,
            initial_state=options.initial_state,
            tracking_enabled=options.track_execution
        )
        
        self.logger.info(f"Graph '{graph_name}' execution completed: {result.status}")
        
        return result
    
    def _resolve_csv_path(self, graph_name: str, options: RunOptions) -> Path:
        """
        Resolve the CSV file path for the graph.
        
        Args:
            graph_name: Name of the graph
            options: Run options that may contain csv_path
            
        Returns:
            Path to the CSV file
        """
        # If explicit CSV path provided, use it
        if options.csv_path:
            return options.csv_path
        
        # Otherwise, resolve from graph name and config
        base_path = self.config.get_graphs_directory()
        csv_path = base_path / f"{graph_name}.csv"
        
        if not csv_path.exists():
            raise FileNotFoundError(f"Graph CSV not found: {csv_path}")
        
        return csv_path
    
    def _get_bundle_path(self, graph_name: str, csv_hash: str) -> Path:
        """
        Generate bundle file path.
        
        Args:
            graph_name: Name of the graph
            csv_hash: Hash of the CSV content
            
        Returns:
            Path where bundle should be saved
        """
        bundles_dir = self.config.get_cache_path() / "bundles"
        
        # Create bundles directory if it doesn't exist
        bundles_dir.mkdir(parents=True, exist_ok=True)
        
        # Use graph name and partial hash for readability
        bundle_filename = f"{graph_name}_{csv_hash[:8]}.json"
        
        return bundles_dir / bundle_filename
    
    def _create_required_agents(self, required_agents: List[str]) -> Dict[str, Any]:
        """
        Create only the agents required by the graph.
        
        Args:
            required_agents: List of agent types needed
            
        Returns:
            Dictionary of agent instances by node ID
        """
        self.logger.debug(f"Creating {len(required_agents)} required agents")
        
        agents = {}
        
        for agent_type in required_agents:
            # Use agent factory to create appropriate agent type
            agent = self.agent_factory.create_agent(agent_type)
            agents[agent_type] = agent
        
        return agents
    
    def _load_required_services(self, required_services: List[str]) -> Dict[str, Any]:
        """
        Load only the services required by the graph.
        
        Args:
            required_services: List of service names needed
            
        Returns:
            Dictionary of service instances
        """
        self.logger.debug(f"Loading {len(required_services)} required services")
        
        # Services are already available via DI
        # This method would coordinate lazy loading if needed
        
        services = {
            'state_adapter': self.state_adapter_service,
            'execution_tracking': self.execution_tracking_service,
            # Add other services as needed based on required_services list
        }
        
        return services
    
    def _inject_services(self, agents: Dict[str, Any], services: Dict[str, Any]) -> None:
        """
        Inject services into agents that need them.
        
        Args:
            agents: Dictionary of agent instances
            services: Dictionary of service instances
        """
        self.logger.debug("Injecting services into agents")
        
        # Use the agent service injection pattern
        for agent in agents.values():
            # Check which services this agent needs and inject them
            # This follows the protocol-based injection pattern
            pass
    
    def _assemble_graph(self, bundle: Any, agents: Dict[str, Any]) -> Any:
        """
        Assemble the graph structure from bundle and agents.
        
        Args:
            bundle: GraphBundle with metadata
            agents: Dictionary of agent instances
            
        Returns:
            Assembled graph ready for execution
        """
        self.logger.debug("Assembling graph structure")
        
        # Create graph structure from bundle metadata
        # This includes nodes, edges, and agent assignments
        
        graph = {
            'nodes': bundle.nodes,
            'edges': bundle.edges,
            'agents': agents,
            'metadata': bundle.metadata
        }
        
        return graph
