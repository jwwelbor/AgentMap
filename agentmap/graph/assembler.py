"""
Graph assembler for AgentMap.

Centralizes logic for building LangGraph graphs with consistent interfaces.
"""

from typing import Any, Callable, Dict

from langgraph.graph import StateGraph

from agentmap.config import get_functions_path
from agentmap.utils.common import extract_func_ref, import_function

from agentmap.logging import get_logger
logger = get_logger("AgentMap")


class GraphAssembler:
    """
    Central class for building LangGraph graphs with consistent interfaces.
    
    Encapsulates all the logic for adding nodes and edges to graphs,
    reducing code duplication across the codebase.
    """
    
    def __init__(self, builder: StateGraph, config_path=None):
        """
        Initialize the graph assembler.
        
        Args:
            builder: StateGraph builder instance
            config_path: Optional path to a custom config file
        """
        self.builder = builder
        self.config_path = config_path
        self.functions_dir = get_functions_path(config_path)
        logger.info("Graph assembler initialized")
    
    def add_node(self, name: str, agent_instance: Any) -> None:
        """
        Add a node to the graph.
        
        Args:
            name: Name of the node
            agent_instance: Agent instance to add
        """
        self.builder.add_node(name, agent_instance.run)
        logger.info(f"🔹 Added node: '{name}' ({agent_instance.__class__.__name__})")
    
    def set_entry_point(self, node_name: str) -> None:
        """
        Set the entry point for the graph.
        
        Args:
            node_name: Name of the entry node
        """
        self.builder.set_entry_point(node_name)
        logger.info(f"🚪 Set entry point: '{node_name}'")
    
    def add_default_edge(self, source: str, target: str) -> None:
        """
        Add a simple edge between nodes.
        
        Args:
            source: Source node name
            target: Target node name
        """
        self.builder.add_edge(source, target)
        logger.info(f"➡️ Added edge: '{source}' → '{target}'")
    
    def add_conditional_edge(self, source: str, condition_func: Callable) -> None:
        """
        Add a conditional edge.
        
        Args:
            source: Source node name
            condition_func: Function that determines the next node
        """
        self.builder.add_conditional_edges(source, condition_func)
        logger.info(f"🔀 Added conditional edge from: '{source}'")
    
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
        logger.info(f"🔀 Added branch: '{source}' → success: '{success_target}', failure: '{failure_target}'")
    
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
        
        logger.info(f"🔀 Added function edge: '{source}' → func:{func_name} " +
                   f"(success: '{success_target}', failure: '{failure_target}')")
    
    def process_node_edges(self, node_name: str, edges: Dict[str, str]) -> None:
        """
        Process all edges for a node.
        
        Args:
            node_name: Name of the source node
            edges: Dictionary of edge conditions to targets
        """
        if not edges:
            logger.info(f"ℹ️ Node '{node_name}' has no outgoing edges")
            return
            
        logger.info(f"🔄 Processing edges for node: '{node_name}'")
        
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
                logger.info(f"🟢 Added success-only edge: '{node_name}' → '{success_target}'")
            
            # Handle failure-only edge
            elif "failure" in edges:
                failure_target = edges["failure"]
                
                def failure_only(state):
                    if not state.get("last_action_success", True):
                        return failure_target
                    else:
                        return None
                
                self.add_conditional_edge(node_name, failure_only)
                logger.info(f"🔴 Added failure-only edge: '{node_name}' → '{failure_target}'")
            
            # Handle default edge
            elif "default" in edges:
                self.add_default_edge(node_name, edges["default"])
    
    def compile(self):
        """Compile the graph."""
        logger.info("📋 Compiling graph")
        graph = self.builder.compile()
        logger.info("✅ Graph compiled successfully")
        return graph