"""
Test suite for JSONStorageService.

This module provides comprehensive tests for the JSON storage service implementation,
verifying all CRUD operations, path-based access, and query filtering.
"""
import os
import sys
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.agentmap.services.storage.types import WriteMode, StorageConfig
from agentmap.services.storage.json_service import JSONStorageService
from agentmap.services.logging_service import LoggingService
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
    