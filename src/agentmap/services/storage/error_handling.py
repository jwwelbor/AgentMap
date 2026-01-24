"""
Error handling mixin for storage services.

This module provides error handling and result creation functionality
that can be mixed into storage services.
"""

from typing import Any

from agentmap.services.storage.types import (
    StorageProviderError,
    StorageResult,
    StorageServiceError,
)


class ErrorHandlerMixin:
    """
    Mixin class providing error handling functionality for storage services.

    This mixin handles:
    - Consistent error handling and logging
    - Creating standardized success/error results
    - Error type mapping

    Expected attributes on the class using this mixin:
    - provider_name: str
    - _logger: Logger instance
    """

    # Type hints for attributes expected from the base class
    provider_name: str
    _logger: Any

    def _handle_error(self, operation: str, error: Exception, **context) -> None:
        """
        Handle storage operation errors consistently.

        Args:
            operation: The operation that failed
            error: The exception that occurred
            **context: Additional context for error reporting

        Raises:
            StorageServiceError: If the error is already a StorageServiceError
            StorageProviderError: For all other errors
        """
        error_msg = f"Storage {operation} failed for {self.provider_name}: {str(error)}"
        self._logger.error(f"[{self.provider_name}] {error_msg}")

        # Add context to error if available
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            error_msg += f" (Context: {context_str})"

        # Raise appropriate exception type
        if isinstance(error, StorageServiceError):
            raise error
        else:
            raise StorageProviderError(error_msg) from error

    def _create_error_result(
        self, operation: str, error: str, **context
    ) -> StorageResult:
        """
        Create a standardized error result.

        Args:
            operation: The operation that failed
            error: Error message
            **context: Additional context

        Returns:
            StorageResult with error information
        """
        return StorageResult(success=False, operation=operation, error=error, **context)

    def _create_success_result(self, operation: str, **context) -> StorageResult:
        """
        Create a standardized success result.

        Args:
            operation: The operation that succeeded
            **context: Additional context

        Returns:
            StorageResult with success information
        """
        return StorageResult(success=True, operation=operation, **context)


__all__ = ["ErrorHandlerMixin"]
