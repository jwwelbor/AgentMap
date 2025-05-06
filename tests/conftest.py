# conftest.py
import logging
import os
from pathlib import Path

import pandas as pd
import pytest

# Import directly from agent files to avoid potential circular issues
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.echo_agent import EchoAgent

# Import GraphBuilder directly from the file
from agentmap.graph.builder import GraphBuilder
from agentmap.logging import TRACE


def pytest_configure(config):
    # Enable logging during tests
    logging.basicConfig(
        level=TRACE,
        format="[%(levelname)s] %(name)s: %(message)s"
    )
    
    
@pytest.fixture
def example_csv_path():
    """Path to an example CSV file that exists."""
    path = Path("examples/LinearGraph.csv")
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
def default_agent():
    """A default agent for testing."""
    return DefaultAgent(
        name="TestAgent",
        prompt="Test prompt",
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )

@pytest.fixture
def echo_agent():
    """An echo agent for testing."""
    return EchoAgent(
        name="EchoTest",
        prompt="",
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