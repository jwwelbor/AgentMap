"""
Main CLI application using GraphRunnerService through dependency injection.

This module provides the complete CLI interface that maintains compatibility
with existing command interfaces while using the new service architecture.
"""

import sys

import typer

from agentmap._version import __version__
from agentmap.deployment.cli.auth_command import auth_cmd
from agentmap.deployment.cli.diagnose_command import diagnose_cmd
from agentmap.deployment.cli.init_config_command import init_config_command
from agentmap.deployment.cli.refresh_command import refresh_cmd
from agentmap.deployment.cli.resume_command import resume_command
from agentmap.deployment.cli.run_command import run_command
from agentmap.deployment.cli.scaffold_command import scaffold_command
from agentmap.deployment.cli.serve_command import serve_command
from agentmap.deployment.cli.update_bundle_command import update_bundle_command
from agentmap.deployment.cli.validate_command import validate_command

# from agentmap.core.cli.validation_commands import (
#     validate_all_cmd,
#     validate_config_cmd,
#     validate_csv_cmd,
# )


# Version callback
def version_callback(value: bool):
    """Show version and exit."""
    if value:
        typer.echo(f"AgentMap {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="agentmap",
    help="AgentMap: Build and deploy LangGraph workflows from CSV files for fun and profit!\n\nMain Commands: run, scaffold, compile, export\nDiagnostics: diagnose, inspect-graph, config, validate-*\n\nShorthand: agentmap run file.csv [options] = agentmap run --csv file.csv [options]",
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
    """AgentMap CLI with service-based architecture.

    Supports shorthand syntax: agentmap run file.csv is equivalent to agentmap run --csv file.csv
    """
    pass


# ============================================================================
# MAIN WORKFLOW COMMANDS (Most commonly used)
# ============================================================================

app.command("run")(run_command)
app.command("scaffold")(scaffold_command)
app.command("update-bundle")(update_bundle_command)
# app.command("export")(export_command)
app.command("resume")(resume_command)
app.command("serve")(serve_command)


# ============================================================================
# CONFIGURATION COMMANDS
# ============================================================================

# app.command("config")(config_cmd)
app.command("init-config")(init_config_command)
app.add_typer(auth_cmd, name="auth")

# ============================================================================
# VALIDATION COMMANDS
# ============================================================================

app.command("validate")(validate_command)  # Bundle-based validation
# app.command("validate-csv")(validate_csv_cmd)
# app.command("validate-config")(validate_config_cmd)
# app.command("validate-all")(validate_all_cmd)

# ============================================================================
# CACHE AND DIAGNOSTIC COMMANDS
# ============================================================================

app.command("refresh")(refresh_cmd)
# app.command("validate-cache")(validate_cache_cmd)
app.command("diagnose")(diagnose_cmd)
# app.command("inspect-graph")(inspect_graph_cmd)


def main_cli():
    """Main CLI entry point for new service-based architecture."""
    try:
        app()
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        typer.secho(f"❌ Unexpected error: {e}", fg=typer.colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    main_cli()
