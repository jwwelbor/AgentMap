"""
Unit tests for ToolAgent.

Tests the ToolAgent implementation including protocol compliance,
tool selection delegation to OrchestratorService, and tool execution
via LangGraph ToolNode.
"""

import unittest
from unittest.mock import Mock, patch

from langchain_core.tools import tool

from agentmap.agents.builtins.tool_agent import ToolAgent
from agentmap.services.protocols import ToolSelectionCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestToolAgent(unittest.TestCase):
    """Test ToolAgent functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()

        # Create mock services
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.mock_execution_tracking = (
            self.mock_factory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter = self.mock_factory.create_mock_state_adapter_service()

        # Create real LangChain tools for testing (ToolNode requires real tools)
        @tool
        def get_weather(location: str) -> str:
            """Get current weather for a location"""
            return f"Weather for {location}"

        @tool
        def get_forecast(location: str, days: int = 3) -> str:
            """Get weather forecast for upcoming days"""
            return f"Forecast for {location} for {days} days"

        self.mock_tool_1 = get_weather
        self.mock_tool_2 = get_forecast

    def test_initialization_basic(self):
        """Test ToolAgent initialization with basic parameters."""
        # Arrange & Act
        agent = ToolAgent(
            name="weather_agent",
            prompt="Help with weather queries",
            context=None,
            tools=[self.mock_tool_1],
            logger=self.mock_logging.get_class_logger("test"),
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )

        # Assert
        self.assertEqual(agent.name, "weather_agent")
        self.assertEqual(agent.prompt, "Help with weather queries")
        self.assertEqual(len(agent.tools), 1)
        self.assertEqual(agent.matching_strategy, "tiered")
        self.assertEqual(agent.confidence_threshold, 0.8)
        self.assertEqual(agent.llm_type, "openai")
        self.assertEqual(agent.temperature, 0.2)

    def test_initialization_with_context(self):
        """Test ToolAgent initialization with context configuration."""
        # Arrange
        context = {
            "matching_strategy": "llm",
            "confidence_threshold": 0.9,
            "llm_type": "anthropic",
            "temperature": 0.5,
            "available_tools": "tool1|tool2",
        }

        # Act
        agent = ToolAgent(
            name="test_agent",
            prompt="Test prompt",
            context=context,
            tools=[self.mock_tool_1, self.mock_tool_2],
            logger=self.mock_logging.get_class_logger("test"),
            execution_tracking_service=self.mock_execution_tracking,
            state_adapter_service=self.mock_state_adapter,
        )

        # Assert
        self.assertEqual(agent.matching_strategy, "llm")
        self.assertEqual(agent.confidence_threshold, 0.9)
        self.assertEqual(agent.llm_type, "anthropic")
        self.assertEqual(agent.temperature, 0.5)

    def test_protocol_implementation_tool_capable(self):
        """Test that ToolAgent can work with tools (protocol compatibility)."""
        # Arrange & Act
        agent = ToolAgent(name="test_agent", prompt="Test", tools=[self.mock_tool_1])

        # Assert - Verify agent can work with tools
        # ToolAgent stores tools internally and uses them via ToolNode
        self.assertTrue(hasattr(agent, "tools"))
        self.assertEqual(len(agent.tools), 1)
        self.assertTrue(hasattr(agent, "tool_node"))
        # Verify it inherits from BaseAgent
        from agentmap.agents.base_agent import BaseAgent

        self.assertIsInstance(agent, BaseAgent)

    def test_protocol_implementation_tool_selection_capable(self):
        """Test that ToolAgent implements ToolSelectionCapableAgent protocol."""
        # Arrange & Act
        agent = ToolAgent(name="test_agent", prompt="Test", tools=[self.mock_tool_1])

        # Assert
        self.assertIsInstance(agent, ToolSelectionCapableAgent)

    def test_configure_orchestrator_service(self):
        """Test configuring orchestrator service via protocol method."""
        # Arrange
        agent = ToolAgent(
            name="test_agent",
            prompt="Test",
            tools=[self.mock_tool_1],
            logger=self.mock_logging.get_class_logger("test"),
        )
        mock_orchestrator = Mock()

        # Act
        agent.configure_orchestrator_service(mock_orchestrator)

        # Assert
        self.assertEqual(agent.orchestrator_service, mock_orchestrator)

    def test_tool_description_resolution_auto_extraction(self):
        """Test automatic extraction of tool descriptions from tool definitions."""

        # Arrange - Create a real tool with description
        @tool
        def calculate(a: int, b: int) -> int:
            """Perform mathematical calculations"""
            return a + b

        # Act
        agent = ToolAgent(
            name="calc_agent", prompt="Calculator", context={}, tools=[calculate]
        )

        # Assert
        self.assertIn("calculate", agent.tool_descriptions)
        self.assertIn(
            "mathematical calculations",
            agent.tool_descriptions["calculate"]["description"].lower(),
        )

    def test_tool_description_resolution_csv_override(self):
        """Test CSV inline descriptions override tool definitions."""

        # Arrange - Create a real tool
        @tool
        def search(query: str) -> str:
            """Original description"""
            return f"Results for {query}"

        # Note: The CSV override only works when there's a pipe separator
        # See _resolve_tool_descriptions logic: if "|" in available_tools and "(" in available_tools
        context = {
            "available_tools": 'search("Custom search description from CSV")|other_tool("desc")'
        }

        # Act
        agent = ToolAgent(
            name="search_agent", prompt="Search", context=context, tools=[search]
        )

        # Assert
        self.assertEqual(
            agent.tool_descriptions["search"]["description"],
            "Custom search description from CSV",
        )

    def test_tool_description_resolution_multiple_tools_csv(self):
        """Test parsing multiple tool descriptions from CSV format."""

        # Arrange - Create real tools
        @tool
        def tool1() -> str:
            """Original 1"""
            return "result1"

        @tool
        def tool2() -> str:
            """Original 2"""
            return "result2"

        context = {"available_tools": 'tool1("First tool") | tool2("Second tool")'}

        # Act
        agent = ToolAgent(
            name="multi_agent", prompt="Multi", context=context, tools=[tool1, tool2]
        )

        # Assert
        self.assertEqual(agent.tool_descriptions["tool1"]["description"], "First tool")
        self.assertEqual(agent.tool_descriptions["tool2"]["description"], "Second tool")

    def test_tools_to_node_format_transformation(self):
        """Test transformation of tools to node format for OrchestratorService."""
        # Arrange
        agent = ToolAgent(
            name="test_agent", prompt="Test", tools=[self.mock_tool_1, self.mock_tool_2]
        )

        # Act
        node_format = agent._tools_to_node_format(agent.tool_descriptions)

        # Assert
        self.assertIn("get_weather", node_format)
        self.assertIn("get_forecast", node_format)

        weather_node = node_format["get_weather"]
        self.assertEqual(weather_node["type"], "tool")
        self.assertEqual(
            weather_node["description"], "Get current weather for a location"
        )
        self.assertEqual(weather_node["prompt"], "Get current weather for a location")

    def test_single_tool_optimization(self):
        """Test that single tool bypasses selection and executes directly."""
        # Arrange
        agent = ToolAgent(
            name="single_tool_agent",
            prompt="Single tool",
            tools=[self.mock_tool_1],
            logger=self.mock_logging.get_class_logger("test"),
        )

        inputs = {"query": "What's the weather?"}

        with patch.object(
            agent, "_execute_tool", return_value="Weather result"
        ) as mock_execute:
            # Act
            result = agent.process(inputs)

            # Assert
            mock_execute.assert_called_once_with(self.mock_tool_1, inputs)
            self.assertEqual(result, "Weather result")

    def test_process_with_orchestrator_service(self):
        """Test process method delegates to OrchestratorService for multiple tools."""
        # Arrange
        agent = ToolAgent(
            name="multi_tool_agent",
            prompt="Multi tool",
            context={"matching_strategy": "tiered", "confidence_threshold": 0.8},
            tools=[self.mock_tool_1, self.mock_tool_2],
            logger=self.mock_logging.get_class_logger("test"),
        )

        mock_orchestrator = Mock()
        mock_orchestrator.select_best_node.return_value = "get_weather"
        agent.configure_orchestrator_service(mock_orchestrator)

        inputs = {"query": "What's the weather?"}

        with patch.object(
            agent, "_execute_tool", return_value="Weather: Sunny"
        ) as mock_execute:
            # Act
            result = agent.process(inputs)

            # Assert
            mock_orchestrator.select_best_node.assert_called_once()
            call_kwargs = mock_orchestrator.select_best_node.call_args[1]
            self.assertEqual(call_kwargs["input_text"], "What's the weather?")
            self.assertEqual(call_kwargs["strategy"], "tiered")
            self.assertEqual(call_kwargs["confidence_threshold"], 0.8)
            self.assertIn("get_weather", call_kwargs["available_nodes"])

            mock_execute.assert_called_once()
            self.assertEqual(result, "Weather: Sunny")

    def test_process_without_orchestrator_service_raises_error(self):
        """Test process raises ValueError when OrchestratorService not configured."""
        # Arrange
        agent = ToolAgent(
            name="multi_tool_agent",
            prompt="Multi tool",
            tools=[self.mock_tool_1, self.mock_tool_2],
            logger=self.mock_logging.get_class_logger("test"),
        )

        inputs = {"query": "test"}

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            agent.process(inputs)

        self.assertIn("OrchestratorService not configured", str(context.exception))

    def test_execute_tool_invokes_tool_directly(self):
        """Test _execute_tool method invokes tool directly (LangGraph 1.x compatibility)."""
        # Arrange
        agent = ToolAgent(
            name="test_agent",
            prompt="Test",
            tools=[self.mock_tool_1],
            logger=self.mock_logging.get_class_logger("test"),
        )

        inputs = {"location": "Seattle"}

        # Act
        result = agent._execute_tool(self.mock_tool_1, inputs)

        # Assert - Tool invoked directly, no ToolNode wrapper in LangGraph 1.x
        self.assertEqual(result, "Weather for Seattle")

    def test_get_input_text_with_configured_fields(self):
        """Test _get_input_text extracts text from configured input fields."""
        # Arrange
        agent = ToolAgent(
            name="test_agent",
            prompt="Test",
            context={"input_fields": "user_query|request"},
            tools=[self.mock_tool_1],
        )
        agent.input_fields = ["user_query", "request"]

        inputs = {"user_query": "What's the weather?", "other_field": "ignored"}

        # Act
        result = agent._get_input_text(inputs)

        # Assert
        self.assertEqual(result, "What's the weather?")

    def test_get_input_text_fallback_to_common_fields(self):
        """Test _get_input_text falls back to common field names."""
        # Arrange
        agent = ToolAgent(
            name="test_agent",
            prompt="Test",
            tools=[self.mock_tool_1],
            logger=self.mock_logging.get_class_logger("test"),
        )

        inputs = {"query": "Search query text", "other": "data"}

        # Act
        result = agent._get_input_text(inputs)

        # Assert
        self.assertEqual(result, "Search query text")

    def test_get_input_text_last_resort_any_string(self):
        """Test _get_input_text uses any string field as last resort."""
        # Arrange
        agent = ToolAgent(
            name="test_agent",
            prompt="Test",
            tools=[self.mock_tool_1],
            logger=self.mock_logging.get_class_logger("test"),
        )

        inputs = {
            "available_tools": "ignored",  # Explicitly ignored
            "custom_field": "Custom text value",
        }

        # Act
        result = agent._get_input_text(inputs)

        # Assert
        self.assertEqual(result, "Custom text value")

    def test_get_tool_by_name_success(self):
        """Test _get_tool_by_name retrieves tool successfully."""
        # Arrange
        agent = ToolAgent(
            name="test_agent", prompt="Test", tools=[self.mock_tool_1, self.mock_tool_2]
        )

        # Act
        tool = agent._get_tool_by_name("get_forecast")

        # Assert
        self.assertEqual(tool, self.mock_tool_2)

    def test_get_tool_by_name_not_found(self):
        """Test _get_tool_by_name raises ValueError for missing tool."""
        # Arrange
        agent = ToolAgent(name="test_agent", prompt="Test", tools=[self.mock_tool_1])

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            agent._get_tool_by_name("nonexistent_tool")

        self.assertIn("Tool 'nonexistent_tool' not found", str(context.exception))


if __name__ == "__main__":
    unittest.main()
