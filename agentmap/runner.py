# agentmap/runner.py

"""
Graph runner for executing AgentMap workflows from compiled graphs or CSV.
"""
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from langgraph.graph import StateGraph

from agentmap.agents import get_agent_class
from agentmap.config import (get_compiled_graphs_path, get_csv_path,
                             get_custom_agents_path, load_config)
from agentmap.exceptions import AgentInitializationError
from agentmap.graph import GraphAssembler
from agentmap.graph.builder import GraphBuilder
from agentmap.logging import get_logger

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
    logger.debug(f"[RUN] Building graph in memory: {graph_name}")
    csv = csv_path or get_csv_path(config_path)
    gb = GraphBuilder(csv)
    logger.debug(f"[RUN] Building graph in memory: {csv}")
    graphs = gb.build()
    graph_def = graphs.get(graph_name)
    if not graph_def:
        raise ValueError(f"No graph found with name: {graph_name}")

    # Create the StateGraph builder
    builder = StateGraph(dict)
    
    # Create the graph assembler
    assembler = GraphAssembler(builder, config_path=config_path, enable_logging=True)
    
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

    # Compile and return the graph
    return assembler.compile()


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
    
    # Handle empty or None agent_type - default to DefaultAgent
    if not agent_type or agent_type.lower() == "none":
        logger.debug("[AgentInit] Empty or None agent type, defaulting to DefaultAgent")
        from agentmap.agents.builtins.default_agent import DefaultAgent
        return DefaultAgent
    
    agent_class = get_agent_class(agent_type)
    if agent_class:
        logger.debug(f"[AgentInit] Using built-in agent class: {agent_class.__name__}")
        return agent_class
        
    # Try to load from custom agents path
    custom_agents_path = get_custom_agents_path(config_path)
    logger.trace(f"[AgentInit] Custom agents path: {custom_agents_path}")    
    # Convert file path to module path
    module_path = str(custom_agents_path).replace("/", ".").replace("\\", ".")
    if module_path.endswith("."):
        module_path = module_path[:-1]
    
    # Try to import the custom agent
    try:
        modname = f"{module_path}.{agent_type.lower()}_agent"
        classname = f"{agent_type}Agent"
        module = __import__(modname, fromlist=[classname])
        logger.trace(f"[AgentInit] Imported custom agent module: {modname}")
        logger.trace(f"[AgentInit] Using custom agent class: {classname}")
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
    config = load_config(config_path)
    autocompile = autocompile_override if autocompile_override is not None else config.get("autocompile", False)

    logger.info(f"[RUN] ⭐ STARTING GRAPH: '{graph_name}'")
    logger.info(f"[RUN] Initial state: {initial_state}") 
    logger.info(f"[RUN] Autocompile: {autocompile}")    
    logger.info(f"[RUN] CSV path: {csv_path}")    
    logger.info(f"[RUN] Config path: {config_path}")

    # Try to load a compiled graph first
    graph = load_compiled_graph(graph_name, config_path)
    if graph:
        logger.debug(f"[RUN] Loaded compiled graph: {graph_name}")
    # If autocompile is enabled, compile and load the graph
    elif autocompile:
        logger.debug(f"[RUN] Autocompile enabled. Compiling: {graph_name}")
        graph = autocompile_and_load(graph_name, config_path)
    else:
        # Otherwise, build the graph in memory
        logger.debug(f"[RUN] Building graph in memory: {graph_name}")
        graph = build_graph_in_memory(graph_name, csv_path, config_path)

    # Run the graph with the initial state
    logger.debug(f"[RUN] Executing graph: {graph_name}")
    
    # Track overall execution time
    start_time = time.time()
    
    try:
        result = graph.invoke(initial_state)
        execution_time = time.time() - start_time
        
        logger.info(f"[RUN] ✅ COMPLETED GRAPH: '{graph_name}' in {execution_time:.2f}s")
        return result
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"[RUN] ❌ GRAPH EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s")
        logger.error(f"[RUN] Error: {str(e)}")
        raise