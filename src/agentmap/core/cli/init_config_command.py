"""
CLI init config command handler.

This module provides the init-config command for copying default configuration
files to the current directory.
"""

from pathlib import Path

import typer


def init_config_command(
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing config files"
    )
) -> None:
    """Copy default configuration files to current directory."""

    # Get template directory
    template_dir = Path(__file__).parent.parent.parent / "templates"
    current_dir = Path.cwd()

    # Files to copy (template_name -> target_name)
    files_to_copy = {
        "config/agentmap_config.yaml.template": "agentmap_config.yaml",
        "config/agentmap_config_storage.yaml.template": "agentmap_config_storage.yaml",
        # Skipping prompt registry for now
        #  "config/agentmap_prompt_registry.yaml.template": "agentmap_prompt_registry.yaml",
        "csv/hello_world.csv": "hello_world.csv",
    }

    # Check for existing files
    existing_files = []
    for target_name in files_to_copy.values():
        target_path = current_dir / target_name
        if target_path.exists():
            existing_files.append(target_name)

    if existing_files and not force:
        typer.secho(
            f"❌ Config files already exist: {', '.join(existing_files)}",
            fg=typer.colors.RED,
        )
        typer.echo("Use --force to overwrite existing files")
        raise typer.Exit(1)

    # Copy files
    copied_files = []
    for template_name, target_name in files_to_copy.items():
        template_path = template_dir / template_name
        target_path = current_dir / target_name

        if not template_path.exists():
            typer.secho(
                f"❌ Template file not found: {template_path}", fg=typer.colors.RED
            )
            raise typer.Exit(1)

        try:
            target_path.write_text(template_path.read_text())
            copied_files.append(target_name)
        except Exception as e:
            typer.secho(f"❌ Failed to copy {target_name}: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)

    typer.secho(
        f"✅ Successfully copied {len(copied_files)} config files:",
        fg=typer.colors.GREEN,
    )
    for file_name in copied_files:
        typer.echo(f"  - {file_name}")
