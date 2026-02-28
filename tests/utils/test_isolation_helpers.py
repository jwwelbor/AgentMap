"""
Test isolation helpers for preventing CI vs local test failures.

This module provides utilities to ensure proper test isolation and prevent
the common issue where tests pass locally but fail in CI environments.
"""

import functools
from pathlib import Path
from typing import Any, Callable, Dict
from unittest.mock import patch


def ensure_file_exists(file_path: Path, description: str = "Test file") -> None:
    """
    Ensure a file exists with helpful error messages for CI debugging.

    Args:
        file_path: Path to the file that should exist
        description: Description for error messages

    Raises:
        AssertionError: If file doesn't exist or is empty
    """
    if not file_path.exists():
        raise AssertionError(f"{description} should exist at: {file_path}")

    if not file_path.is_file():
        raise AssertionError(f"{description} should be a file: {file_path}")

    if file_path.stat().st_size == 0:
        raise AssertionError(f"{description} should not be empty: {file_path}")


def with_path_mocking(workflow_path_key: str = "execution_csv_path"):
    """
    Decorator to automatically mock path resolution for API endpoint tests.

    This prevents CI failures where path validation happens before mocks are applied.

    Args:
        workflow_path_key: Attribute name on test instance containing the CSV path

    Usage:
        @with_path_mocking()
        def test_timeout_scenario(self):
            # Test will automatically mock _resolve_workflow_path
            # to return self.execution_csv_path
    """

    def decorator(test_func: Callable) -> Callable:
        @functools.wraps(test_func)
        def wrapper(self, *args, **kwargs):
            # Get the CSV path from the test instance
            csv_path = getattr(self, workflow_path_key, None)
            if csv_path is None:
                raise ValueError(
                    f"Test instance must have attribute '{workflow_path_key}'"
                )

            # Ensure the file exists before mocking
            ensure_file_exists(csv_path, f"CSV file for {workflow_path_key}")

            # Apply path resolution mock
            with patch(
                "agentmap.infrastructure.api.fastapi.routes.execute._resolve_workflow_path"
            ) as mock_resolve:
                mock_resolve.return_value = csv_path
                return test_func(self, *args, **kwargs)

        return wrapper

    return decorator


def with_robust_mocking(**mock_configs: Dict[str, Any]):
    """
    Decorator to apply multiple robust mocks with proper error handling.

    Args:
        mock_configs: Dictionary of patch paths and their return values/side effects

    Usage:
        @with_robust_mocking(
            'service.method': {'side_effect': TimeoutError("Test timeout")},
            'other.service': {'return_value': Mock()}
        )
        def test_scenario(self):
            # Multiple mocks applied automatically
    """

    def decorator(test_func: Callable) -> Callable:
        @functools.wraps(test_func)
        def wrapper(self, *args, **kwargs):
            # Build list of context managers
            patches = []
            for patch_path, config in mock_configs.items():
                mock_patch = patch(patch_path)
                patches.append(mock_patch)

            # Apply all patches
            with (
                patches[0]
                if len(patches) == 1
                else patch.multiple(**{k: v for k, v in mock_configs.items()})
            ):
                return test_func(self, *args, **kwargs)

        return wrapper

    return decorator


class CITestValidator:
    """
    Utility class for validating test setup in CI environments.
    """

    @staticmethod
    def validate_test_setup(test_instance, required_attributes: list[str]) -> None:
        """
        Validate that a test instance has all required attributes for proper setup.

        Args:
            test_instance: Test class instance
            required_attributes: List of attribute names that must exist

        Raises:
            AssertionError: If any required attribute is missing or invalid
        """
        for attr_name in required_attributes:
            if not hasattr(test_instance, attr_name):
                raise AssertionError(
                    f"Test setup incomplete: missing attribute '{attr_name}'"
                )

            attr_value = getattr(test_instance, attr_name)
            if attr_value is None:
                raise AssertionError(
                    f"Test setup incomplete: attribute '{attr_name}' is None"
                )

            # Special handling for Path objects
            if isinstance(attr_value, Path):
                ensure_file_exists(attr_value, f"Test attribute '{attr_name}'")

    @staticmethod
    def validate_temp_directory(temp_dir: Path) -> None:
        """
        Validate that a temporary directory is properly set up.

        Args:
            temp_dir: Path to temporary directory

        Raises:
            AssertionError: If directory is invalid
        """
        if not temp_dir.exists():
            raise AssertionError(f"Temporary directory should exist: {temp_dir}")

        if not temp_dir.is_dir():
            raise AssertionError(f"Temporary path should be a directory: {temp_dir}")

        # Try to create a test file to ensure write permissions
        test_file = temp_dir / "ci_test_validation.tmp"
        try:
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
        except Exception as e:
            raise AssertionError(
                f"Temporary directory is not writable: {temp_dir} - {e}"
            )


def validate_ci_environment(test_instance) -> Dict[str, Any]:
    """
    Comprehensive validation for CI test environment.

    Args:
        test_instance: Test class instance

    Returns:
        Dictionary with validation results and environment info

    Raises:
        AssertionError: If critical validation fails
    """
    validation_info = {
        "temp_dir_valid": False,
        "csv_files_exist": False,
        "container_initialized": False,
        "services_available": False,
    }

    # Validate temporary directory
    if hasattr(test_instance, "temp_dir"):
        CITestValidator.validate_temp_directory(test_instance.temp_dir)
        validation_info["temp_dir_valid"] = True

    # Validate CSV files
    csv_attributes = [
        attr
        for attr in dir(test_instance)
        if attr.endswith("_csv_path") and isinstance(getattr(test_instance, attr), Path)
    ]

    for csv_attr in csv_attributes:
        csv_path = getattr(test_instance, csv_attr)
        ensure_file_exists(csv_path, f"CSV file '{csv_attr}'")

    if csv_attributes:
        validation_info["csv_files_exist"] = True

    # Validate container
    if hasattr(test_instance, "container") and test_instance.container is not None:
        validation_info["container_initialized"] = True

        # Check basic services
        try:
            logging_service = test_instance.container.logging_service()
            config_service = test_instance.container.app_config_service()
            if logging_service and config_service:
                validation_info["services_available"] = True
        except Exception:
            pass  # Services not available, but container exists

    return validation_info


# Convenience decorator combining common CI fixes
def ci_robust_test(
    workflow_path_key: str = "execution_csv_path", validate_setup: bool = True
):
    """
    Decorator that applies multiple CI robustness fixes.

    Args:
        workflow_path_key: CSV path attribute name
        validate_setup: Whether to validate test setup

    Usage:
        @ci_robust_test()
        def test_execution_scenario(self):
            # Test will be automatically made CI-robust
    """

    def decorator(test_func: Callable) -> Callable:
        @functools.wraps(test_func)
        def wrapper(self, *args, **kwargs):
            if validate_setup:
                # Basic validation
                required_attrs = ["temp_dir", "container", workflow_path_key]
                CITestValidator.validate_test_setup(self, required_attrs)

            # Apply path mocking
            csv_path = getattr(self, workflow_path_key)
            ensure_file_exists(csv_path, f"CSV file for {workflow_path_key}")

            with patch(
                "agentmap.infrastructure.api.fastapi.routes.execute._resolve_workflow_path"
            ) as mock_resolve:
                mock_resolve.return_value = csv_path
                return test_func(self, *args, **kwargs)

        return wrapper

    return decorator
