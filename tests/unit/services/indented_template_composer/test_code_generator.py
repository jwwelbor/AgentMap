"""
Unit tests for CodeGenerator multi-output scaffold generation.

Tests the generate_multi_output_scaffold method and helper methods
for generating type hints, docstrings, and template bodies.
"""

import unittest
from unittest.mock import Mock

from agentmap.services.indented_template_composer.code_generator import CodeGenerator
from tests.utils.mock_service_factory import MockServiceFactory


class TestCodeGeneratorMultiOutputScaffold(unittest.TestCase):
    """Test CodeGenerator.generate_multi_output_scaffold functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.generator = CodeGenerator(self.mock_logging)

    def test_empty_output_fields_list(self):
        """Test with empty output fields list - should default to single output."""
        result = self.generator.generate_multi_output_scaffold([])

        self.assertIn("return_type_hint", result)
        self.assertIn("return_docstring", result)
        self.assertIn("process_body", result)

        # Empty list should be treated as single output with default field
        self.assertEqual(result["return_type_hint"], "Any")
        self.assertIn("result", result["return_docstring"])

    def test_single_output_field(self):
        """Test with single output field."""
        result = self.generator.generate_multi_output_scaffold(["output_data"])

        self.assertEqual(result["return_type_hint"], "Any")
        self.assertIn("output_data", result["return_docstring"])
        self.assertIn("BaseAgent handles state management", result["return_docstring"])
        self.assertIn("output_data", result["process_body"])
        self.assertIn("Your processing logic goes here", result["process_body"])
        self.assertIn("processed", result["process_body"])

    def test_multi_output_fields_two_fields(self):
        """Test with two output fields."""
        result = self.generator.generate_multi_output_scaffold(["field1", "field2"])

        self.assertEqual(result["return_type_hint"], "Dict[str, Any]")
        self.assertIn("'field1'", result["return_docstring"])
        self.assertIn("'field2'", result["return_docstring"])
        self.assertIn(
            "All declared output fields should be included", result["return_docstring"]
        )
        self.assertIn("field1", result["process_body"])
        self.assertIn("field2", result["process_body"])
        self.assertIn("MULTI-OUTPUT agent", result["process_body"])

    def test_multi_output_fields_three_fields(self):
        """Test with three output fields."""
        result = self.generator.generate_multi_output_scaffold(
            ["status", "data", "metadata"]
        )

        self.assertEqual(result["return_type_hint"], "Dict[str, Any]")
        self.assertIn("'status'", result["return_docstring"])
        self.assertIn("'data'", result["return_docstring"])
        self.assertIn("'metadata'", result["return_docstring"])
        # All fields should be in the return dict
        self.assertIn("status", result["process_body"])
        self.assertIn("data", result["process_body"])
        self.assertIn("metadata", result["process_body"])

    def test_single_output_body_format(self):
        """Test single output body format includes required elements."""
        body = self.generator._generate_single_output_body("my_output")

        # Check for required content
        self.assertIn("Your processing logic goes here", body)
        self.assertIn("try:", body)
        self.assertIn("except Exception as e:", body)
        self.assertIn("self.logger.error", body)
        self.assertIn("my_output", body)
        self.assertIn("return result", body)
        self.assertIn("datetime.now(timezone.utc)", body)

    def test_single_output_body_with_different_field_names(self):
        """Test single output body uses the provided field name."""
        body1 = self.generator._generate_single_output_body("field_a")
        body2 = self.generator._generate_single_output_body("field_b")

        self.assertIn("field_a", body1)
        self.assertNotIn("field_b", body1)

        self.assertIn("field_b", body2)
        self.assertNotIn("field_a", body2)

    def test_multi_output_body_format(self):
        """Test multi output body format includes required elements."""
        output_fields = ["field1", "field2"]
        return_dict = '{\n            "field1": None,  # Required output\n            "field2": None,  # Required output\n        }'

        body = self.generator._generate_multi_output_body(output_fields, return_dict)

        # Check for required content
        self.assertIn("MULTI-OUTPUT agent", body)
        self.assertIn("Your processing logic goes here", body)
        self.assertIn("try:", body)
        self.assertIn("except Exception as e:", body)
        self.assertIn("self.logger.error", body)
        self.assertIn("Extract/compute values for each output field", body)
        self.assertIn("Return dict with all declared fields", body)
        self.assertIn("return", body)

    def test_multi_output_body_error_handling(self):
        """Test multi output body includes error handling for all fields."""
        output_fields = ["status", "result"]
        return_dict = '{\n            "status": None,  # Required output\n            "result": None,  # Required output\n        }'

        body = self.generator._generate_multi_output_body(output_fields, return_dict)

        # Error handling should return dict with error info for each field
        self.assertIn("error", body)
        self.assertIn("for f in", body)

    def test_return_dict_format_single_field(self):
        """Test return dict format for single multi-output scenario."""
        result = self.generator.generate_multi_output_scaffold(["single"])

        # Single field should use Any type, not Dict
        self.assertEqual(result["return_type_hint"], "Any")

    def test_return_dict_format_multiple_fields(self):
        """Test return dict format has all fields with comments."""
        output_fields = ["output1", "output2", "output3"]
        result = self.generator.generate_multi_output_scaffold(output_fields)

        body = result["process_body"]

        # Check that return dict includes all fields
        self.assertIn("output1", body)
        self.assertIn("output2", body)
        self.assertIn("output3", body)

    def test_result_dict_has_all_required_keys(self):
        """Test result dict contains all required keys."""
        result = self.generator.generate_multi_output_scaffold(["field"])

        required_keys = {"return_type_hint", "return_docstring", "process_body"}
        self.assertEqual(set(result.keys()), required_keys)

    def test_docstring_clarity_single_output(self):
        """Test single output docstring is clear about state management."""
        result = self.generator.generate_multi_output_scaffold(["result"])

        docstring = result["return_docstring"]
        self.assertIn("store in graph state", docstring)
        self.assertIn("BaseAgent handles state management", docstring)

    def test_docstring_clarity_multi_output(self):
        """Test multi output docstring explains dict requirement."""
        result = self.generator.generate_multi_output_scaffold(["field1", "field2"])

        docstring = result["return_docstring"]
        self.assertIn("Dictionary with keys", docstring)
        self.assertIn("All declared output fields should be included", docstring)

    def test_type_hint_consistency_with_fields(self):
        """Test type hint matches the number of output fields."""
        # Single field uses Any
        single = self.generator.generate_multi_output_scaffold(["one"])
        self.assertEqual(single["return_type_hint"], "Any")

        # Two fields uses Dict[str, Any]
        double = self.generator.generate_multi_output_scaffold(["one", "two"])
        self.assertEqual(double["return_type_hint"], "Dict[str, Any]")

        # Three fields uses Dict[str, Any]
        triple = self.generator.generate_multi_output_scaffold(["one", "two", "three"])
        self.assertEqual(triple["return_type_hint"], "Dict[str, Any]")

    def test_process_body_indentation(self):
        """Test that process body has proper indentation."""
        result = self.generator.generate_multi_output_scaffold(["field"])
        body = result["process_body"]

        # Body should be indented for use in method
        lines = body.split("\n")
        for line in lines:
            if line.strip():  # Non-empty lines
                # Should start with spaces (indentation)
                self.assertTrue(line.startswith(" ") or line.startswith("\n"))

    def test_single_output_includes_timestamp(self):
        """Test single output body includes timestamp."""
        body = self.generator._generate_single_output_body("result")

        self.assertIn("timestamp", body)
        self.assertIn("datetime.now", body)

    def test_multi_output_fields_formatting_in_docstring(self):
        """Test multi output fields are formatted as quoted strings in docstring."""
        result = self.generator.generate_multi_output_scaffold(["field1", "field2"])
        docstring = result["return_docstring"]

        # Fields should be quoted in the docstring
        self.assertIn("'field1'", docstring)
        self.assertIn("'field2'", docstring)


if __name__ == "__main__":
    unittest.main()
