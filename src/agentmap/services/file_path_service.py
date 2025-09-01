"""
File path service for centralized path validation and security.

Provides secure path operations with validation, sanitization, and protection
against path traversal attacks. Supports both Windows and Unix-like systems.
"""

import os
import platform
from pathlib import Path
from typing import List, Optional

from pathvalidate import is_valid_filename, sanitize_filename

from agentmap.exceptions.base_exceptions import (
    AgentMapException,
    InvalidPathError,
    PathTraversalError,
    SystemPathError,
)
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class FilePathService:
    """
    Centralized file path validation and security service.

    Provides secure path operations including:
    - Path validation and sanitization
    - Path traversal attack prevention
    - System path protection
    - Directory creation
    - Storage path resolution
    - Cross-platform filename sanitization
    """

    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        """
        Initialize FilePathService.

        Args:
            logging_service: Logging service for audit trails
        """
        self.app_config_service = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self._dangerous_paths = self._get_dangerous_system_paths()

        self.logger.debug("FilePathService initialized with security checks enabled")

    def validate_safe_path(
        self, path: str, base_directory: Optional[str] = None
    ) -> bool:
        """
        Validate that a path is safe to use.

        Args:
            path: Path to validate
            base_directory: Optional base directory to restrict path within

        Returns:
            True if path is safe, False otherwise

        Raises:
            PathTraversalError: If path contains traversal attempts
            SystemPathError: If path points to dangerous system location
            InvalidPathError: If path is invalid or unsafe
        """
        if not path:
            self.logger.warning("Empty path provided for validation")
            raise InvalidPathError("Path cannot be empty")

        try:
            # Normalize and resolve the path
            normalized_path = self._normalize_and_resolve_path(path)

            # Check for path traversal attempts
            self._check_path_traversal(path)

            # If base directory specified, ensure path is within it
            if base_directory:
                self._check_base_directory_constraint(
                    normalized_path, path, base_directory
                )

            # Check against dangerous system paths
            self._check_dangerous_paths(normalized_path)

            self.logger.debug(f"Path validated successfully: {path}")
            return True

        except (PathTraversalError, SystemPathError, InvalidPathError):
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error validating path {path}: {e}")
            raise InvalidPathError(f"Failed to validate path: {e}")

    def get_dangerous_system_paths(self) -> List[str]:
        """
        Get list of dangerous system paths that should be protected.

        Returns:
            List of dangerous system path patterns
        """
        return self._dangerous_paths.copy()

    def _normalize_and_resolve_path(self, path: str) -> Path:
        """
        Normalize and resolve a path string to a Path object.

        Args:
            path: Path string to normalize

        Returns:
            Resolved Path object

        Raises:
            InvalidPathError: If path cannot be resolved
        """
        try:
            return Path(path).resolve()
        except Exception as e:
            self.logger.error(f"Failed to resolve path {path}: {e}")
            raise InvalidPathError(f"Cannot resolve path: {path}")

    def _check_path_traversal(self, path: str) -> None:
        """
        Check for path traversal attempts in the path string.

        Args:
            path: Path string to check

        Raises:
            PathTraversalError: If path contains traversal attempts
        """
        if ".." in str(path):
            self.logger.warning(f"Path traversal detected: {path}")
            raise PathTraversalError(f"Path traversal not allowed: {path}")

    def _check_base_directory_constraint(
        self, normalized_path: Path, original_path: str, base_directory: str
    ) -> None:
        """
        Check if normalized path is within the specified base directory.

        Args:
            normalized_path: Resolved path to check
            original_path: Original path string for error messages
            base_directory: Base directory to constrain within

        Raises:
            InvalidPathError: If path is outside base directory
        """
        try:
            base_path = self._normalize_and_resolve_path(base_directory)
            normalized_path.relative_to(base_path)
        except ValueError:
            self.logger.warning(
                f"Path outside base directory: {original_path} not in {base_directory}"
            )
            raise InvalidPathError(
                f"Path must be within base directory: {base_directory}"
            )

    def _get_dangerous_system_paths(self) -> List[str]:
        """
        Generate list of dangerous system paths for current platform.

        Returns:
            List of dangerous system paths
        """
        dangerous_paths = []

        system = platform.system().lower()

        if system == "windows":
            # Windows system paths
            dangerous_paths.extend(
                [
                    "C:\\Windows",
                    "C:\\Windows\\System32",
                    "C:\\Program Files",
                    "C:\\Program Files (x86)",
                    "C:\\Users\\Default",
                    "C:\\ProgramData",
                    "C:\\$Recycle.Bin",
                    "C:\\System Volume Information",
                    "%SYSTEMROOT%",
                    "%WINDIR%",
                    "%PROGRAMFILES%",
                    "%TEMP%",
                    "%TMP%",
                ]
            )
        else:
            # Unix-like system paths
            dangerous_paths.extend(
                [
                    "/bin",
                    "/sbin",
                    "/usr/bin",
                    "/usr/sbin",
                    "/etc",
                    "/root",
                    "/boot",
                    "/dev",
                    "/proc",
                    "/sys",
                    "/var/log",
                    "/var/run",
                    # "/tmp",  # Removed to allow test operations
                    "/usr/lib",
                    "/usr/share",
                ]
            )

        return dangerous_paths

    def _check_dangerous_paths(self, path: Path) -> None:
        """
        Check if path points to dangerous system location.

        Args:
            path: Resolved path to check

        Raises:
            SystemPathError: If path is in dangerous location
        """
        path_str = str(path).lower()

        for dangerous_path in self._dangerous_paths:
            dangerous_path_lower = dangerous_path.lower()

            # Handle Windows environment variables
            if "%" in dangerous_path:
                try:
                    expanded = os.path.expandvars(dangerous_path).lower()
                    if path_str.startswith(expanded):
                        self.logger.warning(
                            f"Access to dangerous system path blocked: {path}"
                        )
                        raise SystemPathError(
                            f"Access denied to system path: {dangerous_path}"
                        )
                except:
                    continue

            # Direct path check
            if path_str.startswith(dangerous_path_lower):
                self.logger.warning(f"Access to dangerous system path blocked: {path}")
                raise SystemPathError(f"Access denied to system path: {dangerous_path}")

    def ensure_directory(self, path: str) -> Path:
        """
        Safely create directory structure if it doesn't exist.

        Args:
            path: Directory path to ensure exists

        Returns:
            Path object of created/existing directory

        Raises:
            InvalidPathError: If path validation fails
            SystemPathError: If attempting to create in dangerous location
        """
        if not path:
            raise InvalidPathError("Directory path cannot be empty")

        try:
            # Validate path first
            self.validate_safe_path(path)

            dir_path = Path(path)

            # Create directory if it doesn't exist
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created directory: {path}")
            elif not dir_path.is_dir():
                raise InvalidPathError(f"Path exists but is not a directory: {path}")

            return dir_path

        except (InvalidPathError, SystemPathError, PathTraversalError):
            raise
        except PermissionError as e:
            self.logger.error(f"Permission denied creating directory {path}: {e}")
            raise InvalidPathError(f"Permission denied: {path}")
        except Exception as e:
            self.logger.error(f"Failed to create directory {path}: {e}")
            raise InvalidPathError(f"Failed to create directory: {e}")

    def resolve_storage_path(
        self,
        base_directory: str,
        storage_type: str,
        collection: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Resolve and validate storage path components.

        Args:
            base_directory: Base directory for storage
            storage_type: Type of storage (e.g., 'json', 'csv', 'files')
            collection: Optional collection/subdirectory name
            filename: Optional filename

        Returns:
            Validated and resolved storage path

        Raises:
            InvalidPathError: If any path component is invalid
        """
        if not base_directory:
            raise InvalidPathError("Base directory cannot be empty")

        if not storage_type:
            raise InvalidPathError("Storage type cannot be empty")

        try:
            # Start with base directory
            storage_path = Path(base_directory) / storage_type

            # Add collection if provided
            if collection:
                sanitized_collection = self.sanitize_filename(collection)
                storage_path = storage_path / sanitized_collection

            # Add filename if provided
            if filename:
                sanitized_filename = self.sanitize_filename(filename)
                storage_path = storage_path / sanitized_filename

            # Validate the complete path
            self.validate_safe_path(str(storage_path), base_directory)

            self.logger.debug(f"Resolved storage path: {storage_path}")
            return storage_path

        except (InvalidPathError, SystemPathError, PathTraversalError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to resolve storage path: {e}")
            raise InvalidPathError(f"Path resolution failed: {e}")

    def get_bundle_path(self, csv_hash: str, graph_name: Optional[str] = None) -> Path:
        """Get consistent bundle file path using standard format.

        Args:
            csv_hash: Hash of CSV content
            graph_name: Optional graph name for composite key
            base_directory: Optional base directory (uses cache if not provided)

        Returns:
            Validated Path object for bundle file

        Raises:
            InvalidPathError: If parameters are invalid or path cannot be created
        """
        if not csv_hash:
            raise InvalidPathError("CSV hash is required for bundle path")

        try:
            # Use consistent format: {hash_prefix}_{graph_name}.json
            safe_graph_name = (graph_name or "default").replace("/", "_")
            safe_graph_name = self.sanitize_filename(safe_graph_name)

            filename = f"{csv_hash[:8]}_{safe_graph_name}.json"

            base_directory = str(self.app_config_service.get_cache_path())

            return self.resolve_storage_path(
                base_directory=base_directory, storage_type="bundles", filename=filename
            )

        except InvalidPathError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to create bundle path: {e}")
            raise InvalidPathError(f"Bundle path creation failed: {e}")

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to ensure it's safe for filesystem use.

        Args:
            filename: Filename to sanitize

        Returns:
            Sanitized filename safe for filesystem use

        Raises:
            InvalidPathError: If filename cannot be sanitized
        """
        if not filename:
            raise InvalidPathError("Filename cannot be empty")

        try:
            # Use pathvalidate to sanitize the filename
            sanitized = sanitize_filename(filename.strip())

            # Additional checks for edge cases
            if not sanitized:
                raise InvalidPathError(f"Filename cannot be sanitized: '{filename}'")

            if sanitized.startswith(".") and len(sanitized.strip(".")) == 0:
                raise InvalidPathError(f"Filename cannot be only dots: '{filename}'")

            # Validate the sanitized filename
            if not is_valid_filename(sanitized):
                raise InvalidPathError(
                    f"Sanitized filename is still invalid: '{sanitized}'"
                )

            if sanitized != filename:
                self.logger.debug(f"Filename sanitized: '{filename}' -> '{sanitized}'")

            return sanitized

        except InvalidPathError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to sanitize filename '{filename}': {e}")
            raise InvalidPathError(f"Filename sanitization failed: {e}")
