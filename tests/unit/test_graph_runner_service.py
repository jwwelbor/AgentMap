"""
TDD Tests for Simplified GraphRunnerService.

Tests for simplified GraphRunnerService that takes a Bundle parameter instead of CSV path.
Service should only orchestrate, with no bundle checking or creation logic.
"""

import unittest
from unittest.mock import Mock
from datetime import datetime

# Test utilities
from tests.utils.mock_service_factory import MockServiceFactory

# Import models
from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.execution_result import ExecutionResult
from agentmap.models.node import Node


class TestGraphRunnerService(unittest.TestCase):
    """Tests for simplified GraphRunnerService orchestration."""
    
    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        
        # Create mock dependencies for simplified service
        self.graph_bootstrap = Mock()  # GraphBootstrapService
        self.graph_execution = Mock()  # GraphExecutionService 
        self.logging_service = self.mock_factory.create_mock_logging_service()
        
        # Import the actual service to test
        from agentmap.services.graph.graph_runner_service import GraphRunnerService
        
        # Create simplified service instance (will need to be refactored to match)
        self.runner = GraphRunnerService(
            graph_bootstrap_service=self.graph_bootstrap,
            graph_execution_service=self.graph_execution,
            logging_service=self.logging_service
        )
        
        # Create test bundle with realistic structure
        self.bundle = GraphBundle(
            graph_name="test_graph",
            nodes={
                "agent1": Node(name="agent1", agent_type="test_agent"),
                "agent2": Node(name="agent2", agent_type="test_agent")
            },
            csv_hash="test_hash_12345678",
            bundle_format="metadata-v1"
        )
    
    def test_run_takes_bundle_not_csv(self):
        """Test that run() method takes Bundle parameter, not CSV path."""
        # Arrange
        mock_agents = [Mock(), Mock()]
        self.graph_bootstrap.bootstrap_agents.return_value = mock_agents
        mock_result = ExecutionResult(
            graph_name="test_graph",
            final_state={},
            execution_summary=Mock(),
            success=True,
            total_duration=1.5,
            compiled_from="bundle"
        )
        self.graph_execution.execute.return_value = mock_result
        
        # Act - Should take Bundle, not CSV path!
        result = self.runner.run(self.bundle)
        
        # Assert
        self.assertEqual(result, mock_result)
        self.graph_bootstrap.bootstrap_agents.assert_called_once_with(self.bundle)
        self.graph_execution.execute.assert_called_once_with(self.bundle, mock_agents)
    
    def test_no_bundle_checking_logic(self):
        """Verify simplified service has no CSV parsing or bundle creation dependencies."""
        # GraphRunnerService should NOT have these dependencies in simplified version:
        with self.assertRaises(AttributeError):
            self.runner.csv_parser
        with self.assertRaises(AttributeError):
            self.runner.graph_registry
        with self.assertRaises(AttributeError):
            self.runner.graph_bundle_service
        with self.assertRaises(AttributeError):
            self.runner.agent_factory
        with self.assertRaises(AttributeError):
            self.runner.app_config_service
    
    def test_simple_orchestration_only(self):
        """Verify service only orchestrates, no business logic."""
        # Arrange
        self.graph_bootstrap.bootstrap_agents.return_value = []
        failed_result = ExecutionResult(
            graph_name="test_graph", 
            final_state={},
            execution_summary=Mock(),
            success=False,
            total_duration=0.1,
            compiled_from="bundle"
        )
        self.graph_execution.execute.return_value = failed_result
        
        # Act
        result = self.runner.run(self.bundle)
        
        # Assert - just passes through, no retry logic or modification
        self.assertFalse(result.success)
        self.assertEqual(result, failed_result)
        
        # Verify simple delegation pattern
        self.graph_bootstrap.bootstrap_agents.assert_called_once_with(self.bundle)
        self.graph_execution.execute.assert_called_once_with(self.bundle, [])
    
    def test_handles_execution_errors_gracefully(self):
        """Test error handling - should log but not swallow exceptions."""
        # Arrange
        self.graph_bootstrap.bootstrap_agents.side_effect = Exception("Bootstrap failed")
        
        # Act & Assert
        with self.assertRaises(Exception) as context:
            self.runner.run(self.bundle)
        
        self.assertIn("Bootstrap failed", str(context.exception))
        
        # Should call bootstrap but not execution due to exception
        self.graph_bootstrap.bootstrap_agents.assert_called_once_with(self.bundle)
        self.graph_execution.execute.assert_not_called()
    
    def test_execution_service_error_handling(self):
        """Test error handling when execution service fails."""
        # Arrange
        mock_agents = [Mock()]
        self.graph_bootstrap.bootstrap_agents.return_value = mock_agents
        self.graph_execution.execute.side_effect = Exception("Execution failed")
        
        # Act & Assert
        with self.assertRaises(Exception) as context:
            self.runner.run(self.bundle)
        
        self.assertIn("Execution failed", str(context.exception))
        
        # Should complete bootstrap before execution fails
        self.graph_bootstrap.bootstrap_agents.assert_called_once_with(self.bundle)
        self.graph_execution.execute.assert_called_once_with(self.bundle, mock_agents)
    
    def test_minimal_dependencies_only(self):
        """Verify service only has essential orchestration dependencies."""
        # Should have only these dependencies for orchestration
        self.assertIsNotNone(self.runner.graph_bootstrap)
        self.assertIsNotNone(self.runner.graph_execution) 
        self.assertIsNotNone(self.runner.logger)
        
        # Should NOT have complex dependencies from original service
        dependency_attrs_that_should_not_exist = [
            'csv_parser', 'graph_registry', 'graph_bundle_service', 'agent_factory',
            'config', 'execution_tracking_service', 'state_adapter_service',
            'host_protocol_configuration', '_host_services_available'
        ]
        
        for attr in dependency_attrs_that_should_not_exist:
            with self.assertRaises(AttributeError, msg=f"Simplified service should not have {attr}"):
                getattr(self.runner, attr)


if __name__ == '__main__':
    unittest.main()
