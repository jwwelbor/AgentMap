"""
Graph runner for executing AgentMap workflows from compiled graphs or CSV.
"""
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from langgraph.graph import StateGraph

from agentmap.config import (get_compiled_graphs_path, get_csv_path,
                             get_custom_agents_path, load_config)
from agentmap.exceptions import AgentInitializationError
from agentmap.graph import GraphAssembler
from agentmap.graph.builder import GraphBuilder
from agentmap.logging import get_logger
from agentmap.graph.node_registry import build_node_registry, populate_orchestrator_inputs
from agentmap.state.adapter import StateAdapter
from agentmap.agents.features import HAS_LLM_AGENTS, HAS_STORAGE_AGENTS
from agentmap.agents import get_agent_class
from agentmap.logging.tracking.policy import evaluate_success_policy

logger = get_logger(__name__)


def load_compiled_graph(graph_name: str, config_path: Optional[Union[str, Path]] = None):
    """
    Load a compiled graph from the configured path.
    
    Args:
        graph_name: Name of the graph to load
        config_path: Optional path to a custom config file
    
    Returns:
        Compiled graph or None if not found
    """
    compiled_path = get_compiled_graphs_path(config_path) / f"{graph_name}.pkl"
    if compiled_path.exists():
        logger.debug(f"[RUN] Using compiled graph: {compiled_path}")
        with open(compiled_path, "rb") as f:
            return pickle.load(f)
    else:
        logger.debug(f"[RUN] Compiled graph not found: {compiled_path}")
    return None


def autocompile_and_load(graph_name: str, config_path: Optional[Union[str, Path]] = None):
    """
    Compile and load a graph.
    
    Args:
        graph_name: Name of the graph to compile and load
        config_path: Optional path to a custom config file
    
    Returns:
        Compiled graph
    """
    from agentmap.compiler import compile_graph
    logger.debug(f"[RUN] Autocompile enabled. Compiling: {graph_name}")
    compile_graph(graph_name, config_path=config_path)
    return load_compiled_graph(graph_name, config_path=config_path)


def build_graph_in_memory(graph_name: str, csv_path: str, config_path: Optional[Union[str, Path]] = None):
    """
    Build a graph in memory from CSV with execution logging.
    
    Args:
        graph_name: Name of the graph to build
        csv_path: Path to the CSV file
        config_path: Optional path to a custom config file
    
    Returns:
        Compiled graph with logging wrappers
    """
    logger.debug(f"[BuildGraph] Building graph in memory: {graph_name}")
    csv = csv_path or get_csv_path(config_path)
    gb = GraphBuilder(csv)
    logger.debug(f"[BuildGraph] Building graph in memory: {csv}")
    graphs = gb.build()
    graph_def = graphs.get(graph_name)
    if not graph_def:
        raise ValueError(f"[BuildGraph] No graph found with name: {graph_name}")

    # Create the StateGraph builder
    builder = StateGraph(dict)
    
    # Create the graph assembler
    assembler = GraphAssembler(builder, config_path=config_path)
    
    # Add all nodes to the graph
    for node in graph_def.values():
        logger.debug(f"[AgentInit] resolving agent class for {node.name} with type {node.agent_type}")
        agent_cls = resolve_agent_class(node.agent_type, config_path)
        
        # Create context with input/output field information
        context = {
            "input_fields": node.inputs,
            "output_field": node.output
        }
        
        logger.debug(f"[AgentInit] Instantiating {agent_cls.__name__} as node '{node.name}'")
        agent_instance = agent_cls(name=node.name, prompt=node.prompt or "", context=context)
        
        # Add node to the graph
        assembler.add_node(node.name, agent_instance)

    # Set entry point
    assembler.set_entry_point(next(iter(graph_def)))
    
    # Process edges for all nodes
    for node_name, node in graph_def.items():
        assembler.process_node_edges(node_name, node.edges)
    
    # Add special handling for orchestrator nodes
    add_dynamic_routing(builder, graph_def)

    # Compile and return the graph
    return assembler.compile()


def add_dynamic_routing(builder: StateGraph, graph_def: Dict[str, Any]) -> None:
    """
    Add dynamic routing support for orchestrator nodes.
    
    Args:
        builder: StateGraph builder
        graph_def: Graph definition
    """
    # Find orchestrator nodes
    orchestrator_nodes = []
    for node_name, node in graph_def.items():
        if node.agent_type and node.agent_type.lower() == "orchestrator":
            orchestrator_nodes.append(node_name)
    
    if not orchestrator_nodes:
        return
    
    # For each orchestrator node, add a dynamic edge handler
    for node_name in orchestrator_nodes:
        logger.debug(f"[DynamicRouting] Adding dynamic routing for node: {node_name}")
        
        def dynamic_router(state, node=node_name):
            """Route based on __next_node value in state."""
            # Check if __next_node is set
            next_node = StateAdapter.get_value(state, "__next_node")
            
            if next_node:
                # Clear the next_node field to prevent loops
                state = StateAdapter.set_value(state, "__next_node", None)
                logger.debug(f"[DynamicRouter] Routing from {node} to {next_node}")
                return next_node
            
            # If there are standard edges defined, let them handle routing
            return None
        
        # Add a conditional edge with our dynamic router
        builder.add_conditional_edges(node_name, dynamic_router)


def resolve_agent_class(agent_type: str, config_path: Optional[Union[str, Path]] = None):
    """
    Get an agent class by type, with fallback to custom agents.
    
    Args:
        agent_type: Type of agent to resolve
        config_path: Optional path to a custom config file
        
    Returns:
        Agent class
    
    Raises:
        ValueError: If agent type cannot be resolved
    """
    logger.debug(f"[AgentInit] resolving agent class for type '{agent_type}'")
    
    agent_type_lower = agent_type.lower() if agent_type else ""
    
    # Check LLM agent types
    if not HAS_LLM_AGENTS and agent_type_lower in ("openai", "anthropic", "google", "gpt", "claude", "gemini", "llm"):
        raise ImportError(f"LLM agent '{agent_type}' requested but LLM dependencies are not installed. "
                         "Install with: pip install agentmap[llm]")
    
    # Check storage agent types
    if not HAS_STORAGE_AGENTS and agent_type_lower in ("csv_reader", "csv_writer", "json_reader", "json_writer", 
                                                      "file_reader", "file_writer", "vector_reader", "vector_writer"):
        raise ImportError(f"Storage agent '{agent_type}' requested but storage dependencies are not installed. "
                         "Install with: pip install agentmap[storage]")

    
    # Handle empty or None agent_type - default to DefaultAgent
    if not agent_type or agent_type_lower == "none":
        logger.debug("[AgentInit] Empty or None agent type, defaulting to DefaultAgent")
        from agentmap.agents.builtins.default_agent import DefaultAgent
        return DefaultAgent
    
    agent_class = get_agent_class(agent_type)
    if agent_class:
        logger.debug(f"[AgentInit] Using built-in agent class: {agent_class.__name__}")
        return agent_class
        
    # Try to load from custom agents path
    custom_agents_path = get_custom_agents_path(config_path)
    logger.debug(f"[AgentInit] Custom agents path: {custom_agents_path}")    
    # Convert file path to module path
    module_path = str(custom_agents_path).replace("/", ".").replace("\\", ".")
    if module_path.endswith("."):
        module_path = module_path[:-1]
    
    # Try to import the custom agent
    try:
        modname = f"{module_path}.{agent_type.lower()}_agent"
        classname = f"{agent_type}Agent"
        module = __import__(modname, fromlist=[classname])
        logger.debug(f"[AgentInit] Imported custom agent module: {modname}")
        logger.debug(f"[AgentInit] Using custom agent class: {classname}")
        agent_class = getattr(module, classname)
        return agent_class
    
    except (ImportError, AttributeError) as e:
        errorMessage = f"[AgentInit] Failed to import custom agent '{agent_type}': {e}"
        logger.error(errorMessage)
        raise AgentInitializationError(errorMessage)


def run_graph(
    graph_name: str, 
    initial_state: dict, 
    csv_path: str = None, 
    autocompile_override: bool = None,
    config_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """
    Run a graph with the given initial state.
    
    Args:
        graph_name: Name of the graph to run
        initial_state: Initial state for the graph 
        csv_path: Optional path to CSV file
        autocompile_override: Override autocompile setting
        config_path: Optional path to a custom config file
        
    Returns:
        Output from the graph execution
    """
    from agentmap.logging.tracing import trace_graph
    
    config = load_config(config_path)
    autocompile = autocompile_override if autocompile_override is not None else config.get("autocompile", False)
    execution_config = config.get("execution", {})
    tracking_config = execution_config.get("tracking", {})
    tracking_enabled = tracking_config.get("enabled", True)

    logger.info(f"⭐ STARTING GRAPH: '{graph_name}'")
    
    # Initialize execution tracking (always active, may be minimal)
    initial_state = StateAdapter.initialize_execution_tracker(initial_state, execution_config)
    
    # Use trace_graph context manager to conditionally enable tracing
    with trace_graph(graph_name):
        # Try to load a compiled graph first
        graph = load_compiled_graph(graph_name, config_path)

        # If autocompile is enabled, compile and load the graph
        if not graph and autocompile:
            graph = autocompile_and_load(graph_name, config_path)
        
        # If still no graph, build it in memory
        if not graph:
            graph = build_graph_in_memory(graph_name, csv_path, config_path)
        
        # Get the graph definition for node registry
        csv_file = csv_path or get_csv_path(config_path)
        gb = GraphBuilder(csv_file)
        graphs = gb.build()
        graph_def = graphs.get(graph_name)
        
        # Build node registry and populate orchestrator inputs
        if graph_def:
            node_registry = build_node_registry(graph_def)
            initial_state = populate_orchestrator_inputs(initial_state, graph_def, node_registry)
        
        # Track overall execution time
        start_time = time.time()
        
        try:
            result = graph.invoke(initial_state)
            execution_time = time.time() - start_time
            
            # Process execution results
            tracker = StateAdapter.get_execution_tracker(result)
            tracker.complete_execution()
            summary = tracker.get_summary()
            
            # Store summary in result
            result = StateAdapter.set_value(result, "__execution_summary", summary)
            
            # The graph_success field is already updated during execution
            graph_success = summary["graph_success"]
            # For backwards compatibility
            result = StateAdapter.set_value(result, "__policy_success", graph_success)
            
            # Log result with different detail based on tracking mode
            if tracking_enabled:
                logger.info(f"✅ COMPLETED GRAPH: '{graph_name}' in {execution_time:.2f}s")
                logger.info(f"  Policy success: {graph_success}, Raw success: {summary['overall_success']}")
            else:
                logger.info(f"✅ COMPLETED GRAPH: '{graph_name}' in {execution_time:.2f}s, Success: {graph_success}")
                
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ GRAPH EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s")
            logger.error(f"[RUN] Error: {str(e)}")
            raise
