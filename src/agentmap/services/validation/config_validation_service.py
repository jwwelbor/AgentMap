# src/agentmap/services/validation/config_validation_service.py
from pathlib import Path
from agentmap.models.validation.errors import ValidationResult
from agentmap.models.validation.config_validator import ConfigValidator
from agentmap.services.logging import LoggingService


class ConfigValidationService:
    def __init__(self, logging_service: LoggingService):
        self.logger = logging_service.get_logger("agentmap.config_validation")
        self.validator = ConfigValidator()

    def validate_file(self, config_path: Path) -> ValidationResult:
        self.logger.debug(f"Validating config file: {config_path}")
        return self.validator.validate_file(config_path)
