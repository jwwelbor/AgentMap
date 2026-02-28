# tests/utils/base_test.py
"""
Base test classes and utilities for consistent testing patterns.

This module provides base classes and utilities that ensure consistent
testing patterns across the entire test suite.
"""
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Type
from unittest.mock import Mock

from tests.utils.mock_service_factory import MockServiceFactory, ServiceMockBuilder


class BaseUnitTest:
    """
    Base class for unit tests with mocked dependencies.

    Unit tests should inherit from this class to get standard
    mock services and test utilities.
    """

    def setup_method(self):
        """Set up mocks for each test method."""
        self.mock_factory = MockServiceFactory()
        self.setup_mocks()

    def setup_mocks(self):
        """Override this method to set up specific mocks for your test class."""
        # Default mocks that most tests will need
        self.mock_logging_service = self.mock_factory.create_mock_logging_service()
        self.mock_execution_tracker = self.mock_factory.create_mock_execution_tracker()
        self.mock_config_service = self.mock_factory.create_mock_app_config_service()
        self.mock_app_config_service = (
            self.mock_factory.create_mock_app_config_service()
        )

        # Common test logger
        self.test_logger = self.mock_logging_service.get_logger("test")

    def create_service_mock(self, service_type: str) -> ServiceMockBuilder:
        """
        Create a customizable service mock using the builder pattern.

        Args:
            service_type: Type of service to mock (e.g., 'llm_service')

        Returns:
            ServiceMockBuilder for customization
        """
        return ServiceMockBuilder(service_type)

    def assert_mock_called_with_args(
        self, mock_method, expected_args: tuple, expected_kwargs: dict = None
    ):
        """Assert that a mock method was called with specific arguments."""
        expected_kwargs = expected_kwargs or {}
        mock_method.assert_called_with(*expected_args, **expected_kwargs)

    def assert_service_interaction(
        self, service_mock: Mock, method_name: str, call_count: int = 1
    ):
        """Assert that a service method was called the expected number of times."""
        method_mock = getattr(service_mock, method_name)
        assert (
            method_mock.call_count == call_count
        ), f"{method_name} was called {method_mock.call_count} times, expected {call_count}"


class BaseIntegrationTest:
    """
    Base class for integration tests with real DI container.

    Integration tests should inherit from this class to get a properly
    configured DI container with real services.
    """

    def setup_method(self):
        """Set up real DI container for integration testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = self.create_test_config()
        self.container = self.initialize_container()

    def teardown_method(self):
        """Clean up test environment."""
        if hasattr(self, "container"):
            from agentmap.di import cleanup

            cleanup()

        if hasattr(self, "temp_dir"):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_config(self) -> Path:
        """Create a test configuration file."""
        config_path = Path(self.temp_dir) / "test_config.yaml"
        storage_config_path = Path(self.temp_dir) / "storage_config.yaml"

        config_content = f"""
logging:
  level: DEBUG
  format: "[%(levelname)s] %(name)s: %(message)s"

llm:
  anthropic:
    api_key: "test_key"
    model: "claude-3-5-sonnet-20241022"
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
  default_directory: "{self.temp_dir}/csv_data"
  collections: {{}}

vector:
  default_provider: "chroma"
  collections: {{}}

kv:
  default_provider: "local"
  collections: {{}}
"""

        with open(config_path, "w") as f:
            f.write(config_content)

        with open(storage_config_path, "w") as f:
            f.write(storage_config_content)

        return config_path

    def initialize_container(self):
        """Initialize the DI container with test configuration."""
        from agentmap.di import initialize_di

        return initialize_di(self.config_path)

    def get_service(self, service_name: str):
        """Get a service from the DI container."""
        return getattr(self.container, service_name)()


class AgentTestMixin:
    """
    Mixin class for testing agents with standard patterns.

    This provides common utilities for agent testing regardless
    of whether you're doing unit or integration testing.
    """

    def create_test_agent(
        self,
        agent_class: Type,
        name: str = "TestAgent",
        prompt: str = "Test prompt",
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Create an agent for testing with proper dependencies.

        This method works for both unit tests (with mocks) and
        integration tests (with real services).
        """
        context = context or {}

        # For unit tests, use mocks
        if hasattr(self, "mock_logging_service"):
            logger = self.mock_logging_service.get_logger("test")
            execution_tracking_service = self.mock_execution_tracker
        # For integration tests, use real services
        elif hasattr(self, "container"):
            logging_service = self.container.logging_service()
            logger = logging_service.get_logger("test")
            execution_tracking_service = self.container.execution_tracker()
        else:
            raise ValueError(
                "Test class must inherit from BaseUnitTest or BaseIntegrationTest"
            )

        return agent_class(
            name=name,
            prompt=prompt,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
            context=context,
            **kwargs,
        )

    def run_agent_and_assert_success(
        self, agent, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run an agent and assert it completed successfully."""
        result = agent.run(input_data)
        assert isinstance(result, dict)
        assert result.get("last_action_success") is True
        return result

    def assert_agent_state(self, agent, expected_state: Dict[str, Any]):
        """Assert that an agent has the expected internal state."""
        for key, expected_value in expected_state.items():
            actual_value = getattr(agent, key, None)
            assert (
                actual_value == expected_value
            ), f"Agent.{key} = {actual_value}, expected {expected_value}"


class ServiceTestMixin:
    """
    Mixin class for testing services with standard patterns.

    This provides utilities for testing services whether they're
    mocked or real.
    """

    def assert_service_configured(self, service, expected_config_keys: list):
        """Assert that a service is properly configured."""
        for key in expected_config_keys:
            assert hasattr(service, key) or hasattr(
                service, f"_{key}"
            ), f"Service missing {key}"

    def assert_service_method_exists(self, service, method_name: str):
        """Assert that a service has a specific method."""
        assert hasattr(service, method_name), f"Service missing method {method_name}"
        assert callable(
            getattr(service, method_name)
        ), f"Service.{method_name} is not callable"

    def mock_service_method_response(
        self, service_mock: Mock, method_name: str, response: Any
    ):
        """Set up a mock service method to return a specific response."""
        getattr(service_mock, method_name).return_value = response


# Test data factories for consistent test data creation
class TestDataFactory:
    """Factory for creating consistent test data."""

    @staticmethod
    def create_sample_state(
        input_value: str = "test input", success: bool = True, **additional_fields
    ) -> Dict[str, Any]:
        """Create a sample state dictionary."""
        state = {
            "input": input_value,
            "last_action_success": success,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        state.update(additional_fields)
        return state

    @staticmethod
    def create_agent_context(
        input_fields: list = None, output_field: str = "output", **additional_context
    ) -> Dict[str, Any]:
        """Create a sample agent context."""
        input_fields = input_fields or ["input"]
        context = {"input_fields": input_fields, "output_field": output_field}
        context.update(additional_context)
        return context

    @staticmethod
    def create_llm_config(
        provider: str = "openai", model: str = "gpt-3.5-turbo", **additional_config
    ) -> Dict[str, Any]:
        """Create a sample LLM configuration."""
        config = {"api_key": "test_key", "model": model, "temperature": 0.7}
        config.update(additional_config)
        return {provider: config}


# Convenience classes that combine mixins for common use cases
class AgentUnitTest(BaseUnitTest, AgentTestMixin):
    """Unit test class specifically for testing agents."""


class ServiceUnitTest(BaseUnitTest, ServiceTestMixin):
    """Unit test class specifically for testing services."""


class AgentIntegrationTest(BaseIntegrationTest, AgentTestMixin):
    """Integration test class specifically for testing agents."""


class ServiceIntegrationTest(BaseIntegrationTest, ServiceTestMixin):
    """Integration test class specifically for testing services."""
