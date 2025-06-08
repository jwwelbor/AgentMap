"""
Test to validate agent migration to protocol-based dependency injection.

This test verifies that our updated agents follow the new protocol pattern correctly.
"""
import logging
import unittest
from unittest.mock import Mock
from typing import Dict, Any

# Import the agents we've updated
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent
from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent

# Import protocols
from agentmap.services.protocols import (
    LLMCapableAgent, 
    StorageCapableAgent,
    LLMServiceProtocol,
    StorageServiceProtocol
)
from agentmap.services.storage.protocols import CSVCapableAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class TestAgentMigration(unittest.TestCase):
    """Test suite for agent protocol migration."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock infrastructure services
        self.mock_logger = Mock(spec=logging.Logger)
        self.mock_execution_tracker = Mock(spec=ExecutionTrackingService)
        self.mock_state_adapter = Mock(spec=StateAdapterService)
        
        # Create mock business services
        self.mock_llm_service = Mock(spec=LLMServiceProtocol)
        self.mock_storage_service = Mock(spec=StorageServiceProtocol)
        self.mock_csv_service = Mock()
        
        # Configure mock responses
        self.mock_llm_service.call_llm.return_value = "Mock LLM response"
        
    def test_echo_agent_protocol_compliance(self):
        """Test EchoAgent follows new constructor pattern (no protocols needed)."""
        # Test new constructor pattern
        agent = EchoAgent(
            name="test_echo",
            prompt="Echo test prompt",
            context={"input_fields": ["input"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter
        )
        
        # Verify agent was created correctly
        self.assertEqual(agent.name, "test_echo")
        self.assertEqual(agent.prompt, "Echo test prompt")
        
        # Verify it doesn't implement business service protocols (no business services needed)
        self.assertFalse(isinstance(agent, LLMCapableAgent))
        self.assertFalse(isinstance(agent, StorageCapableAgent))
        
        # Test basic functionality
        inputs = {"input": "test message"}
        result = agent.process(inputs)
        self.assertEqual(result, "test message")
        
    def test_default_agent_protocol_compliance(self):
        """Test DefaultAgent follows new constructor pattern."""
        agent = DefaultAgent(
            name="test_default",
            prompt="Default test prompt",
            context={"input_fields": ["input"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter
        )
        
        # Verify agent was created correctly
        self.assertEqual(agent.name, "test_default")
        self.assertEqual(agent.prompt, "Default test prompt")
        
        # Test basic functionality
        inputs = {"input": "test message"}
        result = agent.process(inputs)
        self.assertIn("DefaultAgent executed", result)
        self.assertIn("Default test prompt", result)
        
    def test_llm_agent_protocol_compliance(self):
        """Test LLMAgent implements LLMCapableAgent protocol correctly."""
        # Test new constructor pattern (no business services)
        agent = LLMAgent(
            name="test_llm",
            prompt="LLM test prompt",
            context={"input_fields": ["input"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter
        )
        
        # Verify protocol implementation
        self.assertTrue(isinstance(agent, LLMCapableAgent))
        
        # Test service configuration
        agent.configure_llm_service(self.mock_llm_service)
        self.assertEqual(agent.llm_service, self.mock_llm_service)
        
        # Test that service is required for operation
        with self.assertRaises(ValueError):
            unconfigured_agent = LLMAgent(
                name="unconfigured",
                prompt="test",
                logger=self.mock_logger,
                execution_tracker_service=self.mock_execution_tracker
            )
            _ = unconfigured_agent.llm_service  # Should raise
            
    def test_storage_agent_protocol_compliance(self):
        """Test BaseStorageAgent implements StorageCapableAgent protocol correctly."""
        # Create a concrete subclass for testing
        class TestStorageAgent(BaseStorageAgent):
            def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
                return f"Processed {collection}"
                
        agent = TestStorageAgent(
            name="test_storage",
            prompt="Storage test prompt",
            context={"input_fields": ["collection"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter
        )
        
        # Verify protocol implementation
        self.assertTrue(isinstance(agent, StorageCapableAgent))
        
        # Test service configuration
        agent.configure_storage_service(self.mock_storage_service)
        self.assertEqual(agent.storage_service, self.mock_storage_service)
        
    def test_csv_agent_protocol_compliance(self):
        """Test CSVAgent implements CSVCapableAgent protocol correctly."""
        agent = CSVAgent(
            name="test_csv",
            prompt="CSV test prompt",
            context={"input_fields": ["collection"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter
        )
        
        # Verify protocol implementation
        self.assertTrue(isinstance(agent, CSVCapableAgent))
        self.assertTrue(isinstance(agent, StorageCapableAgent))  # Inherits from BaseStorageAgent
        
        # Test service configuration
        agent.configure_csv_service(self.mock_csv_service)
        self.assertEqual(agent.csv_service, self.mock_csv_service)
        
    def test_orchestrator_agent_protocol_compliance(self):
        """Test OrchestratorAgent implements LLMCapableAgent protocol correctly."""
        agent = OrchestratorAgent(
            name="test_orchestrator",
            prompt="Orchestrator test prompt",
            context={
                "input_fields": ["input"], 
                "output_field": "output",
                "matching_strategy": "llm"
            },
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker,
            state_adapter_service=self.mock_state_adapter
        )
        
        # Verify protocol implementation
        self.assertTrue(isinstance(agent, LLMCapableAgent))
        
        # Test service configuration
        agent.configure_llm_service(self.mock_llm_service)
        self.assertEqual(agent.llm_service, self.mock_llm_service)
        
    def test_no_legacy_constructor_patterns(self):
        """Test that agents don't use legacy constructor patterns."""
        # All agents should follow the new pattern: (name, prompt, context, logger, execution_tracker, state_adapter)
        # No business services in constructor
        
        agents_to_test = [
            (EchoAgent, {}),
            (DefaultAgent, {}),
            (LLMAgent, {}),
            (OrchestratorAgent, {"matching_strategy": "algorithm"}),  # Don't need LLM for algorithm mode
        ]
        
        for agent_class, extra_context in agents_to_test:
            with self.subTest(agent_class=agent_class.__name__):
                context = {"input_fields": ["input"], "output_field": "output"}
                context.update(extra_context)
                
                # Should be able to create agent with only infrastructure services
                agent = agent_class(
                    name="test",
                    prompt="test prompt",
                    context=context,
                    logger=self.mock_logger,
                    execution_tracker_service=self.mock_execution_tracker,
                    state_adapter_service=self.mock_state_adapter
                )
                
                # Agent should be created successfully
                self.assertEqual(agent.name, "test")
                self.assertEqual(agent.prompt, "test prompt")
                
    def test_service_error_handling(self):
        """Test that agents provide clear errors when services aren't configured."""
        # LLM Agent without LLM service
        llm_agent = LLMAgent(
            name="test",
            prompt="test",
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker
        )
        
        with self.assertRaises(ValueError) as cm:
            _ = llm_agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))
        
        # Storage Agent without storage service
        class TestStorageAgent(BaseStorageAgent):
            def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
                return "test"
                
        storage_agent = TestStorageAgent(
            name="test",
            prompt="test",
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracker
        )
        
        with self.assertRaises(ValueError) as cm:
            _ = storage_agent.storage_service
        self.assertIn("Storage service not configured", str(cm.exception))


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(level=logging.DEBUG)
    
    # Run tests
    unittest.main(verbosity=2)
