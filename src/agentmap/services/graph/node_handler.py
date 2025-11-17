"""
Node handler for managing graph nodes and orchestrator injection.

This module handles adding nodes to the graph and injecting orchestrator
services into orchestration-capable agents.
"""

from typing import Any, Dict, Optional

from agentmap.services.logging_service import LoggingService
from agentmap.services.protocols import OrchestrationCapableAgent


class NodeHandler:
    """Handles node management and orchestrator service injection."""

    def __init__(
        self,
        logging_service: LoggingService,
        orchestrator_service: Any,
    ):
        """Initialize the node handler.

        Args:
            logging_service: Logging service
            orchestrator_service: Orchestrator service for dynamic routing
        """
        self.logger = logging_service.get_class_logger(self)
        self.orchestrator_service = orchestrator_service
        self.orchestrator_nodes = []
        self.orchestrator_node_registry: Optional[Dict[str, Any]] = None
        self.injection_stats = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0,
        }

    def reset_stats(self) -> None:
        """Reset orchestrator tracking and injection statistics."""
        self.orchestrator_nodes = []
        self.injection_stats = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0,
        }

    def set_node_registry(self, node_registry: Optional[Dict[str, Any]]) -> None:
        """Set the orchestrator node registry.

        Args:
            node_registry: Node registry for orchestrator injection
        """
        self.orchestrator_node_registry = node_registry

    def add_node(self, builder: Any, name: str, agent_instance: Any) -> None:
        """
        Add a node to the graph with its agent instance.

        Handles orchestrator service injection for OrchestrationCapableAgent instances.

        Args:
            builder: LangGraph StateGraph builder
            name: Node name
            agent_instance: Agent instance with run method

        Raises:
            ValueError: If orchestrator injection fails
        """
        builder.add_node(name, agent_instance.run)
        class_name = agent_instance.__class__.__name__

        # Only orchestrator agents (not tool selection agents) get dynamic routing
        # OrchestrationCapableAgent has node_registry for dynamic routing
        # ToolSelectionCapableAgent uses orchestrator service for tool selection but uses conditional routing
        if isinstance(agent_instance, OrchestrationCapableAgent) and hasattr(
            agent_instance, "node_registry"
        ):
            self._inject_orchestrator_service(name, agent_instance)

        self.logger.debug(f"🔹 Added node: '{name}' ({class_name})")

    def _inject_orchestrator_service(
        self, name: str, agent_instance: OrchestrationCapableAgent
    ) -> None:
        """Inject orchestrator service and node registry into an agent.

        Args:
            name: Node name
            agent_instance: Agent instance that supports orchestration

        Raises:
            ValueError: If injection fails
        """
        self.orchestrator_nodes.append(name)
        self.injection_stats["orchestrators_found"] += 1

        try:
            # Configure orchestrator service (always available)
            agent_instance.configure_orchestrator_service(self.orchestrator_service)

            # Configure node registry if available
            if self.orchestrator_node_registry:
                agent_instance.node_registry = self.orchestrator_node_registry
                self.logger.debug(
                    f"✅ Injected orchestrator service and node registry into '{name}'"
                )
            else:
                self.logger.debug(
                    f"✅ Injected orchestrator service into '{name}' (no node registry available)"
                )

            self.injection_stats["orchestrators_injected"] += 1
        except Exception as e:
            self.injection_stats["injection_failures"] += 1
            error_msg = f"Failed to inject orchestrator service into '{name}': {e}"
            self.logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg) from e

    def get_orchestrator_nodes(self) -> list:
        """Get list of orchestrator node names.

        Returns:
            List of node names that are orchestrators
        """
        return self.orchestrator_nodes.copy()

    def get_injection_summary(self) -> Dict[str, int]:
        """Get summary of registry injection statistics.

        Returns:
            Dictionary with injection statistics
        """
        return self.injection_stats.copy()
