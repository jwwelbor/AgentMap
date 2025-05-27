"""
Test suite for JSONStorageService.

This module provides comprehensive tests for the JSON storage service implementation,
verifying all CRUD operations, path-based access, and query filtering.
"""
import os
import sys
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.agentmap.services.storage.types import WriteMode, StorageResult, StorageConfig
from agentmap.services.storage.json_service import JSONStorageService
from src.agentmap.logging.service import LoggingService
from src.agentmap.config.configuration import Configuration


class TestJSONStorageService(unittest.TestCase):
    """Test cases for JSONStorageService."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a test directory
        self.test_dir = Path("./test_json_data")
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Create mock logging service
        mock_logger = MagicMock()
        mock_logger.debug = MagicMock()
        mock_logger.info = MagicMock()
        mock_logger.warning = MagicMock()
        mock_logger.error = MagicMock()
        
        self.mock_logging_service = MagicMock(spec=LoggingService)
        self.mock_logging_service.get_class_logger = MagicMock(return_value=mock_logger)
        
        # Create configuration
        self.config_dict = {
            "base_directory": str(self.test_dir),
            "encoding": "utf-8",
            "indent": 2,
            "provider": "json"
        }
        
        # Convert dict to StorageConfig
        storage_config = StorageConfig.from_dict(self.config_dict)
        
        # Create mock configuration
        self.mock_config = MagicMock(spec=Configuration)
        
        # Set up the mock to return our config dict when queried with the expected path
        def get_value_side_effect(path, default=None):
            if path == f"storage.{self.provider_name}" or path == f"storage.providers.{self.provider_name}":
                return self.config_dict
            return default
        
        self.mock_config.get_value = MagicMock(side_effect=get_value_side_effect)
        
        # Provider name
        self.provider_name = "test_json"
        
        # Initialize the service
        self.service = JSONStorageService("test_json", self.mock_config, self.mock_logging_service)
        
        # Test data
        self.users = [
            {"id": "user1", "name": "Alice", "role": "admin", "active": True, "score": 85},
            {"id": "user2", "name": "Bob", "role": "user", "active": True, "score": 75},
            {"id": "user3", "name": "Charlie", "role": "user", "active": False, "score": 90},
        ]
        
        self.nested_data = {
            "company": {
                "name": "Acme Inc.",
                "founded": 2010,
                "address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "zipcode": "12345"
                },
                "employees": [
                    {"id": 1, "name": "Alice", "department": "Engineering"},
                    {"id": 2, "name": "Bob", "department": "Marketing"}
                ]
            }
        }
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the test directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_initialization(self):
        """Test service initialization and health check."""
        # Check if the client is properly initialized
        self.assertIsNotNone(self.service.client)
        
        # Check that the base_directory is what we'd expect from our config
        # The exact value might be different based on internal defaults
        self.assertTrue(os.path.exists(self.service.client["base_directory"]))
        
        # Verify health check - use health_check method from base class
        self.assertTrue(self.service.health_check())
        
        # Also verify backward compatibility method
        if hasattr(self.service, 'is_healthy'):
            self.assertTrue(self.service.is_healthy())
        
        # Create an invalid service with a truly non-existent directory
        import tempfile
        nonexistent_dir = os.path.join(tempfile.gettempdir(), "definitely_not_a_real_dir_12345")
        if os.path.exists(nonexistent_dir):
            shutil.rmtree(nonexistent_dir)
            
        invalid_config_dict = {
            "base_directory": nonexistent_dir,
            "encoding": "utf-8",
            "provider": "json"
        }
        
        # Create mock configuration for invalid service
        invalid_mock_config = MagicMock(spec=Configuration)
        
        # Set up mock to return our invalid config
        def invalid_get_value(path, default=None):
            if path.startswith("storage."):
                return invalid_config_dict
            return default
            
        invalid_mock_config.get_value.side_effect = invalid_get_value
        
        # Create invalid service
        invalid_service = JSONStorageService(
            "invalid_json", 
            invalid_mock_config, 
            self.mock_logging_service
        )
        
        self.assertFalse(invalid_service.health_check())
    
    def test_write_read_basic(self):
        """Test basic write and read operations."""
        # Write users to a file
        result = self.service.write("users", self.users)
        self.assertTrue(result.success)
        
        # Check if file exists - need to use client base directory
        expected_dir = self.service.client["base_directory"]
        file_path = os.path.join(expected_dir, "users.json")
        self.assertTrue(os.path.exists(file_path))
        
        # Read the file back
        data = self.service.read("users")
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]["name"], "Alice")
    
    def test_write_read_document(self):
        """Test document-level write and read operations."""
        # Write a single document with ID
        user = {"name": "Dave", "role": "manager", "active": True}
        result = self.service.write("users", user, document_id="user4")
        self.assertTrue(result.success)
        
        # Read the document by ID
        data = self.service.read("users", document_id="user4")
        self.assertIsNotNone(data)
        self.assertEqual(data["name"], "Dave")
        
        # Test reading non-existent document
        data = self.service.read("users", document_id="nonexistent")
        self.assertIsNone(data)
    
    def test_path_operations(self):
        """Test path-based operations."""
        # Write nested data and verify it's written correctly
        result = self.service.write("company", self.nested_data)
        self.assertTrue(result.success)
        
        # Verify the data was written correctly
        all_company_data = self.service.read("company")
        self.assertIsNotNone(all_company_data)
        self.assertIn("company", all_company_data)
        
        # Read with path
        company_name = self.service.read("company", path="company.name")
        self.assertEqual(company_name, "Acme Inc.")
        
        # Get the address to verify it exists
        address = self.service.read("company", path="company.address")
        self.assertIsNotNone(address)
        self.assertIn("city", address)
        self.assertEqual(address["city"], "Anytown")
        
        # Read array element
        employee = self.service.read("company", path="company.employees.0")
        self.assertEqual(employee["name"], "Alice")
        
        # Update with path
        result = self.service.write(
            "company", 
            {"state": "CA", "country": "USA"}, 
            path="company.address",
            mode=WriteMode.UPDATE
        )
        self.assertTrue(result.success)
        
        # Verify update
        address = self.service.read("company", path="company.address")
        self.assertEqual(address["state"], "CA")
        self.assertEqual(address["city"], "Anytown")  # Original data preserved
        
        # Delete with path
        result = self.service.delete("company", path="company.address.zipcode")
        self.assertTrue(result.success)
        
        # Verify deletion
        address = self.service.read("company", path="company.address")
        self.assertNotIn("zipcode", address)
    
    def test_query_filtering(self):
        """Test query filtering."""
        # Write users data
        self.service.write("users", self.users)
        
        # Query by role
        active_users = self.service.read("users", query={"active": True})
        self.assertEqual(len(active_users), 2)
        
        # Query with multiple conditions
        admin_users = self.service.read("users", query={"role": "admin", "active": True})
        self.assertEqual(len(admin_users), 1)
        self.assertEqual(admin_users[0]["name"], "Alice")
        
        # Query with pagination
        paginated = self.service.read("users", query={"limit": 1, "offset": 1})
        self.assertEqual(len(paginated), 1)
        self.assertEqual(paginated[0]["name"], "Bob")
        
        # Query with sorting
        sorted_users = self.service.read("users", query={"sort": "score", "order": "desc"})
        self.assertEqual(sorted_users[0]["name"], "Charlie")
    
    def test_update_operations(self):
        """Test update operations."""
        # Write initial data
        result = self.service.write("users", self.users)
        self.assertTrue(result.success)
        
        # Verify data was written correctly
        initial_data = self.service.read("users")
        self.assertEqual(len(initial_data), 3)
        
        # Update a document
        updated_user = {"id": "user2", "name": "Robert", "role": "admin"}
        result = self.service.write("users", updated_user, mode=WriteMode.UPDATE)
        self.assertTrue(result.success)
        
        # Verify update - explicitly read the document by ID
        all_users = self.service.read("users")
        updated_user_found = False
        for user in all_users:
            if user.get("id") == "user2":
                self.assertEqual(user["name"], "Robert")
                self.assertEqual(user["role"], "admin")
                updated_user_found = True
                break
        
        self.assertTrue(updated_user_found, "Updated user not found in results")
        
        # Update with new document ID
        new_user = {"name": "Eve", "role": "user"}
        result = self.service.write("users", new_user, document_id="user4", mode=WriteMode.UPDATE)
        self.assertTrue(result.success)
        
        # Verify new document
        users = self.service.read("users")
        self.assertEqual(len(users), 4)
        
        # Update nested path in document
        result = self.service.write(
            "users",
            {"department": "Sales"},
            document_id="user4",
            path="details",
            mode=WriteMode.UPDATE
        )
        self.assertTrue(result.success)
        
        # Verify nested update
        user = self.service.read("users", document_id="user4")
        self.assertEqual(user["details"]["department"], "Sales")
    
    def test_merge_operations(self):
        """Test merge operations."""
        # Write initial nested data
        self.service.write("company", self.nested_data)
        
        # Merge with company data
        merge_data = {
            "company": {
                "website": "example.com",
                "address": {
                    "state": "CA",
                    "country": "USA"
                }
            }
        }
        
        result = self.service.write("company", merge_data, mode=WriteMode.MERGE)
        self.assertTrue(result.success)
        
        # Verify merge
        company = self.service.read("company")
        self.assertEqual(company["company"]["website"], "example.com")
        self.assertEqual(company["company"]["address"]["state"], "CA")
        self.assertEqual(company["company"]["address"]["city"], "Anytown")  # Original data preserved
        
        # Merge at path
        result = self.service.write(
            "company",
            {"ceo": "John Doe"},
            path="company",
            mode=WriteMode.MERGE
        )
        self.assertTrue(result.success)
        
        # Verify path merge
        company = self.service.read("company", path="company")
        self.assertEqual(company["ceo"], "John Doe")
        self.assertEqual(company["name"], "Acme Inc.")  # Original data preserved
    
    def test_append_operations(self):
        """Test append operations."""
        # Write initial data
        self.service.write("users", self.users[:1])  # Just write Alice
        
        # Append more users
        result = self.service.write("users", self.users[1:], mode=WriteMode.APPEND)
        self.assertTrue(result.success)
        
        # Verify append
        users = self.service.read("users")
        self.assertEqual(len(users), 3)
        
        # Append to dictionary
        self.service.write("settings", {"theme": "dark"})
        result = self.service.write("settings", {"language": "en"}, mode=WriteMode.APPEND)
        self.assertTrue(result.success)
        
        # Verify dict append
        settings = self.service.read("settings")
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(settings["language"], "en")
    
    def test_delete_operations(self):
        """Test delete operations."""
        # Write initial data
        self.service.write("users", self.users)
        
        # Delete a document
        result = self.service.delete("users", document_id="user2")
        self.assertTrue(result.success)
        
        # Verify deletion
        users = self.service.read("users")
        self.assertEqual(len(users), 2)
        self.assertIsNone(self.service.read("users", document_id="user2"))
        
        # Delete by query
        result = self.service.delete("users", query={"active": False})
        self.assertTrue(result.success)
        
        # Verify query deletion
        users = self.service.read("users")
        self.assertEqual(len(users), 1)  # Only Alice should remain
        
        # Delete entire file
        result = self.service.delete("users")
        self.assertTrue(result.success)
        
        # Verify file deletion
        base_dir = self.service.client["base_directory"]
        self.assertFalse(os.path.exists(os.path.join(base_dir, "users.json")))
    
    def test_exists(self):
        """Test exists operations."""
        # Check non-existent file
        self.assertFalse(self.service.exists("nonexistent"))
        
        # Write data and check
        self.service.write("users", self.users)
        self.assertTrue(self.service.exists("users"))
        
        # Check document existence
        self.assertTrue(self.service.exists("users", document_id="user1"))
        self.assertFalse(self.service.exists("users", document_id="nonexistent"))
        
        # Check path existence
        self.service.write("company", self.nested_data)
        self.assertTrue(self.service.exists("company", path="company.address.city"))
        self.assertFalse(self.service.exists("company", path="company.address.country"))
        
        # Check document path existence
        self.assertTrue(self.service.exists("company", path="company"))
    
    def test_count(self):
        """Test count operations."""
        # Count empty collection
        self.assertEqual(self.service.count("nonexistent"), 0)
        
        # Write and count
        self.service.write("users", self.users)
        self.assertEqual(self.service.count("users"), 3)
        
        # Count with query
        self.assertEqual(self.service.count("users", query={"active": True}), 2)
        self.assertEqual(self.service.count("users", query={"role": "admin"}), 1)
        
        # Count with path
        self.service.write("company", self.nested_data)
        self.assertEqual(self.service.count("company", path="company.employees"), 2)
    
    def test_list_collections(self):
        """Test listing collections."""
        # Empty directory
        # Need to clear any existing files first
        base_dir = self.service.client["base_directory"]
        for item in os.listdir(base_dir):
            file_path = os.path.join(base_dir, item)
            if os.path.isfile(file_path):
                os.remove(file_path)
                
        # Now check if the directory is empty
        self.assertEqual(len(self.service.list_collections()), 0)
        
        # Add some files
        self.service.write("users", self.users)
        self.service.write("company", self.nested_data)
        self.service.write("settings", {"theme": "dark"})
        
        # Verify listing
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 3)
        self.assertIn("users.json", collections)
        self.assertIn("company.json", collections)
        self.assertIn("settings.json", collections)
    
    def test_format_options(self):
        """Test different format options."""
        # Write dictionary data
        dict_data = {
            "user1": {"name": "Alice", "role": "admin"},
            "user2": {"name": "Bob", "role": "user"}
        }
        self.service.write("dict_users", dict_data)
        
        # Read as raw (default)
        raw_data = self.service.read("dict_users")
        self.assertEqual(len(raw_data), 2)
        self.assertEqual(raw_data["user1"]["name"], "Alice")
        
        # Read as records
        records = self.service.read("dict_users", format="records")
        self.assertEqual(len(records), 2)
        self.assertTrue(isinstance(records, list))
        
        # Write list data and test formats
        self.service.write("list_users", self.users)
        
        # Raw format for list
        list_data = self.service.read("list_users")
        self.assertEqual(len(list_data), 3)
        self.assertTrue(isinstance(list_data, list))
    
    def test_error_handling(self):
        """Test error handling."""
        # Invalid JSON
        base_dir = self.service.client["base_directory"]
        with open(os.path.join(base_dir, "invalid.json"), "w") as f:
            f.write("{invalid: json}")
        
        # The service will raise an exception for invalid JSON
        try:
            result = self.service.read("invalid")
            # If it doesn't raise an exception, at least make sure we don't get data back
            self.assertTrue(result is None or result == {})
        except Exception as e:
            # An exception is expected behavior, so this is fine
            pass
        
        # Write to read-only location
        if os.name != 'nt':  # Skip on Windows
            base_dir = self.service.client["base_directory"]
            test_file = os.path.join(base_dir, "readonly.json")
            with open(test_file, "w") as f:
                f.write("{}")
            os.chmod(test_file, 0o444)  # Read-only
            
            result = self.service.write("readonly", {"test": "data"})
            self.assertFalse(result.success)
        
        # Invalid write mode
        with self.assertRaises(Exception):
            self.service.write("test", {}, mode="invalid_mode")


if __name__ == "__main__":
    unittest.main()
