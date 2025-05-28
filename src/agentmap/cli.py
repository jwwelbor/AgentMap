import json
from pathlib import Path

import typer
import yaml

from agentmap.agents.builtins.storage import (get_storage_config_path, load_storage_config)
from agentmap.di import initialize_di
from agentmap.runner import run_graph

app = typer.Typer()

from agentmap.validation import (
    validate_csv, validate_config, validate_both, print_validation_summary,
    clear_validation_cache, get_validation_cache_stats, cleanup_validation_cache
)


@app.command("validate-csv")
def validate_csv_command(
    csv_path: str = typer.Option(None, "--csv", "-c", help="Path to CSV file to validate"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache and force re-validation"),
    config_file: str = typer.Option(None, "--config", help="Path to custom config file")
):
    """Validate a CSV workflow definition file."""
    # Initialize DI with optional config file
    container = initialize_di(config_file)
    configuration = container.configuration()
    
    # Determine CSV path
    csv_file = Path(csv_path) if csv_path else configuration.get_csv_path()
    
    if not csv_file.exists():
        typer.secho(f"❌ CSV file not found: {csv_file}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    typer.echo(f"Validating CSV file: {csv_file}")
    
    try:
        result = validate_csv(csv_file, use_cache=not no_cache)
        
        # Print results
        print_validation_summary(result)
        
        # Exit with appropriate code
        if result.has_errors:
            raise typer.Exit(code=1)
        elif result.has_warnings:
            typer.echo("\n⚠️  Validation completed with warnings")
            raise typer.Exit(code=0)
        else:
            typer.secho("\n✅ CSV validation passed!", fg=typer.colors.GREEN)
            
    except Exception as e:
        typer.secho(f"❌ Validation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("validate-config")
def validate_config_command(
    config_path: str = typer.Option("agentmap_config.yaml", "--config", "-c", help="Path to config file to validate"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache and force re-validation")
):
    """Validate a YAML configuration file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        typer.secho(f"❌ Config file not found: {config_file}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    typer.echo(f"Validating config file: {config_file}")
    
    try:
        result = validate_config(config_file, use_cache=not no_cache)
        
        # Print results
        print_validation_summary(None, result)
        
        # Exit with appropriate code
        if result.has_errors:
            raise typer.Exit(code=1)
        elif result.has_warnings:
            typer.echo("\n⚠️  Validation completed with warnings")
            raise typer.Exit(code=0)
        else:
            typer.secho("\n✅ Config validation passed!", fg=typer.colors.GREEN)
            
    except Exception as e:
        typer.secho(f"❌ Validation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("validate-all")
def validate_all_command(
    csv_path: str = typer.Option(None, "--csv", help="Path to CSV file to validate"),
    config_path: str = typer.Option("agentmap_config.yaml", "--config", "-c", help="Path to config file to validate"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache and force re-validation"),
    fail_on_warnings: bool = typer.Option(False, "--fail-on-warnings", help="Treat warnings as errors")
):
    """Validate both CSV and configuration files."""
    # Initialize DI with config file
    container = initialize_di(config_file)
    configuration = container.configuration()
    
    # Determine paths
    csv_file = Path(csv_path) if csv_path else configuration.get_csv_path()
    config_file = Path(config_path)
    
    # Check files exist
    missing_files = []
    if not csv_file.exists():
        missing_files.append(f"CSV: {csv_file}")
    if not config_file.exists():
        missing_files.append(f"Config: {config_file}")
    
    if missing_files:
        typer.secho(f"❌ Files not found: {', '.join(missing_files)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    typer.echo(f"Validating files:")
    typer.echo(f"  CSV: {csv_file}")
    typer.echo(f"  Config: {config_file}")
    
    try:
        csv_result, config_result = validate_both(
            csv_file, 
            config_file, 
            use_cache=not no_cache
        )
        
        # Print results
        print_validation_summary(csv_result, config_result)
        
        # Determine exit code
        has_errors = csv_result.has_errors or (config_result.has_errors if config_result else False)
        has_warnings = csv_result.has_warnings or (config_result.has_warnings if config_result else False)
        
        if has_errors:
            raise typer.Exit(code=1)
        elif has_warnings and fail_on_warnings:
            typer.echo("\n❌ Failing due to warnings (--fail-on-warnings enabled)")
            raise typer.Exit(code=1)
        elif has_warnings:
            typer.echo("\n⚠️  Validation completed with warnings")
            raise typer.Exit(code=0)
        else:
            typer.secho("\n✅ All validation passed!", fg=typer.colors.GREEN)
            
    except Exception as e:
        typer.secho(f"❌ Validation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("validate-cache")
def validate_cache_command(
    clear: bool = typer.Option(False, "--clear", help="Clear all validation cache"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove expired cache entries"),
    stats: bool = typer.Option(False, "--stats", help="Show cache statistics"),
    file_path: str = typer.Option(None, "--file", help="Clear cache for specific file only")
):
    """Manage validation result cache."""
    
    if clear:
        if file_path:
            removed = clear_validation_cache(file_path)
            typer.secho(f"✅ Cleared {removed} cache entries for {file_path}", fg=typer.colors.GREEN)
        else:
            removed = clear_validation_cache()
            typer.secho(f"✅ Cleared {removed} cache entries", fg=typer.colors.GREEN)
    
    elif cleanup:
        removed = cleanup_validation_cache()
        typer.secho(f"✅ Removed {removed} expired cache entries", fg=typer.colors.GREEN)
    
    elif stats or not (clear or cleanup):
        # Show stats by default if no other action specified
        cache_stats = get_validation_cache_stats()
        
        typer.echo("Validation Cache Statistics:")
        typer.echo("=" * 30)
        typer.echo(f"Total files: {cache_stats['total_files']}")
        typer.echo(f"Valid files: {cache_stats['valid_files']}")
        typer.echo(f"Expired files: {cache_stats['expired_files']}")
        typer.echo(f"Corrupted files: {cache_stats['corrupted_files']}")
        
        if cache_stats['expired_files'] > 0:
            typer.echo(f"\n💡 Run 'agentmap validate-cache --cleanup' to remove expired entries")
        
        if cache_stats['corrupted_files'] > 0:
            typer.echo(f"⚠️  Found {cache_stats['corrupted_files']} corrupted cache files")



@app.command()
def scaffold(
    graph: str = typer.Option(None, "--graph", "-g", help="Graph name to scaffold agents for"),
    csv: str = typer.Option(None, "--csv", help="CSV path override"),
    output_dir: str = typer.Option(None, "--output", "-o", help="Directory for agent output"),
    func_dir: str = typer.Option(None, "--functions", "-f", help="Directory for function output"),
    config_file: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Scaffold agents and routing functions from the configured CSV, optionally for a specific graph."""
    # Initialize DI with optional config file
    container = initialize_di(config_file)
    
    # Get configuration from DI container
    configuration = container.configuration()
    
    # Get a logger from the logging service
    logging_service = container.logging_service()
    logger = logging_service.get_logger("agentmap.scaffold")
    
    # Determine actual paths to use (CLI args override config)
    csv_path = Path(csv) if csv else configuration.get_csv_path()
    output_path = Path(output_dir) if output_dir else configuration.get_custom_agents_path()
    functions_path = Path(func_dir) if func_dir else configuration.get_functions_path()
    
    # Import here to avoid circular imports
    from agentmap.graph.scaffold import scaffold_agents
    
    # Call scaffold with explicit paths and logger
    scaffolded = scaffold_agents(
        csv_path=csv_path,
        output_path=output_path,
        func_path=functions_path,
        graph_name=graph,
        logger=logger
    )
    
    if not scaffolded:
        typer.secho(f"No unknown agents or functions found to scaffold{' in graph ' + graph if graph else ''}.", fg=typer.colors.YELLOW)
    else:
        typer.secho(f"✅ Scaffolded {scaffolded} agents/functions.", fg=typer.colors.GREEN)


@app.command()
def export(
    graph: str = typer.Option(..., "--graph", "-g", help="Graph name to export"),
    output: str = typer.Option("generated_graph.py", "--output", "-o", help="Output Python file"),
    format: str = typer.Option("python", "--format", "-f", help="Export format (python, pickle, source)"),
    csv: str = typer.Option(None, "--csv", help="CSV path override"),
    state_schema: str = typer.Option("dict", "--state-schema", "-s", 
                                    help="State schema type (dict, pydantic:<ModelName>, or custom)"),
    config_file: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    initialize_di(config_file)

    from agentmap.graph.serialization import export_graph as export_graph_func

    """Export the specified graph in the chosen format."""
    export_graph_func(
        graph, 
        format=format, 
        output_path=output, 
        csv_path=csv,
        state_schema=state_schema
    )


@app.command("compile")
def compile_cmd(
    graph: str = typer.Option(None, "--graph", "-g", help="Compile a single graph"),
    output_dir: str = typer.Option(None, "--output", "-o", help="Output directory for compiled graphs"),
    csv: str = typer.Option(None, "--csv", help="CSV path override"),
    state_schema: str = typer.Option("dict", "--state-schema", "-s", 
                                    help="State schema type (dict, pydantic:<ModelName>, or custom)"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Validate CSV before compiling"),
    config_file: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Compile a graph or all graphs from the CSV to pickle files."""
    
    container = initialize_di(config_file)

    # Validate if requested (default: True)
    if validate:
        from agentmap.validation import validate_csv_for_compilation
        
        configuration = container.configuration()
        csv_file = Path(csv) if csv else configuration.get_csv_path()
        
        typer.echo(f"🔍 Validating CSV file: {csv_file}")
        try:
            validate_csv_for_compilation(csv_file)
            typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"❌ CSV validation failed: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    from agentmap.graph.serialization import (compile_all, export_as_pickle, export_as_source)

    if graph:
        export_as_pickle(
            graph, 
            output_path=output_dir, 
            csv_path=csv,
            state_schema=state_schema
        )
        export_as_source(
            graph, 
            output_path=output_dir, 
            csv_path=csv,
            state_schema=state_schema
        )

    else:
        compile_all(
            csv_path=csv,
            state_schema=state_schema
        )

@app.command()
def run(
    graph: str = typer.Option(None, "--graph", "-g", help="Graph name to run"),
    csv: str = typer.Option(None, "--csv", help="CSV path override"),
    state: str = typer.Option("{}", "--state", "-s", help="Initial state as JSON string"),  
    autocompile: bool = typer.Option(None, "--autocompile", "-a", help="Autocompile graph if missing"),
    validate: bool = typer.Option(False, "--validate", help="Validate CSV before running"),
    config_file: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Run a graph with optional CSV, initial state, and autocompile support."""
    container = initialize_di(config_file)

    # Validate if requested
    if validate:
        from agentmap.validation import validate_csv_for_compilation
        
        configuration = container.configuration()
        csv_file = Path(csv) if csv else configuration.get_csv_path()
        
        typer.echo(f"🔍 Validating CSV file: {csv_file}")
        try:
            validate_csv_for_compilation(csv_file)
            typer.secho("✅ CSV validation passed", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"❌ CSV validation failed: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    try:
        data = json.loads(state)  
    except json.JSONDecodeError:
        typer.secho("❌ Invalid JSON passed to --state", fg=typer.colors.RED) 
        raise typer.Exit(code=1)

    output = run_graph(
        graph_name=graph,  # Can be None
        initial_state=data, 
        csv_path=csv, 
        autocompile_override=autocompile
    )
    print("✅ Output:", output)    


@app.command()
def config(
    config_file: str = typer.Option(None, "--path", "-p", help="Path to config file to display")
):
    """Print the current configuration values."""
    # Initialize the container
    container = initialize_di(config_file)
    
    # Get configuration from the container
    configuration = container.configuration()
    config_data = configuration.get_all()

    print("Configuration values:")
    print("---------------------")
    for k, v in config_data.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for sub_k, sub_v in v.items():
                if isinstance(sub_v, dict):
                    print(f"  {sub_k}:")
                    for deep_k, deep_v in sub_v.items():
                        print(f"    {deep_k}: {deep_v}")
                else:
                    print(f"  {sub_k}: {sub_v}")
        else:
            print(f"{k}: {v}")


@app.command("storage-config")
def storage_config_cmd(
    init: bool = typer.Option(False, "--init", "-i", help="Initialize a default storage configuration file"),
    path: str = typer.Option(None, "--path", "-p", help="Path to storage config file"),
    storage_config_file: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Display or initialize storage configuration."""
    #initialize_di_storage(storage_config_file)
    if init:
        # Get the storage config path
        storage_path = get_storage_config_path(storage_config_file)
        
        # Check if file already exists
        if storage_path.exists():
            overwrite = typer.confirm(f"Storage config already exists at {storage_path}. Overwrite?")
            if not overwrite:
                typer.echo("Aborted.")
                return
        
        # Create default storage config
        default_config = {
            "csv": {
                "default_directory": "data/csv",
                "collections": {
                    "users": "data/csv/users.csv",
                    "products": "data/csv/products.csv"
                }
            },
            "vector": {
                "default_provider": "local",
                "collections": {
                    "documents": {
                        "provider": "local",
                        "path": "data/vector/documents"
                    }
                }
            },
            "kv": {
                "default_provider": "local",
                "collections": {
                    "settings": {
                        "provider": "local",
                        "path": "data/kv/settings.json"
                    }
                }
            }
        }
        
        # Create directory if needed
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        with open(storage_path, "w") as f:
            yaml.dump(default_config, f, sort_keys=False, default_flow_style=False)
        
        typer.secho(f"✅ Created default storage configuration at {storage_path}", fg=typer.colors.GREEN)
    else:
        # Display current storage configuration
        storage_config = load_storage_config(storage_config_file)
        typer.echo("Storage Configuration:")
        typer.echo("----------------------")
        for storage_type, config in storage_config.items():
            typer.echo(f"{storage_type}:")
            for key, value in config.items():
                if isinstance(value, dict):
                    typer.echo(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, dict):
                            typer.echo(f"    {sub_key}:")
                            for deep_key, deep_value in sub_value.items():
                                typer.echo(f"      {deep_key}: {deep_value}")
                        else:
                            typer.echo(f"    {sub_key}: {sub_value}")
                else:
                    typer.echo(f"  {key}: {value}")


# Should be refactored to list capabilities... or maybe read custom agents?
#
# @app.command()
# def list_agents():
#     """List all available agent types in the current environment."""
#     agents = get_agent_map()
#
#     typer.echo("Available Agent Types:")
#     typer.echo("=====================")
#
#     # Core agents
#     typer.echo("\nCore Agents:")
#     for agent_type in ["default", "echo", "branching", "success", "failure", "input", "graph"]:
#         typer.echo(f"  - {agent_type}")
#
#     # LLM agents
#     if HAS_LLM_AGENTS:
#         typer.echo("\nLLM Agents:")
#         for agent_type in ["openai", "anthropic", "google", "llm"]:
#             typer.echo(f"  - {agent_type}")
#     else:
#         typer.echo("\nLLM Agents: [Not Available] - Install with: pip install agentmap[llm]")
#
#     # Storage agents
#     if HAS_STORAGE_AGENTS:
#         typer.echo("\nStorage Agents:")
#         for agent_type in ["csv_reader", "csv_writer", "json_reader", "json_writer",
#                           "file_reader", "file_writer", "vector_reader", "vector_writer"]:
#             typer.echo(f"  - {agent_type}")
#     else:
#         typer.echo("\nStorage Agents: [Not Available] - Install with: pip install agentmap[storage]")

#@app.command()
# def inspect_logging():
#     """Inspect the current logging configuration."""
#     from agentmap.logging.logger import inspect_loggers
#
#     loggers_info = inspect_loggers()
#     typer.echo("Current Logger Configuration:")
#     typer.echo("----------------------------")
#
#     # Print root logger first
#     if "root" in loggers_info:
#         root_info = loggers_info.pop("root")
#         typer.echo("ROOT LOGGER:")
#         typer.echo(f"  Level: {root_info['level']}")
#         typer.echo(f"  Handlers: {', '.join(root_info['handlers'])}")
#         typer.echo(f"  Disabled: {root_info['disabled']}")
#         typer.echo(f"  Propagate: {root_info['propagate']}")
#
#     # Then print all other loggers
#     for name, info in sorted(loggers_info.items()):
#         typer.echo(f"\n{name}:")
#         typer.echo(f"  Level: {info['level']}")
#         typer.echo(f"  Handlers: {', '.join(info['handlers'])}")
#         typer.echo(f"  Disabled: {info['disabled']}")
#         typer.echo(f"  Propagate: {info['propagate']}")

@app.command("diagnose")
def diagnose_command():
    """Check and display dependency status for all components."""
    from agentmap.features_registry import features
    from agentmap.agents.dependency_checker import check_llm_dependencies, check_storage_dependencies
    
    typer.echo("AgentMap Dependency Diagnostics")
    typer.echo("=============================")
    
    # Check LLM dependencies
    typer.echo("\nLLM Dependencies:")
    llm_enabled = features.is_feature_enabled("llm")
    typer.echo(f"LLM feature enabled: {llm_enabled}")
    
    for provider in ["openai", "anthropic", "google"]:
        # Always get fresh dependency info
        has_deps, missing = check_llm_dependencies(provider)
        
        # Check registry status for comparison
        registered = features.is_provider_registered("llm", provider)
        validated = features.is_provider_validated("llm", provider)
        available = features.is_provider_available("llm", provider)
        
        status = "✅ Available" if has_deps and available else "❌ Not available"
        
        # Detect inconsistencies
        if has_deps and not available:
            status = "⚠️ Dependencies OK but provider not available (Registration issue)"
        elif not has_deps and available:
            status = "⚠️ INCONSISTENT: Provider marked available but dependencies missing"
        
        if missing:
            status += f" (Missing: {', '.join(missing)})"
            
        # Add registry status
        status += f" [Registry: reg={registered}, val={validated}, avail={available}]"
        
        typer.echo(f"  {provider.capitalize()}: {status}")
    
    # Check storage dependencies
    typer.echo("\nStorage Dependencies:")
    storage_enabled = features.is_feature_enabled("storage")
    typer.echo(f"Storage feature enabled: {storage_enabled}")
    
    for storage_type in ["csv", "vector", "firebase", "azure_blob", "aws_s3", "gcp_storage"]:
        available = features.is_provider_available("storage", storage_type)
        has_deps, missing = check_storage_dependencies(storage_type)
        
        status = "✅ Available" if available else "❌ Not available"
        if not has_deps and missing:
            status += f" (Missing: {', '.join(missing)})"
        
        typer.echo(f"  {storage_type}: {status}")
    
    # Installation suggestions
    typer.echo("\nInstallation Suggestions:")
    
    # Always check dependencies directly for accurate reporting
    has_llm, missing_llm = check_llm_dependencies()
    has_openai, missing_openai = check_llm_dependencies("openai")
    has_anthropic, missing_anthropic = check_llm_dependencies("anthropic")
    has_google, missing_google = check_llm_dependencies("google")
    
    if not has_llm or not llm_enabled:
        typer.echo("  To enable LLM agents: pip install agentmap[llm]")
    if not storage_enabled:
        typer.echo("  To enable storage agents: pip install agentmap[storage]")
    
    # Provider-specific suggestions
    if not has_openai:
        typer.echo("  For OpenAI support: pip install agentmap[openai] or pip install openai>=1.0.0")
    if not has_anthropic:
        typer.echo("  For Anthropic support: pip install agentmap[anthropic] or pip install anthropic")
    if not has_google:
        typer.echo("  For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai")
    
    # Show path and Python info
    typer.echo("\nEnvironment Information:")
    import sys
    import os
    typer.echo(f"  Python Version: {sys.version}")
    typer.echo(f"  Python Path: {sys.executable}")
    typer.echo(f"  Current Directory: {os.getcwd()}")
    
    # List installed versions of LLM packages
    typer.echo("\nRelevant Package Versions:")
    packages = ["openai", "anthropic", "google.generativeai", "langchain", "langchain_google_genai"]
    for package in packages:
        try:
            if "." in package:
                base_pkg = package.split(".")[0]
                module = __import__(base_pkg)
                typer.echo(f"  {package}: Installed (base package {base_pkg})")
            else:
                module = __import__(package)
                version = getattr(module, "__version__", "unknown")
                typer.echo(f"  {package}: v{version}")
        except ImportError:
            typer.echo(f"  {package}: Not installed")



if __name__ == "__main__":    
    app()