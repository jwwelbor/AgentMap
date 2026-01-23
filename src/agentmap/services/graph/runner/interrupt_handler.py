"""
Interrupt handling for graph execution.

Handles LangGraph interrupts, suspend operations, and human interactions.
Extracted from GraphRunnerService to improve separation of concerns.
"""

from typing import Any, Dict, Optional

from agentmap.models.execution.result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.interaction_handler_service import InteractionHandlerService
from agentmap.services.logging_service import LoggingService


class GraphInterruptHandler:
    """Handles interrupt operations for graph execution."""

    def __init__(
        self,
        logging_service: LoggingService,
        interaction_handler_service: InteractionHandlerService,
    ):
        """
        Initialize interrupt handler.

        Args:
            logging_service: Service for logging operations
            interaction_handler_service: Service for handling user interactions
        """
        self.logging_service = logging_service
        self.interaction_handler = interaction_handler_service
        self.logger = logging_service.get_class_logger(self)

    def log_interrupt_status(
        self, graph_name: str, thread_id: str, interrupt_type: str
    ) -> None:
        """
        Log interrupt/suspend status with appropriate emoji and message.

        Args:
            graph_name: Name of the graph
            thread_id: Thread identifier
            interrupt_type: Type of interrupt (suspend, human_interaction, etc.)
        """
        if interrupt_type in {"suspend", "human_interaction"}:
            self.logger.info(
                f"⏸️  Graph execution suspended for '{graph_name}' "
                f"(thread: {thread_id}, type: {interrupt_type})"
            )
        else:
            self.logger.info(
                f"⏸️  Graph execution interrupted for '{graph_name}' "
                f"(thread: {thread_id}, type: {interrupt_type})"
            )

    def extract_interrupt_type_from_state(self, state: Any) -> str:
        """
        Extract interrupt type from state tasks.

        Args:
            state: LangGraph state object

        Returns:
            Interrupt type string, or 'unknown' if not found
        """
        if not state or not getattr(state, "tasks", None):
            return "unknown"

        first_task = state.tasks[0]
        interrupts = getattr(first_task, "interrupts", None)
        if not interrupts:
            return "unknown"

        interrupt_value = getattr(interrupts[0], "value", {}) or {}
        if isinstance(interrupt_value, dict):
            return interrupt_value.get("type", "unknown")

        return "unknown"

    def extract_interrupt_metadata(
        self,
        state: Any,
        execution_tracker: Any,
        bundle: GraphBundle,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract interrupt metadata from LangGraph state or execution tracker.

        Args:
            state: LangGraph state object
            execution_tracker: Execution tracker object
            bundle: Graph bundle with node configurations

        Returns:
            Dictionary with interrupt metadata, or None if not found
        """
        # Try to extract from LangGraph state first
        if state and getattr(state, "tasks", None):
            first_task = state.tasks[0]
            interrupts = getattr(first_task, "interrupts", None)
            if interrupts:
                interrupt = interrupts[0]
                interrupt_value = getattr(interrupt, "value", None)
                if isinstance(interrupt_value, dict):
                    return {
                        "type": interrupt_value.get("type", "unknown"),
                        "node_name": interrupt_value.get("node_name", "unknown"),
                        "raw": interrupt_value,
                    }

        # Fallback to execution tracker
        if execution_tracker and getattr(execution_tracker, "node_executions", None):
            pending_node = None
            for node in reversed(execution_tracker.node_executions):
                if getattr(node, "success", None) is None:
                    pending_node = node
                    break
            if not pending_node and execution_tracker.node_executions:
                pending_node = execution_tracker.node_executions[-1]

            if pending_node:
                node_name = getattr(pending_node, "node_name", "unknown")
                node_config = None
                if bundle and getattr(bundle, "nodes", None):
                    node_config = bundle.nodes.get(node_name)

                agent_type = (getattr(node_config, "agent_type", "") or "").lower()
                if "suspend" in agent_type:
                    interrupt_type = "suspend"
                elif "human" in agent_type:
                    interrupt_type = "human_interaction"
                else:
                    interrupt_type = "unknown"

                inputs = getattr(pending_node, "inputs", None) or {}
                context = getattr(node_config, "context", {}) if node_config else {}
                if not isinstance(context, dict):
                    context = {}

                return {
                    "type": interrupt_type,
                    "node_name": node_name,
                    "inputs": inputs,
                    "agent_context": context,
                    "fallback": True,
                }

        return None

    def handle_langgraph_interrupt(
        self,
        state: Any,
        bundle: GraphBundle,
        thread_id: str,
        execution_tracker: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle LangGraph GraphInterrupt by extracting and storing metadata.

        Args:
            state: LangGraph state object
            bundle: Graph bundle
            thread_id: Thread identifier
            execution_tracker: Execution tracker object

        Returns:
            Minimal interrupt info dict for downstream handling when available
        """
        from agentmap.services.graph.runner.utils import create_bundle_context

        interrupt_metadata = self.extract_interrupt_metadata(
            state=state, execution_tracker=execution_tracker, bundle=bundle
        )

        if not interrupt_metadata:
            self.logger.warning(
                "No interrupt metadata found during interrupt handling for thread: %s",
                thread_id,
            )
            return None

        interrupt_type = interrupt_metadata.get("type", "unknown")
        node_name = interrupt_metadata.get("node_name", "unknown")
        interrupt_value = interrupt_metadata.get("raw") or {}

        self.logger.debug(
            f"Processing interrupt via metadata: type={interrupt_type}, node={node_name}"
        )

        bundle_context = create_bundle_context(bundle)
        summary_info = {
            "type": interrupt_type,
            "node_name": node_name,
            "thread_id": thread_id,
        }

        if interrupt_type == "human_interaction":
            if not interrupt_value:
                self.logger.warning(
                    "Missing human interaction metadata for node '%s'; skipping interaction storage",
                    node_name,
                )
                return summary_info

            from agentmap.models.human_interaction import (
                HumanInteractionRequest,
                InteractionType,
            )

            interaction_request = HumanInteractionRequest(
                thread_id=thread_id,
                node_name=node_name,
                interaction_type=InteractionType(
                    interrupt_value.get("interaction_type", "text_input")
                ),
                prompt=interrupt_value.get("prompt", ""),
                context=interrupt_value.get("context", {}),
                options=interrupt_value.get("options", []),
                timeout_seconds=interrupt_value.get("timeout_seconds"),
            )

            self.interaction_handler._store_interaction_request(interaction_request)
            self.interaction_handler._store_thread_metadata(
                thread_id=thread_id,
                interaction_request=interaction_request,
                checkpoint_data={
                    "node_name": node_name,
                    "inputs": interrupt_value.get("context", {}),
                    "agent_context": {},
                    "execution_tracker": execution_tracker,
                },
                bundle=bundle,
                bundle_context=bundle_context,
            )

            from agentmap.deployment.cli.display_utils import (
                display_interaction_request,
            )

            display_interaction_request(interaction_request)
            summary_info["interaction_id"] = str(interaction_request.id)

            self.logger.info(
                "✅ Human interaction stored and displayed for thread: %s", thread_id
            )

        elif interrupt_type == "suspend":
            checkpoint_inputs = (
                interrupt_value.get("inputs", {})
                if isinstance(interrupt_value, dict)
                else {}
            )
            if not checkpoint_inputs:
                checkpoint_inputs = interrupt_metadata.get("inputs", {})

            agent_context = (
                interrupt_value.get("agent_context", {})
                if isinstance(interrupt_value, dict)
                else {}
            )
            if not agent_context:
                agent_context = interrupt_metadata.get("agent_context", {})

            checkpoint_payload = {
                "node_name": node_name,
                "inputs": checkpoint_inputs,
                "agent_context": agent_context,
                "execution_tracker": execution_tracker,
            }
            if isinstance(interrupt_value, dict):
                if "reason" in interrupt_value:
                    checkpoint_payload["reason"] = interrupt_value.get("reason")
                if "external_ref" in interrupt_value:
                    checkpoint_payload["external_ref"] = interrupt_value.get(
                        "external_ref"
                    )

            self.interaction_handler._store_thread_metadata_suspend_only(
                thread_id=thread_id,
                checkpoint_data=checkpoint_payload,
                bundle=bundle,
                bundle_context=bundle_context,
            )

            self.logger.info("✅ Suspend checkpoint stored for thread: %s", thread_id)

        else:
            self.logger.warning(
                "⚠️ Unknown interrupt type '%s' for thread: %s",
                interrupt_type,
                thread_id,
            )

        return summary_info

    def create_interrupt_result(
        self,
        graph_name: str,
        thread_id: str,
        state: Any,
        interrupt_type: str = "unknown",
        interrupt_info: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Create an ExecutionResult for an interrupted execution.

        Args:
            graph_name: Name of the graph
            thread_id: Thread identifier
            state: LangGraph state object
            interrupt_type: Type of interrupt
            interrupt_info: Optional interrupt metadata

        Returns:
            ExecutionResult indicating interruption
        """
        from agentmap.models.execution.summary import ExecutionSummary

        # Build interrupt info from provided data or extract from state
        info = dict(interrupt_info) if interrupt_info else {}
        if not info and state and getattr(state, "tasks", None):
            first_task = state.tasks[0]
            interrupts = getattr(first_task, "interrupts", None)
            if interrupts:
                interrupt_value = getattr(interrupts[0], "value", {})
                if isinstance(interrupt_value, dict):
                    info = {
                        "type": interrupt_value.get("type", "unknown"),
                        "node_name": interrupt_value.get("node_name", "unknown"),
                    }

        # Fill in defaults
        info.setdefault("type", interrupt_type)
        info.setdefault("node_name", "unknown")
        info.setdefault("thread_id", thread_id)

        status = (
            "suspended"
            if interrupt_type in {"suspend", "human_interaction"}
            else "interrupted"
        )

        execution_summary = ExecutionSummary(
            graph_name=graph_name,
            status=status,
            graph_success=False,
        )

        final_state = {
            "__interrupted": True,
            "__thread_id": thread_id,
            "__interrupt_info": info,
            "__execution_summary": execution_summary,
            "__interrupt_type": info["type"],
        }

        self.logger.info(
            f"🔄 Returning {status} execution result for thread: {thread_id}"
        )

        return ExecutionResult(
            graph_name=graph_name,
            success=False,
            final_state=final_state,
            execution_summary=execution_summary,
            total_duration=0.0,
            error=None,
        )

    def display_resume_instructions(
        self,
        thread_id: str,
        bundle: GraphBundle,
        interrupt_type: str,
    ) -> None:
        """
        Emit resume instructions via logger and CLI helpers.

        Args:
            thread_id: Thread identifier
            bundle: Graph bundle
            interrupt_type: Type of interrupt
        """
        graph_name = getattr(bundle, "graph_name", "unknown")
        config_file = getattr(bundle, "config_path", None)
        if config_file is not None:
            config_file = str(config_file)
        header = "=" * 60
        config_arg = f" --config {config_file}" if config_file else ""
        base_command = f'agentmap resume {thread_id} "<response>"{config_arg}'

        lines = [
            "",
            header,
            (
                "⏸️  EXECUTION PAUSED - HUMAN INTERACTION REQUIRED"
                if interrupt_type == "human_interaction"
                else "⏸️  EXECUTION SUSPENDED"
            ),
            header,
            f"Thread ID: {thread_id}",
            f"Graph: {graph_name}",
            "",
        ]

        if interrupt_type == "human_interaction":
            lines.extend(
                [
                    "To resume execution, respond with:",
                    f"  {base_command}",
                    "",
                    "Examples:",
                    (
                        f"  • Approve: agentmap resume {thread_id} "
                        f'"approve"{config_arg}'
                    ),
                    (
                        f"  • Reject: agentmap resume {thread_id} "
                        f'"reject"{config_arg}'
                    ),
                    (
                        f"  • Text: agentmap resume {thread_id} "
                        f'"your response"{config_arg}'
                    ),
                ]
            )
        else:
            lines.extend(
                [
                    "To resume execution, provide the external result and run:",
                    f"  {base_command}",
                ]
            )

        lines.append(header)

        self.logger.info("\n".join(lines))

        try:
            from agentmap.deployment.cli.display_utils import (
                display_resume_instructions as cli_display_resume,
            )

            cli_display_resume(
                thread_id=thread_id,
                graph_name=graph_name,
                interrupt_type=interrupt_type,
                config_file=config_file,
            )
        except ImportError:
            self.logger.debug(
                "[GraphInterruptHandler] CLI display utilities unavailable; "
                "logger output provided"
            )
        except Exception as display_error:
            self.logger.debug(
                "[GraphInterruptHandler] Failed to display CLI resume instructions:"
                f" {display_error}"
            )
