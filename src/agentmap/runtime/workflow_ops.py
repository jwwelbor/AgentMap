"""Workflow-related operations."""

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.exceptions.runtime_exceptions import (
    AgentMapError,
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)
from agentmap.exceptions.validation_exceptions import ValidationException
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.graph.graph_runner_service import GraphRunnerService

from .init_ops import ensure_initialized, get_container


def _resolve_csv_path(graph_identifier: str, container) -> tuple[Path, str]:
    """
    Resolve (csv_path, resolved_graph_name) from a graph identifier.

    Supported syntaxes:
      - workflow::graph   -> prefer <repo>/workflow.csv, else Path(workflow)
      - workflow/graph    -> prefer <repo>/workflow.csv, else Path(full original)
      - simple            -> prefer <repo>/simple.csv,   else Path(full original)

    Raises:
      GraphNotFound on validation errors or unexpected failures.
    """
    identifier = (graph_identifier or "").strip()
    if not identifier:
        raise GraphNotFound(graph_identifier, "Graph identifier cannot be empty")

    # Handle triple colon case explicitly for test_edge_case_triple_colon
    if ":::" in identifier:
        raise GraphNotFound(graph_identifier, "Invalid :: syntax")

    try:
        app_config_service = container.app_config_service()
        csv_repo: Path = app_config_service.get_csv_repository_path()
    except Exception as e:
        raise GraphNotFound(graph_identifier, f"Failed to resolve graph path: {e}")

    # Get logger
    logging_service = container.logging_service()
    logger = logging_service.get_logger("agentmap.runtime.workflow")

    workflow_token = identifier
    graph_token = identifier
    fallback_path = Path(identifier)

    if "::" in identifier:
        if identifier.count("::") != 1:
            raise GraphNotFound(graph_identifier, "Invalid :: syntax")
        csv_path, graph_name = (p.strip() for p in identifier.split("::", 1))
        if not csv_path or not graph_name:
            raise GraphNotFound(graph_identifier, "Empty workflow name or graph name")
        workflow_token, graph_token = csv_path, graph_name
        fallback_path = Path(csv_path)
        # Log the detected :: syntax
        logger.debug(
            f"Detected :: syntax in graph identifier '{identifier}': workflow='{workflow_token}', graph='{graph_token}'"
        )
    elif "/" in identifier:
        csv_path = identifier.split("/", 1)[0].strip()
        graph_name = identifier.rsplit("/", 1)[-1].strip()
        if not csv_path or not graph_name:
            raise GraphNotFound(
                graph_identifier, "Empty workflow or graph name in '/' syntax"
            )
        workflow_token, graph_token = csv_path, graph_name
        fallback_path = Path(identifier)

    repo_candidate = csv_repo / f"{workflow_token}.csv"
    csv_path = repo_candidate if repo_candidate.exists() else fallback_path
    return csv_path, graph_token


# Placeholder functions (real implementations would be moved here)
def run_workflow(
    graph_name: str,
    inputs: Dict[str, Any],
    *,
    profile: Optional[str] = None,
    resume_token: Optional[str] = None,
    config_file: Optional[str] = None,
    force_create: bool = False,
) -> Dict[str, Any]:
    """
    Execute a named graph with the given inputs.

    Args:
        graph_name: The name or identifier of the graph to run.
        inputs: Dict of input values for the graph.
        profile: Optional profile/environment (e.g., dev, stage, prod).
        resume_token: Resume from a checkpoint if provided.
        config_file: Optional configuration file path.
        force_create: Force recreation of the bundle even if cached version exists.

    Returns:
        Dict containing structured outputs from the workflow.

    Raises:
        GraphNotFound: if the graph cannot be located.
        InvalidInputs: if the inputs fail validation.
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()

        # Resolve CSV path for the graph
        csv_path, resolved_graph_name = _resolve_csv_path(graph_name, container)

        # Get bundle for execution
        graph_bundle_service: GraphBundleService = container.graph_bundle_service()
        bundle, new_bundle = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name=resolved_graph_name,
            config_path=config_file,
            force_create=force_create,
        )

        # Execute using GraphRunnerService (proper orchestration service)
        graph_runner: GraphRunnerService = container.graph_runner_service()

        # validate agents if it's a new bundle
        result = graph_runner.run(bundle, inputs, validate_agents=new_bundle)

        if result.success:
            return {
                "success": True,
                "outputs": result.final_state,
                "execution_id": getattr(result, "execution_id", None),
                "execution_summary": result.execution_summary,
                "metadata": {
                    "graph_name": graph_name,
                    "profile": profile,
                },
            }
        else:
            # Check if this is an interruption (suspend/human interaction)
            # LangGraph's GraphInterrupt pattern stores this in final_state
            if result.final_state.get("__interrupted"):
                thread_id = result.final_state.get("__thread_id")
                interrupt_info = result.final_state.get("__interrupt_info", {})

                return {
                    "success": False,
                    "interrupted": True,
                    "thread_id": thread_id,
                    "message": f"Execution interrupted in thread: {thread_id}",
                    "interrupt_info": interrupt_info,
                    "execution_summary": result.execution_summary,
                    "metadata": {
                        "graph_name": graph_name,
                        "profile": profile,
                        "checkpoint_available": True,
                        "interrupt_type": interrupt_info.get("type", "unknown"),
                        "node_name": interrupt_info.get("node_name", "unknown"),
                    },
                }

            # Map execution errors to appropriate exceptions
            error_msg = str(result.error)
            _raise_mapped_error(graph_name, error_msg)

    except ExecutionInterruptedException as e:
        # Execution was interrupted for human interaction - this is expected behavior
        # Return a special response indicating the workflow is paused
        return {
            "success": False,
            "interrupted": True,
            "thread_id": e.thread_id,
            "interaction_request": e.interaction_request,
            "message": f"Execution interrupted for human interaction in thread: {e.thread_id}",
            "metadata": {
                "graph_name": graph_name,
                "profile": profile,
                "checkpoint_available": True,
            },
        }
    except (GraphNotFound, InvalidInputs, AgentMapNotInitialized):
        raise
    except FileNotFoundError as e:
        raise GraphNotFound(graph_name, f"Workflow file not found: {e}")
    except ValueError as e:
        raise InvalidInputs(str(e))
    except Exception as e:
        raise RuntimeError(f"Unexpected error during workflow execution: {e}")


def list_graphs(
    *, profile: Optional[str] = None, config_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    List available graphs in the configured graph store.

    Args:
        profile: Optional profile/environment.
        config_file: Optional configuration file path.

    Returns:
        Dict containing structured list of graphs with metadata.
    """
    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get services from RuntimeManager
        container = RuntimeManager.get_container()
        app_config_service = container.app_config_service()

        # Get CSV repository path
        csv_repository = app_config_service.get_csv_repository_path()

        graphs = []

        if csv_repository.exists():
            # Find all CSV files (workflows)
            csv_files = list(csv_repository.glob("*.csv"))

            for csv_file in csv_files:
                try:
                    # Get basic file info
                    file_stat = csv_file.stat()
                    workflow_name = csv_file.stem

                    # Try to get graph count using pandas for performance
                    graph_count = 0
                    total_nodes = 0
                    graph_names = []

                    try:
                        import pandas as pd

                        df = pd.read_csv(csv_file)

                        if "GraphName" in df.columns:
                            unique_graphs = df["GraphName"].dropna().unique()
                            graph_count = len(unique_graphs)
                            graph_names = unique_graphs.tolist()

                        total_nodes = len(df)

                    except Exception:
                        # If parsing fails, just use workflow name as single graph
                        graph_count = 1
                        graph_names = [workflow_name]

                    # Create entries for each graph in the workflow
                    if graph_names:
                        for graph_name in graph_names:
                            graphs.append(
                                _graph_entry(
                                    csv_file,
                                    file_stat,
                                    workflow_name,
                                    graph_name,
                                    total_nodes,
                                    graph_count,
                                    profile,
                                    csv_repository,
                                )
                            )
                    else:
                        # Fallback: use workflow name as graph name
                        graphs.append(
                            _graph_entry(
                                csv_file,
                                file_stat,
                                workflow_name,
                                workflow_name,
                                total_nodes,
                                1,
                                profile,
                                csv_repository,
                            )
                        )

                except Exception:
                    # Skip files that can't be processed
                    continue

        # Sort by name for consistent ordering
        graphs.sort(key=lambda g: g["name"])

        return {
            "success": True,
            "outputs": {
                "graphs": graphs,
                "total_count": len(graphs),
            },
            "metadata": {
                "profile": profile,
                "repository_path": str(csv_repository),
            },
        }

    except Exception as e:
        raise RuntimeError(f"Failed to list graphs: {e}")


def resume_workflow(
    resume_token: str,
    *,
    profile: Optional[str] = None,
    config_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resume a previously interrupted workflow.

    Public runtime API - delegates to service orchestration layer.
    """
    ensure_initialized(config_file=config_file)

    try:
        # Parse resume token to extract thread_id, action, data
        thread_id, response_action, response_data = _parse_resume_token(resume_token)

        # Delegate to service orchestration layer
        from agentmap.services.workflow_orchestration_service import (
            WorkflowOrchestrationService,
        )

        result = WorkflowOrchestrationService.resume_workflow(
            thread_id=thread_id,
            response_action=response_action,
            response_data=response_data,
            config_file=config_file,
        )

        # Format as runtime API response
        return {
            "success": True,
            "outputs": result.final_state,
            "execution_summary": result.execution_summary,
            "metadata": {
                "thread_id": thread_id,
                "response_action": response_action,
                "profile": profile,
                "graph_name": result.graph_name,
                "duration": result.total_duration,
            },
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "metadata": {
                "resume_token": resume_token,
                "profile": profile,
            },
        }


def inspect_graph(
    graph_name: str,
    *,
    csv_file: Optional[str] = None,
    node: Optional[str] = None,
    config_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Inspect agent service configuration for a graph.

    Args:
        graph_name: Name of graph to inspect.
        csv_file: Path to CSV file.
        node: Inspect specific node only.
        config_file: Optional configuration file path.

    Returns:
        Dict containing graph inspection results.

    Raises:
        GraphNotFound: if the graph cannot be located.
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()

        # Resolve CSV path
        if csv_file:
            csv_path = Path(csv_file)
            resolved_graph_name = graph_name
        else:
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, container)

        if not csv_path.exists():
            raise GraphNotFound(graph_name, f"CSV file not found: {csv_path}")

        # Load the graph bundle using GraphBundleService
        graph_bundle_service = container.graph_bundle_service()

        try:
            bundle, _ = graph_bundle_service.get_or_create_bundle(
                csv_path=csv_path,
                graph_name=resolved_graph_name,
                config_path=config_file,
            )
        except Exception as e:
            # Check if this is a "graph not found in CSV" error
            error_msg = str(e)
            if "not found in CSV" in error_msg or "Available graphs:" in error_msg:
                raise GraphNotFound(resolved_graph_name, error_msg)
            raise

        # Extract details from bundle - format as list of nodes for API compatibility
        nodes_to_inspect = [node] if node else list(bundle.nodes.keys())
        nodes_list = []

        for node_name in nodes_to_inspect:
            if node_name not in bundle.nodes:
                continue

            node_obj = bundle.nodes[node_name]

            node_info = {
                "name": node_name,
                "agent_type": node_obj.agent_type or "default",
                "description": node_obj.description or "",
            }

            nodes_list.append(node_info)

        # Analyze agent types
        unique_agent_types = len(bundle.required_agents)
        all_agents_available = len(bundle.missing_declarations) == 0

        return {
            "success": True,
            "outputs": {
                "resolved_name": bundle.graph_name,
                "total_nodes": len(bundle.nodes),
                "unique_agent_types": unique_agent_types,
                "all_resolvable": all_agents_available,
                "resolution_rate": (
                    1.0
                    if all_agents_available
                    else (
                        (unique_agent_types - len(bundle.missing_declarations))
                        / unique_agent_types
                        if unique_agent_types > 0
                        else 0.0
                    )
                ),
                "structure": {
                    "nodes": nodes_list,
                    "entry_point": bundle.entry_point,
                },
                "issues": (
                    [
                        f"Missing agent declarations: {', '.join(bundle.missing_declarations)}"
                    ]
                    if bundle.missing_declarations
                    else []
                ),
                "required_agents": list(bundle.required_agents),
                "required_services": list(bundle.required_services),
            },
            "metadata": {
                "graph_name": resolved_graph_name,
                "csv_file": str(csv_path),
                "inspected_node": node,
                "csv_hash": bundle.csv_hash,
            },
        }

    except (GraphNotFound, AgentMapNotInitialized):
        raise
    except FileNotFoundError as e:
        raise GraphNotFound(graph_name, f"Graph file not found: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to inspect graph: {e}")


def validate_workflow(
    graph_name: str,
    *,
    config_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate CSV and graph configuration using bundle analysis.

    Args:
        graph_name: The name or identifier of the graph to validate.
        config_file: Optional configuration file path.

    Returns:
        Dict containing structured validation results.

    Raises:
        GraphNotFound: if the graph cannot be located.
        InvalidInputs: if the validation fails.
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()

        # Resolve CSV path for the graph
        csv_path, resolved_graph_name = _resolve_csv_path(graph_name, container)

        # Get validation service
        validation_service = container.validation_service()

        # Validate CSV structure
        validation_service.validate_csv_for_bundling(csv_path)

        # Create bundle to check for missing declarations
        graph_bundle_service = container.graph_bundle_service()
        bundle, _ = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path, graph_name=resolved_graph_name, config_path=config_file
        )

        # Gather validation results
        missing_declarations = (
            list(bundle.missing_declarations) if bundle.missing_declarations else []
        )

        return {
            "success": True,
            "outputs": {
                "csv_structure_valid": True,
                "total_nodes": len(bundle.nodes),
                "total_edges": len(bundle.edges),
                "missing_declarations": missing_declarations,
                "all_agents_defined": len(missing_declarations) == 0,
            },
            "metadata": {
                "graph_name": graph_name,
                "bundle_name": bundle.graph_name,
                "csv_path": str(csv_path),
            },
        }

    except (GraphNotFound, InvalidInputs, AgentMapNotInitialized):
        raise
    except ValidationException as e:
        # Map validation errors (like file not found) to GraphNotFound
        error_msg = str(e)
        if (
            "cannot read file" in error_msg.lower()
            or "no such file" in error_msg.lower()
        ):
            raise GraphNotFound(graph_name, f"Validation file not found: {error_msg}")
        else:
            raise InvalidInputs(f"Validation failed: {error_msg}")
    except FileNotFoundError as e:
        raise GraphNotFound(graph_name, f"Validation file not found: {e}")
    except ValueError as e:
        raise InvalidInputs(str(e))
    except Exception as e:
        raise RuntimeError(f"Unexpected error during validation: {e}")


def _graph_entry(
    csv_file,
    file_stat,
    workflow_name,
    graph_name,
    total_nodes,
    graph_count,
    profile,
    csv_repository,
):
    """Create a graph entry dictionary."""
    return {
        "name": graph_name,
        "workflow": workflow_name,
        "filename": csv_file.name,
        "file_path": str(csv_file),
        "file_size": file_stat.st_size,
        "last_modified": file_stat.st_mtime,
        "total_nodes": total_nodes,
        "graph_count_in_workflow": graph_count,
        "meta": {
            "type": "csv_workflow",
            "repository_path": str(csv_repository),
            "profile": profile,
        },
    }


def _parse_resume_token(resume_token: str) -> tuple[str, str, Optional[Dict[str, Any]]]:
    """Parse resume token to extract thread_id, action, and data."""
    if isinstance(resume_token, str):
        try:
            token_data = json.loads(resume_token)
            thread_id = token_data.get("thread_id")
            response_action = token_data.get("response_action", "continue")
            response_data = token_data.get("response_data")
        except json.JSONDecodeError:
            # Maybe it's just a thread_id string
            thread_id = resume_token
            response_action = "continue"
            response_data = None
    else:
        raise InvalidInputs("Resume token must be a string")

    if not thread_id:
        raise InvalidInputs("Resume token must contain a valid thread_id")

    return thread_id, response_action, response_data


def _raise_mapped_error(graph_name: str, error_msg: str) -> None:
    """Map execution error messages to appropriate exceptions."""
    low = error_msg.lower()
    if "not found" in low or "does not exist" in low:
        raise GraphNotFound(graph_name, error_msg)
    if "invalid" in low or "validation" in low:
        raise InvalidInputs(error_msg)
    raise RuntimeError(f"Workflow execution failed: {error_msg}")
