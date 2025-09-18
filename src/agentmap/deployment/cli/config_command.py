"""
CLI config command handler.

This module provides the config command for displaying current configuration values.
"""

from typing import Optional

import typer

from agentmap.runtime_api import get_config


def config_cmd(
    config_file: Optional[str] = typer.Option(
        None, "--path", "-p", help="Path to config file to display"
    )
):
    """Print the current configuration values."""
    try:
        # Get configuration using facade
        result = get_config(config_file=config_file)
        config_data = result["outputs"]

        print("Configuration values:")
        print("---------------------")
        for k, v in config_data.items():
            if isinstance(v, dict):
                print(f"{k}:")
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, dict):
                        print(f"  {sub_k}:")
                        for deep_k, deep_v in sub_v.items():
                            print(f"    {deep_k}: {deep_v}")
                    else:
                        print(f"  {sub_k}: {sub_v}")
            else:
                print(f"{k}: {v}")

    except Exception as e:
        typer.secho(f"❌ Failed to load configuration: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
