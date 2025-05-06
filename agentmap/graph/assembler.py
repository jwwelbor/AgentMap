"""
Graph assembler for AgentMap.

Centralizes logic for building LangGraph graphs with consistent interfaces
and optional logging to reduce code duplication.
"""

import time
from typing import Any, Callable, Dict

from langgraph.graph import StateGraph

from agentmap.config import get_functions_path
from agentmap.logging import get_logger
from agentmap.utils.common import extract_func_ref, import_function
from agentmap.graph.tracked_node import TrackedNode

logger = get_logger(__name__)

class GraphAssembler:
    """
    Central class for building LangGraph graphs with consistent interfaces
    and optional logging.
    
    Encapsulates all the logic for adding nodes and edges to graphs,
    reducing code duplication across the codebase.
    """
    
    def __init__(self, builder: StateGraph, config_path=None, enable_logging=True):
        """
        Initialize the graph assembler.
        
        Args:
            builder: StateGraph builder instance
            config_path: Optional path to a custom config file
            enable_logging: Whether to enable logging of graph operations
        """
        self.builder = builder
        self.config_path = config_path
        self.enable_logging = enable_logging
        self.functions_dir = get_functions_path(config_path)
    
    def add_node(self, name: str, agent_instance: Any) -> None:
        """
        Add a node to the graph with execution tracking and optional logging.
        
        Args:
            name: Name of the node
            agent_instance: Agent instance to add
        """
        # Wrap the agent's run method with tracking
        wrapped_function = TrackedNode(name, agent_instance.run)
        
        if self.enable_logging:
            # Wrap with additional logging if needed
            wrapped_invoke = self._create_node_logger(name, wrapped_function)
            self.builder.add_node(name, wrapped_invoke)
            logger.debug(f"[GraphAssembler] Added node '{name}' with tracking and logging")
        else:
            # Just use the tracked node
            self.builder.add_node(name, wrapped_function)
            logger.debug(f"[GraphAssembler] Added node '{name}' with tracking")
    
    def set_entry_point(self, node_name: str) -> None:
        """
        Set the entry point for the graph.
        
        Args:
            node_name: Name of the entry node
        """
        self.builder.set_entry_point(node_name)
        if self.enable_logging:
            logger.debug(f"[GraphAssembler] Set entry point to '{node_name}'")
    
    def add_default_edge(self, source: str, target: str) -> None:
        """
        Add a simple edge between nodes.
        
        Args:
            source: Source node name
            target: Target node name
        """
        self.builder.add_edge(source, target)
        if self.enable_logging:
            logger.debug(f"[GraphAssembler] Added default edge from '{source}' -> '{target}'")
    
    def add_conditional_edge(self, source: str, condition_func: Callable) -> None:
        """
        Add a conditional edge with centralized logging.
        
        Args:
            source: Source node name
            condition_func: Function that determines the next node
        """
        if self.enable_logging:
            # Wrap condition function with logging if needed
            wrapped_func = self._create_condition_logger(source, condition_func)
            self.builder.add_conditional_edges(source, wrapped_func)
            logger.debug(f"[GraphAssembler] Added conditional edge from '{source}'")
        else:
            self.builder.add_conditional_edges(source, condition_func)
            logger.debug(f"[GraphAssembler] Added conditional edge from '{source}'")
    
    def add_success_failure_edge(self, source: str, success_target: str, failure_target: str) -> None:
        """
        Add a conditional edge based on last_action_success.
        
        Args:
            source: Source node name
            success_target: Target node on success
            failure_target: Target node on failure
        """
        def branch_with_logging(state):
            is_success = state.get("last_action_success", True)
            target = success_target if is_success else failure_target
            
            if self.enable_logging:
                path_type = "success" if is_success else "failure"
                logger.info(f"[GraphExec] 🔀 TRANSITION: '{source}' -> '{target}' ({path_type})")
                
            return target
        
        self.builder.add_conditional_edges(source, branch_with_logging)
        
        if self.enable_logging:
            logger.debug(f"[GraphAssembler] Added success/failure edge from '{source}' with success->{success_target}, failure->{failure_target}")
    
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
        
        def func_with_logging(state):
            result = func(state, success_target, failure_target)
            
            if self.enable_logging:
                if isinstance(result, list):
                    logger.info(f"[GraphExec] 🔀 BRANCHING: '{source}' -> {result} (via {func_name})")
                else:
                    is_success = state.get("last_action_success", True)
                    path_type = "success" if is_success else "failure"
                    logger.info(f"[GraphExec] 🔀 TRANSITION: '{source}' -> '{result}' ({path_type} via {func_name})")
            
            return result
        
        self.builder.add_conditional_edges(source, func_with_logging)
        
        if self.enable_logging:
            logger.debug(f"[GraphAssembler] Added function edge from '{source}' using '{func_name}'")
    
    def process_node_edges(self, node_name: str, edges: Dict[str, str]) -> None:
        """
        Process all edges for a node with appropriate logging.
        
        Args:
            node_name: Name of the source node
            edges: Dictionary of edge conditions to targets
        """
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
                        if self.enable_logging:
                            logger.info(f"[GraphExec] 🔀 TRANSITION: '{node_name}' -> '{success_target}' (success)")
                        return success_target
                    else:
                        if self.enable_logging:
                            logger.info(f"[GraphExec] ⛔ HALTED: '{node_name}' (failure with no defined path)")
                        return None
                
                self.add_conditional_edge(node_name, success_only)
            
            # Handle failure-only edge
            elif "failure" in edges:
                failure_target = edges["failure"]
                
                def failure_only(state):
                    if not state.get("last_action_success", True):
                        if self.enable_logging:
                            logger.info(f"[GraphExec] 🔀 TRANSITION: '{node_name}' -> '{failure_target}' (failure)")
                        return failure_target
                    else:
                        if self.enable_logging:
                            logger.info(f"[GraphExec] ⛔ HALTED: '{node_name}' (success with no defined path)")
                        return None
                
                self.add_conditional_edge(node_name, failure_only)
            
            # Handle default edge
            elif "default" in edges:
                self.add_default_edge(node_name, edges["default"])
    
    def compile(self):
        """Compile the graph."""
        return self.builder.compile()
    
    # Private helper methods
    def _create_node_logger(self, node_name: str, invoke_func: Callable) -> Callable:
        """Create a wrapper for node execution logging."""
        def logging_wrapper(state):
            logger.info(f"[GraphExec] 🔄 EXECUTING NODE: '{node_name}'")
            logger.debug(f"[GraphExec] 📥 Input state for '{node_name}': {state}")
            
            start_time = time.time()
            result = invoke_func(state)
            execution_time = time.time() - start_time
            
            status = "✅ SUCCESS" if result.get("last_action_success", True) else "❌ FAILURE"
            logger.info(f"[GraphExec] {status} Node '{node_name}' completed in {execution_time:.2f}s")
            logger.debug(f"[GraphExec] 📤 Output state from '{node_name}': {result}")
            return result
        return logging_wrapper
    
    def _create_condition_logger(self, source_node: str, condition_func: Callable) -> Callable:
        """Create a wrapper for transition logging."""
        def logging_wrapper(state):
            result = condition_func(state)
            if result is None:
                logger.info(f"[GraphExec] ⛔ HALTED: '{source_node}' (condition returned None)")
            elif isinstance(result, list):
                logger.info(f"[GraphExec] 🔀 BRANCHING: '{source_node}' -> {result}")
            else:
                logger.info(f"[GraphExec] 🔀 TRANSITION: '{source_node}' -> '{result}'")
            return result
        return logging_wrapper