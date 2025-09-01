"""
CLI update-bundle command handler for updating bundle agent mappings.

This module provides the update-bundle command that updates existing
bundles with current declaration mappings for troubleshooting and
manual maintenance.
"""

from pathlib import Path
from typing import Optional

import typer

from agentmap.core.cli.cli_utils import handle_command_error, resolve_csv_path
from agentmap.di import initialize_di
from agentmap.services.graph.bundle_update_service import BundleUpdateService
from agentmap.services.graph.graph_bundle_service import GraphBundleService


def update_bundle_command(
    csv_file: Optional[str] = typer.Argument(
        None, help="CSV file path (shorthand for --csv)"
    ),
    graph: Optional[str] = typer.Option(
        None, "--graph", "-g", help="Graph name to update bundle for"
    ),
    csv: Optional[str] = typer.Option(None, "--csv", help="CSV path override"),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without saving"
    ),
    force: bool = typer.Option(
        False, "--force", help="Force update even if no changes detected"
    ),
):
    """
    Update existing bundle with current agent declaration mappings.

    Useful for troubleshooting and manual updates after editing custom_agents.yaml.
    Supports shorthand: agentmap update-bundle file.csv
    """
    try:
        # Resolve CSV path using utility
        csv_path = resolve_csv_path(csv_file, csv)

        # Initialize DI container
        container = initialize_di(config_file)

        # Get bundle service to load existing bundle
        typer.echo(f"📦 Loading bundle for: {csv_path}")
        graph_bundle_service: GraphBundleService = container.graph_bundle_service()

        # Try to get existing bundle from cache
        bundle = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path, graph_name=graph, config_path=config_file
        )

        if not bundle:
            typer.secho(f"❌ No bundle found for {csv_path}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        graph_display_name = bundle.graph_name or "default"
        typer.echo(f"   Found bundle for graph: {graph_display_name}")

        # Get bundle update service
        bundle_update_service: BundleUpdateService = container.bundle_update_service()

        # Preview mode - show what would be updated
        if dry_run:
            typer.echo(f"\n🔍 Previewing updates for bundle: {graph_display_name}")

            preview = bundle_update_service.get_update_summary(bundle)

            # Display preview results
            typer.echo(f"   Current agent mappings: {preview['current_mappings']}")

            if preview["missing_declarations"]:
                typer.secho(
                    f"   Missing declarations: {len(preview['missing_declarations'])}",
                    fg=typer.colors.YELLOW,
                )
                for agent_type in preview["missing_declarations"]:
                    typer.echo(f"      • {agent_type}")

            if preview["would_resolve"]:
                typer.secho(
                    f"   Would resolve: {len(preview['would_resolve'])} agents",
                    fg=typer.colors.GREEN,
                )
                for agent_type in preview["would_resolve"]:
                    typer.echo(f"      • {agent_type}")

            if preview["would_update"]:
                typer.secho(
                    f"   Would update: {len(preview['would_update'])} mappings",
                    fg=typer.colors.CYAN,
                )
                for agent_type in preview["would_update"]:
                    typer.echo(f"      • {agent_type}")

            if preview["would_remove"]:
                typer.secho(
                    f"   Would remove: {len(preview['would_remove'])} obsolete mappings",
                    fg=typer.colors.RED,
                )
                for agent_type in preview["would_remove"]:
                    typer.echo(f"      • {agent_type}")

            if not any(
                [
                    preview["would_resolve"],
                    preview["would_update"],
                    preview["would_remove"],
                ]
            ):
                typer.secho(
                    "   ✅ No changes needed - bundle is up to date",
                    fg=typer.colors.GREEN,
                )

            return

        # Actual update
        typer.echo(f"\n🔄 Updating bundle: {graph_display_name}")

        # Perform the update
        updated_bundle = bundle_update_service.update_bundle_from_declarations(
            bundle, persist=True
        )

        # Report results
        current_mappings = (
            len(updated_bundle.agent_mappings) if updated_bundle.agent_mappings else 0
        )
        missing_count = (
            len(updated_bundle.missing_declarations)
            if updated_bundle.missing_declarations
            else 0
        )

        typer.secho("✅ Bundle update complete!", fg=typer.colors.GREEN)
        typer.echo(f"   Agent mappings: {current_mappings}")

        if missing_count > 0:
            typer.secho(
                f"   Still missing: {missing_count} declarations",
                fg=typer.colors.YELLOW,
            )
            if updated_bundle.missing_declarations:
                for agent_type in sorted(updated_bundle.missing_declarations):
                    typer.echo(f"      • {agent_type}")
        else:
            typer.secho("   All agent types resolved!", fg=typer.colors.GREEN)

        # Show additional info if bundle has services
        if updated_bundle.required_services:
            service_count = len(updated_bundle.required_services)
            typer.echo(f"   Required services: {service_count}")

        typer.echo(f"\n💡 Tips:")
        typer.echo("   • Use --dry-run to preview changes before updating")
        typer.echo("   • Run 'agentmap scaffold' to create missing agents")
        typer.echo("   • Check custom_agents.yaml for agent declarations")

    except Exception as e:
        handle_command_error("Bundle update", e)
