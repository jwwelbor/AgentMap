"""
Compilation Workflow Integration Tests for AgentMap.

Integration tests for the complete graph compilation workflow including:
- Graph Definition → Graph Bundle → File I/O → Compilation Results
- Real file operations, serialization, and compilation service coordination
- Entry point detection validation
- Service coordination verification
"""
import unittest
import pickle
import time
from pathlib import Path
from typing import Dict, Any

from agentmap.services.compilation_service import CompilationService, CompilationOptions
from agentmap.services.graph_definition_service import GraphDefinitionService
from agentmap.services.graph_bundle_service import GraphBundleService
from agentmap.models.graph_bundle import GraphBundle
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest


class TestAgent:
    """Simple test agent that can be pickled for testing."""
    def __init__(self, name, prompt):
        self.name = name
        self.prompt = prompt
    
    def run(self, state):
        # Simple test implementation
        return {"response": f"Test response from {self.name}"}


class TestCompilationWorkflowIntegration(BaseIntegrationTest):
    """
    Integration tests for graph compilation workflows.
    
    These tests verify real service coordination using the actual DI container
    and test real file I/O operations with compiled graph bundles.
    """
    
    def setup_services(self):
        """Initialize services needed for compilation workflow testing."""
        super().setup_services()
        
        # Core compilation services
        self.compilation_service = self.container.compilation_service()
        self.graph_definition_service = self.container.graph_definition_service()
        self.graph_bundle_service = self.container.graph_bundle_service()
        self.graph_assembly_service = self.container.graph_assembly_service()
        self.node_registry_service = self.container.node_registry_service()
        
        # Set up compilation directories
        self.compiled_dir = Path(self.temp_dir) / "compiled"
        self.compiled_dir.mkdir(exist_ok=True)
        
        # Update app config to use test directories
        self.app_config_service.compiled_graphs_path = self.compiled_dir
    
    def test_basic_graph_compilation_workflow(self):
        """Test basic graph compilation from CSV to .pkl file."""
        # Create simple test graph CSV
        csv_content = self._create_single_node_graph_csv()
        csv_path = self.create_test_csv_file(csv_content, "single_node.csv")
        
        # Create compilation options
        options = CompilationOptions(
            output_dir=self.compiled_dir,
            csv_path=csv_path,
            force_recompile=True,
            include_source=True
        )
        
        # Test compilation workflow
        result = self.compilation_service.compile_graph("test_single", options)
        
        # Verify compilation success
        self.assertTrue(result.success, f"Compilation should succeed: {result.error}")
        self.assertEqual(result.graph_name, "test_single")
        self.assertIsNone(result.error)
        self.assertGreater(result.compilation_time, 0)
        
        # Verify real file creation
        compiled_file = self.compiled_dir / "test_single.pkl"
        self.assert_file_exists(compiled_file, "Compiled graph file")
        
        # Verify source file creation
        source_file = self.compiled_dir / "test_single.src"
        self.assert_file_exists(source_file, "Source file")
        
        # Verify file contents are valid
        self._verify_compiled_file_contents(compiled_file)
        
        # Verify registry statistics
        self.assertIsNotNone(result.registry_stats)
        self.assertIn("nodes_processed", result.registry_stats)
        self.assertEqual(result.registry_stats["nodes_processed"], 1)
    
    def test_entry_point_detection_in_compilation(self):
        """Test that entry point detection works correctly during compilation."""
        # Create graph with clear entry point (node with no incoming edges)
        csv_content = self._create_entry_point_test_graph_csv()
        csv_path = self.create_test_csv_file(csv_content, "entry_point_test.csv")
        
        # Compile the graph
        options = CompilationOptions(
            output_dir=self.compiled_dir,
            csv_path=csv_path,
            force_recompile=True
        )
        
        result = self.compilation_service.compile_graph("entry_point_graph", options)
        
        # Verify compilation success
        self.assertTrue(result.success, f"Entry point compilation failed: {result.error}")
        
        # Load the compiled graph to verify entry point detection
        compiled_file = self.compiled_dir / "entry_point_graph.pkl"
        self.assert_file_exists(compiled_file, "Compiled entry point graph")
        
        # Verify the graph domain model has correct entry point
        graph_domain_model = self.graph_definition_service.build_from_csv(csv_path, "entry_point_graph")
        self.assertIsNotNone(graph_domain_model.entry_point)
        self.assertEqual(graph_domain_model.entry_point, "start_node", 
                        "Entry point should be detected as 'start_node' (has no incoming edges)")
    
    def test_multi_node_graph_compilation_workflow(self):
        """Test compilation of complex multi-node graph with proper edge handling."""
        # Create complex test graph
        csv_content = self._create_multi_node_graph_csv()
        csv_path = self.create_test_csv_file(csv_content, "multi_node.csv")
        
        # Compile the graph
        options = CompilationOptions(
            output_dir=self.compiled_dir,
            csv_path=csv_path,
            force_recompile=True,
            include_source=True
        )
        
        result = self.compilation_service.compile_graph("multi_node_graph", options)
        
        # Verify compilation success
        self.assertTrue(result.success, f"Multi-node compilation failed: {result.error}")
        
        # Verify file creation
        compiled_file = self.compiled_dir / "multi_node_graph.pkl"
        self.assert_file_exists(compiled_file, "Multi-node compiled graph")
        
        # Verify the compiled graph structure
        bundle = self._load_compiled_bundle(compiled_file)
        self.assertIsNotNone(bundle, "Should be able to load compiled bundle")
        
        # Verify node registry contains all nodes
        expected_nodes = {"input_node", "process_node", "output_node"}
        self.assertEqual(set(bundle.node_registry.keys()), expected_nodes,
                        "Node registry should contain all graph nodes")
        
        # Verify compilation stats reflect multi-node structure
        self.assertEqual(result.registry_stats["nodes_processed"], 3)
    
    def test_graph_bundle_service_coordination(self):
        """Test coordination between CompilationService and GraphBundleService."""
        # Create test graph
        csv_content = self._create_single_node_graph_csv()
        csv_path = self.create_test_csv_file(csv_content, "bundle_test.csv")
        
        # Test direct bundle service operations
        graph_domain_model = self.graph_definition_service.build_from_csv(csv_path, "test_single")
        
        # Convert to old format (testing the conversion process)
        old_format = self._convert_graph_to_old_format(graph_domain_model)
        
        # Prepare node registry
        node_registry = self.node_registry_service.prepare_for_assembly(old_format, "test_single")
        
        # Assemble graph
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph_def=old_format,
            node_registry=node_registry,
            enable_logging=True
        )
        
        # Test bundle creation and saving
        csv_content_str = csv_path.read_text()
        bundle = self.graph_bundle_service.create_bundle(
            graph=compiled_graph,
            node_registry=node_registry,
            csv_content=csv_content_str
        )
        
        # Verify bundle properties
        self.assertIsNotNone(bundle.graph)
        self.assertIsNotNone(bundle.node_registry)
        self.assertIsNotNone(bundle.version_hash)
        
        # Test bundle saving and loading
        bundle_path = self.compiled_dir / "test_bundle.pkl"
        self.graph_bundle_service.save_bundle(bundle, bundle_path)
        
        self.assert_file_exists(bundle_path, "Bundle file")
        
        # Test bundle loading
        loaded_bundle = self.graph_bundle_service.load_bundle(bundle_path)
        self.assertIsNotNone(loaded_bundle)
        self.assertEqual(bundle.version_hash, loaded_bundle.version_hash)
        
        # Test CSV verification
        self.assertTrue(self.graph_bundle_service.verify_csv(loaded_bundle, csv_content_str))
    
    def test_compilation_with_force_recompile(self):
        """Test force recompilation behavior."""
        # Create test graph
        csv_content = self._create_recompile_test_csv()
        csv_path = self.create_test_csv_file(csv_content, "recompile_test.csv")
        
        # First compilation
        options = CompilationOptions(
            output_dir=self.compiled_dir,
            csv_path=csv_path,
            force_recompile=False
        )
        
        result1 = self.compilation_service.compile_graph("recompile_test", options)
        self.assertTrue(result1.success)
        
        compiled_file = self.compiled_dir / "recompile_test.pkl"
        first_mtime = compiled_file.stat().st_mtime
        
        # Wait a moment to ensure different timestamps
        time.sleep(0.1)
        
        # Second compilation without force (should skip)
        result2 = self.compilation_service.compile_graph("recompile_test", options)
        self.assertTrue(result2.success)
        second_mtime = compiled_file.stat().st_mtime
        
        # File should not have been recompiled
        self.assertEqual(first_mtime, second_mtime, "File should not be recompiled without force")
        
        # Third compilation with force (should recompile)
        options.force_recompile = True
        result3 = self.compilation_service.compile_graph("recompile_test", options)
        self.assertTrue(result3.success)
        third_mtime = compiled_file.stat().st_mtime
        
        # File should have been recompiled
        self.assertGreater(third_mtime, first_mtime, "File should be recompiled with force")
    
    def test_compilation_error_handling(self):
        """Test compilation error handling with invalid CSV."""
        # Create invalid CSV content (missing required columns)
        invalid_csv = "InvalidColumn,Data\nvalue1,value2\n"
        csv_path = self.create_test_csv_file(invalid_csv, "invalid.csv")
        
        # Attempt compilation
        options = CompilationOptions(
            output_dir=self.compiled_dir,
            csv_path=csv_path
        )
        
        result = self.compilation_service.compile_graph("invalid_graph", options)
        
        # Verify failure is handled gracefully
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("invalid_graph", result.error)
        
        # Verify no files were created
        compiled_file = self.compiled_dir / "invalid_graph.pkl"
        self.assertFalse(compiled_file.exists(), "No file should be created for failed compilation")
    
    def test_auto_compilation_workflow(self):
        """Test auto-compilation integration."""
        # Create test graph
        csv_content = self._create_auto_compile_test_csv()
        csv_path = self.create_test_csv_file(csv_content, "auto_compile_test.csv")
        
        # Test auto-compilation when file doesn't exist
        options = CompilationOptions(
            output_dir=self.compiled_dir,
            csv_path=csv_path
        )
        
        result = self.compilation_service.auto_compile_if_needed("auto_test", csv_path, options)
        
        # Should perform compilation
        self.assertIsNotNone(result, "Auto-compilation should occur when file doesn't exist")
        self.assertTrue(result.success)
        
        # Test auto-compilation when file is current
        result2 = self.compilation_service.auto_compile_if_needed("auto_test", csv_path, options)
        
        # Should not perform compilation
        self.assertIsNone(result2, "Auto-compilation should be skipped when file is current")
    
    def test_compile_all_graphs_workflow(self):
        """Test compilation of all graphs in a CSV file."""
        # Create CSV with multiple graphs
        csv_content = self._create_multiple_graphs_csv()
        csv_path = self.create_test_csv_file(csv_content, "multiple_graphs.csv")
        
        # Compile all graphs
        options = CompilationOptions(
            output_dir=self.compiled_dir,
            csv_path=csv_path,
            force_recompile=True
        )
        
        results = self.compilation_service.compile_all_graphs(options)
        
        # Verify all compilations
        self.assertEqual(len(results), 2, "Should compile both graphs")
        
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        self.assertEqual(len(successful_results), 2, "Both graphs should compile successfully")
        self.assertEqual(len(failed_results), 0, "No graphs should fail")
        
        # Verify files exist for both graphs
        graph1_file = self.compiled_dir / "graph_one.pkl"
        graph2_file = self.compiled_dir / "graph_two.pkl"
        
        self.assert_file_exists(graph1_file, "First graph file")
        self.assert_file_exists(graph2_file, "Second graph file")
    
    def test_compilation_status_checking(self):
        """Test compilation status checking functionality."""
        # Create test graph
        csv_content = self._create_status_test_csv()
        csv_path = self.create_test_csv_file(csv_content, "status_test.csv")
        
        # Check status before compilation
        status_before = self.compilation_service.get_compilation_status("status_test", csv_path)
        
        self.assertFalse(status_before["compiled"])
        self.assertFalse(status_before["current"])
        
        # Compile graph
        options = CompilationOptions(
            output_dir=self.compiled_dir,
            csv_path=csv_path
        )
        
        result = self.compilation_service.compile_graph("status_test", options)
        self.assertTrue(result.success)
        
        # Check status after compilation
        status_after = self.compilation_service.get_compilation_status("status_test", csv_path)
        
        self.assertTrue(status_after["compiled"])
        self.assertTrue(status_after["current"])
        self.assertIn("compiled_time", status_after)
        self.assertIn("csv_modified_time", status_after)
    
    def test_file_system_operations(self):
        """Test real file system operations and error handling."""
        # Test directory creation
        custom_output_dir = Path(self.temp_dir) / "custom_compiled"
        
        csv_content = self._create_filesystem_test_csv()
        csv_path = self.create_test_csv_file(csv_content, "filesystem_test.csv")
        
        # Compile to custom directory
        options = CompilationOptions(
            output_dir=custom_output_dir,
            csv_path=csv_path
        )
        
        result = self.compilation_service.compile_graph("filesystem_test", options)
        
        # Verify directory was created and file exists
        self.assertTrue(result.success)
        self.assert_directory_exists(custom_output_dir, "Custom output directory")
        
        compiled_file = custom_output_dir / "filesystem_test.pkl"
        self.assert_file_exists(compiled_file, "Compiled file in custom directory")
        
        # Verify file size is reasonable
        file_size = compiled_file.stat().st_size
        self.assertGreater(file_size, 100, "Compiled file should have reasonable size")
    
    # Helper methods
    
    def _create_single_node_graph_csv(self) -> str:
        """Create CSV content for single node graph testing."""
        return '''GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
test_single,single_node,,general,Default,,,,response,Simple test node
'''
    
    def _create_entry_point_test_graph_csv(self) -> str:
        """Create CSV content for entry point detection testing."""
        return '''GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
entry_point_graph,start_node,middle_node,general,Default,,,,start_data,Start of process
entry_point_graph,middle_node,end_node,general,Default,,,,middle_data,Middle processing
entry_point_graph,end_node,,general,Default,,,,end_data,End of process
'''
    
    def _create_multi_node_graph_csv(self) -> str:
        """Create CSV content for multi-node graph testing."""
        return '''GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
multi_node_graph,input_node,process_node,general,Default,,,,input_data,Input processing
multi_node_graph,process_node,output_node,general,Default,,,,processed_data,Main processing
multi_node_graph,output_node,,general,Default,,,,final_output,Output formatting
'''
    
    def _create_multiple_graphs_csv(self) -> str:
        """Create CSV content with multiple graphs for batch testing."""
        return '''GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
graph_one,node_one,,general,Default,,,,output_one,First graph node
graph_two,node_two,,general,Default,,,,output_two,Second graph node
'''
    
    def _create_recompile_test_csv(self) -> str:
        """Create CSV content for recompile testing."""
        return '''GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
recompile_test,single_node,,general,Default,,,,response,Simple test node
'''
    
    def _create_auto_compile_test_csv(self) -> str:
        """Create CSV content for auto-compile testing."""
        return '''GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
auto_test,single_node,,general,Default,,,,response,Simple test node
'''
    
    def _create_status_test_csv(self) -> str:
        """Create CSV content for status testing."""
        return '''GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
status_test,single_node,,general,Default,,,,response,Simple test node
'''
    
    def _create_filesystem_test_csv(self) -> str:
        """Create CSV content for filesystem testing."""
        return '''GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
filesystem_test,single_node,,general,Default,,,,response,Simple test node
'''
    
    def _convert_graph_to_old_format(self, graph) -> Dict[str, Any]:
        """Convert Graph domain model to old format for testing."""
        # Create a custom dictionary class that can hold additional attributes
        class GraphDefinition(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._graph_entry_point = None
        
        old_format = GraphDefinition()
        
        for node_name, node in graph.nodes.items():
            # Create a simple agent instance for testing
            agent_instance = self._create_test_agent_instance(node)
            
            # Prepare context with agent instance
            test_context = {
                "instance": agent_instance,
                "input_fields": node.inputs,
                "output_field": node.output,
                "description": node.description or ""
            }
            
            old_format[node_name] = type('Node', (), {
                'name': node.name,
                'context': test_context,
                'agent_type': node.agent_type,
                'inputs': node.inputs,
                'output': node.output,
                'prompt': node.prompt,
                'description': node.description,
                'edges': node.edges,
                '_is_entry_point': node_name == graph.entry_point
            })()
        
        # Store entry point at graph level
        old_format._graph_entry_point = graph.entry_point
        
        return old_format
    
    def _create_test_agent_instance(self, node):
        """Create a simple agent instance for testing."""
        return TestAgent(node.name, node.prompt or "")
    
    def _verify_compiled_file_contents(self, file_path: Path) -> None:
        """Verify that compiled file contains valid pickle data."""
        try:
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            
            # Basic structure verification
            self.assertIsInstance(data, dict, "Compiled file should contain dictionary")
            self.assertIn("graph", data, "Compiled data should have 'graph' key")
            self.assertIn("node_registry", data, "Compiled data should have 'node_registry' key")
            self.assertIn("version_hash", data, "Compiled data should have 'version_hash' key")
            
        except Exception as e:
            self.fail(f"Failed to load or validate compiled file {file_path}: {e}")
    
    def _load_compiled_bundle(self, file_path: Path) -> GraphBundle:
        """Load and return a compiled bundle for testing."""
        return self.graph_bundle_service.load_bundle(file_path)


if __name__ == '__main__':
    unittest.main()
