"""
Unit tests for BaseAgent.run() method with multi-output handling.

Tests cover:
- Single output (backward compatibility)
- Multi-output dict returns
- Scalar returns for multi-output
- Missing fields
- Extra fields
- Validation modes (ignore/warn/error)
- state_updates pattern for parallel execution
"""

import unittest
from typing import Any, Dict
from unittest.mock import Mock, patch

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService
from tests.utils.mock_service_factory import MockServiceFactory


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    def process(self, inputs: Dict[str, Any]) -> Any:
        """Simple process method that returns test values."""
        return inputs.get("output", {})


class TestBaseAgentMultiOutput(unittest.TestCase):
    """Test BaseAgent.run() method with multi-output scenarios."""

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

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking.create_tracker()

    def _create_agent(
        self,
        name: str,
        output_field: str = None,
        output_fields: list = None,
        context: Dict[str, Any] = None,
    ) -> ConcreteAgent:
        """Helper to create a test agent with specified output configuration."""
        test_context = context or {}
        if output_field:
            test_context["output_field"] = output_field
        if output_fields is not None:
            test_context["output_fields"] = output_fields

        agent = ConcreteAgent(
            name=name,
            prompt="Test prompt",
            context=test_context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )

        # Manually set output_fields if provided (since BaseAgent parses from output_field)
        if output_fields is not None:
            agent.output_fields = output_fields

        # Set execution tracker (required by run method)
        agent.set_execution_tracker(self.mock_tracker)

        return agent

    def _configure_state_adapter(self, return_inputs: Dict[str, Any] = None):
        """Configure mock state adapter to return test inputs."""
        if return_inputs is None:
            return_inputs = {}
        self.mock_state_adapter.get_inputs.return_value = return_inputs

    # =========================================================================
    # SINGLE OUTPUT TESTS - Backward Compatibility
    # =========================================================================

    def test_run_single_output_backward_compatibility(self):
        """Test run() with single output field returns dict with one key."""
        # Arrange
        agent = self._create_agent("test_agent", output_field="result")
        self._configure_state_adapter({"input": "test"})

        # Agent returns simple value
        class SingleOutputAgent(ConcreteAgent):
            def process(self, inputs):
                return "test_result"

        agent = SingleOutputAgent(
            name="single_agent",
            prompt="Test",
            context={"output_field": "result"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({"input": "test"})

        # Act
        result = agent.run({"input": "test"})

        # Assert
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)
        self.assertIn("result", result)
        self.assertEqual(result["result"], "test_result")

    def test_run_single_output_scalar_wrapped_correctly(self):
        """Test scalar value is wrapped in single output field."""

        # Arrange
        class ScalarAgent(ConcreteAgent):
            def process(self, inputs):
                return 42

        agent = ScalarAgent(
            name="scalar_agent",
            prompt="Test",
            context={"output_field": "value"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert
        self.assertEqual(result, {"value": 42})

    def test_run_single_output_none_value_wrapped(self):
        """Test None values return empty dict (not wrapped) in single output."""

        # Arrange
        class NoneAgent(ConcreteAgent):
            def process(self, inputs):
                return None

        agent = NoneAgent(
            name="none_agent",
            prompt="Test",
            context={"output_field": "result"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert - None output returns empty dict (no state update)
        self.assertEqual(result, {})

    # =========================================================================
    # MULTI-OUTPUT DICT RETURNS
    # =========================================================================

    def test_run_multi_output_valid_dict_returns_all_fields(self):
        """Test multi-output agent returning valid dict returns all fields."""

        # Arrange
        class MultiOutputAgent(ConcreteAgent):
            def process(self, inputs):
                return {
                    "result1": "value1",
                    "result2": "value2",
                    "result3": "value3",
                }

        context = {"output_field": "result1|result2|result3"}
        agent = MultiOutputAgent(
            name="multi_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({"input": "test"})

        # Act
        result = agent.run({"input": "test"})

        # Assert
        self.assertEqual(len(result), 3)
        self.assertEqual(result["result1"], "value1")
        self.assertEqual(result["result2"], "value2")
        self.assertEqual(result["result3"], "value3")

    def test_run_multi_output_state_updates_pattern(self):
        """Test run() returns state_updates dict for multi-field updates."""

        # Arrange
        class MultiUpdateAgent(ConcreteAgent):
            def process(self, inputs):
                # This would be handled by _post_process typically
                return {
                    "state_updates": {
                        "field1": "value1",
                        "field2": "value2",
                        "field3": "value3",
                    }
                }

        agent = MultiUpdateAgent(
            name="multi_update_agent",
            prompt="Test",
            context={"output_field": "field1|field2|field3"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert - Should return state_updates dict as-is
        self.assertIn("field1", result)
        self.assertIn("field2", result)
        self.assertIn("field3", result)
        self.assertEqual(result["field1"], "value1")
        self.assertEqual(result["field2"], "value2")
        self.assertEqual(result["field3"], "value3")

    def test_run_multi_output_dict_with_none_values(self):
        """Test multi-output dict with None values for some fields."""

        # Arrange
        class PartialAgent(ConcreteAgent):
            def process(self, inputs):
                return {"result1": "value1", "result2": None, "result3": "value3"}

        context = {"output_field": "result1|result2|result3"}
        agent = PartialAgent(
            name="partial_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert
        self.assertEqual(result["result1"], "value1")
        self.assertIsNone(result["result2"])
        self.assertEqual(result["result3"], "value3")

    # =========================================================================
    # SCALAR RETURNS FOR MULTI-OUTPUT
    # =========================================================================

    def test_run_multi_output_scalar_wrapped_in_first_field_warn_mode(self):
        """Test scalar return wrapped in first field with warn mode."""

        # Arrange
        class ScalarMultiAgent(ConcreteAgent):
            def process(self, inputs):
                return "scalar_result"

        context = {
            "output_field": "primary|secondary|tertiary",
            "output_validation": "warn",
        }
        agent = ScalarMultiAgent(
            name="scalar_multi_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        with patch.object(agent, "log_warning") as mock_warn:
            result = agent.run({})

            # Assert - Should log warning about type mismatch via _validate_multi_output
            # Check that warning was called during validation
            warning_calls = [
                c
                for c in mock_warn.call_args_list
                if "declares multiple outputs" in str(c)
            ]
            self.assertTrue(len(warning_calls) > 0 or mock_warn.called)

        # Scalar should be wrapped in first field only (not with None for missing fields)
        self.assertEqual(result["primary"], "scalar_result")

    def test_run_multi_output_list_wrapped_in_first_field(self):
        """Test list return wrapped in first field of multi-output (graceful degradation)."""

        # Arrange
        class ListAgent(ConcreteAgent):
            def process(self, inputs):
                return [1, 2, 3]

        context = {"output_field": "items|count"}
        agent = ListAgent(
            name="list_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert - Non-dict wrapped only in first field (graceful degradation)
        self.assertEqual(result["items"], [1, 2, 3])
        # Only first field returned for non-dict values
        self.assertEqual(len(result), 1)

    def test_run_multi_output_object_wrapped_in_first_field(self):
        """Test custom object wrapped in first field (graceful degradation)."""

        # Arrange
        class CustomObject:
            def __init__(self):
                self.data = "custom"

        class ObjectAgent(ConcreteAgent):
            def process(self, inputs):
                return CustomObject()

        context = {"output_field": "obj|metadata"}
        agent = ObjectAgent(
            name="obj_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert - Non-dict wrapped only in first field (graceful degradation)
        self.assertIsInstance(result["obj"], CustomObject)
        self.assertEqual(result["obj"].data, "custom")
        # Only first field returned for non-dict values
        self.assertEqual(len(result), 1)

    # =========================================================================
    # MISSING FIELDS HANDLING
    # =========================================================================

    def test_run_multi_output_missing_fields_ignore_mode(self):
        """Test missing fields with ignore mode - includes None values."""

        # Arrange
        class IncompleteAgent(ConcreteAgent):
            def process(self, inputs):
                return {"field1": "value1"}  # Missing field2, field3

        context = {
            "output_field": "field1|field2|field3",
            "output_validation": "ignore",
        }
        agent = IncompleteAgent(
            name="incomplete_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        with patch.object(agent, "log_warning"):
            result = agent.run({})

        # Assert
        self.assertEqual(result["field1"], "value1")
        self.assertIsNone(result["field2"])
        self.assertIsNone(result["field3"])

    def test_run_multi_output_missing_fields_warn_mode(self):
        """Test missing fields with warn mode - logs warning."""

        # Arrange
        class IncompleteAgent(ConcreteAgent):
            def process(self, inputs):
                return {"field1": "value1"}  # Missing field2

        context = {
            "output_field": "field1|field2",
            "output_validation": "warn",
        }
        agent = IncompleteAgent(
            name="incomplete_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        with patch.object(agent, "log_warning") as mock_warn:
            result = agent.run({})

            # Assert - Should log warning
            mock_warn.assert_called()
            warn_msg = mock_warn.call_args[0][0]
            self.assertIn("missing declared output fields", warn_msg)
            self.assertIn("field2", warn_msg)

        # Result still includes missing as None
        self.assertEqual(result["field1"], "value1")
        self.assertIsNone(result["field2"])

    def test_run_multi_output_missing_fields_error_mode(self):
        """Test missing fields with error mode - returns error state (caught by run method)."""

        # Arrange
        class IncompleteAgent(ConcreteAgent):
            def process(self, inputs):
                return {"field1": "value1"}  # Missing field2

        context = {
            "output_field": "field1|field2",
            "output_validation": "error",
        }
        agent = IncompleteAgent(
            name="incomplete_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})
        self.mock_execution_tracking.update_graph_success.return_value = False

        # Act - _validate_multi_output raises ValueError which is caught by run()
        result = agent.run({})

        # Assert - run() returns error state with information about the error
        self.assertIn("last_action_success", result)
        self.assertFalse(result["last_action_success"])
        self.assertIn("errors", result)
        error_info = result["errors"][0]
        self.assertIn("missing declared output fields", error_info)
        self.assertIn("field2", error_info)

    def test_run_multi_output_all_fields_missing_error(self):
        """Test error when all declared fields are missing (caught by run method)."""

        # Arrange
        class EmptyAgent(ConcreteAgent):
            def process(self, inputs):
                return {"unrelated": "value"}  # All declared fields missing

        context = {
            "output_field": "field1|field2",
            "output_validation": "error",
        }
        agent = EmptyAgent(
            name="empty_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})
        self.mock_execution_tracking.update_graph_success.return_value = False

        # Act - _validate_multi_output raises ValueError which is caught by run()
        result = agent.run({})

        # Assert - run() returns error state with information about the error
        self.assertIn("last_action_success", result)
        self.assertFalse(result["last_action_success"])
        self.assertIn("errors", result)
        error_info = result["errors"][0]
        self.assertIn("field1", error_info)
        self.assertIn("field2", error_info)

    # =========================================================================
    # EXTRA FIELDS HANDLING
    # =========================================================================

    def test_run_multi_output_extra_fields_filtered_out(self):
        """Test extra fields not in output_fields are removed in ignore mode."""

        # Arrange
        class ExtraAgent(ConcreteAgent):
            def process(self, inputs):
                return {
                    "field1": "value1",
                    "field2": "value2",
                    "extra_field": "extra",
                    "another_extra": "extra2",
                }

        context = {"output_field": "field1|field2", "output_validation": "ignore"}
        agent = ExtraAgent(
            name="extra_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert - Only declared fields in result (ignore mode)
        self.assertEqual(len(result), 2)
        self.assertIn("field1", result)
        self.assertIn("field2", result)
        self.assertNotIn("extra_field", result)
        self.assertNotIn("another_extra", result)

    def test_run_multi_output_extra_fields_debug_logged(self):
        """Test extra fields are logged at debug level."""

        # Arrange
        class ExtraAgent(ConcreteAgent):
            def process(self, inputs):
                return {
                    "field1": "value1",
                    "extra1": "ex1",
                    "extra2": "ex2",
                }

        context = {"output_field": "field1"}
        agent = ExtraAgent(
            name="extra_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        with patch.object(agent, "log_debug") as mock_debug:
            result = agent.run({})

            # Assert
            debug_calls = [call for call in mock_debug.call_args_list]
            extra_logged = any("extra" in str(call).lower() for call in debug_calls)
            # At least one debug call mentions filtering extras
            self.assertTrue(extra_logged or "extra" in str(debug_calls).lower())

    # =========================================================================
    # VALIDATION MODE TESTS
    # =========================================================================

    def test_run_multi_output_default_validation_is_warn(self):
        """Test default validation mode is 'warn'."""

        # Arrange
        class IncompleteAgent(ConcreteAgent):
            def process(self, inputs):
                return {"field1": "value1"}  # Missing field2

        context = {"output_field": "field1|field2"}  # No explicit validation mode
        agent = IncompleteAgent(
            name="default_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act & Assert
        with patch.object(agent, "log_warning") as mock_warn:
            result = agent.run({})

            # Should warn (default mode)
            mock_warn.assert_called()

    def test_run_multi_output_validation_mode_ignore(self):
        """Test 'ignore' validation mode doesn't log warnings."""

        # Arrange
        class IncompleteAgent(ConcreteAgent):
            def process(self, inputs):
                return {}  # All fields missing

        context = {
            "output_field": "field1|field2",
            "output_validation": "ignore",
        }
        agent = IncompleteAgent(
            name="ignore_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        with patch.object(agent, "log_warning") as mock_warn:
            result = agent.run({})

            # Should not warn
            mock_warn.assert_not_called()

        # But result still includes None values
        self.assertIsNone(result["field1"])
        self.assertIsNone(result["field2"])

    # =========================================================================
    # STATE UPDATES TRACKING
    # =========================================================================

    def test_run_calls_tracking_service_for_multi_output(self):
        """Test run() calls execution tracking service for multi-output agents."""

        # Arrange
        class MultiAgent(ConcreteAgent):
            def process(self, inputs):
                return {"result1": "value1", "result2": "value2"}

        context = {"output_field": "result1|result2"}
        agent = MultiAgent(
            name="tracking_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({"input": "test"})

        # Act
        result = agent.run({"input": "test"})

        # Assert - Tracking service should be called
        self.mock_execution_tracking.record_node_start.assert_called()
        self.mock_execution_tracking.record_node_result.assert_called()

        # Verify node result was logged
        result_call_args = self.mock_execution_tracking.record_node_result.call_args
        result_args, result_kwargs = result_call_args
        self.assertTrue(result_args[2])  # success=True

    def test_run_tracking_includes_all_output_fields(self):
        """Test tracking service receives complete multi-output result."""

        # Arrange
        class MultiAgent(ConcreteAgent):
            def process(self, inputs):
                return {"result1": "value1", "result2": "value2", "result3": "value3"}

        context = {"output_field": "result1|result2|result3"}
        agent = MultiAgent(
            name="multi_tracking",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert
        self.assertEqual(len(result), 3)
        self.assertIn("result1", result)
        self.assertIn("result2", result)
        self.assertIn("result3", result)

    # =========================================================================
    # COMPLEX SCENARIOS
    # =========================================================================

    def test_run_multi_output_with_complex_data_types(self):
        """Test multi-output with complex data types (lists, dicts, objects)."""

        # Arrange
        class ComplexAgent(ConcreteAgent):
            def process(self, inputs):
                return {
                    "items": [1, 2, 3, 4, 5],
                    "metadata": {"key": "value", "nested": {"deep": "data"}},
                    "count": 5,
                }

        context = {"output_field": "items|metadata|count"}
        agent = ComplexAgent(
            name="complex_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert - Complex types preserved
        self.assertEqual(result["items"], [1, 2, 3, 4, 5])
        self.assertEqual(result["metadata"]["nested"]["deep"], "data")
        self.assertEqual(result["count"], 5)

    def test_run_multi_output_empty_dict_return(self):
        """Test multi-output agent returning empty dict."""

        # Arrange
        class EmptyDictAgent(ConcreteAgent):
            def process(self, inputs):
                return {}

        context = {
            "output_field": "field1|field2",
            "output_validation": "warn",
        }
        agent = EmptyDictAgent(
            name="empty_dict_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        with patch.object(agent, "log_warning"):
            result = agent.run({})

        # Assert - All fields present with None values
        self.assertEqual(result["field1"], None)
        self.assertEqual(result["field2"], None)

    def test_run_case_sensitive_field_matching(self):
        """Test that field matching is case-sensitive in ignore mode."""

        # Arrange
        class CaseSensitiveAgent(ConcreteAgent):
            def process(self, inputs):
                return {
                    "Field1": "correct",
                    "field1": "wrong",
                    "field2": "value2",
                }

        context = {"output_field": "Field1|field2", "output_validation": "ignore"}
        agent = CaseSensitiveAgent(
            name="case_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert - Only exact case matches (ignore mode filters extras)
        self.assertEqual(result["Field1"], "correct")
        self.assertEqual(result["field2"], "value2")
        self.assertNotIn("field1", result)

    def test_run_with_whitespace_in_output_field_names(self):
        """Test output field names with whitespace are handled correctly."""

        # Arrange
        class WhitespaceAgent(ConcreteAgent):
            def process(self, inputs):
                return {"field1": "value1", "field2": "value2"}

        # Pipe-delimited with whitespace
        context = {"output_field": "field1 | field2"}
        agent = WhitespaceAgent(
            name="whitespace_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert - Whitespace should be trimmed
        self.assertEqual(result["field1"], "value1")
        self.assertEqual(result["field2"], "value2")

    # =========================================================================
    # ERROR HANDLING IN MULTI-OUTPUT
    # =========================================================================

    def test_run_multi_output_process_error_handling(self):
        """Test error handling preserves tracking info."""

        # Arrange
        class ErrorAgent(ConcreteAgent):
            def process(self, inputs):
                raise ValueError("Processing failed")

        context = {"output_field": "result1|result2"}
        agent = ErrorAgent(
            name="error_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Configure tracking service for error handling
        self.mock_execution_tracking.update_graph_success.return_value = False

        # Act
        result = agent.run({})

        # Assert - Error state should be returned
        self.assertIn("graph_success", result)
        self.assertIn("last_action_success", result)
        self.assertIn("errors", result)
        self.assertFalse(result["last_action_success"])

    # =========================================================================
    # INTEGRATION SCENARIOS
    # =========================================================================

    def test_run_multi_output_with_post_process_hook(self):
        """Test multi-output agent using _post_process hook."""

        # Arrange
        class PostProcessAgent(BaseAgent):
            def process(self, inputs):
                return "raw_result"

            def _post_process(self, state, inputs, output):
                # Transform to multi-output format
                return state, {
                    "result": output,
                    "metadata": {"processed": True},
                }

        context = {"output_field": "result|metadata"}
        agent = PostProcessAgent(
            name="post_process_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert
        self.assertEqual(result["result"], "raw_result")
        self.assertEqual(result["metadata"]["processed"], True)

    def test_run_multi_output_large_number_of_fields(self):
        """Test multi-output with many fields (stress test)."""
        # Arrange
        field_names = [f"field{i}" for i in range(10)]
        field_values = {name: f"value{i}" for i, name in enumerate(field_names)}

        class ManyFieldsAgent(ConcreteAgent):
            def process(self, inputs):
                return field_values

        context = {"output_field": "|".join(field_names)}
        agent = ManyFieldsAgent(
            name="many_fields_agent",
            prompt="Test",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )
        agent.set_execution_tracker(self.mock_tracker)
        self._configure_state_adapter({})

        # Act
        result = agent.run({})

        # Assert
        self.assertEqual(len(result), 10)
        for i, field_name in enumerate(field_names):
            self.assertEqual(result[field_name], f"value{i}")


if __name__ == "__main__":
    unittest.main()
