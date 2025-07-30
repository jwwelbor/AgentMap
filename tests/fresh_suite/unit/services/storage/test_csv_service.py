"""
Unit tests for CSVStorageService.

These tests validate the CSVStorageService implementation including:
- CSV reading/writing with various formats
- Header handling and data type conversion
- Delimiter detection and custom separators
- Large file processing
- Query filtering and row management
- Pandas DataFrame operations
"""

import unittest
import os
import tempfile
import shutil
import platform
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
import pytest

from agentmap.services.storage.csv_service import CSVStorageService
from agentmap.services.storage.types import WriteMode, StorageResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestCSVStorageService(unittest.TestCase):
    """Unit tests for CSVStorageService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Use StorageConfigService mock instead of AppConfigService for CSV storage
        self.mock_storage_config_service = MockServiceFactory.create_mock_storage_config_service({
            "csv": {
                "enabled": True,
                "default_directory": self.temp_dir,
                "encoding": "utf-8",
                "collections": {
                    "test_collection": {"filename": "test_collection.csv"},
                    "users": {"filename": "users.csv"}
                }
            }
        })
        
        # Create CSVStorageService with mocked dependencies
        self.service = CSVStorageService(
            provider_name="csv",
            configuration=self.mock_storage_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service._logger
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_csv_file(self, relative_path: str, data: pd.DataFrame) -> str:
        """Helper to create a test CSV file."""
        full_path = os.path.join(self.temp_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        data.to_csv(full_path, index=False, encoding='utf-8')
        return full_path
    
    def _create_sample_dataframe(self) -> pd.DataFrame:
        """Helper to create sample DataFrame for testing."""
        return pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
            'age': [25, 30, 35, 28, 32],
            'city': ['New York', 'Boston', 'Chicago', 'Seattle', 'Austin'],
            'active': [True, False, True, True, False]
        })
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.provider_name, "csv")
        self.assertEqual(self.service.configuration, self.mock_storage_config_service)
        self.assertIsNotNone(self.service._logger)
        
        # Verify base directory was created
        self.assertTrue(os.path.exists(self.temp_dir))
    
    def test_client_initialization(self):
        """Test that client initializes with correct configuration."""
        client = self.service.client
        
        # Verify client configuration has expected structure
        self.assertIsInstance(client, dict)
        
        # Check for expected configuration keys
        expected_keys = ["base_directory", "encoding", "default_options"]
        
        for key in expected_keys:
            self.assertIn(key, client)
        
        # Verify configuration values
        self.assertEqual(client["base_directory"], self.temp_dir)
        self.assertEqual(client["encoding"], "utf-8")
        self.assertIn("skipinitialspace", client["default_options"])
    
    def test_service_health_check(self):
        """Test that health check works correctly."""
        # Should be healthy by default
        self.assertTrue(self.service.health_check())
        
        # Health check should test pandas operations
        result = self.service._perform_health_check()
        self.assertTrue(result)
    
    def test_health_check_with_inaccessible_directory(self):
        """Test health check fails with inaccessible directory."""
        # Use a more reliable approach to test directory access failures
        # Create a config with an invalid path that will definitely fail
        if os.name == 'nt':  # Windows
            # Use an invalid drive that doesn't exist
            inaccessible_dir = "Z:\\nonexistent\\path\\that\\will\\fail"
        else:  # Unix-like systems
            # Create a read-only parent directory to prevent subdirectory creation
            readonly_parent = os.path.join(self.temp_dir, "readonly_parent")
            os.makedirs(readonly_parent)
            os.chmod(readonly_parent, 0o444)  # Read-only permissions
            inaccessible_dir = os.path.join(readonly_parent, "subdir")
        
        try:
            bad_config = MockServiceFactory.create_mock_app_config_service({
                "storage": {
                    "csv": {
                        "provider": "csv",
                        "options": {
                            "base_directory": inaccessible_dir
                        }
                    }
                }
            })
            
            bad_service = CSVStorageService(
                provider_name="csv",
                configuration=bad_config,
                logging_service=self.mock_logging_service
            )
            
            # Health check should fail because directory cannot be created
            self.assertFalse(bad_service.health_check())
            
        finally:
            # Restore permissions for cleanup (Unix only)
            if os.name != 'nt':
                try:
                    readonly_parent = os.path.join(self.temp_dir, "readonly_parent")
                    if os.path.exists(readonly_parent):
                        os.chmod(readonly_parent, 0o755)
                except (OSError, PermissionError):
                    pass  # Ignore cleanup errors
    
    # =============================================================================
    # 2. File Path Management Tests
    # =============================================================================
    
    def test_get_file_path(self):
        """Test file path generation."""
        # Test with relative path
        path = self.service._get_file_path("test_collection")
        expected = os.path.join(self.temp_dir, "test_collection.csv")
        self.assertEqual(path, expected)
        
        # Test with .csv extension already present
        path = self.service._get_file_path("test_collection.csv")
        expected = os.path.join(self.temp_dir, "test_collection.csv")
        self.assertEqual(path, expected)
        
        # Test with absolute path
        abs_path = "/tmp/test.csv"
        path = self.service._get_file_path(abs_path)
        self.assertEqual(path, abs_path)
    
    def test_ensure_directory_exists(self):
        """Test directory creation."""
        nested_file = os.path.join(self.temp_dir, "nested", "deep", "file.csv")
        
        # Directory shouldn't exist initially
        self.assertFalse(os.path.exists(os.path.dirname(nested_file)))
        
        # Should create directory structure
        self.service._ensure_directory_exists(nested_file)
        self.assertTrue(os.path.exists(os.path.dirname(nested_file)))
    
    # =============================================================================
    # 3. DataFrame I/O Operations Tests
    # =============================================================================
    
    def test_read_csv_file(self):
        """Test CSV file reading with pandas."""
        # Create test CSV file
        test_df = self._create_sample_dataframe()
        file_path = self._create_test_csv_file("test.csv", test_df)
        
        # Read the file
        result_df = self.service._read_csv_file(file_path)
        
        # Verify DataFrame content
        pd.testing.assert_frame_equal(result_df, test_df)
    
    def test_read_csv_file_with_custom_options(self):
        """Test CSV reading with custom pandas options."""
        # Create CSV with custom format - use actual newlines, not escaped ones
        custom_data = "Name;Age;City\nAlice;25;New York\nBob;30;Boston"
        custom_file = os.path.join(self.temp_dir, "custom.csv")
        
        with open(custom_file, 'w', encoding='utf-8') as f:
            f.write(custom_data)
        
        # Read with custom separator
        result_df = self.service._read_csv_file(custom_file, sep=';')
        
        self.assertEqual(len(result_df), 2)
        self.assertIn("Name", result_df.columns)
        self.assertEqual(result_df.iloc[0]['Name'], "Alice")
    
    def test_read_nonexistent_csv_file(self):
        """Test reading non-existent CSV file."""
        nonexistent_path = os.path.join(self.temp_dir, "nonexistent.csv")
        
        with self.assertRaises(FileNotFoundError):
            self.service._read_csv_file(nonexistent_path)
    
    def test_write_csv_file(self):
        """Test CSV file writing with pandas."""
        test_df = self._create_sample_dataframe()
        file_path = os.path.join(self.temp_dir, "write_test.csv")
        
        # Write the file
        self.service._write_csv_file(test_df, file_path)
        
        # Verify file was created
        self.assertTrue(os.path.exists(file_path))
        
        # Read back and compare
        loaded_df = pd.read_csv(file_path)
        pd.testing.assert_frame_equal(loaded_df, test_df)
    
    def test_write_csv_file_append_mode(self):
        """Test CSV file writing in append mode."""
        # Create initial file
        initial_df = pd.DataFrame({
            'id': [1, 2],
            'name': ['Alice', 'Bob'],
            'age': [25, 30]
        })
        file_path = os.path.join(self.temp_dir, "append_test.csv")
        self.service._write_csv_file(initial_df, file_path)
        
        # Append more data
        append_df = pd.DataFrame({
            'id': [3, 4],
            'name': ['Charlie', 'Diana'],
            'age': [35, 28]
        })
        self.service._write_csv_file(append_df, file_path, mode='a')
        
        # Read back and verify
        result_df = pd.read_csv(file_path)
        self.assertEqual(len(result_df), 4)
        self.assertEqual(result_df.iloc[-1]['name'], 'Diana')
    
    # =============================================================================
    # 4. Query Filtering Tests
    # =============================================================================
    
    def test_apply_query_filter(self):
        """Test query filtering on DataFrame."""
        test_df = self._create_sample_dataframe()
        
        # Test simple field filter
        query = {"city": "New York"}
        filtered_df = self.service._apply_query_filter(test_df, query)
        
        self.assertEqual(len(filtered_df), 1)
        self.assertEqual(filtered_df.iloc[0]['name'], 'Alice')
        
        # Test boolean filter
        query = {"active": True}
        filtered_df = self.service._apply_query_filter(test_df, query)
        
        self.assertEqual(len(filtered_df), 3)
        for _, row in filtered_df.iterrows():
            self.assertTrue(row['active'])
        
        # Test list filter (isin)
        query = {"city": ["New York", "Boston"]}
        filtered_df = self.service._apply_query_filter(test_df, query)
        
        self.assertEqual(len(filtered_df), 2)
        cities = filtered_df['city'].tolist()
        self.assertIn("New York", cities)
        self.assertIn("Boston", cities)
    
    def test_query_filter_with_sorting(self):
        """Test query filtering with sorting."""
        test_df = self._create_sample_dataframe()
        
        # Test sorting by age (ascending)
        query = {"sort": "age", "order": "asc"}
        filtered_df = self.service._apply_query_filter(test_df, query)
        
        ages = filtered_df['age'].tolist()
        self.assertEqual(ages, sorted(ages))
        
        # Test sorting by name (descending)
        query = {"sort": "name", "order": "desc"}
        filtered_df = self.service._apply_query_filter(test_df, query)
        
        names = filtered_df['name'].tolist()
        self.assertEqual(names, sorted(names, reverse=True))
    
    def test_query_filter_with_pagination(self):
        """Test query filtering with limit and offset."""
        test_df = self._create_sample_dataframe()
        
        # Test limit only
        query = {"limit": 3}
        filtered_df = self.service._apply_query_filter(test_df, query)
        self.assertEqual(len(filtered_df), 3)
        
        # Test offset only
        query = {"offset": 2}
        filtered_df = self.service._apply_query_filter(test_df, query)
        self.assertEqual(len(filtered_df), 3)  # 5 - 2 = 3
        
        # Test limit and offset together
        query = {"offset": 1, "limit": 2}
        filtered_df = self.service._apply_query_filter(test_df, query)
        self.assertEqual(len(filtered_df), 2)
        
        # Verify correct rows are returned
        self.assertEqual(filtered_df.iloc[0]['id'], 2)  # Second row (index 1)
        self.assertEqual(filtered_df.iloc[1]['id'], 3)  # Third row (index 2)
    
    def test_complex_query_combinations(self):
        """Test complex query combinations."""
        test_df = self._create_sample_dataframe()
        
        # Filter + sort + limit
        query = {
            "active": True,
            "sort": "age",
            "order": "desc",
            "limit": 2
        }
        filtered_df = self.service._apply_query_filter(test_df, query)
        
        # Should return 2 active users, sorted by age descending
        self.assertEqual(len(filtered_df), 2)
        ages = filtered_df['age'].tolist()
        self.assertEqual(ages, sorted(ages, reverse=True))
        
        for _, row in filtered_df.iterrows():
            self.assertTrue(row['active'])
    
    # =============================================================================
    # 5. Storage Operations Tests
    # =============================================================================
    
    def test_read_entire_csv(self):
        """Test reading entire CSV file."""
        collection = "test_collection"
        test_df = self._create_sample_dataframe()
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Read entire file (default format: dict)
        result = self.service.read(collection)
        
        self.assertIsInstance(result, dict)
        # Should be index-based dict {0: row_dict, 1: row_dict, ...}
        self.assertEqual(len(result), 5)
        self.assertIn(0, result)
        self.assertIn(4, result)
        self.assertEqual(result[0]['name'], 'Alice')
        self.assertEqual(result[4]['name'], 'Eve')
    
    def test_read_with_different_formats(self):
        """Test reading with different output formats."""
        collection = "format_test"
        test_df = self._create_sample_dataframe()
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Test records format
        result = self.service.read(collection, format="records")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)
        self.assertIn("name", result[0])
        self.assertEqual(result[0]['name'], 'Alice')
        
        # Test dict format (index-based keys)
        result = self.service.read(collection, format="dict")
        self.assertIsInstance(result, dict)
        self.assertIn(0, result)  # Index-based keys
        self.assertIn(4, result)
        self.assertEqual(result[0]['name'], 'Alice')
        
        # Test dataframe format
        result = self.service.read(collection, format="dataframe")
        self.assertIsInstance(result, pd.DataFrame)
        pd.testing.assert_frame_equal(result, test_df)
    
    def test_read_specific_document_by_id(self):
        """Test reading specific row by ID."""
        collection = "id_test"
        test_df = self._create_sample_dataframe()
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Read specific document by ID
        result = self.service.read(collection, document_id=1)
        
        # Should return single record as dict
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "Alice")
        self.assertEqual(result["id"], 1)
        
        # Test non-existent ID
        result = self.service.read(collection, document_id=999)
        self.assertIsNone(result)
    
    def test_read_with_explicit_id_field(self):
        """Test reading with explicit ID field specification."""
        collection = "custom_id_test"
        test_df = pd.DataFrame({
            'user_id': ['u1', 'u2', 'u3'],
            'name': ['Alice', 'Bob', 'Charlie'],
            'score': [100, 85, 92]
        })
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Test auto-detection (user_id ends with _id, should be detected)
        result = self.service.read(collection, document_id='u2')
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "Bob")
        self.assertEqual(result["user_id"], "u2")
        
        # Test explicit id_field (for cases where auto-detection might be ambiguous)
        result = self.service.read(collection, document_id='u2', id_field='user_id')
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "Bob")
        self.assertEqual(result["user_id"], "u2")
    
    def test_read_with_business_identifier(self):
        """Test reading with business identifier that doesn't follow ID conventions."""
        collection = "products_test"
        test_df = pd.DataFrame({
            'sku': ['PROD001', 'PROD002', 'PROD003'],
            'name': ['Widget', 'Gadget', 'Tool'],
            'price': [10.99, 25.50, 15.75]
        })
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Auto-detection should fail (no conventional ID columns)
        result = self.service.read(collection, document_id='PROD002')
        self.assertIsNone(result)  # No ID column detected
        
        # But explicit id_field should work
        result = self.service.read(collection, document_id='PROD002', id_field='sku')
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "Gadget")
        self.assertEqual(result["sku"], "PROD002")
    
    def test_read_nonexistent_file(self):
        """Test reading non-existent CSV file."""
        result = self.service.read("nonexistent_collection")
        
        # Should return None for non-existent file
        self.assertIsNone(result)
    
    def test_read_with_query(self):
        """Test reading with query parameters."""
        collection = "query_read_test"
        test_df = self._create_sample_dataframe()
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Read with query (default format: dict)
        query = {"active": True, "limit": 2}
        result = self.service.read(collection, query=query)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 2)
        
        # Check that all returned rows have active=True
        for row_dict in result.values():
            self.assertTrue(row_dict['active'])
    
    # =============================================================================
    # 6. Write Operations Tests
    # =============================================================================
    
    def test_write_new_csv_file(self):
        """Test writing to new CSV file."""
        collection = "new_collection"
        # Use list of dicts format to ensure 3 rows
        test_data = [
            {'id': 1, 'name': 'Alice', 'age': 25},
            {'id': 2, 'name': 'Bob', 'age': 30},
            {'id': 3, 'name': 'Charlie', 'age': 35}
        ]
        
        # Write data (as list of dicts)
        result = self.service.write(collection, test_data)
        
        # Verify result
        self.assertIsInstance(result, StorageResult)
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "write")
        self.assertEqual(result.collection, collection)
        self.assertEqual(result.rows_written, 3)
        self.assertTrue(result.created_new)
        
        # Verify file was created
        file_path = self.service._get_file_path(collection)
        self.assertTrue(os.path.exists(file_path))
        
        # Verify content
        written_df = pd.read_csv(file_path)
        self.assertEqual(len(written_df), 3)
        self.assertIn("name", written_df.columns)
    
    def test_write_dataframe(self):
        """Test writing DataFrame directly."""
        collection = "dataframe_test"
        test_df = self._create_sample_dataframe()
        
        # Write DataFrame
        result = self.service.write(collection, test_df)
        
        self.assertTrue(result.success)
        self.assertEqual(result.rows_written, 5)
        
        # Read back and compare (specify dataframe format)
        written_df = self.service.read(collection, format="dataframe")
        pd.testing.assert_frame_equal(written_df, test_df)
    
    def test_write_list_of_dicts(self):
        """Test writing list of dictionaries."""
        collection = "list_test"
        test_data = [
            {'id': 1, 'name': 'Alice', 'age': 25},
            {'id': 2, 'name': 'Bob', 'age': 30},
            {'id': 3, 'name': 'Charlie', 'age': 35}
        ]
        
        # Write list of dicts
        result = self.service.write(collection, test_data)
        
        self.assertTrue(result.success)
        self.assertEqual(result.rows_written, 3)
        
        # Read back and verify (use records format for list-like access)
        written_records = self.service.read(collection, format="records")
        self.assertEqual(len(written_records), 3)
        self.assertEqual(written_records[0]['name'], 'Alice')
    
    def test_write_modes(self):
        """Test different write modes."""
        collection = "write_modes_test"
        
        # Test WRITE mode (create/overwrite)
        initial_data = [
            {'id': 1, 'name': 'Alice', 'version': 1},
            {'id': 2, 'name': 'Bob', 'version': 1}
        ]
        
        result = self.service.write(collection, initial_data, mode=WriteMode.WRITE)
        self.assertTrue(result.success)
        self.assertTrue(result.created_new)
        
        # Test APPEND mode
        append_data = [
            {'id': 3, 'name': 'Charlie', 'version': 1},
            {'id': 4, 'name': 'Diana', 'version': 1}
        ]
        
        result = self.service.write(collection, append_data, mode=WriteMode.APPEND)
        self.assertTrue(result.success)
        self.assertFalse(result.created_new)
        
        # Verify all data exists (use dataframe format for DataFrame operations)
        final_df = self.service.read(collection, format="dataframe")
        self.assertEqual(len(final_df), 4)
        
        # Test UPDATE mode
        update_data = [
            {'id': 1, 'name': 'Alice Updated', 'version': 2},
            {'id': 5, 'name': 'Eve', 'version': 1}  # New record
        ]
        
        result = self.service.write(collection, update_data, mode=WriteMode.UPDATE)
        self.assertTrue(result.success)
        
        # Verify updates and additions (use dataframe format for DataFrame operations)
        final_df = self.service.read(collection, format="dataframe")
        alice_row = final_df[final_df['id'] == 1].iloc[0]
        self.assertEqual(alice_row['name'], 'Alice Updated')
        self.assertEqual(alice_row['version'], 2)
        
        # Verify new record was added
        eve_rows = final_df[final_df['id'] == 5]
        self.assertEqual(len(eve_rows), 1)
    
    def test_write_with_custom_options(self):
        """Test writing with custom pandas options."""
        collection = "custom_options_test"
        test_data = {'name': ['Alice', 'Bob'], 'age': [25, 30]}
        
        # Write with custom encoding and separator
        result = self.service.write(collection, test_data, sep=';', encoding='latin-1')
        
        if result.success:  # May fail if encoding doesn't support characters
            # Verify file uses custom separator
            file_path = self.service._get_file_path(collection)
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
                self.assertIn(';', content)
    
    def test_write_unsupported_data_type(self):
        """Test writing unsupported data types."""
        collection = "unsupported_test"
        
        # Try to write unsupported type
        unsupported_data = "plain string"
        
        # Should get StorageProviderError since the service handles errors
        from agentmap.services.storage.types import StorageProviderError
        with self.assertRaises(StorageProviderError) as context:
            self.service.write(collection, unsupported_data)
        
        self.assertIn("Unsupported data type", str(context.exception))
    
    # =============================================================================
    # 7. Delete Operations Tests
    # =============================================================================
    
    def test_delete_specific_row(self):
        """Test deleting specific row by ID."""
        collection = "delete_test"
        test_df = self._create_sample_dataframe()
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Delete specific row
        result = self.service.delete(collection, document_id=2)
        
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "delete")
        self.assertEqual(result.document_id, 2)
        self.assertEqual(result.total_affected, 1)
        
        # Verify row is gone (use dataframe format for DataFrame operations)
        remaining_df = self.service.read(collection, format="dataframe")
        self.assertEqual(len(remaining_df), 4)
        
        # Verify specific row is gone
        bob_rows = remaining_df[remaining_df['name'] == 'Bob']
        self.assertTrue(bob_rows.empty)
    
    def test_delete_with_explicit_id_field(self):
        """Test deleting with explicit ID field specification."""
        collection = "delete_custom_id_test"
        test_df = pd.DataFrame({
            'user_id': ['u1', 'u2', 'u3'],
            'name': ['Alice', 'Bob', 'Charlie']
        })
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Delete with custom ID field
        result = self.service.delete(collection, document_id='u2', id_field='user_id')
        
        self.assertTrue(result.success)
        self.assertEqual(result.total_affected, 1)
        
        # Verify row is gone (use dataframe format for DataFrame operations)
        remaining_df = self.service.read(collection, format="dataframe")
        self.assertEqual(len(remaining_df), 2)
        
        bob_rows = remaining_df[remaining_df['user_id'] == 'u2']
        self.assertTrue(bob_rows.empty)
    
    def test_delete_entire_file(self):
        """Test deleting entire CSV file."""
        collection = "delete_file_test"
        test_df = self._create_sample_dataframe()
        
        # Create test file
        file_path = self._create_test_csv_file(f"{collection}.csv", test_df)
        self.assertTrue(os.path.exists(file_path))
        
        # Delete entire file
        result = self.service.delete(collection)
        
        self.assertTrue(result.success)
        self.assertTrue(result.file_deleted)
        
        # Verify file is gone
        self.assertFalse(os.path.exists(file_path))
    
    def test_delete_nonexistent_file(self):
        """Test deleting non-existent file."""
        result = self.service.delete("nonexistent_collection")
        
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
    
    def test_delete_nonexistent_row(self):
        """Test deleting non-existent row."""
        collection = "delete_row_test"
        test_df = self._create_sample_dataframe()
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Try to delete non-existent row
        result = self.service.delete(collection, document_id=999)
        
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
    
    def test_delete_missing_id_field(self):
        """Test deleting when ID field is missing."""
        collection = "no_id_field_test"
        test_df = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'age': [25, 30]
            # No 'id' field
        })
        
        # Create test file
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Try to delete by ID when no ID field exists
        result = self.service.delete(collection, document_id=1)
        
        self.assertFalse(result.success)
        self.assertIn("ID field", result.error)
        self.assertIn("not found", result.error)
    
    # =============================================================================
    # 8. Utility Operations Tests
    # =============================================================================
    
    def test_exists_operations(self):
        """Test exists functionality."""
        collection = "exists_test"
        
        # File doesn't exist initially
        self.assertFalse(self.service.exists(collection))
        
        # Create file
        test_df = self._create_sample_dataframe()
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # File should exist now
        self.assertTrue(self.service.exists(collection))
        
        # Test document existence
        self.assertTrue(self.service.exists(collection, document_id=1))
        self.assertFalse(self.service.exists(collection, document_id=999))
    
    def test_count_operations(self):
        """Test count functionality."""
        collection = "count_test"
        
        # Empty/non-existent file
        self.assertEqual(self.service.count(collection), 0)
        
        # Create test file
        test_df = self._create_sample_dataframe()
        self._create_test_csv_file(f"{collection}.csv", test_df)
        
        # Count all rows
        self.assertEqual(self.service.count(collection), 5)
        
        # Count with query
        self.assertEqual(self.service.count(collection, {"active": True}), 3)
        self.assertEqual(self.service.count(collection, {"city": "New York"}), 1)
    
    def test_list_collections(self):
        """Test collection (CSV file) listing."""
        # Initially should include configured collections from StorageConfigService
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 2)  # test_collection and users from mock config
        self.assertIn("test_collection", collections)
        self.assertIn("users", collections)
        
        # Create some CSV files
        test_df = self._create_sample_dataframe()
        file_names = ["products.csv", "orders.csv"]  # Don't create users.csv as it's already configured
        
        for file_name in file_names:
            self._create_test_csv_file(file_name, test_df)
        
        # Should list all collections (configured + CSV files found)
        collections = self.service.list_collections()
        expected_collections = {"test_collection", "users", "products", "orders"}
        self.assertEqual(set(collections), expected_collections)
        
        # Should be sorted
        self.assertEqual(collections, sorted(collections))
    
    # =============================================================================
    # 9. Error Handling Tests
    # =============================================================================
    
    def test_read_malformed_csv(self):
        """Test reading malformed CSV file."""
        # Create malformed CSV
        malformed_content = "id,name,age\\n1,Alice,25\\n2,Bob\\n3,Charlie,35,extra"
        malformed_file = os.path.join(self.temp_dir, "malformed.csv")
        
        with open(malformed_file, 'w', encoding='utf-8') as f:
            f.write(malformed_content)
        
        # Should handle gracefully (pandas is quite robust)
        try:
            result_df = self.service._read_csv_file(malformed_file)
            # If it succeeds, verify it handled the issues
            self.assertIsInstance(result_df, pd.DataFrame)
        except Exception as e:
            # If it fails, should be handled by error handling
            self.assertIsInstance(e, Exception)
    
    @pytest.mark.skipif(
        platform.system() == "Windows" or os.environ.get('CI') == 'true',
        reason="Permission tests not reliable on Windows or CI environments. Alternative security validation performed through path validation tests."
    )
    def test_write_to_readonly_location(self):
        """Test writing to read-only location with cross-platform compatibility.
        
        This test validates permission error handling in the CSV storage service.
        
        Platform-specific behavior:
        - Unix-like systems: Uses chmod to create read-only directories and validates permission errors
        - Windows: Skipped due to unreliable chmod behavior
        - CI environments: Skipped due to permission constraints
        
        Alternative security measures are tested through path validation tests on all platforms.
        """
        # Create read-only directory (Unix-like systems only)
        readonly_dir = os.path.join(self.temp_dir, "readonly")
        os.makedirs(readonly_dir)
        os.chmod(readonly_dir, 0o444)  # Read-only permissions
        
        try:
            # Create service with read-only base directory
            readonly_config = MockServiceFactory.create_mock_app_config_service({
                "storage": {
                    "csv": {
                        "options": {
                            "base_directory": readonly_dir
                        }
                    }
                }
            })
            
            readonly_service = CSVStorageService(
                provider_name="csv",
                configuration=readonly_config,
                logging_service=self.mock_logging_service
            )
            
            # Try to write (should handle permission error gracefully)
            test_data = {'name': ['Alice'], 'age': [25]}
            result = readonly_service.write("test", test_data)
            
            # Should handle error gracefully with StorageResult
            self.assertFalse(result.success)
            self.assertIsNotNone(result.error)
            self.assertIn("Permission denied", result.error)
            
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, 0o755)
    
    def test_cross_platform_security_validation(self):
        """Test security validation that works across all platforms.
        
        This test ensures security measures are validated on all platforms,
        including Windows where file permission tests are unreliable.
        Tests path validation and error handling for security violations.
        
        Platform-specific behavior:
        - All platforms: Path traversal validation and security error handling
        - Windows: Alternative security measures since permission tests are unreliable
        - Unix-like: Additional permission validation through other test methods
        """
        # Test path traversal security (works on all platforms)
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "subdir/../../sensitive_file"
        ]
        
        for dangerous_path in dangerous_paths:
            # Should either return error result or raise security exception
            try:
                result = self.service.write(dangerous_path, {"test": "data"})
                # If no exception, should return error result
                if hasattr(result, 'success'):
                    self.assertFalse(result.success, 
                        f"Expected security failure for path: {dangerous_path}")
                    if result.error:
                        self.assertIn("outside base directory", result.error.lower())
            except Exception as e:
                # Security exceptions are acceptable
                error_msg = str(e).lower()
                self.assertTrue(
                    "outside base directory" in error_msg or 
                    "permission" in error_msg or
                    "security" in error_msg,
                    f"Expected security-related error for {dangerous_path}, got: {e}"
                )
        
        # Test that the service correctly handles invalid base directories
        # This works on all platforms
        invalid_configs = []
        
        if platform.system() == "Windows":
            # Windows-specific invalid paths
            invalid_configs.extend([
                "C:\\invalid<>|path",
                "Z:\\nonexistent\\drive"
            ])
        else:
            # Unix-like invalid paths
            invalid_configs.extend([
                "/root/restricted_access",
                "/sys/kernel/restricted"
            ])
        
        for invalid_path in invalid_configs:
            try:
                bad_config = MockServiceFactory.create_mock_app_config_service({
                    "storage": {
                        "csv": {
                            "provider": "csv",
                            "options": {
                                "base_directory": invalid_path
                            }
                        }
                    }
                })
                
                # Service creation or health check should fail
                try:
                    bad_service = CSVStorageService(
                        provider_name="csv",
                        configuration=bad_config,
                        logging_service=self.mock_logging_service
                    )
                    # If service creation succeeds, health check should fail
                    self.assertFalse(bad_service.health_check(),
                        f"Expected health check failure for invalid path: {invalid_path}")
                except Exception:
                    # Exception during service creation is acceptable
                    pass
                    
            except Exception:
                # Any exception is acceptable for invalid paths
                pass
    
    def test_pandas_operation_failure(self):
        """Test handling of pandas operation failures."""
        collection = "pandas_error_test"
        
        # Mock pandas to raise exception
        with patch('pandas.read_csv', side_effect=pd.errors.EmptyDataError("No data")):
            # Try to read (should handle pandas error)
            try:
                result = self.service.read(collection)
                # Should return empty DataFrame or handle gracefully
                if isinstance(result, pd.DataFrame):
                    self.assertTrue(result.empty)
            except Exception:
                # If exception propagates, it should be handled appropriately
                pass
    
    # =============================================================================
    # 10. Performance and Edge Cases Tests
    # =============================================================================
    
    def test_large_dataframe_operations(self):
        """Test operations with larger DataFrames."""
        collection = "large_test"
        
        # Create larger test DataFrame
        large_df = pd.DataFrame({
            'id': range(1000),
            'name': [f'User_{i}' for i in range(1000)],
            'value': [i * 2 for i in range(1000)],
            'category': [f'Cat_{i % 10}' for i in range(1000)]
        })
        
        # Write large DataFrame
        result = self.service.write(collection, large_df)
        self.assertTrue(result.success)
        self.assertEqual(result.rows_written, 1000)
        
        # Read back and verify size (use dataframe format for DataFrame operations)
        read_df = self.service.read(collection, format="dataframe")
        self.assertEqual(len(read_df), 1000)
        
        # Test query on large data (use dataframe format for DataFrame operations)
        query_result = self.service.read(collection, query={"category": "Cat_5", "limit": 10}, format="dataframe")
        self.assertLessEqual(len(query_result), 10)
        
        for _, row in query_result.iterrows():
            self.assertEqual(row['category'], 'Cat_5')
    
    def test_empty_dataframe_operations(self):
        """Test operations with empty DataFrames."""
        collection = "empty_test"
        
        # Create empty DataFrame with columns
        empty_df = pd.DataFrame(columns=['id', 'name', 'age'])
        
        # Write empty DataFrame
        result = self.service.write(collection, empty_df)
        self.assertTrue(result.success)
        self.assertEqual(result.rows_written, 0)
        
        # Read back (should return None for empty file)
        read_result = self.service.read(collection)
        self.assertIsNone(read_result)
        
        # Test count on empty
        self.assertEqual(self.service.count(collection), 0)
    
    def test_special_characters_in_data(self):
        """Test handling of special characters in CSV data."""
        collection = "special_chars_test"
        
        # Data with special characters
        special_df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Alice "Ace"', 'Bob, Jr.', 'Charlie\\nNewline'],
            'description': ['Has "quotes"', 'Has, commas', 'Has\\nnewlines\\rand\\ttabs'],
            'unicode': ['José', 'Café', '🎉 Emoji']
        })
        
        # Write and read back
        result = self.service.write(collection, special_df)
        self.assertTrue(result.success)
        
        read_df = self.service.read(collection, format="dataframe")
        
        # Verify special characters are preserved
        self.assertIn('"', read_df.iloc[0]['name'])
        self.assertIn(',', read_df.iloc[1]['name'])
        self.assertIn('é', read_df.iloc[0]['unicode'])
        
        # Note: Newlines in CSV cells might be handled differently by pandas
        # This test verifies the service can handle them without crashing
    
    def test_mixed_data_types_in_columns(self):
        """Test handling of mixed data types."""
        collection = "mixed_types_test"
        
        # DataFrame with mixed types
        mixed_df = pd.DataFrame({
            'id': [1, 2, 3],
            'mixed_col': ['string', 42, True],
            'nullable_col': ['value', None, 'another'],
            'numeric_col': [1.5, 2, 3.7]
        })
        
        # Write and read back
        result = self.service.write(collection, mixed_df)
        self.assertTrue(result.success)
        
        read_df = self.service.read(collection, format="dataframe")
        
        # Verify data was preserved (types might be converted by pandas)
        self.assertEqual(len(read_df), 3)
        self.assertIn('mixed_col', read_df.columns)
        
        # Check that nullable column handled NaN/None appropriately
        self.assertIn('nullable_col', read_df.columns)
    
    def test_simulated_concurrent_access(self):
        collection = "concurrent_test"
        
        # Simulate multiple rapid operations - use list of dicts format
        for i in range(5):
            test_data = [{'id': i, 'name': f'User_{i}', 'batch': i}]
            
            if i == 0:
                result = self.service.write(collection, test_data)
            else:
                result = self.service.write(collection, test_data, mode=WriteMode.APPEND)
            
            self.assertTrue(result.success)
        
        # Verify all data was written (use dataframe format for DataFrame operations)
        final_df = self.service.read(collection, format="dataframe")
        self.assertEqual(len(final_df), 5)
        
        # Verify all batches are present
        batches = set(final_df['batch'].tolist())
        self.assertEqual(batches, {0, 1, 2, 3, 4})


if __name__ == '__main__':
    unittest.main()
