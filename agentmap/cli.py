import json
import typer

from agentmap.config import load_config
from agentmap.graph.scaffold import scaffold_agents
from agentmap.graph.serialization import (compile_all, export_as_pickle, export_as_source)
from agentmap.graph.serialization import export_graph as export_graph_func
from agentmap.runner import run_graph

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
@app.command()
def run(
    graph: str = typer.Option(..., "--graph", "-g", help="Graph name to run"),
    csv: str = typer.Option(None, "--csv", help="CSV path override"),
    state: str = typer.Option("{}", "--state", "-s", help="Initial state as JSON string"),  
    autocompile: bool = typer.Option(None, "--autocompile", "-a", help="Autocompile graph if missing"),
    config: str = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Run a graph with optional CSV, initial state, and autocompile support."""
    try:
        data = json.loads(state)  
    except json.JSONDecodeError:
        typer.secho("❌ Invalid JSON passed to --state", fg=typer.colors.RED) 
        raise typer.Exit(code=1)

    output = run_graph(
        graph_name=graph, 
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


if __name__ == "__main__":
    app()