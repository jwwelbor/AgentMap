"""
Main CLI application using GraphRunnerService through dependency injection.

This module provides the complete CLI interface that maintains compatibility
with existing command interfaces while using the new service architecture.
"""

import sys

import typer

from agentmap._version import __version__
from agentmap.core.cli.diagnostic_commands import (
    config_cmd,
    diagnose_cmd,
    inspect_graph_cmd,
    validate_cache_cmd,
)
from agentmap.core.cli.run_commands import (
    compile_command,
    export_command,
    resume_command,
    run_command,
    scaffold_command,
)
from agentmap.core.cli.validation_commands import (
    validate_all_cmd,
    validate_config_cmd,
    validate_csv_cmd,
)


# Version callback
def version_callback(value: bool):
    """Show version and exit."""
    if value:
        typer.echo(f"AgentMap {__version__}")
        raise typer.Exit()


app = typer.Typer(
    help="AgentMap: Build and deploy LangGraph workflows from CSV files for fun and profit!\n\nMain Commands: run, scaffold, compile, export\nDiagnostics: diagnose, inspect-graph, config, validate-*"
)


# Add version option to main app
@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    )
):
    """AgentMap CLI with service-based architecture."""


# ============================================================================
# MAIN WORKFLOW COMMANDS (Most commonly used)
# ============================================================================

app.command("run")(run_command)
app.command("scaffold")(scaffold_command)
app.command("compile")(compile_command)
app.command("export")(export_command)
app.command("resume")(resume_command)


# ============================================================================
# CONFIGURATION COMMANDS
# ============================================================================

app.command("config")(config_cmd)

# ============================================================================
# VALIDATION COMMANDS
# ============================================================================

app.command("validate-csv")(validate_csv_cmd)
app.command("validate-config")(validate_config_cmd)
app.command("validate-all")(validate_all_cmd)

# ============================================================================
# CACHE AND DIAGNOSTIC COMMANDS
# ============================================================================

app.command("validate-cache")(validate_cache_cmd)
app.command("diagnose")(diagnose_cmd)
app.command("inspect-graph")(inspect_graph_cmd)


def main_cli():
    """Main CLI entry point for new service-based architecture."""
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        typer.secho(f"❌ Unexpected error: {e}", fg=typer.colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    main_cli()
