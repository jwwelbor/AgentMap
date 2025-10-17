"""
Unit tests for GraphAgent using pure Mock objects and established testing patterns.

This test suite validates the graph agent's subgraph execution functionality,
state mapping capabilities, and service integration patterns.
"""
import unittest
from unittest.mock import Mock
from typing import Dict, Any

from agentmap.agents.builtins.graph_agent import GraphAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphAgent(unittest.TestCase):
    """Unit tests for GraphAgent using pure Mock objects."""
    
    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Create custom service mocks (not part of standard protocols yet)
        self.mock_graph_runner_service = Mock()
        self.mock_function_resolution_service = Mock()
        self.mock_graph_bundle_service = Mock()  # Add mock for bundle service
        
        # Configure graph runner service mock
        self.mock_graph_runner_service.run.return_value = {
            "output": "Mock subgraph result",
            "graph_success": True,
            "last_action_success": True
        }
        
        # Configure graph bundle service mock
        from agentmap.models.graph_bundle import GraphBundle
        from agentmap.models.node import Node
        mock_bundle = GraphBundle.create_metadata(
            graph_name="test_subgraph",
            nodes={"node1": Node(name="node1", agent_type="TestAgent")},
            required_agents=set(),
            required_services=set(),
            function_mappings={},
            csv_hash="test_hash"
        )
        self.mock_graph_bundle_service.get_or_create_bundle.return_value = (
            mock_bundle,
            False,
        )
        
        # Configure function resolution service mock
        self.mock_function_resolution_service.extract_func_ref.return_value = "test.mapping_function"
        self.mock_function_resolution_service.import_function.return_value = lambda x: {"mapped": x.get("input", "default")}
        
        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()
        
        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(GraphAgent)
    
    def create_graph_agent(self, context=None, **kwargs):
        """Helper to create graph agent with common configuration."""
        default_context = {
            "input_fields": ["data1", "data2"],
            "output_field": "result",
            "description": "Test graph agent"
        }
        
        if context is not None:
            if isinstance(context, dict):
                default_context.update(context)
                context = default_context
        else:
            context = default_context
        
        return GraphAgent(
            name="test_graph_agent",
            prompt="test_subgraph",  # subgraph name
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            **kwargs
        )
    
    # =============================================================================
    # 1. Agent Initialization and Context Parsing Tests
    # =============================================================================
    
    def test_agent_initialization_with_dict_context(self):
        """Test graph agent initialization with dict context."""
        context = {
            "input_fields": ["input1", "input2"],
            "output_field": "output",
            "csv_path": "graphs/subgraph.csv",
            "execution_mode": "separate"
        }
        
        agent = self.create_graph_agent(context=context)
        
        # Verify basic configuration
        self.assertEqual(agent.name, "test_graph_agent")
        self.assertEqual(agent.prompt, "test_subgraph")
        self.assertEqual(agent.subgraph_name, "test_subgraph")
        self.assertEqual(agent.input_fields, ["input1", "input2"])
        self.assertEqual(agent.output_field, "output")
        
        # Verify context parsing
        self.assertEqual(agent.csv_path, "graphs/subgraph.csv")
        self.assertEqual(agent.execution_mode, "separate")
        
        # Verify infrastructure services
        self.assertIsNotNone(agent.logger)
        self.assertIsNotNone(agent.execution_tracking_service)
        self.assertIsNotNone(agent.state_adapter_service)
        
        # Verify custom services are not configured by default
        with self.assertRaises(ValueError):
            _ = agent.graph_runner_service
        with self.assertRaises(ValueError):
            _ = agent.function_resolution_service
    
    def test_agent_initialization_with_string_context(self):
        """Test graph agent initialization with string context (CSV path)."""
        agent = GraphAgent(
            name="test_agent",
            prompt="subgraph_name",
            context="graphs/workflow.csv",
            logger=self.mock_logger
        )
        
        # Verify string context parsing
        self.assertEqual(agent.csv_path, "graphs/workflow.csv")
        self.assertEqual(agent.execution_mode, "separate")  # Default
        self.assertEqual(agent.subgraph_name, "subgraph_name")
    
    def test_agent_initialization_with_empty_context(self):
        """Test graph agent initialization with empty context."""
        agent = GraphAgent(
            name="test_agent",
            prompt="subgraph_name",
            context=None,
            logger=self.mock_logger
        )
        
        # Verify defaults
        self.assertIsNone(agent.csv_path)
        self.assertEqual(agent.execution_mode, "separate")
        self.assertEqual(agent.subgraph_name, "subgraph_name")
    
    def test_agent_initialization_with_whitespace_string_context(self):
        """Test graph agent initialization with whitespace string context."""
        agent = GraphAgent(
            name="test_agent",
            prompt="subgraph_name",
            context="   ",  # Whitespace only
            logger=self.mock_logger
        )
        
        # Should treat as empty
        self.assertIsNone(agent.csv_path)
        self.assertEqual(agent.execution_mode, "separate")
    
    def test_agent_initialization_with_execution_mode_native(self):
        """Test graph agent initialization with native execution mode."""
        context = {
            "execution_mode": "native",
            "csv_path": "graphs/test.csv"
        }
        
        agent = self.create_graph_agent(context=context)
        
        self.assertEqual(agent.execution_mode, "native")
        self.assertEqual(agent.csv_path, "graphs/test.csv")
    
    # =============================================================================
    # 2. Service Configuration Tests
    # =============================================================================
    
    def test_graph_runner_service_configuration(self):
        """Test graph runner service configuration."""
        agent = self.create_graph_agent()
        
        # Initially no service
        with self.assertRaises(ValueError) as cm:
            _ = agent.graph_runner_service
        self.assertIn("Graph runner service not configured", str(cm.exception))
        self.assertIn("test_graph_agent", str(cm.exception))
        
        # Configure service
        agent.configure_graph_runner_service(self.mock_graph_runner_service)
        
        # Now service should be accessible
        self.assertEqual(agent.graph_runner_service, self.mock_graph_runner_service)
        
        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        service_configured = any("Graph runner service configured" in call[1] for call in debug_calls)
        self.assertTrue(service_configured, f"Expected service configured log, got: {debug_calls}")
    
    def test_function_resolution_service_configuration(self):
        """Test function resolution service configuration."""
        agent = self.create_graph_agent()
        
        # Initially no service
        with self.assertRaises(ValueError) as cm:
            _ = agent.function_resolution_service
        self.assertIn("Function resolution service not configured", str(cm.exception))
        self.assertIn("test_graph_agent", str(cm.exception))
        
        # Configure service
        agent.configure_function_resolution_service(self.mock_function_resolution_service)
        
        # Now service should be accessible
        self.assertEqual(agent.function_resolution_service, self.mock_function_resolution_service)
        
        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        service_configured = any("Function resolution service configured" in call[1] for call in debug_calls)
        self.assertTrue(service_configured, f"Expected service configured log, got: {debug_calls}")
    
    def test_service_error_when_not_configured(self):
        """Test clear errors when services are accessed but not configured."""
        agent = self.create_graph_agent()
        
        # Test graph runner service error
        with self.assertRaises(ValueError) as cm:
            _ = agent.graph_runner_service
        error_msg = str(cm.exception)
        self.assertIn("Graph runner service not configured", error_msg)
        self.assertIn("test_graph_agent", error_msg)
        
        # Test function resolution service error
        with self.assertRaises(ValueError) as cm:
            _ = agent.function_resolution_service
        error_msg = str(cm.exception)
        self.assertIn("Function resolution service not configured", error_msg)
        self.assertIn("test_graph_agent", error_msg)
    
    # =============================================================================
    # 3. Subgraph State Preparation Tests
    # =============================================================================
    
    def test_prepare_subgraph_state_direct_passthrough(self):
        """Test subgraph state preparation with direct field passthrough."""
        context = {"input_fields": ["field1", "field2"]}
        agent = self.create_graph_agent(context=context)
        
        inputs = {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3"  # Not in input_fields
        }
        
        result = agent._prepare_subgraph_state(inputs)
        
        # Should only include specified fields
        expected = {"field1": "value1", "field2": "value2"}
        self.assertEqual(result, expected)
    
    def test_prepare_subgraph_state_no_mapping_all_fields(self):
        """Test subgraph state preparation with no input fields (pass all)."""
        context = {"input_fields": []}
        agent = self.create_graph_agent(context=context)
        
        inputs = {
            "field1": "value1",
            "field2": "value2"
        }
        
        result = agent._prepare_subgraph_state(inputs)
        
        # Should pass entire state
        self.assertEqual(result, inputs)
        self.assertIsNot(result, inputs)  # Should be a copy
    
    def test_prepare_subgraph_state_field_mapping(self):
        """Test subgraph state preparation with field-to-field mapping."""
        context = {"input_fields": ["target1=source1", "target2=source2", "direct"]}
        agent = self.create_graph_agent(context=context)
        
        inputs = {
            "source1": "mapped_value1",
            "source2": "mapped_value2",
            "direct": "direct_value",
            "unused": "ignored"
        }
        
        result = agent._prepare_subgraph_state(inputs)
        
        # Should apply field mappings
        expected = {
            "target1": "mapped_value1",
            "target2": "mapped_value2",
            "direct": "direct_value"
        }
        self.assertEqual(result, expected)
    
    def test_prepare_subgraph_state_function_mapping(self):
        """Test subgraph state preparation with function mapping."""
        context = {"input_fields": ["func:test.mapping_function"]}
        agent = self.create_graph_agent(context=context)
        agent.configure_function_resolution_service(self.mock_function_resolution_service)
        
        inputs = {"input": "test_data"}
        
        result = agent._prepare_subgraph_state(inputs)
        
        # Should apply function mapping
        expected = {"mapped": "test_data"}
        self.assertEqual(result, expected)
        
        # Verify function resolution service was called
        self.mock_function_resolution_service.extract_func_ref.assert_called_with("func:test.mapping_function")
        self.mock_function_resolution_service.import_function.assert_called_with("test.mapping_function")
    
    def test_prepare_subgraph_state_function_mapping_error(self):
        """Test subgraph state preparation handles function mapping errors."""
        context = {"input_fields": ["func:invalid.function"]}
        agent = self.create_graph_agent(context=context)
        agent.configure_function_resolution_service(self.mock_function_resolution_service)
        
        # Configure service to raise error
        self.mock_function_resolution_service.import_function.side_effect = Exception("Import error")
        
        inputs = {"input": "test_data"}
        
        result = agent._prepare_subgraph_state(inputs)
        
        # Should fall back to original inputs
        self.assertEqual(result, inputs)
        self.assertIsNot(result, inputs)  # Should be a copy
        
        # Should log error
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("Error in mapping function" in call[1] for call in error_calls))
    
    def test_prepare_subgraph_state_function_mapping_invalid_return(self):
        """Test subgraph state preparation handles invalid function return type."""
        context = {"input_fields": ["func:test.bad_function"]}
        agent = self.create_graph_agent(context=context)
        agent.configure_function_resolution_service(self.mock_function_resolution_service)
        
        # Configure function to return non-dict
        self.mock_function_resolution_service.import_function.return_value = lambda x: "not a dict"
        
        inputs = {"input": "test_data"}
        
        result = agent._prepare_subgraph_state(inputs)
        
        # Should fall back to original inputs
        self.assertEqual(result, inputs)
        self.assertIsNot(result, inputs)  # Should be a copy
        
        # Should log warning
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("returned non-dict" in call[1] for call in warning_calls))
    
    def test_prepare_subgraph_state_function_mapping_invalid_reference(self):
        """Test subgraph state preparation handles invalid function reference."""
        context = {"input_fields": ["func:invalid"]}
        agent = self.create_graph_agent(context=context)
        agent.configure_function_resolution_service(self.mock_function_resolution_service)
        
        # Configure service to return None for invalid reference
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        
        inputs = {"input": "test_data"}
        
        result = agent._prepare_subgraph_state(inputs)
        
        # Should fall back to original inputs
        self.assertEqual(result, inputs)
        self.assertIsNot(result, inputs)  # Should be a copy
        
        # Should log warning
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("Invalid function reference" in call[1] for call in warning_calls))
    
    def test_apply_field_mapping_with_missing_source_fields(self):
        """Test field mapping when source fields are missing from inputs."""
        context = {"input_fields": ["target1=missing_source", "target2=existing"]}
        agent = self.create_graph_agent(context=context)
        
        inputs = {"existing": "value", "other": "ignored"}
        
        result = agent._prepare_subgraph_state(inputs)
        
        # Should only include mappings where source exists
        expected = {"target2": "value"}
        self.assertEqual(result, expected)
    
    # =============================================================================
    # 4. Subgraph Execution Tests
    # =============================================================================
    
    def test_process_successful_subgraph_execution(self):
        """Test successful subgraph execution."""
        # Fix: Provide CSV path in context so bundle can be created
        context = {"csv_path": "graphs/test_subgraph.csv"}
        agent = self.create_graph_agent(context=context)
        agent.configure_graph_runner_service(self.mock_graph_runner_service)
        agent.configure_graph_bundle_service(self.mock_graph_bundle_service)
        
        inputs = {"data1": "value1", "data2": "value2"}
        
        result = agent.process(inputs)
        
        # Verify bundle service was called to get the bundle
        self.mock_graph_bundle_service.get_or_create_bundle.assert_called_once()
        bundle_call_args = self.mock_graph_bundle_service.get_or_create_bundle.call_args
        # Use Path.as_posix() to normalize path separators for cross-platform testing
        actual_path = bundle_call_args.kwargs["csv_path"]
        expected_path = "graphs/test_subgraph.csv"
        self.assertEqual(str(actual_path).replace("\\", "/"), expected_path)
        self.assertEqual(bundle_call_args.kwargs["graph_name"], "test_subgraph")
        
        # Verify subgraph was executed with bundle
        self.mock_graph_runner_service.run.assert_called_once()
        call_args = self.mock_graph_runner_service.run.call_args
        
        # Verify call parameters - now uses bundle instead of graph_name
        self.assertIn("bundle", call_args.kwargs)
        self.assertEqual(call_args.kwargs["initial_state"], {"data1": "value1", "data2": "value2"})
        self.assertTrue(call_args.kwargs["is_subgraph"])
        
        # Verify result
        expected = {"output": "Mock subgraph result", "graph_success": True, "last_action_success": True}
        self.assertEqual(result, expected)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        execution_logged = any("Executing subgraph: test_subgraph" in call[1] for call in info_calls)
        success_logged = any("Subgraph execution completed successfully" in call[1] for call in info_calls)
        self.assertTrue(execution_logged)
        self.assertTrue(success_logged)
    
    def test_process_with_csv_path_context(self):
        """Test subgraph execution with CSV path specified."""
        context = {"csv_path": "graphs/custom.csv"}
        agent = self.create_graph_agent(context=context)
        agent.configure_graph_runner_service(self.mock_graph_runner_service)
        agent.configure_graph_bundle_service(self.mock_graph_bundle_service)
        
        inputs = {"data": "value"}
        
        agent.process(inputs)
        
        # Verify bundle service was called to get bundle for the subgraph
        self.mock_graph_bundle_service.get_or_create_bundle.assert_called()
    
    def test_process_without_configured_service(self):
        """Test process method fails gracefully when graph runner service not configured."""
        agent = self.create_graph_agent()
        
        inputs = {"data": "value"}
        
        with self.assertRaises(ValueError) as cm:
            agent.process(inputs)
        
        self.assertIn("Graph runner service not configured", str(cm.exception))
    
    def test_process_with_subgraph_execution_error(self):
        """Test process handles subgraph execution errors gracefully."""
        # Fix: Provide CSV path in context so bundle can be created and error path can be tested
        context = {"csv_path": "graphs/test_subgraph.csv"}
        agent = self.create_graph_agent(context=context)
        agent.configure_graph_runner_service(self.mock_graph_runner_service)
        agent.configure_graph_bundle_service(self.mock_graph_bundle_service)
        
        # Configure service to raise error
        self.mock_graph_runner_service.run.side_effect = Exception("Subgraph execution failed")
        
        inputs = {"data": "value"}
        
        result = agent.process(inputs)
        
        # Should return error result
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("Failed to execute subgraph 'test_subgraph'", result["error"])
        self.assertIn("Subgraph execution failed", result["error"])
        self.assertFalse(result["last_action_success"])
        
        # Should log error
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("Error executing subgraph" in call[1] for call in error_calls))
    
    # =============================================================================
    # 5. Result Processing Tests
    # =============================================================================
    
    def test_process_subgraph_result_default_behavior(self):
        """Test subgraph result processing with default behavior (return entire result)."""
        agent = self.create_graph_agent()
        
        result = {"field1": "value1", "field2": "value2", "graph_success": True}
        
        processed = agent._process_subgraph_result(result)
        
        # Should return entire result by default
        self.assertEqual(processed, result)
    
    def test_process_subgraph_result_with_specific_output_field(self):
        """Test subgraph result processing with specific output field."""
        context = {"output_field": "target_field"}
        agent = self.create_graph_agent(context=context)
        
        result = {"target_field": "extracted_value", "other_field": "ignored"}
        
        processed = agent._process_subgraph_result(result)
        
        # Should extract only the specified field
        self.assertEqual(processed, "extracted_value")
    
    def test_process_subgraph_result_with_output_field_mapping(self):
        """Test subgraph result processing with output field mapping."""
        context = {"output_field": "target=source"}
        agent = self.create_graph_agent(context=context)
        
        result = {"source": "mapped_value", "other": "ignored"}
        
        processed = agent._process_subgraph_result(result)
        
        # Should apply output mapping
        expected = {"target": "mapped_value"}
        self.assertEqual(processed, expected)
    
    def test_process_subgraph_result_with_missing_output_field(self):
        """Test subgraph result processing when specified output field is missing."""
        context = {"output_field": "missing_field"}
        agent = self.create_graph_agent(context=context)
        
        result = {"existing_field": "value"}
        
        processed = agent._process_subgraph_result(result)
        
        # Should return entire result when specified field is missing
        self.assertEqual(processed, result)
    
    def test_process_subgraph_result_with_missing_mapped_source_field(self):
        """Test subgraph result processing when mapped source field is missing."""
        context = {"output_field": "target=missing_source"}
        agent = self.create_graph_agent(context=context)
        
        result = {"existing_field": "value"}
        
        processed = agent._process_subgraph_result(result)
        
        # Should return entire result when mapped source field is missing
        self.assertEqual(processed, result)
    
    # =============================================================================
    # 6. Integration Tests
    # =============================================================================
    
    def test_run_method_integration(self):
        """Test the inherited run method works with GraphAgent."""
        # Fix: Provide CSV path in context so bundle can be created
        context = {"csv_path": "graphs/test_subgraph.csv"}
        agent = self.create_graph_agent(context=context)
        agent.configure_graph_runner_service(self.mock_graph_runner_service)
        agent.configure_graph_bundle_service(self.mock_graph_bundle_service)
        
        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # Configure execution tracker methods
        self.mock_tracker.record_node_start = Mock(return_value=None)
        self.mock_tracker.record_node_result = Mock(return_value=None)
        
        # IMPORTANT: Set execution tracker before calling run() - required by BaseAgent
        agent.set_execution_tracker(self.mock_tracker)
        
        # Test state
        test_state = {
            "data1": "input_value1",
            "data2": "input_value2",
            "other_field": "preserved"
        }
        
        # Execute run method
        result_state = agent.run(test_state)
        
        # Verify subgraph was executed
        self.mock_graph_runner_service.run.assert_called_once()
        
        # Verify state was updated with result
        self.assertIn("result", result_state)
        self.assertEqual(result_state["result"]["output"], "Mock subgraph result")
        
        # Verify original fields are preserved
        self.assertEqual(result_state["other_field"], "preserved")
        
        # Verify tracking calls
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()
    
    def test_post_process_with_execution_summary(self):
        """Test post-processing handles execution summaries from subgraphs."""
        agent = self.create_graph_agent()
        
        # Mock execution tracker with subgraph recording capability
        self.mock_tracker.record_subgraph_execution = Mock()
        
        # CRITICAL: Set execution tracker on agent before testing post-process
        agent.set_execution_tracker(self.mock_tracker)
        
        # Mock output with execution summary
        output = {
            "result": "subgraph_output",
            "__execution_summary": {
                "graph_name": "test_subgraph",
                "success": True,
                "duration": 1.5
            }
        }
        
        # Test state
        test_state = {"existing": "value"}
        
        # Execute post-processing
        updated_state, processed_output = agent._post_process(test_state, {}, output)
        
        # Verify execution summary was recorded
        self.mock_tracker.record_subgraph_execution.assert_called_once_with(
            "test_subgraph",
            {"graph_name": "test_subgraph", "success": True, "duration": 1.5}
        )
        
        # Verify execution summary was removed from output
        self.assertEqual(processed_output, {"result": "subgraph_output"})
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        summary_logged = any("Recorded subgraph execution in parent tracker" in call[1] for call in debug_calls)
        self.assertTrue(summary_logged)
    
    def test_post_process_without_subgraph_recording_capability(self):
        """Test post-processing when tracker doesn't support subgraph recording."""
        agent = self.create_graph_agent()
        
        # CRITICAL: Set execution tracker on agent before testing post-process
        agent.set_execution_tracker(self.mock_tracker)
        
        # Don't add record_subgraph_execution method to tracker
        
        output = {
            "result": "subgraph_output",
            "__execution_summary": {"test": "summary"}
        }
        
        test_state = {"existing": "value"}
        
        # Should not raise error
        updated_state, processed_output = agent._post_process(test_state, {}, output)
        
        # Should still remove execution summary from output
        self.assertEqual(processed_output, {"result": "subgraph_output"})
    
    def test_post_process_sets_success_state(self):
        """Test post-processing sets success state based on subgraph result."""
        agent = self.create_graph_agent()
        
        # CRITICAL: Set execution tracker on agent before testing post-process
        agent.set_execution_tracker(self.mock_tracker)
        
        # Configure state adapter to return updated state
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        output = {"graph_success": False, "error": "Some error"}
        test_state = {"existing": "value"}
        
        updated_state, processed_output = agent._post_process(test_state, {}, output)
        
        # Verify success state was set via state adapter service
        self.mock_state_adapter_service.set_value.assert_called_once_with(test_state, "last_action_success", False)
        
        # Verify updated state contains the success flag
        self.assertEqual(updated_state["last_action_success"], False)
        self.assertEqual(updated_state["existing"], "value")
    
    # =============================================================================
    # 7. Logging Integration Tests
    # =============================================================================
    
    def test_logging_integration_detailed(self):
        """Test that agent properly logs subgraph operations."""
        # Fix: Provide CSV path in context so bundle can be created
        context = {"csv_path": "graphs/test_subgraph.csv"}
        agent = self.create_graph_agent(context=context)
        agent.configure_graph_runner_service(self.mock_graph_runner_service)
        agent.configure_function_resolution_service(self.mock_function_resolution_service)
        agent.configure_graph_bundle_service(self.mock_graph_bundle_service)
        
        inputs = {"data1": "test_data", "data2": "more_data"}
        
        # Execute process to generate log calls
        agent.process(inputs)
        
        # Verify logger was called
        logger_calls = self.mock_logger.calls
        
        # Should have info calls for execution
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) >= 2)
        
        # Verify specific log messages
        log_messages = [call[1] for call in info_calls]
        execution_logged = any("Executing subgraph: test_subgraph" in msg for msg in log_messages)
        success_logged = any("Subgraph execution completed successfully" in msg for msg in log_messages)
        
        self.assertTrue(execution_logged, f"Expected execution logged, got: {log_messages}")
        self.assertTrue(success_logged, f"Expected success logged, got: {log_messages}")
    
    def test_logging_field_mapping_operations(self):
        """Test logging for field mapping operations."""
        # Fix: Add CSV path to context so bundle can be created
        context = {"input_fields": ["target1=source1", "target2=source2"], "csv_path": "graphs/test_subgraph.csv"}
        agent = self.create_graph_agent(context=context)
        agent.configure_graph_runner_service(self.mock_graph_runner_service)
        agent.configure_graph_bundle_service(self.mock_graph_bundle_service)
        
        inputs = {"source1": "value1", "source2": "value2"}
        
        agent.process(inputs)
        
        # Verify mapping operations are logged
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        debug_messages = [call[1] for call in debug_calls]
        
        mapped_logged = any("Mapped source1 -> target1" in msg for msg in debug_messages)
        self.assertTrue(mapped_logged, f"Expected mapping logged, got: {debug_messages}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
