"""
GraphAgentValidationService for AgentMap.

Service responsible for validating agent instantiation and generating summary reports.
Extracted from GraphAgentInstantiationService for better separation of concerns.
"""

from typing import Any, Dict

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.agent.agent_service_injection_service import (
    AgentServiceInjectionService,
)
from agentmap.services.logging_service import LoggingService


class GraphAgentValidationService:
    """
    Service for validating agent instantiation and generating summary statistics.

    This service provides validation and reporting capabilities for the
    agent instantiation process.
    """

    def __init__(
        self,
        agent_service_injection_service: AgentServiceInjectionService,
        logging_service: LoggingService,
    ):
        """
        Initialize with required services.

        Args:
            agent_service_injection_service: Service for checking service injection status
            logging_service: Service for logging
        """
        self.agent_injection = agent_service_injection_service
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[GraphAgentValidationService] Initialized")

    def validate_instantiation(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Validate that all nodes have properly instantiated agents in node_registry.

        Args:
            bundle: GraphBundle to validate

        Returns:
            Validation summary with status and any issues found
        """
        validation_results = {
            "valid": True,
            "total_nodes": len(bundle.nodes) if bundle.nodes else 0,
            "instantiated_nodes": 0,
            "missing_instances": [],
            "invalid_instances": [],
        }

        if not bundle.nodes:
            validation_results["valid"] = False
            validation_results["error"] = "No nodes in bundle"
            return validation_results

        if not bundle.node_instances:
            validation_results["valid"] = False
            validation_results["error"] = (
                "No node_registry in bundle - agents may not have been instantiated.\n"
                "Try running 'agentmap update-bundle' to ensure bundle has proper agent mappings."
            )
            return validation_results

        for node_name, node in bundle.nodes.items():
            validation_result = self._validate_single_node(
                node_name, bundle.node_instances, validation_results
            )
            if validation_result:
                validation_results["instantiated_nodes"] += 1

        # Log validation results
        self._log_validation_results(validation_results)

        return validation_results

    def _validate_single_node(
        self,
        node_name: str,
        node_instances: Dict[str, Any],
        validation_results: Dict[str, Any],
    ) -> bool:
        """
        Validate a single node's agent instance.

        Args:
            node_name: Name of the node to validate
            node_instances: Dictionary of node instances
            validation_results: Results dict to update with issues

        Returns:
            True if validation passed, False otherwise
        """
        # Check if instance exists in node_registry
        if node_name not in node_instances:
            validation_results["missing_instances"].append(node_name)
            validation_results["valid"] = False
            return False

        agent_instance = node_instances[node_name]

        # Validate instance has required methods - collect all errors
        is_node_valid = True
        if not hasattr(agent_instance, "run"):
            validation_results["invalid_instances"].append(
                (node_name, "Missing 'run' method")
            )
            is_node_valid = False

        if not hasattr(agent_instance, "name"):
            validation_results["invalid_instances"].append(
                (node_name, "Missing 'name' attribute")
            )
            is_node_valid = False

        if not is_node_valid:
            validation_results["valid"] = False

        return is_node_valid

    def _log_validation_results(self, validation_results: Dict[str, Any]) -> None:
        """Log validation results with appropriate level and formatting."""
        if validation_results["valid"]:
            self.logger.debug(
                f"[GraphAgentValidationService] Validation passed: "
                f"{validation_results['instantiated_nodes']}/{validation_results['total_nodes']} nodes instantiated"
            )
        else:
            self.logger.error(
                f"[GraphAgentValidationService] Validation failed: "
                f"Missing instances: {validation_results['missing_instances']}, "
                f"Invalid instances: {validation_results['invalid_instances']}"
            )

    def get_instantiation_summary(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Get a summary of agent instantiation status for the bundle.

        Args:
            bundle: GraphBundle to analyze

        Returns:
            Summary dictionary with instantiation statistics
        """
        summary = {
            "graph_name": bundle.graph_name,
            "total_nodes": len(bundle.nodes) if bundle.nodes else 0,
            "instantiated": 0,
            "missing": 0,
            "agent_types": {},
            "service_injection_stats": {},
        }

        if not bundle.nodes:
            return summary

        node_registry = bundle.node_instances or {}

        for node_name, node in bundle.nodes.items():
            self._update_summary_for_node(node_name, node, node_registry, summary)

        return summary

    def _update_summary_for_node(
        self,
        node_name: str,
        node: Any,
        node_registry: Dict[str, Any],
        summary: Dict[str, Any],
    ) -> None:
        """
        Update summary statistics for a single node.

        Args:
            node_name: Name of the node
            node: Node object
            node_registry: Dictionary of node instances
            summary: Summary dict to update
        """
        agent_type = getattr(node, "agent_type", "unknown")

        # Track agent type counts
        if agent_type not in summary["agent_types"]:
            summary["agent_types"][agent_type] = {
                "count": 0,
                "instantiated": 0,
                "nodes": [],
            }

        summary["agent_types"][agent_type]["count"] += 1
        summary["agent_types"][agent_type]["nodes"].append(node_name)

        # Check instantiation status in node_registry
        if node_name in node_registry:
            summary["instantiated"] += 1
            summary["agent_types"][agent_type]["instantiated"] += 1

            # Get service injection status if available
            agent_instance = node_registry[node_name]
            injection_status = self.agent_injection.get_service_injection_status(
                agent_instance
            )
            summary["service_injection_stats"][node_name] = {
                "protocols_implemented": len(
                    injection_status.get("implemented_protocols", [])
                ),
                "services_ready": injection_status.get("summary", {}).get(
                    "injection_ready_count", 0
                ),
            }
        else:
            summary["missing"] += 1
