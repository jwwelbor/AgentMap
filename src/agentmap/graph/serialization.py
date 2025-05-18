"""
Graph serialization for AgentMap.

Provides unified interfaces for exporting and compiling LangGraph workflows
to various formats including Python source (.py), pickle (.pkl), and
flattened source (.src).
"""

import pickle
from pathlib import Path
from typing import Dict, Optional, Union

from agentmap.agents import get_agent_class
from agentmap.config import (get_compiled_graphs_path, get_csv_path,
                             get_custom_agents_path, get_functions_path)
from agentmap.graph import GraphAssembler, GraphBuilder
from agentmap.logging import get_logger
from agentmap.utils.common import extract_func_ref

logger = get_logger(__name__)

from langgraph.graph import StateGraph

# Common import header for Python exports
IMPORT_HEADER = """from langgraph.graph import StateGraph
from agentmap.agents.builtins.openai_agent import OpenAIAgent
from agentmap.agents.builtins.anthropic_agent import AnthropicAgent
from agentmap.agents.builtins.google_agent import GoogleAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.branching_agent import BranchingAgent
from agentmap.agents.builtins.success_agent import SuccessAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
"""

def export_graph(
    graph_name: str,
    format: str = "python",
    output_path: Optional[str] = None,
    csv_path: Optional[str] = None,
    state_schema: str = "dict",
    config_path: Optional[Union[str, Path]] = None
):
    """
    Export a graph to the specified format.
    
    Args:
        graph_name: Name of the graph to export
        format: Export format ('python', 'pickle', or 'source')
        output_path: Optional override for the output path
        csv_path: Optional override for the CSV path
        state_schema: State schema type (dict, pydantic:<ModelName>, or custom)
        config_path: Optional path to a custom config file
    
    Returns:
        Path to the exported file
    """
    if format.lower() == "python":
        return export_as_python(graph_name, output_path, csv_path, state_schema, config_path)
    elif format.lower() in ("pickle", "pkl"):
        return export_as_pickle(graph_name, output_path, csv_path, state_schema, config_path)
    elif format.lower() in ("source", "src"):
        return export_as_source(graph_name, output_path, csv_path, state_schema, config_path)
    else:
        raise ValueError(f"Unsupported export format: {format}")

def get_graph_definition(
    graph_name: str,
    csv_path: Optional[Union[str, Path]] = None,
    config_path: Optional[Union[str, Path]] = None
):
    """
    Get the graph definition from a CSV file.
    
    Args:
        graph_name: Name of the graph to get
        csv_path: Optional override for the CSV path
        config_path: Optional path to a custom config file
        
    Returns:
        Graph definition dictionary
        
    Raises:
        ValueError: If graph not found
    """
    csv_file = csv_path or get_csv_path(config_path)
    gb = GraphBuilder(csv_file)
    graphs = gb.build()
    
    graph_def = graphs.get(graph_name)
    if not graph_def:
        raise ValueError(f"No graph found with name: {graph_name}")
        
    return graph_def

def resolve_agent_class(
    agent_type: str,
    config_path: Optional[Union[str, Path]] = None
):
    """
    Resolve an agent class by type.
    
    Args:
        agent_type: Type of agent to resolve
        config_path: Optional path to a custom config file
        
    Returns:
        Agent class or class name string
        
    Raises:
        ValueError: If agent type cannot be resolved
    """
    if not agent_type:
        return "DefaultAgent"
        
    agent_type = agent_type.lower()
    
    # Check built-in agent types
    agent_class = get_agent_class(agent_type)
    if agent_class:
        return agent_class.__name__
        
    # Try to find a custom agent
    custom_agents_path = get_custom_agents_path(config_path)
    module_path = str(custom_agents_path).replace("/", ".").replace("\\", ".")
    if module_path.endswith("."):
        module_path = module_path[:-1]
        
    # Assume a custom agent class name based on agent_type
    class_name = f"{agent_type.capitalize()}Agent"
    
    # Return the assumed class name
    return class_name

def get_function_imports(
    graph_def: Dict,
    config_path: Optional[Union[str, Path]] = None
):
    """
    Get the function import statements for a graph.
    
    Args:
        graph_def: Graph definition dictionary
        config_path: Optional path to a custom config file
        
    Returns:
        List of import statements
    """
    imports = set()
    functions_dir = get_functions_path(config_path)
    
    for node in graph_def.values():
        for target in node.edges.values():
            func_ref = extract_func_ref(target)
            if func_ref:
                func_file = functions_dir / f"{func_ref}.py"
                if not func_file.exists():
                    raise FileNotFoundError(
                        f"Function '{func_ref}' is referenced but not found. "
                        f"Expected at {func_file}"
                    )
                imports.add(f"from agentmap.functions.{func_ref} import {func_ref}")
    
    return sorted(list(imports))

def get_state_schema_imports(state_schema: str):
    """
    Get import statements for the state schema.
    
    Args:
        state_schema: State schema type (dict, pydantic:<ModelName>, or custom)
        
    Returns:
        List of import statements
    """
    if state_schema == "dict":
        # No imports needed for dict
        return []
    elif state_schema.startswith("pydantic:"):
        model_name = state_schema.split(":", 1)[1]
        return [f"from agentmap.schemas.{model_name.lower()} import {model_name}"]
    else:
        # Assume a custom schema module
        return [f"from {state_schema} import StateSchema"]

def generate_python_code(
    graph_name: str,
    graph_def: Dict,
    state_schema: str = "dict",
    config_path: Optional[Union[str, Path]] = None
):
    """
    Generate Python code for a graph.
    
    Args:
        graph_name: Name of the graph
        graph_def: Graph definition dictionary
        state_schema: State schema type (dict, pydantic:<ModelName>, or custom)
        config_path: Optional path to a custom config file
        
    Returns:
        List of Python code lines
    """
    lines = [IMPORT_HEADER]
    
    # Add state schema imports
    schema_imports = get_state_schema_imports(state_schema)
    if schema_imports:
        lines.extend(schema_imports)
    
    # Add function imports
    imports = get_function_imports(graph_def, config_path)
    lines.extend(imports)
    lines.append("")  # Add spacing
    
    # Create graph builder with appropriate state type
    lines.append(f"# Graph: {graph_name}")
    
    if state_schema == "dict":
        lines.append("builder = StateGraph(dict)")
    elif state_schema.startswith("pydantic:"):
        model_name = state_schema.split(":", 1)[1]
        lines.append(f"builder = StateGraph({model_name})")
    else:
        lines.append(f"builder = StateGraph({state_schema})")
    
    # Add nodes
    for node in graph_def.values():
        agent_class = resolve_agent_class(node.agent_type, config_path)
        prompt = node.prompt.replace('"', '\\"') if node.prompt else ""
        
        # Format the context dictionary for inputs and output
        context_str = "{"
        if node.inputs:
            inputs_str = ", ".join([f'"{field}"' for field in node.inputs])
            context_str += f'"input_fields": [{inputs_str}], '
        if node.output:
            context_str += f'"output_field": "{node.output}", '
        if context_str.endswith(", "):
            context_str = context_str[:-2]
        context_str += "}"
        
        # Add the node creation line
        lines.append(f'# Node: {node.name}')
        lines.append(f'builder.add_node("{node.name}", {agent_class}(name="{node.name}", prompt="{prompt}", context={context_str}))')
    
    # Set entry point
    entry = next(iter(graph_def))
    lines.append(f'builder.set_entry_point("{entry}")')
    
    # Process and add edges
    for node_name, node in graph_def.items():
        # Check for function edges
        has_func = False
        for condition, target in node.edges.items():
            func_ref = extract_func_ref(target)
            if func_ref:
                success = node.edges.get("success", "None")
                failure = node.edges.get("failure", "None")
                lines.append(f'builder.add_conditional_edges("{node_name}", lambda x: {func_ref}(x, "{success}", "{failure}"))')
                has_func = True
                break
        
        if not has_func:
            # Handle success/failure edges
            if "success" in node.edges and "failure" in node.edges:
                success_target = node.edges["success"]
                failure_target = node.edges["failure"]
                lines.append(f'builder.add_conditional_edges("{node_name}", lambda state: "{success_target}" if state.get("last_action_success", True) else "{failure_target}")')
            
            # Handle success-only edge
            elif "success" in node.edges:
                success_target = node.edges["success"]
                lines.append(f'builder.add_conditional_edges("{node_name}", lambda state: "{success_target}" if state.get("last_action_success", True) else None)')
            
            # Handle failure-only edge
            elif "failure" in node.edges:
                failure_target = node.edges["failure"]
                lines.append(f'builder.add_conditional_edges("{node_name}", lambda state: "{failure_target}" if not state.get("last_action_success", True) else None)')
            
            # Handle default edge
            elif "default" in node.edges:
                target = node.edges["default"]
                lines.append(f'builder.add_edge("{node_name}", "{target}")')
    
    # Compile the graph
    lines.append("graph = builder.compile()")
    lines.append("# Run the graph with: graph.invoke(initial_state)")
    lines.append("# Example: result = graph.invoke({\"input\": \"Your input value\"})")
    
    return lines

def export_as_python(
    graph_name: str,
    output_path: Optional[str] = None,
    csv_path: Optional[str] = None,
    state_schema: str = "dict",
    config_path: Optional[Union[str, Path]] = None
):
    """
    Export a graph as a Python file.
    
    Args:
        graph_name: Name of the graph to export
        output_path: Optional override for the output path
        csv_path: Optional override for the CSV path
        state_schema: State schema type (dict, pydantic:<ModelName>, or custom)
        config_path: Optional path to a custom config file
        
    Returns:
        Path to the exported file
    """
    # Get graph definition
    graph_def = get_graph_definition(graph_name, csv_path=csv_path, config_path=config_path)
    
    # Generate Python code
    lines = generate_python_code(graph_name, graph_def, state_schema, config_path)
    
    # Determine output path
    output_path = get_output_path(graph_name, output_path, config_path, "py")
    
    # Write file
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    
    logger.info(f"✅ Exported {graph_name} to {output_path}")
    return output_path

def get_state_schema_class(state_schema: str):
    """
    Get the appropriate state schema class.
    
    Args:
        state_schema: State schema type (dict, pydantic:<ModelName>, or custom)
        
    Returns:
        State schema class
    """
    if state_schema == "dict":
        return dict
    elif state_schema.startswith("pydantic:"):
        model_name = state_schema.split(":", 1)[1]
        try:
            module = __import__(f"agentmap.schemas.{model_name.lower()}", fromlist=[model_name])
            return getattr(module, model_name)
        except (ImportError, AttributeError) as e:
            logger.warning(f"[GetStateSchemaClass] Could not import Pydantic model '{model_name}'. Falling back to dict.")
            logger.warning(f"[GetStateSchemaClass] Error: {e}")
            return dict
    else:
        # Try to import custom schema
        try:
            module_path, class_name = state_schema.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as e:
            logger.warning(f"[GetStateSchemaClass] Could not import custom schema '{state_schema}'. Falling back to dict.")
            logger.warning(f"[GetStateSchemaClass] Error: {e}")
            return dict

def export_as_pickle(
    graph_name: str,
    output_path: Optional[str] = None,
    csv_path: Optional[str] = None,
    state_schema: str = "dict",
    config_path: Optional[Union[str, Path]] = None
):
    """
    Export a graph as a pickle file.
    
    Args:
        graph_name: Name of the graph to export
        output_path: Optional override for the output path
        csv_path: Optional override for the CSV path
        state_schema: State schema type (dict, pydantic:<ModelName>, or custom)
        config_path: Optional path to a custom config file
        
    Returns:
        Path to the exported file
    """
    # Try to import dill, a more powerful serialization library
    try:
        import dill
        use_dill = True
    except ImportError:
        use_dill = False
        logger.warning("Dill package not found. Trying standard pickle with named functions.")
        logger.warning("Consider installing dill with: pip install dill")
    
    # Get graph definition
    graph_def = get_graph_definition(graph_name, csv_path=csv_path, config_path=config_path)
    
    # Get state schema class
    schema_class = get_state_schema_class(state_schema)
    
    # Build LangGraph StateGraph
    builder = StateGraph(schema_class)
    
    # Create the graph assembler (without logging for exports)
    assembler = GraphAssembler(builder, config_path=config_path, enable_logging=False)
    
    # Add nodes to the graph
    for node in graph_def.values():
        agent_cls = get_agent_class(node.agent_type)
        if not agent_cls:
            # Try to load from custom agents path
            custom_agents_path = get_custom_agents_path(config_path)
            module_path = str(custom_agents_path).replace("/", ".").replace("\\", ".")
            if module_path.endswith("."):
                module_path = module_path[:-1]
                
            modname = f"{module_path}.{node.agent_type.lower()}_agent" if node.agent_type else "echo"
            classname = f"{node.agent_type}Agent" if node.agent_type else "EchoAgent"
            
            try:
                module = __import__(modname, fromlist=[classname])
                agent_cls = getattr(module, classname)
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Could not load agent type '{node.agent_type}': {e}")
        
        # Create context with input/output field information
        context = {
            "input_fields": node.inputs,
            "output_field": node.output
        }
        
        # Create agent instance
        agent_instance = agent_cls(name=node.name, prompt=node.prompt or "", context=context)
        
        # Add node to graph
        assembler.add_node(node.name, agent_instance)
    
    # Set entry point
    assembler.set_entry_point(next(iter(graph_def)))
    
    # Process edges for all nodes
    for node_name, node in graph_def.items():
        assembler.process_node_edges(node_name, node.edges)
    
    # Compile the graph
    graph = assembler.compile()
    
    # Determine output path
    output_path = get_output_path(graph_name, output_path, config_path, "pkl")
    
    # Write file
    try:
        with open(output_path, "wb") as f:
            if use_dill:
                dill.dump(graph, f)
            else:
                pickle.dump(graph, f)
        
        logger.info(f"✅ Compiled {graph_name} to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to pickle graph: {e}")
        logger.error("Consider installing dill: pip install dill")
        logger.error("Or use export_as_python instead for reliable serialization.")
        
        # Fallback to Python export
        py_path = export_as_python(graph_name, output_path, csv_path, state_schema, config_path)
        logger.info(f"✅ Exported {graph_name} as Python to {py_path} as fallback")
        return py_path

def export_as_source(
    graph_name: str,
    output_path: Optional[str] = None,
    csv_path: Optional[str] = None,
    state_schema: str = "dict",
    config_path: Optional[Union[str, Path]] = None
):
    """
    Export a graph as a source (.src) file.
    
    Args:
        graph_name: Name of the graph to export
        output_path: Optional override for the output path
        csv_path: Optional override for the CSV path
        state_schema: State schema type (dict, pydantic:<ModelName>, or custom)
        config_path: Optional path to a custom config file
        
    Returns:
        Path to the exported file
    """
    # Get graph definition
    graph_def = get_graph_definition(graph_name, csv_path=csv_path, config_path=config_path)
    
    # Generate source code - simplified version
    src_lines = []
    
    # Add state schema line if not dict
    if state_schema != "dict":
        if state_schema.startswith("pydantic:"):
            model_name = state_schema.split(":", 1)[1]
            src_lines.append(f"builder = StateGraph({model_name})")
        else:
            src_lines.append(f"builder = StateGraph({state_schema})")
    else:
        src_lines.append("builder = StateGraph(dict)")
    
    # Add node creation lines
    for node in graph_def.values():
        agent_class = resolve_agent_class(node.agent_type, config_path)
        src_lines.append(f'builder.add_node("{node.name}", {agent_class}())')
    
    # Set entry point
    entry = next(iter(graph_def))
    src_lines.append(f'builder.set_entry_point("{entry}")')
    
    # Process and add edges - same simplified code generation for edges
    for node_name, node in graph_def.items():
        # Check for function edges
        has_func = False
        for condition, target in node.edges.items():
            func_ref = extract_func_ref(target)
            if func_ref:
                success = node.edges.get("success", "None")
                failure = node.edges.get("failure", "None")
                src_lines.append(f'builder.add_conditional_edges("{node_name}", lambda x: {func_ref}(x, "{success}", "{failure}"))')
                has_func = True
                break
        
        if not has_func:
            # Handle success/failure edges
            if "success" in node.edges and "failure" in node.edges:
                success_target = node.edges["success"]
                failure_target = node.edges["failure"]
                src_lines.append(f'builder.add_conditional_edges("{node_name}", lambda state: "{success_target}" if state.get("last_action_success", True) else "{failure_target}")')
            
            # Handle success-only edge
            elif "success" in node.edges:
                success_target = node.edges["success"]
                src_lines.append(f'builder.add_conditional_edges("{node_name}", lambda state: "{success_target}" if state.get("last_action_success", True) else None)')
            
            # Handle failure-only edge
            elif "failure" in node.edges:
                failure_target = node.edges["failure"]
                src_lines.append(f'builder.add_conditional_edges("{node_name}", lambda state: "{failure_target}" if not state.get("last_action_success", True) else None)')
            
            # Handle default edge
            elif "default" in node.edges:
                target = node.edges["default"]
                src_lines.append(f'builder.add_edge("{node_name}", "{target}")')
    
    # Determine output path
    output_path = get_output_path(graph_name, output_path, config_path, "src")
   
    # Write file
    with open(output_path, "w") as f:
        f.write("\n".join(src_lines))
    
    logger.info(f"✅ Exported {graph_name} source to {output_path}")
    return output_path

def get_output_path(graph_name, output_path, config_path, extension):
    if not output_path:
        output_dir = get_compiled_graphs_path(config_path)
        output_path = output_dir / f"{graph_name}.{extension}"
    else:
        # If output_path is a directory, append the filename
        output_path = Path(output_path)
        if output_path.is_dir():
            output_path = output_path / f"{graph_name}.{extension}"
    
    # Create directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path

def compile_all(
    csv_path: Optional[str] = None,
    state_schema: str = "dict",
    config_path: Optional[Union[str, Path]] = None
):
    """
    Compile all graphs to pickle files.
    
    Args:
        csv_path: Optional override for the CSV path
        state_schema: State schema type (dict, pydantic:<ModelName>, or custom)
        config_path: Optional path to a custom config file
    """
    csv_file = csv_path or get_csv_path(config_path)
    gb = GraphBuilder(csv_file)
    graphs = gb.build()
    
    for name in graphs.keys():
        export_as_pickle(name, csv_path=csv_path, state_schema=state_schema, config_path=config_path)
        export_as_source(name, csv_path=csv_path, state_schema=state_schema, config_path=config_path)
        
    logger.info(f"✅ Compiled {len(graphs)} graphs")