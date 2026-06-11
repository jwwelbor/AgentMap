"""
CLI inspect graph command handler.

This module provides the inspect-graph command for analyzing agent service
configuration and graph structure.
"""

from typing import Optional

import typer

from agentmap.runtime_api import inspect_graph


def inspect_graph_cmd(
    graph_name: str = typer.Argument(..., help="Name of graph to inspect"),
    csv_file: Optional[str] = typer.Option(
        None, "--csv", "-c", help="Path to CSV file"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", help="Path to custom config file"
    ),
    node: Optional[str] = typer.Option(
        None, "--node", "-n", help="Inspect specific node only"
    ),
    show_services: bool = typer.Option(
        True, "--services/--no-services", help="Show service availability"
    ),
    show_protocols: bool = typer.Option(
        True, "--protocols/--no-protocols", help="Show protocol implementations"
    ),
    show_config: bool = typer.Option(
        False, "--config-details", help="Show detailed configuration"
    ),
    show_resolution: bool = typer.Option(
        False, "--resolution", help="Show agent resolution details"
    ),
):
    """Inspect agent service configuration for a graph."""
    if show_services or show_protocols or show_config or show_resolution:
        typer.echo(
            "Note: --services/--protocols/--config-details/--resolution detail flags "
            "are not available in this runtime facade version and will be added in a "
            "future release.",
            err=True,
        )

    typer.echo(f"🔍 Inspecting Graph: {graph_name}")
    typer.echo("=" * 50)

    try:
        result = inspect_graph(
            graph_name,
            csv_file=csv_file,
            node=node,
            config_file=config_file,
        )

        outputs = result["outputs"]

        typer.echo("\n📊 Graph Overview:")
        typer.echo(f"   Resolved Name: {outputs['resolved_name']}")
        typer.echo(f"   Total Nodes: {outputs['total_nodes']}")
        typer.echo(f"   Unique Agent Types: {outputs['unique_agent_types']}")
        typer.echo(f"   All Resolvable: {'✅' if outputs['all_resolvable'] else '❌'}")
        typer.echo(f"   Resolution Rate: {outputs['resolution_rate']:.1%}")

        # Show each node/agent — real facade returns outputs["structure"]["nodes"]
        # as a list of dicts with keys: name, agent_type, description
        for node_info in outputs["structure"]["nodes"]:
            node_name = node_info["name"]
            typer.echo(f"\n🤖 Node: {node_name}")
            typer.echo(f"   Agent Type: {node_info['agent_type']}")
            typer.echo(f"   Description: {node_info['description']}")

        # Show issues summary if any — real facade returns a list of strings
        if outputs["issues"]:
            typer.echo(f"\n⚠️  Issues Found ({len(outputs['issues'])}):")
            for issue in outputs["issues"]:
                typer.echo(f"   {issue}")
        else:
            typer.secho(
                "\n✅ No issues found - all agents properly configured!",
                fg=typer.colors.GREEN,
            )

        # Helpful suggestions
        typer.echo("\n💡 Helpful Commands:")
        typer.echo(
            "   agentmap diagnose                    # Check system dependencies"
        )
        typer.echo(
            f"   agentmap inspect-graph {graph_name} --config-details  # Show detailed config"
        )
        if node:
            typer.echo(
                f"   agentmap inspect-graph {graph_name}             # Inspect all nodes"
            )
        else:
            typer.echo(
                f"   agentmap inspect-graph {graph_name} --node NODE_NAME  # Inspect specific node"
            )

    except Exception as e:
        typer.secho(f"❌ Failed to inspect graph: {e}", fg=typer.colors.RED)
        typer.echo("\n💡 Troubleshooting:")
        typer.echo(f"   • Check that graph '{graph_name}' exists in the CSV file")
        typer.echo(f"   • Verify CSV file path: {csv_file or 'default from config'}")
        typer.echo("   • Run 'agentmap diagnose' to check system dependencies")
        raise typer.Exit(code=1)
