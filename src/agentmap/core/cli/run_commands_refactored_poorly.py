"""
CLI run command handlers using ApplicationBootstrapService.

This module provides run-specific commands that use the new ApplicationBootstrapService
for intelligent initialization with different bootstrap methods for different commands.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import typer

from agentmap.services.application_bootstrap_service import ApplicationBootstrapService


def determine_config_file(config_file: Optional[str] = None) -> Tuple[Optional[str], str]:
    """
    Determine which config file to use with proper precedence and fallback logic.
    
    Args:
        config_file: Optional explicit config file path
        
    Returns:
        Tuple of (actual_config_path, config_source_description)
        
    Raises:
        FileNotFoundError: If explicit config file provided but doesn't exist
    """
    actual_config_path = None
    config_source = "system defaults"

    if config_file:
        # Explicit config file provided - validate it exists
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        actual_config_path = str(config_path)
        config_source = f"explicit config: {actual_config_path}"
    else:
        # Try auto-discovery - look for app_config.yaml in current directory
        app_config_path = Path.cwd() / "app_config.yaml"
        if app_config_path.exists() and app_config_path.is_file():
            actual_config_path = str(app_config_path)
            config_source = f"auto-discovered: {actual_config_path}"
        else:
            # Try agentmap_config.yaml as secondary fallback
            agentmap_config_path = Path.cwd() / "agentmap_config.yaml"
            if agentmap_config_path.exists() and agentmap_config_path.is_file():
                actual_config_path = str(agentmap_config_path)
                config_source = f"auto-discovered: {actual_config_path}"

    # Set up bootstrap logging to show config discovery result
    bootstrap_logger = logging.getLogger("agentmap.bootstrap")
    if not bootstrap_logger.handlers:
        logging.basicConfig(
            level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
        )
    bootstrap_logger.info(f"Using configuration from: {config_source}")
    
    return actual_config_path, config_source


def create_bootstrap_service(config_file: Optional[str] = None) -> Tuple[ApplicationBootstrapService, 'ApplicationContainer']:
    """
    Create bootstrap service with minimal dependencies for initialization.
    
    Args:
        config_file: Optional path to config file
        
    Returns:
        Tuple of (ApplicationBootstrapService, ApplicationContainer)
    """
    from agentmap.di.containers import ApplicationContainer
    
    # Determine config file to use
    actual_config_path, _ = determine_config_file(config_file)
    
    # Create container with config path if provided
    container = ApplicationContainer()
    if actual_config_path:
        container.config_path.override(actual_config_path)
    
    # Register only essential services needed for ApplicationBootstrapService
    # These are the core services needed before intelligent bootstrap
    container.config_service()
    container.logging_service()
    container.json_storage_service()
    container.graph_registry_service()
    container.graph_bundle_service()
    container.container_factory()
    
    # Get the bootstrap service
    bootstrap_service = container.application_bootstrap_service()
    
    return bootstrap_service, container


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
    autocompile: Optional[bool] = typer.Option(
        None, "--autocompile", "-a", help="Autocompile graph if missing"
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
    """Run a graph with intelligent bootstrapping using ApplicationBootstrapService.

    Supports shorthand: agentmap run file.csv is equivalent to agentmap run --csv file.csv
    """
    try:
        # Handle shorthand CSV file argument - positional takes precedence over --csv option
        if csv_file is not None:
            csv = csv_file

        if csv is None:
            typer.secho("❌ Error: CSV file path is required", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Validate state parameter early
        try:
            initial_state = json.loads(state)
        except json.JSONDecodeError as e:
            typer.secho(f"❌ Invalid JSON in --state: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Create bootstrap service with config file support
        bootstrap, container = create_bootstrap_service(config_file)
        
        # Bootstrap with full application initialization for running graphs
        bootstrap.bootstrap_application()
        
        # Get necessary services using container methods
        graph_runner_service = container.graph_runner_service()
        app_config_service = container.app_config_service()
        graph_bundle_service = container.graph_bundle_service()
        
        csv_path = Path(csv)
        
        # Validate CSV if requested
        if validate:
            validate_csv(compilation_service, csv_path)

        # Determine graph name
        if not graph:
            # Extract graph name from CSV filename if not provided
            graph = csv_path.stem
        
        
        
        if bundle_path.exists():
            bundle = graph_bundle_service.load_bundle(bundle_path)
            
            # Verify the bundle is current with CSV
            with open(csv_path, 'r') as f:
                csv_content = f.read()
            if not graph_bundle_service.verify_csv(bundle, csv_content):
                # Bundle is outdated, recompile
                typer.echo("📦 Bundle outdated, updating...")
                
                # compilation_result = compilation_service.compile_graph(
                #     graph_name=graph,
                #     options=compilation_options
                # )
                # if compilation_result.success:
                #     bundle = graph_bundle_service.load_bundle(bundle_path)
                # else:
                #     typer.secho(f"❌ Compilation failed: {compilation_result.error}", fg=typer.colors.RED)
                #     raise typer.Exit(code=1)
        else:
            # No bundle exists, compile it
            typer.echo("📦 No compiled graph found, compiling...")
            compilation_result = compilation_service.compile_graph(
                graph_name=graph,
                options=compilation_options
            )
            if compilation_result.success:
                bundle = graph_bundle_service.load_bundle(bundle_path)
            else:
                typer.secho(f"❌ Compilation failed: {compilation_result.error}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
        
        if not bundle:
            typer.secho("❌ Failed to create or load graph bundle", fg=typer.colors.RED)
            raise typer.Exit(code=1)
            
        # Apply any state to bundle if provided
        if initial_state and initial_state != {}:
            bundle.initial_state = initial_state
        
        # Execute with bundle
        result = graph_runner_service.run(bundle)
        
        # Display result with formatting options
        if result.success:
            typer.secho("✅ Graph execution completed successfully", fg=typer.colors.GREEN)
            
            # Use pretty formatting if requested
            if pretty:
                # Format output for better readability
                if verbose:
                    typer.echo("\n📊 Detailed Execution Output:")
                    formatted_output = json.dumps(result.final_state, indent=2, default=str)
                    print(formatted_output)
                else:
                    typer.echo("\n📊 Execution Output:")
                    # Show condensed output when not verbose
                    if isinstance(result.final_state, dict):
                        # Show just top-level keys and first few chars of values
                        for key, value in result.final_state.items():
                            value_str = str(value)
                            if len(value_str) > 50:
                                value_str = value_str[:50] + "..."
                            print(f"  {key}: {value_str}")
                    else:
                        print(f"  {result.final_state}")
            else:
                print("✅ Output:", result.final_state)
        else:
            typer.secho(f"❌ Graph execution failed: {result.error}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    except Exception as e:
        typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

def validate_csv(compilation_service, csv_path):
    typer.echo(f"🔍 Validating CSV file: {csv_path}")
            
    try:
                # Use compilation service's validation method
        errors = compilation_service.validate_before_compilation(csv_path)
        if errors:
            typer.secho(f"❌ CSV validation failed: {', '.join(errors)}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        else:
            typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ CSV validation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def scaffold_command(
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
):
    """Scaffold agents and routing functions with minimal initialization."""
    try:
        # Create bootstrap service with config file support
        bootstrap, container = create_bootstrap_service(config_file)
        
        # Bootstrap for scaffolding (minimal services only)
        bootstrap.bootstrap_for_scaffold()
        
        # Get services through DI container methods
        scaffold_service = container.graph_scaffold_service()
        app_config_service = container.app_config_service()
        
        # Determine actual paths to use (CLI args override config)
        csv_path = Path(csv) if csv else app_config_service.get_csv_path()
        output_path = Path(output_dir) if output_dir else None
        functions_path = Path(func_dir) if func_dir else None

        # Create scaffold options
        from agentmap.services.graph_scaffold_service import ScaffoldOptions

        scaffold_options = ScaffoldOptions(
            graph_name=graph,
            output_path=output_path,
            function_path=functions_path,
            overwrite_existing=False,
        )

        # Execute scaffolding using new service
        result = scaffold_service.scaffold_agents_from_csv(csv_path, scaffold_options)

        # Process results and provide user feedback
        if result.errors:
            typer.secho("⚠️ Scaffolding completed with errors:", fg=typer.colors.YELLOW)
            for error in result.errors:
                typer.secho(f"   {error}", fg=typer.colors.RED)

        if result.scaffolded_count == 0:
            if graph:
                typer.secho(
                    f"No unknown agents or functions found to scaffold in graph '{graph}'.",
                    fg=typer.colors.YELLOW,
                )
            else:
                typer.secho(
                    "No unknown agents or functions found to scaffold.",
                    fg=typer.colors.YELLOW,
                )
        else:
            # Success message with detailed information
            typer.secho(
                f"✅ Scaffolded {result.scaffolded_count} agents/functions.",
                fg=typer.colors.GREEN,
            )

            # Show service statistics if available
            if result.service_stats and (result.service_stats.get("with_services", 0) > 0):
                with_services = result.service_stats.get("with_services", 0)
                without_services = result.service_stats.get("without_services", 0)
                typer.secho(
                    f"   📊 Service integration: {with_services} with services, {without_services} basic agents",
                    fg=typer.colors.CYAN,
                )

            # Show created files (limited to avoid overwhelming output)
            if result.created_files:
                typer.secho("   📁 Created files:", fg=typer.colors.CYAN)
                for file_path in result.created_files[:5]:  # Show first 5 files
                    typer.secho(f"      {file_path.name}", fg=typer.colors.CYAN)
                if len(result.created_files) > 5:
                    typer.secho(
                        f"      ... and {len(result.created_files) - 5} more files",
                        fg=typer.colors.CYAN,
                    )

    except Exception as e:
        typer.secho(f"❌ Scaffold operation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def validate_command(
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path to validate"),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
):
    """Validate graphs and configuration with minimal services."""
    try:
        # Create bootstrap service with config file support
        bootstrap, container = create_bootstrap_service(config_file)
        
        # Bootstrap for validation (validation services only)
        bootstrap.bootstrap_for_validation()
        
        # Get compilation service for validation
        compilation_service = container.compilation_service()
        app_config_service = container.app_config_service()
        
        if csv:
            # Validate specific CSV
            csv_path = Path(csv)
            typer.echo(f"🔍 Validating CSV file: {csv_path}")
            
            try:
                errors = compilation_service.validate_before_compilation(csv_path)
                if errors:
                    typer.secho(f"❌ CSV validation failed: {', '.join(errors)}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
                else:
                    typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"❌ CSV validation failed: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
        else:
            # Validate all configurations using app config service
            typer.echo("📋 Validating configuration...")
            
            # Basic validation - check if config paths exist
            try:
                csv_path = app_config_service.get_csv_path()
                compiled_path = app_config_service.get_compiled_graphs_path()
                
                if csv_path and csv_path.exists():
                    typer.secho(f"✅ CSV path valid: {csv_path}", fg=typer.colors.GREEN)
                else:
                    typer.secho(f"❌ CSV path invalid or missing", fg=typer.colors.RED)
                    
                if compiled_path and compiled_path.exists():
                    typer.secho(f"✅ Compiled graphs path valid: {compiled_path}", fg=typer.colors.GREEN)
                else:
                    typer.secho(f"⚠️ Compiled graphs path missing (will be created): {compiled_path}", fg=typer.colors.YELLOW)
                    
                typer.secho("✅ Configuration validation completed", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"❌ Configuration validation failed: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

    except Exception as e:
        typer.secho(f"❌ Validation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def export_command(
    graph: str = typer.Option(..., "--graph", "-g", help="Graph name to export"),
    output: str = typer.Option(
        "generated_graph.py", "--output", "-o", help="Output Python file"
    ),
    format: str = typer.Option(
        "python", "--format", "-f", help="Export format (python, pickle, source)"
    ),
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
    state_schema: str = typer.Option(
        "dict",
        "--state-schema",
        "-s",
        help="State schema type (dict, pydantic:<ModelName>, or custom)",
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
):
    """Export the specified graph in the chosen format."""
    try:
        # Create bootstrap service with config file support
        bootstrap, container = create_bootstrap_service(config_file)
        
        # Use minimal initialization for export
        bootstrap.bootstrap_for_validation()
        
        output_service = container.graph_output_service()

        # Export the graph
        result = output_service.export_graph(graph, format, output, state_schema)

        # Display success message
        typer.secho(
            f"✅ Graph '{graph}' exported successfully to {output}",
            fg=typer.colors.GREEN,
        )

        # Show export details if result contains them
        if hasattr(result, "export_path"):
            typer.secho(
                f"   📁 Export path: {result.export_path}", fg=typer.colors.CYAN
            )
        if hasattr(result, "format"):
            typer.secho(f"   📋 Format: {result.format}", fg=typer.colors.CYAN)

    except Exception as e:
        typer.secho(f"❌ Export failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def resume_command(
    thread_id: str = typer.Argument(..., help="Thread ID to resume"),
    response: str = typer.Argument(
        ..., help="Response action (e.g., approve, reject, choose, respond, edit)"
    ),
    data: Optional[str] = typer.Option(
        None, "--data", "-d", help="Additional data as JSON string"
    ),
    data_file: Optional[str] = typer.Option(
        None, "--data-file", "-f", help="Path to JSON file containing additional data"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
):
    """Resume an interrupted workflow by providing thread ID and response data."""
    try:
        # Create bootstrap service with config file support
        bootstrap, container = create_bootstrap_service(config_file)
        
        # Use minimal initialization for storage access
        bootstrap.bootstrap_for_validation()
        
        # Get storage service
        storage_manager = container.storage_service_manager()

        # Check if storage is available
        if not storage_manager:
            typer.secho(
                "❌ Storage services are not available. Please check your configuration.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        # Get the default storage service (or json for structured data)
        storage_service = storage_manager.get_service("json")
        logging_service = container.logging_service()
        logger = logging_service.get_logger("agentmap.cli.resume")

        # Parse response data
        response_data = None
        if data:
            try:
                response_data = json.loads(data)
            except json.JSONDecodeError as e:
                typer.secho(f"❌ Invalid JSON in --data: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
        elif data_file:
            try:
                with open(data_file, "r") as f:
                    response_data = json.load(f)
            except FileNotFoundError:
                typer.secho(f"❌ Data file not found: {data_file}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            except json.JSONDecodeError as e:
                typer.secho(f"❌ Invalid JSON in file: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        # Create CLI interaction handler instance
        from agentmap.infrastructure.interaction.cli_handler import CLIInteractionHandler
        handler = CLIInteractionHandler(storage_service)

        # Log the resume attempt
        logger.info(
            f"Resuming thread '{thread_id}' with action '{response}' and data: {response_data}"
        )

        # Call handler.resume_execution()
        result = handler.resume_execution(
            thread_id=thread_id, response_action=response, response_data=response_data
        )

        # Display success message
        typer.secho(
            f"✅ Successfully resumed thread '{thread_id}' with action '{response}'",
            fg=typer.colors.GREEN,
        )

    except ValueError as e:
        # Handle not found errors gracefully
        typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except RuntimeError as e:
        # Handle storage errors
        typer.secho(f"❌ Storage error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        # Handle unexpected errors
        typer.secho(f"❌ Unexpected error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
