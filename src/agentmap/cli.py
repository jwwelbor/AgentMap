import json

import typer
import yaml

from agentmap.agents.builtins.storage import (get_storage_config_path, load_storage_config)
from agentmap.config import load_config
from agentmap.graph.scaffold import scaffold_agents
from agentmap.graph.serialization import (compile_all, export_as_pickle,
                                          export_as_source)
from agentmap.graph.serialization import export_graph as export_graph_func
from agentmap.runner import run_graph
from agentmap.agents import get_agent_map
from agentmap.agents.features import (HAS_LLM_AGENTS, HAS_STORAGE_AGENTS)

app = typer.Typer()


@app.command()
def scaffold(
    graph: str = typer.Option(None, "--graph", "-g", help="Graph name to scaffold agents for"),
    csv: str = typer.Option(None, "--csv", help="CSV path override"),
    config: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Scaffold agents and routing functions from the configured CSV, optionally for a specific graph."""
    scaffolded = scaffold_agents(csv_path=csv, graph_name=graph, config_path=config)
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
    config: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Export the specified graph in the chosen format."""
    export_graph_func(
        graph, 
        format=format, 
        output_path=output, 
        csv_path=csv,
        state_schema=state_schema,
        config_path=config
    )


@app.command("compile")
def compile_cmd(
    graph: str = typer.Option(None, "--graph", "-g", help="Compile a single graph"),
    output_dir: str = typer.Option(None, "--output", "-o", help="Output directory for compiled graphs"),
    csv: str = typer.Option(None, "--csv", help="CSV path override"),
    state_schema: str = typer.Option("dict", "--state-schema", "-s", 
                                    help="State schema type (dict, pydantic:<ModelName>, or custom)"),
    config: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Compile a graph or all graphs from the CSV to pickle files."""
    
    if graph:
        export_as_pickle(
            graph, 
            output_path=output_dir, 
            csv_path=csv,
            state_schema=state_schema,
            config_path=config
        )
        export_as_source(
            graph, 
            output_path=output_dir, 
            csv_path=csv,
            state_schema=state_schema,
            config_path=config
        )

    else:
        compile_all(
            csv_path=csv,
            state_schema=state_schema,
            config_path=config
        )

def initialize(config_path=None):
    """
    Initialize configuration and logging.
    
    Args:
        config_path: Optional path to a custom config file
    """
    # Load configuration once at startup with the provided path
    from agentmap.config import load_config
    config = load_config(config_path)
    
    # Configure logging with the loaded config
    from agentmap.logging import configure_logging
    configure_logging(config.get("logging", {}))

@app.command()
def run(
    graph: str = typer.Option(None, "--graph", "-g", help="Graph name to run"),
    csv: str = typer.Option(None, "--csv", help="CSV path override"),
    state: str = typer.Option("{}", "--state", "-s", help="Initial state as JSON string"),  
    autocompile: bool = typer.Option(None, "--autocompile", "-a", help="Autocompile graph if missing"),
    config: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Run a graph with optional CSV, initial state, and autocompile support."""
    # Initialize with config path
    initialize(config)

    """Run a graph with optional CSV, initial state, and autocompile support."""
    try:
        data = json.loads(state)  
    except json.JSONDecodeError:
        typer.secho("❌ Invalid JSON passed to --state", fg=typer.colors.RED) 
        raise typer.Exit(code=1)

    output = run_graph(
        graph_name=graph,  # Can be None
        initial_state=data, 
        csv_path=csv, 
        autocompile_override=autocompile,
        config_path=config
    )
    print("✅ Output:", output)


@app.command()
def config(
    path: str = typer.Option(None, "--path", "-p", help="Path to config file to display")
):
    """Print the current configuration values."""
    config_data = load_config(path)
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
    config: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Display or initialize storage configuration."""
    if init:
        # Get the storage config path
        storage_path = get_storage_config_path(config)
        
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
        storage_config = load_storage_config(config)
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

@app.command()
def list_agents():
    """List all available agent types in the current environment."""
    agents = get_agent_map()
    
    typer.echo("Available Agent Types:")
    typer.echo("=====================")
    
    # Core agents
    typer.echo("\nCore Agents:")
    for agent_type in ["default", "echo", "branching", "success", "failure", "input", "graph"]:
        typer.echo(f"  - {agent_type}")
    
    # LLM agents
    if HAS_LLM_AGENTS:
        typer.echo("\nLLM Agents:")
        for agent_type in ["openai", "anthropic", "google", "llm"]:
            typer.echo(f"  - {agent_type}")
    else:
        typer.echo("\nLLM Agents: [Not Available] - Install with: pip install agentmap[llm]")
    
    # Storage agents
    if HAS_STORAGE_AGENTS:
        typer.echo("\nStorage Agents:")
        for agent_type in ["csv_reader", "csv_writer", "json_reader", "json_writer", 
                          "file_reader", "file_writer", "vector_reader", "vector_writer"]:
            typer.echo(f"  - {agent_type}")
    else:
        typer.echo("\nStorage Agents: [Not Available] - Install with: pip install agentmap[storage]")

@app.command()
def inspect_logging():
    """Inspect the current logging configuration."""
    from agentmap.logging.logger import inspect_loggers
    
    loggers_info = inspect_loggers()
    typer.echo("Current Logger Configuration:")
    typer.echo("----------------------------")
    
    # Print root logger first
    if "root" in loggers_info:
        root_info = loggers_info.pop("root")
        typer.echo("ROOT LOGGER:")
        typer.echo(f"  Level: {root_info['level']}")
        typer.echo(f"  Handlers: {', '.join(root_info['handlers'])}")
        typer.echo(f"  Disabled: {root_info['disabled']}")
        typer.echo(f"  Propagate: {root_info['propagate']}")
    
    # Then print all other loggers
    for name, info in sorted(loggers_info.items()):
        typer.echo(f"\n{name}:")
        typer.echo(f"  Level: {info['level']}")
        typer.echo(f"  Handlers: {', '.join(info['handlers'])}")
        typer.echo(f"  Disabled: {info['disabled']}")
        typer.echo(f"  Propagate: {info['propagate']}")

if __name__ == "__main__":
    app()