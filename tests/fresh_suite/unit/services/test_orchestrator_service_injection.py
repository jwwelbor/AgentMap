"""
Unit tests for OrchestratorAgent service injection.

Tests the specific fix for OrchestratorService injection into OrchestratorAgent.
"""

import unittest
from unittest.mock import Mock, MagicMock

from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
from agentmap.services.orchestrator_service import OrchestratorService
from agentmap.services.prompt_manager_service import PromptManagerService
from agentmap.services.logging_service import LoggingService


class TestOrchestratorServiceInjection(unittest.TestCase):
    """Unit tests for OrchestratorAgent with OrchestratorService injection."""
    
    def setUp(self):
        """Set up mocks for testing."""
        # Create mock services
        self.mock_logger = Mock()
        self.mock_execution_tracker = Mock()
        self.mock_state_adapter = Mock()
        
        # Create real services for orchestrator
        self.mock_prompt_manager = Mock(spec=PromptManagerService)
        self.mock_logging_service = Mock(spec=LoggingService)
        self.mock_logging_service.get_class_logger.return_value = self.mock_logger
        self.mock_llm_service = Mock()
        self.mock_features_registry = Mock()
        
        # Create real OrchestratorService
        self.orchestrator_service = OrchestratorService(
            prompt_manager_service=self.mock_prompt_manager,
            logging_service=self.mock_logging_service,
            llm_service=self.mock_llm_service,
            features_registry_service=self.mock_features_registry
        )
    
    def test_orchestrator_agent_accepts_orchestrator_service(self):
        """Test that OrchestratorAgent can be configured with OrchestratorService via protocol."""
        # Create agent without orchestrator service
        agent = OrchestratorAgent(
            name="TestOrchestrator",
            prompt="Route requests",
            context={
                "matching_strategy": "algorithm",
                "confidence_threshold": 0.8,
                "nodes": "NodeA|NodeB|NodeC"
            },
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter,
        )
        
        # Initially, orchestrator_service should be None
        self.assertIsNone(agent.orchestrator_service)
        
        # Configure the service via protocol method
        agent.configure_orchestrator_service(self.orchestrator_service)
        
        # Verify service is properly stored
        self.assertIsNotNone(agent.orchestrator_service)
        self.assertIsInstance(agent.orchestrator_service, OrchestratorService)
        self.assertEqual(agent.orchestrator_service, self.orchestrator_service)
    
    def test_orchestrator_agent_process_with_service(self):
        """Test that OrchestratorAgent can process with OrchestratorService."""
        # Mock the select_best_node method
        self.orchestrator_service.select_best_node = Mock(return_value="NodeB")
        
        # Create agent
        agent = OrchestratorAgent(
            name="TestOrchestrator",
            prompt="Route requests",
            context={
                "matching_strategy": "algorithm",
                "nodes": "NodeA|NodeB|NodeC"
            },
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter,
        )
        
        # Configure orchestrator service via protocol
        agent.configure_orchestrator_service(self.orchestrator_service)
        
        # Set up node registry
        agent.node_registry = {
            "NodeA": {"name": "NodeA", "description": "Process A"},
            "NodeB": {"name": "NodeB", "description": "Process B"},
            "NodeC": {"name": "NodeC", "description": "Process C"}
        }
        
        # Process input
        inputs = {"request": "process this data"}
        result = agent.process(inputs)
        
        # Verify service was called correctly
        self.orchestrator_service.select_best_node.assert_called_once()
        call_args = self.orchestrator_service.select_best_node.call_args
        
        # Check arguments
        self.assertEqual(call_args.kwargs["input_text"], "process this data")
        self.assertEqual(call_args.kwargs["strategy"], "algorithm")
        self.assertEqual(call_args.kwargs["confidence_threshold"], 0.8)
        self.assertEqual(result, "NodeB")
    
    def test_orchestrator_agent_without_service_returns_error(self):
        """Test that OrchestratorAgent handles missing service gracefully."""
        # Create agent without orchestrator service
        agent = OrchestratorAgent(
            name="TestOrchestrator",
            prompt="Route requests",
            context={
                "matching_strategy": "algorithm",
                "default_target": "ErrorHandler"
            },
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter,
        )
        
        # Do NOT configure orchestrator service - leave it as None
        
        # Process should return error or default
        inputs = {"request": "process this"}
        result = agent.process(inputs)
        
        # Should return default target
        self.assertEqual(result, "ErrorHandler")
        
        # Check error was logged (accounting for the agent name prefix)
        self.mock_logger.error.assert_called_with(
            "[OrchestratorAgent:TestOrchestrator] OrchestratorService not configured - cannot perform orchestration"
        )
    
    def test_orchestrator_service_info(self):
        """Test OrchestratorService provides correct service info."""
        info = self.orchestrator_service.get_service_info()
        
        self.assertEqual(info["service"], "OrchestratorService")
        self.assertTrue(info["prompt_manager_available"])
        self.assertTrue(info["llm_service_configured"])
        self.assertTrue(info["features_registry_configured"])
        self.assertIn("algorithm", info["supported_strategies"])
        self.assertIn("llm", info["supported_strategies"])
        self.assertIn("tiered", info["supported_strategies"])
    
    def test_orchestrator_agent_implements_protocol(self):
        """Test that OrchestratorAgent implements OrchestrationCapableAgent protocol."""
        from agentmap.services.protocols import OrchestrationCapableAgent
        
        # Create agent
        agent = OrchestratorAgent(
            name="TestOrchestrator",
            prompt="Route requests",
            context={},
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter,
        )
        
        # Verify it implements the protocol
        self.assertIsInstance(agent, OrchestrationCapableAgent)
        self.assertTrue(hasattr(agent, 'configure_orchestrator_service'))
        self.assertTrue(callable(getattr(agent, 'configure_orchestrator_service')))


class TestGraphRunnerServiceInjection(unittest.TestCase):
    """Test GraphRunnerService properly injects OrchestratorService."""
    
    def test_graph_runner_stores_orchestrator_service(self):
        """Test that GraphRunnerService accepts and stores OrchestratorService."""
        # Create mock services
        mock_services = {
            'graph_definition_service': Mock(),
            'graph_execution_service': Mock(),
            'graph_bundle_service': Mock(),
            'agent_factory_service': Mock(),
            'llm_service': Mock(),
            'storage_service_manager': Mock(),
            'node_registry_service': Mock(),
            'logging_service': Mock(),
            'app_config_service': Mock(),
            'execution_tracking_service': Mock(),
            'execution_policy_service': Mock(),
            'state_adapter_service': Mock(),
            'dependency_checker_service': Mock(),
            'graph_assembly_service': Mock(),
            'prompt_manager_service': Mock(),
            'orchestrator_service': Mock(spec=OrchestratorService),  # The key service
            'host_protocol_configuration_service': Mock(),
            'graph_checkpoint_service': Mock()
        }
        
        # Mock logging service methods
        mock_services['logging_service'].get_class_logger.return_value = Mock()
        
        # Import here to avoid circular dependencies
        from agentmap.services.graph.graph_runner_service import GraphRunnerService
        
        # Create GraphRunnerService with all services
        runner = GraphRunnerService(**mock_services)
        
        # Verify orchestrator_service is stored
        self.assertIsNotNone(runner.orchestrator_service)
        self.assertEqual(runner.orchestrator_service, mock_services['orchestrator_service'])


if __name__ == "__main__":
    unittest.main()
