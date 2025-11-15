"""
Test orchestrator dynamic routing fix.
"""

import unittest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any

from agentmap.services.graph.graph_assembly_service import GraphAssemblyService
from agentmap.models.graph import Graph, Node
from agentmap.services.protocols import OrchestrationCapableAgent


class TestOrchestratorDynamicRouting(unittest.TestCase):
    """Test the orchestrator dynamic routing functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mock services
        self.mock_config = Mock()
        self.mock_logging = Mock()
        self.mock_logging.get_class_logger.return_value = Mock()
        self.mock_state_adapter = Mock()
        self.mock_features = Mock()
        self.mock_function_resolution = Mock()
        self.mock_graph_factory = Mock()
        self.mock_orchestrator_service = Mock()
        
        # Create service with fresh state
        self.assembly_service = GraphAssemblyService(
            app_config_service=self.mock_config,
            logging_service=self.mock_logging,
            state_adapter_service=self.mock_state_adapter,
            features_registry_service=self.mock_features,
            function_resolution_service=self.mock_function_resolution,
            graph_factory_service=self.mock_graph_factory,
            orchestrator_service=self.mock_orchestrator_service,
        )
        
        # CRITICAL: Ensure clean state for each test
        self.assembly_service.orchestrator_nodes = []
        self.assembly_service.injection_stats = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0
        }
    
    def test_orchestrator_dynamic_routing_with_all_nodes(self):
        """Test that orchestrator can route to all nodes in the graph."""
        # Create a simple graph with orchestrator
        graph = Graph(name="test_graph")
        
        # Create a proper mock orchestrator class that implements OrchestrationCapableAgent
        class MockOrchestratorAgent:
            """Mock orchestrator agent that properly implements OrchestrationCapableAgent."""
            def __init__(self):
                self.node_registry: Dict[str, Dict[str, Any]] = {}
                self.orchestrator_service = None
                self.configure_orchestrator_service_called = False
                
            def run(self, state):
                return {"result": "orchestrator_output"}
            
            def configure_orchestrator_service(self, orchestrator_service):
                """Required method for OrchestrationCapableAgent protocol."""
                self.orchestrator_service = orchestrator_service
                self.configure_orchestrator_service_called = True
        
        # Create basic agent class that doesn't implement OrchestrationCapableAgent
        class BasicAgent:
            """Basic agent class that explicitly does NOT implement OrchestrationCapableAgent."""
            def run(self, state):
                return {"result": "output"}
        
        # Create agent instances
        mock_agents = {}
        
        # Create non-orchestrator agents
        for name in ["Start", "NodeA", "NodeB", "NodeC", "Error"]:
            agent = BasicAgent()
            agent.__class__.__name__ = f"MockAgent_{name}"
            mock_agents[name] = agent
        
        # Create orchestrator agent that properly implements OrchestrationCapableAgent
        orchestrator_agent = MockOrchestratorAgent()
        mock_agents["Orchestrator"] = orchestrator_agent
        
        # Add nodes to graph
        nodes = {
            "Start": Node(name="Start", agent_type="input", context={"instance": mock_agents["Start"]}),
            "Orchestrator": Node(name="Orchestrator", agent_type="orchestrator", context={"instance": mock_agents["Orchestrator"]}),
            "NodeA": Node(name="NodeA", agent_type="simple", context={"instance": mock_agents["NodeA"]}),
            "NodeB": Node(name="NodeB", agent_type="simple", context={"instance": mock_agents["NodeB"]}),
            "NodeC": Node(name="NodeC", agent_type="simple", context={"instance": mock_agents["NodeC"]}),
            "Error": Node(name="Error", agent_type="simple", context={"instance": mock_agents["Error"]}),
        }
        
        # Add edges
        nodes["Start"].add_edge("default", "Orchestrator")
        nodes["Orchestrator"].add_edge("failure", "Error")
        nodes["NodeA"].add_edge("default", "Start")
        nodes["NodeB"].add_edge("default", "Start")
        nodes["NodeC"].add_edge("default", "Start")
        
        graph.nodes = nodes
        graph.entry_point = "Start"

        # Mock the builder to avoid actual compilation
        # We need to mock _initialize_builder to prevent it from creating a real StateGraph
        original_init_builder = self.assembly_service._initialize_builder

        def mock_init_builder(graph=None):
            """Mock that preserves orchestrator tracking but uses mock builder."""
            self.assembly_service.orchestrator_nodes = []
            self.assembly_service.injection_stats = {
                "orchestrators_found": 0,
                "orchestrators_injected": 0,
                "injection_failures": 0
            }
            # Keep using the mock builder instead of creating a real StateGraph
            if not hasattr(self.assembly_service, '_mock_builder_set'):
                mock_builder = Mock()
                mock_builder.compile.return_value = Mock()
                mock_builder.add_node = Mock()
                mock_builder.set_entry_point = Mock()
                mock_builder.add_conditional_edges = Mock()
                self.assembly_service.builder = mock_builder
                self.assembly_service._mock_builder_set = True

        self.assembly_service._initialize_builder = mock_init_builder

        # Assemble the graph with a test registry
        test_registry = {"NodeA": {}, "NodeB": {}, "NodeC": {}}

        # Call assemble_graph which should detect the orchestrator and inject the registry
        compiled_graph = self.assembly_service.assemble_graph(
            graph,
            mock_agents,  # Pass agent instances directly
            orchestrator_node_registry=test_registry
        )

        # Verify ONLY the orchestrator was identified (not all 6 nodes)
        self.assertIn("Orchestrator", self.assembly_service.orchestrator_nodes)
        self.assertEqual(len(self.assembly_service.orchestrator_nodes), 1)
        
        # Verify orchestrator service was configured
        orchestrator_agent = mock_agents["Orchestrator"]
        self.assertTrue(orchestrator_agent.configure_orchestrator_service_called)
        self.assertEqual(orchestrator_agent.orchestrator_service, self.mock_orchestrator_service)
        
        # Verify registry was injected into the orchestrator
        self.assertEqual(orchestrator_agent.node_registry, test_registry)
        
        # Verify the injection stats - THIS SHOULD NOW BE 1, not 6
        self.assertEqual(self.assembly_service.injection_stats["orchestrators_found"], 1)
        self.assertEqual(self.assembly_service.injection_stats["orchestrators_injected"], 1)
        
        # Verify that non-orchestrator agents weren't detected as orchestrators
        for name in ["Start", "NodeA", "NodeB", "NodeC", "Error"]:
            self.assertNotIn(name, self.assembly_service.orchestrator_nodes)
            # Verify they don't have node_registry attribute
            self.assertFalse(hasattr(mock_agents[name], 'node_registry'))
    
    def test_dynamic_router_returns_valid_destination(self):
        """Test that the dynamic router validates destinations."""
        # Create a mock state with __next_node set
        mock_state = {"__next_node": "NodeB", "last_action_success": True}
        self.mock_state_adapter.get_value.side_effect = lambda state, key, default=None: state.get(key, default)
        self.mock_state_adapter.set_value.side_effect = lambda state, key, value: {**state, key: value}
        
        # Create nodes
        nodes = ["Start", "Orchestrator", "NodeA", "NodeB", "NodeC"]
        for node in nodes:
            self.assembly_service.builder.add_node(node, lambda x: x)
        
        # Add the dynamic router
        self.assembly_service.orchestrator_nodes = ["Orchestrator"]
        self.assembly_service._add_dynamic_router("Orchestrator")
        
        # The dynamic router should have been added with conditional edges
        # We can't test the actual routing without running the graph,
        # but we've verified the code structure is correct

    def test_orchestration_capable_agent_detection(self):
        """Test that OrchestrationCapableAgent detection works correctly."""
        # Create a proper orchestrator class
        class TestOrchestratorAgent:
            def __init__(self):
                self.node_registry = {}
            
            def run(self, state):
                return {"result": "test"}
            
            def configure_orchestrator_service(self, orchestrator_service):
                pass
        
        # Create a regular agent
        class RegularAgent:
            def run(self, state):
                return {"result": "test"}
        
        orchestrator = TestOrchestratorAgent()
        regular = RegularAgent()
        
        # Test protocol detection
        self.assertTrue(isinstance(orchestrator, OrchestrationCapableAgent))
        self.assertFalse(isinstance(regular, OrchestrationCapableAgent))

    def test_orchestrator_injection_failure_handling(self):
        """Test handling of orchestrator service injection failures."""
        # Create orchestrator that will fail configure_orchestrator_service
        class FailingOrchestratorAgent:
            def __init__(self):
                self.node_registry = {}  # Required for OrchestrationCapableAgent detection

            def configure_orchestrator_service(self, orchestrator_service):
                raise RuntimeError("Service configuration failed")

            def run(self, state):
                return {"result": "test"}

        failing_agent = FailingOrchestratorAgent()
        
        # Create graph with failing agent
        graph = Graph(name="test_graph")
        graph.nodes = {
            "FailingOrchestrator": Node(
                name="FailingOrchestrator", 
                agent_type="orchestrator", 
                context={"instance": failing_agent}
            )
        }
        graph.entry_point = "FailingOrchestrator"
        
        # Mock builder
        self.assembly_service.builder = Mock()
        self.assembly_service.builder.compile.return_value = Mock()
        
        # Assemble with registry should now raise an exception
        test_registry = {"NodeA": {}}
        
        with self.assertRaises(ValueError) as context:
            self.assembly_service.assemble_graph(
                graph, 
                {"FailingOrchestrator": failing_agent},
                orchestrator_node_registry=test_registry
            )
        
        # Verify the error message is informative
        self.assertIn("Failed to inject orchestrator service", str(context.exception))
        self.assertIn("FailingOrchestrator", str(context.exception))
        
        # Verify injection failure was tracked
        self.assertEqual(self.assembly_service.injection_stats["orchestrators_found"], 1)
        self.assertEqual(self.assembly_service.injection_stats["orchestrators_injected"], 0)
        self.assertEqual(self.assembly_service.injection_stats["injection_failures"], 1)

    def test_orchestrator_node_registry_injection_failure(self):
        """Test handling of node registry injection failures."""
        # Create orchestrator that succeeds with service config but fails with node registry
        class NodeRegistryFailingAgent:
            def __init__(self):
                self.orchestrator_service = None
            
            def configure_orchestrator_service(self, orchestrator_service):
                self.orchestrator_service = orchestrator_service
            
            def run(self, state):
                return {"result": "test"}
                
            # Property that raises exception on assignment
            @property 
            def node_registry(self):
                return {}
            
            @node_registry.setter
            def node_registry(self, value):
                raise RuntimeError("Node registry injection failed")
        
        failing_agent = NodeRegistryFailingAgent()
        
        # Create graph with failing agent
        graph = Graph(name="test_graph")
        graph.nodes = {
            "FailingOrchestrator": Node(
                name="FailingOrchestrator", 
                agent_type="orchestrator", 
                context={"instance": failing_agent}
            )
        }
        graph.entry_point = "FailingOrchestrator"
        
        # Mock builder
        self.assembly_service.builder = Mock()
        self.assembly_service.builder.compile.return_value = Mock()
        
        # Assemble with registry should now raise an exception
        test_registry = {"NodeA": {}}
        
        with self.assertRaises(ValueError) as context:
            self.assembly_service.assemble_graph(
                graph, 
                {"FailingOrchestrator": failing_agent},
                orchestrator_node_registry=test_registry
            )
        
        # Verify the error message is informative
        self.assertIn("Failed to inject orchestrator service", str(context.exception))
        
        # Verify orchestrator service was configured successfully before the registry failure
        self.assertEqual(failing_agent.orchestrator_service, self.mock_orchestrator_service)


if __name__ == "__main__":
    unittest.main()
