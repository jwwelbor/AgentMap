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
        bundle = graph_bundle_service.get_or_create_bundle(
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
) -> Dict[str, Any]:
    raise NotImplementedError("Move implementation here")
