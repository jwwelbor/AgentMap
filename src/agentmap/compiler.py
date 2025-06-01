"""
Graph compiler for AgentMap.
Compiles LangGraph workflows to .pkl and exports flattened .src files.
"""

import os
from pathlib import Path
from typing import Optional, Any, Dict, List

from langgraph.graph import StateGraph

from agentmap.graph.builder import GraphBuilder
from agentmap.utils.common import extract_func_ref, import_function
from agentmap.agents import get_agent_class
from agentmap.services.logging_service import LoggingService
from agentmap.services.node_registry_service import NodeRegistryService
from agentmap.graph import GraphAssembler  # Import GraphAssembler

from dependency_injector.wiring import inject, Provide
from agentmap.di.containers import ApplicationContainer
from agentmap.services.config.app_config_service import AppConfigService

def resolve_state_schema(state_schema: str) -> tuple:
    """
    Resolve the state schema to use for graph compilation.
    
    Args:
        state_schema: State schema type ("dict", "pydantic:<ModelName>", etc.)
        
    Returns:
        tuple: (schema_object, schema_code, schema_imports)
    """
    schema_code = "dict"  # Default to dict
    schema_imports = []
    
    if state_schema.startswith("pydantic:"):
        # Extract the model name
        model_name = state_schema.split(":", 1)[1]
        schema_code = model_name
        schema_imports.append(f"from agentmap.models.{model_name.lower()} import {model_name}")
        # We can't evaluate this directly here, so return None and let the client handle import
        return None, schema_code, schema_imports
    elif state_schema == "dict":
        return dict, schema_code, schema_imports
    else:
        # Assume it's a custom schema
        schema_code = state_schema
        # Add an import if it seems like a class name (capital first letter)
        if state_schema[0].isupper():
            schema_imports.append(f"from agentmap.models import {state_schema}")
        # We can't evaluate this directly here, so return None and let the client handle import
        return None, schema_code, schema_imports

@inject
def get_graph_definition(
        graph_name: str, 
        csv_path: Optional[str] = None,
        configuration: AppConfigService = Provide[ApplicationContainer.app_config_service],
        logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
    ) -> Dict:
    """
    Get the graph definition from the CSV.
    
    Args:
        graph_name: Name of the graph to get
        csv_path: Optional override for the CSV file path
        config_path: Optional path to a custom config file
        
    Returns:
        Dictionary containing the graph definition
        
    Raises:
        ValueError: If graph not found
    """
    logger = logging_service.get_logger("agentmap.compiler")
    csv_file = csv_path or configuration.get_csv_path()
    logger.debug(f"[Compiler] Loading graph definition from CSV: {csv_file}")
    
    gb = GraphBuilder(csv_file)
    graphs = gb.build()

    graph_def = graphs.get(graph_name)
    if not graph_def:
        raise ValueError(f"No graph found with name: {graph_name}")
    
    return graph_def


@inject
def build_source_lines(
    graph_def: Dict, 
    state_schema: str = "dict", 
    configuration: AppConfigService = Provide[ApplicationContainer.app_config_service],
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
) -> List[str]:
    """
    Build the source lines for the graph.
    
    Args:
        graph_def: Graph definition
        state_schema: State schema type
        config_path: Optional path to a custom config file
        
    Returns:
        List of source lines
    """
    # Get schema information
    _, schema_code, schema_imports = resolve_state_schema(state_schema)
    
    # Start with standard imports and schema imports
    src_lines = [
        "from langgraph.graph import StateGraph",
        "from agentmap.agents.builtins.openai_agent import OpenAIAgent",
        "from agentmap.agents.builtins.anthropic_agent import AnthropicAgent",
        "from agentmap.agents.builtins.google_agent import GoogleAgent",
        "from agentmap.agents.builtins.echo_agent import EchoAgent",
        "from agentmap.agents.builtins.default_agent import DefaultAgent",
        "from agentmap.agents.builtins.success_agent import SuccessAgent",
        "from agentmap.agents.builtins.failure_agent import FailureAgent",
        "from agentmap.agents.builtins.branching_agent import BranchingAgent"
    ]
    
    # Add schema imports
    src_lines.extend(schema_imports)
    src_lines.append("")  # Blank line
    
    logger = logging_service.get_logger("agentmap.compiler")
    
    # Add function imports if needed
    functions_dir = configuration.get_functions_path()
    function_imports = []
    
    for node in graph_def.values():
        for condition, target in node.edges.items():
            func_ref = extract_func_ref(target)
            if func_ref:
                func_path = functions_dir / f"{func_ref}.py"
                if not func_path.exists():
                    logger.warning(f"[Compiler] Function '{func_ref}' referenced but not found at {func_path}")
                function_imports.append(f"from agentmap.functions.{func_ref} import {func_ref}")
    
    if function_imports:
        src_lines.extend(sorted(function_imports))
        src_lines.append("")  # Blank line
    
    # Add builder initialization
    src_lines.append(f"builder = StateGraph({schema_code})")
    
    # Add nodes
    for node in graph_def.values():
        agent_type = node.agent_type or "Default"
        agent_class_name = get_agent_class_name(agent_type)
        prompt = f'"{node.prompt}"' if node.prompt else '""'
        
        # Format node initialization
        node_line = f'builder.add_node("{node.name}", {agent_class_name}(name="{node.name}", prompt={prompt}))'
        src_lines.append(node_line)
    
    # Set entry point
    entry = next(iter(graph_def))
    src_lines.append(f'builder.set_entry_point("{entry}")')
    
    # Add edges
    src_lines.extend(build_edge_lines(graph_def))
    
    # Add graph compilation and usage example
    src_lines.append("")
    src_lines.append("graph = builder.compile()")
    src_lines.append('# Example: result = graph.invoke({"input": "Test input"})')
    
    return src_lines


def get_agent_class_name(agent_type: str) -> str:
    """
    Get the agent class name.
    
    Args:
        agent_type: Type of agent
        
    Returns:
        Agent class name
    """
    if not agent_type:
        return "DefaultAgent"
        
    agent_type = agent_type.lower()
    from agentmap.agents import AGENT_MAP
    
    if agent_type in AGENT_MAP:
        return AGENT_MAP[agent_type].__name__
    
    # Assume it's a custom agent
    return f"{agent_type.capitalize()}Agent"

@inject
def build_edge_lines(
        graph_def: Dict, 
        configuration: AppConfigService = Provide[ApplicationContainer.app_config_service]
) -> List[str]:
    """
    Build the edge source lines for the graph.
    
    Args:
        graph_def: Graph definition
        config_path: Optional path to a custom config file
        
    Returns:
        List of edge source lines
    """
    edge_lines = []
    functions_dir = configuration.get_functions_path()
    
    for node in graph_def.values():
        has_func = False
        
        # Check for function references first
        for condition, target in node.edges.items():
            func_ref = extract_func_ref(target)
            if func_ref:
                success = node.edges.get("success", "None")
                failure = node.edges.get("failure", "None")
                edge_lines.append(f'# Function-based conditional edge')
                edge_lines.append(f'builder.add_conditional_edges("{node.name}", lambda x: {func_ref}(x, "{success}", "{failure}"))')
                has_func = True
                break
        
        # If no function references, handle conditional edges
        if not has_func:
            if "success" in node.edges and "failure" in node.edges:
                success_target = node.edges["success"]
                failure_target = node.edges["failure"]
                edge_lines.append(f'# Conditional edge with success/failure routing')
                edge_lines.append(f'builder.add_conditional_edges("{node.name}", lambda state: "{success_target}" if state.get("last_action_success", True) else "{failure_target}")')
            elif "success" in node.edges:
                success_target = node.edges["success"]
                edge_lines.append(f'# Success-only conditional edge')
                edge_lines.append(f'builder.add_conditional_edges("{node.name}", lambda state: "{success_target}" if state.get("last_action_success", True) else None)')
            elif "failure" in node.edges:
                failure_target = node.edges["failure"]
                edge_lines.append(f'# Failure-only conditional edge')
                edge_lines.append(f'builder.add_conditional_edges("{node.name}", lambda state: "{failure_target}" if not state.get("last_action_success", True) else None)')
            elif "default" in node.edges:
                target = node.edges["default"]
                edge_lines.append(f'# Direct edge')
                edge_lines.append(f'builder.add_edge("{node.name}", "{target}")')
    
    return edge_lines


# NEW: Enhanced function that uses GraphAssembler with registry
@inject
def create_graph_builder_with_registry(
    graph_def: Dict, 
    node_registry: Dict[str, Dict[str, Any]],
    state_schema: str = "dict",
    configuration: AppConfigService = Provide[ApplicationContainer.app_config_service],
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
) -> tuple:
    """
    Create a StateGraph builder for the graph with pre-compilation registry injection.
    
    Args:
        graph_def: Graph definition
        node_registry: Node registry for orchestrator injection
        state_schema: State schema type
        
    Returns:
        tuple: (compiled_graph, source lines)
    """
    logger = logging_service.get_logger("agentmap.compiler")
    
    # Resolve the state schema
    schema_obj, _, _ = resolve_state_schema(state_schema)
    schema_obj = schema_obj or dict  # Default to dict if schema can't be resolved
    
    # Create the builder
    builder = StateGraph(schema_obj)
    
    # NEW: Create GraphAssembler with node registry for pre-compilation injection
    assembler = GraphAssembler(builder, node_registry=node_registry, enable_logging=True)
    
    # Build source lines for tracking
    src_lines = build_source_lines(graph_def, state_schema)
    
    # Add nodes to the builder (registry injection happens automatically)
    add_nodes_to_assembler(assembler, graph_def)
    
    # Set entry point
    entry = next(iter(graph_def))
    assembler.set_entry_point(entry)
    
    # Add edges to the builder
    add_edges_to_assembler(assembler, graph_def)
    
    # Compile the graph
    compiled_graph = assembler.compile()
    
    # Verify injection worked
    stats = assembler.get_injection_summary()
    if stats["orchestrators_found"] > 0:
        logger.info(f"[Compiler] Registry injection during compilation:")
        logger.info(f"   Orchestrators found: {stats['orchestrators_found']}")
        logger.info(f"   Successfully injected: {stats['orchestrators_injected']}")
        if stats["injection_failures"] > 0:
            logger.warning(f"   Injection failures: {stats['injection_failures']}")
    
    return compiled_graph, src_lines

def create_graph_builder(
    graph_def: Dict, 
    state_schema: str = "dict"
) -> tuple:
    """
    LEGACY: Create a StateGraph builder for the graph without registry.
    
    This is kept for backward compatibility but should use create_graph_builder_with_registry instead.
    
    Args:
        graph_def: Graph definition
        state_schema: State schema type
        
    Returns:
        tuple: (builder, source lines)
    """
    # Resolve the state schema
    schema_obj, _, _ = resolve_state_schema(state_schema)
    schema_obj = schema_obj or dict  # Default to dict if schema can't be resolved
    
    # Create the builder
    builder = StateGraph(schema_obj)
    
    # Build source lines for tracking
    src_lines = build_source_lines(graph_def, state_schema)
    
    # Add nodes to the builder
    add_nodes_to_builder(builder, graph_def)
    
    # Set entry point
    entry = next(iter(graph_def))
    builder.set_entry_point(entry)
    
    # Add edges to the builder
    add_edges_to_builder(builder, graph_def)
    
    return builder, src_lines

# NEW: Function that uses GraphAssembler
def add_nodes_to_assembler(
    assembler: GraphAssembler, 
    graph_def: Dict
) -> None:
    """
    Add nodes to the GraphAssembler (with automatic registry injection).
    
    Args:
        assembler: GraphAssembler instance with registry
        graph_def: Graph definition
    """
    for node in graph_def.values():
        agent_class = get_agent_class(node.agent_type)
        if agent_class:
            # Create context with input/output field information
            context = {
                "input_fields": node.inputs,
                "output_field": node.output,
                "description": node.description or ""
            }
            agent_instance = agent_class(name=node.name, prompt=node.prompt or "", context=context)
        else:
            # Try to load from custom agents path - simplified for now
            # This could be enhanced to use the same logic as in runner
            raise ValueError(f"Could not load agent type '{node.agent_type}' during compilation")
                
        # Add node to assembler (automatic registry injection happens here)
        assembler.add_node(node.name, agent_instance)

def add_edges_to_assembler(
    assembler: GraphAssembler, 
    graph_def: Dict
) -> None:
    """
    Add edges to the GraphAssembler.
    
    Args:
        assembler: GraphAssembler instance
        graph_def: Graph definition
    """
    # Process edges for all nodes
    for node_name, node in graph_def.items():
        assembler.process_node_edges(node_name, node.edges)

@inject
def add_nodes_to_builder(
    builder: StateGraph, 
    graph_def: Dict,
    configuration: AppConfigService = Provide[ApplicationContainer.app_config_service] 
) -> None:
    """
    LEGACY: Add nodes to the StateGraph builder directly.
    
    Args:
        builder: StateGraph builder
        graph_def: Graph definition
        config_path: Optional path to a custom config file
    """
    for node in graph_def.values():
        agent_class = get_agent_class(node.agent_type)
        if agent_class:
            agent_instance = agent_class(name=node.name, prompt=node.prompt or "")
        else:
            # Try to load from custom agents path
            custom_agents_path = configuration.get_custom_agents_path()
            module_path = str(custom_agents_path).replace("/", ".").replace("\\", ".")
            if module_path.endswith("."):
                module_path = module_path[:-1]
                
            modname = f"{module_path}.{node.agent_type.lower()}_agent" if node.agent_type else "echo"
            classname = f"{node.agent_type}Agent" if node.agent_type else "EchoAgent"
            try:
                module = __import__(modname, fromlist=[classname])
                agent_instance = getattr(module, classname)(name=node.name, prompt=node.prompt or "")
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Could not load agent type '{node.agent_type}': {e}")
                
        builder.add_node(node.name, agent_instance)

@inject
def add_edges_to_builder(
    builder: StateGraph, 
    graph_def: Dict, 
    configuration: AppConfigService = Provide[ApplicationContainer.app_config_service],
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
) -> None:
    """
    LEGACY: Add edges to the StateGraph builder directly.
    
    Args:
        builder: StateGraph builder
        graph_def: Graph definition
        config_path: Optional path to a custom config file
        
    Raises:
        FileNotFoundError: If function file not found
    """
    functions_dir = configuration.get_functions_path()
    
    for node in graph_def.values():
        has_func = False
        
        # Check for function references first
        for condition, target in node.edges.items():
            func_ref = extract_func_ref(target)
            if func_ref:
                func_path = functions_dir / f"{func_ref}.py"
                if not func_path.exists():
                    raise FileNotFoundError(f"Function '{func_ref}' not found at {func_path}")
                    
                fn = import_function(func_ref)
                success = node.edges.get("success", "None")
                failure = node.edges.get("failure", "None")
                builder.add_conditional_edges(node.name, lambda x, fn=fn, s=success, f=failure: fn(x, s, f))
                has_func = True
                break
        
        # If no function references, handle conditional edges
        if not has_func:
            if "success" in node.edges and "failure" in node.edges:
                success_target = node.edges["success"]
                failure_target = node.edges["failure"]
                builder.add_conditional_edges(
                    node.name,
                    lambda state, s=success_target, f=failure_target: s if state.get("last_action_success", True) else f
                )
            elif "success" in node.edges:
                success_target = node.edges["success"]
                builder.add_conditional_edges(
                    node.name,
                    lambda state, s=success_target: s if state.get("last_action_success", True) else None
                )
            elif "failure" in node.edges:
                failure_target = node.edges["failure"]
                builder.add_conditional_edges(
                    node.name,
                    lambda state, f=failure_target: f if not state.get("last_action_success", True) else None
                )
            elif "default" in node.edges:
                target = node.edges["default"]
                builder.add_edge(node.name, target)

@inject
def compile_graph(
    graph_name: str, 
    output_dir: Optional[str] = None,
    csv_path: Optional[str] = None,
    state_schema: str = "dict",
    configuration: AppConfigService = Provide[ApplicationContainer.app_config_service],
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service],
    node_registry_service: NodeRegistryService = Provide[ApplicationContainer.node_registry_service]  
):
    """
    Compile a graph to the configured output directory with pre-compilation registry injection.
    
    Args:
        graph_name: Name of the graph to compile
        output_dir: Optional override for the output directory
        csv_path: Optional override for the CSV file path
        state_schema: State schema type ("dict", "pydantic:<ModelName>", etc.)
        config_path: Optional path to a custom config file
    
    Raises:
        ValueError: If graph not found
        FileNotFoundError: If function file not found
    """
    
    logger = logging_service.get_logger("agentmap.compiler")
    logger.info(f"[Compiler] Compiling graph: {graph_name}")
    
    # Get the graph definition
    csv_file = csv_path or configuration.get_csv_path()
    
    # Read the CSV content for versioning
    with open(csv_file, 'r') as f:
        csv_content = f.read()
    
    # Load graph definition
    gb = GraphBuilder(csv_file)
    graphs = gb.build()
    graph_def = graphs.get(graph_name)
    
    if not graph_def:
        raise ValueError(f"No graph found with name: {graph_name}")
    
    # NEW: Build node registry from the graph definition BEFORE compilation
    logger.debug(f"[Compiler] Building node registry for compilation: {graph_name}")
    node_registry = node_registry_service.prepare_for_assembly(graph_def, graph_name)
    
    # Use configured output directory if not specified
    output_dir = output_dir or configuration.get_compiled_graphs_path()
    os.makedirs(output_dir, exist_ok=True)
    
    # NEW: Create the graph builder WITH registry for pre-compilation injection
    graph, src_lines = create_graph_builder_with_registry(graph_def, node_registry, state_schema)
    
    # Create a graph bundle with graph, registry, and version info
    from agentmap.graph.bundle import GraphBundle
    bundle = GraphBundle(graph, node_registry, logging_service.get_logger("agentmap.graph"), csv_content)
    
    # Save the bundle to .pkl
    output_path = Path(output_dir) / f"{graph_name}.pkl"
    bundle.save(output_path)
    
    # Save .src (flattened LangGraph build) - still useful for visibility
    src_path = Path(output_dir) / f"{graph_name}.src"
    with open(src_path, "w") as f:
        f.write("\n".join(src_lines))
    
    logger.info(f"[Compiler] ✅ Compiled {graph_name} to {output_path} with pre-compilation registry injection")
    return output_path

@inject
def compile_all(
    csv_path: Optional[str] = None,
    state_schema: str = "dict",
    configuration: AppConfigService = Provide[ApplicationContainer.app_config_service],
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service]
):
    """
    Compile all graphs defined in the CSV.
    
    Args:
        csv_path: Optional override for the CSV file path
        state_schema: State schema type ("dict", "pydantic:<ModelName>", etc.)
        config_path: Optional path to a custom config file
    """
    logger = logging_service.get_logger("agentmap.compiler")
    logger.info(f"[Compiler] Compiling all graphs")
    
    csv_file = csv_path or configuration.get_csv_path()
    gb = GraphBuilder(csv_file)
    graphs = gb.build()
    
    compiled_paths = []
    for name in graphs.keys():
        try:
            path = compile_graph(name, csv_path=csv_path, state_schema=state_schema)
            compiled_paths.append(path)
        except Exception as e:
            logger.error(f"[Compiler] Error compiling graph {name}: {e}")
    
    logger.info(f"[Compiler] ✅ Compiled {len(compiled_paths)} graphs")
    return compiled_paths