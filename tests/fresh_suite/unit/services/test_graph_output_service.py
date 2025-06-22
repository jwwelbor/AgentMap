"""
Unit tests for GraphOutputService.

Tests validate the consolidated graph output functionality including Python code 
generation, source templates, debug information, and documentation export.
This service replaces the duplicate GraphExportService and GraphSerializationService.
"""

import unittest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from typing import Dict, Any

from agentmap.services.graph_output_service import GraphOutputService
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphOutputService(unittest.TestCase):
    """Comprehensive unit tests for consolidated GraphOutputService."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        self.mock_function_resolution_service = Mock()
        self.mock_compilation_service = Mock()
        
        # Configure mock app config service with expected paths
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
        self.mock_app_config_service.get_csv_path.return_value = Path("graphs/workflow.csv")
        self.mock_app_config_service.get_custom_agents_path.return_value = Path("agents")
        self.mock_app_config_service.get_functions_path.return_value = Path("functions")
        
        # Configure function resolution service
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        
        # Initialize GraphOutputService with mocked dependencies
        self.service = GraphOutputService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            function_resolution_service=self.mock_function_resolution_service,
            compilation_service=self.mock_compilation_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
        
        # Create sample graph definition for testing
        self.sample_graph_def = self._create_sample_graph_definition()
    
    def _create_sample_graph_definition(self) -> Dict[str, Any]:
        """Create a sample graph definition for testing."""
        # Create mock nodes that match the expected structure
        mock_node1 = Mock()
        mock_node1.name = "input_processor"
        mock_node1.context = {"input_fields": ["raw_data"], "output_field": "processed_data"}
        mock_node1.agent_type = "processor"
        mock_node1.inputs = ["raw_data"]
        mock_node1.output = "processed_data"
        mock_node1.prompt = "Process the incoming raw data"
        mock_node1.description = "Data processing node"
        mock_node1.edges = {"default": "output_formatter"}
        
        mock_node2 = Mock()
        mock_node2.name = "output_formatter"
        mock_node2.context = {"input_fields": ["processed_data"], "output_field": "formatted_output"}
        mock_node2.agent_type = "formatter"
        mock_node2.inputs = ["processed_data"]
        mock_node2.output = "formatted_output"
        mock_node2.prompt = "Format the processed data for output"
        mock_node2.description = "Output formatting node"
        mock_node2.edges = {}
        
        return {
            "input_processor": mock_node1,
            "output_formatter": mock_node2
        }
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.compiled_graphs_path, Path("compiled"))
        self.assertEqual(self.service.csv_path, Path("graphs/workflow.csv"))
        self.assertEqual(self.service.custom_agents_path, Path("agents"))
        self.assertEqual(self.service.functions_path, Path("functions"))
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.function_resolution, self.mock_function_resolution_service)
        self.assertEqual(self.service.compilation_service, self.mock_compilation_service)
        
        # Verify logger is configured correctly
        self.assertEqual(self.service.logger.name, 'GraphOutputService')
        
        # Verify get_class_logger was called during initialization
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == '[GraphOutputService] Initialized' 
                          for call in logger_calls if call[0] == 'info'))
    
    def test_service_initialization_without_compilation_service(self):
        """Test service initialization with optional CompilationService as None."""
        service = GraphOutputService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            function_resolution_service=self.mock_function_resolution_service,
            compilation_service=None
        )
        
        self.assertIsNone(service.compilation_service)
        self.assertIsNotNone(service.logger)
    
    def test_service_info_method(self):
        """Test get_service_info() method returns correct information."""
        info = self.service.get_service_info()
        
        # Verify service information structure
        self.assertIsInstance(info, dict)
        self.assertEqual(info["service"], "GraphOutputService")
        self.assertTrue(info["compilation_service_available"])
        self.assertTrue(info["function_resolution_available"])
        self.assertEqual(info["compiled_graphs_path"], str(Path("compiled")))
        self.assertEqual(info["csv_path"], str(Path("graphs/workflow.csv")))
        self.assertEqual(info["functions_path"], str(Path("functions")))
        self.assertEqual(info["supported_formats"], ["python", "source", "src", "debug", "documentation"])
        self.assertEqual(info["note"], "For graph persistence, use GraphBundleService")
        self.assertIn("dill_available", info)
    
    # =============================================================================
    # 2. Export Interface Tests (Consolidated)
    # =============================================================================
    
    def test_export_graph_python_format(self):
        """Test export_graph() with Python format."""
        with patch.object(self.service, 'export_as_python', return_value=Path("test.py")) as mock_export:
            result = self.service.export_graph("test_graph", "python", "/output/path", "dict")
            
            mock_export.assert_called_once_with("test_graph", "/output/path", "dict")
            self.assertEqual(result, Path("test.py"))
    
    def test_export_graph_source_format(self):
        """Test export_graph() with source format."""
        with patch.object(self.service, 'export_as_source', return_value=Path("test.src")) as mock_export:
            result = self.service.export_graph("test_graph", "source", "/output/path", "dict")
            
            mock_export.assert_called_once_with("test_graph", "/output/path", "dict")
            self.assertEqual(result, Path("test.src"))
    
    def test_export_graph_src_format(self):
        """Test export_graph() with src format (alternative source format)."""
        with patch.object(self.service, 'export_as_source', return_value=Path("test.src")) as mock_export:
            result = self.service.export_graph("test_graph", "src")
            
            mock_export.assert_called_once_with("test_graph", None, "dict")
            self.assertEqual(result, Path("test.src"))
    
    def test_export_graph_debug_format(self):
        """Test export_graph() with debug format."""
        with patch.object(self.service, 'export_as_debug', return_value=Path("test.debug")) as mock_export:
            result = self.service.export_graph("test_graph", "debug")
            
            mock_export.assert_called_once_with("test_graph", None, "dict")
            self.assertEqual(result, Path("test.debug"))
    
    def test_export_graph_unsupported_format(self):
        """Test export_graph() raises error for unsupported format."""
        with self.assertRaises(ValueError) as context:
            self.service.export_graph("test_graph", "pickle")
        
        error_msg = str(context.exception)
        self.assertIn("Unsupported export format: pickle", error_msg)
        self.assertIn("Supported formats: python, source, src, debug", error_msg)
        self.assertIn("For persistence, use GraphBundleService", error_msg)
    
    def test_export_graph_default_parameters(self):
        """Test export_graph() with default parameters."""
        with patch.object(self.service, 'export_as_python', return_value=Path("test.py")) as mock_export:
            result = self.service.export_graph("test_graph")
            
            # Should use default format "python", output_path None, state_schema "dict"
            mock_export.assert_called_once_with("test_graph", None, "dict")
            self.assertEqual(result, Path("test.py"))
    
    # =============================================================================
    # 3. Python Export Tests
    # =============================================================================
    
    def test_export_as_python_successful(self):
        """Test export_as_python() successful export."""
        # Mock graph definition retrieval
        with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
             patch.object(self.service, '_generate_python_code', return_value=["# Generated code"]), \
             patch.object(self.service, '_get_output_path', return_value=Path("test.py")), \
             patch('builtins.open', mock_open()) as mock_file:
            
            result = self.service.export_as_python("test_graph", "/output", "dict")
            
            # Verify method calls
            self.service._get_graph_definition.assert_called_once_with("test_graph")
            self.service._generate_python_code.assert_called_once_with("test_graph", self.sample_graph_def, "dict")
            self.service._get_output_path.assert_called_once_with("test_graph", "/output", "py")
            
            # Verify file writing
            mock_file.assert_called_once_with(Path("test.py"), "w")
            mock_file().write.assert_called_once_with("# Generated code")
            
            # Verify result and logging
            self.assertEqual(result, Path("test.py"))
            logger_calls = self.mock_logger.calls
            success_calls = [call for call in logger_calls if call[0] == 'info']
            self.assertTrue(any("✅ Exported test_graph to" in call[1] for call in success_calls))
    
    def test_export_as_python_debug_logging(self):
        """Test export_as_python() includes debug logging."""
        with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
             patch.object(self.service, '_generate_python_code', return_value=["code"]), \
             patch.object(self.service, '_get_output_path', return_value=Path("test.py")), \
             patch('builtins.open', mock_open()):
            
            self.service.export_as_python("test_graph", None, "dict")
            
            # Verify debug logging
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == 'debug']
            self.assertTrue(any("Exporting 'test_graph' as Python code" in call[1] 
                              for call in debug_calls))
    
    # =============================================================================
    # 4. Source Export Tests
    # =============================================================================
    
    def test_export_as_source_successful(self):
        """Test export_as_source() successful export."""
        # Configure mock agent class resolution
        with patch('agentmap.services.graph_output_service.get_agent_class') as mock_get_agent_class:
            mock_agent_class = Mock()
            mock_agent_class.__name__ = "DefaultAgent"
            mock_get_agent_class.return_value = mock_agent_class
            
            # Mock other dependencies
            with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
                 patch.object(self.service, '_get_output_path', return_value=Path("test.src")), \
                 patch('builtins.open', mock_open()) as mock_file:
                
                result = self.service.export_as_source("test_graph", "/output", "dict")
                
                # Verify method calls
                self.service._get_graph_definition.assert_called_once_with("test_graph")
                self.service._get_output_path.assert_called_once_with("test_graph", "/output", "src")
                
                # Verify file writing with expected content
                mock_file.assert_called_once_with(Path("test.src"), "w")
                written_content = mock_file().write.call_args[0][0]
                
                # Verify content includes StateGraph initialization
                self.assertIn("builder = StateGraph(dict)", written_content)
                self.assertIn('builder.add_node("input_processor", DefaultAgent())', written_content)
                self.assertIn('builder.add_node("output_formatter", DefaultAgent())', written_content)
                self.assertIn('builder.set_entry_point("input_processor")', written_content)
                self.assertIn("graph = builder.compile()", written_content)
                
                self.assertEqual(result, Path("test.src"))
    
    def test_export_as_source_custom_state_schema(self):
        """Test export_as_source() with custom state schema."""
        with patch('agentmap.services.graph_output_service.get_agent_class') as mock_get_agent_class:
            mock_agent_class = Mock()
            mock_agent_class.__name__ = "ProcessorAgent"
            mock_get_agent_class.return_value = mock_agent_class
            
            with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
                 patch.object(self.service, '_get_output_path', return_value=Path("test.src")), \
                 patch('builtins.open', mock_open()) as mock_file:
                
                result = self.service.export_as_source("test_graph", None, "CustomSchema")
                
                # Verify custom state schema is used
                written_content = mock_file().write.call_args[0][0]
                self.assertIn("builder = StateGraph(CustomSchema)", written_content)
    
    # =============================================================================
    # 5. Debug Export Tests (New Functionality)
    # =============================================================================
    
    def test_export_as_debug_successful(self):
        """Test export_as_debug() generates comprehensive debug information."""
        with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
             patch.object(self.service, '_generate_python_code', return_value=["# Python code"]), \
             patch.object(self.service, '_get_output_path', return_value=Path("test.debug")), \
             patch('builtins.open', mock_open()) as mock_file:
            
            result = self.service.export_as_debug("test_graph", "/output", "dict")
            
            # Verify method calls
            self.service._get_graph_definition.assert_called_once_with("test_graph")
            self.service._get_output_path.assert_called_once_with("test_graph", "/output", "debug")
            
            # Verify file writing
            mock_file.assert_called_once_with(Path("test.debug"), "w")
            written_content = mock_file().write.call_args[0][0]
            
            # Verify debug content structure
            self.assertIn("# Debug Export for Graph: test_graph", written_content)
            self.assertIn("# State Schema: dict", written_content)
            self.assertIn("# Generated by GraphOutputService", written_content)
            self.assertIn("# === GRAPH STRUCTURE ===", written_content)
            self.assertIn("# Node: input_processor", written_content)
            self.assertIn("#   Agent Type: processor", written_content)
            self.assertIn("#   Inputs: ['raw_data']", written_content)
            self.assertIn("#   Output: processed_data", written_content)
            self.assertIn("# === EXECUTABLE CODE ===", written_content)
            self.assertIn("# Python code", written_content)
            
            self.assertEqual(result, Path("test.debug"))
    
    def test_export_as_debug_truncates_long_prompts(self):
        """Test export_as_debug() truncates long prompts appropriately."""
        # Create node with long prompt
        long_prompt_node = Mock()
        long_prompt_node.name = "long_prompt_node"
        long_prompt_node.agent_type = "test"
        long_prompt_node.inputs = ["input"]
        long_prompt_node.output = "output"
        long_prompt_node.prompt = "A" * 150  # 150 character prompt
        long_prompt_node.edges = {}
        
        graph_def_with_long_prompt = {"long_prompt_node": long_prompt_node}
        
        with patch.object(self.service, '_get_graph_definition', return_value=graph_def_with_long_prompt), \
             patch.object(self.service, '_generate_python_code', return_value=["# Code"]), \
             patch.object(self.service, '_get_output_path', return_value=Path("test.debug")), \
             patch('builtins.open', mock_open()) as mock_file:
            
            self.service.export_as_debug("test_graph", None, "dict")
            
            written_content = mock_file().write.call_args[0][0]
            
            # Verify prompt is truncated to 100 characters + "..."
            self.assertIn("A" * 100 + "...", written_content)
            self.assertNotIn("A" * 150, written_content)
    
    # =============================================================================
    # 6. Documentation Export Tests (New Functionality)
    # =============================================================================
    
    def test_export_as_documentation_markdown(self):
        """Test export_as_documentation() generates markdown documentation."""
        with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
             patch.object(self.service, '_get_output_path', return_value=Path("test.md")), \
             patch('builtins.open', mock_open()) as mock_file:
            
            result = self.service.export_as_documentation("test_graph", "/output", "markdown")
            
            # Verify file writing
            mock_file.assert_called_once_with(Path("test.md"), "w")
            written_content = mock_file().write.call_args[0][0]
            
            # Verify markdown structure
            self.assertIn("# Graph: test_graph", written_content)
            self.assertIn("## Overview", written_content)
            self.assertIn("## Nodes", written_content)
            self.assertIn("### input_processor", written_content)
            self.assertIn("- **Agent Type**: processor", written_content)
            self.assertIn("- **Inputs**: raw_data", written_content)
            self.assertIn("- **Output**: processed_data", written_content)
            self.assertIn("**Prompt:**", written_content)
            self.assertIn("Process the incoming raw data", written_content)
            
            self.assertEqual(result, Path("test.md"))
    
    def test_export_as_documentation_html(self):
        """Test export_as_documentation() generates HTML documentation."""
        with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
             patch.object(self.service, '_get_output_path', return_value=Path("test.html")), \
             patch('builtins.open', mock_open()) as mock_file:
            
            result = self.service.export_as_documentation("test_graph", "/output", "html")
            
            # Verify file writing
            mock_file.assert_called_once_with(Path("test.html"), "w")
            written_content = mock_file().write.call_args[0][0]
            
            # Verify HTML structure
            self.assertIn("<!DOCTYPE html>", written_content)
            self.assertIn("<title>Graph: test_graph</title>", written_content)
            self.assertIn("<h1>Graph: test_graph</h1>", written_content)
            self.assertIn("<h3>input_processor</h3>", written_content)
            self.assertIn("<strong>Agent Type:</strong> processor", written_content)
            self.assertIn("Process the incoming raw data", written_content)
            
            self.assertEqual(result, Path("test.html"))
    
    def test_export_as_documentation_unsupported_format(self):
        """Test export_as_documentation() raises error for unsupported format."""
        with self.assertRaises(ValueError) as context:
            self.service.export_as_documentation("test_graph", None, "pdf")
        
        error_msg = str(context.exception)
        self.assertIn("Unsupported documentation format: pdf", error_msg)
    
    # =============================================================================
    # 7. Graph Definition Retrieval Tests
    # =============================================================================
    
    def test_get_graph_definition_with_compilation_service(self):
        """Test _get_graph_definition() uses CompilationService correctly."""
        # Mock compilation result
        mock_compilation_result = Mock()
        mock_compilation_result.success = True
        mock_compilation_result.error = None
        self.mock_compilation_service.compile_graph.return_value = mock_compilation_result
        
        # Mock graph domain model
        mock_graph_domain_model = Mock()
        mock_graph_domain_model.nodes = self.sample_graph_def
        self.mock_compilation_service.graph_definition.build_from_csv.return_value = mock_graph_domain_model
        
        # Execute test
        with patch.object(self.service, '_convert_graph_to_old_format', return_value=self.sample_graph_def) as mock_convert:
            result = self.service._get_graph_definition("test_graph")
            
            # Verify compilation service was called correctly
            self.mock_compilation_service.compile_graph.assert_called_once()
            args = self.mock_compilation_service.compile_graph.call_args[0]
            self.assertEqual(args[0], "test_graph")
            
            # Verify CompilationOptions
            options = self.mock_compilation_service.compile_graph.call_args[0][1]
            self.assertEqual(options.csv_path, self.service.csv_path)
            self.assertFalse(options.include_source)
            
            # Verify graph definition service was called
            self.mock_compilation_service.graph_definition.build_from_csv.assert_called_once_with(
                self.service.csv_path, "test_graph"
            )
            
            # Verify conversion to old format
            mock_convert.assert_called_once_with(mock_graph_domain_model)
            self.assertEqual(result, self.sample_graph_def)
    
    def test_get_graph_definition_compilation_failure(self):
        """Test _get_graph_definition() handles compilation failure."""
        # Mock compilation failure
        mock_compilation_result = Mock()
        mock_compilation_result.success = False
        mock_compilation_result.error = "Compilation failed"
        self.mock_compilation_service.compile_graph.return_value = mock_compilation_result
        
        # Execute test and verify exception
        with self.assertRaises(ValueError) as context:
            self.service._get_graph_definition("test_graph")
        
        error_msg = str(context.exception)
        self.assertIn("Failed to compile graph for export 'test_graph'", error_msg)
        self.assertIn("Compilation failed", error_msg)
    
    def test_get_graph_definition_no_compilation_service(self):
        """Test _get_graph_definition() raises error when CompilationService unavailable."""
        # Create service without compilation service
        service = GraphOutputService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            function_resolution_service=self.mock_function_resolution_service,
            compilation_service=None
        )
        
        # Execute test and verify exception
        with self.assertRaises(ValueError) as context:
            service._get_graph_definition("test_graph")
        
        error_msg = str(context.exception)
        self.assertIn("CompilationService not available", error_msg)
        self.assertIn("cannot export graph", error_msg)
    
    # =============================================================================
    # 8. Path Resolution Tests
    # =============================================================================
    
    def test_get_output_path_no_override(self):
        """Test _get_output_path() with no output path override."""
        result = self.service._get_output_path("test_graph", None, "py")
        
        expected_path = Path("compiled/test_graph.py")
        self.assertEqual(result, expected_path)
    
    def test_get_output_path_with_file_override(self):
        """Test _get_output_path() with file path override."""
        # Use temp directory instead of absolute path
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            override_path = os.path.join(temp_dir, "custom", "test.py")
            result = self.service._get_output_path("test_graph", override_path, "py")
            
            expected_path = Path(override_path)
            self.assertEqual(result, expected_path)
            # Verify parent directory was created
            self.assertTrue(result.parent.exists())
    
    def test_get_output_path_with_directory_override(self):
        """Test _get_output_path() with directory path override."""
        # Use temp directory instead of absolute path
        import tempfile  
        with tempfile.TemporaryDirectory() as temp_dir:
            override_dir = os.path.join(temp_dir, "custom", "directory")
            
            # Create the directory first to simulate it exists
            os.makedirs(override_dir, exist_ok=True)
            
            with patch('pathlib.Path.is_dir', return_value=True):
                result = self.service._get_output_path("test_graph", override_dir, "py")
            
            expected_path = Path(override_dir) / "test_graph.py"
            self.assertEqual(result, expected_path)
    
    def test_get_output_path_creates_parent_directories(self):
        """Test _get_output_path() creates parent directories."""
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            result = self.service._get_output_path("test_graph", None, "py")
            
            # Verify mkdir was called with correct parameters
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            self.assertEqual(result, Path("compiled/test_graph.py"))
    
    # =============================================================================
    # 9. Graph Conversion Tests
    # =============================================================================
    
    def test_convert_graph_to_old_format(self):
        """Test _convert_graph_to_old_format() converts Graph domain model correctly."""
        # Create mock Graph domain model
        mock_graph = Mock()
        mock_node1 = Mock()
        mock_node1.name = "node1"
        mock_node1.context = {"input_fields": ["input1"]}
        mock_node1.agent_type = "default"
        mock_node1.inputs = ["input1"]
        mock_node1.output = "output1"
        mock_node1.prompt = "Test prompt"
        mock_node1.description = "Test description"
        mock_node1.edges = {"default": "node2"}
        
        mock_graph.nodes = {"node1": mock_node1}
        
        # Execute conversion
        result = self.service._convert_graph_to_old_format(mock_graph)
        
        # Verify conversion creates old format structure
        self.assertIn("node1", result)
        converted_node = result["node1"]
        
        self.assertEqual(converted_node.name, "node1")
        self.assertEqual(converted_node.context, {"input_fields": ["input1"]})
        self.assertEqual(converted_node.agent_type, "default")
        self.assertEqual(converted_node.inputs, ["input1"])
        self.assertEqual(converted_node.output, "output1")
        self.assertEqual(converted_node.prompt, "Test prompt")
        self.assertEqual(converted_node.description, "Test description")
        self.assertEqual(converted_node.edges, {"default": "node2"})
    
    # =============================================================================
    # 10. Python Code Generation Tests
    # =============================================================================
    
    def test_generate_python_code_basic(self):
        """Test _generate_python_code() generates correct Python code."""
        # Configure function resolution to return no functions
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        
        with patch('agentmap.services.graph_output_service.get_agent_class') as mock_get_agent_class:
            mock_agent_class = Mock()
            mock_agent_class.__name__ = "DefaultAgent"
            mock_get_agent_class.return_value = mock_agent_class
            
            result = self.service._generate_python_code("test_graph", self.sample_graph_def, "dict")
            
            # Verify code structure
            code = "\n".join(result)
            
            # Check imports
            self.assertIn("from langgraph.graph import StateGraph", code)
            self.assertIn("from agentmap.agents.builtins.openai_agent import OpenAIAgent", code)
            
            # Check graph construction
            self.assertIn("# Graph: test_graph", code)
            self.assertIn("builder = StateGraph(dict)", code)
            self.assertIn('builder.add_node("input_processor", DefaultAgent(', code)
            self.assertIn('builder.add_node("output_formatter", DefaultAgent(', code)
            self.assertIn('builder.set_entry_point("input_processor")', code)
            self.assertIn("graph = builder.compile()", code)
    
    def test_generate_python_code_with_functions(self):
        """Test _generate_python_code() includes function imports."""
        # Configure function resolution to return functions
        def mock_extract_func_ref(target):
            if target == "output_formatter":
                return "custom_formatter"
            return None
        
        self.mock_function_resolution_service.extract_func_ref.side_effect = mock_extract_func_ref
        
        with patch('agentmap.services.graph_output_service.get_agent_class') as mock_get_agent_class:
            mock_agent_class = Mock()
            mock_agent_class.__name__ = "DefaultAgent"
            mock_get_agent_class.return_value = mock_agent_class
            
            result = self.service._generate_python_code("test_graph", self.sample_graph_def, "dict")
            
            code = "\n".join(result)
            
            # Check function import
            self.assertIn("from agentmap.functions.custom_formatter import custom_formatter", code)
    
    # =============================================================================
    # 11. Error Handling Tests
    # =============================================================================
    
    def test_service_handles_missing_dependencies_gracefully(self):
        """Test service behavior with missing optional dependencies."""
        # Test with None compilation service
        service = GraphOutputService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            function_resolution_service=self.mock_function_resolution_service,
            compilation_service=None
        )
        
        info = service.get_service_info()
        self.assertFalse(info["compilation_service_available"])
    
    def test_export_methods_handle_file_permissions_errors(self):
        """Test export methods handle file permission errors gracefully."""
        with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
             patch.object(self.service, '_generate_python_code', return_value=["code"]), \
             patch.object(self.service, '_get_output_path', return_value=Path("readonly.py")), \
             patch('builtins.open', side_effect=PermissionError("Permission denied")):
            
            # Should propagate the permission error
            with self.assertRaises(PermissionError):
                self.service.export_as_python("test_graph", None, "dict")
    
    def test_service_logs_operation_progress(self):
        """Test that service properly logs operation progress and results."""
        # Test logging during successful operations
        with patch.object(self.service, '_get_graph_definition', return_value=self.sample_graph_def), \
             patch.object(self.service, '_generate_python_code', return_value=["code"]), \
             patch.object(self.service, '_get_output_path', return_value=Path("test.py")), \
             patch('builtins.open', mock_open()):
            
            self.service.export_as_python("test_graph", None, "dict")
            
            # Verify comprehensive logging
            logger_calls = self.mock_logger.calls
            
            # Check for operation start logging
            debug_calls = [call for call in logger_calls if call[0] == 'debug']
            self.assertTrue(any("Exporting 'test_graph' as Python code" in call[1] 
                              for call in debug_calls))
            
            # Check for success logging
            info_calls = [call for call in logger_calls if call[0] == 'info']
            self.assertTrue(any("✅ Exported test_graph to" in call[1] 
                              for call in info_calls))
    
    # =============================================================================
    # 12. State Schema Resolution Tests
    # =============================================================================
    
    def test_resolve_state_schema_dict(self):
        """Test _resolve_state_schema_class() with dict schema."""
        result = self.service._resolve_state_schema_class("dict")
        self.assertEqual(result, dict)
    
    def test_resolve_state_schema_pydantic(self):
        """Test _resolve_state_schema_class() with pydantic schema."""
        with patch('builtins.__import__') as mock_import:
            mock_module = Mock()
            mock_class = Mock()
            mock_module.TestModel = mock_class
            mock_import.return_value = mock_module
            
            result = self.service._resolve_state_schema_class("pydantic:TestModel")
            
            # Verify import was attempted
            mock_import.assert_called_once_with("agentmap.schemas.testmodel", fromlist=["TestModel"])
            self.assertEqual(result, mock_class)
    
    def test_resolve_state_schema_pydantic_import_error(self):
        """Test _resolve_state_schema_class() handles pydantic import errors."""
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            result = self.service._resolve_state_schema_class("pydantic:NonExistentModel")
            
            # Should fallback to dict
            self.assertEqual(result, dict)
            
            # Verify warning was logged
            logger_calls = self.mock_logger.calls
            warning_calls = [call for call in logger_calls if call[0] == 'warning']
            self.assertTrue(any("Failed to import 'NonExistentModel'" in call[1] 
                              for call in warning_calls))


if __name__ == '__main__':
    unittest.main()
