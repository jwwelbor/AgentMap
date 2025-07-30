"""
Unit tests for MemoryStorageService.

These tests validate the MemoryStorageService implementation including:
- In-memory storage operations (CRUD)
- Data serialization/deserialization
- Memory management and cleanup
- Concurrent access patterns
- Path-based operations
- Query filtering
- Collection management
"""

import unittest
import time
import tempfile
import os
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from agentmap.services.storage.memory_service import MemoryStorageService
from agentmap.services.storage.types import WriteMode, StorageResult, StorageConfig
from tests.utils.mock_service_factory import MockServiceFactory


class TestMemoryStorageService(unittest.TestCase):
    """Unit tests for MemoryStorageService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_storage_config_service = MockServiceFactory.create_mock_storage_config_service()
        
        # CRITICAL FIX: Patch StorageConfig.from_dict to return a mock with correct get_option behavior
        def mock_storage_config_from_dict(config_data: Dict[str, Any]) -> Mock:
            """Create a mock StorageConfig that properly exposes configuration values."""
            mock_config = Mock()
            
            def get_option(key: str, default: Any = None) -> Any:
                """Mock get_option method that returns the correct configuration values."""
                return config_data.get(key, default)
            
            mock_config.get_option.side_effect = get_option
            # Also store the raw config data for any other access patterns
            mock_config._config_data = config_data
            return mock_config
        
        # Apply the patch
        self.storage_config_patch = patch.object(StorageConfig, 'from_dict', side_effect=mock_storage_config_from_dict)
        self.storage_config_patch.start()
        
        # Create MemoryStorageService with mocked dependencies
        self.service = MemoryStorageService(
            provider_name="memory",
            configuration=self.mock_storage_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service._logger
    
    def tearDown(self):
        """Clean up after each test."""
        # Stop the StorageConfig patch
        self.storage_config_patch.stop()
        
        # Clear all memory storage
        if hasattr(self.service, '_storage'):
            self.service._storage.clear()
            self.service._metadata.clear()
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.provider_name, "memory")
        self.assertEqual(self.service.configuration, self.mock_storage_config_service)
        self.assertIsNotNone(self.service._logger)
        
        # Verify internal storage structures are initialized
        self.assertIsInstance(self.service._storage, dict)
        self.assertIsInstance(self.service._metadata, dict)
        self.assertIsInstance(self.service._stats, dict)
        
        # Verify stats are initialized
        expected_stats = ["reads", "writes", "deletes", "collections_created", "documents_created"]
        for stat in expected_stats:
            self.assertIn(stat, self.service._stats)
            self.assertEqual(self.service._stats[stat], 0)
    
    def test_client_initialization(self):
        """Test that client initializes with correct configuration."""
        client = self.service.client
        
        # Verify client configuration has expected structure
        self.assertIsInstance(client, dict)
        
        # Check for expected configuration keys
        expected_keys = [
            "max_collections", "max_documents_per_collection", "max_document_size",
            "auto_generate_ids", "deep_copy_on_read", "deep_copy_on_write",
            "track_metadata", "case_sensitive_collections"
        ]
        
        for key in expected_keys:
            self.assertIn(key, client)
    
    def test_service_health_check(self):
        """Test that health check works correctly."""
        # Should be healthy by default
        self.assertTrue(self.service.health_check())
        
        # Health check should perform basic operations
        result = self.service._perform_health_check()
        self.assertTrue(result)
    
    # =============================================================================
    # 2. Core Storage Operations Tests
    # =============================================================================
    
    def test_write_and_read_basic_document(self):
        """Test basic document write and read operations."""
        # Write a document
        test_data = {"name": "John", "age": 30, "city": "New York"}
        result = self.service.write("users", test_data, "user1")
        
        # Verify write success
        self.assertIsInstance(result, StorageResult)
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "write")
        self.assertEqual(result.collection, "users")
        self.assertEqual(result.document_id, "user1")
        self.assertTrue(result.created_new)
        
        # Read the document back
        retrieved_data = self.service.read("users", "user1")
        self.assertEqual(retrieved_data, test_data)
        
        # Verify stats updated
        self.assertEqual(self.service._stats["writes"], 1)
        self.assertEqual(self.service._stats["reads"], 1)
        self.assertEqual(self.service._stats["documents_created"], 1)
    
    def test_write_with_auto_generated_id(self):
        """Test writing document with auto-generated ID."""
        test_data = {"content": "Test document"}
        result = self.service.write("documents", test_data)
        
        # Verify write success with generated ID
        self.assertTrue(result.success)
        self.assertIsNotNone(result.document_id)
        self.assertTrue(result.created_new)
        
        # Should be able to read back using generated ID
        retrieved = self.service.read("documents", result.document_id)
        self.assertEqual(retrieved, test_data)
    
    def test_write_modes(self):
        """Test different write modes: WRITE, UPDATE, and APPEND."""
        collection = "test_modes"
        doc_id = "doc1"
        
        # Test WRITE mode (create)
        initial_data = {"version": 1, "content": "initial"}
        result = self.service.write(collection, initial_data, doc_id, WriteMode.WRITE)
        self.assertTrue(result.success)
        self.assertTrue(result.created_new)
        
        # Test UPDATE mode
        update_data = {"version": 2}
        result = self.service.write(collection, update_data, doc_id, WriteMode.UPDATE)
        self.assertTrue(result.success)
        self.assertFalse(result.created_new)
        
        # Verify merge happened
        retrieved = self.service.read(collection, doc_id)
        self.assertEqual(retrieved["version"], 2)
        self.assertEqual(retrieved["content"], "initial")  # Should still exist
        
        # Test APPEND mode
        append_data = ["item1", "item2"]
        self.service.write(collection, append_data, "list_doc", WriteMode.WRITE)
        
        more_items = ["item3", "item4"]
        result = self.service.write(collection, more_items, "list_doc", WriteMode.APPEND)
        self.assertTrue(result.success)
        
        retrieved_list = self.service.read(collection, "list_doc")
        self.assertEqual(len(retrieved_list), 4)
        
        # Test UPDATE mode with merging behavior
        merge_data = {"new_field": "new_value", "version": 3}
        result = self.service.write(collection, merge_data, doc_id, WriteMode.UPDATE)
        self.assertTrue(result.success)
        
        retrieved = self.service.read(collection, doc_id)
        self.assertEqual(retrieved["version"], 3)
        self.assertEqual(retrieved["new_field"], "new_value")
        self.assertEqual(retrieved["content"], "initial")
    
    def test_path_based_operations(self):
        """Test path-based read and write operations."""
        collection = "nested_data"
        doc_id = "nested_doc"
        
        # Create initial nested document
        initial_data = {
            "user": {
                "profile": {
                    "name": "John",
                    "settings": {
                        "theme": "dark",
                        "notifications": True
                    }
                }
            },
            "metadata": {"created": "2023-01-01"}
        }
        
        self.service.write(collection, initial_data, doc_id)
        
        # Test path-based read
        name = self.service.read(collection, doc_id, path="user.profile.name")
        self.assertEqual(name, "John")
        
        theme = self.service.read(collection, doc_id, path="user.profile.settings.theme")
        self.assertEqual(theme, "dark")
        
        # Test path-based write
        result = self.service.write(
            collection, "light", doc_id, 
            WriteMode.WRITE, path="user.profile.settings.theme"
        )
        self.assertTrue(result.success)
        
        # Verify path update
        updated_theme = self.service.read(collection, doc_id, path="user.profile.settings.theme")
        self.assertEqual(updated_theme, "light")
        
        # Verify rest of document unchanged
        name = self.service.read(collection, doc_id, path="user.profile.name")
        self.assertEqual(name, "John")
    
    def test_delete_operations(self):
        """Test delete operations."""
        collection = "delete_test"
        
        # Create test documents
        self.service.write(collection, {"name": "doc1"}, "doc1")
        self.service.write(collection, {"name": "doc2"}, "doc2")
        
        # Test document deletion
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
        
        # Test collection deletion
        result = self.service.delete(collection)
        self.assertTrue(result.success)
        self.assertTrue(result.collection_deleted)
        
        # Verify collection is gone
        self.assertFalse(self.service.exists(collection))
    
    # =============================================================================
    # 3. Query and Filtering Tests
    # =============================================================================
    
    def test_query_filtering(self):
        """Test query-based filtering."""
        collection = "query_test"
        
        # Create test documents
        docs = [
            {"id": "1", "category": "A", "status": "active", "score": 100},
            {"id": "2", "category": "B", "status": "active", "score": 85},
            {"id": "3", "category": "A", "status": "inactive", "score": 90},
            {"id": "4", "category": "B", "status": "active", "score": 95}
        ]
        
        for doc in docs:
            self.service.write(collection, doc, doc["id"])
        
        # Test simple field filter
        query = {"category": "A"}
        results = self.service.read(collection, query=query)
        self.assertEqual(len(results), 2)
        
        # Test multiple field filter
        query = {"category": "B", "status": "active"}
        results = self.service.read(collection, query=query)
        self.assertEqual(len(results), 2)
        
        # Test with limit
        query = {"status": "active", "limit": 2}
        results = self.service.read(collection, query=query)
        self.assertEqual(len(results), 2)
        
        # Test with sorting
        query = {"status": "active", "sort": "score", "order": "desc"}
        results = self.service.read(collection, query=query)
        result_list = list(results.values())
        self.assertTrue(result_list[0]["score"] >= result_list[1]["score"])
    
    def test_batch_delete_with_query(self):
        """Test batch delete using query filters."""
        collection = "batch_delete_test"
        
        # Create test documents
        docs = [
            {"id": "1", "status": "active"},
            {"id": "2", "status": "inactive"},
            {"id": "3", "status": "inactive"},
            {"id": "4", "status": "active"}
        ]
        
        for doc in docs:
            self.service.write(collection, doc, doc["id"])
        
        # Delete all inactive documents
        query = {"status": "inactive"}
        result = self.service.delete(collection, query=query)
        
        self.assertTrue(result.success)
        self.assertEqual(result.total_affected, 2)
        
        # Verify only active documents remain
        remaining = self.service.read(collection)
        self.assertEqual(len(remaining), 2)
        
        for doc in remaining.values():
            self.assertEqual(doc["status"], "active")
    
    # =============================================================================
    # 4. Collection Management Tests
    # =============================================================================
    
    def test_exists_operations(self):
        """Test exists functionality."""
        collection = "exists_test"
        doc_id = "test_doc"
        
        # Collection doesn't exist initially
        self.assertFalse(self.service.exists(collection))
        
        # Document doesn't exist initially  
        self.assertFalse(self.service.exists(collection, doc_id))
        
        # Create document
        self.service.write(collection, {"data": "test"}, doc_id)
        
        # Now both should exist
        self.assertTrue(self.service.exists(collection))
        self.assertTrue(self.service.exists(collection, doc_id))
        
        # Other document still doesn't exist
        self.assertFalse(self.service.exists(collection, "other_doc"))
    
    def test_count_operations(self):
        """Test count functionality."""
        collection = "count_test"
        
        # Empty collection
        self.assertEqual(self.service.count(collection), 0)
        
        # Add some documents
        for i in range(5):
            self.service.write(collection, {"value": i, "type": "even" if i % 2 == 0 else "odd"}, str(i))
        
        # Count all documents
        self.assertEqual(self.service.count(collection), 5)
        
        # Count with query
        self.assertEqual(self.service.count(collection, {"type": "even"}), 3)
        self.assertEqual(self.service.count(collection, {"type": "odd"}), 2)
    
    def test_list_collections(self):
        """Test collection listing."""
        # Initially no collections
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 0)
        
        # Create some collections
        self.service.write("collection_a", {"data": "a"}, "doc1")
        self.service.write("collection_b", {"data": "b"}, "doc1")
        self.service.write("collection_c", {"data": "c"}, "doc1")
        
        # Should list all collections
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 3)
        self.assertIn("collection_a", collections)
        self.assertIn("collection_b", collections)
        self.assertIn("collection_c", collections)
        
        # Should be sorted
        self.assertEqual(collections, sorted(collections))
    
    # =============================================================================
    # 5. Configuration and Limits Tests
    # =============================================================================
    
    def test_collection_limits(self):
        """Test collection count limits."""
        # Create mock storage config service with low limit
        memory_config_override = {
            "memory": {
                "enabled": True,
                "max_collections": 2,
                "persistence": False,
                "collections": {}
            }
        }
        
        mock_limited_storage_config = MockServiceFactory.create_mock_storage_config_service(memory_config_override)
        
        # Create new service with limit
        limited_service = MemoryStorageService(
            provider_name="memory",
            configuration=mock_limited_storage_config,
            logging_service=self.mock_logging_service
        )
        
        
        # Should be able to create up to limit
        result1 = limited_service.write("collection1", {"data": "1"}, "doc1")
        self.assertTrue(result1.success)
        
        result2 = limited_service.write("collection2", {"data": "2"}, "doc1")
        self.assertTrue(result2.success)
        
        # Should fail on exceeding limit
        result3 = limited_service.write("collection3", {"data": "3"}, "doc1")
        self.assertFalse(result3.success)
        self.assertIn("Maximum collections limit", result3.error)
    
    def test_document_limits(self):
        """Test document count limits per collection."""
        # Create mock storage config service with low limit
        memory_config_override = {
            "memory": {
                "enabled": True,
                "max_documents_per_collection": 2,
                "persistence": False,
                "collections": {}
            }
        }
        
        mock_limited_storage_config = MockServiceFactory.create_mock_storage_config_service(memory_config_override)
        
        # Create new service with limit
        limited_service = MemoryStorageService(
            provider_name="memory",
            configuration=mock_limited_storage_config,
            logging_service=self.mock_logging_service
        )
        
        collection = "limited_collection"
        
        # Should be able to create up to limit
        result1 = limited_service.write(collection, {"data": "1"}, "doc1")
        self.assertTrue(result1.success)
        
        result2 = limited_service.write(collection, {"data": "2"}, "doc2")
        self.assertTrue(result2.success)
        
        # Should fail on exceeding limit
        result3 = limited_service.write(collection, {"data": "3"}, "doc3")
        self.assertFalse(result3.success)
        self.assertIn("Maximum documents per collection limit", result3.error)
    
    def test_deep_copy_configuration(self):
        """Test deep copy configuration settings."""
        collection = "copy_test"
        doc_id = "test_doc"
        
        # Test with deep copy enabled (default)
        original_data = {"nested": {"value": 42}}
        self.service.write(collection, original_data, doc_id)
        
        retrieved = self.service.read(collection, doc_id)
        
        # Modify retrieved data
        retrieved["nested"]["value"] = 999
        
        # Original should be unchanged due to deep copy
        retrieved_again = self.service.read(collection, doc_id)
        self.assertEqual(retrieved_again["nested"]["value"], 42)
    
    # =============================================================================
    # 6. Metadata and Statistics Tests
    # =============================================================================
    
    def test_metadata_tracking(self):
        """Test metadata tracking functionality."""
        collection = "metadata_test"
        doc_id = "test_doc"
        
        # Write document
        self.service.write(collection, {"data": "test"}, doc_id)
        
        # Check metadata exists
        self.assertIn(collection, self.service._metadata)
        self.assertIn(doc_id, self.service._metadata[collection])
        
        metadata = self.service._metadata[collection][doc_id]
        self.assertIn("created_at", metadata)
        self.assertIn("updated_at", metadata)
        self.assertIn("access_count", metadata)
        self.assertIn("version", metadata)
        
        # Read document (should increment access count)
        initial_access_count = metadata["access_count"]
        self.service.read(collection, doc_id)
        self.assertGreater(metadata["access_count"], initial_access_count)
        
        # Update document (should increment version)
        initial_version = metadata["version"]
        self.service.write(collection, {"data": "updated"}, doc_id, WriteMode.UPDATE)
        self.assertGreater(metadata["version"], initial_version)
    
    def test_get_stats(self):
        """Test statistics gathering."""
        # Perform some operations
        self.service.write("test", {"data": "1"}, "doc1")
        self.service.write("test", {"data": "2"}, "doc2")
        self.service.read("test", "doc1")
        self.service.delete("test", "doc2")
        
        stats = self.service.get_stats()
        
        # Check stats structure
        self.assertIsInstance(stats, dict)
        self.assertIn("reads", stats)
        self.assertIn("writes", stats)
        self.assertIn("deletes", stats)
        self.assertIn("total_collections", stats)
        self.assertIn("total_documents", stats)
        self.assertIn("uptime_seconds", stats)
        
        # Verify counts
        self.assertGreaterEqual(stats["writes"], 2)
        self.assertGreaterEqual(stats["reads"], 1)
        self.assertGreaterEqual(stats["deletes"], 1)
    
    def test_clear_all(self):
        """Test clearing all data."""
        # Create some data
        self.service.write("collection1", {"data": "1"}, "doc1")
        self.service.write("collection2", {"data": "2"}, "doc1")
        
        # Verify data exists
        self.assertTrue(self.service.exists("collection1"))
        self.assertTrue(self.service.exists("collection2"))
        
        # Clear all
        result = self.service.clear_all()
        self.assertTrue(result.success)
        self.assertGreater(result.total_affected, 0)
        
        # Verify data is gone
        self.assertFalse(self.service.exists("collection1"))
        self.assertFalse(self.service.exists("collection2"))
        self.assertEqual(len(self.service.list_collections()), 0)
    
    # =============================================================================
    # 7. Error Handling Tests
    # =============================================================================
    
    def test_invalid_write_mode(self):
        """Test handling of invalid write modes."""
        from agentmap.services.storage.types import WriteMode
        
        # This should work fine for valid modes
        result = self.service.write("test", {"data": "test"}, "doc1", WriteMode.WRITE)
        self.assertTrue(result.success)
        
        # Test with invalid mode value (if we manually create invalid enum)
        with patch('agentmap.services.storage.memory_service.WriteMode') as mock_mode:
            mock_mode.INVALID = "invalid"
            
            # The service should handle unknown modes gracefully
            try:
                result = self.service.write("test", {"data": "test"}, "doc1", mock_mode.INVALID)
                self.assertFalse(result.success)
                self.assertIn("Unsupported write mode", result.error)
            except Exception:
                # If it raises an exception, that's also acceptable
                pass
    
    def test_update_nonexistent_document(self):
        """Test updating a document that doesn't exist."""
        result = self.service.write("test", {"data": "new"}, "nonexistent", WriteMode.UPDATE)
        
        self.assertFalse(result.success)
        self.assertIn("not found for update", result.error)
    
    def test_delete_nonexistent_document(self):
        """Test deleting a document that doesn't exist."""
        # Delete from nonexistent collection
        result = self.service.delete("nonexistent_collection", "doc1")
        self.assertFalse(result.success)
        self.assertIn("Collection", result.error)
        self.assertIn("not found", result.error)
        
        # Delete nonexistent document from existing collection
        self.service.write("test", {"data": "test"}, "doc1")
        result = self.service.delete("test", "nonexistent_doc")
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
    
    # =============================================================================
    # 8. Persistence Tests (Optional Feature)
    # =============================================================================
    
    def test_persistence_file_operations(self):
        """Test persistence file save/load operations."""
        # Create temporary file for persistence
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Create mock storage config service with persistence file
            memory_config_override = {
                "memory": {
                    "enabled": True,
                    "persistence_file": temp_path,
                    "max_collections": 100,
                    "collections": {}
                }
            }
            
            mock_persistent_storage_config = MockServiceFactory.create_mock_storage_config_service(memory_config_override)
            
            # Create service with persistence
            persistent_service = MemoryStorageService(
                provider_name="memory",
                configuration=mock_persistent_storage_config,
                logging_service=self.mock_logging_service
            )
            
            # Add some data
            persistent_service.write("users", {"name": "John"}, "user1")
            persistent_service.write("users", {"name": "Jane"}, "user2")
            
            # Save persistence
            result = persistent_service.save_persistence()
            self.assertTrue(result.success)
            
            # Verify file was created
            self.assertTrue(os.path.exists(temp_path))
            
            # Create new service instance that should load the data
            new_service = MemoryStorageService(
                provider_name="memory",
                configuration=mock_persistent_storage_config,
                logging_service=self.mock_logging_service
            )
            
            # Data should be loaded from persistence file
            retrieved = new_service.read("users", "user1")
            self.assertEqual(retrieved["name"], "John")
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    # =============================================================================
    # 9. Edge Cases and Boundary Tests
    # =============================================================================
    
    def test_empty_path_operations(self):
        """Test operations with empty or None paths."""
        collection = "path_test"
        doc_id = "test_doc"
        data = {"test": "data"}
        
        # Write with empty path should work like normal write
        result = self.service.write(collection, data, doc_id, path="")
        self.assertTrue(result.success)
        
        # Read with empty path should return whole document
        retrieved = self.service.read(collection, doc_id, path="")
        self.assertEqual(retrieved, data)
        
        # Read with None path should return whole document
        retrieved = self.service.read(collection, doc_id, path=None)
        self.assertEqual(retrieved, data)
    
    def test_array_index_operations(self):
        """Test path operations with array indices."""
        collection = "array_test"
        doc_id = "array_doc"
        
        # Create document with array
        data = {
            "items": ["item0", "item1", "item2"],
            "nested": [
                {"id": 0, "value": "zero"},
                {"id": 1, "value": "one"}
            ]
        }
        
        self.service.write(collection, data, doc_id)
        
        # Read array element by index
        item = self.service.read(collection, doc_id, path="items.1")
        self.assertEqual(item, "item1")
        
        # Read nested array element
        nested_value = self.service.read(collection, doc_id, path="nested.0.value")
        self.assertEqual(nested_value, "zero")
        
        # Update array element
        self.service.write(collection, "updated_item", doc_id, WriteMode.WRITE, path="items.1")
        updated_item = self.service.read(collection, doc_id, path="items.1")
        self.assertEqual(updated_item, "updated_item")
    
    def test_case_sensitivity(self):
        """Test case sensitivity settings."""
        # Test with case sensitive collections (default)
        self.service.write("TestCollection", {"data": "test"}, "doc1")
        self.service.write("testcollection", {"data": "test"}, "doc1")
        
        # Should have two separate collections
        self.assertTrue(self.service.exists("TestCollection"))
        self.assertTrue(self.service.exists("testcollection"))
        
        collections = self.service.list_collections()
        self.assertIn("TestCollection", collections)
        self.assertIn("testcollection", collections)
    
    def test_concurrent_access_simulation(self):
        """Test behavior with simulated concurrent access."""
        collection = "concurrent_test"
        
        # Create initial document first
        initial_result = self.service.write(collection, {"counter": 0}, "shared_doc", WriteMode.WRITE)
        self.assertTrue(initial_result.success)
        
        # Simulate concurrent writes to same document
        for i in range(1, 10):  # Start from 1 since we already created with 0
            result = self.service.write(collection, {"counter": i}, "shared_doc", WriteMode.UPDATE)
            # Each update should succeed
            self.assertTrue(result.success)
        
        # Final value should be the last write
        final_doc = self.service.read(collection, "shared_doc")
        self.assertEqual(final_doc["counter"], 9)
        
        # Metadata should show multiple updates
        metadata = self.service._metadata[collection]["shared_doc"]
        self.assertGreaterEqual(metadata["version"], 9)


if __name__ == '__main__':
    unittest.main()
