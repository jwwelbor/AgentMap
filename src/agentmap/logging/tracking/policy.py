"""
Success policy evaluator for execution tracking.
"""
from typing import Any, Dict, List, Optional, Callable
import importlib

from dependency_injector.wiring import inject, Provide
from agentmap.di.containers import ApplicationContainer
from agentmap.config.configuration import Configuration
from agentmap.logging.service import LoggingService

@inject
def evaluate_success_policy(
    summary: Dict[str, Any],
    configuration: Configuration = Provide[ApplicationContainer.configuration],
    logging_service: LoggingService = Provide[ApplicationContainer.logging.logging_service]

) -> bool:
    """
    Evaluate the success of a graph execution based on the configured policy.
    
    Args:
        summary: Execution summary from ExecutionTracker
        config_path: Optional path to config file
        
    Returns:
        Boolean indicating overall success based on policy
    """
    # Load config
    execution_config = configuration.get_execution_config()
    policy_config = execution_config.get("success_policy", {})
    
    # Get logger
    logger = logging_service.get_logger("agentmap.tracking")  
    # Get policy type with fallback
    policy_type = policy_config.get("type", "all_nodes")
    
    if policy_type == "all_nodes":
        return _evaluate_all_nodes_policy(summary)
    elif policy_type == "final_node":
        return _evaluate_final_node_policy(summary)
    elif policy_type == "critical_nodes":
        critical_nodes = policy_config.get("critical_nodes", [])
        return _evaluate_critical_nodes_policy(summary, critical_nodes)
    elif policy_type == "custom":
        # For custom policy, load the specified function
        custom_fn_path = policy_config.get("custom_function", "")
        if custom_fn_path:
            return _evaluate_custom_policy(summary, custom_fn_path)
        else:
            logger.warning("Custom policy selected but no function specified. Falling back to all_nodes.")
            return _evaluate_all_nodes_policy(summary)
    else:
        logger.warning(f"Unknown success policy type: {policy_type}. Falling back to all_nodes.")
        return _evaluate_all_nodes_policy(summary)

def _evaluate_all_nodes_policy(summary: Dict[str, Any]) -> bool:
    """All nodes must succeed for the graph to be considered successful."""
    return all(
        node_data.get("success", False) 
        for node_name, node_data in summary["node_results"].items()
    )

def _evaluate_final_node_policy(summary: Dict[str, Any]) -> bool:
    """Only the final node must succeed for the graph to be considered successful."""
    if not summary["execution_path"]:
        return False
    
    final_node = summary["execution_path"][-1]
    return summary["node_results"].get(final_node, {}).get("success", False)

def _evaluate_critical_nodes_policy(summary: Dict[str, Any], critical_nodes: List[str]) -> bool:
    """Critical nodes must succeed for the graph to be considered successful."""
    # If no critical nodes specified, consider it successful
    if not critical_nodes:
        return True
    
    # Check that all critical nodes that were executed succeeded
    for node in critical_nodes:
        node_data = summary["node_results"].get(node)
        # If the critical node was executed and failed, graph fails
        if node_data and not node_data.get("success", False):
            return False
    
    return True

@inject
def _evaluate_custom_policy(
    summary: Dict[str, Any], 
    function_path: str,
    logger: LoggingService = Provide[ApplicationContainer.logging.logging_service].get_logger("agentmap.tracking")
) -> bool:
    """Evaluate using a custom policy function."""
    try:
        # Import the custom function (module.path.function_name)
        module_path, function_name = function_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        custom_function = getattr(module, function_name)
        
        # Call the function with the summary
        return bool(custom_function(summary))
    except (ImportError, AttributeError, ValueError) as e:
        logger.error(f"Error loading custom policy function '{function_path}': {e}")
        return False
    except Exception as e:
        logger.error(f"Error executing custom policy function: {e}")
        return False
