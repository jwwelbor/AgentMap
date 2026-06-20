"""
WorkflowProgressEvent data model for AgentMap graph progress streaming.

This module defines the single typed event emitted by the streaming generator
``run_workflow_stream_async`` (runtime/workflow_ops.py) and consumed by F05's SSE
transport.  It is a **data-only** dataclass consistent with the ``ExecutionResult``
and ``NodeExecution`` convention (claude.md: "models: data-only").

Design rationale (spec.md §3.3 D-6):
  A discriminated typed event (``event_type`` + ``is_terminal``) rather than a raw
  dict is the minimal addition needed so that F05 has an unambiguous terminal-event
  discriminator for SSE framing, and so that a node output containing a ``success``
  key is never mistaken for the final execution result.

Scope constraint (AC-9 / DRIFT-01):
  This module is scoped to graph progress events only.  It does NOT import from the
  per-token LLM streaming seam (F03).  Graph progress streaming (F04) consumes
  LangGraph's ``.astream(stream_mode="updates")``, not the per-token token seam.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class WorkflowProgressEvent:
    """A single typed event from the graph progress streaming generator.

    This is a **data-only** container — all business logic (sequence counter,
    terminal-result construction, failure mapping) belongs in the producing
    services (``GraphRunnerService.run_stream_async``,
    ``GraphExecutionService.stream_compiled_graph_async``).

    **Discriminated record:** ``event_type`` is the string discriminator;
    ``is_terminal`` is the termination flag.  Together they let consumers
    (including F05's SSE framing) distinguish node events from the final result
    without inspecting field shapes.

    **Non-frozen** (consistent with ``ExecutionResult`` and ``NodeExecution``):
    the producer assigns ``sequence`` incrementally as events are emitted.  A
    frozen dataclass would require reconstructing the object at each counter step.

    Attributes:
        event_type: Discriminator string. One of:
            ``"node_progress"`` — a completed node's output event;
            ``"completed"``    — terminal: graph finished successfully;
            ``"failed"``       — terminal: graph execution failed;
            ``"suspended"``    — terminal: graph interrupted for human interaction.
        sequence: 0-based, monotonically increasing counter assigned by the
            producer.  NOT an engine sequence number.
        is_terminal: ``True`` on exactly one event (the last); ``False`` on all
            ``"node_progress"`` events.
        node_name: Name of the completed node (from the ``.astream(updates)`` key).
            ``None`` on terminal events.
        state_delta: The materialized state update the node produced (the
            ``.astream(updates)`` value dict).  Materialized data only — never an
            iterator (Constraint C1).  ``None`` on terminal events.
        node_duration: Node execution duration in seconds if available from the
            tracker / ``NodeExecution``; ``None`` if not yet recorded.
        result: The execution result dict on terminal events — same shape as the
            dict ``run_workflow_async`` returns for the same input (``success``,
            ``outputs``, ``execution_id``, ``execution_summary``, ``metadata``
            keys; and on suspension: ``interrupted``, ``thread_id``,
            ``interrupt_info``).  ``None`` on ``"node_progress"`` events.
        error: Error description string on ``"failed"`` terminal events; ``None``
            otherwise.
    """

    event_type: str
    sequence: int
    is_terminal: bool

    # Per-node fields — present on "node_progress", None on terminal events
    node_name: Optional[str] = field(default=None)
    state_delta: Optional[Dict[str, Any]] = field(default=None)
    node_duration: Optional[float] = field(default=None)

    # Terminal-only fields — present on terminal events, None on node_progress
    result: Optional[Dict[str, Any]] = field(default=None)
    error: Optional[str] = field(default=None)
