"""
Integration tests: CSV context field → Node → agent context accessibility.

Verifies the full pipeline from a raw CSV string (as written by a user)
through parsing, node conversion, and agent factory context merging — ending
with the assertion that structured keys like routing_enabled, task_type,
provider, and model are readable at the top level of the agent's context dict.

This is the regression test for the bug where JSON in the context column was
stored as a raw string under {"context": raw_string} and was therefore
inaccessible via self.context.get("routing_enabled") etc.
"""

import unittest
from pathlib import Path

from agentmap.services.csv_graph_parser.converters import NodeSpecConverter
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest

CSV_HEADER = "GraphName,Node,AgentType,Context,Input_Fields,Output_Field,Success_Next,Failure_Next,Prompt\n"


class TestCSVContextParsingIntegration(BaseIntegrationTest):
    """End-to-end: CSV text → parsed NodeSpecs → converted Nodes → agent context accessible."""

    def setup_services(self):
        super().setup_services()
        self.csv_parser_service = self.container.csv_graph_parser_service()
        logger = self.logging_service.get_class_logger(self)
        self.converter = NodeSpecConverter(logger=logger)

    def _parse_and_convert(
        self, csv_text: str, graph_name: str, node_name: str
    ) -> dict:
        """
        Full pipeline: CSV text → GraphSpec → Node → merged agent context.

        Steps:
          1. Write CSV to temp file
          2. parse_csv_to_graph_spec → GraphSpec with NodeSpec objects
          3. NodeSpecConverter.convert_node_specs_to_nodes → Node objects with parsed context
          4. Simulate AgentFactoryService context merge: base.update(node.context)
        """
        csv_path = Path(self.temp_dir) / "test_workflow.csv"
        csv_path.write_text(CSV_HEADER + csv_text)

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        node_specs = graph_spec.get_nodes_for_graph(graph_name)
        nodes = self.converter.convert_node_specs_to_nodes(node_specs)
        node = nodes[node_name]

        # Reproduce AgentFactoryService.create_agent() context merge
        base = {
            "input_fields": getattr(node, "inputs", []),
            "output_field": getattr(node, "output", None),
            "description": getattr(node, "description", ""),
            "is_custom": False,
            "output_validation": "warn",
        }
        if node.context:
            base.update(node.context)
        return base

    # ------------------------------------------------------------------
    # JSON context (double-escaped in CSV = standard JSON after CSV decode)
    # ------------------------------------------------------------------

    def test_json_context_provider_and_model_accessible(self):
        """provider and model specified as JSON in CSV context are top-level keys."""
        csv_row = (
            "MyWorkflow,ChatNode,llm,"
            '"{""provider"": ""anthropic"", ""model"": ""claude-sonnet-4-6"", ""temperature"": 0.3}",'
            "query,response,End,,You are a helpful assistant\n"
            "MyWorkflow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "MyWorkflow", "ChatNode")

        self.assertEqual(ctx.get("provider"), "anthropic")
        self.assertEqual(ctx.get("model"), "claude-sonnet-4-6")
        self.assertAlmostEqual(ctx.get("temperature"), 0.3)

    def test_json_context_routing_fields_accessible(self):
        """Routing fields from JSON context column are readable at top level."""
        csv_row = (
            "RoutingFlow,RouteNode,llm,"
            '"{""routing_enabled"": true, ""task_type"": ""code_generation"", ""complexity_override"": ""high""}",'
            "request,code,End,,You are a software engineer\n"
            "RoutingFlow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "RoutingFlow", "RouteNode")

        self.assertTrue(ctx.get("routing_enabled"))
        self.assertEqual(ctx.get("task_type"), "code_generation")
        self.assertEqual(ctx.get("complexity_override"), "high")

    def test_json_context_activity_routing_accessible(self):
        """Activity-based routing fields from JSON context are top-level."""
        csv_row = (
            "ActivityFlow,AnalyzeNode,llm,"
            '"{""routing_enabled"": true, ""activity"": ""data_analysis"", ""max_cost_tier"": ""medium""}",'
            "data,analysis,End,,Analyze the data\n"
            "ActivityFlow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "ActivityFlow", "AnalyzeNode")

        self.assertTrue(ctx.get("routing_enabled"))
        self.assertEqual(ctx.get("activity"), "data_analysis")
        self.assertEqual(ctx.get("max_cost_tier"), "medium")

    # ------------------------------------------------------------------
    # Python dict literal (single quotes — no CSV escaping needed)
    # ------------------------------------------------------------------

    def test_python_dict_context_routing_fields_accessible(self):
        """Single-quote Python dict context parsed without CSV quote escaping."""
        csv_row = (
            "SimpleFlow,LLMNode,llm,"
            "\"{'routing_enabled': True, 'task_type': 'creative_writing', 'prefer_quality': True}\","
            "prompt,story,End,,Write a story\n"
            "SimpleFlow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "SimpleFlow", "LLMNode")

        self.assertTrue(ctx.get("routing_enabled"))
        self.assertEqual(ctx.get("task_type"), "creative_writing")
        self.assertTrue(ctx.get("prefer_quality"))

    def test_python_dict_provider_accessible(self):
        """Provider and model from single-quote dict are accessible."""
        csv_row = (
            "DirectFlow,DirectNode,llm,"
            "\"{'provider': 'openai', 'model': 'gpt-4o', 'temperature': 0.5}\","
            "input,output,End,,You are helpful\n"
            "DirectFlow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "DirectFlow", "DirectNode")

        self.assertEqual(ctx.get("provider"), "openai")
        self.assertEqual(ctx.get("model"), "gpt-4o")
        self.assertAlmostEqual(ctx.get("temperature"), 0.5)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_context_does_not_break_parsing(self):
        """Empty context column parses cleanly with no error."""
        csv_row = (
            "EmptyFlow,SimpleNode,default,,input,output,End,,Do something\n"
            "EmptyFlow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "EmptyFlow", "SimpleNode")

        self.assertIn("input_fields", ctx)
        self.assertIsNone(ctx.get("routing_enabled"))
        self.assertIsNone(ctx.get("provider"))

    def test_plain_string_context_preserved_under_context_key(self):
        """A non-JSON, non-dict context string is stored under 'context' key."""
        csv_row = (
            "PlainFlow,PlainNode,default,"
            "just a description string,"
            "input,output,End,,Do something\n"
            "PlainFlow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "PlainFlow", "PlainNode")

        self.assertEqual(ctx.get("context"), "just a description string")

    def test_json_and_python_dict_formats_produce_identical_results(self):
        """Both CSV context formats produce the same top-level keys and values."""
        json_row = (
            "JsonFlow,Node,llm,"
            '"{""routing_enabled"": true, ""task_type"": ""code_generation"", ""temperature"": 0.5}",'
            "input,output,End,,prompt\n"
            "JsonFlow,End,success,,,,,,Done\n"
        )
        python_row = (
            "PyFlow,Node,llm,"
            "\"{'routing_enabled': True, 'task_type': 'code_generation', 'temperature': 0.5}\","
            "input,output,End,,prompt\n"
            "PyFlow,End,success,,,,,,Done\n"
        )
        json_ctx = self._parse_and_convert(json_row, "JsonFlow", "Node")
        py_ctx = self._parse_and_convert(python_row, "PyFlow", "Node")

        self.assertEqual(json_ctx.get("routing_enabled"), py_ctx.get("routing_enabled"))
        self.assertEqual(json_ctx.get("task_type"), py_ctx.get("task_type"))
        self.assertAlmostEqual(json_ctx.get("temperature"), py_ctx.get("temperature"))

    # ------------------------------------------------------------------
    # Non-LLM agents that also read structured context keys
    # ------------------------------------------------------------------

    def test_summary_agent_context_keys_accessible(self):
        """SummaryAgent context keys (llm, format, separator) are top-level after parsing."""
        csv_row = (
            "SummaryFlow,SumNode,summary,"
            '"{""llm"": ""anthropic"", ""model"": ""claude-haiku-4-5-20251001"", ""format"": ""{key}: {value}"", ""separator"": ""\\n""}",'
            "data,summary,End,,Summarize\n"
            "SummaryFlow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "SummaryFlow", "SumNode")

        self.assertEqual(ctx.get("llm"), "anthropic")
        self.assertEqual(ctx.get("model"), "claude-haiku-4-5-20251001")
        self.assertEqual(ctx.get("format"), "{key}: {value}")
        self.assertEqual(ctx.get("separator"), "\n")

    def test_suspend_agent_context_keys_accessible(self):
        """SuspendAgent context keys (topic fields) are top-level after parsing."""
        csv_row = (
            "SuspendFlow,WaitNode,suspend,"
            '"{""suspend_message_topic"": ""my_events"", ""resume_message_topic"": ""my_resumes""}",'
            "input,output,End,,Waiting\n"
            "SuspendFlow,End,success,,,,,,Done\n"
        )
        ctx = self._parse_and_convert(csv_row, "SuspendFlow", "WaitNode")

        self.assertEqual(ctx.get("suspend_message_topic"), "my_events")
        self.assertEqual(ctx.get("resume_message_topic"), "my_resumes")


if __name__ == "__main__":
    unittest.main()
