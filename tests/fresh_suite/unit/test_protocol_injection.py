"""
Direct test to verify protocol-based orchestrator service injection works.
"""


def test_protocol_injection():
    """Test the protocol-based injection of OrchestratorService."""
    # Import required modules
    from unittest.mock import Mock

    from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
    from agentmap.services.orchestrator_service import OrchestratorService
    from agentmap.services.protocols import OrchestrationCapableAgent

    # Create mock services
    mock_logger = Mock()
    mock_logging_service = Mock()
    mock_logging_service.get_class_logger.return_value = mock_logger
    mock_logging_service.get_logger.return_value = mock_logger

    mock_prompt_manager = Mock()

    # Create OrchestratorService
    orchestrator_service = OrchestratorService(
        prompt_manager_service=mock_prompt_manager,
        logging_service=mock_logging_service,
        llm_service=None,
        features_registry_service=None,
    )

    # Create OrchestratorAgent
    agent = OrchestratorAgent(
        name="TestOrchestrator",
        prompt="Test orchestrator",
        context={"matching_strategy": "algorithm"},
        logger=mock_logger,
        execution_tracker_service=None,
        state_adapter_service=None,
    )

    # Verify agent implements the protocol
    assert isinstance(
        agent, OrchestrationCapableAgent
    ), "Agent should implement OrchestrationCapableAgent"

    # Verify service is not configured initially
    assert agent.orchestrator_service is None, "Service should be None initially"

    # Configure the service using the protocol method
    agent.configure_orchestrator_service(orchestrator_service)

    # Verify service is now configured
    assert agent.orchestrator_service is not None, "Service should be configured"
    assert (
        agent.orchestrator_service == orchestrator_service
    ), "Service should be the same instance"

    print("✅ Protocol-based injection working correctly!")


if __name__ == "__main__":
    test_protocol_injection()
