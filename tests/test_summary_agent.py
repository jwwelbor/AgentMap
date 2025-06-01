# tests/test_summary_agent.py
"""Tests for SummaryAgent functionality."""

import pytest
from unittest.mock import patch, MagicMock

from agentmap.agents.builtins.summary_agent import SummaryAgent
from tests.conftest import create_test_agent


def test_summary_agent_initialization_defaults(test_logger, test_execution_tracker):
    """Test SummaryAgent initialization with default parameters."""
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt"
    )
    
    assert agent.name == "test_agent"
    assert agent.prompt == "Test prompt"
    assert agent.format_template == "{key}: {value}"
    assert agent.separator == "\\n\\n"
    assert agent.include_keys is True
    assert agent.use_llm is False


def test_summary_agent_initialization_custom_params(test_logger, test_execution_tracker):
    """Test SummaryAgent initialization with custom parameters."""
    context = {
        "format": "Key: {key} | Value: {value}",
        "separator": "\\n---\\n",
        "include_keys": False
    }
    
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context=context
    )
    
    assert agent.format_template == "Key: {key} | Value: {value}"
    assert agent.separator == "\\n---\\n"
    assert agent.include_keys is False


def test_summary_agent_basic_concatenation_default(test_logger, test_execution_tracker):
    """Test basic concatenation with default configuration."""
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={
            "input_fields": ["field1", "field2"],
            "output_field": "summary"
        }
    )
    
    inputs = {"field1": "value1", "field2": "value2"}
    result = agent.run(inputs)
    
    summary = result["summary"]
    assert "field1: value1" in summary
    assert "field2: value2" in summary
    assert result["last_action_success"] is True


def test_summary_agent_custom_format(test_logger, test_execution_tracker):
    """Test basic concatenation with custom format."""
    context = {
        "format": "[{key}] -> {value}",
        "input_fields": ["field1", "field2"],
        "output_field": "summary"
    }
    
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context=context
    )
    
    inputs = {"field1": "value1", "field2": "value2"}
    result = agent.run(inputs)
    
    summary = result["summary"]
    assert "[field1] -> value1" in summary
    assert "[field2] -> value2" in summary
    assert result["last_action_success"] is True


def test_summary_agent_custom_separator(test_logger, test_execution_tracker):
    """Test basic concatenation with custom separator."""
    context = {
        "separator": " | ",
        "input_fields": ["field1", "field2"],
        "output_field": "summary"
    }
    
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context=context
    )
    
    inputs = {"field1": "value1", "field2": "value2"}
    result = agent.run(inputs)
    
    summary = result["summary"]
    assert " | " in summary
    assert result["last_action_success"] is True


def test_summary_agent_without_keys(test_logger, test_execution_tracker):
    """Test basic concatenation without including keys."""
    context = {
        "include_keys": False,
        "input_fields": ["field1", "field2"],
        "output_field": "summary"
    }
    
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context=context
    )
    
    inputs = {"field1": "value1", "field2": "value2"}
    result = agent.run(inputs)
    
    summary = result["summary"]
    assert "field1" not in summary
    assert "field2" not in summary
    assert "value1" in summary
    assert "value2" in summary
    assert result["last_action_success"] is True


def test_summary_agent_empty_inputs(test_logger, test_execution_tracker):
    """Test SummaryAgent with empty inputs."""
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={
            "input_fields": [],
            "output_field": "summary"
        }
    )
    
    result = agent.run({})
    
    assert result["summary"] == ""
    assert result["last_action_success"] is True


def test_summary_agent_none_values_handling(test_logger, test_execution_tracker):
    """Test SummaryAgent handling of None values in inputs."""
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={
            "input_fields": ["field1", "field2"],
            "output_field": "summary"
        }
    )
    
    inputs = {"field1": "value1", "field2": None}
    result = agent.run(inputs)
    
    summary = result["summary"]
    assert "field1: value1" in summary
    assert "field2" not in summary  # None values should be skipped
    assert result["last_action_success"] is True


def test_summary_agent_formatting_error_fallback(test_logger, test_execution_tracker):
    """Test SummaryAgent handling of formatting errors."""
    context = {
        "format": "{key}: {value} {extra}",  # Extra param will cause error
        "input_fields": ["field1"],
        "output_field": "summary"
    }
    
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context=context
    )
    
    inputs = {"field1": "value1"}
    result = agent.run(inputs)
    
    # Should fall back to "key: value" format
    summary = result["summary"]
    assert "field1: value1" in summary
    assert result["last_action_success"] is True


def test_summary_agent_multiple_fields_processing(test_logger, test_execution_tracker):
    """Test SummaryAgent processing multiple fields correctly."""
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={
            "input_fields": ["title", "content", "author", "date"],
            "output_field": "document_summary"
        }
    )
    
    inputs = {
        "title": "Test Document",
        "content": "This is the main content of the document.",
        "author": "John Doe", 
        "date": "2024-01-01"
    }
    
    result = agent.run(inputs)
    
    summary = result["document_summary"]
    assert "title: Test Document" in summary
    assert "content: This is the main content of the document." in summary
    assert "author: John Doe" in summary
    assert "date: 2024-01-01" in summary
    assert result["last_action_success"] is True


def test_summary_agent_dependencies_injection(test_logger, test_execution_tracker):
    """Test that SummaryAgent properly receives and uses injected dependencies."""
    agent = create_test_agent(
        SummaryAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt"
    )
    
    # Verify dependencies are properly injected
    assert agent._logger is not None
    assert agent._execution_tracker is not None
    assert agent.name == "test_agent"
    assert agent.prompt == "Test prompt"
