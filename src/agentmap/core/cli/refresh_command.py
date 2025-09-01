"""
CLI refresh command handler.

This module provides the refresh command for updating provider availability cache.
"""

from typing import Optional

import typer

from agentmap.di import initialize_di


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
        # Initialize container
        container = initialize_di(config_file)
        dependency_checker = container.dependency_checker_service()
        features_registry = container.features_registry_service()

        typer.echo("🔄 Refreshing Provider Availability Cache")
        typer.echo("=" * 40)

        # Invalidate the cache
        typer.echo("\n📦 Invalidating existing cache...")
        dependency_checker.invalidate_environment_cache()
        typer.secho("✅ Cache invalidated", fg=typer.colors.GREEN)

        # Discover and validate LLM providers
        if not storage_only:
            typer.echo("\n🤖 Discovering LLM Providers...")
            llm_results = dependency_checker.discover_and_validate_providers(
                "llm", True
            )

            for provider, is_available in llm_results.items():
                status = "✅ Available" if is_available else "❌ Not available"
                color = typer.colors.GREEN if is_available else typer.colors.RED
                typer.secho(f"  {provider.capitalize()}: {status}", fg=color)

                if not is_available:
                    # Get missing dependencies
                    _, missing = dependency_checker.check_llm_dependencies(provider)
                    if missing:
                        typer.echo(f"    Missing: {', '.join(missing)}")
                        guide = dependency_checker.get_installation_guide(
                            provider, "llm"
                        )
                        typer.echo(f"    Install: {guide}")

        # Discover and validate storage providers
        if not llm_only:
            typer.echo("\n💾 Discovering Storage Providers...")
            storage_results = dependency_checker.discover_and_validate_providers(
                "storage", True
            )

            for storage_type, is_available in storage_results.items():
                status = "✅ Available" if is_available else "❌ Not available"
                color = typer.colors.GREEN if is_available else typer.colors.RED
                typer.secho(f"  {storage_type}: {status}", fg=color)

                if not is_available:
                    # Get missing dependencies
                    _, missing = dependency_checker.check_storage_dependencies(
                        storage_type
                    )
                    if missing:
                        typer.echo(f"    Missing: {', '.join(missing)}")
                        guide = dependency_checker.get_installation_guide(
                            storage_type, "storage"
                        )
                        typer.echo(f"    Install: {guide}")

        # Show summary
        typer.echo("\n📊 Summary:")
        status_summary = dependency_checker.get_dependency_status_summary()

        llm_count = len(status_summary["llm"]["available_providers"])
        storage_count = len(status_summary["storage"]["available_types"])

        typer.echo(f"  LLM Providers Available: {llm_count}")
        if llm_count > 0:
            typer.echo(
                f"    Providers: {', '.join(status_summary['llm']['available_providers'])}"
            )

        typer.echo(f"  Storage Types Available: {storage_count}")
        if storage_count > 0:
            typer.echo(
                f"    Types: {', '.join(status_summary['storage']['available_types'])}"
            )

        typer.secho(
            "\n✅ Provider availability cache refreshed successfully!",
            fg=typer.colors.GREEN,
        )

    except Exception as e:
        typer.secho(f"❌ Failed to refresh cache: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
