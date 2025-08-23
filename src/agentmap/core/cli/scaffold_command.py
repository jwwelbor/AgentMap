"""
CLI scaffold command handler for agent and function generation.

This module provides the scaffold command that generates agent
and routing function templates based on bundle analysis.
"""

import typer
from pathlib import Path
from typing import Optional

from agentmap.di import initialize_di
from agentmap.core.cli.cli_utils import (
    resolve_csv_path,
    get_or_create_bundle,
    handle_command_error
)
from agentmap.models.scaffold_types import ScaffoldOptions
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.graph_scaffold_service import GraphScaffoldService

def scaffold_command(
    csv_file: Optional[str] = typer.Argument(
        None, help="CSV file path (shorthand for --csv)"
    ),
    graph: Optional[str] = typer.Option(
        None, "--graph", "-g", help="Graph name to scaffold agents for"
    ),
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
    output_dir: Optional[str] = typer.Option(
        None, "--output", "-o", help="Directory for agent output"
    ),
    func_dir: Optional[str] = typer.Option(
        None, "--functions", "-f", help="Directory for function output"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing agent files"
    ),
):
    """
    Scaffold agents and routing functions using bundle analysis.
    
    Uses the same bundle-based approach as the run command, avoiding CSV re-parsing.
    Supports shorthand: agentmap scaffold file.csv
    """
    try:
        # Resolve CSV path using utility
        csv_path = resolve_csv_path(csv_file, csv)
        
        # Initialize DI container
        container = initialize_di(config_file)
        
        # Get or create bundle using utility
        typer.echo(f"📦 Analyzing graph structure from: {csv_path}")
        bundle = get_or_create_bundle(container, csv_path, graph, config_file)
        
        # Get scaffold service
        scaffold_service:GraphScaffoldService = container.graph_scaffold_service()
                
        # Determine output paths (CLI args override config)
        output_path = Path(output_dir) if output_dir else None
        functions_path = Path(func_dir) if func_dir else None
        
        # Create scaffold options
        scaffold_options = ScaffoldOptions(
            graph_name=bundle.graph_name or graph,
            output_path=output_path,
            function_path=functions_path,
            overwrite_existing=overwrite,
        )
        
        # Execute scaffolding directly from bundle (no CSV re-parsing!)
        typer.echo(f"🔨 Scaffolding agents for graph: {bundle.graph_name or 'default'}")
        
        # Check for missing declarations in bundle
        if bundle.missing_declarations:
            typer.echo(f"   Found {len(bundle.missing_declarations)} undefined agent types")
        
        # Use the bundle-based scaffolding method
        result = scaffold_service.scaffold_from_bundle(bundle, scaffold_options)
        
        # Process results
        if result.errors:
            typer.secho("⚠️ Scaffolding completed with errors:", fg=typer.colors.YELLOW)
            for error in result.errors:
                typer.secho(f"   {error}", fg=typer.colors.RED)
        
        if result.scaffolded_count == 0:
            if bundle.graph_name:
                typer.secho(
                    f"No unknown agents or functions found to scaffold in graph '{bundle.graph_name}'.",
                    fg=typer.colors.YELLOW,
                )
            else:
                typer.secho(
                    "No unknown agents or functions found to scaffold.",
                    fg=typer.colors.YELLOW,
                )
        else:
            # Success message
            typer.secho(
                f"✅ Scaffolded {result.scaffolded_count} agents/functions.",
                fg=typer.colors.GREEN,
            )
            
            # Show service statistics if available
            if result.service_stats:
                typer.secho("   📊 Service integrations:", fg=typer.colors.CYAN)
                for service, count in result.service_stats.items():
                    typer.secho(f"      {service}: {count} agents", fg=typer.colors.CYAN)
            
            # Show created files (limited)
            if result.created_files:
                typer.secho("   📁 Created files:", fg=typer.colors.CYAN)
                for file_path in result.created_files[:5]:
                    typer.secho(f"      {file_path.name}", fg=typer.colors.CYAN)
                if len(result.created_files) > 5:
                    typer.secho(
                        f"      ... and {len(result.created_files) - 5} more files",
                        fg=typer.colors.CYAN,
                    )
            
            # Invalidate the cached bundle since we created new agents
            if result.scaffolded_count > 0:
                typer.echo("\n🔄 Invalidating cached bundle after scaffolding...")
                
                # Get services from container
                bundle_service: GraphBundleService = container.graph_bundle_service()
                registry_service = container.graph_registry_service()
                
                try:
                    # Delete the cached bundle file using the service
                    deleted = bundle_service.delete_bundle(bundle)
                    
                    if deleted:
                        # Remove from registry after successful deletion
                        registry_service.remove_entry(bundle.csv_hash)
                        typer.echo("   ✅ Bundle cache cleared. Next run will detect newly scaffolded agents.")
                    else:
                        typer.echo("   ℹ️ No cached bundle found to invalidate.")
                        
                except ValueError as e:
                    typer.echo(f"   ⚠️ Invalid bundle: {e}")
                except (PermissionError, IOError) as e:
                    typer.echo(f"   ⚠️ Could not delete cached bundle: {e}")
                    # Still try to remove from registry even if file deletion failed
                    try:
                        registry_service.remove_entry(bundle.csv_hash)
                    except Exception:
                        pass  # Registry cleanup is best-effort
            
    except Exception as e:
        typer.secho(f"❌ Scaffold operation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
