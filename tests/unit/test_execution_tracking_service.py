"""
Unit tests for ExecutionTrackingService.

These tests mock all dependencies and focus on testing the service logic
in isolation, following the existing test patterns in AgentMap.
"""

import unittest
import time
from unittest.mock import Mock, patch

from agentmap.services.execution_tracking_service import (
    ExecutionTrackingService,
    ExecutionTracker
)
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService
)


class TestExecutionTracker(unittest.TestCase):
    """Unit tests for ExecutionTracker class."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        
        # Mock configuration responses
        self.mock_config_service.get_execution_config = Mock(return_value={
            "timeout": 300,
            "max_retries": 3
        })
        self.mock_config_service.get_tracking_config = Mock(return_value={
            "enabled": True,
            "track_outputs": True,
            "track_inputs": True
        })
        
        # Create tracker instance
        self.tracker = ExecutionTracker(
            app_config_service=self.mock_config_service,
            logging_service=self.mock_logging_service
        )
    
    def test_tracker_initialization(self):
        """Test that tracker initializes correctly with configuration."""
        # Verify configuration was loaded
        self.mock_config_service.get_execution_config.assert_called_once()
        self.mock_config_service.get_tracking_config.assert_called_once()
        
        # Verify initial state
        self.assertEqual(self.tracker.execution_path, [])
        self.assertEqual(self.tracker.node_execution_counts, {})
        self.assertTrue(self.tracker.overall_success)
        self.assertIsNone(self.tracker.end_time)
        
        # Verify tracking settings
        self.assertFalse(self.tracker.minimal_mode)
        self.assertTrue(self.tracker.track_outputs)
        self.assertTrue(self.tracker.track_inputs)
    
    def test_tracker_minimal_mode_initialization(self):
        """Test tracker initialization in minimal mode."""
        # Mock minimal configuration
        self.mock_config_service.get_tracking_config = Mock(return_value={
            "enabled": False,
            "track_outputs": True,
            "track_inputs": True
        })
        
        tracker = ExecutionTracker(
            app_config_service=self.mock_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Verify minimal mode settings
        self.assertTrue(tracker.minimal_mode)
        self.assertFalse(tracker.track_outputs)  # Disabled in minimal mode
        self.assertFalse(tracker.track_inputs)   # Disabled in minimal mode
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_start_execution(self, mock_time):
        """Test starting execution tracking."""
        mock_time.return_value = 1000.0
        
        # Start execution
        self.tracker.start_execution()
        
        # Verify state reset
        self.assertEqual(self.tracker.start_time, 1000.0)
        self.assertIsNone(self.tracker.end_time)
        self.assertTrue(self.tracker.overall_success)
        self.assertEqual(self.tracker.execution_path, [])
        self.assertEqual(self.tracker.node_execution_counts, {})
        
        # Verify debug logging
        logger_calls = self.tracker._logger.calls
        self.assertTrue(any(call[1] == "[ExecutionTracker] Started execution tracking" 
                          for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_record_node_start(self, mock_time):
        """Test recording node start."""
        mock_time.return_value = 1000.0
        
        # Record node start
        self.tracker.record_node_start("TestNode", {"input": "test_data"})
        
        # Verify execution record
        self.assertEqual(len(self.tracker.execution_path), 1)
        record = self.tracker.execution_path[0]
        
        self.assertEqual(record["node_name"], "TestNode")
        self.assertEqual(record["execution_index"], 0)
        self.assertEqual(record["node_execution_number"], 1)
        self.assertEqual(record["start_time"], 1000.0)
        self.assertIsNone(record["end_time"])
        self.assertIsNone(record["success"])
        self.assertIsNone(record["result"])
        self.assertIsNone(record["error"])
        self.assertEqual(record["inputs"], {"input": "test_data"})
        
        # Verify execution count
        self.assertEqual(self.tracker.node_execution_counts["TestNode"], 1)
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_record_node_start_without_inputs(self, mock_time):
        """Test recording node start without inputs."""
        mock_time.return_value = 1000.0
        
        # Record node start without inputs
        self.tracker.record_node_start("TestNode")
        
        # Verify execution record
        record = self.tracker.execution_path[0]
        self.assertNotIn("inputs", record)  # Should not include inputs key
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_record_node_start_no_input_tracking(self, mock_time):
        """Test recording node start when input tracking is disabled."""
        # Disable input tracking
        self.tracker.track_inputs = False
        mock_time.return_value = 1000.0
        
        # Record node start with inputs
        self.tracker.record_node_start("TestNode", {"input": "test_data"})
        
        # Verify inputs are not tracked
        record = self.tracker.execution_path[0]
        self.assertNotIn("inputs", record)
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_record_node_result_success(self, mock_time):
        """Test recording successful node result."""
        mock_time.side_effect = [1000.0, 1002.5]  # Start time, end time
        
        # Record node start and result
        self.tracker.record_node_start("TestNode")
        self.tracker.record_node_result("TestNode", True, {"output": "result"})
        
        # Verify execution record
        record = self.tracker.execution_path[0]
        self.assertEqual(record["success"], True)
        self.assertEqual(record["end_time"], 1002.5)
        self.assertEqual(record["duration"], 2.5)
        self.assertEqual(record["result"], {"output": "result"})
        self.assertIsNone(record["error"])
        
        # Verify overall success remains True
        self.assertTrue(self.tracker.overall_success)
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_record_node_result_failure(self, mock_time):
        """Test recording failed node result."""
        mock_time.side_effect = [1000.0, 1001.5]
        
        # Record node start and failure
        self.tracker.record_node_start("TestNode")
        self.tracker.record_node_result("TestNode", False, None, "Test error")
        
        # Verify execution record
        record = self.tracker.execution_path[0]
        self.assertEqual(record["success"], False)
        self.assertEqual(record["error"], "Test error")
        self.assertIsNone(record["result"])
        
        # Verify overall success is now False
        self.assertFalse(self.tracker.overall_success)
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_record_node_result_no_output_tracking(self, mock_time):
        """Test recording node result when output tracking is disabled."""
        # Disable output tracking
        self.tracker.track_outputs = False
        mock_time.side_effect = [1000.0, 1001.0]
        
        # Record node start and result
        self.tracker.record_node_start("TestNode")
        self.tracker.record_node_result("TestNode", True, {"output": "result"})
        
        # Verify result is not stored
        record = self.tracker.execution_path[0]
        self.assertNotIn("result", record)
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_record_multiple_node_executions(self, mock_time):
        """Test recording multiple node executions."""
        mock_time.side_effect = [1000.0, 1001.0, 1002.0, 1003.0, 1004.0, 1005.0]
        
        # Record multiple nodes
        self.tracker.record_node_start("Node1")
        self.tracker.record_node_result("Node1", True, "result1")
        
        self.tracker.record_node_start("Node2")
        self.tracker.record_node_result("Node2", False, None, "error")
        
        self.tracker.record_node_start("Node1")  # Second execution of Node1
        self.tracker.record_node_result("Node1", True, "result2")
        
        # Verify execution path
        self.assertEqual(len(self.tracker.execution_path), 3)
        
        # Verify execution indices
        self.assertEqual(self.tracker.execution_path[0]["execution_index"], 0)
        self.assertEqual(self.tracker.execution_path[1]["execution_index"], 1)
        self.assertEqual(self.tracker.execution_path[2]["execution_index"], 2)
        
        # Verify node execution numbers
        self.assertEqual(self.tracker.execution_path[0]["node_execution_number"], 1)
        self.assertEqual(self.tracker.execution_path[1]["node_execution_number"], 1)
        self.assertEqual(self.tracker.execution_path[2]["node_execution_number"], 2)  # Second execution of Node1
        
        # Verify execution counts
        self.assertEqual(self.tracker.node_execution_counts["Node1"], 2)
        self.assertEqual(self.tracker.node_execution_counts["Node2"], 1)
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_complete_execution(self, mock_time):
        """Test completing execution tracking."""
        mock_time.return_value = 1005.0
        
        # Complete execution
        self.tracker.complete_execution()
        
        # Verify end time is set
        self.assertEqual(self.tracker.end_time, 1005.0)
        
        # Verify debug logging
        logger_calls = self.tracker._logger.calls
        self.assertTrue(any(call[1] == "[ExecutionTracker] Completed execution tracking" 
                          for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_record_subgraph_execution(self, mock_time):
        """Test recording subgraph execution."""
        mock_time.side_effect = [1000.0, 1001.0]
        
        # Record parent node start
        self.tracker.record_node_start("ParentNode")
        
        # Record subgraph execution
        subgraph_summary = {
            "overall_success": True,
            "nodes": {"SubNode1": {"success": True}, "SubNode2": {"success": True}}
        }
        self.tracker.record_subgraph_execution("SubGraph", subgraph_summary)
        
        # Verify subgraph was recorded
        record = self.tracker.execution_path[0]
        self.assertIn("subgraphs", record)
        self.assertIn("SubGraph", record["subgraphs"])
        self.assertEqual(record["subgraphs"]["SubGraph"], subgraph_summary)
        
        # Verify info logging
        logger_calls = self.tracker._logger.calls
        self.assertTrue(any("Recorded subgraph 'SubGraph'" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    def test_record_subgraph_execution_no_current_node(self):
        """Test recording subgraph execution when no current node context."""
        subgraph_summary = {"overall_success": True, "nodes": {}}
        
        # Try to record subgraph without current node
        self.tracker.record_subgraph_execution("SubGraph", subgraph_summary)
        
        # Verify warning was logged
        logger_calls = self.tracker._logger.calls
        self.assertTrue(any("Cannot record subgraph 'SubGraph' - no current node context" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_get_summary(self, mock_time):
        """Test getting execution summary."""
        mock_time.side_effect = [1000.0, 1001.0, 1002.0, 1003.0, 1005.0]
        
        # Set up tracker state
        self.tracker.start_time = 1000.0
        self.tracker.end_time = 1005.0
        
        # Record some execution
        self.tracker.record_node_start("Node1")
        self.tracker.record_node_result("Node1", True, "result")
        
        # Record subgraph
        subgraph_summary = {"overall_success": True, "nodes": {"SubNode": {}}}
        self.tracker.record_subgraph_execution("SubGraph", subgraph_summary)
        
        # Get summary
        summary = self.tracker.get_summary()
        
        # Verify summary structure
        self.assertTrue(summary["overall_success"])
        self.assertEqual(len(summary["execution_path"]), 1)
        self.assertEqual(summary["subgraph_executions"], 1)
        self.assertIn("SubGraph", summary["subgraph_details"])
        self.assertEqual(summary["total_duration"], 5.0)
        self.assertEqual(summary["start_time"], 1000.0)
        self.assertEqual(summary["end_time"], 1005.0)
        
        # Verify subgraph details
        subgraph_details = summary["subgraph_details"]["SubGraph"]
        self.assertEqual(len(subgraph_details), 1)
        self.assertEqual(subgraph_details[0]["parent_node"], "Node1")
        self.assertTrue(subgraph_details[0]["success"])
        self.assertEqual(subgraph_details[0]["node_count"], 1)
    
    @patch('agentmap.services.execution_tracking_service.time.time')
    def test_get_summary_no_end_time(self, mock_time):
        """Test getting summary when execution hasn't ended."""
        mock_time.return_value = 1005.0
        
        # Set up tracker without end time
        self.tracker.start_time = 1000.0
        self.tracker.end_time = None
        
        summary = self.tracker.get_summary()
        
        # Should use current time for calculations
        self.assertEqual(summary["total_duration"], 5.0)
        self.assertEqual(summary["end_time"], 1005.0)


class TestExecutionTrackingService(unittest.TestCase):
    """Unit tests for ExecutionTrackingService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use migration-safe mock implementations
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        
        # Mock configuration responses
        self.mock_config_service.get_tracking_config = Mock(return_value={
            "enabled": True,
            "track_outputs": True,
            "track_inputs": False
        })
        
        # Create service instance with mocked dependencies
        self.service = ExecutionTrackingService(
            app_config_service=self.mock_config_service,
            logging_service=self.mock_logging_service
        )
    
    def test_service_initialization(self):
        """Test that service initializes correctly with dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.logger.name, "ExecutionTrackingService")
        self.assertEqual(self.service.config, self.mock_config_service)
        
        # Verify initialization log message
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[ExecutionTrackingService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
    
    @patch('agentmap.services.execution_tracking_service.ExecutionTracker')
    def test_create_tracker(self, mock_tracker_class):
        """Test creating a new execution tracker."""
        # Mock tracker instance
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        # Create tracker
        result = self.service.create_tracker()
        
        # Verify tracker was created with correct parameters
        mock_tracker_class.assert_called_once_with(
            app_config_service=self.mock_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Verify start_execution was called
        mock_tracker.start_execution.assert_called_once()
        
        # Verify result
        self.assertEqual(result, mock_tracker)
        
        # Verify debug logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[ExecutionTrackingService] Creating new ExecutionTracker" 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_get_tracking_config(self):
        """Test getting tracking configuration."""
        result = self.service.get_tracking_config()
        
        # Verify config service was called
        self.mock_config_service.get_tracking_config.assert_called_once()
        
        # Verify result
        expected_config = {
            "enabled": True,
            "track_outputs": True,
            "track_inputs": False
        }
        self.assertEqual(result, expected_config)
    
    def test_is_tracking_enabled_true(self):
        """Test checking if tracking is enabled when it is."""
        result = self.service.is_tracking_enabled()
        
        self.assertTrue(result)
    
    def test_is_tracking_enabled_false(self):
        """Test checking if tracking is enabled when it's not."""
        # Mock disabled tracking
        self.mock_config_service.get_tracking_config = Mock(return_value={
            "enabled": False
        })
        
        result = self.service.is_tracking_enabled()
        
        self.assertFalse(result)
    
    def test_is_tracking_enabled_default(self):
        """Test checking if tracking is enabled with default value."""
        # Mock config without enabled key
        self.mock_config_service.get_tracking_config = Mock(return_value={})
        
        result = self.service.is_tracking_enabled()
        
        # Should default to True
        self.assertTrue(result)
    
    def test_get_service_info_success(self):
        """Test getting service information successfully."""
        info = self.service.get_service_info()
        
        # Verify service information
        self.assertEqual(info["service"], "ExecutionTrackingService")
        self.assertTrue(info["config_available"])
        self.assertTrue(info["tracking_enabled"])
        
        # Verify tracking config
        expected_config = {
            "enabled": True,
            "track_outputs": True,
            "track_inputs": False
        }
        self.assertEqual(info["tracking_config"], expected_config)
        
        # Verify capabilities
        capabilities = info["capabilities"]
        self.assertTrue(capabilities["tracker_factory"])
        self.assertTrue(capabilities["pure_data_tracking"])
        self.assertTrue(capabilities["subgraph_support"])
        self.assertTrue(capabilities["configurable_tracking"])
        self.assertTrue(capabilities["clean_architecture"])
        
        # Verify tracker methods
        tracker_methods = info["tracker_methods"]
        expected_methods = [
            "start_execution",
            "record_node_start",
            "record_node_result",
            "complete_execution",
            "record_subgraph_execution",
            "get_summary"
        ]
        self.assertEqual(tracker_methods, expected_methods)
        
        # Verify architecture note
        self.assertIn("Pure data tracking", info["architecture_note"])
    
    def test_get_service_info_config_error(self):
        """Test getting service information when config fails."""
        # Mock config failure
        self.mock_config_service.get_tracking_config = Mock(side_effect=Exception("Config error"))
        
        info = self.service.get_service_info()
        
        # Should still return service info with error indication
        self.assertEqual(info["service"], "ExecutionTrackingService")
        self.assertTrue(info["config_available"])
        self.assertFalse(info["tracking_enabled"])  # Should default to False with error
        self.assertIn("error", info["tracking_config"])


if __name__ == '__main__':
    unittest.main()
