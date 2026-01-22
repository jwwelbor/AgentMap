"""
Unit tests for DeclarationParser.

Tests parsing from string, simple dict, and full dict formats,
error handling for invalid formats, and normalization of different input formats.
"""

import unittest
from typing import Any, Dict
from unittest.mock import Mock

from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.services.declaration_parser import DeclarationParser
from tests.utils.mock_service_factory import MockServiceFactory


class TestDeclarationParser(unittest.TestCase):
    """Test DeclarationParser functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()

        # Create parser under test
        self.parser = DeclarationParser(self.mock_logging)

    def test_initialization(self):
        """Test parser initialization."""
        self.assertIsNotNone(self.parser)

    def test_parse_agent_from_simple_dict(self):
        """Test parsing agent from simple dictionary format."""
        agent_data = {
            "class_path": "test.agents.TestAgent",
            "requires": ["logging_service"],
            "capabilities": ["test", "example"],
        }

        result = self.parser.parse_agent("test_agent", agent_data, "test_source")

        self.assertIsInstance(result, AgentDeclaration)
        self.assertEqual(result.agent_type, "test_agent")
        self.assertEqual(result.class_path, "test.agents.TestAgent")
        self.assertEqual(result.source, "test_source")
        self.assertEqual(len(result.service_requirements), 1)
        self.assertEqual(result.service_requirements[0].name, "logging_service")
        self.assertEqual(result.capabilities, {"test", "example"})

    def test_parse_agent_from_full_dict(self):
        """Test parsing agent from full dictionary format."""
        agent_data = {
            "class": "test.agents.TestAgent",
            "services": ["logging_service", "config_service"],
            "protocols": ["TestProtocol"],
            "capabilities": ["test", "example"],
            "description": "Test agent for testing",
            "metadata": {"category": "test"},
            "config": {"enabled": True},
        }

        result = self.parser.parse_agent("test_agent", agent_data, "test_source")

        self.assertIsInstance(result, AgentDeclaration)
        self.assertEqual(result.agent_type, "test_agent")
        self.assertEqual(result.class_path, "test.agents.TestAgent")
        self.assertEqual(len(result.service_requirements), 2)
        self.assertEqual(len(result.protocol_requirements), 1)
        self.assertEqual(result.capabilities, {"test", "example"})
        self.assertEqual(result.metadata["category"], "test")
        self.assertEqual(result.config["enabled"], True)

    def test_parse_agent_from_minimal_dict(self):
        """Test parsing agent from minimal dictionary."""
        agent_data = {"class_path": "test.agents.MinimalAgent"}

        result = self.parser.parse_agent("minimal_agent", agent_data, "test_source")

        self.assertIsInstance(result, AgentDeclaration)
        self.assertEqual(result.agent_type, "minimal_agent")
        self.assertEqual(result.class_path, "test.agents.MinimalAgent")
        self.assertEqual(len(result.service_requirements), 0)
        self.assertEqual(len(result.protocol_requirements), 0)
        self.assertEqual(len(result.capabilities), 0)

    def test_parse_agent_with_class_alias(self):
        """Test parsing agent with 'class' field instead of 'class_path'."""
        agent_data = {"class": "test.agents.TestAgent", "requires": ["logging_service"]}

        result = self.parser.parse_agent("test_agent", agent_data, "test_source")

        self.assertEqual(result.class_path, "test.agents.TestAgent")

    def test_parse_agent_invalid_data_missing_class_path(self):
        """Test parsing agent with missing class_path raises error."""
        agent_data = {"requires": ["logging_service"]}

        with self.assertRaises(ValueError) as context:
            self.parser.parse_agent("test_agent", agent_data, "test_source")

        self.assertIn("No valid class path found", str(context.exception))

    def test_parse_agent_invalid_data_type(self):
        """Test parsing agent with invalid data type raises error."""
        with self.assertRaises(ValueError):
            self.parser.parse_agent("test_agent", 123, "test_source")

    def test_parse_service_from_simple_dict(self):
        """Test parsing service from simple dictionary format."""
        service_data = {
            "class_path": "test.services.TestService",
            "required": ["logging_service"],
            "optional": ["config_service"],
            "implements": ["TestServiceProtocol"],
            "singleton": True,
        }

        result = self.parser.parse_service("test_service", service_data, "test_source")

        self.assertIsInstance(result, ServiceDeclaration)
        self.assertEqual(result.service_name, "test_service")
        self.assertEqual(result.class_path, "test.services.TestService")
        self.assertEqual(result.required_dependencies, ["logging_service"])
        self.assertEqual(result.optional_dependencies, ["config_service"])
        self.assertEqual(result.implements_protocols, ["TestServiceProtocol"])
        self.assertTrue(result.singleton)
        self.assertEqual(result.source, "test_source")

    def test_parse_service_from_full_dict(self):
        """Test parsing service from full dictionary format."""
        service_data = {
            "class": "test.services.TestService",
            "required": ["logging_service"],
            "optional": ["config_service"],
            "implements": ["TestServiceProtocol"],
            "requires": ["DependencyProtocol"],
            "singleton": False,
            "lazy_load": True,
            "factory_method": "create_service",
            "metadata": {"type": "infrastructure"},
            "config": {"timeout": 30},
        }

        result = self.parser.parse_service("test_service", service_data, "test_source")

        self.assertIsInstance(result, ServiceDeclaration)
        self.assertEqual(result.service_name, "test_service")
        self.assertEqual(result.class_path, "test.services.TestService")
        self.assertEqual(result.required_dependencies, ["logging_service"])
        self.assertEqual(result.optional_dependencies, ["config_service"])
        self.assertEqual(result.implements_protocols, ["TestServiceProtocol"])
        self.assertEqual(result.requires_protocols, ["DependencyProtocol"])
        self.assertFalse(result.singleton)
        self.assertTrue(result.lazy_load)
        self.assertEqual(result.factory_method, "create_service")
        self.assertEqual(result.metadata["type"], "infrastructure")
        self.assertEqual(result.config["timeout"], 30)

    def test_parse_service_with_class_alias(self):
        """Test parsing service with 'class' field instead of 'class_path'."""
        service_data = {"class": "test.services.TestService"}

        result = self.parser.parse_service("test_service", service_data, "test_source")

        self.assertEqual(result.class_path, "test.services.TestService")

    def test_parse_service_invalid_data_missing_class_path(self):
        """Test parsing service with missing class_path raises error."""
        service_data = {"required": ["logging_service"]}

        with self.assertRaises(ValueError) as context:
            self.parser.parse_service("test_service", service_data, "test_source")

        self.assertIn("No valid class path found", str(context.exception))

    def test_parse_service_invalid_data_type(self):
        """Test parsing service with invalid data type raises error."""
        with self.assertRaises(ValueError):
            self.parser.parse_service("test_service", 123, "test_source")

    def test_class_path_extraction(self):
        """Test various ways of specifying class path in declarations."""
        # Test 'class' field
        agent_data1 = {"class": "test.agents.TestAgent"}
        result1 = self.parser.parse_agent("test_agent", agent_data1, "test_source")
        self.assertEqual(result1.class_path, "test.agents.TestAgent")

        # Test 'class_path' field
        agent_data2 = {"class_path": "test.agents.TestAgent"}
        result2 = self.parser.parse_agent("test_agent", agent_data2, "test_source")
        self.assertEqual(result2.class_path, "test.agents.TestAgent")

        # Test service with 'class' field
        service_data1 = {"class": "test.services.TestService"}
        result3 = self.parser.parse_service(
            "test_service", service_data1, "test_source"
        )
        self.assertEqual(result3.class_path, "test.services.TestService")

    def test_service_requirements_parsing(self):
        """Test parsing service requirements from different structures."""
        # Test parsing from 'requires' field
        agent_data1 = {
            "class_path": "test.TestAgent",
            "requires": ["logging_service", "config_service"],
        }
        result1 = self.parser.parse_agent("test_agent", agent_data1, "test_source")
        self.assertEqual(len(result1.service_requirements), 2)
        self.assertEqual(result1.service_requirements[0].name, "logging_service")

        # Test parsing from 'services' field
        agent_data2 = {"class_path": "test.TestAgent", "services": ["storage_service"]}
        result2 = self.parser.parse_agent("test_agent", agent_data2, "test_source")
        self.assertEqual(len(result2.service_requirements), 1)
        self.assertEqual(result2.service_requirements[0].name, "storage_service")

        # Test parsing both fields
        agent_data3 = {
            "class_path": "test.TestAgent",
            "requires": ["logging_service"],
            "services": ["config_service"],
        }
        result3 = self.parser.parse_agent("test_agent", agent_data3, "test_source")
        self.assertEqual(len(result3.service_requirements), 2)

    def test_error_handling_with_none_values(self):
        """Test error handling when required values are None."""
        with self.assertRaises(ValueError):
            self.parser.parse_agent(None, {}, "test_source")

        with self.assertRaises(ValueError):
            self.parser.parse_service("test_service", None, "test_source")

    def test_error_handling_with_empty_agent_type(self):
        """Test behavior when agent_type is empty."""
        agent_data = {"class_path": "test.TestAgent"}

        # Empty agent type should be accepted by the parser
        result = self.parser.parse_agent("", agent_data, "test_source")
        self.assertEqual(result.agent_type, "")
        self.assertEqual(result.class_path, "test.TestAgent")

    def test_error_handling_with_empty_service_name(self):
        """Test behavior when service_name is empty."""
        service_data = {"class_path": "test.TestService"}

        # Empty service name should be accepted by the parser
        result = self.parser.parse_service("", service_data, "test_source")
        self.assertEqual(result.service_name, "")
        self.assertEqual(result.class_path, "test.TestService")

    def test_metadata_preservation(self):
        """Test that metadata is properly preserved during parsing."""
        agent_data = {
            "class_path": "test.TestAgent",
            "metadata": {
                "author": "test_user",
                "version": "1.0.0",
                "description": "Test agent",
            },
        }

        result = self.parser.parse_agent("test_agent", agent_data, "test_source")

        self.assertEqual(result.metadata["author"], "test_user")
        self.assertEqual(result.metadata["version"], "1.0.0")
        self.assertEqual(result.metadata["description"], "Test agent")

    def test_config_preservation(self):
        """Test that config is properly preserved during parsing."""
        service_data = {
            "class_path": "test.TestService",
            "config": {"enabled": True, "timeout": 30, "retries": 3},
        }

        result = self.parser.parse_service("test_service", service_data, "test_source")

        self.assertEqual(result.config["enabled"], True)
        self.assertEqual(result.config["timeout"], 30)
        self.assertEqual(result.config["retries"], 3)


if __name__ == "__main__":
    unittest.main()
