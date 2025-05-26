"""
Graph runner for executing AgentMap workflows from compiled graphs or CSV.
"""

import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import threading
import logging

from langgraph.graph import StateGraph

#from agentmap.config import (get_compiled_graphs_path, get_csv_path, get_custom_agents_path, load_config)
from agentmap.exceptions import AgentInitializationError
from agentmap.graph import GraphAssembler
from agentmap.graph.builder import GraphBuilder
from agentmap.services.node_registry_service import NodeRegistryService
from agentmap.state.adapter import StateAdapter
from agentmap.agents import get_agent_class
from dependency_injector.wiring import inject, Provide
from agentmap.di.containers import ApplicationContainer
from agentmap.config.configuration import Configuration
from agentmap.logging.service import LoggingService
from agentmap.logging.tracking.execution_tracker import ExecutionTracker 
from agentmap.services import LLMService, LLMServiceUser
from agentmap.services.storage.manager import StorageServiceManager
from agentmap.services.storage.injection import inject_storage_services, requires_storage_services


_GRAPH_EXECUTION_LOCK = threading.RLock()
_CURRENT_EXECUTIONS = set()

@inject
def load_compiled_graph(
        graph_name: str,
        configuration: Configuration = Provide[ApplicationContainer.configuration],
        logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
):
    """
    Load a compiled graph bundle from the configured path.
    
    Args:
        graph_name: Name of the graph to load
    
    Returns:
        Graph bundle dictionary or legacy graph object
    """
    logger = logging_service.get_logger("agentmap.runner")
    compiled_path = configuration.get_compiled_graphs_path() / f"{graph_name}.pkl"
    if compiled_path.exists():
        logger.debug(f"[RUN] Loading compiled graph: {compiled_path}")
        
        # Use GraphBundle to load
        from agentmap.graph.bundle import GraphBundle
        bundle = GraphBundle.load(compiled_path, logger)
        
        if bundle:
            if bundle.graph:
                # Return the bundle as a dictionary
                return bundle.to_dict()
        
        # Legacy fallback - try direct load
        try:
            with open(compiled_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"[RUN] Error loading graph directly: {e}")
    else:
        logger.debug(f"[RUN] Compiled graph not found: {compiled_path}")
    
    return None

@inject
def autocompile_and_load(
    graph_name: str, 
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
):
    """
    Compile and load a graph.
    
    Args:
        graph_name: Name of the graph to compile and load
        config_path: Optional path to a custom config file
    
    Returns:
        Compiled graph bundle or legacy graph
    """
    logger = logging_service.get_logger("agentmap.runner")

    from agentmap.compiler import compile_graph
    logger.debug(f"[RUN] Autocompile enabled. Compiling: {graph_name}")
    compile_graph(graph_name)

    return load_compiled_graph(graph_name)

@inject
def build_graph_in_memory(
    graph_name: str, 
    graph_def: Dict[str, Any], 
    logging_service: LoggingService,
    node_registry_service: NodeRegistryService,
    llm_service: LLMService,
    storage_service_manager: StorageServiceManager
):
    """
    Build a graph in memory from pre-loaded graph definition with service injection.
    
    Args:
        graph_name: Name of the graph to build
        graph_def: Pre-loaded graph definition from GraphBuilder
        logging_service: Logging service
        node_registry_service: Node registry service for pre-compilation injection
        llm_service: LLM service for injection into agents
        storage_service_manager: Storage service manager for injection into agents
    
    Returns:
        Compiled graph with pre-injected services
    """
    logger = logging_service.get_logger("agentmap.runner")
    logger.debug(f"[BuildGraph] Building graph in memory: {graph_name}")
    
    if not graph_def:
        raise ValueError(f"[BuildGraph] Invalid or empty graph definition for graph: {graph_name}")

    # Build node registry BEFORE creating assembler
    logger.debug(f"[BuildGraph] Preparing node registry for: {graph_name}")
    node_registry = node_registry_service.prepare_for_assembly(graph_def, graph_name)

    # Create the StateGraph builder
    builder = StateGraph(dict)
    
    # Create assembler WITH node registry for pre-compilation injection
    assembler = GraphAssembler(builder, node_registry=node_registry)
    
    # Add all nodes to the graph (registry injection happens automatically in add_node)
    for node in graph_def.values():
        logger.debug(f"[AgentInit] resolving agent class for {node.name} with type {node.agent_type}")
        agent_cls = resolve_agent_class(node.agent_type)
        
        # Create context with input/output field information
        context = {
            "input_fields": node.inputs,
            "output_field": node.output,
            "description": node.description or ""
        }

        logger.debug(f"[AgentInit] Instantiating {agent_cls.__name__} as node '{node.name}'")

        
        agent_instance = agent_cls(name=node.name, prompt=node.prompt or "", context=context)

        # Inject LLM service if agent requires it
        if isinstance(agent_instance, LLMServiceUser):
            agent_instance.llm_service = llm_service
            logger.debug(f"[AgentInit] Injected LLM service into {node.name}")
        
        # Inject storage services if agent requires them
        if requires_storage_services(agent_instance):
            inject_storage_services(agent_instance, storage_service_manager, logger)
        
        # Add node to the graph (this triggers automatic registry injection for orchestrators)
        assembler.add_node(node.name, agent_instance)

    # Set entry point
    assembler.set_entry_point(next(iter(graph_def)))
    
    # Process edges for all nodes
    for node_name, node in graph_def.items():
        assembler.process_node_edges(node_name, node.edges)
    
    # Verify that pre-compilation injection worked
    verification = node_registry_service.verify_pre_compilation_injection(assembler)
    if not verification["all_injected"] and verification["has_orchestrators"]:
        logger.warning(f"[BuildGraph] Pre-compilation injection incomplete for graph '{graph_name}'")
        logger.warning(f"[BuildGraph] Stats: {verification['stats']}")

    # Compile and return the graph
    compiled_graph = assembler.compile()
    
    logger.info(f"[BuildGraph] ✅ Successfully built graph '{graph_name}' with pre-compilation registry injection")
    return compiled_graph

@inject
def add_dynamic_routing(
        builder: StateGraph, 
        graph_def: Dict[str, Any],
        logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
    ) -> None:
    """
    Add dynamic routing support for orchestrator nodes.
    
    Args:
        builder: StateGraph builder
        graph_def: Graph definition
    """

    logger = logging_service.get_logger("agentmap.runner")
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
        
        def dynamic_router(state, dynamic_node=node_name):
            """Route based on __next_node value in state."""
            # Check if __next_node is set
            next_node = StateAdapter.get_value(state, "__next_node")
            
            if next_node:
                # Clear the next_node field to prevent loops
                state = StateAdapter.set_value(state, "__next_node", None)
                logger.debug(f"[DynamicRouter] Routing from {dynamic_node} to {next_node}")
                return next_node
            
            # If there are standard edges defined, let them handle routing
            return None
        
        # Add a conditional edge with our dynamic router
        builder.add_conditional_edges(node_name, dynamic_router)


@inject
def resolve_agent_class(
        agent_type: str, 
        configuration: Configuration = Provide[ApplicationContainer.configuration],
        logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
    ):
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
    logger = logging_service.get_logger("agentmap.runner")
    logger.debug(f"[AgentInit] resolving agent class for type '{agent_type}'")
    
    from agentmap.features_registry import features
    from agentmap.agents.dependency_checker import get_llm_installation_guide, check_llm_dependencies
    
    agent_type_lower = agent_type.lower() if agent_type else ""
    
    # Handle empty or None agent_type - default to DefaultAgent
    if not agent_type or agent_type_lower == "none":
        logger.debug("[AgentInit] Empty or None agent type, defaulting to DefaultAgent")
        from agentmap.agents.builtins.default_agent import DefaultAgent
        return DefaultAgent
    
    # Check LLM agent types
    if agent_type_lower in ("openai", "anthropic", "google", "gpt", "claude", "gemini", "llm"):
        llm_enabled = features.is_feature_enabled("llm")
        logger.debug(f"[AgentInit] LLM feature enabled: {llm_enabled}")
        
        if not llm_enabled:
            # Double-check dependencies directly
            has_deps, missing = check_llm_dependencies()
            if not has_deps:
                missing_str = ", ".join(missing) if missing else "required dependencies"
                raise ImportError(
                    f"LLM agent '{agent_type}' requested but LLM dependencies are not installed. "
                    f"Missing: {missing_str}. Install with: pip install agentmap[llm]"
                )
        
        # Handle base LLM case
        if agent_type_lower == "llm":
            agent_class = get_agent_class("llm")
            if agent_class:
                return agent_class
            raise ImportError(
                "Base LLM agent requested but not available. "
                "Install with: pip install agentmap[llm]"
            )
        
        # Check specific provider - be extra careful with validation
        provider = agent_type_lower
        if provider in ("gpt", "claude", "gemini"):
            provider = {"gpt": "openai", "claude": "anthropic", "gemini": "google"}[provider]
        
        # Validate provider directly
        has_provider_deps, missing_provider = check_llm_dependencies(provider)
        
        if not has_provider_deps:
            guide = get_llm_installation_guide(provider)
            raise ImportError(
                f"LLM agent '{agent_type}' requested but dependencies are not available. "
                f"Missing: {', '.join(missing_provider)}. Install with: {guide}"
            )
        
        # If we get here, dependencies should be available, so get the agent class
        agent_class = get_agent_class(agent_type)
        if agent_class:
            return agent_class
        
        # If we still failed, something unexpected happened
        raise ImportError(
            f"LLM agent '{agent_type}' requested. Dependencies are available "
            f"but agent class could not be loaded. This might be a registration issue."
        )
    
    # Check storage agent types - similar approach
    if agent_type_lower in ("csv_reader", "csv_writer", "json_reader", "json_writer", 
                            "file_reader", "file_writer", "vector_reader", "vector_writer"):
        storage_enabled = features.is_feature_enabled("storage")
        
        if not storage_enabled:
            # Additional direct validation
            from agentmap.agents.dependency_checker import check_storage_dependencies
            has_deps, missing = check_storage_dependencies()
            
            if not has_deps:
                missing_str = ", ".join(missing) if missing else "required dependencies"
                raise ImportError(
                    f"Storage agent '{agent_type}' requested but storage dependencies are not installed. "
                    f"Missing: {missing_str}. Install with: pip install agentmap[storage]"
                )
    
    # Get agent class from registry
    agent_class = get_agent_class(agent_type)
    if agent_class:
        logger.debug(f"[AgentInit] Using built-in agent class: {agent_class.__name__}")
        return agent_class
        
    # Try to load from custom agents path
    custom_agents_path = configuration.get_custom_agents_path()
    logger.debug(f"[AgentInit] Custom agents path: {custom_agents_path}")    
    
    # Add custom agents path to sys.path if not already present
    import sys
    from pathlib import Path
    custom_agents_path_str = str(custom_agents_path)
    if custom_agents_path_str not in sys.path:
        sys.path.insert(0, custom_agents_path_str)
    
    # Try to import the custom agent
    try:
        # The file is expected to be named <agent_type>_agent.py, class is <AgentType>Agent
        modname = f"{agent_type.lower()}_agent"
        classname = f"{agent_type}Agent"
        module = __import__(modname, fromlist=[classname])
        logger.debug(f"[AgentInit] Imported custom agent module: {modname}")
        logger.debug(f"[AgentInit] Using custom agent class: {classname}")
        agent_class = getattr(module, classname)
        return agent_class
    
    except (ImportError, AttributeError) as e:
        error_message = f"[AgentInit] Failed to import custom agent '{agent_type}': {e}"
        logger.error(error_message)
        raise AgentInitializationError(error_message)
    


@inject
def run_graph(
    graph_name: Optional[str] = None, 
    initial_state: Optional[dict] = {}, 
    csv_path: Optional[str] = None, 
    autocompile_override: Optional[bool] = None,
    configuration: Configuration = Provide[ApplicationContainer.configuration],
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service],
    node_registry_service: NodeRegistryService = Provide[ApplicationContainer.node_registry_service],
    llm_service: LLMService = Provide[ApplicationContainer.llm_service],
    storage_service_manager: StorageServiceManager = Provide[ApplicationContainer.storage_service_manager]
) -> Dict[str, Any]:
    """
    Run a graph with the given initial state.
    
    Args:
        graph_name: Name of the graph to run. If None, uses the first graph in the CSV.
        initial_state: Initial state for the graph. If None, uses an empty dictionary.
        csv_path: Optional path to CSV file
        autocompile_override: Override autocompile setting
        config_path: Optional path to a custom config file
        
    Returns:
        Output from the graph execution
    """
    # Create a unique execution key based on the parameters
    import inspect
    import traceback

    logger = logging_service.get_logger("agentmap.runner")
    state = initial_state or {}

    caller_frame = inspect.currentframe().f_back
    caller_info = f"{caller_frame.f_code.co_filename}:{caller_frame.f_lineno}"
    logger.trace(f"\n===== RUN_GRAPH CALLED FROM: {caller_info} =====")
    logger.trace("STACK TRACE:")
    for line in traceback.format_stack()[:-1]:  # Exclude this frame
        logger.trace(f"  {line.strip()}")
    logger.trace("=====\n")

    import sys
    agentmap_modules = [mod for mod in sys.modules.keys() if mod.startswith('agentmap')]
    logger.trace(f"LOADED AGENTMAP MODULES: {len(agentmap_modules)}")
    for mod in sorted(agentmap_modules):
        logger.trace(f"  {mod}")

    logger.trace("\n=== ENTERING run_graph ===")
    logger.trace(f"Parameters: graph_name={graph_name}, csv_path={csv_path}")
    logger.trace("=====\n")


    import hashlib
    execution_key = hashlib.md5(
        f"{graph_name}:{id(state)}:{csv_path}:{autocompile_override}".encode()
    ).hexdigest()
    
    with _GRAPH_EXECUTION_LOCK:
        # Check if this exact execution is already in progress
        if execution_key in _CURRENT_EXECUTIONS:
            logger.warning(f"[RUN] Detected recursive/duplicate call to run_graph with same parameters")
            # Return a placeholder to break the recursion
            return {"error": "Recursive execution detected and prevented"}
        
        _CURRENT_EXECUTIONS.add(execution_key)
    
    try:
        from agentmap.logging.tracing import trace_graph

        # Set defaults for optional parameters
        autocompile = autocompile_override if autocompile_override is not None else configuration.get_value("autocompile", False)

        execution_config = configuration.get_section("execution")
        tracking_config = execution_config.get("tracking", {})
        tracking_enabled = tracking_config.get("enabled", True)

        #initialize variables
        graph_bundle = None
        node_registry = None
        graph = None
        graph_def = None

        # Get the CSV file path
        csv_file = csv_path or configuration.get_csv_path()

        import inspect
        frame = inspect.currentframe()
        caller_info = inspect.getframeinfo(frame.f_back)

        logger.info(f"⭐ STARTING GRAPH: '{graph_name}'")
        
        # Initialize execution tracking (always active, may be minimal)
        tracker, state = get_execution_tracker(state, configuration.get_tracking_config(), configuration.get_execution_config(), logger)
        
        # Use trace_graph context manager to conditionally enable tracing
        with trace_graph(graph_name):
            # Try to load a compiled graph first - may include bundled node registry
            if graph_name:
                graph_bundle = load_compiled_graph(graph_name)
            
            if graph_bundle:
                graph, node_registry = load_from_compiled_graph(graph, graph_bundle, node_registry)

            # If autocompile is enabled, and we don't have a graph, compile and load
            if not graph and autocompile and graph_name:
                graph, node_registry = compile_and_load(graph, graph_name, node_registry)

            # If we still don't have a graph, need to load CSV and build graph
            if not graph:
                # Load the CSV file and parse graph definition only once
                graph_def, graph_name = read_graph_definition_and_get_graph_name(csv_file, graph_name)

                # NEW: Build graph in memory with pre-compilation registry injection
                # The registry is built and injected during assembly, not after compilation
                graph = build_graph_in_memory(graph_name, graph_def, logging_service, node_registry_service, llm_service, storage_service_manager)
                
                # Note: No need to call inject_into_orchestrators here since it's done during assembly
                logger.debug(f"[RUN] Graph built with pre-compilation registry injection")

            # REMOVED: No longer need post-compilation injection for normal cases
            # The registry injection happens during assembly now
                        
            # Track overall execution time
            start_time = time.time()
            
            try:
                logger.trace(f"\n=== BEFORE INVOKING GRAPH: {graph_name or 'unnamed'} ===")
                result = graph.invoke(state)  # Use state directly, no modification needed
                logger.trace(f"\n=== AFTER INVOKING GRAPH: {graph_name or 'unnamed'} ===")
                execution_time = time.time() - start_time
                
                # Process execution results
                # tracker = StateAdapter.get_execution_tracker(result)
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

                # pretty logger.trace the result
                logger.trace("\n=== EXITING run_graph ===")
                logger.trace(f"Parameters: graph_name={graph_name}, csv_path={csv_path}")
                logger.trace("=====\n")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ GRAPH EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s")
                logger.error(f"[RUN] Error: {str(e)}")
                raise
    finally:
        with _GRAPH_EXECUTION_LOCK:
            _CURRENT_EXECUTIONS.remove(execution_key)

@inject
def read_graph_definition_and_get_graph_name(
    csv_file, 
    graph_name,
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
):
    logger = logging_service.get_logger("agentmap.runner")
    logger.debug(f"[RUN] Loading graph from CSV file: {csv_file}")
    gb = GraphBuilder(csv_file)
    graphs = gb.build()
    if not graph_name:  # Use the first graph in the CSV
        graph_name = list(graphs.keys())[0] if graphs else None
        if not graph_name:
            raise ValueError("No graphs found in CSV file")
        logger.debug(f"[RUN] Loaded first graph name from CSV: {graph_name}")
    graph_def = graphs.get(graph_name)
    if not graph_def:
        raise ValueError(f"[RUN] No graph found with name: {graph_name}")
    return graph_def, graph_name

@inject
def compile_and_load(
    graph, 
    graph_name, 
    node_registry,
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
):
    logger = logging_service.get_logger("agentmap.runner")

    graph_bundle = autocompile_and_load(graph_name)
    if isinstance(graph_bundle, dict) and "graph" in graph_bundle:
        graph = graph_bundle.get("graph")
        node_registry = graph_bundle.get("node_registry")
        version_hash = graph_bundle.get("version_hash")
        logger.debug(f"[RUN] Autocompiled graph with version hash: {version_hash}")
    else:
        raise ValueError(f"Failed to autocompile and load graph: {graph_name}")
    return graph, node_registry

@inject
def load_from_compiled_graph(
    graph, 
    graph_bundle, 
    node_registry,
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
):
    logger = logging_service.get_logger("agentmap.runner")
    logger.debug(f"[RUN] Loaded compiled graph bundle: {graph_bundle}")
    # If we loaded a bundle, extract the components
    if isinstance(graph_bundle, dict) and "graph" in graph_bundle:
        # New format with bundled components
        graph = graph_bundle.get("graph")
        node_registry = graph_bundle.get("node_registry")
        version_hash = graph_bundle.get("version_hash")
        logger.debug(f"[RUN] Loaded bundled graph with version hash: {version_hash}")
    else:
        # Old format with just the graph
        graph = graph_bundle
        logger.debug(f"[RUN] Loaded legacy compiled graph (no bundled registry)")
    return graph, node_registry

@inject
def get_graph(
    autocompile, 
    csv_path, 
    graph_name
):
    # Try to load a compiled graph first
    graph = load_compiled_graph(graph_name)
    # If autocompile is enabled, compile and load the graph
    if not graph and autocompile:
        graph = autocompile_and_load(graph_name)
    # If still no graph, build it in memory
    if not graph:
        graph = build_graph_in_memory(graph_name, csv_path)
    return graph

def create_serializable_result(result):
    """Create a JSON-serializable copy of the result dictionary."""
    if not isinstance(result, dict):
        return {"result": str(result)}
    
    serializable = {}
    for key, value in result.items():
        # Skip ExecutionTracker objects
        if key == "__execution_tracker":
            continue
        # Include other values, converting non-serializable ones to strings
        try:
            # Test if it's JSON serializable
            json.dumps(value)
            serializable[key] = value
        except (TypeError, OverflowError):
            serializable[key] = str(value)
    
    return serializable

def get_execution_tracker(state: Any, tracker_config, execution_config, logger) -> Tuple[ExecutionTracker, Any]:
    """
    Get the execution tracker from state.
    
    Args:
        state: Current state
        
    Returns:
        ExecutionTracker instance or None
    """
    execution_tracker = StateAdapter.get_value(state, "__execution_tracker")
    if execution_tracker is None:
        execution_tracker = ExecutionTracker(tracker_config, execution_config, logger)
        state = StateAdapter.set_value(state, "__execution_tracker", execution_tracker)

    return execution_tracker, state