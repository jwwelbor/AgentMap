#!/usr/bin/env python3
"""
Quick vector service integration verification test.

This test verifies that the vector service can be properly accessed through
the storage manager and that all functionality is preserved after refactoring.
"""

import unittest
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest


class TestVectorServiceIntegration(BaseIntegrationTest):
    """Test vector service integration with storage manager."""
    
    def setup_services(self):
        """Initialize storage services for vector integration testing."""
        super().setup_services()
        
        # Initialize storage manager
        self.storage_manager = self.container.storage_service_manager()
    
    def test_vector_service_is_registered(self):
        """Test that vector service is properly registered."""
        available_providers = self.storage_manager.list_available_providers()
        self.assertIn("vector", available_providers, 
                     "Vector service should be in available providers")
    
    def test_vector_service_can_be_accessed(self):
        """Test that vector service can be accessed through storage manager."""
        vector_service = self.storage_manager.get_service("vector")
        self.assertIsNotNone(vector_service, "Vector service should be accessible")
        
        # Verify it's the correct type
        from agentmap.services.storage.vector_service import VectorStorageService
        self.assertIsInstance(vector_service, VectorStorageService,
                            "Should return VectorStorageService instance")
    
    def test_vector_service_health_check(self):
        """Test that vector service health check works through storage manager."""
        health_results = self.storage_manager.health_check("vector")
        self.assertIn("vector", health_results, 
                     "Health check should include vector service")
        
        # Health check result should be boolean
        self.assertIsInstance(health_results["vector"], bool,
                            "Health check should return boolean")
    
    def test_vector_service_info(self):
        """Test that vector service info is available."""
        service_info = self.storage_manager.get_service_info("vector")
        self.assertIn("vector", service_info, 
                     "Service info should include vector service")
        
        vector_info = service_info["vector"]
        self.assertTrue(vector_info["available"], 
                       "Vector service should be available")
        self.assertEqual(vector_info["type"], "class",
                        "Vector service should be registered as class")
    
    def test_vector_service_functionality_preserved(self):
        """Test that vector service functionality is preserved."""
        vector_service = self.storage_manager.get_service("vector")
        
        # Test basic methods exist
        self.assertTrue(hasattr(vector_service, "read"), 
                       "Vector service should have read method")
        self.assertTrue(hasattr(vector_service, "write"), 
                       "Vector service should have write method")
        self.assertTrue(hasattr(vector_service, "delete"), 
                       "Vector service should have delete method")
        self.assertTrue(hasattr(vector_service, "exists"), 
                       "Vector service should have exists method")
        self.assertTrue(hasattr(vector_service, "health_check"), 
                       "Vector service should have health_check method")
        
        # Test vector-specific methods exist
        self.assertTrue(hasattr(vector_service, "similarity_search"), 
                       "Vector service should have similarity_search method")
        self.assertTrue(hasattr(vector_service, "add_documents"), 
                       "Vector service should have add_documents method")
    
    def test_vector_service_with_other_services(self):
        """Test that vector service works alongside other storage services."""
        # Get multiple services
        vector_service = self.storage_manager.get_service("vector")
        memory_service = self.storage_manager.get_service("memory")
        json_service = self.storage_manager.get_service("json")
        
        # All should be accessible
        self.assertIsNotNone(vector_service, "Vector service should be accessible")
        self.assertIsNotNone(memory_service, "Memory service should be accessible")
        self.assertIsNotNone(json_service, "JSON service should be accessible")
        
        # All should be different instances
        self.assertNotEqual(vector_service, memory_service)
        self.assertNotEqual(vector_service, json_service)
        self.assertNotEqual(memory_service, json_service)


if __name__ == '__main__':
    unittest.main()
