"""
Unit tests for CompilationService.

These tests validate the CompilationService orchestration capabilities
using MockServiceFactory patterns for consistent testing.

CompilationService is responsible for:
- Orchestrating graph compilation with clean interface
- Managing compilation options and results
- Coordinating with GraphDefinitionService, GraphAssemblyService, and GraphBundleService
- Handling both single graph and batch compilation
- Auto-compilation capabilities with dependency tracking
- Validation and error handling throughout compilation process
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from typing import Dict, Any, Optional
import time
import os

from agentmap.services.compilation_service import CompilationService, CompilationOptions, CompilationResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestCompilationService(unittest.TestCase):
    """Unit tests for CompilationService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create all required mock services using MockServiceFactory
        self.mock_graph_definition_service = MockServiceFactory.create_mock_graph_definition_service()
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "csv_path": "graphs/workflow.csv",
            "compiled_graphs_path": "compiled",
            "functions_path": "functions"
        })
        
        # Override path methods to return proper Path objects
        self.mock_app_config_service.get_csv_path.return_value = Path("graphs/workflow.csv")
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
        
        # Configure property access for the service
        self.mock_app_config_service.csv_path = Path("graphs/workflow.csv")
        self.mock_app_config_service.compiled_graphs_path = Path("compiled")
        self.mock_app_config_service.functions_path = Path("functions")
        self.mock_node_registry_service = MockServiceFactory.create_mock_node_registry_service()
        self.mock_graph_bundle_service = MockServiceFactory.create_mock_graph_bundle_service()
        self.mock_assembly_service = MockServiceFactory.create_mock_graph_assembly_service()
        
        # Create mock function resolution service
        self.mock_function_resolution_service = Mock()
        self.mock_function_resolution_service.resolve_function.return_value = Mock()
        
        # Initialize CompilationService with all mocked dependencies
        self.service = CompilationService(
            graph_definition_service=self.mock_graph_definition_service,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config_service,
            node_registry_service=self.mock_node_registry_service,
            graph_bundle_service=self.mock_graph_bundle_service,
            assembly_service=self.mock_assembly_service,
            function_resolution_service=self.mock_function_resolution_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all core services are stored
        self.assertEqual(self.service.graph_definition, self.mock_graph_definition_service)
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertEqual(self.service.node_registry, self.mock_node_registry_service)
        self.assertEqual(self.service.assembly_service, self.mock_assembly_service)
        self.assertEqual(self.service.bundle_service, self.mock_graph_bundle_service)
        self.assertEqual(self.service.function_resolution_service, self.mock_function_resolution_service)
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "CompilationService")
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == "[CompilationService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies gracefully."""
        # This test verifies that all dependencies are actually required
        with self.assertRaises(TypeError):
            # Missing required dependencies should raise TypeError
            CompilationService(
                graph_definition_service=self.mock_graph_definition_service,
                # Missing other required services
            )
    
    def test_get_service_info(self):
        """Test get_service_info() debug method."""
        # Act
        service_info = self.service.get_service_info()
        
        # Assert basic structure
        self.assertIsInstance(service_info, dict)
        self.assertEqual(service_info["service"], "CompilationService")
        
        # Verify dependency availability flags
        self.assertTrue(service_info["graph_definition_available"])
        self.assertTrue(service_info["config_available"])
        self.assertTrue(service_info["node_registry_available"])
        
        # Verify configuration paths (using os.path.normpath to handle path separators)
        self.assertIn("compiled", str(service_info["compiled_graphs_path"]))
        self.assertIn("workflow.csv", str(service_info["csv_path"]))  # Just check filename part
        self.assertIn("functions", str(service_info["functions_path"]))
    
    # =============================================================================
    # 2. CompilationOptions Tests
    # =============================================================================
    
    def test_compilation_options_defaults(self):
        """Test CompilationOptions with default values."""
        options = CompilationOptions()
        
        # Verify default values
        self.assertIsNone(options.output_dir)
        self.assertEqual(options.state_schema, "dict")
        self.assertFalse(options.force_recompile)
        self.assertTrue(options.include_source)
        self.assertIsNone(options.csv_path)
    
    def test_compilation_options_custom_values(self):
        """Test CompilationOptions with custom values."""
        custom_output = Path("custom/output")
        custom_csv = Path("custom/graphs.csv")
        
        options = CompilationOptions(
            output_dir=custom_output,
            state_schema="pydantic",
            force_recompile=True,
            include_source=False,
            csv_path=custom_csv
        )
        
        # Verify custom values
        self.assertEqual(options.output_dir, custom_output)
        self.assertEqual(options.state_schema, "pydantic")
        self.assertTrue(options.force_recompile)
        self.assertFalse(options.include_source)
        self.assertEqual(options.csv_path, custom_csv)
    
    # =============================================================================
    # 3. Single Graph Compilation Tests
    # =============================================================================
    
    def test_compile_graph_success_with_defaults(self):
        """Test compile_graph() with successful compilation using default options."""
        # Prepare test data
        graph_name = "test_workflow"
        
        # Configure graph definition service to return realistic graph
        mock_graph = Mock()
        mock_graph.nodes = {
            "start_node": Mock(name="start_node", inputs=[], output="start_output"),
            "process_node": Mock(name="process_node", inputs=["start_output"], output="final_result")
        }
        
        # Clear the MockServiceFactory's side_effect and set our specific return_value
        self.mock_graph_definition_service.build_from_csv.side_effect = None
        self.mock_graph_definition_service.build_from_csv.return_value = mock_graph
        
        # Configure node registry
        mock_node_registry = {"start_node": Mock(), "process_node": Mock()}
        self.mock_node_registry_service.prepare_for_assembly.side_effect = None
        self.mock_node_registry_service.prepare_for_assembly.return_value = mock_node_registry
        
        # Configure graph assembly
        mock_compiled_graph = Mock()
        self.mock_assembly_service.assemble_graph.side_effect = None
        self.mock_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        # Configure bundle creation and saving
        mock_bundle = Mock()
        self.mock_graph_bundle_service.create_bundle.return_value = mock_bundle
        self.mock_graph_bundle_service.save_bundle.return_value = None
        
        # Mock file operations and CSV reading with small delay
        with patch('os.makedirs'), \
             patch('builtins.open', unittest.mock.mock_open(read_data="test,csv,content")), \
             patch.object(self.service, '_is_compilation_current', return_value=False), \
             patch.object(self.service, '_create_agent_instance', return_value=Mock()), \
             patch('time.time', side_effect=[0.0, 0.1]):  # Mock start and end times
            
            # Execute test
            result = self.service.compile_graph(graph_name)
            
            # Verify successful result
            self.assertIsInstance(result, CompilationResult)
            self.assertEqual(result.graph_name, graph_name)
            self.assertTrue(result.success)
            self.assertIsNone(result.error)
            self.assertEqual(result.output_path, Path("compiled/test_workflow.pkl"))
            self.assertIsNotNone(result.source_path)
            self.assertGreater(result.compilation_time, 0)
            
            # Verify service interactions
            self.mock_graph_definition_service.build_from_csv.assert_called_once()
            self.mock_node_registry_service.prepare_for_assembly.assert_called_once()
            self.mock_assembly_service.assemble_graph.assert_called_once()
            self.mock_graph_bundle_service.create_bundle.assert_called_once()
            self.mock_graph_bundle_service.save_bundle.assert_called_once()
            
            # Verify registry statistics
            registry_stats = result.registry_stats
            self.assertIsNotNone(registry_stats)
            self.assertEqual(registry_stats["nodes_processed"], 2)
            self.assertEqual(registry_stats["registry_size"], 2)
            
            # Verify success logging
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            self.assertTrue(any(f"Compiling graph: {graph_name}" in call[1] for call in info_calls))
            self.assertTrue(any(f"✅ Compiled {graph_name} to" in call[1] for call in info_calls))
            self.assertTrue(any("with registry injection" in call[1] for call in info_calls))
    
    def test_compile_graph_with_custom_options(self):
        """Test compile_graph() with custom compilation options."""
        # Prepare test data
        graph_name = "custom_workflow"
        custom_output = Path("custom/output")
        custom_csv = Path("custom/workflow.csv")
        
        options = CompilationOptions(
            output_dir=custom_output,
            state_schema="pydantic",
            force_recompile=True,
            include_source=False,
            csv_path=custom_csv
        )
        
        # Configure graph definition service
        mock_graph = Mock()
        mock_graph.nodes = {"single_node": Mock(name="single_node")}
        
        self.mock_graph_definition_service.build_from_csv.side_effect = None
        self.mock_graph_definition_service.build_from_csv.return_value = mock_graph
        
        # Configure other services
        self.mock_node_registry_service.prepare_for_assembly.side_effect = None
        self.mock_node_registry_service.prepare_for_assembly.return_value = {"single_node": Mock()}
        
        mock_compiled_graph = Mock()
        self.mock_assembly_service.assemble_graph.side_effect = None
        self.mock_assembly_service.assemble_graph.return_value = mock_compiled_graph
        
        mock_bundle = Mock()
        self.mock_graph_bundle_service.create_bundle.return_value = mock_bundle
        self.mock_graph_bundle_service.save_bundle.return_value = None
        
        # Mock file operations
        with patch('os.makedirs'), \
             patch('builtins.open', unittest.mock.mock_open(read_data="custom,csv,content")), \
             patch.object(self.service, '_is_compilation_current', return_value=False), \
             patch.object(self.service, '_create_agent_instance', return_value=Mock()):
            
            # Execute test
            result = self.service.compile_graph(graph_name, options)
            
            # Verify result uses custom options
            self.assertTrue(result.success)
            self.assertEqual(result.graph_name, graph_name)
            self.assertEqual(result.output_path, custom_output / f"{graph_name}.pkl")
            self.assertIsNone(result.source_path)  # include_source=False
            
            # Verify custom CSV path was used
            build_call_args = self.mock_graph_definition_service.build_from_csv.call_args
            self.assertEqual(build_call_args[0][0], custom_csv)
            self.assertEqual(build_call_args[0][1], graph_name)
    
    def test_compile_graph_skip_current_compilation(self):
        """Test compile_graph() skips compilation when current."""
        # Prepare test data
        graph_name = "current_graph"
        
        # Mock current compilation check
        with patch.object(self.service, '_is_compilation_current', return_value=True), \
             patch.object(self.service, '_get_output_path') as mock_get_output, \
             patch.object(self.service, '_get_source_path') as mock_get_source:
            
            # Configure path methods
            mock_output_path = Path("compiled/current_graph.pkl")
            mock_source_path = Path("compiled/current_graph.src")
            mock_get_output.return_value = mock_output_path
            mock_get_source.return_value = mock_source_path
            
            # Execute test
            result = self.service.compile_graph(graph_name)
            
            # Verify compilation was skipped
            self.assertTrue(result.success)
            self.assertEqual(result.graph_name, graph_name)
            self.assertEqual(result.output_path, mock_output_path)
            self.assertEqual(result.source_path, mock_source_path)
            
            # Verify no compilation services were called
            self.mock_graph_definition_service.build_from_csv.assert_not_called()
            self.mock_assembly_service.assemble_graph.assert_not_called()
            
            # Verify skip logging
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            self.assertTrue(any("is up to date, skipping compilation" in call[1] for call in info_calls))
    
    def test_compile_graph_assembly_failure(self):
        """Test compile_graph() handles graph assembly failures."""
        # Prepare test data
        graph_name = "failing_graph"
        
        # Configure graph definition service
        mock_graph = Mock()
        mock_graph.nodes = {"bad_node": Mock(name="bad_node")}
        
        self.mock_graph_definition_service.build_from_csv.side_effect = None
        self.mock_graph_definition_service.build_from_csv.return_value = mock_graph
        
        # Configure node registry
        self.mock_node_registry_service.prepare_for_assembly.side_effect = None
        self.mock_node_registry_service.prepare_for_assembly.return_value = {"bad_node": Mock()}
        
        # Configure assembly service to return None (failure)
        self.mock_assembly_service.assemble_graph.side_effect = None
        self.mock_assembly_service.assemble_graph.return_value = None
        
        # Mock file operations
        with patch('os.makedirs'), \
             patch('builtins.open', unittest.mock.mock_open(read_data="test,csv")), \
             patch.object(self.service, '_is_compilation_current', return_value=False), \
             patch.object(self.service, '_create_agent_instance', return_value=Mock()):
            
            # Execute test
            result = self.service.compile_graph(graph_name)
            
            # Verify failure result
            self.assertFalse(result.success)
            self.assertEqual(result.graph_name, graph_name)
            self.assertEqual(result.output_path, Path(""))  # Empty path for failure
            self.assertIsNone(result.source_path)
            self.assertIn("assemble_graph returned None", result.error)
            
            # Verify assembly was attempted
            self.mock_assembly_service.assemble_graph.assert_called_once()
            
            # Verify error logging
            logger_calls = self.mock_logger.calls
            error_calls = [call for call in logger_calls if call[0] == "error"]
            self.assertTrue(any(f"Failed to compile graph {graph_name}" in call[1] for call in error_calls))
    
    def test_compile_graph_graph_definition_failure(self):
        """Test compile_graph() handles graph definition loading failures."""
        # Prepare test data
        graph_name = "invalid_graph"
        
        # Configure graph definition service to raise exception
        definition_error = ValueError("Invalid CSV format: missing required columns")
        self.mock_graph_definition_service.build_from_csv.side_effect = definition_error
        
        # Mock current compilation check to force attempt
        with patch.object(self.service, '_is_compilation_current', return_value=False):
            
            # Execute test
            result = self.service.compile_graph(graph_name)
            
            # Verify failure result
            self.assertFalse(result.success)
            self.assertEqual(result.graph_name, graph_name)
            self.assertEqual(result.output_path, Path(""))
            self.assertIsNone(result.source_path)
            self.assertEqual(result.error, f"Failed to compile graph {graph_name}: Invalid CSV format: missing required columns")
            
            # Verify graph definition service was called
            self.mock_graph_definition_service.build_from_csv.assert_called_once()
            
            # Verify no assembly was attempted
            self.mock_assembly_service.assemble_graph.assert_not_called()
    
    # =============================================================================
    # 4. Batch Compilation Tests
    # =============================================================================
    
    def test_compile_all_graphs_success(self):
        """Test compile_all_graphs() with successful batch compilation."""
        # Configure graph definition service to return multiple graphs
        all_graphs = {
            "workflow1": Mock(nodes={"node1": Mock(name="node1")}),
            "workflow2": Mock(nodes={"node2": Mock(name="node2")}),
            "workflow3": Mock(nodes={"node3": Mock(name="node3")})
        }
        
        self.mock_graph_definition_service.build_all_from_csv.side_effect = None
        self.mock_graph_definition_service.build_all_from_csv.return_value = all_graphs
        
        # Mock successful individual compilation
        with patch.object(self.service, 'compile_graph') as mock_compile:
            # Configure mock compile results
            mock_compile.side_effect = [
                CompilationResult("workflow1", Path("compiled/workflow1.pkl"), None, True, 1.0),
                CompilationResult("workflow2", Path("compiled/workflow2.pkl"), None, True, 1.5),
                CompilationResult("workflow3", Path("compiled/workflow3.pkl"), None, True, 2.0)
            ]
            
            # Execute test
            results = self.service.compile_all_graphs()
            
            # Verify batch results
            self.assertEqual(len(results), 3)
            self.assertTrue(all(result.success for result in results))
            
            # Verify each graph was compiled with proper options
            self.assertEqual(mock_compile.call_count, 3)
            call_args_list = mock_compile.call_args_list
            
            # Verify the graph names in the calls
            called_graph_names = [call[0][0] for call in call_args_list]
            self.assertIn("workflow1", called_graph_names)
            self.assertIn("workflow2", called_graph_names)
            self.assertIn("workflow3", called_graph_names)
            
            # Verify options were passed (not None)
            for call in call_args_list:
                self.assertIsNotNone(call[0][1])  # options parameter should not be None
            
            # Verify batch completion logging
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            self.assertTrue(any("Compiling all graphs" in call[1] for call in info_calls))
            self.assertTrue(any("✅ Compilation complete: 3 successful, 0 failed" in call[1] for call in info_calls))
    
    def test_compile_all_graphs_mixed_results(self):
        """Test compile_all_graphs() with mixed success and failure results."""
        # Configure graph definition service
        all_graphs = {
            "good_graph": Mock(nodes={"node1": Mock()}),
            "bad_graph": Mock(nodes={"node2": Mock()})
        }
        
        self.mock_graph_definition_service.build_all_from_csv.side_effect = None
        self.mock_graph_definition_service.build_all_from_csv.return_value = all_graphs
        
        # Mock mixed compilation results
        with patch.object(self.service, 'compile_graph') as mock_compile:
            # Configure mixed results
            mock_compile.side_effect = [
                CompilationResult("good_graph", Path("compiled/good_graph.pkl"), None, True, 1.0),
                CompilationResult("bad_graph", Path(""), None, False, 0.5, error="Compilation failed")
            ]
            
            # Execute test
            results = self.service.compile_all_graphs()
            
            # Verify mixed results
            self.assertEqual(len(results), 2)
            successful_results = [r for r in results if r.success]
            failed_results = [r for r in results if not r.success]
            self.assertEqual(len(successful_results), 1)
            self.assertEqual(len(failed_results), 1)
            
            # Verify logging shows mixed results
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            error_calls = [call for call in logger_calls if call[0] == "error"]
            
            self.assertTrue(any("✅ Compilation complete: 1 successful, 1 failed" in call[1] for call in info_calls))
            self.assertTrue(any("Failed: bad_graph - Compilation failed" in call[1] for call in error_calls))
    
    def test_compile_all_graphs_batch_failure(self):
        """Test compile_all_graphs() handles batch loading failures."""
        # Configure graph definition service to raise exception
        batch_error = FileNotFoundError("CSV file not found: missing.csv")
        self.mock_graph_definition_service.build_all_from_csv.side_effect = batch_error
        
        # Execute test
        results = self.service.compile_all_graphs()
        
        # Verify single failure result for batch
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertFalse(result.success)
        self.assertEqual(result.graph_name, "<batch_compilation>")
        self.assertEqual(result.output_path, Path(""))
        self.assertIn("Failed to compile all graphs", result.error)
        self.assertIn("CSV file not found", result.error)
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(any("Failed to compile all graphs" in call[1] for call in error_calls))
    
    # =============================================================================
    # 5. Auto-Compilation Tests
    # =============================================================================
    
    def test_auto_compile_if_needed_compilation_required(self):
        """Test auto_compile_if_needed() when compilation is needed."""
        # Prepare test data
        graph_name = "outdated_graph"
        csv_path = Path("graphs/updated.csv")
        options = CompilationOptions(csv_path=csv_path)
        
        # Mock compilation check to indicate needed
        with patch.object(self.service, '_is_compilation_current', return_value=False), \
             patch.object(self.service, 'compile_graph') as mock_compile:
            
            # Configure successful compilation
            mock_result = CompilationResult(graph_name, Path("compiled/outdated_graph.pkl"), None, True, 2.5)
            mock_compile.return_value = mock_result
            
            # Execute test
            result = self.service.auto_compile_if_needed(graph_name, csv_path, options)
            
            # Verify compilation was performed
            self.assertIsNotNone(result)
            self.assertEqual(result, mock_result)
            
            # Verify compile_graph was called with correct parameters
            mock_compile.assert_called_once_with(graph_name, options)
            
            # Verify auto-compilation logging
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            self.assertTrue(any(f"Auto-compiling outdated graph: {graph_name}" in call[1] for call in info_calls))
    
    def test_auto_compile_if_needed_current_compilation(self):
        """Test auto_compile_if_needed() when compilation is current."""
        # Prepare test data
        graph_name = "current_graph"
        csv_path = Path("graphs/current.csv")
        
        # Mock compilation check to indicate current
        with patch.object(self.service, '_is_compilation_current', return_value=True):
            
            # Execute test
            result = self.service.auto_compile_if_needed(graph_name, csv_path)
            
            # Verify no compilation was performed
            self.assertIsNone(result)
            
            # Verify debug logging
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertTrue(any(f"Graph {graph_name} is current, no compilation needed" in call[1] for call in debug_calls))
    
    def test_auto_compile_if_needed_with_defaults(self):
        """Test auto_compile_if_needed() creates default options when None provided."""
        # Prepare test data
        graph_name = "default_options_graph"
        csv_path = Path("graphs/test.csv")
        
        # Mock compilation check and compile_graph
        with patch.object(self.service, '_is_compilation_current', return_value=False), \
             patch.object(self.service, 'compile_graph') as mock_compile:
            
            mock_result = CompilationResult(graph_name, Path("compiled/test.pkl"), None, True, 1.0)
            mock_compile.return_value = mock_result
            
            # Execute test with no options
            result = self.service.auto_compile_if_needed(graph_name, csv_path, options=None)
            
            # Verify compilation was performed
            self.assertIsNotNone(result)
            
            # Verify compile_graph was called with created options
            mock_compile.assert_called_once()
            call_args = mock_compile.call_args
            self.assertEqual(call_args[0][0], graph_name)  # graph_name
            
            # Verify options were created with csv_path
            options_arg = call_args[0][1]  # options
            self.assertIsInstance(options_arg, CompilationOptions)
            self.assertEqual(options_arg.csv_path, csv_path)
    
    # =============================================================================
    # 6. Validation and Status Methods Tests
    # =============================================================================
    
    def test_validate_before_compilation_valid_csv(self):
        """Test validate_before_compilation() with valid CSV."""
        # Prepare test data
        csv_path = Path("graphs/valid.csv")
        
        # Configure graph definition service to return no validation errors
        self.mock_graph_definition_service.validate_csv_before_building.side_effect = None
        self.mock_graph_definition_service.validate_csv_before_building.return_value = []
        
        # Execute test
        errors = self.service.validate_before_compilation(csv_path)
        
        # Verify no errors
        self.assertEqual(errors, [])
        
        # Verify validation service was called
        self.mock_graph_definition_service.validate_csv_before_building.assert_called_once_with(csv_path)
        
        # Verify debug logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any(f"Validating CSV before compilation: {csv_path}" in call[1] for call in debug_calls))
    
    def test_validate_before_compilation_invalid_csv(self):
        """Test validate_before_compilation() with invalid CSV."""
        # Prepare test data
        csv_path = Path("graphs/invalid.csv")
        validation_errors = [
            "Missing required column: graph_name",
            "Invalid agent_type: unknown_agent",
            "Circular dependency detected in node flow"
        ]
        
        # Configure graph definition service to return validation errors
        self.mock_graph_definition_service.validate_csv_before_building.side_effect = None
        self.mock_graph_definition_service.validate_csv_before_building.return_value = validation_errors
        
        # Execute test
        errors = self.service.validate_before_compilation(csv_path)
        
        # Verify errors returned
        self.assertEqual(errors, validation_errors)
        self.assertEqual(len(errors), 3)
        
        # Verify validation service was called
        self.mock_graph_definition_service.validate_csv_before_building.assert_called_once_with(csv_path)
    
    def test_get_compilation_status_compiled_current(self):
        """Test get_compilation_status() for compiled and current graph."""
        # Prepare test data
        graph_name = "status_test_graph"
        csv_path = Path("graphs/test.csv")
        
        # Mock path operations and file stats
        with patch.object(self.service, '_get_output_path') as mock_get_output, \
             patch.object(self.service, '_is_compilation_current') as mock_is_current, \
             patch('pathlib.Path.stat') as mock_stat:
            
            # Configure output path
            output_path = Path("compiled/status_test_graph.pkl")
            mock_get_output.return_value = output_path
            
            # Configure file existence and currency using proper global patching
            def mock_exists(self):
                if str(self) == str(output_path) or str(self) == str(csv_path):
                    return True
                return False
            
            with patch('pathlib.Path.exists', mock_exists):
                mock_is_current.return_value = True
                
                # Configure file modification times
                mock_stat.return_value.st_mtime = 1642000000  # Mock timestamp
                
                # Execute test
                status = self.service.get_compilation_status(graph_name, csv_path)
                
                # Verify status
                self.assertEqual(status["graph_name"], graph_name)
                self.assertTrue(status["compiled"])
                self.assertTrue(status["current"])
                self.assertEqual(status["output_path"], output_path)
                self.assertEqual(status["csv_path"], csv_path)
                self.assertEqual(status["compiled_time"], 1642000000)
                self.assertEqual(status["csv_modified_time"], 1642000000)
    
    def test_get_compilation_status_not_compiled(self):
        """Test get_compilation_status() for non-compiled graph."""
        # Prepare test data
        graph_name = "uncompiled_graph"
        
        # Mock path operations
        with patch.object(self.service, '_get_output_path') as mock_get_output:
            
            # Configure output path that doesn't exist
            output_path = Path("compiled/uncompiled_graph.pkl")
            mock_get_output.return_value = output_path
            
            # Configure file existence using proper global patching
            def mock_exists(self):
                if str(self) == str(output_path):
                    return False
                return True  # Other files exist by default
            
            with patch('pathlib.Path.exists', mock_exists):
                
                # Execute test (using default CSV path from config)
                status = self.service.get_compilation_status(graph_name)
                
                # Verify status
                self.assertEqual(status["graph_name"], graph_name)
                self.assertFalse(status["compiled"])
                self.assertFalse(status["current"])
                self.assertEqual(status["output_path"], output_path)
                self.assertEqual(status["csv_path"], Path("graphs/workflow.csv"))  # From config
                self.assertNotIn("compiled_time", status)
                self.assertNotIn("csv_modified_time", status)
    
    def test_get_compilation_status_compiled_outdated(self):
        """Test get_compilation_status() for compiled but outdated graph."""
        # Prepare test data
        graph_name = "outdated_graph"
        csv_path = Path("graphs/updated.csv")
        
        # Mock path operations
        with patch.object(self.service, '_get_output_path') as mock_get_output, \
             patch.object(self.service, '_is_compilation_current') as mock_is_current, \
             patch('pathlib.Path.stat') as mock_stat:
            
            # Configure output path
            output_path = Path("compiled/outdated_graph.pkl")
            mock_get_output.return_value = output_path
            
            # Configure file existence using proper global patching
            def mock_exists(self):
                # Both output_path and csv_path should exist for this test
                if str(self) == str(output_path) or str(self) == str(csv_path):
                    return True
                return False
            
            with patch('pathlib.Path.exists', mock_exists):
                
                mock_is_current.return_value = False  # Outdated
                
                # Configure file modification times (compiled older than CSV)
                # For this test, the service calls both output_path.stat() and csv_path.stat()
                # We'll mock both calls to return the appropriate times
                
                # Mock the global Path.stat to handle both calls
                def mock_stat_for_paths():
                    # This will be called twice - once for output_path, once for csv_path
                    # We'll track which call this is by checking the stack or use a counter
                    mock_stat_result = Mock()
                    # For this test, first call (output_path) should be older
                    # Second call (csv_path) should be newer
                    # We'll just alternate between them
                    if not hasattr(mock_stat_for_paths, 'call_count'):
                        mock_stat_for_paths.call_count = 0
                    
                    mock_stat_for_paths.call_count += 1
                    if mock_stat_for_paths.call_count == 1:
                        mock_stat_result.st_mtime = 1641000000  # Older (compiled file)
                    else:
                        mock_stat_result.st_mtime = 1642000000  # Newer (CSV file)
                    
                    return mock_stat_result
                
                mock_stat.side_effect = mock_stat_for_paths
                
                # Execute test
                status = self.service.get_compilation_status(graph_name, csv_path)
                
                # Verify status shows outdated
                self.assertEqual(status["graph_name"], graph_name)
                self.assertTrue(status["compiled"])
                self.assertFalse(status["current"])  # Outdated
                self.assertEqual(status["compiled_time"], 1641000000)
                self.assertEqual(status["csv_modified_time"], 1642000000)
    
    # =============================================================================
    # 7. Internal Method Tests
    # =============================================================================
    
    def test_is_compilation_current_file_newer(self):
        """Test _is_compilation_current() when compiled file is newer."""
        # Prepare test data
        graph_name = "current_test"
        csv_path = Path("graphs/test.csv")
        output_path = Path("compiled/current_test.pkl")
        
        # Mock the internal method calls using proper global patching
        def mock_exists(self):
            if str(self) == str(output_path) or str(self) == str(csv_path):
                return True
            return False
        
        def mock_stat(self):
            stat_result = Mock()
            if str(self) == str(output_path):
                stat_result.st_mtime = 1642000000  # Newer compiled file
            else:  # csv_path
                stat_result.st_mtime = 1641000000  # Older CSV
            return stat_result
        
        with patch.object(self.service, '_get_output_path', return_value=output_path), \
             patch('pathlib.Path.exists', mock_exists), \
             patch('pathlib.Path.stat', mock_stat):
            
            # Execute test
            result = self.service._is_compilation_current(graph_name, csv_path)
            
            # Verify result
            self.assertTrue(result)
    
    def test_is_compilation_current_missing_compiled_file(self):
        """Test _is_compilation_current() when compiled file doesn't exist."""
        # Prepare test data
        graph_name = "missing_test"
        csv_path = Path("graphs/test.csv")
        output_path = Path("compiled/missing_test.pkl")
        
        # Mock the internal method calls using proper global patching
        def mock_exists(self):
            if str(self) == str(output_path):
                return False
            return True
        
        with patch.object(self.service, '_get_output_path', return_value=output_path), \
             patch('pathlib.Path.exists', mock_exists):
            
            # Execute test
            result = self.service._is_compilation_current(graph_name, csv_path)
            
            # Verify result
            self.assertFalse(result)
    
    def test_is_compilation_current_missing_csv_file(self):
        """Test _is_compilation_current() when CSV file doesn't exist."""
        # Prepare test data
        graph_name = "csv_missing_test"
        csv_path = Path("nonexistent/missing.csv")
        output_path = Path("compiled/csv_missing_test.pkl")
        
        # Mock the internal method calls using proper global patching
        def mock_exists(self):
            if str(self) == str(output_path):
                return True
            elif str(self) == str(csv_path):
                return False
            return True
        
        with patch.object(self.service, '_get_output_path', return_value=output_path), \
             patch('pathlib.Path.exists', mock_exists):
            
            # Execute test
            result = self.service._is_compilation_current(graph_name, csv_path)
            
            # Verify result (returns True when CSV doesn't exist)
            self.assertTrue(result)
    
    def test_get_output_path_default_directory(self):
        """Test _get_output_path() with default output directory."""
        # Configure app config to return proper Path objects instead of strings
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("default_compiled")
        self.mock_app_config_service.compiled_graphs_path = Path("default_compiled")
        
        # Execute test
        result = self.service._get_output_path("test_graph")
        
        # Verify result
        expected = Path("default_compiled/test_graph.pkl")
        self.assertEqual(result, expected)
    
    def test_get_output_path_custom_directory(self):
        """Test _get_output_path() with custom output directory."""
        # Execute test with custom directory
        custom_dir = Path("custom/output")
        result = self.service._get_output_path("test_graph", custom_dir)
        
        # Verify result
        expected = Path("custom/output/test_graph.pkl")
        self.assertEqual(result, expected)
    
    def test_get_source_path_default_directory(self):
        """Test _get_source_path() with default output directory."""
        # Configure app config
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("default_compiled")
        self.mock_app_config_service.compiled_graphs_path = Path("default_compiled")
        
        # Execute test
        result = self.service._get_source_path("test_graph")
        
        # Verify result
        expected = Path("default_compiled/test_graph.src")
        self.assertEqual(result, expected)
    
    def test_get_source_path_custom_directory(self):
        """Test _get_source_path() with custom output directory."""
        # Execute test with custom directory
        custom_dir = Path("custom/source")
        result = self.service._get_source_path("test_graph", custom_dir)
        
        # Verify result
        expected = Path("custom/source/test_graph.src")
        self.assertEqual(result, expected)
    
    # =============================================================================
    # 8. Agent Creation and Error Handling Tests
    # =============================================================================
    
    def test_create_agent_instance_success(self):
        """Test _create_agent_instance() creates proper agent."""
        # Prepare test data
        mock_node = Mock()
        mock_node.name = "test_node"
        mock_node.inputs = ["input1", "input2"]
        mock_node.output = "output1"
        mock_node.description = "Test node description"
        mock_node.prompt = "Test prompt for agent"
        
        graph_name = "test_graph"
        
        # Mock agent creation dependencies
        with patch('agentmap.agents.builtins.default_agent.DefaultAgent') as mock_agent_class, \
             patch('agentmap.services.state_adapter_service.StateAdapterService') as mock_state_adapter, \
             patch.object(self.service, '_get_execution_tracker') as mock_get_tracker:
            
            # Configure mocks
            mock_agent_instance = Mock()
            mock_agent_class.return_value = mock_agent_instance
            mock_state_adapter_instance = Mock()
            mock_state_adapter.return_value = mock_state_adapter_instance
            mock_tracker = Mock()
            mock_get_tracker.return_value = mock_tracker
            
            # Execute test
            result = self.service._create_agent_instance(mock_node, graph_name)
            
            # Verify agent creation
            self.assertEqual(result, mock_agent_instance)
            
            # Verify agent was created with correct parameters
            mock_agent_class.assert_called_once()
            agent_call_args = mock_agent_class.call_args
            
            # Verify agent initialization parameters
            self.assertEqual(agent_call_args[1]["name"], "test_node")
            self.assertEqual(agent_call_args[1]["prompt"], "Test prompt for agent")
            self.assertEqual(agent_call_args[1]["logger"], self.mock_logger)
            self.assertEqual(agent_call_args[1]["execution_tracker_service"], mock_tracker)
            self.assertEqual(agent_call_args[1]["state_adapter_service"], mock_state_adapter_instance)
            
            # Verify context was created correctly
            context = agent_call_args[1]["context"]
            self.assertEqual(context["input_fields"], ["input1", "input2"])
            self.assertEqual(context["output_field"], "output1")
            self.assertEqual(context["description"], "Test node description")
    
    def test_get_execution_tracker_minimal(self):
        """Test _get_execution_tracker() creates minimal tracker for compilation."""
        # Mock ExecutionTracker from the models module
        with patch('agentmap.models.execution_tracker.ExecutionTracker') as mock_tracker_class:
            
            # Configure mock
            mock_tracker_instance = Mock()
            mock_tracker_class.return_value = mock_tracker_instance
            
            # Execute test
            result = self.service._get_execution_tracker()
            
            # Verify tracker creation
            self.assertEqual(result, mock_tracker_instance)
            
            # Verify minimal configuration
            mock_tracker_class.assert_called_once_with(
                track_inputs=False,
                track_outputs=False,
                minimal_mode=True
            )
    
    def test_compile_graph_agent_creation_error(self):
        """Test compile_graph() handles agent creation errors."""
        # Prepare test data
        graph_name = "agent_error_graph"
        
        # Configure graph definition service
        mock_graph = Mock()
        mock_graph.nodes = {"error_node": Mock(name="error_node")}
        
        self.mock_graph_definition_service.build_from_csv.side_effect = None
        self.mock_graph_definition_service.build_from_csv.return_value = mock_graph
        
        # Configure node registry
        self.mock_node_registry_service.prepare_for_assembly.side_effect = None
        self.mock_node_registry_service.prepare_for_assembly.return_value = {"error_node": Mock()}
        
        # Configure agent creation to raise exception
        agent_error = ImportError("Missing agent dependencies: DefaultAgent not available")
        
        # Mock file operations and current compilation check
        with patch('os.makedirs'), \
             patch('builtins.open', unittest.mock.mock_open(read_data="test,csv")), \
             patch.object(self.service, '_is_compilation_current', return_value=False), \
             patch.object(self.service, '_create_agent_instance', side_effect=agent_error):
            
            # Execute test
            result = self.service.compile_graph(graph_name)
            
            # Verify failure result
            self.assertFalse(result.success)
            self.assertEqual(result.graph_name, graph_name)
            self.assertIn("Missing agent dependencies", result.error)
            
            # Verify error logging
            logger_calls = self.mock_logger.calls
            error_calls = [call for call in logger_calls if call[0] == "error"]
            self.assertTrue(any("Failed to compile graph agent_error_graph" in call[1] for call in error_calls))


if __name__ == '__main__':
    unittest.main()
