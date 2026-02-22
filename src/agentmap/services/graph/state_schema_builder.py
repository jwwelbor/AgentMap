"""State schema builder for graph assembly."""

from typing import Any, Dict, Optional, TypedDict

from agentmap.models.graph import Graph
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class StateSchemaBuilder:
    """Builds state schemas for LangGraph StateGraph instances."""

    _SYSTEM_FIELDS = {
        "__execution_summary",
        "__policy_success",
        "__next_node",
        "last_action_success",
        "graph_success",
        "errors",
        "subgraph_bundles",
    }

    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)

    def get_state_schema_from_config(self):
        """Get state schema from configuration."""
        try:
            execution_config = self.config.get_execution_config()
            state_schema_config = execution_config.get("graph", {}).get(
                "state_schema", "dict"
            )
            if state_schema_config == "dict":
                return dict
            if state_schema_config == "pydantic":
                try:
                    from pydantic import BaseModel

                    return BaseModel
                except ImportError:
                    self.logger.warning(
                        "Pydantic requested but not available, falling back to dict"
                    )
                    return dict
            self.logger.warning(
                f"Unknown state schema type '{state_schema_config}', falling back to dict"
            )
            return dict
        except Exception as e:
            self.logger.debug(
                f"Could not read state schema from config: {e}, using dict"
            )
            return dict

    def create_dynamic_state_schema(self, graph: Graph) -> type:
        """Create a TypedDict state schema dynamically from graph structure."""
        field_names = set()
        for node in graph.nodes.values():
            if node.output:
                field_names.add(node.output)
            if node.inputs:
                if isinstance(node.inputs, list):
                    field_names.update(node.inputs)
                elif isinstance(node.inputs, str):
                    field_names.add(node.inputs)

        field_names.update(self._SYSTEM_FIELDS)

        if not field_names:
            return dict

        state_fields = {name: Any for name in field_names}
        return TypedDict(f"{graph.name}State", state_fields, total=False)

    def get_schema_for_graph(self, graph: Optional[Graph] = None) -> type:
        """Get the appropriate state schema for a graph."""
        if graph is not None:
            try:
                execution_config = self.config.get_execution_config()
                state_schema_config = execution_config.get("graph", {}).get(
                    "state_schema", "dynamic"
                )
                if state_schema_config in ("dynamic", "auto"):
                    return self.create_dynamic_state_schema(graph)
                return self.get_state_schema_from_config()
            except Exception as e:
                self.logger.warning(
                    f"Failed to get state schema from config, falling back to dict: {e}"
                )
                return dict
        return self.get_state_schema_from_config()
