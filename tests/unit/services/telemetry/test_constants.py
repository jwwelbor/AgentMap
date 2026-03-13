"""Unit tests for telemetry constants module."""

from __future__ import annotations

import inspect

from agentmap.services.telemetry import constants


class TestConstants:
    """TC-040 through TC-045."""

    SPAN_NAMES = [
        "WORKFLOW_RUN_SPAN",
        "AGENT_RUN_SPAN",
        "LLM_CALL_SPAN",
    ]

    AGENT_ATTRS = [
        "AGENT_NAME",
        "AGENT_TYPE",
        "NODE_NAME",
        "GRAPH_NAME",
    ]

    WORKFLOW_ATTRS = [
        "GRAPH_NODE_COUNT",
        "GRAPH_AGENT_COUNT",
    ]

    GENAI_ATTRS = [
        "GEN_AI_SYSTEM",
        "GEN_AI_REQUEST_MODEL",
        "GEN_AI_RESPONSE_MODEL",
        "GEN_AI_USAGE_INPUT_TOKENS",
        "GEN_AI_USAGE_OUTPUT_TOKENS",
    ]

    ROUTING_ATTRS = [
        "ROUTING_COMPLEXITY",
        "ROUTING_CONFIDENCE",
        "ROUTING_PROVIDER",
        "ROUTING_MODEL",
        "ROUTING_CACHE_HIT",
        "ROUTING_CIRCUIT_BREAKER_STATE",
        "ROUTING_FALLBACK_TIER",
    ]

    def test_span_name_constants_are_nonempty_strings(self) -> None:
        """TC-040: Span name constants exist and are non-empty strings."""
        for name in self.SPAN_NAMES:
            val = getattr(constants, name)
            assert isinstance(val, str), f"{name} is not a string"
            assert len(val) > 0, f"{name} is empty"

    def test_agent_constants_have_agentmap_prefix(self) -> None:
        """TC-041: Agent constants use agentmap.* prefix."""
        for name in self.AGENT_ATTRS:
            val = getattr(constants, name)
            assert val.startswith(
                "agentmap."
            ), f"{name}={val!r} missing agentmap. prefix"

    def test_genai_constants_have_gen_ai_prefix(self) -> None:
        """TC-042: GenAI constants use gen_ai.* prefix."""
        for name in self.GENAI_ATTRS:
            val = getattr(constants, name)
            assert val.startswith("gen_ai."), f"{name}={val!r} missing gen_ai. prefix"

    def test_no_duplicate_constant_values(self) -> None:
        """TC-043: No duplicate constant values across all constants."""
        all_names = (
            self.SPAN_NAMES
            + self.AGENT_ATTRS
            + self.WORKFLOW_ATTRS
            + self.GENAI_ATTRS
            + self.ROUTING_ATTRS
        )
        values = [getattr(constants, n) for n in all_names]
        assert len(values) == len(set(values)), f"Duplicates found: {values}"

    def test_module_has_no_imports(self) -> None:
        """TC-044: Constants module has no import statements (pure strings)."""
        source = inspect.getsource(constants)
        # Filter out only actual import lines (not comments/docstrings about imports)
        lines = source.split("\n")
        import_lines = [
            line.strip()
            for line in lines
            if (line.strip().startswith("import ") or line.strip().startswith("from "))
            and not line.strip().startswith("#")
            and not line.strip().startswith('"""')
            and not line.strip().startswith("'")
        ]
        assert len(import_lines) == 0, f"Found imports: {import_lines}"

    def test_routing_constants_have_agentmap_routing_prefix(self) -> None:
        """TC-045: Routing constants use agentmap.routing.* prefix."""
        for name in self.ROUTING_ATTRS:
            val = getattr(constants, name)
            assert val.startswith(
                "agentmap.routing."
            ), f"{name}={val!r} missing agentmap.routing. prefix"

    def test_workflow_constants_have_agentmap_prefix(self) -> None:
        """Workflow constants use agentmap.* prefix."""
        for name in self.WORKFLOW_ATTRS:
            val = getattr(constants, name)
            assert val.startswith(
                "agentmap."
            ), f"{name}={val!r} missing agentmap. prefix"
