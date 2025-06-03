"""
Integration tests for CompilationService.

These tests use real dependencies and real CSV files to verify the service
works correctly in realistic compilation scenarios.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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


class TestCompilationServiceIntegration(unittest.TestCase):
    """Integration tests for CompilationService with real dependencies."""
    
    def setUp(self):
        """Set up test fixtures with real and minimal mock dependencies."""
        # Create migration-safe mock dependencies
        self.logging_service = MockLoggingService()
        self.config_service = MockAppConfigService()
        self.node_registry_service = MockNodeRegistryService()
        
        # Create real graph builder service
        self.graph_builder_service = GraphBuilderService(
            logging_service=self.logging_service,
            app_config_service=self.config_service
        )
        
        # Create compilation service
        self.service = CompilationService(
            graph_builder_service=self.graph_builder_service,
            logging_service=self.logging_service,
            app_config_service=self.config_service,
            node_registry_service=self.node_registry_service
        )
        
        # Setup temp directories
        self.temp_dir = tempfile.mkdtemp()
        self.compiled_dir = Path(self.temp_dir) / "compiled"
        self.compiled_dir.mkdir()
        
        # Configure mock config service
        self.config_service.compiled_graphs_path = self.compiled_dir
        self.config_service.functions_path = Path(self.temp_dir) / "functions"
        self.config_service.custom_agents_path = Path(self.temp_dir) / "agents"
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def create_test_csv_file(self, content: str) -> Path:
        """Helper method to create temporary CSV file with content."""
        csv_path = Path(self.temp_dir) / "test_graph.csv"
        with open(csv_path, 'w') as f:
            f.write(content)
        return csv_path
    
    def create_simple_workflow_csv(self) -> Path:
        """Create a simple workflow CSV for testing."""
        csv_content = """GraphName,Node,AgentType,Input_Fields,Output_Field,Prompt,Description,Edge,Success_Next,Failure_Next
SimpleWorkflow,StartNode,Input,user_input,processed_input,Collect input,Start node,ProcessNode,,
SimpleWorkflow,ProcessNode,LLM,processed_input,result,Process the input,Processing node,,SuccessNode,FailureNode
SimpleWorkflow,SuccessNode,Output,result,final_output,Success output,Success node,,,
SimpleWorkflow,FailureNode,Output,result,error_output,Error output,Failure node,,,
"""
        return self.create_test_csv_file(csv_content)
    
    def create_multi_graph_csv(self) -> Path:
        """Create a CSV with multiple graphs for testing."""
        csv_content = """GraphName,Node,AgentType,Edge
Workflow1,Start1,Input,End1
Workflow1,End1,Output,
Workflow2,Start2,LLM,End2
Workflow2,End2,Output,
Workflow3,Start3,Processing,End3
Workflow3,End3,Output,
"""
        return self.create_test_csv_file(csv_content)
    
    def test_compile_single_graph_integration(self):
        """Test complete integration of single graph compilation."""
        # Setup CSV
        csv_path = self.create_simple_workflow_csv()
        self.config_service.csv_path = csv_path
        
        # Test compilation with migration-safe mocks
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "csv,content"
            mock_open.return_value.__enter__.return_value.write = Mock()
            
            # Test compilation
            options = CompilationOptions(include_source=True)
            result = self.service.compile_graph("SimpleWorkflow", options)
            
            # Verify result
            self.assertTrue(result.success, f"Compilation failed: {result.error}")
            self.assertEqual(result.graph_name, "SimpleWorkflow")
            self.assertIsNone(result.error)
            
            # Verify output paths
            expected_output = self.compiled_dir / "SimpleWorkflow.pkl"
            expected_source = self.compiled_dir / "SimpleWorkflow.src"
            self.assertEqual(result.output_path, expected_output)
            self.assertEqual(result.source_path, expected_source)
    
    def test_compile_all_graphs_integration(self):
        """Test compilation of all graphs in CSV."""
        # Setup CSV with multiple graphs
        csv_path = self.create_multi_graph_csv()
        self.config_service.csv_path = csv_path
        
        # Test compilation with migration-safe mocks
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "csv,content"
            mock_open.return_value.__enter__.return_value.write = Mock()
            
            # Test compilation
            options = CompilationOptions(include_source=False)
            results = self.service.compile_all_graphs(options)
            
            # Verify results
            self.assertEqual(len(results), 3)
            graph_names = [r.graph_name for r in results]
            self.assertIn("Workflow1", graph_names)
            self.assertIn("Workflow2", graph_names)
            self.assertIn("Workflow3", graph_names)
            
            # All should be successful
            successful_results = [r for r in results if r.success]
            self.assertEqual(len(successful_results), 3)
    
    def test_csv_validation_integration(self):
        """Test CSV validation integration with real GraphBuilderService."""
        # Test with valid CSV
        valid_csv = self.create_simple_workflow_csv()
        errors = self.service.validate_before_compilation(valid_csv)
        self.assertEqual(len(errors), 0)
        
        # Test with invalid CSV
        invalid_csv_content = """WrongColumn,AnotherWrong
Value1,Value2
"""
        invalid_csv = self.create_test_csv_file(invalid_csv_content)
        errors = self.service.validate_before_compilation(invalid_csv)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("Missing required columns" in error for error in errors))
    
    def test_compilation_options_integration(self):
        """Test different compilation options."""
        csv_path = self.create_simple_workflow_csv()
        
        with patch('agentmap.services.compilation_service.create_graph_builder_with_registry') as mock_create, \
             patch('agentmap.services.compilation_service.GraphBundle') as mock_bundle_class, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_create.return_value = (Mock(), ["# Generated code"])
            mock_bundle_class.return_value = Mock()
            mock_open.return_value.__enter__.return_value.read.return_value = "csv,content"
            mock_open.return_value.__enter__.return_value.write = Mock()
            
            # Test custom output directory
            custom_output = Path(self.temp_dir) / "custom_compiled"
            custom_output.mkdir()
            
            options = CompilationOptions(
                output_dir=custom_output,
                state_schema="pydantic:CustomModel",
                include_source=True,
                csv_path=csv_path
            )
            
            result = self.service.compile_graph("SimpleWorkflow", options)
            
            # Verify custom output directory was used
            self.assertTrue(str(result.output_path).startswith(str(custom_output)))
            
            # Verify state schema was passed to compilation
            call_args = mock_create.call_args
            self.assertEqual(call_args[0][2], "pydantic:CustomModel")  # state_schema parameter
    
    def test_auto_compile_integration(self):
        """Test auto-compilation integration."""
        csv_path = self.create_simple_workflow_csv()
        
        # First call should trigger compilation (no existing file)
        with patch('agentmap.services.compilation_service.create_graph_builder_with_registry') as mock_create, \
             patch('agentmap.services.compilation_service.GraphBundle') as mock_bundle_class, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_create.return_value = (Mock(), ["# Generated code"])
            mock_bundle_class.return_value = Mock()
            mock_open.return_value.__enter__.return_value.read.return_value = "csv,content"
            mock_open.return_value.__enter__.return_value.write = Mock()
            
            result1 = self.service.auto_compile_if_needed("SimpleWorkflow", csv_path)
            
            # Should have compiled
            self.assertIsNotNone(result1)
            self.assertTrue(result1.success)
            
            # Create a fake compiled file to simulate existing compilation
            output_path = self.compiled_dir / "SimpleWorkflow.pkl"
            output_path.touch()
            
            # Make the compiled file newer than CSV
            import time
            time.sleep(0.1)
            output_path.touch()
            
            # Second call should not trigger compilation (file is current)
            result2 = self.service.auto_compile_if_needed("SimpleWorkflow", csv_path)
            
            # Should not have compiled
            self.assertIsNone(result2)
    
    def test_compilation_status_integration(self):
        """Test compilation status checking."""
        csv_path = self.create_simple_workflow_csv()
        
        # Initially not compiled
        status = self.service.get_compilation_status("SimpleWorkflow", csv_path)
        self.assertFalse(status["compiled"])
        self.assertFalse(status["current"])
        
        # Create a compiled file
        output_path = self.compiled_dir / "SimpleWorkflow.pkl"
        output_path.touch()
        
        # Now should show as compiled
        status = self.service.get_compilation_status("SimpleWorkflow", csv_path)
        self.assertTrue(status["compiled"])
        # Current status depends on file timestamps
    
    def test_error_handling_integration(self):
        """Test error handling in integration scenarios."""
        # Test with non-existent CSV
        non_existent_csv = Path(self.temp_dir) / "non_existent.csv"
        result = self.service.compile_graph("TestGraph", CompilationOptions(csv_path=non_existent_csv))
        
        self.assertFalse(result.success)
        self.assertIn("not found", result.error.lower())
        
        # Test with invalid graph name
        valid_csv = self.create_simple_workflow_csv()
        result = self.service.compile_graph("NonExistentGraph", CompilationOptions(csv_path=valid_csv))
        
        self.assertFalse(result.success)
        self.assertIn("not found", result.error.lower())
    
    def test_real_csv_parsing_integration(self):
        """Test integration with real CSV parsing scenarios."""
        # Test complex CSV with conditional routing
        complex_csv_content = """GraphName,Node,AgentType,Input_Fields,Output_Field,Prompt,Description,Success_Next,Failure_Next
ComplexWorkflow,InputNode,Input,user_data,raw_input,Get user input,Input node,ValidationNode,ErrorNode
ComplexWorkflow,ValidationNode,Validation,raw_input,validated_data,Validate input,Validation node,ProcessingNode,ErrorNode
ComplexWorkflow,ProcessingNode,LLM,validated_data,processed_result,Process data,Processing node,OutputNode,ErrorNode
ComplexWorkflow,OutputNode,Output,processed_result,final_output,Final output,Output node,,
ComplexWorkflow,ErrorNode,Output,error_info,error_output,Error handling,Error node,,
"""
        
        csv_path = self.create_test_csv_file(complex_csv_content)
        
        with patch('agentmap.services.compilation_service.create_graph_builder_with_registry') as mock_create, \
             patch('agentmap.services.compilation_service.GraphBundle') as mock_bundle_class, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_create.return_value = (Mock(), ["# Complex workflow code"])
            mock_bundle_class.return_value = Mock()
            mock_open.return_value.__enter__.return_value.read.return_value = complex_csv_content
            mock_open.return_value.__enter__.return_value.write = Mock()
            
            result = self.service.compile_graph("ComplexWorkflow", CompilationOptions(csv_path=csv_path))
            
            # Should successfully compile complex workflow
            self.assertTrue(result.success, f"Complex workflow compilation failed: {result.error}")
            
            # Verify the graph was properly converted for compilation
            call_args = mock_create.call_args
            graph_def = call_args[0][0]  # First argument is graph_def
            
            # Should have all nodes
            expected_nodes = ["InputNode", "ValidationNode", "ProcessingNode", "OutputNode", "ErrorNode"]
            for node_name in expected_nodes:
                self.assertIn(node_name, graph_def)
    
    def test_node_registry_integration(self):
        """Test integration with node registry service."""
        csv_path = self.create_simple_workflow_csv()
        
        # Use patch to mock the specific method for this test
        with patch.object(self.node_registry_service, 'prepare_for_assembly') as mock_prepare:
            mock_prepare.return_value = {
                "StartNode": {"type": "orchestrator", "config": {"llm_model": "gpt-4"}},
                "ProcessNode": {"type": "orchestrator", "config": {"llm_model": "gpt-3.5"}},
                "SuccessNode": {"type": "default", "config": {}},
                "FailureNode": {"type": "default", "config": {}}
            }
            
            with patch('agentmap.services.compilation_service.create_graph_builder_with_registry') as mock_create, \
                 patch('agentmap.services.compilation_service.GraphBundle') as mock_bundle_class, \
                 patch('builtins.open', create=True) as mock_open:
                
                mock_create.return_value = (Mock(), ["# Code with registry"])
                mock_bundle_class.return_value = Mock()
                mock_open.return_value.__enter__.return_value.read.return_value = "csv,content"
                mock_open.return_value.__enter__.return_value.write = Mock()
                
                result = self.service.compile_graph("SimpleWorkflow", CompilationOptions(csv_path=csv_path))
                
                # Verify node registry was prepared
                mock_prepare.assert_called_once()
                
                # Verify registry was passed to compilation
                call_args = mock_create.call_args
                node_registry = call_args[0][1]  # Second argument is node_registry
                self.assertIn("StartNode", node_registry)
                self.assertIn("ProcessNode", node_registry)
    
    def test_service_info_integration(self):
        """Test service information integration."""
        info = self.service.get_service_info()
        
        # Verify all components are available
        self.assertEqual(info["service"], "CompilationService")
        self.assertTrue(info["graph_builder_available"])
        self.assertTrue(info["config_available"])
        self.assertTrue(info["node_registry_available"])
        
        # Verify paths are correctly configured
        self.assertEqual(info["compiled_graphs_path"], str(self.compiled_dir))
    
    def test_compilation_time_tracking(self):
        """Test that compilation time is properly tracked."""
        csv_path = self.create_simple_workflow_csv()
        
        with patch('agentmap.services.compilation_service.create_graph_builder_with_registry') as mock_create, \
             patch('agentmap.services.compilation_service.GraphBundle') as mock_bundle_class, \
             patch('builtins.open', create=True) as mock_open, \
             patch('agentmap.services.compilation_service.time') as mock_time:
            
            # Mock time to control compilation timing
            mock_time.time.side_effect = [1000.0, 1002.5]  # 2.5 second compilation
            
            mock_create.return_value = (Mock(), ["# Timed code"])
            mock_bundle_class.return_value = Mock()
            mock_open.return_value.__enter__.return_value.read.return_value = "csv,content"
            mock_open.return_value.__enter__.return_value.write = Mock()
            
            result = self.service.compile_graph("SimpleWorkflow", CompilationOptions(csv_path=csv_path))
            
            # Verify timing was tracked
            self.assertEqual(result.compilation_time, 2.5)
            self.assertTrue(result.success)
    
    def test_source_generation_integration(self):
        """Test source file generation integration."""
        csv_path = self.create_simple_workflow_csv()
        
        with patch('agentmap.services.compilation_service.create_graph_builder_with_registry') as mock_create, \
             patch('agentmap.services.compilation_service.GraphBundle') as mock_bundle_class, \
             patch('builtins.open', create=True) as mock_open:
            
            test_src_lines = [
                "from langgraph.graph import StateGraph",
                "builder = StateGraph(dict)",
                "# Generated workflow code"
            ]
            mock_create.return_value = (Mock(), test_src_lines)
            mock_bundle_class.return_value = Mock()
            mock_open.return_value.__enter__.return_value.read.return_value = "csv,content"
            
            # Mock file writing
            mock_write = Mock()
            mock_open.return_value.__enter__.return_value.write = mock_write
            
            # Test with source generation enabled
            options = CompilationOptions(include_source=True, csv_path=csv_path)
            result = self.service.compile_graph("SimpleWorkflow", options)
            
            # Verify source file was written
            expected_source_content = "\n".join(test_src_lines)
            mock_write.assert_called_with(expected_source_content)
            
            # Verify source path is set
            self.assertIsNotNone(result.source_path)
            self.assertTrue(str(result.source_path).endswith(".src"))
            
            # Test with source generation disabled
            options = CompilationOptions(include_source=False, csv_path=csv_path)
            result = self.service.compile_graph("SimpleWorkflow", options)
            
            # Source path should be None
            self.assertIsNone(result.source_path)


if __name__ == '__main__':
    unittest.main()
