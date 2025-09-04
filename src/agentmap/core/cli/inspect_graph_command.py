"""
CLI inspect graph command handler.

This module provides the inspect-graph command for analyzing agent service
configuration and graph structure.
"""

from pathlib import Path
from typing import Optional

import typer

from agentmap.di import initialize_di


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

    container = initialize_di(config_file)
    graph_runner = container.graph_runner_service()

    typer.echo(f"🔍 Inspecting Graph: {graph_name}")
    typer.echo("=" * 50)

    try:
        # Load the graph definition
        csv_path = (
            Path(csv_file)
            if csv_file
            else container.app_config_service().get_csv_repository_path()
        )
        graph_def, resolved_name = graph_runner._load_graph_definition_for_execution(
            csv_path, graph_name
        )

        # Get agent resolution status
        agent_status = graph_runner.get_agent_resolution_status(graph_def)

        typer.echo(f"\n📊 Graph Overview:")
        typer.echo(f"   Resolved Name: {resolved_name}")
        typer.echo(f"   Total Nodes: {agent_status['total_nodes']}")
        typer.echo(
            f"   Unique Agent Types: {agent_status['overall_status']['unique_agent_types']}"
        )
        typer.echo(
            f"   All Resolvable: {'✅' if agent_status['overall_status']['all_resolvable'] else '❌'}"
        )
        typer.echo(
            f"   Resolution Rate: {agent_status['overall_status']['resolution_rate']:.1%}"
        )

        # Show each node/agent
        nodes_to_inspect = [node] if node else list(graph_def.keys())

        for node_name in nodes_to_inspect:
            if node_name not in graph_def:
                typer.secho(
                    f"❌ Node '{node_name}' not found in graph", fg=typer.colors.RED
                )
                continue

            node_def = graph_def[node_name]

            typer.echo(f"\n🤖 Node: {node_name}")
            typer.echo(f"   Agent Type: {node_def.agent_type or 'default'}")
            typer.echo(f"   Description: {node_def.description or 'No description'}")

            if show_resolution:
                # Show agent resolution details
                agent_type = node_def.agent_type or "default"
                if agent_type in agent_status["agent_types"]:
                    type_info = agent_status["agent_types"][agent_type]["info"]
                    typer.echo(f"   🔧 Resolution:")
                    typer.echo(
                        f"      Resolvable: {'✅' if type_info['resolvable'] else '❌'}"
                    )
                    typer.echo(f"      Source: {type_info.get('source', 'Unknown')}")
                    if not type_info["resolvable"]:
                        typer.echo(
                            f"      Issue: {type_info.get('resolution_error', 'Unknown error')}"
                        )

            # Try to create the agent to get service info
            try:
                # Get node registry for this graph
                node_registry = graph_runner.node_registry.prepare_for_assembly(
                    graph_def, graph_name
                )

                # Create agent instance
                agent_instance = graph_runner._create_agent_instance(
                    node_def, graph_name, node_registry
                )

                # Get service info using our implemented method
                service_info = agent_instance.get_service_info()

                if show_services:
                    typer.echo(f"   📋 Services:")
                    for service, available in service_info["services"].items():
                        status = "✅" if available else "❌"
                        typer.echo(f"      {service}: {status}")

                if show_protocols:
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
                typer.echo(f"   📝 Configuration:")
                config = service_info["configuration"]
                typer.echo(f"      Input Fields: {config.get('input_fields', [])}")
                typer.echo(f"      Output Field: {config.get('output_field', 'None')}")

            except Exception as e:
                typer.secho(
                    f"   ❌ Failed to create agent: {str(e)}", fg=typer.colors.RED
                )
                # Show what we can from the agent status
                agent_type = node_def.agent_type or "default"
                if agent_type in agent_status["agent_types"]:
                    type_info = agent_status["agent_types"][agent_type]["info"]
                    if not type_info["resolvable"]:
                        typer.echo(
                            f"   💡 Resolution error: {type_info.get('resolution_error', 'Unknown')}"
                        )
                        if type_info.get("missing_dependencies"):
                            typer.echo(
                                f"   📦 Missing dependencies: {', '.join(type_info['missing_dependencies'])}"
                            )

        # Show issues summary if any
        if agent_status["issues"]:
            typer.echo(f"\n⚠️  Issues Found ({len(agent_status['issues'])}):")
            for issue in agent_status["issues"]:
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
