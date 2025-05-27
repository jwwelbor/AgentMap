#!/usr/bin/env python3
"""
Test script for Phase 2: Storage Service Protocols

This script verifies that all Phase 2 storage service components work correctly:
- Storage protocols are defined and working
- Base storage service class is functional
- Storage service manager can register and create services
- DI container integration is working
- All imports are circular-dependency free

Run this script to validate Phase 2 implementation.
"""
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, List

# Add src to path for imports
script_dir = Path(__file__).parent
src_dir = script_dir / "src"
sys.path.insert(0, str(src_dir))

def test_imports():
    """Test that all imports work without circular dependencies."""
    print("🔍 Testing imports...")
    
    try:
        # Test storage types
        from agentmap.services.storage.types import (
            WriteMode, StorageResult, StorageConfig,
            StorageServiceError, StorageProviderError
        )
        print("  ✅ Storage types imported successfully")
        
        # Test storage protocols
        from agentmap.services.storage.protocols import (
            StorageReader, StorageWriter, StorageService,
            StorageServiceUser, StorageServiceFactory
        )
        print("  ✅ Storage protocols imported successfully")
        
        # Test base storage service
        from agentmap.services.storage.base import BaseStorageService
        print("  ✅ Base storage service imported successfully")
        
        # Test storage service manager
        from agentmap.services.storage.manager import StorageServiceManager
        print("  ✅ Storage service manager imported successfully")
        
        # Test combined storage module
        from agentmap.services.storage import (
            WriteMode, StorageResult, BaseStorageService, 
            StorageServiceManager, StorageServiceUser
        )
        print("  ✅ Combined storage module imported successfully")
        
        # Test services module exports
        from agentmap.services import (
            StorageServiceManager, StorageServiceUser,
            BaseStorageService, StorageService
        )
        print("  ✅ Services module exports imported successfully")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        traceback.print_exc()
        return False

def test_protocols():
    """Test that protocols are properly defined and checkable."""
    print("\n🔍 Testing protocols...")
    
    try:
        from agentmap.services.storage.protocols import (
            StorageReader, StorageWriter, StorageService, StorageServiceUser
        )
        
        # Test protocol type checking
        class MockService:
            def read(self, collection: str, **kwargs) -> Any:
                return "mock_data"
            
            def write(self, collection: str, data: Any, **kwargs) -> Any:
                return "mock_result"
                
            def delete(self, collection: str, **kwargs) -> Any:
                return "mock_result"
                
            def exists(self, collection: str, **kwargs) -> bool:
                return True
                
            def count(self, collection: str, **kwargs) -> int:
                return 1
                
            def batch_write(self, collection: str, data: List, **kwargs) -> Any:
                return "mock_result"
                
            def get_provider_name(self) -> str:
                return "mock"
                
            def health_check(self) -> bool:
                return True
                
            def list_collections(self) -> List[str]:
                return ["test"]
                
            def create_collection(self, collection: str, schema: Optional[Dict] = None) -> Any:
                return "mock_result"
        
        mock_service = MockService()
        
        # Test isinstance checks
        assert isinstance(mock_service, StorageReader), "Mock service should implement StorageReader"
        assert isinstance(mock_service, StorageWriter), "Mock service should implement StorageWriter"
        assert isinstance(mock_service, StorageService), "Mock service should implement StorageService"
        
        print("  ✅ Protocol type checking works correctly")
        
        # Test StorageServiceUser protocol
        class MockAgent:
            def __init__(self):
                self.storage_service = mock_service
        
        mock_agent = MockAgent()
        assert isinstance(mock_agent, StorageServiceUser), "Mock agent should implement StorageServiceUser"
        
        print("  ✅ StorageServiceUser protocol works correctly")
        return True
        
    except Exception as e:
        print(f"  ❌ Protocol test failed: {e}")
        traceback.print_exc()
        return False

def test_base_service():
    """Test the base storage service implementation."""
    print("\n🔍 Testing base storage service...")
    
    try:
        from agentmap.services.storage.base import BaseStorageService
        from agentmap.services.storage.types import StorageResult, WriteMode
        from agentmap.config.configuration import Configuration
        from agentmap.logging.service import LoggingService
        
        # Create mock configuration and logging service
        config = Configuration({})
        logging_service = LoggingService({})
        
        # Create concrete implementation for testing
        class TestStorageService(BaseStorageService):
            def _initialize_client(self) -> Any:
                return "mock_client"
            
            def _perform_health_check(self) -> bool:
                return True
            
            def read(self, collection: str, **kwargs) -> Any:
                return {"test": "data"}
            
            def write(self, collection: str, data: Any, **kwargs) -> StorageResult:
                return StorageResult(
                    success=True,
                    operation="write",
                    collection=collection
                )
            
            def delete(self, collection: str, **kwargs) -> StorageResult:
                return StorageResult(
                    success=True,
                    operation="delete",
                    collection=collection
                )
        
        # Test service creation
        service = TestStorageService("test", config, logging_service)
        
        # Test basic functionality
        assert service.get_provider_name() == "test", "Provider name should be 'test'"
        assert service.health_check() == True, "Health check should return True"
        
        # Test read operation
        result = service.read("test_collection")
        assert result == {"test": "data"}, "Read should return test data"
        
        # Test write operation
        write_result = service.write("test_collection", {"new": "data"})
        assert write_result.success == True, "Write should succeed"
        assert write_result.operation == "write", "Operation should be 'write'"
        
        # Test batch write (uses default implementation)
        batch_result = service.batch_write("test_collection", [{"item1": "data"}, {"item2": "data"}])
        assert batch_result.success == True, "Batch write should succeed"
        
        print("  ✅ Base storage service works correctly")
        return True
        
    except Exception as e:
        print(f"  ❌ Base service test failed: {e}")
        traceback.print_exc()
        return False

def test_service_manager():
    """Test the storage service manager."""
    print("\n🔍 Testing storage service manager...")
    
    try:
        from agentmap.services.storage.manager import StorageServiceManager
        from agentmap.services.storage.base import BaseStorageService
        from agentmap.services.storage.types import StorageResult
        from agentmap.config.configuration import Configuration
        from agentmap.logging.service import LoggingService
        
        # Create mock configuration and logging service
        config = Configuration({
            "storage": {
                "default_provider": "test",
                "test": {
                    "provider": "test",
                    "connection_string": "mock://test"
                }
            }
        })
        logging_service = LoggingService({})
        
        # Create test service class
        class TestStorageService(BaseStorageService):
            def _initialize_client(self) -> Any:
                return "mock_client"
            
            def _perform_health_check(self) -> bool:
                return True
            
            def read(self, collection: str, **kwargs) -> Any:
                return {"test": "data"}
            
            def write(self, collection: str, data: Any, **kwargs) -> StorageResult:
                return StorageResult(success=True, operation="write")
            
            def delete(self, collection: str, **kwargs) -> StorageResult:
                return StorageResult(success=True, operation="delete")
        
        # Create service manager
        manager = StorageServiceManager(config, logging_service)
        
        # Test provider registration
        manager.register_provider("test", TestStorageService)
        assert manager.is_provider_available("test"), "Test provider should be available"
        
        # Test service creation
        service = manager.get_service("test")
        assert service.get_provider_name() == "test", "Service should have correct provider name"
        
        # Test default service
        default_service = manager.get_default_service()
        assert default_service.get_provider_name() == "test", "Default service should be test provider"
        
        # Test service caching (should return same instance)
        service2 = manager.get_service("test")
        assert service is service2, "Service should be cached"
        
        # Test health check
        health_results = manager.health_check()
        assert "test" in health_results, "Health results should include test provider"
        assert health_results["test"] == True, "Test provider should be healthy"
        
        # Test service info
        info = manager.get_service_info()
        assert "test" in info, "Service info should include test provider"
        assert info["test"]["available"] == True, "Test provider should be available"
        
        print("  ✅ Storage service manager works correctly")
        return True
        
    except Exception as e:
        print(f"  ❌ Service manager test failed: {e}")
        traceback.print_exc()
        return False

def test_di_integration():
    """Test DI container integration."""
    print("\n🔍 Testing DI container integration...")
    
    try:
        from agentmap.di.containers import ApplicationContainer
        
        # Create container and set up config path to None (will use defaults)
        container = ApplicationContainer()
        container.config_path.override(None)
        
        # Test that storage service manager is available
        storage_manager = container.storage_service_manager()
        assert storage_manager is not None, "Storage service manager should be available"
        
        # Test that it's a singleton (same instance on multiple calls)
        storage_manager2 = container.storage_service_manager()
        assert storage_manager is storage_manager2, "Storage service manager should be singleton"
        
        # Test that we can get basic info from the manager
        available_providers = storage_manager.list_available_providers()
        assert isinstance(available_providers, list), "Should return list of providers"
        
        print("  ✅ DI container integration works correctly")
        return True
        
    except Exception as e:
        print(f"  ❌ DI integration test failed: {e}")
        traceback.print_exc()
        return False

def test_type_system():
    """Test that the type system is working correctly."""
    print("\n🔍 Testing type system...")
    
    try:
        from agentmap.services.storage.types import (
            WriteMode, StorageResult, StorageConfig,
            StorageServiceError, StorageProviderError
        )
        
        # Test WriteMode enum
        assert WriteMode.WRITE == "write", "WriteMode.WRITE should equal 'write'"
        assert WriteMode.from_string("update") == WriteMode.UPDATE, "from_string should work"
        
        # Test StorageResult
        result = StorageResult(
            success=True,
            operation="test",
            collection="test_collection",
            data={"test": "value"}
        )
        
        assert result.success == True, "Result success should be True"
        assert result["operation"] == "test", "Result should be subscriptable"
        
        result_dict = result.to_dict()
        assert "success" in result_dict, "to_dict should include success"
        assert "data" in result_dict, "to_dict should include data"
        
        # Test StorageConfig
        config = StorageConfig.from_dict({
            "provider": "test",
            "connection_string": "test://connection",
            "timeout": 30
        })
        
        assert config.provider == "test", "Config provider should be 'test'"
        assert config.timeout == 30, "Config timeout should be 30"
        
        # Test exceptions
        try:
            raise StorageServiceError("Test error", operation="test")
        except StorageServiceError as e:
            assert e.operation == "test", "Exception should preserve operation"
        
        print("  ✅ Type system works correctly")
        return True
        
    except Exception as e:
        print(f"  ❌ Type system test failed: {e}")
        traceback.print_exc()
        return False

def test_backward_compatibility():
    """Test backward compatibility with existing code."""
    print("\n🔍 Testing backward compatibility...")
    
    try:
        # Test that DocumentResult is still available
        from agentmap.services.storage import DocumentResult
        from agentmap.services import DocumentResult as ServicesDocumentResult
        
        # These should be the same type
        assert DocumentResult is ServicesDocumentResult, "DocumentResult should be available in both places"
        
        # Test creating with old name
        result = DocumentResult(success=True, file_path="test.csv")
        assert result.success == True, "DocumentResult should work as before"
        
        print("  ✅ Backward compatibility maintained")
        return True
        
    except Exception as e:
        print(f"  ❌ Backward compatibility test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🚀 Starting Phase 2 Storage Service Tests")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Protocol Tests", test_protocols),
        ("Base Service Tests", test_base_service),
        ("Service Manager Tests", test_service_manager),
        ("DI Integration Tests", test_di_integration),
        ("Type System Tests", test_type_system),
        ("Backward Compatibility Tests", test_backward_compatibility),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            traceback.print_exc()
    
    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Phase 2 tests passed! Storage service protocols are ready.")
        return 0
    else:
        print("❌ Some tests failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
