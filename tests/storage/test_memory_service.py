#!/usr/bin/env python3
"""
Simple test script for MemoryStorageService functionality.

This script demonstrates basic in-memory storage operations using the MemoryStorageService
without complex mocking or dependencies.
"""
import sys
from pathlib import Path

# Add the src directory to Python path for imports
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def test_memory_service():
    """Test basic MemoryStorageService functionality."""
    
    print("🧪 Testing MemoryStorageService...")
    
    try:
        # Import required classes
        from agentmap.services.storage.memory_service import MemoryStorageService
        from agentmap.services.storage.types import WriteMode, StorageConfig
        from agentmap.services.logging_service import LoggingService
        
        # Create a simple mock configuration
        class MockConfig:
            def get_option(self, key, default=None):
                options = {
                    "max_collections": 100,
                    "max_documents_per_collection": 1000,
                    "max_document_size": 1048576,
                    "auto_generate_ids": True,
                    "deep_copy_on_read": True,
                    "deep_copy_on_write": True,
                    "track_metadata": True,
                    "case_sensitive_collections": True,
                    "persistence_file": None,
                }
                return options.get(key, default)
        
        # Create a simple mock logging service
        class MockLoggingService:
            def get_class_logger(self, cls):
                import logging
                return logging.getLogger(cls.__class__.__name__)
        
        # Initialize the service
        config = MockConfig()
        logging_service = MockLoggingService()
        memory_service = MemoryStorageService("memory", config, logging_service)
        
        print("✅ Service initialized successfully")
        
        # Test health check
        print("🔍 Testing health check...")
        health = memory_service.health_check()
        print(f"✅ Health check: {'PASS' if health else 'FAIL'}")
        
        # Test collections listing (empty initially)
        print("📂 Testing collections listing...")
        collections = memory_service.list_collections()
        print(f"✅ Collections found: {collections}")
        
        # Test basic document operations
        print("📝 Testing document creation...")
        result = memory_service.write("users", {"name": "Alice", "age": 30}, "user1")
        print(f"✅ Write result: {result.success}, Created new: {result.created_new}")
        
        # Test auto-generated ID
        print("📝 Testing auto-generated ID...")
        result = memory_service.write("users", {"name": "Bob", "age": 25})
        print(f"✅ Auto-ID write result: {result.success}, Document ID: {result.document_id}")
        
        # Test document reading
        print("📖 Testing document reading...")
        user = memory_service.read("users", "user1")
        print(f"✅ Read user1: {user}")
        
        # Test collection reading
        print("📖 Testing collection reading...")
        all_users = memory_service.read("users")
        print(f"✅ All users: {all_users}")
        
        # Test query filtering
        print("🔍 Testing query filtering...")
        young_users = memory_service.read("users", query={"age": 25})
        print(f"✅ Young users (age=25): {young_users}")
        
        # Test document existence
        print("🔍 Testing document existence...")
        exists = memory_service.exists("users", "user1")
        print(f"✅ User1 exists: {exists}")
        
        # Test collection existence
        exists = memory_service.exists("users")
        print(f"✅ Users collection exists: {exists}")
        
        # Test document counting
        print("📊 Testing document counting...")
        count = memory_service.count("users")
        print(f"✅ Total users: {count}")
        
        # Test path-based operations
        print("📝 Testing path-based operations...")
        result = memory_service.write("users", "New York", "user1", path="address.city")
        print(f"✅ Path write result: {result.success}")
        
        # Read with path
        city = memory_service.read("users", "user1", path="address.city")
        print(f"✅ User1 city: {city}")
        
        # Test update mode
        print("📝 Testing UPDATE mode...")
        result = memory_service.write("users", {"email": "alice@example.com"}, "user1", mode=WriteMode.UPDATE)
        print(f"✅ Update result: {result.success}")
        
        # Verify update
        updated_user = memory_service.read("users", "user1")
        print(f"✅ Updated user1: {updated_user}")
        
        # Test APPEND mode
        print("📝 Testing APPEND mode...")
        result = memory_service.write("tags", ["python"], "user1", mode=WriteMode.APPEND)
        print(f"✅ Append result: {result.success}")
        
        result = memory_service.write("tags", ["developer"], "user1", mode=WriteMode.APPEND)
        print(f"✅ Second append result: {result.success}")
        
        tags = memory_service.read("tags", "user1")
        print(f"✅ User1 tags: {tags}")
        
        # Test MERGE mode
        print("📝 Testing MERGE mode...")
        result = memory_service.write("users", {"status": "active", "age": 31}, "user1", mode=WriteMode.MERGE)
        print(f"✅ Merge result: {result.success}")
        
        merged_user = memory_service.read("users", "user1")
        print(f"✅ Merged user1: {merged_user}")
        
        # Test batch operations
        print("📝 Testing batch operations...")
        batch_data = [
            {"name": "Charlie", "age": 35},
            {"name": "Diana", "age": 28},
            {"name": "Eve", "age": 22}
        ]
        
        for i, user_data in enumerate(batch_data):
            result = memory_service.write("users", user_data, f"user{i+10}")
            
        # Count all users
        total_users = memory_service.count("users")
        print(f"✅ Total users after batch: {total_users}")
        
        # Test query with sorting and pagination
        print("📊 Testing advanced queries...")
        result = memory_service.read("users", query={"limit": 2, "offset": 1, "sort": "age", "order": "desc"})
        print(f"✅ Paginated users: {len(result) if result else 0} users returned")
        
        # Test batch delete with query
        print("🗑️ Testing batch delete...")
        delete_result = memory_service.delete("users", query={"age": 22})
        print(f"✅ Batch delete result: {delete_result.success}, Affected: {delete_result.total_affected}")
        
        # Test statistics
        print("📊 Testing statistics...")
        stats = memory_service.get_stats()
        print(f"✅ Service stats: {stats}")
        
        # Test individual document deletion
        print("🗑️ Testing document deletion...")
        result = memory_service.delete("users", "user1")
        print(f"✅ Delete result: {result.success}")
        
        # Verify deletion
        exists = memory_service.exists("users", "user1")
        print(f"✅ User1 exists after delete: {exists}")
        
        # Test collection deletion
        print("🗑️ Testing collection deletion...")
        result = memory_service.delete("tags")
        print(f"✅ Collection delete result: {result.success}")
        
        # Final statistics
        final_stats = memory_service.get_stats()
        print(f"✅ Final stats: {final_stats}")
        
        print("\\n🎉 All tests completed successfully!")
        
        # Optional: Test clear all
        print("🧹 Testing clear all...")
        result = memory_service.clear_all()
        print(f"✅ Clear all result: {result.success}, Collections cleared: {result.get('collections_cleared', 0)}")
        
        print("✅ Memory storage test completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_memory_service()
    exit(0 if success else 1)
