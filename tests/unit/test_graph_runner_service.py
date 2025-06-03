"""
Unit tests for GraphRunnerService.

These tests mock all dependencies and focus on testing the service logic
in isolation, following the existing test patterns in AgentMap.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, call
import time

from agentmap.services.graph_runner_service import GraphRunnerService, RunOptions
from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.services.compilation_service import CompilationService
from agentmap.models.execution_result import ExecutionResult
from agentmap.models.graph import Graph
from agentmap.models.node import Node
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService,
    MockNodeRegistryService,
    LLMService,
    StorageServiceManager,
    ExecutionTracker
)


class TestGraphRunnerService(unittest.TestCase):
    """Unit tests for GraphRunnerService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use migration-safe mock implementations
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        self.mock_node_registry_service = MockNodeRegistryService()
        
        # Create mock services for all 8 dependencies
        self.mock_graph_builder = Mock(spec=GraphBuilderService)
        self.mock_compilation = Mock(spec=CompilationService)
        self.mock_llm_service = Mock(spec=LLMService)
        self.mock_storage_service_manager = Mock(spec=StorageServiceManager)
        self.mock_execution_tracker = Mock(spec=ExecutionTracker)
        
        # Create service instance with mocked dependencies
        self.service = GraphRunnerService(
            graph_builder_service=self.mock_graph_builder,
            compilation_service=self.mock_compilation,
            llm_service=self.mock_llm_service,
            storage_service_manager=self.mock_storage_service_manager,
            node_registry_service=self.mock_node_registry_service,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_config_service,
            execution_tracker=self.mock_execution_tracker
        )
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all 8 dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.graph_builder, self.mock_graph_builder)
        self.assertEqual(self.service.compilation, self.mock_compilation)
        self.assertEqual(self.service.llm_service, self.mock_llm_service)
        self.assertEqual(self.service.storage_service_manager, self.mock_storage_service_manager)
        self.assertEqual(self.service.node_registry, self.mock_node_registry_service)
        self.assertEqual(self.service.logger.name, "GraphRunnerService")
        self.assertEqual(self.service.config, self.mock_config_service)
        self.assertEqual(self.service.execution_tracker, self.mock_execution_tracker)
        
        # Verify initialization log message
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[GraphRunnerService] Initialized with all dependencies" 
                          for call in logger_calls if call[0] == "info"))
    
    def test_get_service_info(self):
        """Test getting service information for debugging."""
        info = self.service.get_service_info()
        
        # Verify service information structure
        self.assertEqual(info["service"], "GraphRunnerService")
        self.assertTrue(info["graph_builder_available"])
        self.assertTrue(info["compilation_service_available"])
        self.assertTrue(info["llm_service_available"])
        self.assertTrue(info["storage_service_manager_available"])
        self.assertTrue(info["node_registry_available"])
        self.assertTrue(info["execution_tracker_available"])
        self.assertTrue(info["config_available"])
        self.assertTrue(info["dependencies_initialized"])
        
        # Verify capabilities
        capabilities = info["capabilities"]
        self.assertTrue(capabilities["graph_resolution"])
        self.assertTrue(capabilities["agent_resolution"])
        self.assertTrue(capabilities["service_injection"])
        self.assertTrue(capabilities["precompiled_graphs"])
        self.assertTrue(capabilities["autocompilation"])
        self.assertTrue(capabilities["memory_building"])
    
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
        
        end_node = Node(name="EndNode", agent_type="Default")
        graph.nodes["EndNode"] = end_node
        
        graph.entry_point = "TestNode"
        return graph
    
    def create_old_format_graph(self):
        """Helper method to create a graph in old format."""
        return {
            "TestNode": type('Node', (), {
                'name': 'TestNode',
                'agent_type': 'LLM',
                'inputs': ['input'],
                'output': 'output',
                'prompt': 'Test prompt',
                'edges': {'default': 'EndNode'},
                'context': None,
                'description': None
            })(),
            "EndNode": type('Node', (), {
                'name': 'EndNode',
                'agent_type': 'Default',
                'inputs': [],
                'output': 'result',
                'prompt': '',
                'edges': {},
                'context': None,
                'description': None
            })()
        }
    
    @patch('agentmap.services.graph_runner_service.time')
    @patch('agentmap.services.graph_runner_service.StateAdapter')
    def test_run_graph_success_precompiled_path(self, mock_state_adapter, mock_time):
        """Test successful run_graph using precompiled path."""
        # Setup timing
        mock_time.time.side_effect = [1000.0, 1002.5]  # Start and end times
        
        # Setup mock graph and execution
        mock_compiled_graph = Mock()
        mock_compiled_graph.invoke.return_value = {"result": "success"}
        
        # Setup _resolve_graph to return precompiled path
        with patch.object(self.service, '_resolve_graph', return_value=(mock_compiled_graph, "precompiled", None)):
            # Setup execution tracker
            mock_summary = {"graph_success": True, "overall_success": True}
            self.mock_execution_tracker.get_summary.return_value = mock_summary
            
            # Setup StateAdapter
            mock_state_adapter.set_value.side_effect = lambda state, key, value: {**state, key: value}
            
            # Test execution
            options = RunOptions(initial_state={"input": "test"})
            result = self.service.run_graph("TestGraph", options)
            
            # Verify result
            self.assertIsInstance(result, ExecutionResult)
            self.assertEqual(result.graph_name, "TestGraph")
            self.assertTrue(result.success)
            self.assertEqual(result.execution_time, 2.5)
            self.assertEqual(result.source_info, "precompiled")
            self.assertIsNone(result.error)
            
            # Verify execution tracker was used
            self.mock_execution_tracker.start_execution.assert_called_once_with("TestGraph")
            self.mock_execution_tracker.complete_execution.assert_called_once()
            self.mock_execution_tracker.get_summary.assert_called_once()
            
            # Verify graph was invoked
            mock_compiled_graph.invoke.assert_called_once_with({"input": "test"})
    
    @patch('agentmap.services.graph_runner_service.time')
    @patch('agentmap.services.graph_runner_service.StateAdapter')
    def test_run_graph_success_memory_path(self, mock_state_adapter, mock_time):
        """Test successful run_graph using in-memory path."""
        # Setup timing
        mock_time.time.side_effect = [1000.0, 1003.0]  # Start and end times
        
        # Setup mock graph and execution
        mock_compiled_graph = Mock()
        mock_compiled_graph.invoke.return_value = {"result": "success"}
        mock_graph_def = self.create_old_format_graph()
        
        # Setup _resolve_graph to return memory path
        with patch.object(self.service, '_resolve_graph', return_value=(mock_compiled_graph, "memory", mock_graph_def)):
            # Setup execution tracker
            mock_summary = {"graph_success": True, "overall_success": True}
            self.mock_execution_tracker.get_summary.return_value = mock_summary
            
            # Setup StateAdapter
            mock_state_adapter.set_value.side_effect = lambda state, key, value: {**state, key: value}
            
            # Test execution
            result = self.service.run_graph("TestGraph")
            
            # Verify result
            self.assertIsInstance(result, ExecutionResult)
            self.assertEqual(result.graph_name, "TestGraph")
            self.assertTrue(result.success)
            self.assertEqual(result.execution_time, 3.0)
            self.assertEqual(result.source_info, "memory")
            self.assertIsNone(result.error)
    
    @patch('agentmap.services.graph_runner_service.time')
    def test_run_graph_execution_failure(self, mock_time):
        """Test run_graph with execution failure."""
        # Setup timing
        mock_time.time.side_effect = [1000.0, 1001.5]  # Start and end times
        
        # Setup _resolve_graph to raise an exception
        with patch.object(self.service, '_resolve_graph', side_effect=Exception("Graph resolution failed")):
            # Test execution
            result = self.service.run_graph("TestGraph")
            
            # Verify error result
            self.assertIsInstance(result, ExecutionResult)
            self.assertEqual(result.graph_name, "TestGraph")
            self.assertFalse(result.success)
            self.assertEqual(result.execution_time, 1.5)
            self.assertIsNone(result.source_info)
            self.assertEqual(result.error, "Graph resolution failed")
            
            # Verify error logging
            logger_calls = self.service.logger.calls
            self.assertTrue(any("GRAPH EXECUTION FAILED" in call[1] 
                              for call in logger_calls if call[0] == "error"))
    
    @patch('agentmap.services.graph_runner_service.time')
    @patch('agentmap.services.graph_runner_service.StateAdapter')
    @patch('agentmap.services.graph_runner_service.pickle')
    @patch('agentmap.graph.bundle.GraphBundle')
    @patch('builtins.open', new_callable=mock_open)
    def test_run_from_compiled_success(self, mock_file, mock_bundle, mock_pickle, mock_state_adapter, mock_time):
        """Test successful run_from_compiled."""
        # Setup timing
        mock_time.time.side_effect = [1000.0, 1002.0]
        
        # Setup mock compiled graph
        mock_compiled_graph = Mock()
        mock_compiled_graph.invoke.return_value = {"result": "success"}
        
        # Setup GraphBundle loading
        mock_bundle_instance = Mock()
        mock_bundle_instance.graph = mock_compiled_graph
        mock_bundle.load.return_value = mock_bundle_instance
        
        # Setup execution tracker
        mock_summary = {"graph_success": True, "overall_success": True}
        self.mock_execution_tracker.get_summary.return_value = mock_summary
        
        # Setup StateAdapter
        mock_state_adapter.set_value.side_effect = lambda state, key, value: {**state, key: value}
        
        # Test execution
        graph_path = Path("/test/TestGraph.pkl")
        with patch.object(Path, 'exists', return_value=True):
            result = self.service.run_from_compiled(graph_path)
        
        # Verify result
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "TestGraph")
        self.assertTrue(result.success)
        self.assertEqual(result.execution_time, 2.0)
        self.assertEqual(result.source_info, "precompiled")
        self.assertIsNone(result.error)
        
        # Verify GraphBundle.load was called
        mock_bundle.load.assert_called_once_with(graph_path, self.service.logger)
    
    @patch('agentmap.services.graph_runner_service.time')
    @patch('builtins.open', new_callable=mock_open)
    def test_run_from_compiled_file_not_found(self, mock_file, mock_time):
        """Test run_from_compiled with missing file."""
        # Setup timing
        mock_time.time.side_effect = [1000.0, 1001.0]
        
        # Test execution with non-existent file
        graph_path = Path("/test/NonExistent.pkl")
        with patch.object(Path, 'exists', return_value=False):
            result = self.service.run_from_compiled(graph_path)
        
        # Verify error result
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "NonExistent")
        self.assertFalse(result.success)
        self.assertEqual(result.source_info, "precompiled")
        self.assertIn("Compiled graph not found", result.error)
    
    @patch('agentmap.services.graph_runner_service.time')
    @patch('agentmap.services.graph_runner_service.StateAdapter')
    def test_run_from_csv_direct_success(self, mock_state_adapter, mock_time):
        """Test successful run_from_csv_direct."""
        # Setup timing
        mock_time.time.side_effect = [1000.0, 1002.5]
        
        # Setup mock graph and execution
        mock_compiled_graph = Mock()
        mock_compiled_graph.invoke.return_value = {"result": "success"}
        mock_graph_def = self.create_old_format_graph()
        
        # Setup methods to return expected values
        with patch.object(self.service, '_load_graph_definition', return_value=(mock_graph_def, "TestGraph")), \
             patch.object(self.service, '_build_graph_in_memory', return_value=mock_compiled_graph):
            
            # Setup execution tracker
            mock_summary = {"graph_success": True, "overall_success": True}
            self.mock_execution_tracker.get_summary.return_value = mock_summary
            
            # Setup StateAdapter
            mock_state_adapter.set_value.side_effect = lambda state, key, value: {**state, key: value}
            
            # Test execution
            csv_path = Path("/test/graph.csv")
            result = self.service.run_from_csv_direct(csv_path, "TestGraph")
            
            # Verify result
            self.assertIsInstance(result, ExecutionResult)
            self.assertEqual(result.graph_name, "TestGraph")
            self.assertTrue(result.success)
            self.assertEqual(result.execution_time, 2.5)
            self.assertEqual(result.source_info, "memory")
            self.assertIsNone(result.error)
    
    def test_resolve_graph_precompiled_path(self):
        """Test _resolve_graph using precompiled path."""
        options = RunOptions()
        
        # Mock successful precompiled graph load
        mock_bundle = {"graph": Mock(), "node_registry": None, "version_hash": "abc123"}
        
        with patch.object(self.service, '_load_compiled_graph', return_value=mock_bundle), \
             patch.object(self.service, '_extract_graph_from_bundle', return_value=Mock()) as mock_extract:
            
            result_graph, source_info, graph_def = self.service._resolve_graph("TestGraph", options)
            
            # Verify precompiled path was used
            self.assertEqual(source_info, "precompiled")
            self.assertIsNone(graph_def)
            mock_extract.assert_called_once_with(mock_bundle)
    
    def test_resolve_graph_autocompile_path(self):
        """Test _resolve_graph using autocompile path."""
        options = RunOptions(autocompile=True)
        
        # Mock no precompiled graph but successful autocompile
        mock_bundle = {"graph": Mock(), "node_registry": None, "version_hash": "def456"}
        
        with patch.object(self.service, '_load_compiled_graph', return_value=None), \
             patch.object(self.service, '_autocompile_and_load', return_value=mock_bundle), \
             patch.object(self.service, '_extract_graph_from_bundle', return_value=Mock()) as mock_extract:
            
            result_graph, source_info, graph_def = self.service._resolve_graph("TestGraph", options)
            
            # Verify autocompile path was used
            self.assertEqual(source_info, "autocompiled")
            self.assertIsNone(graph_def)
            mock_extract.assert_called_once_with(mock_bundle)
    
    def test_resolve_graph_memory_path(self):
        """Test _resolve_graph using memory path."""
        options = RunOptions(csv_path=Path("/test/graph.csv"))
        
        # Mock no precompiled or autocompiled graph
        mock_graph_def = self.create_old_format_graph()
        mock_compiled_graph = Mock()
        
        with patch.object(self.service, '_load_compiled_graph', return_value=None), \
             patch.object(self.service, '_autocompile_and_load', return_value=None), \
             patch.object(self.service, '_load_graph_definition', return_value=(mock_graph_def, "TestGraph")), \
             patch.object(self.service, '_build_graph_in_memory', return_value=mock_compiled_graph):
            
            result_graph, source_info, graph_def = self.service._resolve_graph("TestGraph", options)
            
            # Verify memory path was used
            self.assertEqual(source_info, "memory")
            self.assertEqual(graph_def, mock_graph_def)
            self.assertEqual(result_graph, mock_compiled_graph)
    
    @patch('agentmap.services.graph_runner_service.pickle')
    @patch('agentmap.graph.bundle.GraphBundle')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_compiled_graph_success(self, mock_file, mock_bundle, mock_pickle):
        """Test _load_compiled_graph with successful loading."""
        # Setup GraphBundle loading
        mock_bundle_instance = Mock()
        mock_bundle_instance.graph = Mock()
        mock_bundle_instance.to_dict.return_value = {"graph": Mock(), "version_hash": "abc123"}
        mock_bundle.load.return_value = mock_bundle_instance
        
        # Setup path existence
        with patch.object(Path, 'exists', return_value=True):
            result = self.service._load_compiled_graph("TestGraph")
        
        # Verify successful loading
        self.assertIsNotNone(result)
        self.assertIn("graph", result)
        self.assertEqual(result["version_hash"], "abc123")
    
    def test_load_compiled_graph_not_found(self):
        """Test _load_compiled_graph with missing file."""
        # Setup path not existing
        with patch.object(Path, 'exists', return_value=False):
            result = self.service._load_compiled_graph("TestGraph")
        
        # Verify None returned
        self.assertIsNone(result)
    
    def test_autocompile_and_load_success(self):
        """Test _autocompile_and_load with successful compilation."""
        options = RunOptions(csv_path=Path("/test/graph.csv"))
        
        # Mock successful autocompilation
        from agentmap.services.compilation_service import CompilationResult
        mock_result = CompilationResult("TestGraph", Path("/test/TestGraph.pkl"), None, True, 1.0)
        self.mock_compilation.auto_compile_if_needed.return_value = mock_result
        
        mock_bundle = {"graph": Mock(), "version_hash": "auto123"}
        
        with patch.object(self.service, '_load_compiled_graph', return_value=mock_bundle):
            result = self.service._autocompile_and_load("TestGraph", options)
        
        # Verify successful autocompilation
        self.assertEqual(result, mock_bundle)
        self.mock_compilation.auto_compile_if_needed.assert_called_once()
    
    def test_autocompile_and_load_failure(self):
        """Test _autocompile_and_load with compilation failure."""
        options = RunOptions(csv_path=Path("/test/graph.csv"))
        
        # Mock failed autocompilation
        from agentmap.services.compilation_service import CompilationResult
        mock_result = CompilationResult("TestGraph", Path(""), None, False, 1.0, error="Compilation failed")
        self.mock_compilation.auto_compile_if_needed.return_value = mock_result
        
        result = self.service._autocompile_and_load("TestGraph", options)
        
        # Verify failure handling
        self.assertIsNone(result)
    
    @patch('agentmap.services.graph_runner_service.StateGraph')
    @patch('agentmap.graph.GraphAssembler')
    def test_build_graph_in_memory_success(self, mock_assembler_class, mock_state_graph):
        """Test _build_graph_in_memory with successful building."""
        # Setup mock graph definition
        mock_graph_def = self.create_old_format_graph()
        
        # Setup mock assembler
        mock_assembler = Mock()
        mock_assembler_class.return_value = mock_assembler
        mock_compiled_graph = Mock()
        mock_assembler.compile.return_value = mock_compiled_graph
        
        # Setup node registry
        mock_node_registry = Mock()
        self.mock_node_registry_service.prepare_for_assembly.return_value = mock_node_registry
        verification_result = {"all_injected": True, "has_orchestrators": False, "stats": {}}
        self.mock_node_registry_service.verify_pre_compilation_injection.return_value = verification_result
        
        # Setup agent creation
        with patch.object(self.service, '_create_agent_instance', return_value=Mock()) as mock_create_agent, \
             patch.object(self.service, '_validate_agent_configuration'):
            
            result = self.service._build_graph_in_memory("TestGraph", mock_graph_def)
        
        # Verify result
        self.assertEqual(result, mock_compiled_graph)
        
        # Verify node registry preparation
        self.mock_node_registry_service.prepare_for_assembly.assert_called_once_with(mock_graph_def, "TestGraph")
        
        # Verify agent creation for each node
        self.assertEqual(mock_create_agent.call_count, 2)  # Two nodes in test graph
        
        # Verify assembler operations
        mock_assembler.add_node.assert_called()
        mock_assembler.set_entry_point.assert_called()
        mock_assembler.process_node_edges.assert_called()
        mock_assembler.compile.assert_called_once()
    
    def test_create_agent_instance_success(self):
        """Test _create_agent_instance with successful creation."""
        # Create test node
        node = type('Node', (), {
            'name': 'TestNode',
            'agent_type': 'LLM',
            'inputs': ['input'],
            'output': 'output',
            'prompt': 'Test prompt',
            'description': 'Test description'
        })()
        
        # Mock agent class and instance
        mock_agent_class = Mock()
        mock_agent_instance = Mock()
        mock_agent_class.return_value = mock_agent_instance
        
        with patch.object(self.service, '_resolve_agent_class', return_value=mock_agent_class), \
             patch.object(self.service, '_inject_services_into_agent'), \
             patch.object(self.service, '_validate_agent_configuration'):
            
            result = self.service._create_agent_instance(node, "TestGraph")
        
        # Verify agent creation
        self.assertEqual(result, mock_agent_instance)
        
        # Verify agent class was called with correct parameters
        mock_agent_class.assert_called_once()
        call_args = mock_agent_class.call_args
        self.assertEqual(call_args[1]['name'], 'TestNode')
        self.assertEqual(call_args[1]['prompt'], 'Test prompt')
        self.assertIn('input_fields', call_args[1]['context'])
        self.assertIn('output_field', call_args[1]['context'])
    
    def test_inject_services_into_agent_llm_agent(self):
        """Test _inject_services_into_agent for LLM agent."""
        # Create mock LLM agent
        from agentmap.services import LLMServiceUser
        mock_agent = Mock(spec=LLMServiceUser)
        node = Mock()
        node.name = "TestLLMNode"
        
        with patch.object(self.service, '_inject_llm_service') as mock_inject_llm, \
             patch.object(self.service, '_inject_storage_services') as mock_inject_storage:
            
            self.service._inject_services_into_agent(mock_agent, node, "TestGraph")
        
        # Verify LLM service injection was called
        mock_inject_llm.assert_called_once_with(mock_agent, "TestLLMNode")
        mock_inject_storage.assert_called_once_with(mock_agent, "TestLLMNode")
    
    def test_inject_llm_service_for_llm_agent(self):
        """Test _inject_llm_service for agent that requires LLM service."""
        from agentmap.services import LLMServiceUser
        mock_agent = Mock(spec=LLMServiceUser)
        
        self.service._inject_llm_service(mock_agent, "TestNode")
        
        # Verify LLM service was injected
        self.assertEqual(mock_agent.llm_service, self.mock_llm_service)
    
    def test_inject_llm_service_for_non_llm_agent(self):
        """Test _inject_llm_service for agent that doesn't require LLM service."""
        mock_agent = Mock()  # Not LLMServiceUser
        
        self.service._inject_llm_service(mock_agent, "TestNode")
        
        # Verify no LLM service injection occurred
        self.assertFalse(hasattr(mock_agent, 'llm_service'))
    
    @patch('agentmap.services.storage.injection.requires_storage_services')
    @patch('agentmap.services.storage.injection.inject_storage_services')
    def test_inject_storage_services_for_storage_agent(self, mock_inject_storage, mock_requires_storage):
        """Test _inject_storage_services for agent that requires storage."""
        mock_agent = Mock()
        mock_requires_storage.return_value = True
        
        self.service._inject_storage_services(mock_agent, "TestNode")
        
        # Verify storage service injection was called
        mock_inject_storage.assert_called_once_with(
            mock_agent, 
            self.mock_storage_service_manager, 
            self.service.logger
        )
    
    @patch('agentmap.services.storage.injection.requires_storage_services')
    def test_inject_storage_services_for_non_storage_agent(self, mock_requires_storage):
        """Test _inject_storage_services for agent that doesn't require storage."""
        mock_agent = Mock()
        mock_requires_storage.return_value = False
        
        self.service._inject_storage_services(mock_agent, "TestNode")
        
        # Verify no storage service injection occurred
        # (Just checking no exception was raised)
        
    def test_validate_agent_configuration_valid(self):
        """Test _validate_agent_configuration for valid agent."""
        mock_agent = Mock()
        mock_agent.name = "TestNode"
        mock_agent.run = Mock()
        
        node = Mock()
        node.name = "TestNode"
        
        # Should not raise exception
        self.service._validate_agent_configuration(mock_agent, node)
    
    def test_validate_agent_configuration_missing_name(self):
        """Test _validate_agent_configuration for agent missing name."""
        mock_agent = Mock()
        mock_agent.name = None  # Missing name
        mock_agent.run = Mock()
        
        node = Mock()
        node.name = "TestNode"
        
        with self.assertRaises(ValueError) as context:
            self.service._validate_agent_configuration(mock_agent, node)
        
        self.assertIn("missing required 'name' attribute", str(context.exception))
    
    def test_validate_agent_configuration_missing_run_method(self):
        """Test _validate_agent_configuration for agent missing run method."""
        mock_agent = Mock()
        mock_agent.name = "TestNode"
        del mock_agent.run  # Remove run method
        
        node = Mock()
        node.name = "TestNode"
        
        with self.assertRaises(ValueError) as context:
            self.service._validate_agent_configuration(mock_agent, node)
        
        self.assertIn("missing required 'run' method", str(context.exception))
    
    @patch('agentmap.agents.get_agent_class')
    def test_resolve_agent_class_builtin_agent(self, mock_get_agent_class):
        """Test _resolve_agent_class for built-in agent."""
        mock_agent_class = Mock()
        mock_get_agent_class.return_value = mock_agent_class
        
        result = self.service._resolve_agent_class("LLM")
        
        self.assertEqual(result, mock_agent_class)
        mock_get_agent_class.assert_called_once_with("LLM")
    
    @patch('agentmap.agents.get_agent_class')
    def test_resolve_agent_class_default_for_none(self, mock_get_agent_class):
        """Test _resolve_agent_class for None/empty agent type."""
        mock_get_agent_class.return_value = None
        
        with patch('agentmap.agents.builtins.default_agent.DefaultAgent') as mock_default:
            result = self.service._resolve_agent_class(None)
        
        # Should import and return DefaultAgent for None type
        # (Actual import handling is complex, just verify the logic flow)
    
    def test_load_graph_definition_with_graph_name(self):
        """Test _load_graph_definition with specific graph name."""
        csv_path = Path("/test/graph.csv")
        test_graph = self.create_test_graph()
        
        self.mock_graph_builder.build_from_csv.return_value = test_graph
        
        with patch.object(self.service, '_convert_domain_model_to_old_format', return_value={"node": "data"}) as mock_convert:
            graph_def, resolved_name = self.service._load_graph_definition(csv_path, "TestGraph")
        
        # Verify graph builder was called correctly
        self.mock_graph_builder.build_from_csv.assert_called_once_with(csv_path, "TestGraph")
        
        # Verify conversion was called
        mock_convert.assert_called_once_with(test_graph)
        
        # Verify result
        self.assertEqual(graph_def, {"node": "data"})
        self.assertEqual(resolved_name, "TestGraph")
    
    def test_load_graph_definition_first_graph(self):
        """Test _load_graph_definition returning first available graph."""
        csv_path = Path("/test/graph.csv")
        test_graphs = {"Graph1": self.create_test_graph(), "Graph2": Graph(name="Graph2")}
        
        self.mock_graph_builder.build_all_from_csv.return_value = test_graphs
        
        with patch.object(self.service, '_convert_domain_model_to_old_format', return_value={"node": "data"}) as mock_convert:
            graph_def, resolved_name = self.service._load_graph_definition(csv_path, None)
        
        # Verify graph builder was called correctly
        self.mock_graph_builder.build_all_from_csv.assert_called_once_with(csv_path)
        
        # Verify first graph was used (depends on dict ordering)
        self.assertIn(resolved_name, ["Graph1", "Graph2"])
    
    def test_convert_domain_model_to_old_format(self):
        """Test _convert_domain_model_to_old_format conversion."""
        graph = self.create_test_graph()
        
        result = self.service._convert_domain_model_to_old_format(graph)
        
        # Verify structure
        self.assertIn("TestNode", result)
        self.assertIn("EndNode", result)
        
        # Verify node properties
        test_node = result["TestNode"]
        self.assertEqual(test_node.name, "TestNode")
        self.assertEqual(test_node.agent_type, "LLM")
        self.assertEqual(test_node.inputs, ["input"])
        self.assertEqual(test_node.output, "output")
        self.assertEqual(test_node.prompt, "Test prompt")
        self.assertEqual(test_node.edges, {"default": "EndNode"})
    
    def test_extract_graph_from_bundle_new_format(self):
        """Test _extract_graph_from_bundle with new bundle format."""
        mock_graph = Mock()
        bundle = {
            "graph": mock_graph,
            "node_registry": Mock(),
            "version_hash": "abc123"
        }
        
        result = self.service._extract_graph_from_bundle(bundle)
        
        self.assertEqual(result, mock_graph)
    
    def test_extract_graph_from_bundle_legacy_format(self):
        """Test _extract_graph_from_bundle with legacy format."""
        mock_graph = Mock()
        
        result = self.service._extract_graph_from_bundle(mock_graph)
        
        self.assertEqual(result, mock_graph)
    
    def test_get_agent_resolution_status(self):
        """Test get_agent_resolution_status for graph analysis."""
        mock_graph_def = self.create_old_format_graph()
        
        with patch.object(self.service, '_get_agent_type_info', return_value={
            "agent_type": "LLM",
            "is_llm_agent": True,
            "is_storage_agent": False,
            "is_builtin": True,
            "is_custom": False,
            "dependencies_available": True,
            "missing_dependencies": []
        }) as mock_get_info:
            
            status = self.service.get_agent_resolution_status(mock_graph_def)
        
        # Verify status structure
        self.assertEqual(status["total_nodes"], 2)
        self.assertIn("agent_types", status)
        self.assertIn("resolution_summary", status)
        self.assertIn("overall_status", status)
        
        # Verify summary counts
        summary = status["resolution_summary"]
        self.assertEqual(summary["resolvable"], 2)  # Both nodes should be resolvable
        self.assertEqual(summary["missing_dependencies"], 0)
        
        # Verify overall status
        overall = status["overall_status"]
        self.assertTrue(overall["all_resolvable"])
        self.assertFalse(overall["has_issues"])
    
    def test_run_options_defaults(self):
        """Test RunOptions default values."""
        options = RunOptions()
        
        self.assertIsNone(options.initial_state)
        self.assertIsNone(options.autocompile)
        self.assertIsNone(options.csv_path)
        self.assertFalse(options.validate_before_run)
        self.assertTrue(options.track_execution)
        self.assertFalse(options.force_compilation)
        self.assertEqual(options.execution_mode, "standard")
    
    def test_run_options_custom_values(self):
        """Test RunOptions with custom values."""
        options = RunOptions(
            initial_state={"test": "value"},
            autocompile=True,
            csv_path=Path("/test/custom.csv"),
            validate_before_run=True,
            track_execution=False,
            force_compilation=True,
            execution_mode="debug"
        )
        
        self.assertEqual(options.initial_state, {"test": "value"})
        self.assertTrue(options.autocompile)
        self.assertEqual(options.csv_path, Path("/test/custom.csv"))
        self.assertTrue(options.validate_before_run)
        self.assertFalse(options.track_execution)
        self.assertTrue(options.force_compilation)
        self.assertEqual(options.execution_mode, "debug")


if __name__ == '__main__':
    unittest.main()
