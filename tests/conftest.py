# conftest.py
import logging
import os
from pathlib import Path

import pandas as pd
import pytest

# Import directly from agent files to avoid potential circular issues
from agentmap.agents import DefaultAgent
from agentmap.agents import EchoAgent
# Import GraphBuilder directly from the file
from agentmap.graph.builder import GraphBuilder
from agentmap.di import initialize_di



def pytest_configure(config):
    # Enable logging during tests
    logging.basicConfig(
        level="DEBUG",
        format="[%(levelname)s] %(name)s: %(message)s"
    )


# =============================================================================
# DI Test Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def test_di_container():
    """Session-scoped DI container for efficient test execution."""
    from agentmap.di import initialize_di
    return initialize_di()


@pytest.fixture
def test_logger(test_di_container):
    """Provide test logger from DI container."""
    logging_service = test_di_container.logging_service()
    return logging_service.get_logger("test")


@pytest.fixture
def test_execution_tracker(test_di_container):
    """Provide test execution tracker from DI container."""
    return test_di_container.execution_tracker()


def create_test_agent(agent_class, name, test_logger, test_execution_tracker, **kwargs):
    """
    Factory for creating agents with proper test dependencies.
    
    Args:
        agent_class: Agent class to instantiate
        name: Agent name
        test_logger: Logger fixture
        test_execution_tracker: ExecutionTracker fixture
        **kwargs: Additional arguments (prompt, context, etc.)
    
    Returns:
        Properly initialized agent instance
    """
    return agent_class(
        name=name,
        logger=test_logger,
        execution_tracker=test_execution_tracker,
        **kwargs
    )


# =============================================================================
# Legacy Test Fixtures 
# =============================================================================
    
    
@pytest.fixture
def example_csv_path():
    """Path to an example CSV file that exists."""
    path = Path("../examples/LinearGraph.csv")
    assert path.exists(), f"Example CSV not found: {path}"
    return path

@pytest.fixture
def sample_state():
    """A sample state dictionary for testing."""
    return {
        "input": "Test message",
        "last_action_success": True
    }

@pytest.fixture
def default_agent(test_logger, test_execution_tracker):
    """A default agent for testing."""
    return DefaultAgent(
        name="TestAgent",
        prompt="Test prompt",
        logger=test_logger,
        execution_tracker=test_execution_tracker,
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )

@pytest.fixture
def echo_agent(test_logger, test_execution_tracker):
    """An echo agent for testing."""
    return EchoAgent(
        name="EchoTest",
        prompt="",
        logger=test_logger,
        execution_tracker=test_execution_tracker,
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )

@pytest.fixture
def graph_builder(example_csv_path):
    """A graph builder with example CSV loaded."""
    return GraphBuilder(example_csv_path)

@pytest.fixture
def built_graphs(graph_builder):
    """The built graphs from the example CSV."""
    return graph_builder.build()