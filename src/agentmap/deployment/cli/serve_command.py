"""
CLI serve command handler for starting the AgentMap HTTP API server.

This command provides a convenient alias for starting the FastAPI server
through the main CLI interface.
"""

from typing import Optional

import typer

from agentmap.deployment.cli.utils.cli_presenter import (
    map_exception_to_exit_code,
    print_err,
)
from agentmap.deployment.http.api.server import run_server


def serve_command(
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(
        False, "--reload", "-r", help="Enable auto-reload for development"
    ),
):
    """
    Start the AgentMap HTTP API server.

    This command starts a FastAPI server that provides HTTP endpoints for
    workflow execution, validation, and management.

    Examples:
        agentmap serve --config agentmap_local_config.yaml
        agentmap serve --host 0.0.0.0 --port 8080 --reload
    """
    try:
        typer.echo("Starting AgentMap API server...")
        typer.echo(f"  Host: {host}")
        typer.echo(f"  Port: {port}")
        typer.echo(f"  Config: {config_file or 'default'}")
        typer.echo(f"  Auto-reload: {'enabled' if reload else 'disabled'}")
        typer.echo("\nServer starting... Press Ctrl+C to stop")
        typer.echo(
            f"\n📖 API Documentation: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs"
        )
        typer.echo(
            f"📖 Alternative Docs: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/redoc\n"
        )

        # Start the server
        run_server(
            host=host,
            port=port,
            reload=reload,
            config_file=config_file,
        )

    except KeyboardInterrupt:
        typer.echo("\n\nServer stopped by user")
        raise typer.Exit(code=0)
    except Exception as e:
        print_err(f"Failed to start server: {str(e)}")
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
