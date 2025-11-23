"""Edge processing for graph assembly."""

from typing import Any, Dict, List, Optional, Tuple, Union

from langgraph.graph import StateGraph

from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.logging_service import LoggingService
from agentmap.services.state_adapter_service import StateAdapterService


class EdgeProcessor:
    """Processes edges for LangGraph StateGraph instances."""

    def __init__(
        self,
        logging_service: LoggingService,
        function_resolution_service: FunctionResolutionService,
        state_adapter_service: StateAdapterService,
    ):
        self.logger = logging_service.get_class_logger(self)
        self.function_resolution = function_resolution_service
        self.state_adapter = state_adapter_service

    def process_node_edges(
        self,
        builder: StateGraph,
        node_name: str,
        edges: Dict[str, Union[str, List[str]]],
        orchestrator_nodes: List[str],
    ) -> None:
        """Process edges for a node and add them to the graph."""
        if node_name in orchestrator_nodes:
            return
        if not edges:
            return
        if self._try_add_function_edge(builder, node_name, edges):
            return
        self._add_standard_edges(builder, node_name, edges)

    def _try_add_function_edge(
        self,
        builder: StateGraph,
        node_name: str,
        edges: Dict[str, Union[str, List[str]]],
    ) -> bool:
        """Try to add function-based routing edge."""
        for target in edges.values():
            func_ref = self.function_resolution.extract_func_ref(target)
            if func_ref:
                func = self.function_resolution.load_function(func_ref)
                success = edges.get("success")
                failure = edges.get("failure")

                def wrapped(state, f=func, s=success, fa=failure):
                    return f(state, s, fa)

                builder.add_conditional_edges(node_name, wrapped)
                return True
        return False

    def _normalize_edge_value(
        self, edge_value: Union[str, List[str], None]
    ) -> Tuple[bool, Union[str, List[str], None]]:
        """Normalize edge value and determine if parallel."""
        if edge_value is None:
            return False, None
        if isinstance(edge_value, str):
            return False, edge_value
        if isinstance(edge_value, list):
            if len(edge_value) == 0:
                return False, None
            if len(edge_value) == 1:
                return False, edge_value[0]
            return True, edge_value
        return False, str(edge_value)

    def _add_standard_edges(
        self,
        builder: StateGraph,
        node_name: str,
        edges: Dict[str, Union[str, List[str]]],
    ) -> None:
        """Add standard edge types with parallel support."""
        has_success = "success" in edges
        has_failure = "failure" in edges
        has_default = "default" in edges

        success_parallel, success_targets = False, None
        failure_parallel, failure_targets = False, None

        if has_success:
            success_parallel, success_targets = self._normalize_edge_value(
                edges["success"]
            )
        if has_failure:
            failure_parallel, failure_targets = self._normalize_edge_value(
                edges["failure"]
            )

        if has_success and has_failure:

            def branch(state, s=success_targets, f=failure_targets):
                return s if state.get("last_action_success", True) else f

            builder.add_conditional_edges(node_name, branch)
            # Log parallel routing if applicable
            success_label = (
                f"parallel success → {success_targets}"
                if success_parallel
                else f"success → {success_targets}"
            )
            failure_label = (
                f"parallel failure → {failure_targets}"
                if failure_parallel
                else f"failure → {failure_targets}"
            )
            self.logger.debug(f"[{node_name}] → {success_label} / {failure_label}")
        elif has_success:

            def branch(state, t=success_targets):
                return t if state.get("last_action_success", True) else None

            builder.add_conditional_edges(node_name, branch)
            if success_parallel:
                self.logger.debug(
                    f"[{node_name}] → parallel success → {success_targets}"
                )
            else:
                self.logger.debug(f"[{node_name}] → success → {success_targets}")
        elif has_failure:

            def branch(state, t=failure_targets):
                return t if not state.get("last_action_success", True) else None

            builder.add_conditional_edges(node_name, branch)
            if failure_parallel:
                self.logger.debug(
                    f"[{node_name}] → parallel failure → {failure_targets}"
                )
            else:
                self.logger.debug(f"[{node_name}] → failure → {failure_targets}")
        elif has_default:
            default_parallel, default_targets = self._normalize_edge_value(
                edges["default"]
            )
            if default_parallel:
                # For parallel default edges, use conditional edge that returns the list
                def branch(state, targets=default_targets):
                    return targets

                builder.add_conditional_edges(node_name, branch)
                self.logger.debug(
                    f"[{node_name}] → parallel default → {default_targets}"
                )
            else:
                builder.add_edge(node_name, default_targets)
                self.logger.debug(f"[{node_name}] → default → {default_targets}")

    def add_dynamic_router(
        self, builder: StateGraph, node_name: str, failure_target: Optional[str] = None
    ) -> None:
        """Add dynamic routing for orchestrator nodes."""

        def dynamic_router(state):
            if failure_target:
                if not self.state_adapter.get_value(state, "last_action_success", True):
                    return failure_target
            next_node = self.state_adapter.get_value(state, "__next_node")
            if not next_node:
                return None
            self.state_adapter.set_value(state, "__next_node", None)
            return next_node

        builder.add_conditional_edges(node_name, dynamic_router, path_map=None)
