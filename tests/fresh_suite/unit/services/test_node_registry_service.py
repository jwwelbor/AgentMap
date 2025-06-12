"""
Unit tests for NodeRegistryService.

These tests validate the NodeRegistryService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock
from typing import Dict, Any, Optional

from agentmap.services.node_registry_service import NodeRegistryService, NodeMetadata
from tests.utils.mock_service_factory import MockServiceFactory


class TestNodeRegistryService(unittest.TestCase):
    """Unit tests for NodeRegistryService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "node_registry": {
                "max_description_length": 100
            }
        })
        
        # Initialize NodeRegistryService with all mocked dependencies
        self.service = NodeRegistryService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.configuration, self.mock_app_config_service)
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, 'NodeRegistryService')
        
        # Verify get_class_logger was called during initialization
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
        
        # Verify internal cache is initialized
        self.assertIsInstance(self.service._registry_cache, dict)
        self.assertEqual(len(self.service._registry_cache), 0)
    
    def test_service_logs_status(self):
        """Test that service status logging works correctly."""
        # Service initialization doesn't log by default, but we can test that logger works
        self.assertIsNotNone(self.mock_logger)
        self.assertEqual(self.mock_logger.name, 'NodeRegistryService')
    
    # =============================================================================
    # 2. Core Business Logic Tests
    # =============================================================================
    
    def test_build_registry_basic_functionality(self):
        """Test build_registry() creates registry from graph definition."""
        # Create mock graph definition with realistic node structure
        mock_node1 = Mock()
        mock_node1.context = {"description": "Test node 1 description"}
        mock_node1.description = "Node 1"
        mock_node1.prompt = "Test prompt for node 1"
        mock_node1.agent_type = "default"
        mock_node1.inputs = ["input1"]
        mock_node1.output = "output1"
        
        mock_node2 = Mock()
        mock_node2.context = {"description": "Test node 2 description"}
        mock_node2.description = "Node 2"
        mock_node2.prompt = "Test prompt for node 2"
        mock_node2.agent_type = "llm"
        mock_node2.inputs = ["input2"]
        mock_node2.output = "output2"
        
        graph_def = {
            "node1": mock_node1,
            "node2": mock_node2
        }
        
        # Execute test
        result = self.service.build_registry(graph_def, "test_graph")
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 2)
        self.assertIn("node1", result)
        self.assertIn("node2", result)
        
        # Verify node1 metadata
        node1_metadata = result["node1"]
        self.assertEqual(node1_metadata["description"], "Test node 1 description")
        self.assertEqual(node1_metadata["prompt"], "Test prompt for node 1")
        self.assertEqual(node1_metadata["type"], "default")
        self.assertEqual(node1_metadata["input_fields"], ["input1"])
        self.assertEqual(node1_metadata["output_field"], "output1")
        
        # Verify node2 metadata
        node2_metadata = result["node2"]
        self.assertEqual(node2_metadata["description"], "Test node 2 description")
        self.assertEqual(node2_metadata["prompt"], "Test prompt for node 2")
        self.assertEqual(node2_metadata["type"], "llm")
        self.assertEqual(node2_metadata["input_fields"], ["input2"])
        self.assertEqual(node2_metadata["output_field"], "output2")
        
        # Verify caching
        self.assertIn("test_graph", self.service._registry_cache)
        self.assertEqual(self.service._registry_cache["test_graph"], result)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        info_calls = [call for call in logger_calls if call[0] == "info"]
        
        self.assertTrue(any("[NodeRegistry] Building registry for graph: test_graph" in call[1] 
                          for call in debug_calls))
        self.assertTrue(any("Built registry with 2 nodes for: test_graph" in call[1] 
                          for call in info_calls))
    
    def test_build_registry_with_cache_hit(self):
        """Test build_registry() returns cached result when available."""
        # Create test graph definition
        mock_node = Mock()
        mock_node.context = {}
        mock_node.description = "Test node"
        mock_node.prompt = "Test prompt"
        mock_node.agent_type = "default"
        mock_node.inputs = []
        mock_node.output = ""
        
        graph_def = {"node1": mock_node}
        
        # First call builds registry
        result1 = self.service.build_registry(graph_def, "cached_graph")
        
        # Reset logger calls to check cache behavior
        self.mock_logger.calls.clear()
        
        # Second call should use cache
        result2 = self.service.build_registry(graph_def, "cached_graph")
        
        # Verify same result returned
        self.assertEqual(result1, result2)
        
        # Verify cache was used (should see debug message about using cached registry)
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Using cached registry for: cached_graph" in call[1] 
                          for call in debug_calls))
    
    def test_build_registry_force_rebuild(self):
        """Test build_registry() with force_rebuild=True bypasses cache."""
        # Create test graph definition
        mock_node = Mock()
        mock_node.context = {}
        mock_node.description = "Test node"
        mock_node.prompt = "Test prompt"
        mock_node.agent_type = "default"
        mock_node.inputs = []
        mock_node.output = ""
        
        graph_def = {"node1": mock_node}
        
        # First call builds registry
        result1 = self.service.build_registry(graph_def, "force_graph")
        
        # Reset logger calls
        self.mock_logger.calls.clear()
        
        # Second call with force_rebuild should not use cache
        result2 = self.service.build_registry(graph_def, "force_graph", force_rebuild=True)
        
        # Verify results are equal (same graph definition)
        self.assertEqual(result1, result2)
        
        # Verify cache was bypassed (should see building message, not cache message)
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Building registry for graph: force_graph" in call[1] 
                          for call in debug_calls))
        self.assertFalse(any("Using cached registry" in call[1] 
                           for call in debug_calls))
    
    def test_build_registry_empty_graph_definition(self):
        """Test build_registry() handles empty graph definition."""
        # Execute with empty graph definition
        result = self.service.build_registry({}, "empty_graph")
        
        # Verify empty result
        self.assertEqual(result, {})
        
        # Verify warning logged
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("Empty graph definition provided" in call[1] 
                          for call in warning_calls))
    
    def test_build_registry_none_graph_definition(self):
        """Test build_registry() handles None graph definition."""
        # Execute with None graph definition
        result = self.service.build_registry(None, "none_graph")
        
        # Verify empty result
        self.assertEqual(result, {})
        
        # Verify warning logged
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("Empty graph definition provided" in call[1] 
                          for call in warning_calls))
    
    def test_build_registry_node_processing_error(self):
        """Test build_registry() handles node processing errors gracefully."""
        # Create mock node that will cause processing error
        mock_node = Mock()
        # Remove context attribute to make node.context access fail
        del mock_node.context
        mock_node.description = "Test description"
        mock_node.prompt = "Test prompt"
        mock_node.agent_type = "test_type"
        mock_node.inputs = []
        mock_node.output = ""
        
        graph_def = {"error_node": mock_node}
        
        # Execute test
        result = self.service.build_registry(graph_def, "error_graph")
        
        # Verify error node gets minimal metadata
        self.assertIn("error_node", result)
        error_metadata = result["error_node"]
        self.assertIn("Error processing node:", error_metadata["description"])
        self.assertIn("context", error_metadata["description"])  # Should mention the missing attribute
        self.assertEqual(error_metadata["prompt"], "")
        self.assertEqual(error_metadata["type"], "test_type")  # agent_type should still be accessible
        
        # Verify error was logged
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("Failed to process node 'error_node'" in call[1] 
                          for call in error_calls))
        self.assertTrue(any("context" in call[1] 
                          for call in error_calls))
    
    def test_build_registry_with_fallback_description(self):
        """Test build_registry() creates fallback description from prompt."""
        # Create node with no description but has prompt
        mock_node = Mock()
        mock_node.context = {}  # No description in context
        mock_node.description = ""  # No description field
        mock_node.prompt = "Test prompt for fallback"
        mock_node.agent_type = "default"
        mock_node.inputs = []
        mock_node.output = ""
        
        graph_def = {"fallback_node": mock_node}
        
        # Execute test
        result = self.service.build_registry(graph_def)
        
        # Verify fallback description was created from prompt
        node_metadata = result["fallback_node"]
        self.assertEqual(node_metadata["description"], "Test prompt for fallback")
        
        # Verify the core business logic: no description -> use prompt
        self.assertNotEqual(node_metadata["description"], "")  # Should not be empty
        self.assertIn("Test prompt", node_metadata["description"])  # Should contain prompt content
    
    def test_prepare_for_assembly_success(self):
        """Test prepare_for_assembly() delegates to build_registry and logs summary."""
        # Create test graph definition
        mock_node = Mock()
        mock_node.context = {"description": "Assembly test node"}
        mock_node.description = "Assembly Node"
        mock_node.prompt = "Assembly prompt"
        mock_node.agent_type = "default"
        mock_node.inputs = ["input1"]
        mock_node.output = "output1"
        
        graph_def = {"assembly_node": mock_node}
        
        # Execute test
        result = self.service.prepare_for_assembly(graph_def, "assembly_graph")
        
        # Verify result is same as build_registry
        expected_result = self.service.build_registry(graph_def, "assembly_graph")
        self.assertEqual(result, expected_result)
        
        # Verify preparation logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        info_calls = [call for call in logger_calls if call[0] == "info"]
        
        self.assertTrue(any("Preparing registry for assembly: assembly_graph" in call[1] 
                          for call in debug_calls))
        self.assertTrue(any("Registry prepared for assembly:" in call[1] 
                          for call in info_calls))
        self.assertTrue(any("Total nodes: 1" in call[1] 
                          for call in info_calls))
    
    def test_verify_pre_compilation_injection_with_orchestrators(self):
        """Test verify_pre_compilation_injection() with successful injection."""
        # Create mock assembler with injection stats
        mock_assembler = Mock()
        mock_assembler.get_injection_summary.return_value = {
            "orchestrators_found": 2,
            "orchestrators_injected": 2,
            "injection_failures": 0
        }
        
        # Execute test
        result = self.service.verify_pre_compilation_injection(mock_assembler)
        
        # Verify result structure
        self.assertTrue(result["has_orchestrators"])
        self.assertTrue(result["all_injected"])
        self.assertEqual(result["success_rate"], 1.0)
        self.assertIn("stats", result)
        
        # Verify success logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any("✅ All 2 orchestrators successfully injected" in call[1] 
                          for call in info_calls))
    
    def test_verify_pre_compilation_injection_with_failures(self):
        """Test verify_pre_compilation_injection() with injection failures."""
        # Create mock assembler with injection failures
        mock_assembler = Mock()
        mock_assembler.get_injection_summary.return_value = {
            "orchestrators_found": 3,
            "orchestrators_injected": 2,
            "injection_failures": 1
        }
        
        # Execute test
        result = self.service.verify_pre_compilation_injection(mock_assembler)
        
        # Verify result structure
        self.assertTrue(result["has_orchestrators"])
        self.assertFalse(result["all_injected"])
        self.assertAlmostEqual(result["success_rate"], 2/3, places=2)
        
        # Verify warning logging
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("⚠️ Only 2/3 orchestrators injected" in call[1] 
                          for call in warning_calls))
    
    def test_verify_pre_compilation_injection_no_orchestrators(self):
        """Test verify_pre_compilation_injection() with no orchestrators."""
        # Create mock assembler with no orchestrators
        mock_assembler = Mock()
        mock_assembler.get_injection_summary.return_value = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0
        }
        
        # Execute test
        result = self.service.verify_pre_compilation_injection(mock_assembler)
        
        # Verify result structure
        self.assertFalse(result["has_orchestrators"])
        self.assertTrue(result["all_injected"])  # True because no failures
        self.assertEqual(result["success_rate"], 0)
        
        # Verify debug logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("No orchestrators found in graph" in call[1] 
                          for call in debug_calls))
    
    def test_get_registry_summary_populated_registry(self):
        """Test get_registry_summary() with populated registry."""
        # Create test registry
        test_registry = {
            "node1": {
                "description": "Node 1 description",
                "prompt": "Node 1 prompt",
                "type": "default",
                "input_fields": ["input1"],
                "output_field": "output1"
            },
            "node2": {
                "description": "Node 2 description",
                "prompt": "Node 2 prompt",
                "type": "llm",
                "input_fields": ["input2"],
                "output_field": "output2"
            },
            "node3": {
                "description": "",  # No description
                "prompt": "Node 3 prompt",
                "type": "default",
                "input_fields": [],
                "output_field": ""
            }
        }
        
        # Execute test
        result = self.service.get_registry_summary(test_registry)
        
        # Verify summary structure
        self.assertEqual(result["total_nodes"], 3)
        self.assertEqual(result["has_descriptions"], 2)  # Only node1 and node2 have descriptions
        self.assertIn("node_types", result)
        self.assertIn("node_names", result)
        
        # Verify node types summary
        node_types = result["node_types"]
        self.assertEqual(node_types["default"], 2)
        self.assertEqual(node_types["llm"], 1)
        
        # Verify node names
        self.assertEqual(set(result["node_names"]), {"node1", "node2", "node3"})
    
    def test_get_registry_summary_empty_registry(self):
        """Test get_registry_summary() with empty registry."""
        # Execute test with empty registry
        result = self.service.get_registry_summary({})
        
        # Verify empty summary
        self.assertEqual(result["total_nodes"], 0)
        self.assertEqual(result["has_descriptions"], 0)
        self.assertEqual(result["node_types"], {})
        self.assertEqual(result["node_names"], [])
    
    def test_get_registry_summary_none_registry(self):
        """Test get_registry_summary() with None registry."""
        # Execute test with None registry
        result = self.service.get_registry_summary(None)
        
        # Verify empty summary
        self.assertEqual(result["total_nodes"], 0)
        self.assertEqual(result["has_descriptions"], 0)
        self.assertEqual(result["node_types"], {})
        self.assertEqual(result["node_names"], [])
    
    def test_clear_cache_specific_graph(self):
        """Test clear_cache() for specific graph."""
        # Build registries for multiple graphs
        mock_node = Mock()
        mock_node.context = {}
        mock_node.description = "Test"
        mock_node.prompt = "Test"
        mock_node.agent_type = "default"
        mock_node.inputs = []
        mock_node.output = ""
        
        graph_def = {"node1": mock_node}
        
        self.service.build_registry(graph_def, "graph1")
        self.service.build_registry(graph_def, "graph2")
        
        # Verify both are cached
        self.assertIn("graph1", self.service._registry_cache)
        self.assertIn("graph2", self.service._registry_cache)
        
        # Clear specific graph
        self.service.clear_cache("graph1")
        
        # Verify only graph1 was cleared
        self.assertNotIn("graph1", self.service._registry_cache)
        self.assertIn("graph2", self.service._registry_cache)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Cleared cache for graph: graph1" in call[1] 
                          for call in debug_calls))
    
    def test_clear_cache_all_graphs(self):
        """Test clear_cache() for all graphs."""
        # Build registries for multiple graphs
        mock_node = Mock()
        mock_node.context = {}
        mock_node.description = "Test"
        mock_node.prompt = "Test"
        mock_node.agent_type = "default"
        mock_node.inputs = []
        mock_node.output = ""
        
        graph_def = {"node1": mock_node}
        
        self.service.build_registry(graph_def, "graph1")
        self.service.build_registry(graph_def, "graph2")
        
        # Verify both are cached
        self.assertIn("graph1", self.service._registry_cache)
        self.assertIn("graph2", self.service._registry_cache)
        
        # Clear all caches
        self.service.clear_cache()
        
        # Verify all were cleared
        self.assertEqual(len(self.service._registry_cache), 0)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Cleared all registry caches" in call[1] 
                          for call in debug_calls))
    
    def test_clear_cache_nonexistent_graph(self):
        """Test clear_cache() for nonexistent graph."""
        # Clear cache for graph that doesn't exist
        self.service.clear_cache("nonexistent_graph")
        
        # Should not raise error and cache should remain empty
        self.assertEqual(len(self.service._registry_cache), 0)
    
    # =============================================================================
    # 3. Context Parsing Tests
    # =============================================================================
    
    def test_parse_node_context_dict_input(self):
        """Test _parse_node_context() with dictionary input."""
        context_dict = {"description": "Test description", "category": "test"}
        
        result = self.service._parse_node_context(context_dict)
        
        self.assertEqual(result, context_dict)
    
    def test_parse_node_context_json_string(self):
        """Test _parse_node_context() with JSON string input."""
        context_json = '{"description": "JSON description", "type": "json_test"}'
        
        result = self.service._parse_node_context(context_json)
        
        self.assertEqual(result["description"], "JSON description")
        self.assertEqual(result["type"], "json_test")
    
    def test_parse_node_context_key_value_colon(self):
        """Test _parse_node_context() with colon-separated key-value pairs."""
        context_str = "description:Test description,category:test,priority:high"
        
        result = self.service._parse_node_context(context_str)
        
        self.assertEqual(result["description"], "Test description")
        self.assertEqual(result["category"], "test")
        self.assertEqual(result["priority"], "high")
    
    def test_parse_node_context_key_value_equals(self):
        """Test _parse_node_context() with equals-separated key-value pairs."""
        context_str = "description=Test description,category=test,priority=high"
        
        result = self.service._parse_node_context(context_str)
        
        self.assertEqual(result["description"], "Test description")
        self.assertEqual(result["category"], "test")
        self.assertEqual(result["priority"], "high")
    
    def test_parse_node_context_plain_string(self):
        """Test _parse_node_context() with plain string input."""
        context_str = "This is just a plain description string"
        
        result = self.service._parse_node_context(context_str)
        
        self.assertEqual(result["description"], context_str)
    
    def test_parse_node_context_empty_string(self):
        """Test _parse_node_context() with empty string input."""
        result = self.service._parse_node_context("")
        
        self.assertEqual(result, {})
    
    def test_parse_node_context_none_input(self):
        """Test _parse_node_context() with None input."""
        result = self.service._parse_node_context(None)
        
        self.assertEqual(result, {})
    
    def test_parse_node_context_invalid_json(self):
        """Test _parse_node_context() with invalid JSON string."""
        context_str = '{"description": "Invalid JSON", "missing_quote: "value"}'
        
        result = self.service._parse_node_context(context_str)
        
        # Should fall back to using whole string as description
        self.assertEqual(result["description"], context_str)
        
        # Verify warning logging for malformed JSON
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("Malformed JSON in context" in call[1] 
                          for call in warning_calls))
    
    def test_parse_node_context_unknown_type(self):
        """Test _parse_node_context() with unknown input type."""
        context_obj = Mock()  # Some other object type
        
        result = self.service._parse_node_context(context_obj)
        
        self.assertEqual(result, {})
        
        # Verify debug logging for unknown type
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Unknown context type" in call[1] 
                          for call in debug_calls))
    
    # =============================================================================
    # 4. Error Handling and Edge Case Tests
    # =============================================================================
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies gracefully."""
        # Test missing logging service
        with self.assertRaises(AttributeError) as context:
            NodeRegistryService(
                configuration=self.mock_app_config_service,
                logging_service=None
            )
        self.assertIn("'NoneType' object has no attribute 'get_class_logger'", str(context.exception))
        
        # Test missing configuration service
        service_with_none_config = NodeRegistryService(
            configuration=None,
            logging_service=self.mock_logging_service
        )
        # Verify service was created but configuration is None
        self.assertIsNone(service_with_none_config.configuration)
        self.assertIsNotNone(service_with_none_config.logger)
    
    def test_service_initialization_with_completely_missing_arguments(self):
        """Test service handles completely missing arguments (TypeError)."""
        # Test with no arguments at all
        with self.assertRaises(TypeError) as context:
            NodeRegistryService()
        
        # Should mention missing required positional arguments
        error_msg = str(context.exception)
        self.assertTrue(
            "missing" in error_msg and "required" in error_msg,
            f"Expected error about missing required arguments, got: {error_msg}"
        )
    
    def test_build_registry_without_graph_name_no_caching(self):
        """Test build_registry() without graph_name doesn't cache result."""
        # Create test graph definition
        mock_node = Mock()
        mock_node.context = {}
        mock_node.description = "Test"
        mock_node.prompt = "Test"
        mock_node.agent_type = "default"
        mock_node.inputs = []
        mock_node.output = ""
        
        graph_def = {"node1": mock_node}
        
        # Execute without graph_name
        result = self.service.build_registry(graph_def)
        
        # Verify result is returned but not cached
        self.assertIsInstance(result, dict)
        self.assertIn("node1", result)
        
        # Cache should only contain "unnamed" key, not specific graph name
        self.assertEqual(len(self.service._registry_cache), 0)
    
    def test_node_metadata_to_dict(self):
        """Test NodeMetadata.to_dict() functionality."""
        # Create NodeMetadata instance
        metadata = NodeMetadata(
            description="Test description",
            prompt="Test prompt",
            type="test_type",
            input_fields=["input1", "input2"],
            output_field="output"
        )
        
        # Convert to dict
        result = metadata.to_dict()
        
        # Verify structure
        expected = {
            "description": "Test description",
            "prompt": "Test prompt",
            "type": "test_type",
            "input_fields": ["input1", "input2"],
            "output_field": "output"
        }
        self.assertEqual(result, expected)
    
    def test_node_metadata_to_dict_with_defaults(self):
        """Test NodeMetadata.to_dict() with default values."""
        # Create NodeMetadata with minimal data
        metadata = NodeMetadata(
            description="Test description",
            prompt="Test prompt",
            type="test_type"
        )
        
        # Convert to dict
        result = metadata.to_dict()
        
        # Verify defaults are applied
        self.assertEqual(result["input_fields"], [])
        self.assertEqual(result["output_field"], "")
    
    def test_prepare_for_assembly_with_none_graph_name(self):
        """Test prepare_for_assembly() with None graph_name."""
        # Create test graph definition
        mock_node = Mock()
        mock_node.context = {}
        mock_node.description = "Test"
        mock_node.prompt = "Test"
        mock_node.agent_type = "default"
        mock_node.inputs = []
        mock_node.output = ""
        
        graph_def = {"node1": mock_node}
        
        # Execute with None graph_name
        result = self.service.prepare_for_assembly(graph_def, None)
        
        # Should still work
        self.assertIsInstance(result, dict)
        self.assertIn("node1", result)
        
        # Verify logging mentions None
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Preparing registry for assembly: None" in call[1] 
                          for call in debug_calls))
    
    def test_verify_pre_compilation_injection_assembler_method_error(self):
        """Test verify_pre_compilation_injection() handles assembler method errors."""
        # Create mock assembler that raises exception
        mock_assembler = Mock()
        mock_assembler.get_injection_summary.side_effect = AttributeError("Mock assembler error")
        
        # Execute test
        with self.assertRaises(AttributeError) as context:
            self.service.verify_pre_compilation_injection(mock_assembler)
        
        # Verify exception is propagated
        self.assertIn("Mock assembler error", str(context.exception))


if __name__ == '__main__':
    unittest.main()
