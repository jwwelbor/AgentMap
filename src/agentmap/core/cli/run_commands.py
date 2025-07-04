"""
CLI run command handlers using the new service architecture.

This module provides run-specific commands that maintain compatibility
with existing interfaces while using GraphRunnerService.
"""

import json
from pathlib import Path
from typing import Optional

import typer

from agentmap.core.adapters import create_service_adapter, validate_run_parameters
from agentmap.di import initialize_application, initialize_di
from agentmap.infrastructure.interaction.cli_handler import CLIInteractionHandler


def run_command(
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
    """Run a graph with optional CSV, initial state, and autocompile support."""
    try:
        # Validate parameters early
        validate_run_parameters(csv=csv, state=state)

        # Initialize DI container with agent bootstrap (agents needed for graph execution)
        container = initialize_application(config_file)
        adapter = create_service_adapter(container)
        validation_service = container.validation_service

        # Get execution formatter service
        formatter_service = container.execution_formatter_service()

        # Get services
        graph_runner_service, app_config_service, logging_service = (
            adapter.initialize_services()
        )
        logger = logging_service.get_logger("agentmap.cli.run")

        # Validate CSV if requested
        if validate:
            logger.info("Validating CSV file before execution")

            csv_path = Path(csv) if csv else app_config_service.get_csv_path()
            typer.echo(f"🔍 Validating CSV file: {csv_path}")

            try:
                validation_service.validate_csv_for_compilation(csv_path)
                typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"❌ CSV validation failed: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        # Create run options using adapter
        run_options = adapter.create_run_options(
            csv=csv, state=state, autocompile=autocompile, config_file=config_file
        )

        # Execute graph using service (graph name separate from options)
        logger.info(f"Executing graph '{graph}' with options: {run_options}")
        result = graph_runner_service.run_graph(graph, run_options)

        # Convert result to legacy format and display
        output = adapter.extract_result_state(result)

        if result.success:
            typer.secho(
                "✅ Graph execution completed successfully", fg=typer.colors.GREEN
            )

            # Use pretty formatting if requested
            if pretty:
                formatted_output = formatter_service.format_execution_result(
                    output["final_state"], verbose=verbose
                )
                print(formatted_output)
            else:
                print("✅ Output:", output["final_state"])
        else:
            typer.secho(
                f"❌ Graph execution failed: {result.error}", fg=typer.colors.RED
            )
            raise typer.Exit(code=1)

    except Exception as e:
        # Use adapter for consistent error handling
        # Note: Using initialize_di() here for error handling to avoid double bootstrap
        error_info = create_service_adapter(initialize_di()).handle_execution_error(e)
        typer.secho(f"❌ Error: {error_info['error']}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def compile_command(
    graph: Optional[str] = typer.Option(
        None, "--graph", "-g", help="Compile a single graph"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output directory for compiled graphs"
    ),
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
    state_schema: str = typer.Option(
        "dict",
        "--state-schema",
        "-s",
        help="State schema type (dict, pydantic:<ModelName>, or custom)",
    ),
    validate: bool = typer.Option(
        True, "--validate/--no-validate", help="Validate CSV before compiling"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
    include_source: bool = typer.Option(
        True, "--include-source", help="Generate source code with compiled graph"
    ),
):
    """Compile a graph or all graphs from the CSV to pickle files."""
    container = initialize_di(config_file)
    validation_service = container.validation_service
    compilation_service = container.graph_compilation_service()

    # Validate if requested (default: True)
    if validate:
        configuration = container.app_config_service()
        csv_file = Path(csv) if csv else configuration.get_csv_path()

        typer.echo(f"🔍 Validating CSV file: {csv_file}")
        try:
            validation_service.validate_csv_for_compilation(csv_file)
            typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"❌ CSV validation failed: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    from agentmap.services.compilation_service import CompilationOptions

    compilation_options = CompilationOptions()
    compilation_options.output_dir = output_dir
    compilation_options.include_source = include_source
    compilation_options.state_schema = state_schema

    if graph:
        compilation_result = compilation_service.compile_graph(
            graph, csv_path=csv, options=compilation_options
        )
    else:
        compilation_result = compilation_service.compile_all_graphs(
            csv_path=csv, options=compilation_options
        )

    # Check compilation result and handle errors
    if hasattr(compilation_result, "success") and not compilation_result.success:
        if hasattr(compilation_result, "errors") and compilation_result.errors:
            for error in compilation_result.errors:
                typer.secho(f"❌ Compilation error: {error}", fg=typer.colors.RED)
        else:
            typer.secho("❌ Compilation failed", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    else:
        typer.secho("✅ Compilation completed successfully", fg=typer.colors.GREEN)
        print(compilation_result)


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
    """Scaffold agents and routing functions from the configured CSV, optionally for a specific graph."""
    try:
        # Initialize DI container with agent bootstrap (scaffolding needs agent discovery)
        container = initialize_application(config_file)

        # Get services through DI container
        graph_scaffold_service = container.graph_scaffold_service()
        app_config_service = container.app_config_service()
        logging_service = container.logging_service()

        # Get a logger for this operation
        logger = logging_service.get_logger("agentmap.cli.scaffold")

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
        logger.info(f"Starting scaffold operation for CSV: {csv_path}")
        result = graph_scaffold_service.scaffold_agents_from_csv(
            csv_path, scaffold_options
        )

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
            if result.service_stats and (
                result.service_stats.get("with_services", 0) > 0
            ):
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

        # Log final summary for debugging
        logger.info(
            f"Scaffold operation completed: {result.scaffolded_count} created, {len(result.errors)} errors"
        )

    except Exception as e:
        # Enhanced error handling with proper logging
        error_message = f"Scaffold operation failed: {str(e)}"

        # Try to get logger if possible
        try:
            if "logging_service" in locals():
                logger = logging_service.get_logger("agentmap.cli.scaffold")
                logger.error(error_message)
        except:
            pass  # If logging fails, continue with user feedback

        typer.secho(f"❌ Error: {error_message}", fg=typer.colors.RED)
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
        container = initialize_di(config_file)
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
        # Initialize DI container and get storage service
        container = initialize_di(config_file)
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
        logger.error(f"Unexpected error in resume command: {e}")
        typer.secho(f"❌ Unexpected error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
