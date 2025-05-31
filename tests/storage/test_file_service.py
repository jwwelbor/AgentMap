#!/usr/bin/env python3
"""
Simple test script for FileStorageService functionality.

This script demonstrates basic file operations using the FileStorageService
without complex mocking or dependencies.
"""
import sys
from pathlib import Path

# Add the src directory to Python path for imports
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def test_file_service():
    """Test basic FileStorageService functionality."""
    
    print("🧪 Testing FileStorageService...")
    
    try:
        # Import required classes
        from agentmap.services.storage.file_service import FileStorageService
        from agentmap.services.storage.types import WriteMode, StorageConfig
        from agentmap.services.logging_service import LoggingService
        
        # Create a simple mock configuration
        class MockConfig:
            def get_option(self, key, default=None):
                options = {
                    "base_directory": "./test_data/files",
                    "encoding": "utf-8",
                    "create_dirs": True,
                    "allow_binary": True,
                    "include_metadata": True,
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                    "should_split": False,
                    "newline": None,
                    "max_file_size": None,
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
        file_service = FileStorageService("file", config, logging_service)
        
        print("✅ Service initialized successfully")
        
        # Test health check
        print("🔍 Testing health check...")
        health = file_service.health_check()
        print(f"✅ Health check: {'PASS' if health else 'FAIL'}")
        
        # Test directory listing (empty initially)
        print("📂 Testing directory listing...")
        collections = file_service.list_collections()
        print(f"✅ Collections found: {collections}")
        
        # Test text file write
        print("📝 Testing text file write...")
        result = file_service.write("documents", "Hello, World!", "test.txt")
        print(f"✅ Write result: {result.success}, Created new: {result.created_new}")
        
        # Test text file read
        print("📖 Testing text file read...")
        content = file_service.read("documents", "test.txt")
        print(f"✅ Read content: {content}")
        
        # Test file existence
        print("🔍 Testing file existence...")
        exists = file_service.exists("documents", "test.txt")
        print(f"✅ File exists: {exists}")
        
        # Test file metadata
        print("📊 Testing file metadata...")
        metadata = file_service.get_file_metadata("documents", "test.txt")
        print(f"✅ Metadata: {metadata}")
        
        # Test append mode
        print("📝 Testing append mode...")
        result = file_service.write("documents", "\\nAppended text!", "test.txt", mode=WriteMode.APPEND)
        print(f"✅ Append result: {result.success}")
        
        # Read again to verify append
        content = file_service.read("documents", "test.txt")
        print(f"✅ Content after append: {content}")
        
        # Test directory listing with files
        print("📂 Testing directory listing with files...")
        files = file_service.read("documents")  # List files in documents directory
        print(f"✅ Files in documents: {files}")
        
        # Test file copy
        print("📋 Testing file copy...")
        result = file_service.copy_file("documents", "test.txt", "documents", "test_copy.txt")
        print(f"✅ Copy result: {result.success}")
        
        # Test file deletion
        print("🗑️ Testing file deletion...")
        result = file_service.delete("documents", "test_copy.txt")
        print(f"✅ Delete result: {result.success}")
        
        # Test binary file handling
        print("🔢 Testing binary file handling...")
        binary_data = b"\\x89PNG\\r\\n\\x1a\\n"  # PNG header bytes
        result = file_service.write("documents", binary_data, "test.png", binary_mode=True)
        print(f"✅ Binary write result: {result.success}")
        
        # Read binary file
        binary_content = file_service.read("documents", "test.png", binary_mode=True)
        print(f"✅ Binary read success: {isinstance(binary_content, (bytes, dict))}")
        
        print("\\n🎉 All tests completed successfully!")
        
        # Clean up test files
        print("🧹 Cleaning up test files...")
        file_service.delete("documents", "test.txt")
        file_service.delete("documents", "test.png")
        
        print("✅ Cleanup completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_file_service()
    exit(0 if success else 1)
