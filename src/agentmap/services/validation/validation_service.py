# src/agentmap/services/validation/validation_service.py
from pathlib import Path
from typing import Optional, Tuple

import typer

from agentmap.exceptions.validation_exceptions import ValidationException
from agentmap.models.validation.validation_models import ValidationResult
from agentmap.services.config import AppConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.validation.config_validation_service import (
    ConfigValidationService,
)
from agentmap.services.validation.csv_validation_service import CSVValidationService
from agentmap.services.validation.validation_cache_service import ValidationCacheService


class ValidationService:
    def __init__(
        self,
        config_service: AppConfigService,
        logging_service: LoggingService,
        csv_validator: Optional[CSVValidationService] = None,
        config_validator: Optional[ConfigValidationService] = None,
        cache_service: Optional[ValidationCacheService] = None,
    ):
        self.config_service = config_service
        self.logger = logging_service.get_logger("agentmap.validation")

        # Create a minimal function resolution service if csv_validator is not provided
        if csv_validator is None:
            # Create minimal services for CSV validation
            functions_path = config_service.get_functions_path()
            from agentmap.models.agent_registry import AgentRegistry
            from agentmap.services.agent.agent_registry_service import (
                AgentRegistryService,
            )
            from agentmap.services.function_resolution_service import (
                FunctionResolutionService,
            )

            function_resolution_service = FunctionResolutionService(functions_path)
            agent_registry_model = AgentRegistry()
            agent_registry_service = AgentRegistryService(
                agent_registry_model, logging_service
            )

            self.csv_validator = CSVValidationService(
                logging_service, function_resolution_service, agent_registry_service
            )
        else:
            self.csv_validator = csv_validator

        self.config_validator = config_validator or ConfigValidationService(
            logging_service
        )
        self.cache_service = cache_service or ValidationCacheService()

    def validate_csv_file(
        self, csv_path: Path, use_cache: bool = True
    ) -> ValidationResult:
        csv_path = Path(csv_path)

        if use_cache:
            file_hash = self.cache_service.calculate_file_hash(csv_path)
            cached = self.cache_service.get_cached_result(str(csv_path), file_hash)
            if cached:
                self.logger.debug(f"Using cached CSV validation result for {csv_path}")
                return cached

        result = self.csv_validator.validate_file(csv_path)

        if use_cache and result.file_hash:
            self.cache_service.cache_result(result)

        return result

    def validate_config_file(
        self, config_path: Path, use_cache: bool = True
    ) -> ValidationResult:
        config_path = Path(config_path)

        if use_cache:
            file_hash = self.cache_service.calculate_file_hash(config_path)
            cached = self.cache_service.get_cached_result(str(config_path), file_hash)
            if cached:
                self.logger.debug(
                    f"Using cached config validation result for {config_path}"
                )
                return cached

        result = self.config_validator.validate_file(config_path)

        if use_cache and result.file_hash:
            self.cache_service.cache_result(result)

        return result

    def validate_and_raise(
        self, csv_path: Path, config_path: Optional[Path] = None, use_cache: bool = True
    ) -> None:
        csv_result = self.validate_csv_file(csv_path, use_cache)

        if csv_result.has_errors:
            raise ValidationException(csv_result)

        if config_path:
            config_result = self.validate_config_file(config_path, use_cache)
            if config_result.has_errors:
                raise ValidationException(config_result)

    def clear_validation_cache(self, file_path: Optional[str] = None) -> int:
        return self.cache_service.clear_cache(file_path)

    def cleanup_validation_cache(self) -> int:
        return self.cache_service.cleanup_expired()

    def get_validation_cache_stats(self) -> dict:
        return self.cache_service.get_cache_stats()

    # ========================================================================
    # CLI-compatible method aliases and additional methods
    # ========================================================================

    def validate_csv(self, csv_path: Path, use_cache: bool = True) -> ValidationResult:
        """CLI-compatible alias for validate_csv_file."""
        return self.validate_csv_file(csv_path, use_cache)

    def validate_config(
        self, config_path: Path, use_cache: bool = True
    ) -> ValidationResult:
        """CLI-compatible alias for validate_config_file."""
        return self.validate_config_file(config_path, use_cache)

    def validate_both(
        self, csv_path: Path, config_path: Path, use_cache: bool = True
    ) -> Tuple[ValidationResult, ValidationResult]:
        """Validate both CSV and config files and return both results."""
        csv_result = self.validate_csv_file(csv_path, use_cache)
        config_result = self.validate_config_file(config_path, use_cache)
        return csv_result, config_result

    def validate_csv_for_bundling(self, csv_path: Path) -> None:
        """Validate CSV for compilation requirements and raise if invalid."""
        result = self.validate_csv_file(csv_path, use_cache=False)
        if result.has_errors:
            error_messages = [error.message for error in result.errors]
            raise ValidationException(
                file_path=str(csv_path),
                error_count=len(result.errors),
                error_messages=error_messages,
                warning_count=len(result.warnings),
                info_count=len(result.info),
            )

    def print_validation_summary(
        self,
        csv_result: Optional[ValidationResult] = None,
        config_result: Optional[ValidationResult] = None,
    ):
        """Print validation summary to console using typer for formatting."""
        if csv_result:
            self._print_single_validation_summary("CSV", csv_result)

        if config_result:
            self._print_single_validation_summary("Config", config_result)

    def _print_single_validation_summary(
        self, file_type: str, result: ValidationResult
    ):
        """Print summary for a single validation result."""
        if result.has_errors:
            typer.secho(f"\n❌ {file_type} Validation Errors:", fg=typer.colors.RED)
            for i, error in enumerate(result.errors, 1):
                typer.echo(f"  {i}. {error.message}")
                if hasattr(error, "line_number") and error.line_number:
                    typer.echo(f"     Line {error.line_number}")

        if result.has_warnings:
            typer.secho(
                f"\n⚠️  {file_type} Validation Warnings:", fg=typer.colors.YELLOW
            )
            for i, warning in enumerate(result.warnings, 1):
                typer.echo(f"  {i}. {warning.message}")
                if hasattr(warning, "line_number") and warning.line_number:
                    typer.echo(f"     Line {warning.line_number}")

        if not result.has_errors and not result.has_warnings:
            typer.secho(
                f"🔍 {file_type} validation completed successfully",
                fg=typer.colors.GREEN,
            )
