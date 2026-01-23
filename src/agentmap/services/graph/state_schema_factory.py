"""
State schema factory for creating LangGraph state schemas.

This module handles the creation of state schemas for LangGraph graphs,
supporting dict, pydantic, and dynamic TypedDict schemas.
"""

from typing import Any, Dict, TypedDict

from agentmap.models.graph import Graph
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class StateSchemaFactory:
    """Factory for creating state schemas for LangGraph graphs."""

    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
    ):
        """Initialize the state schema factory.

        Args:
            app_config_service: Application configuration service
            logging_service: Logging service
        """
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)

    def get_state_schema_from_config(self) -> type:
        """
        Get state schema from configuration.

        Returns:
            State schema type (dict, pydantic model, or other LangGraph-compatible schema)
        """
        try:
            execution_config = self.config.get_execution_config()
            state_schema_config = execution_config.get("graph", {}).get(
                "state_schema", "dict"
            )

            if state_schema_config == "dict":
                return dict

            if state_schema_config == "pydantic":
                return self._get_pydantic_schema(execution_config)

            # Unknown schema type
            self.logger.warning(
                f"Unknown state schema type '{state_schema_config}', falling back to dict"
            )
            return dict

        except Exception as e:
            self.logger.debug(
                f"Could not read state schema from config: {e}, using dict"
            )
            return dict

    def _get_pydantic_schema(self, execution_config: Dict[str, Any]) -> type:
        """Get pydantic BaseModel schema from configuration.

        Args:
            execution_config: Execution configuration dictionary

        Returns:
            Pydantic BaseModel or dict fallback
        """
        try:
            from pydantic import BaseModel

            model_class = execution_config.get("graph", {}).get("state_model_class")
            # TODO: Implement dynamic model class import when needed
            return BaseModel
        except ImportError:
            self.logger.warning(
                "Pydantic requested but not available, falling back to dict"
            )
            return dict

    def create_dynamic_state_schema(self, graph: Graph) -> type:
        """
        Create a TypedDict state schema dynamically from graph structure.

        This enables parallel node execution by allowing LangGraph to track
        individual state fields independently. Without this, concurrent updates
        to a plain dict state schema cause InvalidUpdateError.

        Args:
            graph: Graph domain model with nodes

        Returns:
            TypedDict class with fields for all node outputs
        """
        # Collect all input and output fields from nodes
        field_names = set()
        for node in graph.nodes.values():
            # Add output field
            if node.output:
                field_names.add(node.output)
            # Add input fields (nodes may read from initial state)
            if node.inputs:
                if isinstance(node.inputs, list):
                    field_names.update(node.inputs)
                elif isinstance(node.inputs, str):
                    field_names.add(node.inputs)

        # Add system fields that are always needed
        # These are used by the execution service and orchestrator
        system_fields = {
            "__execution_summary",  # Execution tracking metadata
            "__policy_success",  # Policy evaluation result
            "__next_node",  # Orchestrator dynamic routing
            "last_action_success",  # Standard success tracking
            "graph_success",  # Overall graph success
            "errors",  # Error collection
        }
        field_names.update(system_fields)

        if not field_names:
            # No output fields defined, fall back to dict
            self.logger.debug("No output fields found, using plain dict schema")
            return dict

        # Create TypedDict with all fields as optional Any
        # Using total=False makes all fields optional (not required at initialization)
        state_fields = {name: Any for name in field_names}

        # Create dynamic TypedDict class
        StateSchema = TypedDict(f"{graph.name}State", state_fields, total=False)

        self.logger.debug(
            f"Created dynamic state schema for '{graph.name}' with {len(field_names)} fields: {sorted(field_names)}"
        )

        return StateSchema

    def get_state_schema_for_graph(self, graph: Graph) -> type:
        """
        Get the appropriate state schema for a graph.

        This method determines whether to use a dynamic schema based on the graph
        structure or a config-based schema.

        Args:
            graph: Graph domain model

        Returns:
            State schema type
        """
        try:
            execution_config = self.config.get_execution_config()
            state_schema_config = execution_config.get("graph", {}).get(
                "state_schema", "dynamic"
            )

            # Support both 'dynamic' (new default) and 'auto'
            if state_schema_config in ("dynamic", "auto"):
                return self.create_dynamic_state_schema(graph)
            else:
                return self.get_state_schema_from_config()
        except Exception as e:
            self.logger.debug(
                f"Could not create dynamic state schema: {e}, using config schema"
            )
            return self.get_state_schema_from_config()
