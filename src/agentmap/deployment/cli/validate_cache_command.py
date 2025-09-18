"""
CLI validate cache command handler.

This module provides the validate-cache command for managing validation result cache.
"""

from typing import Optional

import typer

from agentmap.runtime_api import validate_cache


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
    try:
        # Manage cache using facade
        result = validate_cache(
            clear=clear,
            cleanup=cleanup,
            stats=stats,
            file_path=file_path,
        )

        outputs = result["outputs"]
        action = outputs["action"]

        if action == "clear_file":
            typer.secho(
                f"✅ Cleared {outputs['removed_entries']} cache entries for {outputs['file_path']}",
                fg=typer.colors.GREEN,
            )
        elif action == "clear_all":
            typer.secho(
                f"✅ Cleared {outputs['removed_entries']} cache entries",
                fg=typer.colors.GREEN,
            )
        elif action == "cleanup":
            typer.secho(
                f"✅ Removed {outputs['removed_entries']} expired cache entries",
                fg=typer.colors.GREEN,
            )
        else:  # stats
            cache_stats = outputs["cache_stats"]

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

    except Exception as e:
        typer.secho(f"❌ Failed to manage validation cache: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
