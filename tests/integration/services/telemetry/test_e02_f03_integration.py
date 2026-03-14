"""Integration tests for E02-F03 Workflow and LLM Instrumentation.

These tests verify:
- Full span hierarchy (workflow -> agent -> LLM) with proper parent-child
  relationships using real OTEL SDK with InMemorySpanExporter.
- Embedded mode: workflow spans parent under host application active span.
- Subgraph nesting: nested workflow spans with parent_name attribute.
- GenAI semconv attributes present on real exported spans.
- Routing attributes present when routing context is used.
- Backward compatibility: services work when telemetry_service=None.
- DI container wiring patterns for telemetry injection.
- All E02-F03 constants are importable and non-empty.

Test IDs: INT-200 through INT-231 (task T-E02-F03-005).

Requires ``opentelemetry-sdk`` to be installed.  The entire module is
skipped automatically when the SDK is unavailable.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest

# ---------------------------------------------------------------------------
# Graceful skip when OTEL SDK is not installed
# ---------------------------------------------------------------------------
try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from opentelemetry.trace import StatusCode

    _sdk_available = True
except ImportError:
    _sdk_available = False

pytestmark = pytest.mark.skipif(
    not _sdk_available,
    reason="opentelemetry-sdk not installed -- skipping OTEL integration tests",
)

from agentmap.services.telemetry.constants import (  # noqa: E402
    AGENT_NAME,
    AGENT_RUN_SPAN,
    AGENT_TYPE,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GRAPH_AGENT_COUNT,
    GRAPH_NAME,
    GRAPH_NODE_COUNT,
    LLM_CALL_SPAN,
    NODE_NAME,
    ROUTING_CACHE_HIT,
    ROUTING_CIRCUIT_BREAKER_STATE,
    ROUTING_COMPLEXITY,
    ROUTING_CONFIDENCE,
    ROUTING_FALLBACK_TIER,
    ROUTING_MODEL,
    ROUTING_PROVIDER,
    WORKFLOW_RUN_SPAN,
)
from agentmap.services.telemetry.noop_telemetry_service import (  # noqa: E402
    NoOpTelemetryService,
)
from agentmap.services.telemetry.otel_telemetry_service import (  # noqa: E402
    OTELTelemetryService,
)
from agentmap.services.telemetry.protocol import (  # noqa: E402
    TelemetryServiceProtocol,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _otel_provider():
    """Create a per-test TracerProvider + InMemorySpanExporter pair."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, provider


@pytest.fixture()
def otel_exporter(_otel_provider):
    """Per-test InMemorySpanExporter."""
    exporter, _ = _otel_provider
    return exporter


@pytest.fixture()
def telemetry_service(_otel_provider):
    """Create a real OTELTelemetryService with tracer from test provider."""
    _, provider = _otel_provider
    svc = OTELTelemetryService()
    svc._tracer = provider.get_tracer("agentmap")
    return svc


# ---------------------------------------------------------------------------
# INT-200: Full trace hierarchy -- workflow -> agent -> LLM spans
# ---------------------------------------------------------------------------


class TestFullSpanHierarchy:
    """INT-200: Verify end-to-end span hierarchy using real OTEL SDK.

    Simulates the span nesting that instrumented GraphRunnerService,
    BaseAgent, and LLMService will produce once T-001/T-002/T-003 land.
    """

    def test_workflow_agent_llm_hierarchy(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-200: 1 workflow root, N agent children, 1+ LLM grandchildren."""
        # Simulate a workflow span wrapping agent spans wrapping LLM spans
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "test_graph", GRAPH_NODE_COUNT: 3},
        ) as workflow_span:
            telemetry_service.set_span_attributes(workflow_span, {GRAPH_AGENT_COUNT: 3})

            # Agent 1 -- no LLM call
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "agent_1",
                    AGENT_TYPE: "EchoAgent",
                    NODE_NAME: "agent_1",
                    GRAPH_NAME: "test_graph",
                },
            ):
                pass

            # Agent 2 -- has LLM call
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "agent_2",
                    AGENT_TYPE: "OpenAIAgent",
                    NODE_NAME: "agent_2",
                    GRAPH_NAME: "test_graph",
                },
            ):
                with telemetry_service.start_span(
                    LLM_CALL_SPAN,
                    attributes={
                        GEN_AI_SYSTEM: "openai",
                        GEN_AI_REQUEST_MODEL: "gpt-4",
                    },
                ) as llm_span:
                    telemetry_service.set_span_attributes(
                        llm_span,
                        {
                            GEN_AI_USAGE_INPUT_TOKENS: 100,
                            GEN_AI_USAGE_OUTPUT_TOKENS: 50,
                        },
                    )

            # Agent 3 -- no LLM call
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "agent_3",
                    AGENT_TYPE: "EchoAgent",
                    NODE_NAME: "agent_3",
                    GRAPH_NAME: "test_graph",
                },
            ):
                pass

        spans = otel_exporter.get_finished_spans()

        # Find spans by name
        workflow_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]
        agent_spans = [s for s in spans if s.name == AGENT_RUN_SPAN]
        llm_spans = [s for s in spans if s.name == LLM_CALL_SPAN]

        assert (
            len(workflow_spans) == 1
        ), f"Expected 1 workflow span, got {len(workflow_spans)}"
        assert len(agent_spans) == 3, f"Expected 3 agent spans, got {len(agent_spans)}"
        assert len(llm_spans) == 1, f"Expected 1 LLM span, got {len(llm_spans)}"

        wf_span = workflow_spans[0]
        wf_span_id = wf_span.context.span_id
        wf_trace_id = wf_span.context.trace_id

        # All agent spans should be children of the workflow span
        for agent_span in agent_spans:
            assert (
                agent_span.parent is not None
            ), f"Agent span {agent_span.attributes.get(AGENT_NAME)} has no parent"
            assert agent_span.parent.span_id == wf_span_id, (
                f"Agent span parent mismatch for "
                f"{agent_span.attributes.get(AGENT_NAME)}"
            )
            assert (
                agent_span.context.trace_id == wf_trace_id
            ), "Agent span has different trace_id"

        # LLM span should be a child of agent_2's span
        llm_span_obj = llm_spans[0]
        agent_2_span = [
            s for s in agent_spans if s.attributes.get(AGENT_NAME) == "agent_2"
        ][0]
        assert llm_span_obj.parent is not None, "LLM span has no parent"
        assert (
            llm_span_obj.parent.span_id == agent_2_span.context.span_id
        ), "LLM span parent is not agent_2"
        assert (
            llm_span_obj.context.trace_id == wf_trace_id
        ), "LLM span has different trace_id"

    def test_all_spans_share_trace_id(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-200: All spans in a workflow share the same trace_id."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "trace_test"},
        ):
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={AGENT_NAME: "a1"},
            ):
                with telemetry_service.start_span(
                    LLM_CALL_SPAN,
                    attributes={GEN_AI_SYSTEM: "openai"},
                ):
                    pass

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 3
        trace_ids = {s.context.trace_id for s in spans}
        assert (
            len(trace_ids) == 1
        ), f"Expected all spans to share 1 trace_id, got {len(trace_ids)}"


# ---------------------------------------------------------------------------
# INT-201: Embedded mode -- workflow span parents under host span
# ---------------------------------------------------------------------------


class TestEmbeddedMode:
    """INT-201: Verify workflow span is child of host application span."""

    def test_workflow_span_parents_under_host_span(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-201: Workflow span parent_span_id matches host span_id."""
        # Use the same tracer provider that backs our telemetry_service
        tracer = telemetry_service.get_tracer()

        # Create a host application span
        with tracer.start_as_current_span("host.request") as host_span:
            host_span_id = host_span.get_span_context().span_id
            host_trace_id = host_span.get_span_context().trace_id

            # Run workflow inside host span context
            with telemetry_service.start_span(
                WORKFLOW_RUN_SPAN,
                attributes={GRAPH_NAME: "embedded_graph"},
            ):
                pass

        spans = otel_exporter.get_finished_spans()
        workflow_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]
        assert len(workflow_spans) == 1

        wf_span = workflow_spans[0]
        assert (
            wf_span.parent is not None
        ), "Workflow span should have a parent in embedded mode"
        assert (
            wf_span.parent.span_id == host_span_id
        ), "Workflow span parent should be the host span"
        assert (
            wf_span.context.trace_id == host_trace_id
        ), "Workflow span should share host span's trace_id"


# ---------------------------------------------------------------------------
# INT-202: Subgraph produces nested workflow span
# ---------------------------------------------------------------------------


class TestSubgraphNesting:
    """INT-202: Verify subgraph workflow spans nest properly."""

    def test_nested_workflow_spans(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-202: Subgraph workflow span is child of parent agent span."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "parent_workflow", GRAPH_NODE_COUNT: 2},
        ):
            # Agent that triggers a subgraph (GraphAgent)
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "graph_agent",
                    AGENT_TYPE: "GraphAgent",
                    NODE_NAME: "graph_agent",
                    GRAPH_NAME: "parent_workflow",
                },
            ):
                # Subgraph workflow span
                with telemetry_service.start_span(
                    WORKFLOW_RUN_SPAN,
                    attributes={
                        GRAPH_NAME: "child_workflow",
                        GRAPH_NODE_COUNT: 1,
                    },
                ) as subgraph_span:
                    # Set parent_name attribute on subgraph span
                    telemetry_service.set_span_attributes(
                        subgraph_span,
                        {"agentmap.graph.parent_name": "parent_workflow"},
                    )
                    # Child agent in subgraph
                    with telemetry_service.start_span(
                        AGENT_RUN_SPAN,
                        attributes={
                            AGENT_NAME: "sub_agent",
                            AGENT_TYPE: "EchoAgent",
                            NODE_NAME: "sub_agent",
                            GRAPH_NAME: "child_workflow",
                        },
                    ):
                        pass

        spans = otel_exporter.get_finished_spans()
        workflow_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]
        agent_spans = [s for s in spans if s.name == AGENT_RUN_SPAN]

        assert (
            len(workflow_spans) == 2
        ), f"Expected 2 workflow spans, got {len(workflow_spans)}"
        assert len(agent_spans) == 2, f"Expected 2 agent spans, got {len(agent_spans)}"

        # Identify parent and subgraph workflow spans
        parent_wf = [
            s
            for s in workflow_spans
            if s.attributes.get(GRAPH_NAME) == "parent_workflow"
        ][0]
        child_wf = [
            s
            for s in workflow_spans
            if s.attributes.get(GRAPH_NAME) == "child_workflow"
        ][0]

        # Subgraph workflow should be child of graph_agent span
        graph_agent_s = [
            s for s in agent_spans if s.attributes.get(AGENT_NAME) == "graph_agent"
        ][0]
        assert (
            child_wf.parent is not None
        ), "Subgraph workflow span should have a parent"
        assert (
            child_wf.parent.span_id == graph_agent_s.context.span_id
        ), "Subgraph workflow should be child of GraphAgent span"

        # Subgraph should have parent_name attribute
        assert child_wf.attributes.get("agentmap.graph.parent_name") == (
            "parent_workflow"
        ), "Subgraph workflow should have agentmap.graph.parent_name attribute"

        # Parent workflow should not have parent_name attribute
        assert "agentmap.graph.parent_name" not in (
            parent_wf.attributes or {}
        ), "Parent workflow should NOT have agentmap.graph.parent_name"


# ---------------------------------------------------------------------------
# INT-210: GenAI span with correct semconv attributes
# ---------------------------------------------------------------------------


class TestGenAISpanAttributes:
    """INT-210: Verify GenAI span creation with actual OTEL SDK."""

    def test_genai_span_attributes(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-210: gen_ai.chat span has correct semconv attributes."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={
                GEN_AI_SYSTEM: "anthropic",
                GEN_AI_REQUEST_MODEL: "claude-3-sonnet",
            },
        ) as span:
            telemetry_service.set_span_attributes(
                span,
                {
                    GEN_AI_USAGE_INPUT_TOKENS: 150,
                    GEN_AI_USAGE_OUTPUT_TOKENS: 75,
                },
            )

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1

        exported = spans[0]
        assert exported.name == LLM_CALL_SPAN
        assert exported.attributes[GEN_AI_SYSTEM] == "anthropic"
        assert exported.attributes[GEN_AI_REQUEST_MODEL] == "claude-3-sonnet"
        assert exported.attributes[GEN_AI_USAGE_INPUT_TOKENS] == 150
        assert exported.attributes[GEN_AI_USAGE_OUTPUT_TOKENS] == 75

    def test_genai_span_has_nonzero_duration(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-210: Exported GenAI span has valid timing."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={GEN_AI_SYSTEM: "openai"},
        ):
            pass

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].start_time is not None
        assert spans[0].end_time is not None
        assert spans[0].end_time >= spans[0].start_time

    def test_genai_span_without_token_counts(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-210 variant: Token count attributes absent when not set."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={
                GEN_AI_SYSTEM: "anthropic",
                GEN_AI_REQUEST_MODEL: "claude-3-sonnet",
            },
        ):
            pass

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert GEN_AI_USAGE_INPUT_TOKENS not in attrs
        assert GEN_AI_USAGE_OUTPUT_TOKENS not in attrs


# ---------------------------------------------------------------------------
# INT-211: Routing attributes on real exported span
# ---------------------------------------------------------------------------


class TestRoutingAttributesOnSpan:
    """INT-211: Verify routing decision attributes on real exported span."""

    def test_routing_attributes_present(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-211: Routing attributes appear on gen_ai.chat span."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={
                GEN_AI_SYSTEM: "openai",
                GEN_AI_REQUEST_MODEL: "gpt-4",
            },
        ) as span:
            telemetry_service.set_span_attributes(
                span,
                {
                    ROUTING_COMPLEXITY: "high",
                    ROUTING_CONFIDENCE: 0.95,
                    ROUTING_PROVIDER: "openai",
                    ROUTING_MODEL: "gpt-4",
                },
            )

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes

        assert attrs[ROUTING_COMPLEXITY] == "high"
        assert attrs[ROUTING_CONFIDENCE] == 0.95
        assert attrs[ROUTING_PROVIDER] == "openai"
        assert attrs[ROUTING_MODEL] == "gpt-4"

    def test_routing_cache_hit_attribute(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-211: Routing cache_hit attribute on span."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={GEN_AI_SYSTEM: "anthropic"},
        ) as span:
            telemetry_service.set_span_attributes(span, {ROUTING_CACHE_HIT: True})

        spans = otel_exporter.get_finished_spans()
        assert spans[0].attributes[ROUTING_CACHE_HIT] is True

    def test_routing_circuit_breaker_state_attribute(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-211: Circuit breaker state attribute on span."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={GEN_AI_SYSTEM: "openai"},
        ) as span:
            telemetry_service.set_span_attributes(
                span, {ROUTING_CIRCUIT_BREAKER_STATE: "closed"}
            )

        spans = otel_exporter.get_finished_spans()
        assert spans[0].attributes[ROUTING_CIRCUIT_BREAKER_STATE] == "closed"

    def test_routing_fallback_tier_attribute(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-211: Fallback tier attribute on span."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={GEN_AI_SYSTEM: "openai"},
        ) as span:
            telemetry_service.set_span_attributes(span, {ROUTING_FALLBACK_TIER: 2})

        spans = otel_exporter.get_finished_spans()
        assert spans[0].attributes[ROUTING_FALLBACK_TIER] == 2

    def test_routing_attributes_absent_for_direct_calls(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-211: No routing attributes when call is direct (no routing)."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={
                GEN_AI_SYSTEM: "anthropic",
                GEN_AI_REQUEST_MODEL: "claude-3-sonnet",
            },
        ):
            # No routing attributes set
            pass

        spans = otel_exporter.get_finished_spans()
        attrs = spans[0].attributes
        assert ROUTING_COMPLEXITY not in attrs
        assert ROUTING_PROVIDER not in attrs
        assert ROUTING_MODEL not in attrs
        assert ROUTING_CONFIDENCE not in attrs
        assert ROUTING_CACHE_HIT not in attrs

    def test_routing_attributes_on_llm_span_not_child(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-211: Routing data as attributes on gen_ai.chat, not child."""
        with telemetry_service.start_span(
            LLM_CALL_SPAN,
            attributes={GEN_AI_SYSTEM: "openai"},
        ) as span:
            telemetry_service.set_span_attributes(
                span,
                {
                    ROUTING_COMPLEXITY: "medium",
                    ROUTING_PROVIDER: "openai",
                },
            )

        spans = otel_exporter.get_finished_spans()
        # Only 1 span -- no child span for routing
        assert len(spans) == 1
        assert spans[0].name == LLM_CALL_SPAN


# ---------------------------------------------------------------------------
# INT-220: E02-F03 constants importable and non-empty
# ---------------------------------------------------------------------------


class TestE02F03Constants:
    """INT-220: All E02-F03 constants are importable and non-empty strings."""

    def test_workflow_span_constants(self) -> None:
        """INT-220: Workflow and LLM span name constants exist."""
        assert isinstance(WORKFLOW_RUN_SPAN, str) and len(WORKFLOW_RUN_SPAN) > 0
        assert isinstance(LLM_CALL_SPAN, str) and len(LLM_CALL_SPAN) > 0
        assert isinstance(AGENT_RUN_SPAN, str) and len(AGENT_RUN_SPAN) > 0

    def test_graph_attribute_constants(self) -> None:
        """INT-220: Graph attribute constants exist and are non-empty."""
        for name, val in [
            ("GRAPH_NAME", GRAPH_NAME),
            ("GRAPH_NODE_COUNT", GRAPH_NODE_COUNT),
            ("GRAPH_AGENT_COUNT", GRAPH_AGENT_COUNT),
        ]:
            assert isinstance(val, str), f"{name} is not a string"
            assert len(val) > 0, f"{name} is empty"

    def test_genai_attribute_constants(self) -> None:
        """INT-220: GenAI semconv constants exist and are non-empty."""
        for name, val in [
            ("GEN_AI_SYSTEM", GEN_AI_SYSTEM),
            ("GEN_AI_REQUEST_MODEL", GEN_AI_REQUEST_MODEL),
            ("GEN_AI_USAGE_INPUT_TOKENS", GEN_AI_USAGE_INPUT_TOKENS),
            ("GEN_AI_USAGE_OUTPUT_TOKENS", GEN_AI_USAGE_OUTPUT_TOKENS),
        ]:
            assert isinstance(val, str), f"{name} is not a string"
            assert len(val) > 0, f"{name} is empty"

    def test_routing_attribute_constants(self) -> None:
        """INT-220: Routing attribute constants exist and are non-empty."""
        for name, val in [
            ("ROUTING_COMPLEXITY", ROUTING_COMPLEXITY),
            ("ROUTING_CONFIDENCE", ROUTING_CONFIDENCE),
            ("ROUTING_PROVIDER", ROUTING_PROVIDER),
            ("ROUTING_MODEL", ROUTING_MODEL),
            ("ROUTING_CACHE_HIT", ROUTING_CACHE_HIT),
            ("ROUTING_CIRCUIT_BREAKER_STATE", ROUTING_CIRCUIT_BREAKER_STATE),
            ("ROUTING_FALLBACK_TIER", ROUTING_FALLBACK_TIER),
        ]:
            assert isinstance(val, str), f"{name} is not a string"
            assert len(val) > 0, f"{name} is empty"


# ---------------------------------------------------------------------------
# INT-221: E02-F02 agent spans nest correctly under E02-F03 workflow span
# ---------------------------------------------------------------------------


class TestCrossFeatureSpanNesting:
    """INT-221: Agent spans (E02-F02) nest under workflow span (E02-F03)."""

    def test_agent_spans_under_workflow_with_lifecycle_events(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-221: Agent spans with lifecycle events nest under workflow."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "cross_feature_test"},
        ):
            # Simulate agent execution with lifecycle events (E02-F02 pattern)
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "test_agent",
                    AGENT_TYPE: "EchoAgent",
                    NODE_NAME: "test_agent",
                    GRAPH_NAME: "cross_feature_test",
                },
            ) as agent_span:
                telemetry_service.add_span_event(agent_span, "pre_process.start")
                telemetry_service.add_span_event(agent_span, "process.start")
                telemetry_service.add_span_event(agent_span, "post_process.start")
                telemetry_service.add_span_event(agent_span, "agent.complete")

        spans = otel_exporter.get_finished_spans()
        workflow_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]
        agent_spans = [s for s in spans if s.name == AGENT_RUN_SPAN]

        assert len(workflow_spans) == 1
        assert len(agent_spans) == 1

        wf = workflow_spans[0]
        ag = agent_spans[0]

        # Agent is child of workflow
        assert ag.parent is not None
        assert ag.parent.span_id == wf.context.span_id

        # Agent has E02-F02 lifecycle events
        event_names = [e.name for e in ag.events]
        assert event_names == [
            "pre_process.start",
            "process.start",
            "post_process.start",
            "agent.complete",
        ]


# ---------------------------------------------------------------------------
# INT-230/INT-231: Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """INT-230/INT-231: Existing services work without telemetry."""

    def test_graph_runner_service_constructor_accepts_current_params(
        self,
    ) -> None:
        """INT-230: GraphRunnerService can be constructed with current params.

        This verifies the constructor hasn't broken with existing callers
        (no telemetry_service parameter required).
        """
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.declaration_registry_service import (
            DeclarationRegistryService,
        )
        from agentmap.services.execution_tracking_service import (
            ExecutionTrackingService,
        )
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )
        from agentmap.services.graph.graph_assembly_service import (
            GraphAssemblyService,
        )
        from agentmap.services.graph.graph_bundle_service import (
            GraphBundleService,
        )
        from agentmap.services.graph.graph_checkpoint_service import (
            GraphCheckpointService,
        )
        from agentmap.services.graph.graph_execution_service import (
            GraphExecutionService,
        )
        from agentmap.services.graph.graph_runner_service import (
            GraphRunnerService,
        )
        from agentmap.services.interaction_handler_service import (
            InteractionHandlerService,
        )
        from agentmap.services.logging_service import LoggingService

        # Construct with all required params as mocks -- no telemetry_service
        mock_config = create_autospec(AppConfigService, instance=True)
        mock_logging = create_autospec(LoggingService, instance=True)
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_instantiation = create_autospec(
            GraphAgentInstantiationService, instance=True
        )
        mock_assembly = create_autospec(GraphAssemblyService, instance=True)
        mock_execution = create_autospec(GraphExecutionService, instance=True)
        mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
        mock_interaction = create_autospec(InteractionHandlerService, instance=True)
        mock_checkpoint = create_autospec(GraphCheckpointService, instance=True)
        mock_bundle_svc = create_autospec(GraphBundleService, instance=True)
        mock_decl_registry = create_autospec(DeclarationRegistryService, instance=True)

        # This should not raise -- backward compatible
        runner = GraphRunnerService(
            app_config_service=mock_config,
            graph_bootstrap_service=None,
            graph_agent_instantiation_service=mock_instantiation,
            graph_assembly_service=mock_assembly,
            graph_execution_service=mock_execution,
            execution_tracking_service=mock_tracking,
            logging_service=mock_logging,
            interaction_handler_service=mock_interaction,
            graph_checkpoint_service=mock_checkpoint,
            graph_bundle_service=mock_bundle_svc,
            declaration_registry_service=mock_decl_registry,
        )
        assert runner is not None

    def test_llm_service_constructor_accepts_current_params(self) -> None:
        """INT-231: LLMService can be constructed with current params.

        This verifies the constructor hasn't broken with existing callers
        (no telemetry_service parameter required).
        """
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.config.llm_models_config_service import (
            LLMModelsConfigService,
        )
        from agentmap.services.llm_service import LLMService
        from agentmap.services.logging_service import LoggingService
        from agentmap.services.routing.routing_service import LLMRoutingService

        mock_config = create_autospec(AppConfigService, instance=True)
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {},
        }
        mock_logging = create_autospec(LoggingService, instance=True)
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_routing = create_autospec(LLMRoutingService, instance=True)
        mock_models = create_autospec(LLMModelsConfigService, instance=True)

        # This should not raise -- backward compatible
        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=mock_routing,
            llm_models_config_service=mock_models,
        )
        assert svc is not None


# ---------------------------------------------------------------------------
# Additional: Workflow span status and error recording
# ---------------------------------------------------------------------------


class TestWorkflowSpanStatus:
    """Verify workflow span status on success and error paths."""

    def test_workflow_span_status_ok(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """Workflow span has OK status after successful execution."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "ok_graph"},
        ) as span:
            # Simulate setting OK status
            from opentelemetry.trace import StatusCode as SC

            span.set_status(SC.OK)

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    def test_workflow_span_status_error(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """Workflow span has ERROR status after exception."""
        try:
            with telemetry_service.start_span(
                WORKFLOW_RUN_SPAN,
                attributes={GRAPH_NAME: "error_graph"},
            ) as span:
                error = RuntimeError("workflow failed")
                telemetry_service.record_exception(span, error)
        except Exception:
            pass

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR

        # Exception event should be present
        exception_events = [e for e in spans[0].events if e.name == "exception"]
        assert len(exception_events) >= 1

    def test_workflow_span_duration(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """Workflow span has valid start and end times."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "duration_test"},
        ):
            pass

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.start_time is not None
        assert span.end_time is not None
        assert span.end_time >= span.start_time


# ---------------------------------------------------------------------------
# NoOp telemetry produces no spans
# ---------------------------------------------------------------------------


class TestNoOpTelemetryProducesNoSpans:
    """Verify NoOpTelemetryService does not produce any real spans."""

    def test_noop_produces_no_exported_spans(
        self,
        otel_exporter,
    ) -> None:
        """NoOp telemetry does not export any spans."""
        noop = NoOpTelemetryService()
        with noop.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "noop_test"},
        ) as span:
            noop.set_span_attributes(span, {GRAPH_NODE_COUNT: 1})
            noop.add_span_event(span, "test.event")

        # No real spans should be exported
        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 0


# ---------------------------------------------------------------------------
# DI wiring verification
# ---------------------------------------------------------------------------


class TestDIWiringPatterns:
    """Verify DI container wiring for telemetry."""

    def test_telemetry_container_provides_service(self) -> None:
        """DI: TelemetryContainer provides a protocol-satisfying service."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        container = TelemetryContainer(logging_service=mock_ls)
        svc = container.telemetry_service()

        assert isinstance(svc, TelemetryServiceProtocol)

    def test_telemetry_service_is_singleton(self) -> None:
        """DI: telemetry_service resolves to the same singleton."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        container = TelemetryContainer(logging_service=mock_ls)

        svc1 = container.telemetry_service()
        svc2 = container.telemetry_service()
        assert svc1 is svc2

    def test_graph_agent_container_receives_telemetry(self) -> None:
        """DI: GraphAgentContainer wires telemetry to instantiation svc."""
        from agentmap.di.container_parts.graph_agent import (
            GraphAgentContainer,
        )
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        telemetry_container = TelemetryContainer(logging_service=mock_ls)
        telemetry_svc = telemetry_container.telemetry_service()

        graph_agent_container = GraphAgentContainer(
            features_registry_service=MagicMock(),
            logging_service=mock_ls,
            custom_agent_loader=MagicMock(),
            app_config_service=MagicMock(),
            llm_service=MagicMock(),
            storage_service_manager=MagicMock(),
            host_protocol_configuration_service=MagicMock(),
            prompt_manager_service=MagicMock(),
            graph_checkpoint_service=MagicMock(),
            blob_storage_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            orchestrator_service=MagicMock(),
            declaration_registry_service=MagicMock(),
            telemetry_service=telemetry_svc,
        )

        instantiation_svc = graph_agent_container.graph_agent_instantiation_service()
        assert instantiation_svc.telemetry_service is not None
        assert instantiation_svc.telemetry_service is telemetry_svc


# ---------------------------------------------------------------------------
# Workflow phase events (should-have)
# ---------------------------------------------------------------------------


class TestWorkflowPhaseEvents:
    """Verify workflow phase events are recorded via add_span_event."""

    def test_phase_events_recorded_on_workflow_span(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """Phase events appear as span events, not child spans."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "phase_test"},
        ) as span:
            telemetry_service.add_span_event(span, "registry.created")
            telemetry_service.add_span_event(span, "tracker.created")
            telemetry_service.add_span_event(span, "graph.execution.start")
            telemetry_service.add_span_event(span, "result.processing")

        spans = otel_exporter.get_finished_spans()
        # Only 1 span (workflow root) -- phases are events, not child spans
        assert len(spans) == 1

        events = spans[0].events
        event_names = [e.name for e in events]
        assert "registry.created" in event_names
        assert "tracker.created" in event_names
        assert "graph.execution.start" in event_names
        assert "result.processing" in event_names
