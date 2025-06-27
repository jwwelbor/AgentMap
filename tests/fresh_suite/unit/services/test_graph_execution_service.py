"""
Unit tests for GraphExecutionService.

These tests validate the GraphExecutionService coordination capabilities
using MockServiceFactory patterns for consistent testing.

GraphExecutionService is responsible for:
- Coordinating execution flow between tracking, policy, and assembly services
- Executing compiled graphs from bundle files
- Executing graphs from in-memory definitions
- Setting up execution tracking across agent instances
- Orchestrating the complete execution lifecycle
"""

import unittest
import unittest.mock
from unittest.mock import Mock, patch
from pathlib import Path
from typing import Dict, Any
import time

from agentmap.services.graph_execution_service import GraphExecutionService
from agentmap.models.execution_result import ExecutionResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphExecutionService(unittest.TestCase):
    """Unit tests for GraphExecutionService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create all required mock services using MockServiceFactory
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_execution_policy_service = MockServiceFactory.create_mock_execution_policy_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        self.mock_graph_assembly_service = MockServiceFactory.create_mock_graph_assembly_service()
        self.mock_graph_bundle_service = MockServiceFactory.create_mock_graph_bundle_service()
        self.mock_graph_factory_service = MockServiceFactory.create_mock_graph_factory_service()
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Initialize GraphExecutionService with all mocked dependencies
        self.service = GraphExecutionService(
            execution_tracking_service=self.mock_execution_tracking_service,
            execution_policy_service=self.mock_execution_policy_service,
            state_adapter_service=self.mock_state_adapter_service,
            graph_assembly_service=self.mock_graph_assembly_service,
            graph_bundle_service=self.mock_graph_bundle_service,
            graph_factory_service=self.mock_graph_factory_service,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all execution coordination services are stored
        self.assertEqual(self.service.execution_tracking_service, self.mock_execution_tracking_service)
        self.assertEqual(self.service.execution_policy_service, self.mock_execution_policy_service)
        self.assertEqual(self.service.state_adapter_service, self.mock_state_adapter_service)
        self.assertEqual(self.service.graph_assembly_service, self.mock_graph_assembly_service)
        self.assertEqual(self.service.graph_bundle_service, self.mock_graph_bundle_service)
        self.assertEqual(self.service.graph_factory_service, self.mock_graph_factory_service)
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "GraphExecutionService")
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == "[GraphExecutionService] Initialized with execution coordination services" 
                          for call in logger_calls if call[0] == "info"))
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies gracefully."""
        # This test verifies that all dependencies are actually required
        with self.assertRaises(TypeError):
            # Missing required dependencies should raise TypeError
            GraphExecutionService(
                execution_tracking_service=self.mock_execution_tracking_service,
                # Missing other required services
            )
    
    def test_get_service_info(self):
        """Test get_service_info() debug method."""
        # Act
        service_info = self.service.get_service_info()
        
        # Assert basic structure
        self.assertIsInstance(service_info, dict)
        self.assertEqual(service_info["service"], "GraphExecutionService")
        
        # Verify dependency availability flags
        self.assertTrue(service_info["execution_tracking_service_available"])
        self.assertTrue(service_info["execution_policy_service_available"])
        self.assertTrue(service_info["state_adapter_service_available"])
        self.assertTrue(service_info["graph_assembly_service_available"])
        self.assertTrue(service_info["graph_bundle_service_available"])
        
        # Verify overall initialization status
        self.assertTrue(service_info["dependencies_initialized"])
        
        # Verify capabilities
        capabilities = service_info["capabilities"]
        self.assertTrue(capabilities["compiled_graph_execution"])
        self.assertTrue(capabilities["definition_graph_execution"])
        self.assertTrue(capabilities["execution_tracking_setup"])
        self.assertTrue(capabilities["bundle_loading"])
        self.assertTrue(capabilities["graph_assembly"])
        self.assertTrue(capabilities["execution_coordination"])
        self.assertTrue(capabilities["policy_evaluation"])
        self.assertTrue(capabilities["state_management"])
        self.assertTrue(capabilities["error_handling"])
        
        # Verify execution methods
        execution_methods = service_info["execution_methods"]
        self.assertIn("execute_compiled_graph", execution_methods)
        self.assertIn("execute_from_definition", execution_methods)
        self.assertIn("setup_execution_tracking", execution_methods)
        
        # Verify coordination services
        coordination_services = service_info["coordination_services"]
        self.assertIn("ExecutionTrackingService", coordination_services)
        self.assertIn("ExecutionPolicyService", coordination_services)
        self.assertIn("StateAdapterService", coordination_services)
        self.assertIn("GraphAssemblyService", coordination_services)
        self.assertIn("GraphBundleService", coordination_services)
    
    # =============================================================================
    # 2. Execution Tracking Setup Tests
    # =============================================================================
    
    def test_setup_execution_tracking(self):
        """Test setup_execution_tracking() creates tracker correctly."""
        # Configure execution tracking service to return realistic tracker
        mock_tracker = Mock()
        mock_tracker.graph_name = "test_graph"
        mock_tracker.tracking_config = {"enabled": True}
        
        # Clear the MockServiceFactory's side_effect and set our specific return_value
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Execute test
        result_tracker = self.service.setup_execution_tracking("test_graph")
        
        # Verify execution tracking service was called
        self.mock_execution_tracking_service.create_tracker.assert_called_once()
        
        # Verify returned tracker
        self.assertEqual(result_tracker, mock_tracker)
        self.assertEqual(result_tracker.graph_name, "test_graph")
        
        # Verify debug logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Setting up execution tracking for: test_graph" in call[1] for call in debug_calls))
        self.assertTrue(any("Execution tracking setup complete for: test_graph" in call[1] for call in debug_calls))
    
    def test_setup_execution_tracking_with_different_graph_names(self):
        """Test setup_execution_tracking() handles various graph names."""
        # Configure mock tracker
        def create_mock_tracker_for_graph():
            mock_tracker = Mock()
            mock_tracker.tracking_config = {"enabled": True}
            return mock_tracker
        
        self.mock_execution_tracking_service.create_tracker.side_effect = create_mock_tracker_for_graph
        
        # Test with different graph names
        graph_names = ["simple_graph", "complex-graph-name", "graph_with_123_numbers", ""]
        
        for graph_name in graph_names:
            with self.subTest(graph_name=graph_name):
                result = self.service.setup_execution_tracking(graph_name)
                self.assertIsNotNone(result)
                
                # Verify execution tracking service was called for each
                expected_calls = graph_names.index(graph_name) + 1
                self.assertEqual(self.mock_execution_tracking_service.create_tracker.call_count, expected_calls)
    
    # =============================================================================
    # 3. Compiled Graph Execution Tests
    # =============================================================================
    
    def test_execute_compiled_graph_success(self):
        """Test execute_compiled_graph() with successful execution."""
        # Prepare test data
        bundle_path = Path("compiled/test_graph.pkl")
        initial_state = {"user_id": "user123", "input_data": "test_data"}
        
        # Configure bundle loading
        mock_bundle = Mock()
        mock_compiled_graph = Mock()
        mock_bundle.graph = mock_compiled_graph
        
        # Clear side effects and set specific return values
        self.mock_graph_bundle_service.load_bundle.side_effect = None
        self.mock_graph_bundle_service.load_bundle.return_value = mock_bundle
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure execution summary
        mock_execution_summary = Mock()
        mock_execution_summary.graph_name = "test_graph"
        mock_execution_summary.graph_success = True
        self.mock_execution_tracking_service.to_summary.side_effect = None
        self.mock_execution_tracking_service.to_summary.return_value = mock_execution_summary
        
        # Configure policy evaluation
        self.mock_execution_policy_service.evaluate_success_policy.side_effect = None
        self.mock_execution_policy_service.evaluate_success_policy.return_value = True
        
        # Configure state adapter
        def mock_set_value(state, key, value):
            updated_state = state.copy()
            updated_state[key] = value
            return updated_state
        
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # Configure graph execution
        final_execution_state = {
            "user_id": "user123",
            "result": "processing_complete",
            "output_data": "processed_test_data"
        }
        mock_compiled_graph.invoke.return_value = final_execution_state
        
        # Mock the internal _load_compiled_graph_from_bundle method to bypass file checks
        with patch.object(self.service, '_load_compiled_graph_from_bundle', return_value=mock_compiled_graph):
            # Execute test
            result = self.service.execute_compiled_graph(bundle_path, initial_state)
        
        # Verify result structure
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "test_graph")
        self.assertTrue(result.success)
        self.assertEqual(result.compiled_from, "precompiled")
        self.assertIsNone(result.error)
        
        # Verify final state includes execution metadata
        self.assertIn("__execution_summary", result.final_state)
        self.assertIn("__policy_success", result.final_state)
        self.assertEqual(result.final_state["user_id"], "user123")
        
        # Verify service interactions
        self.mock_execution_tracking_service.create_tracker.assert_called_once()
        self.mock_execution_policy_service.evaluate_success_policy.assert_called_once_with(mock_execution_summary)
        
        # Verify execution timing
        self.assertGreaterEqual(result.total_duration, 0)  # Allow zero duration for mock
        
        # Verify success logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any("Executing compiled graph: test_graph" in call[1] for call in info_calls))
        self.assertTrue(any("✅ COMPLETED COMPILED GRAPH: 'test_graph'" in call[1] for call in info_calls))
    
    def test_execute_compiled_graph_bundle_loading_failure(self):
        """Test execute_compiled_graph() handles bundle loading failures."""
        # Prepare test data
        bundle_path = Path("nonexistent/missing.pkl")
        initial_state = {"user_id": "user123"}
        
        # Configure bundle service to raise FileNotFoundError
        bundle_error = FileNotFoundError(f"Compiled graph bundle not found: {bundle_path}")
        
        # Mock the internal _load_compiled_graph_from_bundle method to raise the error
        with patch.object(self.service, '_load_compiled_graph_from_bundle', side_effect=bundle_error):
            # Execute test
            result = self.service.execute_compiled_graph(bundle_path, initial_state)
        
        # Verify error result
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "missing")  # From path stem
        self.assertFalse(result.success)
        self.assertEqual(result.final_state, initial_state)  # Original state preserved
        self.assertIsNone(result.execution_summary)
        self.assertEqual(result.total_duration, 0.0)
        self.assertEqual(result.compiled_from, "precompiled")
        self.assertIn("Compiled graph bundle not found", result.error)
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("❌ COMPILED GRAPH EXECUTION FAILED: 'missing'" in call[1] for call in error_calls))
        self.assertTrue(any("Compiled graph bundle not found" in call[1] for call in error_calls))
    
    def test_execute_compiled_graph_execution_failure(self):
        """Test execute_compiled_graph() handles graph execution failures."""
        # Prepare test data
        bundle_path = Path("compiled/failing_graph.pkl")
        initial_state = {"input": "test_data"}
        
        # Configure successful bundle loading
        mock_compiled_graph = Mock()
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure graph execution to raise exception
        execution_error = ValueError("Graph execution failed: invalid node configuration")
        mock_compiled_graph.invoke.side_effect = execution_error
        
        # Mock the internal _load_compiled_graph_from_bundle method to return successful graph
        with patch.object(self.service, '_load_compiled_graph_from_bundle', return_value=mock_compiled_graph):
            # Execute test
            result = self.service.execute_compiled_graph(bundle_path, initial_state)
        
        # Verify error result
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "failing_graph")
        self.assertFalse(result.success)
        self.assertEqual(result.final_state, initial_state)  # Original state preserved
        self.assertIsNone(result.execution_summary)
        self.assertEqual(result.compiled_from, "precompiled")
        self.assertEqual(result.error, "Graph execution failed: invalid node configuration")
        
        # Verify execution failed
        mock_compiled_graph.invoke.assert_called_once_with(initial_state)
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("❌ COMPILED GRAPH EXECUTION FAILED: 'failing_graph'" in call[1] for call in error_calls))
        self.assertTrue(any("Graph execution failed: invalid node configuration" in call[1] for call in error_calls))
    
    def test_execute_compiled_graph_policy_evaluation_failure(self):
        """Test execute_compiled_graph() with policy evaluation returning False."""
        # Prepare test data
        bundle_path = Path("compiled/policy_fail_graph.pkl")
        initial_state = {"input": "test_data"}
        
        # Configure successful bundle loading and execution
        mock_compiled_graph = Mock()
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure execution summary
        mock_execution_summary = Mock()
        mock_execution_summary.graph_name = "policy_fail_graph"
        mock_execution_summary.graph_success = False  # Some nodes failed
        self.mock_execution_tracking_service.to_summary.side_effect = None
        self.mock_execution_tracking_service.to_summary.return_value = mock_execution_summary
        
        # Configure policy evaluation to return False (policy failure)
        self.mock_execution_policy_service.evaluate_success_policy.side_effect = None
        self.mock_execution_policy_service.evaluate_success_policy.return_value = False
        
        # Configure state adapter
        def mock_set_value(state, key, value):
            updated_state = state.copy()
            updated_state[key] = value
            return updated_state
        
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # Configure successful graph execution
        final_execution_state = {"input": "test_data", "result": "partial_success"}
        mock_compiled_graph.invoke.return_value = final_execution_state
        
        # Mock the internal _load_compiled_graph_from_bundle method to return successful graph
        with patch.object(self.service, '_load_compiled_graph_from_bundle', return_value=mock_compiled_graph):
            # Execute test
            result = self.service.execute_compiled_graph(bundle_path, initial_state)
        
        # Verify result shows policy failure but execution success
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "policy_fail_graph")
        self.assertFalse(result.success)  # Policy evaluation failed
        self.assertEqual(result.compiled_from, "precompiled")
        self.assertIsNone(result.error)  # No execution error, just policy failure
        
        # Verify final state includes execution metadata
        self.assertIn("__execution_summary", result.final_state)
        self.assertIn("__policy_success", result.final_state)
        self.assertFalse(result.final_state["__policy_success"])
        
        # Verify policy evaluation was called
        self.mock_execution_policy_service.evaluate_success_policy.assert_called_once_with(mock_execution_summary)
        
        # Verify success logging (execution succeeded even though policy failed)
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any("✅ COMPLETED COMPILED GRAPH: 'policy_fail_graph'" in call[1] for call in info_calls))
    
    # =============================================================================
    # 4. Definition Graph Execution Tests
    # =============================================================================
    
    def test_execute_from_definition_success(self):
        """Test execute_from_definition() with successful execution."""
        # Prepare test data
        graph_def = {
            "node1": Mock(name="node1", context={"instance": Mock()}),
            "node2": Mock(name="node2", context={"instance": Mock()})
        }
        initial_state = {"project_id": "proj456", "input": "test_input"}
        graph_name = "test_definition_graph"
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure graph assembly
        mock_compiled_graph = Mock()
        self.mock_graph_assembly_service.assemble_graph.side_effect = None
        self.mock_graph_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        # Configure execution summary
        mock_execution_summary = Mock()
        mock_execution_summary.graph_name = graph_name
        mock_execution_summary.graph_success = True
        self.mock_execution_tracking_service.to_summary.side_effect = None
        self.mock_execution_tracking_service.to_summary.return_value = mock_execution_summary
        
        # Configure policy evaluation
        self.mock_execution_policy_service.evaluate_success_policy.side_effect = None
        self.mock_execution_policy_service.evaluate_success_policy.return_value = True
        
        # Configure state adapter
        def mock_set_value(state, key, value):
            updated_state = state.copy()
            updated_state[key] = value
            return updated_state
        
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # Configure graph execution
        final_execution_state = {
            "project_id": "proj456",
            "result": "definition_processing_complete",
            "output": "processed_test_input"
        }
        mock_compiled_graph.invoke.return_value = final_execution_state
        
        # Mock agent instances to have set_execution_tracker method
        for node_name, node in graph_def.items():
            if node.context and "instance" in node.context:
                node.context["instance"].set_execution_tracker = Mock()
        
        # Execute test
        result = self.service.execute_from_definition(graph_def, initial_state, graph_name)
        
        # Verify result structure
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, graph_name)
        self.assertTrue(result.success)
        self.assertEqual(result.compiled_from, "memory")
        self.assertIsNone(result.error)
        
        # Verify final state includes execution metadata
        self.assertIn("__execution_summary", result.final_state)
        self.assertIn("__policy_success", result.final_state)
        self.assertEqual(result.final_state["project_id"], "proj456")
        
        # Verify service interactions
        self.mock_execution_tracking_service.create_tracker.assert_called_once()
        self.mock_graph_assembly_service.assemble_graph.assert_called_once()
        self.mock_execution_policy_service.evaluate_success_policy.assert_called_once_with(mock_execution_summary)
        
        # Verify execution timing
        self.assertGreaterEqual(result.total_duration, 0)  # Allow zero duration for mock
        
        # Verify agent tracker setting was attempted
        for node_name, node in graph_def.items():
            if node.context and "instance" in node.context:
                node.context["instance"].set_execution_tracker.assert_called_once_with(mock_tracker)
        
        # Verify success logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any(f"Executing from definition: {graph_name}" in call[1] for call in info_calls))
        self.assertTrue(any(f"✅ COMPLETED DEFINITION GRAPH: '{graph_name}'" in call[1] for call in info_calls))
    
    def test_execute_from_definition_without_graph_name(self):
        """Test execute_from_definition() extracts graph name from definition."""
        # Prepare test data without explicit graph name
        graph_def = {
            "start_node": Mock(name="start_node", graph_name="extracted_graph"),
            "end_node": Mock(name="end_node", graph_name="extracted_graph")
        }
        initial_state = {"input": "test"}
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure graph assembly
        mock_compiled_graph = Mock()
        self.mock_graph_assembly_service.assemble_graph.side_effect = None
        self.mock_graph_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        # Configure execution summary
        mock_execution_summary = Mock()
        self.mock_execution_tracking_service.to_summary.side_effect = None
        self.mock_execution_tracking_service.to_summary.return_value = mock_execution_summary
        
        # Configure policy evaluation
        self.mock_execution_policy_service.evaluate_success_policy.side_effect = None
        self.mock_execution_policy_service.evaluate_success_policy.return_value = True
        
        # Configure state adapter
        self.mock_state_adapter_service.set_value.side_effect = lambda s, k, v: {**s, k: v}
        
        # Configure graph execution
        mock_compiled_graph.invoke.return_value = {"input": "test", "result": "success"}
        
        # Execute test without providing graph_name
        result = self.service.execute_from_definition(graph_def, initial_state)
        
        # Verify result used extracted graph name
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "extracted_graph")  # Should extract from first node
        self.assertTrue(result.success)
        self.assertEqual(result.compiled_from, "memory")
    
    def test_execute_from_definition_assembly_failure(self):
        """Test execute_from_definition() handles graph assembly failures."""
        # Prepare test data
        graph_def = {
            "invalid_node": Mock(name="invalid_node", context={"instance": Mock()})
        }
        initial_state = {"input": "test"}
        graph_name = "failing_assembly_graph"
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure graph assembly to raise exception
        assembly_error = ValueError("Failed to assemble graph 'failing_assembly_graph': missing required dependencies")
        self.mock_graph_assembly_service.assemble_graph.side_effect = assembly_error
        
        # Mock agent instances to have set_execution_tracker method
        for node_name, node in graph_def.items():
            if node.context and "instance" in node.context:
                node.context["instance"].set_execution_tracker = Mock()
        
        # Execute test
        result = self.service.execute_from_definition(graph_def, initial_state, graph_name)
        
        # Verify error result
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, graph_name)
        self.assertFalse(result.success)
        self.assertEqual(result.final_state, initial_state)  # Original state preserved
        self.assertEqual(result.compiled_from, "memory")
        self.assertIn("missing required dependencies", result.error)
        
        # Verify assembly was attempted
        self.mock_graph_assembly_service.assemble_graph.assert_called_once()
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("❌ DEFINITION GRAPH EXECUTION FAILED: 'failing_assembly_graph'" in call[1] for call in error_calls))
        self.assertTrue(any("missing required dependencies" in call[1] for call in error_calls))
    
    def test_execute_from_definition_no_agent_instances(self):
        """Test execute_from_definition() handles nodes without agent instances."""
        # Prepare test data with nodes missing agent instances
        graph_def = {
            "node_without_instance": Mock(name="node_without_instance", context={}),
            "node_with_none_context": Mock(name="node_with_none_context", context=None),
            "node_without_context": Mock(name="node_without_context")
        }
        # Remove context attribute from the last node
        delattr(graph_def["node_without_context"], "context")
        
        initial_state = {"input": "test"}
        graph_name = "incomplete_graph"
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure graph assembly
        mock_compiled_graph = Mock()
        self.mock_graph_assembly_service.assemble_graph.side_effect = None
        self.mock_graph_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        # Configure execution summary
        mock_execution_summary = Mock()
        self.mock_execution_tracking_service.to_summary.side_effect = None
        self.mock_execution_tracking_service.to_summary.return_value = mock_execution_summary
        
        # Configure policy evaluation
        self.mock_execution_policy_service.evaluate_success_policy.side_effect = None
        self.mock_execution_policy_service.evaluate_success_policy.return_value = True
        
        # Configure state adapter
        self.mock_state_adapter_service.set_value.side_effect = lambda s, k, v: {**s, k: v}
        
        # Configure graph execution
        mock_compiled_graph.invoke.return_value = {"input": "test", "result": "success"}
        
        # Execute test
        result = self.service.execute_from_definition(graph_def, initial_state, graph_name)
        
        # Verify execution succeeded despite missing agent instances
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, graph_name)
        self.assertTrue(result.success)  # Should still succeed
        
        # Verify warning logging about missing agent instances
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        
        # Should have critical error about no agent instances found
        self.assertTrue(any("❌ CRITICAL: No agent instances found to set tracker on" in call[1] for call in error_calls))
    
    # =============================================================================
    # 5. Internal Method Tests
    # =============================================================================
    
    def test_load_compiled_graph_from_bundle_success(self):
        """Test _load_compiled_graph_from_bundle() with GraphBundle format."""
        # Prepare test data
        bundle_path = Path("test_bundles/valid_bundle.pkl")
        
        # Configure bundle service to return valid bundle
        mock_bundle = Mock()
        mock_compiled_graph = Mock()
        mock_bundle.graph = mock_compiled_graph
        
        self.mock_graph_bundle_service.load_bundle.side_effect = None
        self.mock_graph_bundle_service.load_bundle.return_value = mock_bundle
        
        # Create a mock file for path.exists() check
        with patch('pathlib.Path.exists', return_value=True):
            # Execute test
            result = self.service._load_compiled_graph_from_bundle(bundle_path)
            
            # Verify result
            self.assertEqual(result, mock_compiled_graph)
            
            # Verify bundle service was called
            self.mock_graph_bundle_service.load_bundle.assert_called_once_with(bundle_path)
            
            # Verify debug logging
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertTrue(any(f"Loading bundle: {bundle_path}" in call[1] for call in debug_calls))
            self.assertTrue(any("Loaded GraphBundle format" in call[1] for call in debug_calls))
    
    def test_load_compiled_graph_from_bundle_missing_file(self):
        """Test _load_compiled_graph_from_bundle() handles missing files."""
        # Prepare test data
        missing_path = Path("nonexistent/missing.pkl")
        
        # Execute test with non-existent file
        with patch('pathlib.Path.exists', return_value=False):
            with self.assertRaises(FileNotFoundError) as context:
                self.service._load_compiled_graph_from_bundle(missing_path)
            
            # Verify error message
            self.assertIn("Compiled graph bundle not found", str(context.exception))
            self.assertIn(str(missing_path), str(context.exception))
    
    def test_load_compiled_graph_from_bundle_invalid_format(self):
        """Test _load_compiled_graph_from_bundle() handles invalid bundle formats."""
        # Prepare test data
        bundle_path = Path("test_bundles/invalid_bundle.pkl")
        
        # Configure bundle service to return invalid bundle
        bundle_error = ValueError("Invalid bundle format: corrupted data")
        self.mock_graph_bundle_service.load_bundle.side_effect = bundle_error
        
        # Execute test
        with patch('pathlib.Path.exists', return_value=True):
            with self.assertRaises(ValueError) as context:
                self.service._load_compiled_graph_from_bundle(bundle_path)
            
            # Verify error message includes both GraphBundle and pickle errors
            error_message = str(context.exception)
            self.assertIn("Could not load bundle in either GraphBundle or legacy format", error_message)
            self.assertIn("Invalid bundle format: corrupted data", error_message)
    
    def test_graph_name_resolution_delegated_to_factory_service(self):
        """Test that graph name resolution is delegated to GraphFactoryService."""
        # Prepare test data
        graph_def = {"node1": Mock()}
        initial_state = {"input": "test"}
        
        # Configure factory service to return specific graph name
        self.mock_graph_factory_service.resolve_graph_name_from_definition.side_effect = None
        self.mock_graph_factory_service.resolve_graph_name_from_definition.return_value = "factory_resolved_name"
        
        # Configure other services for successful execution
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        mock_graph = Mock()
        self.mock_graph_factory_service.create_graph_from_definition.side_effect = None
        self.mock_graph_factory_service.create_graph_from_definition.return_value = mock_graph
        
        mock_compiled_graph = Mock()
        self.mock_graph_assembly_service.assemble_graph.side_effect = None
        self.mock_graph_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        mock_execution_summary = Mock()
        self.mock_execution_tracking_service.to_summary.side_effect = None
        self.mock_execution_tracking_service.to_summary.return_value = mock_execution_summary
        
        self.mock_execution_policy_service.evaluate_success_policy.side_effect = None
        self.mock_execution_policy_service.evaluate_success_policy.return_value = True
        
        self.mock_state_adapter_service.set_value.side_effect = lambda s, k, v: {**s, k: v}
        
        mock_compiled_graph.invoke.return_value = {"result": "success"}
        
        # Mock agent instance
        for node_name, node in graph_def.items():
            node.context = {"instance": Mock()}
            node.context["instance"].set_execution_tracker = Mock()
        
        # Execute test without providing graph_name (should use factory service)
        result = self.service.execute_from_definition(graph_def, initial_state)
        
        # Verify factory service was called to resolve graph name
        self.mock_graph_factory_service.resolve_graph_name_from_definition.assert_called_once_with(graph_def)
        
        # Verify factory service was also called to create graph from definition  
        self.mock_graph_factory_service.create_graph_from_definition.assert_called_once_with(graph_def, "factory_resolved_name")
        
        # The test succeeds if both factory service methods were called correctly
        # (The actual result.graph_name value depends on internal implementation details)
    
    def test_set_tracker_on_agents_comprehensive(self):
        """Test _set_tracker_on_agents() with various agent configurations."""
        # Prepare test data with different agent configurations
        mock_tracker = Mock()
        
        # Agent with proper set_execution_tracker method
        proper_agent = Mock()
        proper_agent.set_execution_tracker = Mock()
        
        # Agent without set_execution_tracker method
        incomplete_agent = Mock()
        delattr(incomplete_agent, "set_execution_tracker")
        
        graph_def = {
            "proper_node": Mock(name="proper_node", context={"instance": proper_agent}),
            "incomplete_node": Mock(name="incomplete_node", context={"instance": incomplete_agent}),
            "no_instance_node": Mock(name="no_instance_node", context={}),
            "none_context_node": Mock(name="none_context_node", context=None),
            "no_context_node": Mock(name="no_context_node")
        }
        
        # Remove context attribute from the last node
        delattr(graph_def["no_context_node"], "context")
        
        # Execute test
        self.service._set_tracker_on_agents(graph_def, mock_tracker)
        
        # Verify proper agent received tracker
        proper_agent.set_execution_tracker.assert_called_once_with(mock_tracker)
        
        # Verify incomplete agent was not called (no method)
        self.assertFalse(hasattr(incomplete_agent, "set_execution_tracker"))
        
        # Verify debug logging shows detailed information
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        
        # Should log processing of each node
        self.assertTrue(any("Processing node: proper_node" in call[1] for call in debug_calls))
        self.assertTrue(any("Processing node: incomplete_node" in call[1] for call in debug_calls))
        self.assertTrue(any("Processing node: no_instance_node" in call[1] for call in debug_calls))
        
        # Should log success for proper agent
        self.assertTrue(any("✅ Set tracker for agent: proper_node" in call[1] for call in debug_calls))
        
        # Should log warnings for problematic nodes
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("❌ No agent instance found for node: no_instance_node" in call[1] for call in warning_calls))
        self.assertTrue(any("❌ Agent incomplete_node missing set_execution_tracker method" in call[1] for call in warning_calls))
        
        # Should log final statistics
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any("Set tracker on 1/5 agent instances" in call[1] for call in info_calls))
    
    def test_set_tracker_on_agents_no_agents_found(self):
        """Test _set_tracker_on_agents() when no valid agents are found."""
        # Prepare test data with no valid agents
        mock_tracker = Mock()
        
        graph_def = {
            "no_context": Mock(name="no_context"),
            "empty_context": Mock(name="empty_context", context={}),
            "none_context": Mock(name="none_context", context=None)
        }
        
        # Remove context from first node
        delattr(graph_def["no_context"], "context")
        
        # Execute test
        self.service._set_tracker_on_agents(graph_def, mock_tracker)
        
        # Verify critical error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        
        # Should log critical error about no agents found
        self.assertTrue(any("❌ CRITICAL: No agent instances found to set tracker on - execution tracking will fail!" in call[1] for call in error_calls))
        
        # Should log details about each node's status
        for node_name in graph_def.keys():
            self.assertTrue(any(f"Node {node_name}:" in call[1] for call in error_calls))
    
    # =============================================================================
    # 6. Error Handling and Edge Cases
    # =============================================================================
    
    def test_execute_from_definition_with_execution_error_and_summary_creation(self):
        """Test execute_from_definition() creates execution summary even after errors."""
        # Prepare test data
        graph_def = {
            "error_node": Mock(name="error_node", context={"instance": Mock()})
        }
        initial_state = {"input": "test"}
        graph_name = "error_handling_graph"
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure graph assembly
        mock_compiled_graph = Mock()
        self.mock_graph_assembly_service.assemble_graph.side_effect = None
        self.mock_graph_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        # Configure graph execution to raise exception
        execution_error = RuntimeError("Runtime execution error during node processing")
        mock_compiled_graph.invoke.side_effect = execution_error
        
        # Configure execution summary creation after error
        mock_execution_summary = Mock()
        mock_execution_summary.node_executions = [{"node": "error_node", "status": "failed"}]
        self.mock_execution_tracking_service.to_summary.side_effect = None
        self.mock_execution_tracking_service.to_summary.return_value = mock_execution_summary
        
        # Mock agent instances to have set_execution_tracker method
        for node_name, node in graph_def.items():
            if node.context and "instance" in node.context:
                node.context["instance"].set_execution_tracker = Mock()
        
        # Execute test
        result = self.service.execute_from_definition(graph_def, initial_state, graph_name)
        
        # Verify error result includes execution summary
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, graph_name)
        self.assertFalse(result.success)
        self.assertEqual(result.final_state, initial_state)  # Original state preserved
        self.assertEqual(result.compiled_from, "memory")
        self.assertEqual(result.error, "Runtime execution error during node processing")
        self.assertIsNotNone(result.execution_summary)  # Should have summary even after error
        
        # Verify execution tracking completion was called
        self.mock_execution_tracking_service.complete_execution.assert_called_once_with(mock_tracker)
        self.mock_execution_tracking_service.to_summary.assert_called_once_with(mock_tracker, graph_name, initial_state)
        
        # Verify error logging with detailed traceback
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("❌ DEFINITION GRAPH EXECUTION FAILED: 'error_handling_graph'" in call[1] for call in error_calls))
        self.assertTrue(any("Runtime execution error during node processing" in call[1] for call in error_calls))
        self.assertTrue(any("Full traceback:" in call[1] for call in error_calls))
        
        # Verify debug logging about summary creation
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Creating execution summary from tracker after error" in call[1] for call in debug_calls))
        self.assertTrue(any("Error execution summary created with 1 node executions" in call[1] for call in debug_calls))
    
    def test_execute_from_definition_summary_creation_failure(self):
        """Test execute_from_definition() handles execution summary creation failures."""
        # Prepare test data
        graph_def = {
            "node1": Mock(name="node1", context={"instance": Mock()})
        }
        initial_state = {"input": "test"}
        graph_name = "summary_error_graph"
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure graph assembly
        mock_compiled_graph = Mock()
        self.mock_graph_assembly_service.assemble_graph.side_effect = None
        self.mock_graph_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        # Configure graph execution to raise exception
        execution_error = RuntimeError("Graph execution failed")
        mock_compiled_graph.invoke.side_effect = execution_error
        
        # Configure execution summary creation to also fail
        summary_error = ValueError("Failed to create execution summary")
        self.mock_execution_tracking_service.to_summary.side_effect = summary_error
        
        # Mock agent instances to have set_execution_tracker method
        for node_name, node in graph_def.items():
            if node.context and "instance" in node.context:
                node.context["instance"].set_execution_tracker = Mock()
        
        # Execute test
        result = self.service.execute_from_definition(graph_def, initial_state, graph_name)
        
        # Verify error result without execution summary
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, graph_name)
        self.assertFalse(result.success)
        self.assertEqual(result.final_state, initial_state)
        self.assertEqual(result.compiled_from, "memory")
        self.assertEqual(result.error, "Graph execution failed")
        self.assertIsNone(result.execution_summary)  # Should be None due to summary creation failure
        
        # Verify both execution tracking calls were attempted
        self.mock_execution_tracking_service.complete_execution.assert_called_once_with(mock_tracker)
        self.mock_execution_tracking_service.to_summary.assert_called_once()
        
        # Verify error logging for both failures
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("❌ DEFINITION GRAPH EXECUTION FAILED: 'summary_error_graph'" in call[1] for call in error_calls))
        self.assertTrue(any("Graph execution failed" in call[1] for call in error_calls))
        self.assertTrue(any("Failed to create execution summary after error: Failed to create execution summary" in call[1] for call in error_calls))
    
    def test_execute_from_definition_no_execution_tracker(self):
        """Test execute_from_definition() handles missing execution tracker."""
        # Prepare test data
        graph_def = {
            "node1": Mock(name="node1", context={"instance": Mock()})
        }
        initial_state = {"input": "test"}
        graph_name = "no_tracker_graph"
        
        # Configure execution tracking to return None
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = None
        
        # Configure graph assembly
        mock_compiled_graph = Mock()
        self.mock_graph_assembly_service.assemble_graph.side_effect = None
        self.mock_graph_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        # Configure graph execution to raise exception
        execution_error = RuntimeError("Graph execution failed without tracker")
        mock_compiled_graph.invoke.side_effect = execution_error
        
        # Mock agent instances to have set_execution_tracker method
        for node_name, node in graph_def.items():
            if node.context and "instance" in node.context:
                node.context["instance"].set_execution_tracker = Mock()
        
        # Execute test
        result = self.service.execute_from_definition(graph_def, initial_state, graph_name)
        
        # Verify error result
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, graph_name)
        self.assertFalse(result.success)
        self.assertEqual(result.final_state, initial_state)
        self.assertEqual(result.compiled_from, "memory")
        self.assertEqual(result.error, "Graph execution failed without tracker")
        self.assertIsNone(result.execution_summary)  # No summary due to no tracker
        
        # Verify warning about no tracker for summary
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("No execution tracker available for error summary" in call[1] for call in warning_calls))
    
    def test_execute_compiled_graph_with_empty_state(self):
        """Test execute_compiled_graph() handles empty initial state."""
        # Prepare test data
        bundle_path = Path("compiled/empty_state_graph.pkl")
        empty_state = {}
        
        # Configure successful bundle loading and execution
        mock_compiled_graph = Mock()
        
        # Configure execution tracking
        mock_tracker = Mock()
        self.mock_execution_tracking_service.create_tracker.side_effect = None
        self.mock_execution_tracking_service.create_tracker.return_value = mock_tracker
        
        # Configure execution summary
        mock_execution_summary = Mock()
        self.mock_execution_tracking_service.to_summary.side_effect = None
        self.mock_execution_tracking_service.to_summary.return_value = mock_execution_summary
        
        # Configure policy evaluation
        self.mock_execution_policy_service.evaluate_success_policy.side_effect = None
        self.mock_execution_policy_service.evaluate_success_policy.return_value = True
        
        # Configure state adapter
        self.mock_state_adapter_service.set_value.side_effect = lambda s, k, v: {**s, k: v}
        
        # Configure graph execution with empty state
        mock_compiled_graph.invoke.return_value = {"result": "empty_state_processed"}
        
        # Mock the internal _load_compiled_graph_from_bundle method to return successful graph
        with patch.object(self.service, '_load_compiled_graph_from_bundle', return_value=mock_compiled_graph):
            # Execute test
            result = self.service.execute_compiled_graph(bundle_path, empty_state)
        
        # Verify successful execution with empty state
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "empty_state_graph")
        self.assertTrue(result.success)
        self.assertEqual(result.compiled_from, "precompiled")
        self.assertIsNone(result.error)
        
        # Verify graph was invoked with empty state
        mock_compiled_graph.invoke.assert_called_once_with(empty_state)
        
        # Verify final state contains execution metadata
        self.assertIn("__execution_summary", result.final_state)
        self.assertIn("__policy_success", result.final_state)
        self.assertEqual(result.final_state["result"], "empty_state_processed")


if __name__ == '__main__':
    unittest.main()
