"""
Error handling mixin for storage services.
"""

from typing import Any

from agentmap.services.storage.types import (
    StorageProviderError,
    StorageResult,
    StorageServiceError,
)


class ErrorHandlerMixin:
    """Mixin class providing error handling functionality."""

    provider_name: str
    _logger: Any

    def _handle_error(self, operation: str, error: Exception, **context) -> None:
        """Handle storage operation errors consistently."""
        error_msg = f"Storage {operation} failed for {self.provider_name}: {str(error)}"
        self._logger.error(f"[{self.provider_name}] {error_msg}")

        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            error_msg += f" (Context: {context_str})"

        if isinstance(error, StorageServiceError):
            raise error
        else:
            raise StorageProviderError(error_msg) from error

    def _create_error_result(
        self, operation: str, error: str, **context
    ) -> StorageResult:
        """Create a standardized error result."""
        return StorageResult(success=False, operation=operation, error=error, **context)

    def _create_success_result(self, operation: str, **context) -> StorageResult:
        """Create a standardized success result."""
        return StorageResult(success=True, operation=operation, **context)


__all__ = ["ErrorHandlerMixin"]
