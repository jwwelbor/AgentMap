"""
Agent run() / run_async() lifecycle and telemetry-wrapper mixin for BaseAgent.

Extracted out of ``base_agent.py`` to address three related tech-debt items
(E04-F02 code review):

TD-007
    ``_execute_agent_lifecycle`` (sync) and ``_execute_agent_lifecycle_async``
    duplicated their state-update resolution + completion-logging block
    verbatim.  That logic now lives in a single ``_resolve_state_update()``
    helper (plus ``_handle_lifecycle_interrupt`` / ``_handle_lifecycle_error``
    for the other two duplicated blocks) so the sync and async lifecycles
    cannot drift out of sync.

TD-008
    ``base_agent.py`` exceeded the file/method line-count guidance because
    the sync and async lifecycle + telemetry-wrapper methods lived inline.
    They are relocated here as a mixin, and each method is kept under the
    50-line guidance by delegating shared logic to the helpers above.

TD-009
    ``_run_with_telemetry`` / ``_run_async_with_telemetry`` used to wrap the
    lifecycle call in a ``with self._telemetry_service.start_span(...) as
    span:`` block and treated *any* exception escaping that block --
    including one raised by ``span.__exit__()`` *after* the lifecycle had
    already returned successfully -- as a telemetry failure, and re-ran the
    whole lifecycle via ``_run_core`` / ``_run_async_core``.  That duplicated
    side effects (process() called twice, tracking recorded twice, etc.).

    The span context manager is now driven manually (``__enter__`` /
    ``__exit__``) so failures are handled precisely:

    - A failure creating the span or entering the context manager (i.e.
      *before* the lifecycle runs) still falls back to an uninstrumented
      re-run -- this is the intended, pre-execution fallback path.
    - A failure raised by ``span.__exit__()`` *after* the lifecycle already
      ran (success, error, or interrupt) is logged as a warning and does
      **not** trigger a second lifecycle execution -- the already-computed
      result (or the already-raised exception) is what propagates.
"""

import time
from typing import Any, Dict

from langgraph.errors import GraphInterrupt

from agentmap.services.telemetry.constants import (
    AGENT_NAME,
    AGENT_RUN_SPAN,
    AGENT_TYPE,
    GRAPH_NAME,
    NODE_NAME,
)


class AgentLifecycleMixin:
    """Provides BaseAgent's run()/run_async() lifecycle and telemetry wrapper.

    Expects the including class (BaseAgent) to provide: ``name``, ``context``,
    ``_telemetry_service``, ``execution_tracking_service``,
    ``current_execution_tracker``, ``state_adapter_service``, ``input_fields``,
    ``output_fields``, ``process()``, ``process_async()``, ``_pre_process()``,
    ``_post_process()``, ``_validate_multi_output()``, the ``log_*`` methods,
    and the span helpers ``_record_lifecycle_event`` / ``_set_span_status_ok``
    / ``_record_span_exception``.
    """

    # ------------------------------------------------------------------
    # TD-007: shared helpers used by both the sync and async lifecycles
    # ------------------------------------------------------------------

    def _resolve_state_update(
        self,
        output: Any,
        execution_id: str,
        start_time: float,
        is_async: bool = False,
    ) -> Dict[str, Any]:
        """Resolve process() output into a state-update dict and log completion.

        Shared by ``_execute_agent_lifecycle`` and
        ``_execute_agent_lifecycle_async`` so the multi-output / single-output
        / no-output resolution rules stay identical between the sync and
        async paths (TD-007).
        """
        if isinstance(output, dict) and "state_updates" in output:
            state_updates = output["state_updates"]
            msg = (
                f"Async returning multiple state updates: {list(state_updates.keys())}"
                if is_async
                else f"Returning multiple state updates: {list(state_updates.keys())}"
            )
            self.log_debug(msg)
            result = state_updates
        elif self.output_fields and output is not None:
            if len(self.output_fields) > 1:
                state_updates = self._validate_multi_output(output)
                msg = (
                    f"Async multi-output: updating fields {list(state_updates.keys())}"
                    if is_async
                    else f"Multi-output: updating fields {list(state_updates.keys())}"
                )
                self.log_debug(msg)
                result = state_updates
            else:
                msg = (
                    f"Async set output field '{self.output_fields[0]}' = {output}"
                    if is_async
                    else f"Set output field '{self.output_fields[0]}' = {output}"
                )
                self.log_debug(msg)
                result = {self.output_fields[0]: output}
        else:
            result = {}

        duration = time.time() - start_time
        label = "RUN_ASYNC" if is_async else "RUN"
        self.log_trace(
            f"\n*** AGENT {self.name} {label} COMPLETED [{execution_id}] in {duration:.4f}s ***"
        )
        return result

    def _handle_lifecycle_interrupt(
        self, span: Any, tracker: Any, tracking_service: Any, is_async: bool = False
    ) -> None:
        """Record the suspended-execution bookkeeping shared by both lifecycles.

        Caller is expected to bare ``raise`` immediately afterward so the
        original GraphInterrupt propagates unchanged.
        """
        self._record_lifecycle_event(span, "agent.suspended")
        tracking_service.record_node_result(
            tracker, self.name, True, result={"status": "suspended"}
        )
        prefix = "Async graph" if is_async else "Graph"
        self.log_info(f"{prefix} execution suspended in {self.name}")

    def _handle_lifecycle_error(
        self,
        exc: Exception,
        state: Any,
        inputs: Dict[str, Any],
        tracker: Any,
        tracking_service: Any,
        span: Any,
        execution_id: str,
        start_time: float,
        is_async: bool = False,
    ) -> Dict[str, Any]:
        """Build and return the error state-update shared by both lifecycles."""
        self._record_span_exception(span, exc)

        kind = " (async)" if is_async else ""
        error_msg = f"Error in {self.name}{kind}: {str(exc)}"
        self.log_error(error_msg)

        tracking_service.record_node_result(tracker, self.name, False, error=error_msg)
        graph_success = tracking_service.update_graph_success(tracker)

        error_updates = {
            "graph_success": graph_success,
            "last_action_success": False,
            "errors": [error_msg],
        }

        try:
            self._post_process(state, inputs, error_updates)
        except Exception as post_error:
            post_kind = " async" if is_async else ""
            self.log_error(f"Error in{post_kind} post-processing: {str(post_error)}")

        duration = time.time() - start_time
        label = "RUN_ASYNC" if is_async else "RUN"
        self.log_trace(
            f"\n*** AGENT {self.name} {label} FAILED [{execution_id}] in {duration:.4f}s ***"
        )
        return error_updates

    # ------------------------------------------------------------------
    # TD-009: manual span context-manager handling
    # ------------------------------------------------------------------

    def _exit_span_quietly(
        self, span_cm: Any, exc_type: Any, exc: Any, tb: Any, when: str = ""
    ) -> None:
        """Call ``span_cm.__exit__`` and swallow any exception it raises.

        A failure here is a telemetry-infrastructure problem, not an agent
        problem -- it must never trigger a second lifecycle execution
        (TD-009), so it is logged and discarded rather than propagated or
        used to decide whether to fall back to an uninstrumented re-run.
        """
        try:
            span_cm.__exit__(exc_type, exc, tb)
        except Exception as exit_error:
            self.log_warning(f"Telemetry span exit failed{when}: {exit_error}")

    def _run_with_telemetry(
        self, state: Any, execution_id: str, start_time: float
    ) -> Dict[str, Any]:
        """Run agent lifecycle wrapped in a telemetry span.

        Falls back to ``_run_core`` only when *creating or entering* the span
        fails (pre-execution).  A failure from ``span.__exit__()`` after the
        lifecycle already completed is logged and does not re-run the agent
        (TD-009).
        """
        try:
            span_cm = self._telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: self.name,
                    AGENT_TYPE: self.__class__.__name__,
                    NODE_NAME: self.name,
                    GRAPH_NAME: self.context.get("graph_name", "unknown"),
                },
            )
            span = span_cm.__enter__()
        except Exception as span_creation_error:
            self.log_warning(
                f"Telemetry error, executing without instrumentation: "
                f"{span_creation_error}"
            )
            return self._run_core(state, execution_id, start_time)

        try:
            result = self._execute_agent_lifecycle(
                state, execution_id, start_time, span
            )
        except GraphInterrupt:
            self._exit_span_quietly(
                span_cm, None, None, None, " while handling suspend"
            )
            raise
        except Exception as lifecycle_error:
            self._exit_span_quietly(
                span_cm,
                type(lifecycle_error),
                lifecycle_error,
                lifecycle_error.__traceback__,
                " while handling error",
            )
            raise
        else:
            self._exit_span_quietly(
                span_cm, None, None, None, " after successful execution"
            )
            return result

    def _run_core(
        self, state: Any, execution_id: str, start_time: float
    ) -> Dict[str, Any]:
        """Run agent lifecycle without telemetry instrumentation."""
        return self._execute_agent_lifecycle(state, execution_id, start_time, span=None)

    async def _run_async_with_telemetry(
        self, state: Any, execution_id: str, start_time: float
    ) -> Dict[str, Any]:
        """Async run lifecycle wrapped in a telemetry span.

        Mirrors ``_run_with_telemetry`` (TD-009): only a pre-execution
        span-creation/entry failure falls back to ``_run_async_core``.
        """
        assert self._telemetry_service is not None
        try:
            span_cm = self._telemetry_service.start_span(
                AGENT_RUN_SPAN,
                attributes={
                    AGENT_NAME: self.name,
                    AGENT_TYPE: self.__class__.__name__,
                    NODE_NAME: self.name,
                    GRAPH_NAME: self.context.get("graph_name", "unknown"),
                },
            )
            span = span_cm.__enter__()
        except Exception as span_creation_error:
            self.log_warning(
                f"Telemetry error, executing async without instrumentation: "
                f"{span_creation_error}"
            )
            return await self._run_async_core(state, execution_id, start_time)

        try:
            result = await self._execute_agent_lifecycle_async(
                state, execution_id, start_time, span
            )
        except GraphInterrupt:
            self._exit_span_quietly(
                span_cm, None, None, None, " while handling suspend"
            )
            raise
        except Exception as lifecycle_error:
            self._exit_span_quietly(
                span_cm,
                type(lifecycle_error),
                lifecycle_error,
                lifecycle_error.__traceback__,
                " while handling error",
            )
            raise
        else:
            self._exit_span_quietly(
                span_cm, None, None, None, " after successful execution"
            )
            return result

    async def _run_async_core(
        self, state: Any, execution_id: str, start_time: float
    ) -> Dict[str, Any]:
        """Async run lifecycle without telemetry instrumentation."""
        return await self._execute_agent_lifecycle_async(
            state, execution_id, start_time, span=None
        )

    # ------------------------------------------------------------------
    # Sync / async lifecycles
    # ------------------------------------------------------------------

    def _lifecycle_start(self, state: Any):
        """Resolve tracking service/tracker and extract inputs (shared preamble).

        Raises ValueError if no tracker has been distributed to the agent yet.
        """
        tracking_service = self.execution_tracking_service
        tracker = self.current_execution_tracker
        if tracker is None:
            raise ValueError(
                f"No ExecutionTracker set for agent '{self.name}'. "
                "Tracker must be distributed to agents before graph execution starts."
            )

        inputs = self.state_adapter_service.get_inputs(
            state,
            self.input_fields,
            expected_params=getattr(self, "expected_params", None),
        )
        tracking_service.record_node_start(tracker, self.name, inputs)
        return tracking_service, tracker, inputs

    def _trace_phase(
        self, execution_id: str, phase: str, is_async: bool = False
    ) -> None:
        """Emit the "*** AGENT ... PHASE [id] ***" trace line for *phase*."""
        label = f"ASYNC {phase}" if is_async else phase
        self.log_trace(f"\n*** AGENT {self.name} {label} [{execution_id}] ***")

    def _execute_agent_lifecycle(
        self,
        state: Any,
        execution_id: str,
        start_time: float,
        span: Any = None,
    ) -> Dict[str, Any]:
        """Execute the full agent lifecycle with optional span instrumentation.

        Contains the core run() logic: input extraction, pre-process, process,
        post-process, state update construction, and error handling.  When
        *span* is not None, lifecycle events are recorded on it.
        """
        tracking_service, tracker, inputs = self._lifecycle_start(state)

        try:
            self._record_lifecycle_event(span, "pre_process.start")
            self._trace_phase(execution_id, "PRE-PROCESS START")
            state, inputs = self._pre_process(state, inputs)

            self._record_lifecycle_event(span, "process.start")
            self._trace_phase(execution_id, "PROCESS START")
            output = self.process(inputs)

            self._record_lifecycle_event(span, "post_process.start")
            self._trace_phase(execution_id, "POST-PROCESS START")
            state, output = self._post_process(state, inputs, output)

            self._record_lifecycle_event(span, "agent.complete")
            self._set_span_status_ok(span)
            tracking_service.record_node_result(tracker, self.name, True, result=output)

            return self._resolve_state_update(
                output, execution_id, start_time, is_async=False
            )

        except GraphInterrupt:
            self._handle_lifecycle_interrupt(
                span, tracker, tracking_service, is_async=False
            )
            raise

        except Exception as e:
            return self._handle_lifecycle_error(
                e,
                state,
                inputs,
                tracker,
                tracking_service,
                span,
                execution_id,
                start_time,
                is_async=False,
            )

    async def _execute_agent_lifecycle_async(
        self,
        state: Any,
        execution_id: str,
        start_time: float,
        span: Any = None,
    ) -> Dict[str, Any]:
        """Execute the full agent async lifecycle with optional span instrumentation.

        Mirrors ``_execute_agent_lifecycle`` but calls ``process_async()``
        instead of ``process()`` so subclasses can provide native async work
        while the base-class default keeps the event loop responsive via
        ``run_in_executor`` (REQ-NF-001).

        GraphInterrupt propagates unchanged (REQ-F-001).
        """
        tracking_service, tracker, inputs = self._lifecycle_start(state)

        try:
            self._record_lifecycle_event(span, "pre_process.start")
            self._trace_phase(execution_id, "PRE-PROCESS START", is_async=True)
            state, inputs = self._pre_process(state, inputs)

            self._record_lifecycle_event(span, "process.start")
            self._trace_phase(execution_id, "PROCESS START", is_async=True)
            output = await self.process_async(inputs)

            self._record_lifecycle_event(span, "post_process.start")
            self._trace_phase(execution_id, "POST-PROCESS START", is_async=True)
            state, output = self._post_process(state, inputs, output)

            self._record_lifecycle_event(span, "agent.complete")
            self._set_span_status_ok(span)
            tracking_service.record_node_result(tracker, self.name, True, result=output)

            return self._resolve_state_update(
                output, execution_id, start_time, is_async=True
            )

        except GraphInterrupt:
            self._handle_lifecycle_interrupt(
                span, tracker, tracking_service, is_async=True
            )
            raise

        except Exception as e:
            return self._handle_lifecycle_error(
                e,
                state,
                inputs,
                tracker,
                tracking_service,
                span,
                execution_id,
                start_time,
                is_async=True,
            )
