"""
CLI run command handlers using ApplicationBootstrapService with Typer.

This module provides run-specific commands that use the ApplicationBootstrapService
for intelligent initialization and Bundle-based execution.
"""

import json
from pathlib import Path
from typing import Optional

import typer

from agentmap.di import initialize_di, initialize_application
from agentmap.services.graph.graph_registry_service import GraphRegistryService
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.models.storage.types import StorageResult

def get_graph_bundle(container, csv_path, graph_name, config_file) -> tuple:
    """
    Create bootstrap service with minimal dependencies.
    
    Args:
        config_file: Optional path to configuration file
        
    Returns:
        Tuple of (bootstrap_service, config_file_used)
    """

    
    # Get the ApplicationBootstrapService from the container
    registry_service: GraphRegistryService = container.graph_registry_service()
    logging_service = container.logging_service()
    graph_bundle_service: GraphBundleService = container.graph_bundle_service()
    app_config_service: AppConfigService = container.app_config_service()

    csv_hash = registry_service.compute_hash(Path(csv_path), logging_service) 
    bundle_path = registry_service.find_bundle(csv_hash)

    if bundle_path:
        # Load existing bundle (no CSV parsing!)
        bundle = graph_bundle_service.load_bundle(bundle_path)
    else:
        # Slow path - parse CSV, compile, register
        bundle = graph_bundle_service.create_bundle_from_csv(csv_path, config_file, csv_hash, graph_name )
        bundle_path = app_config_service.get_cache_path() / "bundles" / f"{csv_hash[:8]}.json"
        save_result: StorageResult = graph_bundle_service.save_bundle(bundle, bundle_path)
        if save_result.success:
            bundle_path = Path(save_result.file_path)
        registry_service.register(csv_hash, graph_name, bundle_path, csv_path)

    return bundle    


def run_command(
    csv_file: Optional[str] = typer.Argument(
        None, help="CSV file path (shorthand for --csv)"
    ),
    graph: Optional[str] = typer.Option(
        None, "--graph", "-g", help="Graph name to run"
    ),
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
    state: str = typer.Option(
        "{}", "--state", "-s", help="Initial state as JSON string"
    ),
    validate: bool = typer.Option(
        False, "--validate", help="Validate CSV before running"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
    pretty: bool = typer.Option(
        False, "--pretty", "-p", help="Format output for better readability"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed execution info with --pretty"
    ),
):
    """
    Run a graph with intelligent bootstrapping using GraphBundle.
    
    Supports shorthand: agentmap run file.csv is equivalent to agentmap run --csv file.csv
    """
    try:
        # Handle shorthand CSV file argument - positional takes precedence
        if csv_file is not None:
            csv = csv_file
        
        if not csv:
            typer.secho("❌ CSV file required", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        csv_path = Path(csv)
        if not csv_path.exists():
            typer.secho(f"❌ CSV file not found: {csv_path}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        
        # Validate CSV if requested
        if validate:
            typer.echo("🔍 Validating CSV file before execution")
            validation_service = container.validation_service()
            
            try:
                validation_service.validate_csv_for_bundling(csv_path)
                typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"❌ CSV validation failed: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        # Parse initial state early for validation
        initial_state = {}
        if state != "{}":
            try:
                initial_state = json.loads(state)
            except json.JSONDecodeError as e:
                typer.secho(f"❌ Invalid JSON in --state: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)


        # This is where the real work starts    
        # Bootstrap with bundle detection
        
        # Create minimal container for bootstrap - using initialize_di for minimal setup
        container = initialize_di(config_file)
        bundle = get_graph_bundle(container, csv_path, graph, config_file)

        # TODO: rebuild the container using the bundle to load everything needed based on bundle requirements
        container = initialize_application(config_file, bundle)

        runner = container.graph_runner_service()        
        typer.echo(f"📊 Executing graph: {bundle.graph_name or graph or 'default'}")
        result = runner.run(bundle)
        
        # Display result
        if result.success:
            typer.secho("✅ Graph execution completed successfully", fg=typer.colors.GREEN)
            
            # Handle pretty formatting if requested
            if pretty:
                formatter_service = container.execution_formatter_service()
                formatted_output = formatter_service.format_execution_result(
                    result.final_state, verbose=verbose
                )
                print(formatted_output)
            else:
                # Simple output
                print("✅ Output:", result.final_state)
        else:
            typer.secho(f"❌ Graph execution failed: {result.error}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
            
    except Exception as e:
        # Provide detailed error information
        typer.secho(f"❌ Error: {str(e)}", fg=typer.colors.RED)
        
        # Log additional details if verbose
        if verbose:
            import traceback
            typer.secho("\nDetailed error trace:", fg=typer.colors.YELLOW)
            typer.echo(traceback.format_exc())
        
        raise typer.Exit(code=1)


# def scaffold_command(
#     graph: Optional[str] = typer.Option(
#         None, "--graph", "-g", help="Graph name to scaffold agents for"
#     ),
#     csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
#     output_dir: Optional[str] = typer.Option(
#         None, "--output", "-o", help="Directory for agent output"
#     ),
#     func_dir: Optional[str] = typer.Option(
#         None, "--functions", "-f", help="Directory for function output"
#     ),
#     config_file: Optional[str] = typer.Option(
#         None, "--config", "-c", help="Path to custom config file"
#     ),
# ):
#     """Scaffold agents and routing functions with minimal initialization."""
#     try:
#         # Create bootstrap service
#         bootstrap, config_used = create_bootstrap_service(config_file)
        
#         # Use minimal bootstrap for scaffolding
#         container = bootstrap.bootstrap_for_scaffold_v2(config_used)
        
#         # Get services
#         scaffold_service = container.graph_scaffold_service()
#         app_config_service = container.app_config_service()
        
#         # Determine actual paths to use (CLI args override config)
#         csv_path = Path(csv) if csv else app_config_service.get_csv_path()
#         output_path = Path(output_dir) if output_dir else None
#         functions_path = Path(func_dir) if func_dir else None
        
#         # Create scaffold options
#         from agentmap.services.graph_scaffold_service import ScaffoldOptions
#         scaffold_options = ScaffoldOptions(
#             graph_name=graph,
#             output_path=output_path,
#             function_path=functions_path,
#             overwrite_existing=False,
#         )
        
#         # Execute scaffolding
#         typer.echo(f"🔨 Starting scaffold operation for CSV: {csv_path}")
#         result = scaffold_service.scaffold_agents_from_csv(csv_path, scaffold_options)
        
#         # Process results
#         if result.errors:
#             typer.secho("⚠️ Scaffolding completed with errors:", fg=typer.colors.YELLOW)
#             for error in result.errors:
#                 typer.secho(f"   {error}", fg=typer.colors.RED)
        
#         if result.scaffolded_count == 0:
#             if graph:
#                 typer.secho(
#                     f"No unknown agents or functions found to scaffold in graph '{graph}'.",
#                     fg=typer.colors.YELLOW,
#                 )
#             else:
#                 typer.secho(
#                     "No unknown agents or functions found to scaffold.",
#                     fg=typer.colors.YELLOW,
#                 )
#         else:
#             # Success message
#             typer.secho(
#                 f"✅ Scaffolded {result.scaffolded_count} agents/functions.",
#                 fg=typer.colors.GREEN,
#             )
            
#             # Show created files (limited)
#             if result.created_files:
#                 typer.secho("   📁 Created files:", fg=typer.colors.CYAN)
#                 for file_path in result.created_files[:5]:
#                     typer.secho(f"      {file_path.name}", fg=typer.colors.CYAN)
#                 if len(result.created_files) > 5:
#                     typer.secho(
#                         f"      ... and {len(result.created_files) - 5} more files",
#                         fg=typer.colors.CYAN,
#                     )
            
#     except Exception as e:
#         typer.secho(f"❌ Scaffold operation failed: {e}", fg=typer.colors.RED)
#         raise typer.Exit(code=1)


# def validate_command(
#     csv: Optional[str] = typer.Option(None, "--csv", help="CSV path to validate"),
#     graph: Optional[str] = typer.Option(
#         None, "--graph", "-g", help="Graph name to validate"
#     ),
#     config_file: Optional[str] = typer.Option(
#         None, "--config", "-c", help="Path to custom config file"
#     ),
# ):
#     """Validate CSV and graph configuration with minimal services."""
#     try:
#         # Create bootstrap service
#         bootstrap, config_used = create_bootstrap_service(config_file)
        
#         # Use minimal bootstrap for validation
#         container = bootstrap.bootstrap_for_validation_v2(config_used)
        
#         # Get services
#         validation_service = container.validation_service()
#         app_config_service = container.app_config_service()
        
#         # Get CSV path
#         csv_path = Path(csv) if csv else app_config_service.get_csv_path()
        
#         # Validate CSV
#         typer.echo(f"🔍 Validating CSV: {csv_path}")
#         validation_service.validate_csv_for_bundling(csv_path)
        
#         typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
        
#         # If graph name provided, could do additional graph-specific validation
#         if graph:
#             typer.echo(f"   Graph: {graph}")
        
#     except Exception as e:
#         typer.secho(f"❌ Validation failed: {e}", fg=typer.colors.RED)
#         raise typer.Exit(code=1)


# def export_command(
#     graph: str = typer.Option(..., "--graph", "-g", help="Graph name to export"),
#     output: str = typer.Option(
#         "generated_graph.py", "--output", "-o", help="Output Python file"
#     ),
#     format: str = typer.Option(
#         "python", "--format", "-f", help="Export format (python, pickle, source)"
#     ),
#     csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
#     state_schema: str = typer.Option(
#         "dict",
#         "--state-schema",
#         "-s",
#         help="State schema type (dict, pydantic:<ModelName>, or custom)",
#     ),
#     config_file: Optional[str] = typer.Option(
#         None, "--config", "-c", help="Path to custom config file"
#     ),
# ):
#     """Export the specified graph in the chosen format."""
#     try:
#         # For export, we don't need full bootstrap - just basic services
#         container = initialize_di(config_file)
#         output_service = container.graph_output_service()
        
#         # Export the graph
#         result = output_service.export_graph(graph, format, output, state_schema)
        
#         # Display success message
#         typer.secho(
#             f"✅ Graph '{graph}' exported successfully to {output}",
#             fg=typer.colors.GREEN,
#         )
        
#         # Show export details if available
#         if hasattr(result, "export_path"):
#             typer.secho(
#                 f"   📁 Export path: {result.export_path}", fg=typer.colors.CYAN
#             )
#         if hasattr(result, "format"):
#             typer.secho(f"   📋 Format: {result.format}", fg=typer.colors.CYAN)
        
#     except Exception as e:
#         typer.secho(f"❌ Export failed: {e}", fg=typer.colors.RED)
#         raise typer.Exit(code=1)


# def resume_command(
#     thread_id: str = typer.Argument(..., help="Thread ID to resume"),
#     response: str = typer.Argument(
#         ..., help="Response action (e.g., approve, reject, choose, respond, edit)"
#     ),
#     data: Optional[str] = typer.Option(
#         None, "--data", "-d", help="Additional data as JSON string"
#     ),
#     data_file: Optional[str] = typer.Option(
#         None, "--data-file", "-f", help="Path to JSON file containing additional data"
#     ),
#     config_file: Optional[str] = typer.Option(
#         None, "--config", "-c", help="Path to custom config file"
#     ),
# ):
#     """Resume an interrupted workflow by providing thread ID and response data."""
#     try:
#         # For resume, we need storage services but not full bootstrap
#         container = initialize_di(config_file)
        
#         storage_manager = container.storage_service_manager()
        
#         # Check if storage is available
#         if not storage_manager:
#             typer.secho(
#                 "❌ Storage services are not available. Please check your configuration.",
#                 fg=typer.colors.RED,
#             )
#             raise typer.Exit(code=1)
        
#         # Get storage service
#         storage_service = storage_manager.get_service("json")
#         logging_service = container.logging_service()
#         logger = logging_service.get_logger("agentmap.cli.resume")
        
#         # Parse response data
#         response_data = None
#         if data:
#             try:
#                 response_data = json.loads(data)
#             except json.JSONDecodeError as e:
#                 typer.secho(f"❌ Invalid JSON in --data: {e}", fg=typer.colors.RED)
#                 raise typer.Exit(code=1)
#         elif data_file:
#             try:
#                 with open(data_file, "r") as f:
#                     response_data = json.load(f)
#             except FileNotFoundError:
#                 typer.secho(f"❌ Data file not found: {data_file}", fg=typer.colors.RED)
#                 raise typer.Exit(code=1)
#             except json.JSONDecodeError as e:
#                 typer.secho(f"❌ Invalid JSON in file: {e}", fg=typer.colors.RED)
#                 raise typer.Exit(code=1)
        
#         # Create CLI interaction handler
#         from agentmap.infrastructure.interaction.cli_handler import CLIInteractionHandler
#         handler = CLIInteractionHandler(storage_service)
        
#         # Log the resume attempt
#         logger.info(
#             f"Resuming thread '{thread_id}' with action '{response}' and data: {response_data}"
#         )
        
#         # Resume execution
#         result = handler.resume_execution(
#             thread_id=thread_id, response_action=response, response_data=response_data
#         )
        
#         # Display success message
#         typer.secho(
#             f"✅ Successfully resumed thread '{thread_id}' with action '{response}'",
#             fg=typer.colors.GREEN,
#         )
        
#     except ValueError as e:
#         # Handle not found errors gracefully
#         typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)
#         raise typer.Exit(code=1)
#     except RuntimeError as e:
#         # Handle storage errors
#         typer.secho(f"❌ Storage error: {e}", fg=typer.colors.RED)
#         raise typer.Exit(code=1)
#     except Exception as e:
#         # Handle unexpected errors
#         typer.secho(f"❌ Unexpected error: {e}", fg=typer.colors.RED)
#         raise typer.Exit(code=1)
