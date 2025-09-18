"""
CLI inspect graph command handler.

This module provides the inspect-graph command for analyzing agent service
configuration and graph structure.
"""

from pathlib import Path
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

    typer.echo(f"🔍 Inspecting Graph: {graph_name}")
    typer.echo("=" * 50)

    try:
        # Inspect using facade
        result = inspect_graph(
            graph_name,
            csv_file=csv_file,
            node=node,
            config_file=config_file,
        )

        outputs = result["outputs"]
        metadata = result["metadata"]

        typer.echo(f"\n📊 Graph Overview:")
        typer.echo(f"   Resolved Name: {outputs['resolved_name']}")
        typer.echo(f"   Total Nodes: {outputs['total_nodes']}")
        typer.echo(f"   Unique Agent Types: {outputs['unique_agent_types']}")
        typer.echo(f"   All Resolvable: {'✅' if outputs['all_resolvable'] else '❌'}")
        typer.echo(f"   Resolution Rate: {outputs['resolution_rate']:.1%}")

        # Show each node/agent
        for node_name, node_info in outputs["node_details"].items():
            typer.echo(f"\n🤖 Node: {node_name}")
            typer.echo(f"   Agent Type: {node_info['agent_type']}")
            typer.echo(f"   Description: {node_info['description']}")

            if show_resolution:
                typer.echo(f"   🔧 Resolution:")
                typer.echo(
                    f"      Resolvable: {'✅' if node_info['resolvable'] else '❌'}"
                )
                typer.echo(f"      Source: {node_info.get('source', 'Unknown')}")
                if not node_info["resolvable"]:
                    typer.echo(
                        f"      Issue: {node_info.get('resolution_error', 'Unknown error')}"
                    )

            # Show service info if available
            if node_info["service_info"]:
                service_info = node_info["service_info"]

                if show_services and "services" in service_info:
                    typer.echo(f"   📋 Services:")
                    for service, available in service_info["services"].items():
                        status = "✅" if available else "❌"
                        typer.echo(f"      {service}: {status}")

                if show_protocols and "protocols" in service_info:
                    typer.echo(f"   🔌 Protocols:")
                    for protocol, implemented in service_info["protocols"].items():
                        status = "✅" if implemented else "❌"
                        typer.echo(f"      {protocol}: {status}")

                if show_config:
                    # Show any specialized configuration
                    for key, value in service_info.items():
                        if key not in [
                            "agent_name",
                            "agent_type",
                            "services",
                            "protocols",
                            "configuration",
                        ]:
                            typer.echo(f"   ⚙️  {key.replace('_', ' ').title()}:")
                            if isinstance(value, dict):
                                for sub_key, sub_value in value.items():
                                    typer.echo(f"      {sub_key}: {sub_value}")
                            else:
                                typer.echo(f"      {value}")

                # Show basic configuration always
                if "configuration" in service_info:
                    typer.echo(f"   📝 Configuration:")
                    config = service_info["configuration"]
                    typer.echo(f"      Input Fields: {config.get('input_fields', [])}")
                    typer.echo(
                        f"      Output Field: {config.get('output_field', 'None')}"
                    )

            elif node_info["error"]:
                typer.secho(
                    f"   ❌ Failed to create agent: {node_info['error']}",
                    fg=typer.colors.RED,
                )

        # Show issues summary if any
        if outputs["issues"]:
            typer.echo(f"\n⚠️  Issues Found ({len(outputs['issues'])}):")
            for issue in outputs["issues"]:
                typer.echo(f"   {issue['node']}: {issue['issue']}")
                if issue.get("missing_deps"):
                    typer.echo(f"      Missing: {', '.join(issue['missing_deps'])}")
                if issue.get("resolution_error"):
                    typer.echo(f"      Error: {issue['resolution_error']}")
        else:
            typer.secho(
                f"\n✅ No issues found - all agents properly configured!",
                fg=typer.colors.GREEN,
            )

        # Helpful suggestions
        typer.echo(f"\n💡 Helpful Commands:")
        typer.echo(
            f"   agentmap diagnose                    # Check system dependencies"
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
        typer.echo(f"   • Run 'agentmap diagnose' to check system dependencies")
        raise typer.Exit(code=1)
