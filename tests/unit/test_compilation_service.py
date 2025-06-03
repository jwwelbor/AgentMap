"""
Unit tests for CompilationService.

These tests mock all dependencies and focus on testing the service logic
in isolation, following the existing test patterns in AgentMap.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, call
import time

from agentmap.services.compilation_service import (
    CompilationService, 
    CompilationOptions, 
    CompilationResult
)
from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.models.graph import Graph
from agentmap.models.node import Node
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService,
    MockNodeRegistryService
)


class TestCompilationService(unittest.TestCase):
    """Unit tests for CompilationService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use migration-safe mock implementations
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        self.mock_node_registry_service = MockNodeRegistryService()
        
        # Create mock graph builder service
        self.mock_graph_builder = GraphBuilderService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_config_service
        )
        
        # Create service instance with mocked dependencies
        self.service = CompilationService(
            graph_builder_service=self.mock_graph_builder,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_config_service,
            node_registry_service=self.mock_node_registry_service
        )
    
    def test_service_initialization(self):
        """Test that service initializes correctly with dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.graph_builder, self.mock_graph_builder)
        self.assertEqual(self.service.logger.name, "CompilationService")
        self.assertEqual(self.service.config, self.mock_config_service)
        self.assertEqual(self.service.node_registry, self.mock_node_registry_service)
        
        # Verify initialization log message
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[CompilationService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
    
    def create_test_graph(self) -> Graph:
        """Helper method to create a test graph."""
        graph = Graph(name="TestGraph")
        node = Node(
            name="TestNode",
            agent_type="LLM",
            inputs=["input"],
            output="output",
            prompt="Test prompt"
        )
        node.add_edge("default", "EndNode")
        graph.nodes["TestNode"] = node
        
        end_node = Node(name="EndNode", agent_type="Output")
        graph.nodes["EndNode"] = end_node
        
        graph.entry_point = "TestNode"
        return graph
    
    def test_compile_graph_success(self):
        """Test successful graph compilation."""
        # Create test graph and mock dependencies
        test_graph = self.create_test_graph()
        
        # Mock the graph builder to return our test graph
        with patch.object(self.mock_graph_builder, 'build_from_csv', return_value=test_graph), \
             patch('agentmap.services.compilation_service.time') as mock_time, \
             patch('agentmap.services.compilation_service.os.makedirs'), \
             patch('builtins.open', mock_open()):
            
            mock_time.time.side_effect = [1000.0, 1002.5]  # Start and end times
            
            # Test compilation
            options = CompilationOptions(state_schema="dict", include_source=True)
            result = self.service.compile_graph("TestGraph", options)
            
            # Verify result
            self.assertTrue(result.success)
            self.assertEqual(result.graph_name, "TestGraph")
            self.assertEqual(result.compilation_time, 2.5)
            self.assertIsNone(result.error)
            self.assertTrue(str(result.output_path).endswith("TestGraph.pkl"))
            self.assertTrue(str(result.source_path).endswith("TestGraph.src"))
        
    def test_compile_graph_failure(self):
        """Test graph compilation failure handling."""
        # Make graph builder fail
        with patch.object(self.mock_graph_builder, 'build_from_csv', side_effect=Exception("Test error")), \
             patch('agentmap.services.compilation_service.time') as mock_time:
            
            mock_time.time.side_effect = [1000.0, 1001.0]  # Start and end times
            
            # Test compilation
            result = self.service.compile_graph("TestGraph")
            
            # Verify result
            self.assertFalse(result.success)
            self.assertEqual(result.graph_name, "TestGraph")
            self.assertEqual(result.compilation_time, 1.0)
            self.assertIn("Test error", result.error)
            self.assertEqual(result.output_path, Path(""))
    
    def test_compile_graph_with_default_options(self):
        """Test compilation with default options."""
        test_graph = self.create_test_graph()
        
        with patch.object(self.mock_graph_builder, 'build_from_csv', return_value=test_graph), \
             patch('agentmap.services.compilation_service.time') as mock_time, \
             patch('agentmap.services.compilation_service.os.makedirs'), \
             patch('builtins.open', mock_open()):
            
            mock_time.time.side_effect = [1000.0, 1001.0]
            
            # Test with no options (should use defaults)
            result = self.service.compile_graph("TestGraph")
            
            # Verify default options were used
            self.assertTrue(result.success)
            # CSV path should come from config
            self.assertEqual(result.graph_name, "TestGraph")
    
    def test_compile_all_graphs_success(self):
        """Test successful compilation of all graphs."""
        # Setup mock graphs
        graph1 = Graph(name="Graph1")
        graph2 = Graph(name="Graph2")
        
        with patch.object(self.mock_graph_builder, 'build_all_from_csv', return_value={"Graph1": graph1, "Graph2": graph2}), \
             patch.object(self.service, 'compile_graph') as mock_compile:
            
            mock_compile.side_effect = [
                CompilationResult("Graph1", Path("/test/Graph1.pkl"), None, True, 1.0),
                CompilationResult("Graph2", Path("/test/Graph2.pkl"), None, True, 1.0)
            ]
            
            # Test compilation
            results = self.service.compile_all_graphs()
            
            # Verify results
            self.assertEqual(len(results), 2)
            self.assertTrue(all(r.success for r in results))
            
            # Verify individual compilations were called
            self.assertEqual(mock_compile.call_count, 2)
    
    def test_compile_all_graphs_with_failures(self):
        """Test compilation of all graphs with some failures."""
        # Setup mock graphs
        graph1 = Graph(name="Graph1")
        graph2 = Graph(name="Graph2")
        
        with patch.object(self.mock_graph_builder, 'build_all_from_csv', return_value={"Graph1": graph1, "Graph2": graph2}), \
             patch.object(self.service, 'compile_graph') as mock_compile:
            
            mock_compile.side_effect = [
                CompilationResult("Graph1", Path("/test/Graph1.pkl"), None, True, 1.0),
                CompilationResult("Graph2", Path(""), None, False, 1.0, error="Compilation failed")
            ]
            
            # Test compilation
            results = self.service.compile_all_graphs()
            
            # Verify results
            self.assertEqual(len(results), 2)
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            self.assertEqual(len(successful), 1)
            self.assertEqual(len(failed), 1)
    
    def test_compile_all_graphs_batch_failure(self):
        """Test batch compilation failure."""
        # Make graph builder fail
        with patch.object(self.mock_graph_builder, 'build_all_from_csv', side_effect=Exception("CSV parse error")):
            
            # Test compilation
            results = self.service.compile_all_graphs()
            
            # Verify single failure result
            self.assertEqual(len(results), 1)
            result = results[0]
            self.assertFalse(result.success)
            self.assertEqual(result.graph_name, "<batch_compilation>")
            self.assertIn("CSV parse error", result.error)
    
    @patch.object(Path, 'exists')
    @patch.object(Path, 'stat')
    def test_auto_compile_if_needed_current(self, mock_stat, mock_exists):
        """Test auto-compile when compilation is current."""
        # Setup mocks to indicate compilation is current
        mock_exists.return_value = True
        mock_stat.return_value.st_mtime = 2000.0  # Compiled file newer than CSV
        
        with patch.object(self.service, '_is_compilation_current', return_value=True):
            result = self.service.auto_compile_if_needed("TestGraph", Path("/test/graph.csv"))
            
            # Should return None (no compilation needed)
            self.assertIsNone(result)
            
            # Should log that no compilation is needed
            logger_calls = self.service.logger.calls
            self.assertTrue(any(call[1] == "[CompilationService] Graph TestGraph is current, no compilation needed" 
                              for call in logger_calls if call[0] == "debug"))
    
    def test_auto_compile_if_needed_outdated(self):
        """Test auto-compile when compilation is outdated."""
        with patch.object(self.service, '_is_compilation_current', return_value=False), \
             patch.object(self.service, 'compile_graph') as mock_compile:
            
            mock_result = CompilationResult("TestGraph", Path("/test/TestGraph.pkl"), None, True, 1.0)
            mock_compile.return_value = mock_result
            
            result = self.service.auto_compile_if_needed("TestGraph", Path("/test/graph.csv"))
            
            # Should return compilation result
            self.assertEqual(result, mock_result)
            
            # Should log auto-compilation
            logger_calls = self.service.logger.calls
            self.assertTrue(any(call[1] == "[CompilationService] Auto-compiling outdated graph: TestGraph" 
                              for call in logger_calls if call[0] == "info"))
    
    def test_validate_before_compilation(self):
        """Test CSV validation before compilation."""
        csv_path = Path("/test/graph.csv")
        expected_errors = ["Error 1", "Error 2"]
        
        with patch.object(self.mock_graph_builder, 'validate_csv_before_building', return_value=expected_errors):
            result = self.service.validate_before_compilation(csv_path)
            
            self.assertEqual(result, expected_errors)
    
    @patch.object(Path, 'exists')
    @patch.object(Path, 'stat')
    def test_get_compilation_status_compiled(self, mock_stat, mock_exists):
        """Test getting compilation status for compiled graph."""
        # Setup mocks - output path exists (compiled file is present)
        mock_exists.return_value = True
        mock_stat.return_value.st_mtime = 2000.0
        
        with patch.object(self.service, '_is_compilation_current', return_value=True):
            status = self.service.get_compilation_status("TestGraph")
            
            # Verify status information
            self.assertEqual(status["graph_name"], "TestGraph")
            self.assertTrue(status["compiled"])
            self.assertTrue(status["current"])
            self.assertEqual(status["compiled_time"], 2000.0)
    
    @patch.object(Path, 'exists')
    def test_get_compilation_status_not_compiled(self, mock_exists):
        """Test getting compilation status for non-compiled graph."""
        mock_exists.return_value = False
        
        status = self.service.get_compilation_status("TestGraph")
        
        # Verify status information
        self.assertEqual(status["graph_name"], "TestGraph")
        self.assertFalse(status["compiled"])
        self.assertFalse(status["current"])
    
    def test_convert_graph_to_old_format(self):
        """Test conversion of Graph domain model to old format."""
        graph = self.create_test_graph()
        
        old_format = self.service._convert_graph_to_old_format(graph)
        
        # Verify conversion
        self.assertIn("TestNode", old_format)
        self.assertIn("EndNode", old_format)
        
        test_node = old_format["TestNode"]
        self.assertEqual(test_node.name, "TestNode")
        self.assertEqual(test_node.agent_type, "LLM")
        self.assertEqual(test_node.inputs, ["input"])
        self.assertEqual(test_node.output, "output")
        self.assertEqual(test_node.prompt, "Test prompt")
        self.assertEqual(test_node.edges, {"default": "EndNode"})
    
    @patch.object(Path, 'exists')
    @patch.object(Path, 'stat')
    def test_is_compilation_current_true(self, mock_stat, mock_exists):
        """Test compilation currency check when current."""
        mock_exists.return_value = True
        # Compiled file newer than CSV
        mock_stat.side_effect = lambda: type('MockStat', (), {'st_mtime': 2000.0})()
        
        with patch.object(Path, 'stat') as mock_path_stat:
            mock_path_stat.side_effect = [
                type('MockStat', (), {'st_mtime': 2000.0})(),  # Compiled file
                type('MockStat', (), {'st_mtime': 1000.0})()   # CSV file
            ]
            
            result = self.service._is_compilation_current("TestGraph", Path("/test/graph.csv"))
            self.assertTrue(result)
    
    @patch.object(Path, 'exists')
    @patch.object(Path, 'stat')
    def test_is_compilation_current_false(self, mock_stat, mock_exists):
        """Test compilation currency check when outdated."""
        mock_exists.return_value = True
        
        with patch.object(Path, 'stat') as mock_path_stat:
            mock_path_stat.side_effect = [
                type('MockStat', (), {'st_mtime': 1000.0})(),  # Compiled file
                type('MockStat', (), {'st_mtime': 2000.0})()   # CSV file (newer)
            ]
            
            result = self.service._is_compilation_current("TestGraph", Path("/test/graph.csv"))
            self.assertFalse(result)
    
    @patch.object(Path, 'exists')
    def test_is_compilation_current_no_compiled_file(self, mock_exists):
        """Test compilation currency check when no compiled file exists."""
        mock_exists.return_value = False
        
        result = self.service._is_compilation_current("TestGraph", Path("/test/graph.csv"))
        self.assertFalse(result)
    
    def test_get_output_path(self):
        """Test getting output path for compiled graph."""
        path = self.service._get_output_path("TestGraph")
        
        expected = Path("/test/compiled") / "TestGraph.pkl"
        self.assertEqual(path, expected)
    
    def test_get_output_path_custom_dir(self):
        """Test getting output path with custom directory."""
        custom_dir = Path("/custom/output")
        path = self.service._get_output_path("TestGraph", custom_dir)
        
        expected = custom_dir / "TestGraph.pkl"
        self.assertEqual(path, expected)
    
    def test_get_source_path(self):
        """Test getting source path for compiled graph."""
        path = self.service._get_source_path("TestGraph")
        
        expected = Path("/test/compiled") / "TestGraph.src"
        self.assertEqual(path, expected)
    
    def test_get_service_info(self):
        """Test getting service information."""
        info = self.service.get_service_info()
        
        # Verify service information
        self.assertEqual(info["service"], "CompilationService")
        self.assertTrue(info["graph_builder_available"])
        self.assertTrue(info["config_available"])
        self.assertTrue(info["node_registry_available"])
        self.assertEqual(info["compiled_graphs_path"], str(Path("/test/compiled")))
        self.assertEqual(info["csv_path"], str(Path("/test/graph.csv")))
        self.assertEqual(info["functions_path"], str(Path("/test/functions")))
    
    def test_compilation_options_defaults(self):
        """Test CompilationOptions default values."""
        options = CompilationOptions()
        
        self.assertIsNone(options.output_dir)
        self.assertEqual(options.state_schema, "dict")
        self.assertFalse(options.force_recompile)
        self.assertTrue(options.include_source)
        self.assertIsNone(options.csv_path)
    
    def test_compilation_options_custom(self):
        """Test CompilationOptions with custom values."""
        options = CompilationOptions(
            output_dir=Path("/custom"),
            state_schema="pydantic:MyModel",
            force_recompile=True,
            include_source=False,
            csv_path=Path("/custom/graph.csv")
        )
        
        self.assertEqual(options.output_dir, Path("/custom"))
        self.assertEqual(options.state_schema, "pydantic:MyModel")
        self.assertTrue(options.force_recompile)
        self.assertFalse(options.include_source)
        self.assertEqual(options.csv_path, Path("/custom/graph.csv"))
    
    def test_compilation_result_success(self):
        """Test CompilationResult for successful compilation."""
        result = CompilationResult(
            graph_name="TestGraph",
            output_path=Path("/test/TestGraph.pkl"),
            source_path=Path("/test/TestGraph.src"),
            success=True,
            compilation_time=2.5,
            registry_stats={"nodes": 3}
        )
        
        self.assertEqual(result.graph_name, "TestGraph")
        self.assertTrue(result.success)
        self.assertEqual(result.compilation_time, 2.5)
        self.assertIsNone(result.error)
        self.assertEqual(result.registry_stats["nodes"], 3)
    
    def test_compilation_result_failure(self):
        """Test CompilationResult for failed compilation."""
        result = CompilationResult(
            graph_name="TestGraph",
            output_path=Path(""),
            source_path=None,
            success=False,
            compilation_time=1.0,
            error="Compilation failed"
        )
        
        self.assertEqual(result.graph_name, "TestGraph")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Compilation failed")
        self.assertIsNone(result.registry_stats)


if __name__ == '__main__':
    unittest.main()
