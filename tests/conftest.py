# tests/conftest.py
"""
Pytest configuration and fixtures for AgentMap testing.

This provides a clean, consistent testing environment with proper
separation between unit tests (mocked) and integration tests (real DI).
"""
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import pytest

from tests.utils.mock_factory import MockServiceFactory
from tests.utils.base_test import TestDataFactory


def pytest_configure(config):
    """Configure pytest with proper logging and markers."""
    # Enable logging during tests
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(levelname)s] %(name)s: %(message)s"
    )
    
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests with mocked dependencies")
    config.addinivalue_line("markers", "integration: Integration tests with real DI container") 
    config.addinivalue_line("markers", "e2e: End-to-end tests with full application")


# =============================================================================
# Mock Service Fixtures (for unit tests)
# =============================================================================

@pytest.fixture
def mock_service_factory():
    """Provide the mock service factory."""
    return MockServiceFactory()


@pytest.fixture
def mock_config_service():
    """Provide a mock ConfigService."""
    return MockServiceFactory.create_config_service()


@pytest.fixture
def mock_app_config_service():
    """Provide a mock AppConfigService."""
    return MockServiceFactory.create_app_config_service()


@pytest.fixture
def mock_logging_service():
    """Provide a mock LoggingService."""
    return MockServiceFactory.create_logging_service()


@pytest.fixture
def mock_llm_service():
    """Provide a mock LLMService."""
    return MockServiceFactory.create_llm_service()


@pytest.fixture
def mock_execution_tracker():
    """Provide a mock ExecutionTracker."""
    return MockServiceFactory.create_execution_tracker()


@pytest.fixture
def mock_node_registry_service():
    """Provide a mock NodeRegistryService."""
    return MockServiceFactory.create_node_registry_service()


@pytest.fixture
def mock_storage_service_manager():
    """Provide a mock StorageServiceManager."""
    return MockServiceFactory.create_storage_service_manager()


@pytest.fixture
def mock_container():
    """Provide a complete mock DI container."""
    return MockServiceFactory.create_mock_container()


@pytest.fixture
def test_logger(mock_logging_service):
    """Provide a test logger from mock logging service."""
    return mock_logging_service.get_logger("test")


# =============================================================================
# Real DI Container Fixtures (for integration tests)
# =============================================================================

@pytest.fixture
def temp_test_dir():
    """Provide a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config_path(temp_test_dir):
    """Create a test configuration file."""
    config_path = Path(temp_test_dir) / "test_config.yaml"
    storage_config_path = Path(temp_test_dir) / "storage_config.yaml"
    
    config_content = f"""
logging:
  level: DEBUG
  format: "[%(levelname)s] %(name)s: %(message)s"

llm:
  anthropic:
    api_key: "test_key"
    model: "claude-3-sonnet-20240229"
    temperature: 0.7
  openai:
    api_key: "test_key"
    model: "gpt-3.5-turbo"
    temperature: 0.7

execution:
  max_retries: 3
  timeout: 30

storage_config_path: "{storage_config_path}"
"""
    
    storage_config_content = f"""
csv:
  default_directory: "{temp_test_dir}/csv_data"
  collections: {{}}

vector:
  default_provider: "chroma"
  collections: {{}}

kv:
  default_provider: "local"
  collections: {{}}
"""
    
    with open(config_path, 'w') as f:
        f.write(config_content)
        
    with open(storage_config_path, 'w') as f:
        f.write(storage_config_content)
    
    return config_path


@pytest.fixture
def integration_container(test_config_path):
    """Provide a real DI container for integration tests."""
    from agentmap.di import initialize_di, cleanup
    
    # Initialize container
    container = initialize_di(test_config_path)
    
    yield container
    
    # Cleanup after test
    cleanup()


@pytest.fixture
def real_logging_service(integration_container):
    """Provide real logging service from DI container."""
    return integration_container.logging_service()


@pytest.fixture
def real_execution_tracker(integration_container):
    """Provide real execution tracker from DI container."""
    return integration_container.execution_tracker()


@pytest.fixture
def integration_logger(real_logging_service):
    """Provide a real logger for integration tests."""
    return real_logging_service.get_logger("integration_test")


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_state():
    """Provide a sample state dictionary."""
    return TestDataFactory.create_sample_state()


@pytest.fixture
def sample_agent_context():
    """Provide a sample agent context."""
    return TestDataFactory.create_agent_context()


@pytest.fixture
def sample_llm_config():
    """Provide a sample LLM configuration."""
    return TestDataFactory.create_llm_config()


@pytest.fixture
def custom_state():
    """Factory fixture for creating custom state dictionaries."""
    return TestDataFactory.create_sample_state


@pytest.fixture
def custom_context():
    """Factory fixture for creating custom agent contexts."""
    return TestDataFactory.create_agent_context


@pytest.fixture
def custom_llm_config():
    """Factory fixture for creating custom LLM configurations."""
    return TestDataFactory.create_llm_config


# =============================================================================
# Agent Creation Fixtures (works for both unit and integration)
# =============================================================================

@pytest.fixture
def agent_factory(request):
    """
    Factory for creating agents with appropriate dependencies.
    
    Automatically detects whether the test is unit or integration
    and provides the appropriate services.
    """
    def create_agent(agent_class, name="TestAgent", prompt="Test prompt", context=None, **kwargs):
        context = context or {}
        
        # Check if this is an integration test
        if hasattr(request, 'fixturenames') and 'integration_container' in request.fixturenames:
            # Integration test - use real services
            container = request.getfixturevalue('integration_container')
            logging_service = container.logging_service()
            logger = logging_service.get_logger("test")
            execution_tracker = container.execution_tracker()
        else:
            # Unit test - use mocks
            mock_logging_service = request.getfixturevalue('mock_logging_service')
            logger = mock_logging_service.get_logger("test")
            execution_tracker = request.getfixturevalue('mock_execution_tracker')
        
        return agent_class(
            name=name,
            prompt=prompt,
            logger=logger,
            execution_tracker_service=execution_tracker_service,
            context=context,
            **kwargs
        )
    
    return create_agent


# =============================================================================
# Legacy Compatibility Fixtures (for existing tests)
# =============================================================================

@pytest.fixture
def example_csv_path():
    """Path to an example CSV file that exists."""
    path = Path("../examples/LinearGraph.csv")
    if path.exists():
        return path
    # Fallback for tests that need a CSV
    return Path("tests/data/sample.csv")  # You'll need to create this


@pytest.fixture
def default_agent(agent_factory):
    """A default agent for testing."""
    from agentmap.agents.builtins.default_agent import DefaultAgent
    return agent_factory(
        DefaultAgent,
        name="TestAgent",
        prompt="Test prompt",
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )


@pytest.fixture
def echo_agent(agent_factory):
    """An echo agent for testing."""
    from agentmap.agents.builtins.echo_agent import EchoAgent
    return agent_factory(
        EchoAgent,
        name="EchoTest",
        prompt="",
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )


# =============================================================================
# Utility Functions for Test Organization
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests based on their location and content.
    
    This helps organize tests without requiring manual marking.
    """
    for item in items:
        # Mark tests based on path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        
        # Mark tests that use real DI container
        if "integration_container" in item.fixturenames:
            item.add_marker(pytest.mark.integration)
        
        # Mark tests that only use mocks
        elif any(fixture.startswith("mock_") for fixture in item.fixturenames):
            item.add_marker(pytest.mark.unit)


# =============================================================================
# Custom Assertion Helpers
# =============================================================================

@pytest.fixture
def assert_helpers():
    """Provide custom assertion helpers."""
    class AssertHelpers:
        @staticmethod
        def assert_agent_success(result: Dict[str, Any]):
            """Assert that an agent execution was successful."""
            assert isinstance(result, dict)
            assert result.get("last_action_success") is True
        
        @staticmethod
        def assert_service_available(service, method_name: str):
            """Assert that a service has a specific method available."""
            assert hasattr(service, method_name)
            assert callable(getattr(service, method_name))
        
        @staticmethod
        def assert_mock_called_properly(mock, expected_calls: int = 1):
            """Assert that a mock was called the expected number of times."""
            assert mock.call_count == expected_calls
    
    return AssertHelpers()