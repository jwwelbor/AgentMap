"""Edge processing for graph assembly."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from langgraph.graph import StateGraph

from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.logging_service import LoggingService
from agentmap.services.state_adapter_service import StateAdapterService


@dataclass
class EdgeConfig:
    """Configuration for edge routing."""

    has_success: bool
    has_failure: bool
    has_default: bool
    success_parallel: bool
    success_targets: Union[str, List[str], None]
    failure_parallel: bool
    failure_targets: Union[str, List[str], None]

    @property
    def has_success_and_failure(self) -> bool:
        """Check if both success and failure edges exist."""
        return self.has_success and self.has_failure

    @property
    def has_success_only(self) -> bool:
        """Check if only success edge exists."""
        return self.has_success and not self.has_failure

    @property
    def has_failure_only(self) -> bool:
        """Check if only failure edge exists."""
        return self.has_failure and not self.has_success


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

    def _prepare_edge_config(
        self, edges: Dict[str, Union[str, List[str]]]
    ) -> EdgeConfig:
        """Prepare normalized edge configuration."""
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

        return EdgeConfig(
            has_success=has_success,
            has_failure=has_failure,
            has_default=has_default,
            success_parallel=success_parallel,
            success_targets=success_targets,
            failure_parallel=failure_parallel,
            failure_targets=failure_targets,
        )

    def _log_routing(
        self, node_name: str, edge_type: str, targets: Union[str, List[str]], is_parallel: bool
    ) -> None:
        """Log routing information for edges."""
        prefix = "parallel " if is_parallel else ""
        self.logger.debug(f"[{node_name}] → {prefix}{edge_type} → {targets}")

    def _add_success_failure_routing(
        self, builder: StateGraph, node_name: str, config: EdgeConfig
    ) -> None:
        """Add routing when both success and failure edges exist."""

        def branch(state, s=config.success_targets, f=config.failure_targets):
            return s if state.get("last_action_success", True) else f

        builder.add_conditional_edges(node_name, branch)

        # Log both paths
        success_label = (
            f"parallel success → {config.success_targets}"
            if config.success_parallel
            else f"success → {config.success_targets}"
        )
        failure_label = (
            f"parallel failure → {config.failure_targets}"
            if config.failure_parallel
            else f"failure → {config.failure_targets}"
        )
        self.logger.debug(f"[{node_name}] → {success_label} / {failure_label}")

    def _add_success_routing(
        self, builder: StateGraph, node_name: str, config: EdgeConfig
    ) -> None:
        """Add routing when only success edge exists."""

        def branch(state, t=config.success_targets):
            return t if state.get("last_action_success", True) else None

        builder.add_conditional_edges(node_name, branch)
        self._log_routing(node_name, "success", config.success_targets, config.success_parallel)

    def _add_failure_routing(
        self, builder: StateGraph, node_name: str, config: EdgeConfig
    ) -> None:
        """Add routing when only failure edge exists."""

        def branch(state, t=config.failure_targets):
            return t if not state.get("last_action_success", True) else None

        builder.add_conditional_edges(node_name, branch)
        self._log_routing(node_name, "failure", config.failure_targets, config.failure_parallel)

    def _add_default_routing(
        self, builder: StateGraph, node_name: str, edges: Dict[str, Union[str, List[str]]]
    ) -> None:
        """Add routing when only default edge exists."""
        default_parallel, default_targets = self._normalize_edge_value(
            edges["default"]
        )
        if default_parallel:

            def branch(state, targets=default_targets):
                return targets

            builder.add_conditional_edges(node_name, branch)
            self._log_routing(node_name, "default", default_targets, True)
        else:
            builder.add_edge(node_name, default_targets)
            self._log_routing(node_name, "default", default_targets, False)

    def _add_standard_edges(
        self,
        builder: StateGraph,
        node_name: str,
        edges: Dict[str, Union[str, List[str]]],
    ) -> None:
        """Add standard edge types with parallel support."""
        edge_config = self._prepare_edge_config(edges)

        if edge_config.has_success_and_failure:
            self._add_success_failure_routing(builder, node_name, edge_config)
        elif edge_config.has_success_only:
            self._add_success_routing(builder, node_name, edge_config)
        elif edge_config.has_failure_only:
            self._add_failure_routing(builder, node_name, edge_config)
        elif edge_config.has_default:
            self._add_default_routing(builder, node_name, edges)

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
