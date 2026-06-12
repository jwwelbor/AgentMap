"""
GraphExecutionService for AgentMap.

Service that executes pre-assembled graphs and manages execution tracking.
Simplified to focus on execution rather than graph building.
"""

import asyncio
import time
from typing import Any, Dict, Optional

from langgraph.errors import GraphInterrupt

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.execution.result import ExecutionResult
from agentmap.services.execution_policy_service import ExecutionPolicyService
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.logging_service import LoggingService
from agentmap.services.state_adapter_service import StateAdapterService


class GraphExecutionService:
    """
    Service for executing pre-assembled graphs.

    This service focuses purely on execution coordination:
    - Takes a pre-assembled, executable graph
    - Manages execution tracking
    - Evaluates success policies
    - Returns execution results
    """

    def __init__(
        self,
        execution_tracking_service: ExecutionTrackingService,
        execution_policy_service: ExecutionPolicyService,
        state_adapter_service: StateAdapterService,
        logging_service: LoggingService,
    ):
        """
        Initialize service with execution dependencies only.

        Args:
            execution_tracking_service: Service for execution tracking
            execution_policy_service: Service for policy evaluation
            state_adapter_service: Service for state management
            logging_service: Service for logging operations
        """
        self.execution_tracking = execution_tracking_service
        self.execution_policy = execution_policy_service
        self.state_adapter = state_adapter_service
        self.logger = logging_service.get_class_logger(self)

        self.logger.info(
            "[GraphExecutionService] Initialized for pre-assembled graph execution"
        )

    def execute_compiled_graph(
        self,
        executable_graph: Any,
        graph_name: str,
        initial_state: Dict[str, Any],
        execution_tracker: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute a pre-compiled/assembled graph.

        Args:
            executable_graph: The compiled graph ready for execution
            graph_name: Name of the graph for tracking
            initial_state: Initial state dictionary
            execution_tracker: Pre-created execution tracker with agents configured
            config: Optional LangGraph config (for checkpoint support with thread_id)

        Returns:
            ExecutionResult with complete execution details
        """
        self.logger.info(f"[GraphExecutionService] Executing graph: {graph_name}")

        start_time = time.time()
        execution_summary = None

        try:
            # Execute the graph (tracker already set on agents during instantiation)
            self.logger.debug(
                f"[GraphExecutionService] Starting graph invocation: {graph_name}"
            )
            self.logger.debug(
                f"[GraphExecutionService] Initial state keys: {list(initial_state.keys())}"
            )

            # Invoke the graph (with optional config for checkpoint support)
            try:
                final_state = executable_graph.invoke(initial_state, config=config)
            except ExecutionInterruptedException as e:
                # Handle execution interruption for human interaction
                self.logger.info(
                    f"[GraphExecutionService] Execution interrupted for human interaction in thread: {e.thread_id}"
                )
                self.logger.debug(
                    f"[GraphExecutionService] Interruption checkpoint data preserved for thread: {e.thread_id}"
                )
                # Re-raise for upper layers to handle
                raise

            # Log final state info
            self.logger.debug(
                f"[GraphExecutionService] Final state type: {type(final_state)}"
            )
            self.logger.debug(
                f"[GraphExecutionService] Final state keys: "
                f"{list(final_state.keys()) if hasattr(final_state, 'keys') else 'N/A'}"
            )

            # Complete execution tracking
            self.execution_tracking.complete_execution(execution_tracker)
            execution_summary = self.execution_tracking.to_summary(
                execution_tracker, graph_name, final_state
            )

            # Calculate execution time and evaluate policy
            execution_time = time.time() - start_time
            graph_success = self.execution_policy.evaluate_success_policy(
                execution_summary
            )

            # Update state with execution metadata
            final_state = self.state_adapter.set_value(
                final_state, "__execution_summary", execution_summary
            )
            final_state = self.state_adapter.set_value(
                final_state, "__policy_success", graph_success
            )

            # Create successful execution result
            result = ExecutionResult(
                graph_name=graph_name,
                success=graph_success,
                final_state=final_state,
                execution_summary=execution_summary,
                total_duration=execution_time,
                error=None,
            )

            self.logger.info(
                f"✅ Graph execution completed: '{graph_name}' in {execution_time:.2f}s"
            )

            return result

        except GraphInterrupt:
            # Re-raise interruption exceptions without wrapping
            raise

        except Exception as e:
            execution_time = time.time() - start_time

            self.logger.error(
                f"❌ Graph execution failed: '{graph_name}' after {execution_time:.2f}s"
            )
            self.logger.error(f"[GraphExecutionService] Error: {str(e)}")

            # Log detailed error for debugging
            import traceback

            self.logger.error(
                f"[GraphExecutionService] Full traceback:\n{traceback.format_exc()}"
            )

            # Try to create execution summary even on error
            try:
                if execution_tracker is not None:
                    self.logger.debug(
                        "[GraphExecutionService] Creating error execution summary"
                    )
                    self.execution_tracking.complete_execution(execution_tracker)
                    execution_summary = self.execution_tracking.to_summary(
                        execution_tracker, graph_name, initial_state
                    )
                    self.logger.debug(
                        f"[GraphExecutionService] Error summary created with "
                        f"{len(execution_summary.node_executions) if execution_summary else 0} node executions"
                    )
            except Exception as summary_error:
                self.logger.error(
                    f"[GraphExecutionService] Failed to create error summary: {summary_error}"
                )
                # Create minimal execution summary on error
                from agentmap.models.execution.summary import ExecutionSummary

                execution_summary = ExecutionSummary(
                    graph_name=graph_name, status="failed", graph_success=False
                )

            # Create error execution result
            result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=initial_state,  # Return original state on error
                execution_summary=execution_summary,
                total_duration=execution_time,
                error=str(e),
            )

            return result

    async def _invoke_compiled_graph_in_thread(
        self,
        executable_graph: Any,
        initial_state: Dict[str, Any],
        config: Optional[Dict[str, Any]],
    ) -> Any:
        """Execute a sync-only compiled graph in a worker thread.

        This is the named, patchable seam required by REQ-NF-008.  Any
        compiled graph that does not expose a native async surface (``ainvoke``)
        is routed through this helper so blocking ``invoke`` never runs directly
        on the event loop.

        Args:
            executable_graph: The compiled graph (sync-only; no ainvoke).
            initial_state: Initial state dictionary.
            config: Optional LangGraph config forwarded to invoke.

        Returns:
            The final state returned by ``executable_graph.invoke``.
        """
        return await asyncio.to_thread(
            executable_graph.invoke, initial_state, config=config
        )

    async def execute_compiled_graph_async(
        self,
        executable_graph: Any,
        graph_name: str,
        initial_state: Dict[str, Any],
        execution_tracker: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """Execute a pre-compiled/assembled graph asynchronously.

        Prefers the compiled graph's native async invocation surface
        (``ainvoke``) when available.  When the compiled graph is sync-only,
        the blocking ``invoke`` call is isolated behind the named worker-thread
        seam ``_invoke_compiled_graph_in_thread`` (REQ-NF-008) so the event
        loop is never blocked.

        The result shape, metadata injection, policy evaluation, and error
        handling are identical to ``execute_compiled_graph`` (AC-001, AC-002).

        Args:
            executable_graph: The compiled graph ready for execution.
            graph_name: Name of the graph for tracking.
            initial_state: Initial state dictionary.
            execution_tracker: Pre-created execution tracker with agents configured.
            config: Optional LangGraph config (for checkpoint support with thread_id).

        Returns:
            ExecutionResult with complete execution details.

        Raises:
            GraphInterrupt: Re-raised without wrapping (same as sync path).
            asyncio.CancelledError: Re-raised without swallowing (REQ-F-009).
        """
        self.logger.info(
            f"[GraphExecutionService] Executing graph (async): {graph_name}"
        )

        start_time = time.time()
        execution_summary = None

        try:
            self.logger.debug(
                f"[GraphExecutionService] Starting async graph invocation: {graph_name}"
            )
            self.logger.debug(
                f"[GraphExecutionService] Initial state keys: {list(initial_state.keys())}"
            )

            # Prefer native async surface; fall back to worker-thread seam for
            # sync-only graphs (REQ-F-003, REQ-NF-001, REQ-NF-008).
            if hasattr(executable_graph, "ainvoke"):
                try:
                    final_state = await executable_graph.ainvoke(
                        initial_state, config=config
                    )
                except ExecutionInterruptedException as e:
                    self.logger.info(
                        f"[GraphExecutionService] Async execution interrupted "
                        f"for human interaction in thread: {e.thread_id}"
                    )
                    raise
            else:
                try:
                    final_state = await self._invoke_compiled_graph_in_thread(
                        executable_graph, initial_state, config
                    )
                except ExecutionInterruptedException as e:
                    self.logger.info(
                        f"[GraphExecutionService] Async fallback execution "
                        f"interrupted in thread: {e.thread_id}"
                    )
                    raise

            self.logger.debug(
                f"[GraphExecutionService] Async final state type: {type(final_state)}"
            )
            self.logger.debug(
                f"[GraphExecutionService] Async final state keys: "
                f"{list(final_state.keys()) if hasattr(final_state, 'keys') else 'N/A'}"
            )

            # Reuse the same tracking, policy, and metadata-injection path as
            # the sync method (AC-001 parity requirement).
            self.execution_tracking.complete_execution(execution_tracker)
            execution_summary = self.execution_tracking.to_summary(
                execution_tracker, graph_name, final_state
            )

            execution_time = time.time() - start_time
            graph_success = self.execution_policy.evaluate_success_policy(
                execution_summary
            )

            final_state = self.state_adapter.set_value(
                final_state, "__execution_summary", execution_summary
            )
            final_state = self.state_adapter.set_value(
                final_state, "__policy_success", graph_success
            )

            result = ExecutionResult(
                graph_name=graph_name,
                success=graph_success,
                final_state=final_state,
                execution_summary=execution_summary,
                total_duration=execution_time,
                error=None,
            )

            self.logger.info(
                f"✅ Async graph execution completed: '{graph_name}' "
                f"in {execution_time:.2f}s"
            )

            return result

        except GraphInterrupt:
            # Re-raise intentional interrupts without wrapping (same as sync).
            raise

        except asyncio.CancelledError:
            # Propagate cancellation; finalize tracker so it is not leaked
            # (REQ-F-009).
            execution_time = time.time() - start_time
            self.logger.info(
                f"[GraphExecutionService] Async execution cancelled: '{graph_name}' "
                f"after {execution_time:.2f}s — finalizing tracker"
            )
            try:
                if execution_tracker is not None:
                    self.execution_tracking.complete_execution(execution_tracker)
            except Exception as finalize_err:
                self.logger.warning(
                    f"[GraphExecutionService] Tracker finalization failed on "
                    f"cancellation: {finalize_err}"
                )
            raise

        except Exception as e:
            execution_time = time.time() - start_time

            self.logger.error(
                f"❌ Async graph execution failed: '{graph_name}' "
                f"after {execution_time:.2f}s"
            )
            self.logger.error(f"[GraphExecutionService] Error: {str(e)}")

            import traceback

            self.logger.error(
                f"[GraphExecutionService] Full traceback:\n{traceback.format_exc()}"
            )

            # Mirror the sync error-summary path (same error taxonomy).
            try:
                if execution_tracker is not None:
                    self.logger.debug(
                        "[GraphExecutionService] Creating async error execution summary"
                    )
                    self.execution_tracking.complete_execution(execution_tracker)
                    execution_summary = self.execution_tracking.to_summary(
                        execution_tracker, graph_name, initial_state
                    )
            except Exception as summary_error:
                self.logger.error(
                    f"[GraphExecutionService] Failed to create async error summary: "
                    f"{summary_error}"
                )
                from agentmap.models.execution.summary import ExecutionSummary

                execution_summary = ExecutionSummary(
                    graph_name=graph_name, status="failed", graph_success=False
                )

            return ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=initial_state,
                execution_summary=execution_summary,
                total_duration=execution_time,
                error=str(e),
            )

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the execution service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphExecutionService",
            "simplified": True,
            "execution_tracking_available": self.execution_tracking is not None,
            "execution_policy_available": self.execution_policy is not None,
            "state_adapter_available": self.state_adapter is not None,
            "dependencies_ready": all(
                [
                    self.execution_tracking is not None,
                    self.execution_policy is not None,
                    self.state_adapter is not None,
                ]
            ),
            "capabilities": {
                "pre_assembled_execution": True,
                "execution_tracking": True,
                "policy_evaluation": True,
                "state_management": True,
                "error_handling": True,
                "interruption_handling": True,
            },
        }
