"""Validation-related exceptions."""

from typing import List, Optional

from agentmap.exceptions.base_exceptions import AgentMapException


class ValidationException(AgentMapException):
    """Exception raised when validation fails."""

    def __init__(
        self,
        file_path: str,
        error_count: int,
        error_messages: Optional[List[str]] = None,
        warning_count: int = 0,
        info_count: int = 0,
    ):
        """
        Initialize ValidationException with primitive data.

        Args:
            file_path: Path to the file that failed validation
            error_count: Number of validation errors
            error_messages: List of error message strings (optional)
            warning_count: Number of warnings (optional)
            info_count: Number of info messages (optional)
        """
        self.file_path = file_path
        self.error_count = error_count
        self.warning_count = warning_count
        self.info_count = info_count
        self.error_messages = error_messages or []

        # Build descriptive message
        message = f"Validation failed with {error_count} error(s)"
        if warning_count > 0:
            message += f" and {warning_count} warning(s)"
        if info_count > 0:
            message += f" and {info_count} info message(s)"
        message += f" in {file_path}"

        super().__init__(message)

    def __str__(self) -> str:
        """Return detailed string representation."""
        lines = [super().__str__()]

        if self.error_messages:
            lines.append("Errors:")
            for i, msg in enumerate(self.error_messages, 1):
                lines.append(f"  {i}. {msg}")

        return "\n".join(lines)
