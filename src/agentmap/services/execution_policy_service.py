"""
ExecutionPolicyService for AgentMap.

Service that wraps existing policy evaluation functions from agentmap.logging.tracking.policy.
This service provides configuration-aware policy evaluation and follows the established
service wrapper pattern for dependency injection and clean architecture.
"""

import importlib
from typing import Any, Dict, List

from agentmap.models.execution.summary import ExecutionSummary
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class ExecutionPolicyService:
    """
    Service for evaluating execution success policies.

    Wraps the existing policy evaluation functions while providing clean dependency
    injection and configuration access. This service coordinates policy evaluation
    based on configuration settings and provides standardized policy management.
    """

    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        """Initialize service with dependency injection."""
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.logger.info("[ExecutionPolicyService] Initialized")

    def _evaluate_success_policy(
        self,
        summary: ExecutionSummary,
        execution_config: Dict[str, Any],
    ) -> bool:
        """
        Evaluate the success of a graph execution based on the configured policy.

        Args:
            summary: ExecutionSummary object from ExecutionTrackingService
            execution_config: Execution-specific configuration

        Returns:
            Boolean indicating overall success based on policy
        """
        policy_config = execution_config.get("success_policy", {})
        policy_type = policy_config.get("type", "all_nodes")

        if policy_type == "all_nodes":
            return self._evaluate_all_nodes_policy(summary)
        elif policy_type == "final_node":
            return self._evaluate_final_node_policy(summary)
        elif policy_type == "critical_nodes":
            critical_nodes = policy_config.get("critical_nodes", [])
            return self._evaluate_critical_nodes_policy(summary, critical_nodes)
        elif policy_type == "custom":
            custom_fn_path = policy_config.get("custom_function", "")
            if custom_fn_path:
                return self._evaluate_custom_policy(summary, custom_fn_path)
            else:
                self.logger.warning(
                    "Custom policy selected but no function specified. Falling back to all_nodes."
                )
                return self._evaluate_all_nodes_policy(summary)
        else:
            self.logger.warning(
                f"Unknown success policy type: {policy_type}. Falling back to all_nodes."
            )
            return self._evaluate_all_nodes_policy(summary)

    def _evaluate_all_nodes_policy(self, summary: ExecutionSummary) -> bool:
        """All nodes must succeed for the graph to be considered successful."""
        return all(executed_node.success for executed_node in summary.node_executions)

    def _evaluate_final_node_policy(self, summary: ExecutionSummary) -> bool:
        """Only the final node must succeed for the graph to be considered successful."""
        if not summary.node_executions:
            return False

        # Get the last executed node
        final_node = summary.node_executions[-1]
        return final_node.success

    def _evaluate_critical_nodes_policy(
        self, summary: ExecutionSummary, critical_nodes: List[str]
    ) -> bool:
        """Critical nodes must succeed for the graph to be considered successful."""
        if not critical_nodes:
            return True

        # Create a map of node names to their execution results
        node_results = {
            node.node_name: node.success for node in summary.node_executions
        }

        # Check that all critical nodes succeeded
        for critical_node_name in critical_nodes:
            if (
                critical_node_name not in node_results
                or not node_results[critical_node_name]
            ):
                return False

        return True

    def _evaluate_custom_policy(
        self, summary: ExecutionSummary, function_path: str
    ) -> bool:
        """Evaluate using a custom policy function."""
        try:
            module_path, function_name = function_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            custom_function = getattr(module, function_name)
            return bool(custom_function(summary))
        except (ImportError, AttributeError, ValueError) as e:
            self.logger.error(
                f"Error loading custom policy function '{function_path}': {e}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Error executing custom policy function: {e}")
            return False

    def evaluate_success_policy(self, summary: ExecutionSummary) -> bool:
        """
        Evaluate the success of a graph execution based on the configured policy.

        Args:
            summary: ExecutionSummary object from ExecutionTrackingService containing
                     node execution details and overall execution status

        Returns:
            Boolean indicating overall success based on configured policy
        """
        self.logger.debug("[ExecutionPolicyService] Evaluating success policy")

        try:
            execution_config = self.config.get_execution_config()
            result = self._evaluate_success_policy(summary, execution_config)
            policy_type = execution_config.get("success_policy", {}).get(
                "type", "all_nodes"
            )

            self.logger.debug(
                f"[ExecutionPolicyService] Policy evaluation complete. "
                f"Type: {policy_type}, Result: {result}"
            )

            return result

        except Exception as e:
            self.logger.error(f"[ExecutionPolicyService] Error evaluating policy: {e}")
            return False

    def get_available_policies(self) -> List[str]:
        """Return list of valid policy types."""
        return ["all_nodes", "final_node", "critical_nodes", "custom"]

    def validate_policy_config(self, policy_config: Dict[str, Any]) -> List[str]:
        """
        Validate policy configuration and return any errors.

        Args:
            policy_config: Policy configuration dictionary to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        policy_type = policy_config.get("type", "all_nodes")

        if policy_type not in self.get_available_policies():
            errors.append(f"Invalid policy type: {policy_type}")
            return errors

        if policy_type == "critical_nodes":
            critical_nodes = policy_config.get("critical_nodes", [])
            if not isinstance(critical_nodes, list):
                errors.append("critical_nodes must be a list")
            elif not critical_nodes:
                errors.append(
                    "critical_nodes policy requires at least one critical node"
                )

        elif policy_type == "custom":
            custom_function = policy_config.get("custom_function", "")
            if not custom_function:
                errors.append("custom policy requires custom_function to be specified")
            elif not isinstance(custom_function, str):
                errors.append("custom_function must be a string")
            elif "." not in custom_function:
                errors.append(
                    "custom_function must be in format 'module.path.function_name'"
                )

        return errors

    @staticmethod
    def get_policy_description(policy_type: str) -> str:
        """
        Get human-readable description of a policy type.

        Args:
            policy_type: Policy type to describe

        Returns:
            Description string explaining the policy behavior
        """
        descriptions = {
            "all_nodes": "All nodes must succeed for the graph to be considered successful",
            "final_node": "Only the final node must succeed for the graph to be considered successful",
            "critical_nodes": "All specified critical nodes must succeed for the graph to be considered successful",
            "custom": "Uses a custom function to evaluate success based on execution summary",
        }

        return descriptions.get(policy_type, f"Unknown policy type: {policy_type}")

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the policy service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        try:
            execution_config = self.config.get_execution_config()
            current_policy = execution_config.get("success_policy", {})
        except Exception:
            current_policy = {"error": "Unable to load policy configuration"}

        return {
            "service": "ExecutionPolicyService",
            "config_available": self.config is not None,
            "available_policies": self.get_available_policies(),
            "current_policy": current_policy,
            "capabilities": {
                "policy_evaluation": True,
                "policy_validation": True,
                "configuration_integration": True,
                "error_handling": True,
            },
            "wrapped_functions": [
                "evaluate_success_policy",
                "_evaluate_all_nodes_policy",
                "_evaluate_final_node_policy",
                "_evaluate_critical_nodes_policy",
                "_evaluate_custom_policy",
            ],
        }
