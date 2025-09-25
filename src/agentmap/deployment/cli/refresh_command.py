"""
CLI refresh command handler.

This module provides the refresh command for updating provider availability cache.
"""

from typing import Optional

import typer

from agentmap.runtime_api import refresh_cache


def refresh_cmd(
    force: bool = typer.Option(
        False, "--force", "-f", help="Force refresh even if cache exists"
    ),
    llm_only: bool = typer.Option(
        False, "--llm-only", help="Only refresh LLM providers"
    ),
    storage_only: bool = typer.Option(
        False, "--storage-only", help="Only refresh storage providers"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    ),
):
    """
    Refresh availability cache by discovering and validating all providers.

    This command invalidates the cache and re-validates all LLM and storage
    providers, updating their availability status.
    """
    try:
        typer.echo("🔄 Refreshing Provider Availability Cache")
        typer.echo("=" * 40)

        # Refresh using facade
        result = refresh_cache(
            force=force,
            llm_only=llm_only,
            storage_only=storage_only,
            config_file=config_file,
        )

        outputs = result["outputs"]

        typer.echo("\n📦 Invalidating existing cache...")
        typer.secho("✅ Cache invalidated", fg=typer.colors.GREEN)

        # Display LLM results
        if not storage_only and outputs.get("llm_results"):
            typer.echo("\n🤖 Discovering LLM Providers...")
            for provider, is_available in outputs["llm_results"].items():
                status = "✅ Available" if is_available else "❌ Not available"
                color = typer.colors.GREEN if is_available else typer.colors.RED
                typer.secho(f"  {provider.capitalize()}: {status}", fg=color)

        # Display storage results
        if not llm_only and outputs.get("storage_results"):
            typer.echo("\n💾 Discovering Storage Providers...")
            for storage_type, is_available in outputs["storage_results"].items():
                status = "✅ Available" if is_available else "❌ Not available"
                color = typer.colors.GREEN if is_available else typer.colors.RED
                typer.secho(f"  {storage_type}: {status}", fg=color)

        # Show summary
        if outputs.get("status_summary"):
            typer.echo("\n📊 Summary:")
            status_summary = outputs["status_summary"]

            llm_count = len(
                status_summary.get("llm", {}).get("available_providers", [])
            )
            storage_count = len(
                status_summary.get("storage", {}).get("available_types", [])
            )

            typer.echo(f"  LLM Providers Available: {llm_count}")
            if llm_count > 0:
                providers = status_summary.get("llm", {}).get("available_providers", [])
                typer.echo(f"    Providers: {', '.join(providers)}")

            typer.echo(f"  Storage Types Available: {storage_count}")
            if storage_count > 0:
                types = status_summary.get("storage", {}).get("available_types", [])
                typer.echo(f"    Types: {', '.join(types)}")

        typer.secho(
            "\n✅ Provider availability cache refreshed successfully!",
            fg=typer.colors.GREEN,
        )
    except typer.Exit:
        # Re-raise typer.Exit as-is to preserve exit codes
        raise

    except Exception as e:
        typer.secho(f"❌ Failed to refresh cache: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
