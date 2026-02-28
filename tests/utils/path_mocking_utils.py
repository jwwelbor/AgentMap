"""
Path Mocking Utilities for AgentMap Tests.

This module provides reusable utilities for mocking pathlib.Path operations
that commonly cause issues in tests due to read-only properties.

Common Issues Solved:
- Path.exists is read-only and cannot be mocked directly
- Path.stat is read-only and cannot be mocked directly
- Complex path existence/timestamp scenarios need consistent handling

Usage Examples:
    # Simple path existence mocking
    with PathExistsMocker({"/existing/file.txt": True, "/missing/file.txt": False}):
        # test code

    # Path stat mocking with timestamps
    with PathStatMocker({"/file1.txt": 1642000000, "/file2.txt": 1641000000}):
        # test code

    # Combined path operations
    with PathOperationsMocker() as path_mock:
        path_mock.set_exists("/file.txt", True)
        path_mock.set_stat("/file.txt", timestamp=1642000000)
        # test code
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Union
from unittest.mock import Mock, patch


class PathExistsMocker:
    """
    Context manager for mocking pathlib.Path.exists() method.

    Handles the read-only nature of Path.exists by patching the global method.
    """

    def __init__(self, path_existence_map: Dict[Union[str, Path], bool]):
        """
        Initialize with a mapping of paths to their existence status.

        Args:
            path_existence_map: Dictionary mapping path strings/Path objects to boolean existence
        """
        # Normalize all paths to strings for consistent comparison
        self.path_map = {
            str(path): exists for path, exists in path_existence_map.items()
        }
        self.default_exists = False

    def _make_mock_exists(self):
        """Create mock function for Path.exists() method."""

        def mock_exists(path_instance):
            path_str = str(path_instance)
            return self.path_map.get(path_str, self.default_exists)

        return mock_exists

    def __enter__(self):
        self.patcher = patch("pathlib.Path.exists", self._make_mock_exists())
        self.patcher.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.patcher.__exit__(exc_type, exc_val, exc_tb)


class PathStatMocker:
    """
    Context manager for mocking pathlib.Path.stat() method.

    Handles the read-only nature of Path.stat by patching the global method.
    """

    def __init__(self, path_timestamp_map: Dict[Union[str, Path], float]):
        """
        Initialize with a mapping of paths to their modification timestamps.

        Args:
            path_timestamp_map: Dictionary mapping path strings/Path objects to timestamps
        """
        # Normalize all paths to strings for consistent comparison
        self.path_map = {
            str(path): timestamp for path, timestamp in path_timestamp_map.items()
        }
        self.default_timestamp = 1640000000  # Default timestamp if path not found

    def _make_mock_stat(self):
        """Create mock function for Path.stat() method."""

        def mock_stat(path_instance):
            path_str = str(path_instance)
            timestamp = self.path_map.get(path_str, self.default_timestamp)

            mock_stat_result = Mock()
            mock_stat_result.st_mtime = timestamp
            return mock_stat_result

        return mock_stat

    def __enter__(self):
        self.patcher = patch("pathlib.Path.stat", self._make_mock_stat())
        self.patcher.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.patcher.__exit__(exc_type, exc_val, exc_tb)


class PathOperationsMocker:
    """
    Comprehensive context manager for mocking multiple Path operations.

    Provides a fluent interface for setting up complex path mocking scenarios.
    """

    def __init__(self):
        self.existence_map: Dict[str, bool] = {}
        self.timestamp_map: Dict[str, float] = {}
        self.default_exists = False
        self.default_timestamp = 1640000000

        self.exists_patcher = None
        self.stat_patcher = None

    def set_exists(
        self, path: Union[str, Path], exists: bool
    ) -> "PathOperationsMocker":
        """Set existence status for a path. Returns self for chaining."""
        self.existence_map[str(path)] = exists
        return self

    def set_stat(
        self, path: Union[str, Path], timestamp: float
    ) -> "PathOperationsMocker":
        """Set stat timestamp for a path. Returns self for chaining."""
        self.timestamp_map[str(path)] = timestamp
        return self

    def set_file_newer_than(
        self,
        newer_path: Union[str, Path],
        older_path: Union[str, Path],
        newer_time: float = 1642000000,
        older_time: float = 1641000000,
    ) -> "PathOperationsMocker":
        """Convenience method to set one file as newer than another."""
        self.set_exists(newer_path, True)
        self.set_exists(older_path, True)
        self.set_stat(newer_path, newer_time)
        self.set_stat(older_path, older_time)
        return self

    def set_compilation_scenario(
        self,
        output_path: Union[str, Path],
        csv_path: Union[str, Path],
        is_current: bool = True,
    ) -> "PathOperationsMocker":
        """Convenience method for common compilation currency scenarios."""
        if is_current:
            # Compiled file is newer than CSV
            self.set_file_newer_than(output_path, csv_path, 1642000000, 1641000000)
        else:
            # CSV is newer than compiled file (outdated compilation)
            self.set_file_newer_than(csv_path, output_path, 1642000000, 1641000000)
        return self

    def _make_mock_exists(self):
        """Create mock function for Path.exists() method."""

        def mock_exists(path_instance):
            path_str = str(path_instance)
            return self.existence_map.get(path_str, self.default_exists)

        return mock_exists

    def _make_mock_stat(self):
        """Create mock function for Path.stat() method."""

        def mock_stat(path_instance):
            path_str = str(path_instance)
            timestamp = self.timestamp_map.get(path_str, self.default_timestamp)

            mock_stat_result = Mock()
            mock_stat_result.st_mtime = timestamp
            return mock_stat_result

        return mock_stat

    def __enter__(self):
        self.exists_patcher = patch("pathlib.Path.exists", self._make_mock_exists())
        self.stat_patcher = patch("pathlib.Path.stat", self._make_mock_stat())

        self.exists_patcher.__enter__()
        self.stat_patcher.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stat_patcher:
            self.stat_patcher.__exit__(exc_type, exc_val, exc_tb)
        if self.exists_patcher:
            self.exists_patcher.__exit__(exc_type, exc_val, exc_tb)


# Convenience functions for common scenarios
@contextmanager
def mock_path_exists(path_existence_map: Dict[Union[str, Path], bool]):
    """Convenience context manager for simple path existence mocking."""
    with PathExistsMocker(path_existence_map):
        yield


@contextmanager
def mock_path_stat(path_timestamp_map: Dict[Union[str, Path], float]):
    """Convenience context manager for simple path stat mocking."""
    with PathStatMocker(path_timestamp_map):
        yield


@contextmanager
def mock_file_comparison(
    newer_file: Union[str, Path],
    older_file: Union[str, Path],
    newer_time: float = 1642000000,
    older_time: float = 1641000000,
):
    """Convenience context manager for comparing file modification times."""
    with PathOperationsMocker() as path_mock:
        path_mock.set_file_newer_than(newer_file, older_file, newer_time, older_time)
        yield path_mock


@contextmanager
def mock_compilation_currency(
    output_path: Union[str, Path], csv_path: Union[str, Path], is_current: bool = True
):
    """Convenience context manager for compilation currency scenarios."""
    with PathOperationsMocker() as path_mock:
        path_mock.set_compilation_scenario(output_path, csv_path, is_current)
        yield path_mock


# Time mocking utilities
class TimeMocker:
    """Utility for mocking time.time() with controlled progression."""

    def __init__(self, start_time: float = 0.0, increment: float = 0.1):
        self.start_time = start_time
        self.increment = increment
        self.call_count = 0

    def __call__(self):
        """Mock time.time() call."""
        result = self.start_time + (self.call_count * self.increment)
        self.call_count += 1
        return result


@contextmanager
def mock_time_progression(start_time: float = 0.0, increment: float = 0.1):
    """Mock time.time() with automatic progression for timing tests."""
    time_mocker = TimeMocker(start_time, increment)
    with patch("time.time", time_mocker):
        yield time_mocker


# Mock service configuration helpers
class MockServiceConfigHelper:
    """Helper for configuring mock services with proper Path properties."""

    @staticmethod
    def configure_app_config_service(mock_service, config_dict: Dict[str, str]):
        """
        Configure a mock app config service with both method and property access.

        Args:
            mock_service: Mock service object to configure
            config_dict: Dictionary of config keys to path strings
        """
        # Configure method returns and properties for all paths

        if "csv_path" in config_dict:
            csv_path = Path(config_dict["csv_path"])
            mock_service.get_csv_repository_path.return_value = csv_path
            mock_service.csv_path = csv_path

        if "compiled_graphs_path" in config_dict:
            compiled_path = Path(config_dict["compiled_graphs_path"])
            mock_service.get_compiled_graphs_path.return_value = compiled_path
            mock_service.compiled_graphs_path = compiled_path

        if "functions_path" in config_dict:
            functions_path = Path(config_dict["functions_path"])
            mock_service.get_functions_path.return_value = functions_path
            mock_service.functions_path = functions_path

        return mock_service


# Integration with existing MockServiceFactory
def enhance_mock_app_config_service(mock_service, config_dict: Dict[str, str]):
    """
    Enhance an existing mock app config service with proper Path property support.

    This function can be used to upgrade existing MockServiceFactory created services.
    """
    return MockServiceConfigHelper.configure_app_config_service(
        mock_service, config_dict
    )
