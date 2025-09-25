"""
CLI update-bundle command handler for updating bundle agent mappings.

This command follows SPEC-DEP-001 by using only the runtime facade
and CLI presenter utilities for consistent behavior and error handling.
"""

from typing import Optional

import typer

from agentmap.deployment.cli.utils.cli_presenter import (
    map_exception_to_exit_code,
    print_err,
    print_json,
)
from agentmap.runtime_api import ensure_initialized, update_bundle


def update_bundle_command(
    workflow: Optional[str] = typer.Argument(
        None,
        help="workflow file, workflow/graph, or filename::graph_name (e.g., 'customer_data::support_flow')",
    ),
    graph: Optional[str] = typer.Option(
        None,
        "--workflow",
        "-w",
        help="workflow file, workflow_folder/workflow_file, or filename::graph_name (e.g., 'customer_data::support_flow')",
    ),
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

    This command follows the facade pattern defined in SPEC-DEP-001 for
    consistent behavior across all deployment adapters.

    **Supported Syntax Examples:**

    • Traditional syntax:
      agentmap update-bundle workflow/graph_name

    • Simplified syntax (NEW):
      agentmap update-bundle filename::graph_name
      agentmap update-bundle --workflow filename
      agentmap update-bundle --workflow filename::graph_name

    The :: syntax provides a convenient shorthand where the graph name
    defaults to the CSV filename (without .csv extension), but you can
    specify a different graph name after the :: delimiter.

    This command always forces recreation of the bundle to ensure it's up to date.
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized(config_file=config_file)

        # Determine graph name - now supports :: syntax like run_command
        graph_name = workflow or graph

        if not graph_name:
            print_err("Must provide workflow argument")
            print_err("Examples:")
            print_err("  agentmap update-bundle workflow/graph_name")
            print_err("  agentmap update-bundle filename::graph_name")
            print_err("  agentmap update-bundle --workflow filename::graph_name")
            raise typer.Exit(code=2)

        # Execute using runtime facade - always force recreation for update-bundle
        typer.echo(f"📦 Updating bundle for: {graph_name}")

        result = update_bundle(
            graph_name=graph_name,
            config_file=config_file,
            dry_run=dry_run,
            force=True,  # Always force for update-bundle command
        )

        # Display results using CLI presenter for consistency
        if result.get("success", False):
            outputs = result.get("outputs", {})
            metadata = result.get("metadata", {})
            bundle_name = metadata.get("bundle_name", graph_name)

            if dry_run:
                # Preview mode output
                typer.echo(f"\n🔍 Previewing updates for bundle: {bundle_name}")

                current_mappings = outputs.get("current_mappings", 0)
                typer.echo(f"   Current agent mappings: {current_mappings}")

                missing_declarations = outputs.get("missing_declarations", [])
                would_resolve = outputs.get("would_resolve", [])
                would_update = outputs.get("would_update", [])
                would_remove = outputs.get("would_remove", [])

                if missing_declarations:
                    typer.secho(
                        f"   Missing declarations: {len(missing_declarations)}",
                        fg=typer.colors.YELLOW,
                    )
                    for agent_type in missing_declarations:
                        typer.echo(f"      • {agent_type}")

                if would_resolve:
                    typer.secho(
                        f"   Would resolve: {len(would_resolve)} agents",
                        fg=typer.colors.GREEN,
                    )
                    for agent_type in would_resolve:
                        typer.echo(f"      • {agent_type}")

                if would_update:
                    typer.secho(
                        f"   Would update: {len(would_update)} mappings",
                        fg=typer.colors.CYAN,
                    )
                    for agent_type in would_update:
                        typer.echo(f"      • {agent_type}")

                if would_remove:
                    typer.secho(
                        f"   Would remove: {len(would_remove)} obsolete mappings",
                        fg=typer.colors.RED,
                    )
                    for agent_type in would_remove:
                        typer.echo(f"      • {agent_type}")

                if not any([would_resolve, would_update, would_remove]):
                    typer.secho(
                        "   ✅ No changes needed - bundle is up to date",
                        fg=typer.colors.GREEN,
                    )
            else:
                # Actual update output
                typer.echo(f"\n🔄 Updated bundle: {bundle_name}")

                current_mappings = outputs.get("current_mappings", 0)
                missing_declarations = outputs.get("missing_declarations", [])
                required_services = outputs.get("required_services", 0)

                typer.secho("✅ Bundle update complete!", fg=typer.colors.GREEN)
                typer.echo(f"   Agent mappings: {current_mappings}")

                missing_count = len(missing_declarations)
                if missing_count > 0:
                    typer.secho(
                        f"   Still missing: {missing_count} declarations",
                        fg=typer.colors.YELLOW,
                    )
                    for agent_type in sorted(missing_declarations):
                        typer.echo(f"      • {agent_type}")
                else:
                    typer.secho("   All agent types resolved!", fg=typer.colors.GREEN)

                # Show additional info if bundle has services
                if required_services > 0:
                    typer.echo(f"   Required services: {required_services}")

                typer.echo(f"\n💡 Tips:")
                typer.echo("   • Use --dry-run to preview changes before updating")
                typer.echo("   • Run 'agentmap scaffold' to create missing agents")
                typer.echo("   • Check custom_agents.yaml for agent declarations")

        else:
            # This shouldn't happen with the facade pattern, but handle gracefully
            error_msg = result.get("error", "Unknown error")
            print_err(f"Bundle update failed: {error_msg}")
            raise typer.Exit(code=1)

        raise typer.Exit(code=0)

    except typer.Exit:
        # Re-raise typer.Exit as-is to preserve exit codes
        raise
    except Exception as e:
        # Use CLI presenter for consistent error handling and exit codes
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
