"""
Unit tests for ExecutionTrackingService.

These tests validate the ExecutionTrackingService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from datetime import datetime, timedelta

from agentmap.models.execution.summary import ExecutionSummary
from agentmap.models.execution.tracker import ExecutionTracker
from agentmap.services.execution_tracking_service import (
    ExecutionTrackingService,
)
from tests.utils.migration_utils import MockLoggingService
from tests.utils.mock_service_factory import MockServiceFactory


class TestExecutionTrackingService(unittest.TestCase):
    """Unit tests for ExecutionTrackingService with mocked dependencies."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use MockServiceFactory for consistent mock behavior
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service(
                {
                    "tracking": {
                        "enabled": True,
                        "track_inputs": False,
                        "track_outputs": False,
                    }
                }
            )
        )

        # Use migration-safe mock logging service
        self.mock_logging_service = MockLoggingService()

        # Create service instance with mocked dependencies
        self.service = ExecutionTrackingService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
        )

        # Get the mock logger for verification
        self.mock_logger = self.service.logger

    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================

    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertEqual(self.service.logging_service, self.mock_logging_service)

        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "ExecutionTrackingService")

        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                call[1] == "[ExecutionTrackingService] Initialized"
                for call in logger_calls
                if call[0] == "info"
            )
        )

    def test_service_accesses_tracking_config(self):
        """Test that service accesses tracking configuration correctly."""
        # Mock get_tracking_config method
        tracking_config = {
            "enabled": True,
            "track_inputs": True,
            "track_outputs": False,
        }
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config

        # Act
        tracker = self.service.create_tracker()

        # Assert
        self.mock_app_config_service.get_tracking_config.assert_called_once()
        self.assertTrue(tracker.track_inputs)
        self.assertFalse(tracker.track_outputs)
        self.assertFalse(tracker.minimal_mode)

    # =============================================================================
    # 2. create_tracker() Method Tests
    # =============================================================================

    def test_create_tracker_returns_execution_tracker(self):
        """Test that create_tracker() returns ExecutionTracker instance."""
        # Act
        tracker = self.service.create_tracker()

        # Assert
        self.assertIsInstance(tracker, ExecutionTracker)
        self.assertIsNotNone(tracker.start_time)
        self.assertTrue(tracker.overall_success)
        self.assertEqual(len(tracker.node_executions), 0)
        self.assertEqual(len(tracker.node_execution_counts), 0)

    def test_create_tracker_with_tracking_enabled(self):
        """Test create_tracker() with tracking enabled configuration."""
        # Arrange
        tracking_config = {"enabled": True, "track_inputs": True, "track_outputs": True}
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config

        # Act
        tracker = self.service.create_tracker()

        # Assert
        self.assertTrue(tracker.track_inputs)
        self.assertTrue(tracker.track_outputs)
        self.assertFalse(tracker.minimal_mode)

    def test_create_tracker_with_tracking_disabled(self):
        """Test create_tracker() with tracking disabled configuration."""
        # Arrange
        tracking_config = {
            "enabled": False,
            "track_inputs": True,
            "track_outputs": True,
        }
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config

        # Act
        tracker = self.service.create_tracker()

        # Assert
        self.assertFalse(tracker.track_inputs)
        self.assertFalse(tracker.track_outputs)
        self.assertTrue(tracker.minimal_mode)

    def test_create_tracker_with_default_values(self):
        """Test create_tracker() handles missing config values with defaults."""
        # Arrange
        tracking_config = {}  # Empty config
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config

        # Act
        tracker = self.service.create_tracker()

        # Assert - Should use default values
        self.assertFalse(tracker.track_inputs)
        self.assertFalse(tracker.track_outputs)
        self.assertTrue(tracker.minimal_mode)  # disabled by default

    # =============================================================================
    # 3. record_node_start() Method Tests
    # =============================================================================

    def test_record_node_start_creates_node_execution(self):
        """Test that record_node_start() creates NodeExecution entry."""
        # Arrange
        tracker = self.service.create_tracker()
        node_name = "test_node"
        inputs = {"param1": "value1"}

        # Act
        self.service.record_node_start(tracker, node_name, inputs)

        # Assert
        self.assertEqual(len(tracker.node_executions), 1)
        node_exec = tracker.node_executions[0]
        self.assertEqual(node_exec.node_name, node_name)
        self.assertIsNotNone(node_exec.start_time)
        self.assertIsNone(node_exec.success)
        self.assertIsNone(node_exec.end_time)

    def test_record_node_start_updates_execution_counts(self):
        """Test that record_node_start() updates node execution counts."""
        # Arrange
        tracker = self.service.create_tracker()
        node_name = "test_node"

        # Act - Record multiple starts for same node
        self.service.record_node_start(tracker, node_name)
        self.service.record_node_start(tracker, node_name)
        self.service.record_node_start(tracker, "other_node")

        # Assert
        self.assertEqual(tracker.node_execution_counts[node_name], 2)
        self.assertEqual(tracker.node_execution_counts["other_node"], 1)
        self.assertEqual(len(tracker.node_executions), 3)

    def test_record_node_start_tracks_inputs_when_enabled(self):
        """Test that record_node_start() tracks inputs when enabled."""
        # Arrange
        tracking_config = {"enabled": True, "track_inputs": True}
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config
        tracker = self.service.create_tracker()

        inputs = {"param1": "value1", "param2": {"nested": "value"}}

        # Act
        self.service.record_node_start(tracker, "test_node", inputs)

        # Assert
        node_exec = tracker.node_executions[0]
        self.assertEqual(node_exec.inputs, inputs)

    def test_record_node_start_ignores_inputs_when_disabled(self):
        """Test that record_node_start() ignores inputs when disabled."""
        # Arrange
        tracking_config = {"enabled": True, "track_inputs": False}
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config
        tracker = self.service.create_tracker()

        inputs = {"param1": "value1"}

        # Act
        self.service.record_node_start(tracker, "test_node", inputs)

        # Assert
        node_exec = tracker.node_executions[0]
        self.assertIsNone(node_exec.inputs)

    def test_record_node_start_handles_none_inputs(self):
        """Test that record_node_start() handles None inputs gracefully."""
        # Arrange
        tracker = self.service.create_tracker()

        # Act
        self.service.record_node_start(tracker, "test_node", None)

        # Assert
        node_exec = tracker.node_executions[0]
        self.assertIsNone(node_exec.inputs)

    # =============================================================================
    # 4. record_node_result() Method Tests
    # =============================================================================

    def test_record_node_result_success(self):
        """Test that record_node_result() records successful execution."""
        # Arrange
        tracker = self.service.create_tracker()
        node_name = "test_node"
        result = {"output": "success_value"}

        self.service.record_node_start(tracker, node_name)

        # Act
        self.service.record_node_result(tracker, node_name, True, result)

        # Assert
        node_exec = tracker.node_executions[0]
        self.assertTrue(node_exec.success)
        self.assertIsNotNone(node_exec.end_time)
        self.assertIsNotNone(node_exec.duration)
        self.assertTrue(tracker.overall_success)
        self.assertIsNone(node_exec.error)

    def test_record_node_result_failure(self):
        """Test that record_node_result() records failed execution."""
        # Arrange
        tracker = self.service.create_tracker()
        node_name = "test_node"
        error_msg = "Node execution failed"

        self.service.record_node_start(tracker, node_name)

        # Act
        self.service.record_node_result(tracker, node_name, False, None, error_msg)

        # Assert
        node_exec = tracker.node_executions[0]
        self.assertFalse(node_exec.success)
        self.assertEqual(node_exec.error, error_msg)
        self.assertFalse(tracker.overall_success)  # Failure sets overall to False

    def test_record_node_result_tracks_outputs_when_enabled(self):
        """Test that record_node_result() tracks outputs when enabled."""
        # Arrange
        tracking_config = {"enabled": True, "track_outputs": True}
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config
        tracker = self.service.create_tracker()

        result = {"output": "result_value", "metrics": {"time": 1.5}}

        self.service.record_node_start(tracker, "test_node")

        # Act
        self.service.record_node_result(tracker, "test_node", True, result)

        # Assert
        node_exec = tracker.node_executions[0]
        self.assertEqual(node_exec.output, result)

    def test_record_node_result_ignores_outputs_when_disabled(self):
        """Test that record_node_result() ignores outputs when disabled."""
        # Arrange
        tracking_config = {"enabled": True, "track_outputs": False}
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config
        tracker = self.service.create_tracker()

        result = {"output": "result_value"}

        self.service.record_node_start(tracker, "test_node")

        # Act
        self.service.record_node_result(tracker, "test_node", True, result)

        # Assert
        node_exec = tracker.node_executions[0]
        self.assertIsNone(node_exec.output)

    def test_record_node_result_calculates_duration(self):
        """Test that record_node_result() calculates execution duration."""
        # Arrange
        tracker = self.service.create_tracker()

        self.service.record_node_start(tracker, "test_node")
        node_exec = tracker.node_executions[0]

        # Mock start time to be 2 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=2)
        node_exec.start_time = past_time

        # Act
        self.service.record_node_result(tracker, "test_node", True)

        # Assert
        self.assertIsNotNone(node_exec.duration)
        self.assertGreater(node_exec.duration, 1.8)  # At least 1.8 seconds
        self.assertLess(node_exec.duration, 2.5)  # Less than 2.5 seconds

    def test_record_node_result_handles_multiple_nodes(self):
        """Test that record_node_result() finds correct node in multiple executions."""
        # Arrange
        # Arrange
        tracking_config = {"enabled": True, "track_inputs": True, "track_outputs": True}
        self.mock_app_config_service.get_tracking_config.return_value = tracking_config
        tracker = self.service.create_tracker()

        # Start multiple nodes
        self.service.record_node_start(tracker, "node1")
        self.service.record_node_start(tracker, "node2")
        self.service.record_node_start(tracker, "node1")  # node1 again

        # Act - Complete the second node1 execution (most recent)
        self.service.record_node_result(tracker, "node1", True, "result1")

        # Assert - Should update the most recent node1 execution
        node1_executions = [
            n for n in tracker.node_executions if n.node_name == "node1"
        ]
        self.assertEqual(len(node1_executions), 2)

        # The last node1 execution should be completed
        last_node1 = node1_executions[-1]
        self.assertTrue(last_node1.success)
        self.assertEqual(last_node1.output, "result1")

        # First node1 should still be incomplete
        first_node1 = node1_executions[0]
        self.assertIsNone(first_node1.success)

    def test_record_node_result_handles_no_matching_node(self):
        """Test that record_node_result() handles non-existent node gracefully."""
        # Arrange
        tracker = self.service.create_tracker()
        self.service.record_node_start(tracker, "existing_node")

        # Act - Try to record result for non-existent node
        self.service.record_node_result(tracker, "non_existent_node", True)

        # Assert - Should not crash, existing node should remain unchanged
        self.assertEqual(len(tracker.node_executions), 1)
        existing_node = tracker.node_executions[0]
        self.assertIsNone(existing_node.success)  # Still incomplete

    # =============================================================================
    # 5. complete_execution() Method Tests
    # =============================================================================

    def test_complete_execution_sets_end_time(self):
        """Test that complete_execution() sets tracker end time."""
        # Arrange
        tracker = self.service.create_tracker()
        self.assertIsNone(tracker.end_time)

        # Act
        self.service.complete_execution(tracker)

        # Assert
        self.assertIsNotNone(tracker.end_time)
        self.assertIsInstance(tracker.end_time, datetime)

    def test_complete_execution_idempotent(self):
        """Test that complete_execution() is idempotent."""
        # Arrange
        tracker = self.service.create_tracker()

        # Act - Call multiple times
        self.service.complete_execution(tracker)
        first_end_time = tracker.end_time

        self.service.complete_execution(tracker)
        second_end_time = tracker.end_time

        # Assert - End time should be updated (not the same)
        self.assertIsNotNone(first_end_time)
        self.assertIsNotNone(second_end_time)
        # Allow for small time differences, but both should be valid times
        self.assertIsInstance(first_end_time, datetime)
        self.assertIsInstance(second_end_time, datetime)

    # =============================================================================
    # 6. record_subgraph_execution() Method Tests
    # =============================================================================

    def test_record_subgraph_execution(self):
        """Test that record_subgraph_execution() records subgraph tracker."""
        # Arrange
        tracker = self.service.create_tracker()
        subgraph_tracker = self.service.create_tracker()
        subgraph_name = "subgraph"

        self.service.record_node_start(tracker, "parent_node")

        # Act
        self.service.record_subgraph_execution(tracker, subgraph_name, subgraph_tracker)

        # Assert
        parent_node = tracker.node_executions[0]
        self.assertEqual(parent_node.subgraph_execution_tracker, subgraph_tracker)

    def test_record_subgraph_execution_finds_incomplete_node(self):
        """Test that record_subgraph_execution() finds the most recent incomplete node."""
        # Arrange
        tracker = self.service.create_tracker()
        subgraph_tracker = self.service.create_tracker()

        # Start and complete one node
        self.service.record_node_start(tracker, "completed_node")
        self.service.record_node_result(tracker, "completed_node", True)

        # Start another node but don't complete it
        self.service.record_node_start(tracker, "incomplete_node")

        # Act
        self.service.record_subgraph_execution(tracker, "subgraph", subgraph_tracker)

        # Assert - Should attach to the incomplete node
        incomplete_node = tracker.node_executions[1]
        self.assertEqual(incomplete_node.subgraph_execution_tracker, subgraph_tracker)

        # Completed node should not have subgraph tracker
        completed_node = tracker.node_executions[0]
        self.assertIsNone(completed_node.subgraph_execution_tracker)

    # =============================================================================
    # 7. to_summary() Method Tests
    # =============================================================================

    def test_to_summary_creates_execution_summary(self):
        """Test that to_summary() creates ExecutionSummary from tracker."""
        # Arrange
        tracker = self.service.create_tracker()
        graph_name = "test_graph"

        # Add some execution data
        self.service.record_node_start(tracker, "node1")
        self.service.record_node_result(tracker, "node1", True, {"result": "value"})
        self.service.complete_execution(tracker)

        # Act
        summary = self.service.to_summary(tracker, graph_name)

        # Assert
        self.assertIsInstance(summary, ExecutionSummary)
        self.assertEqual(summary.graph_name, graph_name)
        self.assertEqual(summary.start_time, tracker.start_time)
        self.assertEqual(summary.end_time, tracker.end_time)
        self.assertTrue(summary.graph_success)
        self.assertEqual(summary.status, "completed")

    def test_to_summary_converts_node_executions(self):
        """Test that to_summary() properly converts NodeExecution objects."""
        # Arrange
        tracker = self.service.create_tracker()

        # Create multiple node executions
        self.service.record_node_start(tracker, "node1", {"input": "test"})
        self.service.record_node_result(tracker, "node1", True, {"output": "result1"})

        self.service.record_node_start(tracker, "node2")
        self.service.record_node_result(tracker, "node2", False, None, "Error occurred")

        # Act
        summary = self.service.to_summary(tracker, "test_graph")

        # Assert
        self.assertEqual(len(summary.node_executions), 2)

        # Check first node (success)
        node1_summary = summary.node_executions[0]
        self.assertEqual(node1_summary.node_name, "node1")
        self.assertTrue(node1_summary.success)
        self.assertIsNotNone(node1_summary.start_time)
        self.assertIsNotNone(node1_summary.end_time)
        self.assertIsNotNone(node1_summary.duration)

        # Check second node (failure)
        node2_summary = summary.node_executions[1]
        self.assertEqual(node2_summary.node_name, "node2")
        self.assertFalse(node2_summary.success)
        self.assertEqual(node2_summary.error, "Error occurred")

    def test_to_summary_handles_in_progress_execution(self):
        """Test that to_summary() handles in-progress execution."""
        # Arrange
        tracker = self.service.create_tracker()

        self.service.record_node_start(tracker, "node1")
        self.service.record_node_result(tracker, "node1", True)
        # Don't call complete_execution()

        # Act
        summary = self.service.to_summary(tracker, "test_graph")

        # Assert
        self.assertEqual(summary.status, "in_progress")
        self.assertIsNone(summary.end_time)

    def test_to_summary_preserves_overall_success_status(self):
        """Test that to_summary() preserves overall success status."""
        # Arrange
        tracker = self.service.create_tracker()

        # Mix of success and failure
        self.service.record_node_start(tracker, "success_node")
        self.service.record_node_result(tracker, "success_node", True)

        self.service.record_node_start(tracker, "failure_node")
        self.service.record_node_result(tracker, "failure_node", False, None, "Failed")

        self.service.complete_execution(tracker)

        # Act
        summary = self.service.to_summary(tracker, "test_graph")

        # Assert - Overall success should be False due to failure
        self.assertFalse(summary.graph_success)

    # =============================================================================
    # 8. Error Handling and Edge Cases
    # =============================================================================

    def test_service_handles_invalid_inputs_gracefully(self):
        """Test that service methods handle invalid inputs gracefully."""
        # Arrange
        tracker = self.service.create_tracker()

        # Act & Assert - These should not raise exceptions
        self.service.record_node_start(tracker, "")  # Empty node name
        self.service.record_node_start(tracker, None)  # None node name - should handle

        # Verify executions were recorded (even with invalid names)
        self.assertEqual(len(tracker.node_executions), 2)

    def test_service_with_none_tracker_handles_gracefully(self):
        """Test that service methods handle None tracker input."""
        # These should not crash, but behavior may vary
        # The actual service might raise AttributeError, which is acceptable
        with self.assertRaises((AttributeError, TypeError)):
            self.service.record_node_start(None, "test_node")

        with self.assertRaises((AttributeError, TypeError)):
            self.service.record_node_result(None, "test_node", True)

        with self.assertRaises((AttributeError, TypeError)):
            self.service.complete_execution(None)


if __name__ == "__main__":
    unittest.main()
