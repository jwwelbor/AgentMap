"""
Unit tests for GraphAssemblyService.

These tests validate the GraphAssemblyService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional
from pathlib import Path

from agentmap.services.graph_assembly_service import GraphAssemblyService
from agentmap.services.node_registry_service import NodeRegistryUser
from agentmap.models.node import Node
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphAssemblyService(unittest.TestCase):
    """Unit tests for GraphAssemblyService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create all required mock services using MockServiceFactory
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "execution": {
                "graph": {
                    "state_schema": "dict"
                }
            }
        })
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Create mocks for services not yet in MockServiceFactory
        self.mock_features_registry_service = Mock()
        self.mock_function_resolution_service = Mock()
        
        # Configure function resolution service methods
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        self.mock_function_resolution_service.load_function.return_value = Mock()
        
        # Initialize GraphAssemblyService with all mocked dependencies
        self.service = GraphAssemblyService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            state_adapter_service=self.mock_state_adapter_service,
            features_registry_service=self.mock_features_registry_service,
            function_resolution_service=self.mock_function_resolution_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertEqual(self.service.state_adapter, self.mock_state_adapter_service)
        self.assertEqual(self.service.features_registry, self.mock_features_registry_service)
        self.assertEqual(self.service.function_resolution, self.mock_function_resolution_service)
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, 'GraphAssemblyService')
        
        # Verify get_class_logger was called during initialization
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
        
        # Verify StateGraph builder is initialized
        self.assertIsNotNone(self.service.builder)
        
        # Verify internal state is initialized
        self.assertEqual(self.service.orchestrator_nodes, [])
        self.assertIsNone(self.service.node_registry)
        expected_stats = {"orchestrators_found": 0, "orchestrators_injected": 0, "injection_failures": 0}
        self.assertEqual(self.service.injection_stats, expected_stats)
    
    def test_get_state_schema_from_config_dict(self):
        """Test _get_state_schema_from_config() returns dict schema."""
        # Should use config value from setUp
        result = self.service._get_state_schema_from_config()
        self.assertEqual(result, dict)
    
    def test_get_state_schema_from_config_pydantic(self):
        """Test _get_state_schema_from_config() with pydantic schema."""
        # Mock pydantic availability and config
        self.mock_app_config_service.get_execution_config.return_value = {
            "graph": {"state_schema": "pydantic"}
        }
        
        with patch('pydantic.BaseModel') as mock_base_model:
            result = self.service._get_state_schema_from_config()
            self.assertEqual(result, mock_base_model)
    
    def test_get_state_schema_from_config_pydantic_not_available(self):
        """Test _get_state_schema_from_config() falls back when pydantic unavailable."""
        # Mock config for pydantic but import will fail
        self.mock_app_config_service.get_execution_config.return_value = {
            "graph": {"state_schema": "pydantic"}
        }
        
        with patch('builtins.__import__', side_effect=ImportError('No module named pydantic')):
            result = self.service._get_state_schema_from_config()
            self.assertEqual(result, dict)
            
            # Verify warning was logged
            logger_calls = self.mock_logger.calls
            warning_calls = [call for call in logger_calls if call[0] == "warning"]
            self.assertTrue(any("Pydantic requested but not available" in call[1] 
                              for call in warning_calls))
    
    def test_get_state_schema_from_config_unknown_schema(self):
        """Test _get_state_schema_from_config() falls back for unknown schema."""
        self.mock_app_config_service.get_execution_config.return_value = {
            "graph": {"state_schema": "unknown_schema"}
        }
        
        result = self.service._get_state_schema_from_config()
        self.assertEqual(result, dict)
        
        # Verify warning was logged
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("Unknown state schema type 'unknown_schema'" in call[1] 
                          for call in warning_calls))
    
    def test_get_state_schema_from_config_exception(self):
        """Test _get_state_schema_from_config() handles config exceptions."""
        self.mock_app_config_service.get_execution_config.side_effect = Exception("Config error")
        
        result = self.service._get_state_schema_from_config()
        self.assertEqual(result, dict)
        
        # Verify debug was logged
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Could not read state schema from config" in call[1] 
                          for call in debug_calls))
    
    # =============================================================================
    # 2. Core Graph Assembly Tests
    # =============================================================================
    
    def test_assemble_graph_basic_workflow(self):
        """Test assemble_graph() creates valid LangGraph from node definitions."""
        # Create mock nodes with agent instances
        mock_agent1 = Mock()
        mock_agent1.run = Mock(return_value={"result": "agent1_output"})
        mock_agent1.__class__.__name__ = "DefaultAgent"
        
        mock_agent2 = Mock()
        mock_agent2.run = Mock(return_value={"result": "agent2_output"})
        mock_agent2.__class__.__name__ = "DefaultAgent"
        
        # Create nodes with agent instances in context
        node1 = Node(name="node1", agent_type="default")
        node1.context = {"instance": mock_agent1}
        node1.edges = {"default": "node2"}
        
        node2 = Node(name="node2", agent_type="default")
        node2.context = {"instance": mock_agent2}
        
        # Create Graph object
        from agentmap.models.graph import Graph
        graph = Graph(name="test_graph")
        graph.nodes["node1"] = node1
        graph.nodes["node2"] = node2
        
        # Mock the StateGraph class and its methods
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        
        # Execute test
        with patch('agentmap.services.graph_assembly_service.StateGraph', return_value=mock_builder) as mock_state_graph:
            result = self.service.assemble_graph(graph)
            
            # Verify StateGraph was created with correct schema
            mock_state_graph.assert_called_once_with(state_schema=dict)
            
            # Verify nodes were added to LangGraph
            self.assertEqual(mock_builder.add_node.call_count, 2)
            mock_builder.add_node.assert_any_call("node1", mock_agent1.run)
            mock_builder.add_node.assert_any_call("node2", mock_agent2.run)
            
            # Verify edge was added
            mock_builder.add_edge.assert_called_once_with("node1", "node2")
            
            # Verify entry point was set to first node
            mock_builder.set_entry_point.assert_called_once_with("node1")
            
            # Verify compilation was called
            mock_builder.compile.assert_called_once()
            
            # Verify result is the compiled graph
            self.assertEqual(result, mock_compiled)
    
    def test_assemble_graph_with_node_registry_injection(self):
        """Test assemble_graph() injects node registry into orchestrator agents."""
        # Create orchestrator agent that implements NodeRegistryUser protocol
        class MockOrchestratorAgent:
            def __init__(self):
                self.node_registry = None
                
            def run(self, state):
                return {"result": "orchestrator_output"}
        
        # Make it appear as NodeRegistryUser
        MockOrchestratorAgent.__name__ = "OrchestratorAgent"
        
        mock_orchestrator = MockOrchestratorAgent()
        self.assertIsInstance(mock_orchestrator, NodeRegistryUser)
        
        # Create node with orchestrator agent
        node1 = Node(name="orchestrator_node", agent_type="orchestrator")
        node1.context = {"instance": mock_orchestrator}
        
        # Create Graph object
        from agentmap.models.graph import Graph
        graph = Graph(name="test_graph")
        graph.nodes["orchestrator_node"] = node1
        test_registry = {"node1": {"description": "Test node"}}
        
        # Mock the StateGraph class
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        
        # Execute test
        with patch('agentmap.services.graph_assembly_service.StateGraph', return_value=mock_builder):
            result = self.service.assemble_graph(graph, test_registry)
            
            # Verify registry was injected
            self.assertEqual(mock_orchestrator.node_registry, test_registry)
            
            # Verify injection stats
            expected_stats = {
                "orchestrators_found": 1,
                "orchestrators_injected": 1,
                "injection_failures": 0
            }
            self.assertEqual(self.service.injection_stats, expected_stats)
    
    def test_assemble_graph_registry_injection_failure(self):
        """Test assemble_graph() handles registry injection failures gracefully."""
        # Create orchestrator agent that will fail injection
        mock_orchestrator = Mock()
        mock_orchestrator.run = Mock(return_value={"result": "output"})
        mock_orchestrator.__class__.__name__ = "OrchestratorAgent"
        
        # Make setting node_registry raise an exception
        type(mock_orchestrator).node_registry = property(
            lambda self: None,
            lambda self, value: (_ for _ in ()).throw(AttributeError("Injection failed"))
        )
        
        node1 = Node(name="failing_orchestrator", agent_type="orchestrator")
        node1.context = {"instance": mock_orchestrator}
        
        # Create Graph object
        from agentmap.models.graph import Graph
        graph = Graph(name="test_graph")
        graph.nodes["failing_orchestrator"] = node1
        test_registry = {"node1": {"description": "Test node"}}
        
        # Mock the StateGraph class
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        
        # Execute test
        with patch('agentmap.services.graph_assembly_service.StateGraph', return_value=mock_builder):
            result = self.service.assemble_graph(graph, test_registry)
            
            # Verify injection failure was recorded
            expected_stats = {
                "orchestrators_found": 1,
                "orchestrators_injected": 0,
                "injection_failures": 1
            }
            self.assertEqual(self.service.injection_stats, expected_stats)
            
            # Verify error was logged
            logger_calls = self.mock_logger.calls
            error_calls = [call for call in logger_calls if call[0] == "error"]
            self.assertTrue(any("Failed to inject registry into 'failing_orchestrator'" in call[1] 
                              for call in error_calls))
    
    def test_assemble_graph_with_entry_point_detection(self):
        """Test assemble_graph() detects and uses proper entry points."""
        # Create nodes with entry point configuration
        node1 = Node(name="node1", agent_type="default")
        node1.context = {"instance": Mock()}
        node1._is_entry_point = True  # Node-level entry point marker
        
        node2 = Node(name="node2", agent_type="default")
        node2.context = {"instance": Mock()}
        
        # Create Graph object
        from agentmap.models.graph import Graph
        graph = Graph(name="test_graph")
        graph.nodes["node1"] = node1
        graph.nodes["node2"] = node2
        
        # Mock the StateGraph class
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        
        # Execute test
        with patch('agentmap.services.graph_assembly_service.StateGraph', return_value=mock_builder):
            result = self.service.assemble_graph(graph)
            
            # Verify node1 was set as entry point due to _is_entry_point marker
            mock_builder.set_entry_point.assert_called_once_with("node1")
    
    def test_assemble_graph_graph_level_entry_point(self):
        """Test assemble_graph() prioritizes graph-level entry point."""
        # Create nodes
        node1 = Node(name="node1", agent_type="default")
        node1.context = {"instance": Mock()}
        node1._is_entry_point = True  # Node-level entry point (should be ignored)
        
        node2 = Node(name="node2", agent_type="default")
        node2.context = {"instance": Mock()}
        
        # Create Graph object with entry point
        from agentmap.models.graph import Graph
        graph = Graph(name="test_graph", entry_point="node2")
        graph.nodes["node1"] = node1
        graph.nodes["node2"] = node2
        
        # Mock the StateGraph class
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        
        # Execute test
        with patch('agentmap.services.graph_assembly_service.StateGraph', return_value=mock_builder):
            result = self.service.assemble_graph(graph)
            
            # Verify node2 was set as entry point due to graph-level setting
            mock_builder.set_entry_point.assert_called_once_with("node2")
    
    def test_assemble_graph_fallback_entry_point(self):
        """Test assemble_graph() falls back to first node when no entry point specified."""
        # Create nodes without entry point markers
        node1 = Node(name="node1", agent_type="default")
        node1.context = {"instance": Mock()}
        
        node2 = Node(name="node2", agent_type="default")
        node2.context = {"instance": Mock()}
        
        # Create Graph object
        from agentmap.models.graph import Graph
        graph = Graph(name="test_graph")
        graph.nodes["node1"] = node1
        graph.nodes["node2"] = node2
        
        # Mock the StateGraph class
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        
        # Execute test
        with patch('agentmap.services.graph_assembly_service.StateGraph', return_value=mock_builder):
            result = self.service.assemble_graph(graph)
            
            # Verify first node was set as entry point (fallback behavior)
            mock_builder.set_entry_point.assert_called_once_with("node1")
            
            # Verify warning was logged
            logger_calls = self.mock_logger.calls
            warning_calls = [call for call in logger_calls if call[0] == "warning"]
            self.assertTrue(any("No entry point detected, using first node: 'node1'" in call[1] 
                              for call in warning_calls))
    
    def test_assemble_graph_with_logging_disabled(self):
        """Test assemble_graph() respects logger level settings."""
        node1 = Node(name="node1", agent_type="default")
        node1.context = {"instance": Mock()}
        
        # Create Graph object
        from agentmap.models.graph import Graph
        graph = Graph(name="test_graph")
        graph.nodes["node1"] = node1
        
        # Clear existing log calls
        self.mock_logger.calls.clear()
        
        # Mock the StateGraph class
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        
        # Set logger to WARNING level to suppress INFO and DEBUG
        import logging
        self.mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= logging.WARNING)
        
        # Mock the actual logging methods to respect the level check
        original_info = self.mock_logger.info
        original_debug = self.mock_logger.debug
        
        def conditional_info(msg, *args, **kwargs):
            if self.mock_logger.isEnabledFor(logging.INFO):
                return original_info(msg, *args, **kwargs)
        
        def conditional_debug(msg, *args, **kwargs):
            if self.mock_logger.isEnabledFor(logging.DEBUG):
                return original_debug(msg, *args, **kwargs)
        
        self.mock_logger.info = conditional_info
        self.mock_logger.debug = conditional_debug
        
        # Execute test with high logging threshold
        with patch('agentmap.services.graph_assembly_service.StateGraph', return_value=mock_builder):
            result = self.service.assemble_graph(graph)
            
            # Verify that INFO level calls were filtered out
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            
            # Should have no info or debug calls when logger level is WARNING+
            self.assertEqual(len(info_calls), 0)
            self.assertEqual(len(debug_calls), 0)
    
    # =============================================================================
    # 3. Node Addition and Agent Integration Tests
    # =============================================================================
    
    def test_add_node_with_agent_instance(self):
        """Test add_node() integrates agent instances properly."""
        mock_agent = Mock()
        mock_agent.run = Mock(return_value={"result": "test_output"})
        mock_agent.__class__.__name__ = "TestAgent"
        
        with patch.object(self.service, 'builder') as mock_builder:
            self.service.add_node("test_node", mock_agent)
            
            # Verify LangGraph add_node was called with agent's run method
            mock_builder.add_node.assert_called_once_with("test_node", mock_agent.run)
            
            # Verify logging
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertTrue(any("Added node: 'test_node' (TestAgent)" in call[1] 
                              for call in debug_calls))
    
    def test_add_node_orchestrator_with_registry_injection(self):
        """Test add_node() identifies and injects registry into orchestrator agents."""
        # Create orchestrator agent
        class MockOrchestratorAgent:
            def __init__(self):
                self.node_registry = None
                
            def run(self, state):
                return {"result": "orchestrator_output"}
        
        MockOrchestratorAgent.__name__ = "OrchestratorAgent"
        mock_orchestrator = MockOrchestratorAgent()
        
        # Set up service with node registry
        self.service.node_registry = {"node1": {"description": "Test node"}}
        
        with patch.object(self.service, 'builder') as mock_builder:
            self.service.add_node("orchestrator_node", mock_orchestrator)
            
            # Verify orchestrator was identified
            self.assertIn("orchestrator_node", self.service.orchestrator_nodes)
            
            # Verify registry was injected
            self.assertEqual(mock_orchestrator.node_registry, self.service.node_registry)
            
            # Verify injection stats
            self.assertEqual(self.service.injection_stats["orchestrators_found"], 1)
            self.assertEqual(self.service.injection_stats["orchestrators_injected"], 1)
            self.assertEqual(self.service.injection_stats["injection_failures"], 0)
    
    def test_add_node_orchestrator_without_registry(self):
        """Test add_node() handles orchestrator when no registry available."""
        class MockOrchestratorAgent:
            def __init__(self):
                self.node_registry = None
                
            def run(self, state):
                return {"result": "orchestrator_output"}
        
        MockOrchestratorAgent.__name__ = "OrchestratorAgent"
        mock_orchestrator = MockOrchestratorAgent()
        
        # No registry set on service
        self.service.node_registry = None
        
        with patch.object(self.service, 'builder') as mock_builder:
            self.service.add_node("orchestrator_node", mock_orchestrator)
            
            # Verify orchestrator was identified but no injection occurred
            self.assertIn("orchestrator_node", self.service.orchestrator_nodes)
            self.assertIsNone(mock_orchestrator.node_registry)
            
            # Verify stats reflect no injection attempt
            self.assertEqual(self.service.injection_stats["orchestrators_found"], 1)
            self.assertEqual(self.service.injection_stats["orchestrators_injected"], 0)
            self.assertEqual(self.service.injection_stats["injection_failures"], 0)
    
    def test_add_node_with_logging_disabled(self):
        """Test add_node() respects logger level settings."""
        mock_agent = Mock()
        mock_agent.__class__.__name__ = "TestAgent"
        
        # Clear existing log calls
        self.mock_logger.calls.clear()
        
        # Set logger to WARNING level to suppress DEBUG
        import logging
        self.mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= logging.WARNING)
        
        # Mock the actual logging methods to respect the level check
        original_debug = self.mock_logger.debug
        
        def conditional_debug(msg, *args, **kwargs):
            if self.mock_logger.isEnabledFor(logging.DEBUG):
                return original_debug(msg, *args, **kwargs)
        
        self.mock_logger.debug = conditional_debug
        
        with patch.object(self.service, 'builder') as mock_builder:
            self.service.add_node("test_node", mock_agent)
            
            # Verify no debug logging occurred
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertEqual(len(debug_calls), 0)
    
    # =============================================================================
    # 4. Edge Processing Tests
    # =============================================================================
    
    def test_process_node_edges_success_failure(self):
        """Test process_node_edges() handles success/failure routing."""
        edges = {"success": "success_node", "failure": "failure_node"}
        
        with patch.object(self.service, 'builder') as mock_builder:
            self.service.process_node_edges("source_node", edges)
            
            # Verify conditional edge was added
            mock_builder.add_conditional_edges.assert_called_once()
            args = mock_builder.add_conditional_edges.call_args[0]
            self.assertEqual(args[0], "source_node")
            
            # Test the routing function
            routing_func = args[1]
            
            # Test success routing
            success_state = {"last_action_success": True}
            self.assertEqual(routing_func(success_state), "success_node")
            
            # Test failure routing
            failure_state = {"last_action_success": False}
            self.assertEqual(routing_func(failure_state), "failure_node")
            
            # Verify logging
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertTrue(any("success → success_node / failure → failure_node" in call[1] 
                              for call in debug_calls))
    
    def test_process_node_edges_success_only(self):
        """Test process_node_edges() handles success-only routing."""
        edges = {"success": "success_node"}
        
        with patch.object(self.service, 'builder') as mock_builder:
            self.service.process_node_edges("source_node", edges)
            
            # Verify conditional edge was added
            mock_builder.add_conditional_edges.assert_called_once()
            args = mock_builder.add_conditional_edges.call_args[0]
            
            # Test the routing function
            routing_func = args[1]
            
            # Test success routing
            success_state = {"last_action_success": True}
            self.assertEqual(routing_func(success_state), "success_node")
            
            # Test no routing when failure
            failure_state = {"last_action_success": False}
            self.assertIsNone(routing_func(failure_state))
    
    def test_process_node_edges_failure_only(self):
        """Test process_node_edges() handles failure-only routing."""
        edges = {"failure": "failure_node"}
        
        with patch.object(self.service, 'builder') as mock_builder:
            self.service.process_node_edges("source_node", edges)
            
            # Verify conditional edge was added
            mock_builder.add_conditional_edges.assert_called_once()
            args = mock_builder.add_conditional_edges.call_args[0]
            
            # Test the routing function
            routing_func = args[1]
            
            # Test no routing when success
            success_state = {"last_action_success": True}
            self.assertIsNone(routing_func(success_state))
            
            # Test failure routing
            failure_state = {"last_action_success": False}
            self.assertEqual(routing_func(failure_state), "failure_node")
    
    def test_process_node_edges_default_routing(self):
        """Test process_node_edges() handles default (direct) routing."""
        edges = {"default": "next_node"}
        
        with patch.object(self.service.builder, 'add_edge') as mock_add_edge:
            self.service.process_node_edges("source_node", edges)
            
            # Verify direct edge was added
            mock_add_edge.assert_called_once_with("source_node", "next_node")
            
            # Verify logging
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertTrue(any("[source_node] → default → next_node" in call[1] 
                              for call in debug_calls))
    
    def test_process_node_edges_function_based_routing(self):
        """Test process_node_edges() handles function-based routing."""
        edges = {"func": "router_function", "success": "success_node", "failure": "failure_node"}
        
        # Configure function resolution service to detect function
        self.mock_function_resolution_service.extract_func_ref.return_value = "router_function"
        
        mock_router_func = Mock()
        self.mock_function_resolution_service.load_function.return_value = mock_router_func
        
        with patch.object(self.service.builder, 'add_conditional_edges') as mock_add_conditional:
            self.service.process_node_edges("source_node", edges)
            
            # Verify function was loaded
            self.mock_function_resolution_service.load_function.assert_called_once_with("router_function")
            
            # Verify conditional edge was added
            mock_add_conditional.assert_called_once()
            args = mock_add_conditional.call_args[0]
            self.assertEqual(args[0], "source_node")
            
            # Test the wrapped function
            wrapped_func = args[1]
            test_state = {"test": "value"}
            wrapped_func(test_state)
            
            # Verify original function was called with success/failure nodes
            mock_router_func.assert_called_once_with(test_state, "success_node", "failure_node")
            
            # Verify logging
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertTrue(any("routed by function 'router_function'" in call[1] 
                              for call in debug_calls))
    
    def test_process_node_edges_empty_edges(self):
        """Test process_node_edges() handles empty edges gracefully."""
        # Test with empty dict
        with patch.object(self.service.builder, 'add_edge') as mock_add_edge, \
             patch.object(self.service.builder, 'add_conditional_edges') as mock_add_conditional:
            
            self.service.process_node_edges("source_node", {})
            
            # Verify no edges were added
            mock_add_edge.assert_not_called()
            mock_add_conditional.assert_not_called()
        
        # Test with None
        with patch.object(self.service.builder, 'add_edge') as mock_add_edge, \
             patch.object(self.service.builder, 'add_conditional_edges') as mock_add_conditional:
            
            self.service.process_node_edges("source_node", None)
            
            # Verify no edges were added
            mock_add_edge.assert_not_called()
            mock_add_conditional.assert_not_called()
    
    def test_process_node_edges_with_logging_disabled(self):
        """Test process_node_edges() respects logger level settings."""
        edges = {"default": "next_node"}
        
        # Clear existing log calls
        self.mock_logger.calls.clear()
        
        # Set logger to WARNING level to suppress DEBUG
        import logging
        self.mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= logging.WARNING)
        
        # Mock the actual logging methods to respect the level check
        original_debug = self.mock_logger.debug
        
        def conditional_debug(msg, *args, **kwargs):
            if self.mock_logger.isEnabledFor(logging.DEBUG):
                return original_debug(msg, *args, **kwargs)
        
        self.mock_logger.debug = conditional_debug
        
        with patch.object(self.service.builder, 'add_edge'):
            self.service.process_node_edges("source_node", edges)
            
            # Verify no debug logging occurred
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertEqual(len(debug_calls), 0)
    
    # =============================================================================
    # 5. Entry Point Configuration Tests
    # =============================================================================
    
    def test_set_entry_point(self):
        """Test set_entry_point() configures LangGraph entry point."""
        with patch.object(self.service.builder, 'set_entry_point') as mock_set_entry:
            self.service.set_entry_point("start_node")
            
            # Verify LangGraph entry point was set
            mock_set_entry.assert_called_once_with("start_node")
            
            # Verify logging
            logger_calls = self.mock_logger.calls
            debug_calls = [call for call in logger_calls if call[0] == "debug"]
            self.assertTrue(any("Set entry point: 'start_node'" in call[1] 
                              for call in debug_calls))
    
    # =============================================================================
    # 6. Dynamic Router Tests
    # =============================================================================
    
    def test_add_dynamic_router(self):
        """Test _add_dynamic_router() adds state-based routing."""
        # Set up orchestrator nodes
        self.service.orchestrator_nodes = ["orchestrator1"]
        
        with patch.object(self.service.builder, 'add_conditional_edges') as mock_add_conditional:
            self.service._add_dynamic_router("orchestrator1")
            
            # Verify conditional edge was added
            mock_add_conditional.assert_called_once()
            args = mock_add_conditional.call_args[0]
            self.assertEqual(args[0], "orchestrator1")
            
            # Test the router function
            router_func = args[1]
            
            # Mock state adapter behavior
            def mock_get_value(state, key):
                return state.get(key)
            
            def mock_set_value(state, key, value):
                updated_state = state.copy()
                updated_state[key] = value
                return updated_state
            
            self.mock_state_adapter_service.get_value.side_effect = mock_get_value
            self.mock_state_adapter_service.set_value.side_effect = mock_set_value
            
            # Test router with next node specified
            state_with_next = {"__next_node": "target_node"}
            result = router_func(state_with_next)
            self.assertEqual(result, "target_node")
            
            # Verify state adapter was used to clear the next node
            self.mock_state_adapter_service.set_value.assert_called_with(state_with_next, "__next_node", None)
            
            # Test router with no next node
            state_without_next = {}
            result = router_func(state_without_next)
            self.assertIsNone(result)
    
    # =============================================================================
    # 7. Compilation Tests
    # =============================================================================
    
    def test_compile_success(self):
        """Test compile() successfully compiles LangGraph."""
        mock_compiled_graph = Mock()
        
        with patch.object(self.service.builder, 'compile', return_value=mock_compiled_graph) as mock_compile:
            result = self.service.compile()
            
            # Verify compilation was called
            mock_compile.assert_called_once()
            
            # Verify result is the compiled graph
            self.assertEqual(result, mock_compiled_graph)
            
            # Verify compilation logging
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            self.assertTrue(any("Compiling graph" in call[1] 
                              for call in info_calls))
    
    def test_compile_with_injection_stats_logging(self):
        """Test compile() logs injection statistics when orchestrators present."""
        # Set up injection stats
        self.service.injection_stats = {
            "orchestrators_found": 2,
            "orchestrators_injected": 2,
            "injection_failures": 0
        }
        
        with patch.object(self.service.builder, 'compile', return_value=Mock()):
            result = self.service.compile()
            
            # Verify injection stats were logged
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            self.assertTrue(any("Registry injection summary:" in call[1] 
                              for call in info_calls))
    
    def test_compile_with_logging_disabled(self):
        """Test compile() respects logger level settings."""
        # Clear existing log calls
        self.mock_logger.calls.clear()
        
        # Set logger to WARNING level to suppress INFO
        import logging
        self.mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= logging.WARNING)
        
        # Mock the actual logging methods to respect the level check
        original_info = self.mock_logger.info
        
        def conditional_info(msg, *args, **kwargs):
            if self.mock_logger.isEnabledFor(logging.INFO):
                return original_info(msg, *args, **kwargs)
        
        self.mock_logger.info = conditional_info
        
        with patch.object(self.service.builder, 'compile', return_value=Mock()):
            result = self.service.compile()
            
            # Verify no info logging occurred
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == "info"]
            self.assertEqual(len(info_calls), 0)
    
    # =============================================================================
    # 8. Injection Summary Tests
    # =============================================================================
    
    def test_get_injection_summary(self):
        """Test get_injection_summary() returns copy of injection statistics."""
        # Set up test stats
        test_stats = {
            "orchestrators_found": 3,
            "orchestrators_injected": 2,
            "injection_failures": 1
        }
        self.service.injection_stats = test_stats
        
        result = self.service.get_injection_summary()
        
        # Verify returned stats match
        self.assertEqual(result, test_stats)
        
        # Verify it's a copy (modifying return value doesn't affect original)
        result["orchestrators_found"] = 999
        self.assertEqual(self.service.injection_stats["orchestrators_found"], 3)
    
    # =============================================================================
    # 9. Error Handling and Edge Cases Tests
    # =============================================================================
    
    def test_assemble_graph_empty_graph_definition(self):
        """Test assemble_graph() handles empty graph definition with clear error."""
        # Create empty Graph object
        from agentmap.models.graph import Graph
        graph = Graph(name="empty_graph")
        
        # Empty graphs should raise ValueError with clear message
        with self.assertRaises(ValueError) as context:
            self.service.assemble_graph(graph)
        
        # Verify the error message is clear about the actual problem
        error_msg = str(context.exception)
        self.assertIn("has no nodes", error_msg)
        self.assertIn("empty_graph", error_msg)
    
    def test_assemble_graph_creates_fresh_builder(self):
        """Test assemble_graph() creates fresh StateGraph for each compilation."""
        # First assembly
        initial_builder = self.service.builder
        
        with patch.object(self.service, '_get_state_schema_from_config', return_value=dict), \
             patch('agentmap.services.graph_assembly_service.StateGraph') as mock_state_graph_class, \
             patch.object(self.service.builder, 'compile', return_value=Mock()):
            
            mock_builder = Mock()
            mock_state_graph_class.return_value = mock_builder
            
            # Create Graph object with one node (minimum for valid graph)
            from agentmap.models.graph import Graph
            from agentmap.models.node import Node
            graph = Graph(name="fresh_builder_test")
            
            # Add minimal node to make graph valid
            test_node = Node(name="test_node", agent_type="default")
            test_node.context = {"instance": Mock()}
            graph.nodes["test_node"] = test_node
            
            self.service.assemble_graph(graph)
            
            # Verify new StateGraph was created
            mock_state_graph_class.assert_called_with(state_schema=dict)
            
            # Verify stats were reset
            expected_stats = {"orchestrators_found": 0, "orchestrators_injected": 0, "injection_failures": 0}
            self.assertEqual(self.service.injection_stats, expected_stats)
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies gracefully."""
        # Test missing logging service
        with self.assertRaises(AttributeError) as context:
            GraphAssemblyService(
                app_config_service=self.mock_app_config_service,
                logging_service=None,
                state_adapter_service=self.mock_state_adapter_service,
                features_registry_service=self.mock_features_registry_service,
                function_resolution_service=self.mock_function_resolution_service
            )
        self.assertIn("'NoneType' object has no attribute 'get_class_logger'", str(context.exception))
        
        # Test missing config service - should fail during initialization
        with self.assertRaises(AttributeError) as context:
            GraphAssemblyService(
                app_config_service=None,
                logging_service=self.mock_logging_service,
                state_adapter_service=self.mock_state_adapter_service,
                features_registry_service=self.mock_features_registry_service,
                function_resolution_service=self.mock_function_resolution_service
            )
        # Should mention that None config cannot be used
        self.assertIn("'NoneType' object has no attribute 'get_functions_path'", str(context.exception))
    
    def test_service_initialization_with_completely_missing_arguments(self):
        """Test service handles completely missing arguments (TypeError)."""
        # Test with no arguments at all
        with self.assertRaises(TypeError) as context:
            GraphAssemblyService()
        
        # Should mention missing required positional arguments
        error_msg = str(context.exception)
        self.assertTrue(
            "missing" in error_msg and "required" in error_msg,
            f"Expected error about missing required arguments, got: {error_msg}"
        )
    
    def test_add_node_with_missing_run_method(self):
        """Test add_node() handles agents without run method."""
        mock_agent_without_run = Mock()
        del mock_agent_without_run.run  # Remove run method
        mock_agent_without_run.__class__.__name__ = "InvalidAgent"
        
        with patch.object(self.service.builder, 'add_node') as mock_add_node:
            # This should raise AttributeError when trying to access run method
            with self.assertRaises(AttributeError):
                self.service.add_node("invalid_node", mock_agent_without_run)
    
    def test_process_node_edges_invalid_function_reference(self):
        """Test process_node_edges() handles invalid function references."""
        edges = {"func": "invalid_function"}
        
        # Configure function resolution to detect but fail to load function
        self.mock_function_resolution_service.extract_func_ref.return_value = "invalid_function"
        self.mock_function_resolution_service.load_function.side_effect = FileNotFoundError("Function not found")
        
        # Should propagate the FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            self.service.process_node_edges("source_node", edges)
    
    def test_assemble_graph_integration_realistic_workflow(self):
        """Integration test with realistic workflow scenario."""
        # Create realistic agents
        class InputAgent:
            def run(self, state):
                return {"user_input": "Hello, world!"}
        
        class ProcessorAgent:
            def run(self, state):
                return {"processed_data": state.get("user_input", "").upper()}
        
        class OutputAgent:
            def run(self, state):
                return {"final_output": f"Result: {state.get('processed_data', '')}"}
        
        # Create nodes with realistic configuration
        input_node = Node(name="input", agent_type="input")
        input_node.context = {"instance": InputAgent()}
        input_node.edges = {"default": "processor"}
        
        processor_node = Node(name="processor", agent_type="default")
        processor_node.context = {"instance": ProcessorAgent()}
        processor_node.edges = {"success": "output", "failure": "error_handler"}
        
        output_node = Node(name="output", agent_type="output")
        output_node.context = {"instance": OutputAgent()}
        
        # Create Graph object
        from agentmap.models.graph import Graph
        graph = Graph(name="integration_test_graph")
        graph.nodes["input"] = input_node
        graph.nodes["processor"] = processor_node
        graph.nodes["output"] = output_node
        
        # Create mock builder to track calls
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        
        # Execute integration test by patching StateGraph constructor
        with patch('agentmap.services.graph_assembly_service.StateGraph', return_value=mock_builder) as mock_state_graph:
            result = self.service.assemble_graph(graph)
            
            # Verify StateGraph was created
            mock_state_graph.assert_called_once_with(state_schema=dict)
            
            # Verify all nodes were added
            self.assertEqual(mock_builder.add_node.call_count, 3)
            
            # Verify edges were processed
            mock_builder.add_edge.assert_called_once_with("input", "processor")  # Default edge
            mock_builder.add_conditional_edges.assert_called_once()  # Success/failure edge
            
            # Verify entry point was set
            mock_builder.set_entry_point.assert_called_once_with("input")
            
            # Verify compilation
            mock_builder.compile.assert_called_once()
            self.assertEqual(result, mock_compiled)


if __name__ == '__main__':
    unittest.main()
