"""
Common utilities for CLI commands.

This module provides shared functionality for CLI commands to reduce
code duplication while maintaining clear error handling and user feedback.
"""

import json
from pathlib import Path
from typing import Optional, Tuple, Any, Dict

import typer

from agentmap.di import initialize_di
from agentmap.services.graph.graph_registry_service import GraphRegistryService
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.models.storage.types import StorageResult
from agentmap.services.logging_service import LoggingService
from agentmap.services.static_bundle_analyzer import StaticBundleAnalyzer
from agentmap.models.graph_bundle import GraphBundle


def resolve_csv_path(
    csv_file: Optional[str] = None,
    csv_option: Optional[str] = None
) -> Path:
    """
    Resolve CSV path from either positional argument or option.
    
    Args:
        csv_file: Positional CSV file argument
        csv_option: --csv option value
        
    Returns:
        Path object for the CSV file
        
    Raises:
        typer.Exit: If CSV is not provided or doesn't exist
    """
    # Handle shorthand CSV file argument
    csv = csv_file if csv_file is not None else csv_option
    
    if not csv:
        typer.secho("❌ CSV file required", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    csv_path = Path(csv)
    if not csv_path.exists():
        typer.secho(f"❌ CSV file not found: {csv_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    return csv_path


def parse_json_state(state_str: str) -> Dict[str, Any]:
    """
    Parse JSON state string with error handling.
    
    Args:
        state_str: JSON string to parse
        
    Returns:
        Parsed dictionary
        
    Raises:
        typer.Exit: If JSON is invalid
    """
    if state_str == "{}":
        return {}
    
    try:
        return json.loads(state_str)
    except json.JSONDecodeError as e:
        typer.secho(f"❌ Invalid JSON in --state: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def get_or_create_bundle(
    container, 
    csv_path: Path, 
    graph_name: Optional[str] = None, 
    config_file: Optional[str] = None
) -> GraphBundle:
    """
    Get existing bundle from cache or create a new one.
    
    This function encapsulates the bundle caching logic, checking for
    existing bundles and creating new ones as needed.
    
    TODO: Consider moving this to GraphBundleService as a high-level
    orchestration method since it already has all required dependencies.
    
    Args:
        container: DI container with required services
        csv_path: Path to CSV file
        graph_name: Optional graph name
        config_file: Optional path to configuration file
        
    Returns:
        GraphBundle ready for execution or scaffolding
    """
    # Get required services from container
    registry_service: GraphRegistryService = container.graph_registry_service()
    logging_service: LoggingService = container.logging_service()
    logger = logging_service.get_logger(__name__)
    graph_bundle_service: GraphBundleService = container.graph_bundle_service()
    app_config_service: AppConfigService = container.app_config_service()

    # Compute hash for CSV file
    csv_hash = registry_service.compute_hash(csv_path, logging_service) 
    bundle_path = registry_service.find_bundle(csv_hash)

    if bundle_path:
        # Load existing bundle from cache
        logger.info(f"Loading cached bundle for hash {csv_hash[:8]}")
        bundle = graph_bundle_service.load_bundle(bundle_path)
    else:
        # Create new bundle
        logger.info(f"Creating new bundle for {csv_path}")
        
        try:
            # Try fast path with static analysis
            static_analyzer: StaticBundleAnalyzer = container.static_bundle_analyzer()
            bundle = static_analyzer.create_static_bundle(csv_path, graph_name)
            logger.info("Created bundle using fast static analysis")
        except Exception as e:
            # Fall back to full CSV parsing if needed
            logger.warning(f"Static analysis failed, using full CSV parsing: {e}")
            bundle = graph_bundle_service.create_bundle_from_csv(
                csv_path, config_file, csv_hash, graph_name
            )

        # Save bundle to cache
        bundle_path = app_config_service.get_cache_path() / "bundles" / f"{csv_hash[:8]}.json"
        save_result: StorageResult = graph_bundle_service.save_bundle(bundle, bundle_path)
        
        if save_result.success:
            bundle_path = Path(save_result.file_path)
            # Register in registry for future lookups
            registry_service.register(csv_hash, graph_name, bundle_path, csv_path)
            logger.info(f"Bundle saved and registered: {bundle_path}")
        else:
            logger.warning(f"Failed to save bundle: {save_result.error}")
        
        # Log warnings for missing declarations
        if bundle.missing_declarations:
            logger.warning(
                f"Missing declarations for agent types: {', '.join(bundle.missing_declarations)}. "
                f"These agents will need to be defined before graph execution."
            )

    return bundle


def handle_command_error(e: Exception, verbose: bool = False) -> None:
    """
    Standard error handling for CLI commands.
    
    Args:
        e: Exception that occurred
        verbose: Whether to show detailed traceback
    """
    typer.secho(f"❌ Error: {str(e)}", fg=typer.colors.RED)
    
    if verbose:
        import traceback
        typer.secho("\nDetailed error trace:", fg=typer.colors.YELLOW)
        typer.echo(traceback.format_exc())
    
    raise typer.Exit(code=1)
