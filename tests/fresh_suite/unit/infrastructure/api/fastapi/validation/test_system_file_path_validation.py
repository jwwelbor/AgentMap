"""
Unit tests for system file path validation.

Tests the validate_system_file_path method to ensure it properly validates
system-resolved file paths without inappropriate path traversal checks.
"""

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from agentmap.infrastructure.api.fastapi.validation.common_validation import RequestValidator


class TestSystemFilePathValidation(unittest.TestCase):
    """Test system file path validation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary file for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_file = self.temp_dir / "test_workflow.csv"
        self.test_file.write_text("test,content\n1,2\n")
        
        # Create a large test file for size validation
        self.large_file = self.temp_dir / "large_file.csv"
        self.large_file.write_text("x" * (1024 * 1024))  # 1MB file

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary files
        if self.test_file.exists():
            self.test_file.unlink()
        if self.large_file.exists():
            self.large_file.unlink()
        self.temp_dir.rmdir()

    def test_validate_system_file_path_success(self):
        """Test successful validation of a system-resolved file path."""
        # This should succeed even with absolute paths (which would fail validate_file_path)
        result = RequestValidator.validate_system_file_path(self.test_file)
        
        self.assertEqual(result, self.test_file)
        self.assertTrue(result.exists())

    def test_validate_system_file_path_with_size_limit(self):
        """Test validation with size limit."""
        # Small file should pass
        result = RequestValidator.validate_system_file_path(
            self.test_file, max_size=1024
        )
        self.assertEqual(result, self.test_file)
        
        # Large file should fail size check
        with self.assertRaises(HTTPException) as context:
            RequestValidator.validate_system_file_path(
                self.large_file, max_size=1024
            )
        
        self.assertEqual(context.exception.status_code, 413)
        self.assertIn("File too large", context.exception.detail)

    def test_validate_system_file_path_nonexistent_file(self):
        """Test validation of non-existent file."""
        nonexistent_file = self.temp_dir / "nonexistent.csv"
        
        with self.assertRaises(HTTPException) as context:
            RequestValidator.validate_system_file_path(nonexistent_file)
        
        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("File not found", context.exception.detail)

    def test_validate_system_file_path_empty_path(self):
        """Test validation with empty path."""
        with self.assertRaises(HTTPException) as context:
            RequestValidator.validate_system_file_path("")
        
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("File path cannot be empty", context.exception.detail)

    def test_validate_system_file_path_directory(self):
        """Test validation when path points to a directory."""
        with self.assertRaises(HTTPException) as context:
            RequestValidator.validate_system_file_path(self.temp_dir)
        
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Path is not a file", context.exception.detail)

    def test_validate_system_file_path_accepts_absolute_paths(self):
        """Test that system validation accepts absolute paths (unlike user validation)."""
        # This test demonstrates the key difference from validate_file_path
        # System-resolved paths can be absolute and that's OK
        absolute_path = self.test_file.resolve()
        
        # This should NOT raise a path traversal error
        result = RequestValidator.validate_system_file_path(absolute_path)
        self.assertEqual(result, absolute_path)

    def test_validate_system_file_path_with_string_input(self):
        """Test validation with string input instead of Path object."""
        result = RequestValidator.validate_system_file_path(str(self.test_file))
        
        self.assertEqual(result, self.test_file)
        self.assertIsInstance(result, Path)


if __name__ == "__main__":
    unittest.main()
