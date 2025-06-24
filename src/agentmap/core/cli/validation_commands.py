"""
CLI validation command handlers using the new service architecture.

This module provides validation commands that maintain compatibility
with existing interfaces while using the service architecture.
"""

from pathlib import Path
from typing import Optional

import typer

from agentmap.di import initialize_di


def validate_csv_cmd(
    csv_path: Optional[str] = typer.Option(
        None, "--csv", "-c", help="Path to CSV file to validate"
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Skip cache and force re-validation"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", help="Path to custom config file"
    ),
):
    """Validate a CSV workflow definition file."""
    # Initialize DI with optional config file
    container = initialize_di(config_file)
    configuration = container.app_config_service()
    container.logging_service().get_logger("agentmap.cli.validate_csv")
    validation_service = container.validation_service()

    # Determine CSV path
    csv_file = Path(csv_path) if csv_path else configuration.get_csv_path()

    if not csv_file.exists():
        typer.secho(f"❌ CSV file not found: {csv_file}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Validating CSV file: {csv_file}")

    try:
        # from agentmap.validation import validate_csv, print_validation_summary
        result = validation_service.validate_csv(csv_file, use_cache=not no_cache)

        # Print results
        validation_service.print_validation_summary(result)

        # Exit with appropriate code
        if result.has_errors:
            raise typer.Exit(code=1)
        elif result.has_warnings:
            typer.echo("\n⚠️  Validation completed with warnings")
            raise typer.Exit(code=0)
        else:
            typer.secho("\n✅ CSV validation passed!", fg=typer.colors.GREEN)
            # Typer will automatically exit with code 0

    except typer.Exit:
        # Re-raise typer.Exit exceptions (these are intentional exits)
        raise
    except Exception as e:
        typer.secho(f"❌ Validation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def validate_config_cmd(
    config_path: str = typer.Option(
        "agentmap_config.yaml", "--config", "-c", help="Path to config file to validate"
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Skip cache and force re-validation"
    ),
):
    """Validate a YAML configuration file."""
    config_file = Path(config_path)

    container = initialize_di(config_file)
    # configuration = container.app_config_service()
    # logger = container.logging_service().get_logger("agentmap.cli.validate_config")
    validation_service = container.validation_service()

    if not config_file.exists():
        typer.secho(f"❌ Config file not found: {config_file}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Validating config file: {config_file}")

    try:
        result = validation_service.validate_config(config_file, use_cache=not no_cache)

        # Print results
        validation_service.print_validation_summary(None, result)

        # Exit with appropriate code
        if result.has_errors:
            raise typer.Exit(code=1)
        elif result.has_warnings:
            typer.echo("\n⚠️  Validation completed with warnings")
            raise typer.Exit(code=0)
        else:
            typer.secho("\n✅ Config validation passed!", fg=typer.colors.GREEN)
            # Typer will automatically exit with code 0

    except typer.Exit:
        # Re-raise typer.Exit exceptions (these are intentional exits)
        raise
    except Exception as e:
        typer.secho(f"❌ Validation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def validate_all_cmd(
    csv_path: Optional[str] = typer.Option(
        None, "--csv", help="Path to CSV file to validate"
    ),
    config_path: str = typer.Option(
        "agentmap_config.yaml", "--config", "-c", help="Path to config file to validate"
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Skip cache and force re-validation"
    ),
    fail_on_warnings: bool = typer.Option(
        False, "--fail-on-warnings", help="Treat warnings as errors"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config-file", help="Path to initialization config file"
    ),
):
    """Validate both CSV and configuration files."""
    # Initialize DI with config file
    container = initialize_di(config_file)
    configuration = container.app_config_service()
    # logger = container.logging_service().get_logger("agentmap.cli.validate_config")
    validation_service = container.validation_service()

    # Determine paths
    csv_file = Path(csv_path) if csv_path else configuration.get_csv_path()
    config_file_path = Path(config_path)

    # Check files exist
    missing_files = []
    if not csv_file.exists():
        missing_files.append(f"CSV: {csv_file}")
    if not config_file_path.exists():
        missing_files.append(f"Config: {config_file_path}")

    if missing_files:
        typer.secho(
            f"❌ Files not found: {', '.join(missing_files)}", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    typer.echo(f"Validating files:")
    typer.echo(f"  CSV: {csv_file}")
    typer.echo(f"  Config: {config_file_path}")

    try:
        csv_result, config_result = validation_service.validate_both(
            csv_file, config_file_path, use_cache=not no_cache
        )

        # Print results
        validation_service.print_validation_summary(csv_result, config_result)

        # Determine exit code
        has_errors = csv_result.has_errors or (
            config_result.has_errors if config_result else False
        )
        has_warnings = csv_result.has_warnings or (
            config_result.has_warnings if config_result else False
        )

        if has_errors:
            raise typer.Exit(code=1)
        elif has_warnings and fail_on_warnings:
            typer.echo("\n❌ Failing due to warnings (--fail-on-warnings enabled)")
            raise typer.Exit(code=1)
        elif has_warnings:
            typer.echo("\n⚠️  Validation completed with warnings")
            raise typer.Exit(code=0)
        else:
            typer.secho("\n✅ All validation passed!", fg=typer.colors.GREEN)
            # Typer will automatically exit with code 0

    except typer.Exit:
        # Re-raise typer.Exit exceptions (these are intentional exits)
        raise
    except Exception as e:
        typer.secho(f"❌ Validation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def validate_csv_for_compilation_command(
    csv_path: Optional[str] = None, config_file: Optional[str] = None
) -> dict:
    """
    Validate CSV specifically for compilation requirements.

    Args:
        csv_path: Path to CSV file to validate
        config_file: Path to custom config file

    Returns:
        Dict containing validation results

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If validation fails
    """
    # Initialize services
    container = initialize_di(config_file)
    validation_service = container.validation_service()
    logging_service = container.logging_service()
    app_config_service = container.app_config_service()

    logger = logging_service.get_logger("agentmap.cli.validate_compilation")

    # Determine CSV path
    csv_file = Path(csv_path) if csv_path else app_config_service.get_csv_path()

    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    logger.info(f"Validating CSV for compilation: {csv_file}")

    # Use existing compilation validation
    try:
        validation_service.validate_csv_for_compilation(csv_file)
        return {
            "success": True,
            "file_path": str(csv_file),
            "message": "CSV validation for compilation passed",
        }
    except Exception as e:
        return {
            "success": False,
            "file_path": str(csv_file),
            "error": str(e),
            "message": "CSV validation for compilation failed",
        }
