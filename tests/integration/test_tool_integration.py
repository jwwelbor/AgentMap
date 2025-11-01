"""
Integration tests for tool support in AgentMap.

Tests end-to-end functionality of:
- CSV parsing with tool fields
- Tool loading from modules
- ToolAgent instantiation and execution
- OrchestratorService injection
- Tool selection and execution
- Error scenarios
- Backward compatibility
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from langchain_core.tools import tool

from agentmap.runtime_api import ensure_initialized, run_workflow
from agentmap.models.validation.csv_row_model import CSVRowModel
from agentmap.services.tool_loader import load_tools_from_module


class TestToolIntegration:
    """Integration tests for tool support with real services."""

    @pytest.fixture
    def initialized_agentmap(self):
        """Ensure AgentMap is initialized for testing."""
        ensure_initialized()
        return True

    @pytest.fixture
    def tool_module_content(self):
        """Provide example tool module content."""
        return '''"""Example calculator tools for testing."""
from langchain_core.tools import tool


@tool
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@tool
def subtract(a: int, b: int) -> int:
    """Subtract second number from first."""
    return a - b


@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers together."""
    return a * b
'''

    @pytest.fixture
    def temp_tool_module(self, tool_module_content):
        """Create temporary tool module file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_tools.py", delete=False
        ) as f:
            f.write(tool_module_content)
            temp_path = f.name

        yield temp_path

        # Cleanup
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass

    def test_csv_parsing_with_tool_fields(self):
        """Test CSV row parsing with Available_Tools and Tool_Source fields."""
        csv_row_data = {
            "GraphName": "TestGraph",
            "Node": "ToolNode",
            "AgentType": "tool_agent",
            "Available_Tools": "add|subtract|multiply",
            "Tool_Source": "calculator_tools.py",
            "Prompt": "Perform calculation",
        }

        # Validate CSV row with tool fields
        csv_row = CSVRowModel(**csv_row_data)

        assert csv_row.Available_Tools == "add|subtract|multiply"
        assert csv_row.Tool_Source == "calculator_tools.py"
        assert csv_row.AgentType == "tool_agent"

    def test_csv_parsing_backward_compatibility(self):
        """Test CSV parsing without tool fields maintains backward compatibility."""
        csv_row_data = {
            "GraphName": "LegacyGraph",
            "Node": "EchoNode",
            "AgentType": "echo",
            "Prompt": "Echo message",
        }

        # Should parse successfully without tool fields
        csv_row = CSVRowModel(**csv_row_data)

        assert csv_row.Available_Tools is None
        assert csv_row.Tool_Source is None
        assert csv_row.AgentType == "echo"

    def test_tool_loading_from_module(self, temp_tool_module):
        """Test loading tools from a Python module."""
        tools = load_tools_from_module(temp_tool_module)

        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "add" in tool_names
        assert "subtract" in tool_names
        assert "multiply" in tool_names

        # Verify tool descriptions
        add_tool = next(t for t in tools if t.name == "add")
        assert "add two numbers" in add_tool.description.lower()

    def test_tool_loading_missing_module(self):
        """Test error handling when tool module does not exist."""
        with pytest.raises(ImportError) as exc_info:
            load_tools_from_module("nonexistent_module.py")

        assert "Tool module not found" in str(exc_info.value)
        assert "nonexistent_module.py" in str(exc_info.value)

    def test_tool_loading_no_tools_in_module(self):
        """Test error handling when module has no @tool decorated functions."""
        # Create module with no tools
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_empty.py", delete=False
        ) as f:
            f.write(
                '''"""Empty module with no tools."""

def regular_function():
    """Not a tool."""
    return "Not decorated"
'''
            )
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                load_tools_from_module(temp_path)

            assert "No @tool decorated functions found" in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_tool_agent_instantiation(self, temp_tool_module):
        """Test creating ToolAgent with tools from module."""
        from agentmap.agents.builtins.tool_agent import ToolAgent

        # Load tools
        tools = load_tools_from_module(temp_tool_module)

        # Create ToolAgent
        agent = ToolAgent(
            name="calculator",
            prompt="Perform calculations",
            context={"matching_strategy": "algorithm"},
            tools=tools,
        )

        assert agent.name == "calculator"
        assert len(agent.tools) == 3
        assert agent.matching_strategy == "algorithm"

    def test_tool_agent_orchestrator_injection(self, initialized_agentmap, temp_tool_module):
        """Test OrchestratorService injection into ToolAgent."""
        from agentmap.agents.builtins.tool_agent import ToolAgent
        from agentmap.di.containers import ApplicationContainer

        # Get services from container
        container = ApplicationContainer()
        container.init_resources()
        orchestrator_service = container.orchestrator_service()
        tools = load_tools_from_module(temp_tool_module)

        # Create agent
        agent = ToolAgent(
            name="calculator",
            prompt="Perform math operations",
            tools=tools,
        )

        # Configure orchestrator service
        agent.configure_orchestrator_service(orchestrator_service)

        assert agent.orchestrator_service is not None

    def test_tool_agent_single_tool_optimization(self, temp_tool_module):
        """Test ToolAgent optimization when only one tool is available."""
        from agentmap.agents.builtins.tool_agent import ToolAgent
        from unittest.mock import Mock

        # Load tools and take only one
        all_tools = load_tools_from_module(temp_tool_module)
        single_tool = [all_tools[0]]

        # Create mock logger
        mock_logger = Mock()

        # Create agent with single tool
        agent = ToolAgent(
            name="adder",
            prompt="Add numbers",
            tools=single_tool,
            logger=mock_logger,
        )

        # Execute should bypass orchestrator service
        result = agent.process({"a": 5, "b": 3})

        assert result == "8"  # 5 + 3 = 8

    def test_tool_agent_selection_and_execution(
        self, initialized_agentmap, temp_tool_module
    ):
        """Test end-to-end tool selection and execution."""
        from agentmap.agents.builtins.tool_agent import ToolAgent
        from agentmap.di.containers import ApplicationContainer
        from unittest.mock import Mock

        # Get services
        container = ApplicationContainer()
        container.init_resources()
        orchestrator_service = container.orchestrator_service()
        llm_service = container.llm_service()

        # Load tools
        tools = load_tools_from_module(temp_tool_module)

        # Create mock logger
        mock_logger = Mock()

        # Create agent with inline descriptions
        agent = ToolAgent(
            name="calculator",
            prompt="Do math",
            context={
                "matching_strategy": "algorithm",
                "available_tools": 'add("adds numbers")|subtract("subtracts numbers")|multiply("multiplies numbers")',
            },
            tools=tools,
            logger=mock_logger,
        )

        # Configure services
        agent.configure_llm_service(llm_service)
        agent.configure_orchestrator_service(orchestrator_service)

        # Execute with clear input for addition
        result = agent.process({"input": "add these numbers", "a": 10, "b": 5})

        assert result == "15"  # 10 + 5 = 15

    def test_tool_description_resolution_priority(self, temp_tool_module):
        """Test tool description resolution with CSV override priority."""
        from agentmap.agents.builtins.tool_agent import ToolAgent

        tools = load_tools_from_module(temp_tool_module)

        # Create agent with CSV inline descriptions
        agent = ToolAgent(
            name="calculator",
            prompt="Calculate",
            context={
                "available_tools": 'add("custom add description")|subtract("custom subtract")',
            },
            tools=tools,
        )

        # CSV descriptions should override tool descriptions
        assert (
            agent.tool_descriptions["add"]["description"]
            == "custom add description"
        )
        assert (
            agent.tool_descriptions["subtract"]["description"]
            == "custom subtract"
        )

        # Tool without CSV override keeps original description
        assert "multiply" in agent.tool_descriptions["multiply"]["description"].lower()

    def test_csv_validation_tool_source_format(self):
        """Test CSV validation for Tool_Source format."""
        # Valid .py file
        csv_row_valid = CSVRowModel(
            GraphName="Test",
            Node="Tool1",
            Tool_Source="my_tools.py",
            Available_Tools="tool1|tool2",
        )
        assert csv_row_valid.Tool_Source == "my_tools.py"

        # Valid toolnode keyword
        csv_row_toolnode = CSVRowModel(
            GraphName="Test",
            Node="Tool2",
            Tool_Source="toolnode",
            Available_Tools="tool1",
        )
        assert csv_row_toolnode.Tool_Source == "toolnode"

        # Invalid format
        with pytest.raises(ValueError) as exc_info:
            CSVRowModel(
                GraphName="Test",
                Node="Tool3",
                Tool_Source="invalid_format",
                Available_Tools="tool1",
            )
        assert "must be either 'toolnode' or a .py file path" in str(
            exc_info.value
        ).lower()

    def test_csv_validation_available_tools_format(self):
        """Test CSV validation for Available_Tools format."""
        # Valid pipe-separated tools
        csv_row = CSVRowModel(
            GraphName="Test",
            Node="Tool1",
            Available_Tools="tool_one|tool_two|tool_three",
            Tool_Source="tools.py",
        )
        assert csv_row.Available_Tools == "tool_one|tool_two|tool_three"

        # Invalid tool name (non-alphanumeric)
        with pytest.raises(ValueError) as exc_info:
            CSVRowModel(
                GraphName="Test",
                Node="Tool2",
                Available_Tools="valid-tool|invalid.tool",
                Tool_Source="tools.py",
            )
        assert "invalid tool name" in str(exc_info.value).lower()

    def test_csv_warning_tools_without_source(self):
        """Test warning when Available_Tools specified without Tool_Source."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            CSVRowModel(
                GraphName="Test",
                Node="ToolNode",
                Available_Tools="tool1|tool2",
                # Tool_Source intentionally missing
            )

            assert len(w) == 1
            assert "Available_Tools but no Tool_Source" in str(w[0].message)

    def test_backward_compatibility_workflows(self, initialized_agentmap):
        """Test that existing workflows without tools continue working."""
        csv_row = CSVRowModel(
            GraphName="LegacyWorkflow",
            Node="EchoNode",
            AgentType="echo",
            Prompt="Hello world",
            Input_Fields="message",
            Output_Field="result",
        )

        # Should have no tool fields
        assert csv_row.Available_Tools is None
        assert csv_row.Tool_Source is None

        # Existing agent types should still work
        assert csv_row.AgentType == "echo"
