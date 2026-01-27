"""
Unit tests for BaseAgent._validate_multi_output method.

Tests validation of dict returns for multi-output agents, including:
- Handling missing/extra fields
- Supporting configurable validation modes (ignore/warn/error)
- Graceful degradation for non-dict returns
"""

import logging
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


class TestValidateMultiOutput(unittest.TestCase):
    """Test BaseAgent._validate_multi_output method."""

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

    def _create_agent(
        self, output_fields: list, context: Dict[str, Any] = None
    ) -> ConcreteAgent:
        """Helper to create a test agent with specified output fields."""
        test_context = context or {}
        if "output_fields" not in test_context:
            test_context["output_fields"] = output_fields

        agent = ConcreteAgent(
            name="test_agent",
            prompt="Test prompt",
            context=test_context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )

        # Manually set output_fields since it's not extracted from context in BaseAgent
        agent.output_fields = output_fields

        return agent

    # ======================================================================
    # TESTS: Happy Path - Valid Dict Returns
    # ======================================================================

    def test_validate_multi_output_returns_all_fields_when_valid(self):
        """Test validation succeeds and returns all declared fields when output is valid."""
        # Arrange
        agent = self._create_agent(["field1", "field2", "field3"])
        output = {"field1": "value1", "field2": "value2", "field3": "value3"}

        # Act
        result = agent._validate_multi_output(output)

        # Assert
        self.assertEqual(result, output)
        self.assertEqual(len(result), 3)
        self.assertIn("field1", result)
        self.assertIn("field2", result)
        self.assertIn("field3", result)

    def test_validate_multi_output_with_single_field(self):
        """Test validation with single output field."""
        # Arrange
        agent = self._create_agent(["output"])
        output = {"output": "result value"}

        # Act
        result = agent._validate_multi_output(output)

        # Assert
        self.assertEqual(result, {"output": "result value"})

    def test_validate_multi_output_with_none_values(self):
        """Test validation accepts None values for declared fields."""
        # Arrange
        agent = self._create_agent(["field1", "field2"])
        output = {"field1": None, "field2": "value2"}

        # Act
        result = agent._validate_multi_output(output)

        # Assert
        self.assertEqual(result, {"field1": None, "field2": "value2"})

    # ======================================================================
    # TESTS: Extra Fields - Filtering Behavior
    # ======================================================================

    def test_validate_multi_output_filters_extra_fields(self):
        """Test that extra fields are removed in 'ignore' mode."""
        # Arrange
        agent = self._create_agent(
            ["field1", "field2"], {"output_validation": "ignore"}
        )
        output = {
            "field1": "value1",
            "field2": "value2",
            "extra_field": "extra_value",
            "another_extra": "another_value",
        }

        # Act
        result = agent._validate_multi_output(output)

        # Assert - Only declared fields should be present
        self.assertEqual(len(result), 2)
        self.assertIn("field1", result)
        self.assertIn("field2", result)
        self.assertNotIn("extra_field", result)
        self.assertNotIn("another_extra", result)

    def test_validate_multi_output_filters_extra_with_debug_logging(self):
        """Test that extra fields are logged at debug level in 'ignore' mode."""
        # Arrange
        agent = self._create_agent(["field1"], {"output_validation": "ignore"})
        output = {"field1": "value1", "extra1": "ex1", "extra2": "ex2"}

        # Act
        with patch.object(agent, "log_debug") as mock_log_debug:
            result = agent._validate_multi_output(output)

            # Assert
            mock_log_debug.assert_called_once()
            call_args = mock_log_debug.call_args[0][0]
            self.assertIn("extra1", call_args)
            self.assertIn("extra2", call_args)

    def test_validate_multi_output_extra_fields_mode_warn(self):
        """Test extra fields with 'warn' mode - logs warning, keeps extras in state."""
        # Arrange
        agent = self._create_agent(["field1", "field2"], {"output_validation": "warn"})
        output = {
            "field1": "value1",
            "field2": "value2",
            "extra1": "ex1",
            "extra2": "ex2",
        }

        # Act
        with patch.object(agent, "log_warning") as mock_log_warning:
            result = agent._validate_multi_output(output)

            # Assert
            mock_log_warning.assert_called_once()
            warning_msg = mock_log_warning.call_args[0][0]
            self.assertIn("returned extra fields", warning_msg)
            self.assertIn("extra1", warning_msg)
            self.assertIn("extra2", warning_msg)
            self.assertIn("test_agent", warning_msg)
            self.assertIn("will be included in state", warning_msg)
            # Result should contain ALL fields (declared + extras)
            self.assertEqual(result, output)
            self.assertIn("extra1", result)
            self.assertIn("extra2", result)

    def test_validate_multi_output_extra_fields_default_warn_behavior(self):
        """Test that default mode (warn) keeps extra fields in state."""
        # Arrange - No validation mode specified, should default to warn
        agent = self._create_agent(["field1", "field2"])
        output = {
            "field1": "value1",
            "field2": "value2",
            "extra1": "ex1",
            "extra2": "ex2",
        }

        # Act
        with patch.object(agent, "log_warning") as mock_log_warning:
            result = agent._validate_multi_output(output)

            # Assert - Should keep all fields (warn mode default)
            self.assertEqual(result, output)
            self.assertIn("extra1", result)
            self.assertIn("extra2", result)
            mock_log_warning.assert_called_once()

    def test_validate_multi_output_missing_and_extra_fields_warn_mode(self):
        """Test warn mode with both missing and extra fields - warns about both, keeps extras, adds None for missing."""
        # Arrange
        agent = self._create_agent(
            ["field1", "field2", "field3"], {"output_validation": "warn"}
        )
        output = {
            "field1": "value1",
            # field2 is missing
            # field3 is missing
            "extra1": "ex1",
            "extra2": "ex2",
        }

        # Act
        with patch.object(agent, "log_warning") as mock_log_warning:
            result = agent._validate_multi_output(output)

            # Assert - Should have 2 warnings (one for missing, one for extras)
            self.assertEqual(mock_log_warning.call_count, 2)

            # Check warnings
            warning_calls = [call[0][0] for call in mock_log_warning.call_args_list]
            missing_warning = [
                w for w in warning_calls if "missing declared output fields" in w
            ][0]
            extra_warning = [w for w in warning_calls if "extra fields" in w][0]

            self.assertIn("field2", missing_warning)
            self.assertIn("field3", missing_warning)
            self.assertIn("extra1", extra_warning)
            self.assertIn("extra2", extra_warning)

            # Result should have: declared fields (with None for missing) + extras
            self.assertEqual(len(result), 5)  # 3 declared + 2 extras
            self.assertEqual(result["field1"], "value1")
            self.assertIsNone(result["field2"])
            self.assertIsNone(result["field3"])
            self.assertEqual(result["extra1"], "ex1")
            self.assertEqual(result["extra2"], "ex2")

    def test_validate_multi_output_extra_fields_mode_error(self):
        """Test extra fields with 'error' mode - raises ValueError."""
        # Arrange
        agent = self._create_agent(["field1", "field2"], {"output_validation": "error"})
        output = {
            "field1": "value1",
            "field2": "value2",
            "extra1": "ex1",
            "extra2": "ex2",
        }

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            agent._validate_multi_output(output)

        error_msg = str(context.exception)
        self.assertIn("returned extra fields", error_msg)
        self.assertIn("extra1", error_msg)
        self.assertIn("extra2", error_msg)
        self.assertIn("test_agent", error_msg)
        self.assertIn("Declared fields are", error_msg)

    # ======================================================================
    # TESTS: Missing Fields - Validation Mode Behavior
    # ======================================================================

    def test_validate_multi_output_missing_fields_mode_ignore(self):
        """Test missing fields with 'ignore' mode - logs nothing, includes None values."""
        # Arrange
        agent = self._create_agent(
            ["field1", "field2", "field3"], {"output_validation": "ignore"}
        )
        output = {"field1": "value1"}  # Missing field2, field3

        # Act
        with patch.object(agent, "log_warning") as mock_log_warning:
            result = agent._validate_multi_output(output)

            # Assert
            mock_log_warning.assert_not_called()
            # With ignore mode, still include missing fields as None
            self.assertEqual(
                result, {"field1": "value1", "field2": None, "field3": None}
            )

    def test_validate_multi_output_missing_fields_mode_warn(self):
        """Test missing fields with 'warn' mode - logs warning, includes None values."""
        # Arrange
        agent = self._create_agent(["field1", "field2"], {"output_validation": "warn"})
        output = {"field1": "value1"}  # Missing field2

        # Act
        with patch.object(agent, "log_warning") as mock_log_warning:
            result = agent._validate_multi_output(output)

            # Assert
            mock_log_warning.assert_called_once()
            warning_msg = mock_log_warning.call_args[0][0]
            self.assertIn("missing declared output fields", warning_msg)
            self.assertIn("field2", warning_msg)
            self.assertIn("test_agent", warning_msg)
            # Result still includes missing as None
            self.assertEqual(result, {"field1": "value1", "field2": None})

    def test_validate_multi_output_missing_fields_mode_error(self):
        """Test missing fields with 'error' mode - raises ValueError."""
        # Arrange
        agent = self._create_agent(["field1", "field2"], {"output_validation": "error"})
        output = {"field1": "value1"}  # Missing field2

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            agent._validate_multi_output(output)

        error_msg = str(context.exception)
        self.assertIn("missing declared output fields", error_msg)
        self.assertIn("field2", error_msg)
        self.assertIn("test_agent", error_msg)

    def test_validate_multi_output_missing_multiple_fields_error(self):
        """Test error message includes all missing fields."""
        # Arrange
        agent = self._create_agent(
            ["field1", "field2", "field3", "field4"],
            {"output_validation": "error"},
        )
        output = {"field2": "value2"}  # Missing field1, field3, field4

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            agent._validate_multi_output(output)

        error_msg = str(context.exception)
        self.assertIn("field1", error_msg)
        self.assertIn("field3", error_msg)
        self.assertIn("field4", error_msg)

    def test_validate_multi_output_all_fields_missing_error(self):
        """Test error when all declared fields are missing."""
        # Arrange
        agent = self._create_agent(["field1", "field2"], {"output_validation": "error"})
        output = {"unrelated": "value"}  # All declared fields missing

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            agent._validate_multi_output(output)

        error_msg = str(context.exception)
        self.assertIn("field1", error_msg)
        self.assertIn("field2", error_msg)

    # ======================================================================
    # TESTS: Non-Dict Returns - Graceful Degradation
    # ======================================================================

    def test_validate_multi_output_wraps_scalar_in_first_field_ignore(self):
        """Test scalar return wrapped in first field with 'ignore' mode."""
        # Arrange
        agent = self._create_agent(
            ["field1", "field2"], {"output_validation": "ignore"}
        )
        scalar_value = "scalar result"

        # Act
        with patch.object(agent, "log_warning"):
            result = agent._validate_multi_output(scalar_value)

            # Assert
            self.assertEqual(result, {"field1": "scalar result"})

    def test_validate_multi_output_wraps_scalar_with_warning(self):
        """Test scalar return logs warning before wrapping."""
        # Arrange
        agent = self._create_agent(["field1", "field2"], {"output_validation": "warn"})
        scalar_value = 42

        # Act
        with patch.object(agent, "log_warning") as mock_log_warning:
            result = agent._validate_multi_output(scalar_value)

            # Assert
            mock_log_warning.assert_called_once()
            warning_msg = mock_log_warning.call_args[0][0]
            self.assertIn("test_agent", warning_msg)
            self.assertIn("declares multiple outputs", warning_msg)
            self.assertIn("field1", warning_msg)
            self.assertIn("int", warning_msg)
            self.assertEqual(result, {"field1": 42})

    def test_validate_multi_output_wraps_list_with_error(self):
        """Test list return raises error with 'error' mode."""
        # Arrange
        agent = self._create_agent(["field1", "field2"], {"output_validation": "error"})
        list_value = ["item1", "item2"]

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            agent._validate_multi_output(list_value)

        error_msg = str(context.exception)
        self.assertIn("declares multiple outputs", error_msg)
        self.assertIn("field1", error_msg)
        self.assertIn("list", error_msg)

    def test_validate_multi_output_wraps_none_value(self):
        """Test None return wrapped in first field."""
        # Arrange
        agent = self._create_agent(["output", "metadata"])

        # Act
        result = agent._validate_multi_output(None)

        # Assert
        self.assertEqual(result, {"output": None})

    def test_validate_multi_output_wraps_object_value(self):
        """Test arbitrary object wrapped in first field."""
        # Arrange
        agent = self._create_agent(["result", "status"])

        class CustomObject:
            def __init__(self):
                self.data = "custom"

        obj = CustomObject()

        # Act
        result = agent._validate_multi_output(obj)

        # Assert
        self.assertEqual(result, {"result": obj})
        self.assertEqual(result["result"].data, "custom")

    # ======================================================================
    # TESTS: Validation Mode Default Behavior
    # ======================================================================

    def test_validate_multi_output_default_mode_is_warn(self):
        """Test that default validation mode is 'warn' when not specified."""
        # Arrange
        agent = self._create_agent(["field1", "field2"], {})
        output = {"field1": "value1"}  # Missing field2

        # Act
        with patch.object(agent, "log_warning") as mock_log_warning:
            result = agent._validate_multi_output(output)

            # Assert - Should warn (not error)
            mock_log_warning.assert_called_once()

    def test_validate_multi_output_context_without_validation_key(self):
        """Test behavior when context has no 'output_validation' key."""
        # Arrange
        agent = self._create_agent(["field1"], {})

        # Act
        result = agent._validate_multi_output({"field1": "value"})

        # Assert - Should use default behavior
        self.assertEqual(result, {"field1": "value"})

    # ======================================================================
    # TESTS: Edge Cases
    # ======================================================================

    def test_validate_multi_output_empty_output_dict_ignore(self):
        """Test empty dict with 'ignore' mode."""
        # Arrange
        agent = self._create_agent(
            ["field1", "field2"], {"output_validation": "ignore"}
        )
        output = {}

        # Act
        result = agent._validate_multi_output(output)

        # Assert
        self.assertEqual(result, {"field1": None, "field2": None})

    def test_validate_multi_output_empty_output_dict_error(self):
        """Test empty dict with 'error' mode raises ValueError."""
        # Arrange
        agent = self._create_agent(["field1"], {"output_validation": "error"})
        output = {}

        # Act & Assert
        with self.assertRaises(ValueError):
            agent._validate_multi_output(output)

    def test_validate_multi_output_empty_fields_list(self):
        """Test with empty output_fields list in ignore mode."""
        # Arrange
        agent = self._create_agent([], {"output_validation": "ignore"})
        output = {"field1": "value1"}

        # Act
        result = agent._validate_multi_output(output)

        # Assert - Empty fields list with ignore mode means nothing should be returned
        self.assertEqual(result, {})

    def test_validate_multi_output_case_sensitive_field_matching(self):
        """Test that field matching is case-sensitive in ignore mode."""
        # Arrange
        agent = self._create_agent(
            ["Field1", "field2"], {"output_validation": "ignore"}
        )
        output = {"field1": "wrong", "Field1": "correct", "field2": "value2"}

        # Act
        result = agent._validate_multi_output(output)

        # Assert - Only declared fields (case-sensitive match)
        self.assertEqual(result, {"Field1": "correct", "field2": "value2"})
        self.assertNotIn("field1", result)

    def test_validate_multi_output_preserves_complex_values(self):
        """Test that complex data types are preserved in output."""
        # Arrange
        agent = self._create_agent(["data", "metadata"])
        complex_data = {
            "nested": {
                "deep": [1, 2, 3],
                "value": "complex",
            },
            "list": ["a", "b", "c"],
            "number": 42.5,
            "bool": True,
        }
        metadata = [{"key": "value"}]
        output = {"data": complex_data, "metadata": metadata}

        # Act
        result = agent._validate_multi_output(output)

        # Assert
        self.assertEqual(result["data"], complex_data)
        self.assertEqual(result["metadata"], metadata)

    # ======================================================================
    # TESTS: Multiple Non-Dict Type Handling
    # ======================================================================

    def test_validate_multi_output_wraps_dict_error_with_non_dict(self):
        """Test error message correctly identifies non-dict type."""
        # Arrange
        agent = self._create_agent(["out1"], {"output_validation": "error"})

        # Test with various types
        test_cases = [
            ("string value", "str"),
            (123, "int"),
            ([1, 2, 3], "list"),
            ((1, 2), "tuple"),
            ({1, 2}, "set"),
        ]

        for value, type_name in test_cases:
            # Act & Assert
            with self.assertRaises(ValueError) as context:
                agent._validate_multi_output(value)

            error_msg = str(context.exception)
            self.assertIn(type_name, error_msg)

    # ======================================================================
    # TESTS: Integration with Agent Logging
    # ======================================================================

    def test_validate_multi_output_uses_agent_logging(self):
        """Test that validation uses agent's logging methods."""
        # Arrange
        agent = self._create_agent(["field1"], {"output_validation": "warn"})
        output = {}

        # Act
        with patch.object(agent, "log_warning") as mock_warning:
            with patch.object(agent, "log_debug") as mock_debug:
                agent._validate_multi_output(output)

                # Assert
                mock_warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
