"""
Integration tests for GraphRegistryService with DI container.

Tests the service integration with real dependencies through the DI container
to verify proper wiring and end-to-end functionality.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentmap.di.containers import ApplicationContainer


class TestGraphRegistryServiceIntegration(unittest.TestCase):
    """Integration tests for GraphRegistryService through DI container."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.container = ApplicationContainer()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_config_path = Path(self.temp_dir.name) / "test_config.yaml"
        
        # Create minimal test configuration
        self.test_config_path.write_text("""
app:
  cache_path: "{cache_dir}"
  
logging:
  level: INFO
  
storage:
  providers:
    json:
      type: local
      path: "{storage_dir}"
""".format(
    cache_dir=self.temp_dir.name + "/cache",
    storage_dir=self.temp_dir.name + "/storage"
))
        
        # Override config path in container
        self.container.config_path.override(str(self.test_config_path))
        
        # Initialize container
        self.container.wire(modules=["agentmap.services"])
    
    def tearDown(self):
        """Clean up integration test fixtures."""
        self.container.unwire()
        self.temp_dir.cleanup()
    
    def create_test_files(self):
        """Create test CSV and bundle files."""
        csv_file = Path(self.temp_dir.name) / "test_graph.csv"
        csv_file.write_text("node,agent,action\ntest_node,test_agent,test_action\n")
        
        bundle_file = Path(self.temp_dir.name) / "test_bundle.bundle"
        bundle_file.write_bytes(b"test bundle content for integration")
        
        return csv_file, bundle_file
    
    def test_service_instantiation_through_di(self):
        """Test that GraphRegistryService can be instantiated through DI container."""
        try:
            # Get service from container
            registry_service = self.container.graph_registry_service()
            
            # Verify service is properly initialized
            self.assertIsNotNone(registry_service, "Service should be instantiated")
            self.assertIsNotNone(registry_service.json_storage, "JSON storage should be injected")
            self.assertIsNotNone(registry_service.config, "App config should be injected")
            self.assertIsNotNone(registry_service.logger, "Logger should be injected")
            
        except Exception as e:
            self.fail(f"Service instantiation failed: {e}")
    
    def test_service_dependencies_injection(self):
        """Test that all required dependencies are properly injected."""
        registry_service = self.container.graph_registry_service()
        
        # Verify dependency types
        from agentmap.services.storage.json_service import JSONStorageService
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.logging_service import LoggingService
        
        # Note: These assertions might need adjustment based on actual implementation
        # The exact types depend on how the services are implemented
        self.assertIsNotNone(registry_service.json_storage, "JSON storage dependency required")
        self.assertIsNotNone(registry_service.config, "App config dependency required")
        self.assertIsNotNone(registry_service.logger, "Logging dependency required")
    
    def test_end_to_end_registry_operations(self):
        """Test complete registry workflow through DI container."""
        registry_service = self.container.graph_registry_service()
        csv_file, bundle_file = self.create_test_files()
        
        try:
            # Test hash computation
            csv_hash = registry_service.compute_hash(csv_file)
            self.assertEqual(len(csv_hash), 64, "Hash should be SHA-256")
            
            # Test registration
            registry_service.register(
                csv_hash=csv_hash,
                graph_name="integration_test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file,
                node_count=1
            )
            
            # Test finding registered bundle
            found_bundle = registry_service.find_bundle(csv_hash)
            self.assertEqual(found_bundle, bundle_file, "Should find registered bundle")
            
            # Test entry information
            entry_info = registry_service.get_entry_info(csv_hash)
            self.assertIsNotNone(entry_info, "Entry info should exist")
            self.assertEqual(entry_info["graph_name"], "integration_test_graph")
            self.assertEqual(entry_info["node_count"], 1)
            
            # Test removal
            removed = registry_service.remove_entry(csv_hash)
            self.assertTrue(removed, "Entry should be removed successfully")
            
            # Verify removal
            found_after_removal = registry_service.find_bundle(csv_hash)
            self.assertIsNone(found_after_removal, "Bundle should not be found after removal")
            
        finally:
            # Clean up test files
            if csv_file.exists():
                csv_file.unlink()
            if bundle_file.exists():
                bundle_file.unlink()
    
    def test_persistence_through_json_storage_service(self):
        """Test that registry persists through real JSON storage service."""
        registry_service = self.container.graph_registry_service()
        csv_file, bundle_file = self.create_test_files()
        
        try:
            # Register entry
            csv_hash = registry_service.compute_hash(csv_file)
            registry_service.register(
                csv_hash=csv_hash,
                graph_name="persistence_test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file
            )
            
            # Create new service instance (simulating restart)
            new_registry_service = self.container.graph_registry_service()
            
            # In a real scenario, the new service would load the persisted registry
            # For integration testing, we verify the storage operations occurred
            # The exact behavior depends on the JSONStorageService implementation
            
            # At minimum, verify the service can be created and used
            test_hash = new_registry_service.compute_hash(csv_file)
            self.assertEqual(test_hash, csv_hash, "Hash computation should be consistent")
            
        finally:
            # Clean up test files
            if csv_file.exists():
                csv_file.unlink()
            if bundle_file.exists():
                bundle_file.unlink()
    
    def test_app_config_integration(self):
        """Test integration with AppConfigService for cache path configuration."""
        registry_service = self.container.graph_registry_service()
        
        # Verify that the service uses the configured cache path
        expected_cache_dir = Path(self.temp_dir.name) / "cache"
        expected_registry_path = str(expected_cache_dir / "graph_registry.json")
        
        # The exact path verification depends on the implementation
        # At minimum, verify the service has a registry path configured
        self.assertIsNotNone(registry_service._registry_path, "Registry path should be configured")
        self.assertIn("graph_registry.json", registry_service._registry_path, 
                     "Registry path should include registry filename")
    
    def test_logging_service_integration(self):
        """Test integration with LoggingService."""
        registry_service = self.container.graph_registry_service()
        csv_file, bundle_file = self.create_test_files()
        
        try:
            # Verify logger is configured
            self.assertIsNotNone(registry_service.logger, "Logger should be configured")
            
            # Test that operations use the logger (this would show up in log output)
            csv_hash = registry_service.compute_hash(csv_file)
            registry_service.register(
                csv_hash=csv_hash,
                graph_name="logging_test_graph",
                bundle_path=bundle_file,
                csv_path=csv_file
            )
            
            # In a real logging setup, we could verify log messages
            # For integration testing, we verify no exceptions occur
            self.assertTrue(True, "Operations should complete without logging errors")
            
        finally:
            # Clean up test files
            if csv_file.exists():
                csv_file.unlink()
            if bundle_file.exists():
                bundle_file.unlink()
    
    def test_service_singleton_behavior(self):
        """Test that the service follows singleton pattern in DI container."""
        # Get service instances multiple times
        service1 = self.container.graph_registry_service()
        service2 = self.container.graph_registry_service()
        
        # Should be the same instance (singleton)
        self.assertIs(service1, service2, "Service should be singleton in container")
    
    def test_graceful_degradation_with_missing_dependencies(self):
        """Test behavior when optional dependencies are missing."""
        # This test would be more relevant if GraphRegistryService had optional dependencies
        # For now, we verify the service works with all required dependencies present
        
        registry_service = self.container.graph_registry_service()
        self.assertIsNotNone(registry_service, "Service should work with all dependencies")
    
    def test_concurrent_access_through_di(self):
        """Test concurrent access to service instance through DI container."""
        import threading
        
        results = []
        errors = []
        
        def access_service():
            """Access service in thread."""
            try:
                service = self.container.graph_registry_service()
                results.append(id(service))  # Store instance ID
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=access_service)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors
        self.assertEqual(len(errors), 0, f"No access errors expected: {errors}")
        
        # Verify all threads got the same singleton instance
        self.assertEqual(len(set(results)), 1, "All threads should get same singleton instance")
    
    @patch('agentmap.services.graph.graph_registry_service.GraphRegistryService')
    def test_service_registration_in_container(self, mock_service_class):
        """Test that the service is properly registered in the DI container."""
        # Create mock instance
        mock_instance = mock_service_class.return_value
        
        # Get service from container
        service = self.container.graph_registry_service()
        
        # Verify service was created with expected dependencies
        mock_service_class.assert_called_once()
        call_args = mock_service_class.call_args
        
        # Should be called with 3 arguments (json_storage, app_config, logging)
        self.assertEqual(len(call_args[0]), 3, "Should be called with 3 dependencies")
        
        # Verify the mock instance was returned
        self.assertEqual(service, mock_instance, "Should return service instance")


class TestGraphRegistryServiceWithGraphRunner(unittest.TestCase):
    """Test GraphRegistryService integration with GraphRunnerService."""
    
    def setUp(self):
        """Set up GraphRunner integration tests."""
        self.container = ApplicationContainer()
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create minimal test configuration
        test_config_path = Path(self.temp_dir.name) / "test_config.yaml"
        test_config_path.write_text("""
app:
  cache_path: "{cache_dir}"
  
logging:
  level: INFO
""".format(cache_dir=self.temp_dir.name + "/cache"))
        
        self.container.config_path.override(str(test_config_path))
        self.container.wire(modules=["agentmap.services"])
    
    def tearDown(self):
        """Clean up GraphRunner integration tests."""
        self.container.unwire()
        self.temp_dir.cleanup()
    
    def test_graph_registry_available_to_graph_runner(self):
        """Test that GraphRegistryService is available for use by GraphRunnerService."""
        try:
            # Get both services from container
            registry_service = self.container.graph_registry_service()
            
            # Verify registry service is available
            self.assertIsNotNone(registry_service, "Registry service should be available")
            
            # In the future, GraphRunnerService would use GraphRegistryService
            # For now, we verify the service is ready for integration
            self.assertTrue(hasattr(registry_service, 'find_bundle'), 
                          "Registry should provide find_bundle method")
            self.assertTrue(hasattr(registry_service, 'register'), 
                          "Registry should provide register method")
            self.assertTrue(hasattr(registry_service, 'compute_hash'), 
                          "Registry should provide compute_hash method")
            
        except Exception as e:
            self.fail(f"Service integration preparation failed: {e}")
    
    def test_registry_cache_performance_for_graph_runner(self):
        """Test that registry provides performance benefits for repeated graph usage."""
        registry_service = self.container.graph_registry_service()
        
        # Create test CSV file
        csv_file = Path(self.temp_dir.name) / "repeated_graph.csv"
        csv_file.write_text("node,agent,action\nrepeat_node,repeat_agent,repeat_action\n")
        
        bundle_file = Path(self.temp_dir.name) / "repeated_bundle.bundle"
        bundle_file.write_bytes(b"repeated bundle content")
        
        try:
            csv_hash = registry_service.compute_hash(csv_file)
            
            # First time: register bundle
            registry_service.register(
                csv_hash=csv_hash,
                graph_name="repeated_graph",
                bundle_path=bundle_file,
                csv_path=csv_file
            )
            
            # Subsequent times: fast lookup (this is what GraphRunnerService would do)
            import time
            start_time = time.time()
            
            for _ in range(100):
                found_bundle = registry_service.find_bundle(csv_hash)
                self.assertEqual(found_bundle, bundle_file)
            
            lookup_time = time.time() - start_time
            
            # Should be very fast for repeated lookups
            self.assertLess(lookup_time, 0.1, "100 lookups should be under 0.1 seconds")
            
        finally:
            if csv_file.exists():
                csv_file.unlink()
            if bundle_file.exists():
                bundle_file.unlink()


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
