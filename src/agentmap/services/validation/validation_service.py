# src/agentmap/services/validation/validation_service.py
from pathlib import Path
from typing import Optional

from agentmap.models.validation.errors import ValidationResult, ValidationException
from agentmap.migration_utils import RealLoggingService as LoggingService
from agentmap.services.config import AppConfigService
from agentmap.services.validation.csv_validation_service import CSVValidationService
from agentmap.services.validation.config_validation_service import ConfigValidationService
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
        self.csv_validator = csv_validator or CSVValidationService(logging_service)
        self.config_validator = config_validator or ConfigValidationService(logging_service)
        self.cache_service = cache_service or ValidationCacheService()

    def validate_csv_file(self, csv_path: Path, use_cache: bool = True) -> ValidationResult:
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

    def validate_config_file(self, config_path: Path, use_cache: bool = True) -> ValidationResult:
        config_path = Path(config_path)

        if use_cache:
            file_hash = self.cache_service.calculate_file_hash(config_path)
            cached = self.cache_service.get_cached_result(str(config_path), file_hash)
            if cached:
                self.logger.debug(f"Using cached config validation result for {config_path}")
                return cached

        result = self.config_validator.validate_file(config_path)

        if use_cache and result.file_hash:
            self.cache_service.cache_result(result)

        return result

    def validate_and_raise(self, csv_path: Path, config_path: Optional[Path] = None, use_cache: bool = True) -> None:
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
