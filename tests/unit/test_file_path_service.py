"""
Unit tests for FilePathService.

Tests path validation, sanitization, directory creation, path traversal protection,
and system path security checks across Windows and Unix-like platforms.
"""

import os
import platform
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agentmap.services.file_path_service import (
    FilePathService,
    InvalidPathError,
    PathTraversalError,
    SystemPathError,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestFilePathService(unittest.TestCase):
    """Test FilePathService functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.mock_app_config = self.mock_factory.create_mock_app_config_service()
        
        # Create service under test
        self.service = FilePathService(self.mock_app_config, self.mock_logging)
        
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.service)
        self.assertIsNotNone(self.service._dangerous_paths)
        self.assertTrue(len(self.service._dangerous_paths) > 0)

    def test_validate_safe_path_valid(self):
        """Test validation of safe path."""
        safe_path = os.path.join(self.temp_dir, "safe", "path.txt")
        
        result = self.service.validate_safe_path(safe_path, self.temp_dir)
        
        self.assertTrue(result)

    def test_validate_safe_path_empty(self):
        """Test validation fails for empty path."""
        with self.assertRaises(InvalidPathError):
            self.service.validate_safe_path("")

    def test_validate_safe_path_traversal(self):
        """Test path traversal detection."""
        traversal_path = os.path.join(self.temp_dir, "..", "dangerous", "path.txt")
        
        with self.assertRaises(PathTraversalError):
            self.service.validate_safe_path(traversal_path, self.temp_dir)

    def test_validate_safe_path_outside_base(self):
        """Test path outside base directory detection."""
        outside_path = "/completely/different/path.txt"
        
        with self.assertRaises(InvalidPathError):
            self.service.validate_safe_path(outside_path, self.temp_dir)

    def test_get_dangerous_system_paths(self):
        """Test dangerous system paths retrieval."""
        dangerous_paths = self.service.get_dangerous_system_paths()
        
        self.assertIsInstance(dangerous_paths, list)
        self.assertTrue(len(dangerous_paths) > 0)
        
        # Check platform-specific paths
        system = platform.system().lower()
        if system == "windows":
            self.assertIn("C:\\Windows", dangerous_paths)
        else:
            self.assertIn("/bin", dangerous_paths)

    @patch('platform.system')
    def test_dangerous_paths_windows(self, mock_system):
        """Test Windows-specific dangerous paths."""
        mock_system.return_value = "Windows"
        
        service = FilePathService(self.mock_app_config, self.mock_logging)
        dangerous_paths = service.get_dangerous_system_paths()
        
        self.assertIn("C:\\Windows", dangerous_paths)
        self.assertIn("C:\\Program Files", dangerous_paths)

    @patch('platform.system')
    def test_dangerous_paths_unix(self, mock_system):
        """Test Unix-specific dangerous paths."""
        mock_system.return_value = "Linux"
        
        service = FilePathService(self.mock_app_config, self.mock_logging)
        dangerous_paths = service.get_dangerous_system_paths()
        
        self.assertIn("/bin", dangerous_paths)
        self.assertIn("/etc", dangerous_paths)

    def test_ensure_directory_creates(self):
        """Test directory creation."""
        new_dir = os.path.join(self.temp_dir, "new", "directory")
        
        result_path = self.service.ensure_directory(new_dir)
        
        self.assertTrue(os.path.exists(new_dir))
        self.assertTrue(os.path.isdir(new_dir))
        self.assertEqual(str(result_path), new_dir)

    def test_ensure_directory_exists(self):
        """Test directory already exists."""
        existing_dir = os.path.join(self.temp_dir, "existing")
        os.makedirs(existing_dir, exist_ok=True)
        
        result_path = self.service.ensure_directory(existing_dir)
        
        self.assertTrue(os.path.exists(existing_dir))
        self.assertEqual(str(result_path), existing_dir)

    def test_ensure_directory_empty_path(self):
        """Test ensure directory with empty path."""
        with self.assertRaises(InvalidPathError):
            self.service.ensure_directory("")

    def test_ensure_directory_file_exists(self):
        """Test ensure directory where file exists."""
        file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(file_path, 'w') as f:
            f.write("test")
        
        with self.assertRaises(InvalidPathError):
            self.service.ensure_directory(file_path)

    def test_resolve_storage_path_basic(self):
        """Test basic storage path resolution."""
        result = self.service.resolve_storage_path(
            self.temp_dir, "json", "test_collection", "test.json"
        )
        
        expected_path = Path(self.temp_dir) / "json" / "test_collection" / "test.json"
        self.assertEqual(result, expected_path)

    def test_resolve_storage_path_no_collection(self):
        """Test storage path resolution without collection."""
        result = self.service.resolve_storage_path(
            self.temp_dir, "csv", filename="data.csv"
        )
        
        expected_path = Path(self.temp_dir) / "csv" / "data.csv"
        self.assertEqual(result, expected_path)

    def test_resolve_storage_path_no_filename(self):
        """Test storage path resolution without filename."""
        result = self.service.resolve_storage_path(
            self.temp_dir, "files", "documents"
        )
        
        expected_path = Path(self.temp_dir) / "files" / "documents"
        self.assertEqual(result, expected_path)

    def test_resolve_storage_path_empty_base(self):
        """Test storage path resolution with empty base directory."""
        with self.assertRaises(InvalidPathError):
            self.service.resolve_storage_path("", "json")

    def test_resolve_storage_path_empty_type(self):
        """Test storage path resolution with empty storage type."""
        with self.assertRaises(InvalidPathError):
            self.service.resolve_storage_path(self.temp_dir, "")

    def test_sanitize_filename_valid(self):
        """Test filename sanitization with valid filename."""
        valid_filename = "test_file.txt"
        
        result = self.service.sanitize_filename(valid_filename)
        
        self.assertEqual(result, valid_filename)

    def test_sanitize_filename_dangerous(self):
        """Test filename sanitization with dangerous characters."""
        dangerous_filename = "file<>:|*?.txt"
        
        result = self.service.sanitize_filename(dangerous_filename)
        
        # Should be sanitized to remove dangerous characters
        self.assertNotEqual(result, dangerous_filename)
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)

    def test_sanitize_filename_empty(self):
        """Test filename sanitization with empty filename."""
        with self.assertRaises(InvalidPathError):
            self.service.sanitize_filename("")

    def test_sanitize_filename_dots_only(self):
        """Test filename sanitization with dots only."""
        with self.assertRaises(InvalidPathError):
            self.service.sanitize_filename("...")

    def test_sanitize_filename_whitespace(self):
        """Test filename sanitization with whitespace."""
        filename_with_spaces = "  test file.txt  "
        
        result = self.service.sanitize_filename(filename_with_spaces)
        
        # Should trim whitespace
        self.assertEqual(result, "test file.txt")

    def test_check_dangerous_paths_system_path(self):
        """Test dangerous path checking with system path."""
        # This test may vary by platform
        system = platform.system().lower()
        
        if system == "windows":
            dangerous_path = "C:\\Windows\\System32\\test.txt"
        else:
            dangerous_path = "/bin/test"
        
        with self.assertRaises(SystemPathError):
            # Use private method directly for testing
            path_obj = Path(dangerous_path).resolve()
            self.service._check_dangerous_paths(path_obj)

    def test_integration_safe_workflow(self):
        """Test complete safe workflow integration."""
        # Create base directory
        base_dir = self.service.ensure_directory(
            os.path.join(self.temp_dir, "safe_workflow")
        )
        
        # Resolve storage path
        storage_path = self.service.resolve_storage_path(
            str(base_dir), "json", "test_collection", "data.json"
        )
        
        # Validate the path
        is_valid = self.service.validate_safe_path(str(storage_path), str(base_dir))
        
        # Sanitize filename component
        sanitized_filename = self.service.sanitize_filename("data.json")
        
        self.assertTrue(is_valid)
        self.assertEqual(sanitized_filename, "data.json")
        self.assertTrue(str(storage_path).startswith(str(base_dir)))


if __name__ == "__main__":
    unittest.main()
