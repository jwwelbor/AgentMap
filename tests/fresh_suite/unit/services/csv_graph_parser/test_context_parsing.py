"""
Unit tests for CSV context field parsing in NodeSpecConverter.

The context column in a CSV workflow file can contain structured configuration
(routing params, provider, model, temperature, etc.). These tests verify that
the converter correctly parses the raw context string into a dict whose keys
are accessible at the top level — e.g. so that an LLM agent can read
`self.context.get("routing_enabled")` directly without manually parsing JSON.

Supported formats:
  1. JSON string  — {"routing_enabled": true, "task_type": "code_generation"}
  2. Python dict literal — {'routing_enabled': True, 'task_type': 'code_generation'}
  3. Plain string  — treated as opaque, stored under {"context": plain_string}
  4. Empty/None   — yields empty dict {}
"""

import unittest
from dataclasses import dataclass, field
from typing import List, Optional, Union

from agentmap.models.graph_spec import NodeSpec
from agentmap.services.csv_graph_parser.converters import NodeSpecConverter
from tests.utils.mock_service_factory import MockServiceFactory


def _make_node_spec(context: Optional[str], name: str = "TestNode") -> NodeSpec:
    """Helper to build a minimal NodeSpec with the given context string."""
    return NodeSpec(name=name, graph_name="TestGraph", context=context)


class TestNodeSpecConverterContextParsing(unittest.TestCase):
    """Test that NodeSpecConverter parses the context string into a flat dict."""

    def setUp(self):
        mock_factory = MockServiceFactory()
        logger = mock_factory.create_mock_logging_service()
        self.converter = NodeSpecConverter(logger=logger)

    # ------------------------------------------------------------------
    # Empty / None context
    # ------------------------------------------------------------------

    def test_none_context_yields_empty_dict(self):
        """No context → Node.context is empty dict."""
        node_spec = _make_node_spec(context=None)
        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        self.assertEqual(nodes["TestNode"].context, {})

    def test_empty_string_context_yields_empty_dict(self):
        """Empty string context → Node.context is empty dict."""
        node_spec = _make_node_spec(context="")
        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        # _make_node_spec passes "" but parsers.py would convert "" to None;
        # converter receives None or "" — either way result must be {}
        self.assertEqual(nodes["TestNode"].context, {})

    # ------------------------------------------------------------------
    # JSON format (what arrives after CSV double-quote unescaping)
    # ------------------------------------------------------------------

    def test_json_context_is_parsed_to_dict(self):
        """JSON context string is parsed so keys are top-level in Node.context."""
        context_str = '{"provider": "anthropic", "model": "claude-3-5-sonnet-20241022", "temperature": 0.7}'
        node_spec = _make_node_spec(context=context_str)

        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        ctx = nodes["TestNode"].context

        self.assertEqual(ctx.get("provider"), "anthropic")
        self.assertEqual(ctx.get("model"), "claude-3-5-sonnet-20241022")
        self.assertAlmostEqual(ctx.get("temperature"), 0.7)

    def test_json_routing_context_keys_are_accessible(self):
        """Routing fields from JSON context are top-level in Node.context."""
        context_str = '{"routing_enabled": true, "task_type": "code_generation", "complexity_override": "high"}'
        node_spec = _make_node_spec(context=context_str)

        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        ctx = nodes["TestNode"].context

        self.assertTrue(ctx.get("routing_enabled"))
        self.assertEqual(ctx.get("task_type"), "code_generation")
        self.assertEqual(ctx.get("complexity_override"), "high")

    def test_json_with_nested_list_is_parsed(self):
        """JSON context with list values is fully parsed."""
        context_str = (
            '{"provider_preference": ["anthropic", "openai"], "task_type": "general"}'
        )
        node_spec = _make_node_spec(context=context_str)

        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        ctx = nodes["TestNode"].context

        self.assertEqual(ctx.get("provider_preference"), ["anthropic", "openai"])
        self.assertEqual(ctx.get("task_type"), "general")

    # ------------------------------------------------------------------
    # Python dict literal format (single quotes — no CSV escaping needed)
    # ------------------------------------------------------------------

    def test_python_dict_literal_is_parsed(self):
        """Single-quote Python dict literal is parsed via ast.literal_eval."""
        context_str = "{'provider': 'openai', 'temperature': 0.5}"
        node_spec = _make_node_spec(context=context_str)

        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        ctx = nodes["TestNode"].context

        self.assertEqual(ctx.get("provider"), "openai")
        self.assertAlmostEqual(ctx.get("temperature"), 0.5)

    def test_python_dict_routing_fields_are_accessible(self):
        """Routing fields from Python dict literal context are top-level."""
        context_str = "{'routing_enabled': True, 'task_type': 'data_analysis', 'max_cost_tier': 'medium'}"
        node_spec = _make_node_spec(context=context_str)

        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        ctx = nodes["TestNode"].context

        self.assertTrue(ctx.get("routing_enabled"))
        self.assertEqual(ctx.get("task_type"), "data_analysis")
        self.assertEqual(ctx.get("max_cost_tier"), "medium")

    # ------------------------------------------------------------------
    # Plain string fallback
    # ------------------------------------------------------------------

    def test_plain_string_stored_under_context_key(self):
        """A plain non-JSON string is stored as {"context": value} for backward compat."""
        context_str = "some plain description"
        node_spec = _make_node_spec(context=context_str)

        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        ctx = nodes["TestNode"].context

        self.assertEqual(ctx.get("context"), "some plain description")

    def test_invalid_json_falls_back_to_plain_string(self):
        """Malformed JSON that is also not a Python dict is stored as plain string."""
        context_str = "{not valid json or python"
        node_spec = _make_node_spec(context=context_str)

        nodes = self.converter.convert_node_specs_to_nodes([node_spec])
        ctx = nodes["TestNode"].context

        self.assertEqual(ctx.get("context"), context_str)


class TestAgentContextAccessAfterConversion(unittest.TestCase):
    """
    Verify that after NodeSpecConverter + AgentFactoryService context merging,
    routing and provider keys are readable directly via self.context.get(...).

    This mirrors what LLMAgent.__init__ does:
        self.routing_enabled = self.context.get("routing_enabled", False)
        self.provider_name = self.context.get("provider", "anthropic")
    """

    def setUp(self):
        mock_factory = MockServiceFactory()
        logger = mock_factory.create_mock_logging_service()
        self.converter = NodeSpecConverter(logger=logger)

    def _simulate_agent_factory_merge(self, node_context: dict) -> dict:
        """
        Reproduce the merge logic in AgentFactoryService.create_agent():
            context = {"input_fields": ..., "output_field": ..., ...}
            context.update(node.context)
        Returns the merged dict.
        """
        base_context = {
            "input_fields": ["query"],
            "output_field": "response",
            "description": "test",
            "is_custom": False,
            "output_validation": "warn",
        }
        base_context.update(node_context)
        return base_context

    def test_provider_readable_after_merge(self):
        """provider specified in JSON context is readable at top level after factory merge."""
        context_str = '{"provider": "openai", "model": "gpt-4o", "temperature": 0.3}'
        node_spec = _make_node_spec(context=context_str)
        nodes = self.converter.convert_node_specs_to_nodes([node_spec])

        merged = self._simulate_agent_factory_merge(nodes["TestNode"].context)

        self.assertEqual(merged.get("provider"), "openai")
        self.assertEqual(merged.get("model"), "gpt-4o")
        self.assertAlmostEqual(merged.get("temperature"), 0.3)

    def test_routing_enabled_readable_after_merge(self):
        """routing_enabled from JSON context is True at top level after factory merge."""
        context_str = '{"routing_enabled": true, "task_type": "creative_writing"}'
        node_spec = _make_node_spec(context=context_str)
        nodes = self.converter.convert_node_specs_to_nodes([node_spec])

        merged = self._simulate_agent_factory_merge(nodes["TestNode"].context)

        self.assertTrue(merged.get("routing_enabled"))
        self.assertEqual(merged.get("task_type"), "creative_writing")

    def test_routing_enabled_readable_from_python_dict_literal(self):
        """routing_enabled from single-quote dict is readable after factory merge."""
        context_str = "{'routing_enabled': True, 'activity': 'code_generation'}"
        node_spec = _make_node_spec(context=context_str)
        nodes = self.converter.convert_node_specs_to_nodes([node_spec])

        merged = self._simulate_agent_factory_merge(nodes["TestNode"].context)

        self.assertTrue(merged.get("routing_enabled"))
        self.assertEqual(merged.get("activity"), "code_generation")


if __name__ == "__main__":
    unittest.main()
