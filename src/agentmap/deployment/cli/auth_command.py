"""
CLI auth command handler.

This module provides authentication management commands for AgentMap.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
import yaml
from typer import colors

# Create the auth app with subcommands
auth_app = typer.Typer(name="auth", help="Authentication management commands")


def generate_api_key(length: int = 32) -> str:
    """Generate a cryptographically secure API key."""
    return secrets.token_urlsafe(length)


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256 (same as AuthService)."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key_config(
    name: str, permissions: list, expires_days: int = None
) -> dict:
    """Generate a complete API key configuration."""
    api_key = generate_api_key()

    config = {
        "key": api_key,
        "permissions": permissions,
        "user_id": name,
        "metadata": {
            "description": f"{name} API key",
            "created": datetime.now().isoformat(),
            "created_by": "agentmap_cli",
        },
    }

    if expires_days:
        expiry = datetime.now() + timedelta(days=expires_days)
        config["expires_at"] = expiry.isoformat()

    return config


def create_auth_configuration() -> dict:
    """Create a complete authentication configuration."""

    # Generate different API keys
    keys = {
        "admin": generate_api_key_config("admin", ["admin"]),
        "readonly": generate_api_key_config("readonly", ["read"]),
        "executor": generate_api_key_config("executor", ["read", "execute"]),
        "developer": generate_api_key_config(
            "developer", ["read", "write"], expires_days=90
        ),
    }

    # Build authentication configuration
    auth_config = {
        "authentication": {
            "enabled": True,
            "api_keys": keys,
            "public_endpoints": [
                "/",
                "/health",
                "/docs",
                "/openapi.json",
                "/redoc",
                "/favicon.ico",
            ],
            "permissions": {
                "default_permissions": ["read"],
                "admin_permissions": ["read", "write", "execute", "admin"],
                "execution_permissions": ["read", "execute"],
            },
            "embedded_mode": {"enabled": True, "bypass_auth": False},
        }
    }

    return auth_config, keys


def load_yaml_config(config_path: str) -> dict:
    """Load YAML configuration file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        typer.secho(f"❌ Error parsing YAML file: {e}", fg=colors.RED)
        raise typer.Exit(code=1)


def save_yaml_config(config_path: str, config: dict):
    """Save configuration to YAML file."""
    try:
        # Ensure directory exists
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
    except Exception as e:
        typer.secho(f"❌ Error saving configuration file: {e}", fg=colors.RED)
        raise typer.Exit(code=1)


def print_api_keys(keys: dict):
    """Print API keys in a formatted way."""
    typer.secho("\n🔑 Generated API Keys:", fg=colors.GREEN, bold=True)
    typer.secho("-" * 80, fg=colors.BLUE)

    for name, config in keys.items():
        typer.secho(f"\n{name.upper()} Key:", fg=colors.YELLOW, bold=True)
        typer.echo(f"  API Key: {config['key']}")
        typer.echo(f"  Permissions: {', '.join(config['permissions'])}")
        if "expires_at" in config:
            typer.echo(f"  Expires: {config['expires_at']}")
        typer.echo(f"  Key Hash: {hash_api_key(config['key'])}")

    typer.secho("\n" + "-" * 80, fg=colors.BLUE)


def print_environment_setup(keys: dict):
    """Print environment variable setup instructions."""
    typer.secho(
        "\n🖥️  Environment Variable Setup (Windows CMD):", fg=colors.CYAN, bold=True
    )
    typer.secho("-" * 80, fg=colors.BLUE)
    for name, config in keys.items():
        env_name = f"AGENTMAP_API_KEY_{name.upper()}"
        typer.echo(f"set {env_name}={config['key']}")

    typer.secho(
        "\n🖥️  Environment Variable Setup (PowerShell):", fg=colors.CYAN, bold=True
    )
    typer.secho("-" * 80, fg=colors.BLUE)
    for name, config in keys.items():
        env_name = f"AGENTMAP_API_KEY_{name.upper()}"
        typer.echo(f'$env:{env_name}="{config["key"]}"')


@auth_app.command("init")
def auth_init(
    config: str = typer.Option(
        ..., "--config", "-c", help="Path to configuration file to create/update"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing auth configuration if it exists",
    ),
):
    """Generate new authentication configuration in specified config file.

    Creates a new auth section with API keys. Will error if auth section already exists
    unless --force is used.
    """
    config_path = Path(config)

    # Load existing config or create new one
    existing_config = load_yaml_config(config)

    # Check if auth section already exists
    if "authentication" in existing_config and not force:
        typer.secho(
            f"❌ Authentication section already exists in {config}. Use --force to overwrite.",
            fg=colors.RED,
        )
        raise typer.Exit(code=1)

    # Generate auth configuration
    auth_config, keys = create_auth_configuration()

    # Merge with existing config
    existing_config.update(auth_config)

    # Save configuration
    save_yaml_config(config, existing_config)

    typer.secho(
        f"✅ Authentication configuration {'updated' if force else 'created'} in: {config}",
        fg=colors.GREEN,
    )

    # Display generated keys
    print_api_keys(keys)
    print_environment_setup(keys)


@auth_app.command("update")
def auth_update(
    config: str = typer.Option(
        ..., "--config", "-c", help="Path to configuration file to update"
    )
):
    """Update API keys in existing authentication configuration.

    Regenerates all API keys while preserving the rest of the auth configuration.
    """
    config_path = Path(config)

    if not config_path.exists():
        typer.secho(f"❌ Configuration file not found: {config}", fg=colors.RED)
        raise typer.Exit(code=1)

    # Load existing config
    existing_config = load_yaml_config(config)

    if "authentication" not in existing_config:
        typer.secho(
            f"❌ No authentication section found in {config}. Use 'agentmap auth init' instead.",
            fg=colors.RED,
        )
        raise typer.Exit(code=1)

    # Generate new API keys
    _, new_keys = create_auth_configuration()

    # Update only the API keys, preserving other auth settings
    existing_config["authentication"]["api_keys"] = new_keys

    # Save updated configuration
    save_yaml_config(config, existing_config)

    typer.secho(f"✅ API keys updated in: {config}", fg=colors.GREEN)

    # Display new keys
    print_api_keys(new_keys)
    print_environment_setup(new_keys)


@auth_app.command("view")
def auth_view(
    config: str = typer.Option(
        ..., "--config", "-c", help="Path to configuration file to view"
    ),
    show_keys: bool = typer.Option(
        False,
        "--show-keys",
        "-s",
        help="Show actual API keys (security warning: keys will be visible)",
    ),
):
    """View authentication configuration and API keys from config file.

    By default, API keys are masked for security. Use --show-keys to display actual keys.
    """
    config_path = Path(config)

    if not config_path.exists():
        typer.secho(f"❌ Configuration file not found: {config}", fg=colors.RED)
        raise typer.Exit(code=1)

    # Load configuration
    existing_config = load_yaml_config(config)

    if "authentication" not in existing_config:
        typer.secho(f"❌ No authentication section found in {config}", fg=colors.RED)
        raise typer.Exit(code=1)

    auth_config = existing_config["authentication"]

    typer.secho(
        f"\n🔍 Authentication Configuration from: {config}", fg=colors.CYAN, bold=True
    )
    typer.secho("=" * 80, fg=colors.BLUE)

    # Show general auth settings
    typer.secho(
        f"\nAuthentication Enabled: {auth_config.get('enabled', False)}",
        fg=colors.GREEN if auth_config.get("enabled") else colors.RED,
    )

    # Show API keys
    api_keys = auth_config.get("api_keys", {})
    if api_keys:
        if show_keys:
            typer.secho(
                "\n⚠️  WARNING: API keys are visible below!", fg=colors.RED, bold=True
            )
            print_api_keys(api_keys)
            print_environment_setup(api_keys)
        else:
            typer.secho(
                "\n🔑 API Keys (masked for security):", fg=colors.GREEN, bold=True
            )
            typer.secho("-" * 80, fg=colors.BLUE)
            for name, config in api_keys.items():
                typer.secho(f"\n{name.upper()} Key:", fg=colors.YELLOW, bold=True)
                typer.echo(f"  API Key: {'*' * 32}...{config['key'][-8:]}")
                typer.echo(f"  Permissions: {', '.join(config['permissions'])}")
                if "expires_at" in config:
                    typer.echo(f"  Expires: {config['expires_at']}")
                typer.echo(f"  Key Hash: {hash_api_key(config['key'])}")

            typer.secho(
                f"\n💡 Use --show-keys to display actual API keys", fg=colors.CYAN
            )
    else:
        typer.secho("\n❌ No API keys found in configuration", fg=colors.RED)

    # Show other auth settings
    if "public_endpoints" in auth_config:
        typer.secho(
            f"\n📂 Public Endpoints ({len(auth_config['public_endpoints'])}):",
            fg=colors.GREEN,
        )
        for endpoint in auth_config["public_endpoints"]:
            typer.echo(f"  - {endpoint}")

    if "permissions" in auth_config:
        typer.secho(f"\n🔐 Permission Settings:", fg=colors.GREEN)
        permissions = auth_config["permissions"]
        for key, value in permissions.items():
            if isinstance(value, list):
                typer.echo(f"  {key}: {', '.join(value)}")
            else:
                typer.echo(f"  {key}: {value}")


# Main auth command that includes all subcommands
@auth_app.callback()
def auth_callback():
    """Authentication management for AgentMap."""
    pass


# Export the auth app for registration in main CLI
auth_cmd = auth_app
