"""
Performance benchmark suite for OTEL instrumentation overhead.

Validates REQ-NF06-001: instrumentation overhead < 5% for workflows
with per-node execution times above 10ms.

Run with: pytest -m benchmark -s tests/benchmark/
"""

import statistics
import time

import pytest


def _create_telemetry_service():
    """Create a real OTEL telemetry service backed by InMemorySpanExporter.

    Returns the telemetry service instance configured with a
    SimpleSpanProcessor and InMemorySpanExporter for deterministic,
    low-overhead span collection.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from agentmap.services.telemetry.otel_telemetry_service import (
        OTELTelemetryService,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    service = OTELTelemetryService()
    # Inject the provider's tracer so spans are actually recorded
    service._tracer = provider.get_tracer("agentmap")
    return service


def _run_synthetic_workflow(telemetry_service, node_count, node_delay_ms):
    """Run a synthetic workflow that exercises all major instrumentation points.

    When *telemetry_service* is ``None`` the workflow executes the bare
    sleep loop (baseline path).  When a real service is provided the
    workflow creates a workflow span, records phase events, and creates
    per-node agent spans with lifecycle events -- exercising span
    creation, attribute setting, and event recording.

    Returns wall-clock execution time in seconds.
    """
    delay_s = node_delay_ms / 1000.0
    start = time.monotonic()

    if telemetry_service is not None:
        with telemetry_service.start_span(
            "agentmap.workflow.run",
            attributes={
                "agentmap.graph.name": "benchmark",
                "agentmap.graph.node_count": node_count,
            },
        ) as workflow_span:
            # Record phase events (exercises add_span_event)
            for phase in (
                "workflow.phase.registry_creation",
                "workflow.phase.tracker_creation",
                "workflow.phase.agent_instantiation",
                "workflow.phase.graph_assembly",
                "workflow.phase.execution",
            ):
                telemetry_service.add_span_event(workflow_span, phase)

            # Simulate per-node agent execution
            for i in range(node_count):
                with telemetry_service.start_span(
                    "agentmap.agent.run",
                    attributes={
                        "agentmap.agent.name": f"node_{i}",
                        "agentmap.agent.type": "DefaultAgent",
                    },
                ) as agent_span:
                    telemetry_service.add_span_event(agent_span, "pre_process.start")
                    telemetry_service.add_span_event(agent_span, "process.start")
                    time.sleep(delay_s)
                    telemetry_service.add_span_event(agent_span, "post_process.start")
                    telemetry_service.add_span_event(agent_span, "agent.complete")

            # Finalization phase event
            telemetry_service.add_span_event(
                workflow_span, "workflow.phase.finalization"
            )
    else:
        # Baseline path -- no telemetry overhead
        for _ in range(node_count):
            time.sleep(delay_s)

    elapsed = time.monotonic() - start
    return elapsed


@pytest.mark.benchmark
class TestInstrumentationOverhead:
    """Validate that OTEL instrumentation overhead stays below 5%.

    TC-660: Measures telemetry-active vs telemetry-inactive execution.
    TC-661: Asserts overhead < 5% for per-node times > 10ms.
    TC-663: Prints results to stdout for CI visibility.
    """

    N_RUNS = 20
    NODE_COUNT = 5
    NODE_DELAY_MS = 15  # Above the 10ms threshold per PRD
    OVERHEAD_THRESHOLD_PCT = 5.0

    def test_workflow_overhead_below_threshold(self):
        """REQ-NF06-001: Instrumentation overhead < 5% for workflows
        with per-node execution times above 10ms.
        """
        # -- Baseline (no telemetry) ------------------------------------------
        baseline_times = []
        for _ in range(self.N_RUNS):
            t = _run_synthetic_workflow(
                telemetry_service=None,
                node_count=self.NODE_COUNT,
                node_delay_ms=self.NODE_DELAY_MS,
            )
            baseline_times.append(t)

        # -- Instrumented (real SDK + InMemorySpanExporter) --------------------
        telemetry_service = _create_telemetry_service()
        instrumented_times = []
        for _ in range(self.N_RUNS):
            t = _run_synthetic_workflow(
                telemetry_service=telemetry_service,
                node_count=self.NODE_COUNT,
                node_delay_ms=self.NODE_DELAY_MS,
            )
            instrumented_times.append(t)

        # -- Calculate overhead ------------------------------------------------
        baseline_median = statistics.median(baseline_times)
        instrumented_median = statistics.median(instrumented_times)
        overhead_pct = (instrumented_median - baseline_median) / baseline_median * 100

        # -- Print results for CI visibility (TC-663) --------------------------
        print(f"\n{'=' * 60}")
        print("INSTRUMENTATION OVERHEAD BENCHMARK")
        print(f"{'=' * 60}")
        print(f"Nodes: {self.NODE_COUNT}, " f"Delay per node: {self.NODE_DELAY_MS}ms")
        print(f"Runs: {self.N_RUNS}")
        print(f"Baseline median:      {baseline_median:.6f}s")
        print(f"Instrumented median:  {instrumented_median:.6f}s")
        print(f"Overhead:             {overhead_pct:.2f}%")
        print(f"Threshold:            {self.OVERHEAD_THRESHOLD_PCT:.2f}%")
        result_label = "PASS" if overhead_pct < self.OVERHEAD_THRESHOLD_PCT else "FAIL"
        print(f"Result:               {result_label}")
        print(f"{'=' * 60}")

        # -- Assert (TC-661) ---------------------------------------------------
        assert overhead_pct < self.OVERHEAD_THRESHOLD_PCT, (
            f"Instrumentation overhead {overhead_pct:.2f}% exceeds "
            f"{self.OVERHEAD_THRESHOLD_PCT}% threshold. "
            f"Baseline: {baseline_median:.6f}s, "
            f"Instrumented: {instrumented_median:.6f}s"
        )
