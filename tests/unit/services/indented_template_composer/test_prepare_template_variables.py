"""
Unit tests for AgentTemplateComposer._prepare_template_variables with multi-output support.

These tests validate the integration of multi-output scaffolding into template variable preparation.
"""

import unittest
from unittest.mock import Mock

from agentmap.models.scaffold_types import ServiceAttribute, ServiceRequirements
from agentmap.services.indented_template_composer.agent_template_composer import (
    AgentTemplateComposer,
)
from agentmap.services.indented_template_composer.code_generator import CodeGenerator
from agentmap.services.indented_template_composer.template_loader import TemplateLoader
from agentmap.services.logging_service import LoggingService


class TestPrepareTemplateVariables(unittest.TestCase):
    """Unit tests for _prepare_template_variables with multi-output support."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logging_service = Mock(spec=LoggingService)
        self.mock_logging_service.get_class_logger.return_value = Mock()

        self.mock_template_loader = Mock(spec=TemplateLoader)
        self.code_generator = CodeGenerator(self.mock_logging_service)

        self.composer = AgentTemplateComposer(
            template_loader=self.mock_template_loader,
            code_generator=self.code_generator,
            logging_service=self.mock_logging_service,
        )

    def test_prepare_template_variables_single_output_field(self):
        """Test that single output field is handled correctly."""
        agent_type = "TestAgent"
        info = {
            "agent_type": "TestAgent",
            "node_name": "test_node",
            "description": "Test agent",
            "input_fields": ["input1"],
            "output_field": "result",
            "context": "",
            "prompt": "Test prompt",
        }
        service_reqs = ServiceRequirements(
            services=[], protocols=[], imports=[], attributes=[], usage_examples={}
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # Verify output_field is set correctly
        self.assertEqual(variables["output_field"], "result")

        # Verify multi-output variables are included
        self.assertIn("return_type_hint", variables)
        self.assertIn("return_docstring", variables)
        self.assertIn("process_body", variables)

    def test_prepare_template_variables_pipe_delimited_output_fields(self):
        """Test that pipe-delimited output fields are parsed correctly."""
        agent_type = "MultiOutputAgent"
        info = {
            "agent_type": "MultiOutputAgent",
            "node_name": "multi_node",
            "description": "Agent with multiple outputs",
            "input_fields": ["data"],
            "output_field": "result|status|count",
            "context": "",
            "prompt": "Multi-output prompt",
        }
        service_reqs = ServiceRequirements(
            services=[], protocols=[], imports=[], attributes=[], usage_examples={}
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # Verify output_field is preserved
        self.assertEqual(variables["output_field"], "result|status|count")

        # Verify output_fields_list is created
        self.assertIn("output_fields_list", variables)
        output_fields = eval(variables["output_fields_list"])
        self.assertEqual(output_fields, ["result", "status", "count"])

        # Verify multi-output variables are included
        self.assertIn("return_type_hint", variables)
        self.assertIn("return_docstring", variables)
        self.assertIn("process_body", variables)

    def test_prepare_template_variables_multi_output_return_type_hint(self):
        """Test that return_type_hint is appropriate for multi-output."""
        agent_type = "MultiAgent"
        info = {
            "agent_type": "MultiAgent",
            "node_name": "multi_node",
            "description": "Multi-output agent",
            "input_fields": ["input1"],
            "output_field": "output1|output2|output3",
            "context": "",
            "prompt": "",
        }
        service_reqs = ServiceRequirements(
            services=[], protocols=[], imports=[], attributes=[], usage_examples={}
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # Return type should be Dict[str, Any] for multi-output
        return_type = variables["return_type_hint"]
        self.assertIn("Dict", return_type)

    def test_prepare_template_variables_no_output_field(self):
        """Test handling of None or empty output_field."""
        agent_type = "NoOutputAgent"
        info = {
            "agent_type": "NoOutputAgent",
            "node_name": "no_output_node",
            "description": "Agent with no output",
            "input_fields": [],
            "output_field": None,
            "context": "",
            "prompt": "",
        }
        service_reqs = ServiceRequirements(
            services=[], protocols=[], imports=[], attributes=[], usage_examples={}
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # output_field should be "None specified"
        self.assertEqual(variables["output_field"], "None specified")

        # Should still include multi-output variables
        self.assertIn("return_type_hint", variables)
        self.assertIn("return_docstring", variables)
        self.assertIn("process_body", variables)

    def test_prepare_template_variables_with_services(self):
        """Test that multi-output variables work with service requirements."""
        agent_type = "ServiceAgent"
        info = {
            "agent_type": "ServiceAgent",
            "node_name": "service_node",
            "description": "Service-based multi-output agent",
            "input_fields": ["config"],
            "output_field": "result|error|metadata",
            "context": '{"services": ["llm"]}',
            "prompt": "Service prompt",
        }
        service_reqs = ServiceRequirements(
            services=["llm"],
            protocols=["LLMCapableAgent"],
            imports=["from agentmap.services.protocols import LLMCapableAgent"],
            attributes=[
                ServiceAttribute("llm_service", "LLMServiceProtocol", "LLM service")
            ],
            usage_examples={},
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # Verify service variables are included
        self.assertIn("llm", variables["service_description"])
        self.assertIn("LLMCapableAgent", variables["class_definition"])

        # Verify multi-output variables are still included
        self.assertIn("return_type_hint", variables)
        self.assertIn("return_docstring", variables)
        self.assertIn("process_body", variables)

    def test_prepare_template_variables_preserves_existing_variables(self):
        """Test that new multi-output variables don't break existing ones."""
        agent_type = "ComplexAgent"
        info = {
            "agent_type": "ComplexAgent",
            "node_name": "complex_node",
            "description": "Complex agent with everything",
            "input_fields": ["input1", "input2", "input3"],
            "output_field": "primary|secondary",
            "context": "Complex context",
            "prompt": "Complex prompt",
        }
        service_reqs = ServiceRequirements(
            services=["llm", "csv"],
            protocols=["LLMCapableAgent", "CSVCapableAgent"],
            imports=[
                "from agentmap.services.protocols import LLMCapableAgent",
                "from agentmap.services.protocols import CSVCapableAgent",
            ],
            attributes=[
                ServiceAttribute("llm_service", "LLMServiceProtocol", "LLM service"),
                ServiceAttribute("csv_service", "CSVServiceProtocol", "CSV service"),
            ],
            usage_examples={"llm": "response = self.llm_service.call()", "csv": "data = self.csv_service.read()"},
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # Verify all existing variables are still present
        self.assertEqual(variables["agent_type"], "ComplexAgent")
        self.assertEqual(variables["class_name"], "ComplexAgent")
        self.assertEqual(variables["node_name"], "complex_node")
        self.assertEqual(variables["description"], "Complex agent with everything")
        self.assertEqual(variables["input_fields"], "input1, input2, input3")
        self.assertEqual(variables["output_field"], "primary|secondary")
        self.assertEqual(variables["context"], "Complex context")
        self.assertIn("Complex prompt", variables["prompt_doc"])

        # Verify service variables
        self.assertIn("llm, csv", variables["service_description"])
        self.assertIn("LLMCapableAgent", variables["class_definition"])
        self.assertIn("CSVCapableAgent", variables["class_definition"])

        # Verify new multi-output variables
        self.assertIn("return_type_hint", variables)
        self.assertIn("return_docstring", variables)
        self.assertIn("process_body", variables)


class TestGenerateMultiOutputScaffold(unittest.TestCase):
    """Unit tests for generate_multi_output_scaffold method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logging_service = Mock(spec=LoggingService)
        self.mock_logging_service.get_class_logger.return_value = Mock()

        self.code_generator = CodeGenerator(self.mock_logging_service)

    def test_generate_multi_output_scaffold_single_output(self):
        """Test scaffold generation for single output field."""
        output_fields = ["result"]

        result = self.code_generator.generate_multi_output_scaffold(output_fields)

        # Verify result structure
        self.assertIn("return_type_hint", result)
        self.assertIn("return_docstring", result)
        self.assertIn("process_body", result)

        # For single output, return type should be appropriate
        self.assertIsInstance(result["return_type_hint"], str)
        self.assertIsInstance(result["return_docstring"], str)
        self.assertIsInstance(result["process_body"], str)

    def test_generate_multi_output_scaffold_multiple_outputs(self):
        """Test scaffold generation for multiple output fields."""
        output_fields = ["result", "status", "count"]

        result = self.code_generator.generate_multi_output_scaffold(output_fields)

        # Verify result structure
        self.assertIn("return_type_hint", result)
        self.assertIn("return_docstring", result)
        self.assertIn("process_body", result)

        # For multi-output, return type should indicate Dict
        return_type = result["return_type_hint"]
        self.assertIn("Dict", return_type)

        # Docstring should mention all fields
        docstring = result["return_docstring"]
        self.assertIn("result", docstring)
        self.assertIn("status", docstring)
        self.assertIn("count", docstring)

    def test_generate_multi_output_scaffold_empty_list(self):
        """Test scaffold generation with empty output fields."""
        output_fields = []

        result = self.code_generator.generate_multi_output_scaffold(output_fields)

        # Should still return valid structure
        self.assertIn("return_type_hint", result)
        self.assertIn("return_docstring", result)
        self.assertIn("process_body", result)

    def test_generate_multi_output_scaffold_includes_return_example(self):
        """Test that scaffold includes return statement example."""
        output_fields = ["field1", "field2"]

        result = self.code_generator.generate_multi_output_scaffold(output_fields)

        # Process body should include a return statement example
        process_body = result["process_body"]
        self.assertIn("return", process_body)
        self.assertIn("{", process_body)
        self.assertIn("field1", process_body)
        self.assertIn("field2", process_body)


if __name__ == "__main__":
    unittest.main()
