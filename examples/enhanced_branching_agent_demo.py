"""
Demonstration of Enhanced BranchingAgent Capabilities

This script shows how the new configurable BranchingAgent can be used
both for testing workflows and for real conditional logic in production.

Key Improvement: No more duplicative configuration!
- The `success_field` automatically defaults to the first `input_field`
- Most configurations are now cleaner and more intuitive
- Still supports custom `success_field` override when needed
"""
import logging
from agentmap.agents.builtins.branching_agent import BranchingAgent
from tests.utils.mock_service_factory import MockServiceFactory

def demo_default_configuration():
    """Demonstrate default BranchingAgent behavior."""
    print("🔀 **Default Configuration Demo**")
    print("=" * 50)
    
    # Create mock services
    mock_logging_service = MockServiceFactory.create_mock_logging_service()
    mock_tracker = MockServiceFactory.create_mock_execution_tracking_service().create_tracker()
    mock_state_adapter = MockServiceFactory.create_mock_state_adapter_service()
    logger = mock_logging_service.get_class_logger(BranchingAgent)
    
    # Create agent with default configuration
    agent = BranchingAgent(
        name="default_branching",
        prompt="Default branching logic",
        context={
            "input_fields": ["success"],
            "output_field": "result"
        },
        logger=logger,
        execution_tracker_service=mock_tracker,
        state_adapter_service=mock_state_adapter
    )
    
    # Test various inputs
    test_cases = [
        {"success": True},
        {"success": False},
        {"success": "yes"},
        {"success": "no"},
        {"success": 1},
        {"success": 0},
        {"should_succeed": True},  # Fallback field
        {"other_field": "ignored"}  # No relevant field, uses default
    ]
    
    for inputs in test_cases:
        result = agent.process(inputs)
        print(f"Input: {inputs}")
        print(f"Result: {result}")
        print()

def demo_custom_configuration():
    """Demonstrate custom BranchingAgent configuration for real-world use."""
    print("🔧 **Custom Configuration Demo**")
    print("=" * 50)
    
    # Create mock services
    mock_logging_service = MockServiceFactory.create_mock_logging_service()
    mock_tracker = MockServiceFactory.create_mock_execution_tracking_service().create_tracker()
    mock_state_adapter = MockServiceFactory.create_mock_state_adapter_service()
    logger = mock_logging_service.get_class_logger(BranchingAgent)
    
    # Create agent for API response validation
    api_validator = BranchingAgent(
        name="api_response_validator",
        prompt="Validate API response status",
        context={
            "input_fields": ["http_status"],  # This automatically becomes the success_field!
            "output_field": "validation_result",
            "success_values": [200, 201, "OK", "CREATED"],
            "failure_values": [400, 401, 403, 404, 500, "ERROR", "FAILED"],
            "default_result": False  # Fail by default for unknown status codes
        },
        logger=logger,
        execution_tracker_service=mock_tracker,
        state_adapter_service=mock_state_adapter
    )
    
    print("**API Response Validator:**")
    api_test_cases = [
        {"http_status": 200},
        {"http_status": 404},
        {"http_status": "OK"},
        {"http_status": "ERROR"},
        {"http_status": 999}  # Unknown status code
    ]
    
    for inputs in api_test_cases:
        result = api_validator.process(inputs)
        print(f"HTTP Status: {inputs['http_status']}")
        print(f"Validation: {result}")
        print()
    
    # Create agent for task completion checking
    task_checker = BranchingAgent(
        name="task_completion_checker",
        prompt="Check if task is complete",
        context={
            "input_fields": ["task_status"],  # Primary field to check
            "output_field": "task_result",
            "success_values": ["COMPLETED", "DONE", "FINISHED", "SUCCESS"],
            "failure_values": ["FAILED", "ERROR", "CANCELLED", "TIMEOUT"],
            "fallback_fields": ["progress"],  # Check progress if task_status not found
            "default_result": False
        },
        logger=logger,
        execution_tracker_service=mock_tracker,
        state_adapter_service=mock_state_adapter
    )
    
    print("**Task Completion Checker:**")
    task_test_cases = [
        {"task_status": "COMPLETED"},
        {"task_status": "FAILED"},
        {"task_status": "IN_PROGRESS"},  # Unknown status, check fallback
        {"progress": 100},  # Uses fallback field
        {"progress": 0},    # Uses fallback field
        {"other_data": "value"}  # No relevant fields, uses default
    ]
    
    for inputs in task_test_cases:
        result = task_checker.process(inputs)
        print(f"Task Input: {inputs}")
        print(f"Completion Check: {result}")
        print()

def demo_workflow_testing_scenarios():
    """Demonstrate how to use BranchingAgent for testing different workflow paths."""
    print("🧪 **Workflow Testing Scenarios**")
    print("=" * 50)
    
    # Create mock services
    mock_logging_service = MockServiceFactory.create_mock_logging_service()
    mock_tracker = MockServiceFactory.create_mock_execution_tracking_service().create_tracker()
    mock_state_adapter = MockServiceFactory.create_mock_state_adapter_service()
    logger = mock_logging_service.get_class_logger(BranchingAgent)
    
    # Scenario 1: User authentication testing
    auth_tester = BranchingAgent(
        name="auth_test_branch",
        prompt="Test authentication scenarios",
        context={
            "input_fields": ["user_type"],  # Automatically becomes success_field
            "output_field": "auth_result",
            "success_values": ["admin", "premium", "verified"],
            "failure_values": ["guest", "suspended", "unverified"],
            "default_result": False
        },
        logger=logger,
        execution_tracker_service=mock_tracker,
        state_adapter_service=mock_state_adapter
    )
    
    print("**Authentication Testing:**")
    auth_scenarios = [
        {"user_type": "admin"},
        {"user_type": "guest"},
        {"user_type": "premium"},
        {"user_type": "suspended"}
    ]
    
    for scenario in auth_scenarios:
        result = auth_tester.process(scenario)
        print(f"User Type: {scenario['user_type']}")
        print(f"Auth Test: {result}")
        print()
    
    # Scenario 2: Error simulation testing
    error_simulator = BranchingAgent(
        name="error_sim_branch",
        prompt="Simulate different error conditions",
        context={
            "input_fields": ["error_rate"],  # Automatically becomes success_field
            "output_field": "error_simulation",
            "success_values": [0, "none", "low"],
            "failure_values": [100, "high", "critical"],
            "default_result": True  # Default to success (low error rate)
        },
        logger=logger,
        execution_tracker_service=mock_tracker,
        state_adapter_service=mock_state_adapter
    )
    
    print("**Error Simulation Testing:**")
    error_scenarios = [
        {"error_rate": 0},
        {"error_rate": 100},
        {"error_rate": "low"},
        {"error_rate": "high"},
        {"error_rate": 50}  # Unknown rate, uses default
    ]
    
    for scenario in error_scenarios:
        result = error_simulator.process(scenario)
        print(f"Error Rate: {scenario['error_rate']}")
        print(f"Simulation: {result}")
        print()

def demo_configuration_inspection():
    """Demonstrate how to inspect agent configuration."""
    print("🔍 **Configuration Inspection Demo**")
    print("=" * 50)
    
    # Create mock services
    mock_logging_service = MockServiceFactory.create_mock_logging_service()
    logger = mock_logging_service.get_class_logger(BranchingAgent)
    
    # Create agent with complex configuration
    agent = BranchingAgent(
        name="complex_branching",
        prompt="Complex branching logic",
        context={
            "input_fields": ["operation_result"],  # Automatically becomes success_field
            "success_values": ["PASSED", "COMPLETED", "OK", "GOOD"],
            "failure_values": ["FAILED", "ERROR", "BAD", "TIMEOUT"],
            "default_result": False,
            "fallback_fields": ["backup_result", "status", "outcome"]
        },
        logger=logger
    )
    
    # Inspect configuration
    config = agent.get_configuration_info()
    
    print("**Agent Configuration:**")
    for key, value in config.items():
        print(f"{key}: {value}")
    print()
    
    # Show how configuration affects behavior
    print("**Behavior Examples:**")
    test_inputs = [
        {"operation_result": "PASSED"},
        {"backup_result": "COMPLETED"},  # Uses fallback
        {"unknown_field": "value"}  # No relevant field
    ]
    
    for inputs in test_inputs:
        success, field_used, value_found = agent._determine_success_detailed(inputs)
        print(f"Input: {inputs}")
        print(f"Success: {success}, Field Used: {field_used}, Value: {value_found}")
        print()

if __name__ == "__main__":
    print("🎯 **Enhanced BranchingAgent Demonstration**")
    print("=" * 60)
    print("This demo shows the flexible, configurable BranchingAgent")
    print("that can be used for both testing and production workflows.")
    print()
    
    demo_default_configuration()
    demo_custom_configuration()
    demo_workflow_testing_scenarios()
    demo_configuration_inspection()
    
    print("✨ **Key Benefits:**")
    print("- Configurable success criteria for any field")
    print("- Custom success/failure values")
    print("- Fallback field support")
    print("- Useful for both testing and production")
    print("- Clear logging and decision tracking")
    print("- Backward compatible with existing workflows")
