"""
Enhanced Generated Test Template for ExecutionTrackingService.

This test template demonstrates the enhanced return type analysis capabilities
of the improved Service Interface Auditor.
Refactored to use pure Mock objects for cleaner, more maintainable tests.
"""

import unittest
from unittest.mock import Mock

from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.models.execution.summary import ExecutionSummary
from agentmap.models.execution.tracker import ExecutionTracker, NodeExecution

from tests.utils.mock_service_factory import MockServiceFactory


class TestExecutionTrackingServiceEnhanced(unittest.TestCase):
    """Enhanced unit tests for ExecutionTrackingService with return type awareness and pure Mock objects."""

    def setUp(self):
        """Set up test fixtures with pure Mock objects."""
        # Create pure Mock objects - clean and flexible
        self.mock_config_service = Mock()
        self.mock_logging_service = Mock()
        
        # Configure mock logger to behave like real logger
        self.mock_logger = Mock()
        self.mock_logger.name = "ExecutionTrackingService"
        self.mock_logging_service.get_class_logger.return_value = self.mock_logger
        
        # Configure default tracking config (can be overridden per test)
        self.mock_config_service.get_tracking_config.return_value = {
            "track_inputs": True,
            "track_outputs": True,
            "enabled": True
        }

        # Create service instance with mocked dependencies
        self.service = ExecutionTrackingService(
            app_config_service=self.mock_config_service,
            logging_service=self.mock_logging_service
        )

    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify service is properly configured
        self.assertIsNotNone(self.service)
        self.assertEqual(self.service.logger.name, "ExecutionTrackingService")

        # Verify dependencies were called correctly
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
        self.mock_logger.info.assert_called_with("[ExecutionTrackingService] Initialized")

    def test_create_tracker_method_exists(self):
        """Test that create_tracker method exists and is callable."""
        self.assertTrue(hasattr(self.service, "create_tracker"))
        self.assertTrue(callable(getattr(self.service, "create_tracker")))

    def test_create_tracker_returns_expected_type(self):
        """Test that create_tracker returns expected type: ExecutionTracker."""
        # Method signature: def create_tracker(self) -> ExecutionTracker
        # Configure specific tracking config for this test
        self.mock_config_service.get_tracking_config.return_value = {
            "track_inputs": True,
            "track_outputs": True,
            "enabled": True
        }

        # Call the method
        result = self.service.create_tracker()

        # Verify ExecutionTracker return type and basic structure
        from agentmap.models.execution.tracker import ExecutionTracker
        self.assertIsInstance(result, ExecutionTracker)
        self.assertIsNotNone(result.start_time)
        self.assertIsInstance(result.node_executions, list)
        self.assertTrue(result.track_inputs)
        self.assertTrue(result.track_outputs)
        self.assertFalse(result.minimal_mode)
        
        # Verify the config method was called
        self.mock_config_service.get_tracking_config.assert_called_once()

    def test_record_node_start_method_exists(self):
        """Test that record_node_start method exists and is callable."""
        self.assertTrue(hasattr(self.service, "record_node_start"))
        self.assertTrue(callable(getattr(self.service, "record_node_start")))

    def test_record_node_start_returns_expected_type(self):
        """Test that record_node_start returns expected type: None."""
        # Method signature: def record_node_start(self, tracker: ExecutionTracker, node_name: str, inputs: Optional[Dict[str, Any]] = None)
        
        # Create a tracker instance for testing
        tracker = self.service.create_tracker()
        
        # Call the method with required parameters
        result = self.service.record_node_start(tracker=tracker, node_name="test_node")
        
        # Method returns None
        self.assertIsNone(result)
        
        # Verify the tracker was updated
        self.assertEqual(len(tracker.node_executions), 1)
        self.assertEqual(tracker.node_executions[0].node_name, "test_node")
        self.assertIsNotNone(tracker.node_executions[0].start_time)

    def test_to_summary_method_exists(self):
        """Test that to_summary method exists and is callable."""
        self.assertTrue(hasattr(self.service, "to_summary"))
        self.assertTrue(callable(getattr(self.service, "to_summary")))

    def test_to_summary_returns_expected_type(self):
        """Test that to_summary returns expected type: ExecutionSummary."""
        # Method signature: def to_summary(self, tracker: ExecutionTracker, graph_name: str)
        
        # Create a tracker instance and add some test data
        tracker = self.service.create_tracker()
        self.service.record_node_start(tracker, "test_node", {"input": "test"})
        self.service.record_node_result(tracker, "test_node", True, "test_result")
        self.service.complete_execution(tracker)
        
        # Call the method with required parameters
        result = self.service.to_summary(tracker=tracker, graph_name="test_graph")
        
        # Verify return type: ExecutionSummary
        self.assertIsNotNone(result)
        from agentmap.models.execution.summary import ExecutionSummary
        self.assertIsInstance(result, ExecutionSummary)
        self.assertEqual(result.graph_name, "test_graph")
        self.assertEqual(len(result.node_executions), 1)
        self.assertEqual(result.node_executions[0].node_name, "test_node")

    def test_record_node_result_method_exists(self):
        """Test that record_node_result method exists and is callable."""
        self.assertTrue(hasattr(self.service, "record_node_result"))
        self.assertTrue(callable(getattr(self.service, "record_node_result")))

    def test_record_node_result_updates_tracker(self):
        """Test that record_node_result properly updates the tracker."""
        # Create tracker and start a node execution
        tracker = self.service.create_tracker()
        self.service.record_node_start(tracker, "test_node")
        
        # Verify node execution is in progress
        self.assertEqual(len(tracker.node_executions), 1)
        self.assertIsNone(tracker.node_executions[0].success)
        self.assertIsNone(tracker.node_executions[0].end_time)
        
        # Record successful result
        result = self.service.record_node_result(tracker, "test_node", True, "test_output")
        
        # Method returns None
        self.assertIsNone(result)
        
        # Verify the node execution was completed
        node_execution = tracker.node_executions[0]
        self.assertTrue(node_execution.success)
        self.assertIsNotNone(node_execution.end_time)
        self.assertIsNotNone(node_execution.duration)
        
    def test_complete_execution_method_exists(self):
        """Test that complete_execution method exists and is callable."""
        self.assertTrue(hasattr(self.service, "complete_execution"))
        self.assertTrue(callable(getattr(self.service, "complete_execution")))

    def test_complete_execution_returns_expected_type(self):
        """Test that complete_execution returns expected type: None."""
        # Create tracker
        tracker = self.service.create_tracker()
        self.assertIsNone(tracker.end_time)
        
        # Call the method
        result = self.service.complete_execution(tracker)
        
        # Method returns None
        self.assertIsNone(result)
        
        # Verify end time was set
        self.assertIsNotNone(tracker.end_time)

    def test_record_subgraph_execution_method_exists(self):
        """Test that record_subgraph_execution method exists and is callable."""
        self.assertTrue(hasattr(self.service, "record_subgraph_execution"))
        self.assertTrue(callable(getattr(self.service, "record_subgraph_execution")))

    def test_mock_configuration_flexibility(self):
        """Test that pure Mock objects provide configuration flexibility."""
        # Test different config scenarios in single test to show flexibility
        
        # Scenario 1: Minimal tracking
        self.mock_config_service.get_tracking_config.return_value = {
            "track_inputs": False,
            "track_outputs": False,
            "enabled": False
        }
        
        tracker1 = self.service.create_tracker()
        self.assertTrue(tracker1.minimal_mode)
        
        # Scenario 2: Full tracking  
        self.mock_config_service.get_tracking_config.return_value = {
            "track_inputs": True,
            "track_outputs": True,
            "enabled": True
        }
        
        tracker2 = self.service.create_tracker()
        self.assertFalse(tracker2.minimal_mode)
        self.assertTrue(tracker2.track_inputs)
        self.assertTrue(tracker2.track_outputs)

    def test_method_call_verification_enhanced(self):
        """Test enhanced method call verification capabilities with pure Mocks."""
        # Reset call count for clean test
        self.mock_config_service.reset_mock()
        self.mock_logging_service.reset_mock()
        
        # Perform operations
        tracker = self.service.create_tracker()
        self.service.record_node_start(tracker, "node1", {"input": "data"})
        self.service.record_node_result(tracker, "node1", True, {"output": "result"})
        
        # Verify specific method calls
        self.mock_config_service.get_tracking_config.assert_called_once()
        
        # Verify we can check call arguments if needed
        call_args = self.mock_config_service.get_tracking_config.call_args
        self.assertIsNotNone(call_args)  # Called with no arguments
        
        # Test that we can configure side effects if needed
        self.mock_config_service.get_tracking_config.side_effect = [
            {"enabled": True, "track_inputs": True, "track_outputs": True},
            {"enabled": False, "track_inputs": False, "track_outputs": False}
        ]
        
        # Create two trackers with different configs
        tracker_a = self.service.create_tracker()
        tracker_b = self.service.create_tracker()
        
        # Verify they have different configurations
        self.assertFalse(tracker_a.minimal_mode)
        self.assertTrue(tracker_b.minimal_mode)
        
        # Verify multiple calls were made
        self.assertEqual(self.mock_config_service.get_tracking_config.call_count, 3)  # 1 + 2 = 3 total


if __name__ == "__main__":
    unittest.main()
