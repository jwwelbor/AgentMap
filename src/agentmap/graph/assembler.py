"""
Graph assembler for AgentMap with OrchestratorAgent support.

Adds dynamic routing capabilities for OrchestratorAgent nodes.
"""

from typing import Any, Callable, Dict, Optional

from langgraph.graph import StateGraph

from agentmap.agents.features import is_llm_enabled
from agentmap.logging import get_logger
from agentmap.state.adapter import StateAdapter
from agentmap.utils.common import extract_func_ref, import_function
from dependency_injector.wiring import inject, Provide
from agentmap.di.containers import ApplicationContainer
from agentmap.config.configuration import Configuration
from agentmap.logging.service import LoggingService
from agentmap.services import NodeRegistryUser

logger = get_logger("AgentMap")

class GraphAssembler:
    """
    Central class for building LangGraph graphs with consistent interfaces.
    
    Encapsulates all the logic for adding nodes and edges to graphs,
    reducing code duplication across the codebase.
    """

    @inject
    def __init__(
            self,
            builder: StateGraph,
            node_registry: Optional[Dict[str, Dict[str, Any]]] = None, 
            enable_logging=True,
            configuration: Configuration = Provide[ApplicationContainer.configuration],
            logging_service: LoggingService = Provide[ApplicationContainer.logging_service],
    ):
        self.builder = builder
        self.functions_dir = configuration.get_functions_path()
        self.enable_logging = enable_logging
        self.orchestrator_nodes = []  # Initialize the orchestrator nodes list
        
        # Store node registry for pre-compilation injection
        self.node_registry = node_registry

        self.injection_stats = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0
        }

        self.logger = logging_service.get_class_logger(self)

        if enable_logging:
            self.logger.info("Graph assembler initialized")
            if node_registry:
                self.logger.info(f"Graph assembler initialized with node registry containing {len(node_registry)} nodes")
    
    def set_node_registry(self, node_registry: Dict[str, Dict[str, Any]]) -> None:
        """
        Set the node registry for orchestrator injection.
        
        Args:
            node_registry: Dictionary mapping node names to metadata
        """
        self.node_registry = node_registry
        self.logger.info(f"Node registry set with {len(node_registry)} nodes")
    
    def add_node(self, name: str, agent_instance: Any) -> None:
        """Add a node to the graph with automatic registry injection for orchestrators."""
        # Handle special case for LLM-based orchestrators
        agent_class_name = agent_instance.__class__.__name__
        
        # Log helpful warnings about potential missing dependencies
        if agent_class_name == "OrchestratorAgent" and not is_llm_enabled():
            self.logger.warning(f"Orchestrator agent '{name}' may have limited functionality without LLM agents.")
            self.logger.warning("Install LLM dependencies with: pip install agentmap[llm]")

        # Add node to graph
        self.builder.add_node(name, agent_instance.run)
        
        # Check if this is agent needs NodeRegistry and inject like and orchestrator agent
        if isinstance(agent_instance, NodeRegistryUser):
            self.orchestrator_nodes.append(name)
            self.injection_stats["orchestrators_found"] += 1
            
            # Inject node registry if available
            if self.node_registry:
                try:
                    agent_instance.node_registry = self.node_registry
                    self.injection_stats["orchestrators_injected"] += 1
                    
                    if self.enable_logging:
                        self.logger.info(f"✅ Injected registry into orchestrator '{name}' (pre-compilation)")
                        self.logger.debug(f"Registry contains {len(self.node_registry)} nodes: {list(self.node_registry.keys())}")
                        
                except Exception as e:
                    self.injection_stats["injection_failures"] += 1
                    self.logger.error(f"❌ Failed to inject registry into orchestrator '{name}': {e}")
            else:
                self.logger.warning(f"⚠️ No registry available for orchestrator '{name}' - will need post-compilation injection")
            
        if self.enable_logging:
            self.logger.info(f"🔹 Added node: '{name}' ({agent_class_name})")
    
    def get_injection_summary(self) -> Dict[str, int]:
        """
        Get summary of registry injection statistics.
        
        Returns:
            Dictionary with injection statistics
        """
        return self.injection_stats.copy()
    
    def set_entry_point(self, node_name: str) -> None:
        """
        Set the entry point for the graph.
        
        Args:
            node_name: Name of the entry node
        """
        self.builder.set_entry_point(node_name)
        if self.enable_logging:
            self.logger.info(f"🚪 Set entry point: '{node_name}'")
    
    def add_default_edge(self, source: str, target: str) -> None:
        """
        Add a simple edge between nodes.
        
        Args:
            source: Source node name
            target: Target node name
        """
        self.builder.add_edge(source, target)
        if self.enable_logging:
            self.logger.info(f"➡️ Added edge: '{source}' → '{target}'")
    
    def add_conditional_edge(self, source: str, condition_func: Callable) -> None:
        """
        Add a conditional edge.
        
        Args:
            source: Source node name
            condition_func: Function that determines the next node
        """
        self.builder.add_conditional_edges(source, condition_func)
        if self.enable_logging:
            self.logger.info(f"🔀 Added conditional edge from: '{source}'")
    
    def add_success_failure_edge(self, source: str, success_target: str, failure_target: str) -> None:
        """
        Add a conditional edge based on last_action_success.
        
        Args:
            source: Source node name
            success_target: Target node on success
            failure_target: Target node on failure
        """
        def branch_function(state):
            is_success = state.get("last_action_success", True)
            return success_target if is_success else failure_target
        
        self.builder.add_conditional_edges(source, branch_function)
        if self.enable_logging:
            self.logger.info(f"🔀 Added branch: '{source}' → success: '{success_target}', failure: '{failure_target}'")
    
    def add_function_edge(self, source: str, func_name: str, success_target: str = None, failure_target: str = None) -> None:
        """
        Add an edge that uses a function to determine the next node.
        
        Args:
            source: Source node name
            func_name: Name of the routing function
            success_target: Success target for the function (optional)
            failure_target: Failure target for the function (optional)
        """
        # Check if function exists
        func_path = self.functions_dir / f"{func_name}.py"
        if not func_path.exists():
            raise FileNotFoundError(f"Function '{func_name}' not found at {func_path}")
        
        # Import the function
        func = import_function(func_name)
        
        def func_wrapper(state):
            return func(state, success_target, failure_target)
        
        self.builder.add_conditional_edges(source, func_wrapper)
        
        if self.enable_logging:
            self.logger.info(f"🔀 Added function edge: '{source}' → func:{func_name} " +
                       f"(success: '{success_target}', failure: '{failure_target}')")
    
    def add_dynamic_router(self, node_name: str) -> None:
        """
        Add dynamic routing support for an orchestrator node.
        
        Args:
            node_name: Name of the orchestrator node
        """
        def dynamic_router(state):
            # Check for __next_node field set by OrchestratorAgent
            next_node = StateAdapter.get_value(state, "__next_node")
            if next_node:
                # Clear the field to prevent loops
                state = StateAdapter.set_value(state, "__next_node", None)
                if self.enable_logging:
                    self.logger.debug(f"[DynamicRouter] Dynamic routing from '{node_name}' to '{next_node}'")
                return next_node
            # Fall back to regular routing if not set
            return None
            
        self.builder.add_conditional_edges(node_name, dynamic_router)
        if self.enable_logging:
            self.logger.info(f"🔄 Added dynamic router for orchestrator: '{node_name}'")
    
    def process_node_edges(self, node_name: str, edges: Dict[str, str]) -> None:
        """
        Process all edges for a node.
        
        Args:
            node_name: Name of the source node
            edges: Dictionary of edge conditions to targets
        """
        if not edges:
            if self.enable_logging:
                self.logger.info(f"ℹ️ Node '{node_name}' has no outgoing edges")
            return
            
        if self.enable_logging:
            self.logger.info(f"🔄 Processing edges for node: '{node_name}'")
        
        has_func = False
        
        # First check for function references
        for condition, target in edges.items():
            func_ref = extract_func_ref(target)
            if func_ref:
                success = edges.get("success", "None")
                failure = edges.get("failure", "None")
                self.add_function_edge(node_name, func_ref, success, failure)
                has_func = True
                break
        
        if not has_func:
            # Handle success/failure edges
            if "success" in edges and "failure" in edges:
                self.add_success_failure_edge(node_name, edges["success"], edges["failure"])
            
            # Handle success-only edge
            elif "success" in edges:
                success_target = edges["success"]
                
                def success_only(state):
                    if state.get("last_action_success", True):
                        return success_target
                    else:
                        return None
                
                self.add_conditional_edge(node_name, success_only)
                if self.enable_logging:
                    self.logger.info(f"🟢 Added success-only edge: '{node_name}' → '{success_target}'")
            
            # Handle failure-only edge
            elif "failure" in edges:
                failure_target = edges["failure"]
                
                def failure_only(state):
                    if not state.get("last_action_success", True):
                        return failure_target
                    else:
                        return None
                
                self.add_conditional_edge(node_name, failure_only)
                if self.enable_logging:
                    self.logger.info(f"🔴 Added failure-only edge: '{node_name}' → '{failure_target}'")
            
            # Handle default edge
            elif "default" in edges:
                self.add_default_edge(node_name, edges["default"])
    
    def finalize(self) -> None:
        """Add dynamic routing for all orchestrator nodes."""
        for node_name in self.orchestrator_nodes:
            self.add_dynamic_router(node_name)
    
    def compile(self) -> Any:
        """Compile the graph and report injection statistics."""
        # Add dynamic routing for orchestrator nodes before compiling
        self.finalize()
        
        if self.enable_logging:
            self.logger.info("📋 Compiling graph")
            
            # Report injection statistics
            stats = self.get_injection_summary()
            if stats["orchestrators_found"] > 0:
                self.logger.info(f"📊 Registry injection summary:")
                self.logger.info(f"   Orchestrators found: {stats['orchestrators_found']}")
                self.logger.info(f"   Orchestrators injected: {stats['orchestrators_injected']}")
                if stats["injection_failures"] > 0:
                    self.logger.warning(f"   Injection failures: {stats['injection_failures']}")
            
        graph = self.builder.compile()
        
        if self.enable_logging:
            self.logger.info("✅ Graph compiled successfully")
            
        return graph