#!/usr/bin/env python3
"""
Test script for VectorStorageService implementation.

This script verifies that the VectorStorageService can be properly instantiated
and follows the StorageService protocol correctly.
"""
import sys
import os

# Add the src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_vector_service_import():
    """Test that VectorStorageService can be imported."""
    try:
        from agentmap.services.storage.vector_service import VectorStorageService
        print("✅ VectorStorageService imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import VectorStorageService: {e}")
        return False

def test_storage_service_registration():
    """Test that VectorStorageService is registered in storage services."""
    try:
        from agentmap.services.storage import VectorStorageService
        print("✅ VectorStorageService available in storage services module")
        return True
    except Exception as e:
        print(f"❌ VectorStorageService not available in storage services: {e}")
        return False

def test_protocol_compliance():
    """Test that VectorStorageService implements the required protocols."""
    try:
        from agentmap.services.storage.vector_service import VectorStorageService
        from agentmap.services.storage.protocols import StorageService
        from agentmap.services.storage.base import BaseStorageService
        
        # Check inheritance
        assert issubclass(VectorStorageService, BaseStorageService)
        print("✅ VectorStorageService inherits from BaseStorageService")
        
        # Check protocol compliance (runtime check)
        from typing import get_type_hints
        
        # Check if it has required methods
        required_methods = ['read', 'write', 'delete', 'exists', 'count', 'list_collections', 'health_check']
        
        for method_name in required_methods:
            if not hasattr(VectorStorageService, method_name):
                print(f"❌ Missing required method: {method_name}")
                return False
        
        print("✅ VectorStorageService implements required StorageService methods")
        return True
        
    except Exception as e:
        print(f"❌ Protocol compliance check failed: {e}")
        return False

def test_vector_specific_methods():
    """Test that VectorStorageService has vector-specific methods."""
    try:
        from agentmap.services.storage.vector_service import VectorStorageService
        
        # Check vector-specific methods
        vector_methods = ['similarity_search', 'add_documents']
        
        for method_name in vector_methods:
            if not hasattr(VectorStorageService, method_name):
                print(f"❌ Missing vector-specific method: {method_name}")
                return False
        
        print("✅ VectorStorageService has vector-specific convenience methods")
        return True
        
    except Exception as e:
        print(f"❌ Vector-specific methods check failed: {e}")
        return False

def test_service_instantiation():
    """Test that VectorStorageService can be instantiated (basic check)."""
    try:
        from agentmap.services.storage.vector_service import VectorStorageService
        from agentmap.config.configuration import Configuration
        from agentmap.logging.service import LoggingService
        
        # Mock configuration and logging service
        class MockConfig:
            def get_value(self, key, default=None):
                # Return basic vector config
                if key.startswith("storage.vector"):
                    return {
                        'provider': 'chroma',
                        'embedding_model': 'openai',
                        'persist_directory': './test_vectors',
                        'k': 4
                    }
                return default
                
            def get_option(self, key, default=None):
                options = {
                    'provider': 'chroma',
                    'embedding_model': 'openai', 
                    'persist_directory': './test_vectors',
                    'k': 4
                }
                return options.get(key, default)
        
        class MockLoggingService:
            def get_class_logger(self, obj):
                import logging
                return logging.getLogger(obj.__class__.__name__)
        
        # Try to instantiate
        config = MockConfig()
        logging_service = MockLoggingService()
        
        service = VectorStorageService("vector", config, logging_service)
        print("✅ VectorStorageService instantiated successfully")
        
        # Test basic properties
        assert service.get_provider_name() == "vector"
        print("✅ Provider name correct")
        
        return True
        
    except Exception as e:
        print(f"❌ Service instantiation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🧪 Testing VectorStorageService Implementation")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_vector_service_import),
        ("Registration Test", test_storage_service_registration),
        ("Protocol Compliance", test_protocol_compliance),
        ("Vector Methods", test_vector_specific_methods),
        ("Instantiation Test", test_service_instantiation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"   {test_name} failed!")
    
    print("\n" + "=" * 50)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! VectorStorageService implementation looks good.")
        print("\n📋 Next Steps:")
        print("   1. ✅ VectorStorageService created and working")
        print("   2. ⏭️  Ready to refactor Vector agents to use the service")
        print("   3. ⏭️  Update vector agents to follow delegation pattern")
        return True
    else:
        print("⚠️  Some tests failed. Please fix the issues before proceeding.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
