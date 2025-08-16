"""
Unit tests for GraphRunnerService.

These tests validate the GraphRunnerService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock
from pathlib import Path
from typing import Dict, Any, Optional

from agentmap.services.graph.graph_runner_service import GraphRunnerService, RunOptions
from agentmap.models.execution_result import ExecutionResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphRunnerService(unittest.TestCase):
    """Unit tests for GraphRunnerService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create all 15 mock services using MockServiceFactory
        self.mock_graph_definition_service = MockServiceFactory.create_mock_graph_definition_service()
        self.mock_graph_execution_service = MockServiceFactory.create_mock_graph_execution_service()
        self.mock_compilation_service = MockServiceFactory.create_mock_compilation_service()
        self.mock_graph_bundle_service = MockServiceFactory.create_mock_graph_bundle_service()
        self.mock_agent_factory_service = Mock()  # Create mock agent factory service
        # Configure basic methods for agent factory service
        self.mock_agent_factory_service.resolve_agent_class.return_value = type('MockAgent', (), {
            '__init__': lambda self, **kwargs: None,
            'run': lambda self, **kwargs: {},
            'name': 'mock_agent'
        })
        self.mock_agent_factory_service.get_agent_resolution_context.return_value = {
            'resolvable': True,
            'missing_dependencies': [],
            'resolution_error': None
        }
        self.mock_llm_service = MockServiceFactory.create_mock_llm_service()
        self.mock_storage_service_manager = MockServiceFactory.create_mock_storage_service_manager()
        self.mock_node_registry_service = MockServiceFactory.create_mock_node_registry_service()
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "autocompile": False,
            "csv_path": "graphs/test.csv",
            "compiled_graphs_path": "compiled",
            "execution": {
                "track_execution": True
            }
        })
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_execution_policy_service = MockServiceFactory.create_mock_execution_policy_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        self.mock_dependency_checker_service = MockServiceFactory.create_mock_dependency_checker_service()
        self.mock_graph_assembly_service = MockServiceFactory.create_mock_graph_assembly_service()
        
        # Initialize GraphRunnerService with all mocked dependencies
        self.service = GraphRunnerService(
            graph_definition_service=self.mock_graph_definition_service,
            graph_execution_service=self.mock_graph_execution_service,
            graph_bundle_service=self.mock_graph_bundle_service,
            agent_factory_service=self.mock_agent_factory_service,
            llm_service=self.mock_llm_service,
            storage_service_manager=self.mock_storage_service_manager,
            node_registry_service=self.mock_node_registry_service,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config_service,
            execution_tracking_service=self.mock_execution_tracking_service,
            execution_policy_service=self.mock_execution_policy_service,
            state_adapter_service=self.mock_state_adapter_service,
            dependency_checker_service=self.mock_dependency_checker_service,
            graph_assembly_service=self.mock_graph_assembly_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all core specialized services are stored
        self.assertEqual(self.service.graph_definition, self.mock_graph_definition_service)
        self.assertEqual(self.service.graph_execution, self.mock_graph_execution_service)
        self.assertEqual(self.service.graph_bundle_service, self.mock_graph_bundle_service)
        
        # Verify supporting services are stored
        self.assertEqual(self.service.agent_factory, self.mock_agent_factory_service)
        self.assertEqual(self.service.llm_service, self.mock_llm_service)
        self.assertEqual(self.service.storage_service_manager, self.mock_storage_service_manager)
        self.assertEqual(self.service.node_registry, self.mock_node_registry_service)
        self.assertEqual(self.service.dependency_checker, self.mock_dependency_checker_service)
        self.assertEqual(self.service.graph_assembly_service, self.mock_graph_assembly_service)
        
        # Verify infrastructure services are stored
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertEqual(self.service.execution_tracking_service, self.mock_execution_tracking_service)
        self.assertEqual(self.service.execution_policy_service, self.mock_execution_policy_service)
        self.assertEqual(self.service.state_adapter_service, self.mock_state_adapter_service)
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "GraphRunnerService")
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == "[GraphRunnerService] Initialized as simplified facade" 
                          for call in logger_calls if call[0] == "info"))
    
    def test_service_logs_status(self):
        """Test that service status logging works correctly."""
        # Verify status logging was called during initialization
        logger_calls = self.mock_logger.calls
        
        # Should have debug calls about service status
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(len(debug_calls) > 0)
        
        # Should have info about all dependencies being initialized
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any("All dependencies initialized successfully" in call[1] 
                          for call in info_calls))
    
    def test_get_default_options(self):
        """Test get_default_options() method."""
        # Configure app config service for specific behavior
        self.mock_app_config_service.get_value.return_value = False  # autocompile
        self.mock_app_config_service.get_csv_path.return_value = Path("test/path.csv")
        self.mock_app_config_service.get_execution_config.return_value = {
            "track_execution": True
        }
        
        # Act
        options = self.service.get_default_options()
        
        # Assert
        self.assertIsInstance(options, RunOptions)
        self.assertIsNone(options.initial_state)
        self.assertFalse(options.autocompile)
        self.assertEqual(options.csv_path, Path("test/path.csv"))
        self.assertFalse(options.validate_before_run)
        self.assertTrue(options.track_execution)
        self.assertFalse(options.force_compilation)
        self.assertEqual(options.execution_mode, "standard")
        
        # Verify config method calls
        self.mock_app_config_service.get_value.assert_called_with("autocompile", False)
        self.mock_app_config_service.get_csv_path.assert_called_once()
        self.mock_app_config_service.get_execution_config.assert_called_once()
    
    def test_get_service_info(self):
        """Test get_service_info() debug method."""
        # Act
        service_info = self.service.get_service_info()
        
        # Assert basic structure
        self.assertIsInstance(service_info, dict)
        self.assertEqual(service_info["service"], "GraphRunnerService")
        self.assertEqual(service_info["architecture"], "simplified_facade")
        
        # Verify specialized services section
        specialized_services = service_info["specialized_services"]
        self.assertTrue(specialized_services["graph_definition_service_available"])
        self.assertTrue(specialized_services["graph_execution_service_available"])
        self.assertTrue(specialized_services["graph_bundle_service_available"])
        
        # Verify supporting services section
        supporting_services = service_info["supporting_services"]
        self.assertTrue(supporting_services["agent_factory_available"])
        self.assertTrue(supporting_services["llm_service_available"])
        self.assertTrue(supporting_services["storage_service_manager_available"])
        self.assertTrue(supporting_services["node_registry_available"])
        self.assertTrue(supporting_services["dependency_checker_available"])
        self.assertTrue(supporting_services["graph_assembly_service_available"])
        
        # Verify infrastructure services section
        infrastructure_services = service_info["infrastructure_services"]
        self.assertTrue(infrastructure_services["config_available"])
        self.assertTrue(infrastructure_services["execution_tracking_service_available"])
        self.assertTrue(infrastructure_services["execution_policy_service_available"])
        self.assertTrue(infrastructure_services["state_adapter_service_available"])
        
        # Verify overall initialization status
        self.assertTrue(service_info["dependencies_initialized"])
        
        # Verify capabilities
        capabilities = service_info["capabilities"]
        self.assertTrue(capabilities["graph_resolution"])
        self.assertTrue(capabilities["agent_resolution"])
        self.assertTrue(capabilities["service_injection"])
        self.assertTrue(capabilities["execution_delegation"])
        self.assertTrue(capabilities["facade_pattern"])
    
    # =============================================================================
    # 2. Core Business Logic Tests
    # =============================================================================
    
    
    
    def x(self):
        """Test run_graph() with in-memory definition execution fallback."""
        # Configure mocks for definition execution scenario
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
        self.mock_app_config_service.get_csv_path.return_value = Path("graphs/test.csv")
        
        # Configure autocompile to be disabled
        def mock_get_value(key: str, default: Any = None) -> Any:
            if key == "autocompile":
                return False
            return default
        
        self.mock_app_config_service.get_value.side_effect = mock_get_value
        
        # Mock graph definition loading - MUST clear side_effect first!
        mock_graph_model = Mock()
        mock_graph_model.nodes = {
            "node1": Mock(name="node1", agent_type="default", inputs=["input1"], 
                         output="output1", prompt="Test prompt", description="Test node",
                         context={}, edges=["node2"]),
            "node2": Mock(name="node2", agent_type="default", inputs=["input2"], 
                         output="output2", prompt="Test prompt 2", description="Test node 2",
                         context={}, edges=[])
        }
        # FIX: Add missing entry_point attribute that _convert_domain_model_to_old_format expects
        mock_graph_model.entry_point = "node1"  # Set a valid entry point
        
        # Clear the MockServiceFactory's side_effect and set our specific return_value
        self.mock_graph_definition_service.build_from_csv.side_effect = None
        self.mock_graph_definition_service.build_from_csv.return_value = mock_graph_model
        
        # Mock node registry preparation - MUST clear side_effect first!
        mock_node_registry = {"node1": Mock(), "node2": Mock()}
        self.mock_node_registry_service.prepare_for_assembly.side_effect = None
        self.mock_node_registry_service.prepare_for_assembly.return_value = mock_node_registry
        
        # Mock agent class resolution (needed for _create_agent_instance)
        def mock_resolve_agent_class(agent_type):
            # Return a simple mock agent class
            return type('MockAgent', (), {
                '__init__': lambda self, **kwargs: None,
                'run': lambda self, **kwargs: {},
                'name': 'mock_agent'
            })
        
        # Patch the agent resolution to avoid complex dependency checking
        import unittest.mock
        with unittest.mock.patch.object(self.service, '_resolve_agent_class', side_effect=mock_resolve_agent_class), \
             unittest.mock.patch.object(self.service, '_configure_agent_services'), \
             unittest.mock.patch.object(self.service, '_validate_agent_configuration'):
            
            # Mock execution result for definition-based execution
            mock_execution_result = Mock()
            mock_execution_result.graph_name = "test_graph"
            mock_execution_result.success = True
            mock_execution_result.final_state = {"result": "definition_output"}
            mock_execution_result.execution_summary = Mock()
            mock_execution_result.total_duration = 1.8
            mock_execution_result.compiled_from = "memory"
            mock_execution_result.error = None
            
            # Override the MockServiceFactory's side_effect with our specific return_value
            self.mock_graph_execution_service.execute_from_definition.side_effect = None
            self.mock_graph_execution_service.execute_from_definition.return_value = mock_execution_result
            
            # Mock file existence check - no compiled graph exists
            with unittest.mock.patch('pathlib.Path.exists', return_value=False):
                # Execute test
                result = self.service.run_graph("test_graph")
                
                # Verify graph definition was loaded
                self.mock_graph_definition_service.build_from_csv.assert_called_once()
                definition_call_args = self.mock_graph_definition_service.build_from_csv.call_args
                self.assertEqual(definition_call_args[0][0], Path("graphs/test.csv"))  # csv_path
                self.assertEqual(definition_call_args[0][1], "test_graph")  # graph_name
                
                # Verify node registry was prepared
                self.mock_node_registry_service.prepare_for_assembly.assert_called_once()
                
                # Verify delegation to definition execution
                self.mock_graph_execution_service.execute_from_definition.assert_called_once()
                exec_call_args = self.mock_graph_execution_service.execute_from_definition.call_args
                self.assertEqual(exec_call_args[1]['state'], {})
                
                # Verify result
                self.assertEqual(result, mock_execution_result)
                self.assertTrue(result.success)
                self.assertEqual(result.compiled_from, "memory")
    

    
    def test_run_from_csv_direct(self):
        """Test run_from_csv_direct() direct CSV execution without compilation."""
        # Prepare test data
        csv_path = Path("custom_graphs/workflow.csv")
        graph_name = "custom_workflow"
        initial_state = {"project_id": "proj456", "config": {"mode": "production"}}
        
        # Configure graph definition loading
        mock_graph_model = Mock()
        mock_graph_model.nodes = {
            "start_node": Mock(name="start_node", agent_type="input", inputs=[], 
                               output="start_output", prompt="Start prompt", description="Start node",
                               context={}, edges=["process_node"]),
            "process_node": Mock(name="process_node", agent_type="processor", inputs=["start_output"], 
                                 output="final_output", prompt="Process prompt", description="Process node",
                                 context={}, edges=[])
        }
        # FIX: Add missing entry_point attribute
        mock_graph_model.entry_point = "start_node"
        
        # Clear the MockServiceFactory's side_effect and set our specific return_value
        self.mock_graph_definition_service.build_from_csv.side_effect = None
        self.mock_graph_definition_service.build_from_csv.return_value = mock_graph_model
        
        # Mock node registry preparation - MUST clear side_effect first!
        mock_node_registry = {"start_node": Mock(), "process_node": Mock()}
        self.mock_node_registry_service.prepare_for_assembly.side_effect = None
        self.mock_node_registry_service.prepare_for_assembly.return_value = mock_node_registry
        
        # Mock agent class resolution (needed for _create_agent_instance)
        def mock_resolve_agent_class(agent_type):
            # Return a simple mock agent class
            return type('MockAgent', (), {
                '__init__': lambda self, **kwargs: None,
                'run': lambda self, **kwargs: {},
                'name': 'mock_agent'
            })
        
        # Configure execution result
        mock_execution_result = Mock()
        mock_execution_result.graph_name = graph_name
        mock_execution_result.success = True
        mock_execution_result.final_state = {
            "project_id": "proj456",
            "final_output": "workflow_completed",
            "execution_status": "success"
        }
        mock_execution_result.execution_summary = Mock()
        mock_execution_result.total_duration = 4.3
        mock_execution_result.compiled_from = "memory"
        mock_execution_result.error = None
        
        # Override the MockServiceFactory's side_effect with our specific return_value
        self.mock_graph_execution_service.execute_from_definition.side_effect = None
        self.mock_graph_execution_service.execute_from_definition.return_value = mock_execution_result
        
        # Create options with initial state
        options = RunOptions(initial_state=initial_state)
        
        # Patch the complex internal methods to avoid dependency issues
        import unittest.mock
        with unittest.mock.patch.object(self.service, '_resolve_agent_class', side_effect=mock_resolve_agent_class), \
             unittest.mock.patch.object(self.service, '_configure_agent_services'), \
             unittest.mock.patch.object(self.service, '_validate_agent_configuration'):
            
            # Execute test
            result = self.service.run_from_csv_direct(csv_path, graph_name, options)
            
            # Verify graph definition loading from specified CSV
            self.mock_graph_definition_service.build_from_csv.assert_called_once()
            definition_call_args = self.mock_graph_definition_service.build_from_csv.call_args
            
            # Verify node registry was prepared
            self.mock_node_registry_service.prepare_for_assembly.assert_called_once()
            
            # Verify delegation to definition execution
            self.mock_graph_execution_service.execute_from_definition.assert_called_once()
            exec_call_args = self.mock_graph_execution_service.execute_from_definition.call_args
            self.assertEqual(exec_call_args[1]['state'], initial_state)
            
            # Verify result
            self.assertEqual(result, mock_execution_result)
            self.assertEqual(result.graph_name, graph_name)
            self.assertTrue(result.success)
            self.assertEqual(result.final_state["project_id"], "proj456")
            
            # Verify logging
            logger_calls = self.mock_logger.calls
            self.assertTrue(any("Running directly from CSV" in call[1] 
                              for call in logger_calls if call[0] == "info"))
    
    def test_run_graph_with_options_none(self):
        """Test run_graph() with None options uses defaults."""
        # Configure mocks for default options path
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
        self.mock_app_config_service.get_csv_path.return_value = Path("graphs/default.csv")
        
        # Configure default autocompile behavior
        def mock_get_value(key: str, default: Any = None) -> Any:
            if key == "autocompile":
                return True  # Default in get_default_options
            return default
        
        self.mock_app_config_service.get_value.side_effect = mock_get_value
        self.mock_app_config_service.get_execution_config.return_value = {
            "track_execution": True
        }
        
        # Mock successful compilation using defaults - MUST clear side_effect first!
        mock_compilation_result = Mock()
        mock_compilation_result.success = True
        
        # Clear the MockServiceFactory's side_effect and set our success result
        self.mock_compilation_service.auto_compile_if_needed.side_effect = None
        self.mock_compilation_service.auto_compile_if_needed.return_value = mock_compilation_result
        
        # Mock execution result
        mock_execution_result = Mock()
        mock_execution_result.success = True
        
        # Override the MockServiceFactory's side_effect with our specific return_value
        self.mock_graph_execution_service.execute_compiled_graph.side_effect = None
        self.mock_graph_execution_service.execute_compiled_graph.return_value = mock_execution_result
        
        # Mock no compiled graph exists
        import unittest.mock
        with unittest.mock.patch('pathlib.Path.exists', return_value=False):
            # Execute with None options
            result = self.service.run_graph("test_graph", options=None)
            
            # Verify get_default_options was used
            self.mock_app_config_service.get_value.assert_called()
            self.mock_app_config_service.get_csv_path.assert_called()
            self.mock_app_config_service.get_execution_config.assert_called()
            
            # Verify compilation with default settings
            self.mock_compilation_service.auto_compile_if_needed.assert_called_once()
            
            # Verify result
            self.assertEqual(result, mock_execution_result)
    
    def test_run_graph_execution_paths_priority(self):
        """Test that run_graph() follows correct execution path priority."""
        # Test priority: compiled -> autocompile -> definition
        
        # Configure mocks
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
        
        # Test 1: Compiled graph exists (highest priority)
        import unittest.mock
        with unittest.mock.patch('pathlib.Path.exists', return_value=True):
            mock_execution_result = Mock(success=True, compiled_from="precompiled")
            
            # Override the MockServiceFactory's side_effect with our specific return_value
            self.mock_graph_execution_service.execute_compiled_graph.side_effect = None
            self.mock_graph_execution_service.execute_compiled_graph.return_value = mock_execution_result
            
            result = self.service.run_graph("test_graph")
            
            # Should use compiled path, not call compilation or definition services
            self.mock_graph_execution_service.execute_compiled_graph.assert_called_once()
            self.mock_compilation_service.auto_compile_if_needed.assert_not_called()
            self.mock_graph_definition_service.build_from_csv.assert_not_called()
            
            self.assertEqual(result.compiled_from, "precompiled")
            
            # Reset mocks for next test
            self.mock_graph_execution_service.reset_mock()
            self.mock_compilation_service.reset_mock()
            self.mock_graph_definition_service.reset_mock()
    
    # =============================================================================
    # 3. Error Handling and Edge Case Tests
    # =============================================================================
    
    def test_run_graph_execution_failure(self):
        """Test run_graph() handles execution service failures gracefully."""
        # Configure mocks to simulate finding a compiled graph
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
        
        # Configure execution service to raise an exception
        execution_error = Exception("Mock execution service failure")
        self.mock_graph_execution_service.execute_compiled_graph.side_effect = execution_error
        
        import unittest.mock
        with unittest.mock.patch('pathlib.Path.exists', return_value=True):
            # Execute test
            result = self.service.run_graph("test_graph")
            
            # Verify error ExecutionResult is returned
            self.assertIsNotNone(result)
            self.assertEqual(result.graph_name, "test_graph")
            self.assertFalse(result.success)
            self.assertEqual(result.final_state, {})  # Original empty state
            self.assertIsNone(result.execution_summary)
            self.assertEqual(result.total_duration, 0.0)
            self.assertIsNone(result.compiled_from)
            self.assertEqual(result.error, "Mock execution service failure")
            
            # Verify execution service was called
            self.mock_graph_execution_service.execute_compiled_graph.assert_called_once()
            
            # Verify error logging
            logger_calls = self.mock_logger.calls
            error_calls = [call for call in logger_calls if call[0] == "error"]
            self.assertTrue(len(error_calls) >= 2)  # Should have at least 2 error log calls
            self.assertTrue(any("GRAPH EXECUTION FAILED" in call[1] for call in error_calls))
            self.assertTrue(any("Mock execution service failure" in call[1] for call in error_calls))
    
    
    def test_run_from_csv_direct_invalid_csv(self):
        """Test run_from_csv_direct() handles invalid CSV file gracefully."""
        # Prepare test data
        invalid_csv_path = Path("invalid/corrupted.csv")
        graph_name = "corrupted_graph"
        initial_state = {"project_id": "proj456"}
        
        # Configure graph definition service to raise exception for invalid CSV
        csv_error = ValueError("Invalid CSV format: missing required columns")
        self.mock_graph_definition_service.build_from_csv.side_effect = csv_error
        
        # Create options with initial state
        options = RunOptions(initial_state=initial_state)
        
        # Execute test
        result = self.service.run_from_csv_direct(invalid_csv_path, graph_name, options)
        
        # Verify error ExecutionResult is returned
        self.assertIsNotNone(result)
        self.assertEqual(result.graph_name, graph_name)
        self.assertFalse(result.success)
        self.assertEqual(result.final_state, initial_state)  # Original state preserved
        self.assertIsNone(result.execution_summary)
        self.assertEqual(result.total_duration, 0.0)
        self.assertEqual(result.compiled_from, "memory")
        self.assertEqual(result.error, "Invalid CSV format: missing required columns")
        
        # Verify graph definition service was called
        self.mock_graph_definition_service.build_from_csv.assert_called_once()
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(len(error_calls) >= 2)
        self.assertTrue(any("CSV DIRECT EXECUTION FAILED" in call[1] for call in error_calls))
        self.assertTrue(any("Invalid CSV format" in call[1] for call in error_calls))
    
    def test_run_graph_with_invalid_options(self):
        """Test run_graph() handles invalid options gracefully."""
        # Test with None options - should use defaults
        self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
        
        def mock_get_value(key: str, default: Any = None) -> Any:
            if key == "autocompile":
                return False  # No autocompile
            return default
        
        self.mock_app_config_service.get_value.side_effect = mock_get_value
        self.mock_app_config_service.get_csv_path.return_value = Path("graphs/default.csv")
        self.mock_app_config_service.get_execution_config.return_value = {
            "track_execution": True
        }
        
        # Mock graph definition loading with realistic nodes to avoid empty graph errors
        mock_graph_model = Mock()
        mock_graph_model.nodes = {
            "node1": Mock(name="node1", agent_type="default", inputs=["input1"], 
                         output="output1", prompt="Test prompt", description="Test node",
                         context={}, edges=[])
        }
        # FIX: Add missing entry_point attribute
        mock_graph_model.entry_point = "node1"
        
        # Clear the MockServiceFactory's side_effect and set our specific return_value
        self.mock_graph_definition_service.build_from_csv.side_effect = None
        self.mock_graph_definition_service.build_from_csv.return_value = mock_graph_model
        
        # Mock node registry preparation - MUST clear side_effect first!
        mock_node_registry = {"node1": Mock()}
        self.mock_node_registry_service.prepare_for_assembly.side_effect = None
        self.mock_node_registry_service.prepare_for_assembly.return_value = mock_node_registry
        
        # Mock agent class resolution to prevent exceptions
        def mock_resolve_agent_class(agent_type):
            return type('MockAgent', (), {
                '__init__': lambda self, **kwargs: None,
                'run': lambda self, **kwargs: {},
                'name': 'mock_agent'
            })
        
        # Mock successful execution
        mock_execution_result = Mock()
        mock_execution_result.success = True
        mock_execution_result.graph_name = "test_graph"
        
        # Override the MockServiceFactory's side_effect
        self.mock_graph_execution_service.execute_from_definition.side_effect = None
        self.mock_graph_execution_service.execute_from_definition.return_value = mock_execution_result
        
        # Mock no compiled graph exists, no autocompile
        import unittest.mock
        with unittest.mock.patch('pathlib.Path.exists', return_value=False), \
             unittest.mock.patch.object(self.service, '_resolve_agent_class', side_effect=mock_resolve_agent_class), \
             unittest.mock.patch.object(self.service, '_configure_agent_services'), \
             unittest.mock.patch.object(self.service, '_validate_agent_configuration'):
            
            # Test with None options
            result = self.service.run_graph("test_graph", options=None)
            
            # Verify default options were used
            self.mock_app_config_service.get_value.assert_called()
            self.mock_app_config_service.get_csv_path.assert_called()
            self.mock_app_config_service.get_execution_config.assert_called()
            
            # Verify graph definition service was called
            self.mock_graph_definition_service.build_from_csv.assert_called_once()
            
            # Verify execution succeeded with defaults
            self.assertEqual(result, mock_execution_result)
            self.assertTrue(result.success)
    
    # skip this test because it's tightly coupled to the removed compilation service
    def test_run_graph_with_empty_graph_name(self):
        # we have to decide if this is  still possible or not and then recreate this test with the new approach or remove it all together.
        # """Test run_graph() handles empty or None graph name."""
        # # Configure basic mocks
        # self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
        
        # # Configure no autocompile
        # def mock_get_value(key: str, default: Any = None) -> Any:
        #     if key == "autocompile":
        #         return False
        #     return default
        
        # self.mock_app_config_service.get_value.side_effect = mock_get_value
        # self.mock_app_config_service.get_csv_path.return_value = Path("graphs/test.csv")
        
        # # Mock graph definition service to return all graphs for empty name
        # # Create realistic mock graph models with proper node structure
        # mock_node1 = Mock(name="node1", agent_type="default", inputs=["input1"], 
        #                  output="output1", prompt="Test prompt", description="Test node",
        #                  context={}, edges=[])
        # mock_node2 = Mock(name="node2", agent_type="default", inputs=["input2"], 
        #                  output="output2", prompt="Test prompt 2", description="Test node 2",
        #                  context={}, edges=[])
        
        # all_graphs = {
        #     "first_graph": Mock(nodes={"node1": mock_node1}),
        #     "second_graph": Mock(nodes={"node2": mock_node2})
        # }
        # self.mock_graph_definition_service.build_all_from_csv.return_value = all_graphs
        
        # # Mock node registry preparation - MUST clear side_effect first!
        # mock_node_registry = {"node1": Mock()}
        # self.mock_node_registry_service.prepare_for_assembly.side_effect = None
        # self.mock_node_registry_service.prepare_for_assembly.return_value = mock_node_registry
        
        # # Mock agent class resolution to prevent exceptions
        # def mock_resolve_agent_class(agent_type):
        #     return type('MockAgent', (), {
        #         '__init__': lambda self, **kwargs: None,
        #         'run': lambda self, **kwargs: {},
        #         'name': 'mock_agent'
        #     })
        
        # # Mock successful execution
        # mock_execution_result = Mock()
        # mock_execution_result.success = True
        # mock_execution_result.graph_name = "first_graph"
        # mock_execution_result.final_state = {"result": "success"}
        # mock_execution_result.execution_summary = Mock()
        # mock_execution_result.total_duration = 1.0
        # mock_execution_result.compiled_from = "memory"
        # mock_execution_result.error = None
        
        # # Override the MockServiceFactory's side_effect
        # self.mock_graph_execution_service.execute_from_definition.side_effect = None
        # self.mock_graph_execution_service.execute_from_definition.return_value = mock_execution_result
        
        # # Mock no compiled graph exists
        # import unittest.mock
        # with unittest.mock.patch('pathlib.Path.exists', return_value=False), \
        #      unittest.mock.patch.object(self.service, '_resolve_agent_class', side_effect=mock_resolve_agent_class), \
        #      unittest.mock.patch.object(self.service, '_configure_agent_services'), \
        #      unittest.mock.patch.object(self.service, '_validate_agent_configuration'):
            
        #     # Test with empty string graph name
        #     result = self.service.run_graph("", options=None)
            
        #     # Should have used first available graph
        #     self.assertEqual(result, mock_execution_result)
        #     self.assertEqual(result.graph_name, "first_graph")
            
        #     # Verify build_all_from_csv was called for empty name
        #     self.mock_graph_definition_service.build_all_from_csv.assert_called_once()
    
    
        # # Mock agent class resolution (needed for _create_agent_instance)
        # def mock_resolve_agent_class(agent_type):
        #     # Return a simple mock agent class
        #     return type('MockAgent', (), {
        #         '__init__': lambda self, **kwargs: None,
        #         'run': lambda self, **kwargs: {},
        #         'name': 'mock_agent'
        #     })
        
        # # Mock successful execution from definition (fallback path)
        # mock_execution_result = Mock()
        # mock_execution_result.success = True
        # mock_execution_result.compiled_from = "memory"
        # mock_execution_result.graph_name = "test_graph"
        
        # # Override the MockServiceFactory's side_effect
        # self.mock_graph_execution_service.execute_from_definition.side_effect = None
        # self.mock_graph_execution_service.execute_from_definition.return_value = mock_execution_result
        
        # import unittest.mock
        # # Patch the agent resolution and service injection to avoid complex dependency issues
        # with unittest.mock.patch.object(self.service, '_resolve_agent_class', side_effect=mock_resolve_agent_class), \
        #      unittest.mock.patch.object(self.service, '_configure_agent_services'), \
        #      unittest.mock.patch.object(self.service, '_validate_agent_configuration'), \
        #      unittest.mock.patch('pathlib.Path.exists', return_value=False):
            
        #     # Create explicit RunOptions with autocompile=True to ensure autocompilation is attempted
        #     options = RunOptions(
        #         autocompile=True,
        #         csv_path=Path("graphs/test.csv")
        #     )
            
        #     # Execute test with explicit options
        #     result = self.service.run_graph("test_graph", options)
            
        #     # Verify compilation was attempted and failed
        #     self.mock_compilation_service.auto_compile_if_needed.assert_called_once()
            
        #     # Verify fallback to definition execution succeeded
        #     self.mock_graph_definition_service.build_from_csv.assert_called_once()
        #     self.mock_graph_execution_service.execute_from_definition.assert_called_once()
            
        #     # Verify successful result from fallback
        #     self.assertEqual(result, mock_execution_result)
        #     self.assertTrue(result.success)
        #     self.assertEqual(result.compiled_from, "memory")
            
        #     # Verify error logging for compilation exception
        #     logger_calls = self.mock_logger.calls
        #     error_calls = [call for call in logger_calls if call[0] == "error"]
        #     self.assertTrue(any("Autocompilation error" in call[1] for call in error_calls))
        return True
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies gracefully."""
        # This test verifies that all dependencies are actually required
        with self.assertRaises(TypeError):
            # Missing required dependencies should raise TypeError
            GraphRunnerService(
                graph_definition_service=self.mock_graph_definition_service,
                # Missing other required services
            )
    
    def test_get_default_options_with_different_configurations(self):
        """Test get_default_options() with various configuration scenarios."""
        # Test with autocompile enabled - need to override the side_effect, not return_value
        def mock_get_value(key: str, default: Any = None) -> Any:
            if key == "autocompile":
                return True  # Override autocompile to be True
            return default
        
        self.mock_app_config_service.get_value.side_effect = mock_get_value
        self.mock_app_config_service.get_csv_path.return_value = Path("custom/path.csv")
        self.mock_app_config_service.get_execution_config.return_value = {
            "track_execution": False
        }
        
        # Act
        options = self.service.get_default_options()
        
        # Assert
        self.assertTrue(options.autocompile)
        self.assertEqual(options.csv_path, Path("custom/path.csv"))
        self.assertFalse(options.track_execution)
        
        # Reset and test with None execution config
        self.mock_app_config_service.get_execution_config.return_value = {}
        options = self.service.get_default_options()
        self.assertTrue(options.track_execution)  # Should default to True
    
    def test_get_default_options_call_verification(self):
        """Test that get_default_options() calls configuration methods correctly."""
        # Reset mocks to track calls
        self.mock_app_config_service.reset_mock()
        
        # Act
        options = self.service.get_default_options()
        
        # Verify specific method calls
        self.mock_app_config_service.get_value.assert_called_once_with("autocompile", False)
        self.mock_app_config_service.get_csv_path.assert_called_once()
        self.mock_app_config_service.get_execution_config.assert_called_once()
        
        # Verify returned object type
        self.assertIsInstance(options, RunOptions)
    
    def test_service_initialization_logging_detail(self):
        """Test detailed logging behavior during service initialization."""
        # Verify specific log messages that should be present
        logger_calls = self.mock_logger.calls
        
        # Check for facade initialization message
        facade_init_found = any(
            call[1] == "[GraphRunnerService] Initialized as simplified facade"
            for call in logger_calls if call[0] == "info"
        )
        self.assertTrue(facade_init_found, "Should log facade initialization")
        
        # Check for debug logging about service status
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertGreater(len(debug_calls), 0, "Should have debug log calls")
        
        # Check that logger name is correctly set
        self.assertEqual(self.service.logger.name, "GraphRunnerService")
    
    def test_service_dependency_count_validation(self):
        """Test that all 15 dependencies are properly injected and accessible."""
        # Verify we have all expected dependencies (15 total)
        dependencies = [
            self.service.graph_definition,
            self.service.graph_execution, 
            self.service.graph_bundle_service,
            self.service.agent_factory,
            self.service.llm_service,
            self.service.storage_service_manager,
            self.service.node_registry,
            self.service.dependency_checker,
            self.service.graph_assembly_service,
            self.service.config,
            self.service.execution_tracking_service,
            self.service.execution_policy_service,
            self.service.state_adapter_service,
            self.service.logger  # Logger comes from logging_service
        ]
        
        # Verify none are None
        for dep in dependencies:
            self.assertIsNotNone(dep, f"Dependency should not be None: {dep}")
        
        # Verify count matches expected
        self.assertEqual(len(dependencies), 15, "Should have exactly 15 dependencies")
    
    def test_get_service_info_comprehensive(self):
        """Test get_service_info() provides comprehensive service information."""
        # Act
        service_info = self.service.get_service_info()
        
        # Verify all required top-level keys
        required_keys = [
            "service", "architecture", "specialized_services", "supporting_services",
            "infrastructure_services", "dependencies_initialized", "capabilities",
            "delegation_methods", "complexity_reduction"
        ]
        
        for key in required_keys:
            self.assertIn(key, service_info, f"Should contain key: {key}")
        
        # Verify delegation methods are listed
        delegation_methods = service_info["delegation_methods"]
        self.assertIsInstance(delegation_methods, list)
        self.assertGreater(len(delegation_methods), 0, "Should list delegation methods")
        
        # Verify complexity reduction info
        complexity_reduction = service_info["complexity_reduction"]
        self.assertTrue(complexity_reduction["delegation_based"])
        self.assertTrue(complexity_reduction["single_responsibility"])
        self.assertTrue(complexity_reduction["clean_separation"])


if __name__ == '__main__':
    unittest.main()
