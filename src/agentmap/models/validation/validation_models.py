# src/agentmap/models/validation/errors.py
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ValidationLevel(Enum):
    """Validation severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationError(BaseModel):
    """Individual validation error."""

    level: ValidationLevel
    message: str
    line_number: Optional[int] = None
    field_name: Optional[str] = None
    value: Optional[str] = None
    suggestion: Optional[str] = None

    def __init__(self, **data):
        # Handle case where level is passed as a string
        if "level" in data and isinstance(data["level"], str):
            try:
                data["level"] = ValidationLevel(data["level"])
            except ValueError:
                # If string doesn't match enum values, try to find matching enum
                level_str = data["level"].lower()
                for enum_val in ValidationLevel:
                    if enum_val.value == level_str:
                        data["level"] = enum_val
                        break
                else:
                    # Default to ERROR if no match found
                    data["level"] = ValidationLevel.ERROR
        super().__init__(**data)

    class Config:
        """Pydantic configuration for proper enum serialization."""

        use_enum_values = True  # Serialize enums by their values

    def __str__(self) -> str:
        # Handle case where level might be a string instead of enum
        if isinstance(self.level, str):
            level_str = self.level.upper()
        else:
            level_str = self.level.value.upper()

        parts = [f"[{level_str}]"]

        if self.line_number:
            parts.append(f"Line {self.line_number}")

        if self.field_name:
            parts.append(f"Field: {self.field_name}")

        if self.value:
            parts.append(f"Value: '{self.value}'")

        parts.append(self.message)

        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")

        return " ".join(parts)


class ValidationResult(BaseModel):
    """Result of validation operation."""

    file_path: str
    file_type: str = "csv"
    is_valid: bool = True
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)
    info: List[ValidationError] = Field(default_factory=list)
    file_hash: Optional[str] = None
    validation_time: datetime = Field(default_factory=datetime.now)

    class Config:
        """Pydantic configuration for proper serialization."""

        use_enum_values = True  # Serialize enums by their values
        json_encoders = {
            datetime: lambda v: v.isoformat()  # Ensure datetime is properly serialized
        }

    def add_error(
        self,
        message: str,
        line_number: Optional[int] = None,
        field_name: Optional[str] = None,
        value: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        """Add an error to the validation result."""
        error = ValidationError(
            level=ValidationLevel.ERROR,
            message=message,
            line_number=line_number,
            field_name=field_name,
            value=value,
            suggestion=suggestion,
        )
        self.errors.append(error)
        self.is_valid = False

    def add_warning(
        self,
        message: str,
        line_number: Optional[int] = None,
        field_name: Optional[str] = None,
        value: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        """Add a warning to the validation result."""
        warning = ValidationError(
            level=ValidationLevel.WARNING,
            message=message,
            line_number=line_number,
            field_name=field_name,
            value=value,
            suggestion=suggestion,
        )
        self.warnings.append(warning)

    def add_info(
        self,
        message: str,
        line_number: Optional[int] = None,
        field_name: Optional[str] = None,
        value: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        """Add an info message to the validation result."""
        info = ValidationError(
            level=ValidationLevel.INFO,
            message=message,
            line_number=line_number,
            field_name=field_name,
            value=value,
            suggestion=suggestion,
        )
        self.info.append(info)

    @property
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0

    @property
    def has_info(self) -> bool:
        """Check if validation has info messages."""
        return len(self.info) > 0

    @property
    def error_count(self) -> int:
        """Get number of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Get number of warnings."""
        return len(self.warnings)

    @property
    def info_count(self) -> int:
        """Get number of info messages."""
        return len(self.info)

    @property
    def total_issues(self) -> int:
        """Get total number of issues (errors + warnings + info)."""
        return len(self.errors) + len(self.warnings) + len(self.info)

    def raise_if_invalid(self):
        """Raise ValidationException if validation failed."""
        if not self.is_valid:
            # Import here to avoid circular dependency
            from agentmap.exceptions.validation_exceptions import ValidationException

            error_messages = [str(error) for error in self.errors]
            raise ValidationException(
                file_path=self.file_path,
                error_count=len(self.errors),
                error_messages=error_messages,
                warning_count=len(self.warnings),
                info_count=len(self.info),
            )
