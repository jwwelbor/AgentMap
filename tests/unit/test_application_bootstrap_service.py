"""
Comprehensive tests for ApplicationBootstrapService.

Tests fast path (with bundle), slow path (without bundle), and different bootstrap methods
for various CLI commands. Follows TDD approach with comprehensive test coverage for
all application initialization scenarios.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from agentmap.services.application_bootstrap_service import ApplicationBootstrapService
from tests.utils.mock_service_factory import MockServiceFactory


class TestApplicationBootstrapService(unittest.TestCase):
    """Comprehensive tests for ApplicationBootstrapService."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        
        # Create mock services using MockServiceFactory pattern
        self.config_service = self.mock_factory.create_mock_app_config_service()
        self.logging_service = self.mock_factory.create_mock_logging_service()
        self.storage_service = Mock()  # JSONStorageService - create manually since no factory method
        self.graph_registry = Mock()  # GraphRegistryService - create manually
        self.graph_bundle_service = Mock()  # GraphBundleService - create manually  
        self.container_factory = Mock()  # ContainerFactory - create manually
        
        # Create the service under test
        # Note: This follows TDD - the service doesn't exist yet, but tests define the interface
        self.bootstrap_service = ApplicationBootstrapService(
            self.config_service,
            self.logging_service,
            self.storage_service,
            self.graph_registry,
            self.graph_bundle_service,
            self.container_factory
        )
    
    def test_bootstrap_for_csv_fast_path_with_existing_bundle(self):
        """Test fast path when bundle exists with service registry."""
        # Arrange
        bundle = self._create_mock_graph_bundle(
            graph_id="test",
            agents=[self._create_mock_agent_config("agent1"), self._create_mock_agent_config("agent2")],
            edges=[],
            csv_path="test.csv",
            service_registry={"agent1": {}, "agent2": {}}
        )
        self.graph_registry.get_bundle_for_csv.return_value = bundle
        mock_container = Mock()
        self.container_factory.create_from_registry.return_value = mock_container
        
        # Act
        result_container, result_bundle = self.bootstrap_service.bootstrap_for_csv("test.csv")
        
        # Assert
        self.assertEqual(result_bundle, bundle)
        self.assertEqual(result_container, mock_container)
        self.container_factory.create_from_registry.assert_called_once_with(bundle.service_registry)
        self.graph_bundle_service.create_bundle_from_csv.assert_not_called()
        
    def test_bootstrap_for_csv_slow_path_creates_bundle(self):
        """Test slow path when no bundle exists - creates new bundle."""
        # Arrange
        self.graph_registry.get_bundle_for_csv.return_value = None
        mock_container = Mock()
        mock_container.get_registry_snapshot.return_value = {"all": "services"}
        self.container_factory.create_full_container.return_value = mock_container
        
        new_bundle = self._create_mock_graph_bundle("test", [], [], "test.csv")
        self.graph_bundle_service.create_bundle_from_csv.return_value = new_bundle
        
        # Act
        result_container, result_bundle = self.bootstrap_service.bootstrap_for_csv("test.csv")
        
        # Assert
        self.assertEqual(result_container, mock_container)
        self.assertEqual(result_bundle.service_registry, {"all": "services"})
        self.graph_bundle_service.create_bundle_from_csv.assert_called_once_with("test.csv")
        self.graph_registry.save_bundle.assert_called_once()
        
    def test_bootstrap_for_csv_updates_bundle_with_registry_snapshot(self):
        """Test that slow path updates bundle with container registry snapshot."""
        # Arrange
        self.graph_registry.get_bundle_for_csv.return_value = None
        mock_container = Mock()
        registry_snapshot = {"llm_service": {"type": "openai"}, "storage_service": {"type": "json"}}
        mock_container.get_registry_snapshot.return_value = registry_snapshot
        self.container_factory.create_full_container.return_value = mock_container
        
        new_bundle = self._create_mock_graph_bundle("test", [], [], "test.csv")
        self.graph_bundle_service.create_bundle_from_csv.return_value = new_bundle
        
        # Act
        result_container, result_bundle = self.bootstrap_service.bootstrap_for_csv("test.csv")
        
        # Assert - Bundle should be updated with registry snapshot
        self.assertEqual(result_bundle.service_registry, registry_snapshot)
        
        # Verify save_bundle was called with updated bundle
        self.graph_registry.save_bundle.assert_called_once()
        saved_bundle_call = self.graph_registry.save_bundle.call_args[0][0]
        self.assertEqual(saved_bundle_call.service_registry, registry_snapshot)
    
    def test_bootstrap_for_scaffold_creates_minimal_container(self):
        """Test scaffold bootstrap creates minimal container for template processing."""
        # Arrange
        mock_container = Mock()
        self.container_factory.create_scaffold_container.return_value = mock_container
        
        # Act
        result = self.bootstrap_service.bootstrap_for_scaffold("template.yaml")
        
        # Assert
        self.assertEqual(result, mock_container)
        self.container_factory.create_scaffold_container.assert_called_once()
    
    def test_bootstrap_for_validation_creates_validation_container(self):
        """Test validation bootstrap creates validation-specific container."""
        # Arrange
        mock_container = Mock()
        self.container_factory.create_validation_container.return_value = mock_container
        
        # Act
        result = self.bootstrap_service.bootstrap_for_validation()
        
        # Assert
        self.assertEqual(result, mock_container)
        self.container_factory.create_validation_container.assert_called_once()
    
    def test_bootstrap_for_csv_handles_missing_csv_file(self):
        """Test error handling for missing CSV files."""
        # Arrange
        self.graph_registry.get_bundle_for_csv.side_effect = FileNotFoundError("CSV file not found")
        
        # Act & Assert
        with self.assertRaises(FileNotFoundError) as context:
            self.bootstrap_service.bootstrap_for_csv("nonexistent.csv")
        
        self.assertIn("CSV file not found", str(context.exception))
    
    def test_bootstrap_for_csv_handles_bundle_creation_failure(self):
        """Test error handling when bundle creation fails."""
        # Arrange
        self.graph_registry.get_bundle_for_csv.return_value = None
        self.container_factory.create_full_container.return_value = Mock()
        self.graph_bundle_service.create_bundle_from_csv.side_effect = ValueError("Invalid CSV format")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.bootstrap_service.bootstrap_for_csv("invalid.csv")
        
        self.assertIn("Invalid CSV format", str(context.exception))
    
    def test_bootstrap_for_csv_handles_container_creation_failure(self):
        """Test error handling when container creation fails."""
        # Arrange
        bundle = self._create_mock_graph_bundle("test", [], [], "test.csv", {"agent1": {}})
        self.graph_registry.get_bundle_for_csv.return_value = bundle
        self.container_factory.create_from_registry.side_effect = RuntimeError("Container creation failed")
        
        # Act & Assert
        with self.assertRaises(RuntimeError) as context:
            self.bootstrap_service.bootstrap_for_csv("test.csv")
        
        self.assertIn("Container creation failed", str(context.exception))
    
       
    def test_bootstrap_for_csv_caches_bundle_after_creation(self):
        """Test that newly created bundles are cached for future use."""
        # Arrange
        self.graph_registry.get_bundle_for_csv.return_value = None
        mock_container = Mock()
        registry_snapshot = {"cached": "services"}
        mock_container.get_registry_snapshot.return_value = registry_snapshot
        self.container_factory.create_full_container.return_value = mock_container
        
        new_bundle = self._create_mock_graph_bundle("test", [], [], "test.csv")
        self.graph_bundle_service.create_bundle_from_csv.return_value = new_bundle
        
        # Act
        result_container, result_bundle = self.bootstrap_service.bootstrap_for_csv("test.csv")
        
        # Assert - Bundle should be saved with updated service registry
        self.graph_registry.save_bundle.assert_called_once()
        saved_bundle = self.graph_registry.save_bundle.call_args[0][0]
        
        # Verify the bundle was updated with the registry snapshot before saving
        self.assertEqual(saved_bundle.service_registry, registry_snapshot)
        self.assertEqual(result_bundle.service_registry, registry_snapshot)
    
    def test_bootstrap_service_dependency_injection(self):
        """Test that all required dependencies are properly injected."""
        # Verify all dependencies are available
        self.assertIsNotNone(self.bootstrap_service.config_service)
        self.assertIsNotNone(self.bootstrap_service.logging_service)
        self.assertIsNotNone(self.bootstrap_service.storage_service)
        self.assertIsNotNone(self.bootstrap_service.graph_registry)
        self.assertIsNotNone(self.bootstrap_service.graph_bundle_service)
        self.assertIsNotNone(self.bootstrap_service.container_factory)
    
    def test_bootstrap_service_logger_initialization(self):
        """Test that class logger is properly initialized."""
        # Verify logger was requested for this class
        self.logging_service.get_class_logger.assert_called_once_with(self.bootstrap_service)
    
    def test_fast_path_performance_optimization(self):
        """Test that fast path bypasses expensive operations."""
        # Arrange
        bundle = self._create_mock_graph_bundle("test", [], [], "test.csv", {"fast": "path"})
        self.graph_registry.get_bundle_for_csv.return_value = bundle
        self.container_factory.create_from_registry.return_value = Mock()
        
        # Act
        self.bootstrap_service.bootstrap_for_csv("test.csv")
        
        # Assert - Fast path should not call expensive operations
        self.container_factory.create_full_container.assert_not_called()
        self.graph_bundle_service.create_bundle_from_csv.assert_not_called()
        
        # Fast path should use lightweight registry-based container creation
        self.container_factory.create_from_registry.assert_called_once()
    
    def test_slow_path_comprehensive_initialization(self):
        """Test that slow path performs complete initialization."""
        # Arrange
        self.graph_registry.get_bundle_for_csv.return_value = None
        mock_container = Mock()
        mock_container.get_registry_snapshot.return_value = {"complete": "registry"}
        self.container_factory.create_full_container.return_value = mock_container
        
        new_bundle = self._create_mock_graph_bundle("test", [], [], "test.csv")
        self.graph_bundle_service.create_bundle_from_csv.return_value = new_bundle
        
        # Act
        self.bootstrap_service.bootstrap_for_csv("test.csv")
        
        # Assert - Slow path should perform complete initialization
        self.container_factory.create_full_container.assert_called_once()
        self.graph_bundle_service.create_bundle_from_csv.assert_called_once()
        self.graph_registry.save_bundle.assert_called_once()
        
        # Should not use fast path
        self.container_factory.create_from_registry.assert_not_called()
    
    def _create_mock_agent_config(self, agent_name: str) -> Mock:
        """Create a mock AgentConfig for testing."""
        mock_agent = Mock()
        mock_agent.name = agent_name
        mock_agent.type = "default"
        mock_agent.config = {}
        return mock_agent
    
    def _create_mock_graph_bundle(self, graph_id: str, agents: list = None, edges: list = None, 
                                  csv_path: str = None, service_registry: dict = None) -> Mock:
        """Create a mock GraphBundle for testing."""
        mock_bundle = Mock()
        mock_bundle.graph_id = graph_id
        mock_bundle.agents = agents or []
        mock_bundle.edges = edges or []
        mock_bundle.csv_path = csv_path
        mock_bundle.service_registry = service_registry or {}
        return mock_bundle
    



if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
