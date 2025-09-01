"""
CLI validate cache command handler.

This module provides the validate-cache command for managing validation result cache.
"""

from typing import Optional

import typer

from agentmap.di import initialize_di


def validate_cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Clear all validation cache"),
    cleanup: bool = typer.Option(
        False, "--cleanup", help="Remove expired cache entries"
    ),
    stats: bool = typer.Option(False, "--stats", help="Show cache statistics"),
    file_path: Optional[str] = typer.Option(
        None, "--file", help="Clear cache for specific file only"
    ),
):
    """Manage validation result cache."""
    container = initialize_di()
    validation_cache_service = container.validation_cache_service()

    if clear:
        if file_path:
            removed = validation_cache_service.clear_validation_cache(file_path)
            typer.secho(
                f"✅ Cleared {removed} cache entries for {file_path}",
                fg=typer.colors.GREEN,
            )
        else:
            removed = validation_cache_service.clear_validation_cache()
            typer.secho(f"✅ Cleared {removed} cache entries", fg=typer.colors.GREEN)

    elif cleanup:
        removed = validation_cache_service.cleanup_validation_cache()
        typer.secho(
            f"✅ Removed {removed} expired cache entries", fg=typer.colors.GREEN
        )

    elif stats or not (clear or cleanup):
        # Show stats by default if no other action specified
        cache_stats = validation_cache_service.get_validation_cache_stats()

        typer.echo("Validation Cache Statistics:")
        typer.echo("=" * 30)
        typer.echo(f"Total files: {cache_stats['total_files']}")
        typer.echo(f"Valid files: {cache_stats['valid_files']}")
        typer.echo(f"Expired files: {cache_stats['expired_files']}")
        typer.echo(f"Corrupted files: {cache_stats['corrupted_files']}")

        if cache_stats["expired_files"] > 0:
            typer.echo(
                f"\n💡 Run 'agentmap validate-cache --cleanup' to remove expired entries"
            )

        if cache_stats["corrupted_files"] > 0:
            typer.echo(
                f"⚠️  Found {cache_stats['corrupted_files']} corrupted cache files"
            )
