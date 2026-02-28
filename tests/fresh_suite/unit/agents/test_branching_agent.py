"""
Unit tests for BranchingAgent using pure Mock objects and established testing patterns.

This test suite validates the branching agent's configurable decision logic and its critical
role in workflow testing and conditional execution paths.
"""

import unittest
from unittest.mock import Mock

from agentmap.agents.builtins.branching_agent import BranchingAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestBranchingAgent(unittest.TestCase):
    """Unit tests for BranchingAgent using pure Mock objects."""

    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(BranchingAgent)

    def create_branching_agent(self, **context_overrides):
        """Helper to create branching agent with common configuration."""
        context = {
            "input_fields": ["success"],
            "output_field": "result",
            "description": "Test branching agent for workflow control",
            **context_overrides,
        }

        return BranchingAgent(
            name="test_branching",
            prompt="Branch based on input conditions",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

    # =============================================================================
    # 1. Agent Initialization and Configuration Tests
    # =============================================================================

    def test_agent_initialization_default_configuration(self):
        """Test branching agent initializes with default configuration."""
        agent = self.create_branching_agent()

        # Verify basic configuration
        self.assertEqual(agent.name, "test_branching")
        self.assertEqual(agent.prompt, "Branch based on input conditions")

        # Verify default configuration
        self.assertEqual(agent.success_field, "success")
        self.assertIn(True, agent.success_values)
        self.assertIn("true", agent.success_values)
        self.assertIn("yes", agent.success_values)
        self.assertIn(False, agent.failure_values)
        self.assertIn("false", agent.failure_values)
        self.assertIn("no", agent.failure_values)
        self.assertTrue(agent.default_result)

        # Verify infrastructure services
        self.assertIsNotNone(agent.logger)
        self.assertIsNotNone(agent.execution_tracking_service)
        self.assertIsNotNone(agent.state_adapter_service)

    def test_agent_initialization_custom_configuration(self):
        """Test branching agent with custom configuration."""
        agent = self.create_branching_agent(
            success_field="status",
            success_values=["PASSED", "OK", "GOOD"],
            failure_values=["FAILED", "ERROR", "BAD"],
            default_result=False,
            fallback_fields=["result", "outcome"],
        )

        # Verify custom configuration
        self.assertEqual(agent.success_field, "status")
        self.assertEqual(
            agent.success_values, ["passed", "ok", "good"]
        )  # Normalized to lowercase
        self.assertEqual(agent.failure_values, ["failed", "error", "bad"])
        self.assertFalse(agent.default_result)
        self.assertEqual(agent.fallback_fields, ["result", "outcome"])

    def test_agent_protocol_compliance(self):
        """Test that BranchingAgent correctly implements (or doesn't implement) service protocols."""
        agent = self.create_branching_agent()

        # BranchingAgent should NOT implement business service protocols
        self.assertFalse(isinstance(agent, LLMCapableAgent))
        self.assertFalse(isinstance(agent, StorageCapableAgent))

        # Verify service access raises appropriate errors for unconfigured services
        with self.assertRaises(ValueError) as cm:
            _ = agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            _ = agent.storage_service
        self.assertIn("Storage service not configured", str(cm.exception))

    # =============================================================================
    # 2. Default Configuration Success Determination Tests
    # =============================================================================

    def test_determine_success_with_default_field_boolean_values(self):
        """Test success determination with boolean values in default 'success' field."""
        agent = self.create_branching_agent()

        # Test True
        success = agent._determine_success({"success": True})
        self.assertTrue(success)

        # Test False
        success = agent._determine_success({"success": False})
        self.assertFalse(success)

    def test_determine_success_with_default_field_string_values(self):
        """Test success determination with string values in default 'success' field."""
        agent = self.create_branching_agent()

        # Test success strings (case insensitive)
        success_strings = [
            "true",
            "True",
            "TRUE",
            "yes",
            "Yes",
            "success",
            "succeed",
            "1",
            "t",
            "y",
        ]
        for value in success_strings:
            with self.subTest(value=value):
                success = agent._determine_success({"success": value})
                self.assertTrue(success, f"Expected '{value}' to be successful")

        # Test failure strings
        failure_strings = [
            "false",
            "False",
            "FALSE",
            "no",
            "No",
            "failure",
            "fail",
            "0",
            "f",
            "n",
        ]
        for value in failure_strings:
            with self.subTest(value=value):
                success = agent._determine_success({"success": value})
                self.assertFalse(success, f"Expected '{value}' to be failure")

    def test_determine_success_with_default_field_numeric_values(self):
        """Test success determination with numeric values in default 'success' field."""
        agent = self.create_branching_agent()

        # Test truthy numbers
        truthy_numbers = [1, 2, -1, 0.1, 1.0]
        for value in truthy_numbers:
            with self.subTest(value=value):
                success = agent._determine_success({"success": value})
                self.assertTrue(success, f"Expected {value} to be successful")

        # Test falsy numbers
        falsy_numbers = [0, 0.0]
        for value in falsy_numbers:
            with self.subTest(value=value):
                success = agent._determine_success({"success": value})
                self.assertFalse(success, f"Expected {value} to be failure")

    def test_determine_success_with_fallback_fields(self):
        """Test success determination falls back to other fields when 'success' not found."""
        agent = self.create_branching_agent()

        # Test fallback to should_succeed
        success = agent._determine_success({"should_succeed": True})
        self.assertTrue(success)

        # Test fallback to succeed
        success = agent._determine_success({"succeed": "yes"})
        self.assertTrue(success)

        # Test fallback to branch
        success = agent._determine_success({"branch": False})
        self.assertFalse(success)

    def test_determine_success_with_no_relevant_fields(self):
        """Test success determination uses default when no relevant fields found."""
        agent = self.create_branching_agent()

        # Should use default (True)
        success = agent._determine_success({"irrelevant": "data"})
        self.assertTrue(success)

        # Test with custom default
        agent_false_default = self.create_branching_agent(default_result=False)
        success = agent_false_default._determine_success({"irrelevant": "data"})
        self.assertFalse(success)

    # =============================================================================
    # 3. Custom Configuration Tests
    # =============================================================================

    def test_automatic_success_field_from_input_fields(self):
        """Test that success_field automatically defaults to first input field."""
        # Test with single input field
        agent1 = self.create_branching_agent(input_fields=["status"])
        self.assertEqual(agent1.success_field, "status")

        # Test with multiple input fields (uses first one)
        agent2 = self.create_branching_agent(
            input_fields=["result", "details", "timestamp"]
        )
        self.assertEqual(agent2.success_field, "result")

        # Test with no input fields (defaults to "success")
        agent3 = self.create_branching_agent(input_fields=[])
        self.assertEqual(agent3.success_field, "success")

    def test_custom_success_field_configuration(self):
        """Test agent with custom success field (override of input field)."""
        agent = self.create_branching_agent(
            input_fields=["primary_field", "secondary_field"],
            success_field="secondary_field",  # Override: check secondary_field instead of primary_field
        )

        # Should check 'secondary_field' instead of default first input field
        success = agent._determine_success(
            {"primary_field": False, "secondary_field": True}
        )
        self.assertTrue(success)  # Uses 'secondary_field', ignores 'primary_field'

        # Verify it's using the override field
        self.assertEqual(agent.success_field, "secondary_field")

    def test_custom_success_values_configuration(self):
        """Test agent with custom success values."""
        agent = self.create_branching_agent(
            success_values=["PASSED", "COMPLETED", "OK"],
            failure_values=["FAILED", "ERROR"],
        )

        # Test custom success values
        success = agent._determine_success({"success": "PASSED"})
        self.assertTrue(success)

        success = agent._determine_success({"success": "completed"})  # Case insensitive
        self.assertTrue(success)

        # Test custom failure values
        success = agent._determine_success({"success": "FAILED"})
        self.assertFalse(success)

        # Test value not in either list (should use default)
        success = agent._determine_success({"success": "UNKNOWN"})
        self.assertTrue(success)  # Default is True

    def test_custom_fallback_fields_configuration(self):
        """Test agent with custom fallback fields."""
        agent = self.create_branching_agent(
            success_field="primary", fallback_fields=["secondary", "tertiary"]
        )

        # Should check fields in order: primary -> secondary -> tertiary
        success = agent._determine_success(
            {"tertiary": False, "secondary": True, "other": "ignored"}
        )
        self.assertTrue(success)  # Uses 'secondary' field

        # Should use 'tertiary' if 'secondary' not found
        success = agent._determine_success({"tertiary": False, "other": "ignored"})
        self.assertFalse(success)  # Uses 'tertiary' field

    # =============================================================================
    # 4. Process Method Tests (Fixed)
    # =============================================================================

    def test_process_with_success_input_fixed(self):
        """Test process method with successful input (single field)."""
        agent = self.create_branching_agent()

        # FIXED: Only provide success field, not conflicting fields
        inputs = {"success": True}

        result = agent.process(inputs)

        # Should describe the successful branching decision
        self.assertIn("BRANCH:", result)
        self.assertIn("test_branching", result)
        self.assertIn("SUCCEED", result)
        self.assertIn("'success' = True", result)
        self.assertIn("Branch based on input conditions", result)

    def test_process_with_failure_input_fixed(self):
        """Test process method with failure input (single field)."""
        agent = self.create_branching_agent()

        # FIXED: Only provide success field
        inputs = {"success": False}

        result = agent.process(inputs)

        # Should describe the failure decision
        self.assertIn("BRANCH:", result)
        self.assertIn("test_branching", result)
        self.assertIn("FAIL", result)
        self.assertIn("'success' = False", result)

    def test_process_with_custom_field_configuration(self):
        """Test process method with custom field configuration."""
        agent = self.create_branching_agent(
            input_fields=["task_result"],  # Automatically becomes success_field
            success_values=["COMPLETED"],
        )

        inputs = {"task_result": "COMPLETED"}

        result = agent.process(inputs)

        # Should use custom field and values
        self.assertIn("SUCCEED", result)
        self.assertIn("'task_result' = COMPLETED", result)

    def test_process_with_no_matching_field(self):
        """Test process method when no matching field found."""
        agent = self.create_branching_agent()

        inputs = {"other_data": "value"}

        result = agent.process(inputs)

        # Should use default behavior and indicate no field found
        self.assertIn("SUCCEED", result)  # Default is True
        self.assertIn("no 'success' field found", result)
        self.assertIn("default behavior", result)

    def test_process_with_unrecognized_value(self):
        """Test process method with unrecognized value in success field."""
        agent = self.create_branching_agent()

        inputs = {"success": "UNKNOWN_VALUE"}

        result = agent.process(inputs)

        # Should use default result for unrecognized value
        self.assertIn("SUCCEED", result)  # Default is True
        self.assertIn("'success' = UNKNOWN_VALUE", result)

    # =============================================================================
    # 5. Detailed Success Determination Tests
    # =============================================================================

    def test_determine_success_detailed_return_values(self):
        """Test _determine_success_detailed returns correct information."""
        agent = self.create_branching_agent()

        # Test with found field
        success, field_used, value_found = agent._determine_success_detailed(
            {"success": True}
        )
        self.assertTrue(success)
        self.assertEqual(field_used, "success")
        self.assertTrue(value_found)

        # Test with fallback field
        success, field_used, value_found = agent._determine_success_detailed(
            {"succeed": "no"}
        )
        self.assertFalse(success)
        self.assertEqual(field_used, "succeed")
        self.assertEqual(value_found, "no")

        # Test with no relevant field
        success, field_used, value_found = agent._determine_success_detailed(
            {"other": "data"}
        )
        self.assertTrue(success)  # Default
        self.assertIsNone(field_used)
        self.assertIsNone(value_found)

    def test_evaluate_value_method(self):
        """Test _evaluate_value method with various inputs."""
        agent = self.create_branching_agent(
            success_values=["GOOD", "OK"], failure_values=["BAD", "ERROR"]
        )

        # Test success values
        self.assertTrue(agent._evaluate_value("GOOD"))
        self.assertTrue(agent._evaluate_value("ok"))  # Case insensitive

        # Test failure values
        self.assertFalse(agent._evaluate_value("BAD"))
        self.assertFalse(agent._evaluate_value("error"))  # Case insensitive

        # Test boolean values (backward compatibility)
        self.assertTrue(agent._evaluate_value(True))
        self.assertFalse(agent._evaluate_value(False))

        # Test numeric values (backward compatibility)
        self.assertTrue(agent._evaluate_value(1))
        self.assertFalse(agent._evaluate_value(0))

        # Test unrecognized value
        self.assertTrue(agent._evaluate_value("UNKNOWN"))  # Uses default (True)

    # =============================================================================
    # 6. Post-Processing Hook Tests
    # =============================================================================

    def test_post_process_sets_success_flag_correctly(self):
        """Test _post_process hook sets last_action_success correctly."""
        agent = self.create_branching_agent()

        # Test success case
        inputs = {"success": True}
        initial_state = {"existing": "data"}
        output = "test output"

        final_state, final_output = agent._post_process(initial_state, inputs, output)

        # Verify output is a dict with state_updates
        self.assertIsInstance(final_output, dict)
        self.assertIn("state_updates", final_output)

        # Verify state updates contain both result and last_action_success
        state_updates = final_output["state_updates"]
        self.assertEqual(state_updates["last_action_success"], True)
        self.assertIn("Will trigger SUCCESS branch", state_updates["result"])

        # Test failure case
        inputs = {"success": False}

        final_state, final_output = agent._post_process(initial_state, inputs, output)

        # Verify output is a dict with state_updates
        self.assertIsInstance(final_output, dict)
        self.assertIn("state_updates", final_output)

        # Verify state updates contain both result and last_action_success
        state_updates = final_output["state_updates"]
        self.assertEqual(state_updates["last_action_success"], False)
        self.assertIn("Will trigger FAILURE branch", state_updates["result"])

    # =============================================================================
    # 7. Integration Tests
    # =============================================================================

    def test_run_method_integration_with_success_path(self):
        """Test the inherited run method works with success path."""
        agent = self.create_branching_agent()

        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # Configure execution tracker methods
        self.mock_tracker.record_node_start = Mock(return_value=None)
        self.mock_tracker.record_node_result = Mock(return_value=None)

        # IMPORTANT: Set execution tracker before calling run() - required by BaseAgent
        agent.set_execution_tracker(self.mock_tracker)

        # Test state with success condition
        test_state = {"success": True, "other_field": "preserved"}

        # Execute run method
        result_state = agent.run(test_state)

        # Verify state was updated correctly
        self.assertIn("result", result_state)
        result = result_state["result"]
        self.assertIn("SUCCEED", result)

        # Verify last_action_success was set to True
        self.assertTrue(result_state.get("last_action_success"))

        # Original fields are NOT in result - BranchingAgent returns TWO fields
        # (result and last_action_success)
        self.assertNotIn("other_field", result_state)
        self.assertEqual(len(result_state), 2)  # result + last_action_success

    def test_run_method_integration_with_custom_configuration(self):
        """Test run method with custom configuration."""
        agent = self.create_branching_agent(
            input_fields=["status"],  # Automatically becomes success_field
            success_values=["PASSED"],
        )

        # Configure state adapter and tracker
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_tracker.record_node_start = Mock(return_value=None)
        self.mock_tracker.record_node_result = Mock(return_value=None)

        # IMPORTANT: Set execution tracker before calling run() - required by BaseAgent
        agent.set_execution_tracker(self.mock_tracker)

        test_state = {"status": "PASSED"}

        result_state = agent.run(test_state)

        # Should use custom configuration
        result = result_state["result"]
        self.assertIn("SUCCEED", result)
        self.assertIn("'status' = PASSED", result)

    # =============================================================================
    # 8. Configuration Information Tests
    # =============================================================================

    def test_get_configuration_info(self):
        """Test configuration information retrieval."""
        agent = self.create_branching_agent(
            success_field="custom_field",
            success_values=["GOOD"],
            failure_values=["BAD"],
            default_result=False,
        )

        config_info = agent.get_configuration_info()

        # Verify configuration details
        self.assertEqual(config_info["success_field"], "custom_field")
        self.assertEqual(config_info["success_values"], ["good"])  # Normalized
        self.assertEqual(config_info["failure_values"], ["bad"])  # Normalized
        self.assertFalse(config_info["default_result"])
        self.assertIsInstance(config_info["fallback_fields"], list)

    # =============================================================================
    # 9. Value Normalization Tests
    # =============================================================================

    def test_normalize_values_method(self):
        """Test _normalize_values converts strings to lowercase."""
        agent = self.create_branching_agent()

        input_values = ["TRUE", "False", 123, "Yes", "NO"]
        normalized = agent._normalize_values(input_values)

        expected = ["true", "false", 123, "yes", "no"]
        self.assertEqual(normalized, expected)

    # =============================================================================
    # 10. Logging Integration Tests
    # =============================================================================

    def test_logging_integration_with_configuration(self):
        """Test that agent properly logs configuration and decisions."""
        agent = self.create_branching_agent()

        inputs = {"success": True}
        agent.process(inputs)

        # Verify configuration and decision logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        info_calls = [call for call in logger_calls if call[0] == "info"]

        # Should log configuration
        config_logged = any(
            "BranchingAgent configured" in call[1] for call in debug_calls
        )
        self.assertTrue(
            config_logged, f"Expected configuration logged, got: {debug_calls}"
        )

        # Should log decision details
        decision_logged = any(
            "Decision based on field" in call[1] for call in info_calls
        )
        self.assertTrue(decision_logged, f"Expected decision logged, got: {info_calls}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
