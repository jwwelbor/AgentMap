"""
Unit tests for BaseAgent.run() method multi-output handling.

Tests for the new multi-output detection and validation in the run method:
- Single output returns dict with one key (backward compatibility)
- Multi-output calls _validate_multi_output
- Multi-output returns filtered dict with declared fields only
- Logging behavior is preserved
"""

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService
from tests.utils.mock_service_factory import MockServiceFactory


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    def process(self, inputs: Dict[str, Any]) -> Any:
        """Simple process method for testing."""
        return inputs.get("output", {})


class TestRunMethodMultiOutput(unittest.TestCase):
    """Test BaseAgent.run() method multi-output handling."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()

        # Create mock services
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.mock_execution_tracking = (
            self.mock_factory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter = self.mock_factory.create_mock_state_adapter_service()

        # Create a logger for the test agent
        self.mock_logger = self.mock_logging.get_class_logger("TestAgent")

        # Create mock tracker
        self.mock_tracker = self.mock_execution_tracking.create_tracker()

    def _create_agent(
        self,
        name: str,
        output_fields: list,
        context: Dict[str, Any] = None,
    ) -> ConcreteAgent:
        """Helper to create a test agent with specified output fields."""
        test_context = context or {}
        if "output_fields" not in test_context:
            # Set up output_field based on output_fields
            if len(output_fields) > 1:
                test_context["output_field"] = " | ".join(output_fields)
            elif len(output_fields) == 1:
                test_context["output_field"] = output_fields[0]

        agent = ConcreteAgent(
            name=name,
            prompt="Test prompt",
            context=test_context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )

        # Manually set output_fields to ensure correct configuration
        agent.output_fields = output_fields

        # Set the execution tracker
        agent.set_execution_tracker(self.mock_tracker)

        return agent

    # ======================================================================
    # TESTS: Single Output (Backward Compatibility)
    # ======================================================================

    def test_run_with_single_output_returns_dict_with_one_key(self):
        """Test single-output agent returns dict with one key (backward compatibility)."""
        # Arrange
        agent = self._create_agent("single_output_agent", ["result"])
        self.mock_state_adapter.get_inputs.return_value = {"input": "value"}

        test_state = {"input": "value"}

        # Act
        result = agent.run(test_state)

        # Assert
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)
        self.assertIn("result", result)
        self.assertNotIn("state_updates", result)

    def test_run_with_single_output_uses_first_output_field(self):
        """Test that single output is assigned to first (and only) output_field."""
        # Arrange
        agent = self._create_agent("single_agent", ["output"])

        def mock_process(inputs):
            return "test_output_value"

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert
        self.assertEqual(result, {"output": "test_output_value"})

    def test_run_single_output_does_not_call_validate_multi_output(self):
        """Test single-output agents do NOT call _validate_multi_output."""
        # Arrange
        agent = self._create_agent("single_agent", ["output"])
        self.mock_state_adapter.get_inputs.return_value = {"input": "value"}

        test_state = {"input": "value"}

        # Act
        with patch.object(agent, "_validate_multi_output") as mock_validate:
            result = agent.run(test_state)

            # Assert - _validate_multi_output should NOT be called for single output
            mock_validate.assert_not_called()

    def test_run_single_output_backward_compatibility_logging(self):
        """Test single-output maintains original logging format."""
        # Arrange
        agent = self._create_agent("single_agent", ["result"])
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "log_debug") as mock_log_debug:
            result = agent.run(test_state)

            # Assert - Should log with old format for backward compatibility
            # Should include the old message pattern: "Set output field 'X' = Y"
            log_calls = [call for call in mock_log_debug.call_args_list]
            debug_messages = [str(call[0][0]) for call in log_calls]
            found_old_format = any(
                "Set output field 'result'" in msg for msg in debug_messages
            )
            self.assertTrue(
                found_old_format,
                f"Expected old format log message, got: {debug_messages}",
            )

    # ======================================================================
    # TESTS: Multi-Output Detection and Routing
    # ======================================================================

    def test_run_detects_multi_output_when_two_fields(self):
        """Test run method detects multi-output scenario (len(output_fields) > 1)."""
        # Arrange
        agent = self._create_agent("multi_agent", ["field1", "field2"])

        def mock_process(inputs):
            return {"field1": "value1", "field2": "value2"}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "_validate_multi_output") as mock_validate:
            mock_validate.return_value = {"field1": "value1", "field2": "value2"}
            result = agent.run(test_state)

            # Assert - _validate_multi_output should be called
            mock_validate.assert_called_once()

    def test_run_detects_multi_output_when_three_fields(self):
        """Test run method detects multi-output with three or more fields."""
        # Arrange
        agent = self._create_agent("multi_agent", ["field1", "field2", "field3"])

        def mock_process(inputs):
            return {"field1": "v1", "field2": "v2", "field3": "v3"}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "_validate_multi_output") as mock_validate:
            mock_validate.return_value = {
                "field1": "v1",
                "field2": "v2",
                "field3": "v3",
            }
            result = agent.run(test_state)

            # Assert - _validate_multi_output should be called
            mock_validate.assert_called_once()

    def test_run_calls_validate_multi_output_with_output_value(self):
        """Test run passes the output value to _validate_multi_output."""
        # Arrange
        agent = self._create_agent("multi_agent", ["field1", "field2"])
        output_value = {"field1": "value1", "field2": "value2"}

        def mock_process(inputs):
            return output_value

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "_validate_multi_output") as mock_validate:
            mock_validate.return_value = output_value
            result = agent.run(test_state)

            # Assert - _validate_multi_output called with correct output
            mock_validate.assert_called_once_with(output_value)

    # ======================================================================
    # TESTS: Multi-Output Return Value
    # ======================================================================

    def test_run_multi_output_returns_filtered_dict(self):
        """Test multi-output returns filtered dict in ignore mode."""
        # Arrange
        agent = self._create_agent(
            "multi_agent", ["field1", "field2"], {"output_validation": "ignore"}
        )

        def mock_process(inputs):
            return {"field1": "value1", "field2": "value2", "extra": "ignore"}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert - Ignore mode filters extras
        self.assertIsInstance(result, dict)
        self.assertIn("field1", result)
        self.assertIn("field2", result)
        self.assertNotIn("extra", result)
        self.assertNotIn("state_updates", result)

    def test_run_multi_output_returns_only_declared_fields(self):
        """Test multi-output returns only declared fields."""
        # Arrange
        agent = self._create_agent("multi_agent", ["result1", "result2", "result3"])

        def mock_process(inputs):
            return {"result1": "v1", "result2": "v2", "result3": "v3"}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert
        self.assertEqual(len(result), 3)
        self.assertEqual(result["result1"], "v1")
        self.assertEqual(result["result2"], "v2")
        self.assertEqual(result["result3"], "v3")

    def test_run_multi_output_with_missing_fields(self):
        """Test multi-output handles missing fields via validation."""
        # Arrange
        agent = self._create_agent(
            "multi_agent", ["field1", "field2"], {"output_validation": "ignore"}
        )

        def mock_process(inputs):
            return {"field1": "value1"}  # field2 missing

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert
        self.assertIn("field1", result)
        self.assertIn("field2", result)  # Should be included with None value
        self.assertEqual(result["field1"], "value1")
        self.assertIsNone(result["field2"])

    # ======================================================================
    # TESTS: Multi-Output Logging
    # ======================================================================

    def test_run_multi_output_logs_debug_message(self):
        """Test multi-output run logs appropriate debug message."""
        # Arrange
        agent = self._create_agent("multi_agent", ["field1", "field2"])

        def mock_process(inputs):
            return {"field1": "value1", "field2": "value2"}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "log_debug") as mock_log_debug:
            result = agent.run(test_state)

            # Assert - Should log multi-output message
            log_calls = [call for call in mock_log_debug.call_args_list]
            debug_messages = [str(call[0][0]) for call in log_calls]
            found_multi_output_log = any(
                "Multi-output" in msg for msg in debug_messages
            )
            self.assertTrue(
                found_multi_output_log,
                f"Expected multi-output log message, got: {debug_messages}",
            )

    def test_run_multi_output_logs_field_names(self):
        """Test multi-output logs the names of fields being updated."""
        # Arrange
        agent = self._create_agent("multi_agent", ["result1", "result2"])

        def mock_process(inputs):
            return {"result1": "v1", "result2": "v2"}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "log_debug") as mock_log_debug:
            result = agent.run(test_state)

            # Assert
            log_calls = [call for call in mock_log_debug.call_args_list]
            debug_messages = [str(call[0][0]) for call in log_calls]
            found_field_names = any(
                "result1" in msg and "result2" in msg for msg in debug_messages
            )
            self.assertTrue(
                found_field_names,
                f"Expected field names in log, got: {debug_messages}",
            )

    # ======================================================================
    # TESTS: Multi-Output Timing and Trace Logging
    # ======================================================================

    def test_run_multi_output_includes_execution_timing(self):
        """Test multi-output run includes timing information in trace log."""
        # Arrange
        agent = self._create_agent("multi_agent", ["field1", "field2"])

        def mock_process(inputs):
            return {"field1": "value1", "field2": "value2"}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "log_trace") as mock_log_trace:
            result = agent.run(test_state)

            # Assert - Should log timing in completion message
            log_calls = [call for call in mock_log_trace.call_args_list]
            trace_messages = [str(call[0][0]) for call in log_calls]
            found_timing = any(
                "RUN COMPLETED" in msg and "s ***" in msg for msg in trace_messages
            )
            self.assertTrue(
                found_timing,
                f"Expected timing in trace log, got: {trace_messages}",
            )

    def test_run_multi_output_preserves_execution_id(self):
        """Test multi-output includes execution ID in logging."""
        # Arrange
        agent = self._create_agent("multi_agent", ["field1", "field2"])

        def mock_process(inputs):
            return {"field1": "value1", "field2": "value2"}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "log_trace") as mock_log_trace:
            result = agent.run(test_state)

            # Assert - Start and completion messages should have execution IDs
            log_calls = [call for call in mock_log_trace.call_args_list]
            trace_messages = [str(call[0][0]) for call in log_calls]

            # Should have START and COMPLETED messages with execution IDs
            has_start = any("RUN START" in msg for msg in trace_messages)
            has_completed = any("RUN COMPLETED" in msg for msg in trace_messages)

            self.assertTrue(has_start, "Expected RUN START message")
            self.assertTrue(has_completed, "Expected RUN COMPLETED message")

    # ======================================================================
    # TESTS: Backward Compatibility with output_field
    # ======================================================================

    def test_run_single_output_uses_output_field_value(self):
        """Test single output uses output_field property name."""
        # Arrange
        agent = self._create_agent("single_agent", ["custom_output"])
        # output_field should be "custom_output"
        self.assertEqual(agent.output_field, "custom_output")

        def mock_process(inputs):
            return "result_value"

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert - Should use output_field name as key
        self.assertIn("custom_output", result)
        self.assertEqual(result["custom_output"], "result_value")

    def test_run_returns_dict_for_single_output_not_raw_value(self):
        """Test run always returns dict, never raw value for single output."""
        # Arrange
        agent = self._create_agent("single_agent", ["output"])

        def mock_process(inputs):
            return "scalar_value"

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {"output": "scalar_value"})

    # ======================================================================
    # TESTS: No Output Field Handling
    # ======================================================================

    def test_run_with_no_output_field_returns_empty_dict(self):
        """Test run returns empty dict when no output_field is specified."""
        # Arrange
        agent = self._create_agent("no_output_agent", [])
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert
        self.assertEqual(result, {})
        self.assertEqual(len(result), 0)

    def test_run_with_no_output_field_does_not_call_validate(self):
        """Test no-output agents do not call _validate_multi_output."""
        # Arrange
        agent = self._create_agent("no_output_agent", [])
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "_validate_multi_output") as mock_validate:
            result = agent.run(test_state)

            # Assert
            mock_validate.assert_not_called()

    # ======================================================================
    # TESTS: Integration with state_updates pattern
    # ======================================================================

    def test_run_with_state_updates_returns_all_fields(self):
        """Test state_updates special case still works (not a dict from process)."""
        # Arrange
        agent = self._create_agent("single_agent", ["output"])

        def mock_process(inputs):
            return {"state_updates": {"output": "value", "extra": "field"}}

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert - state_updates returns all fields as-is
        self.assertEqual(result, {"output": "value", "extra": "field"})

    # ======================================================================
    # TESTS: None Output Handling
    # ======================================================================

    def test_run_single_output_with_none_output_returns_empty_dict(self):
        """Test single output with None value returns empty dict (no updates)."""
        # Arrange
        agent = self._create_agent("single_agent", ["output"])

        def mock_process(inputs):
            return None

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert - When output is None, return empty dict (no updates)
        self.assertEqual(result, {})

    def test_run_multi_output_with_none_output_does_not_call_validate(self):
        """Test multi-output with None output does NOT call _validate_multi_output."""
        # Arrange
        agent = self._create_agent("multi_agent", ["field1", "field2"])

        def mock_process(inputs):
            return None

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        with patch.object(agent, "_validate_multi_output") as mock_validate:
            result = agent.run(test_state)

            # Assert - _validate_multi_output should NOT be called when output is None
            mock_validate.assert_not_called()
            # Should return empty dict
            self.assertEqual(result, {})

    # ======================================================================
    # TESTS: Preserves existing behavior for output_field condition
    # ======================================================================

    def test_run_only_processes_output_when_output_field_and_output_not_none(self):
        """Test output is only processed when both output_field exists and output is not None."""
        # Arrange - Agent with output field
        agent = self._create_agent("single_agent", ["output"])

        def mock_process(inputs):
            return None

        agent.process = mock_process
        self.mock_state_adapter.get_inputs.return_value = {"input": "test"}

        test_state = {"input": "test"}

        # Act
        result = agent.run(test_state)

        # Assert - When output is None, returns empty dict (no state updates)
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
