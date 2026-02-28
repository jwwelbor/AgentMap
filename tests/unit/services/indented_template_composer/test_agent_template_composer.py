"""
Unit tests for AgentTemplateComposer scaffolding generation.

Tests the compose_template method with multi-output support, covering:
- Single output generates Any type hint
- Multi-output generates Dict[str, Any] type hint
- Docstrings list all fields
- Template body has correct return dict structure
"""

import unittest
from unittest.mock import Mock

from agentmap.models.scaffold_types import (
    ServiceAttribute,
    ServiceRequirements,
)
from agentmap.services.indented_template_composer.agent_template_composer import (
    AgentTemplateComposer,
)
from agentmap.services.indented_template_composer.code_generator import CodeGenerator
from agentmap.services.indented_template_composer.template_loader import TemplateLoader
from tests.utils.mock_service_factory import MockServiceFactory


class TestAgentTemplateComposerScaffoldGeneration(unittest.TestCase):
    """Test AgentTemplateComposer.compose_template with scaffolding generation."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.code_generator = CodeGenerator(self.mock_logging)

        # Create mock template loader with proper template loading
        self.mock_template_loader = Mock(spec=TemplateLoader)

        # Create composer
        self.composer = AgentTemplateComposer(
            self.mock_template_loader,
            self.code_generator,
            self.mock_logging,
        )

    def _mock_template_loader(self, templates: dict):
        """Configure mock template loader with provided templates."""

        def load_template(path):
            if path in templates:
                return templates[path]
            raise ValueError(f"Template not found: {path}")

        self.mock_template_loader.load_template = Mock(side_effect=load_template)
        self.composer._load_template = self.mock_template_loader.load_template

    def _create_basic_master_template(self):
        """Create a basic master template for testing."""
        # Include all variables that _prepare_template_variables creates
        return """{header}
{class_definition}
{init_method}
{process_method}
{helper_methods}
{footer}
{service_examples}
"""

    def _create_basic_modular_templates(self):
        """Create basic modular templates for testing."""
        return {
            "master_template.txt": self._create_basic_master_template(),
            "modular/header.txt": '{imports}\n"""Header for {agent_type} agent"""',
            "modular/class_definition.txt": 'class {class_definition}:\n    """Agent class."""',
            "modular/init_method.txt": (
                "    def __init__(self):{service_attributes}\n" "        pass"
            ),
            "modular/process_method.txt": (
                "    def process(self, inputs) -> {return_type_hint}:\n"
                '        """{return_docstring}"""\n'
                "{input_field_access}\n"
                "{process_body}"
            ),
            "modular/helper_methods.txt": "    # Helper methods",
            "modular/footer.txt": "    # Footer",
        }

    def test_single_output_generates_any_type_hint(self):
        """Test that single output field generates Any type hint."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "data_processor"
        info = {
            "agent_type": agent_type,
            "node_name": "process_data",
            "description": "Process input data",
            "input_fields": ["input_data"],
            "output_field": "output_result",
            "prompt": None,
            "context": "Processing context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify type hint is Any for single output
        self.assertIn("-> Any", result)
        self.assertNotIn("-> Dict[str, Any]", result)

    def test_single_output_docstring_mentions_field_name(self):
        """Test that single output docstring mentions the field name."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "processor"
        info = {
            "agent_type": agent_type,
            "node_name": "my_processor",
            "description": "Test processor",
            "input_fields": [],
            "output_field": "result_data",
            "prompt": None,
            "context": "Test context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify docstring mentions the output field name
        self.assertIn("result_data", result)

    def test_single_output_process_body_pattern(self):
        """Test that single output process body has correct pattern."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "transformer"
        info = {
            "agent_type": agent_type,
            "node_name": "transform",
            "description": "Transform data",
            "input_fields": ["raw_input"],
            "output_field": "transformed",
            "prompt": None,
            "context": "Transformation context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify process body has single-output pattern
        self.assertIn("return result", result)
        self.assertIn("BaseAgent handles state management", result)

    def test_multi_output_two_fields_generates_dict_type_hint(self):
        """Test that two output fields generate Dict[str, Any] type hint."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "analyzer"
        info = {
            "agent_type": agent_type,
            "node_name": "analyze",
            "description": "Analyze data",
            "input_fields": ["data"],
            "output_field": "status|result",  # Multi-output format
            "prompt": None,
            "context": "Analysis context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify type hint is Dict[str, Any] for multiple outputs
        self.assertIn("-> Dict[str, Any]", result)

    def test_multi_output_three_fields_generates_dict_type_hint(self):
        """Test that three output fields generate Dict[str, Any] type hint."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "processor"
        info = {
            "agent_type": agent_type,
            "node_name": "process",
            "description": "Process",
            "input_fields": [],
            "output_field": "status|data|metadata",  # Multi-output format
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify type hint is Dict[str, Any]
        self.assertIn("-> Dict[str, Any]", result)

    def test_multi_output_docstring_lists_all_fields(self):
        """Test that multi-output docstring lists all declared fields."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "extractor"
        info = {
            "agent_type": agent_type,
            "node_name": "extract",
            "description": "Extract information",
            "input_fields": ["text"],
            "output_field": "entities|relations|metadata",
            "prompt": None,
            "context": "Extraction context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify docstring mentions all fields
        self.assertIn("'entities'", result)
        self.assertIn("'relations'", result)
        self.assertIn("'metadata'", result)
        self.assertIn("Dictionary with keys", result)

    def test_multi_output_docstring_indicates_dict_requirement(self):
        """Test that multi-output docstring indicates dict return requirement."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "collector"
        info = {
            "agent_type": agent_type,
            "node_name": "collect",
            "description": "Collect data",
            "input_fields": [],
            "output_field": "field1|field2",
            "prompt": None,
            "context": "Collection context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify docstring mentions the dict requirement
        self.assertIn("All declared output fields should be included", result)

    def test_multi_output_template_body_has_return_dict(self):
        """Test that multi-output process body includes dict return structure."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "mapper"
        info = {
            "agent_type": agent_type,
            "node_name": "map",
            "description": "Map data",
            "input_fields": ["input"],
            "output_field": "mapped|transformed",
            "prompt": None,
            "context": "Mapping context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify process body includes dict return pattern
        self.assertIn("MULTI-OUTPUT agent", result)
        self.assertIn("return {", result)

    def test_multi_output_body_has_all_declared_fields(self):
        """Test that multi-output body includes all declared fields in return dict."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "validator"
        info = {
            "agent_type": agent_type,
            "node_name": "validate",
            "description": "Validate",
            "input_fields": [],
            "output_field": "is_valid|errors|warnings",
            "prompt": None,
            "context": "Validation context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify all fields are in the return dict
        self.assertIn("is_valid", result)
        self.assertIn("errors", result)
        self.assertIn("warnings", result)

    def test_multi_output_body_error_handling_includes_all_fields(self):
        """Test that multi-output error handling includes all fields."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "processor"
        info = {
            "agent_type": agent_type,
            "node_name": "process",
            "description": "Process",
            "input_fields": [],
            "output_field": "result1|result2",
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify error handling returns dict with all fields
        self.assertIn("except Exception", result)
        # Error handler should include field iteration
        self.assertIn("for f in", result)

    def test_prepare_template_variables_single_output_field(self):
        """Test _prepare_template_variables with single output field."""
        agent_type = "processor"
        info = {
            "agent_type": agent_type,
            "node_name": "process_node",
            "description": "Process data",
            "input_fields": ["input_data"],
            "output_field": "result",
            "prompt": "Process this",
            "context": "Processing context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # Verify return type hint is Any for single output
        self.assertEqual(variables["return_type_hint"], "Any")
        self.assertIn("result", variables["return_docstring"])

    def test_prepare_template_variables_multi_output_fields(self):
        """Test _prepare_template_variables with multi-output fields."""
        agent_type = "extractor"
        info = {
            "agent_type": agent_type,
            "node_name": "extract_node",
            "description": "Extract data",
            "input_fields": ["text"],
            "output_field": "entities|relations",
            "prompt": None,
            "context": "Extraction context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # Verify return type hint is Dict[str, Any] for multi-output
        self.assertEqual(variables["return_type_hint"], "Dict[str, Any]")
        self.assertIn("'entities'", variables["return_docstring"])
        self.assertIn("'relations'", variables["return_docstring"])

    def test_prepare_template_variables_empty_output_fields(self):
        """Test _prepare_template_variables handles empty output fields."""
        agent_type = "worker"
        info = {
            "agent_type": agent_type,
            "node_name": "work",
            "description": "Do work",
            "input_fields": [],
            "output_field": None,
            "prompt": None,
            "context": "Work context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        variables = self.composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

        # Should treat as single output with default name
        self.assertEqual(variables["return_type_hint"], "Any")
        self.assertIn("None specified", variables["output_field"])

    def test_compose_template_with_service_requirements(self):
        """Test compose_template with service requirements."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "service_consumer"
        info = {
            "agent_type": agent_type,
            "node_name": "consume_service",
            "description": "Consume service",
            "input_fields": ["request"],
            "output_field": "response",
            "prompt": None,
            "context": "Service context",
        }

        service_reqs = ServiceRequirements(
            services=["logging", "config"],
            protocols=["LoggingCapable"],
            imports=["from logging import Logger"],
            attributes=[
                ServiceAttribute(
                    name="logger",
                    type_hint="Logger",
                    documentation="Logger service",
                )
            ],
            usage_examples={"logging": "logger.info('message')"},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify template includes service info
        self.assertIn("LoggingCapable", result)
        self.assertIn("from logging import Logger", result)

    def test_multi_output_output_field_parsing_with_pipe(self):
        """Test that output field with pipe is parsed as multi-output."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "multi"
        info = {
            "agent_type": agent_type,
            "node_name": "multi_output",
            "description": "Multi output",
            "input_fields": [],
            "output_field": "a|b|c",  # Pipe-separated fields
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Should be multi-output
        self.assertIn("-> Dict[str, Any]", result)
        self.assertIn("'a'", result)
        self.assertIn("'b'", result)
        self.assertIn("'c'", result)

    def test_single_output_with_spaces_in_field_name(self):
        """Test single output handles field names with spaces."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "processor"
        info = {
            "agent_type": agent_type,
            "node_name": "node",
            "description": "Process",
            "input_fields": [],
            "output_field": "final_result",
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Should be single output with the field name
        self.assertIn("final_result", result)
        self.assertIn("-> Any", result)

    def test_multi_output_with_whitespace_in_field_names(self):
        """Test multi-output handles field names with extra whitespace."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "analyzer"
        info = {
            "agent_type": agent_type,
            "node_name": "analyze",
            "description": "Analyze",
            "input_fields": [],
            "output_field": "field1 | field2 | field3",  # Spaces around pipes
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Should trim whitespace and be multi-output
        self.assertIn("-> Dict[str, Any]", result)
        self.assertIn("'field1'", result)
        self.assertIn("'field2'", result)
        self.assertIn("'field3'", result)

    def test_docstring_format_single_output_mentions_state_management(self):
        """Test single output docstring mentions state management by BaseAgent."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "simple"
        info = {
            "agent_type": agent_type,
            "node_name": "simple",
            "description": "Simple",
            "input_fields": [],
            "output_field": "output",
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify docstring explains state management
        self.assertIn("BaseAgent handles state management", result)

    def test_return_dict_structure_in_multi_output_body(self):
        """Test that multi-output body has properly formatted return dict."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "formatter"
        info = {
            "agent_type": agent_type,
            "node_name": "format",
            "description": "Format",
            "input_fields": [],
            "output_field": "formatted|metadata",
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify return dict structure with comments for each field
        self.assertIn("formatted", result)
        self.assertIn("metadata", result)
        self.assertIn("Required output", result)

    def test_class_name_generation_in_template(self):
        """Test that class name is properly generated in template."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "my_custom_agent"
        info = {
            "agent_type": agent_type,
            "node_name": "custom",
            "description": "Custom",
            "input_fields": [],
            "output_field": "result",
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify class name is generated correctly (PascalCase with Agent suffix)
        self.assertIn("MyCustomAgent", result)

    def test_multiple_service_attributes_in_init(self):
        """Test that multiple service attributes are included in __init__."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "multi_service"
        info = {
            "agent_type": agent_type,
            "node_name": "multi",
            "description": "Multi service",
            "input_fields": [],
            "output_field": "result",
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=["logging", "config", "storage"],
            protocols=[],
            imports=[],
            attributes=[
                ServiceAttribute(
                    name="logger", type_hint="Logger", documentation="Logger"
                ),
                ServiceAttribute(
                    name="config", type_hint="Config", documentation="Config"
                ),
                ServiceAttribute(
                    name="storage", type_hint="Storage", documentation="Storage"
                ),
            ],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify all service attributes are mentioned
        self.assertIn("self.logger", result)
        self.assertIn("self.config", result)
        self.assertIn("self.storage", result)

    def test_input_fields_access_code_generation(self):
        """Test that input field access code is generated."""
        templates = self._create_basic_modular_templates()
        self._mock_template_loader(templates)

        agent_type = "accessor"
        info = {
            "agent_type": agent_type,
            "node_name": "access",
            "description": "Access fields",
            "input_fields": ["field1", "field2", "field3"],
            "output_field": "result",
            "prompt": None,
            "context": "Context",
        }

        service_reqs = ServiceRequirements(
            services=[],
            protocols=[],
            imports=[],
            attributes=[],
            usage_examples={},
        )

        result = self.composer.compose_template(agent_type, info, service_reqs)

        # Verify input field access code is generated
        self.assertIn("field1", result)
        self.assertIn("field2", result)
        self.assertIn("field3", result)


if __name__ == "__main__":
    unittest.main()
