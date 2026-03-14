"""
Tests for GraphRunnerService phase event completion (T-E02-F06-002).

Verifies that all six graph execution lifecycle phase events are recorded
correctly on the workflow root span via add_span_event.

Test cases TC-630 through TC-633.
"""

from unittest.mock import MagicMock, patch

from tests.unit.services.graph.test_graph_runner_telemetry import (
    _make_graph_runner_service,
    _make_mock_bundle,
    _make_mock_telemetry_with_span,
    _setup_successful_run,
)

ALL_PHASE_EVENTS = [
    "workflow.phase.registry_creation",
    "workflow.phase.tracker_creation",
    "workflow.phase.agent_instantiation",
    "workflow.phase.graph_assembly",
    "workflow.phase.execution",
    "workflow.phase.finalization",
]


def _run_and_collect_phase_events(telemetry_service=None, node_count=2):
    """Run a successful workflow and return the list of phase event names recorded.

    Returns:
        (event_names, service, mocks, mock_telemetry) tuple.
    """
    if telemetry_service is None:
        mock_telemetry, _mock_span = _make_mock_telemetry_with_span()
    else:
        mock_telemetry = telemetry_service

    service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
    bundle = _make_mock_bundle("test_graph", node_count=node_count)
    _setup_successful_run(mocks, bundle)

    mock_current_span = MagicMock()
    mock_current_span.is_recording.return_value = True
    with patch(
        "opentelemetry.trace.get_current_span",
        return_value=mock_current_span,
    ):
        service.run(bundle)

    event_names = []
    for call in mock_telemetry.add_span_event.call_args_list:
        if len(call[0]) >= 2:
            event_names.append(call[0][1])

    return event_names, service, mocks, mock_telemetry


# ---------------------------------------------------------------------------
# TC-630: All six phase events recorded on completion
# ---------------------------------------------------------------------------


class TestTC630AllSixPhaseEvents:
    """TC-630: All six phase events recorded on successful workflow completion."""

    def test_all_six_phase_events_present(self):
        """Exactly six phase events are recorded with correct names."""
        event_names, *_ = _run_and_collect_phase_events()

        for phase in ALL_PHASE_EVENTS:
            assert (
                phase in event_names
            ), f"Phase event '{phase}' not found in recorded events: {event_names}"

    def test_finalization_event_present(self):
        """The workflow.phase.finalization event is among recorded events."""
        event_names, *_ = _run_and_collect_phase_events()

        assert (
            "workflow.phase.finalization" in event_names
        ), f"finalization event not found in: {event_names}"

    def test_exactly_six_phase_events(self):
        """Exactly six phase events are recorded (no extra, no missing)."""
        event_names, *_ = _run_and_collect_phase_events()

        phase_events = [e for e in event_names if e.startswith("workflow.phase.")]
        assert (
            len(phase_events) == 6
        ), f"Expected 6 phase events, got {len(phase_events)}: {phase_events}"


# ---------------------------------------------------------------------------
# TC-631: Finalization event recorded after execution event
# ---------------------------------------------------------------------------


class TestTC631FinalizationOrder:
    """TC-631: Finalization event appears after execution event in call order."""

    def test_finalization_after_execution(self):
        """workflow.phase.finalization is recorded after workflow.phase.execution."""
        event_names, *_ = _run_and_collect_phase_events()

        exec_idx = event_names.index("workflow.phase.execution")
        final_idx = event_names.index("workflow.phase.finalization")
        assert final_idx > exec_idx, (
            f"finalization (idx={final_idx}) should come after "
            f"execution (idx={exec_idx})"
        )

    def test_phase_events_in_lifecycle_order(self):
        """All six phase events appear in the expected lifecycle order."""
        event_names, *_ = _run_and_collect_phase_events()

        # Filter to only phase events and verify order
        phase_events = [e for e in event_names if e.startswith("workflow.phase.")]
        for i, expected_phase in enumerate(ALL_PHASE_EVENTS):
            assert phase_events[i] == expected_phase, (
                f"Expected phase {expected_phase} at position {i}, "
                f"got {phase_events[i]}. Full order: {phase_events}"
            )


# ---------------------------------------------------------------------------
# TC-632: Events on root span via add_span_event, not child spans
# ---------------------------------------------------------------------------


class TestTC632EventsOnRootSpan:
    """TC-632: Phase events recorded via add_span_event, not as child spans."""

    def test_single_start_span_call(self):
        """start_span is called exactly once (for the workflow root span)."""
        _, _, _, mock_telemetry = _run_and_collect_phase_events()

        assert (
            mock_telemetry.start_span.call_count == 1
        ), f"Expected 1 start_span call, got {mock_telemetry.start_span.call_count}"

    def test_phase_events_via_add_span_event(self):
        """All six phase events use add_span_event (not start_span)."""
        event_names, _, _, mock_telemetry = _run_and_collect_phase_events()

        # add_span_event should have at least 6 calls (one per phase)
        assert mock_telemetry.add_span_event.call_count >= 6, (
            f"Expected at least 6 add_span_event calls, "
            f"got {mock_telemetry.add_span_event.call_count}"
        )

        # All phase events should be in the add_span_event calls
        for phase in ALL_PHASE_EVENTS:
            assert (
                phase in event_names
            ), f"Phase '{phase}' not recorded via add_span_event"


# ---------------------------------------------------------------------------
# TC-633: No duplicate phase event names per run
# ---------------------------------------------------------------------------


class TestTC633NoDuplicateEvents:
    """TC-633: Each phase event name appears exactly once."""

    def test_no_duplicate_phase_events(self):
        """Each of the six phase event names appears exactly once."""
        event_names, *_ = _run_and_collect_phase_events()

        phase_events = [e for e in event_names if e.startswith("workflow.phase.")]
        for phase in ALL_PHASE_EVENTS:
            count = phase_events.count(phase)
            assert count == 1, (
                f"Phase event '{phase}' appeared {count} times, expected 1. "
                f"All phase events: {phase_events}"
            )

    def test_total_unique_phase_events_equals_six(self):
        """The set of unique phase event names has exactly six members."""
        event_names, *_ = _run_and_collect_phase_events()

        phase_events = [e for e in event_names if e.startswith("workflow.phase.")]
        unique_phases = set(phase_events)
        assert (
            len(unique_phases) == 6
        ), f"Expected 6 unique phase events, got {len(unique_phases)}: {unique_phases}"
