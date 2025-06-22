"""
Unit tests for JSONStorageService.

These tests validate the JSONStorageService implementation including:
- JSON storage and retrieval operations
- Schema validation and data integrity
- Nested object handling
- Error handling for malformed JSON
- Path-based operations
- Query filtering
- Document management
"""

import unittest
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from typing import Dict, Any, List

from agentmap.services.storage.json_service import JSONStorageService
from agentmap.services.storage.types import WriteMode, StorageResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestJSONStorageService(unittest.TestCase):
    """Unit tests for JSONStorageService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "storage": {
                "json": {
                    "options": {
                        "base_directory": self.temp_dir,
                        "encoding": "utf-8",
                        "indent": 2
                    }
                }
            }
        })
        
        # Create JSONStorageService with mocked dependencies
        self.service = JSONStorageService(
            provider_name="json",
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
    
    def _create_test_json_file(self, relative_path: str, data: Dict[str, Any]) -> str:
        """Helper to create a test JSON file."""
        full_path = os.path.join(self.temp_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return full_path
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.provider_name, "json")
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
        expected_keys = ["base_directory", "encoding", "indent"]
        
        for key in expected_keys:
            self.assertIn(key, client)
        
        # Verify configuration values
        self.assertEqual(client["base_directory"], self.temp_dir)
        self.assertEqual(client["encoding"], "utf-8")
        self.assertEqual(client["indent"], 2)
    
    def test_service_health_check(self):
        """Test that health check works correctly."""
        # Should be healthy by default
        self.assertTrue(self.service.health_check())
        
        # Health check should test JSON operations
        result = self.service._perform_health_check()
        self.assertTrue(result)
    
    def test_is_healthy_backward_compatibility(self):
        """Test backward compatibility is_healthy() method."""
        # is_healthy() should delegate to health_check()
        self.assertTrue(self.service.is_healthy())
    
    def test_health_check_with_inaccessible_directory(self):
        """Test health check fails with inaccessible directory."""
        # Create service with directory that cannot be created
        bad_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {
                "json": {
                    "options": {
                        "base_directory": "/protected/directory"
                    }
                }
            }
        })
        
        # Mock os.makedirs to raise PermissionError in the specific module
        with patch('agentmap.services.storage.json_service.os.makedirs', side_effect=PermissionError("Permission denied")):
            bad_service = JSONStorageService(
                provider_name="json",
                configuration=bad_config,
                logging_service=self.mock_logging_service
            )
            
            # The PermissionError is raised when client is accessed (lazy initialization)
            from agentmap.services.storage.types import StorageServiceConfigurationError
            with self.assertRaises(StorageServiceConfigurationError):
                _ = bad_service.client  # This triggers client initialization
        
        # Now test with a service where directory creation succeeds but access fails
        with patch('agentmap.services.storage.json_service.os.access', return_value=False):  # Simulate no write access
            accessible_config = MockServiceFactory.create_mock_app_config_service({
                "storage": {
                    "json": {
                        "options": {
                            "base_directory": self.temp_dir  # Use existing directory
                        }
                    }
                }
            })
            
            accessible_service = JSONStorageService(
                provider_name="json",
                configuration=accessible_config,
                logging_service=self.mock_logging_service
            )
            
            # Health check should fail due to no write access
            self.assertFalse(accessible_service.health_check())
    
    # =============================================================================
    # 2. File Path Management Tests
    # =============================================================================
    
    def test_get_file_path(self):
        """Test file path generation."""
        # Test with relative path
        path = self.service._get_file_path("test_collection")
        expected = os.path.join(self.temp_dir, "test_collection.json")
        self.assertEqual(path, expected)
        
        # Test with .json extension already present
        path = self.service._get_file_path("test_collection.json")
        expected = os.path.join(self.temp_dir, "test_collection.json")
        self.assertEqual(path, expected)
        
        # Test with absolute path
        abs_path = "/tmp/test.json"
        path = self.service._get_file_path(abs_path)
        self.assertEqual(path, abs_path)
    
    def test_ensure_directory_exists(self):
        """Test directory creation."""
        nested_file = os.path.join(self.temp_dir, "nested", "deep", "file.json")
        
        # Directory shouldn't exist initially
        self.assertFalse(os.path.exists(os.path.dirname(nested_file)))
        
        # Should create directory structure
        self.service._ensure_directory_exists(nested_file)
        self.assertTrue(os.path.exists(os.path.dirname(nested_file)))
    
    # =============================================================================
    # 3. Basic JSON File Operations Tests
    # =============================================================================
    
    def test_read_json_file(self):
        """Test JSON file reading."""
        # Create test JSON file
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        file_path = self._create_test_json_file("test.json", test_data)
        
        # Read the file
        result = self.service._read_json_file(file_path)
        self.assertEqual(result, test_data)
    
    def test_write_json_file(self):
        """Test JSON file writing."""
        test_data = {"name": "John", "age": 30, "hobbies": ["reading", "coding"]}
        file_path = os.path.join(self.temp_dir, "write_test.json")
        
        # Write the file
        self.service._write_json_file(file_path, test_data)
        
        # Verify file was created and contains correct data
        self.assertTrue(os.path.exists(file_path))
        
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        self.assertEqual(loaded_data, test_data)
    
    def test_read_nonexistent_json_file(self):
        """Test reading non-existent JSON file."""
        nonexistent_path = os.path.join(self.temp_dir, "nonexistent.json")
        
        with self.assertRaises(FileNotFoundError):
            self.service._read_json_file(nonexistent_path)
    
    def test_read_malformed_json_file(self):
        """Test reading malformed JSON file."""
        # Create malformed JSON file
        malformed_path = os.path.join(self.temp_dir, "malformed.json")
        with open(malformed_path, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json, syntax}')
        
        with self.assertRaises(ValueError) as context:
            self.service._read_json_file(malformed_path)
        
        self.assertIn("Invalid JSON", str(context.exception))
    
    def test_write_non_serializable_data(self):
        """Test writing non-serializable data."""
        # Data with non-serializable object
        non_serializable_data = {"function": lambda x: x}
        file_path = os.path.join(self.temp_dir, "non_serializable.json")
        
        with self.assertRaises(ValueError) as context:
            self.service._write_json_file(file_path, non_serializable_data)
        
        self.assertIn("Cannot serialize to JSON", str(context.exception))
    
    # =============================================================================
    # 4. Path-based Operations Tests
    # =============================================================================
    
    def test_apply_path_operations(self):
        """Test path-based data extraction."""
        test_data = {
            "user": {
                "profile": {
                    "name": "John Doe",
                    "age": 30,
                    "addresses": [
                        {"type": "home", "city": "New York"},
                        {"type": "work", "city": "Boston"}
                    ]
                }
            },
            "settings": {"theme": "dark"}
        }
        
        # Test simple path
        result = self.service._apply_path(test_data, "settings.theme")
        self.assertEqual(result, "dark")
        
        # Test nested path
        result = self.service._apply_path(test_data, "user.profile.name")
        self.assertEqual(result, "John Doe")
        
        # Test array access
        result = self.service._apply_path(test_data, "user.profile.addresses.0.city")
        self.assertEqual(result, "New York")
        
        # Test empty path
        result = self.service._apply_path(test_data, "")
        self.assertEqual(result, test_data)
        
        # Test non-existent path
        result = self.service._apply_path(test_data, "nonexistent.path")
        self.assertIsNone(result)
        
        # Test invalid array index
        result = self.service._apply_path(test_data, "user.profile.addresses.10.city")
        self.assertIsNone(result)
    
    def test_update_path_operations(self):
        """Test path-based data updates."""
        initial_data = {
            "user": {"name": "John", "age": 30},
            "settings": {"theme": "light"}
        }
        
        # Test simple path update
        result = self.service._update_path(initial_data, "settings.theme", "dark")
        self.assertEqual(result["settings"]["theme"], "dark")
        self.assertEqual(result["user"]["name"], "John")  # Unchanged
        
        # Test creating new nested path
        result = self.service._update_path(initial_data, "user.profile.bio", "Developer")
        self.assertEqual(result["user"]["profile"]["bio"], "Developer")
        self.assertEqual(result["user"]["name"], "John")  # Existing data preserved
        
        # Test array path update
        array_data = {"items": ["a", "b", "c"]}
        result = self.service._update_path(array_data, "items.1", "updated")
        self.assertEqual(result["items"], ["a", "updated", "c"])
        
        # Test creating array with index
        result = self.service._update_path({}, "list.0", "first")
        self.assertEqual(result["list"], ["first"])
        
        # Test empty path (replace entire data)
        result = self.service._update_path(initial_data, "", {"completely": "new"})
        self.assertEqual(result, {"completely": "new"})
    
    def test_delete_path_operations(self):
        """Test path-based data deletion."""
        test_data = {
            "user": {
                "name": "John",
                "age": 30,
                "hobbies": ["reading", "coding", "gaming"]
            },
            "settings": {"theme": "dark", "language": "en"}
        }
        
        # Test simple key deletion
        result = self.service._delete_path(test_data, "settings.language")
        self.assertNotIn("language", result["settings"])
        self.assertIn("theme", result["settings"])  # Other keys preserved
        
        # Test array element deletion
        result = self.service._delete_path(test_data, "user.hobbies.1")
        expected_hobbies = ["reading", "gaming"]  # "coding" removed
        self.assertEqual(result["user"]["hobbies"], expected_hobbies)
        
        # Test deleting entire nested object
        result = self.service._delete_path(test_data, "user")
        self.assertNotIn("user", result)
        self.assertIn("settings", result)  # Other data preserved
        
        # Test non-existent path (should not error)
        result = self.service._delete_path(test_data, "nonexistent.path")
        self.assertEqual(result, test_data)  # Unchanged
    
    # =============================================================================
    # 5. Document Management Tests
    # =============================================================================
    
    def test_find_document_by_id(self):
        """Test document finding by ID with direct storage structure."""
        # Test dict structure with direct storage (document ID as key)
        dict_data = {
            "doc1": {"name": "Document 1"},
            "doc2": {"name": "Document 2"}
        }
        
        result = self.service._find_document_by_id(dict_data, "doc1")
        self.assertEqual(result, {"name": "Document 1"})
        
        # Test not found
        result = self.service._find_document_by_id(dict_data, "nonexistent")
        self.assertIsNone(result)
        
        # Test with empty data
        result = self.service._find_document_by_id({}, "doc1")
        self.assertIsNone(result)
        
        # Test with list data - should return None (no ID lookup in lists)
        list_data = [
            {"id": "doc1", "name": "Document 1"},
            {"id": "doc2", "name": "Document 2"}
        ]
        
        result = self.service._find_document_by_id(list_data, "doc1")
        self.assertIsNone(result)  # List structures don't support ID lookup
    
    def test_ensure_id_in_document(self):
        """Test ensuring document data is properly formatted for direct storage."""
        # Test dict document - should be stored directly (no wrapping)
        doc_data = {"name": "John", "age": 30}
        result = self.service._ensure_id_in_document(doc_data, "user123")
        
        # Should return data directly without wrapping
        self.assertEqual(result, doc_data)
        self.assertEqual(result["name"], "John")
        self.assertEqual(result["age"], 30)
        self.assertNotIn("value", result)  # No wrapping in direct storage
        
        # Test non-dict document - stored directly as-is
        simple_data = "simple string"
        result = self.service._ensure_id_in_document(simple_data, "item123")
        
        self.assertEqual(result, "simple string")
        # Non-dict data stored directly without any modification
    
    def test_update_document_in_structure(self):
        """Test updating documents in different structures with direct storage."""
        # Test updating in dict structure - documents stored directly
        dict_data = {
            "doc1": {"name": "Document 1", "version": 1},
            "doc2": {"name": "Document 2", "version": 1}
        }
        
        new_doc_data = {"name": "Updated Document 1", "version": 2}
        result, created = self.service._update_document_in_structure(
            dict_data, new_doc_data, "doc1"
        )
        
        self.assertFalse(created)  # Document existed
        # With direct storage, the new data is merged directly
        self.assertEqual(result["doc1"]["name"], "Updated Document 1")
        self.assertEqual(result["doc1"]["version"], 2)
        
        # Test adding new document to dict
        new_doc_data = {"name": "New Document", "version": 1}
        result, created = self.service._update_document_in_structure(
            dict_data, new_doc_data, "doc3"
        )
        
        self.assertTrue(created)  # Document was created
        self.assertIn("doc3", result)
        self.assertEqual(result["doc3"], new_doc_data)
        
        # Test updating in list structure - direct storage doesn't support ID-based updates in lists
        list_data = [
            {"id": "doc1", "name": "Document 1"},
            {"id": "doc2", "name": "Document 2"}
        ]
        
        new_doc_data = {"name": "Updated Document 1"}
        result, created = self.service._update_document_in_structure(
            list_data, new_doc_data, "doc1"
        )
        
        # Direct storage doesn't support ID-based updates in lists
        # So the document is not found and a new one is created instead
        self.assertTrue(created)  # Document was created (not updated)
        # The new document is appended to the list
        self.assertEqual(len(result), 3)  # Original 2 + 1 new document
        self.assertEqual(result[2], new_doc_data)  # New document at end
    
    def test_merge_documents(self):
        """Test document merging functionality."""
        doc1 = {
            "name": "John",
            "age": 30,
            "address": {"city": "New York", "zip": "10001"},
            "hobbies": ["reading"]
        }
        
        doc2 = {
            "age": 31,
            "address": {"zip": "10002", "country": "USA"},
            "hobbies": ["reading", "coding"],
            "profession": "Developer"
        }
        
        result = self.service._merge_documents(doc1, doc2)
        
        # Check merged values
        self.assertEqual(result["name"], "John")  # From doc1
        self.assertEqual(result["age"], 31)  # From doc2 (overwrite)
        self.assertEqual(result["profession"], "Developer")  # New from doc2
        
        # Check nested merge
        self.assertEqual(result["address"]["city"], "New York")  # From doc1
        self.assertEqual(result["address"]["zip"], "10002")  # From doc2 (overwrite)
        self.assertEqual(result["address"]["country"], "USA")  # New from doc2
        
        # Check non-dict values are overwritten
        self.assertEqual(result["hobbies"], ["reading", "coding"])  # From doc2
    
    # =============================================================================
    # 6. Storage Operations Tests
    # =============================================================================
    
    def test_read_entire_file(self):
        """Test reading entire JSON file."""
        collection = "test_collection"
        test_data = {
            "doc1": {"name": "Document 1", "type": "article"},
            "doc2": {"name": "Document 2", "type": "blog"}
        }
        
        # Create test file
        file_path = self.service._get_file_path(collection)
        self.service._write_json_file(file_path, test_data)
        
        # Read entire file
        result = self.service.read(collection)
        self.assertEqual(result, test_data)
    
    def test_read_specific_document(self):
        """Test reading specific document by ID with direct storage."""
        collection = "documents"
        # Use direct storage structure - document ID as key, data stored directly
        test_data = {
            "doc1": {"id": "doc1", "title": "First Document", "content": "Content 1"},
            "doc2": {"id": "doc2", "title": "Second Document", "content": "Content 2"}
        }
        
        # Create test file
        file_path = self.service._get_file_path(collection)
        self.service._write_json_file(file_path, test_data)
        
        # Read specific document - should return data directly
        result = self.service.read(collection, "doc1")
        expected = {"id": "doc1", "title": "First Document", "content": "Content 1"}
        self.assertEqual(result, expected)
        
        # Test non-existent document
        result = self.service.read(collection, "nonexistent")
        self.assertIsNone(result)
    
    def test_read_with_path(self):
        """Test reading with path parameter."""
        collection = "users"
        test_data = {
            "user1": {
                "profile": {"name": "John", "age": 30},
                "settings": {"theme": "dark"}
            }
        }
        
        # Create test file
        file_path = self.service._get_file_path(collection)
        self.service._write_json_file(file_path, test_data)
        
        # Read with path
        name = self.service.read(collection, "user1", path="profile.name")
        self.assertEqual(name, "John")
        
        # Read nested path
        theme = self.service.read(collection, "user1", path="settings.theme")
        self.assertEqual(theme, "dark")
    
    def test_read_nonexistent_file(self):
        """Test reading non-existent file."""
        result = self.service.read("nonexistent_collection")
        self.assertIsNone(result)
    
    def test_write_new_file(self):
        """Test writing to new file."""
        collection = "new_collection"
        document_id = "doc1"
        data = {"title": "New Document", "content": "Test content"}
        
        # Write document
        result = self.service.write(collection, data, document_id)
        
        # Verify result
        self.assertIsInstance(result, StorageResult)
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "write")
        self.assertEqual(result.collection, collection)
        self.assertEqual(result.document_id, document_id)
        
        # Verify file was created
        file_path = self.service._get_file_path(collection)
        self.assertTrue(os.path.exists(file_path))
        
        # Verify content - user data should be preserved with direct storage
        retrieved = self.service.read(collection, document_id)
        expected = {"title": "New Document", "content": "Test content"}
        self.assertEqual(retrieved, expected)  # Should get data exactly as stored
    
    def test_write_modes(self):
        """Test different write modes."""
        collection = "write_modes"
        document_id = "test_doc"
        
        # Test WRITE mode (create new)
        initial_data = {"version": 1, "content": "initial"}
        result = self.service.write(collection, initial_data, document_id, WriteMode.WRITE)
        self.assertTrue(result.success)
        
        # Test UPDATE mode
        update_data = {"version": 2, "status": "updated"}
        result = self.service.write(collection, update_data, document_id, WriteMode.UPDATE)
        self.assertTrue(result.success)
        
        # Verify merge happened
        retrieved = self.service.read(collection, document_id)
        self.assertEqual(retrieved["version"], 2)
        self.assertEqual(retrieved["status"], "updated")
        self.assertEqual(retrieved["content"], "initial")  # Should be preserved
    
    def test_write_with_path(self):
        """Test writing with path parameter."""
        collection = "path_writes"
        document_id = "test_doc"
        
        # Create initial document
        initial_data = {"user": {"name": "John"}, "metadata": {"created": "2023-01-01"}}
        self.service.write(collection, initial_data, document_id)
        
        # Update using path
        result = self.service.write(
            collection, "Jane", document_id, 
            WriteMode.UPDATE, path="user.name"
        )
        self.assertTrue(result.success)
        
        # Verify path update
        retrieved = self.service.read(collection, document_id)
        self.assertEqual(retrieved["user"]["name"], "Jane")
        self.assertEqual(retrieved["metadata"]["created"], "2023-01-01")  # Unchanged
        
        # Create new nested path
        result = self.service.write(
            collection, 30, document_id,
            WriteMode.UPDATE, path="user.profile.age"
        )
        self.assertTrue(result.success)
        
        retrieved = self.service.read(collection, document_id)
        self.assertEqual(retrieved["user"]["profile"]["age"], 30)
    
    def test_delete_document(self):
        """Test document deletion."""
        collection = "delete_test"
        
        # Create test documents
        docs = {
            "doc1": {"title": "Document 1"},
            "doc2": {"title": "Document 2"}
        }
        
        file_path = self.service._get_file_path(collection)
        self.service._write_json_file(file_path, docs)
        
        # Delete specific document
        result = self.service.delete(collection, "doc1")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "delete")
        self.assertEqual(result.document_id, "doc1")
        
        # Verify document is gone
        retrieved = self.service.read(collection, "doc1")
        self.assertIsNone(retrieved)
        
        # Verify other document still exists
        retrieved = self.service.read(collection, "doc2")
        self.assertIsNotNone(retrieved)
    
    def test_delete_entire_file(self):
        """Test deleting entire file."""
        collection = "delete_file_test"
        
        # Create test file
        self.service.write(collection, {"test": "data"}, "doc1")
        file_path = self.service._get_file_path(collection)
        self.assertTrue(os.path.exists(file_path))
        
        # Delete entire file
        result = self.service.delete(collection)
        self.assertTrue(result.success)
        self.assertTrue(result.collection_deleted)
        
        # Verify file is gone
        self.assertFalse(os.path.exists(file_path))
    
    def test_delete_with_path(self):
        """Test deletion with path parameter using direct storage."""
        collection = "delete_path_test"
        document_id = "test_doc"
        
        # Create document with nested data
        data = {
            "user": {
                "name": "John",
                "profile": {"age": 30, "city": "NYC"}
            },
            "settings": {"theme": "dark", "lang": "en"}
        }
        
        self.service.write(collection, data, document_id)
        
        # Delete nested field
        result = self.service.delete(collection, document_id, path="user.profile.age")
        self.assertTrue(result.success)
        
        # Verify field was deleted - read returns data directly
        retrieved = self.service.read(collection, document_id)
        self.assertNotIn("age", retrieved["user"]["profile"])
        self.assertIn("city", retrieved["user"]["profile"])  # Other fields preserved
        
        # Delete entire nested object
        result = self.service.delete(collection, document_id, path="settings")
        self.assertTrue(result.success)
        
        retrieved = self.service.read(collection, document_id)
        self.assertNotIn("settings", retrieved)
        self.assertIn("user", retrieved)  # Other data preserved
    
    # =============================================================================
    # 7. Query and Filtering Tests
    # =============================================================================
    
    def test_apply_query_filter(self):
        """Test query filtering functionality."""
        test_data = [
            {"id": "1", "category": "A", "status": "active", "score": 100},
            {"id": "2", "category": "B", "status": "active", "score": 85},
            {"id": "3", "category": "A", "status": "inactive", "score": 90},
            {"id": "4", "category": "B", "status": "active", "score": 95}
        ]
        
        # Test simple filter
        query = {"category": "A"}
        result = self.service._apply_query_filter(test_data, query)
        
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["is_collection"])
        filtered_data = result["data"]
        
        for item in filtered_data:
            self.assertEqual(item["category"], "A")
        
        # Test multiple field filter
        query = {"category": "B", "status": "active"}
        result = self.service._apply_query_filter(test_data, query)
        
        self.assertEqual(result["count"], 2)
        filtered_data = result["data"]
        
        for item in filtered_data:
            self.assertEqual(item["category"], "B")
            self.assertEqual(item["status"], "active")
        
        # Test with limit
        query = {"status": "active", "limit": 2}
        result = self.service._apply_query_filter(test_data, query)
        
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["data"]), 2)
        
        # Test with sorting
        query = {"status": "active", "sort": "score", "order": "desc"}
        result = self.service._apply_query_filter(test_data, query)
        
        scores = [item["score"] for item in result["data"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        
        # Test with offset
        query = {"status": "active", "offset": 1, "limit": 1}
        result = self.service._apply_query_filter(test_data, query)
        
        self.assertEqual(result["count"], 1)
    
    def test_read_with_query(self):
        """Test reading with query parameters."""
        collection = "query_test"
        
        # Create test data
        test_data = [
            {"id": "1", "type": "article", "author": "John", "published": True},
            {"id": "2", "type": "blog", "author": "Jane", "published": True},
            {"id": "3", "type": "article", "author": "John", "published": False},
            {"id": "4", "type": "blog", "author": "Bob", "published": True}
        ]
        
        file_path = self.service._get_file_path(collection)
        self.service._write_json_file(file_path, test_data)
        
        # Query by type
        result = self.service.read(collection, query={"type": "article"})
        self.assertEqual(len(result), 2)
        
        # Query by multiple fields
        result = self.service.read(collection, query={"author": "John", "published": True})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "1")
        
        # Query with sorting
        result = self.service.read(collection, query={"published": True, "sort": "author"})
        authors = [item["author"] for item in result]
        self.assertEqual(authors, sorted(authors))
    
    # =============================================================================
    # 8. Utility Operations Tests
    # =============================================================================
    
    def test_exists_operations(self):
        """Test exists functionality."""
        collection = "exists_test"
        document_id = "test_doc"
        
        # File/document doesn't exist initially
        self.assertFalse(self.service.exists(collection))
        self.assertFalse(self.service.exists(collection, document_id))
        
        # Create document
        self.service.write(collection, {"data": "test"}, document_id)
        
        # Now both should exist
        self.assertTrue(self.service.exists(collection))
        self.assertTrue(self.service.exists(collection, document_id))
        
        # Other document still doesn't exist
        self.assertFalse(self.service.exists(collection, "other_doc"))
    
    def test_count_operations(self):
        """Test count functionality."""
        collection = "count_test"
        
        # Empty collection
        self.assertEqual(self.service.count(collection), 0)
        
        # Create test documents
        docs = [
            {"id": "1", "type": "A"},
            {"id": "2", "type": "B"},
            {"id": "3", "type": "A"},
            {"id": "4", "type": "B"},
            {"id": "5", "type": "A"}
        ]
        
        file_path = self.service._get_file_path(collection)
        self.service._write_json_file(file_path, docs)
        
        # Count all documents
        self.assertEqual(self.service.count(collection), 5)
        
        # Count with query
        self.assertEqual(self.service.count(collection, {"type": "A"}), 3)
        self.assertEqual(self.service.count(collection, {"type": "B"}), 2)
    
    def test_list_collections(self):
        """Test collection listing."""
        # Initially no collections
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 0)
        
        # Create some collections
        collection_names = ["users", "posts", "settings"]
        for collection in collection_names:
            self.service.write(collection, {"test": "data"}, "doc1")
        
        # Should list all collections
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 3)
        
        for collection in collection_names:
            self.assertIn(f"{collection}.json", collections)
    
    # =============================================================================
    # 9. Error Handling Tests
    # =============================================================================
    
    def test_error_handling_context_manager(self):
        """Test context manager error handling."""
        # Test with non-existent file in read mode
        with self.assertRaises(FileNotFoundError):
            with self.service._open_json_file("/nonexistent/file.json", 'r'):
                pass
        
        # Test with directory that can't be created (mock failure)
        with patch('agentmap.services.storage.json_service.os.makedirs', side_effect=PermissionError("Permission denied")):
            with self.assertRaises(PermissionError):
                with self.service._open_json_file("protected/file.json", 'w'):
                    pass
    
    def test_update_nonexistent_document(self):
        """Test updating non-existent document fails."""
        collection = "update_test"
        
        # Try to update document in non-existent file
        result = self.service.write(collection, {"data": "new"}, "doc1", WriteMode.UPDATE)
        
        # Should fail since document doesn't exist
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
        
        # Verify no document was created
        retrieved = self.service.read(collection, "doc1")
        self.assertIsNone(retrieved)
    
    def test_delete_nonexistent_document(self):
        """Test deleting non-existent document."""
        collection = "delete_test"
        
        # Delete from non-existent file
        result = self.service.delete(collection, "doc1")
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
        
        # Create file with documents
        self.service.write(collection, {"data": "test"}, "existing_doc")
        
        # Delete non-existent document
        result = self.service.delete(collection, "nonexistent_doc")
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
    
    def test_invalid_write_mode(self):
        """Test handling of invalid write modes."""
        # Test with invalid mode value
        result = self.service.write("test", {"data": "test"}, "doc1", "invalid_mode")
        self.assertFalse(result.success)
        self.assertIn("Unsupported write mode", result.error)
    
    # =============================================================================
    # 10. Edge Cases and Complex Scenarios Tests
    # =============================================================================
    
    def test_empty_data_structures(self):
        """Test handling of empty data structures."""
        collection = "empty_test"
        
        # Test empty dict - should be stored and retrieved as empty dict
        result = self.service.write(collection, {}, "empty_dict")
        self.assertTrue(result.success)
        
        retrieved = self.service.read(collection, "empty_dict")
        self.assertEqual(retrieved, {})  # Should get empty dict directly
        
        # Test empty list
        file_path = self.service._get_file_path("empty_list")
        self.service._write_json_file(file_path, [])
        
        retrieved = self.service.read("empty_list")
        self.assertEqual(retrieved, [])
    
    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters."""
        collection = "unicode_test"
        document_id = "unicode_doc"
        
        # Data with Unicode characters
        unicode_data = {
            "name": "José María",
            "description": "Testing émojis: 🚀 🎉 ✨",
            "special_chars": "Quotes: \"'\" Backslashes: \\\\ Newlines: \\n\\r"
        }
        
        # Write and read back
        result = self.service.write(collection, unicode_data, document_id)
        self.assertTrue(result.success)
        
        retrieved = self.service.read(collection, document_id)
        self.assertEqual(retrieved["name"], "José María")
        self.assertIn("🚀", retrieved["description"])
        self.assertIn("\\\\", retrieved["special_chars"])
    
    def test_large_nested_structures(self):
        """Test handling of deeply nested data structures."""
        # Create deeply nested structure
        nested_data = {"level": 0}
        current = nested_data
        
        for i in range(1, 10):
            current["nested"] = {"level": i, "data": f"level_{i}"}
            current = current["nested"]
        
        collection = "deep_nested"
        document_id = "deep_doc"
        
        # Write and read back
        result = self.service.write(collection, nested_data, document_id)
        self.assertTrue(result.success)
        
        # Test deep path access
        deep_value = self.service.read(
            collection, document_id, 
            path="nested.nested.nested.nested.data"
        )
        self.assertEqual(deep_value, "level_4")
    
    def test_concurrent_access_simulation(self):
        """Test simulated concurrent access scenarios."""
        collection = "concurrent_test"
        
        # Simulate multiple rapid writes to same file
        for i in range(5):
            result = self.service.write(collection, {"counter": i}, f"doc_{i}")
            self.assertTrue(result.success)
        
        # All documents should exist
        for i in range(5):
            retrieved = self.service.read(collection, f"doc_{i}")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved["counter"], i)
    
    def test_mixed_data_types_in_collections(self):
        """Test collections with mixed data types."""
        collection = "mixed_types"
        
        # Write different types of documents
        documents = [
            ("string_doc", "simple string"),
            ("number_doc", 42),
            ("list_doc", [1, 2, 3, {"nested": "value"}]),
            ("dict_doc", {"complex": {"nested": {"data": "value"}}}),
            ("bool_doc", True),
            ("null_doc", None)
        ]
        
        for doc_id, doc_data in documents:
            result = self.service.write(collection, doc_data, doc_id)
            self.assertTrue(result.success)
        
        # Read all back and verify types - user data should be preserved
        for doc_id, expected_data in documents:
            retrieved = self.service.read(collection, doc_id)
            
            # All data should be returned exactly as originally provided
            self.assertEqual(retrieved, expected_data, f"Data should match for {doc_id}")


if __name__ == '__main__':
    unittest.main()
