"""
Test the CSV Storage Service implementation.

This test verifies that the CSVStorageService works correctly
with the established patterns and protocols.
"""
import tempfile

from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.csv_service import CSVStorageService
from agentmap.services.storage.types import WriteMode


def test_csv_storage_service():
    """Test basic CSV storage service functionality."""
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Testing with temporary directory: {temp_dir}")
        
        # Create test configuration
        config_data = {
            "storage": {
                "csv": {
                    "provider": "csv",
                    "base_directory": temp_dir,
                    "encoding": "utf-8"
                }
            }
        }
        
        # Create configuration and logging service
        configuration = Configuration(config_data)
        logging_service = LoggingService({})
        
        # Create CSV storage service
        csv_service = CSVStorageService("csv", configuration, logging_service)
        
        # Test health check
        print("Testing health check...")
        assert csv_service.health_check() == True, "Health check should pass"
        print("✓ Health check passed")
        
        # Test write operation
        print("Testing write operation...")
        test_data = [
            {"id": 1, "name": "Alice", "age": 25},
            {"id": 2, "name": "Bob", "age": 30},
            {"id": 3, "name": "Charlie", "age": 35}
        ]
        
        result = csv_service.write("test_users", test_data, mode=WriteMode.WRITE)
        assert result.success == True, f"Write should succeed: {result.error}"
        assert result.rows_written == 3, "Should write 3 rows"
        print("✓ Write operation passed")
        
        # Test read operation
        print("Testing read operation...")
        data = csv_service.read("test_users", format="records")
        assert len(data) == 3, "Should read 3 records"
        assert data[0]["name"] == "Alice", "First record should be Alice"
        print("✓ Read operation passed")
        
        # Test exists operation
        print("Testing exists operation...")
        assert csv_service.exists("test_users") == True, "File should exist"
        assert csv_service.exists("test_users", document_id=1) == True, "Document 1 should exist"
        assert csv_service.exists("test_users", document_id=999) == False, "Document 999 should not exist"
        print("✓ Exists operation passed")
        
        # Test count operation
        print("Testing count operation...")
        count = csv_service.count("test_users")
        assert count == 3, "Should count 3 records"
        print("✓ Count operation passed")
        
        # Test query filtering
        print("Testing query filtering...")
        filtered_data = csv_service.read("test_users", query={"name": "Bob"}, format="records")
        assert len(filtered_data) == 1, "Should find 1 record for Bob"
        assert filtered_data[0]["age"] == 30, "Bob should be 30 years old"
        print("✓ Query filtering passed")
        
        # Test append operation
        print("Testing append operation...")
        new_data = [{"id": 4, "name": "Diana", "age": 28}]
        result = csv_service.write("test_users", new_data, mode=WriteMode.APPEND)
        assert result.success == True, "Append should succeed"
        
        # Verify append worked
        data = csv_service.read("test_users", format="records")
        assert len(data) == 4, "Should now have 4 records"
        print("✓ Append operation passed")
        
        # Test update operation
        print("Testing update operation...")
        update_data = [{"id": 2, "name": "Robert", "age": 31}]  # Update Bob's info
        result = csv_service.write("test_users", update_data, mode=WriteMode.UPDATE)
        assert result.success == True, "Update should succeed"
        
        # Verify update worked
        data = csv_service.read("test_users", document_id=2, format="dict")
        assert data["name"] == "Robert", "Name should be updated to Robert"
        assert data["age"] == 31, "Age should be updated to 31"
        print("✓ Update operation passed")
        
        # Test delete document
        print("Testing delete document...")
        result = csv_service.delete("test_users", document_id=3)
        assert result.success == True, "Delete should succeed"
        
        # Verify delete worked
        count = csv_service.count("test_users")
        assert count == 3, "Should now have 3 records"
        assert csv_service.exists("test_users", document_id=3) == False, "Document 3 should not exist"
        print("✓ Delete document passed")
        
        # Test list collections
        print("Testing list collections...")
        collections = csv_service.list_collections()
        assert "test_users.csv" in collections, "test_users.csv should be in collections"
        print("✓ List collections passed")
        
        # Test delete entire file
        print("Testing delete entire file...")
        result = csv_service.delete("test_users")
        assert result.success == True, "File deletion should succeed"
        assert csv_service.exists("test_users") == False, "File should not exist"
        print("✓ Delete file passed")
        
        print("\\n🎉 All CSV Storage Service tests passed!")


if __name__ == "__main__":
    test_csv_storage_service()
