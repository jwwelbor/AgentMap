"""Bundle update and scaffolding operations."""

from typing import Any, Dict, Optional


def update_bundle(
    graph_name: str,
    *,
    config_file: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Update existing bundle with current agent declaration mappings.

    Args:
        graph_name: The name or identifier of the graph to update bundle for.
        config_file: Optional configuration file path.
        dry_run: Preview changes without saving.
        force: Force update even if no changes detected.

    Returns:
        Dict containing structured update results.

    Raises:
        GraphNotFound: if the graph cannot be located.
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    from pathlib import Path

    from agentmap.exceptions.runtime_exceptions import (
        AgentMapNotInitialized,
        GraphNotFound,
    )
    from agentmap.runtime.runtime_manager import RuntimeManager

    from .init_ops import ensure_initialized
    from .workflow_ops import _resolve_csv_path

    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()

        # Resolve CSV path for the graph
        csv_path, resolved_graph_name = _resolve_csv_path(graph_name, container)

        # Get bundle service and force recreation of bundle
        graph_bundle_service = container.graph_bundle_service()
        bundle, _ = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name=resolved_graph_name,
            config_path=config_file,
            force_create=True,
        )

        # Analyze the bundle update results
        missing_declarations = (
            list(bundle.missing_declarations) if bundle.missing_declarations else []
        )
        current_mappings = len(bundle.agent_mappings) if bundle.agent_mappings else 0
        required_services = (
            len(bundle.required_services) if bundle.required_services else 0
        )

        if dry_run:
            # In dry-run mode, return what would happen
            return {
                "success": True,
                "outputs": {
                    "current_mappings": current_mappings,
                    "missing_declarations": missing_declarations,
                    "would_resolve": [],  # These would be resolved after agent creation
                    "would_update": (
                        list(bundle.agent_mappings.keys())
                        if bundle.agent_mappings
                        else []
                    ),
                    "would_remove": [],  # Old mappings that would be removed
                },
                "metadata": {
                    "bundle_name": bundle.graph_name,
                    "csv_path": str(csv_path),
                    "dry_run": True,
                },
            }
        else:
            # Actual update was performed by force recreation
            return {
                "success": True,
                "outputs": {
                    "current_mappings": current_mappings,
                    "missing_declarations": missing_declarations,
                    "required_services": required_services,
                },
                "metadata": {
                    "bundle_name": bundle.graph_name,
                    "csv_path": str(csv_path),
                    "force_recreated": True,
                },
            }

    except (GraphNotFound, AgentMapNotInitialized):
        raise
    except FileNotFoundError as e:
        raise GraphNotFound(graph_name, f"Bundle update file not found: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error during bundle update: {e}")


def scaffold_agents(
    graph_name: str,
    *,
    output_dir: Optional[str] = None,
    func_dir: Optional[str] = None,
    config_file: Optional[str] = None,
    overwrite: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Scaffold agents and routing functions using bundle analysis.

    Args:
        graph_name: The name or identifier of the graph to scaffold agents for.
        output_dir: Optional directory for agent output.
        func_dir: Optional directory for function output.
        config_file: Optional configuration file path.
        overwrite: Whether to overwrite existing agent files.

    Returns:
        Dict containing structured scaffold results with progress messages.

    Raises:
        GraphNotFound: if the graph cannot be located.
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    from pathlib import Path

    from agentmap.exceptions.runtime_exceptions import (
        AgentMapNotInitialized,
        GraphNotFound,
    )
    from agentmap.models.scaffold_types import ScaffoldOptions
    from agentmap.runtime.runtime_manager import RuntimeManager
    from agentmap.services.graph.graph_scaffold_service import GraphScaffoldService

    from .init_ops import ensure_initialized
    from .workflow_ops import _resolve_csv_path

    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()

        # Resolve CSV path for the graph
        csv_path, resolved_graph_name = _resolve_csv_path(graph_name, container)

        # Get bundle service - create bundle for analysis
        graph_bundle_service = container.graph_bundle_service()
        bundle, _ = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name=resolved_graph_name,
            config_path=config_file,
        )

        # Get scaffold service
        scaffold_service: GraphScaffoldService = container.graph_scaffold_service()

        # Determine output paths (CLI args override config)
        output_path = Path(output_dir) if output_dir else None
        functions_path = Path(func_dir) if func_dir else None

        # Create scaffold options
        scaffold_options = ScaffoldOptions(
            graph_name=bundle.graph_name or resolved_graph_name,
            output_path=output_path,
            function_path=functions_path,
            overwrite_existing=overwrite,
            force_rescaffold=force,
        )

        # Collect progress information before scaffolding
        progress_messages = []
        missing_declarations = (
            list(bundle.missing_declarations) if bundle.missing_declarations else []
        )

        # Add progress messages that CLI can display
        progress_messages.append(f"📦 Analyzing graph structure from: {csv_path}")
        progress_messages.append(
            f"🔨 Scaffolding agents for graph: {bundle.graph_name or resolved_graph_name}"
        )

        if missing_declarations:
            progress_messages.append(
                f"   Found {len(missing_declarations)} undefined agent types"
            )

        # Use the bundle-based scaffolding method
        result = scaffold_service.scaffold_from_bundle(bundle, scaffold_options)

        # Transform ScaffoldResult into structured response format
        success = len(result.errors) == 0 or result.scaffolded_count > 0

        # Bundle was updated inside scaffold_service, add progress message
        if result.scaffolded_count > 0:
            progress_messages.append("🔄 Bundle updated with newly scaffolded agents")

        return {
            "success": success,
            "outputs": {
                "scaffolded_count": result.scaffolded_count,
                "errors": result.errors,
                "created_files": [str(f) for f in result.created_files],
                "skipped_files": [str(f) for f in result.skipped_files],
                "service_stats": result.service_stats,
                "missing_declarations": missing_declarations,
                "progress_messages": progress_messages,
            },
            "metadata": {
                "bundle_name": bundle.graph_name or resolved_graph_name,
                "csv_path": str(csv_path),
                "graph_name": resolved_graph_name,
                "total_agents_in_bundle": len(bundle.nodes) if bundle.nodes else 0,
                "agents_needing_scaffold": len(missing_declarations),
            },
        }

    except (GraphNotFound, AgentMapNotInitialized):
        raise
    except FileNotFoundError as e:
        raise GraphNotFound(graph_name, f"Bundle scaffolding file not found: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error during agent scaffolding: {e}")
