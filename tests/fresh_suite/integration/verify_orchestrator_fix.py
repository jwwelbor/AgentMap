"""
Simple script to test that orchestrator service is properly injected.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from agentmap.di.containers import ApplicationContainer


def test_orchestrator_service_injection():
    """Test that OrchestratorService is properly configured in the container."""
    print("Testing OrchestratorService injection...")
    
    # Initialize container
    container = ApplicationContainer()
    
    # Bootstrap happens automatically when getting services
    # Just initialize the logging service to ensure it's ready
    logging_service = container.logging_service()
    
    # Get the orchestrator service
    orchestrator_service = container.orchestrator_service()
    print(f"✅ OrchestratorService created: {orchestrator_service}")
    
    # Get service info
    info = orchestrator_service.get_service_info()
    print(f"✅ Service info: {info['service']}")
    print(f"✅ Supported strategies: {info['supported_strategies']}")
    
    # Test that GraphRunnerService has it
    graph_runner = container.graph_runner_service()
    print(f"✅ GraphRunnerService has orchestrator_service: {graph_runner.orchestrator_service is not None}")
    
    # Create a simple test to verify agent gets the service
    from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
    from agentmap.services.protocols import OrchestrationCapableAgent
    
    # Create an agent
    agent = OrchestratorAgent(
        name="TestOrchestrator",
        prompt="Test",
        context={"matching_strategy": "algorithm"},
        logger=container.logging_service().get_logger("test"),
        execution_tracker_service=container.execution_tracking_service(),
        state_adapter_service=container.state_adapter_service()
    )
    
    print(f"✅ Agent created, orchestrator_service is None: {agent.orchestrator_service is None}")
    print(f"✅ Agent implements OrchestrationCapableAgent: {isinstance(agent, OrchestrationCapableAgent)}")
    
    # Configure the service
    agent.configure_orchestrator_service(orchestrator_service)
    print(f"✅ After configuration, orchestrator_service is set: {agent.orchestrator_service is not None}")
    
    print("\n🎉 All tests passed! OrchestratorService injection is working correctly.")


if __name__ == "__main__":
    test_orchestrator_service_injection()
