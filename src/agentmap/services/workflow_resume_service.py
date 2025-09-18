import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agentmap.di import initialize_di
from agentmap.models.execution.result import ExecutionResult


# Resume operations (extracted from resume_command.py)
class WorkflowResumeService:
    """
    Service for resuming interrupted workflows.

    This also preserves the existing architecture and just extracts the
    reusable logic from resume_command.py
    """

    @staticmethod
    def resume_workflow(
        thread_id: str,
        response_action: str,
        response_data: Optional[Union[Dict[str, Any], str]] = None,
        data_file_path: Optional[str] = None,
        config_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resume workflow using the same logic as resume_command.py

        This preserves the existing resume architecture and just makes it reusable.
        """
        # Initialize DI container (same as resume_command.py)
        container = initialize_di(config_file)
        system_storage_manager = container.system_storage_manager()

        # Check storage availability (same as resume_command.py)
        if not system_storage_manager:
            raise RuntimeError("Storage services are not available")

        # Get services (same as resume_command.py)
        storage_service = system_storage_manager.get_service("json")
        logging_service = container.logging_service()
        logger = logging_service.get_logger("agentmap.workflow.resume")

        # Parse response data (same logic as resume_command.py)
        parsed_response_data = WorkflowResumeService._parse_response_data(
            response_data, data_file_path
        )

        # Get graph services (same as resume_command.py)
        try:
            graph_bundle_service = container.graph_bundle_service()
            graph_runner_service = container.graph_runner_service()
            graph_checkpoint_service = container.graph_checkpoint_service()
            services_available = True
        except Exception as e:
            logger.warning(f"Graph services not available: {e}")
            graph_bundle_service = None
            graph_runner_service = None
            graph_checkpoint_service = None
            services_available = False

        # Create interaction handler (same as resume_command.py)
        from agentmap.deployment.cli.cli_handler import CLIInteractionHandler

        handler = CLIInteractionHandler(
            storage_service=storage_service,
            graph_bundle_service=graph_bundle_service,
            graph_runner_service=graph_runner_service,
            graph_checkpoint_service=graph_checkpoint_service,
        )

        # Resume execution (same as resume_command.py)
        result = handler.resume_execution(
            thread_id=thread_id,
            response_action=response_action,
            response_data=parsed_response_data,
        )

        return {
            "success": True,
            "thread_id": thread_id,
            "response_action": response_action,
            "services_available": services_available,
            "result": result,
        }

    @staticmethod
    def _parse_response_data(
        response_data: Optional[Union[Dict[str, Any], str]] = None,
        data_file_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Parse response data (same logic as resume_command.py)"""

        if response_data:
            if isinstance(response_data, str):
                try:
                    return json.loads(response_data)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in response_data: {e}")
            else:
                return response_data

        elif data_file_path:
            try:
                with open(data_file_path, "r") as f:
                    return json.load(f)
            except FileNotFoundError:
                raise ValueError(f"Data file not found: {data_file_path}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in file: {e}")

        return None


# Convenience function for resume
def resume_workflow(
    thread_id: str,
    response_action: str,
    response_data: Optional[Union[Dict[str, Any], str]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Convenience function for workflow resume that preserves existing architecture.
    """
    return WorkflowResumeService.resume_workflow(
        thread_id=thread_id,
        response_action=response_action,
        response_data=response_data,
        **kwargs,
    )
