"""
Integration test for GraphRunnerService delegation to AgentServiceInjectionService.

Tests that the refactored service injection maintains backward compatibility
and correctly delegates from GraphRunnerService to AgentServiceInjectionService.
"""

import unittest
from typing import Any, Dict, Optional
from unittest.mock import Mock, MagicMock, patch

try:
    from agentmap.services.agent.agent_service_injection_service import AgentServiceInjectionService
    from agentmap.services.protocols import (
        CSVCapableAgent,
        JSONCapableAgent,
        LLMCapableAgent,
        PromptCapableAgent,
        StorageCapableAgent,
    )
except ImportError:
    # Mock imports if AgentMap is not available in test environment
    print("WARNING: AgentMap imports not available, using mock classes")
    
    class AgentServiceInjectionService:
        pass
    
    class LLMCapableAgent:
        pass
    
    class StorageCapableAgent:
        pass
    
    class PromptCapableAgent:
        pass
    
    class CSVCapableAgent:
        pass
    
    class JSONCapableAgent:
        pass


class MockAgent:
    """Mock agent implementing multiple protocols for testing."""
    
    def __init__(self, name: str = "test_agent"):
        self.name = name
        self.llm_service = None
        self.storage_service = None
        self.prompt_manager_service = None
        self.csv_service = None
        self.json_service = None
        
        # Track configuration calls
        self.configuration_calls = []
    
    def configure_llm_service(self, llm_service: Any) -> None:
        self.llm_service = llm_service
        self.configuration_calls.append(("llm_service", llm_service))
    
    def configure_storage_service(self, storage_service: Any) -> None:
        self.storage_service = storage_service
        self.configuration_calls.append(("storage_service", storage_service))
    
    def configure_prompt_service(self, prompt_service: Any) -> None:
        self.prompt_manager_service = prompt_service
        self.configuration_calls.append(("prompt_service", prompt_service))
    
    def configure_csv_service(self, csv_service: Any) -> None:
        self.csv_service = csv_service
        self.configuration_calls.append(("csv_service", csv_service))
    
    def configure_json_service(self, json_service: Any) -> None:
        self.json_service = json_service
        self.configuration_calls.append(("json_service", json_service))


class MockGraphRunnerService:
    """Mock GraphRunnerService to test delegation pattern."""
    
    def __init__(self, agent_service_injection_service: Optional[AgentServiceInjectionService] = None):
        self.agent_service_injection_service = agent_service_injection_service
        self.llm_service = Mock(name="mock_llm_service")
        self.storage_service_manager = Mock(name="mock_storage_service_manager")
        self.logger = Mock(name="mock_logger")
        
        # Mock host services
        self.host_protocol_configuration = Mock()
        self._host_services_available = True
        
        # Track delegation calls
        self.delegation_calls = []
    
    def _configure_agent_services(self, agent: Any) -> None:
        """
        Simulate the refactored GraphRunnerService method that delegates to AgentServiceInjectionService.
        """
        self.delegation_calls.append(("configure_agent_services", agent.name))
        
        # Delegate to AgentServiceInjectionService if available
        if hasattr(self, 'agent_service_injection_service') and self.agent_service_injection_service:
            # Use the centralized service injection
            summary = self.agent_service_injection_service.configure_all_services(agent)
            total_core = summary['total_services_configured']
            
            # Configure host-defined services after core services
            host_services_configured = self._configure_host_services(agent)
            
            # Log summary at appropriate level
            total_configured = total_core + host_services_configured
            if total_configured > 0:
                # INFO level for production visibility when services are configured
                self.logger.info(
                    f"[GraphRunnerService] Configured {total_configured} services for {agent.name} "
                    f"(core: {total_core}, host: {host_services_configured})"
                )
            else:
                # DEBUG level when no services configured (normal for basic agents)
                self.logger.debug(
                    f"[GraphRunnerService] No services configured for {agent.name} "
                    "(agent does not implement service protocols)"
                )
        else:
            # Fallback to legacy implementation for backward compatibility
            self._configure_agent_services_fallback(agent)
    
    def _configure_host_services(self, agent: Any) -> int:
        """Mock host services configuration."""
        return 0  # No host services for this test
    
    def _configure_agent_services_fallback(self, agent: Any) -> None:
        """Mock fallback service configuration."""
        self.delegation_calls.append(("configure_agent_services_fallback", agent.name))
        
        # Minimal fallback - configure only essential services
        if isinstance(agent, LLMCapableAgent) and self.llm_service:
            agent.configure_llm_service(self.llm_service)
            self.logger.debug(f"[GraphRunnerService] Configured LLM service for {agent.name} (fallback)")
        
        if isinstance(agent, StorageCapableAgent) and self.storage_service_manager:
            agent.configure_storage_service(self.storage_service_manager)
            self.logger.debug(f"[GraphRunnerService] Configured storage service for {agent.name} (fallback)")


class TestGraphRunnerServiceIntegration(unittest.TestCase):
    """Integration tests for GraphRunnerService delegation to AgentServiceInjectionService."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock services
        self.llm_service = Mock(name="llm_service")
        self.storage_service_manager = Mock(name="storage_service_manager")
        self.logging_service = Mock(name="logging_service")
        self.prompt_manager_service = Mock(name="prompt_manager_service")
        self.orchestrator_service = Mock(name="orchestrator_service")
        self.graph_checkpoint_service = Mock(name="graph_checkpoint_service")
        self.blob_storage_service = Mock(name="blob_storage_service")
        
        # Mock logger
        self.mock_logger = Mock()
        self.logging_service.get_class_logger.return_value = self.mock_logger
        
        # Mock storage services
        self.storage_service_manager.get_service.side_effect = lambda service_type: Mock(name=f"{service_type}_service")
        
        # Create AgentServiceInjectionService
        self.agent_service_injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            logging_service=self.logging_service,
            prompt_manager_service=self.prompt_manager_service,
            orchestrator_service=self.orchestrator_service,
            graph_checkpoint_service=self.graph_checkpoint_service,
            blob_storage_service=self.blob_storage_service,
        )
        
        # Create GraphRunnerService with delegation
        self.graph_runner_with_delegation = MockGraphRunnerService(
            agent_service_injection_service=self.agent_service_injection_service
        )
        
        # Create GraphRunnerService without delegation (fallback)
        self.graph_runner_fallback = MockGraphRunnerService(
            agent_service_injection_service=None
        )
    
    def test_delegation_to_agent_service_injection_service(self):
        """Test that GraphRunnerService correctly delegates to AgentServiceInjectionService."""
        agent = MockAgent("test_delegation_agent")
        
        # Configure services using delegation
        self.graph_runner_with_delegation._configure_agent_services(agent)
        
        # Verify delegation occurred
        self.assertIn(
            ("configure_agent_services", "test_delegation_agent"),
            self.graph_runner_with_delegation.delegation_calls
        )
        
        # Verify services were configured
        self.assertIsNotNone(agent.llm_service, "LLM service should be configured via delegation")
        self.assertIsNotNone(agent.storage_service, "Storage service should be configured via delegation")
        self.assertIsNotNone(agent.prompt_manager_service, "Prompt service should be configured via delegation")
        
        # Verify services are the correct ones
        self.assertEqual(agent.llm_service, self.llm_service)
        self.assertEqual(agent.storage_service, self.storage_service_manager)
        self.assertEqual(agent.prompt_manager_service, self.prompt_manager_service)
    
    def test_fallback_when_injection_service_unavailable(self):
        """Test GraphRunnerService fallback behavior when AgentServiceInjectionService is not available."""
        agent = MockAgent("test_fallback_agent")
        
        # Configure services using fallback
        self.graph_runner_fallback._configure_agent_services(agent)
        
        # Verify fallback was used
        self.assertIn(
            ("configure_agent_services_fallback", "test_fallback_agent"),
            self.graph_runner_fallback.delegation_calls
        )
        
        # Verify essential services were configured in fallback mode
        self.assertIsNotNone(agent.llm_service, "LLM service should be configured in fallback")
        self.assertIsNotNone(agent.storage_service, "Storage service should be configured in fallback")
        
        # Verify services are the correct ones
        self.assertEqual(agent.llm_service, self.graph_runner_fallback.llm_service)
        self.assertEqual(agent.storage_service, self.graph_runner_fallback.storage_service_manager)
    
    def test_service_configuration_counts_match(self):
        """Test that service configuration counts match between delegation and fallback."""
        # Test with multi-service agent
        delegation_agent = MockAgent("delegation_agent")
        fallback_agent = MockAgent("fallback_agent")
        
        # Configure via delegation
        self.graph_runner_with_delegation._configure_agent_services(delegation_agent)
        
        # Configure via fallback
        self.graph_runner_fallback._configure_agent_services(fallback_agent)
        
        # Both should configure the same essential services
        # (delegation will configure more services, but essential ones should match)
        self.assertEqual(
            delegation_agent.llm_service is not None,
            fallback_agent.llm_service is not None,
            "LLM service configuration should match"
        )
        self.assertEqual(
            delegation_agent.storage_service is not None,
            fallback_agent.storage_service is not None,
            "Storage service configuration should match"
        )
    
    def test_backward_compatibility_preserved(self):
        """Test that backward compatibility is preserved with strict service injection."""
        agent = MockAgent("compatibility_test_agent")
        
        # Record initial state
        initial_configuration_calls = len(agent.configuration_calls)
        
        # Configure via delegation (new method) - should work with all required services available
        self.graph_runner_with_delegation._configure_agent_services(agent)
        delegation_calls = agent.configuration_calls[initial_configuration_calls:]
        
        # Reset agent
        agent = MockAgent("compatibility_test_agent")
        
        # Configure via fallback (legacy method)
        self.graph_runner_fallback._configure_agent_services(agent)
        fallback_calls = agent.configuration_calls
        
        # Essential services should be configured in both cases
        delegation_services = {call[0] for call in delegation_calls}
        fallback_services = {call[0] for call in fallback_calls}
        
        # LLM and Storage should be configured in both (these are required services)
        essential_services = {"llm_service", "storage_service"}
        
        self.assertTrue(
            essential_services.issubset(delegation_services),
            f"Delegation should configure essential services. Got: {delegation_services}"
        )
        self.assertTrue(
            essential_services.issubset(fallback_services),
            f"Fallback should configure essential services. Got: {fallback_services}"
        )
        
        # With strict behavior, delegation should still configure more services when available
        # (This test assumes all services are properly configured, not None)
        self.assertGreaterEqual(
            len(delegation_services),
            len(fallback_services),
            "Delegation should configure at least as many services as fallback when services are available"
        )
    
    def test_logging_consistency(self):
        """Test that logging remains consistent between delegation and fallback."""
        agent = MockAgent("logging_test_agent")
        
        # Configure via delegation
        self.graph_runner_with_delegation._configure_agent_services(agent)
        
        # Verify that GraphRunnerService logger was called
        # (The actual AgentServiceInjectionService uses its own logger)
        self.graph_runner_with_delegation.logger.info.assert_called()
        
        # Check the logging call contains expected information
        info_calls = self.graph_runner_with_delegation.logger.info.call_args_list
        self.assertTrue(len(info_calls) > 0, "Should have INFO level log calls")
        
        # Look for service configuration summary
        summary_logged = any(
            "services for logging_test_agent" in str(call)
            for call in info_calls
        )
        self.assertTrue(summary_logged, "Should log service configuration summary")
    
    def test_error_handling_consistency(self):
        """Test that error handling is consistent with strict service injection behavior."""
        
        # Test 1: Agent configuration method failures (should still propagate)
        class FailingAgent:
            def __init__(self, name: str = "failing_agent"):
                self.name = name
            
            def configure_llm_service(self, service: Any) -> None:
                raise RuntimeError("LLM configuration failed")
            
            def configure_storage_service(self, service: Any) -> None:
                raise RuntimeError("Storage configuration failed")
        
        failing_agent_delegation = FailingAgent("failing_delegation_agent")
        failing_agent_fallback = FailingAgent("failing_fallback_agent")
        
        # Test delegation error handling - agent method failures should propagate
        with self.assertRaises(RuntimeError) as context:
            self.graph_runner_with_delegation._configure_agent_services(failing_agent_delegation)
        self.assertIn("configuration failed", str(context.exception))
        
        # Test fallback error handling - should behave the same way
        with self.assertRaises(RuntimeError) as context:
            self.graph_runner_fallback._configure_agent_services(failing_agent_fallback)
        self.assertIn("configuration failed", str(context.exception))
        
        # Test 2: Missing service errors (strict behavior)
        # Create injection service with missing optional services
        strict_injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            logging_service=self.logging_service,
            prompt_manager_service=None,  # Missing optional service
        )
        
        class PromptRequiringAgent:
            def __init__(self, name: str = "prompt_agent"):
                self.name = name
                self.prompt_manager_service = None
            
            def configure_prompt_service(self, service: Any) -> None:
                self.prompt_manager_service = service
        
        prompt_agent = PromptRequiringAgent("test_prompt_agent")
        
        # Should raise exception due to strict service availability checking
        with self.assertRaises(Exception) as context:
            strict_injection_service.configure_core_services(prompt_agent)
        
        # Verify error message indicates service not available
        error_message = str(context.exception).lower()
        self.assertTrue(
            "not available" in error_message,
            f"Exception should indicate service not available: {context.exception}"
        )
    
    def test_service_injection_service_status(self):
        """Test that service injection status methods work correctly with strict behavior."""
        agent = MockAgent("status_test_agent")
        
        # Get injection status before configuration
        status_before = self.agent_service_injection_service.get_service_injection_status(agent)
        
        # Configure services (should work since all services are available in test setup)
        summary = self.agent_service_injection_service.configure_all_services(agent)
        
        # Get injection status after configuration
        status_after = self.agent_service_injection_service.get_service_injection_status(agent)
        
        # Verify status information
        self.assertEqual(status_before["agent_name"], "status_test_agent")
        self.assertEqual(status_after["agent_name"], "status_test_agent")
        
        # Should show protocols implemented
        self.assertIn("implemented_protocols", status_before)
        self.assertIn("implemented_protocols", status_after)
        
        # Should show service injection potential
        self.assertIn("service_injection_potential", status_before)
        self.assertIn("service_injection_potential", status_after)
        
        # With strict behavior, successful configuration should reflect in summary
        self.assertGreater(summary["total_services_configured"], 0, "Should configure services when available")
        self.assertEqual(summary["configuration_status"], "success", "Configuration should succeed with available services")
        
        # Test status reporting with missing services (should indicate strict behavior)
        strict_injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            logging_service=self.logging_service,
            prompt_manager_service=None,  # Missing service
        )
        
        # Get service availability status - should show missing services
        availability_status = strict_injection_service.get_service_availability_status()
        self.assertIn("core_services", availability_status)
        
        # Should indicate prompt manager not available
        self.assertFalse(
            availability_status["core_services"]["prompt_manager_service_available"],
            "Status should reflect missing prompt manager service"
        )


class TestServiceInjectionMigration(unittest.TestCase):
    """Tests for migration from old storage/injection.py to new AgentServiceInjectionService."""
    
    def setUp(self):
        """Set up migration test fixtures."""
        # Mock the old storage/injection.py functions
        self.mock_old_inject_storage_services = Mock()
        self.mock_old_requires_storage_services = Mock(return_value=True)
        self.mock_old_get_required_service_types = Mock(return_value=["csv", "json"])
        
        # Create new service
        self.new_service = AgentServiceInjectionService(
            llm_service=Mock(),
            storage_service_manager=Mock(),
            logging_service=Mock(),
        )
        
        # Mock logger
        mock_logger = Mock()
        self.new_service.logger = mock_logger
        
        # Mock storage service manager
        self.new_service.storage_service_manager.get_service.side_effect = (
            lambda service_type: Mock(name=f"{service_type}_service")
        )
    
    def test_functional_equivalence(self):
        """Test that new service provides same functionality as old storage/injection.py."""
        
        # Create test agent
        class TestAgent:
            def __init__(self, name="migration_test_agent"):
                self.name = name
                self.csv_service = None
                self.json_service = None
            
            def configure_csv_service(self, service):
                self.csv_service = service
            
            def configure_json_service(self, service):
                self.json_service = service
        
        agent = TestAgent()
        
        # Test requires_storage_services equivalence
        new_requires = self.new_service.requires_storage_services(agent)
        self.assertTrue(new_requires, "New service should detect storage requirements")
        
        # Test get_required_service_types equivalence
        new_types = self.new_service.get_required_service_types(agent)
        expected_types = {"csv", "json"}
        self.assertEqual(set(new_types), expected_types, "New service should return correct service types")
        
        # Test service injection equivalence
        storage_configured = self.new_service.configure_storage_services(agent)
        self.assertEqual(storage_configured, 2, "Should configure 2 storage services")
        self.assertIsNotNone(agent.csv_service, "CSV service should be configured")
        self.assertIsNotNone(agent.json_service, "JSON service should be configured")
    
    def test_error_handling_migration(self):
        """Test that error handling behavior matches between old and new implementations."""
        
        # Create agent that should fail due to missing service
        class TestAgent:
            def __init__(self, name="failing_migration_agent"):
                self.name = name
            
            def configure_csv_service(self, service):
                pass
        
        # Create service with no available storage services
        failing_service = AgentServiceInjectionService(
            llm_service=Mock(),
            storage_service_manager=Mock(),
            logging_service=Mock(),
        )
        failing_service.storage_service_manager.get_service.return_value = None
        
        agent = TestAgent()
        
        # Should raise exception like old implementation
        with self.assertRaises(Exception):
            failing_service.configure_storage_services(agent)
    
    def test_logging_migration(self):
        """Test that logging behavior is consistent with old implementation."""
        
        class TestAgent:
            def __init__(self, name="logging_migration_agent"):
                self.name = name
                self.csv_service = None
            
            def configure_csv_service(self, service):
                self.csv_service = service
        
        agent = TestAgent()
        mock_logger = Mock()
        self.new_service.logger = mock_logger
        
        # Configure storage services
        self.new_service.configure_storage_services(agent)
        
        # Verify debug logging occurred (like old implementation)
        mock_logger.debug.assert_called()
        
        # Check that agent name is included in log messages
        debug_calls = mock_logger.debug.call_args_list
        agent_name_logged = any(
            "logging_migration_agent" in str(call)
            for call in debug_calls
        )
        self.assertTrue(agent_name_logged, "Agent name should be included in log messages")


if __name__ == '__main__':
    # Run integration tests with verbose output
    unittest.main(verbosity=2)
