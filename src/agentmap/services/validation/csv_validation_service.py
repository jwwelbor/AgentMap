# src/agentmap/services/validation/csv_validation_service.py
from pathlib import Path
from agentmap.models.validation.errors import ValidationResult
from agentmap.models.validation.csv_validator import CSVValidator
from agentmap.services.logging import LoggingService


class CSVValidationService:
    def __init__(self, logging_service: LoggingService):
        self.logger = logging_service.get_logger("agentmap.csv_validation")
        self.validator = CSVValidator()

    def validate_file(self, csv_path: Path) -> ValidationResult:
        self.logger.debug(f"Validating CSV file: {csv_path}")
        return self.validator.validate_file(csv_path)
