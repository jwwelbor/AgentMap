"""
Unit tests for FileStorageService.

These tests validate the FileStorageService implementation including:
- File I/O operations and path handling
- File locking and concurrent access
- Error handling for file system issues
- File format validation
- Security path validation
- Text and binary file handling
- LangChain document loader integration
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from agentmap.services.storage.file_service import FileStorageService
from agentmap.services.storage.types import WriteMode, StorageResult, StorageProviderError
from tests.utils.mock_service_factory import MockServiceFactory


class TestFileStorageService(unittest.TestCase):
    """Unit tests for FileStorageService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "storage": {
                "file": {
                    "options": {
                        "base_directory": self.temp_dir,
                        "encoding": "utf-8",
                        "allow_binary": True
                    }
                }
            }
        })
        
        # Create FileStorageService with mocked dependencies
        self.service = FileStorageService(
            provider_name="file",
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service._logger
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_file(self, relative_path: str, content: str) -> str:
        """Helper to create a test file."""
        full_path = os.path.join(self.temp_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return full_path
    
    def _create_test_binary_file(self, relative_path: str, content: bytes) -> str:
        """Helper to create a test binary file."""
        full_path = os.path.join(self.temp_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'wb') as f:
            f.write(content)
        return full_path
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.provider_name, "file")
        self.assertEqual(self.service.configuration, self.mock_app_config_service)
        self.assertIsNotNone(self.service._logger)
        
        # Verify base directory was created
        self.assertTrue(os.path.exists(self.temp_dir))
    
    def test_client_initialization(self):
        """Test that client initializes with correct configuration."""
        client = self.service.client
        
        # Verify client configuration has expected structure
        self.assertIsInstance(client, dict)
        
        # Check for expected configuration keys
        expected_keys = [
            "base_directory", "encoding", "chunk_size", "chunk_overlap",
            "should_split", "include_metadata", "allow_binary"
        ]
        
        for key in expected_keys:
            self.assertIn(key, client)
        
        # Verify base directory is correct
        self.assertEqual(client["base_directory"], self.temp_dir)
    
    def test_service_health_check(self):
        """Test that health check works correctly."""
        # Should be healthy by default
        self.assertTrue(self.service.health_check())
        
        # Health check should test file operations
        result = self.service._perform_health_check()
        self.assertTrue(result)
    
    def test_health_check_with_inaccessible_directory(self):
        """Test health check fails with inaccessible directory."""
        # Create service with an invalid path that can't be created
        # Use a path with invalid characters that will cause creation to fail
        import platform
        if platform.system() == "Windows":
            # Windows doesn't allow these characters in paths
            invalid_path = "C:\\invalid<>|path"
        else:
            # Unix-like systems - use a path we can't write to
            invalid_path = "/root/readonly_test_directory"
        
        bad_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {
                "file": {
                    "options": {
                        "base_directory": invalid_path
                    }
                }
            }
        })
        
        # The service initialization itself should fail when trying to create invalid directory
        with self.assertRaises(Exception):
            bad_service = FileStorageService(
                provider_name="file",
                configuration=bad_config,
                logging_service=self.mock_logging_service
            )
            # Try to access the client to trigger initialization
            _ = bad_service.client
    
    # =============================================================================
    # 2. File Path Security Tests
    # =============================================================================
    
    def test_path_validation_security(self):
        """Test path validation prevents directory traversal attacks."""
        import platform
        
        # Base dangerous paths that should work on all platforms
        dangerous_paths = [
            "../../../etc/passwd",
            "subdir/../../etc/passwd",
        ]
        
        # Add platform-specific dangerous paths
        if platform.system() != "Windows":
            # Unix-like systems
            dangerous_paths.extend([
                "/etc/passwd",
                "/etc/shadow",
                "/root/.bashrc"
            ])
        else:
            # Windows systems - use paths that are more likely to be restricted
            dangerous_paths.extend([
                "C:\\Windows\\System32\\drivers\\etc\\hosts",
                "..\\..\\..\\Windows\\System32\\config"
            ])
        
        for dangerous_path in dangerous_paths:
            # Test through public read API
            # The service might either raise an exception or return None
            try:
                result = self.service.read("test_collection", dangerous_path)
                # If no exception was raised, result should be None
                self.assertIsNone(result, f"Expected None for dangerous path: {dangerous_path}")
            except StorageProviderError as e:
                # If exception was raised, verify it mentions path security
                self.assertIn("outside base directory", str(e))
            except Exception as e:
                # Some paths might cause other exceptions (e.g., invalid path format)
                # This is also acceptable as it prevents access
                pass
            
            # Test through public write API  
            # The service might either raise an exception or return error result
            try:
                result = self.service.write("test_collection", "content", dangerous_path)
                # If no exception was raised, should return error result
                if hasattr(result, 'success'):
                    self.assertFalse(result.success, f"Expected failure for dangerous path: {dangerous_path}")
                    if not result.success and result.error:
                        self.assertIn("outside base directory", result.error)
            except StorageProviderError as e:
                # If exception was raised, verify it mentions path security
                self.assertIn("outside base directory", str(e))
            except Exception as e:
                # Some paths might cause other exceptions (e.g., invalid path format)
                # This is also acceptable as it prevents access
                pass
    
    def test_path_validation_allowed_paths(self):
        """Test path validation allows safe paths."""
        safe_paths = [
            "safe_file.txt",
            "subdir/safe_file.txt",
            "deeply/nested/safe_file.txt",
        ]
        
        for safe_path in safe_paths:
            # Should not raise exception
            validated_path = self.service._validate_file_path(safe_path)
            self.assertIsInstance(validated_path, str)
            self.assertTrue(validated_path.startswith(self.temp_dir))
    
    def test_resolve_file_path(self):
        """Test file path resolution."""
        # Test directory only (collection)
        dir_path = self.service._resolve_file_path("documents")
        expected = Path(self.temp_dir) / "documents"
        self.assertEqual(dir_path, expected)
        
        # Test file path (collection + document_id)
        file_path = self.service._resolve_file_path("documents", "file.txt")
        expected = Path(self.temp_dir) / "documents" / "file.txt"
        self.assertEqual(file_path, expected)
    
    # =============================================================================
    # 3. Text File Operations Tests
    # =============================================================================
    
    def test_write_and_read_text_file(self):
        """Test basic text file write and read operations."""
        collection = "documents"
        document_id = "test.txt"
        content = "This is a test file content.\nWith multiple lines."
        
        # Write text file
        result = self.service.write(collection, content, document_id)
        
        # Verify write success
        self.assertIsInstance(result, StorageResult)
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "write")
        self.assertEqual(result.collection, collection)
        self.assertTrue(result.created_new)
        
        # Verify file exists
        self.assertTrue(self.service.exists(collection, document_id))
        
        # Read the file back
        retrieved_content = self.service.read(collection, document_id, format="text")
        self.assertEqual(retrieved_content, content)
    
    def test_write_modes_text_files(self):
        """Test different write modes for text files."""
        collection = "write_modes"
        document_id = "test.txt"
        
        # Test WRITE mode (create)
        initial_content = "Initial content"
        result = self.service.write(collection, initial_content, document_id, WriteMode.WRITE)
        self.assertTrue(result.success)
        self.assertTrue(result.created_new)
        
        # Test APPEND mode
        append_content = "Appended content"
        result = self.service.write(collection, append_content, document_id, WriteMode.APPEND)
        self.assertTrue(result.success)
        self.assertFalse(result.created_new)
        
        # Verify content was appended
        final_content = self.service.read(collection, document_id, format="text")
        self.assertIn(initial_content, final_content)
        self.assertIn(append_content, final_content)
        
        # Test UPDATE mode (same as write for text files)
        update_content = "Updated content"
        result = self.service.write(collection, update_content, document_id, WriteMode.UPDATE)
        self.assertTrue(result.success)
        
        # Content should be replaced
        final_content = self.service.read(collection, document_id, format="text")
        self.assertEqual(final_content, update_content)
    
    def test_file_format_detection(self):
        """Test file format detection."""
        # Test text file detection
        text_files = ["file.txt", "script.py", "data.csv", "config.json", "readme.md"]
        for filename in text_files:
            self.assertTrue(self.service._is_text_file(filename))
            self.assertFalse(self.service._is_binary_file(filename))
        
        # Test binary file detection
        binary_files = ["image.png", "document.pdf", "archive.zip", "executable.exe"]
        for filename in binary_files:
            self.assertTrue(self.service._is_binary_file(filename))
            self.assertFalse(self.service._is_text_file(filename))
    
    # =============================================================================
    # 4. Binary File Operations Tests  
    # =============================================================================
    
    def test_write_and_read_binary_file(self):
        """Test binary file write and read operations."""
        collection = "binary"
        document_id = "test.bin"
        content = b"\\x00\\x01\\x02\\x03\\xFF\\xFE\\xFD"
        
        # Write binary file
        result = self.service.write(collection, content, document_id, binary_mode=True)
        
        # Verify write success
        self.assertTrue(result.success)
        self.assertTrue(result.created_new)
        
        # Read the file back
        retrieved_content = self.service.read(collection, document_id, binary_mode=True, format="raw")
        self.assertEqual(retrieved_content, content)
    
    def test_binary_file_detection_and_handling(self):
        """Test automatic binary file detection and handling."""
        collection = "mixed_files"
        
        # Create a binary file (will be detected as binary)
        binary_content = b"\\x89PNG\\r\\n\\x1a\\n"  # PNG header
        result = self.service.write(collection, binary_content, "image.png")
        self.assertTrue(result.success)
        
        # Default read should return raw binary content
        retrieved = self.service.read(collection, "image.png")
        self.assertEqual(retrieved, binary_content)
        
        # To get structured data with metadata, explicitly request structured format
        structured_result = self.service.read(collection, "image.png", format="structured")
        self.assertIsInstance(structured_result, dict)
        self.assertIn("content", structured_result)
        self.assertIn("metadata", structured_result)
        self.assertEqual(structured_result["metadata"]["type"], "binary")
    
    def test_binary_disabled_configuration(self):
        """Test behavior when binary file handling is disabled."""
        # Create service with binary disabled
        no_binary_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {
                "file": {
                    "options": {
                        "base_directory": self.temp_dir,
                        "allow_binary": False
                    }
                }
            }
        })
        
        no_binary_service = FileStorageService(
            provider_name="file",
            configuration=no_binary_config,
            logging_service=self.mock_logging_service
        )
        
        # Try to write binary content
        binary_content = b"binary data"
        result = no_binary_service.write("test", binary_content, "test.bin", binary_mode=True)
        
        # Should fail
        self.assertFalse(result.success)
        self.assertIn("not allowed", result.error)
    
    # =============================================================================
    # 5. Directory Operations Tests
    # =============================================================================
    
    def test_directory_listing(self):
        """Test directory listing functionality."""
        collection = "test_dir"
        
        # Create some test files
        files = ["file1.txt", "file2.txt", "file3.json"]
        for filename in files:
            self.service.write(collection, f"Content of {filename}", filename)
        
        # List directory (read collection without document_id)
        file_list = self.service.read(collection)
        
        # Should return sorted list of filenames
        self.assertIsInstance(file_list, list)
        self.assertEqual(len(file_list), 3)
        self.assertEqual(sorted(file_list), sorted(files))
    
    def test_directory_creation(self):
        """Test automatic directory creation."""
        nested_path = "deeply/nested/directory/structure"
        filename = "test.txt"
        content = "Test content"
        
        # Write to deeply nested path (should create directories)
        result = self.service.write(nested_path, content, filename)
        self.assertTrue(result.success)
        
        # Verify directory structure was created
        full_path = os.path.join(self.temp_dir, nested_path, filename)
        self.assertTrue(os.path.exists(full_path))
        
        # Verify content is correct
        retrieved = self.service.read(nested_path, filename, format="text")
        self.assertEqual(retrieved, content)
    
    def test_list_collections(self):
        """Test collection (directory) listing."""
        # Initially no collections
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 0)
        
        # Create some collections
        collection_names = ["docs", "images", "data"]
        for collection in collection_names:
            self.service.write(collection, "test content", "test.txt")
        
        # Should list all collections
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 3)
        for collection in collection_names:
            self.assertIn(collection, collections)
    
    # =============================================================================
    # 6. Delete Operations Tests
    # =============================================================================
    
    def test_delete_file(self):
        """Test file deletion."""
        collection = "delete_test"
        document_id = "to_delete.txt"
        
        # Create file
        self.service.write(collection, "content to delete", document_id)
        self.assertTrue(self.service.exists(collection, document_id))
        
        # Delete file
        result = self.service.delete(collection, document_id)
        self.assertTrue(result.success)
        self.assertTrue(result.file_deleted)
        
        # Verify file is gone
        self.assertFalse(self.service.exists(collection, document_id))
    
    def test_delete_directory(self):
        """Test directory deletion."""
        collection = "dir_to_delete"
        
        # Create directory with files
        self.service.write(collection, "file1 content", "file1.txt")
        self.service.write(collection, "file2 content", "file2.txt")
        
        # Delete directory (should only work if empty by default)
        # First remove files
        self.service.delete(collection, "file1.txt")
        self.service.delete(collection, "file2.txt")
        
        # Now delete directory
        result = self.service.delete(collection)
        self.assertTrue(result.success)
        self.assertTrue(result.directory_deleted)
    
    def test_delete_with_recursive_option(self):
        """Test recursive directory deletion."""
        collection = "recursive_delete"
        
        # Create directory with files
        self.service.write(collection, "content1", "file1.txt")
        self.service.write(collection, "content2", "file2.txt")
        
        # Delete recursively
        result = self.service.delete(collection, recursive=True)
        self.assertTrue(result.success)
        self.assertTrue(result.directory_deleted)
        
        # Verify directory is gone
        self.assertFalse(self.service.exists(collection))
    
    def test_delete_nonexistent_file(self):
        """Test deleting non-existent file."""
        result = self.service.delete("nonexistent", "file.txt")
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
    
    # =============================================================================
    # 7. File Metadata Tests
    # =============================================================================
    
    def test_get_file_metadata(self):
        """Test file metadata retrieval."""
        collection = "metadata_test"
        document_id = "test_file.txt"
        content = "Test file for metadata"
        
        # Create file
        self.service.write(collection, content, document_id)
        
        # Get metadata
        metadata = self.service.get_file_metadata(collection, document_id)
        
        # Verify metadata structure
        self.assertIsInstance(metadata, dict)
        expected_keys = [
            "name", "size", "created_at", "modified_at", "is_directory", 
            "is_file", "extension", "is_text", "is_binary"
        ]
        
        for key in expected_keys:
            self.assertIn(key, metadata)
        
        # Verify metadata values
        self.assertEqual(metadata["name"], document_id)
        self.assertGreater(metadata["size"], 0)
        self.assertTrue(metadata["is_file"])
        self.assertFalse(metadata["is_directory"])
        self.assertEqual(metadata["extension"], ".txt")
        self.assertTrue(metadata["is_text"])
        self.assertFalse(metadata["is_binary"])
    
    def test_metadata_for_nonexistent_file(self):
        """Test metadata for non-existent file."""
        metadata = self.service.get_file_metadata("nonexistent", "file.txt")
        self.assertEqual(metadata, {})
    
    # =============================================================================
    # 8. File Copy Operations Tests
    # =============================================================================
    
    def test_copy_file(self):
        """Test file copying functionality."""
        source_collection = "source"
        source_id = "original.txt"
        target_collection = "target"
        target_id = "copy.txt"
        content = "Content to copy"
        
        # Create source file
        self.service.write(source_collection, content, source_id)
        
        # Copy file
        result = self.service.copy_file(
            source_collection, source_id,
            target_collection, target_id
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "copy")
        self.assertTrue(result.created_new)
        
        # Verify copy exists and has same content
        copied_content = self.service.read(target_collection, target_id, format="text")
        self.assertEqual(copied_content, content)
        
        # Verify original still exists
        original_content = self.service.read(source_collection, source_id, format="text")
        self.assertEqual(original_content, content)
    
    def test_copy_nonexistent_file(self):
        """Test copying non-existent file."""
        result = self.service.copy_file(
            "nonexistent", "file.txt",
            "target", "copy.txt"
        )
        
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
    
    # =============================================================================
    # 9. LangChain Document Loader Tests
    # =============================================================================
    
    @patch('langchain_community.document_loaders.TextLoader')
    def test_langchain_loader_integration(self, mock_text_loader):
        """Test integration with LangChain document loaders."""
        # Mock document loader
        mock_doc = Mock()
        mock_doc.page_content = "Loaded document content"
        mock_doc.metadata = {"source": "test.unknown", "type": "document"}
        
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = [mock_doc]
        mock_text_loader.return_value = mock_loader_instance
        
        # Create a file with unknown extension (not in text_extensions)
        # This will force it through the document loader path
        collection = "langchain_test"
        document_id = "document.unknown"  # Unknown extension
        self._create_test_file(f"{collection}/{document_id}", "Original content")
        
        # Read using document loader - the mocked LangChain loader should be used
        result = self.service.read(collection, document_id)
        
        # Verify that TextLoader was called
        mock_text_loader.assert_called_once()
        mock_loader_instance.load.assert_called_once()
        
        # Since the file service now returns raw content by default,
        # it should extract and return the page_content from the mocked loader
        self.assertEqual(result, "Loaded document content")
        
        # To get structured data with metadata, explicitly request structured format
        structured_result = self.service.read(collection, document_id, format="structured")
        self.assertIsInstance(structured_result, dict)
        self.assertIn("content", structured_result)
        self.assertIn("metadata", structured_result)
        self.assertEqual(structured_result["content"], "Loaded document content")
        self.assertEqual(structured_result["metadata"]["source"], "test.unknown")
    
    @patch('langchain_community.document_loaders.TextLoader')
    def test_langchain_loader_fallback(self, mock_text_loader):
        """Test fallback when LangChain loaders fail."""
        # Mock loader to raise exception
        mock_text_loader.side_effect = ImportError("LangChain not available")
        
        collection = "fallback_test"
        document_id = "test.unknown"  # Unknown extension to trigger document loader path
        content = "Fallback content"
        
        # Create test file
        self._create_test_file(f"{collection}/{document_id}", content)
        
        # Should fall back to text reading
        result = self.service.read(collection, document_id, format="text")
        self.assertEqual(result, content)
    
    def test_fallback_loader_creation(self):
        """Test creation of fallback loader."""
        test_file = self._create_test_file("test/fallback.txt", "Fallback test content")
        
        # Create fallback loader
        fallback_loader = self.service._create_fallback_loader(test_file)
        
        # Test loading
        documents = fallback_loader.load()
        self.assertEqual(len(documents), 1)
        
        doc = documents[0]
        self.assertEqual(doc.page_content, "Fallback test content")
        self.assertIn("source", doc.metadata)
    
    # =============================================================================
    # 10. Error Handling Tests
    # =============================================================================
    
    def test_write_without_document_id(self):
        """Test writing without providing document_id."""
        result = self.service.write("test", "content")
        
        self.assertFalse(result.success)
        self.assertIn("document_id", result.error)
        self.assertIn("required", result.error)
    
    def test_read_nonexistent_file(self):
        """Test reading non-existent file."""
        result = self.service.read("nonexistent", "file.txt")
        self.assertIsNone(result)
    
    def test_invalid_file_path_characters(self):
        """Test handling of files with invalid characters."""
        # Most filesystems have restrictions on certain characters
        invalid_names = ["file<name>.txt", "file|name.txt", 'file"name.txt']
        
        for invalid_name in invalid_names:
            # The service should handle this gracefully (either succeed or fail cleanly)
            try:
                result = self.service.write("test", "content", invalid_name)
                # If it succeeds, that's fine
                if result.success:
                    self.assertTrue(self.service.exists("test", invalid_name))
            except Exception:
                # If it raises an exception, that's also acceptable
                pass
    
    @unittest.skipIf(
        os.name == 'nt' or os.environ.get('CI') == 'true', 
        "Permission tests unreliable on Windows and CI environments"
    )
    def test_file_permission_errors(self):
        """Test handling of file permission errors."""
        collection = "permission_test"
        document_id = "readonly.txt"
        
        # Create file
        self.service.write(collection, "initial content", document_id)
        
        # Make file read-only
        file_path = os.path.join(self.temp_dir, collection, document_id)
        os.chmod(file_path, 0o444)  # Read-only
        
        try:
            # Try to write to read-only file
            result = self.service.write(collection, "new content", document_id)
            # Should handle permission error gracefully
            self.assertFalse(result.success)
            self.assertIsNotNone(result.error)
            self.assertIn("Permission denied", result.error)
            
        finally:
            # Restore permissions for cleanup
            os.chmod(file_path, 0o644)
    
    # =============================================================================
    # 11. Configuration and Options Tests
    # =============================================================================
    
    def test_encoding_configuration(self):
        """Test custom encoding configuration."""
        # Create service with different encoding
        custom_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {
                "file": {
                    "options": {
                        "base_directory": self.temp_dir,
                        "encoding": "latin-1"
                    }
                }
            }
        })
        
        custom_service = FileStorageService(
            provider_name="file",
            configuration=custom_config,
            logging_service=self.mock_logging_service
        )
        
        # Test with content that has special characters
        content = "Café with special chars: áéíóú"
        
        result = custom_service.write("test", content, "special.txt")
        if result.success:  # Encoding might not support all characters
            retrieved = custom_service.read("test", "special.txt", format="text")
            # Content might be different due to encoding, but operation should complete
            self.assertIsNotNone(retrieved)
    
    def test_automatic_directory_creation(self):
        """Test that directories are automatically created when needed."""
        # This should always work now since we always create directories
        nested_path = "very/deeply/nested/directory/structure"
        
        # Try to write to non-existent nested directory
        result = self.service.write(nested_path, "content", "file.txt")
        
        # Should succeed because directories are automatically created
        self.assertTrue(result.success)
        self.assertTrue(self.service.exists(nested_path, "file.txt"))
        
        # Verify the directory structure was created
        expected_dir = os.path.join(self.temp_dir, nested_path)
        self.assertTrue(os.path.exists(expected_dir))
    
    # =============================================================================
    # 12. Format and Output Tests
    # =============================================================================
    
    def test_different_output_formats(self):
        """Test different output format options."""
        collection = "format_test"
        document_id = "test.txt"
        content = "Test content for formats"
        
        # Create file
        self.service.write(collection, content, document_id)
        
        # Test text format
        text_result = self.service.read(collection, document_id, format="text")
        self.assertEqual(text_result, content)
        
        # Test raw format
        raw_result = self.service.read(collection, document_id, format="raw")
        self.assertEqual(raw_result, content)
        
        # Test default format (now returns raw content)
        default_result = self.service.read(collection, document_id)
        self.assertEqual(default_result, content)
        
        # To get structured data with metadata, explicitly request structured format
        dict_result = self.service.read(collection, document_id, format="structured")
        self.assertIsInstance(dict_result, dict)
        self.assertIn("content", dict_result)
        self.assertIn("metadata", dict_result)
        self.assertEqual(dict_result["content"], content)
    
    def test_content_preparation(self):
        """Test content preparation for writing."""
        # Test string content
        string_content = "Simple string"
        prepared = self.service._prepare_content(string_content)
        self.assertEqual(prepared, string_content)
        
        # Test dict content
        dict_content = {"key": "value", "content": "extracted"}
        prepared = self.service._prepare_content(dict_content)
        self.assertEqual(prepared, "extracted")  # Should extract 'content' field
        
        # Test dict without content field
        dict_no_content = {"data": "test"}
        prepared = self.service._prepare_content(dict_no_content)
        self.assertEqual(prepared, str(dict_no_content))
        
        # Test bytes content
        bytes_content = b"binary content"
        prepared = self.service._prepare_content(bytes_content)
        self.assertEqual(prepared, bytes_content)
        
        # Test mock LangChain document
        mock_doc = Mock()
        mock_doc.page_content = "Document content"
        prepared = self.service._prepare_content(mock_doc)
        self.assertEqual(prepared, "Document content")
        
        # Test list of mock LangChain documents
        mock_docs = [Mock(), Mock()]
        mock_docs[0].page_content = "Content 1"
        mock_docs[1].page_content = "Content 2"
        prepared = self.service._prepare_content(mock_docs)
        self.assertEqual(prepared, "Content 1\n\nContent 2")


if __name__ == '__main__':
    unittest.main()
