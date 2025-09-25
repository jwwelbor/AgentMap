import unittest
from agentmap.services.graph.scaffold.service_requirements_parser import ServiceRequirementsParser
from agentmap.models.scaffold_types import ServiceRequirements, ServiceAttribute


class TestServiceRequirementParser(unittest.TestCase):
    """Test ServiceRequirementParser following established patterns."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ServiceRequirementsParser()

    def test_parse_services_with_empty_context_returns_empty_requirements(self):
        """Test parse_services() with empty context returns empty ServiceRequirements."""
        result = self.parser.parse_services("")
        
        self.assertIsInstance(result, ServiceRequirements)
        self.assertEqual(result.services, [])
        self.assertEqual(result.protocols, [])
        self.assertEqual(result.imports, [])
        self.assertEqual(result.attributes, [])
        self.assertEqual(result.usage_examples, {})

    def test_parse_services_with_none_context_returns_empty_requirements(self):
        """Test parse_services() with None context returns empty ServiceRequirements."""
        result = self.parser.parse_services(None)
        
        self.assertIsInstance(result, ServiceRequirements)
        self.assertEqual(result.services, [])
        self.assertEqual(result.protocols, [])
        self.assertEqual(result.imports, [])
        self.assertEqual(result.attributes, [])
        self.assertEqual(result.usage_examples, {})

    def test_parse_services_with_json_context_llm_service(self):
        """Test parse_services() with JSON context containing LLM service."""
        context = '{"services": ["llm"]}'
        result = self.parser.parse_services(context)
        
        self.assertIsInstance(result, ServiceRequirements)
        self.assertEqual(result.services, ["llm"])
        self.assertEqual(result.protocols, ["LLMCapableAgent"])
        self.assertEqual(result.imports, ["from agentmap.services.protocols import LLMCapableAgent"])
        self.assertEqual(len(result.attributes), 1)
        
        # Verify attribute structure
        llm_attr = result.attributes[0]
        self.assertIsInstance(llm_attr, ServiceAttribute)
        self.assertEqual(llm_attr.name, "llm_service")
        self.assertEqual(llm_attr.type_hint, "LLMServiceProtocol")
        self.assertEqual(llm_attr.documentation, "LLM service for calling language models")
        
        # Verify usage example exists
        self.assertIn("llm", result.usage_examples)
        self.assertIn("llm_service.call_llm", result.usage_examples["llm"])

    def test_parse_services_with_storage_service_unified_approach(self):
        """Test parse_services() with unified storage service."""
        context = '{"services": ["storage"]}'
        result = self.parser.parse_services(context)
        
        self.assertEqual(result.services, ["storage"])
        self.assertEqual(result.protocols, ["StorageCapableAgent"])
        self.assertEqual(result.imports, ["from agentmap.services.protocols import StorageCapableAgent"])
        self.assertEqual(len(result.attributes), 1)
        
        # Verify storage attribute
        storage_attr = result.attributes[0]
        self.assertEqual(storage_attr.name, "storage_service")
        self.assertEqual(storage_attr.type_hint, "StorageServiceProtocol")
        self.assertEqual(storage_attr.documentation, "Generic storage service (supports all storage types)")

    def test_parse_services_with_specific_storage_types(self):
        """Test parse_services() with specific storage types uses separate services."""
        context = '{"services": ["csv", "json"]}'
        result = self.parser.parse_services(context)
        
        self.assertEqual(result.services, ["csv", "json"])
        self.assertEqual(len(result.protocols), 2)
        self.assertIn("CSVCapableAgent", result.protocols)
        self.assertIn("JSONCapableAgent", result.protocols)
        
        # Verify separate imports
        self.assertIn("from agentmap.services.protocols import CSVCapableAgent", result.imports)
        self.assertIn("from agentmap.services.protocols import JSONCapableAgent", result.imports)
        
        # Verify attributes
        self.assertEqual(len(result.attributes), 2)
        attr_names = [attr.name for attr in result.attributes]
        self.assertIn("csv_service", attr_names)
        self.assertIn("json_service", attr_names)

    def test_parse_services_with_string_format_context(self):
        """Test parse_services() with string format context."""
        context = "services:llm|storage"
        result = self.parser.parse_services(context)
        
        self.assertEqual(result.services, ["llm", "storage"])
        self.assertEqual(len(result.protocols), 2)
        self.assertIn("LLMCapableAgent", result.protocols)
        self.assertIn("StorageCapableAgent", result.protocols)

    def test_parse_services_with_dict_context(self):
        """Test parse_services() with dict context."""
        context = {"services": ["llm", "csv"]}
        result = self.parser.parse_services(context)
        
        self.assertEqual(result.services, ["llm", "csv"])
        self.assertEqual(len(result.protocols), 2)
        self.assertIn("LLMCapableAgent", result.protocols)
        self.assertIn("CSVCapableAgent", result.protocols)

    def test_parse_services_with_unknown_service_raises_error(self):
        """Test parse_services() with unknown service raises ValueError."""
        context = '{"services": ["unknown_service"]}'
        
        with self.assertRaises(ValueError) as cm:
            self.parser.parse_services(context)
        
        self.assertIn("Unknown services: ['unknown_service']", str(cm.exception))
        self.assertIn("Available:", str(cm.exception))

    def test_parse_services_removes_duplicate_protocols(self):
        """Test parse_services() removes duplicate protocols from multiple services."""
        # Both llm and storage might theoretically share protocols in future
        context = '{"services": ["llm"]}'
        result = self.parser.parse_services(context)
        
        # Ensure no duplicates in protocols
        unique_protocols = set(result.protocols)
        self.assertEqual(len(result.protocols), len(unique_protocols))
        
        # Ensure no duplicates in imports
        unique_imports = set(result.imports)
        self.assertEqual(len(result.imports), len(unique_imports))

    def test_parse_services_mixed_llm_and_specific_storage(self):
        """Test parse_services() with LLM and specific storage types."""
        context = '{"services": ["llm", "csv", "vector"]}'
        result = self.parser.parse_services(context)
        
        self.assertEqual(result.services, ["llm", "csv", "vector"])
        
        # Should have separate protocols for each service
        expected_protocols = ["LLMCapableAgent", "CSVCapableAgent", "VectorCapableAgent"]
        for protocol in expected_protocols:
            self.assertIn(protocol, result.protocols)
        
        # Should have separate attributes for each service
        attr_names = [attr.name for attr in result.attributes]
        expected_attrs = ["llm_service", "csv_service", "vector_service"]
        for attr_name in expected_attrs:
            self.assertIn(attr_name, attr_names)

    def test_extract_services_list_handles_various_formats(self):
        """Test _extract_services_list() with various input formats."""
        # Test empty/None
        self.assertEqual(self.parser._extract_services_list(""), [])
        self.assertEqual(self.parser._extract_services_list(None), [])
        
        # Test dict
        self.assertEqual(self.parser._extract_services_list({"services": ["llm"]}), ["llm"])
        
        # Test JSON string
        self.assertEqual(self.parser._extract_services_list('{"services": ["llm", "storage"]}'), ["llm", "storage"])
        
        # Test key:value string
        self.assertEqual(self.parser._extract_services_list("services:llm|storage"), ["llm", "storage"])
        
        # Test malformed JSON
        self.assertEqual(self.parser._extract_services_list('{"malformed": json'), [])


if __name__ == '__main__':
    unittest.main()
