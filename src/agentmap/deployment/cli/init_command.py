"""
CLI init command handler.

This module provides the init command that replaces init-config with enhanced
functionality including folder structure creation and sample workflow setup.
"""

from pathlib import Path

import typer


def init_command(
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing config files"
    )
) -> None:
    """Initialize AgentMap project with config files and folder structure."""

    # Get template directory
    template_dir = Path(__file__).parent.parent.parent / "templates"
    current_dir = Path.cwd()

    # Define folder structure to create
    folders_to_create = [
        "agentmap_data",
        "agentmap_data/workflows",
        "agentmap_data/custom_agents",
        "agentmap_data/custom_functions",
        "agentmap_data/custom_tools",
    ]

    # Define files to copy (template_name -> target_name)
    files_to_copy = {
        "config/agentmap_config.yaml.template": "agentmap_config.yaml",
        "config/agentmap_config_storage.yaml.template": "agentmap_config_storage.yaml",
        "csv/hello_world.csv": "agentmap_data/workflows/hello_world.csv",
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

    # Create folder structure
    for folder in folders_to_create:
        folder_path = current_dir / folder
        folder_path.mkdir(parents=True, exist_ok=True)

    # Create README.md files in empty directories to guide users
    # Using a mapping to avoid repetition (DRY principle)
    readme_info = {
        "custom_agents": "Custom Agents",
        "custom_functions": "Custom Functions",
        "custom_tools": "Custom Tools",
    }

    for folder_name, title in readme_info.items():
        readme_path = current_dir / f"agentmap_data/{folder_name}/README.md"
        content = (
            f"# {title}\n\n"
            f"AgentMap {folder_name.replace('_', ' ')} go in this folder. "
            "See the documentation online for more information.\n"
        )
        readme_path.write_text(content)

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
            # Ensure parent directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(template_path.read_text())
            copied_files.append(target_name)
        except Exception as e:
            typer.secho(f"❌ Failed to copy {target_name}: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)

    typer.secho(
        "✅ Successfully initialized AgentMap project:",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"  Created {len(folders_to_create)} directories")
    typer.echo(f"  Copied {len(copied_files)} files:")
    for file_name in copied_files:
        typer.echo(f"    - {file_name}")
