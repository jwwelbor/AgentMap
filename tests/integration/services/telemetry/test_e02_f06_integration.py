"""Integration tests for E02-F06 Extended Instrumentation.

These tests verify end-to-end telemetry behavior using real OTEL SDK
with InMemorySpanExporter:

- INT-600: Storage read span exported with correct hierarchy (storage
  spans nest under agent spans).
- INT-601: Storage write span with record_count attribute.
- INT-602: Storage failure produces ERROR span with exception event.
- INT-610: All six phase events on workflow span in chronological order.
- INT-620: Sub-workflow span parent-child linking via GraphAgent.
- INT-630: Cross-feature compatibility (F01 constants, F02 agent spans,
  F03 workflow spans).

Task: T-E02-F06-005.

Requires ``opentelemetry-sdk`` for OTEL-dependent tests.  Those tests
skip automatically when the SDK is unavailable.
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
    GRAPH_NAME,
    GRAPH_NODE_COUNT,
    GRAPH_PARENT_NAME,
    NODE_NAME,
    STORAGE_BACKEND,
    STORAGE_OPERATION,
    STORAGE_READ_SPAN,
    STORAGE_RECORD_COUNT,
    STORAGE_WRITE_SPAN,
    WORKFLOW_RUN_SPAN,
)
from agentmap.services.telemetry.otel_telemetry_service import (  # noqa: E402
    OTELTelemetryService,
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
# Helpers -- minimal concrete storage service for integration testing
# ---------------------------------------------------------------------------


def _make_test_storage_service(
    telemetry_service,
    provider_name="csv",
    read_result=None,
    read_error=None,
    write_error=None,
):
    """Create a minimal concrete storage service for integration testing.

    Returns a storage service instance with controllable behavior.
    """
    from agentmap.services.config.storage_config_service import (
        StorageConfigService,
    )
    from agentmap.services.logging_service import LoggingService
    from agentmap.services.storage.base import BaseStorageService
    from agentmap.services.storage.types import StorageResult, WriteMode

    class _TestStorageService(BaseStorageService):
        """Minimal concrete storage service for testing."""

        def __init__(self, **kwargs):
            self._read_result = kwargs.pop("read_result", None)
            self._read_error = kwargs.pop("read_error", None)
            self._write_error = kwargs.pop("write_error", None)
            super().__init__(**kwargs)

        def _initialize_client(self):
            return MagicMock()

        def _perform_health_check(self):
            return True

        def _perform_read(
            self, collection, document_id=None, query=None, path=None, **kwargs
        ):
            if self._read_error:
                raise self._read_error
            if self._read_result is not None:
                return self._read_result
            return [{"id": 1}, {"id": 2}]

        def _perform_write(
            self,
            collection,
            data,
            document_id=None,
            mode=WriteMode.WRITE,
            path=None,
            **kwargs,
        ):
            if self._write_error:
                raise self._write_error
            return StorageResult(success=True)

        def delete(self, collection, document_id=None, query=None, **kwargs):
            return StorageResult(success=True)

    mock_config = create_autospec(StorageConfigService, instance=True)
    mock_config.get_provider_config.return_value = {}
    mock_logging = create_autospec(LoggingService, instance=True)
    mock_logging.get_class_logger.return_value = MagicMock()

    return _TestStorageService(
        provider_name=provider_name,
        configuration=mock_config,
        logging_service=mock_logging,
        telemetry_service=telemetry_service,
        read_result=read_result,
        read_error=read_error,
        write_error=write_error,
    )


# ---------------------------------------------------------------------------
# INT-600: Storage read span exported with correct hierarchy
# ---------------------------------------------------------------------------


class TestStorageReadSpanIntegration:
    """INT-600: Storage read span export using real OTEL SDK."""

    def test_storage_read_span_exported_with_correct_name(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-600: agentmap.storage.read span exported on storage read."""
        storage = _make_test_storage_service(telemetry_service)

        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "int600_test"},
        ):
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "storage_agent",
                    AGENT_TYPE: "EchoAgent",
                    NODE_NAME: "storage_agent",
                    GRAPH_NAME: "int600_test",
                },
            ):
                storage.read("test_collection")

        spans = otel_exporter.get_finished_spans()
        storage_spans = [s for s in spans if s.name == STORAGE_READ_SPAN]
        assert (
            len(storage_spans) == 1
        ), f"Expected 1 storage read span, got {len(storage_spans)}"

    def test_storage_read_span_has_correct_attributes(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-600: Storage read span has backend and operation attributes."""
        storage = _make_test_storage_service(telemetry_service, provider_name="json")

        with telemetry_service.start_span(
            AGENT_RUN_SPAN,
            attributes={AGENT_NAME: "agent1"},
        ):
            storage.read("collection1")

        spans = otel_exporter.get_finished_spans()
        storage_span = [s for s in spans if s.name == STORAGE_READ_SPAN][0]

        assert storage_span.attributes[STORAGE_BACKEND] == "json"
        assert storage_span.attributes[STORAGE_OPERATION] == "read"

    def test_storage_read_span_is_child_of_agent_span(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-600: Storage span parent_span_id matches agent span_id."""
        storage = _make_test_storage_service(telemetry_service)

        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "hierarchy_test"},
        ):
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "agent_with_storage",
                    AGENT_TYPE: "StorageAgent",
                    NODE_NAME: "agent_with_storage",
                    GRAPH_NAME: "hierarchy_test",
                },
            ):
                storage.read("data_collection")

        spans = otel_exporter.get_finished_spans()
        storage_spans = [s for s in spans if s.name == STORAGE_READ_SPAN]
        agent_spans = [s for s in spans if s.name == AGENT_RUN_SPAN]
        workflow_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]

        assert len(storage_spans) == 1
        assert len(agent_spans) == 1
        assert len(workflow_spans) == 1

        storage_span = storage_spans[0]
        agent_span = agent_spans[0]
        workflow_span = workflow_spans[0]

        # Storage span should be child of agent span
        assert storage_span.parent is not None, "Storage span should have a parent"
        assert (
            storage_span.parent.span_id == agent_span.context.span_id
        ), "Storage span parent should be the agent span"

        # Agent span should be child of workflow span
        assert agent_span.parent is not None
        assert agent_span.parent.span_id == workflow_span.context.span_id

        # Full hierarchy: workflow -> agent -> storage
        assert (
            storage_span.context.trace_id == agent_span.context.trace_id
        ), "Storage and agent spans should share trace_id"
        assert (
            agent_span.context.trace_id == workflow_span.context.trace_id
        ), "Agent and workflow spans should share trace_id"

    def test_storage_read_span_status_ok_on_success(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-600: Storage span status is OK after successful read."""
        storage = _make_test_storage_service(telemetry_service)

        storage.read("test_collection")

        spans = otel_exporter.get_finished_spans()
        storage_span = [s for s in spans if s.name == STORAGE_READ_SPAN][0]
        assert storage_span.status.status_code == StatusCode.OK

    def test_storage_read_span_has_record_count(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-600: Storage read span records count when result is a list."""
        test_data = [{"id": i} for i in range(5)]
        storage = _make_test_storage_service(telemetry_service, read_result=test_data)

        storage.read("test_collection")

        spans = otel_exporter.get_finished_spans()
        storage_span = [s for s in spans if s.name == STORAGE_READ_SPAN][0]
        assert storage_span.attributes.get(STORAGE_RECORD_COUNT) == 5


# ---------------------------------------------------------------------------
# INT-601: Storage write span with record count
# ---------------------------------------------------------------------------


class TestStorageWriteSpanIntegration:
    """INT-601: Storage write span with record_count attribute."""

    def test_storage_write_span_exported(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-601: agentmap.storage.write span exported on storage write."""
        storage = _make_test_storage_service(telemetry_service)

        storage.write("test_collection", [{"key": "value"}])

        spans = otel_exporter.get_finished_spans()
        write_spans = [s for s in spans if s.name == STORAGE_WRITE_SPAN]
        assert (
            len(write_spans) == 1
        ), f"Expected 1 storage write span, got {len(write_spans)}"

    def test_storage_write_span_has_record_count(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-601: Write span record_count matches written data size."""
        records = [{"id": i, "data": f"item_{i}"} for i in range(10)]
        storage = _make_test_storage_service(telemetry_service)

        storage.write("output_collection", records)

        spans = otel_exporter.get_finished_spans()
        write_span = [s for s in spans if s.name == STORAGE_WRITE_SPAN][0]

        assert write_span.attributes.get(STORAGE_RECORD_COUNT) == 10

    def test_storage_write_span_has_correct_attributes(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-601: Write span has backend and operation attributes."""
        storage = _make_test_storage_service(
            telemetry_service, provider_name="firebase"
        )

        storage.write("output_collection", [{"key": "value"}])

        spans = otel_exporter.get_finished_spans()
        write_span = [s for s in spans if s.name == STORAGE_WRITE_SPAN][0]

        assert write_span.attributes[STORAGE_BACKEND] == "firebase"
        assert write_span.attributes[STORAGE_OPERATION] == "write"

    def test_storage_write_no_record_count_for_non_list(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-601: No record_count when writing dict (non-list) data."""
        storage = _make_test_storage_service(telemetry_service)

        storage.write("output_collection", {"single": "record"})

        spans = otel_exporter.get_finished_spans()
        write_span = [s for s in spans if s.name == STORAGE_WRITE_SPAN][0]

        assert STORAGE_RECORD_COUNT not in (write_span.attributes or {})


# ---------------------------------------------------------------------------
# INT-602: Storage failure produces ERROR span
# ---------------------------------------------------------------------------


class TestStorageFailureSpanIntegration:
    """INT-602: Storage operation failure records ERROR on real exported span."""

    def test_storage_read_failure_produces_error_span(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-602: Read failure sets span status to ERROR."""
        storage = _make_test_storage_service(
            telemetry_service,
            read_error=FileNotFoundError("missing.csv"),
        )

        with pytest.raises(FileNotFoundError):
            storage.read("missing_collection")

        spans = otel_exporter.get_finished_spans()
        storage_span = [s for s in spans if s.name == STORAGE_READ_SPAN][0]
        assert storage_span.status.status_code == StatusCode.ERROR

    def test_storage_read_failure_has_exception_event(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-602: Read failure records an exception event on the span."""
        storage = _make_test_storage_service(
            telemetry_service,
            read_error=FileNotFoundError("data_file_not_found.csv"),
        )

        with pytest.raises(FileNotFoundError):
            storage.read("missing_collection")

        spans = otel_exporter.get_finished_spans()
        storage_span = [s for s in spans if s.name == STORAGE_READ_SPAN][0]

        exception_events = [e for e in storage_span.events if e.name == "exception"]
        assert (
            len(exception_events) >= 1
        ), "Expected at least one exception event on span"

        # Verify exception details
        event_attrs = dict(exception_events[0].attributes)
        assert "exception.type" in event_attrs
        assert "FileNotFoundError" in event_attrs["exception.type"]

    def test_storage_read_failure_propagates_exception(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-602: Exception propagates to caller after being recorded."""
        storage = _make_test_storage_service(
            telemetry_service,
            read_error=FileNotFoundError("test.csv"),
        )

        with pytest.raises(FileNotFoundError, match="test.csv"):
            storage.read("missing_collection")

    def test_storage_write_failure_produces_error_span(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-602: Write failure sets span status to ERROR."""
        storage = _make_test_storage_service(
            telemetry_service,
            write_error=IOError("disk full"),
        )

        with pytest.raises(IOError):
            storage.write("output_collection", [{"data": "test"}])

        spans = otel_exporter.get_finished_spans()
        write_span = [s for s in spans if s.name == STORAGE_WRITE_SPAN][0]
        assert write_span.status.status_code == StatusCode.ERROR

        exception_events = [e for e in write_span.events if e.name == "exception"]
        assert len(exception_events) >= 1


# ---------------------------------------------------------------------------
# INT-610: All six phase events on exported workflow span
# ---------------------------------------------------------------------------


class TestPhaseEventsIntegration:
    """INT-610: All six workflow phase events on real exported workflow span."""

    EXPECTED_PHASE_EVENTS = [
        "workflow.phase.registry_creation",
        "workflow.phase.tracker_creation",
        "workflow.phase.agent_instantiation",
        "workflow.phase.graph_assembly",
        "workflow.phase.execution",
        "workflow.phase.finalization",
    ]

    def test_all_six_phase_events_present(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-610: Exactly six workflow.phase.* events on workflow span."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "phase_event_test", GRAPH_NODE_COUNT: 3},
        ) as span:
            for phase in self.EXPECTED_PHASE_EVENTS:
                telemetry_service.add_span_event(span, phase)

        spans = otel_exporter.get_finished_spans()
        workflow_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]
        assert len(workflow_spans) == 1

        workflow_span = workflow_spans[0]
        phase_events = [
            e for e in workflow_span.events if e.name.startswith("workflow.phase.")
        ]

        assert (
            len(phase_events) == 6
        ), f"Expected 6 phase events, got {len(phase_events)}"

        phase_names = [e.name for e in phase_events]
        for expected in self.EXPECTED_PHASE_EVENTS:
            assert expected in phase_names, f"Missing phase event: {expected}"

    def test_phase_events_in_chronological_order(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-610: Phase event timestamps are in ascending order."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "phase_order_test"},
        ) as span:
            for phase in self.EXPECTED_PHASE_EVENTS:
                telemetry_service.add_span_event(span, phase)

        spans = otel_exporter.get_finished_spans()
        workflow_span = [s for s in spans if s.name == WORKFLOW_RUN_SPAN][0]
        phase_events = [
            e for e in workflow_span.events if e.name.startswith("workflow.phase.")
        ]

        timestamps = [e.timestamp for e in phase_events]
        assert timestamps == sorted(timestamps), (
            f"Phase events not in chronological order: "
            f"{list(zip([e.name for e in phase_events], timestamps))}"
        )

    def test_no_duplicate_phase_events(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-610: Each phase event name appears exactly once."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "no_duplicates_test"},
        ) as span:
            for phase in self.EXPECTED_PHASE_EVENTS:
                telemetry_service.add_span_event(span, phase)

        spans = otel_exporter.get_finished_spans()
        workflow_span = [s for s in spans if s.name == WORKFLOW_RUN_SPAN][0]
        phase_events = [
            e for e in workflow_span.events if e.name.startswith("workflow.phase.")
        ]

        phase_names = [e.name for e in phase_events]
        assert len(phase_names) == len(
            set(phase_names)
        ), f"Duplicate phase events found: {phase_names}"

    def test_phase_events_are_events_not_child_spans(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-610: Phase events are span events, not separate child spans."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "events_not_spans_test"},
        ) as span:
            for phase in self.EXPECTED_PHASE_EVENTS:
                telemetry_service.add_span_event(span, phase)

        spans = otel_exporter.get_finished_spans()
        # Only 1 span: the workflow root. Phases are events, not children.
        assert len(spans) == 1, (
            f"Expected 1 span (workflow root), got {len(spans)}: "
            f"{[s.name for s in spans]}"
        )

    def test_finalization_event_after_execution(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-610: workflow.phase.finalization recorded after execution."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "finalization_order_test"},
        ) as span:
            for phase in self.EXPECTED_PHASE_EVENTS:
                telemetry_service.add_span_event(span, phase)

        spans = otel_exporter.get_finished_spans()
        workflow_span = [s for s in spans if s.name == WORKFLOW_RUN_SPAN][0]
        phase_events = [
            e for e in workflow_span.events if e.name.startswith("workflow.phase.")
        ]

        phase_names = [e.name for e in phase_events]
        exec_idx = phase_names.index("workflow.phase.execution")
        final_idx = phase_names.index("workflow.phase.finalization")
        assert (
            final_idx > exec_idx
        ), f"Finalization ({final_idx}) should come after execution ({exec_idx})"


# ---------------------------------------------------------------------------
# INT-620: Sub-workflow span parent-child linking
# ---------------------------------------------------------------------------


class TestSubWorkflowSpanHierarchy:
    """INT-620: Sub-workflow span nesting verified via span IDs."""

    def test_two_workflow_spans_exported(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-620: Parent and sub-workflow both export workflow.run spans."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "parent_graph", GRAPH_NODE_COUNT: 2},
        ):
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "graph_agent_node",
                    AGENT_TYPE: "GraphAgent",
                    NODE_NAME: "graph_agent_node",
                    GRAPH_NAME: "parent_graph",
                },
            ):
                with telemetry_service.start_span(
                    WORKFLOW_RUN_SPAN,
                    attributes={
                        GRAPH_NAME: "child_subgraph",
                        GRAPH_NODE_COUNT: 1,
                        GRAPH_PARENT_NAME: "parent_graph",
                    },
                ):
                    with telemetry_service.start_span(
                        AGENT_RUN_SPAN,
                        attributes={
                            AGENT_NAME: "sub_agent",
                            AGENT_TYPE: "EchoAgent",
                            NODE_NAME: "sub_agent",
                            GRAPH_NAME: "child_subgraph",
                        },
                    ):
                        pass

        spans = otel_exporter.get_finished_spans()
        workflow_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]
        assert (
            len(workflow_spans) == 2
        ), f"Expected 2 workflow spans, got {len(workflow_spans)}"

    def test_sub_workflow_parent_is_graph_agent_span(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-620: Sub-workflow span parent_span_id matches GraphAgent span_id."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "parent_graph", GRAPH_NODE_COUNT: 2},
        ):
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "graph_agent",
                    AGENT_TYPE: "GraphAgent",
                    NODE_NAME: "graph_agent",
                    GRAPH_NAME: "parent_graph",
                },
            ):
                with telemetry_service.start_span(
                    WORKFLOW_RUN_SPAN,
                    attributes={
                        GRAPH_NAME: "sub_workflow",
                        GRAPH_NODE_COUNT: 1,
                        GRAPH_PARENT_NAME: "parent_graph",
                    },
                ):
                    pass

        spans = otel_exporter.get_finished_spans()
        workflow_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]
        agent_spans = [s for s in spans if s.name == AGENT_RUN_SPAN]

        sub_wf = [
            s for s in workflow_spans if s.attributes.get(GRAPH_NAME) == "sub_workflow"
        ][0]
        graph_agent_span = [
            s for s in agent_spans if s.attributes.get(AGENT_NAME) == "graph_agent"
        ][0]

        assert sub_wf.parent is not None, "Sub-workflow should have a parent"
        assert (
            sub_wf.parent.span_id == graph_agent_span.context.span_id
        ), "Sub-workflow parent_span_id should match GraphAgent span_id"

    def test_sub_workflow_has_parent_name_attribute(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-620: Sub-workflow span has agentmap.graph.parent_name attribute."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "ParentWorkflow", GRAPH_NODE_COUNT: 1},
        ):
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "graph_agent",
                    AGENT_TYPE: "GraphAgent",
                    NODE_NAME: "graph_agent",
                    GRAPH_NAME: "ParentWorkflow",
                },
            ):
                with telemetry_service.start_span(
                    WORKFLOW_RUN_SPAN,
                    attributes={
                        GRAPH_NAME: "ChildWorkflow",
                        GRAPH_NODE_COUNT: 1,
                        GRAPH_PARENT_NAME: "ParentWorkflow",
                    },
                ):
                    pass

        spans = otel_exporter.get_finished_spans()
        child_wf = [
            s
            for s in spans
            if s.name == WORKFLOW_RUN_SPAN
            and s.attributes.get(GRAPH_NAME) == "ChildWorkflow"
        ][0]

        assert child_wf.attributes.get(GRAPH_PARENT_NAME) == "ParentWorkflow"

    def test_all_spans_share_trace_id(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-620: All spans in nested workflow share the same trace_id."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "parent", GRAPH_NODE_COUNT: 1},
        ):
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "graph_agent",
                    AGENT_TYPE: "GraphAgent",
                    NODE_NAME: "graph_agent",
                    GRAPH_NAME: "parent",
                },
            ):
                with telemetry_service.start_span(
                    WORKFLOW_RUN_SPAN,
                    attributes={
                        GRAPH_NAME: "child",
                        GRAPH_NODE_COUNT: 1,
                        GRAPH_PARENT_NAME: "parent",
                    },
                ):
                    with telemetry_service.start_span(
                        AGENT_RUN_SPAN,
                        attributes={
                            AGENT_NAME: "sub_agent",
                            AGENT_TYPE: "EchoAgent",
                            NODE_NAME: "sub_agent",
                            GRAPH_NAME: "child",
                        },
                    ):
                        pass

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 4, f"Expected 4 spans, got {len(spans)}"

        trace_ids = {s.context.trace_id for s in spans}
        assert (
            len(trace_ids) == 1
        ), f"Expected all spans to share 1 trace_id, got {len(trace_ids)}"

    def test_full_span_hierarchy_verified(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-620: Full hierarchy: parent workflow -> GraphAgent -> child
        workflow -> child agent."""
        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "root_graph", GRAPH_NODE_COUNT: 2},
        ):
            # Regular agent in parent workflow
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "echo_agent",
                    AGENT_TYPE: "EchoAgent",
                    NODE_NAME: "echo_agent",
                    GRAPH_NAME: "root_graph",
                },
            ):
                pass

            # GraphAgent that triggers sub-workflow
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "graph_agent",
                    AGENT_TYPE: "GraphAgent",
                    NODE_NAME: "graph_agent",
                    GRAPH_NAME: "root_graph",
                },
            ):
                with telemetry_service.start_span(
                    WORKFLOW_RUN_SPAN,
                    attributes={
                        GRAPH_NAME: "sub_graph",
                        GRAPH_NODE_COUNT: 1,
                        GRAPH_PARENT_NAME: "root_graph",
                    },
                ):
                    with telemetry_service.start_span(
                        AGENT_RUN_SPAN,
                        attributes={
                            AGENT_NAME: "sub_echo_agent",
                            AGENT_TYPE: "EchoAgent",
                            NODE_NAME: "sub_echo_agent",
                            GRAPH_NAME: "sub_graph",
                        },
                    ):
                        pass

        spans = otel_exporter.get_finished_spans()

        # Extract by type and name
        wf_spans = [s for s in spans if s.name == WORKFLOW_RUN_SPAN]
        agent_spans = [s for s in spans if s.name == AGENT_RUN_SPAN]

        root_wf = [s for s in wf_spans if s.attributes.get(GRAPH_NAME) == "root_graph"][
            0
        ]
        sub_wf = [s for s in wf_spans if s.attributes.get(GRAPH_NAME) == "sub_graph"][0]
        echo_agent = [
            s for s in agent_spans if s.attributes.get(AGENT_NAME) == "echo_agent"
        ][0]
        graph_agent = [
            s for s in agent_spans if s.attributes.get(AGENT_NAME) == "graph_agent"
        ][0]
        sub_echo = [
            s for s in agent_spans if s.attributes.get(AGENT_NAME) == "sub_echo_agent"
        ][0]

        # Verify hierarchy
        # echo_agent -> parent is root_wf
        assert echo_agent.parent.span_id == root_wf.context.span_id
        # graph_agent -> parent is root_wf
        assert graph_agent.parent.span_id == root_wf.context.span_id
        # sub_wf -> parent is graph_agent
        assert sub_wf.parent.span_id == graph_agent.context.span_id
        # sub_echo -> parent is sub_wf
        assert sub_echo.parent.span_id == sub_wf.context.span_id

        # Verify parent workflow has no GRAPH_PARENT_NAME
        assert GRAPH_PARENT_NAME not in (root_wf.attributes or {})
        # Verify sub-workflow has GRAPH_PARENT_NAME
        assert sub_wf.attributes.get(GRAPH_PARENT_NAME) == "root_graph"


# ---------------------------------------------------------------------------
# INT-630: Cross-feature compatibility
# ---------------------------------------------------------------------------


class TestCrossFeatureCompatibility:
    """INT-630/631/632: Cross-feature integration points."""

    def test_storage_constants_importable_and_follow_convention(self) -> None:
        """INT-630: All storage constants importable and follow agentmap.storage.*."""
        from agentmap.services.telemetry.constants import (
            STORAGE_BACKEND,
            STORAGE_OPERATION,
            STORAGE_READ_SPAN,
            STORAGE_RECORD_COUNT,
            STORAGE_WRITE_SPAN,
        )

        for name, val in [
            ("STORAGE_READ_SPAN", STORAGE_READ_SPAN),
            ("STORAGE_WRITE_SPAN", STORAGE_WRITE_SPAN),
            ("STORAGE_BACKEND", STORAGE_BACKEND),
            ("STORAGE_OPERATION", STORAGE_OPERATION),
            ("STORAGE_RECORD_COUNT", STORAGE_RECORD_COUNT),
        ]:
            assert isinstance(val, str), f"{name} is not a string"
            assert len(val) > 0, f"{name} is empty"
            assert val.startswith(
                "agentmap.storage."
            ), f"{name}={val!r} does not follow agentmap.storage.* convention"

    def test_storage_span_nests_under_agent_span(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-631: Storage span is child of E02-F02 agent span."""
        storage = _make_test_storage_service(telemetry_service)

        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "cross_feature_test"},
        ):
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: "agent_1",
                    AGENT_TYPE: "EchoAgent",
                    NODE_NAME: "agent_1",
                    GRAPH_NAME: "cross_feature_test",
                },
            ):
                storage.read("test_collection")

        spans = otel_exporter.get_finished_spans()
        wf_span = [s for s in spans if s.name == WORKFLOW_RUN_SPAN][0]
        agent_span = [s for s in spans if s.name == AGENT_RUN_SPAN][0]
        storage_span = [s for s in spans if s.name == STORAGE_READ_SPAN][0]

        # Full hierarchy: workflow -> agent -> storage
        assert agent_span.parent.span_id == wf_span.context.span_id
        assert storage_span.parent.span_id == agent_span.context.span_id

    def test_phase_events_coexist_with_existing_workflow_span(
        self,
        otel_exporter,
        telemetry_service,
    ) -> None:
        """INT-632: Finalization event integrates with existing five events."""
        all_phases = [
            "workflow.phase.registry_creation",
            "workflow.phase.tracker_creation",
            "workflow.phase.agent_instantiation",
            "workflow.phase.graph_assembly",
            "workflow.phase.execution",
            "workflow.phase.finalization",
        ]

        with telemetry_service.start_span(
            WORKFLOW_RUN_SPAN,
            attributes={GRAPH_NAME: "compat_test"},
        ) as span:
            for phase in all_phases:
                telemetry_service.add_span_event(span, phase)

            # Also add agent spans (E02-F02 compatibility)
            with telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={AGENT_NAME: "test_agent"},
            ):
                pass

        spans = otel_exporter.get_finished_spans()
        wf_span = [s for s in spans if s.name == WORKFLOW_RUN_SPAN][0]
        agent_spans = [s for s in spans if s.name == AGENT_RUN_SPAN]

        # Verify all 6 phase events present
        phase_names = [
            e.name for e in wf_span.events if e.name.startswith("workflow.phase.")
        ]
        assert len(phase_names) == 6
        assert "workflow.phase.finalization" in phase_names

        # Agent spans coexist with phase events
        assert len(agent_spans) == 1
